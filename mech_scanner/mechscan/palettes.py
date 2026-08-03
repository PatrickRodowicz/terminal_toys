"""Screen palettes, and the hue collapse that produces the tinted ones."""
import colorsys

from .materials import MATERIALS

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
