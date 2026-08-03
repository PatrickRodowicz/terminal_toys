"""Cockpit chrome: the fixed furniture of a gunsight.

Drawn over the render with a transparent background so it reads as glass rather
than as a panel, and every piece of it sits outside the model area -- there was
a boresight cross at the centre once and it obscured too much.

Deliberately NOT decoration. The bearing tape and the elevation ladder are
driven by the camera's real azimuth and tilt, so they are readouts that happen
to look like chrome rather than chrome pretending to be readouts. The one
invented thing is the crew -- a callsign, a pilot and a hull number,
faction-neutral, rolled once at launch and pinned by --seed -- and it says so
by being the only thing on the display in the dim colour.
"""
import math
import random
import time

CHROME_SPAN = 120.0       # degrees of bearing visible across the tape
CHROME_EL = 80.0          # degrees of elevation across the ladder
CARDINAL = {0: 'N', 45: 'NE', 90: 'E', 135: 'SE',
            180: 'S', 225: 'SW', 270: 'W', 315: 'NW'}
UNIT_CALLS = ('ANVIL', 'HAMMER', 'SABRE', 'LANCER', 'VANGUARD', 'TALON',
              'REAPER', 'WARDEN', 'BASILISK', 'TEMPEST', 'GRENADIER',
              'MARSHAL', 'PIKEMAN', 'HALBERD')
PILOT_CALLS = ('SPECTER', 'HAVOC', 'VIPER', 'GHOST', 'JACKAL', 'RAPTOR',
               'NOMAD', 'FURY', 'CINDER', 'MAGPIE', 'DRIFTER', 'TINDER',
               'KESTREL', 'BADGER', 'SALVO', 'RIVET')


class Crew:
    """Who is flying it. Rolled once; --seed pins the roll."""

    __slots__ = ('callsign', 'pilot', 'hull', 't0')

    def __init__(self, seed=None):
        rng = random.Random(seed)
        self.callsign = '%s-%d' % (rng.choice(UNIT_CALLS), rng.randint(1, 6))
        self.pilot = rng.choice(PILOT_CALLS)
        self.hull = '%04X' % rng.randrange(0x10000)
        self.t0 = time.time()

    def line(self, wide):
        """Sheds the hull number first on a narrow viewport: a full crew line
        at 90 columns runs straight across the top of the lock bracket."""
        el = int(time.time() - self.t0)
        if wide:
            return '%s · %s · HULL %s   T+%02d:%02d' % (
                self.callsign, self.pilot, self.hull, el // 60, el % 60)
        return '%s · %s   T+%02d:%02d' % (self.callsign, self.pilot,
                                          el // 60, el % 60)


def draw(ov, P, panel, rows, cols, crew, az, el, wipey, now):
    H, HD = P['hud'], P['hud_dim']

    def ctext(r, c, t, col=None):
        ov.text(r, c, t, col or HD, None)

    # Six columns held back on the right, not four: the ladder labels are three
    # wide ('+20') and at four they ran off the last column and vanished.
    vx0, vx1 = panel + 1, cols - 6
    vy0, vy1 = 1, rows - 2
    if not (vx1 - vx0 > 20 and vy1 - vy0 > 6):
        return

    # Viewport corners. Thin and dim on purpose: the lock frame is heavy
    # (┏━┃) and moves, this is light (┌─│) and does not, so the two never read
    # as the same object.
    ctext(vy0, vx0, '┌──')
    ctext(vy0, vx1 - 2, '──┐')
    ctext(vy1, vx0, '└──')
    ctext(vy1, vx1 - 2, '──┘')
    for d in (1, 2):
        ctext(vy0 + d, vx0, '│')
        ctext(vy0 + d, vx1, '│')
        ctext(vy1 - d, vx0, '│')
        ctext(vy1 - d, vx1, '│')

    line = crew.line(vx1 - vx0 >= 90)
    rec = (now % 1.4) < 0.95
    ctext(vy0, max(vx0 + 4, vx1 - len(line) - 4), line)
    if rec:
        ov.text(vy0, max(vx0 + 1, vx1 - len(line) - 7), '●', P['alert'], None)

    # Wipe markers. The chrome's one moving part, and it only moves while the
    # sensor is actually acquiring -- the line between the two carets is the
    # same line the renderer is holding geometry back behind.
    if wipey is not None:
        wr = int(wipey / 2)
        if vy0 < wr < vy1:
            ov.text(wr, vx0, '▶', P['sel'], None)
            ov.text(wr, vx1, '◀', P['sel'], None)

    # Bearing tape, on the camera's real azimuth. Gridlines every 15°,
    # cardinals spelled out, caret fixed at the centre -- so the tape slides
    # under the caret as the turntable comes round, which is what a tape is.
    tw = vx1 - vx0 - 1
    brg_c = math.degrees(az) % 360.0
    dpc = CHROME_SPAN / tw
    tr = vy1 - 1
    ctext(tr, vx0 + 1, '·' * tw)
    g = int((brg_c - CHROME_SPAN / 2.0) // 15) * 15
    while g <= brg_c + CHROME_SPAN / 2.0:
        lab = CARDINAL.get(g % 360, '%03d' % (g % 360))
        cx_ = vx0 + 1 + int(tw / 2.0 + (g - brg_c) / dpc)
        c0_ = cx_ - len(lab) // 2
        if vx0 < c0_ and c0_ + len(lab) <= vx1:
            ctext(tr, c0_, lab, H if len(lab) < 3 else HD)
        g += 15
    ov.text(tr, vx0 + 1 + tw // 2, '▲', P['sel'], None)

    # Elevation ladder, on the camera's real tilt.
    lx = vx1 + 2
    lh = vy1 - vy0 - 3
    if lh > 4 and lx < cols - 1:
        el_c = math.degrees(el)
        mid = vy0 + 2 + lh // 2
        dpr = CHROME_EL / lh
        e = int((el_c - CHROME_EL / 2.0) // 10) * 10
        while e <= el_c + CHROME_EL / 2.0:
            r_ = mid + int((el_c - e) / dpr)
            if vy0 + 1 < r_ < vy1:
                if e % 20 == 0:
                    ctext(r_, lx, ' 00' if e == 0 else '%+03d' % e, H)
                else:
                    ctext(r_, lx, '─')
            e += 10
        ov.text(mid, lx - 1, '◀', P['sel'], None)
