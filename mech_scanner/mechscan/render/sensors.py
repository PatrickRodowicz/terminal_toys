"""The four sensor channels, and the acquisition wipe that runs across them.

Each channel is a different question asked of the same mesh, and each answers
it from something already measured -- nothing here is a filter laid over a
picture.

  OPTICAL  the lit hull.
  THERMAL  false colour from a heat field with the fusion plant as its source.
           See mesh/thermal.py. The first version false-coloured ambient
           occlusion alone and got a cold torso, which is nonsense on a machine
           built around a 375-rated reactor.
  LIDAR    a range return, drawn as a point cloud, brightness by range.
  XRAY     the inversion: the near skin drops to a ghost and the FAR side of
           the hull is drawn bright, with the reactor marked. Wireframe rather
           than translucency because the painter's algorithm has no blend
           buffer to be honest with.

LIDAR and XRAY were very nearly the same picture at one point -- both drew
grazing-angle contours and XRAY only added the far side at 62% brightness,
which on a mostly convex hull lands inside the silhouette and reads as noise.
Two sensors that produce the same image are one sensor with two names.
"""

from ..ansi import lerp

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

# XRAY draws the far side bright and the near skin as a ghost, so the two need
# to be separable at a glance; and the reactor gets its own colour because it
# is the one thing on a diagnostic x-ray you could not possibly miss.
XRAY_FAR = (176, 208, 255)
XRAY_CORE = (255, 232, 150)
SCAN_GRAZE = 0.42        # |n . view| below this is a contour, and only those
                         # get drawn -- outlining all 6,000 facets fills the
                         # silhouette with scribble and shows nothing.
