"""Source STL to drawable Models.

`load_models` is the only entry point the rest of the program uses: give it an
STL and a list of facet budgets and it returns one Model per budget, from the
cache where it can and from the full decimate -> voxelise -> segment -> occlude
pipeline where it cannot. Building all three levels up front costs a few
seconds once; building them lazily would put that pause in the middle of a
keypress instead, which is worse.

Everything measured off the source -- occlusion, sections, the reactor point,
the heat field -- is measured in the SOURCE mesh's own coordinates, before
`normalise` moves anything, so the voxel grid and the decimated vertices never
have to agree on a transform.
"""
import math, os

from ..text import commas
from .cache import cache_path, cache_read, cache_write
from .decimate import decimate_to
from .model import MODEL_H, Model, apply_norm, normalise
from .occlusion import face_ao
from .segment import (SECTIONS, face_sections, section_centroid,
                      section_share, segment_solid)
from .stl import analyse_stl, load_stl
from .thermal import heat_field
from .voxels import voxel_solid

def build_model(tris, src, target, up, ao_radius, grid, note=None):
    """Decimate, occlude, normalise. Occlusion is measured in the source mesh's
    own coordinates -- the voxel grid is built from the source triangles, and
    the decimated vertices have not been moved yet -- so the two never have to
    agree on a transform."""
    (solid, dims, org, s, shell, sol, sealed, vox, seclab, seccount,
     core, _lat) = grid
    if note:
        note('decimating %s facets to %s' % (commas(len(tris)), commas(target)))
    verts, faces, ncell = decimate_to(tris, target)
    if note:
        note('occluding %s facets' % commas(len(faces)))
    ao = face_ao(verts, faces, solid, dims, org, s, ao_radius)
    # Sections, like occlusion, are read in the SOURCE mesh's coordinates --
    # before normalise() moves anything -- so the labelled grid and the
    # decimated vertices never need to agree on a transform.
    sec = face_sections(verts, faces, seclab, dims, org, s)
    # Normalise against the mesh's own open-sky value rather than against 1.0.
    # Theory says an unoccluded facet sees the whole hemisphere, but a facet on
    # a real machine is surrounded by panel gaps, bolt heads and its own
    # neighbours, so the raw mean here is 0.35 and shading straight off it
    # drags the entire model into shadow. The 85th percentile is what this
    # surface actually achieves when nothing is in the way; that is the number
    # worth calling 'open'.
    ref = sorted(ao)[int(len(ao) * 0.85)] if ao else 1.0
    if ref > 1e-3:
        ao = [min(1.0, a / ref) for a in ao]
    # Heat, while the vertices are still in source coordinates -- the reactor
    # centroid came out of the voxel grid and lives in the same frame.
    src_h_raw = ((src['bbox'][1] if up == 'y' else src['bbox'][2])
                 if src.get('bbox') else 0.0) or 1.0
    temp = heat_field(verts, faces, ao, core, src_h_raw)
    verts, scale, xf = normalise(verts, up)
    reactor_m = apply_norm(core, xf) if core else None
    # Scale must come from the SOURCE height, not the decimated one. Decimation
    # pulls the extreme vertices in slightly, so a per-LOD scale made the
    # machine's displacement -- and now its derived density -- change every
    # time d was pressed: 142.4 m3 at low detail against 138.8 at high, for
    # one unchanging object. The source is the truth; the LOD is an
    # approximation of it and does not get a vote on how big the mech is.
    if src.get('bbox'):
        # bbox is in SOURCE axes, so pick the one that 'up' will become.
        src_h = src['bbox'][1] if up == 'y' else src['bbox'][2]
        if src_h:
            scale = MODEL_H / src_h

    # Decimated volume and area, for the reduction report.
    dvol = darea = 0.0
    # Area per section as well as volume. Armour is a skin, so when the panel
    # spreads Sarna's twelve tons over the machine it has to spread it by
    # surface, not by displacement -- an arm has far more skin per cubic metre
    # than the torso does, and distributing by volume would have quietly
    # armoured the torso at the limbs' expense.
    sec_area = [0.0] * len(SECTIONS)
    for fi, (ia, ib, ic) in enumerate(faces):
        pa, pb, pc = verts[ia], verts[ib], verts[ic]
        dvol += (pa[0] * (pb[1] * pc[2] - pb[2] * pc[1])
                 - pa[1] * (pb[0] * pc[2] - pb[2] * pc[0])
                 + pa[2] * (pb[0] * pc[1] - pb[1] * pc[0]))
        ux, uy, uz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
        vx, vy, vz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
        mx = uy * vz - uz * vy
        my = uz * vx - ux * vz
        mz = ux * vy - uy * vx
        fa = math.sqrt(mx * mx + my * my + mz * mz)
        darea += fa
        si = sec[fi]
        if si < len(sec_area):
            sec_area[si] += fa
    dvol = abs(dvol) / 6.0
    darea /= 2.0
    _atot = sum(sec_area) or 1.0
    sec_area = [a / _atot for a in sec_area]

    report = dict(src)
    report.update({
        'faces': len(faces), 'verts': len(verts), 'grid': ncell,
        'target': target, 'vox': vox, 'ao_radius': ao_radius,
        'shell_cells': shell, 'solid_cells': sol, 'sealed': sealed,
        'scale': scale, 'up': up,
        # Volume as built: the source mesh is millimetres of printed plastic,
        # so scale it to the height the renderer stands it at and the number
        # becomes a real displacement in cubic metres -- and, at the plate
        # density the built-in model is calibrated to, a real tonnage.
        # As-built figures come from the SOURCE volume scaled up, not from the
        # decimated hull: the source is the truth and the decimation is an
        # approximation of it, so quoting the approximation would make the
        # displacement of the machine change every time you press d.
        'built_volume': src['volume'] * scale ** 3,
        'built_area': src['area'] * scale ** 2,
        # NOTE what is not here: mass. Mass is not a property of a mesh, and
        # this report is the measured half of the display. Tonnage comes from
        # canon and canon is attached by the caller, so the mass and the
        # derived density live on the Rig (see rig.Rig.mass) where the canon
        # table is. Keeping them out also makes the cache canon-independent:
        # the same built mesh is valid whether or not you claim to know what
        # it depicts.
        'sec_share': section_share(seccount),
        'sec_area': sec_area,
        'reactor': list(core) if core else None,
        # ...and the same point in model space, which is where the XRAY
        # channel has to draw it.
        'reactor_m': list(reactor_m) if reactor_m else None,
        'lod_volume': dvol, 'lod_area': darea,
        'vol_err': (dvol / (src['volume'] * scale ** 3) - 1.0) * 100.0
                   if src.get('volume') else 0.0,
        'area_err': (darea / (src['area'] * scale ** 2) - 1.0) * 100.0
                    if src.get('area') else 0.0,
    })
    return Model(verts, faces, ao, report, sec, temp)


def load_models(path, targets, up='z', ao_radius=4.0, vox=80, note=None,
                use_cache=True, cache_dir=None):
    """Every level of detail, from cache where possible.

    Building all three up front costs a few seconds once; building them lazily
    would put that pause in the middle of a keypress instead, which is worse.
    After the first run it is a file read.
    """
    mtime = os.stat(path).st_mtime
    out = []
    tris = None
    src = None
    grid = None
    for t in targets:
        cp = cache_path(path, t, up, ao_radius, vox, cache_dir)
        m = cache_read(cp, mtime) if use_cache else None
        if m is None:
            if tris is None:
                if note:
                    note('reading %s' % os.path.basename(path))
                tris = load_stl(path)
                if note:
                    note('analysing %s facets' % commas(len(tris)))
                src = analyse_stl(tris)
            if grid is None:
                # Once, not once per level: the occupancy grid depends only on
                # the source mesh, and rebuilding it per LOD was three
                # identical four-second passes.
                if note:
                    note('voxelising at %d^3' % vox)
                grid = voxel_solid(tris, vox, want_volume=src['volume']) + (vox,)
                if note:
                    note('segmenting limbs')
                seclab, seccount, mir = segment_solid(grid[0], grid[1], note)
                # Where the reactor is: the centroid of the torso's own mass,
                # measured, not sited by hand. The thermal channel needs it.
                core = section_centroid(seclab, grid[1], grid[2], grid[3],
                                        SECTIONS.index('TORSO'))
                grid = grid + (seclab, seccount, core, (mir[0], mir[1]))
            m = build_model(tris, src, t, up, ao_radius, grid, note)
            if use_cache:
                cache_write(cp, m, mtime)
        out.append(m)
    return out
