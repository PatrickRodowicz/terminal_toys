"""Everything drawn behind the model: sky, ground, grid, cast shadow.

All of it is cheap -- a handful of polygons and a few dozen lines -- and all of
it is skipped wholesale in the instrument channels, because a scan return draws
on an instrument field rather than on a daylit sky. Leaving the sky and the
shadow in put olive ground and a hard sun shadow behind a lidar trace, which
read as a bug rather than as a picture.
"""
import math

from ..ansi import lerp, quant, shade
from ..lighting import SUN
from ..math3d import hull2d
from .sensors import SCAN_BG


def draw_sky(ras, P, pxh, stars, stars_on, sim, nosun):
    if nosun:
        ras.clear(quant(SCAN_BG))
        return
    sky0, sky1 = P['sky']
    horizon = int(pxh * 0.60)
    for yb in range(0, horizon, 2):
        t = yb / max(1, horizon)
        ras.hband(yb, yb + 2, quant(lerp(sky0, sky1, t * t)))
    ras.hband(horizon, pxh, quant(P['ground']))
    if stars_on and P['star'] is not None:
        sc_ = P['star']
        for sxp, syp, br, ph in stars:
            if syp >= horizon:
                continue
            tw = 0.55 + 0.45 * math.sin(sim * 2.0 + ph)
            ras.point(sxp, syp, quant(shade(sc_, br * tw * 0.9)))


def draw_ground(ras, cam, P, gr, nosun):
    """The ground quad. Drawn even when it will not be filled, because the
    projection is four points and the caller wants the gradient either way."""
    if nosun:
        return
    gq = [cam.project(x, y, 0.0) for x, y in
          ((-gr, -gr), (gr, -gr), (gr, gr), (-gr, gr))]
    ras.fill([q[:2] for q in gq], quant(shade(P['ground'], 1.25)),
             quant(shade(P['ground'], 0.7)))


def draw_grid(ras, cam, gr, colour):
    step = gr / 8.0
    project = cam.project
    for i in range(17):
        t = -gr + i * step
        for pa, pb in (((t, -gr), (t, gr)), ((-gr, t), (gr, t))):
            a = project(pa[0], pa[1], 0.0)
            b = project(pb[0], pb[1], 0.0)
            ras.line_c(a[0], a[1], b[0], b[1], colour)


def draw_shadow(ras, cam, P, rig, world, explode, shadow_on, nosun):
    """Two shapes for two kinds of model.

    A loaded mesh gets height bands, each hulled on the ground separately, so
    the gap between the legs survives -- and because the turntable moves the
    *eye* and not the mech, those hulls are static and were computed once at
    load (see mesh/shadow.py). The built-in model is already a set of parts, so
    each part's own bounding box is the natural band.
    """
    if not (shadow_on and not nosun and SUN[2] > 0.05):
        return
    # The built-in model's parts fly apart under `e`, at which point a shadow
    # cast from their bounding boxes stops meaning anything. A loaded mesh has
    # no joints to explode, so it never reaches this test.
    if not rig.stl_mode and explode >= 0.4:
        return
    shc = quant(lerp(P['ground'], P['shadow'], 0.75 * (1.0 - explode / 0.4)))
    project = cam.project
    if rig.stl_mode:
        for band in rig.parts[0].model.shadow:
            sp = [project(bx, by, 0.01)[:2] for bx, by in band]
            if len(sp) >= 3:
                ras.fill(sp, shc)
        return
    for wv in world:
        xs = [w[0] for w in wv]
        ys = [w[1] for w in wv]
        zs = [w[2] for w in wv]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        z0, z1 = min(zs), max(zs)
        sp = []
        for bx in (x0, x1):
            for by in (y0, y1):
                for bz in (z0, z1):
                    t = bz / SUN[2]
                    q = project(bx - SUN[0] * t, by - SUN[1] * t, 0.01)
                    sp.append((q[0], q[1]))
        h = hull2d(sp)
        if len(h) >= 3:
            ras.fill(h, shc)
