"""Per-stage frame cost.

Builds an instrumented copy of the package with a timer at every stage boundary
in the frame loop, runs it, and reports milliseconds per frame and share of
frame by stage.

The stage boundaries are the `# ---- name ----` comments the frame loop already
carries, so the split follows the program's own structure rather than one
invented for the measurement. Those comments are load-bearing for this reason:
renaming one changes what the numbers mean.

Written rather than eyeballed because the whole question is which stage
dominates, and the answer differs by terminal size and by sensor channel. It
was this that showed the shader at 51-53% of the frame -- almost all of it
recomputing constants -- and the emitter at a stubborn 15-25% that is per-cell
and has never been touched.

Usage:  python3 tools/profile.py [--builtin] [--lod 2] [--sensor xray] ...
        COLUMNS=200 LINES=60 python3 tools/profile.py
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
BUILD = os.path.join(HERE, '_profile')

PROBE = '''
# --- instrumentation, injected by tools/profile.py ------------------------
import atexit as _atexit
import collections as _coll
import sys as _sys
import time as _time

_ACC = _coll.OrderedDict()
_LAST = [None, None]
_NFRAMES = [0]


def _T(name):
    t = _time.perf_counter()
    if _LAST[0] is not None:
        _ACC[_LAST[0]] = _ACC.get(_LAST[0], 0.0) + (t - _LAST[1])
    _LAST[0], _LAST[1] = name, t


def _Tstop():
    _T(None)
    _LAST[0] = None


@_atexit.register
def _report():
    if not _ACC:
        return
    nf = _NFRAMES[0] or 1
    tot = sum(_ACC.values())
    _sys.stderr.write('\\n%-14s %9s %7s\\n' % ('stage', 'ms/frame', 'pct'))
    for k, v in sorted(_ACC.items(), key=lambda kv: -kv[1]):
        _sys.stderr.write('%-14s %9.2f %6.1f%%\\n'
                          % (k, v / nf * 1000.0, v / tot * 100.0))
    _sys.stderr.write('%-14s %9.2f\\n' % ('TOTAL', tot / nf * 1000.0))
'''

# Sixteen spaces exactly: the frame loop's own body. Other modules use the same
# comment style at other indents and must not be probed.
MARK = re.compile(r'^(                )# ---- (\S+)')


def build():
    if os.path.isdir(BUILD):
        shutil.rmtree(BUILD)
    shutil.copytree(os.path.join(PROJ, 'mechscan'),
                    os.path.join(BUILD, 'mechscan'),
                    ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy(os.path.join(PROJ, 'scan.py'), BUILD)

    app = os.path.join(BUILD, 'mechscan', 'app.py')
    out = []
    for ln in open(app).read().split('\n'):
        m = MARK.match(ln)
        if m:
            out.append('%s_T(%r)' % (m.group(1), m.group(2)))
        if 'queue.sort(key=' in ln:
            out.append(re.match(r'^(\s*)', ln).group(1) + "_T('sort')")
        if ln.strip() == 'self.frame += 1':
            ind = re.match(r'^(\s*)', ln).group(1)
            out.append(ind + '_Tstop()')
            out.append(ind + '_NFRAMES[0] += 1')
        out.append(ln)
    txt = '\n'.join(out)
    anchor = 'GRID_SOLID, GRID_XRAY, GRID_OFF = 0, 1, 2'
    if anchor not in txt:
        sys.exit('app.py has moved: the probe has nowhere to anchor')
    txt = txt.replace(anchor, PROBE + '\n\n' + anchor, 1)
    if '_T(' not in txt:
        sys.exit('no stage markers matched -- has the frame loop reindented?')
    open(app, 'w').write(txt)
    return os.path.join(BUILD, 'scan.py')


def main():
    entry = build()
    args = sys.argv[1:] or []
    if '--builtin' not in args:
        # An absolute mech directory, and the project's own cache: the
        # instrumented copy is a bare package with no mechs/ beside it, and
        # rebuilding the mesh to time the frame loop would be silly.
        args = [os.path.join(PROJ, 'mechs', 'timber_wolf')] + args
    cmd = [sys.executable, entry] + args + [
        '--frames', '120', '--fps', '999', '--seed', '7', '--no-boot',
        '--cache-dir', os.path.join(PROJ, 'cache'),
        '--dt', repr(1.0 / 30.0)]
    p = subprocess.run(cmd, cwd=BUILD, capture_output=True,
                       env=dict(os.environ))
    sys.stderr.write(p.stderr.decode())
    return p.returncode


if __name__ == '__main__':
    sys.exit(main())
