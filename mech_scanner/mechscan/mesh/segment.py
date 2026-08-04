"""Split the hull into the machine's own limbs.

Done off the occupancy grid that was already built for occlusion, by
morphology: erode until the joints break, take the pieces as seeds, then grow
them all back at once. See the long comment below for what was tried first and
why it failed.
"""
import math
from collections import deque

# Split the mesh into the machine's own limbs, off the occupancy grid that was
# already built for occlusion.
#
# The first attempt sliced the grid horizontally and took connected components
# per slice -- a Reeb graph of the height function. It found the legs and the
# missile pods cleanly and FAILED on the arms, giving one arm 2.9% of the hull
# and the other 0.9%: above the hips an arm and the side of the torso fall in
# the same 2D component wherever they overlap in plan view, and no amount of
# per-slice connectivity will part them. That is measured, not suspected.
#
# Morphology fits the shape of the problem instead. A mech's joints are its
# narrow places -- ankle, knee, hip, shoulder, elbow -- so erosion breaks them
# first and the limbs fall off on their own. Erode to a core, take 3D connected
# components as seeds, then grow every seed at once back over the full solid.
# The simultaneous flood is a watershed: it assigns each cell to whichever core
# reaches it first, which puts the boundary in the joint where it belongs.
#
# The torso is deliberately left whole -- everything that is not a limb is
# TORSO. Splitting it into centre and side torsos is a later job.
SECTIONS = ('TORSO', 'LA', 'RA', 'LL', 'RL')

# Two sets of names for the same five labels, because the labels mean two
# different things depending on whether we know what the mesh depicts.
#
# What the algorithm ACTUALLY finds is the largest eroded core, plus up to two
# outboard components on each side of the measured mirror plane, split by
# height. On the Timber Wolf those are a torso, two arms and two legs, and
# saying so is reporting a fact. On an arbitrary mesh they are still the
# largest core and four outboard lobes, and calling one of them 'arm L' would
# be inventing an anatomy the geometry never claimed -- so the geometric names
# describe exactly what was measured and nothing more.
MECH_NAMES = {'TORSO': 'torso', 'LA': 'arm L', 'RA': 'arm R',
              'LL': 'leg L', 'RL': 'leg R'}
GEOM_NAMES = {'TORSO': 'core', 'LA': 'upper L', 'RA': 'upper R',
              'LL': 'lower L', 'RL': 'lower R'}


def section_names(canon):
    return MECH_NAMES if canon else GEOM_NAMES
# Erosion depth is NOT a constant. It has to scale with the voxel resolution --
# at 96^3 a depth of 6 parts the limbs cleanly, at the default 80^3 the same
# depth erases them and leaves two lumps. So sweep it, and let bilateral
# symmetry decide: the correct depth is the deepest one that still finds at
# least two outboard components on EACH side of the mirror plane, which is
# what a mech with two arms and two legs must produce. Nothing in the search
# knows the machine is symmetric, so when it agrees, that agreement is
# evidence rather than assumption.
#
# Two per side is what a Timber Wolf produces; it is not what every machine
# produces. The Marauder's arms are gauntlets slung under wide shoulders and no
# erosion depth parts them from the trunk -- but depth 5 finds its two legs
# perfectly, one on each side at 0.28 of the height. Requiring two per side
# threw that away and fell through to the one-lump fallback, so the whole
# machine reported as torso and the armour tonnage went with it.
#
# So two per side is the PREFERRED answer and one per side is an accepted one:
# the sweep keeps the deepest symmetric-but-thin result as it goes and uses it
# only if nothing better turns up. Bilateral agreement is still the evidence --
# a lone lobe on one side and nothing on the other is noise and is refused.
ERODE_SWEEP = (8, 7, 6, 5, 4, 3, 2)
SEG_MIN_CELLS = 40
SEG_LAT_FRAC = 0.10       # outboard means this far off the mirror plane


def mirror_plane(solid, dims, step=3.0):
    """The vertical plane that best maps the solid onto itself.

    Needed because the obvious shortcut -- lateral axis = whichever way the
    legs are furthest apart -- is a coin flip on this mesh: the Mad Cat is
    modelled mid-stride and its legs are separated diagonally, 35.3 grid units
    one way against 38.1 the other. Structure is symmetric even when pose is
    not, and the symmetric mass outweighs the stride.

    Returns (lateral_x, lateral_y, centre_x, centre_y, score). The score is
    reported rather than asserted: it comes out at 0.686 against a worst case
    of 0.327, and it is NOT 1.0 precisely because the stride is real.
    """
    nx, ny, nz = dims
    nxy = nx * ny
    cells = []
    for p in range(len(solid)):
        if solid[p]:
            k, rem = divmod(p, nxy)
            j, i = divmod(rem, nx)
            cells.append((i, j, k))
    if not cells:
        return 1.0, 0.0, 0.0, 0.0, 0.0
    occ = set(cells)
    cx = sum(c[0] for c in cells) / len(cells)
    cy = sum(c[1] for c in cells) / len(cells)
    best = None
    ang = 0.0
    while ang < 180.0:            # a plane and its opposite are one plane
        a = math.radians(ang)
        ux, uy = math.cos(a), math.sin(a)
        hit = 0
        for i, j, k in cells:
            dx, dy = i - cx, j - cy
            d = 2.0 * (dx * ux + dy * uy)
            if (int(round(cx + dx - d * ux)),
                    int(round(cy + dy - d * uy)), k) in occ:
                hit += 1
        sc = hit / float(len(cells))
        if best is None or sc > best[0]:
            best = (sc, ux, uy)
        ang += step
    return best[1], best[2], cx, cy, best[0]


def _erode(solid, dims, n):
    nx, ny, nz = dims
    nxy = nx * ny
    cur = solid
    for _ in range(n):
        out = bytearray(len(cur))
        for p in range(len(cur)):
            if not cur[p]:
                continue
            k, rem = divmod(p, nxy)
            j, i = divmod(rem, nx)
            if (i == 0 or j == 0 or k == 0 or i == nx - 1 or j == ny - 1
                    or k == nz - 1):
                continue
            if (cur[p - 1] and cur[p + 1] and cur[p - nx] and cur[p + nx]
                    and cur[p - nxy] and cur[p + nxy]):
                out[p] = 1
        cur = out
    return cur


def _components_3d(grid, dims, minsize):
    nx, ny, nz = dims
    nxy = nx * ny
    seen = bytearray(len(grid))
    comps = []
    for start in range(len(grid)):
        if seen[start] or not grid[start]:
            continue
        q = deque([start])
        seen[start] = 1
        cells = []
        while q:
            p = q.popleft()
            cells.append(p)
            k, rem = divmod(p, nxy)
            j, i = divmod(rem, nx)
            for d, ok in ((-1, i > 0), (1, i < nx - 1), (-nx, j > 0),
                          (nx, j < ny - 1), (-nxy, k > 0), (nxy, k < nz - 1)):
                p2 = p + d
                if ok and not seen[p2] and grid[p2]:
                    seen[p2] = 1
                    q.append(p2)
        if len(cells) >= minsize:
            comps.append(cells)
    comps.sort(key=len, reverse=True)
    return comps


def segment_solid(solid, dims, note=None):
    """Label every solid cell TORSO / LA / RA / LL / RL.

    Limbs are named by measurement, never by which way the STL happens to face:
    a component is an arm or a leg by its height and how far it sits off the
    measured mirror plane, and left from right by the sign of that offset.
    """
    nx, ny, nz = dims
    nxy = nx * ny
    ux, uy, cx, cy, score = mirror_plane(solid, dims)
    if note:
        note('mirror plane %.0f%% symmetric' % (score * 100.0))
    lat_min = SEG_LAT_FRAC * max(nx, ny)
    comps = []
    stats = []
    depth_used = 0
    thin = None                 # deepest one-per-side result seen so far
    for depth in ERODE_SWEEP:
        core = _erode(solid, dims, depth)
        cs = _components_3d(core, dims, SEG_MIN_CELLS)
        st = []
        for ci, cells in enumerate(cs):
            sx = sy = sz = 0
            for p in cells:
                k, rem = divmod(p, nxy)
                j, i = divmod(rem, nx)
                sx += i; sy += j; sz += k
            n = float(len(cells))
            st.append({'i': ci, 'n': len(cells), 'z': (sz / n) / max(1, nz - 1),
                       'lat': (sx / n - cx) * ux + (sy / n - cy) * uy})
        left = [x for x in st[1:] if x['lat'] < -lat_min]
        right = [x for x in st[1:] if x['lat'] > lat_min]
        if len(left) >= 2 and len(right) >= 2:
            comps, stats, depth_used = cs, st, depth
            break
        if thin is None and left and right:
            thin = (cs, st, depth)
    if not comps and thin:              # limbs on both sides, but only one each
        comps, stats, depth_used = thin
    if not comps:                       # nothing parted: one solid lump
        comps = _components_3d(solid, dims, SEG_MIN_CELLS)
        stats = [{'i': 0, 'n': len(comps[0]) if comps else 0, 'z': 0.5,
                  'lat': 0.0}]
    if note:
        note('%d sections at erosion %d' % (len(comps), depth_used))

    # The trunk is simply the biggest core; everything is measured against it.
    lab_of = {0: 'TORSO'}
    # Pick per SIDE, never globally: taking 'the two largest remaining' picked
    # two components off the same shoulder and left the other arm unlabelled.
    core_z = stats[0]['z'] if stats else 0.5
    for sgn, leg_tag, arm_tag in ((-1, 'LL', 'LA'), (1, 'RL', 'RA')):
        side = [x for x in stats[1:]
                if (x['lat'] < -lat_min if sgn < 0 else x['lat'] > lat_min)]
        if not side:
            continue
        leg = min(side, key=lambda x: x['z'])       # a leg reaches the ground
        if len(side) == 1 and leg['z'] >= core_z:
            # With two lobes on a side the lower is a leg by construction. With
            # only one there is nothing to be lower than, so height against the
            # trunk decides: a lobe that hangs no further down than the body it
            # is attached to is not something the machine stands on.
            lab_of[leg['i']] = arm_tag
            continue
        lab_of[leg['i']] = leg_tag
        rest = [x for x in side if x is not leg and x['z'] > leg['z']]
        if rest:                                    # an arm hangs, it does not
            lab_of[max(rest, key=lambda x: x['n'])['i']] = arm_tag
    for x in stats:
        lab_of.setdefault(x['i'], 'TORSO')

    idx = dict((s, i) for i, s in enumerate(SECTIONS))
    lab = bytearray(len(solid))
    q = deque()
    for ci, cells in enumerate(comps):
        v = idx[lab_of[ci]] + 1
        for p in cells:
            lab[p] = v
            q.append(p)
    while q:                       # one flood, all cores at once: a watershed
        p = q.popleft()
        v = lab[p]
        k, rem = divmod(p, nxy)
        j, i = divmod(rem, nx)
        for d, ok in ((-1, i > 0), (1, i < nx - 1), (-nx, j > 0),
                      (nx, j < ny - 1), (-nxy, k > 0), (nxy, k < nz - 1)):
            p2 = p + d
            if ok and solid[p2] and not lab[p2]:
                lab[p2] = v
                q.append(p2)
    counts = [0] * len(SECTIONS)
    for v in lab:
        if v:
            counts[v - 1] += 1
    return lab, counts, (ux, uy, cx, cy, score)


def face_sections(verts, faces, lab, dims, org, s):
    """Section index per facet, from the labelled cell its centroid sits in."""
    nx, ny, nz = dims
    ox, oy, oz = org
    nxy = nx * ny
    out = bytearray(len(faces))
    for fi, (ia, ib, ic) in enumerate(faces):
        pa, pb, pc = verts[ia], verts[ib], verts[ic]
        i = int(((pa[0] + pb[0] + pc[0]) / 3.0 - ox) * s)
        j = int(((pa[1] + pb[1] + pc[1]) / 3.0 - oy) * s)
        k = int(((pa[2] + pb[2] + pc[2]) / 3.0 - oz) * s)
        v = 0
        if 0 <= i < nx and 0 <= j < ny and 0 <= k < nz:
            v = lab[(k * ny + j) * nx + i]
        if not v:
            # A facet centroid can land just outside the solid on a thin
            # panel; take the nearest labelled cell in a small neighbourhood
            # rather than silently calling it torso.
            best = None
            for dk in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    for di in (-1, 0, 1):
                        i2, j2, k2 = i + di, j + dj, k + dk
                        if 0 <= i2 < nx and 0 <= j2 < ny and 0 <= k2 < nz:
                            w = lab[(k2 * ny + j2) * nx + i2]
                            if w:
                                best = w
                                break
                    if best:
                        break
                if best:
                    break
            v = best or 1
        out[fi] = v - 1
    return out


def section_centroid(lab, dims, org, s, si):
    """Centroid of one labelled section, back in SOURCE coordinates.

    `s` is cells per source unit, the same convention face_sections uses, so
    the way back out is a division.
    """
    nx, ny, _nz = dims
    nxy = nx * ny
    tag = si + 1
    sx = sy = sz = 0
    n = 0
    for p, v in enumerate(lab):
        if v == tag:
            k, rem = divmod(p, nxy)
            j, i = divmod(rem, nx)
            sx += i
            sy += j
            sz += k
            n += 1
    if not n:
        return None
    return (org[0] + (sx / float(n) + 0.5) / s,
            org[1] + (sy / float(n) + 0.5) / s,
            org[2] + (sz / float(n) + 0.5) / s)


def present(share):
    """Which of the five sections this mesh actually has.

    Not every machine produces five. The panels, the report and the target
    cycle all take their section list from here rather than from SECTIONS, so
    a section the segmentation never found is absent from the display instead
    of being listed at 0.0 t -- which reads as a limb that has been shot off.
    """
    return [i for i, v in enumerate(share) if v > 0.0]


def section_share(counts):
    """Fraction of the enclosed volume in each section, from VOXEL counts.

    An earlier version summed signed tetrahedron volumes per section, on the
    argument that the divergence theorem would sort out the open boundary.
    It does not: the fan integral is only volume for a CLOSED surface, and for
    an open patch the answer depends on where the patch's rim sits relative to
    the origin. The evidence was the arms coming out 3.1 m3 against 5.8 m3 --
    a near 2:1 split between two limbs whose facet counts agreed to within 4%.

    Counting labelled cells has no such problem. The watershed assigns every
    solid cell to exactly one section, so the counts are a true partition of
    the enclosed volume, and the legs now agree exactly.
    """
    tot = float(sum(counts)) or 1.0
    return [c / tot for c in counts]
