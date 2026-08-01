#!/usr/bin/env python3
"""
 DISKSCAPE // voxel cartography of a filesystem
 ----------------------------------------------
 Your disk as a city, seen from a slow-orbiting camera. Every directory is a
 block whose footprint and height both come from its size, split so that a
 block's *volume* is exactly proportional to the bytes it holds. Drill into a
 district to see its own skyline.

 With --footprint count the ground plan switches to file count instead, and
 the two channels come apart: sprawling low-rise = a thousand tiny files,
 lone spire = one enormous one.

 Everything is real: an os.scandir walk on a background thread, apparent size
 or true block usage, hardlinks counted once. The city builds itself while the
 scan runs.

 Usage:
   python3 dscape.py                    survey $PWD
   python3 dscape.py ~/Projects         survey a path
   python3 dscape.py / --one-filesystem stay on the root device
   python3 dscape.py --apparent-size    st_size instead of allocated blocks
   python3 dscape.py --exclude '*.cache' --exclude node_modules
   python3 dscape.py --palette amber    matrix | amber | ice | plasma | blood
   python3 dscape.py --levels 1         districts only, no sub-blocks
   python3 dscape.py --height log       log height curve (default: power)
   python3 dscape.py --footprint count  ground plan by file count, not bytes
   python3 dscape.py --blocks half      coarser glyphs if quadrants look wrong
   python3 dscape.py --speed 2.5        orbit rate (also live, with , and .)
   python3 dscape.py --print            no graphics, just a du-style report
   (also --fps --tilt --zen --no-windows --no-stars)

 Live controls (press h in-flight for the full list):
   SPACE pause orbit    q quit          h help
   <- -> orbit          ^ v tilt        [ ] zoom      , . spin rate
   t     plan view: cranes the camera overhead and stops the spin, so the
         city flattens into a plain treemap. Tilt and pause do nothing while
         it holds. t again returns to the orbit, spinning.
   W     street level: drops you into the streets the treemap leaves between
         plots, outside whichever district was selected. wasd walks, the
         arrows turn and look, and a crosshair names the building ahead —
         ENTER steps into it, x marks it. W again returns to the orbit.
         Note it relays the city out with wider streets while it holds: the
         orbit layout leaves gaps too narrow to stand in, and a walker wedged
         in one has nowhere legal to be. Same data, coarser plan.
   j k   select         ENTER descend   BKSP ascend
 Past the directory you launched in, BKSP starts a fresh scan of the parent:
 the walk only ever went downward, so there is no tree above the root.
   p     palette        1-5 direct      w windows   g grid   l labels
   b     biggest files  x mark          r rescan    z zen    f footprint

 Marked paths are printed to stdout on exit, one per line, so you can pipe
 them somewhere that deletes things. This program never removes a file.
"""
import sys, os, math, time, shutil, argparse, signal, random, select, stat
import threading, colorsys, heapq, fnmatch
from collections import deque

# --- ANSI -----------------------------------------------------------------
ESC = '\033['
HIDE, SHOW = ESC + '?25l', ESC + '?25h'
HOME, CLEAR = ESC + 'H', ESC + '2J'
RESET = ESC + '0m'
FG_DEF, BG_DEF = ESC + '39m', ESC + '49m'

_FG, _BG = {}, {}


def fg(rgb):
    s = _FG.get(rgb)
    if s is None:
        s = f'{ESC}38;2;{rgb[0]};{rgb[1]};{rgb[2]}m'
        _FG[rgb] = s
    return s


def bg(rgb):
    s = _BG.get(rgb)
    if s is None:
        s = f'{ESC}48;2;{rgb[0]};{rgb[1]};{rgb[2]}m'
        _BG[rgb] = s
    return s


# Quadrant glyphs, indexed by a 4-bit mask of which sub-cells take the
# foreground colour: bit 1 = top-left, 2 = top-right, 4 = bottom-left,
# 8 = bottom-right. All sixteen exist in Block Elements (U+2580..U+259F), the
# same range as the half-blocks, so nothing here needs an exotic font.
QUAD = [' ', '▘', '▝', '▀', '▖', '▌', '▞', '▛',
        '▗', '▚', '▐', '▜', '▄', '▙', '▟', '█']


def lerp(c0, c1, t):
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    return (int(c0[0] + (c1[0] - c0[0]) * t),
            int(c0[1] + (c1[1] - c0[1]) * t),
            int(c0[2] + (c1[2] - c0[2]) * t))


def shade(c, k):
    return (min(255, int(c[0] * k)), min(255, int(c[1] * k)), min(255, int(c[2] * k)))


def quant(rgb, step=6):
    """Snap colors to a coarse ladder so the SGR caches stay small and the
    run-length emitter gets long runs out of every gradient."""
    return (rgb[0] // step * step, rgb[1] // step * step, rgb[2] // step * step)


# --- palettes -------------------------------------------------------------
# 'bld' is the base building color; face brightness is derived from it, and
# category tints are hue rotations of it, so every palette stays coherent.
PALETTES = {
    'matrix': {
        'bld':  (60, 220, 140), 'ground': (5, 24, 18), 'grid': (18, 74, 54),
        'win':  (200, 255, 220), 'sky': ((2, 9, 7), (10, 40, 30)),
        'star': (95, 140, 110), 'beam': (120, 255, 235),
        'hud':  (60, 235, 150), 'hud_dim': (25, 130, 85),
        'panel': (3, 16, 12), 'alert': (255, 120, 90), 'sel': (255, 245, 170),
    },
    'amber': {
        'bld':  (255, 172, 48), 'ground': (26, 13, 4), 'grid': (86, 48, 12),
        'win':  (255, 244, 205), 'sky': ((10, 5, 2), (44, 22, 8)),
        'star': (140, 105, 55), 'beam': (255, 205, 90),
        'hud':  (255, 176, 44), 'hud_dim': (140, 92, 20),
        'panel': (18, 9, 2), 'alert': (255, 95, 60), 'sel': (255, 255, 220),
    },
    'ice': {
        'bld':  (90, 200, 255), 'ground': (7, 14, 32), 'grid': (28, 54, 100),
        'win':  (230, 248, 255), 'sky': ((2, 6, 16), (16, 34, 68)),
        'star': (120, 150, 180), 'beam': (150, 235, 255),
        'hud':  (90, 210, 255), 'hud_dim': (40, 110, 150),
        'panel': (5, 11, 24), 'alert': (255, 130, 130), 'sel': (255, 250, 210),
    },
    'plasma': {
        'bld':  (200, 100, 240), 'ground': (18, 8, 32), 'grid': (66, 32, 96),
        'win':  (255, 235, 255), 'sky': ((7, 3, 16), (34, 16, 60)),
        'star': (140, 105, 165), 'beam': (120, 245, 255),
        'hud':  (230, 110, 240), 'hud_dim': (120, 55, 130),
        'panel': (13, 6, 24), 'alert': (255, 210, 90), 'sel': (190, 255, 255),
    },
    'blood': {
        'bld':  (235, 70, 62), 'ground': (26, 7, 9), 'grid': (86, 26, 28),
        'win':  (255, 228, 200), 'sky': ((10, 2, 3), (44, 12, 14)),
        'star': (140, 80, 80), 'beam': (255, 170, 90),
        'hud':  (255, 80, 72), 'hud_dim': (135, 38, 35),
        'panel': (18, 5, 6), 'alert': (255, 200, 60), 'sel': (255, 240, 200),
    },
}
PAL_NAMES = ['matrix', 'amber', 'ice', 'plasma', 'blood']

# --- file categories ------------------------------------------------------
# Districts take their tint from whatever kind of data dominates them, so the
# shape of a tree is legible before you read a single label.
CAT_NAMES = ['code', 'media', 'image', 'archive', 'doc', 'data', 'binary', 'other']
CAT_HUE = [-0.10, 0.30, 0.16, 0.44, 0.55, -0.24, 0.07, 0.0]
NCAT = len(CAT_NAMES)
CAT_OTHER = NCAT - 1

_CAT_EXT = {
    'code': 'py js ts tsx jsx mjs cjs c h cc cpp hpp cxx rs go java kt kts rb php '
            'sh bash zsh fish lua sql html htm css scss sass less vue svelte swift '
            'cs pl pm r jl ex exs erl scala clj cljs hs ml mli nim zig dart gradle '
            'cmake mk am toml ini cfg conf tf hcl proto patch diff',
    'media': 'mp4 mkv avi mov webm flv wmv m4v mpg mpeg vob 3gp mp3 flac wav ogg '
             'm4a aac opus wma aiff mid midi m2ts mts',
    'image': 'png jpg jpeg gif bmp svg webp tiff tif psd xcf ai eps raw cr2 cr3 nef '
             'arw dng heic heif ico avif',
    'archive': 'zip tar gz bz2 xz 7z rar zst lz lz4 lzma tgz tbz txz jar war ear '
               'iso dmg pkg deb rpm apk cab msi squashfs',
    'doc': 'pdf doc docx xls xlsx ppt pptx odt ods odp rtf txt md markdown rst org '
           'epub mobi azw3 djvu tex bib pages numbers key',
    'data': 'json xml csv tsv yaml yml db sqlite sqlite3 sqlitedb parquet avro orc '
            'ndjson jsonl bson pickle pkl npy npz h5 hdf5 mat sav dat log',
    'binary': 'so dll dylib exe bin o a lib obj pyc pyo class wasm node ko img vdi '
              'qcow2 vmdk vhd swp core dump elf efi',
}
EXT_CAT = {}
for _i, _n in enumerate(CAT_NAMES):
    for _e in _CAT_EXT.get(_n, '').split():
        EXT_CAT[_e] = _i


def cat_of(name):
    d = name.rfind('.')
    if d <= 0 or d == len(name) - 1 or len(name) - d > 12:
        return CAT_OTHER
    return EXT_CAT.get(name[d + 1:].lower(), CAT_OTHER)


def cat_colors(base):
    """Hue-rotate the palette's building color into one tint per category."""
    h, l, s = colorsys.rgb_to_hls(base[0] / 255.0, base[1] / 255.0, base[2] / 255.0)
    out = []
    for off in CAT_HUE:
        r, g, b = colorsys.hls_to_rgb((h + off) % 1.0, l, s)
        tint = (int(r * 255), int(g * 255), int(b * 255))
        out.append(lerp(base, tint, 0.62))
    return out


# --- formatting -----------------------------------------------------------
_UNITS = ('B', 'K', 'M', 'G', 'T', 'P')


def human(n, pad=False):
    n = float(n)
    i = 0
    while n >= 1024.0 and i < len(_UNITS) - 1:
        n /= 1024.0
        i += 1
    if i == 0:
        s = f'{int(n)} B'
    elif n >= 100:
        s = f'{n:.0f} {_UNITS[i]}B'
    elif n >= 10:
        s = f'{n:.1f} {_UNITS[i]}B'
    else:
        s = f'{n:.2f} {_UNITS[i]}B'
    return s.rjust(9) if pad else s


def commas(n):
    return f'{n:,}'


BAR_W = 9
_EIGHTHS = ' ▏▎▍▌▋▊▉'


def bar_str(frac):
    """Share-of-directory bar in eighths of a cell. A whole-cell bar rounded
    everything under 1/BAR_W down to nothing, which left the column blank for
    almost every row and made it look like it meant nothing at all."""
    if frac <= 0:
        return ' ' * BAR_W
    e = int(round(min(frac, 1.0) * BAR_W * 8))
    if e == 0:
        e = 1                       # anything non-zero gets a visible sliver
    full, rem = divmod(e, 8)
    s = '█' * full + (_EIGHTHS[rem] if rem else '')
    return s[:BAR_W].ljust(BAR_W)


def fmt_dur(s):
    s = int(s)
    return f'{s // 60:02d}:{s % 60:02d}'


# --- the tree -------------------------------------------------------------
FILES_NAME = '(files here)'


class Node:
    __slots__ = ('name', 'parent', 'children', 'size', 'files', 'subdirs',
                 'cats', 'listed', 'done', 'pending', 'err', 'seed',
                 'isfiles', 'fnode')

    def __init__(self, name, parent):
        self.name = name
        self.parent = parent
        self.children = []
        self.size = 0
        self.files = 0
        self.subdirs = 0
        self.cats = [0] * NCAT
        self.listed = False
        self.done = False
        self.pending = 0
        self.err = False
        self.seed = (hash(name) & 0xffff) or 1
        self.isfiles = False   # the synthetic "loose files" district
        self.fnode = None      # cached synthetic child, for stable identity

    def path(self):
        # the loose-files district stands for its own directory, so that
        # rescanning or reporting it names something that actually exists
        parts = []
        n = self.parent if self.isfiles else self
        while n.parent is not None:
            parts.append(n.name)
            n = n.parent
        parts.append(n.name)
        parts.reverse()
        return os.path.join(*parts) if len(parts) > 1 else parts[0]

    def top_cat(self):
        c = self.cats
        best, bi = -1, CAT_OTHER
        for i in range(NCAT):
            if c[i] > best:
                best, bi = c[i], i
        return bi if best > 0 else CAT_OTHER


PSEUDO = ('/proc', '/sys', '/dev', '/run/user')


class Scanner(threading.Thread):
    """Breadth-first os.scandir walk. BFS on purpose: the top of the tree
    resolves first, so the skyline is roughly right within a second even on a
    multi-terabyte volume, and only refines from there."""

    def __init__(self, root_path, apparent=False, one_fs=False, excludes=()):
        super().__init__(daemon=True)
        self.root = Node(os.path.abspath(root_path), None)
        self.apparent = apparent
        self.one_fs = one_fs
        self.excludes = list(excludes)
        self.lock = threading.Lock()
        self.stop_flag = False
        self.finished = False
        self.files = 0
        self.dirs = 0
        self.bytes = 0
        self.errors = 0
        self.links = 0
        self.current = ''
        self.started_at = time.time()
        self.elapsed = 0.0
        self.biggest = []          # min-heap of (size, path), capped
        self._seen = set()         # (dev, ino) for multiply-linked files
        try:
            self.root_dev = os.stat(self.root.name).st_dev
        except OSError:
            self.root_dev = -1

    def excluded(self, name, full):
        if full in PSEUDO or full.startswith('/proc/') or full.startswith('/sys/'):
            return True
        for pat in self.excludes:
            if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(full, pat):
                return True
        return False

    def run(self):
        q = deque([self.root])
        while q and not self.stop_flag:
            self._scan(q.popleft(), q)
            self.elapsed = time.time() - self.started_at
        self.elapsed = time.time() - self.started_at
        self.finished = True

    def _scan(self, node, q):
        path = node.path()
        self.current = path
        own_bytes = 0
        own_files = 0
        cats = [0] * NCAT
        kids = []
        apparent = self.apparent
        seen = self._seen
        try:
            it = os.scandir(path)
        except OSError:
            self.errors += 1
            node.err = True
            node.listed = True
            self._complete(node)
            return
        try:
            with it:
                for e in it:
                    if self.stop_flag:
                        break
                    try:
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        self.errors += 1
                        continue
                    mode = st.st_mode
                    if stat.S_ISDIR(mode):
                        full = os.path.join(path, e.name)
                        if self.one_fs and st.st_dev != self.root_dev:
                            continue
                        if self.excluded(e.name, full):
                            continue
                        kids.append(Node(e.name, node))
                    elif stat.S_ISREG(mode):
                        if st.st_nlink > 1:
                            key = (st.st_dev, st.st_ino)
                            if key in seen:
                                self.links += 1
                                continue
                            seen.add(key)
                        sz = st.st_size if apparent else getattr(st, 'st_blocks', 0) * 512
                        own_bytes += sz
                        own_files += 1
                        cats[cat_of(e.name)] += sz
                        self._note_big(sz, path, e.name)
        except OSError:
            self.errors += 1
            node.err = True

        with self.lock:
            node.children.extend(kids)
            node.listed = True
            node.pending = len(kids)
            n = node
            while n is not None:
                n.size += own_bytes
                n.files += own_files
                nc = n.cats
                for i in range(NCAT):
                    nc[i] += cats[i]
                n = n.parent
            if kids:
                n = node
                while n is not None:
                    n.subdirs += len(kids)
                    n = n.parent
            if not kids:
                self._complete_locked(node)
        self.files += own_files
        self.bytes += own_bytes
        self.dirs += 1
        q.extend(kids)

    def _complete(self, node):
        with self.lock:
            self._complete_locked(node)

    def _complete_locked(self, node):
        node.done = True
        p = node.parent
        while p is not None:
            p.pending -= 1
            if p.pending <= 0 and p.listed:
                p.done = True
                p = p.parent
            else:
                break

    def _note_big(self, sz, path, name):
        b = self.biggest
        if len(b) < 24:
            heapq.heappush(b, (sz, os.path.join(path, name)))
        elif sz > b[0][0]:
            heapq.heapreplace(b, (sz, os.path.join(path, name)))


# --- squarified treemap ---------------------------------------------------
def _worst(row_max, row_min, row_area, length):
    s2 = row_area * row_area
    r2 = length * length
    return max(r2 * row_max / s2, s2 / (r2 * row_min))


def squarify(areas, x, y, w, h):
    """Classic squarified treemap. `areas` must be positive and already sum to
    roughly w*h; returns one (x, y, w, h) per input, in input order."""
    out = []
    i, n = 0, len(areas)
    while i < n and w > 1e-6 and h > 1e-6:
        length = w if w < h else h
        j = i
        row_area = 0.0
        row_max = row_min = None
        while j < n:
            a = areas[j]
            new_area = row_area + a
            new_max = a if row_max is None or a > row_max else row_max
            new_min = a if row_min is None or a < row_min else row_min
            if j > i and _worst(row_max, row_min, row_area, length) <= \
                    _worst(new_max, new_min, new_area, length):
                break
            row_area, row_max, row_min = new_area, new_max, new_min
            j += 1
        if w >= h:
            rw = row_area / h
            cy = y
            for k in range(i, j):
                rh = areas[k] / row_area * h
                out.append((x, cy, rw, rh))
                cy += rh
            x += rw
            w -= rw
        else:
            rh = row_area / w
            cx = x
            for k in range(i, j):
                rw = areas[k] / row_area * w
                out.append((cx, y, rw, rh))
                cx += rw
            y += rh
            h -= rh
        i = j
    while len(out) < n:
        out.append((x, y, 0.0, 0.0))
    return out


# --- raster ---------------------------------------------------------------
class Raster:
    """Pixel buffer at 1x2 per terminal cell, emitted as half-blocks. Spans are
    written with slice assignment, which is the only reason this runs at frame
    rate in pure Python."""

    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = [[None] * w for _ in range(h)]

    def clear(self, c=None):
        w = self.w
        for row in self.px:
            row[:] = [c] * w

    def hband(self, y0, y1, c):
        px, w = self.px, self.w
        if y0 < 0:
            y0 = 0
        if y1 > self.h:
            y1 = self.h
        row = [c] * w
        for y in range(y0, y1):
            px[y] = row[:]

    def point(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = c

    def fill(self, pts, c0, c1=None, yref=None):
        """Scanline-fill a convex polygon, lerping c0->c1 down the screen.

        `yref` overrides the span the gradient is measured over. A polygon that
        has been clipped against the near plane has vertices flung out to
        ~1e5 px, so its own ymin/ymax would compress the whole visible wall
        into one narrow slice of the ramp and it would render flat. Callers
        that clip pass the unclipped face's screen extent instead. Defaulted,
        so nothing that does not clip changes by a pixel.
        """
        n = len(pts)
        ys = [p[1] for p in pts]
        ymin, ymax = min(ys), max(ys)
        # The scan bounds always come from the polygon itself; only the
        # gradient may be measured over a different span.
        y0 = int(math.ceil(ymin - 0.5))
        y1 = int(math.floor(ymax - 0.5))
        if y0 < 0:
            y0 = 0
        if y1 >= self.h:
            y1 = self.h - 1
        if y1 < y0:
            return
        if yref is not None:
            ymin, ymax = yref
        span = (ymax - ymin) or 1.0
        px, W = self.px, self.w
        grad = c1 is not None and c1 != c0
        for y in range(y0, y1 + 1):
            yc = y + 0.5
            xs = []
            for i in range(n):
                ax, ay = pts[i]
                bx, by = pts[i - 1]
                if (ay <= yc < by) or (by <= yc < ay):
                    xs.append(ax + (bx - ax) * (yc - ay) / (by - ay))
            if len(xs) < 2:
                continue
            if len(xs) > 2:
                xs.sort()
            elif xs[0] > xs[1]:
                xs.reverse()
            c = quant(lerp(c0, c1, (yc - ymin) / span)) if grad else c0
            row = px[y]
            for i in range(0, len(xs) - 1, 2):
                xa = int(math.ceil(xs[i] - 0.5))
                xb = int(math.floor(xs[i + 1] - 0.5)) + 1
                if xa < 0:
                    xa = 0
                if xb > W:
                    xb = W
                if xb > xa:
                    row[xa:xb] = [c] * (xb - xa)

    def line(self, x0, y0, x1, y1, c):
        dx, dy = x1 - x0, y1 - y0
        steps = int(max(abs(dx), abs(dy)))
        if steps <= 0:
            self.point(int(x0), int(y0), c)
            return
        sx, sy = dx / steps, dy / steps
        px, W, H = self.px, self.w, self.h
        x, y = x0, y0
        for _ in range(steps + 1):
            xi, yi = int(x), int(y)
            if 0 <= xi < W and 0 <= yi < H:
                px[yi][xi] = c
            x += sx
            y += sy

    def line_c(self, x0, y0, x1, y1, c):
        """line(), but clipped to the viewport first (Liang-Barsky).

        line() steps one pixel at a time and merely *tests* each one for being
        on screen, which is fine when endpoints come from a camera 210 units
        away. A near-plane clip leaves vertices at ~1e5 px, and a segment that
        long costs tens of milliseconds to walk while painting nothing. Clip
        the parameter range instead, then step only the part that lands.
        """
        dx, dy = x1 - x0, y1 - y0
        t0, t1 = 0.0, 1.0
        for p, q in ((-dx, x0), (dx, self.w - 1 - x0),
                     (-dy, y0), (dy, self.h - 1 - y0)):
            if p == 0.0:
                if q < 0.0:
                    return              # parallel to this edge and outside it
            else:
                r = q / p
                if p < 0.0:
                    if r > t1:
                        return
                    if r > t0:
                        t0 = r
                else:
                    if r < t0:
                        return
                    if r < t1:
                        t1 = r
        self.line(x0 + t0 * dx, y0 + t0 * dy,
                  x0 + t1 * dx, y0 + t1 * dy, c)


# --- keyboard -------------------------------------------------------------
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
                # Consume the whole CSI sequence, up to its final byte. Taking
                # a fixed three characters meant every parameterised sequence
                # spilled its parameters into the stream as ordinary keys:
                # shift+Up arrived as ESC ; 2 A and that bare '2' switched the
                # palette, a mouse click emitted 2, 3 and 4, and a bracketed
                # paste emitted '0', which reset the view. Harmless while the
                # arrows were a secondary control; not once they steer.
                j = i + 2
                while j < len(s) and not ('\x40' <= s[j] <= '\x7e'):
                    j += 1
                if j >= len(s):         # split read: leave it for the next poll
                    break
                # An unrecognised CSI is swallowed, not reported as ESC. ESC
                # ascends the tree, and no terminal sends a parameterised
                # sequence to mean the user pressed Escape -- only a bare \x1b
                # does, which the branch below still handles.
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


# --- city layout ----------------------------------------------------------
PLOT = 100.0        # world units across the whole survey area
HMAX = 78.0         # tallest possible building
STREET = 0.20       # fraction of a plot given over to streets
MIN_PLOT = 1.1      # world units below which we stop subdividing
ROT_RATE = 0.30     # radians/second of orbit at --speed 1

# Sample points around the circle the auto-fit frames. Fixed angles, not
# angles relative to the camera, so the fit is bit-for-bit identical at every
# azimuth rather than rippling by however much the sampling missed.
FIT_RING = [(math.cos(i * math.pi / 12), math.sin(i * math.pi / 12))
            for i in range(24)]

# --- street level ---------------------------------------------------------
# Human scale is fixed from the eye, not from the buildings: a 1.7 m eye at
# EYE_H makes one world unit about 3.4 m, which puts the median block at ~36 m
# (twelve storeys), the tallest at ~220 m, and the streets between them at
# 1.5-3 m. A dense downtown of alleys, which is the right look for this.
EYE_H = 0.5
WALK_R = 0.30       # collision radius, about a metre
WALK_V = 4.0        # world units per second on foot, ~14 m/s
WALK_TURN = 0.10    # radians per turn keypress; autorepeat does the rest
WALK_TAU = 0.18     # velocity decay; see the note on key repeat in walk_step
FP_FOV = math.radians(65.0)     # vertical field of view

# The orbit camera sits 210 units out from a 100-unit plot, so no geometry ever
# comes near it and clamping the divisor is enough. Standing in a street, walls
# cross the eye plane constantly, so there is a real near plane now. It has to
# be clipped against, not clamped to -- clamping does not only fold a straddling
# wall inside out, it also freezes the size of a wall you are walking toward.
# ZNEAR sits well inside WALK_R so a whole face is never nearer than this; what
# crosses the plane is the far side of a face that extends past your shoulder.
ZNEAR = 0.08

# Street level relays the city out with wider streets and no slivers. This is
# not decoration: the orbit layout leaves 93 of 238 gaps narrower than twice
# the walker, and a walker wedged in a gap it does not fit has *no* legal
# position -- pushing it off one wall pushes it into the other, for ever.
# Measured over half a million substeps, the shipped layout leaves the walker
# up to 0.10 units inside a building and no number of resolution passes fixes
# it (16 passes still left 0.047); these numbers leave exactly zero. Shrinking
# the walker instead does not work either -- at radius 0.14 it is still 0.04
# inside, because the layout emits blocks as thin as 0.04 whatever you do.
WALK_STREET = 0.50
WALK_MINPLOT = 4.0


class Bldg:
    __slots__ = ('node', 'x0', 'y0', 'x1', 'y1', 'h', 'cat', 'root', 'level')

    def __init__(self, node, x0, y0, x1, y1, h, cat, root, level):
        self.node = node
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.h = h
        self.cat = cat
        self.root = root      # which top-level district this belongs to
        self.level = level


def weight_of(node, mode):
    """Footprints are compressed, not raw. File counts across a home directory
    span five decades; laid out linearly, one .cache district swallows the
    entire plot and everything else becomes a sliver. The 0.55 power keeps the
    ordering intact while leaving every district a footprint you can see."""
    w = float(node.size) if mode == 'size' else float(node.files) + node.subdirs * 0.35
    return w ** 0.55 if w > 0 else 0.0


def layout(cur, levels, footprint, height_mode, budget=520, min_plot=MIN_PLOT,
           street=STREET):
    """Lay the current directory out as a city. Returns (buildings, districts)
    where districts are the (node, rect) of the direct children — the things
    the selection cursor moves between."""
    kids = [c for c in cur.children if c.size > 0 or c.files > 0]

    # Bytes sitting loose in this directory belong to no subdirectory, so
    # without this they get no block: a Downloads holding 28 GB of files and
    # two small folders would render as just the two folders. Give them a
    # district of their own so they can be seen, selected and opened.
    if not cur.isfiles:
        own = cur.size - sum(c.size for c in cur.children)
        own_files = cur.files - sum(c.files for c in cur.children)
        if own > 0 or own_files > 0:
            fn = cur.fnode
            if fn is None:
                fn = Node(FILES_NAME, cur)
                fn.isfiles = True
                cur.fnode = fn
            fn.size = max(own, 0)
            fn.files = max(own_files, 0)
            fn.done = cur.done
            for i in range(NCAT):
                fn.cats[i] = max(cur.cats[i] - sum(c.cats[i]
                                                   for c in cur.children), 0)
            kids.append(fn)

    if not kids:
        return [], []
    kids.sort(key=lambda n: n.size, reverse=True)

    ws = [weight_of(n, footprint) for n in kids]
    floor = max(ws) * 0.006 if ws else 1.0
    ws = [max(w, floor, 1e-9) for w in ws]
    tot = sum(ws)
    scale = (PLOT * PLOT) / tot
    rects = squarify([w * scale for w in ws], -PLOT / 2, -PLOT / 2, PLOT, PLOT)

    districts = list(zip(kids, rects))

    # height scale is global across the whole city so blocks stay comparable
    hmax_size = max((n.size for n in kids), default=1) or 1
    if height_mode == 'log':
        s0 = max(hmax_size / 1e4, 1.0)
        den = math.log1p(hmax_size / s0)

        def height(sz):
            return max(0.55, HMAX * math.log1p(max(sz, 0) / s0) / den)
    else:
        def height(sz):
            return max(0.55, HMAX * (max(sz, 0) / hmax_size) ** 0.45)

    out = []
    # Subdivide the largest districts first and stop once we hit the budget,
    # so a directory with 40k children still renders at frame rate.
    order = sorted(range(len(kids)), key=lambda i: -(rects[i][2] * rects[i][3]))
    subdivide = set()
    spent = len(kids)
    for i in order:
        if levels <= 1 or spent >= budget:
            break
        n = kids[i]
        _, _, w, h = rects[i]
        if len(n.children) < 2 or min(w, h) < min_plot * 3:
            continue
        k = min(len(n.children), 24)
        if spent + k > budget:
            continue
        subdivide.add(i)
        spent += k

    for i, (n, (x, y, w, h)) in enumerate(zip(kids, rects)):
        if w <= 0 or h <= 0:
            continue
        cat = n.top_cat()
        mx = min(min(w, h) * street, 1.2)
        x0, y0, x1, y1 = x + mx, y + mx, x + w - mx, y + h - mx
        if x1 - x0 < 0.05 or y1 - y0 < 0.05:
            continue
        if i in subdivide:
            _sub(out, n, x0, y0, x1 - x0, y1 - y0, height, footprint, n, 2,
                 levels, budget, min_plot, street)
        else:
            out.append(Bldg(n, x0, y0, x1, y1, height(n.size), cat, n, 1))
    return out, districts


def _sub(out, node, x, y, w, h, height, footprint, root, level, levels, budget,
         min_plot, street=STREET):
    kids = [c for c in node.children if c.size > 0 or c.files > 0][:24]
    if not kids or level > levels:
        out.append(Bldg(node, x, y, x + w, y + h, height(node.size),
                        node.top_cat(), root, level - 1))
        return
    kids.sort(key=lambda n: n.size, reverse=True)
    ws = [max(weight_of(n, footprint), 1e-9) for n in kids]
    tot = sum(ws)
    rects = squarify([wt / tot * (w * h) for wt in ws], x, y, w, h)
    for n, (rx, ry, rw, rh) in zip(kids, rects):
        if rw <= 0 or rh <= 0:
            continue
        mx = min(min(rw, rh) * street, 0.45)
        a, b, c, d = rx + mx, ry + mx, rx + rw - mx, ry + rh - mx
        if c - a < 0.04 or d - b < 0.04:
            continue
        # Recurse while there is plot left to divide and budget to spend.
        # Without this every city bottomed out at two levels and --levels
        # above 2 did nothing at all.
        if (level < levels and len(n.children) >= 2 and len(out) < budget
                and min(c - a, d - b) >= min_plot * 2):
            _sub(out, n, a, b, c - a, d - b, height, footprint, root,
                 level + 1, levels, budget, min_plot, street)
        else:
            out.append(Bldg(n, a, b, c, d, height(n.size), n.top_cat(),
                            root, level))


# --- painter's order ------------------------------------------------------
# No single per-block number can order these blocks correctly, and two earlier
# attempts to find one both failed. The depth of a block is not a property of
# the block: for two neighbouring footprints the near/far answer depends on
# which side of the edge *between* them the camera stands, so any scalar key
# is wrong somewhere on the orbit. Measured against a ray-cast ground truth,
# sorting by the nearest corner leaves up to 56 wrong pixels per frame, and it
# is worst at the cardinal azimuths — where the camera's ground position falls
# inside the plot and the "nearest" corner is no longer the nearest one.
#
# What does work is the layout's own structure. squarify slices a strip off
# the remaining rectangle each pass, so the plot is a guillotine partition:
# every block sits on one side of every cut, never across one. That is a BSP,
# and drawing the far side of each cut before the near side is exact, by
# construction, for any camera. It also costs less than the sort it replaces,
# because the tree depends only on the layout — the camera enters just once
# per cut, as a comparison against the cut line.
def _split(rects):
    """Find an axis-aligned line no rect straddles, as balanced as possible."""
    best = None
    n = len(rects)
    for axis in (0, 1):
        if axis == 0:
            srt = sorted(rects, key=lambda b: b.x0)
            lo_k = [b.x0 for b in srt]
            hi_k = [b.x1 for b in srt]
        else:
            srt = sorted(rects, key=lambda b: b.y0)
            lo_k = [b.y0 for b in srt]
            hi_k = [b.y1 for b in srt]
        m = -1e30
        for i in range(n - 1):
            if hi_k[i] > m:
                m = hi_k[i]
            if m <= lo_k[i + 1] + 1e-9:
                bal = abs((i + 1) - n * 0.5)
                if best is None or bal < best[0]:
                    best = (bal, axis, (m + lo_k[i + 1]) * 0.5,
                            srt[:i + 1], srt[i + 1:])
    return best


def build_bsp(rects):
    """(axis, cut, lo, hi, leaf). Built once per relayout, not per frame."""
    if len(rects) <= 1:
        return (0, 0.0, None, None, rects)
    s = _split(rects)
    if s is None:                    # not guillotine after all; draw them flat
        return (0, 0.0, None, None, rects)
    _, axis, cut, lo, hi = s
    return (axis, cut, build_bsp(lo), build_bsp(hi), None)


def bsp_order(tree, camx, camy):
    """Back to front. O(n), no comparisons, exact for any camera position."""
    out = []
    stack = [tree]
    push = stack.append
    while stack:
        axis, cut, lo, hi, leaf = stack.pop()
        if leaf is not None:
            out.extend(leaf)
        elif (camx if axis == 0 else camy) < cut:
            push(lo)                 # near side pushed first, so drawn last
            push(hi)
        else:
            push(hi)
            push(lo)
    return out


# --- near-plane clipping --------------------------------------------------
# Sutherland-Hodgman against the single plane zv = ZNEAR, run on the camera
# -space triples *before* the perspective divide. All three components are
# linear in world position, so interpolating the crossing point linearly is
# exact rather than approximate -- which is the whole reason for clipping here
# rather than after the divide, where nothing is linear any more.
def clip_near(cp):
    """cp = [(u, v, zv), ...] convex. Returns [] or a 3-to-5 point polygon."""
    for p in cp:
        if p[2] < ZNEAR:
            break
    else:
        return cp                       # wholly in front, the common case
    out = []
    n = len(cp)
    for i in range(n):
        a, b = cp[i], cp[i - 1]
        ain, bin_ = a[2] >= ZNEAR, b[2] >= ZNEAR
        if ain != bin_:
            t = (ZNEAR - b[2]) / (a[2] - b[2])
            out.append((b[0] + (a[0] - b[0]) * t,
                        b[1] + (a[1] - b[1]) * t, ZNEAR))
        if ain:
            out.append(a)
    return out


def clip_seg(a, b):
    """Same plane, for a segment. Returns (a, b) or None if wholly behind."""
    if a[2] >= ZNEAR and b[2] >= ZNEAR:
        return a, b
    if a[2] < ZNEAR and b[2] < ZNEAR:
        return None
    t = (ZNEAR - b[2]) / (a[2] - b[2])
    m = (b[0] + (a[0] - b[0]) * t, b[1] + (a[1] - b[1]) * t, ZNEAR)
    return (a, m) if a[2] >= ZNEAR else (m, b)


def ray_block(b, ox, oy, oz, dx, dy, dz):
    """Slab method. Distance to the near face of b, or None if the ray misses.

    The same test the ray-cast harness used to prove the painter's order; here
    it answers what the crosshair is pointing at.
    """
    t0, t1 = 0.0, 1e30
    for o, d, lo, hi in ((ox, dx, b.x0, b.x1), (oy, dy, b.y0, b.y1),
                         (oz, dz, 0.0, b.h)):
        if -1e-12 < d < 1e-12:
            if o < lo or o > hi:
                return None
        else:
            ta, tb = (lo - o) / d, (hi - o) / d
            if ta > tb:
                ta, tb = tb, ta
            if ta > t0:
                t0 = ta
            if tb < t1:
                t1 = tb
            if t0 > t1:
                return None
    return t0 if t0 > 0.0 else (t1 if t1 > 0.0 else None)


# --- report mode ----------------------------------------------------------
def populate_files(fn, apparent):
    """Fill a loose-files district with one node per real file. Done on demand
    from a single scandir of the one directory, so nothing is held for the
    hundreds of thousands of files the survey walked past."""
    base = fn.path()
    kids = []
    try:
        with os.scandir(base) as it:
            for e in it:
                try:
                    st = e.stat(follow_symlinks=False)
                except OSError:
                    continue
                if not stat.S_ISREG(st.st_mode):
                    continue
                sz = st.st_size if apparent else getattr(st, 'st_blocks', 0) * 512
                c = Node(e.name, fn.parent)   # parent, so path() is the real one
                c.size = sz
                c.files = 1
                c.done = True
                c.cats[cat_of(e.name)] = sz
                kids.append(c)
    except OSError:
        pass
    fn.children = kids
    return kids


def enterable(n):
    """Is there a city to draw inside `n`? `children` alone is the wrong test:
    it holds subdirectories only, so a directory of nothing but files looked
    like a leaf even though layout() gives its loose bytes a district of their
    own -- which for a folder of 47 GB of models is the whole point of going in.
    Mirrors layout()'s own kids test, so the two cannot disagree."""
    if n.isfiles:
        return True                 # populate_files decides; it may find none
    if any(c.size > 0 or c.files > 0 for c in n.children):
        return True
    return (n.size - sum(c.size for c in n.children) > 0
            or n.files - sum(c.files for c in n.children) > 0)


def print_report(sc, limit=40):
    root = sc.root
    kids = sorted(root.children, key=lambda n: n.size, reverse=True)
    total = root.size or 1
    print(f'\n{root.name}   {human(root.size)}   {commas(root.files)} files   '
          f'{commas(root.subdirs)} dirs')
    print('-' * 64)
    for n in kids[:limit]:
        pct = n.size / total * 100.0
        bar = '█' * int(pct / 100.0 * 24)
        print(f'{human(n.size, True)}  {pct:5.1f}%  {bar:<24} {n.name}')
    own = root.size - sum(n.size for n in kids)
    if own > 0:
        print(f'{human(own, True)}  {own / total * 100:5.1f}%  '
              f'{"·" * int(own / total * 24):<24} (files here)')
    print('-' * 64)
    print('largest files:')
    for sz, p in sorted(sc.biggest, reverse=True)[:12]:
        print(f'{human(sz, True)}  {p}')
    if sc.errors:
        print(f'\n{sc.errors} unreadable entries skipped')


HELP_LINES = [
    'SPACE  pause orbit',
    'q      quit',
    '<- ->  orbit camera',
    '^  v   camera tilt',
    't      plan view (top',
    '       down, paused)',
    '[  ]   zoom out / in',
    ',  .   spin slower /',
    '       faster (through',
    '       zero to reverse)',
    'j / k  select district',
    'ENTER  descend',
    'BKSP   ascend (rescans',
    '       above the root)',
    'r      rescan subtree',
    'x      mark path',
    'b      biggest files',
    'l      district labels',
    'w      window lights',
    'g      ground grid',
    's      starfield',
    'f      footprint metric',
    'p      cycle palette',
    '1-5    palette direct',
    'z      zen mode',
    'W      street level',
    'h / ?  close help',
]

# Street level rebinds w/a/s/d, so it needs its own list rather than a single
# one grown to cover both. Keys not named here are silently inert while it
# holds -- nobody needs to be told off by their own skyline.
WALK_HELP_LINES = [
    'W      back to orbit',
    'q      quit',
    'w / s  forward / back',
    'a / d  strafe',
    '<- ->  turn',
    '^  v   look up / down',
    '[  ]   field of view',
    ',  .   walk slower /',
    '       faster',
    'ENTER  enter the',
    '       building ahead',
    'x      mark it',
    'BKSP   ascend',
    'j / k  select district',
    '       (the beam)',
    'r      rescan subtree',
    'b      biggest files',
    'l      district labels',
    'g      ground grid',
    'f      footprint metric',
    'p      cycle palette',
    '1-5    palette direct',
    'z      zen mode',
    '0      reset to orbit',
    'h / ?  close help',
]


# --- main -----------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('path', nargs='?', default='.')
    ap.add_argument('--apparent-size', action='store_true')
    ap.add_argument('--one-filesystem', '-x', action='store_true')
    ap.add_argument('--exclude', action='append', default=[])
    ap.add_argument('--palette', default='matrix', choices=PAL_NAMES)
    ap.add_argument('--levels', type=int, default=3)
    ap.add_argument('--height', default='pow', choices=['pow', 'log'])
    ap.add_argument('--footprint', default='size', choices=['size', 'count'])
    ap.add_argument('--blocks', default='quad', choices=['quad', 'half'])
    ap.add_argument('--fps', type=float, default=30.0)
    ap.add_argument('--tilt', type=float, default=22.0)
    ap.add_argument('--speed', type=float, default=1.0)
    ap.add_argument('--zen', action='store_true')
    ap.add_argument('--no-windows', action='store_true')
    ap.add_argument('--no-stars', action='store_true')
    ap.add_argument('--print', dest='report', action='store_true')
    ap.add_argument('-h', '--help', action='store_true')
    args = ap.parse_args()

    if args.help:
        print(__doc__)
        return 0

    root_path = os.path.abspath(os.path.expanduser(args.path))
    if not os.path.isdir(root_path):
        print(f'dscape: not a directory: {root_path}', file=sys.stderr)
        return 1

    sc = Scanner(root_path, args.apparent_size, args.one_filesystem, args.exclude)
    sc.start()

    if args.report:
        while not sc.finished:
            time.sleep(0.1)
        print_report(sc)
        return 0

    # Horizontal sub-cells per terminal cell. 2 uses quadrant glyphs for twice
    # the horizontal detail; 1 falls back to plain half-blocks.
    SUBX = 2 if args.blocks == 'quad' else 1

    kb = Keyboard()
    marked = []          # paths, for the exit report; survives a rescan
    marked_nodes = set()  # the same things as live nodes, for the render test

    quitting = []          # set by a signal, drained by the frame loop

    def cleanup(*_):
        # Teardown must finish come what may: it is the only thing that puts
        # the cursor, colours and terminal mode back. Go deaf first, then
        # retry once, because a signal already in flight can land between
        # entering here and the SIG_IGN taking effect.
        for s in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            try:
                signal.signal(s, signal.SIG_IGN)
            except Exception:
                pass
        for _attempt in (0, 1):
            try:
                kb.restore()
                sys.stdout.write(SHOW + RESET + BG_DEF + FG_DEF + CLEAR + HOME)
                sys.stdout.flush()
                return
            except BaseException:
                continue

    # A handler that raises can fire *anywhere*, including inside cleanup, in
    # which case the exception escapes main and dumps a traceback over a
    # terminal that has not been restored yet. Just record the request and let
    # the frame loop notice it at a point where unwinding is safe.
    for s in (signal.SIGTERM, signal.SIGHUP):
        try:
            signal.signal(s, lambda *_: quitting.append(True))
        except Exception:
            pass

    sys.stdout.write(HIDE + CLEAR)
    pal_i = PAL_NAMES.index(args.palette)
    P = PALETTES[PAL_NAMES[pal_i]]
    CATC = cat_colors(P['bld'])

    stack = [sc.root]
    sel = 0
    az = 0.7
    el = math.radians(max(6.0, min(75.0, args.tilt)))
    el_target = el          # camera tilt eases toward this
    az_target = None        # set only in plan view, to hold it square
    dist_cam = 210.0        # pulled back in plan view, toward orthographic
    dist_target = 210.0
    plan = False            # top-down plan view (t)
    plan_restore = el       # only the tilt: the rest of the set is fixed
    walk = False            # street level (W)
    wx, wy = 0.0, 0.0       # walker's feet; eye is EYE_H above them
    wv_f = wv_s = 0.0       # forward/strafe velocity, decayed each frame
    walk_near = None        # blocks close enough to collide with
    walk_anchor = None      # where walk_near was gathered from
    walk_target = None      # the block under the crosshair
    walk_restore = None     # the whole orbit variable set, put back by W
    zoom = 1.0
    speed = args.speed
    paused = False
    zen = args.zen
    show_help = False
    show_big = False
    labels = True
    windows = not args.no_windows
    stars_on = not args.no_stars
    grid_on = True
    footprint = args.footprint
    levels = max(1, args.levels)
    flash, flash_until = '', 0.0

    cols = rows = 0
    ras = None
    ov = None
    stars = []
    blds, districts = [], []
    bsp = None                      # guillotine tree, rebuilt by relayout()
    last_layout = 0.0
    layout_sig = None
    fit_f, fit_ox, fit_oy = None, 0.0, 0.0
    t0 = time.time()
    prev_now = t0
    frame = 0
    fps_avg = args.fps

    pending_select = None   # name to re-select once a fresh scan surfaces it
    sel_node = None         # the selection is a *node*, not a row index

    def set_sel(i):
        nonlocal sel, sel_node
        sel = i
        sel_node = districts[i][0] if 0 <= i < len(districts) else None

    def relayout():
        nonlocal blds, districts, sel, sel_node, pending_select, bsp
        # Stop subdividing once a plot is under a few pixels wide. This is the
        # constraint that actually decides how dense the city gets, and it has
        # to be derived from the terminal: in fixed world units a tiny font
        # buys nothing, and a small terminal turns into mud.
        min_plot = max(0.5, min(6.0, 500.0 / (cols * SUBX * 0.75)))
        budget = max(250, min(1400, cols * rows // 20))
        street = STREET
        if walk:
            # Wider streets and no slivers, so the walker always has somewhere
            # legal to stand. See WALK_STREET for why this is not optional.
            min_plot, street = WALK_MINPLOT, WALK_STREET
        with sc.lock:
            blds, districts = layout(stack[-1], levels, footprint,
                                     args.height, budget, min_plot, street)
        bsp = build_bsp(blds)
        # Districts are re-sorted by size every time the scan moves, so a bare
        # row index would slide onto a different directory under the cursor.
        # Re-find the node we were actually pointing at.
        if pending_select is not None:
            for i, (n, _) in enumerate(districts):
                if n.name == pending_select:
                    sel = i
                    pending_select = None
                    break
        elif sel_node is not None:
            for i, (n, _) in enumerate(districts):
                if n is sel_node:
                    sel = i
                    break
        if sel >= len(districts):
            sel = max(0, len(districts) - 1)
        sel_node = districts[sel][0] if districts else None
        # The layout is rebuilt every 0.45 s while the scan runs, and on every
        # descend and ascend, so a building can materialise around the walker.
        # Inside a footprint both wall tests pick None and the block draws
        # nothing, so you would be standing in an invisible building -- push
        # back out before anyone sees it.
        if walk:
            walk_gather()
            for _ in range(8):
                if not walk_resolve():
                    break
            else:
                walk_spawn()        # wedged: start again from the street

    # --- walking --------------------------------------------------------
    # Every block stands at least 0.55 units tall and the eye is at 0.5, so
    # there is nothing to step over and no height test to make: a footprint is
    # simply solid. That also keeps the renderer honest -- inside a footprint
    # both wall tests pick None and the block draws nothing, so the camera
    # being outside every footprint is what makes the cheap backface test
    # correct, and collision is what guarantees it.
    def walk_gather():
        """Blocks near enough to matter. Refreshed on movement, not per frame."""
        nonlocal walk_near, walk_anchor
        r = 8.0
        walk_near = [b for b in blds
                     if b.x0 - r < wx < b.x1 + r and b.y0 - r < wy < b.y1 + r]
        walk_anchor = (wx, wy)

    def walk_resolve():
        """Push the walker out of any block it overlaps. True if it moved."""
        nonlocal wx, wy
        moved = False
        for _pass in (0, 1):        # twice, so an inside corner settles
            for b in walk_near:
                cx = b.x0 if wx < b.x0 else (b.x1 if wx > b.x1 else wx)
                cy = b.y0 if wy < b.y0 else (b.y1 if wy > b.y1 else wy)
                dx, dy = wx - cx, wy - cy
                d2 = dx * dx + dy * dy
                if d2 >= WALK_R * WALK_R:
                    continue
                moved = True
                if d2 > 1e-12:
                    d = math.sqrt(d2)
                    k = (WALK_R - d) / d
                    wx += dx * k
                    wy += dy * k
                else:
                    # dead centre inside: leave by the nearest wall
                    out = min((wx - b.x0, -1.0, 0.0), (b.x1 - wx, 1.0, 0.0),
                              (wy - b.y0, 0.0, -1.0), (b.y1 - wy, 0.0, 1.0))
                    wx += out[1] * (out[0] + WALK_R)
                    wy += out[2] * (out[0] + WALK_R)
        g = PLOT / 2 - WALK_R
        wx = max(-g, min(g, wx))
        wy = max(-g, min(g, wy))
        return moved

    def walk_clear(px, py):
        """Distance from (px, py) to the nearest block, negative if inside.

        The plot edge counts as a wall. It is not one you can bump into, but
        beyond it there is nothing to see, so treating open ground as elbow
        room sent the spawn straight out to the perimeter every time.
        """
        g = PLOT / 2
        best = min(g - px, px + g, g - py, py + g)
        if best < 0.0:
            return -1.0
        for b in blds:
            cx = b.x0 if px < b.x0 else (b.x1 if px > b.x1 else px)
            cy = b.y0 if py < b.y0 else (b.y1 if py > b.y1 else py)
            if cx == px and cy == py:
                return -1.0
            d = math.hypot(px - cx, py - cy)
            if d < best:
                best = d
        return best

    def walk_spawn():
        """Put the walker on the street outside whatever district is selected,
        so W means 'go and stand next to the thing I was looking at'."""
        nonlocal wx, wy, az
        if districts and 0 <= sel < len(districts):
            _, (rx, ry, rw, rh) = districts[sel]
            tx, ty = rx + rw / 2, ry + rh / 2
        else:
            tx = ty = 0.0
        # Nearest is the wrong thing to want. The closest point that merely
        # clears the walker is the tightest crack against the district wall,
        # and standing in a 0.6-unit slot between ten-unit blocks means the
        # whole screen is one wall. Score elbow room against distance instead
        # and you come out on the widest street nearby, facing in.
        g = PLOT / 2 - WALK_R
        best, bests = None, -1e30
        for ring in range(1, 34):
            r = ring * 0.7
            steps = max(10, ring * 5)
            for i in range(steps):
                a = i * 2 * math.pi / steps
                px, py = tx + r * math.cos(a), ty + r * math.sin(a)
                if not (-g <= px <= g and -g <= py <= g):
                    continue
                cl = walk_clear(px, py)
                if cl < WALK_R:
                    continue
                # room is worth having, but only up to a point: past a couple
                # of units it is a plaza and further out buys nothing
                s = min(cl, 2.0) * 3.0 - r * 0.28
                if s > bests:
                    best, bests = (px, py), s
            if best is not None and ring * 0.7 > 14.0:
                break               # far enough that nothing better is coming
        wx, wy = best if best is not None else (0.0, 0.0)
        # Facing the district you asked for sounds right and looks terrible:
        # you are standing a metre from it, so its nearest wall is the whole
        # screen. Look down the street instead, preferring the open direction
        # that also points roughly at the selection -- you get a view, and the
        # compass and the beam still say where the thing is.
        # The camera's forward vector is (-sin az, cos az).
        want = math.atan2(-(tx - wx), ty - wy)
        best_a, best_s = want, -1e30
        for i in range(24):
            a = i * math.pi / 12
            dx_, dy_ = -math.sin(a), math.cos(a)
            reach = 60.0
            for b in blds:
                t = ray_block(b, wx, wy, EYE_H, dx_, dy_, 0.0)
                if t is not None and t < reach:
                    reach = t
            d = (a - want + math.pi) % (2 * math.pi) - math.pi
            s = min(reach, 26.0) + 7.0 * math.cos(d)
            if s > best_s:
                best_a, best_s = a, s
        az = best_a
        walk_gather()
        walk_resolve()

    def start_scan(path, select_name=None):
        """Throw the tree away and walk somewhere else. Used by `r`, and by
        ascending past the survey root — there is no tree above the root, so
        going up is a rescan rather than a navigation step."""
        nonlocal sc, stack, sel, sel_node, layout_sig, pending_select
        sc.stop_flag = True
        sc = Scanner(path, args.apparent_size, args.one_filesystem, args.exclude)
        sc.start()
        stack = [sc.root]
        sel, sel_node = 0, None
        layout_sig = None
        marked_nodes.clear()   # nodes are stale; the marked paths survive
        pending_select = select_name

    try:
        while True:
            if quitting:
                break
            now = time.time()
            sim = now - t0
            dt_frame = min(0.25, now - prev_now)
            prev_now = now
            size = shutil.get_terminal_size((100, 30))
            if size.columns != cols or size.lines != rows:
                cols, rows = max(40, size.columns), max(16, size.lines)
                ras = Raster(cols * SUBX, rows * 2)
                ov = [[None] * cols for _ in range(rows)]
                rng = random.Random(1234)
                # Stars thin out toward the horizon and are gone by two thirds
                # down. That cutoff used to be a hard edge in the placement,
                # which showed as a seam in a tall window; the limit is the
                # same, but each star also dims toward it, so it reads as the
                # fade it always looked like.
                slim = max(6, int(rows * 2 * 0.66))
                stars = [(rng.randrange(cols * SUBX), sy, rng.random(),
                          (1.0 - sy / slim) ** 0.85)
                         for sy in (rng.randrange(slim)
                                    for _ in range(int(cols * rows / 90)))]
                fit_f = None
                sys.stdout.write(CLEAR)

            cur = stack[-1]
            pxw, pxh = cols * SUBX, rows * 2

            # ---- keys ----
            for k in kb.poll():
                if k in ('q', 'Q', '\x03'):
                    raise KeyboardInterrupt
                elif k == ' ':
                    # Plan view is static by definition, so there is nothing to
                    # pause. Unpausing there used to add the orbit spin on top
                    # of the ease that holds the plan's heading square; the two
                    # fought and settled at a skewed offset, which from
                    # overhead read as the whole plan drifting off true.
                    # Nothing orbits at street level either, so the same holds.
                    if not (plan or walk):
                        paused = not paused
                        flash, flash_until = ('PAUSED' if paused else 'ORBIT',
                                              now + 0.8)
                elif k == 'LEFT':
                    if walk:
                        # Screen-right sits at bearing az - theta (xr rotates
                        # the world by -az), so az counts anticlockwise and
                        # turning left *adds*. Fixed step per press, like orbit.
                        az += WALK_TURN
                    elif az_target is None:
                        az -= 0.12
                    else:
                        az_target -= math.pi / 2   # quarter-turn the plan
                elif k == 'RIGHT':
                    if walk:
                        az -= WALK_TURN
                    elif az_target is None:
                        az += 0.12
                    else:
                        az_target += math.pi / 2
                elif k in ('UP', 'DOWN'):
                    # Tilt is inert in plan view. Dropping the elevation from
                    # here used to clear `plan` on its own and leave the held
                    # heading, the pulled-back camera and the pause behind it,
                    # which is neither a plan nor an orbit. `t` is the only way
                    # out, so every exit restores the whole set together.
                    if walk:
                        # el is the camera's own pitch, so positive is looking
                        # down: the same variable, reused rather than doubled.
                        lim = math.radians(60)
                        if k == 'UP':
                            el_target = max(-lim, el_target - 0.06)
                        else:
                            el_target = min(lim, el_target + 0.06)
                    elif plan:
                        pass
                    elif k == 'UP':
                        el_target = min(math.radians(80), el_target + 0.05)
                    else:
                        el_target = max(math.radians(5), el_target - 0.05)
                elif k in ('w', 'a', 's', 'd') and walk:
                    # Movement while walking. `w` and `s` are the window and
                    # star toggles in orbit; the mode owns the keymap while it
                    # holds, and W puts the whole set back on the way out.
                    v = WALK_V * speed
                    if k == 'w':
                        wv_f = v
                    elif k == 's':
                        wv_f = -v
                    elif k == 'a':
                        wv_s = -v
                    else:
                        wv_s = v
                elif k == 'W':
                    # The single entry and the single exit. Walk and plan view
                    # are mutually exclusive, and neither reaches into the
                    # other: W is silently inert while the plan is up.
                    if walk:
                        (el_target, az_target, dist_target, paused, zoom,
                         speed) = walk_restore
                        walk = False
                        wv_f = wv_s = 0.0
                        walk_target = None
                        # re-seed the orbit fit rather than easing up from the
                        # street focal length, which would swim into place
                        fit_f = None
                        layout_sig = None       # orbit streets back
                        flash, flash_until = 'ORBIT', now + 0.9
                    elif not plan:
                        walk_restore = (el_target, az_target, dist_target,
                                        paused, zoom, speed)
                        walk = True
                        el = el_target = 0.0
                        az_target, paused = None, True
                        zoom, speed = 1.0, 1.0
                        wv_f = wv_s = 0.0
                        fit_f = None
                        # the walk layout has to exist before the spawn looks
                        # for somewhere to stand in it
                        relayout()
                        layout_sig = None
                        walk_spawn()
                        flash, flash_until = 'STREET LEVEL', now + 1.2
                elif k == 't' and walk:
                    pass        # plan and street level are mutually exclusive
                elif k == 't':
                    plan = not plan
                    if plan:
                        # square the treemap up and flatten the perspective,
                        # otherwise it reads as a tilted, splayed city rather
                        # than a plan. Snap to the nearest quarter turn so the
                        # camera takes the short way round.
                        plan_restore = el_target
                        el_target, paused = math.pi / 2, True
                        az_target = round(az / (math.pi / 2)) * (math.pi / 2)
                        dist_target = 760.0
                        flash, flash_until = 'PLAN VIEW', now + 1.0
                    else:
                        # always come back spinning. The pause belongs to plan
                        # view, not to the orbit you left, so carrying it back
                        # out just looked like the city had frozen.
                        el_target, paused = plan_restore, False
                        az_target, dist_target = None, 210.0
                        flash, flash_until = 'ORBIT', now + 1.0
                elif k == ']':
                    zoom = min(6.0, zoom * 1.12)
                elif k == '[':
                    zoom = max(0.4, zoom / 1.12)
                elif k in ('.', '>'):
                    if walk:
                        speed = min(3.0, speed + 0.25)
                        flash, flash_until = f'PACE {speed:.2f}x', now + 0.8
                    else:
                        speed = min(8.0, speed + 0.25)
                        flash, flash_until = f'SPIN {speed:+.2f}x', now + 0.8
                elif k in (',', '<'):
                    if walk:
                        speed = max(0.4, speed - 0.25)
                        flash, flash_until = f'PACE {speed:.2f}x', now + 0.8
                    else:
                        speed = max(-8.0, speed - 0.25)  # through zero, reverse
                        flash, flash_until = f'SPIN {speed:+.2f}x', now + 0.8
                elif k in ('j', '\t'):
                    if districts:
                        set_sel((sel + 1) % len(districts))
                elif k == 'k':
                    if districts:
                        set_sel((sel - 1) % len(districts))
                elif k == 'ENTER':
                    # From the street you step into the building you are facing;
                    # from orbit you descend into the district under the cursor.
                    n = None
                    if walk:
                        if walk_target is not None:
                            n = walk_target.node
                        else:
                            flash, flash_until = 'NOTHING AHEAD', now + 0.9
                    elif districts and sel < len(districts):
                        n = districts[sel][0]
                    if n is not None:
                        if n.isfiles and not n.children:
                            populate_files(n, args.apparent_size)
                        if enterable(n) and (n.children or not n.isfiles):
                            stack.append(n)
                            sel, sel_node = 0, None
                            layout_sig = None
                            flash, flash_until = 'DESCEND ' + n.name[:20], now + 1.0
                        elif n.isfiles:
                            flash, flash_until = 'NO READABLE FILES HERE', now + 1.0
                        else:
                            flash, flash_until = 'EMPTY — nothing to show', now + 1.0
                elif k in ('BKSP', 'ESC'):
                    if len(stack) > 1:
                        child = stack.pop()
                        layout_sig = None
                        sel_node = child          # relayout re-finds its row
                        flash, flash_until = 'ASCEND', now + 0.8
                    else:
                        rp = sc.root.name
                        parent = os.path.dirname(rp.rstrip(os.sep)) or os.sep
                        if parent == rp or not os.path.isdir(parent):
                            flash, flash_until = 'AT FILESYSTEM ROOT', now + 1.0
                        else:
                            warn = ''
                            if args.one_filesystem:
                                try:
                                    if os.stat(parent).st_dev != os.stat(rp).st_dev:
                                        warn = ' (-x HIDES IT)'
                                except OSError:
                                    pass
                            start_scan(parent, os.path.basename(rp.rstrip(os.sep)))
                            shown = parent if len(parent) <= 30 else '…' + parent[-29:]
                            flash = 'SURVEY ↑ ' + shown + warn
                            flash_until = now + 2.0
                elif k == 'p':
                    pal_i = (pal_i + 1) % len(PAL_NAMES)
                    P = PALETTES[PAL_NAMES[pal_i]]
                    CATC = cat_colors(P['bld'])
                    flash, flash_until = PAL_NAMES[pal_i].upper(), now + 0.8
                elif k in '12345':
                    pal_i = int(k) - 1
                    P = PALETTES[PAL_NAMES[pal_i]]
                    CATC = cat_colors(P['bld'])
                    flash, flash_until = PAL_NAMES[pal_i].upper(), now + 0.8
                elif k == 'w':
                    windows = not windows
                elif k == 'g':
                    grid_on = not grid_on
                elif k == 'l':
                    labels = not labels
                elif k == 's':
                    stars_on = not stars_on
                elif k == 'z':
                    zen = not zen
                elif k == 'b':
                    show_big = not show_big
                elif k == 'f':
                    footprint = 'size' if footprint == 'count' else 'count'
                    layout_sig = None
                    flash, flash_until = 'FOOTPRINT = ' + footprint.upper(), now + 1.0
                elif k == 'x':
                    # Marks the building you are facing at street level, the
                    # district under the cursor from orbit. Either way it only
                    # ever *marks*: the paths print on exit, nothing is touched.
                    n = None
                    if walk:
                        if walk_target is not None:
                            n = walk_target.node
                        else:
                            flash, flash_until = 'NOTHING AHEAD', now + 0.9
                    elif districts and sel < len(districts):
                        n = districts[sel][0]
                    if n is not None:
                        p = n.path()
                        if n.isfiles:
                            # its path is the directory itself, so marking it
                            # would mark far more than the loose files
                            flash, flash_until = 'OPEN IT TO MARK FILES', now + 1.2
                            continue
                        if n in marked_nodes:
                            marked_nodes.discard(n)
                            if p in marked:
                                marked.remove(p)
                            flash, flash_until = 'UNMARKED', now + 0.8
                        else:
                            marked_nodes.add(n)
                            marked.append(p)
                            flash, flash_until = 'MARKED ' + p[-28:], now + 1.2
                elif k == 'r':
                    start_scan(cur.path())
                    flash, flash_until = 'RESCAN', now + 1.0
                elif k in ('h', '?'):
                    show_help = not show_help
                elif k == '0':
                    # The panic key, so it has to restore the *whole* camera
                    # variable set. It used to clear `plan` and leave `paused`
                    # behind, so t then 0 gave you a frozen orbit -- the same
                    # neither-one-mode-nor-the-other state the tilt keys used
                    # to produce. A partial reset is worse than none.
                    az, zoom, speed = 0.7, 1.0, args.speed
                    el_target, plan = math.radians(22), False
                    az_target, dist_target = None, 210.0
                    paused = False
                    if walk:
                        walk = False
                        wv_f = wv_s = 0.0
                        walk_target = None
                        fit_f = None
                        layout_sig = None

            # ---- layout (cheap to skip; the tree only grows) ----
            sig = (id(cur), footprint, levels, len(cur.children), cur.size >> 22)
            if sig != layout_sig or (not sc.finished and now - last_layout > 0.45):
                relayout()
                layout_sig = sig
                last_layout = now

            if not paused:
                # per second, not per frame: otherwise --fps silently doubles
                # the rotation rate and the orbit stutters when the scan is busy
                az += ROT_RATE * speed * dt_frame
            if walk:
                # A terminal reports key presses, never releases, so there is
                # no such thing as a key being "held" here. Each press instead
                # tops the velocity up and it decays with a short time
                # constant: under the ~30/s autorepeat that arrives while a key
                # really is held, the top-ups outrun the decay and the walk is
                # smooth; let go and it coasts to a stop in about half a
                # second. Decay is per second, like everything else, so --fps
                # cannot change how fast you walk.
                k_decay = math.exp(-dt_frame / WALK_TAU)
                step_f, step_s = wv_f * dt_frame, wv_s * dt_frame
                wv_f *= k_decay
                wv_s *= k_decay
                if step_f or step_s:
                    # forward is (-sa, ca), right is (ca, sa)
                    ca_, sa_ = math.cos(az), math.sin(az)
                    mx = -step_f * sa_ + step_s * ca_
                    my = step_f * ca_ + step_s * sa_
                    # Substep: the layout still leaves blocks as thin as 0.04
                    # units, and a single frame's move can be longer than that,
                    # so a one-shot test would let you walk through a wall.
                    n_sub = int(math.hypot(mx, my) / (WALK_R * 0.5)) + 1
                    for _s in range(n_sub):
                        wx += mx / n_sub
                        wy += my / n_sub
                        walk_resolve()
                    if walk_anchor is None or math.hypot(
                            wx - walk_anchor[0], wy - walk_anchor[1]) > 2.0:
                        walk_gather()
            # ease tilt, plan-view heading and camera distance, so t reads as
            # the camera craning overhead rather than cutting to a new shot
            k_ease = min(1.0, dt_frame * 5.0)
            if abs(el_target - el) > 1e-4:
                el += (el_target - el) * k_ease
            else:
                el = el_target
            if az_target is not None:
                az += (az_target - az) * k_ease
            if abs(dist_target - dist_cam) > 0.5:
                dist_cam += (dist_target - dist_cam) * k_ease
            else:
                dist_cam = dist_target

            ca, sa = math.cos(az), math.sin(az)
            ce, se = math.cos(el), math.sin(el)
            DIST = dist_cam

            # ---- auto-fit: frame the city inside the area the HUD leaves ----
            # never eat so much of a narrow terminal that the city has nowhere
            # left to go: the old flat 24-column floor did exactly that
            panel = 0 if zen else min(38, max(20, cols // 3))
            panel = min(panel, max(12, cols - 22))
            hmx = max((b.h for b in blds), default=HMAX * 0.5)
            panel_px = panel * SUBX
            avail_w = pxw - panel_px - 2

            if walk:
                # Framing the whole city is meaningless from inside it: the
                # eye is the frame. A fixed focal length from a fixed field of
                # view, and deliberately no low-pass — an eased F while you
                # turn would feel like a rubber lens.
                camX, camY, camZ = wx, wy, EYE_H
                fov = max(0.35, min(1.6, FP_FOV / zoom))
                F = (pxh / 2) / math.tan(fov / 2)
                OX = panel_px + avail_w / 2
                OY = pxh / 2
                # Make the orbit fit re-seed rather than ease up from the
                # street focal length when W hands the camera back.
                fit_f = None
                fog_near, fog_far = 12.0, 70.0
            else:
                # Fit the CYLINDER that circumscribes the plot, not the plot's
                # own corners. Fitting the corners meant the frame tracked the
                # silhouette of a rotating square, which is 41% wider corner-on
                # than edge-on: the city pulled away as a corner came round and
                # crept back in on the flats, a 17% breathing every quarter
                # turn. A circle centred on the plot is rotationally symmetric,
                # so its projection does not depend on the azimuth at all —
                # substituting th = phi - az below leaves no `az` term — and the
                # framing is therefore exactly constant as the camera orbits.
                rad = PLOT * 0.7071067811865476        # (PLOT/2) * sqrt(2)
                us, vs = [], []
                for cth, sth in FIT_RING:
                    xr, yr = rad * cth, rad * sth
                    for cz_ in (0.0, hmx):
                        zv = yr * ce - cz_ * se + DIST
                        if zv < 1.0:
                            zv = 1.0
                        # x is scaled by SUBX: a quadrant sub-cell is half as
                        # wide as it is tall, so equal world lengths need SUBX
                        # times as many horizontal pixels as vertical ones.
                        us.append(SUBX * xr / zv)
                        vs.append(-(yr * se + cz_ * ce) / zv)
                du = (max(us) - min(us)) or 1e-6
                dv = (max(vs) - min(vs)) or 1e-6
                # A constant fit has to be the safe one, so the framing now sits
                # where the corner-on framing used to — the loosest point of the
                # old swing. The margin was 0.94 to leave room for that swing;
                # with nothing left to swing, some of it can go back to the city.
                want = min(avail_w / du, (pxh - 4) / dv) * 0.97 * zoom
                ox = panel_px + avail_w / 2 - want * (min(us) + max(us)) / 2
                oy = pxh / 2 - want * (min(vs) + max(vs)) / 2
                if fit_f is None:
                    fit_f, fit_ox, fit_oy = want, ox, oy
                else:   # low-pass so rotation doesn't make the frame breathe
                    a = 0.18
                    fit_f += (want - fit_f) * a
                    fit_ox += (ox - fit_ox) * a
                    fit_oy += (oy - fit_oy) * a
                F, OX, OY = fit_f, fit_ox, fit_oy
                camX = DIST * ce * sa
                camY = -DIST * ce * ca
                camZ = DIST * se
                fog_near, fog_far = DIST - 80, DIST + 90

            # The orbit projection, kept verbatim. The free-camera form below is
            # its algebraic superset — substituting the orbit's own camera
            # position into it gives back exactly this — but "algebraically
            # identical" is not "bit-identical": subtracting the eye first
            # reassociates the sums and moves the odd result by an ULP, which is
            # enough to flip an int(ceil(...)) and shift a pixel. Orbit renders
            # are the regression gate here, so orbit keeps its own arithmetic.
            def proj_orbit(x, y, z):
                xr = x * ca + y * sa
                yr = -x * sa + y * ca
                zv = yr * ce - z * se + DIST
                if zv < 1.0:
                    zv = 1.0
                return (OX + F * SUBX * xr / zv,
                        OY - F * (yr * se + z * ce) / zv, zv)

            def view(x, y, z):
                """World -> camera space (right, up, forward), before the divide.

                All three are linear in (x, y, z), which is what lets clip_near
                interpolate a crossing point exactly.
                """
                dx, dy, dz = x - camX, y - camY, z - camZ
                xr = dx * ca + dy * sa
                yr = -dx * sa + dy * ca
                return (xr, -(yr * se + dz * ce), yr * ce - dz * se)

            def toscreen(p):
                zv = p[2]
                return (OX + F * SUBX * p[0] / zv, OY + F * p[1] / zv, zv)

            def proj_fp(x, y, z):
                # No near clamp: callers clip, and clamping would be a bug of
                # its own here — a wall 0.3 units from your face would stop
                # growing as you walked into it. The 1e-9 floor is only there so
                # a point landing exactly on the eye cannot raise; an ambient
                # animation must not be able to traceback over a raw terminal.
                p = view(x, y, z)
                zv = p[2] if abs(p[2]) > 1e-9 else 1e-9
                return (OX + F * SUBX * p[0] / zv, OY + F * p[1] / zv, zv)

            proj = proj_fp if walk else proj_orbit

            # A face whose corners all sit in front of the near plane needs no
            # clipping; one that straddles it is clipped, and then two things
            # stop being true of it. Its vertices are flung out to ~1e5 px, so
            # `fill` has to be told the real screen extent to run its gradient
            # over or the whole visible wall lands in one slice of the ramp and
            # renders flat. And its corners no longer correspond to the face's
            # own, so the window lattice cannot interpolate between them.
            def face(wpts, ca_, cb_):
                """Draw a world-space quad, clipped. Returns (screen_pts,
                was_clipped); screen_pts is None if it was clipped or dropped."""
                cp = [view(*w) for w in wpts]
                cl = clip_near(cp)
                if len(cl) < 3:
                    return None, False
                if len(cl) == len(cp):
                    pts = [toscreen(p) for p in cl]
                    ras.fill([p[:2] for p in pts], cb_, ca_)
                    return pts, False
                lo = view((wpts[0][0] + wpts[1][0]) * 0.5,
                          (wpts[0][1] + wpts[1][1]) * 0.5, wpts[0][2])
                hi = view((wpts[2][0] + wpts[3][0]) * 0.5,
                          (wpts[2][1] + wpts[3][1]) * 0.5, wpts[2][2])
                ys = [toscreen(lo)[1] if lo[2] >= ZNEAR else pxh * 4.0,
                      toscreen(hi)[1] if hi[2] >= ZNEAR else -pxh * 3.0]
                ras.fill([toscreen(p)[:2] for p in cl], cb_, ca_,
                         yref=(min(ys), max(ys)))
                return None, True

            def wline(ax, ay, az_, bx, by, bz, col):
                """A world-space segment, near-clipped then viewport-clipped."""
                s = clip_seg(view(ax, ay, az_), view(bx, by, bz))
                if s is None:
                    return
                p, q = toscreen(s[0]), toscreen(s[1])
                ras.line_c(p[0], p[1], q[0], q[1], col)

            # ---- sky ----
            sky0, sky1 = P['sky']
            bands = 14
            for i in range(bands):
                c = quant(lerp(sky0, sky1, (i / (bands - 1.0)) ** 1.6))
                ras.hband(pxh * i // bands, pxh * (i + 1) // bands, c)
            if stars_on:
                sc_ = P['star']
                for sx, sy, br, fade in stars:
                    tw = 0.65 + 0.35 * math.sin(sim * (1.0 + br * 3.0) + sx)
                    ras.point(sx, sy, quant(shade(sc_, (0.15 + br * tw * 0.9)
                                                  * fade)))

            # ---- ground ----
            g = PLOT / 2
            if walk:
                # Ground out to the horizon, or standing at the plot edge and
                # looking outward shows sky below the horizon line. The grid
                # still stops at the plot: that is where the data is.
                og = g * 8.0
                gq = clip_near([view(-og, -og, 0), view(og, -og, 0),
                                view(og, og, 0), view(-og, og, 0)])
                if len(gq) >= 3:
                    ras.fill([toscreen(p)[:2] for p in gq],
                             quant(shade(P['ground'], 1.35)),
                             quant(P['ground']), yref=(OY, pxh))
            else:
                gp = [proj(-g, -g, 0)[:2], proj(g, -g, 0)[:2],
                      proj(g, g, 0)[:2], proj(-g, g, 0)[:2]]
                ras.fill(gp, quant(shade(P['ground'], 1.35)),
                         quant(P['ground']))
            if grid_on:
                gc = quant(shade(P['grid'], 0.85))
                step = PLOT / 10
                for i in range(11):
                    t = -g + i * step
                    for pa, pb in (((t, -g), (t, g)), ((-g, t), (g, t))):
                        if walk:
                            s = clip_seg(view(pa[0], pa[1], 0),
                                         view(pb[0], pb[1], 0))
                            if s is None:
                                continue
                            a, b = toscreen(s[0]), toscreen(s[1])
                            ras.line_c(a[0], a[1], b[0], b[1], gc)
                        else:
                            a = proj(pa[0], pa[1], 0)
                            b = proj(pb[0], pb[1], 0)
                            ras.line(a[0], a[1], b[0], b[1], gc)
            # survey sweep: a searchlight raking the plot while the walk runs
            if not sc.finished:
                sweep = sim * 1.5
                bx = math.cos(sweep) * g * 1.4
                by = math.sin(sweep) * g * 1.4
                bc = quant(shade(P['beam'], 0.75))
                if walk:
                    s = clip_seg(view(0, 0, 0.2), view(bx, by, 0.2))
                    if s is not None:
                        a, b = toscreen(s[0]), toscreen(s[1])
                        ras.line_c(a[0], a[1], b[0], b[1], bc)
                else:
                    a = proj(0, 0, 0.2)
                    b = proj(bx, by, 0.2)
                    ras.line(a[0], a[1], b[0], b[1], bc)

            # ---- buildings, painter's algorithm ----
            # Back to front, exactly, by walking the layout's guillotine cuts.
            # See build_bsp: the tree is rebuilt only when the layout changes,
            # and it is exact for any camera — including one standing inside
            # the city, which is the whole reason street level is affordable.
            order = bsp_order(bsp, camX, camY) if bsp is not None else blds
            if walk:
                # What the crosshair is on. The view direction, derived the
                # same way the projection derives it, then the slab test that
                # the ray-cast harness used to prove the painter's order.
                rdx, rdy, rdz = -sa * ce, ca * ce, -se
                walk_target, bt = None, 1e30
                for b in blds:
                    t = ray_block(b, camX, camY, camZ, rdx, rdy, rdz)
                    if t is not None and t < bt:
                        walk_target, bt = b, t
                # One selection, not two: looking at a district selects it, so
                # the panel, the reticle and the beam all keep their meaning
                # and j/k still work for cycling when you would rather not walk.
                if walk_target is not None and walk_target.root is not sel_node:
                    for i, (n, _) in enumerate(districts):
                        if n is walk_target.root:
                            set_sel(i)
                            break
            pulse = 0.5 + 0.5 * math.sin(sim * 3.4)
            win_budget = 2600 if not walk else 4200
            # Painter's has no occlusion culling, so from inside the city every
            # block is drawn at close range unless it is thrown away first; the
            # cull is what makes street level cheap. The half-angle comes from
            # the projection rather than the field of view, so it stays right
            # whatever the panel leaves for the city: a point lands on the right
            # edge when F*SUBX*xr/zv = avail_w/2.
            #
            # The test is against the whole *box*, not the footprint. A footprint
            # test is only right at zero pitch: looking up, a tall block's top
            # has a larger zv than its base, so it swings toward the centre of
            # the screen, and a block whose footprint is outside the wedge can
            # still be plainly visible. Measured, that cost 64 wrongly dropped
            # blocks over 408 sample views, every one of them while looking up.
            #
            # xr, zv and the two plane functions are all linear in world
            # position, so the extreme value over an axis-aligned box is the
            # value at its centre plus the extents weighted by |coefficient| --
            # exact, and cheaper than projecting eight corners.
            if walk:
                # a few pixels of slack, so a block grazing the frame edge
                # can never be lost to rounding: overdrawing a sliver is free,
                # dropping a visible building is not
                cull_t = (avail_w + 8.0) / (2.0 * F * SUBX)
                # right plane: xr - t*zv > 0 is outside
                cgA = ca + cull_t * sa * ce
                cgB = sa - cull_t * ca * ce
                cgC = cull_t * se
                # left plane: -xr - t*zv > 0 is outside
                chA = -ca + cull_t * sa * ce
                chB = -sa - cull_t * ca * ce
                # behind: zv < ZNEAR
                czA, czB, czC = -sa * ce, ca * ce, -se
                agA, agB, agC = abs(cgA), abs(cgB), abs(cgC)
                ahA, ahB = abs(chA), abs(chB)
                azA, azB, azC = abs(czA), abs(czB), abs(czC)

            for b in order:
                x0, y0, x1, y1, h = b.x0, b.y0, b.x1, b.y1, b.h
                if walk:
                    # depth to the footprint centre, from the eye
                    mx_, my_ = (x0 + x1) * 0.5, (y0 + y1) * 0.5
                    ddx, ddy = mx_ - camX, my_ - camY
                    depth = math.sqrt(ddx * ddx + ddy * ddy)
                    # Distance alone is the wrong cull. Fog only takes a
                    # block 55% of the way to the sky, so nothing ever truly
                    # disappears into it, and a 72-unit tower just past the fog
                    # limit was still painting 1200 pixels when it got dropped.
                    # Cull on apparent size instead: measured from the nearest
                    # corner, a block under about a pixel tall cannot show.
                    nx_ = x0 if camX < x0 else (x1 if camX > x1 else camX)
                    ny_ = y0 if camY < y0 else (y1 if camY > y1 else camY)
                    dnear = math.hypot(nx_ - camX, ny_ - camY)
                    if F * h < 0.6 * dnear:
                        continue                    # sub-pixel on screen
                    # Cull only when the whole box is outside one plane. Asking
                    # instead whether any corner is *inside* would be wrong:
                    # stand close to a wide block and every corner falls outside
                    # while the block fills the screen.
                    ecx, ecy = (x0 + x1) * 0.5 - camX, (y0 + y1) * 0.5 - camY
                    ecz = h * 0.5 - camZ
                    hx, hy, hz = (x1 - x0) * 0.5, (y1 - y0) * 0.5, h * 0.5
                    if czA * ecx + czB * ecy + czC * ecz \
                            + azA * hx + azB * hy + azC * hz < ZNEAR:
                        continue                    # entirely behind the eye
                    if cgA * ecx + cgB * ecy + cgC * ecz \
                            - (agA * hx + agB * hy + agC * hz) > 0.0:
                        continue                    # entirely off to the right
                    if chA * ecx + chB * ecy + cgC * ecz \
                            - (ahA * hx + ahB * hy + agC * hz) > 0.0:
                        continue                    # entirely off to the left
                else:
                    # fog only, so the footprint centre is the right depth here
                    depth = ((-(x0 + x1) * 0.5 * sa + (y0 + y1) * 0.5 * ca) * ce
                             + DIST)
                is_sel = sel_node is not None and b.root is sel_node
                base = CATC[b.cat]
                if is_sel:
                    base = lerp(base, P['sel'], 0.45 + 0.2 * pulse)
                if marked_nodes and (b.node in marked_nodes or b.root in marked_nodes):
                    base = lerp(base, P['alert'], 0.55)
                # aerial perspective: far blocks sink toward the sky color
                fogt = (depth - fog_near) / (fog_far - fog_near)
                if fogt < 0.0:
                    fogt = 0.0
                elif fogt > 1.0:
                    fogt = 1.0
                base = lerp(base, sky1, fogt * 0.55)

                top_c = quant(shade(base, 1.0))
                if not b.node.done:
                    top_c = quant(lerp(top_c, P['beam'], 0.15 + 0.2 * pulse))

                # Which walls face the camera, tested per block against the
                # camera's actual position. A single global test is only right
                # for an orthographic camera: across a 100-unit plot at this
                # distance the view direction swings about 13 degrees, so near
                # a flip the blocks out at the edges would be given their FAR
                # wall, and its window lights would sit on the near silhouette
                # until the global test caught up.
                sxa = x1 if camX > x1 else (x0 if camX < x0 else None)
                sya = y1 if camY > y1 else (y0 if camY < y0 else None)

                # side faces first, then the roof paints over them
                if sxa is None:
                    fx_pts = fx_world = None
                    fx_clip = False
                else:
                    fa = quant(shade(base, 0.74))
                    fb = quant(shade(base, 0.44))
                    fx_world = ((sxa, y0, 0.0), (sxa, y1, 0.0),
                                (sxa, y1, h), (sxa, y0, h))
                    if walk:
                        fx_pts, fx_clip = face(fx_world, fa, fb)
                    else:
                        p0 = proj(sxa, y0, 0)
                        p1 = proj(sxa, y1, 0)
                        p2 = proj(sxa, y1, h)
                        p3 = proj(sxa, y0, h)
                        ras.fill([p0[:2], p1[:2], p2[:2], p3[:2]], fb, fa)
                        fx_pts, fx_clip = (p0, p1, p2, p3), False

                if sya is None:
                    fy_pts = fy_world = None
                    fy_clip = False
                else:
                    ga = quant(shade(base, 0.40))
                    gb = quant(shade(base, 0.20))
                    fy_world = ((x0, sya, 0.0), (x1, sya, 0.0),
                                (x1, sya, h), (x0, sya, h))
                    if walk:
                        fy_pts, fy_clip = face(fy_world, ga, gb)
                    else:
                        q0 = proj(x0, sya, 0)
                        q1 = proj(x1, sya, 0)
                        q2 = proj(x1, sya, h)
                        q3 = proj(x0, sya, h)
                        ras.fill([q0[:2], q1[:2], q2[:2], q3[:2]], gb, ga)
                        fy_pts, fy_clip = (q0, q1, q2, q3), False

                # the roof is only visible from above it; at a low tilt the
                # camera can sit below a tall block's roofline
                roof_vis = camZ > h
                ec = quant(shade(top_c, 1.5))
                cnr = quant(shade(base, 0.16))

                # Edge lighting. Without it every block melts into its
                # neighbours and the city reads as one lump; a lit roofline and
                # a dark vertical corner are what make the silhouette legible.
                # Only the roofline you can actually see, though: all four
                # edges were being stroked whatever the camera did, so from
                # below a block the two FAR rooflines were drawn straight
                # through solid wall. Faintly visible at --tilt 6, and
                # unmissable from the street, where no roof is ever visible.
                if roof_vis:
                    roof_e = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
                else:
                    # the top edges of the walls that face us, and no others
                    roof_e = []
                    if sxa is not None:
                        roof_e.append(((sxa, y0), (sxa, y1)))
                    if sya is not None:
                        roof_e.append(((x0, sya), (x1, sya)))

                if walk:
                    if roof_vis:
                        cq = clip_near([view(x0, y0, h), view(x1, y0, h),
                                        view(x1, y1, h), view(x0, y1, h)])
                        if len(cq) >= 3:
                            ras.fill([toscreen(p)[:2] for p in cq], top_c,
                                     quant(shade(top_c, 0.78)))
                        for i in range(4):
                            a_, bb_ = roof_e[i], roof_e[(i + 1) % 4]
                            wline(a_[0], a_[1], h, bb_[0], bb_[1], h, ec)
                    else:
                        for a_, bb_ in roof_e:
                            wline(a_[0], a_[1], h, bb_[0], bb_[1], h, ec)
                    if sxa is not None and sya is not None:
                        wline(sxa, sya, 0.0, sxa, sya, h, cnr)
                else:
                    t0p = proj(x0, y0, h)
                    t1p = proj(x1, y0, h)
                    t2p = proj(x1, y1, h)
                    t3p = proj(x0, y1, h)
                    if roof_vis:
                        ras.fill([t0p[:2], t1p[:2], t2p[:2], t3p[:2]], top_c,
                                 quant(shade(top_c, 0.78)))
                        roof = (t0p, t1p, t2p, t3p)
                        for i in range(4):
                            a, bb = roof[i], roof[(i + 1) % 4]
                            ras.line(a[0], a[1], bb[0], bb[1], ec)
                    else:
                        for a_, bb_ in roof_e:
                            p = proj(a_[0], a_[1], h)
                            q = proj(bb_[0], bb_[1], h)
                            ras.line(p[0], p[1], q[0], q[1], ec)
                    if sxa is not None and sya is not None:
                        e0 = proj(sxa, sya, 0)
                        e1 = proj(sxa, sya, h)
                        ras.line(e0[0], e0[1], e1[0], e1[1], cnr)

                # ---- window lights ----
                # In walk mode the lattice is the per-pixel cost that matters,
                # and past ~35 units a face is small and half fogged out
                # anyway, so it buys nothing.
                if (windows and win_budget > 0 and h > 2.0
                        and not (walk and depth > 35.0)):
                    wc = quant(lerp(P['win'], base, 0.25 + 0.25 * fogt))
                    seed = b.node.seed
                    for pts, wpts, clipped in ((fx_pts, fx_world, fx_clip),
                                               (fy_pts, fy_world, fy_clip)):
                        if pts is None and not clipped:
                            continue
                        if clipped:
                            # No screen corners to interpolate between any more,
                            # so walk the lattice in world space and project
                            # each light. Costs more per light, but only on the
                            # handful of faces you are standing right against —
                            # and those are the most visible surface in the
                            # frame, so dropping their windows is not an option.
                            w0, w1, w2, w3 = wpts
                            sw = math.hypot(w1[0] - w0[0], w1[1] - w0[1])
                            nu = min(24, max(1, int(sw / 0.20)))
                            nv = min(40, max(2, int(h / 0.34)))
                        else:
                            a0, a1, a2, a3 = pts
                            # lattice spacing comes from the face's size *on
                            # screen*, else a distant block gets a light a pixel
                            bw = math.hypot(a1[0] - a0[0], a1[1] - a0[1])
                            bh_ = math.hypot(a3[0] - a0[0], a3[1] - a0[1])
                            nu = int(bw / 3.6)
                            nv = int(bh_ / 3.0)
                            if nu < 1 or nv < 2:
                                continue
                            # a near wall fills the buffer, and 8x18 lights
                            # spread over it read as giant sparse dots
                            nu = min(nu, 24 if walk else 8)
                            nv = min(nv, 40 if walk else 18)
                        # after the sizing, not before: the budget running out
                        # has to fall in the same place it always did, or a
                        # different set of faces keeps its lights
                        if win_budget <= 0:
                            break
                        for iv in range(nv):
                            fv = (iv + 0.62) / nv
                            for iu in range(nu):
                                s = (seed * 1103515245 + iu * 7919 + iv * 104729)
                                if (s >> 6) & 3 == 0:
                                    continue
                                if ((s >> 3) ^ int(sim * 1.7 + iv)) & 63 == 0:
                                    continue
                                fu = (iu + 0.5) / nu
                                if clipped:
                                    lx = w0[0] + (w1[0] - w0[0]) * fu
                                    ly = w0[1] + (w1[1] - w0[1]) * fu
                                    p = view(lx, ly, h * fv)
                                    if p[2] < ZNEAR:
                                        continue
                                    q = toscreen(p)
                                    px_, py_ = q[0], q[1]
                                    if not (0 <= px_ < pxw and 0 <= py_ < pxh):
                                        continue
                                else:
                                    bx = a0[0] + (a1[0] - a0[0]) * fu
                                    by = a0[1] + (a1[1] - a0[1]) * fu
                                    tx = a3[0] + (a2[0] - a3[0]) * fu
                                    ty = a3[1] + (a2[1] - a3[1]) * fu
                                    px_ = bx + (tx - bx) * fv
                                    py_ = by + (ty - by) * fv
                                ras.point(int(px_), int(py_), wc)
                                win_budget -= 1

                # ---- aircraft warning beacon on the real landmarks ----
                if h > HMAX * 0.62:
                    if math.sin(sim * 2.2 + b.node.seed) > 0.55:
                        cxm, cym = (x0 + x1) * 0.5, (y0 + y1) * 0.5
                        if walk:
                            vp = view(cxm, cym, h + 0.6)
                            # a beacon behind you used to have its divisor
                            # clamped and could land back on screen as a phantom
                            bp = toscreen(vp) if vp[2] >= ZNEAR else None
                        else:
                            bp = proj(cxm, cym, h + 0.6)
                        if bp is not None:
                            ras.point(int(bp[0]), int(bp[1]), P['alert'])
                            ras.point(int(bp[0]), int(bp[1]) - 1, P['alert'])

            # ---- selection reticle ----
            if sel_node is not None and districts:
                _, (rx, ry, rw, rh) = districts[sel]
                if rw > 0 and rh > 0:
                    sc_ = quant(lerp(P['sel'], P['beam'], 0.4))
                    cw = ((rx, ry), (rx + rw, ry), (rx + rw, ry + rh),
                          (rx, ry + rh))
                    # dashed, and drawn over the blocks: it has to be findable
                    # even when the district is behind the skyline
                    for i in range(4):
                        aw, bw = cw[i], cw[(i + 1) % 4]
                        if walk:
                            s_ = clip_seg(view(aw[0], aw[1], 0.15),
                                          view(bw[0], bw[1], 0.15))
                            if s_ is None:
                                continue
                            a, b2 = toscreen(s_[0]), toscreen(s_[1])
                        else:
                            a = proj(aw[0], aw[1], 0.15)
                            b2 = proj(bw[0], bw[1], 0.15)
                        # A near-clipped vertex sits ~1e5 px out, and this loop
                        # steps one pixel at a time, so it needs a bound.
                        n = int(max(abs(b2[0] - a[0]), abs(b2[1] - a[1])))
                        if n > pxw + pxh:
                            n = pxw + pxh
                        for s in range(n + 1):
                            if (s + int(sim * 9)) % 6 < 3:
                                ras.point(int(a[0] + (b2[0] - a[0]) * s / max(n, 1)),
                                          int(a[1] + (b2[1] - a[1]) * s / max(n, 1)), sc_)
                    hh = max((b.h for b in blds if b.root is sel_node), default=1.0)
                    bc_ = quant(shade(P['beam'], 0.5 + 0.5 * pulse))
                    if walk:
                        # From the street the reticle is under the skyline, so
                        # the beam is the only thing that says where the
                        # selection is. Run it from the ground up so it is
                        # visible over the buildings between you and it.
                        wline(rx + rw / 2, ry + rh / 2, 0.0,
                              rx + rw / 2, ry + rh / 2,
                              hh + 9.0 + 2.0 * pulse, bc_)
                    else:
                        a = proj(rx + rw / 2, ry + rh / 2, hh + 1.0)
                        bm = proj(rx + rw / 2, ry + rh / 2,
                                  hh + 9.0 + 2.0 * pulse)
                        ras.line(a[0], a[1], bm[0], bm[1], bc_)

            # ---- overlay ----
            for r in range(rows):
                orow = ov[r]
                for c in range(cols):
                    orow[c] = None

            def otext(r, c, s, col, bgc=None):
                """Text inherits whatever background the cell already had.

                Without this, every string emitted SGR 49 ("default
                background"), which on a translucent terminal is *transparent*
                — so each line punched a wallpaper-coloured hole exactly its
                own width through the panel, giving ragged ribbons instead of
                a solid panel."""
                if r < 0 or r >= rows:
                    return
                orow = ov[r]
                for i, chx in enumerate(s):
                    cc = c + i
                    if 0 <= cc < cols:
                        b = bgc
                        if b is None:
                            prev = orow[cc]
                            b = prev[2] if prev is not None else None
                        orow[cc] = (chx, col, b)

            def ofill(r0, c0, hh, ww, bgc):
                for r in range(max(0, r0), min(rows, r0 + hh)):
                    orow = ov[r]
                    for c in range(max(0, c0), min(cols, c0 + ww)):
                        orow[c] = (' ', None, bgc)

            H, HD, AL = P['hud'], P['hud_dim'], P['alert']
            PN = P['panel']

            if labels and districts and not zen:
                # Biggest district first, selected always first of all, so the
                # labels that matter win the space. Each one is clamped inside
                # the viewport and skipped if it would land on one already
                # placed — unclamped centred text was running off both edges
                # and disappearing under the panel.
                lab_bg = quant(shade(P['sky'][0], 0.9))
                placed = []
                items = sorted(enumerate(districts),
                               key=lambda t: (t[0] != sel, -(t[1][1][2] * t[1][1][3])))
                shown = 0
                for i, (n, (rx, ry, rw, rh)) in items:
                    if i != sel and (shown >= 16 or
                                     rw * rh < PLOT * PLOT * 0.010):
                        continue
                    hh = max((b.h for b in blds if b.root is n), default=1.0)
                    if walk:
                        # A rooftop label is off the top of the screen for
                        # anything close, so from the street they hang at
                        # head height instead and read as signs.
                        vp = view(rx + rw / 2, ry + rh / 2, 1.0)
                        if vp[2] < ZNEAR or vp[2] > fog_far:
                            continue    # behind you, or lost in the fog
                        p = toscreen(vp)
                    else:
                        p = proj(rx + rw / 2, ry + rh / 2, hh + 2.5)
                    r = int(p[1] / 2)
                    if r < 0 or r >= rows - 1:
                        continue
                    lab = f' {n.name[:16]} {human(n.size)} '
                    w = len(lab)
                    if w > cols - panel - 2:
                        continue
                    c0 = int(p[0] / SUBX) - w // 2
                    c0 = max(panel + 1, min(c0, cols - w - 1))
                    if any(pr == r and c0 < pc1 and pc0 < c0 + w
                           for pr, pc0, pc1 in placed):
                        continue
                    placed.append((r, c0, c0 + w))
                    otext(r, c0, lab, P['sel'] if i == sel else H, lab_bg)
                    shown += 1

            if not zen:
                # ---- left panel ----
                ofill(0, 0, rows, panel, PN)
                otext(0, 0, ' DISKSCAPE'.ljust(panel), (10, 10, 10), H)
                bc = ' / '.join(n.name if n.parent else os.path.basename(n.name.rstrip('/')) or '/'
                                for n in stack)
                if len(bc) > panel - 2:
                    bc = '…' + bc[-(panel - 3):]
                otext(1, 1, bc, H)
                # column header, so the middle column isn't an unexplained gap.
                # A narrow panel drops the bar entirely rather than squeezing
                # the name out of existence.
                wide = panel >= 26
                hdr = (f'{"SIZE":>10} {"SHARE":<9} NAME' if wide
                       else f'{"SIZE":>10} NAME')
                otext(2, 1, hdr[:panel - 2].ljust(panel - 2), HD)

                with sc.lock:
                    tot = cur.size or 1
                    # built from `districts`, not from cur.children, so the row
                    # index and the selection index cannot drift apart and the
                    # loose-files district gets a row like anything else
                    rowsdata = [(n.name, n.size, n.done, n.top_cat(), n)
                                for n, _ in districts]
                    empties = sorted((c for c in cur.children
                                      if c.size <= 0 and c.files <= 0),
                                     key=lambda c: c.name)
                    rowsdata += [(c.name, 0, c.done, CAT_OTHER, c)
                                 for c in empties]

                # last row belongs to the status bar; four above it are the
                # separator and the three telemetry lines
                avail = rows - 16 if show_big else rows - 9
                start = max(0, min(sel - avail // 2, len(rowsdata) - avail))
                r = 3
                for i in range(start, min(len(rowsdata), start + avail)):
                    nm, szv, dn, ct, nd = rowsdata[i]
                    pct = szv / tot
                    is_s = i == sel
                    # colour means one thing only: file-type category. It used
                    # to fall back to a flat dim below 2%, so the same channel
                    # silently switched from "what kind" to "how small".
                    tint = CATC[ct]
                    col = P['sel'] if is_s else \
                        quant(lerp(HD, tint, min(1.0, 0.32 + pct * 9.0)))
                    mk = '≡' if nd.isfiles else \
                        ('×' if nd in marked_nodes else (' ' if dn else '·'))
                    rbg = quant(shade(H, 0.22)) if is_s else PN
                    if wide:
                        line = f'{mk}{human(szv):>9} {" " * BAR_W} {nm}'
                    else:
                        line = f'{mk}{human(szv):>9} {nm}'
                    otext(r, 1, line[:panel - 2].ljust(panel - 2), col, rbg)
                    # the bar keeps the category colour even on the selected
                    # row, where drawing it in the selection colour made it
                    # read as a blank highlighted box
                    if wide:
                        otext(r, 12, bar_str(pct)[:panel - 13], tint, rbg)
                    r += 1

                # ---- bottom of panel: scan telemetry ----
                br = rows - 4
                otext(br - 1, 1, '─' * (panel - 2), HD)
                if sc.finished:
                    st = f'SURVEY COMPLETE {fmt_dur(sc.elapsed)}'
                    stc = H
                else:
                    spin = '|/-\\'[int(sim * 8) % 4]
                    st = f'{spin} SCANNING {fmt_dur(time.time() - sc.started_at)}'
                    stc = P['beam']
                otext(br, 1, st[:panel - 2], stc)
                otext(br + 1, 1, f'{commas(sc.files)} files  {human(sc.bytes)}'[:panel - 2], HD)
                errs = f'{sc.errors} skipped' if sc.errors else ''
                otext(br + 2, 1, (f'{commas(sc.dirs)} dirs  {errs}')[:panel - 2], HD)

                # ---- biggest files ----
                if show_big:
                    bh = 12
                    r0 = rows - bh - 1
                    bw = min(cols - panel - 2, 58)
                    c0 = cols - bw - 1
                    ofill(r0, c0, bh, bw, PN)
                    otext(r0, c0, ' LARGEST FILES '.ljust(bw), (10, 10, 10), H)
                    with sc.lock:
                        big = sorted(sc.biggest, reverse=True)[:bh - 1]
                    for i, (szv, p) in enumerate(big):
                        p = p[len(root_path):] or '/'
                        if len(p) > bw - 13:
                            p = '…' + p[-(bw - 14):]
                        otext(r0 + 1 + i, c0 + 1, f'{human(szv):>9}  {p}', HD)

                # ---- status line ----
                # these sit over the 3D scene, so they carry their own backing
                # rather than resetting to the terminal's (translucent) default
                bar_bg = quant(shade(P['sky'][0], 0.85))
                ofill(rows - 1, panel, 1, cols - panel, bar_bg)
                if cur.isfiles:
                    stat_l = f'{human(cur.size)} · {commas(cur.files)} files'
                else:
                    nsub = len(cur.children)
                    stat_l = (f'{human(cur.size)} · {commas(cur.files)} files · '
                              f'{commas(nsub)} subdir{"" if nsub == 1 else "s"}')
                otext(rows - 1, panel + 2, stat_l, H)
                if walk:
                    keys = ('wasd move  ←→ turn  ↑↓ look  ENTER enter  '
                            'x mark  W orbit')
                else:
                    keys = 'j/k select  ENTER descend  BKSP up  h help  q quit'
                if cols - panel - len(stat_l) - 8 > len(keys):
                    otext(rows - 1, cols - len(keys) - 1, keys, HD)
                fpsl = f' {fps_avg:4.1f}fps  {len(blds)} blocks  {footprint} '
                otext(0, cols - len(fpsl), fpsl, HD, bar_bg)
                if marked:
                    m = f' {len(marked)} MARKED '
                    otext(0, cols - len(fpsl) - len(m), m, AL, bar_bg)

            if walk and not zen:
                # ---- compass ----
                # A treemap has no landmarks and every alley looks like every
                # other one, so without a heading the mode is a maze. The
                # marks are world directions; the tick is the selection.
                cw0, cwn = panel + 1, cols - panel - 2
                if cwn > 20:
                    bar_bg2 = quant(shade(P['sky'][0], 0.8))
                    ofill(0, cw0, 1, cwn, bar_bg2)
                    span = 2.4                      # radians across the strip
                    # Offset to the right of the crosshair is az - bearing, not
                    # the other way round: xr rotates the world by -az, so a
                    # thing on your screen-right has the *smaller* bearing.
                    # The labels are bearings too, hence E at -pi/2, which is
                    # world +x -- the direction plan view draws to the right.
                    for lab, ang in (('N', 0.0), ('E', -math.pi / 2),
                                     ('S', math.pi), ('W', math.pi / 2)):
                        d = (az - ang + math.pi) % (2 * math.pi) - math.pi
                        if abs(d) < span / 2:
                            c = cw0 + int((d / span + 0.5) * cwn)
                            if cw0 <= c < cw0 + cwn:
                                otext(0, c, lab, H, bar_bg2)
                    if sel_node is not None and districts:
                        _, (rx, ry, rw, rh) = districts[sel]
                        bd = math.atan2(-(rx + rw / 2 - camX),
                                        ry + rh / 2 - camY)
                        d = (az - bd + math.pi) % (2 * math.pi) - math.pi
                        if abs(d) < span / 2:
                            c = cw0 + int((d / span + 0.5) * cwn)
                            if cw0 <= c < cw0 + cwn:
                                otext(0, c, '▼', P['sel'], bar_bg2)

                # ---- crosshair and what it is on ----
                ccol, crow = (panel + cols) // 2, rows // 2
                otext(crow, ccol, '+', H)
                if walk_target is not None:
                    n = walk_target.node
                    card = [f' {n.name[:24]} ',
                            f' {human(n.size)} · {commas(n.files)} files ']
                    cwid = max(len(s) for s in card)
                    cr = min(rows - 4, crow + 2)
                    cc = max(panel + 1, min(ccol - cwid // 2, cols - cwid - 1))
                    ofill(cr, cc, len(card), cwid, PN)
                    for i, s in enumerate(card):
                        otext(cr + i, cc, s.ljust(cwid),
                              H if i == 0 else HD, PN)

            if flash and now < flash_until:
                msg = f'[ {flash} ]'
                otext(rows - 3, max(panel + 2, (cols + panel - len(msg)) // 2), msg,
                      H, quant(shade(P['sky'][0], 0.85)))

            if show_help:
                # the legend lives here because the colour coding is otherwise
                # undiscoverable — there was no way to learn what a tint meant
                hl = WALK_HELP_LINES if walk else HELP_LINES
                body = list(hl) + ['', 'COLOUR = FILE TYPE'] + \
                    [f'  {n}' for n in CAT_NAMES]
                base = len(hl) + 2
                # wrap to two columns rather than clipping: on a short terminal
                # the legend is exactly what would have been cut off
                ncol = 1
                if len(body) + 2 > rows and cols - panel >= 52:
                    ncol = 2
                per = -(-len(body) // ncol)
                bw, bh = 25 * ncol + 1, min(rows, per + 2)
                r0 = max(0, (rows - bh) // 2)
                c0 = max(0, (cols + panel - bw) // 2)
                ofill(r0, c0, bh, bw, PN)
                otext(r0, c0, '┌' + '─' * (bw - 2) + '┐', HD, PN)
                otext(r0, c0 + 2, '┤ CONTROLS ├', H, PN)
                for ci in range(ncol):
                    for i in range(per):
                        idx = ci * per + i
                        if idx >= len(body) or 1 + i >= bh - 1:
                            break
                        col = CATC[idx - base] if base <= idx < base + NCAT else H
                        otext(r0 + 1 + i, c0 + 2 + ci * 25,
                              body[idx][:23], col, PN)
                for i in range(1, bh - 1):
                    otext(r0 + i, c0, '│', HD, PN)
                    otext(r0 + i, c0 + bw - 1, '│', HD, PN)
                otext(r0 + bh - 1, c0, '└' + '─' * (bw - 2) + '┘', HD, PN)

            # ---- paint ----
            px = ras.px
            out = [HOME]
            for r in range(rows):
                orow = ov[r]
                ptop = px[r * 2]
                pbot = px[r * 2 + 1]
                line = []
                cfg = cbg = -1
                for c in range(cols):
                    o = orow[c]
                    if o is not None:
                        chx, f_, b_ = o
                        if f_ is None:
                            t = ptop[c * SUBX]
                            f_ = t if t is not None else (200, 200, 200)
                    elif SUBX == 1:
                        t = ptop[c]
                        b_ = pbot[c]
                        if t == b_:
                            chx, f_ = '█', t
                            b_ = None
                        else:
                            chx, f_ = '▀', t
                    else:
                        x2 = c + c
                        pa = ptop[x2]
                        pb = ptop[x2 + 1]
                        pc = pbot[x2]
                        pd = pbot[x2 + 1]
                        if pa == pb == pc == pd:
                            # overwhelmingly the common case (sky, flat faces),
                            # so it gets the cheapest possible test
                            chx, f_, b_ = '█', pa, None
                        else:
                            la = pa[0] + pa[1] + pa[2]
                            lb = pb[0] + pb[1] + pb[2]
                            lc = pc[0] + pc[1] + pc[2]
                            ld = pd[0] + pd[1] + pd[2]
                            hi = lo = la
                            f_ = b_ = pa
                            if lb > hi:
                                hi, f_ = lb, pb
                            if lb < lo:
                                lo, b_ = lb, pb
                            if lc > hi:
                                hi, f_ = lc, pc
                            if lc < lo:
                                lo, b_ = lc, pc
                            if ld > hi:
                                hi, f_ = ld, pd
                            if ld < lo:
                                lo, b_ = ld, pd
                            if hi == lo:
                                chx, f_, b_ = '█', pa, None
                            else:
                                # split the four sub-cells about the midpoint
                                # of their luminance range; brightest becomes
                                # the foreground, darkest the background
                                mid = (hi + lo) * 0.5
                                m = 1 if la >= mid else 0
                                if lb >= mid:
                                    m |= 2
                                if lc >= mid:
                                    m |= 4
                                if ld >= mid:
                                    m |= 8
                                chx = QUAD[m]
                    if f_ != cfg:
                        line.append(fg(f_) if f_ is not None else FG_DEF)
                        cfg = f_
                    if b_ != cbg:
                        line.append(bg(b_) if b_ is not None else BG_DEF)
                        cbg = b_
                    line.append(chx)
                line.append(RESET)
                out.append(''.join(line))
                if r < rows - 1:
                    out.append('\n')
            sys.stdout.write(''.join(out))
            sys.stdout.flush()

            frame += 1
            dt = time.time() - now
            fps_avg += (1.0 / max(dt, 1e-3) - fps_avg) * 0.1
            time.sleep(max(0.0, 1.0 / args.fps - dt))
    except (KeyboardInterrupt, BrokenPipeError):
        pass
    finally:
        sc.stop_flag = True
        cleanup()
        try:
            root = sc.root
            print(f'{root.name}  {human(root.size)}  {commas(root.files)} files  '
                  f'{commas(root.subdirs)} dirs'
                  f'{"" if sc.finished else "  (partial)"}')
            if marked:
                print(f'\n{len(marked)} marked:')
                for p in marked:
                    print(p)
        except (BrokenPipeError, KeyboardInterrupt):
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
