"""Size and flag sweep.

Every terminal shape crossed with every mode and every palette, a few frames
each, asserting a clean exit, no traceback and a plausible amount of output.
This is the harness that catches the class of bug where a panel, a bracket or a
tape is laid out against a width that only exists at one terminal size -- which
in this program has happened to the armour column, the elevation ladder and the
crew line, each time at a size nobody was looking at.

Usage:  python3 tools/sweep.py
"""
import os
import subprocess
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(PROJ, 'scan.py')

SIZES = [(60, 18), (80, 24), (110, 30), (170, 48), (240, 70), (300, 90),
         (26, 10), (400, 100)]
FLAGS = [[], ['--blocks', 'half'], ['--zen'], ['--tilt', '70'],
         ['--tilt', '-20'], ['--no-shadow'], ['--no-idle', '--speed', '0'],
         ['--builtin'], ['--no-ao'], ['--lod', '0'], ['--lod', '2'],
         ['--builtin', '--zen'], ['--up', 'y'],
         ['--lighting', 'key'], ['--lighting', 'flat'],
         ['--builtin', '--lighting', 'key'],
         ['--builtin', '--lighting', 'flat'],
         ['--sensor', 'thermal'], ['--sensor', 'lidar'],
         ['--sensor', 'xray'], ['--builtin', '--sensor', 'lidar'],
         ['--no-chrome'], ['--no-boot'], ['--builtin', '--no-chrome']]
PALS = ['field', 'matrix', 'amber', 'ice', 'plasma', 'blood']


def run(cols, rows, flags):
    env = dict(os.environ, COLUMNS=str(cols), LINES=str(rows))
    p = subprocess.run([sys.executable, ENTRY, '--frames', '3', '--fps', '200']
                       + flags, capture_output=True, env=env, timeout=180,
                       cwd=PROJ)
    err = p.stderr.decode()
    ok = p.returncode == 0 and 'Traceback' not in err and len(p.stdout) > 100
    return ok, err, len(p.stdout)


def main():
    bad = 0
    for cols, rows in SIZES:
        for fl in FLAGS:
            ok, err, n = run(cols, rows, fl)
            print('%-4s %3dx%-3d %-30s %s'
                  % ('ok' if ok else 'FAIL', cols, rows, ' '.join(fl), n))
            if not ok:
                bad += 1
                print(err[:800])
    for pl in PALS:
        ok, err, _n = run(120, 36, ['--palette', pl])
        print('%-4s palette %s' % ('ok' if ok else 'FAIL', pl))
        if not ok:
            bad += 1
            print(err[:800])
    print('\nfailures: %d' % bad)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
