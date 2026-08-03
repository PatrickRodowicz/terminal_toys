"""What is being drawn, and the measurements taken off it once at load.

Two kinds of thing arrive here and the rest of the program should not have to
keep asking which it has:

  * A loaded STL. One rigid watertight shell, three levels of detail, segmented
    into the machine's own limbs. No joints, so `i` (idle) and `e` (explode)
    have nothing to move.
  * The built-in procedural mech. Seventeen bones and forty-odd parts, each
    with its own mass, which does pose and does explode.

`stl_mode` is the one flag that distinguishes them, and everything that follows
from it -- which panel page, what `j`/`k` cycles, whether the shadow comes from
precomputed bands or from part bounding boxes -- is asked of the Rig rather
than rediscovered at each call site.

Everything measured here is measured ONCE, at the rest pose, over EVERY level
of detail rather than just the one showing. Both of those were bugs first: a
camera fit that tracked the current level made the model jump when `d` cycled,
and an explode direction computed only for the visible level crashed the frame
loop the moment another level was selected. The key soak found the second one;
looking at it did not.
"""
import math
import os

from .math3d import IDENT, mvec, normed
from .mesh import builtin
from .mesh.build import MeshView, Part
from .mesh.frames import Frame
from .mesh.model import LOD_TARGETS
from .mesh.pipeline import load_models
from .mesh.thermal import REACTOR_R


class Extent:
    """The model's own size, for the camera fit.

    The bounding CYLINDER, not the bounding box: a cylinder's projection does
    not depend on the azimuth at all, so the framing stays exactly constant as
    the turntable turns instead of breathing every quarter revolution.
    """

    __slots__ = ('mrad', 'mz0', 'mz1', 'mcz')

    def __init__(self, world_verts):
        self.mrad = max(math.hypot(w[0], w[1]) for w in world_verts)
        self.mz0 = min(w[2] for w in world_verts)
        self.mz1 = max(w[2] for w in world_verts)
        self.mcz = (self.mz0 + self.mz1) / 2.0


class Rig:
    __slots__ = ('frames', 'order', 'parts', 'lods', 'stl_mode', 'name',
                 'ext', 'lod_i', 'canon')

    def __init__(self, frames, order, parts, lods, stl_mode, name, lod_i=0,
                 canon=None):
        self.frames = frames
        self.order = order
        self.parts = parts
        self.lods = lods
        self.stl_mode = stl_mode
        self.name = name
        self.lod_i = lod_i
        # The canon table for this machine, or None. Held here and not baked
        # into the mesh report, so the built-mesh cache stays valid whether or
        # not we claim to know what the mesh depicts.
        self.canon = canon
        self.ext = None

    # -- construction ------------------------------------------------------
    @classmethod
    def builtin(cls):
        frames, order, parts = builtin.build_mech()
        rig = cls(frames, order, parts, [], False, 'MADCAT-X')
        rig.measure()
        rig._heat_field()
        return rig

    @classmethod
    def from_stl(cls, path, targets=None, up='z', ao_radius=4.0, vox=80,
                 no_ao=False, note=None, use_cache=True, lod=1, canon=None,
                 cache_dir=None):
        models = load_models(path, targets or LOD_TARGETS, up=up,
                             ao_radius=ao_radius, vox=vox, note=note,
                             use_cache=use_cache, cache_dir=cache_dir)
        root = Frame('root', None, (0.0, 0.0, 0.0), IDENT)
        frames, order, lods = {'root': root}, [root], []
        for m in models:
            mv = MeshView(m.verts, m.faces, 'plate')
            p = Part(os.path.basename(path), root, mv, 'hull',
                     trust_winding=True, ao=None if no_ao else m.ao,
                     wear_amp=0.055, sec=m.sec, temp=m.temp)
            p.model = m
            lods.append(p)
        lod_i = min(lod, len(lods) - 1)
        rig = cls(frames, order, [lods[lod_i]], lods, True, path, lod_i,
                  canon)
        rig.measure()
        return rig

    # -- measurement -------------------------------------------------------
    @property
    def levels(self):
        """Every Part the frame loop could ever be asked to draw."""
        return self.lods or self.parts

    @property
    def report(self):
        return self.parts[0].model.report if self.stl_mode else None

    @property
    def mass(self):
        """Tonnage, or None if nothing sourced one.

        Canon owns this number. A mesh has a volume, and turning that into a
        mass needs a density, and picking a density to reach a tonnage you
        already believe is circular. So: no canon, no mass.
        """
        return float(self.canon['mass_t']) if self.canon else None

    @property
    def density(self):
        """Derived: canon tonnage over measured displacement, that way round."""
        rp = self.report
        if not (self.canon and rp and rp.get('built_volume')):
            return None
        return float(self.canon['mass_t']) / rp['built_volume']

    def measure(self):
        """Extent and explode directions, over every level of detail."""
        for f in self.order:
            f.resolve()
        allw = []
        for p in self.levels:
            M, T = p.frame.M, p.frame.T
            for v in p.v:
                q = mvec(M, v)
                allw.append((q[0] + T[0], q[1] + T[1], q[2] + T[2]))
        self.ext = Extent(allw)
        mcz = self.ext.mcz
        for p in self.levels:
            M, T = p.frame.M, p.frame.T
            c = mvec(M, p.centroid)
            c = (c[0] + T[0], c[1] + T[1], c[2] + T[2])
            p.expdir = normed((c[0], c[1] * 0.55, (c[2] - mcz) * 0.9))

    def set_lod(self, i):
        self.lod_i = i % len(self.lods)
        self.parts = [self.lods[self.lod_i]]

    # -- the built-in model's heat field -----------------------------------
    def _heat_field(self):
        """The built-in mech needs a heat field too.

        Without one the thermal channel is a flat silhouette on it -- and
        worse, with no temperature to carry, the per-facet 'hot' slot still
        held the SELECTION flag, so picking a part made it read white hot.

        Same physics as the loaded mesh: a point source at the torso, inverse
        square, no occlusion term because the procedural parts have none.
        Scaled off the built-in's OWN height, not MODEL_H: it is modelled in
        its own units and is not normalised to the loaded mesh's twelve metres.
        """
        parts = self.parts
        if not parts:
            return

        def wc(pt, fr):
            q = mvec(fr.M, pt)
            return (q[0] + fr.T[0], q[1] + fr.T[1], q[2] + fr.T[2])

        tp = [p for p in parts if p.name == 'torso hull'] or parts
        kx = sum(wc(p.centroid, p.frame)[0] for p in tp) / len(tp)
        ky = sum(wc(p.centroid, p.frame)[1] for p in tp) / len(tp)
        kz = sum(wc(p.centroid, p.frame)[2] for p in tp) / len(tp)
        zs = [wc(v, p.frame)[2] for p in parts for v in p.v]
        h = (max(zs) - min(zs)) or 1.0
        hi = 0.0
        for p in parts:
            p.temp = []
            for _idx, _mat, _n, lc in p.faces:
                wx, wy, wz = wc(lc, p.frame)
                d2 = ((wx - kx) ** 2 + (wy - ky) ** 2 + (wz - kz) ** 2)
                v = 1.0 / (1.0 + d2 / ((REACTOR_R * h) ** 2))
                p.temp.append(v)
                if v > hi:
                    hi = v
        hi = hi or 1.0
        for p in parts:
            p.temp = [v / hi for v in p.temp]
