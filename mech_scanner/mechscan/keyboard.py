"""Non-blocking raw-mode key input."""
import os, select, sys

class Keyboard:
    """Non-blocking raw-mode key reader. No-ops when stdin isn't a tty."""

    def __init__(self):
        self.fd = None
        self.old = None
        self.termios = None
        if not sys.stdin.isatty():
            return
        try:
            import termios, tty
            self.termios = termios
            self.fd = sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        except Exception:
            self.fd = None

    def restore(self):
        if self.fd is not None and self.old is not None:
            try:
                self.termios.tcsetattr(self.fd, self.termios.TCSADRAIN, self.old)
            except Exception:
                pass

    def poll(self):
        if self.fd is None:
            return []
        keys = []
        while select.select([sys.stdin], [], [], 0)[0]:
            try:
                data = os.read(self.fd, 64)
            except OSError:
                break
            if not data:
                break
            keys.extend(self._parse(data.decode('utf-8', 'ignore')))
            if len(keys) > 32:
                break
        return keys

    @staticmethod
    def _parse(s):
        out, i = [], 0
        arrows = {'A': 'UP', 'B': 'DOWN', 'C': 'RIGHT', 'D': 'LEFT'}
        while i < len(s):
            if s[i] == '\x1b' and s[i + 1:i + 2] == '[':
                # Consume the whole CSI sequence up to its final byte. Taking a
                # fixed three characters spills every parameterised sequence's
                # parameters into the stream as ordinary keys.
                j = i + 2
                while j < len(s) and not ('\x40' <= s[j] <= '\x7e'):
                    j += 1
                if j >= len(s):
                    break
                if j == i + 2 and s[j] in arrows:
                    out.append(arrows[s[j]])
                i = j + 1
            elif s[i] == '\x7f' or s[i] == '\x08':
                out.append('BKSP')
                i += 1
            elif s[i] == '\r' or s[i] == '\n':
                out.append('ENTER')
                i += 1
            elif s[i] == '\x1b':
                out.append('ESC')
                i += 1
            else:
                out.append(s[i])
                i += 1
        return out
