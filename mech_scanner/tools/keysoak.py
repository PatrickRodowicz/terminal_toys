"""Key soak over a real pty.

Every bound key, every unbound key, arrow sequences and a parameterised CSI,
hammered while the model animates. Asserts no traceback, that the process is
still emitting frames at the end, and that it exits cleanly on q.

A real pty rather than a pipe, because the key reader only arms itself when
stdin is a tty -- so a pipe-based test would exercise nothing. And every key,
bound or not, because the failure this catches is a state combination the
author never typed: the explode direction that existed only for the visible
level of detail crashed the frame loop the moment `d` was pressed, and it was
this harness that found it, not looking at the code.

Usage:  python3 tools/keysoak.py
"""
import fcntl
import os
import pty
import random
import select
import struct
import sys
import termios
import time

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(PROJ, 'scan.py')

BOUND = (list(' [],.jkr\tewlgsizhp?0123456damvcfnNbLS-=')
         + ['\x1b[A', '\x1b[B', '\x1b[C', '\x1b[D'])
UNBOUND = [k for k in list('otuxy789/\\`~')
           + ['\x1b[1;2A', '\x1b[<0;10;10M', '\x1b[200~', '\x1b']]

COLS, ROWS = 150, 44
NKEYS = 300


def drain(fd, budget=8, timeout=0.0):
    """Bounded: the child out-produces a naive drain loop, which spins forever
    if it is allowed to."""
    got = b''
    for _ in range(budget):
        if not select.select([fd], [], [], timeout)[0]:
            break
        try:
            d = os.read(fd, 65536)
        except OSError:
            break
        if not d:
            break
        got += d
    return got


def main():
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['COLUMNS'] = str(COLS)
        os.environ['LINES'] = str(ROWS)
        os.chdir(PROJ)
        os.execv(sys.executable, [sys.executable, ENTRY, '--fps', '20'])

    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', ROWS, COLS, 0, 0))
    rng = random.Random(4)
    buf = b''
    try:
        for i in range(NKEYS):
            k = rng.choice(BOUND if i % 2 == 0 else UNBOUND)
            os.write(fd, k.encode())
            time.sleep(0.012)
            buf += drain(fd)
        time.sleep(0.4)
        buf += drain(fd, 40)
        # Still drawing?
        extra = b''
        time.sleep(0.5)
        extra += drain(fd, 40, 0.2)
        os.write(fd, b'q')
        time.sleep(0.5)
        extra += drain(fd, 40, 0.2)
    finally:
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass

    txt = (buf + extra).decode('utf-8', 'replace')
    tb = 'Traceback' in txt
    alive = len(extra) > 500
    frames = txt.count('\x1b[H')
    print('keys sent      %d' % NKEYS)
    print('bytes          %d' % len(txt))
    print('frames drawn   %d' % frames)
    print('still drawing  %s' % alive)
    print('tracebacks     %s' % tb)
    if tb:
        print(txt[txt.index('Traceback'):][:900])
    time.sleep(0.3)
    try:
        exited = os.waitpid(pid, os.WNOHANG)[0] != 0
    except ChildProcessError:
        exited = True
    print('exited on q    %s' % exited)
    ok = not tb and alive and frames > 40 and exited
    print('RESULT:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
