"""The left-hand panel, in its four pages.

COMBAT is what a gunner would want and nothing about the renderer. It requires
canon, because most of what is on it -- tonnage, loadout, heat sinks, speeds --
is not a property of a mesh. SURVEY is what COMBAT becomes when we do not know
what the mesh depicts: the measured half alone. MESH (m) is the renderer's own
report. STRUCTURE is the built-in model's part list, which is a different kind
of object -- articulated, with a mass per part -- and gets a page shaped for
that.

Two sources and no third, and every block says which it is: the canon table,
which is Sarna's, and the mesh, which is measured. The interesting cases are
the ones that mix them -- the armour spread below is twelve canon tons
distributed over MEASURED skin area. When there is no canon there is no mixing
to do, and SURVEY is measurement only.
"""
import os

from ..mesh.model import LOD_NAMES, MODEL_H
from ..mesh.segment import SECTIONS, section_names
from ..text import bar_str, commas


def _blank(ov, P, panel, rows):
    H, PN = P['hud'], P['panel']
    for r in range(1, rows):
        ov.text(r, 0, ' ' * panel, H, PN)


def _field(ov, P, panel, r, k, v, hot=False):
    H, HD, PN = P['hud'], P['hud_dim'], P['panel']
    ov.text(r, 1, k[:panel - 3], HD, PN)
    ov.text(r, max(len(k) + 2, panel - 1 - len(v)),
            v, P['sel'] if hot else H, PN)


def draw_combat(ov, P, panel, rows, report, sel, canon):
    """Designation, armour, loadout, heat, mobility, airframe.

    Ordered by what a gunner needs first, then simply cut to fit: a short
    terminal loses the airframe trivia, not the armour spread.
    """
    if not canon:
        return draw_survey(ov, P, panel, rows, report, sel)
    H, HD, PN = P['hud'], P['hud_dim'], P['panel']
    _blank(ov, P, panel, rows)
    W = panel - 2

    # Every block is conditional on the canon.md actually carrying the field.
    # A mech whose sources say nothing about its engine gets no AIRFRAME block
    # -- not an AIRFRAME block with a blank in it, and certainly not a
    # plausible-looking engine. That is the whole contract of the file format:
    # absent means absent, and the readout gets shorter rather than wrong.
    g = canon.get
    lines = []          # (kind, a, b, hot)
    lines.append(('head', g('name'), '', False))
    sub = '  '.join(x for x in (g('codename'), g('config')) if x)
    if sub:
        lines.append(('text', sub, '', False))
    lines.append(('rule', '', '', False))
    if g('mass_t') or g('origin'):
        lines.append(('kv',
                      '%g t' % g('mass_t') if g('mass_t') else '',
                      g('origin') or '', False))
    lines.append(('blank', '', '', False))

    # Armour is a SKIN, so the canon tonnage is spread by surface area and not
    # by displacement -- an arm has far more skin per cubic metre than the
    # torso does, and distributing by volume would have quietly armoured the
    # torso at the limbs' expense.
    area = report.get('sec_area') or []
    if g('armour_t'):
        lines.append(('sec', 'ARMOUR', '%.1f t' % g('armour_t'), False))
        # What the caption has to say is HOW the tonnage was distributed,
        # because that is the one line on this page mixing a canon number with
        # a measured one. The armour type is a separate fact and lives in
        # AIRFRAME with the rest of the construction trivia -- interpolating it
        # here produced 'composite a-2 ferro-fibr' and said nothing.
        lines.append(('dim', 'by measured skin area', '', False))
        for si, _sc in enumerate(SECTIONS):
            if si >= len(area):
                break
            lines.append(('bar', si, '%4.1f' % (area[si] * g('armour_t')),
                          si == sel))
        lines.append(('blank', '', '', False))

    if g('weapons'):
        lines.append(('sec', 'LOADOUT', g('config') or '', False))
        for wn, wc in g('weapons'):
            lines.append(('wpn', wn, '%d' % wc, False))
        lines.append(('blank', '', '', False))

    if g('heatsinks'):
        lines.append(('sec', 'HEAT', '', False))
        lines.append(('kv', 'sinks', g('heatsinks'), False))
        lines.append(('blank', '', '', False))

    if g('walk_mp') or g('run_mp'):
        lines.append(('sec', 'MOBILITY', '', False))
        for mp, speed, label in ((g('walk_mp'), g('cruise'), 'walk'),
                                 (g('run_mp'), g('flank'), 'run')):
            if mp:
                lines.append(('kv', '%s %d' % (label, mp),
                              '%.1f km/h' % speed if speed else '', False))
        lines.append(('blank', '', '', False))

    air = [x for x in (g('chassis'), g('engine'), g('armour')) if x]
    if air or g('podspace') or g('intro'):
        lines.append(('sec', 'AIRFRAME', '', False))
        for x in air:
            lines.append(('dim', x, '', False))
        if g('podspace'):
            lines.append(('kv', 'pod space', '%.1f t' % g('podspace'), False))
        if g('intro'):
            lines.append(('kv', 'introduced', '%d' % g('intro'), False))

    amax = max(area) if area else 1.0
    rr = 1
    for kind, a, b, hotl in lines:
        if rr >= rows - 2:
            break
        if kind == 'head':
            ov.text(rr, 1, a[:W], P['sel'], PN)
        elif kind == 'rule':
            ov.text(rr, 1, '─' * W, HD, PN)
        elif kind == 'sec':
            ov.text(rr, 1, ('%s %s' % (a, '─' * W))[:W - len(b) - 1], H, PN)
            if b:
                ov.text(rr, panel - 1 - len(b), b, P['sel'], PN)
        elif kind == 'text':
            ov.text(rr, 1, a[:W], H, PN)
        elif kind == 'dim':
            ov.text(rr, 1, a[:W], HD, PN)
        elif kind == 'kv':
            _field(ov, P, panel, rr, a, b, hotl)
        elif kind == 'wpn':
            ov.text(rr, 1, ('%sx ' % b) + a[:W - 3], H, PN)
        elif kind == 'bar':
            ov.text(rr, 1, ('▸' if hotl else ' ')
                    + section_names(True)[SECTIONS[a]][:8],
                    P['sel'] if hotl else H, PN)
            # Right-aligned off the panel edge, not off a hand-counted column:
            # '%4.1f t' is six characters and panel-5 gave it five, so the unit
            # spilled two cells into the model.
            val = b + ' t'
            if panel >= 22:
                ov.text(rr, panel - 8 - len(val),
                        bar_str(area[a] / amax, 6), HD, PN)
            ov.text(rr, panel - 1 - len(val), val,
                    P['sel'] if hotl else HD, PN)
        rr += 1


def draw_survey(ov, P, panel, rows, report, sel):
    """COMBAT with the canon removed: what is actually known about this mesh.

    Everything here is measured, and the page is deliberately shorter than the
    one it replaces -- because without a source for the fiction, most of a
    combat readout simply does not exist. No mass: mass is not a property of a
    mesh. No armour spread: there are no tons to spread. The sections keep
    their measured volume shares, under names that describe what the
    segmentation found rather than what a mech would have there.
    """
    H, HD, PN = P['hud'], P['hud_dim'], P['panel']
    _blank(ov, P, panel, rows)
    W = panel - 2
    names = section_names(False)
    bbox = report.get('bbox') or (0, 0, 0)
    scale = report.get('scale') or 1.0
    share = report.get('sec_share') or []
    area = report.get('sec_area') or []

    ov.text(1, 1, 'UNIDENTIFIED'[:W], P['sel'], PN)
    ov.text(2, 1, 'no canon source'[:W], HD, PN)
    ov.text(3, 1, '─' * W, HD, PN)

    lines = [('kv', 'height', '%.1f m' % MODEL_H),
             ('kv', 'width', '%.1f m' % (bbox[0] * scale)),
             ('kv', 'depth', '%.1f m' % (bbox[1] * scale)),
             ('blank', '', ''),
             ('sec', 'MEASURED', ''),
             ('kv', 'volume', '%.1f m³' % report['built_volume']),
             ('kv', 'surface', '%.1f m²' % report['built_area']),
             ('kv', 'watertight', 'yes' if report['watertight'] else 'no'),
             ('kv', 'sealed', 'yes' if report.get('sealed') else 'NO'),
             ('blank', '', ''),
             ('sec', 'SECTIONS', ''),
             # Volume and skin side by side, because the difference between
             # them is the only interesting thing about the pair. On the
             # reference mesh the torso is 63.0% of the displacement but only
             # 59.3% of the surface, which is exactly why armour is spread by
             # area and not by volume. On a shape of uniform thickness the two
             # columns agree, and that is worth being able to see.
             ('head2', 'vol', 'skin')]
    for si, _sc in enumerate(SECTIONS):
        if si >= len(share):
            break
        lines.append(('bar', si,
                      (area[si] * 100.0) if si < len(area) else 0.0))

    wide = panel >= 24
    rr = 4
    for kind, a, b in lines:
        if rr >= rows - 2:
            break
        if kind == 'sec':
            ov.text(rr, 1, ('%s %s' % (a, '─' * W))[:W], H, PN)
        elif kind == 'dim':
            ov.text(rr, 1, a[:W], HD, PN)
        elif kind == 'head2':
            # The skin column is the first thing to go on a narrow panel. It
            # is the more interesting of the two, but it needs its neighbour
            # to mean anything, and squeezing both truncated the section names
            # to 'upper'/'lower' -- which loses the side, and a section list
            # that cannot tell you left from right is worse than one column.
            ov.text(rr, panel - (12 if wide else 6),
                    ('%5s %5s' % (a, b)) if wide else '%5s' % a, HD, PN)
        elif kind == 'kv':
            _field(ov, P, panel, rr, a, b, False)
        elif kind == 'bar':
            hot = a == sel
            ov.text(rr, 1, ('▸' if hot else ' ') + names[SECTIONS[a]][:8],
                    P['sel'] if hot else H, PN)
            ov.text(rr, panel - (12 if wide else 6),
                    ('%4.1f%% %4.1f%%' % (share[a] * 100.0, b)) if wide
                    else '%4.1f%%' % (share[a] * 100.0),
                    P['sel'] if hot else HD, PN)
        rr += 1


def draw_mesh(ov, P, panel, rows, report, model_name, lod_i, ao_on, drawn,
              fps_avg, mass=None):
    """The renderer's own report. Numbers about the renderer live here and
    nowhere else -- a facet count is not something a gunner wants on a
    targeting display."""
    HD, PN = P['hud_dim'], P['panel']
    _blank(ov, P, panel, rows)
    ov.text(1, 1, os.path.basename(model_name)[:panel - 2], P['sel'], PN)
    ov.text(2, 1, '─' * (panel - 2), HD, PN)

    rr = 3
    for k, v in (
            ('source', commas(report['src_tris'])),
            ('vertices', commas(report['src_verts'])),
            ('edges', commas(report['edges'])),
            ('watertight', 'yes' if report['watertight'] else 'no'),
            ('', ''),
            (LOD_NAMES[lod_i] if lod_i < len(LOD_NAMES)
             else 'LOD %d' % lod_i, ''),
            ('facets', commas(report['faces'])),
            ('of source', '%.2f%%'
             % (report['faces'] / float(report['src_tris']) * 100.0)),
            ('vol error', '%+.2f%%' % report['vol_err']),
            ('area error', '%+.2f%%' % report['area_err']),
            ('', ''),
            ('AS BUILT', ''),
            ('height', '%.1f m' % MODEL_H),
            ('volume', '%.1f m³' % report['built_volume']),
            # Mass only where there is a canon source for it. With none, the
            # row is absent rather than showing a zero or a guess.
            ('mass' if mass else '', '%.1f t' % mass if mass else ''),
            ('drawn', commas(drawn)),
            ('fps', '%.1f' % fps_avg),
            ('', ''),
            ('occlusion', 'on' if ao_on else 'off'),
            ('ao reach', '%g vox' % report['ao_radius']),
            ('grid', '%d³' % report['vox']),
            ('solid cells', commas(report['solid_cells'])),
            ('sealed', 'yes' if report.get('sealed') else 'NO')):
        if rr >= rows - 2:
            break
        if k:
            _field(ov, P, panel, rr, k, v, hot=k in ('facets', 'occlusion'))
        rr += 1


def draw_structure(ov, P, panel, rows, parts, sel, total_mass):
    """The built-in model's part list: an articulated assembly, by mass."""
    H, HD, PN = P['hud'], P['hud_dim'], P['panel']
    mx = max((p.mass for p in parts), default=1.0) or 1.0
    _blank(ov, P, panel, rows)
    ov.text(1, 1, 'STRUCTURE', P['sel'], PN)
    ov.text(2, 1, '─' * (panel - 2), HD, PN)
    top = max(0, min(sel - (rows - 8) // 2, len(parts) - (rows - 8)))
    r = 3
    for i in range(top, len(parts)):
        if r >= rows - 4:
            break
        p = parts[i]
        cur = i == sel
        # The bar is the first thing to go when the panel is narrow: a two-cell
        # bar says nothing a number does not.
        wide = panel >= 24
        nm = p.name[:panel - (15 if wide else 8)]
        ov.text(r, 1, ('▸' if cur else ' ') + nm, P['sel'] if cur else H, PN)
        if wide:
            ov.text(r, panel - 13, bar_str(p.mass / mx, 7), HD, PN)
        ov.text(r, panel - 5, '%4.1f' % p.mass, P['sel'] if cur else HD, PN)
        r += 1
    if parts and sel >= 0:
        p = parts[sel]
        ov.text(rows - 4, 1, '─' * (panel - 2), HD, PN)
        ov.text(rows - 3, 1, p.name[:panel - 2], P['sel'], PN)
        ov.text(rows - 2, 1, '%s  %.1f m³  %d f'
                % (p.group, p.volume, len(p.faces)), HD, PN)
        ov.text(rows - 5, 1, '%-*s%5.1f t'
                % (panel - 8, 'TOTAL', total_mass), H, PN)
