#!/usr/bin/env python3
"""
 MECHMODEL // turntable rig for a battlemech
 -------------------------------------------
 A 3D model on a slow-orbiting camera, drawn in a terminal at half-block
 resolution. Same renderer family as dscape.py -- the 1x2 pixel buffer, the
 quadrant-glyph emitter, the orbit camera -- but the geometry underneath is
 different in kind: dscape draws axis-aligned boxes on a guillotine plan and
 gets its painter's order exactly from the plan's own cuts. Nothing here is
 axis-aligned, so facets carry true normals and sort by depth.

 Point it at an STL and it renders that. The reference model is 242,976
 triangles and the renderer can afford a few thousand, so the mesh goes through
 a pipeline first: vertex-cluster decimation to a facet budget, a voxel
 occupancy grid flooded from the outside to find what is solid, and a
 hemisphere of rays per facet for real ambient occlusion -- occlusion that sees
 the arm hanging in front of the chest, not just local curvature. That is
 seconds of work, so it is cached beside the source file and is a few
 milliseconds thereafter. Three levels of detail are built; d cycles them.

 A few thousand facets is not a compromise. At this resolution the model covers
 maybe 150x400 pixels, so it is already one facet per handful of pixels.

 The display is a targeting and diagnostics HUD, and it has two panels. The
 COMBAT panel (default) is what a gunner would want: designation, tonnage,
 loadout, heat sinks, speeds, and the armour spread over the machine's five
 sections. The MESH panel (m) is the renderer's own report -- welded vertex
 count, whether every edge is used exactly twice (which is what watertight
 means and what makes the enclosed volume a real number), the decimation error
 against the source, facets drawn and frame rate.

 Two sources and no third, and every line says which it is. CANON is Sarna's
 and is quoted, never rounded or filled in -- Sarna assigns no body location to
 any Prime weapon, so neither does this program. Everything else is measured
 off the mesh. Where they meet is stated: the armour spread is Sarna's twelve
 tons distributed over MEASURED skin area, and the density is Sarna's 75 tons
 over the measured displacement.

 SCAN is not a progress bar. It fills with BEARING swept since the scan began
 and completes on a full revolution; the percentage beside it is how much of
 the hull actually returned. 'Every facet returned' was tried and measured as
 the wrong test -- it stalls near 96%, because at a fixed tilt some of the hull
 never faces the sensor at any bearing.

 With --builtin, or with no STL to hand, it draws a mech assembled here out of
 lofted convex hulls on a 17-bone skeleton -- articulated, so j and k walk the
 structure list and e pulls it apart.

 Usage:
   python3 mechmodel.py                 mc.stl if it is beside the script
   python3 mechmodel.py thing.stl       any binary or ASCII STL
   python3 mechmodel.py --builtin       the procedural mech instead
   python3 mechmodel.py --up y          for a Y-up STL
   python3 mechmodel.py --faces 20000   one custom facet budget
   python3 mechmodel.py --palette ice   field | matrix | amber | ice | plasma | blood
   python3 mechmodel.py --stats         print the mesh report and exit
   python3 mechmodel.py --lighting key  cheaper shading, still solid-looking
   (also --tilt --az --dist --speed --fps --blocks --zen --lod --voxels
    --ao-radius --no-ao --no-cache --no-stars --no-shadow --no-idle --frames)

 Live controls (h for the full list):
   m     panel: combat / mesh
   j k   target section -- NO TARGET, torso, arm L/R, leg L/R. The sections
         are segmented off the occupancy grid; see SECTIONS.
   SPACE pause spin   q quit         h help        0 reset
   <- -> orbit        ^ v tilt       [ ] zoom      , . spin rate
   d     detail       a occlusion    w wireframe   l labels   S shadow
   v     sensor: optical / thermal / lidar / xray
   c     cutaway plane, - and = to move the station
   L     lighting: full / key / flat -- key drops the fill light, sheen,
         ambient and fog; flat drops lighting altogether, which on a
         one-material mesh leaves a silhouette.
   p     palette      1-6 direct     g grid x3     z zen      s stars
   e     explode      i idle -- the built-in model only, and silently inert
         on a loaded mesh, which is one rigid shell with no joints to move.
"""
import sys, os, math, time, shutil, argparse, signal, random, select
import colorsys, struct, array, json, zlib
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
# 8 = bottom-right.
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
    return (min(255, max(0, int(c[0] * k))),
            min(255, max(0, int(c[1] * k))),
            min(255, max(0, int(c[2] * k))))


def quant(rgb, step=6):
    """Snap colors to a coarse ladder so the SGR caches stay small and the
    run-length emitter gets long runs out of every gradient."""
    return (rgb[0] // step * step, rgb[1] // step * step, rgb[2] // step * step)


# --- materials ------------------------------------------------------------
# One palette entry per *material*, not per part, so the mech reads as a built
# object: olive drab plate, bare gun-metal at every joint, oxide on the load
# bearing surfaces that would actually rust, and hazard paint where a ground
# crew would actually put it. Brightness carries the distinction as well as
# hue, which is what lets the tinted palettes below stay legible in one colour.
MATERIALS = {
    'plate':  (96, 106, 62),      # olive drab armour
    'plate2': (78, 88, 52),       # the same armour, shaded panel
    'plate3': (118, 126, 82),     # sun-bleached upper surface
    'rust':   (124, 74, 42),      # oxide on knees, feet, shoulder yokes
    'rust2':  (92, 54, 32),
    'metal':  (122, 120, 112),    # bare actuator housings
    'metal2': (86, 84, 78),
    'dark':   (44, 46, 42),       # recesses, gaps, tube throats
    'tube':   (28, 29, 27),       # missile tube bore
    'glass':  (146, 196, 212),    # cockpit laminate
    'haz_y':  (206, 190, 62),     # hazard stripe
    'haz_k':  (36, 36, 32),
    'red':    (162, 52, 40),      # unit flash
    'green':  (74, 138, 66),
    'lamp':   (236, 232, 196),    # running lights, gun-lens glow
}

# Materials that are their own light source rather than a lit surface, so the
# shader pulls them back toward their base colour. A dict rather than the
# `mat in ('lamp', 'glass')` tuple scan it replaces, because that ran once per
# facet per frame.
SOFT_MAT = dict((m, m in ('lamp', 'glass')) for m in MATERIALS)

# Tonnes per cubic metre of *enclosed hull*, not of solid material -- a limb
# casing is mostly myomer bundle, coolant run and void, so the figure that
# turns a modelled volume into a believable mass is the mean density of the
# whole assembly. Actuator housings are the dense parts; laminate plate is
# lighter than it looks; glass and lamp housings are skin. Calibrated so the
# 187 m3 of hull below comes out at the 65 tonnes the class is rated for,
# which is the one number in the table that is chosen rather than measured.
DENSITY = {
    'plate': 0.31, 'plate2': 0.31, 'plate3': 0.31, 'rust': 0.31,
    'rust2': 0.31, 'metal': 0.53, 'metal2': 0.53, 'dark': 0.16,
    'tube': 0.16, 'glass': 0.12, 'haz_y': 0.31, 'haz_k': 0.31,
    'red': 0.31, 'green': 0.31, 'lamp': 0.06,
}

# --- canon ------------------------------------------------------------------
# The vehicle in mc.stl is the Timber Wolf, Inner Sphere codename Mad Cat, and
# its fiction is not mine to invent. Everything below is from Sarna, the
# BattleTech wiki, and nothing has been rounded, averaged or filled in:
#
#   https://www.sarna.net/wiki/Timber_Wolf_(Mad_Cat)
#   https://www.sarna.net/news/good-mechs-timber-wolf/
#
# Note what is deliberately ABSENT. Sarna lists the Prime's nine weapons but
# assigns none of them to a body location, so this table does not either. An
# earlier draft of this program put the ER larges "in the arms" and the LRM-20s
# "in the side torsos"; that is the sort of thing everyone knows and nobody
# sourced, and it is not in the table for that reason. If a location is wanted
# it has to come from the wiki, not from the shape of the mesh or from me.
CANON = {
    'name':      'TIMBER WOLF',
    'codename':  'MAD CAT',
    'config':    'PRIME',
    'mass_t':    75,                    # tons
    'chassis':   'Type W3 Endo-Steel',
    'engine':    'Starfire 375 XL',
    'cruise':    54.0,                  # km/h
    'flank':     86.4,                  # km/h
    'walk_mp':   5,
    'run_mp':    8,
    'armour':    'Composite A-2 Ferro-Fibrous',
    'armour_t':  12,                    # tons
    'heatsinks': '15 double',
    'podspace':  27.5,                  # tons
    'intro':     2945,
    'origin':    'Clan Wolf',
    'quirk':     'Weak Head Armor (1)',
    # Prime configuration. Counts are Sarna's; locations are not stated there.
    'weapons': (('ER Large Laser', 2), ('ER Medium Laser', 2),
                ('Medium Pulse Laser', 1), ('LRM-20', 2), ('Machine Gun', 2)),
    'codename_origin':
        "Phelan Kell's Wolfhound targeting computer switched between MAD and "
        "CAT; Focht made the designation official.",
}

# --- palettes -------------------------------------------------------------
# 'field' is the model as painted. The others are a hue collapse: every
# material is dragged onto one hue at a fixed saturation, keeping its own
# luminance, so the mech stays readable as a machine rather than a silhouette.
# 'field' is daylight: hazy overcast sky, dry olive grass, the machine lit the
# way the reference photograph is lit. The other five are the dscape night
# palettes, kept so the two programs can sit side by side. 'bounce' is the
# colour the ground throws back up onto downward-facing surfaces -- see the
# hemisphere term in the shader. 'star' is None where the sky is too bright to
# have any.
PALETTES = {
    'field':  {'tint': None,
               'sky': ((122, 146, 172), (214, 212, 194)),
               'ground': (92, 96, 58), 'grid': (118, 122, 80), 'star': None,
               'bounce': (104, 100, 62),
               'hud': (222, 232, 170), 'hud_dim': (130, 138, 94),
               'panel': (22, 24, 16), 'sel': (255, 244, 180),
               'alert': (240, 130, 70), 'shadow': (46, 48, 32)},
    'matrix': {'tint': (0.38, 0.70),
               'sky': ((2, 9, 7), (10, 40, 30)), 'ground': (5, 24, 18),
               'grid': (18, 74, 54), 'star': (95, 140, 110),
               'bounce': (8, 34, 26),
               'hud': (60, 235, 150), 'hud_dim': (25, 130, 85),
               'panel': (3, 16, 12), 'sel': (255, 245, 170),
               'alert': (255, 120, 90), 'shadow': (2, 12, 9)},
    'amber':  {'tint': (0.09, 0.78),
               'sky': ((10, 5, 2), (44, 22, 8)), 'ground': (26, 13, 4),
               'grid': (86, 48, 12), 'star': (140, 105, 55),
               'bounce': (44, 22, 8),
               'hud': (255, 176, 44), 'hud_dim': (140, 92, 20),
               'panel': (18, 9, 2), 'sel': (255, 255, 220),
               'alert': (255, 95, 60), 'shadow': (13, 6, 2)},
    'ice':    {'tint': (0.56, 0.62),
               'sky': ((2, 6, 16), (16, 34, 68)), 'ground': (7, 14, 32),
               'grid': (28, 54, 100), 'star': (120, 150, 180),
               'bounce': (14, 28, 58),
               'hud': (90, 210, 255), 'hud_dim': (40, 110, 150),
               'panel': (5, 11, 24), 'sel': (255, 250, 210),
               'alert': (255, 130, 130), 'shadow': (3, 7, 16)},
    'plasma': {'tint': (0.79, 0.60),
               'sky': ((7, 3, 16), (34, 16, 60)), 'ground': (18, 8, 32),
               'grid': (66, 32, 96), 'star': (140, 105, 165),
               'bounce': (30, 14, 52),
               'hud': (230, 110, 240), 'hud_dim': (120, 55, 130),
               'panel': (13, 6, 24), 'sel': (190, 255, 255),
               'alert': (255, 210, 90), 'shadow': (9, 4, 16)},
    'blood':  {'tint': (0.99, 0.74),
               'sky': ((10, 2, 3), (44, 12, 14)), 'ground': (26, 7, 9),
               'grid': (86, 26, 28), 'star': (140, 80, 80),
               'bounce': (42, 12, 14),
               'hud': (255, 80, 72), 'hud_dim': (135, 38, 35),
               'panel': (18, 5, 6), 'sel': (255, 240, 200),
               'alert': (255, 200, 60), 'shadow': (13, 3, 4)},
}
PAL_NAMES = ['field', 'matrix', 'amber', 'ice', 'plasma', 'blood']


def palette_materials(pal):
    """Materials as this palette paints them.

    A tinted palette keeps each material's luminance and replaces its hue, so
    'metal' stays brighter than 'plate2' and the mech does not collapse into a
    single flat shape. Lamps and glass keep a little of their own lift.
    """
    t = PALETTES[pal]['tint']
    if t is None:
        return dict(MATERIALS)
    hue, sat = t
    out = {}
    for k, c in MATERIALS.items():
        _, l, _ = colorsys.rgb_to_hls(c[0] / 255.0, c[1] / 255.0, c[2] / 255.0)
        s = sat
        if k in ('lamp', 'glass'):
            l = min(1.0, l * 1.15)
            s *= 0.5
        r, g, b = colorsys.hls_to_rgb(hue, l, s)
        out[k] = (int(r * 255), int(g * 255), int(b * 255))
    return out


# --- formatting -----------------------------------------------------------
def commas(n):
    return '{:,}'.format(int(n))


def bar_str(frac, n=10):
    if frac < 0:
        frac = 0.0
    if frac > 1:
        frac = 1.0
    full = int(frac * n)
    rem = frac * n - full
    s = '█' * full
    if full < n:
        s += ' ▏▎▍▌▋▊▉'[int(rem * 8)]
    return (s + ' ' * n)[:n]


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

    def fill(self, pts, c0, c1=None):
        """Scanline-fill a convex polygon, lerping c0 (top) -> c1 (bottom)."""
        n = len(pts)
        ys = [p[1] for p in pts]
        ymin, ymax = min(ys), max(ys)
        y0 = int(math.ceil(ymin - 0.5))
        y1 = int(math.floor(ymax - 0.5))
        if y0 < 0:
            y0 = 0
        if y1 >= self.h:
            y1 = self.h - 1
        if y1 < y0:
            return
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

    def fill3(self, a, b, c, col):
        """fill(), specialised to a triangle in one flat colour.

        Worth its own method because of what the facets actually measure: on
        the STL at 80x24 a facet covers 0.93 scanlines and 2.3 pixels. At that
        size the generic fill's per-scanline overhead -- a fresh list, a loop
        over every edge, two appends, a length test, sometimes a sort -- IS the
        cost, and the slice assignment the whole raster design exists to reach
        is writing two pixels. Sorting the three vertices once and walking the
        long edge against one short edge removes all of it.

        The arithmetic is deliberately kept in the same order as fill() --
        dx precomputed but still divided by dy, never multiplied by a
        reciprocal -- so this is bit-for-bit the same picture, which was
        checked rather than assumed.
        """
        if a[1] > b[1]:
            a, b = b, a
        if b[1] > c[1]:
            b, c = c, b
        if a[1] > b[1]:
            a, b = b, a
        ay, by, cy = a[1], b[1], c[1]
        y0 = int(math.ceil(ay - 0.5))
        y1 = int(math.floor(cy - 0.5))
        if y0 < 0:
            y0 = 0
        if y1 >= self.h:
            y1 = self.h - 1
        if y1 < y0:
            return
        dyl = cy - ay
        if dyl == 0.0:
            return
        ax, bx, cx = a[0], b[0], c[0]
        dxl = cx - ax
        d1x, d1y = bx - ax, by - ay
        d2x, d2y = cx - bx, cy - by
        px, W = self.px, self.w
        for y in range(y0, y1 + 1):
            yc = y + 0.5
            xl = ax + dxl * (yc - ay) / dyl
            if yc < by:
                if d1y == 0.0:
                    continue
                xr = ax + d1x * (yc - ay) / d1y
            else:
                if d2y == 0.0:
                    continue
                xr = bx + d2x * (yc - by) / d2y
            if xl > xr:
                xl, xr = xr, xl
            xa = int(math.ceil(xl - 0.5))
            xb = int(math.floor(xr - 0.5)) + 1
            if xa < 0:
                xa = 0
            if xb > W:
                xb = W
            if xb > xa:
                px[y][xa:xb] = [col] * (xb - xa)

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
        """line(), but clipped to the viewport first (Liang-Barsky), so a
        segment whose endpoint landed far off screen costs nothing to skip."""
        dx, dy = x1 - x0, y1 - y0
        t0, t1 = 0.0, 1.0
        for p, q in ((-dx, x0), (dx, self.w - 1 - x0),
                     (-dy, y0), (dy, self.h - 1 - y0)):
            if p == 0.0:
                if q < 0.0:
                    return
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


# --- linear algebra -------------------------------------------------------
# 3x3 matrices are flat 9-tuples, row-major. Every rotation used here is
# orthonormal, which is what lets normals be transformed by the same matrix as
# positions instead of by its inverse transpose.
IDENT = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def mmul(a, b):
    return (a[0] * b[0] + a[1] * b[3] + a[2] * b[6],
            a[0] * b[1] + a[1] * b[4] + a[2] * b[7],
            a[0] * b[2] + a[1] * b[5] + a[2] * b[8],
            a[3] * b[0] + a[4] * b[3] + a[5] * b[6],
            a[3] * b[1] + a[4] * b[4] + a[5] * b[7],
            a[3] * b[2] + a[4] * b[5] + a[5] * b[8],
            a[6] * b[0] + a[7] * b[3] + a[8] * b[6],
            a[6] * b[1] + a[7] * b[4] + a[8] * b[7],
            a[6] * b[2] + a[7] * b[5] + a[8] * b[8])


def mvec(m, v):
    x, y, z = v
    return (m[0] * x + m[1] * y + m[2] * z,
            m[3] * x + m[4] * y + m[5] * z,
            m[6] * x + m[7] * y + m[8] * z)


def rx(deg):
    """Rotate about +x. Positive takes +y toward +z, so a positive angle on a
    limb frame swings its downward axis *forward*."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (1.0, 0.0, 0.0, 0.0, c, -s, 0.0, s, c)


def ry(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (c, 0.0, s, 0.0, 1.0, 0.0, -s, 0.0, c)


def rz(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (c, -s, 0.0, s, c, 0.0, 0.0, 0.0, 1.0)


def rxyz(ax=0.0, ay=0.0, az=0.0):
    return mmul(mmul(rz(az), ry(ay)), rx(ax))


def normed(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


# --- the skeleton ---------------------------------------------------------
class Frame:
    """One bone. `rot` is its rest orientation in the parent, `pose` whatever
    the animation adds on top; the two are kept apart so a reset is a reset and
    an explode can scale the offsets without eating the rest pose."""

    __slots__ = ('name', 'parent', 'off', 'rot', 'pose', 'M', 'T')

    def __init__(self, name, parent, off, rot):
        self.name = name
        self.parent = parent
        self.off = off
        self.rot = rot
        self.pose = IDENT
        self.M = IDENT
        self.T = (0.0, 0.0, 0.0)

    def resolve(self):
        local = mmul(self.rot, self.pose)
        if self.parent is None:
            self.M, self.T = local, self.off
        else:
            pM, pT = self.parent.M, self.parent.T
            o = mvec(pM, self.off)
            self.M = mmul(pM, local)
            self.T = (pT[0] + o[0], pT[1] + o[1], pT[2] + o[2])


# --- mesh construction ----------------------------------------------------
# Everything in the model is a loft: a stack of cross-section rings, joined
# ring to ring by quads and closed with n-gon caps. A box is two rectangular
# rings, a hydraulic ram is two circular ones, the cockpit pod is nine ellipse
# rings on a curved profile. One primitive, and `Raster.fill` takes any convex
# polygon, so the caps cost nothing extra.

def rect2(hw, hd, bev=0.0):
    """Rectangle cross-section, optionally with its corners cut. The bevel is
    what keeps armour plate from reading as a cardboard box: a lit chamfer down
    every vertical edge is most of what says 'machined' at this resolution."""
    if bev <= 0.0:
        return [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    b = min(bev, hw * 0.9, hd * 0.9)
    return [(-hw + b, -hd), (hw - b, -hd), (hw, -hd + b), (hw, hd - b),
            (hw - b, hd), (-hw + b, hd), (-hw, hd - b), (-hw, -hd + b)]


def ngon2(rx_, ry_, n, phase=0.0):
    return [(rx_ * math.cos(phase + 2 * math.pi * i / n),
             ry_ * math.sin(phase + 2 * math.pi * i / n)) for i in range(n)]


def ring(pts2, t, axis='z'):
    """Lift a cross-section into 3D at position `t` along `axis`."""
    if axis == 'z':
        return [(u, v, t) for u, v in pts2]
    if axis == 'y':
        return [(u, t, v) for u, v in pts2]
    return [(t, u, v) for u, v in pts2]


def place(pts3, off=(0.0, 0.0, 0.0), rot=IDENT):
    out = []
    for p in pts3:
        q = mvec(rot, p) if rot is not IDENT else p
        out.append((q[0] + off[0], q[1] + off[1], q[2] + off[2]))
    return out


class Mesh:
    """Vertices plus (index-tuple, material) faces. Vertices are shared inside
    a loft, so a box is 8 vertices and not 24 -- the per-frame transform cost is
    linear in vertices, and this model is transformed every single frame."""

    def __init__(self):
        self.v = []
        self.f = []

    def loft(self, rings, mat, cap0=True, cap1=True, matf=None):
        n = len(rings[0])
        base = len(self.v)
        for r in rings:
            if len(r) != n:
                raise ValueError('loft rings must agree in length')
            self.v.extend(r)
        for k in range(len(rings) - 1):
            a = base + k * n
            b = a + n
            for i in range(n):
                j = (i + 1) % n
                m = matf(k, i) if matf else mat
                if m is not None:
                    self.f.append(((a + i, a + j, b + j, b + i), m))
        if cap0:
            self.f.append((tuple(base + i for i in range(n - 1, -1, -1)), mat))
        if cap1:
            last = base + (len(rings) - 1) * n
            self.f.append((tuple(range(last, last + n)), mat))

    def poly(self, pts, mat):
        base = len(self.v)
        self.v.extend(pts)
        self.f.append((tuple(range(base, base + len(pts))), mat))

    # -- primitives --------------------------------------------------------
    def box(self, mat, size, off=(0, 0, 0), rot=IDENT, bev=0.0, taper=1.0,
            axis='z', matf=None):
        """A slab. `taper` scales the far cross-section, which is how every
        tapered limb segment in the model is made."""
        hu, hv, ht = size[0] / 2.0, size[1] / 2.0, size[2] / 2.0
        r0 = ring(rect2(hu, hv, bev), -ht, axis)
        r1 = ring(rect2(hu * taper, hv * taper, bev * taper), ht, axis)
        self.loft([place(r0, off, rot), place(r1, off, rot)], mat, matf=matf)

    def tube(self, mat, r0, r1, length, n=10, off=(0, 0, 0), rot=IDENT,
             axis='z', phase=0.0):
        a = ring(ngon2(r0, r0, n, phase), -length / 2.0, axis)
        b = ring(ngon2(r1, r1, n, phase), length / 2.0, axis)
        self.loft([place(a, off, rot), place(b, off, rot)], mat)

    def pod(self, mat, profile, n=10, off=(0, 0, 0), rot=IDENT, axis='y',
            phase=0.0, matf=None):
        """A lofted hull from (position, half-width, half-height) rings. The
        cockpit pod, the shoulder yokes and the missile-rack shells are all
        this; a closed profile (zero radius at both ends) needs no caps."""
        rings = []
        for t, a, b in profile:
            rings.append(place(ring(ngon2(max(a, 1e-4), max(b, 1e-4), n, phase),
                                    t, axis), off, rot))
        cap0 = profile[0][1] > 1e-3
        cap1 = profile[-1][1] > 1e-3
        self.loft(rings, mat, cap0=cap0, cap1=cap1, matf=matf)

    def grid_face(self, corners, nu, nv, colf, inset=0.0):
        """Subdivide a planar quad into nu x nv cells, each coloured by
        colf(i, j). This is how the missile tubes, the hazard chevrons and the
        armour panel lines are drawn: as geometry, not as texture, because the
        renderer has no texture stage and a quad is cheaper than one anyway."""
        p00, p10, p11, p01 = corners

        def at(u, v):
            a = [p00[k] + (p10[k] - p00[k]) * u for k in range(3)]
            b = [p01[k] + (p11[k] - p01[k]) * u for k in range(3)]
            return tuple(a[k] + (b[k] - a[k]) * v for k in range(3))

        for i in range(nu):
            for j in range(nv):
                m = colf(i, j)
                if m is None:
                    continue
                u0, u1 = (i + inset) / nu, (i + 1 - inset) / nu
                v0, v1 = (j + inset) / nv, (j + 1 - inset) / nv
                self.poly([at(u0, v0), at(u1, v0), at(u1, v1), at(u0, v1)], m)


class Part:
    """A mesh bound to a bone, with its faces pre-analysed.

    Normals are made to point away from the part's own centroid at build time.
    Every primitive here is star-shaped about its centre, so this is exact, and
    it means the loft generators never have to agree on a winding convention --
    a class of bug that costs an afternoon and shows up as one face of one limb
    being inside-out from one angle.
    """

    def __init__(self, name, frame, mesh, group, trust_winding=False,
                 ao=None, wear_amp=0.09, sec=None, temp=None):
        """`trust_winding` turns the outward-from-centroid pass OFF, for a mesh
        that already has a consistent winding of its own -- an STL, say. The
        centroid trick is exact for a star-shaped primitive and badly wrong for
        a whole mech: a facet inside the armpit points *toward* the body centre,
        and reorienting it would turn it inside out.

        `ao` is a per-face occlusion factor in [0, 1], folded into the same
        per-face brightness multiplier the weathering uses -- so occlusion
        costs the shader exactly nothing at frame time."""
        self.name = name
        self.frame = frame
        self.group = group
        self.v = mesh.v
        self.faces = []           # (idx, mat, local_normal, local_centroid)
        self.volume = 0.0
        self.mass = 0.0
        cx = sum(p[0] for p in mesh.v) / len(mesh.v)
        cy = sum(p[1] for p in mesh.v) / len(mesh.v)
        cz = sum(p[2] for p in mesh.v) / len(mesh.v)
        self.centroid = (cx, cy, cz)
        # crc32, not hash(): hash() of a str is salted per process, so the
        # weathering pattern came out different on every launch and no two
        # runs of the program ever drew the same frame. Invisible to the eye
        # -- it is a +-5% brightness jitter -- but it makes the renderer
        # unreproducible, which showed up the moment a pixel diff was used to
        # check an optimisation and the control run disagreed with itself on
        # 7% of pixels.
        self.sec = sec
        # Keep occlusion unfolded as well as folded: the shader wants it baked
        # into brightness, and the diagnostics want the number itself.
        self.aoraw = list(ao) if ao is not None else None
        self.temp = list(temp) if temp is not None else None
        rng = random.Random(zlib.crc32(name.encode()) & 0xffff)
        self.wear = []
        self.wear_plain = []
        for _fi, (idx, mat) in enumerate(mesh.f):
            pts = [mesh.v[i] for i in idx]
            nx = ny = nz = 0.0
            for k in range(len(pts)):
                a, b = pts[k - 1], pts[k]
                nx += (a[1] - b[1]) * (a[2] + b[2])
                ny += (a[2] - b[2]) * (a[0] + b[0])
                nz += (a[0] - b[0]) * (a[1] + b[1])
            area2 = math.sqrt(nx * nx + ny * ny + nz * nz)
            if area2 < 1e-12:
                continue                     # degenerate; a zero-width bevel
            fx = sum(p[0] for p in pts) / len(pts)
            fy = sum(p[1] for p in pts) / len(pts)
            fz = sum(p[2] for p in pts) / len(pts)
            n = (nx / area2, ny / area2, nz / area2)
            if not trust_winding and (
                    (fx - cx) * n[0] + (fy - cy) * n[1]
                    + (fz - cz) * n[2]) < 0:
                n = (-n[0], -n[1], -n[2])
                idx = tuple(reversed(idx))
            # Divergence theorem: 3V = sum over faces of (p . n) * area.
            self.volume += (fx * n[0] + fy * n[1] + fz * n[2]) * area2 / 2.0
            self.mass += ((fx * n[0] + fy * n[1] + fz * n[2]) * area2 / 2.0
                          / 3.0) * DENSITY.get(mat, 2.0)
            self.faces.append((idx, mat, n, (fx, fy, fz)))
            # Deterministic per-face weathering: a few percent of brightness,
            # fixed at build time so it does not crawl as the model turns.
            w = 1.0 + rng.uniform(-wear_amp, wear_amp * 0.78)
            self.wear_plain.append(w)
            self.wear.append(w * (AO_FLOOR + (1.0 - AO_FLOOR) * ao[_fi])
                             if ao is not None else w)
        self.volume /= 3.0
        self.mass = abs(self.mass)
        self.volume = abs(self.volume)


# --- ambient occlusion ------------------------------------------------------
# How dark a fully occluded facet goes. Occlusion multiplies brightness, so 0.34
# means a facet buried in an armpit keeps a third of its lit value -- enough to
# stay a surface rather than become a hole.
AO_FLOOR = 0.34

# The light rig, world-fixed so the shading changes as the camera comes round.
# SUN is the key; FILL is a dim, roughly opposite source standing in for
# everything the sky and the ground bounce back sideways.
SUN = normed((0.52, -0.66, 0.54))          # direction *toward* the sun
FILL = normed((-0.62, 0.48, 0.18))

# Lighting cost, traded against how much of the model you can still read.
#   FULL  key + fill + sheen + hemisphere ambient + fog -- the look as built
#   KEY   the key light alone. Still legibly three-dimensional, ~20% cheaper
#         than FULL at the shading stage.
#   FLAT  no lighting at all. Honest warning: on a single-material mesh like
#         the STL this is a featureless silhouette -- every facet takes the
#         same colour and the machine becomes a green cut-out. It is the
#         fastest thing the renderer can draw and it buys about a millisecond
#         over KEY, which is why KEY is the one worth reaching for.
# Sensor channels. Each is a different question asked of the same mesh, and
# each answers it from something already measured -- nothing here is a filter
# laid over a picture.
#   OPTICAL  the lit hull
#   THERMAL  false colour from a heat field with the fusion plant as its
#            source. See REACTOR_R. The first version false-coloured ambient
#            occlusion alone and got a cold torso, which is nonsense on a
#            machine built around a 375-rated reactor.
#   LIDAR    front-face wireframe, graded by range. A surface return.
#   XRAY     the same but WITHOUT backface culling, so the far side of the hull
#            comes through. Wireframe rather than translucency because the
#            painter's algorithm has no blend buffer to be honest with.
SENSOR_OPTICAL, SENSOR_THERMAL, SENSOR_LIDAR, SENSOR_XRAY = 0, 1, 2, 3
SENSOR_NAMES = ('OPTICAL', 'THERMAL', 'LIDAR', 'XRAY')

# Cold -> hot. Fixed, not palette-derived: a thermal channel that changed
# colour when you pressed p would be decoration, not an instrument.
HEAT_STOPS = ((16, 20, 62), (40, 66, 150), (36, 150, 148), (120, 196, 90),
              (232, 206, 84), (238, 132, 48), (244, 236, 220))
HEAT_LUT = []
for _i in range(65):
    _t = _i / 64.0 * (len(HEAT_STOPS) - 1)
    _a = min(len(HEAT_STOPS) - 2, int(_t))
    HEAT_LUT.append(lerp(HEAT_STOPS[_a], HEAT_STOPS[_a + 1], _t - _a))

# Scan-channel phosphor. Fixed, like the heat ramp, and deliberately not a
# palette colour: the first attempt drew the wireframe in the palette's grid
# olive, which on the daylit field put olive lines over olive ground.
SCAN_COL = (150, 232, 198)
SCAN_BG = (10, 14, 18)
SCAN_GRAZE = 0.42        # |n . view| below this is a contour, and only those
                         # get drawn -- outlining all 6,000 facets fills the
                         # silhouette with scribble and shows nothing.

# The heat field. Sarna gives this machine a Starfire 375 XL, and a fusion
# plant is hotter than everything else on the mech put together -- so a
# thermal channel whose brightest thing was an armpit was measuring the wrong
# quantity. Occlusion is a real property, but it is the *trapping* term, not
# the source.
#
# The source is a point at the measured centroid of the TORSO section. The
# engine is not placed by hand and it is not eyeballed off the silhouette: it
# is where the mass of the torso actually is, which for an XL plant filling
# the centre and both sides is the honest available answer. Falloff is inverse
# square, as a point source radiating into a solid must be. Occlusion stays in
# as the second term, weaker: heat that reaches the skin in a joint has a
# harder time leaving it.
REACTOR_R = 0.20         # half-strength distance, as a fraction of mech height
REACTOR_MIX = 0.76       # weight of the source term against the trapping term

LIGHT_FULL, LIGHT_KEY, LIGHT_FLAT = 0, 1, 2
LIGHT_NAMES = ('LIGHTING FULL', 'LIGHTING KEY ONLY', 'LIGHTING FLAT')
LIGHT_ARGS = ('full', 'key', 'flat')

# A facet gets a top-to-bottom gradient only if it is at least this tall on
# screen. The gradient is what makes a cylindrical limb on the built-in model
# read as round -- but STL facets average 0.93 scanlines at 80x24, and a
# gradient across one scanline is one colour bought at the price of a lerp and
# a quant on every scanline of every facet. So spend it only where it shows.
GRAD_MIN_H = 5.0


# --- STL ------------------------------------------------------------------
# Everything below turns a printable mesh into something a terminal can draw at
# frame rate. The reference model is 242,976 triangles; the renderer can afford
# a few thousand. That is not a compromise, it is the right number: at half-
# block resolution the model covers roughly 150x400 pixels, so a few thousand
# facets is already one facet per handful of pixels and more would be invisible.
# The whole pipeline -- decimate, voxelise, occlude -- runs once and is cached.

MODEL_H = 12.0            # world height every loaded model is normalised to
LOD_TARGETS = (2600, 6200, 14000)
LOD_NAMES = ('LOD LOW', 'LOD MEDIUM', 'LOD HIGH')
CACHE_MAGIC = b'MMSH'
CACHE_VER = 7
CACHE_HEAD = '<HHIIId'
CACHE_HLEN = len(CACHE_MAGIC) + struct.calcsize(CACHE_HEAD)
SHADOW_BANDS = 14


def load_stl(path):
    """Read binary or ASCII STL into a flat list of 12-float tuples
    (nx, ny, nz, then three vertices). The stored facet normal is kept: it is
    the only record of the original surface once the geometry is decimated,
    and it is what tells a clustered triangle which way round it should face."""
    d = open(path, 'rb').read()
    if len(d) < 84:
        raise ValueError('%s: too short to be an STL' % path)
    n = struct.unpack('<I', d[80:84])[0]
    if len(d) == 84 + 50 * n:
        return [r[:12] for r in struct.iter_unpack('<12fH', d[84:84 + 50 * n])]
    # ASCII: the header check has to be the size arithmetic above, not the
    # leading word. Plenty of binary STLs in the wild start with "solid".
    txt = d.decode('utf-8', 'replace')
    if 'facet' not in txt:
        raise ValueError('%s: not a recognisable STL' % path)
    out = []
    nrm = (0.0, 0.0, 1.0)
    vs = []
    for line in txt.splitlines():
        w = line.split()
        if not w:
            continue
        if w[0] == 'facet' and len(w) >= 5:
            nrm = (float(w[2]), float(w[3]), float(w[4]))
            vs = []
        elif w[0] == 'vertex' and len(w) >= 4:
            vs.append((float(w[1]), float(w[2]), float(w[3])))
        elif w[0] == 'endfacet' and len(vs) == 3:
            out.append(nrm + vs[0] + vs[1] + vs[2])
    if not out:
        raise ValueError('%s: no facets found' % path)
    return out


def stl_bounds(tris):
    x0 = y0 = z0 = 1e30
    x1 = y1 = z1 = -1e30
    for t in tris:
        for k in (3, 6, 9):
            a, b, c = t[k], t[k + 1], t[k + 2]
            if a < x0: x0 = a
            if a > x1: x1 = a
            if b < y0: y0 = b
            if b > y1: y1 = b
            if c < z0: z0 = c
            if c > z1: z1 = c
    return (x0, y0, z0, x1, y1, z1)


def analyse_stl(tris):
    """Facts about the source mesh, for the panel. Welds at a tolerance
    relative to the diagonal, then checks that every edge is used exactly twice
    -- which is what 'watertight' means and what makes the enclosed volume a
    real number rather than a hopeful one."""
    x0, y0, z0, x1, y1, z1 = stl_bounds(tris)
    diag = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2 + (z1 - z0) ** 2)
    inv = 1.0 / max(diag * 1e-6, 1e-12)
    vid = {}
    idx = []
    for t in tris:
        tri = []
        for k in (3, 6, 9):
            key = (int(t[k] * inv), int(t[k + 1] * inv), int(t[k + 2] * inv))
            i = vid.get(key)
            if i is None:
                i = len(vid)
                vid[key] = i
            tri.append(i)
        idx.append(tri)
    edges = {}
    for a, b, c in idx:
        for u, v in ((a, b), (b, c), (c, a)):
            e = (u, v) if u < v else (v, u)
            edges[e] = edges.get(e, 0) + 1
    manifold = all(v == 2 for v in edges.values())
    vol = area = 0.0
    for t in tris:
        ax, ay, az = t[3], t[4], t[5]
        bx, by, bz = t[6], t[7], t[8]
        cx, cy, cz = t[9], t[10], t[11]
        vol += (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx)
                + az * (bx * cy - by * cx))
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        mx = uy * vz - uz * vy
        my = uz * vx - ux * vz
        mz = ux * vy - uy * vx
        area += math.sqrt(mx * mx + my * my + mz * mz)
    return {
        'src_tris': len(tris), 'src_verts': len(vid), 'edges': len(edges),
        'watertight': manifold,
        'bbox': (x1 - x0, y1 - y0, z1 - z0),
        'volume': abs(vol) / 6.0, 'area': area / 2.0,
    }


def cluster_decimate(tris, ncell):
    """Vertex clustering: snap every corner to a grid cell, keep one
    representative per cell, drop triangles whose corners collapse together.

    Clustering rather than quadric edge collapse because this is O(n) in one
    pass where the collapse is a priority queue over 364,000 edges and minutes
    of Python. Measured against the source at the shipped LODs, the enclosed
    volume moves by under 1% and the surface area by under 2%, which for a
    150-pixel-tall render is far below anything visible.
    """
    x0, y0, z0, x1, y1, z1 = stl_bounds(tris)
    ext = max(x1 - x0, y1 - y0, z1 - z0) or 1.0
    s = ncell / ext
    nx = int((x1 - x0) * s) + 2
    ny = int((y1 - y0) * s) + 2

    # The representative is the area-weighted mean of the corners that landed
    # in the cell, not the cell centre. The centre quantises every surface onto
    # a lattice and the model comes out visibly stair-stepped; the mean leaves
    # flat panels flat and keeps long straight edges straight.
    acc = {}
    keys = []
    for t in tris:
        ux, uy, uz = t[6] - t[3], t[7] - t[4], t[8] - t[5]
        vx, vy, vz = t[9] - t[3], t[10] - t[4], t[11] - t[5]
        cx = uy * vz - uz * vy
        cy = uz * vx - ux * vz
        cz = ux * vy - uy * vx
        w = math.sqrt(cx * cx + cy * cy + cz * cz) * 0.5 + 1e-9
        tk = []
        for k in (3, 6, 9):
            key = ((int((t[k + 2] - z0) * s) * ny
                    + int((t[k + 1] - y0) * s)) * nx + int((t[k] - x0) * s))
            a = acc.get(key)
            if a is None:
                acc[key] = [t[k] * w, t[k + 1] * w, t[k + 2] * w, w]
            else:
                a[0] += t[k] * w
                a[1] += t[k + 1] * w
                a[2] += t[k + 2] * w
                a[3] += w
            tk.append(key)
        keys.append((tk[0], tk[1], tk[2], cx, cy, cz))

    order = {}
    verts = []
    for key, a in acc.items():
        order[key] = len(verts)
        verts.append((a[0] / a[3], a[1] / a[3], a[2] / a[3]))

    seen = set()
    faces = []
    for a, b, c, fnx, fny, fnz in keys:
        if a == b or b == c or a == c:
            continue                       # collapsed to an edge or a point
        ia, ib, ic = order[a], order[b], order[c]
        # canonical rotation: kills exact duplicates without touching winding
        if ia <= ib and ia <= ic:
            k = (ia, ib, ic)
        elif ib <= ia and ib <= ic:
            k = (ib, ic, ia)
        else:
            k = (ic, ia, ib)
        if k in seen:
            continue
        seen.add(k)
        # Re-orient against the original facet normal. Clustering can reverse a
        # winding, and on a backface-culled render a reversed facet is a hole
        # you can see straight through the model.
        pa, pb, pc = verts[ia], verts[ib], verts[ic]
        ux, uy, uz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
        vx, vy, vz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
        mx = uy * vz - uz * vy
        my = uz * vx - ux * vz
        mz = ux * vy - uy * vx
        faces.append((ia, ib, ic) if mx * fnx + my * fny + mz * fnz >= 0
                     else (ia, ic, ib))
    return verts, faces


def decimate_to(tris, target, tol=0.06, probes=5):
    """Find the grid resolution that lands nearest `target` faces.

    Not a binary search. Face count over a surface grows as the *square* of the
    grid resolution, so one probe predicts the answer: n' = n * sqrt(target/f).
    That converges in two or three passes where bisecting the range took nine,
    and each pass is a full clustering of a quarter-million triangles. Keeps
    the best seen rather than the last, since the count is only monotone in the
    grid size, not smooth in it.
    """
    n = 40
    best = None
    for _ in range(probes):
        v, f = cluster_decimate(tris, n)
        cnt = len(f)
        if best is None or abs(cnt - target) < abs(best[2] - target):
            best = (v, f, cnt, n)
        if abs(cnt - target) <= tol * target:
            break
        nn = int(round(n * math.sqrt(target / float(max(cnt, 1)))))
        nn = max(4, min(400, nn))
        if nn == n:
            nn = n + (1 if cnt < target else -1)
        n = nn
    return best[0], best[1], best[3]


def voxel_solid(tris, res, density=1.5, want_volume=None):
    """Burn the dense mesh into an occupancy grid, flood the outside, and call
    everything unreached solid.

    The sampling lattice on each triangle is sized from its LONGEST EDGE, not
    its area. Sizing from area leaks: an STL like this is full of slivers --
    triangles whose area is near zero but whose edges run across a dozen voxels
    -- and those get three samples, leave their span unmarked, and let the
    outside flood walk straight into the interior. The failure is silent: the
    grid still looks like a model, 'solid' just quietly comes to mean 'shell',
    and occlusion stops seeing anything it should. Caught by checking the
    interior voxel count against the enclosed volume, which is the sort of
    cross-check worth building in.
    """
    x0, y0, z0, x1, y1, z1 = stl_bounds(tris)
    ext = max(x1 - x0, y1 - y0, z1 - z0) or 1.0
    s = res / ext
    nx = int((x1 - x0) * s) + 3
    ny = int((y1 - y0) * s) + 3
    nz = int((z1 - z0) * s) + 3
    cell = ext / res
    ox, oy, oz = x0 - cell, y0 - cell, z0 - cell
    grid = bytearray(nx * ny * nz)
    for t in tris:
        ax, ay, az = t[3], t[4], t[5]
        ux, uy, uz = t[6] - ax, t[7] - ay, t[8] - az
        vx, vy, vz = t[9] - ax, t[10] - ay, t[11] - az
        wx, wy, wz = vx - ux, vy - uy, vz - uz
        e2 = max(ux * ux + uy * uy + uz * uz,
                 vx * vx + vy * vy + vz * vz,
                 wx * wx + wy * wy + wz * wz)
        m = int(math.sqrt(e2) * density * s) + 1
        for ia in range(m + 1):
            fa = ia / m
            for ib in range(m + 1 - ia):
                fb = ib / m
                i = int((ax + ux * fa + vx * fb - ox) * s)
                j = int((ay + uy * fa + vy * fb - oy) * s)
                k = int((az + uz * fa + vz * fb - oz) * s)
                grid[(k * ny + j) * nx + i] = 1
    shell = sum(grid)

    nxy = nx * ny
    total = nxy * nz
    out = bytearray(total)
    q = deque()

    def seed(p):
        if not grid[p] and not out[p]:
            out[p] = 1
            q.append(p)

    for j in range(ny):
        for i in range(nx):
            seed((0 * ny + j) * nx + i)
            seed(((nz - 1) * ny + j) * nx + i)
    for k in range(nz):
        for i in range(nx):
            seed((k * ny + 0) * nx + i)
            seed((k * ny + ny - 1) * nx + i)
        for j in range(ny):
            seed((k * ny + j) * nx + 0)
            seed((k * ny + j) * nx + nx - 1)
    while q:
        p = q.popleft()
        k, rem = divmod(p, nxy)
        j, i = divmod(rem, nx)
        if i > 0:
            seed(p - 1)
        if i < nx - 1:
            seed(p + 1)
        if j > 0:
            seed(p - nx)
        if j < ny - 1:
            seed(p + nx)
        if k > 0:
            seed(p - nxy)
        if k < nz - 1:
            seed(p + nxy)
    solid = bytearray(total)
    for p in range(total):
        if not out[p]:
            solid[p] = 1
    nsolid = sum(solid)
    # Cross-check, because the leak this function is written to avoid is
    # *silent*: a leaked grid still looks like a model, it just stops having an
    # inside. The mesh's own enclosed volume says how many cells should be
    # solid; a conservative voxelisation overshoots that by about half a cell
    # of thickness over the whole surface, and never undershoots. Coming in
    # low means the flood got in.
    ok = True
    if want_volume:
        expect = want_volume * s ** 3
        ok = nsolid >= expect * 0.92
    return solid, (nx, ny, nz), (ox, oy, oz), s, shell, nsolid, ok


def hemi_dirs(nx, ny, nz):
    """Thirteen directions in the hemisphere about a normal: the axis plus two
    rings. Fixed rather than randomised, so a face gets the same answer every
    run and the cached occlusion means something."""
    ux, uy, uz = (0.0, 0.0, 1.0) if abs(nz) < 0.9 else (1.0, 0.0, 0.0)
    ax = uy * nz - uz * ny
    ay = uz * nx - ux * nz
    az = ux * ny - uy * nx
    al = math.sqrt(ax * ax + ay * ay + az * az) or 1.0
    ax, ay, az = ax / al, ay / al, az / al
    bx = ny * az - nz * ay
    by = nz * ax - nx * az
    bz = nx * ay - ny * ax
    dirs = [(nx, ny, nz)]
    for rad, cnt, ph in ((0.55, 6, 0.0), (0.90, 6, 0.4)):
        ct = math.sqrt(1.0 - rad * rad)
        for i in range(cnt):
            th = 2 * math.pi * i / cnt + ph
            c, sn = math.cos(th) * rad, math.sin(th) * rad
            dirs.append((nx * ct + ax * c + bx * sn,
                         ny * ct + ay * c + by * sn,
                         nz * ct + az * c + bz * sn))
    return dirs


def face_ao(verts, faces, solid, dims, org, s, radius_cells=4.0, steps=3):
    """Per-face occlusion: fire the hemisphere, march each ray out to the
    radius, and count the ones that end up inside solid. This is occlusion in
    the real sense -- it sees the arm hanging in front of the chest, which a
    curvature estimate never can, and that is the whole reason for the grid."""
    nxg, nyg, nzg = dims
    ox, oy, oz = org
    inv = 1.0 / s
    out = []
    for ia, ib, ic in faces:
        pa, pb, pc = verts[ia], verts[ib], verts[ic]
        cx = (pa[0] + pb[0] + pc[0]) / 3.0
        cy = (pa[1] + pb[1] + pc[1]) / 3.0
        cz = (pa[2] + pb[2] + pc[2]) / 3.0
        ux, uy, uz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
        vx, vy, vz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
        mx = uy * vz - uz * vy
        my = uz * vx - ux * vz
        mz = ux * vy - uy * vx
        ml = math.sqrt(mx * mx + my * my + mz * mz) or 1.0
        dirs = hemi_dirs(mx / ml, my / ml, mz / ml)
        hit = 0
        for dx, dy, dz in dirs:
            for st in range(1, steps + 1):
                r = radius_cells * st / steps * inv
                i = int((cx + dx * r - ox) * s)
                j = int((cy + dy * r - oy) * s)
                k = int((cz + dz * r - oz) * s)
                if 0 <= i < nxg and 0 <= j < nyg and 0 <= k < nzg \
                        and solid[(k * nyg + j) * nxg + i]:
                    hit += 1
                    break              # blocked: the rest of this ray is moot
        out.append(1.0 - hit / float(len(dirs)))
    return out


def heat_field(verts, faces, ao, core, height):
    """Per-facet temperature in [0, 1]: reactor proximity plus trapping.

    Baked at build time and cached, so the thermal channel costs the shader a
    single list index at frame time -- the same trick occlusion already uses.
    Normalised against its own maximum rather than against a theoretical one,
    because the maximum is the skin nearest the plant and that is exactly the
    thing the ramp's top end should mean.
    """
    if core is None or not faces:
        return [0.0] * len(faces)
    kx, ky, kz = core
    r2 = (REACTOR_R * height) ** 2 or 1.0
    out = []
    for fi, (ia, ib, ic) in enumerate(faces):
        pa, pb, pc = verts[ia], verts[ib], verts[ic]
        dx = (pa[0] + pb[0] + pc[0]) / 3.0 - kx
        dy = (pa[1] + pb[1] + pc[1]) / 3.0 - ky
        dz = (pa[2] + pb[2] + pc[2]) / 3.0 - kz
        q = 1.0 / (1.0 + (dx * dx + dy * dy + dz * dz) / r2)
        trap = 1.0 - (ao[fi] if fi < len(ao) else 1.0)
        out.append(REACTOR_MIX * q + (1.0 - REACTOR_MIX) * trap)
    hi = max(out) or 1.0
    return [min(1.0, v / hi) for v in out]


def shadow_bands(verts, nbands=SHADOW_BANDS):
    """Ground shadow as a stack of height bands, each hulled separately.

    One hull over the whole model is a blob that loses the gap between the
    legs. Banding by height keeps the legs apart and the arms distinct for
    almost nothing, and because the model is static under an orbiting camera --
    the turntable moves the eye, not the mech -- the whole thing is computed
    once at load and only projected at frame time.
    """
    if not verts or SUN[2] <= 0.05:
        return []
    z0 = min(v[2] for v in verts)
    z1 = max(v[2] for v in verts)
    span = (z1 - z0) or 1.0
    buckets = [[] for _ in range(nbands)]
    for x, y, z in verts:
        b = int((z - z0) / span * nbands)
        if b >= nbands:
            b = nbands - 1
        t = z / SUN[2]
        buckets[b].append((x - SUN[0] * t, y - SUN[1] * t))
    out = []
    for b in buckets:
        h = hull2d(b)
        if len(h) >= 3:
            out.append(h)
    return out


class _MeshView:
    """Just enough of Mesh's shape for Part to consume an indexed triangle
    soup. The loft builders and the STL loader produce the same two fields, so
    Part does not need to know which it is looking at."""

    __slots__ = ('v', 'f')

    def __init__(self, verts, faces, mat):
        self.v = verts
        self.f = [(f, mat) for f in faces]


def print_mesh_report(src, lods):
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
    # Mass is canon and density is derived, not the other way round.
    print('  mass          %14.1f   t   (%s %s, per Sarna)'
          % (src['built_mass'], CANON['name'], CANON['config']))
    print('  mean density  %14.3f   t/m3  derived: canon mass / measured'
          % src.get('built_density', 0.0))
    print()
    print('SECTIONS   segmented off the occupancy grid by erosion + watershed')
    print('  %-8s %10s %10s' % ('section', 'volume m3', 'mass t'))
    share = src.get('sec_share') or []
    for i, sec in enumerate(SECTIONS):
        if i < len(share):
            print('  %-8s %10.1f %10.1f'
                  % (SECTION_NAMES[sec], share[i] * src['built_volume'],
                     share[i] * src['built_mass']))
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


class Model:
    """A loaded, decimated, occluded mesh at one level of detail, normalised so
    it stands MODEL_H tall on z = 0 and centred on the vertical axis."""

    __slots__ = ('verts', 'faces', 'ao', 'report', 'shadow', 'sec', 'temp')

    def __init__(self, verts, faces, ao, report, sec=None, temp=None):
        self.verts = verts
        self.faces = faces
        self.ao = ao
        self.report = report
        self.sec = sec if sec is not None else bytearray(len(faces))
        self.temp = temp if temp is not None else [0.0] * len(faces)
        self.shadow = shadow_bands(verts)


def normalise(verts, up='z'):
    """Stand the model on the ground, centre it on the vertical axis, scale it
    to MODEL_H. Returns the vertices and the metres-per-source-unit factor,
    which is what lets the panel quote a real-world volume for a mesh whose own
    units are millimetres of printed plastic."""
    if up == 'y':
        verts = [(v[0], -v[2], v[1]) for v in verts]
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    z0 = min(zs)
    k = MODEL_H / ((max(zs) - z0) or 1.0)
    return [((v[0] - cx) * k, (v[1] - cy) * k, (v[2] - z0) * k)
            for v in verts], k


# --- segmentation -----------------------------------------------------------
# Split the mesh into the machine's own limbs, off the occupancy grid that was
# already built for occlusion.
#
# The first attempt sliced the grid horizontally and took connected components
# per slice -- a Reeb graph of the height function. It found the legs and the
# missile pods cleanly and FAILED on the arms, giving one arm 2.9% of the hull
# and the other 0.9%: above the hips an arm and the side of the torso fall in
# the same 2D component wherever they overlap in plan view, and no amount of
# per-slice connectivity will part them. That is measured, not suspected.
#
# Morphology fits the shape of the problem instead. A mech's joints are its
# narrow places -- ankle, knee, hip, shoulder, elbow -- so erosion breaks them
# first and the limbs fall off on their own. Erode to a core, take 3D connected
# components as seeds, then grow every seed at once back over the full solid.
# The simultaneous flood is a watershed: it assigns each cell to whichever core
# reaches it first, which puts the boundary in the joint where it belongs.
#
# The torso is deliberately left whole -- everything that is not a limb is
# TORSO. Splitting it into centre and side torsos is a later job.
SECTIONS = ('TORSO', 'LA', 'RA', 'LL', 'RL')
SECTION_NAMES = {'TORSO': 'torso', 'LA': 'arm L', 'RA': 'arm R',
                 'LL': 'leg L', 'RL': 'leg R'}
# Erosion depth is NOT a constant. It has to scale with the voxel resolution --
# at 96^3 a depth of 6 parts the limbs cleanly, at the default 80^3 the same
# depth erases them and leaves two lumps. So sweep it, and let bilateral
# symmetry decide: the correct depth is the deepest one that still finds at
# least two outboard components on EACH side of the mirror plane, which is
# what a mech with two arms and two legs must produce. Nothing in the search
# knows the machine is symmetric, so when it agrees, that agreement is
# evidence rather than assumption.
ERODE_SWEEP = (8, 7, 6, 5, 4, 3, 2)
SEG_MIN_CELLS = 40
SEG_LAT_FRAC = 0.10       # outboard means this far off the mirror plane


def mirror_plane(solid, dims, step=3.0):
    """The vertical plane that best maps the solid onto itself.

    Needed because the obvious shortcut -- lateral axis = whichever way the
    legs are furthest apart -- is a coin flip on this mesh: the Mad Cat is
    modelled mid-stride and its legs are separated diagonally, 35.3 grid units
    one way against 38.1 the other. Structure is symmetric even when pose is
    not, and the symmetric mass outweighs the stride.

    Returns (lateral_x, lateral_y, centre_x, centre_y, score). The score is
    reported rather than asserted: it comes out at 0.686 against a worst case
    of 0.327, and it is NOT 1.0 precisely because the stride is real.
    """
    nx, ny, nz = dims
    nxy = nx * ny
    cells = []
    for p in range(len(solid)):
        if solid[p]:
            k, rem = divmod(p, nxy)
            j, i = divmod(rem, nx)
            cells.append((i, j, k))
    if not cells:
        return 1.0, 0.0, 0.0, 0.0, 0.0
    occ = set(cells)
    cx = sum(c[0] for c in cells) / len(cells)
    cy = sum(c[1] for c in cells) / len(cells)
    best = None
    ang = 0.0
    while ang < 180.0:            # a plane and its opposite are one plane
        a = math.radians(ang)
        ux, uy = math.cos(a), math.sin(a)
        hit = 0
        for i, j, k in cells:
            dx, dy = i - cx, j - cy
            d = 2.0 * (dx * ux + dy * uy)
            if (int(round(cx + dx - d * ux)),
                    int(round(cy + dy - d * uy)), k) in occ:
                hit += 1
        sc = hit / float(len(cells))
        if best is None or sc > best[0]:
            best = (sc, ux, uy)
        ang += step
    return best[1], best[2], cx, cy, best[0]


def _erode(solid, dims, n):
    nx, ny, nz = dims
    nxy = nx * ny
    cur = solid
    for _ in range(n):
        out = bytearray(len(cur))
        for p in range(len(cur)):
            if not cur[p]:
                continue
            k, rem = divmod(p, nxy)
            j, i = divmod(rem, nx)
            if (i == 0 or j == 0 or k == 0 or i == nx - 1 or j == ny - 1
                    or k == nz - 1):
                continue
            if (cur[p - 1] and cur[p + 1] and cur[p - nx] and cur[p + nx]
                    and cur[p - nxy] and cur[p + nxy]):
                out[p] = 1
        cur = out
    return cur


def _components_3d(grid, dims, minsize):
    nx, ny, nz = dims
    nxy = nx * ny
    seen = bytearray(len(grid))
    comps = []
    for start in range(len(grid)):
        if seen[start] or not grid[start]:
            continue
        q = deque([start])
        seen[start] = 1
        cells = []
        while q:
            p = q.popleft()
            cells.append(p)
            k, rem = divmod(p, nxy)
            j, i = divmod(rem, nx)
            for d, ok in ((-1, i > 0), (1, i < nx - 1), (-nx, j > 0),
                          (nx, j < ny - 1), (-nxy, k > 0), (nxy, k < nz - 1)):
                p2 = p + d
                if ok and not seen[p2] and grid[p2]:
                    seen[p2] = 1
                    q.append(p2)
        if len(cells) >= minsize:
            comps.append(cells)
    comps.sort(key=len, reverse=True)
    return comps


def segment_solid(solid, dims, note=None):
    """Label every solid cell TORSO / LA / RA / LL / RL.

    Limbs are named by measurement, never by which way the STL happens to face:
    a component is an arm or a leg by its height and how far it sits off the
    measured mirror plane, and left from right by the sign of that offset.
    """
    nx, ny, nz = dims
    nxy = nx * ny
    ux, uy, cx, cy, score = mirror_plane(solid, dims)
    if note:
        note('mirror plane %.0f%% symmetric' % (score * 100.0))
    lat_min = SEG_LAT_FRAC * max(nx, ny)
    comps = []
    stats = []
    depth_used = 0
    for depth in ERODE_SWEEP:
        core = _erode(solid, dims, depth)
        cs = _components_3d(core, dims, SEG_MIN_CELLS)
        st = []
        for ci, cells in enumerate(cs):
            sx = sy = sz = 0
            for p in cells:
                k, rem = divmod(p, nxy)
                j, i = divmod(rem, nx)
                sx += i; sy += j; sz += k
            n = float(len(cells))
            st.append({'i': ci, 'n': len(cells), 'z': (sz / n) / max(1, nz - 1),
                       'lat': (sx / n - cx) * ux + (sy / n - cy) * uy})
        left = [x for x in st[1:] if x['lat'] < -lat_min]
        right = [x for x in st[1:] if x['lat'] > lat_min]
        if len(left) >= 2 and len(right) >= 2:
            comps, stats, depth_used = cs, st, depth
            break
    if not comps:                       # nothing parted: one solid lump
        comps = _components_3d(solid, dims, SEG_MIN_CELLS)
        stats = [{'i': 0, 'n': len(comps[0]) if comps else 0, 'z': 0.5,
                  'lat': 0.0}]
    if note:
        note('limbs parted at erosion %d' % depth_used)

    # The trunk is simply the biggest core; everything is measured against it.
    lab_of = {0: 'TORSO'}
    # Pick per SIDE, never globally: taking 'the two largest remaining' picked
    # two components off the same shoulder and left the other arm unlabelled.
    for sgn, leg_tag, arm_tag in ((-1, 'LL', 'LA'), (1, 'RL', 'RA')):
        side = [x for x in stats[1:]
                if (x['lat'] < -lat_min if sgn < 0 else x['lat'] > lat_min)]
        if not side:
            continue
        leg = min(side, key=lambda x: x['z'])       # a leg reaches the ground
        lab_of[leg['i']] = leg_tag
        rest = [x for x in side if x is not leg and x['z'] > leg['z']]
        if rest:                                    # an arm hangs, it does not
            lab_of[max(rest, key=lambda x: x['n'])['i']] = arm_tag
    for x in stats:
        lab_of.setdefault(x['i'], 'TORSO')

    idx = dict((s, i) for i, s in enumerate(SECTIONS))
    lab = bytearray(len(solid))
    q = deque()
    for ci, cells in enumerate(comps):
        v = idx[lab_of[ci]] + 1
        for p in cells:
            lab[p] = v
            q.append(p)
    while q:                       # one flood, all cores at once: a watershed
        p = q.popleft()
        v = lab[p]
        k, rem = divmod(p, nxy)
        j, i = divmod(rem, nx)
        for d, ok in ((-1, i > 0), (1, i < nx - 1), (-nx, j > 0),
                      (nx, j < ny - 1), (-nxy, k > 0), (nxy, k < nz - 1)):
            p2 = p + d
            if ok and solid[p2] and not lab[p2]:
                lab[p2] = v
                q.append(p2)
    counts = [0] * len(SECTIONS)
    for v in lab:
        if v:
            counts[v - 1] += 1
    return lab, counts, (ux, uy, cx, cy, score)


def face_sections(verts, faces, lab, dims, org, s):
    """Section index per facet, from the labelled cell its centroid sits in."""
    nx, ny, nz = dims
    ox, oy, oz = org
    nxy = nx * ny
    out = bytearray(len(faces))
    for fi, (ia, ib, ic) in enumerate(faces):
        pa, pb, pc = verts[ia], verts[ib], verts[ic]
        i = int(((pa[0] + pb[0] + pc[0]) / 3.0 - ox) * s)
        j = int(((pa[1] + pb[1] + pc[1]) / 3.0 - oy) * s)
        k = int(((pa[2] + pb[2] + pc[2]) / 3.0 - oz) * s)
        v = 0
        if 0 <= i < nx and 0 <= j < ny and 0 <= k < nz:
            v = lab[(k * ny + j) * nx + i]
        if not v:
            # A facet centroid can land just outside the solid on a thin
            # panel; take the nearest labelled cell in a small neighbourhood
            # rather than silently calling it torso.
            best = None
            for dk in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    for di in (-1, 0, 1):
                        i2, j2, k2 = i + di, j + dj, k + dk
                        if 0 <= i2 < nx and 0 <= j2 < ny and 0 <= k2 < nz:
                            w = lab[(k2 * ny + j2) * nx + i2]
                            if w:
                                best = w
                                break
                    if best:
                        break
                if best:
                    break
            v = best or 1
        out[fi] = v - 1
    return out


def section_centroid(lab, dims, org, s, si):
    """Centroid of one labelled section, back in SOURCE coordinates.

    `s` is cells per source unit, the same convention face_sections uses, so
    the way back out is a division.
    """
    nx, ny, _nz = dims
    nxy = nx * ny
    tag = si + 1
    sx = sy = sz = 0
    n = 0
    for p, v in enumerate(lab):
        if v == tag:
            k, rem = divmod(p, nxy)
            j, i = divmod(rem, nx)
            sx += i
            sy += j
            sz += k
            n += 1
    if not n:
        return None
    return (org[0] + (sx / float(n) + 0.5) / s,
            org[1] + (sy / float(n) + 0.5) / s,
            org[2] + (sz / float(n) + 0.5) / s)


def _section_share(counts):
    """Fraction of the enclosed volume in each section, from VOXEL counts.

    An earlier version summed signed tetrahedron volumes per section, on the
    argument that the divergence theorem would sort out the open boundary.
    It does not: the fan integral is only volume for a CLOSED surface, and for
    an open patch the answer depends on where the patch's rim sits relative to
    the origin. The evidence was the arms coming out 3.1 m3 against 5.8 m3 --
    a near 2:1 split between two limbs whose facet counts agreed to within 4%.

    Counting labelled cells has no such problem. The watershed assigns every
    solid cell to exactly one section, so the counts are a true partition of
    the enclosed volume, and the legs now agree exactly.
    """
    tot = float(sum(counts)) or 1.0
    return [c / tot for c in counts]


def build_model(tris, src, target, up, ao_radius, grid, note=None):
    """Decimate, occlude, normalise. Occlusion is measured in the source mesh's
    own coordinates -- the voxel grid is built from the source triangles, and
    the decimated vertices have not been moved yet -- so the two never have to
    agree on a transform."""
    (solid, dims, org, s, shell, sol, sealed, vox, seclab, seccount,
     core) = grid
    if note:
        note('decimating %s facets to %s' % (commas(len(tris)), commas(target)))
    verts, faces, ncell = decimate_to(tris, target)
    if note:
        note('occluding %s facets' % commas(len(faces)))
    ao = face_ao(verts, faces, solid, dims, org, s, ao_radius)
    # Sections, like occlusion, are read in the SOURCE mesh's coordinates --
    # before normalise() moves anything -- so the labelled grid and the
    # decimated vertices never need to agree on a transform.
    sec = face_sections(verts, faces, seclab, dims, org, s)
    # Normalise against the mesh's own open-sky value rather than against 1.0.
    # Theory says an unoccluded facet sees the whole hemisphere, but a facet on
    # a real machine is surrounded by panel gaps, bolt heads and its own
    # neighbours, so the raw mean here is 0.35 and shading straight off it
    # drags the entire model into shadow. The 85th percentile is what this
    # surface actually achieves when nothing is in the way; that is the number
    # worth calling 'open'.
    ref = sorted(ao)[int(len(ao) * 0.85)] if ao else 1.0
    if ref > 1e-3:
        ao = [min(1.0, a / ref) for a in ao]
    # Heat, while the vertices are still in source coordinates -- the reactor
    # centroid came out of the voxel grid and lives in the same frame.
    src_h_raw = ((src['bbox'][1] if up == 'y' else src['bbox'][2])
                 if src.get('bbox') else 0.0) or 1.0
    temp = heat_field(verts, faces, ao, core, src_h_raw)
    verts, scale = normalise(verts, up)
    # Scale must come from the SOURCE height, not the decimated one. Decimation
    # pulls the extreme vertices in slightly, so a per-LOD scale made the
    # machine's displacement -- and now its derived density -- change every
    # time d was pressed: 142.4 m3 at low detail against 138.8 at high, for
    # one unchanging object. The source is the truth; the LOD is an
    # approximation of it and does not get a vote on how big the mech is.
    if src.get('bbox'):
        # bbox is in SOURCE axes, so pick the one that 'up' will become.
        src_h = src['bbox'][1] if up == 'y' else src['bbox'][2]
        if src_h:
            scale = MODEL_H / src_h

    # Decimated volume and area, for the reduction report.
    dvol = darea = 0.0
    # Area per section as well as volume. Armour is a skin, so when the panel
    # spreads Sarna's twelve tons over the machine it has to spread it by
    # surface, not by displacement -- an arm has far more skin per cubic metre
    # than the torso does, and distributing by volume would have quietly
    # armoured the torso at the limbs' expense.
    sec_area = [0.0] * len(SECTIONS)
    for fi, (ia, ib, ic) in enumerate(faces):
        pa, pb, pc = verts[ia], verts[ib], verts[ic]
        dvol += (pa[0] * (pb[1] * pc[2] - pb[2] * pc[1])
                 - pa[1] * (pb[0] * pc[2] - pb[2] * pc[0])
                 + pa[2] * (pb[0] * pc[1] - pb[1] * pc[0]))
        ux, uy, uz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
        vx, vy, vz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
        mx = uy * vz - uz * vy
        my = uz * vx - ux * vz
        mz = ux * vy - uy * vx
        fa = math.sqrt(mx * mx + my * my + mz * mz)
        darea += fa
        si = sec[fi]
        if si < len(sec_area):
            sec_area[si] += fa
    dvol = abs(dvol) / 6.0
    darea /= 2.0
    _atot = sum(sec_area) or 1.0
    sec_area = [a / _atot for a in sec_area]

    report = dict(src)
    report.update({
        'faces': len(faces), 'verts': len(verts), 'grid': ncell,
        'target': target, 'vox': vox, 'ao_radius': ao_radius,
        'shell_cells': shell, 'solid_cells': sol, 'sealed': sealed,
        'scale': scale, 'up': up,
        # Volume as built: the source mesh is millimetres of printed plastic,
        # so scale it to the height the renderer stands it at and the number
        # becomes a real displacement in cubic metres -- and, at the plate
        # density the built-in model is calibrated to, a real tonnage.
        # As-built figures come from the SOURCE volume scaled up, not from the
        # decimated hull: the source is the truth and the decimation is an
        # approximation of it, so quoting the approximation would make the
        # displacement of the machine change every time you press d.
        'built_volume': src['volume'] * scale ** 3,
        'built_area': src['area'] * scale ** 2,
        # Mass is Sarna's 75 tons, not a density guess. The density is the
        # DERIVED figure now: canon tonnage over measured displacement. That
        # is the right way round -- the wiki owns the tonnage, the mesh owns
        # the geometry, and neither is asked to supply the other's number.
        'built_mass': float(CANON['mass_t']),
        'built_density': (float(CANON['mass_t']) / (src['volume'] * scale ** 3)
                          if src.get('volume') else 0.0),
        'sec_share': _section_share(seccount),
        'sec_area': sec_area,
        'reactor': list(core) if core else None,
        'lod_volume': dvol, 'lod_area': darea,
        'vol_err': (dvol / (src['volume'] * scale ** 3) - 1.0) * 100.0
                   if src.get('volume') else 0.0,
        'area_err': (darea / (src['area'] * scale ** 2) - 1.0) * 100.0
                    if src.get('area') else 0.0,
    })
    return Model(verts, faces, ao, report, sec, temp)


def _cache_path(path, target, up, ao_radius, vox):
    st = os.stat(path)
    return '%s.%d-%d-%s-%g-%d.mmesh' % (path, target, st.st_size, up,
                                        ao_radius, vox)


def _cache_read(cp, mtime):
    try:
        d = open(cp, 'rb').read()
    except OSError:
        return None
    try:
        if len(d) < CACHE_HLEN or d[:len(CACHE_MAGIC)] != CACHE_MAGIC:
            return None
        ver, order, jlen, nv, nf, mt = struct.unpack(
            CACHE_HEAD, d[len(CACHE_MAGIC):CACHE_HLEN])
        if ver != CACHE_VER or order != (sys.byteorder != 'little'):
            return None
        if abs(mt - mtime) > 1e-6:
            return None
        o = CACHE_HLEN
        report = json.loads(d[o:o + jlen].decode('utf-8'))
        o += jlen
        va = array.array('f')
        va.frombytes(d[o:o + nv * 12])
        o += nv * 12
        fa = array.array('i')
        fa.frombytes(d[o:o + nf * 12])
        o += nf * 12
        aa = array.array('f')
        aa.frombytes(d[o:o + nf * 4])
        o += nf * 4
        sec = bytearray(d[o:o + nf])
        o += nf
        ta = array.array('f')
        ta.frombytes(d[o:o + nf * 4])
        if (len(va) != nv * 3 or len(fa) != nf * 3 or len(aa) != nf
                or len(sec) != nf or len(ta) != nf):
            return None
    except Exception:
        return None       # a truncated or foreign cache just means rebuild
    verts = [(va[i * 3], va[i * 3 + 1], va[i * 3 + 2]) for i in range(nv)]
    faces = [(fa[i * 3], fa[i * 3 + 1], fa[i * 3 + 2]) for i in range(nf)]
    return Model(verts, faces, list(aa), report, sec, list(ta))


def _cache_write(cp, m, mtime):
    j = json.dumps(m.report).encode('utf-8')
    head = CACHE_MAGIC + struct.pack(
        CACHE_HEAD, CACHE_VER, sys.byteorder != 'little',
        len(j), len(m.verts), len(m.faces), mtime)
    try:
        tmp = '%s.%d.tmp' % (cp, os.getpid())
        with open(tmp, 'wb') as fh:
            fh.write(head)
            fh.write(j)
            fh.write(array.array('f', [c for v in m.verts for c in v]).tobytes())
            fh.write(array.array('i', [c for f in m.faces for c in f]).tobytes())
            fh.write(array.array('f', m.ao).tobytes())
            fh.write(bytes(m.sec))
            fh.write(array.array('f', m.temp).tobytes())
        os.replace(tmp, cp)
    except OSError:
        pass          # a read-only directory is no reason to fail to draw


def load_models(path, targets, up='z', ao_radius=4.0, vox=80, note=None,
                use_cache=True):
    """Every level of detail, from cache where possible.

    Building all three up front costs a few seconds once; building them lazily
    would put that pause in the middle of a keypress instead, which is worse.
    After the first run it is a file read.
    """
    mtime = os.stat(path).st_mtime
    out = []
    tris = None
    src = None
    grid = None
    for t in targets:
        cp = _cache_path(path, t, up, ao_radius, vox)
        m = _cache_read(cp, mtime) if use_cache else None
        if m is None:
            if tris is None:
                if note:
                    note('reading %s' % os.path.basename(path))
                tris = load_stl(path)
                if note:
                    note('analysing %s facets' % commas(len(tris)))
                src = analyse_stl(tris)
            if grid is None:
                # Once, not once per level: the occupancy grid depends only on
                # the source mesh, and rebuilding it per LOD was three
                # identical four-second passes.
                if note:
                    note('voxelising at %d^3' % vox)
                grid = voxel_solid(tris, vox, want_volume=src['volume']) + (vox,)
                if note:
                    note('segmenting limbs')
                seclab, seccount, _mir = segment_solid(grid[0], grid[1], note)
                # Where the reactor is: the centroid of the torso's own mass,
                # measured, not sited by hand. The thermal channel needs it.
                core = section_centroid(seclab, grid[1], grid[2], grid[3],
                                        SECTIONS.index('TORSO'))
                grid = grid + (seclab, seccount, core)
            m = build_model(tris, src, t, up, ao_radius, grid, note)
            if use_cache:
                _cache_write(cp, m, mtime)
        out.append(m)
    return out


# --- the mech -------------------------------------------------------------
# Coordinates: +x right, +y forward (the way the mech faces), +z up. One unit
# is roughly one metre; the machine stands 11.2 of them to the top of its
# missile racks and 6.6 to the hip.
#
# The legs are digitigrade -- reverse-jointed, the way a bird's are. Absolute
# limb angles are thigh +36 (forward and down), shin -48 (back and down), foot
# level. Each frame's rotation is stated as the *difference* from its parent's,
# so the chain cancels at the ankle and the sole lies flat however the leg is
# posed. That is what puts the knee well forward of the hip, the ankle well
# behind it, and the foot back underneath the centre of mass -- the deep Z that
# is the whole silhouette of the class. Anything shallower reads as a column.

def build_mech():
    frames = {}
    order = []

    def F(name, parent, off=(0.0, 0.0, 0.0), rot=IDENT):
        f = Frame(name, frames.get(parent), off, rot)
        frames[name] = f
        order.append(f)
        return f

    parts = []

    def P(name, frame, mesh, group):
        parts.append(Part(name, frames[frame], mesh, group))

    F('root', None, (0.0, 0.0, 0.0))
    F('pelvis', 'root', (0.0, 0.0, 6.60))
    # The pod hangs nose-down off the waist gimbal, which is what gives the
    # class its hunched, forward-leaning stance.
    F('torso', 'pelvis', (0.0, 0.80, 1.80), rx(-12))

    # ---- pelvis and waist ----
    m = Mesh()
    m.box('plate', (3.9, 2.6, 1.20), off=(0, -0.10, 0.10), bev=0.46)
    m.box('metal2', (2.2, 1.9, 1.00), off=(0, -0.15, 0.85), bev=0.32)
    m.box('plate2', (4.3, 1.0, 0.90), off=(0, -1.15, 0.05), bev=0.26)
    for s in (-1, 1):
        m.tube('metal', 0.70, 0.70, 1.05, 12, off=(s * 1.72, -0.10, -0.10),
               rot=ry(90), axis='z')
        m.tube('dark', 0.38, 0.38, 1.18, 8, off=(s * 1.72, -0.10, -0.10),
               rot=ry(90), axis='z')
    P('pelvis', 'pelvis', m, 'core')

    # ---- torso pod ----
    # Nine rings on an egg profile, 5.5 units nose to tail: blunt at the back
    # where the reactor and the heat sinks live, drawn out to a rounded point at
    # the nose. It is the single largest object in the model on purpose -- on
    # the real machine the pod is as long as the legs are tall, and shrinking it
    # is the fastest way to make a mech look like a toy.
    m = Mesh()
    prof = [(-2.55, 0.42, 0.36), (-2.15, 1.30, 1.06), (-1.45, 1.92, 1.44),
            (-0.55, 2.22, 1.60), (0.40, 2.25, 1.58), (1.25, 2.08, 1.42),
            (2.00, 1.66, 1.12), (2.55, 1.06, 0.70), (2.92, 0.30, 0.24)]

    def hullmat(k, i):
        # Panel the hull: the upper band bleaches in the sun, the flanks sit in
        # their own shadow, and one ring back from the nose is a bare collar.
        if k == 6:
            return 'metal2'
        if k == 3 and i in (8, 9):
            return 'haz_y'                # unit flash, port flank
        if k == 4 and i == 8:
            return 'red'
        return 'plate3' if 2 <= i <= 7 else ('plate2' if i in (0, 9) else 'plate')

    m.pod('plate', prof, n=10, off=(0.0, 0.20, 0.05), phase=math.pi / 10,
          matf=hullmat)
    # dorsal spine housing and heat-sink louvres
    m.box('plate2', (1.35, 3.4, 0.60), off=(0, -0.20, 1.42), bev=0.20)
    m.grid_face(((-0.55, -1.85, 1.74), (0.55, -1.85, 1.74),
                 (0.55, 1.35, 1.74), (-0.55, 1.35, 1.74)),
                1, 9, lambda i, j: 'dark' if j % 2 == 0 else None)
    # engine exhaust, aft
    for s in (-1, 1):
        m.tube('metal2', 0.50, 0.60, 0.80, 8, off=(s * 0.72, -2.55, 0.15),
               rot=rx(90), axis='z')
        m.tube('dark', 0.36, 0.36, 0.88, 8, off=(s * 0.72, -2.62, 0.15),
               rot=rx(90), axis='z')
    P('torso hull', 'torso', m, 'core')

    # ---- cockpit ----
    # Offset to port, as on the real thing: the pilot sits beside the reactor
    # rather than above it. The canopy is a blister on the shoulder of the hull,
    # and the laminate is *painted onto its own front face* with grid_face
    # rather than modelled as separate panes -- panes floated at a guessed
    # radius end up inside the blister, invisible, which is exactly what the
    # first cut of this did.
    m = Mesh()
    F('canopy', 'torso', (-1.05, 1.35, 0.58), rxyz(ax=-14, az=-11))
    m.box('plate2', (2.35, 1.85, 1.40), bev=0.36)
    m.grid_face(((-1.00, 0.95, -0.46), (1.00, 0.95, -0.46),
                 (1.00, 0.95, 0.44), (-1.00, 0.95, 0.44)),
                1, 3, lambda i, j: 'dark' if j == 1 else 'glass')
    m.box('dark', (2.10, 0.30, 0.30), off=(0, 0.86, 0.62), bev=0.06)     # brow
    m.box('metal', (2.40, 0.40, 0.20), off=(0, 0.80, -0.68), bev=0.06)   # sill
    m.tube('lamp', 0.12, 0.12, 0.14, 6, off=(-1.05, 0.88, 0.70), rot=rx(90))
    # sensor cluster, on the hull centreline beside the canopy
    m.tube('dark', 0.20, 0.16, 0.70, 8, off=(1.35, 0.55, 0.10), rot=rx(96))
    P('cockpit', 'canopy', m, 'core')

    for s, tag in ((-1, 'L'), (1, 'R')):
        # ---- shoulder yoke and missile rack ----
        # The racks sit high, aft and close inboard, cocked up and out just
        # enough to clear the pod. Splayed wide they read as ears.
        F('yoke' + tag, 'torso', (s * 1.55, -0.95, 1.05),
          rxyz(ax=9, ay=-s * 7))
        m = Mesh()
        m.box('rust', (1.15, 1.70, 1.60), off=(s * 0.40, 0, 0.40), bev=0.32)
        m.tube('metal', 0.52, 0.52, 1.45, 10, off=(s * 0.22, 0, 0.10), rot=ry(90))
        P('yoke ' + tag, 'yoke' + tag, m, 'mount')

        F('rack' + tag, 'yoke' + tag, (s * 0.85, -0.20, 1.60),
          rxyz(ax=7, ay=-s * 5))
        m = Mesh()
        RW, RD, RH = 1.95, 2.60, 1.72
        m.box('plate', (RW, RD, RH), bev=0.28)
        # Tube face: a 5x3 bore grid recessed into the front cap, drawn as its
        # own quads a hair proud of the plate so it cannot z-fight the cap.
        y = RD / 2.0 + 0.015
        m.grid_face(((-RW / 2 + 0.16, y, -RH / 2 + 0.16),
                     (RW / 2 - 0.16, y, -RH / 2 + 0.16),
                     (RW / 2 - 0.16, y, RH / 2 - 0.16),
                     (-RW / 2 + 0.16, y, RH / 2 - 0.16)),
                    5, 3, lambda i, j: 'tube', inset=0.15)
        # Hazard chevrons along the top lip and the outboard flank -- where a
        # ground crew paints them, because that is what you walk into.
        z = RH / 2.0 + 0.015
        m.grid_face(((-RW / 2, -RD / 2, z), (RW / 2, -RD / 2, z),
                     (RW / 2, -RD / 2 + 0.60, z), (-RW / 2, -RD / 2 + 0.60, z)),
                    8, 1, lambda i, j: 'haz_y' if i % 2 == 0 else 'haz_k')
        m.grid_face(((-RW / 2, RD / 2 - 0.60, z), (RW / 2, RD / 2 - 0.60, z),
                     (RW / 2, RD / 2, z), (-RW / 2, RD / 2, z)),
                    8, 1, lambda i, j: 'haz_y' if i % 2 else 'haz_k')
        xf = s * (RW / 2.0 + 0.015)
        m.grid_face(((xf, -RD / 2, -RH / 2 + 0.25), (xf, RD / 2, -RH / 2 + 0.25),
                     (xf, RD / 2, -RH / 2 + 0.62), (xf, -RD / 2, -RH / 2 + 0.62)),
                    10, 1, lambda i, j: 'haz_y' if i % 2 else 'haz_k')
        # reload hatch and unit flash
        m.box('metal2', (1.05, 0.06, 0.85), off=(-s * 0.35, -RD / 2 - 0.02, 0.05))
        m.box('red', (0.38, 0.06, 0.38), off=(s * 0.62, -RD / 2 - 0.04, -0.42))
        P('LRM rack ' + tag, 'rack' + tag, m, 'weapon')

        # ---- arm ----
        # Shoulder ball, upper arm splayed outward and canted forward, elbow,
        # forearm, and a laser pod with a lens on the muzzle. The pods hang to
        # about knee height, which is where the reference carries them.
        F('sh' + tag, 'torso', (s * 2.25, -0.30, -0.20), rxyz(ax=4, ay=-s * 14))
        m = Mesh()
        m.tube('metal', 0.72, 0.72, 1.05, 12, off=(0, 0, 0.05), rot=ry(90))
        m.tube('dark', 0.42, 0.42, 1.16, 8, off=(0, 0, 0.05), rot=ry(90))
        m.box('plate', (1.05, 1.45, 1.90), off=(s * 0.30, 0, -0.85), bev=0.30,
              taper=0.86)
        P('shoulder ' + tag, 'sh' + tag, m, 'mount')

        F('elb' + tag, 'sh' + tag, (0.0, 0.0, -1.95), rxyz(ax=10, ay=s * 9))
        m = Mesh()
        m.tube('metal2', 0.50, 0.50, 0.95, 10, off=(0, 0, 0.05), rot=ry(90))
        m.box('plate2', (0.92, 1.20, 1.60), off=(0, 0.02, -0.90), bev=0.26)
        # hydraulic ram down the back of the forearm
        m.tube('metal', 0.14, 0.14, 1.30, 8, off=(0, -0.68, -0.80))
        m.tube('lamp', 0.10, 0.10, 0.55, 6, off=(0, -0.68, -0.32))
        P('forearm ' + tag, 'elb' + tag, m, 'limb')

        F('gun' + tag, 'elb' + tag, (0.0, 0.14, -1.95), rxyz(ax=5))
        m = Mesh()
        m.pod('plate', [(-0.85, 0.68, 0.60), (-0.22, 0.90, 0.78),
                        (0.62, 0.88, 0.76), (1.05, 0.66, 0.56)],
              n=8, axis='z', phase=math.pi / 8)
        # muzzle: recessed barrel, dark throat, hot lens
        m.tube('metal2', 0.48, 0.38, 0.60, 10, off=(0, 0.05, -1.18))
        m.tube('dark', 0.32, 0.32, 0.16, 10, off=(0, 0.05, -1.50))
        m.tube('lamp', 0.20, 0.20, 0.06, 10, off=(0, 0.05, -1.57))
        m.grid_face(((-0.55, 0.92, 0.10), (0.55, 0.92, 0.10),
                     (0.55, 0.92, 0.42), (-0.55, 0.92, 0.42)),
                    6, 1, lambda i, j: 'haz_y' if i % 2 else 'haz_k')
        P('laser pod ' + tag, 'gun' + tag, m, 'weapon')

        # ---- leg ----
        F('hip' + tag, 'pelvis', (s * 1.75, -0.10, 0.0),
          rxyz(ax=36, ay=-s * 5))
        m = Mesh()
        m.tube('metal', 0.64, 0.64, 1.10, 12, off=(0, 0, 0), rot=ry(90))
        m.box('plate', (1.30, 1.32, 2.90), off=(0, 0.06, -1.55), bev=0.34,
              taper=0.84)
        m.box('plate2', (1.36, 0.52, 1.90), off=(0, 0.70, -1.60), bev=0.20)
        m.box('rust2', (0.48, 0.40, 2.30), off=(s * 0.70, -0.56, -1.55), bev=0.12)
        P('thigh ' + tag, 'hip' + tag, m, 'limb')

        F('knee' + tag, 'hip' + tag, (0.0, 0.0, -3.00), rx(-84))
        m = Mesh()
        # Knee cowl: the surface that takes the weather, so it takes the oxide.
        # It also projects well forward, which is most of what announces a
        # reverse joint from side on.
        m.tube('metal', 0.72, 0.72, 1.15, 12, off=(0, 0, 0.05), rot=ry(90))
        m.pod('rust', [(-0.90, 0.60, 0.74), (-0.30, 0.82, 1.05),
                       (0.35, 0.84, 1.05), (0.80, 0.62, 0.76)],
              n=8, axis='z', off=(0, 0.62, -0.10), phase=math.pi / 8)
        m.box('rust2', (1.05, 0.42, 0.70), off=(0, 1.12, -0.20), bev=0.12)
        P('knee ' + tag, 'knee' + tag, m, 'limb')

        m = Mesh()
        m.box('plate', (1.10, 1.12, 3.20), off=(0, -0.04, -1.85), bev=0.30,
              taper=0.86)
        m.box('plate2', (1.16, 0.44, 2.10), off=(0, -0.62, -1.85), bev=0.16)
        # calf ram, the piece that reads as a machine in motion
        m.tube('metal', 0.16, 0.16, 1.90, 8, off=(s * 0.48, 0.76, -1.45))
        m.tube('metal2', 0.23, 0.23, 1.05, 8, off=(s * 0.48, 0.76, -2.55))
        m.box('green', (0.32, 0.06, 0.32), off=(-s * 0.55, -0.72, -1.15))
        P('shin ' + tag, 'knee' + tag, m, 'limb')

        # ---- ankle shaft and foot ----
        # A short vertical pastern between the shin and the sole. Without it the
        # shin has to reach the ground on its own and the ankle ends up either
        # buried or floating; with it, the leg gets the extra break that makes
        # the digitigrade stance legible.
        F('ankle' + tag, 'knee' + tag, (0.0, 0.0, -3.50), rx(48))
        m = Mesh()
        m.tube('metal', 0.52, 0.52, 0.95, 10, off=(0, 0, 0), rot=ry(90))
        m.box('metal2', (0.86, 0.90, 1.15), off=(0, 0.02, -0.60), bev=0.20)
        m.tube('metal', 0.15, 0.15, 0.95, 8, off=(s * 0.38, 0.50, -0.62))
        P('ankle ' + tag, 'ankle' + tag, m, 'limb')

        m = Mesh()
        # Sole plate, then three splayed toes and a heel spur. Splayed toes are
        # most of what makes a bird leg look like it is carrying something.
        m.box('rust2', (1.85, 2.90, 0.50), off=(0, 0.55, -1.55), bev=0.26)
        for k, txo in ((-1, -0.58), (0, 0.0), (1, 0.58)):
            m.box('rust', (0.52, 1.15, 0.40), off=(txo, 1.95, -1.60),
                  rot=rz(k * 8), bev=0.12, taper=0.8)
        m.box('rust2', (1.15, 0.80, 0.42), off=(0, -1.05, -1.53), bev=0.14,
              taper=0.85)
        m.box('plate2', (1.30, 1.30, 0.55), off=(0, 0.35, -1.22), bev=0.18)
        P('foot ' + tag, 'ankle' + tag, m, 'limb')

    return frames, order, parts


def pose_mech(frames, sim, idle=True):
    """Idle pose. Small, slow and out of phase across the joints -- a machine
    this heavy never quite stops moving, and a rig that is perfectly still
    reads as a photograph rather than as a model."""
    if not idle:
        for f in frames.values():
            f.pose = IDENT
        return
    b = math.sin(sim * 0.9)
    b2 = math.sin(sim * 0.9 + 1.1)
    frames['pelvis'].pose = rxyz(ax=b * 0.7, az=b2 * 0.5)
    frames['torso'].pose = rxyz(ax=-b * 1.1, ay=b2 * 0.6, az=math.sin(sim * 0.6) * 1.4)
    for tag, ph in (('L', 0.0), ('R', 2.1)):
        s = -1 if tag == 'L' else 1
        frames['sh' + tag].pose = rxyz(ax=math.sin(sim * 0.75 + ph) * 1.6,
                                       ay=s * math.sin(sim * 0.5 + ph) * 1.0)
        frames['elb' + tag].pose = rxyz(ax=math.sin(sim * 0.65 + ph) * 1.3)
        frames['rack' + tag].pose = rxyz(ax=math.sin(sim * 0.55 + ph) * 0.9)


# --- geometry helpers -----------------------------------------------------
def hull2d(pts):
    """Monotone-chain convex hull. Used only on the eight ground-projected
    corners of a part's bounding box, to give the cast shadow a silhouette
    instead of an axis-aligned smear."""
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2:
                (ax, ay), (bx, by) = out[-2], out[-1]
                if (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax) > 0:
                    break
                out.pop()
            out.append(p)
        return out

    lo = half(pts)
    hi = half(reversed(pts))
    return lo[:-1] + hi[:-1]


# --- main -----------------------------------------------------------------
GRID_SOLID, GRID_XRAY, GRID_OFF = 0, 1, 2
GRID_NAMES = ('GRID', 'GRID X-RAY', 'GRID OFF')

# Keys only. This was a page and a half of prose at one point, which is a
# strange thing to put behind a key you press mid-orbit to remember what 'v'
# does. The prose that was worth keeping is in the module docstring and in the
# comments beside the things it describes; the rest was explaining decisions to
# someone who did not ask.
HELP = [
    'MECHMODEL // controls',
    '',
    'SPACE  pause turntable    v      sensor channel',
    '<- ->  orbit              c      cutaway plane',
    '^ v    tilt               - =    move the cut',
    '[ ]    zoom               j k    target section',
    ', .    spin rate          m      panel: combat/mesh',
    'd      detail             l      labels',
    'a      occlusion          L      lighting',
    'w      wireframe          S      cast shadow',
    'g      grid               p 1-6  palette',
    's      starfield          e      exploded view',
    'i      idle animation     z      zen (hide HUD)',
    '0      reset              h      this help    q  quit',
    '',
    'j k cycle NO TARGET -> torso -> arms -> legs.',
    'SCAN fills with BEARING swept, not with time; the',
    'percentage is how much of the hull actually came',
    'back. A full turn ends it. 0 restarts it.',
]


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('model', nargs='?', default=None,
                    help='an STL to load; defaults to mc.stl beside this '
                         'script if it is there, else the built-in model')
    ap.add_argument('--builtin', action='store_true',
                    help='the procedural mech, ignoring any STL')
    ap.add_argument('--up', default='z', choices=('z', 'y'),
                    help="which axis the STL calls up (default z)")
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
    ap.add_argument('--palette', default='field', choices=PAL_NAMES)
    ap.add_argument('--fps', type=float, default=30.0)
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
    ap.add_argument('--sensor', default='optical',
                    choices=[n.lower() for n in SENSOR_NAMES],
                    help='sensor channel to start in')
    ap.add_argument('--lighting', default='full', choices=LIGHT_ARGS,
                    help='full / key (key light only) / flat (no lighting; '
                         'a single-material mesh becomes a silhouette)')
    ap.add_argument('--stats', action='store_true')
    ap.add_argument('--frames', type=int, default=0,
                    help='render N frames and exit (harness use)')
    ap.add_argument('-h', '--help', action='store_true')
    args = ap.parse_args()
    if args.help:
        print(__doc__)
        return

    # ---- pick a model ----
    stl_path = args.model
    if stl_path is None and not args.builtin:
        here = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'mc.stl')
        if os.path.exists(here):
            stl_path = here
    if args.builtin:
        stl_path = None
    if stl_path is not None and not os.path.exists(stl_path):
        print('no such file: %s' % stl_path, file=sys.stderr)
        return 2

    lods = []
    frames_d, forder, parts = build_mech()
    if stl_path is not None:
        targets = (args.faces,) if args.faces else LOD_TARGETS
        # Building is seconds on a cold cache and milliseconds on a warm one,
        # so say what is happening rather than show a black terminal.
        def note(msg):
            sys.stdout.write('  %s ...\r\n' % msg)
            sys.stdout.flush()
        try:
            models = load_models(stl_path, targets, up=args.up,
                                 ao_radius=args.ao_radius, vox=args.voxels,
                                 note=note, use_cache=not args.no_cache)
        except (OSError, ValueError, struct.error) as e:
            print('cannot load %s: %s' % (stl_path, e), file=sys.stderr)
            return 2
        frames_d, forder = {}, []
        root = Frame('root', None, (0.0, 0.0, 0.0), IDENT)
        frames_d['root'] = root
        forder.append(root)
        for i, m in enumerate(models):
            mv = _MeshView(m.verts, m.faces, 'plate')
            lods.append(Part(os.path.basename(stl_path), root, mv, 'hull',
                             trust_winding=True,
                             ao=None if args.no_ao else m.ao, wear_amp=0.055,
                             sec=m.sec, temp=m.temp))
            lods[-1].model = m
        lod = min(args.lod, len(lods) - 1)
        parts = [lods[lod]]

    # The built-in mech needs a heat field too, or the thermal channel is a
    # flat silhouette on it -- and worse, with no temperature to carry, the
    # per-facet 'hot' slot still held the SELECTION flag, so picking a part
    # made it read white hot. Same physics as the loaded mesh: a point source
    # at the torso, inverse square, no occlusion term because the procedural
    # parts have none.
    if not lods and parts:
        for f in forder:
            f.resolve()

        def _wc(pt, fr):
            q = mvec(fr.M, pt)
            return (q[0] + fr.T[0], q[1] + fr.T[1], q[2] + fr.T[2])

        tp = [p for p in parts if p.name == 'torso hull'] or parts
        kx = sum(_wc(p.centroid, p.frame)[0] for p in tp) / len(tp)
        ky = sum(_wc(p.centroid, p.frame)[1] for p in tp) / len(tp)
        kz = sum(_wc(p.centroid, p.frame)[2] for p in tp) / len(tp)
        # Scale off the built-in's own height, not MODEL_H: the procedural
        # mech is modelled in its own units and is not normalised to the
        # loaded mesh's twelve metres.
        _zs = [_wc(v, p.frame)[2] for p in parts for v in p.v]
        _h = (max(_zs) - min(_zs)) or 1.0
        _hi = 0.0
        for p in parts:
            p.temp = []
            for _idx, _mat, _n, lc in p.faces:
                wx, wy, wz = _wc(lc, p.frame)
                d2 = ((wx - kx) ** 2 + (wy - ky) ** 2 + (wz - kz) ** 2)
                v = 1.0 / (1.0 + d2 / ((REACTOR_R * _h) ** 2))
                p.temp.append(v)
                if v > _hi:
                    _hi = v
        _hi = _hi or 1.0
        for p in parts:
            p.temp = [v / _hi for v in p.temp]

    if args.stats:
        if lods:
            print_mesh_report(lods[0].model.report,
                              [p.model.report for p in lods])
        else:
            print('%-18s %-8s %8s %8s %7s'
                  % ('PART', 'GROUP', 'VOL m3', 'MASS t', 'FACES'))
            tot = vol = nf = 0.0
            for p in parts:
                print('%-18s %-8s %8.2f %8.2f %7d'
                      % (p.name, p.group, p.volume, p.mass, len(p.faces)))
                tot += p.mass
                vol += p.volume
                nf += len(p.faces)
            print('%-18s %-8s %8.2f %8.2f %7d' % ('TOTAL', '', vol, tot, nf))
        return

    SUBX = 2 if args.blocks == 'quad' else 1
    kb = Keyboard()
    restored = [False]
    quitting = []          # set by a signal, drained by the frame loop

    def cleanup(*_):
        # Teardown must finish come what may: it is the only thing that puts
        # the cursor, colours and terminal mode back. Go deaf first, then retry
        # once, because a signal already in flight can land between entering
        # here and the SIG_IGN taking effect.
        if restored[0]:
            return
        restored[0] = True
        for sg in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            try:
                signal.signal(sg, signal.SIG_IGN)
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

    # A signal handler must not touch sys.stdout. The emitter holds the
    # BufferedWriter's lock for most of every frame -- one 20 KB write into a
    # pty -- and re-entering it from a handler raises RuntimeError, which a
    # defensive `except Exception: pass` around the teardown then swallows.
    # The result is a process that exits 0 having restored nothing: raw mode
    # still set, cursor still hidden. Measured at 60 teardowns out of 60 before
    # this changed. So the handler only records the request, and the frame loop
    # tears down at the top of the next iteration, where nothing is
    # half-written and the lock is free.
    for sg in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        try:
            signal.signal(sg, lambda *_: quitting.append(True))
        except Exception:
            pass

    sys.stdout.write(HIDE + CLEAR)

    pal = args.palette
    P = PALETTES[pal]
    MAT = palette_materials(pal)

    az = math.radians(args.az)
    el = math.radians(args.tilt)
    DIST = args.dist
    zoom = 1.0
    spin = args.speed
    paused = False
    grid_mode = GRID_SOLID
    zen = args.zen
    stars_on = not args.no_stars
    shadow_on = not args.no_shadow
    idle_on = not args.no_idle
    light_mode = LIGHT_ARGS.index(args.lighting)
    sensor = SENSOR_NAMES.index(args.sensor.upper())
    cutaway = False
    cut_z = 0.55
    labels = False
    wire = False
    explode = 0.0
    explode_t = 0.0
    sel = -1              # -1 is NO TARGET, and it is the state you start in
    panel_mode = 0        # 0 combat, 1 mesh
    show_help = False
    # Sensor coverage. Not a decorative barber pole: a byte per facet, set the
    # first time that facet survives the backface test, so the bar measures how
    # much of the hull the sensor has actually returned as the target turns.
    # It fills as you orbit, it completes, and it stays complete.
    scan_seen = None
    scan_left = 0
    scan_tot = 0
    scan_sweep = 0.0      # radians of bearing covered since the scan began
    scan_az = None
    flash, flash_until = '', 0.0

    # The model's own extent, measured once at the rest pose. The camera fit
    # uses the bounding *cylinder*, not the corners: a cylinder's projection
    # does not depend on the azimuth at all, so the framing is exactly constant
    # as the turntable turns instead of breathing every quarter revolution.
    for f in forder:
        f.resolve()
    allw = []
    # Every level of detail, not just the one showing: the levels differ by a
    # fraction of a unit at the silhouette, and framing that tracked the
    # current level would make the model jump when d cycles.
    for p in (lods or parts):
        M, T = p.frame.M, p.frame.T
        for v in p.v:
            q = mvec(M, v)
            allw.append((q[0] + T[0], q[1] + T[1], q[2] + T[2]))
    MRAD = max(math.hypot(w[0], w[1]) for w in allw)
    MZ0 = min(w[2] for w in allw)
    MZ1 = max(w[2] for w in allw)
    MCZ = (MZ0 + MZ1) / 2.0
    # Rest-pose direction of each part from the model's axis, for the explode.
    # Over every level of detail, not just the one showing: d swaps which Part
    # is in `parts`, and a level that never got here crashes the frame loop the
    # moment it is selected. Found by the key soak, not by looking.
    for p in (lods or parts):
        M, T = p.frame.M, p.frame.T
        c = mvec(M, p.centroid)
        c = (c[0] + T[0], c[1] + T[1], c[2] + T[2])
        p.expdir = normed((c[0], c[1] * 0.55, (c[2] - MCZ) * 0.9))

    FIT_RING = [(math.cos(a * math.pi / 8), math.sin(a * math.pi / 8))
                for a in range(16)]
    stl_mode = bool(lods)
    lod_i = min(args.lod, len(lods) - 1) if stl_mode else 0
    ao_on = not args.no_ao
    model_name = stl_path if stl_mode else 'MADCAT-X'

    rng = random.Random(7)
    stars = []
    cols = rows = 0
    ras = None
    ov = None
    t0 = time.time()
    sim = 0.0
    frame = 0
    fps_avg = args.fps
    last = t0

    try:
        while True:
            if quitting:
                break
            now = time.time()
            dt = min(0.2, now - last)
            last = now
            if not paused:
                sim += dt * spin

            sz = shutil.get_terminal_size((100, 30))
            if sz.columns != cols or sz.lines != rows:
                cols, rows = max(24, sz.columns), max(10, sz.lines)
                ras = Raster(cols * SUBX, rows * 2)
                sy_max = int(rows * 2 * 0.62)
                stars = [(rng.randrange(cols * SUBX), rng.randrange(sy_max),
                          rng.random(), rng.random() * 6.283)
                         for _ in range(int(cols * rows * 0.05))]
                sys.stdout.write(CLEAR)
            pxw, pxh = cols * SUBX, rows * 2
            ov = [[None] * cols for _ in range(rows)]

            # ---- input ----
            for k in kb.poll():
                if k in ('q', 'Q'):
                    raise KeyboardInterrupt
                elif k == ' ':
                    paused = not paused
                    flash, flash_until = ('PAUSED' if paused else 'RUNNING',
                                          now + 0.8)
                elif k == 'LEFT':
                    az -= 0.12
                elif k == 'RIGHT':
                    az += 0.12
                elif k == 'UP':
                    el = min(math.radians(78), el + 0.05)
                elif k == 'DOWN':
                    el = max(math.radians(-25), el - 0.05)
                elif k == '[':
                    zoom = max(0.35, zoom / 1.09)
                elif k == ']':
                    zoom = min(4.5, zoom * 1.09)
                elif k == ',':
                    spin = max(-6.0, spin - 0.25)
                    flash, flash_until = f'SPIN {spin:+.2f}', now + 0.8
                elif k == '.':
                    spin = min(6.0, spin + 0.25)
                    flash, flash_until = f'SPIN {spin:+.2f}', now + 0.8
                elif k in ('j', '\t', 'k'):
                    # Alive again on a loaded mesh: the shell is still one
                    # watertight body, but it has been segmented into the
                    # machine's own limbs, so there is something to select
                    # between after all.
                    # -1 is a real state, not a sentinel to skip past: a
                    # gunner who wants the whole machine and no section
                    # highlighted has to be able to get there, and the cycle
                    # is the obvious way in and out of it.
                    n_sel = len(SECTIONS) if stl_mode else len(parts)
                    sel = (sel + (2 if k != 'k' else 0)) % (n_sel + 1) - 1
                    if stl_mode:
                        flash, flash_until = (
                            'NO TARGET' if sel < 0 else
                            SECTION_NAMES[SECTIONS[sel]].upper(), now + 0.8)
                elif k == 'm':
                    panel_mode = (panel_mode + 1) % 2
                    flash, flash_until = (
                        ('COMBAT', 'MESH')[panel_mode] + ' PANEL', now + 0.8)
                elif k == 'e':
                    if not stl_mode:
                        explode_t = 0.0 if explode_t > 0.5 else 1.0
                        flash, flash_until = ('EXPLODED' if explode_t else
                                              'ASSEMBLED', now + 0.9)
                elif k == 'd':
                    if stl_mode and len(lods) > 1:
                        lod_i = (lod_i + 1) % len(lods)
                        parts = [lods[lod_i]]
                        sel = -1
                        scan_seen = None      # different mesh, different hull
                        flash, flash_until = (
                            '%s  %s FACETS'
                            % (LOD_NAMES[lod_i] if lod_i < len(LOD_NAMES)
                               else 'LOD %d' % lod_i,
                               commas(len(parts[0].faces))), now + 1.1)
                elif k == 'a':
                    ao_on = not ao_on
                    flash, flash_until = ('OCCLUSION ON' if ao_on
                                          else 'OCCLUSION OFF', now + 0.9)
                elif k == 'w':
                    wire = not wire
                    flash, flash_until = ('WIREFRAME' if wire else 'SOLID',
                                          now + 0.8)
                elif k == 'l':
                    labels = not labels
                elif k == 'L':
                    light_mode = (light_mode + 1) % 3
                    flash, flash_until = LIGHT_NAMES[light_mode], now + 0.9
                elif k == 'v':
                    sensor = (sensor + 1) % len(SENSOR_NAMES)
                    flash, flash_until = ('SENSOR ' + SENSOR_NAMES[sensor],
                                          now + 0.9)
                elif k == 'c':
                    cutaway = not cutaway
                    flash, flash_until = ('CUTAWAY' if cutaway
                                          else 'CUTAWAY OFF', now + 0.8)
                elif k == '-':
                    cut_z = max(0.02, cut_z - 0.04)
                elif k == '=':
                    cut_z = min(0.99, cut_z + 0.04)
                elif k == 'S':
                    shadow_on = not shadow_on
                    flash, flash_until = ('SHADOW ON' if shadow_on
                                          else 'SHADOW OFF', now + 0.8)
                elif k == 'g':
                    grid_mode = (grid_mode + 1) % 3
                    flash, flash_until = GRID_NAMES[grid_mode], now + 0.8
                elif k == 's':
                    stars_on = not stars_on
                elif k == 'i':
                    # Idle is a pose on the built-in skeleton. A loaded mesh is
                    # one rigid body with no joints to move, so: silently inert.
                    if not stl_mode:
                        idle_on = not idle_on
                        flash, flash_until = ('IDLE ON' if idle_on
                                              else 'IDLE OFF', now + 0.8)
                elif k == 'z':
                    zen = not zen
                elif k in ('h', '?'):
                    show_help = not show_help
                elif k == 'p':
                    pal = PAL_NAMES[(PAL_NAMES.index(pal) + 1) % len(PAL_NAMES)]
                    P, MAT = PALETTES[pal], palette_materials(pal)
                    flash, flash_until = pal.upper(), now + 0.9
                elif k in '123456':
                    pal = PAL_NAMES[int(k) - 1]
                    P, MAT = PALETTES[pal], palette_materials(pal)
                    flash, flash_until = pal.upper(), now + 0.9
                elif k == '0':
                    az, el, zoom, spin = (math.radians(args.az),
                                          math.radians(args.tilt),
                                          1.0, args.speed)
                    DIST, explode_t, wire = args.dist, 0.0, False
                    grid_mode, paused = GRID_SOLID, False
                    sel, scan_seen = -1, None      # target dropped, scan rerun
                    flash, flash_until = 'RESET', now + 0.8
                elif k == 'ESC':
                    show_help = False

            explode += (explode_t - explode) * min(1.0, dt * 4.0)
            if not paused:
                az += dt * spin * 0.32

            # ---- camera ----
            ca, sa = math.cos(az), math.sin(az)
            ce, se = math.cos(el), math.sin(el)
            camX = DIST * ce * sa
            camY = -DIST * ce * ca
            camZ = DIST * se + MCZ
            panel = 0 if zen else min(26, max(0, cols // 4))
            panel_px = panel * SUBX
            avail_w = pxw - panel_px

            # Fit the cylinder that circumscribes the model -- grown by the
            # explode displacement, so pulling the machine apart pulls the
            # camera back with it instead of flinging the parts off screen.
            eg = explode * MRAD * 1.15
            fr_ = MRAD + eg
            us, vs = [], []
            for cth, sth in FIT_RING:
                xr, yr = fr_ * cth, fr_ * sth
                for cz_ in (MZ0 - MCZ - eg, MZ1 - MCZ + eg):
                    zv = yr * ce - cz_ * se + DIST
                    if zv < 1.0:
                        zv = 1.0
                    us.append(SUBX * xr / zv)
                    vs.append(-(yr * se + cz_ * ce) / zv)
            du = (max(us) - min(us)) or 1e-6
            dv = (max(vs) - min(vs)) or 1e-6
            Fl = min(avail_w / du, (pxh - 4) / dv) * 0.93 * zoom
            OX = panel_px + avail_w / 2 - Fl * (min(us) + max(us)) / 2
            OY = pxh / 2 - Fl * (min(vs) + max(vs)) / 2

            def proj(x, y, z):
                """World -> screen. The model is small next to DIST, so no near
                plane can be crossed; the clamp is only there so a degenerate
                pose cannot raise over a raw terminal."""
                z -= MCZ
                xr = x * ca + y * sa
                yr = -x * sa + y * ca
                zv = yr * ce - z * se + DIST
                if zv < 0.6:
                    zv = 0.6
                return (OX + Fl * SUBX * xr / zv,
                        OY - Fl * (yr * se + z * ce) / zv, zv)

            psel_on = sensor != SENSOR_THERMAL
            see_through = sensor == SENSOR_XRAY
            wireonly = sensor in (SENSOR_LIDAR, SENSOR_XRAY)
            # Any channel that is not the eye draws on an instrument field.
            # Gating this on `wireonly` alone left THERMAL sitting on a blue
            # sky over daylit olive ground with a hard sun shadow under it,
            # which reads as an optical photograph that somebody tinted --
            # exactly the thing the channel is not.
            nosun = wireonly or sensor == SENSOR_THERMAL
            cutplane = (MZ0 + (MZ1 - MZ0) * cut_z) if cutaway else None

            # ---- sky ----
            if nosun:
                # No sun in a sensor return: a scan channel draws on an
                # instrument field, not on a daylit sky. Leaving the sky
                # and the cast shadow in put olive ground and a hard sun
                # shadow behind a lidar trace, which read as a bug.
                ras.clear(quant(SCAN_BG))
            else:
                sky0, sky1 = P['sky']
                horizon = int(pxh * 0.60)
                for yb in range(0, horizon, 2):
                    t = yb / max(1, horizon)
                    ras.hband(yb, yb + 2, quant(lerp(sky0, sky1, t * t)))
                ras.hband(horizon, pxh, quant(P['ground']))
                if stars_on and P['star'] is not None:
                    sc_ = P['star']
                    for sxp, syp, br, ph in stars:
                        if syp >= horizon:
                            continue
                        tw = 0.55 + 0.45 * math.sin(sim * 2.0 + ph)
                        ras.point(sxp, syp, quant(shade(sc_, br * tw * 0.9)))
            # ---- ground plane and grid ----
            GR = MRAD * 3.4
            gq = [proj(x, y, 0.0) for x, y in
                  ((-GR, -GR), (GR, -GR), (GR, GR), (-GR, GR))]
            if not nosun:
                ras.fill([q[:2] for q in gq], quant(shade(P['ground'], 1.25)),
                         quant(shade(P['ground'], 0.7)))

            def draw_grid(gc):
                step = GR / 8.0
                for i in range(17):
                    t = -GR + i * step
                    for pa, pb in (((t, -GR), (t, GR)), ((-GR, t), (GR, t))):
                        a = proj(pa[0], pa[1], 0.0)
                        b = proj(pb[0], pb[1], 0.0)
                        ras.line_c(a[0], a[1], b[0], b[1], gc)

            if grid_mode == GRID_SOLID:
                draw_grid(quant(shade(P['grid'], 0.9)))

            # ---- pose and transform ----
            if not stl_mode:
                pose_mech(frames_d, sim, idle_on)
            for f in forder:
                f.resolve()

            ex = explode * MRAD * 1.15
            world = []                     # per part: (list of world verts)
            for p in parts:
                M, T = p.frame.M, p.frame.T
                tx = T[0] + p.expdir[0] * ex
                ty = T[1] + p.expdir[1] * ex
                tz = T[2] + p.expdir[2] * ex
                wv = []
                for v in p.v:
                    x, y, z = v
                    wv.append((M[0] * x + M[1] * y + M[2] * z + tx,
                               M[3] * x + M[4] * y + M[5] * z + ty,
                               M[6] * x + M[7] * y + M[8] * z + tz))
                world.append(wv)

            # ---- cast shadow ----
            # Two shapes for two kinds of model. A loaded mesh gets height
            # bands, each hulled on the ground separately, so the gap between
            # the legs survives -- and because the turntable moves the *eye*
            # and not the mech, those hulls are static and were computed once
            # at load. The built-in model is already a set of parts, so each
            # part's own bounding box is the natural band.
            if shadow_on and not nosun and SUN[2] > 0.05 and explode < 0.4:
                shc = quant(lerp(P['ground'], P['shadow'],
                                 0.75 * (1.0 - explode / 0.4)))
            if shadow_on and not nosun and SUN[2] > 0.05 and stl_mode:
                for band in parts[0].model.shadow:
                    sp = [proj(bx, by, 0.01)[:2] for bx, by in band]
                    if len(sp) >= 3:
                        ras.fill(sp, shc)
            elif shadow_on and not nosun and SUN[2] > 0.05 and explode < 0.4:
                for wv in world:
                    xs = [w[0] for w in wv]
                    ys = [w[1] for w in wv]
                    zs = [w[2] for w in wv]
                    x0, x1 = min(xs), max(xs)
                    y0, y1 = min(ys), max(ys)
                    z0, z1 = min(zs), max(zs)
                    sp = []
                    for bx in (x0, x1):
                        for by in (y0, y1):
                            for bz in (z0, z1):
                                t = bz / SUN[2]
                                q = proj(bx - SUN[0] * t, by - SUN[1] * t, 0.01)
                                sp.append((q[0], q[1]))
                    h = hull2d(sp)
                    if len(h) >= 3:
                        ras.fill(h, shc)

            if grid_mode == GRID_XRAY:
                draw_grid(quant(shade(P['grid'], 1.9)))

            # ---- gather faces ----
            # Painter's algorithm over individual facets, sorted by mean
            # camera-space depth. dscape can do better than a sort because its
            # blocks sit on a guillotine plan whose own cuts give an exact
            # order; nothing here is axis-aligned, so there is no such plan.
            # The sort is wrong only where two hulls interpenetrate, which in
            # this model happens exclusively inside joints -- a bearing sunk
            # into a limb, a ram buried in a calf -- where the seam is hidden
            # by the very parts that create it.
            sel_part = (parts[sel] if (parts and not stl_mode and sel >= 0)
                        else None)
            SC = P['sel']
            fog0, fog1 = DIST - MRAD * 1.6, DIST + MRAD * 2.4
            fogc = P['sky'][1]
            sil = [1e9, 1e9, -1e9, -1e9]        # silhouette box, screen px
            queue = []
            # One bytearray per part, rebuilt whenever the part list changes,
            # so a level-of-detail switch cannot be scored against the hull it
            # is no longer drawing.
            if scan_seen is None or len(scan_seen) != len(parts):
                scan_seen = [bytearray(len(p.faces)) for p in parts]
                scan_tot = sum(len(p.faces) for p in parts) or 1
                scan_left = scan_tot
                scan_sweep, scan_az = 0.0, az
            # 'Every facet returned' is the wrong completion test and measuring
            # it proved as much: it stalls around 96%, because at a fixed tilt
            # some of the hull -- undersides, the inside of the shoulder --
            # never turns to face the sensor at any bearing at all. A bar that
            # asymptotes short of full is the loading-forever bar again.
            #
            # A full REVOLUTION is the test that terminates and that means
            # something: the sensor has now seen the target from every bearing,
            # and the coverage it reached is the fraction of hull a sweep at
            # this elevation can return. What it missed is a fact about the
            # geometry, not an unfinished job -- so the strip stops counting
            # and reports the achieved figure.
            scan_sweep += abs(az - scan_az)
            scan_az = az
            for pi, p in enumerate(parts):
                wv = world[pi]
                M = p.frame.M
                hot = p is sel_part and not zen
                praw = p.temp if sensor == SENSOR_THERMAL else None
                # On a loaded mesh the highlight is per FACET, not per part:
                # one Part carries the whole shell and the selection is a
                # section of it.
                psec = p.sec if (stl_mode and not zen) else None
                # Occlusion lives inside the per-face brightness multiplier, so
                # toggling it is a choice of list, not a branch in the shader.
                wr = p.wear if ao_on else p.wear_plain
                # proj() inlined. It is a closure called once per vertex, and
                # at a few thousand vertices the call and its cell lookups cost
                # more than the arithmetic inside it.
                fsub = Fl * SUBX
                sp = []
                spa = sp.append
                for w in wv:
                    wx, wy, wz = w
                    wz -= MCZ
                    xr = wx * ca + wy * sa
                    yr = -wx * sa + wy * ca
                    zv = yr * ce - wz * se + DIST
                    if zv < 0.6:
                        zv = 0.6
                    spa((OX + fsub * xr / zv,
                         OY - Fl * (yr * se + wz * ce) / zv, zv))

                # World normals depend only on the part's frame matrix -- and
                # the turntable spins the camera, not the mech, so on a still
                # pose every normal is the one computed last frame. Cache them
                # against the matrix itself: a pose that really does move (idle
                # sway, explode, a part selected and pulled out) fails the
                # comparison and recomputes, so this is exact, not an
                # approximation.
                nw = p.__dict__.get('_nw')
                if nw is None or p._nw_M != M:
                    m0, m1, m2, m3, m4, m5, m6, m7, m8 = M
                    nw = [(m0 * ln[0] + m1 * ln[1] + m2 * ln[2],
                           m3 * ln[0] + m4 * ln[1] + m5 * ln[2],
                           m6 * ln[0] + m7 * ln[1] + m8 * ln[2])
                          for _i, _m, ln, _c in p.faces]
                    p._nw, p._nw_M = nw, M

                qa = queue.append
                # Local, and only touched while the scan is incomplete: once
                # it finishes this whole thing costs one `if scan_left` per
                # facet, and the gather loop is the hot loop in this program.
                pseen = scan_seen[pi]
                for fi, (idx, mat, ln, lc) in enumerate(p.faces):
                    n = nw[fi]
                    h = hot if psec is None else (psec[fi] == sel)
                    a = wv[idx[0]]
                    # Backface test against the eye, not against a global
                    # azimuth: under perspective the two disagree at the edges
                    # of a wide model and the disagreement is a hole. XRAY is
                    # exactly the mode that wants the far side, so it is the
                    # one mode that skips this.
                    if see_through:
                        pass
                    elif ((camX - a[0]) * n[0] + (camY - a[1]) * n[1] +
                            (camZ - a[2]) * n[2]) <= 0.0:
                        continue
                    if cutplane is not None and a[2] > cutplane:
                        continue          # cutaway: nothing above the station
                    if scan_left and not pseen[fi]:
                        pseen[fi] = 1
                        scan_left -= 1
                    if praw is not None:
                        h = praw[fi]      # thermal carries temperature, not select
                    if len(idx) == 3:
                        s0 = sp[idx[0]]
                        s1 = sp[idx[1]]
                        s2 = sp[idx[2]]
                        qa(((s0[2] + s1[2] + s2[2]) / 3,
                            ((s0[0], s0[1]), (s1[0], s1[1]), (s2[0], s2[1])),
                            mat, n, wr[fi], h))
                        continue
                    zsum = 0.0
                    pts = []
                    for i in idx:
                        s = sp[i]
                        pts.append((s[0], s[1]))
                        zsum += s[2]
                    zsum /= len(idx)
                    qa((zsum, pts, mat, n, wr[fi], h))

            queue.sort(key=lambda q: -q[0])
            drawn = len(queue)

            # ---- shade and fill ----
            sky_c, bounce_c = P['sky'][1], P['bounce']
            # Everything the shader reads, hoisted out of the loop: attribute
            # and global lookups are per-facet costs at a few thousand facets.
            # The shader below is the same expression as ever, with shade() and
            # lerp() inlined -- including their int() truncations, which is what
            # makes it bit-for-bit identical to the version that called them
            # rather than merely close to it.
            S0, S1, S2 = SUN
            F0, F1, F2 = FILL
            b0, b1, b2 = bounce_c
            ks0, ks1, ks2 = sky_c[0] - b0, sky_c[1] - b1, sky_c[2] - b2
            fgr, fgg, fgb = fogc
            fogd = 1.0 / (fog1 - fog0)
            SCr, SCg, SCb = SC
            soft = SOFT_MAT
            rfill, rfill3 = ras.fill, ras.fill3
            lm = light_mode

            if wireonly:
                # A return, not a picture: brightness is range, and the only
                # geometry drawn is the facet outline. Costs no fill at all,
                # which is why these are the fastest channels in the program.
                near, far = fog0, fog1
                span = (far - near) or 1.0
                wc0 = SCAN_COL
                # View direction, good enough for a grazing test at this range.
                vlen = math.sqrt(camX * camX + camY * camY + camZ * camZ) or 1.0
                vdx, vdy, vdz = camX / vlen, camY / vlen, camZ / vlen
                # The silhouette has to be accumulated here as well as in the
                # fill loop. It was not, and the consequence was that the lock
                # frame -- and, once the strip moved onto row 0, every readout
                # on the display -- disappeared in precisely the two channels
                # you would be scanning a target with. Over every queued facet,
                # not just the contours: the box is the target's extent, which
                # does not depend on which facets happen to graze the view.
                for zsum, pts, mat, n, wear, hot in queue:
                    for px_, py_ in pts:
                        if px_ < sil[0]:
                            sil[0] = px_
                        if px_ > sil[2]:
                            sil[2] = px_
                        if py_ < sil[1]:
                            sil[1] = py_
                        if py_ > sil[3]:
                            sil[3] = py_
                    d = n[0] * vdx + n[1] * vdy + n[2] * vdz
                    if d < 0.0:
                        d = -d
                    if d > SCAN_GRAZE:
                        continue        # facing us: interior, not a contour
                    g = 1.0 - (zsum - near) / span
                    if g < 0.12:
                        g = 0.12
                    elif g > 1.0:
                        g = 1.0
                    if see_through:
                        g *= 0.62
                    if hot and psel_on:
                        c = quant(lerp(shade(wc0, g), SC, 0.5))
                    else:
                        c = quant(shade(wc0, g))
                    for i in range(len(pts)):
                        a_, b_ = pts[i - 1], pts[i]
                        ras.line_c(a_[0], a_[1], b_[0], b_[1], c)
                queue = []

            for zsum, pts, mat, n, wear, hot in queue:
                base = MAT[mat]
                n0, n1, n2 = n
                if sensor == SENSOR_THERMAL:
                    # 'hot' carries temperature in this channel, not the
                    # selection flag. The field is already smooth and already
                    # normalised, so it goes on the ramp end to end -- the
                    # earlier version had to squash it into the middle third
                    # because raw per-facet occlusion swung hard between
                    # neighbours and read as camouflage. A reactor does not.
                    ti = int(hot * 64.0)
                    base = HEAT_LUT[ti if 0 <= ti <= 64 else 0]
                if lm == LIGHT_FLAT or sensor == SENSOR_THERMAL:
                    r, g, b = base
                else:
                    ndl = n0 * S0 + n1 * S1 + n2 * S2
                    if lm == LIGHT_KEY:
                        k = (0.34 + 0.78 * ndl) if ndl > 0.0 else 0.34
                        k *= wear
                        r = int(base[0] * k)
                        g = int(base[1] * k)
                        b = int(base[2] * k)
                    else:
                        ndf = n0 * F0 + n1 * F1 + n2 * F2
                        k = 0.30
                        if ndl > 0.0:
                            # A cheap metallic sheen: the same Lambert term
                            # raised hard, so a face square to the sun gets a
                            # hot edge and the rest of the hull stays matte.
                            # Without it every panel reads as painted card.
                            # ndl**9 as three squarings, not a pow() call.
                            x2 = ndl * ndl
                            x4 = x2 * x2
                            k += 0.72 * ndl + 0.55 * x4 * x4 * ndl
                        if ndf > 0.0:
                            k += 0.26 * ndf
                        k *= wear
                        r = int(base[0] * k)
                        g = int(base[1] * k)
                        b = int(base[2] * k)
                    if r > 255:
                        r = 255
                    elif r < 0:
                        r = 0
                    if g > 255:
                        g = 255
                    elif g < 0:
                        g = 0
                    if b > 255:
                        b = 255
                    elif b < 0:
                        b = 0
                if lm == LIGHT_FULL and sensor != SENSOR_THERMAL:
                    # Hemisphere ambient: an upward face is under the sky and
                    # takes the sky's colour, a downward face is over the ground
                    # and takes the ground's. This is what tells a horizontal
                    # surface from a vertical one on the side the sun never
                    # reaches, and it is the cheapest single thing that stops
                    # the model reading as a cut-out. Weak on purpose -- at 0.16
                    # it tints, it does not wash.
                    t = 0.5 * (n2 + 1.0)
                    ar = int(b0 + ks0 * t)
                    ag = int(b1 + ks1 * t)
                    ab = int(b2 + ks2 * t)
                    r = int(r + (ar - r) * 0.16)
                    g = int(g + (ag - g) * 0.16)
                    b = int(b + (ab - b) * 0.16)
                    if soft[mat]:
                        r = int(r + (base[0] - r) * 0.55)
                        g = int(g + (base[1] - g) * 0.55)
                        b = int(b + (base[2] - b) * 0.55)
                    fog = (zsum - fog0) * fogd
                    if fog > 0.0:
                        fog *= 0.30
                        if fog > 0.34:
                            fog = 0.34
                        r = int(r + (fgr - r) * fog)
                        g = int(g + (fgg - g) * fog)
                        b = int(b + (fgb - b) * fog)
                if hot and psel_on:
                    r = int(r + (SCr - r) * 0.34)
                    g = int(g + (SCg - g) * 0.34)
                    b = int(b + (SCb - b) * 0.34)
                # Gradient only where it can be seen -- see GRAD_MIN_H.
                ylo = yhi = pts[0][1]
                for pt in pts:
                    px_, py = pt
                    if py < ylo:
                        ylo = py
                    elif py > yhi:
                        yhi = py
                    if px_ < sil[0]:
                        sil[0] = px_
                    elif px_ > sil[2]:
                        sil[2] = px_
                if ylo < sil[1]:
                    sil[1] = ylo
                if yhi > sil[3]:
                    sil[3] = yhi
                if yhi - ylo >= GRAD_MIN_H:
                    c = (r, g, b)
                    rfill(pts, quant(shade(c, 1.05)), quant(shade(c, 0.93)))
                elif len(pts) == 3:
                    p0, p1, p2 = pts
                    rfill3(p0, p1, p2,
                           (r // 6 * 6, g // 6 * 6, b // 6 * 6))
                else:
                    rfill(pts, (r // 6 * 6, g // 6 * 6, b // 6 * 6))
                if wire:
                    wc = quant(shade((r, g, b), 1.9))
                    for i in range(len(pts)):
                        a, b_ = pts[i - 1], pts[i]
                        ras.line_c(a[0], a[1], b_[0], b_[1], wc)

            # ---- overlay ----
            H, HD, PN = P['hud'], P['hud_dim'], P['panel']

            def otext(r, c, s, f=None, b=None):
                if r < 0 or r >= rows:
                    return
                row = ov[r]
                for i, ch in enumerate(s):
                    x = c + i
                    if 0 <= x < cols:
                        row[x] = (ch, f, b)

            if not zen:
                total_mass = sum(p.mass for p in parts)
                nfaces = sum(len(p.faces) for p in parts)
                otext(0, 0, ' ' * cols, H, PN)
                # Row 0 is the instrument strip and nothing else. It used to
                # carry a facet count and a draw count in the top right of a
                # targeting display -- and they were painted over by the strip
                # every frame anyway, so the only thing lost by deleting them
                # is a line of dead code. Numbers about the renderer belong in
                # the mesh panel, which is the page about the renderer.
                if flash and now < flash_until:
                    otext(1, cols - len(flash) - 3, ' ' + flash + ' ',
                          PN, P['alert'])

                if panel > 4 and stl_mode and panel_mode == 0:
                    # ---- combat page ----
                    # Everything a gunner would want and nothing about the
                    # renderer. Two sources and no third: the CANON table,
                    # which is Sarna's, and the mesh, which is measured. Each
                    # block says which it is, because the interesting cases
                    # are the ones that mix them -- the armour distribution
                    # below is twelve canon tons spread over measured skin.
                    rp = parts[0].model.report
                    for r in range(1, rows - 1):
                        otext(r, 0, ' ' * panel, H, PN)
                    W = panel - 2

                    def field(r, k, v, hot=False):
                        otext(r, 1, k[:panel - 3], HD, PN)
                        otext(r, max(len(k) + 2, panel - 1 - len(v)), v,
                              P['sel'] if hot else H, PN)

                    lines = []          # (kind, a, b, hot)
                    lines.append(('head', CANON['name'], '', False))
                    lines.append(('text', '%s  %s' % (CANON['codename'],
                                                      CANON['config']), '',
                                  False))
                    lines.append(('rule', '', '', False))
                    lines.append(('kv', '%d t' % CANON['mass_t'],
                                  CANON['origin'], False))
                    lines.append(('blank', '', '', False))

                    area = rp.get('sec_area') or []
                    lines.append(('sec', 'ARMOUR', '%.1f t'
                                  % CANON['armour_t'], False))
                    lines.append(('dim', 'ferro-fibrous, by area', '', False))
                    for si, sc in enumerate(SECTIONS):
                        if si >= len(area):
                            break
                        t = area[si] * CANON['armour_t']
                        lines.append(('bar', si, '%4.1f' % t, si == sel))
                    lines.append(('blank', '', '', False))

                    lines.append(('sec', 'LOADOUT', CANON['config'], False))
                    for wn, wc in CANON['weapons']:
                        lines.append(('wpn', wn, '%d' % wc, False))
                    lines.append(('blank', '', '', False))

                    lines.append(('sec', 'HEAT', '', False))
                    lines.append(('kv', 'sinks', CANON['heatsinks'], False))
                    lines.append(('kv', 'core', '375 XL', False))
                    lines.append(('blank', '', '', False))
                    lines.append(('sec', 'MOBILITY', '', False))
                    lines.append(('kv', 'walk %d' % CANON['walk_mp'],
                                  '%.1f km/h' % CANON['cruise'], False))
                    lines.append(('kv', 'run %d' % CANON['run_mp'],
                                  '%.1f km/h' % CANON['flank'], False))
                    lines.append(('blank', '', '', False))
                    lines.append(('sec', 'AIRFRAME', '', False))
                    lines.append(('dim', CANON['chassis'], '', False))
                    lines.append(('dim', CANON['engine'], '', False))
                    lines.append(('kv', 'pod space', '%.1f t'
                                  % CANON['podspace'], False))
                    lines.append(('blank', '', '', False))
                    lines.append(('sec', 'QUIRK', '', False))
                    lines.append(('dim', CANON['quirk'], '', False))

                    # Ordered by what a gunner needs first, then simply cut to
                    # fit: a short terminal loses the airframe trivia, not the
                    # armour spread.
                    amax = max(area) if area else 1.0
                    rr = 1
                    for kind, a, b, hotl in lines:
                        if rr >= rows - 2:
                            break
                        if kind == 'head':
                            otext(rr, 1, a[:W], P['sel'], PN)
                        elif kind == 'rule':
                            otext(rr, 1, '─' * W, HD, PN)
                        elif kind == 'sec':
                            otext(rr, 1, ('%s %s' % (a, '─' * W))[:W - len(b)
                                                                  - 1],
                                  H, PN)
                            if b:
                                otext(rr, panel - 1 - len(b), b, P['sel'], PN)
                        elif kind == 'text':
                            otext(rr, 1, a[:W], H, PN)
                        elif kind == 'dim':
                            otext(rr, 1, a[:W], HD, PN)
                        elif kind == 'kv':
                            field(rr, a, b, hotl)
                        elif kind == 'wpn':
                            otext(rr, 1, ('%sx ' % b) + a[:W - 3], H, PN)
                        elif kind == 'bar':
                            otext(rr, 1,
                                  ('▸' if hotl else ' ')
                                  + SECTION_NAMES[SECTIONS[a]][:8],
                                  P['sel'] if hotl else H, PN)
                            if panel >= 22:
                                otext(rr, panel - 12,
                                      bar_str(area[a] / amax, 6), HD, PN)
                            otext(rr, panel - 5, b + ' t',
                                  P['sel'] if hotl else HD, PN)
                        rr += 1
                elif panel > 4 and stl_mode:
                    # ---- mesh page ----
                    rp = parts[0].model.report
                    for r in range(1, rows - 1):
                        otext(r, 0, ' ' * panel, H, PN)
                    otext(1, 1, os.path.basename(model_name)[:panel - 2],
                          P['sel'], PN)
                    otext(2, 1, '─' * (panel - 2), HD, PN)

                    def field(r, k, v, hot=False):
                        otext(r, 1, k[:panel - 3], HD, PN)
                        otext(r, max(len(k) + 2, panel - 1 - len(v)), v,
                              P['sel'] if hot else H, PN)

                    rr = 3
                    for k, v in (
                            ('source', commas(rp['src_tris'])),
                            ('vertices', commas(rp['src_verts'])),
                            ('edges', commas(rp['edges'])),
                            ('watertight',
                             'yes' if rp['watertight'] else 'no'),
                            ('', ''),
                            (LOD_NAMES[lod_i] if lod_i < len(LOD_NAMES)
                             else 'LOD %d' % lod_i, ''),
                            ('facets', commas(rp['faces'])),
                            ('of source', '%.2f%%'
                             % (rp['faces'] / float(rp['src_tris']) * 100.0)),
                            ('vol error', '%+.2f%%' % rp['vol_err']),
                            ('area error', '%+.2f%%' % rp['area_err']),
                            ('', ''),
                            ('AS BUILT', ''),
                            ('height', '%.1f m' % MODEL_H),
                            ('volume', '%.1f m³' % rp['built_volume']),
                            ('mass', '%.1f t' % rp['built_mass']),
                            ('drawn', commas(drawn)),
                            ('fps', '%.1f' % fps_avg),
                            ('', ''),
                            ('occlusion', 'on' if ao_on else 'off'),
                            ('ao reach', '%g vox' % rp['ao_radius']),
                            ('grid', '%d³' % rp['vox']),
                            ('solid cells', commas(rp['solid_cells'])),
                            ('sealed', 'yes' if rp.get('sealed') else 'NO')):
                        if rr >= rows - 2:
                            break
                        if k:
                            field(rr, k, v,
                                  hot=k in ('facets', 'occlusion'))
                        rr += 1
                elif panel > 4:
                    mx = max((p.mass for p in parts), default=1.0) or 1.0
                    for r in range(1, rows - 1):
                        otext(r, 0, ' ' * panel, H, PN)
                    otext(1, 1, 'STRUCTURE', P['sel'], PN)
                    otext(2, 1, '─' * (panel - 2), HD, PN)
                    top = max(0, min(sel - (rows - 8) // 2,
                                     len(parts) - (rows - 8)))
                    r = 3
                    for i in range(top, len(parts)):
                        if r >= rows - 4:
                            break
                        p = parts[i]
                        cur = i == sel
                        # The bar is the first thing to go when the panel is
                        # narrow: a two-cell bar says nothing a number does not.
                        wide = panel >= 24
                        nm = p.name[:panel - (15 if wide else 8)]
                        otext(r, 1, ('▸' if cur else ' ') + nm,
                              P['sel'] if cur else H, PN)
                        if wide:
                            otext(r, panel - 13, bar_str(p.mass / mx, 7), HD, PN)
                        otext(r, panel - 5, '%4.1f' % p.mass,
                              P['sel'] if cur else HD, PN)
                        r += 1
                    if parts and sel >= 0:
                        p = parts[sel]
                        otext(rows - 4, 1, '─' * (panel - 2), HD, PN)
                        otext(rows - 3, 1, p.name[:panel - 2], P['sel'], PN)
                        otext(rows - 2, 1,
                              '%s  %.1f m³  %d f' % (p.group, p.volume,
                                                     len(p.faces)), HD, PN)
                        otext(rows - 5, 1, '%-*s%5.1f t'
                              % (panel - 8, 'TOTAL', total_mass), H, PN)

                hint = (' <-> orbit  ^v tilt  [] zoom  v sensor  '
                        + ('jk target  c cutaway  m panel  d detail  '
                           if stl_mode else 'jk part  e explode  ')
                        + 'p palette  h help  q quit ')
                otext(rows - 1, 0, ' ' * cols, HD, PN)
                otext(rows - 1, 1, hint[:cols - 2], HD, PN)

                if labels:
                    for pi, p in enumerate(parts):
                        wv = world[pi]
                        cx = sum(w[0] for w in wv) / len(wv)
                        cy = sum(w[1] for w in wv) / len(wv)
                        cz = max(w[2] for w in wv)
                        s = proj(cx, cy, cz + 0.2)
                        c0 = int(s[0] / SUBX) - len(p.name) // 2
                        r0 = int(s[1] / 2)
                        if 1 <= r0 < rows - 1 and c0 > panel:
                            otext(r0, c0, p.name,
                                  P['sel'] if pi == sel else H, None)

            # ---- targeting frame ----
            # Brackets track the model's real projected silhouette, which the
            # fill loop already measured facet by facet -- not a guess from the
            # bounding sphere, so they tighten on the legs when the arms swing
            # out of frame under the cutaway.
            if not zen and sil[2] > sil[0]:
                bc0 = max(panel, int(sil[0] / SUBX) - 1)
                bc1 = min(cols - 2, int(sil[2] / SUBX) + 1)
                br0 = max(1, int(sil[1] / 2) - 1)
                br1 = min(rows - 3, int(sil[3] / 2) + 1)
                locked = (now - t0) > 1.2
                BR = H if locked else HD
                arm = max(2, min(6, (bc1 - bc0) // 4))
                vrm = max(1, min(3, (br1 - br0) // 4))
                if bc1 > bc0 and br1 > br0:
                    otext(br0, bc0, '┏' + '━' * (arm - 1), BR)
                    otext(br0, bc1 - arm + 1, '━' * (arm - 1) + '┓', BR)
                    otext(br1, bc0, '┗' + '━' * (arm - 1), BR)
                    otext(br1, bc1 - arm + 1, '━' * (arm - 1) + '┛', BR)
                    for rr in range(1, vrm + 1):
                        otext(br0 + rr, bc0, '┃', BR)
                        otext(br0 + rr, bc1, '┃', BR)
                        otext(br1 - rr, bc0, '┃', BR)
                        otext(br1 - rr, bc1, '┃', BR)
                    mc = (bc0 + bc1) // 2
                    mr = (br0 + br1) // 2
                    otext(mr, mc - 1, '─┼─', BR)
                    tag = ' %s %s ' % (CANON['codename'],
                                       'LOCK' if locked else 'ACQ')
                    otext(max(0, br0 - 1), mc - len(tag) // 2, tag,
                          P['sel'] if locked else HD, PN)

                # ---- instrument strip ----
                # The scan bar was a barber pole -- (sim * 0.7) % 1.0 -- and
                # it loaded forever and meant nothing. It now reports sensor
                # COVERAGE: the fraction of the hull's facets that have come
                # round far enough to return at least once. It fills as the
                # target turns, it reaches 100%, and then it says so and stops.
                # XRAY completes almost at once, which is correct: that is the
                # channel that does not need the far side to turn towards you.
                rng = DIST
                brg = math.degrees(az) % 360.0
                elv = math.degrees(el)
                rpt = lods[lod_i].model.report if (stl_mode and lods) else None
                if rpt and 0 <= sel < len(SECTIONS):
                    share = rpt.get('sec_share') or []
                    smass = ((share[sel] if sel < len(share) else 0.0)
                             * rpt['built_mass'])
                    sname = SECTION_NAMES[SECTIONS[sel]].upper()
                    starg = '%-6s %5.1f t' % (sname, smass)
                elif rpt:
                    starg = '%-6s %5.1f t' % ('HULL', rpt['built_mass'])
                else:
                    starg = '%-6s' % ('--' if sel < 0 else parts[sel].name[:6])
                cov = 1.0 - scan_left / float(scan_tot or 1)
                if scan_sweep < 2.0 * math.pi and scan_left:
                    scantxt = 'SCAN %s %3d%%' % (
                        bar_str(scan_sweep / (2.0 * math.pi), 8),
                        int(cov * 100.0))
                else:
                    scantxt = 'SWEPT 360°  %3d%%' % int(cov * 100.0)
                # Target before bearing: at 80 columns the strip runs off
                # the right-hand edge, and what a gunner loses last is what
                # they are shooting at, not the elevation readout.
                strip = ('MK-VII  %-7s  %-18s  TGT %s   BRG %05.1f  '
                         'EL %+05.1f  RNG %05.1f m'
                         % (SENSOR_NAMES[sensor], scantxt, starg, brg, elv,
                            rng))
                otext(0, 0, ' ' * cols, HD, PN)
                otext(0, 1, strip[:cols - 2], H,
                      PN)

            if show_help:
                bw = min(cols - 4, 66)
                bh = len(HELP) + 2
                c0 = (cols - bw) // 2
                r0 = max(0, (rows - bh) // 2)
                otext(r0, c0, '┌' + '─' * (bw - 2) + '┐', HD, PN)
                for i, ln in enumerate(HELP):
                    otext(r0 + 1 + i, c0, '│', HD, PN)
                    otext(r0 + 1 + i, c0 + bw - 1, '│', HD, PN)
                    otext(r0 + 1 + i, c0 + 2, ln[:bw - 4],
                          P['sel'] if i == 0 else H, PN)
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
            if args.frames and frame >= args.frames:
                break
            el_t = time.time() - now
            fps_avg += (1.0 / max(el_t, 1e-3) - fps_avg) * 0.1
            time.sleep(max(0.0, 1.0 / args.fps - el_t))
    except (KeyboardInterrupt, BrokenPipeError):
        pass
    finally:
        cleanup()


if __name__ == '__main__':
    main()
