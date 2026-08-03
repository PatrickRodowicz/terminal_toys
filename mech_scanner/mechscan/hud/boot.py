"""The cold start.

Drawn INSIDE the frame loop rather than as a blocking prologue. The renderer is
already running behind it, so the last half second can wipe the panel away and
reveal a display that is already turning, and nothing has to be special-cased
in the signal teardown.

The numbers on it are the real ones from this run's load -- facet count, grid
size, solid cells, sections found -- so the POST is reporting on work that
actually happened rather than reciting a script.
"""

from ..mesh.segment import SECTIONS
from ..render.sensors import SENSOR_NAMES
from ..text import bar_str, commas

BOOT_LINE_DT = 0.16       # seconds between lines
BOOT_HOLD = 0.85          # pause on the completed list
BOOT_WIPE = 0.55          # the reveal


def checklist(report, nparts, canon=None):
    """What the POST reports. Real numbers where there are real numbers."""
    if not report:
        return (('power bus', 'nominal'),
                ('gyro spin-up', '3200 rpm'),
                ('structural model', '%d parts' % nparts),
                ('optics calibration', 'nominal'))
    return (
        ('power bus', 'nominal'),
        ('gyro spin-up', '3200 rpm'),
        ('sensor head', '%d channels' % len(SENSOR_NAMES)),
        ('mesh load', '%s facets' % commas(report['src_tris'])),
        ('watertight', 'yes' if report['watertight'] else 'NO'),
        ('occupancy grid', '%d³' % report['vox']),
        ('solid cells', commas(report['solid_cells'])),
        ('limb segmentation', '%d sections' % len(SECTIONS)),
        ('reactor trace', 'located' if report.get('reactor_m') else 'n/a'),
        # The armour figure is canon, so the POST only claims to have loaded
        # an armour model when there is one to load.
        (('armour model', '%.1f t' % canon['armour_t']) if canon
         else ('canon source', 'none — survey only')),
        ('optics calibration', 'nominal'),
    )


def duration(checks):
    return len(checks) * BOOT_LINE_DT + BOOT_HOLD + BOOT_WIPE


def draw(ov, P, rows, cols, checks, bt):
    """Returns False once the sequence has run out."""
    H, HD, PN = P['hud'], P['hud_dim'], P['panel']
    blen = duration(checks)
    if bt >= blen:
        return False
    # The reveal: the panel retreats up the screen over the last half second,
    # uncovering a display that has been running behind it the whole time.
    left = blen - bt
    cover = rows if left > BOOT_WIPE else int(rows * (left / BOOT_WIPE))
    for r in range(cover):
        ov.text(r, 0, ' ' * cols, HD, PN)
    bc = max(2, (cols - 46) // 2)
    br = max(0, (rows - len(checks) - 6) // 2)

    def btext(r, c, t, col=None):
        if r < cover:
            ov.text(r, c, t[:cols - c], col or HD, PN)

    btext(br, bc, 'MK-VII TARGETING AND DIAGNOSTIC SUITE', P['sel'])
    btext(br + 1, bc, 'firmware 4.2.7 · cold start')
    nshow = int(bt / BOOT_LINE_DT)
    for i, (nm, val) in enumerate(checks):
        if i >= nshow:
            break
        r = br + 3 + i
        ok = i < nshow - 1 or bt > len(checks) * BOOT_LINE_DT
        btext(r, bc, '[%s] %-20s' % ('OK' if ok else '··', nm),
              H if ok else HD)
        if ok:
            btext(r, bc + 26, val)
    r = br + 4 + len(checks)
    frac = min(1.0, bt / (len(checks) * BOOT_LINE_DT))
    btext(r, bc, '%s  %3d%%' % (bar_str(frac, 30), int(frac * 100)))
    if frac >= 1.0:
        btext(r + 2, bc, 'SYSTEMS NOMINAL — ACQUIRING TARGET', P['sel'])
    return True
