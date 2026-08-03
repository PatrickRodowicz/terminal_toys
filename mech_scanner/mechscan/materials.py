"""What the machine is made of.

One entry per material, not per part -- see the comment below. `DENSITY` is
what turns a modelled volume into a believable tonnage for the built-in mech;
the loaded STL takes its mass from CANON instead and derives its density.
"""

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
