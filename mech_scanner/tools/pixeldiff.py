"""Compare two builds of the renderer frame by frame.

The tool to reach for before and after any change that is meant to be
invisible -- a cache, a hoist, an inlining. Point it at two copies of the
project and it reports how many emitted frames are byte-identical.

Read the control column first. It runs the NEW build against itself, and if
that is not a clean sweep then the comparison beside it means nothing. That has
happened twice here: once because the per-facet weathering used hash() of a
string, which Python salts per process, so no two runs of the program ever drew
the same frame; and once because the cockpit chrome carries a wall-clock
mission timer and a blinking REC lamp, so two runs a second apart differ in the
top row regardless of the renderer. --dt and --no-chrome exist because of those
two, and they are applied here.

Note what a static pose can hide. If the pose does not move, a cache with an
incomplete key still returns the right answer, because the thing its key forgot
never changed. So the turntable is left spinning for the comparison.

Both builds are pointed at this project's mech directory and its cache, so the
comparison is between two renderers and not between two copies of a mesh.

Usage:  python3 tools/pixeldiff.py OLD_PROJECT_DIR [NEW_PROJECT_DIR]
        where each directory contains a scan.py entry point.
"""
import os
import subprocess
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CASES = (
    ('optical      ', []),
    ('thermal      ', ['--sensor', 'thermal']),
    ('lidar        ', ['--sensor', 'lidar']),
    ('xray         ', ['--sensor', 'xray']),
    ('key light    ', ['--lighting', 'key']),
    ('flat light   ', ['--lighting', 'flat']),
    ('amber        ', ['--palette', 'amber']),
    ('no occlusion ', ['--no-ao']),
    ('lod high     ', ['--lod', '2']),
    ('builtin      ', ['--builtin']),
)
SIZES = ((80, 24), (200, 60))
FRAMES = 55


MECH = os.path.join(PROJ, 'mechs', 'timber_wolf')


def run(proj, args, cols, rows):
    env = dict(os.environ, COLUMNS=str(cols), LINES=str(rows))
    cmd = [sys.executable, os.path.join(proj, 'scan.py')]
    if '--builtin' not in args:
        cmd.append(MECH)
    cmd += ['--frames', str(FRAMES), '--fps', '999', '--seed', '7',
            '--no-boot', '--no-chrome', '--cache-dir',
            os.path.join(PROJ, 'cache'), '--dt', repr(1.0 / 30.0)] + args
    r = subprocess.run(cmd, cwd=proj, env=env, capture_output=True)
    return r.stdout.decode('utf-8', 'replace')


def compare(a, b):
    fa = [f for f in a.split('\x1b[H') if f.count('\n') > 5]
    fb = [f for f in b.split('\x1b[H') if f.count('\n') > 5]
    n = min(len(fa), len(fb))
    if n < 20:
        return 0, 0
    return sum(1 for i in range(n) if fa[i] == fb[i]), n


def main():
    if not 2 <= len(sys.argv) <= 3:
        sys.exit(__doc__)
    old = os.path.abspath(sys.argv[1])
    new = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else PROJ
    # Warm both caches first, and throw the output away. On a cold cache the
    # loader prints its progress to stdout before the first frame, which shifts
    # the frame stream by one and reports the whole run as differing -- a
    # spurious 0/55 that says nothing about the renderer. Cheap insurance: the
    # second run is a file read.
    print('warming caches ...')
    for proj in (old, new):
        run(proj, [], 80, 24)
    fails = ctrl = 0
    for label, args in CASES:
        for cols, rows in SIZES:
            a = run(old, args, cols, rows)
            b = run(new, args, cols, rows)
            c = run(new, args, cols, rows)
            s0, n0 = compare(b, c)
            s1, n1 = compare(a, b)
            if not (n0 and s0 == n0):
                ctrl += 1
            ok = n1 and s1 == n1
            if not ok:
                fails += 1
            print('%s %3dx%-3d  control %3d/%-3d  old-vs-new %3d/%-3d  %s'
                  % (label, cols, rows, s0, n0, s1, n1,
                     'IDENTICAL' if ok else '*** DIFFERS ***'))
    print('\n%d comparisons, %d differing, %d control failures'
          % (len(CASES) * len(SIZES), fails, ctrl))
    return 1 if (fails or ctrl) else 0


if __name__ == '__main__':
    sys.exit(main())
