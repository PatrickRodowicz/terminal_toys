"""The light rig, and the lighting modes that switch parts of it off.

World-fixed, which is the fact the whole renderer is built around: the
turntable moves the EYE, not the mech, so for a facet that has not moved
n.SUN and n.FILL are exactly the numbers they were last frame. That is what
makes the lit-colour cache in render/facets.py exact rather than approximate.
"""

from .math3d import normed

# How dark a fully occluded facet goes. Occlusion multiplies brightness, so 0.34
# means a facet buried in an armpit keeps a third of its lit value -- enough to
# stay a surface rather than become a hole.
AO_FLOOR = 0.34

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
LIGHT_FULL, LIGHT_KEY, LIGHT_FLAT = 0, 1, 2
LIGHT_NAMES = ('LIGHTING FULL', 'LIGHTING KEY ONLY', 'LIGHTING FLAT')
LIGHT_ARGS = ('full', 'key', 'flat')

# A facet gets a top-to-bottom gradient only if it is at least this tall on
# screen. The gradient is what makes a cylindrical limb on the built-in model
# read as round -- but STL facets average 0.93 scanlines at 80x24, and a
# gradient across one scanline is one colour bought at the price of a lerp and
# a quant on every scanline of every facet. So spend it only where it shows.
GRAD_MIN_H = 5.0
