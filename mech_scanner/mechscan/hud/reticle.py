"""The lock brackets and the instrument strip.

Both are driven by measurement rather than by decoration. The brackets track
the model's real projected silhouette, which the fill loop already accumulated
facet by facet -- not a guess from the bounding sphere, so they tighten on the
legs when the arms swing out of frame under the cutaway.

The strip's SCAN field was a barber pole -- (sim * 0.7) % 1.0 -- and it loaded
forever and meant nothing. It now fills with the BEARING swept since the scan
began and completes on a full revolution, and the percentage beside it is how
much of the hull actually returned. 'Every facet returned' was tried and
measured as the wrong test: it stalls near 96%, because at a fixed tilt some of
the hull -- undersides, the inside of a shoulder -- never turns to face the
sensor at any bearing at all. That is a fact about the geometry, not an
unfinished job, so the strip stops counting and reports the achieved figure.
"""
import math

from ..mesh.segment import SECTIONS, section_names
from ..render.sensors import SENSOR_NAMES
from ..text import bar_str


def draw_brackets(ov, P, sil, panel, rows, cols, subx, locked):
    """Returns True if the brackets were drawn, i.e. there is a target on
    screen at all -- which is also the condition for the strip below."""
    H, HD = P['hud'], P['hud_dim']
    bc0 = max(panel, int(sil[0] / subx) - 1)
    bc1 = min(cols - 2, int(sil[2] / subx) + 1)
    br0 = max(1, int(sil[1] / 2) - 1)
    br1 = min(rows - 3, int(sil[3] / 2) + 1)
    # Lock follows the SWEEP, not the wall clock. It used to brighten 1.2 s
    # after the program started, which meant the brackets said LOCK before the
    # sensor had seen the far side of the target -- and made the frame at which
    # they changed depend on how fast the host happened to be running. Found by
    # a pixel-diff harness that could not get two runs to agree.
    BR = H if locked else HD
    arm = max(2, min(6, (bc1 - bc0) // 4))
    vrm = max(1, min(3, (br1 - br0) // 4))
    if not (bc1 > bc0 and br1 > br0):
        return
    ov.text(br0, bc0, '┏' + '━' * (arm - 1), BR)
    ov.text(br0, bc1 - arm + 1, '━' * (arm - 1) + '┓', BR)
    ov.text(br1, bc0, '┗' + '━' * (arm - 1), BR)
    ov.text(br1, bc1 - arm + 1, '━' * (arm - 1) + '┛', BR)
    for rr in range(1, vrm + 1):
        ov.text(br0 + rr, bc0, '┃', BR)
        ov.text(br0 + rr, bc1, '┃', BR)
        ov.text(br1 - rr, bc0, '┃', BR)
        ov.text(br1 - rr, bc1, '┃', BR)
    mc = (bc0 + bc1) // 2
    mr = (br0 + br1) // 2
    ov.text(mr, mc - 1, '─┼─', BR)


def draw_strip(ov, P, cols, sensor, scan, report, parts, sel, brg, elv,
               rng, mass=None, canon=None):
    H, HD, PN = P['hud'], P['hud_dim'], P['panel']
    # Tonnage where canon supplies a tonnage; otherwise the share of measured
    # volume, which is a real number about the actual mesh. The sight reports
    # what it knows and does not pad the field to look the same either way.
    # Field widths differ between the two because the names do: the mech names
    # fit in six ('arm L'), the geometric ones need seven ('upper L'). Sizing
    # both to the wider would shift the whole strip on the reference model for
    # the sake of a case it never hits.
    if report and 0 <= sel < len(SECTIONS):
        share = report.get('sec_share') or []
        frac = share[sel] if sel < len(share) else 0.0
        sname = section_names(canon)[SECTIONS[sel]].upper()
        starg = ('%-6s %5.1f t' % (sname, frac * mass) if mass
                 else '%-7s %5.1f%%' % (sname, frac * 100.0))
    elif report:
        starg = ('%-6s %5.1f t' % ('HULL', mass) if mass
                 else '%-7s %5s' % ('HULL', '--'))
    else:
        starg = '%-6s' % ('--' if sel < 0 else parts[sel].name[:6])
    cov = scan.coverage
    if scan.sweeping and scan.left:
        scantxt = 'SCAN %s %3d%%' % (bar_str(scan.sweep / (2.0 * math.pi), 8),
                                     int(cov * 100.0))
    else:
        scantxt = 'SWEPT 360°  %3d%%' % int(cov * 100.0)
    # Target before bearing: at 80 columns the strip runs off the right-hand
    # edge, and what a gunner loses last is what they are shooting at, not the
    # elevation readout.
    strip = ('MK-VII  %-7s  %-18s  TGT %s   BRG %05.1f  EL %+05.1f  RNG %05.1f m'
             % (SENSOR_NAMES[sensor], scantxt, starg, brg, elv, rng))
    ov.text(0, 0, ' ' * cols, HD, PN)
    ov.text(0, 1, strip[:cols - 2], H, PN)
