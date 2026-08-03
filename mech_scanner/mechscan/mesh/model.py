"""The Model: one loaded mesh at one level of detail, in world units.

Kept apart from the pipeline that builds it (pipeline.py) and from the cache
that stores it (cache.py) so that both can depend on this without depending on
each other.
"""

from .shadow import shadow_bands

MODEL_H = 12.0            # world height every loaded model is normalised to
LOD_TARGETS = (2600, 6200, 14000)
LOD_NAMES = ('LOD LOW', 'LOD MEDIUM', 'LOD HIGH')

class Model:
    """A loaded, decimated, occluded mesh at one level of detail, normalised so
    it stands MODEL_H tall on z = 0 and centred on the vertical axis."""

    __slots__ = ('verts', 'faces', 'ao', 'report', 'shadow', 'sec', 'temp')

    def __init__(self, verts, faces, ao, report, sec=None, temp=None):
        self.verts = verts
        self.faces = faces
        self.ao = ao
        self.report = report
        self.sec = sec if sec is not None else bytearray(len(faces))
        self.temp = temp if temp is not None else [0.0] * len(faces)
        self.shadow = shadow_bands(verts)


def normalise(verts, up='z'):
    """Stand the model on the ground, centre it on the vertical axis, scale it
    to MODEL_H. Returns the vertices and the metres-per-source-unit factor,
    which is what lets the panel quote a real-world volume for a mesh whose own
    units are millimetres of printed plastic."""
    if up == 'y':
        verts = [(v[0], -v[2], v[1]) for v in verts]
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    z0 = min(zs)
    k = MODEL_H / ((max(zs) - z0) or 1.0)
    # The transform comes back as well as the vertices. Anything measured in
    # source coordinates -- the reactor point, so far -- has to be able to
    # follow the mesh into model space, and re-deriving the mapping at the
    # call site is how the two quietly drift apart.
    return ([((v[0] - cx) * k, (v[1] - cy) * k, (v[2] - z0) * k)
             for v in verts], k, (cx, cy, z0, k, up))


def apply_norm(p, xf):
    cx, cy, z0, k, up = xf
    x, y, z = (p[0], -p[2], p[1]) if up == 'y' else p
    return ((x - cx) * k, (y - cy) * k, (z - z0) * k)
