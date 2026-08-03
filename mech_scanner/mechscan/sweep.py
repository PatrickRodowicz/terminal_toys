"""The sensor sweep: what the instrument has actually seen.

Not a decorative barber pole. `seen` is a byte per facet, set the first time
that facet survives the backface test in the gather loop, so `coverage`
measures how much of the hull the sensor has genuinely returned as the target
turns. It fills as you orbit, it completes, and it stays complete.

Completion is a full REVOLUTION of bearing, not full coverage. 'Every facet
returned' was measured and is the wrong test -- it stalls around 96%, because
at a fixed tilt some of the hull never faces the sensor at any bearing at all.
A bar that asymptotes short of full is the loading-forever bar again. A
revolution is the test that terminates and that means something: the sensor has
now seen the target from every bearing, and the coverage it reached is the
fraction of hull a sweep at this elevation can return.
"""
import math

TWO_PI = 2.0 * math.pi

# The acquisition wipe: while the sensor is still sweeping, a bright line runs
# down the target and the geometry it has not reached yet is held back. The
# line is compared in SCREEN space rather than world space -- at these tilts a
# horizontal world plane projects to within a pixel of a horizontal screen
# line, and doing it in screen space costs two comparisons against numbers the
# fill loop has already computed for the gradient test.
WIPE_PERIOD = 2.1        # seconds for one pass down the frame
WIPE_BAND = 3.0          # pixels either side of the line that read as the edge
WIPE_HELD = 0.46         # brightness of geometry the wipe has not reached


class Scan:
    __slots__ = ('seen', 'left', 'total', 'sweep', 'az')

    def __init__(self):
        self.seen = None
        self.left = 0
        self.total = 0
        self.sweep = 0.0      # radians of bearing covered since the scan began
        self.az = None

    def restart(self):
        """Drop the scan entirely. The next bind() rebuilds it."""
        self.seen = None

    def bind(self, parts, az):
        """One bytearray per part, rebuilt whenever the part list changes, so a
        level-of-detail switch cannot be scored against the hull it is no
        longer drawing."""
        if self.seen is not None and len(self.seen) == len(parts):
            return
        self.seen = [bytearray(len(p.faces)) for p in parts]
        self.total = sum(len(p.faces) for p in parts) or 1
        self.left = self.total
        self.sweep, self.az = 0.0, az

    def advance(self, az):
        self.sweep += abs(az - self.az)
        self.az = az

    @property
    def sweeping(self):
        return self.sweep < TWO_PI

    @property
    def coverage(self):
        return 1.0 - self.left / float(self.total or 1)

    def wipe_y(self, sim, pxh):
        """Screen row of the acquisition wipe, or None once the sweep is done.

        Active only while the sweep is running, so it is a thing that happens
        and then stops rather than an animation that loops forever -- which is
        what the old scan bar was.
        """
        if not self.sweeping:
            return None
        return (sim % WIPE_PERIOD) / WIPE_PERIOD * pxh
