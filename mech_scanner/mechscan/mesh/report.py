"""The --stats report.

Provenance first, then measurement, then the canon-derived figures -- and those
only where a canon source was actually attached. Without one the mass and
density lines are absent rather than zero: a mesh does not have a tonnage, and
printing a number that came from nowhere is the failure this program is written
to avoid. The sources from the mech's canon.md are printed with it, so the
report says where every quoted fact came from.
"""
import os

from ..text import commas
from .model import LOD_NAMES, MODEL_H
from .segment import SECTIONS, section_names


def print_mesh_report(src, lods, canon=None, mech=None):
    if mech is not None:
        print('MECH   %s' % mech.title)
        print('  directory     %s' % mech.dir)
        print('  mesh          %s' % os.path.basename(mech.stl))
        print('  canon         %s'
              % ('%s %s' % (canon.get('name', ''), canon.get('config', ''))
                 if canon else 'none -- measured survey only'))
        for i, u in enumerate(mech.sources):
            print('  %-13s %s' % ('source' if i == 0 else '', u))
        print()
    print('SOURCE')
    print('  facets        %14s' % commas(src['src_tris']))
    print('  vertices      %14s   (welded)' % commas(src['src_verts']))
    print('  edges         %14s' % commas(src['edges']))
    print('  watertight    %14s   %s' % (
        'yes' if src['watertight'] else 'no',
        'every edge used exactly twice' if src['watertight']
        else 'enclosed volume is not meaningful'))
    # json round-trips a tuple as a list, so the cached report needs coercing
    print('  bounding box  %6.1f x %.1f x %.1f  source units'
          % tuple(src['bbox']))
    print('  volume        %14.1f   cubic source units' % src['volume'])
    print('  surface area  %14.1f   square source units' % src['area'])
    print('  occupancy     %14s   solid cells, %s on the shell'
          % (commas(src['solid_cells']), commas(src['shell_cells'])))
    print('  sealed        %14s   %s' % (
        'yes' if src.get('sealed') else 'NO',
        'interior matches the enclosed volume' if src.get('sealed')
        else 'the flood leaked: occlusion will be wrong'))
    print()
    print('AS BUILT   normalised to %.1f m tall, %.4f m per source unit'
          % (MODEL_H, src['scale']))
    print('  volume        %14.1f   m3' % src['built_volume'])
    print('  surface area  %14.1f   m2' % src['built_area'])
    if canon:
        # Mass is canon and density is derived, not the other way round: the
        # wiki owns the tonnage, the mesh owns the geometry, and neither is
        # asked to supply the other's number.
        mass = float(canon['mass_t'])
        print('  mass          %14.1f   t   (%s %s, per Sarna)'
              % (mass, canon['name'], canon['config']))
        print('  mean density  %14.3f   t/m3  derived: canon mass / measured'
              % (mass / src['built_volume'] if src.get('built_volume') else 0.0))
    else:
        print('  mass                     n/a   no canon source for this mesh;'
              ' see --canon')
    print()
    print('SECTIONS   segmented off the occupancy grid by erosion + watershed')
    names = section_names(canon)
    share = src.get('sec_share') or []
    if canon:
        print('  %-8s %10s %10s' % ('section', 'volume m3', 'mass t'))
        for i, sec in enumerate(SECTIONS):
            if i < len(share):
                print('  %-8s %10.1f %10.1f'
                      % (names[sec], share[i] * src['built_volume'],
                         share[i] * float(canon['mass_t'])))
    else:
        area = src.get('sec_area') or []
        print('  %-8s %10s %9s %9s' % ('section', 'volume m3', 'of vol', 'of skin'))
        for i, sec in enumerate(SECTIONS):
            if i < len(share):
                print('  %-8s %10.1f %8.1f%% %8.1f%%'
                      % (names[sec], share[i] * src['built_volume'],
                         share[i] * 100.0,
                         (area[i] * 100.0) if i < len(area) else 0.0))
    print()
    print('%-8s %8s %8s %6s %10s %10s' %
          ('LEVEL', 'FACETS', 'VERTS', 'GRID', 'VOL ERR', 'AREA ERR'))
    for i, r in enumerate(lods):
        print('%-8s %8s %8s %6d %9.2f%% %9.2f%%'
              % (LOD_NAMES[i] if i < len(LOD_NAMES) else 'LOD %d' % i,
                 commas(r['faces']), commas(r['verts']), r['grid'],
                 r['vol_err'], r['area_err']))
    print()
    print('Reduction to %s facets is %.2f%% of the source. Errors are against'
          % (commas(lods[len(lods) // 2]['faces']),
             lods[len(lods) // 2]['faces'] / float(src['src_tris']) * 100.0))
    print('the source mesh, measured, not estimated.')
