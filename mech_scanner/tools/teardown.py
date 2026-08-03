"""Signal teardown soak.

SIGTERM / SIGHUP / SIGINT delivered at a random point in the frame loop, sixty
times. Asserts the process dies, leaves no traceback, and emits the cursor-show
sequence -- because the failure mode being guarded against is a process that
exits 0 having restored nothing, leaving the user's terminal in raw mode with
the cursor hidden.

That failure was real and it was total: 60 out of 60. The handler used to tear
down inline, and a handler must not touch sys.stdout -- the emitter holds the
BufferedWriter's lock for most of every frame, so re-entering it from a signal
raises RuntimeError, which the defensive `except Exception: pass` around the
teardown then swallowed. The handler now only records the request. This harness
is what proves it stayed fixed.

Usage:  python3 tools/teardown.py [N]
"""
import os
import pty
import random
import select
import signal
import sys
import time

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(PROJ, 'scan.py')


def once(rng):
    sig = rng.choice((signal.SIGTERM, signal.SIGHUP, signal.SIGINT))
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['COLUMNS'] = '120'
        os.environ['LINES'] = '34'
        os.chdir(PROJ)
        os.execv(sys.executable, [sys.executable, ENTRY, '--fps', '30'])
    time.sleep(rng.uniform(0.15, 0.75))
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        pass
    out = b''
    t = time.time()
    while time.time() - t < 2.0:
        if select.select([fd], [], [], 0.1)[0]:
            try:
                d = os.read(fd, 65536)
            except OSError:
                break
            if not d:
                break
            out += d
        else:
            try:
                if os.waitpid(pid, os.WNOHANG)[0]:
                    break
            except ChildProcessError:
                break
    for fn in (lambda: os.waitpid(pid, 0), lambda: os.close(fd)):
        try:
            fn()
        except (ChildProcessError, OSError):
            pass
    txt = out.decode('utf-8', 'replace')
    ok = 'Traceback' not in txt and '\x1b[?25h' in txt
    return ok, sig, txt


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    rng = random.Random(11)
    bad = 0
    for _ in range(n):
        ok, sig, txt = once(rng)
        if not ok:
            bad += 1
            print('FAIL', sig,
                  txt[-500:] if 'Traceback' in txt else 'no cursor restore')
    print('teardowns %d, failures %d' % (n, bad))
    print('RESULT:', 'PASS' if bad == 0 else 'FAIL')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
