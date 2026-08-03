"""Everything the renderer reads out of the app's state, resolved once a frame.

The frame loop owns a couple of dozen toggles. Passing them one at a time to
four render functions is how a signature grows to twenty arguments and how a
mode ends up half-applied because one call site was missed. So they are
resolved here, in one place, into the derived flags the renderer actually asks
about -- and the derivations are the interesting part:

  `nosun`  is not the same as `wireonly`. Gating the sky on `wireonly` alone
           left THERMAL sitting on a blue sky over daylit olive ground with a
           hard sun shadow under it, which reads as an optical photograph that
           somebody tinted -- exactly the thing the channel is not. Any channel
           that is not the eye draws on an instrument field.
"""

from ..lighting import LIGHT_FULL
from .sensors import (SENSOR_LIDAR, SENSOR_THERMAL, SENSOR_XRAY)


class View:
    """Derived render state for one frame. Cheap to build, read-only in use."""

    __slots__ = ('stl_mode', 'zen', 'sensor', 'light_mode', 'pal', 'mat',
                 'ao_on', 'cutplane', 'psel_on', 'see_through', 'wireonly',
                 'nosun', 'sky_c', 'bounce_c', 'sel_col', 'fogc',
                 'fog0', 'fog1', 'fogd')

    def __init__(self, stl_mode, zen, sensor, light_mode, pal, mat, P, ao_on,
                 cutplane, dist, mrad):
        self.stl_mode = stl_mode
        self.zen = zen
        self.sensor = sensor
        self.light_mode = light_mode
        self.pal = pal
        self.mat = mat
        self.ao_on = ao_on
        self.cutplane = cutplane

        self.psel_on = sensor != SENSOR_THERMAL
        self.see_through = sensor == SENSOR_XRAY
        self.wireonly = sensor in (SENSOR_LIDAR, SENSOR_XRAY)
        self.nosun = self.wireonly or sensor == SENSOR_THERMAL

        self.sky_c = P['sky'][1]
        self.bounce_c = P['bounce']
        self.sel_col = P['sel']
        self.fogc = P['sky'][1]
        self.fog0 = dist - mrad * 1.6
        self.fog1 = dist + mrad * 2.4
        self.fogd = 1.0 / (self.fog1 - self.fog0)

    @property
    def fog_on(self):
        return self.light_mode == LIGHT_FULL and self.sensor != SENSOR_THERMAL
