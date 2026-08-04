"""Changing target while the sight is running.

Building a mech is seconds of work on a cold cache -- decimation, a voxel
occupancy grid, a hemisphere of rays per facet, segmentation -- and the frame
loop cannot stop for it. A sight that freezes for four seconds is a sight that
has failed. So the build runs on a worker thread while the display keeps
turning the CURRENT target, and the pipeline's own progress messages become the
acquisition readout.

Nothing on that readout is invented. Every line is a stage that actually ran,
and a warm cache says so rather than miming four seconds of work it did not do.

There is deliberately **no progress bar**. The number of stages is not known
before they happen, so a bar would have to guess at its own denominator, and
this project has already learned once what a bar that cannot honestly reach
100% does to a display -- see the long note in sweep.py about why the scan
completes on a revolution of bearing rather than on coverage. Elapsed seconds
is the readout instead, because it is the one number actually known.

Two threading rules, both load-bearing:

  * The worker builds a Rig and touches NOTHING else. In particular it does not
    write to stdout: the emitter owns that and holds the writer's lock for most
    of every frame, so a second writer would land in the middle of a frame.
    The note callback appends to a list instead.
  * The SWAP happens in the frame loop, at the top of a frame, before anything
    has read `rig`. Half a frame drawn against the old mesh and half against
    the new is precisely the class of bug `Scan.bind` already guards against,
    and there is no reason to invite it in.

The thread is a daemon. A signal teardown must not wait for a decimation to
finish before it can put the terminal back.
"""
import threading
import time

# How long the readout stays up even when a warm cache makes the build instant.
# Not padding for its own sake: a state that appears and vanishes inside one
# frame is a flicker, and the thing worth reading is WHICH machine was
# acquired. The lines on it stay true either way.
MIN_HOLD = 1.15
# A failure is held longer, because it carries a reason worth reading.
FAIL_HOLD = 3.4


class Acquisition:
    """One in-flight target change: a worker, its notes, and its result."""

    __slots__ = ('name', 'mech', 'lines', 't0', 't1', 'rig', 'err', 'thread')

    def __init__(self, name, mech, build):
        self.name = name          # the mech directory name
        self.mech = mech          # canon.Mech, adopted by the app on swap
        self.lines = []
        self.rig = None
        self.err = None
        self.t0 = time.time()
        # When the build actually stopped, so the readout can freeze the
        # elapsed figure at what the work cost instead of ticking on through
        # the hold and reporting the hold.
        self.t1 = None
        self.thread = threading.Thread(target=self._run, args=(build,),
                                       daemon=True)
        self.thread.start()

    # -- worker side -------------------------------------------------------
    def _run(self, build):
        # `rig` and `err` are what the frame loop polls, so each is assigned
        # LAST, after t1 -- otherwise the loop can see a finished acquisition
        # with no time to report against it. One frame of '0.0 s' is a small
        # thing to get wrong; reading a None is not.
        try:
            rig = build(self._note)
        except BaseException as e:
            # Deliberately everything. An exception that escapes a thread does
            # not reach the frame loop -- it prints a traceback over the
            # display and vanishes -- and this acquisition would then never
            # finish and never clear, hanging the readout forever. A failure
            # has to become a value the frame loop can see.
            self.t1 = time.time()
            self.err = '%s: %s' % (type(e).__name__, e)
        else:
            self.t1 = time.time()
            self.rig = rig

    def _note(self, msg):
        # list.append is atomic, and that is the whole of the synchronisation
        # here: the frame loop only ever reads this list, never writes it.
        self.lines.append(msg)

    # -- frame-loop side ---------------------------------------------------
    @property
    def finished(self):
        return self.rig is not None or self.err is not None

    def ready(self, now):
        """The new rig, once it exists AND has been on screen long enough."""
        if self.rig is not None and now - self.t0 >= MIN_HOLD:
            return self.rig
        return None

    def spent(self, now):
        """A failed acquisition that has been up long enough to have been read."""
        return self.err is not None and now - self.t0 >= FAIL_HOLD
