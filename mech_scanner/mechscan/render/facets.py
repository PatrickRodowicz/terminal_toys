"""The hot path: transform, gather, shade, fill.

This is where the frame time goes, so this is the one module written for the
interpreter rather than for the reader. Three habits run through all of it and
none of them are decoration:

  * Everything the inner loops read is hoisted into a local first. At a few
    thousand facets, an attribute lookup or a global lookup is a per-facet
    cost.
  * shade() and lerp() are inlined, INCLUDING their int() truncations, which is
    what makes this bit-for-bit identical to the version that called them
    rather than merely close to it.
  * Anything that does not change between frames is cached against an exact
    key. The turntable moves the EYE, not the mech, and the lights are
    world-fixed, so world vertices, world normals and lit colours are all the
    numbers they were last frame for a model that has not moved. Keyed on
    everything that CAN move them, so an idle sway or an explode still
    recomputes: exact, not approximate.

Painter's algorithm over individual facets, sorted by mean camera-space depth.
dscape.py can do better than a sort because its blocks sit on a guillotine plan
whose own cuts give an exact order; nothing here is axis-aligned, so there is
no such plan. The sort is wrong only where two hulls interpenetrate, which in
this model happens exclusively inside joints -- a bearing sunk into a limb, a
ram buried in a calf -- where the seam is hidden by the very parts that create
it.
"""
import math
from operator import itemgetter

from ..ansi import quant, shade
from ..lighting import (FILL, GRAD_MIN_H, LIGHT_FLAT, LIGHT_FULL, LIGHT_KEY,
                        SUN)
from ..materials import SOFT_MAT
from ..sweep import WIPE_BAND, WIPE_HELD
from .sensors import (HEAT_LUT, SCAN_COL, SCAN_GRAZE, SENSOR_THERMAL,
                      XRAY_CORE, XRAY_FAR)

_getdepth = itemgetter(0)


def world_vertices(parts, ex):
    """Each part's vertices in world space, cached against the pose.

    Same argument as the normal cache, one stage earlier. On a loaded mesh the
    root frame is fixed and nothing explodes, so this transform produced the
    same five thousand vertices every frame -- 2 ms of it at high detail.
    """
    world = []
    for p in parts:
        M, T = p.frame.M, p.frame.T
        tx = T[0] + p.expdir[0] * ex
        ty = T[1] + p.expdir[1] * ex
        tz = T[2] + p.expdir[2] * ex
        wkey = (M, tx, ty, tz)
        wv = p.__dict__.get('_wv')
        if wv is None or p._wv_key != wkey:
            wv = []
            wa = wv.append
            for v in p.v:
                x, y, z = v
                wa((M[0] * x + M[1] * y + M[2] * z + tx,
                    M[3] * x + M[4] * y + M[5] * z + ty,
                    M[6] * x + M[7] * y + M[8] * z + tz))
            p._wv, p._wv_key = wv, wkey
        world.append(wv)
    return world


def _lit_colours(p, nw, wr, litkey, MAT, lm, sensor, sky_c, bounce_c):
    """Per-facet lit colour, cached.

    The single biggest cost in this program was the shader, at 51-53% of the
    frame, and almost all of what it computed did not change between frames.
    The lights are world-fixed and the turntable moves the eye, so for a facet
    that has not moved, n.SUN, n.FILL, the sheen, the hemisphere ambient and
    the weathering are all exactly the numbers they were last frame. Only fog
    (range) and the selection tint vary, and those two are all that is left in
    the per-frame shader below.
    """
    S0, S1, S2 = SUN
    F0, F1, F2 = FILL
    b0, b1, b2 = bounce_c
    ks0, ks1, ks2 = sky_c[0] - b0, sky_c[1] - b1, sky_c[2] - b2
    soft = SOFT_MAT
    ptemp = p.temp
    lit = []
    la = lit.append
    for _fi, (_idx, _mat, _ln, _lc) in enumerate(p.faces):
        base = MAT[_mat]
        n0, n1, n2 = nw[_fi]
        wear = wr[_fi]
        if sensor == SENSOR_THERMAL:
            t_ = ptemp[_fi] if ptemp else 0.0
            ti = int(t_ * 64.0)
            base = HEAT_LUT[ti if 0 <= ti <= 64 else 0]
        if lm == LIGHT_FLAT or sensor == SENSOR_THERMAL:
            la(base)
            continue
        ndl = n0 * S0 + n1 * S1 + n2 * S2
        if lm == LIGHT_KEY:
            k = (0.34 + 0.78 * ndl) if ndl > 0.0 else 0.34
            k *= wear
            la((int(base[0] * k), int(base[1] * k), int(base[2] * k)))
            continue
        ndf = n0 * F0 + n1 * F1 + n2 * F2
        k = 0.30
        if ndl > 0.0:
            x2 = ndl * ndl
            x4 = x2 * x2
            k += 0.72 * ndl + 0.55 * x4 * x4 * ndl
        if ndf > 0.0:
            k += 0.26 * ndf
        k *= wear
        r = int(base[0] * k)
        g = int(base[1] * k)
        b = int(base[2] * k)
        if r > 255:
            r = 255
        elif r < 0:
            r = 0
        if g > 255:
            g = 255
        elif g < 0:
            g = 0
        if b > 255:
            b = 255
        elif b < 0:
            b = 0
        t = 0.5 * (n2 + 1.0)
        ar = int(b0 + ks0 * t)
        ag = int(b1 + ks1 * t)
        ab = int(b2 + ks2 * t)
        r = int(r + (ar - r) * 0.16)
        g = int(g + (ag - g) * 0.16)
        b = int(b + (ab - b) * 0.16)
        if soft[_mat]:
            r = int(r + (base[0] - r) * 0.55)
            g = int(g + (base[1] - g) * 0.55)
            b = int(b + (base[2] - b) * 0.55)
        la((r, g, b))
    p._lit, p._lit_key = lit, litkey
    return lit


def gather(parts, world, cam, view, sel, sel_part, scan_seen, scan_left):
    """Project, cull and queue every visible facet, sorted back to front.

    Returns (queue, scan_left). A queue entry is
    (mean depth, screen points, world normal, lit colour, highlight).
    """
    ca, sa, ce, se = cam.ca, cam.sa, cam.ce, cam.se
    camX, camY, camZ = cam.x, cam.y, cam.z
    dist, mcz, Fl, OX, OY = cam.dist, cam.mcz, cam.fl, cam.ox, cam.oy
    fsub = Fl * cam.subx

    stl_mode = view.stl_mode
    zen = view.zen
    sensor = view.sensor
    wireonly = view.wireonly
    see_through = view.see_through
    cutplane = view.cutplane
    ao_on = view.ao_on
    lm = view.light_mode
    pal = view.pal
    MAT = view.mat
    sky_c, bounce_c = view.sky_c, view.bounce_c

    queue = []
    qa = queue.append
    for pi, p in enumerate(parts):
        wv = world[pi]
        M = p.frame.M
        hot = p is sel_part and not zen
        praw = p.temp if sensor == SENSOR_THERMAL else None
        # On a loaded mesh the highlight is per FACET, not per part: one Part
        # carries the whole shell and the selection is a section of it.
        psec = p.sec if (stl_mode and not zen) else None
        # Occlusion lives inside the per-face brightness multiplier, so
        # toggling it is a choice of list, not a branch in the shader.
        wr = p.wear if ao_on else p.wear_plain

        # Screen x,y in one list and depth in another, rather than (x, y, z)
        # triples. The rasteriser and the shader both want (x, y) pairs, so
        # with triples every facet had to build three fresh pairs plus a tuple
        # to hold them -- five allocations per facet where two will do.
        sp = []
        sz = []
        spa = sp.append
        sza = sz.append
        for w in wv:
            wx, wy, wz = w
            wz -= mcz
            xr = wx * ca + wy * sa
            yr = -wx * sa + wy * ca
            zv = yr * ce - wz * se + dist
            if zv < 0.6:
                zv = 0.6
            spa((OX + fsub * xr / zv,
                 OY - Fl * (yr * se + wz * ce) / zv))
            sza(zv)

        # Vertex indices on their own, cached with the normals. The gather loop
        # unpacked (idx, mat, ln, lc) per facet and used one of the four -- mat
        # moved into the lit cache and ln/lc were never read here -- so three
        # of every four unpacks were paid for nothing.
        gidx = p.__dict__.get('_gidx')
        if gidx is None:
            gidx = p._gidx = [f[0] for f in p.faces]
        nw = p.__dict__.get('_nw')
        if nw is None or p._nw_M != M:
            m0, m1, m2, m3, m4, m5, m6, m7, m8 = M
            nw = [(m0 * ln[0] + m1 * ln[1] + m2 * ln[2],
                   m3 * ln[0] + m4 * ln[1] + m5 * ln[2],
                   m6 * ln[0] + m7 * ln[1] + m8 * ln[2])
                  for _i, _m, ln, _c in p.faces]
            p._nw, p._nw_M = nw, M

        if wireonly:
            lit = None
        else:
            litkey = (M, lm, pal, ao_on, sensor, id(MAT))
            lit = p.__dict__.get('_lit')
            if lit is None or p._lit_key != litkey:
                lit = _lit_colours(p, nw, wr, litkey, MAT, lm, sensor,
                                   sky_c, bounce_c)

        # Local, and only touched while the scan is incomplete: once it
        # finishes this whole thing costs one `if scan_left` per facet, and
        # this is the hot loop in the program.
        pseen = scan_seen[pi]
        lit_ = lit or gidx          # any same-length list will do
        for fi, (idx, n, lc_) in enumerate(zip(gidx, nw, lit_)):
            h = hot if psec is None else (psec[fi] == sel)
            a = wv[idx[0]]
            # Backface test against the eye, not against a global azimuth:
            # under perspective the two disagree at the edges of a wide model
            # and the disagreement is a hole. XRAY is exactly the mode that
            # wants the far side, so it is the one mode that skips this.
            if see_through:
                pass
            elif ((camX - a[0]) * n[0] + (camY - a[1]) * n[1] +
                    (camZ - a[2]) * n[2]) <= 0.0:
                continue
            if cutplane is not None and a[2] > cutplane:
                continue          # cutaway: nothing above the station
            if scan_left and not pseen[fi]:
                pseen[fi] = 1
                scan_left -= 1
            if praw is not None:
                h = praw[fi]      # thermal carries temperature, not select
            if len(idx) == 3:
                i0, i1, i2 = idx
                qa(((sz[i0] + sz[i1] + sz[i2]) / 3,
                    (sp[i0], sp[i1], sp[i2]), n, lc_, h))
                continue
            zsum = 0.0
            pts = []
            for i in idx:
                pts.append(sp[i])
                zsum += sz[i]
            zsum /= len(idx)
            qa((zsum, pts, n, lc_, h))

    queue.sort(key=_getdepth, reverse=True)
    return queue, scan_left


def draw_solid(ras, queue, view, sil, wipey, wire):
    """Shade and fill every queued facet, accumulating the silhouette box.

    The silhouette box lives in four LOCAL floats for the length of this loop
    and is written back once at the end. It was four list slots, and a list
    index is a bytecode dispatch plus a bounds check -- eight of them per
    facet, in the hottest loop in the program, to maintain a number nothing
    reads until the loop is over.
    """
    fog0, fogd = view.fog0, view.fogd
    fgr, fgg, fgb = view.fogc
    SCr, SCg, SCb = view.sel_col
    psel_on = view.psel_on
    fog_on = view.light_mode == LIGHT_FULL and view.sensor != SENSOR_THERMAL
    rfill, rfill3 = ras.fill, ras.fill3
    sx0, sy0, sx1, sy1 = sil
    for zsum, pts, n, lc_, hot in queue:
        r, g, b = lc_
        if fog_on:
            fog = (zsum - fog0) * fogd
            if fog > 0.0:
                fog *= 0.30
                if fog > 0.34:
                    fog = 0.34
                r = int(r + (fgr - r) * fog)
                g = int(g + (fgg - g) * fog)
                b = int(b + (fgb - b) * fog)
        if hot and psel_on:
            r = int(r + (SCr - r) * 0.34)
            g = int(g + (SCg - g) * 0.34)
            b = int(b + (SCb - b) * 0.34)
        if len(pts) == 3:
            (ax_, ay_), (bx_, by_), (cx_, cy_) = pts
            ylo = ay_ if ay_ < by_ else by_
            if cy_ < ylo:
                ylo = cy_
            yhi = ay_ if ay_ > by_ else by_
            if cy_ > yhi:
                yhi = cy_
            if ax_ < sx0:
                sx0 = ax_
            if ax_ > sx1:
                sx1 = ax_
            if bx_ < sx0:
                sx0 = bx_
            if bx_ > sx1:
                sx1 = bx_
            if cx_ < sx0:
                sx0 = cx_
            if cx_ > sx1:
                sx1 = cx_
        else:
            ylo = yhi = pts[0][1]
            for pt in pts:
                px_, py = pt
                if py < ylo:
                    ylo = py
                elif py > yhi:
                    yhi = py
                if px_ < sx0:
                    sx0 = px_
                elif px_ > sx1:
                    sx1 = px_
        if ylo < sy0:
            sy0 = ylo
        if yhi > sy1:
            sy1 = yhi
        if wipey is not None:
            if ylo > wipey:
                r = int(r * WIPE_HELD)
                g = int(g * WIPE_HELD)
                b = int(b * WIPE_HELD)
            elif yhi > wipey - WIPE_BAND:
                r = int(r + (SCAN_COL[0] - r) * 0.66)
                g = int(g + (SCAN_COL[1] - g) * 0.66)
                b = int(b + (SCAN_COL[2] - b) * 0.66)
        # Gradient only where it can be seen -- see GRAD_MIN_H.
        if yhi - ylo >= GRAD_MIN_H:
            c = (r, g, b)
            rfill(pts, quant(shade(c, 1.05)), quant(shade(c, 0.93)))
        elif len(pts) == 3:
            p0, p1, p2 = pts
            rfill3(p0, p1, p2, (r // 6 * 6, g // 6 * 6, b // 6 * 6))
        else:
            rfill(pts, (r // 6 * 6, g // 6 * 6, b // 6 * 6))
        if wire:
            wc = quant(shade((r, g, b), 1.9))
            for i in range(len(pts)):
                a, b_ = pts[i - 1], pts[i]
                ras.line_c(a[0], a[1], b_[0], b_[1], wc)
    sil[0], sil[1], sil[2], sil[3] = sx0, sy0, sx1, sy1


def draw_instrument(ras, queue, cam, view, sil, sim, reactor_m):
    """LIDAR and XRAY: the two channels that draw no surfaces.

    LIDAR is a range return, so it is drawn as one -- a point per vertex of
    every facet the beam can reach, brightness by range, no contour filter. A
    point cloud does not scribble the way six thousand outlines did, and the
    density falling off around the curve of the hull is the shape of the return
    rather than an artefact.

    XRAY is the inversion: the near skin drops to a faint outline and the far
    side is drawn bright, which is what makes the channel mean something -- you
    are looking through the front of the machine at the inside of its back.
    """
    near, far = view.fog0, view.fog1
    span = (far - near) or 1.0
    wc0 = SCAN_COL
    camX, camY, camZ = cam.x, cam.y, cam.z
    # View direction, good enough at this range. The SIGN of this dot is free
    # information the grazing test was throwing away with abs(): positive is
    # the near side, negative the far.
    vlen = math.sqrt(camX * camX + camY * camY + camZ * camZ) or 1.0
    vdx, vdy, vdz = camX / vlen, camY / vlen, camZ / vlen

    # The silhouette has to be accumulated here as well as in the fill loop. It
    # was not, and the consequence was that the lock frame -- and, once the
    # strip moved onto row 0, every readout on the display -- disappeared in
    # precisely the two channels you would be scanning a target with. Over
    # every queued facet, not just the contours: the box is the target's
    # extent, which does not depend on which facets happen to graze the view.
    for zsum, pts, n, lc_, hot in queue:
        for px_, py_ in pts:
            if px_ < sil[0]:
                sil[0] = px_
            if px_ > sil[2]:
                sil[2] = px_
            if py_ < sil[1]:
                sil[1] = py_
            if py_ > sil[3]:
                sil[3] = py_

    if not view.see_through:
        rp_ = ras.point
        for zsum, pts, n, lc_, hot in queue:
            g = 1.0 - (zsum - near) / span
            if g < 0.15:
                g = 0.15
            elif g > 1.0:
                g = 1.0
            # Facets square to the beam return more energy than facets glancing
            # off it, which is true of lidar and also happens to shade the
            # cloud.
            d = n[0] * vdx + n[1] * vdy + n[2] * vdz
            if d < 0.0:
                d = -d
            c = quant(shade(wc0, g * (0.34 + 0.66 * d)))
            sx_ = sy_ = 0.0
            for px_, py_ in pts:
                rp_(int(px_), int(py_), c)
                sx_ += px_
                sy_ += py_
            # Centroid as well as vertices: vertices are shared between
            # neighbouring facets so they land on top of each other, and the
            # cloud came out thinner than the facet count suggests.
            rp_(int(sx_ / len(pts)), int(sy_ / len(pts)), c)
        return

    for zsum, pts, n, lc_, hot in queue:
        d = n[0] * vdx + n[1] * vdy + n[2] * vdz
        if d < 0.0:                   # far side: the payload
            # Grazing filter on the far side too. Drawing every back-facing
            # outline in full measured at 32.5 ms/frame against 22.8 for the
            # old channel, and 67 ms at high detail, which is fifteen frames a
            # second for an ambient display. The inversion is what makes this
            # channel mean something, not the density -- so keep the inversion
            # and pay for the contours only.
            if d < -SCAN_GRAZE:
                continue
            g = 0.45 + 0.55 * (1.0 - (zsum - near) / span)
            if g < 0.2:
                g = 0.2
            elif g > 1.0:
                g = 1.0
            c = quant(shade(XRAY_FAR, g))
        else:                         # near skin: a ghost
            if d > SCAN_GRAZE:
                continue
            c = quant(shade(wc0, 0.30))
        for i in range(len(pts)):
            a_, b_ = pts[i - 1], pts[i]
            ras.line_c(a_[0], a_[1], b_[0], b_[1], c)

    if not reactor_m:
        return
    # The reactor is marked because on a real diagnostic x-ray the power plant
    # is the one thing you could not miss.
    rs = cam.project(reactor_m[0], reactor_m[1], reactor_m[2])
    rx_, ry_ = int(rs[0]), int(rs[1])
    # Pulsing, because a fusion plant on an instrument is never drawn still.
    # Floor the pulse high: at 0.62 the trough quantised to (158,143,93), which
    # is olive -- the core spent half its cycle reading as a brown stain rather
    # than a light source.
    pw = 0.86 + 0.14 * math.sin(sim * 3.4)
    for dy_ in range(-4, 5):
        for dx_ in range(-8, 9):
            q = dx_ * dx_ * 0.25 + dy_ * dy_
            if q > 16.0:
                continue
            # Cut the tail of the falloff off rather than letting it run to
            # black: the dim outer ring was being drawn ON TOP of the bright
            # interior structure and reading as a dark halo, which is the
            # opposite of a glow.
            gi = pw * (1.0 - q / 24.0)
            if gi < 0.58:
                continue
            ras.point(rx_ + dx_, ry_ + dy_,
                      (255, 255, 240) if q < 1.5
                      else quant(shade(XRAY_CORE, gi)))
