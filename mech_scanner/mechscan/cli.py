"""Command line: pick a machine, build it, and either report on it or fly it.

The positional argument is a MECH -- a directory under mechs/ holding a mesh and
its canon.md. It also accepts a path to any such directory, or a bare .stl for
a mesh nobody has written facts about. With nothing at all it loads the first
mech in mechs/.
"""
import argparse
import os
import struct
import sys

from . import __doc__ as _pkg_doc
from . import canon as canon_mod
from .app import App
from .lighting import LIGHT_ARGS
from .mesh.model import LOD_TARGETS
from .mesh.report import print_mesh_report
from .palettes import PAL_NAMES
from .render.sensors import SENSOR_NAMES
from .rig import Rig


def build_parser():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('model', nargs='?', default=None,
                    help='a mech: a name under mechs/, a path to a mech '
                         'directory, or a bare .stl. Default: the first mech '
                         'in mechs/')
    ap.add_argument('--list', action='store_true',
                    help='list the available mechs and exit')
    ap.add_argument('--builtin', action='store_true',
                    help='the procedural mech, ignoring any mesh')
    ap.add_argument('--up', default=None, choices=('z', 'y'),
                    help='which axis the mesh calls up. Overrides the '
                         "mech's canon.md; default z")
    ap.add_argument('--faces', type=int, default=None,
                    help='facet budget; overrides the three built-in levels')
    ap.add_argument('--lod', type=int, default=1, choices=(0, 1, 2),
                    help='starting detail level, 0 low .. 2 high')
    ap.add_argument('--ao-radius', type=float, default=4.0,
                    help='occlusion reach, in voxels')
    ap.add_argument('--voxels', type=int, default=80,
                    help='occupancy grid resolution on the longest axis')
    ap.add_argument('--no-ao', action='store_true')
    ap.add_argument('--no-cache', action='store_true',
                    help='rebuild the mesh cache instead of reading it')
    ap.add_argument('--cache-dir', default=None,
                    help='where built meshes are cached (default: cache/ '
                         'inside the project). Nothing in it is precious')
    ap.add_argument('--canon', default='auto', choices=('auto', 'none'),
                    help="none ignores the mech's canon.md and shows the "
                         'measured survey instead')
    ap.add_argument('--palette', default='field', choices=PAL_NAMES)
    ap.add_argument('--fps', type=float, default=60.0,
                    help='frame rate cap; 0 for uncapped. r cycles it live. '
                         'Default 60')
    ap.add_argument('--speed', type=float, default=1.0)
    ap.add_argument('--tilt', type=float, default=16.0)
    ap.add_argument('--az', type=float, default=34.0,
                    help='starting azimuth in degrees')
    ap.add_argument('--dist', type=float, default=34.0)
    ap.add_argument('--blocks', default='quad', choices=('quad', 'half'))
    ap.add_argument('--zen', action='store_true')
    ap.add_argument('--no-stars', action='store_true')
    ap.add_argument('--no-shadow', action='store_true')
    ap.add_argument('--no-idle', action='store_true')
    ap.add_argument('--no-boot', action='store_true',
                    help='skip the startup sequence (b replays it)')
    ap.add_argument('--no-chrome', action='store_true',
                    help='start with the cockpit chrome off (f toggles it)')
    ap.add_argument('--seed', type=int, default=None,
                    help='pin the callsign, pilot and hull number')
    ap.add_argument('--sensor', default='optical',
                    choices=[n.lower() for n in SENSOR_NAMES],
                    help='sensor channel to start in')
    ap.add_argument('--lighting', default='full', choices=LIGHT_ARGS,
                    help='full / key (key light only) / flat (no lighting; '
                         'a single-material mesh becomes a silhouette)')
    ap.add_argument('--stats', action='store_true',
                    help='print the mesh report and exit')
    ap.add_argument('--frames', type=int, default=0,
                    help='render N frames and exit (harness use)')
    ap.add_argument('--dt', type=float, default=0.0,
                    help='pin the simulation timestep, in seconds, instead of '
                         'reading the wall clock. Two runs otherwise land at '
                         'different azimuths, so a pixel-diff harness needs '
                         'this to be comparing the renderer rather than the '
                         'speed of the host (harness use)')
    ap.add_argument('-h', '--help', action='store_true')
    return ap


def list_mechs():
    names = canon_mod.available()
    if not names:
        print('no mechs in %s' % canon_mod.mechs_dir())
        return 0
    print('%-20s %-24s %s' % ('MECH', 'DESIGNATION', 'MESH'))
    for n in names:
        try:
            m = canon_mod.load_dir(os.path.join(canon_mod.mechs_dir(), n))
        except (OSError, ValueError) as e:
            print('%-20s %s' % (n, e))
            continue
        print('%-20s %-24s %s'
              % (n, (m.canon or {}).get('name', '(no canon.md)'),
                 os.path.basename(m.stl)))
    return 0


def find_mech(args):
    """(Mech, error message). Exactly one of the two is None."""
    if args.builtin:
        return None, None
    target = args.model
    # A bare .stl is a mesh nobody has written facts about: load it on its own,
    # from wherever it is, with no canon.
    if target and target.lower().endswith('.stl'):
        if not os.path.exists(target):
            return None, 'no such file: %s' % target
        return canon_mod.Mech(os.path.dirname(os.path.abspath(target)),
                              os.path.abspath(target), None,
                              args.up or 'z', [], [], os.path.basename(target)), None
    directory = canon_mod.resolve(target)
    if directory is None:
        names = canon_mod.available()
        return None, ('no such mech: %s\navailable: %s'
                      % (target, ', '.join(names) if names else '(none)'))
    try:
        return canon_mod.load_dir(directory,
                                  use_canon=args.canon != 'none'), None
    except (OSError, ValueError) as e:
        return None, 'cannot load %s: %s' % (directory, e)


def print_structure(rig):
    """The built-in model has no mesh report; it has a parts list."""
    print('%-18s %-8s %8s %8s %7s'
          % ('PART', 'GROUP', 'VOL m3', 'MASS t', 'FACES'))
    tot = vol = nf = 0.0
    for p in rig.parts:
        print('%-18s %-8s %8.2f %8.2f %7d'
              % (p.name, p.group, p.volume, p.mass, len(p.faces)))
        tot += p.mass
        vol += p.volume
        nf += len(p.faces)
    print('%-18s %-8s %8.2f %8.2f %7d' % ('TOTAL', '', vol, tot, nf))


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.help:
        print(_pkg_doc)
        return 0
    if args.list:
        return list_mechs()

    mech, err = find_mech(args)
    if err:
        print(err, file=sys.stderr)
        return 2

    if mech is None:
        rig = Rig.builtin()
    else:
        # Building is seconds on a cold cache and milliseconds on a warm one,
        # so say what is happening rather than show a black terminal.
        def note(msg):
            sys.stdout.write('  %s ...\r\n' % msg)
            sys.stdout.flush()

        try:
            rig = Rig.from_stl(
                mech.stl, targets=(args.faces,) if args.faces else LOD_TARGETS,
                up=args.up or mech.up, ao_radius=args.ao_radius,
                vox=args.voxels, no_ao=args.no_ao, note=note,
                use_cache=not args.no_cache, lod=args.lod, canon=mech.canon,
                cache_dir=args.cache_dir)
        except (OSError, ValueError, struct.error) as e:
            print('cannot load %s: %s' % (mech.stl, e), file=sys.stderr)
            return 2

    if args.stats:
        if rig.stl_mode:
            print_mesh_report(rig.lods[0].model.report,
                              [p.model.report for p in rig.lods],
                              rig.canon, mech)
        else:
            print_structure(rig)
        return 0

    app = App(rig, args)
    app.install_signals()
    app.run()
    return 0
