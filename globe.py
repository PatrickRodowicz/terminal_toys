#!/usr/bin/env python3
"""
 ORBITAL SURVEILLANCE GRID // dot-matrix earth
 ---------------------------------------------
 A spinning dot-matrix globe for the terminal. Real Natural Earth coastlines,
 day/night terminator, city lights, orbiting satellites, live trace arcs,
 HUD telemetry. Everything is live-tunable from the keyboard.

 Usage:
   python3 globe.py                     spin forever, fit to terminal
   python3 globe.py --palette amber     matrix | amber | ice | plasma | blood
   python3 globe.py --speed 0.4         rotation rate (default 1.0)
   python3 globe.py --tilt 15           camera elevation, degrees (default 15)
   python3 globe.py --fps 60            frame rate (default 30)
   python3 globe.py --zen               globe only, no HUD/traces/glitch
   python3 globe.py --dense             finer dot grid
   python3 globe.py --map               print the land bitmap and exit
   (also --no-hud --no-stars --no-traces --no-night --no-glitch --no-sats)

 Live controls (press h in-flight for the full list):
   SPACE pause   q quit      h help     0 reset
   <- -> speed   ^ v tilt    r reverse  p palette (1-5 direct)
   n night   s stars   t traces   o orbits   g glitch   u hud
   d density   z zen   l labels
"""
import sys, os, math, time, shutil, argparse, signal, random, zlib, base64, select

# --- embedded land bitmap -------------------------------------------------
# Natural Earth 110m land polygons, scanline-rasterized to a MAP_W x MAP_H
# equirectangular bit mask, zlib+base64. ~6 KB, no runtime dependencies.
MAP_W, MAP_H = 720, 360
LAND_B64 = (
    "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"
    "tat21f4X7T8Rd9Rp"
)
_LAND = zlib.decompress(base64.b64decode(LAND_B64))

TWO_PI = math.pi * 2.0

# Sun fixed in view space: the terminator stays put and the world turns
# through it. Mostly from the left, slightly toward the viewer.
SUN = (-0.78, 0.16, 0.60)
SUN = tuple(c / math.sqrt(sum(k * k for k in SUN)) for c in SUN)


def is_land(x, y, z):
    """Unit vector on the sphere -> True if it lands on a continent."""
    lat = math.asin(max(-1.0, min(1.0, z)))
    lon = math.atan2(y, x)
    i = int((lon + math.pi) / TWO_PI * MAP_W)
    j = int((math.pi / 2 - lat) / math.pi * MAP_H)
    if i >= MAP_W:
        i = MAP_W - 1
    if j >= MAP_H:
        j = MAP_H - 1
    idx = j * MAP_W + i
    return bool(_LAND[idx >> 3] & (0x80 >> (idx & 7)))


def print_map(w=100, h=40):
    for jj in range(h):
        line = []
        for ii in range(w):
            lat = math.radians(90 - (jj + 0.5) * 180 / h)
            lon = math.radians(-180 + (ii + 0.5) * 360 / w)
            cl = math.cos(lat)
            line.append('#' if is_land(cl * math.cos(lon),
                                       cl * math.sin(lon),
                                       math.sin(lat)) else ' ')
        print(''.join(line))


# --- palettes -------------------------------------------------------------
# day/night are deliberately split in *hue* as well as brightness, so the
# terminator reads instantly: warm+bright lit side, cool+dim dark side.
PALETTES = {
    'matrix': {
        'ocean_day':   ((0, 150, 95), (80, 255, 175)),
        'ocean_night': ((0, 38, 62), (0, 66, 104)),
        'land_day':    ((150, 255, 150), (230, 255, 230)),
        'land_night':  ((22, 78, 96), (40, 118, 140)),
        'twilight':    (255, 190, 80),
        'lights':      (255, 225, 120),
        'star':        (95, 140, 110),
        'arc':         (120, 255, 235),
        'packet':      (225, 255, 255),
        'city':        (255, 250, 190),
        'sat':         (150, 255, 255),
        'orbit':       (30, 105, 95),
        'hud':         (60, 235, 150),
        'hud_dim':     (25, 130, 85),
        'alert':       (255, 120, 90),
    },
    'amber': {
        'ocean_day':   ((150, 80, 0), (255, 165, 40)),
        'ocean_night': ((44, 24, 48), (78, 40, 78)),
        'land_day':    ((255, 190, 60), (255, 245, 195)),
        'land_night':  ((92, 46, 74), (132, 70, 100)),
        'twilight':    (255, 120, 60),
        'lights':      (255, 245, 200),
        'star':        (140, 105, 55),
        'arc':         (255, 205, 90),
        'packet':      (255, 255, 225),
        'city':        (255, 250, 210),
        'sat':         (255, 230, 150),
        'orbit':       (110, 62, 20),
        'hud':         (255, 176, 44),
        'hud_dim':     (140, 92, 20),
        'alert':       (255, 95, 60),
    },
    'ice': {
        'ocean_day':   ((0, 120, 180), (90, 210, 255)),
        'ocean_night': ((16, 22, 66), (30, 44, 108)),
        'land_day':    ((170, 240, 255), (240, 253, 255)),
        'land_night':  ((44, 56, 122), (72, 92, 160)),
        'twilight':    (255, 170, 200),
        'lights':      (255, 240, 190),
        'star':        (120, 150, 180),
        'arc':         (150, 235, 255),
        'packet':      (255, 255, 255),
        'city':        (235, 250, 255),
        'sat':         (215, 245, 255),
        'orbit':       (40, 80, 120),
        'hud':         (90, 210, 255),
        'hud_dim':     (40, 110, 150),
        'alert':       (255, 130, 130),
    },
    'plasma': {
        'ocean_day':   ((120, 30, 160), (215, 95, 245)),
        'ocean_night': ((26, 20, 62), (48, 34, 100)),
        'land_day':    ((255, 150, 240), (255, 235, 255)),
        'land_night':  ((70, 44, 118), (104, 66, 156)),
        'twilight':    (120, 245, 255),
        'lights':      (255, 240, 170),
        'star':        (140, 105, 165),
        'arc':         (120, 245, 255),
        'packet':      (255, 255, 255),
        'city':        (255, 235, 255),
        'sat':         (190, 255, 255),
        'orbit':       (78, 40, 105),
        'hud':         (230, 110, 240),
        'hud_dim':     (120, 55, 130),
        'alert':       (255, 210, 90),
    },
    'blood': {
        'ocean_day':   ((150, 25, 30), (255, 80, 70)),
        'ocean_night': ((40, 18, 24), (72, 32, 44)),
        'land_day':    ((255, 130, 100), (255, 225, 205)),
        'land_night':  ((86, 34, 46), (124, 52, 66)),
        'twilight':    (255, 200, 90),
        'lights':      (255, 225, 150),
        'star':        (140, 80, 80),
        'arc':         (255, 170, 90),
        'packet':      (255, 245, 220),
        'city':        (255, 235, 200),
        'sat':         (255, 210, 170),
        'orbit':       (95, 34, 34),
        'hud':         (255, 70, 65),
        'hud_dim':     (135, 35, 33),
        'alert':       (255, 200, 60),
    },
}
PAL_NAMES = ['matrix', 'amber', 'ice', 'plasma', 'blood']

# --- world cities (lat, lon, label) ---------------------------------------
CITIES = [
    (35.68, 139.69, 'TOKYO'),     (40.71, -74.01, 'NEW YORK'),
    (51.51, -0.13, 'LONDON'),     (48.86, 2.35, 'PARIS'),
    (55.76, 37.62, 'MOSCOW'),     (39.90, 116.41, 'BEIJING'),
    (1.35, 103.82, 'SINGAPORE'),  (-33.87, 151.21, 'SYDNEY'),
    (-23.55, -46.63, 'SAO PAULO'), (19.43, -99.13, 'MEXICO CITY'),
    (28.61, 77.21, 'NEW DELHI'),  (30.04, 31.24, 'CAIRO'),
    (-26.20, 28.05, 'JOHANNESBURG'), (37.77, -122.42, 'SAN FRANCISCO'),
    (25.20, 55.27, 'DUBAI'),      (52.52, 13.40, 'BERLIN'),
    (-34.60, -58.38, 'BUENOS AIRES'), (37.57, 126.98, 'SEOUL'),
    (41.01, 28.98, 'ISTANBUL'),   (6.52, 3.38, 'LAGOS'),
    (64.15, -21.94, 'REYKJAVIK'), (-36.85, 174.76, 'AUCKLAND'),
    (13.76, 100.50, 'BANGKOK'),   (59.33, 18.07, 'STOCKHOLM'),
    (43.65, -79.38, 'TORONTO'),   (-12.05, -77.04, 'LIMA'),
    (22.32, 114.17, 'HONG KONG'), (-6.21, 106.85, 'JAKARTA'),
    (60.17, 24.94, 'HELSINKI'),   (33.69, 73.05, 'ISLAMABAD'),
]

# --- satellites: (inclination, RAAN, orbit radius, period s, phase, name) --
SATS = [
    (51.6, 15, 1.14, 22.0, 0.00, 'ISS'),
    (98.2, 130, 1.28, 30.0, 0.35, 'POLAR-1'),
    (63.4, 250, 1.46, 41.0, 0.70, 'MOLNIYA'),
]


def geo_vec(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    c = math.cos(la)
    return (c * math.cos(lo), c * math.sin(lo), math.sin(la))


CITY_VECS = [(geo_vec(a, b), n) for a, b, n in CITIES]

# --- ANSI -----------------------------------------------------------------
ESC = '\033['
HIDE, SHOW = ESC + '?25l', ESC + '?25h'
HOME, CLEAR = ESC + 'H', ESC + '2J'
RESET = ESC + '0m'

_SGR = {}


def sgr(rgb):
    s = _SGR.get(rgb)
    if s is None:
        s = f'{ESC}38;2;{rgb[0]};{rgb[1]};{rgb[2]}m'
        _SGR[rgb] = s
    return s


def lerp(c0, c1, t):
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    return (int(c0[0] + (c1[0] - c0[0]) * t),
            int(c0[1] + (c1[1] - c0[1]) * t),
            int(c0[2] + (c1[2] - c0[2]) * t))


def quant(rgb, step=12):
    """Snap colors to a coarse ladder so the SGR cache stays small."""
    return (rgb[0] // step * step, rgb[1] // step * step, rgb[2] // step * step)


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
                out.append(arrows.get(s[i + 2:i + 3], 'ESC'))
                i += 3
            else:
                out.append(s[i])
                i += 1
        return out


# --- trace arcs -----------------------------------------------------------
def slerp(a, b, t):
    d = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))
    om = math.acos(d)
    if om < 1e-6:
        return a
    s = math.sin(om)
    w0, w1 = math.sin((1 - t) * om) / s, math.sin(t * om) / s
    return (a[0] * w0 + b[0] * w1, a[1] * w0 + b[1] * w1, a[2] * w0 + b[2] * w1)


class Trace:
    """An animated great-circle link between two cities."""
    __slots__ = ('a', 'b', 'src', 'dst', 'born', 'dur', 'lift', 'pts', 'ip')

    def __init__(self, now, rng):
        (self.a, self.src), (self.b, self.dst) = rng.sample(CITY_VECS, 2)
        self.born = now
        self.dur = rng.uniform(3.4, 6.5)
        d = math.acos(max(-1.0, min(1.0, sum(
            self.a[i] * self.b[i] for i in range(3)))))
        self.lift = 0.05 + 0.16 * (d / math.pi)
        n = max(24, int(d * 44))
        self.pts = []
        for k in range(n + 1):
            t = k / n
            p = slerp(self.a, self.b, t)
            m = math.sqrt(p[0] ** 2 + p[1] ** 2 + p[2] ** 2)
            r = 1.0 + self.lift * math.sin(math.pi * t)
            s = r / m
            self.pts.append((p[0] * s, p[1] * s, p[2] * s))
        self.ip = '%d.%d.%d.%d' % (rng.choice((10, 172, 192, 198, 203)),
                                   rng.randrange(256), rng.randrange(256),
                                   rng.randrange(1, 255))

    def phase(self, now):
        """0..1 draw progress, or None once finished."""
        p = (now - self.born) / self.dur
        return None if p >= 1.0 else p


# --- HUD ------------------------------------------------------------------
BANNER = 'ORBITAL SURVEILLANCE GRID'
LOG_VERBS = ['TRACE', 'PROBE', 'SYNC', 'RELAY', 'HANDSHAKE', 'UPLINK',
             'BEACON', 'DECRYPT', 'ROUTE', 'PING']
LOG_TAIL = ['OK', 'OK', 'OK', 'ACK', '200', 'LOCKED', 'RETRY', 'TIMEOUT']

HELP_LINES = [
    'SPACE  pause / resume',
    'q      quit',
    '<- ->  rotation speed',
    '^  v   camera tilt',
    'r      reverse spin',
    '0      reset defaults',
    'p      cycle palette',
    '1-5    palette direct',
    'n      day/night',
    's      starfield',
    't      trace arcs',
    'o      satellites',
    'g      glitch bursts',
    'u      HUD panel',
    'l      city labels',
    'd      dot density',
    'z      zen mode',
    'h / ?  close help',
]


class Hud:
    def __init__(self, rng):
        self.log = []
        self.rng = rng
        self.pkts = 0
        self.next_log = 0.0

    def tick(self, now, traces):
        self.pkts += self.rng.randrange(6, 190)
        if now >= self.next_log:
            self.next_log = now + self.rng.uniform(0.35, 1.4)
            v = self.rng.choice(LOG_VERBS)
            tail = self.rng.choice(LOG_TAIL)
            if traces and self.rng.random() < 0.65:
                t = self.rng.choice(traces)
                line = f'{v} {t.src[:11]}>{t.dst[:11]}'
            else:
                line = f'{v} {self.rng.choice(CITIES)[2][:11]}'
            self.log.append((line, tail))
            if len(self.log) > 40:
                self.log.pop(0)


def fmt_dur(s):
    s = int(s)
    return f'{s // 3600:02d}:{(s // 60) % 60:02d}:{s % 60:02d}'


# --- main -----------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('--speed', type=float, default=1.0)
    ap.add_argument('--tilt', type=float, default=15.0)
    ap.add_argument('--fps', type=float, default=30.0)
    ap.add_argument('--palette', default='matrix', choices=sorted(PALETTES))
    ap.add_argument('--no-hud', action='store_true')
    ap.add_argument('--no-stars', action='store_true')
    ap.add_argument('--no-traces', action='store_true')
    ap.add_argument('--no-night', action='store_true')
    ap.add_argument('--no-glitch', action='store_true')
    ap.add_argument('--no-sats', action='store_true')
    ap.add_argument('--no-labels', action='store_true')
    ap.add_argument('--zen', action='store_true')
    ap.add_argument('--dense', action='store_true')
    ap.add_argument('--map', action='store_true')
    ap.add_argument('-h', '--help', action='store_true')
    args, _ = ap.parse_known_args()

    if args.help:
        print(__doc__)
        return
    if args.map:
        print_map()
        return
    if args.zen:
        args.no_hud = args.no_traces = args.no_glitch = True

    defaults = dict(speed=args.speed, tilt=args.tilt, palette=args.palette)
    rng = random.Random()
    dense = args.dense
    cells, cell_key = [], None
    hud = Hud(rng)
    kbd = Keyboard()

    def cleanup(*_):
        kbd.restore()
        sys.stdout.write(SHOW + RESET + CLEAR + HOME)
        sys.stdout.flush()
        os._exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    sys.stdout.write(HIDE + CLEAR)
    t0 = time.time()
    sim = 0.0                 # simulated clock: freezes while paused
    ang = 0.0
    paused = False
    show_help = False
    last_size = (0, 0)
    stars = []
    traces = []
    next_trace = 0.0
    glitch_until = -1.0
    next_glitch = rng.uniform(6, 16)
    frame = 0
    fps_est = args.fps
    last_t = t0
    flash = ''
    flash_until = 0.0

    def note(msg):
        nonlocal flash, flash_until
        flash, flash_until = msg, time.time() + 1.3

    try:
        while True:
            now = time.time()
            dt = now - last_t
            last_t = now
            if frame and dt > 1e-6:
                fps_est = fps_est * 0.9 + min(1.0 / dt, 999.0) * 0.1
            if not paused:
                sim += dt

            # ---- input ----
            for k in kbd.poll():
                if k in ('q', 'Q', '\x03'):
                    cleanup()
                elif k == ' ':
                    paused = not paused
                    note('PAUSED' if paused else 'RESUMED')
                elif k in ('h', 'H', '?'):
                    show_help = not show_help
                elif k == 'LEFT':
                    args.speed = round(max(-4.0, args.speed - 0.1), 2)
                    note(f'SPEED {args.speed:+.2f}')
                elif k == 'RIGHT':
                    args.speed = round(min(4.0, args.speed + 0.1), 2)
                    note(f'SPEED {args.speed:+.2f}')
                elif k == 'UP':
                    args.tilt = round(min(89.0, args.tilt + 3.0), 1)
                    note(f'TILT {args.tilt:+.0f}')
                elif k == 'DOWN':
                    args.tilt = round(max(-89.0, args.tilt - 3.0), 1)
                    note(f'TILT {args.tilt:+.0f}')
                elif k in ('r', 'R'):
                    args.speed = -args.speed
                    note('REVERSE')
                elif k == '0':
                    args.speed = defaults['speed']
                    args.tilt = defaults['tilt']
                    args.palette = defaults['palette']
                    note('RESET')
                elif k in ('p', 'P'):
                    i = PAL_NAMES.index(args.palette)
                    args.palette = PAL_NAMES[(i + 1) % len(PAL_NAMES)]
                    note(args.palette.upper())
                elif k in '12345':
                    args.palette = PAL_NAMES[int(k) - 1]
                    note(args.palette.upper())
                elif k in ('n', 'N'):
                    args.no_night = not args.no_night
                    note('NIGHT ' + ('OFF' if args.no_night else 'ON'))
                elif k in ('s', 'S'):
                    args.no_stars = not args.no_stars
                    note('STARS ' + ('OFF' if args.no_stars else 'ON'))
                elif k in ('t', 'T'):
                    args.no_traces = not args.no_traces
                    note('TRACES ' + ('OFF' if args.no_traces else 'ON'))
                elif k in ('o', 'O'):
                    args.no_sats = not args.no_sats
                    note('ORBITS ' + ('OFF' if args.no_sats else 'ON'))
                elif k in ('g', 'G'):
                    args.no_glitch = not args.no_glitch
                    note('GLITCH ' + ('OFF' if args.no_glitch else 'ON'))
                elif k in ('u', 'U'):
                    args.no_hud = not args.no_hud
                    note('HUD ' + ('OFF' if args.no_hud else 'ON'))
                    sys.stdout.write(CLEAR)
                elif k in ('l', 'L'):
                    args.no_labels = not args.no_labels
                    note('LABELS ' + ('OFF' if args.no_labels else 'ON'))
                elif k in ('d', 'D'):
                    dense = not dense
                    note('DENSITY ' + ('HIGH' if dense else 'NORMAL'))
                elif k in ('z', 'Z'):
                    on = not (args.no_hud and args.no_traces and args.no_glitch)
                    args.no_hud = args.no_traces = args.no_glitch = on
                    args.no_sats = on
                    note('ZEN ' + ('ON' if on else 'OFF'))
                    sys.stdout.write(CLEAR)

            P = PALETTES[args.palette]
            tilt = math.radians(args.tilt)
            ct, st = math.cos(tilt), math.sin(tilt)

            cols, rows = shutil.get_terminal_size((80, 24))
            cols = max(cols, 20)
            rows = max(rows, 10)
            if (cols, rows) != last_size:
                sys.stdout.write(CLEAR)
                last_size = (cols, rows)
                stars = []

            panel = 30 if (not args.no_hud and cols >= 104) else 0
            top = 0 if args.no_hud else 2
            bot = rows - (0 if args.no_hud else 2)
            area_w = cols - panel
            area_h = max(bot - top, 4)
            R = max(3.0, min((area_w - 6) / 2.0, (area_h - 2)))
            cx, cy = area_w / 2.0, top + area_h / 2.0

            # Only the spin changes frame to frame; anything else that moves
            # the disc invalidates the baked sample plan.
            key = (top, bot, area_w, R, cx, cy, args.tilt, dense)
            if key != cell_key:
                cell_key = key
                cells = build_cells(top, bot, area_w, R, cx, cy, ct, st,
                                    4 if dense else 3)

            if not stars and not args.no_stars:
                for _ in range(int(cols * rows * 0.035)):
                    stars.append((rng.randrange(cols), rng.randrange(rows),
                                  rng.random(), rng.uniform(0.4, 2.2)))

            # ---- framebuffer ----
            ch = [[' '] * cols for _ in range(rows)]
            co = [[None] * cols for _ in range(rows)]

            def put(r, c, glyph, color):
                if 0 <= r < rows and 0 <= c < cols:
                    ch[r][c] = glyph
                    co[r][c] = color

            def text(r, c, s, color):
                for k, g in enumerate(s):
                    put(r, c + k, g, color)

            ca, sa = math.cos(ang), math.sin(ang)

            def project(x, y, z, spin=True):
                """World -> (screen col, screen row, depth). Pole is vertical."""
                # screen x is negated so (right, up, toward-viewer) is a
                # right-handed basis -- otherwise the globe renders mirrored.
                if spin:
                    rx = y * sa - x * ca
                    ry = x * sa + y * ca
                else:
                    rx, ry = -x, y
                ty = z * ct - ry * st
                tz = z * st + ry * ct
                return rx, ty, tz

            def occluded(rx, ty, tz):
                if tz <= 0:
                    return True
                rho2 = rx * rx + ty * ty
                return rho2 < 1.0 and tz < math.sqrt(1.0 - rho2) - 0.004

            # ---- stars ----
            if not args.no_stars:
                for sx, sy, ph, sp in stars:
                    if sy < top or sy >= bot or (panel and sx >= cols - panel):
                        continue
                    dx = (sx - cx) / R
                    dy = (sy - cy) / (R * 0.5)
                    if dx * dx + dy * dy < 1.06:
                        continue
                    tw = 0.5 + 0.5 * math.sin(sim * sp + ph * TWO_PI)
                    if tw < 0.22:
                        continue
                    put(sy, sx, '.' if tw < 0.62 else '*',
                        quant(lerp((0, 0, 0), P['star'], 0.35 + 0.65 * tw)))

            # ---- globe ----
            # Spinning only shifts longitude, so the whole surface is one
            # offset into the coastline bitmap.
            shift = ang / TWO_PI * MAP_W
            land_lo, land_hi = P['land_day']
            night_lo, night_hi = P['land_night']
            sea_lo, sea_hi = P['ocean_day']
            seanight_lo, seanight_hi = P['ocean_night']
            for r, c, subs, centre, depth, ill, sea_glyph in cells:
                n = 0
                for rowoff, base in subs:
                    idx = rowoff + int(base - shift) % MAP_W
                    if _LAND[idx >> 3] & (0x80 >> (idx & 7)):
                        n += 1
                if args.no_night:
                    ill = 1.0

                # Half coverage, not "any sample hit": taking any hit
                # over-reports land badly (8.4% of cells wrong against a
                # 64-sample reference, vs 0.9% at half).
                cov = n / len(subs)
                if cov >= 0.5:
                    day = lerp(land_lo, land_hi, depth)
                    night = lerp(night_lo, night_hi, depth)
                    # glyph carries how much land is in the cell; depth is
                    # already in the colour, so it must not also gate the
                    # glyph -- keying it on screen depth made land change
                    # character as it crossed a fixed ring on the display.
                    glyph = '@' if cov > 0.80 else '#'
                    if ill < 0.26 and not args.no_night:
                        # anchor the twinkle to the ground, not to the cell
                        rowoff, base = centre
                        idx = rowoff + int(base - shift) % MAP_W
                        seed = ((idx * 2654435761) & 0xFFFFFFFF) / 4294967296.0
                        if seed > 0.90:
                            tw = 0.6 + 0.4 * math.sin(sim * 3.1 + seed * 40)
                            put(r, c, '*', quant(lerp(night, P['lights'], tw)))
                            continue
                else:
                    day = lerp(sea_lo, sea_hi, depth)
                    night = lerp(seanight_lo, seanight_hi, depth)
                    glyph = sea_glyph

                col = lerp(night, day, ill)
                if 0.26 < ill < 0.72 and not args.no_night:
                    # warm twilight band right at the terminator
                    g = 1.0 - abs(ill - 0.49) / 0.23
                    col = lerp(col, P['twilight'], 0.42 * g)
                put(r, c, glyph, quant(col))

            # ---- satellites (inertial: not carried by Earth's spin) ----
            if not args.no_sats:
                for inc, raan, rad, per, phase, name in SATS:
                    ci, si = math.cos(math.radians(inc)), math.sin(math.radians(inc))
                    cR, sR = math.cos(math.radians(raan)), math.sin(math.radians(raan))

                    def orbit_pt(u):
                        ox, oy = math.cos(u), math.sin(u)
                        px, py, pz = ox, oy * ci, oy * si
                        return (rad * (px * cR - py * sR),
                                rad * (px * sR + py * cR),
                                rad * pz)

                    for k in range(72):        # faint orbit ring
                        px, py, pz = orbit_pt(k / 72 * TWO_PI)
                        rx, ty, tz = project(px, py, pz, spin=False)
                        if occluded(rx, ty, tz):
                            continue
                        put(int(cy - ty * R * 0.5), int(cx + rx * R), '.',
                            quant(P['orbit']))

                    u = TWO_PI * (sim / per + phase)
                    px, py, pz = orbit_pt(u)
                    rx, ty, tz = project(px, py, pz, spin=False)
                    if not occluded(rx, ty, tz):
                        r = int(cy - ty * R * 0.5)
                        c = int(cx + rx * R)
                        put(r, c, '^', P['sat'])
                        if not args.no_labels and R > 16 and c + 2 + len(name) < area_w:
                            text(r, c + 2, name, quant(lerp((0, 0, 0), P['sat'], 0.6)))

            # ---- trace arcs ----
            if not args.no_traces:
                if sim >= next_trace and not paused:
                    next_trace = sim + rng.uniform(0.7, 2.3)
                    traces.append(Trace(sim, rng))
                    if len(traces) > 7:
                        traces.pop(0)
                traces = [t for t in traces if t.phase(sim) is not None]

                for tr in traces:
                    ph = tr.phase(sim)
                    head = min(1.0, ph * 1.9)
                    fade = 1.0 if ph < 0.62 else 1.0 - (ph - 0.62) / 0.38
                    n = len(tr.pts)
                    lastidx = int(head * (n - 1))
                    for k in range(lastidx + 1):
                        px, py, pz = tr.pts[k]
                        rx, ty, tz = project(px, py, pz)
                        if occluded(rx, ty, tz):
                            continue
                        near = 1.0 - abs(k - lastidx) / max(n * 0.30, 1)
                        b = fade * (0.42 + 0.58 * max(0.0, near))
                        if b < 0.10:
                            continue
                        put(int(cy - ty * R * 0.5), int(cx + rx * R),
                            '=' if near > 0.55 else '-',
                            quant(lerp((0, 0, 0), P['arc'], b)))
                    if head < 1.0:
                        px, py, pz = tr.pts[lastidx]
                        rx, ty, tz = project(px, py, pz)
                        if not occluded(rx, ty, tz):
                            put(int(cy - ty * R * 0.5), int(cx + rx * R),
                                'O', P['packet'])

                live = set()
                for tr in traces:
                    live.add(tr.src)
                    live.add(tr.dst)
                for vec, name in CITY_VECS:
                    rx, ty, tz = project(*vec)
                    if tz <= 0.10:
                        continue
                    c = int(cx + rx * R)
                    r = int(cy - ty * R * 0.5)
                    if name in live:
                        blink = 0.55 + 0.45 * math.sin(sim * 7.0)
                        put(r, c, 'X', quant(lerp(P['city'], P['alert'], blink)))
                        if (not args.no_labels and R > 18
                                and c + 2 + len(name) < area_w):
                            text(r, c + 2, name, quant(
                                lerp((0, 0, 0), P['alert'], 0.55 + 0.35 * blink)))
                    elif tz > 0.35:
                        put(r, c, 'o', quant(lerp((0, 0, 0), P['city'], 0.55)))

            # ---- HUD ----
            if not args.no_hud:
                if not paused:
                    hud.tick(sim, traces)
                H, HD = P['hud'], P['hud_dim']
                lonc = ((90.0 - math.degrees(ang) + 180.0) % 360.0) - 180.0
                bar = '─' * max(0, cols - 2)
                text(0, 0, '┌' + bar + '┐', HD)
                text(rows - 1, 0, '└' + bar + '┘', HD)
                title = f'┤ {BANNER} ├'
                text(0, max(2, (cols - len(title)) // 2), title, H)
                text(1, 2, f'LON {lonc:+07.2f}  TILT {args.tilt:+05.1f}  '
                           f'SPIN x{args.speed:+.2f}' + ('  [PAUSED]' if paused else ''),
                     H if paused else HD)
                stamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now))
                text(1, max(2, cols - len(stamp) - 2), stamp, HD)
                foot = (f'UPTIME {fmt_dur(now - t0)}  FPS {fps_est:04.1f}  '
                        f'NODES {len(CITY_VECS)}  LINKS {len(traces)}  '
                        f'PKT {hud.pkts:,}')
                text(rows - 2, 2, foot, HD)
                right = f'[{args.palette.upper()}]  h HELP  q QUIT'
                text(rows - 2, max(2, cols - len(right) - 2), right, HD)

                if panel:
                    px0 = cols - panel
                    for r in range(top, bot):
                        put(r, px0, '│', HD)
                    text(top, px0 + 2, '// LIVE TRACE LOG', H)
                    avail = bot - top - 3
                    for i, (line, tail) in enumerate(hud.log[-avail:]):
                        r = top + 2 + i
                        if r >= bot:
                            break
                        text(r, px0 + 2, line[:panel - 13], HD)
                        c = P['alert'] if tail in ('TIMEOUT', 'RETRY') else H
                        text(r, cols - len(tail) - 2, tail, c)

            # ---- transient key feedback ----
            if flash and now < flash_until:
                msg = f'[ {flash} ]'
                text(max(0, rows - 3), max(1, (cols - len(msg)) // 2), msg,
                     P['hud'])

            # ---- help overlay ----
            if show_help:
                bw = 30
                bh = len(HELP_LINES) + 2
                r0 = max(0, (rows - bh) // 2)
                c0 = max(0, (cols - bw) // 2)
                H, HD = P['hud'], P['hud_dim']
                for i in range(bh):
                    for j in range(bw):
                        put(r0 + i, c0 + j, ' ', None)
                text(r0, c0, '┌' + '─' * (bw - 2) + '┐', HD)
                text(r0, c0 + 2, '┤ CONTROLS ├', H)
                for i, line in enumerate(HELP_LINES):
                    put(r0 + 1 + i, c0, '│', HD)
                    text(r0 + 1 + i, c0 + 2, line[:bw - 3], H)
                    put(r0 + 1 + i, c0 + bw - 1, '│', HD)
                text(r0 + bh - 1, c0, '└' + '─' * (bw - 2) + '┘', HD)

            # ---- glitch burst ----
            if not args.no_glitch and not paused:
                if sim >= next_glitch:
                    glitch_until = sim + rng.uniform(0.08, 0.26)
                    next_glitch = sim + rng.uniform(7, 22)
                if sim < glitch_until:
                    for _ in range(rng.randrange(2, 6)):
                        r = rng.randrange(rows)
                        off = rng.randrange(-4, 5)
                        if off:
                            ch[r] = ch[r][off:] + ch[r][:off]
                            co[r] = co[r][off:] + co[r][:off]

            # ---- paint ----
            out = [HOME]
            for r in range(rows):
                crow, orow = ch[r], co[r]
                cur = None
                line = []
                for c in range(cols):
                    col = orow[c]
                    if col is None:
                        if cur is not None:
                            line.append(RESET)
                            cur = None
                        line.append(' ')
                    else:
                        if col != cur:
                            line.append(sgr(col))
                            cur = col
                        line.append(crow[c])
                if cur is not None:
                    line.append(RESET)
                out.append(''.join(line))
                if r < rows - 1:
                    out.append('\n')
            sys.stdout.write(''.join(out))
            sys.stdout.flush()

            frame += 1
            if not paused:
                ang = (ang + 0.02 * args.speed) % TWO_PI
            time.sleep(max(0.0, 1.0 / args.fps - (time.time() - now)))
    except (KeyboardInterrupt, BrokenPipeError):
        pass
    finally:
        cleanup()


def build_cells(top, bot, area_w, R, cx, cy, ct, st, sub):
    """Per-character-cell sample plan for the globe's front face.

    Sampling the other way round -- a fixed lat/lon lattice projected onto
    the grid -- aliases badly: the lattice is fixed in world space, the
    grid is fixed in screen space, and rotation slides one across the
    other.  Cells end up with no sample or several competing ones, so
    landmasses grow holes and isolated dots blink in open ocean.

    One sample plan per cell instead, `sub` x `sub` supersampled for a
    land-coverage fraction.  Tilt and cell position are constant, so
    everything except longitude can be baked now:

      lat (hence the bitmap row) is fixed per sub-sample, and spinning by
      `ang` only shifts longitude, so the frame loop needs an add and a
      modulo per sample -- no trigonometry at all.
    """
    fr = [(k + 0.5) / sub for k in range(sub)]
    cells = []
    for r in range(top, bot):
        for c in range(area_w):
            rx = (c + 0.5 - cx) / R
            ty = (cy - (r + 0.5)) / (R * 0.5)
            rho2 = rx * rx + ty * ty
            if rho2 >= 1.0:              # centre off the disc: no cell
                continue
            tz = math.sqrt(1.0 - rho2)

            def plan(px, py):
                """Cell-relative sub-sample -> (bitmap row offset, column)."""
                sx = (c + px - cx) / R
                sy = (cy - (r + py)) / (R * 0.5)
                q = sx * sx + sy * sy
                if q >= 1.0:
                    return None
                sz = math.sqrt(1.0 - q)
                z = sy * ct + sz * st
                ry = -sy * st + sz * ct
                lat = math.asin(max(-1.0, min(1.0, z)))
                j = min(MAP_H - 1, int((math.pi / 2 - lat) / math.pi * MAP_H))
                # lon = atan2(ry, -sx) - ang, so bake the constant half and
                # pre-add MAP_W to keep the running value non-negative
                a = math.atan2(ry, -sx)
                return (j * MAP_W, (a + math.pi) / TWO_PI * MAP_W + MAP_W)

            subs = [p for p in (plan(px, py) for py in fr for px in fr)
                    if p is not None]
            if not subs:
                continue
            centre = plan(0.5, 0.5)

            depth = tz ** 0.55
            raw = rx * SUN[0] + ty * SUN[1] + tz * SUN[2]
            ill = max(0.0, min(1.0, (raw + 0.13) / 0.30))
            cells.append((r, c, tuple(subs), centre, depth, ill,
                          '·' if depth > 0.45 else '.'))
    return cells


if __name__ == '__main__':
    main()
