"""One bone of the built-in mech's skeleton."""

from ..math3d import IDENT, mmul, mvec

class Frame:
    """One bone. `rot` is its rest orientation in the parent, `pose` whatever
    the animation adds on top; the two are kept apart so a reset is a reset and
    an explode can scale the offsets without eating the rest pose."""

    __slots__ = ('name', 'parent', 'off', 'rot', 'pose', 'M', 'T')

    def __init__(self, name, parent, off, rot):
        self.name = name
        self.parent = parent
        self.off = off
        self.rot = rot
        self.pose = IDENT
        self.M = IDENT
        self.T = (0.0, 0.0, 0.0)

    def resolve(self):
        local = mmul(self.rot, self.pose)
        if self.parent is None:
            self.M, self.T = local, self.off
        else:
            pM, pT = self.parent.M, self.parent.T
            o = mvec(pM, self.off)
            self.M = mmul(pM, local)
            self.T = (pT[0] + o[0], pT[1] + o[1], pT[2] + o[2])
