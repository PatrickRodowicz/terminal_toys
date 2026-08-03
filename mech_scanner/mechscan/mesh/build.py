"""Loft primitives, and the Part that binds a mesh to a bone.

Everything in the built-in model is a loft: a stack of cross-section rings,
joined ring to ring by quads and closed with n-gon caps. A box is two
rectangular rings, a hydraulic ram is two circular ones, the cockpit pod is
nine ellipse rings on a curved profile. One primitive, and Raster.fill takes
any convex polygon, so the caps cost nothing extra.

`Part` is the join between the two halves of this program: the loft builders
and the STL loader both produce vertices plus indexed faces, and Part consumes
either without knowing which it has.
"""
import math, random, zlib

from ..lighting import AO_FLOOR
from ..materials import DENSITY
from ..math3d import IDENT, mvec

# Everything in the model is a loft: a stack of cross-section rings, joined
# ring to ring by quads and closed with n-gon caps. A box is two rectangular
# rings, a hydraulic ram is two circular ones, the cockpit pod is nine ellipse
# rings on a curved profile. One primitive, and `Raster.fill` takes any convex
# polygon, so the caps cost nothing extra.

def rect2(hw, hd, bev=0.0):
    """Rectangle cross-section, optionally with its corners cut. The bevel is
    what keeps armour plate from reading as a cardboard box: a lit chamfer down
    every vertical edge is most of what says 'machined' at this resolution."""
    if bev <= 0.0:
        return [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    b = min(bev, hw * 0.9, hd * 0.9)
    return [(-hw + b, -hd), (hw - b, -hd), (hw, -hd + b), (hw, hd - b),
            (hw - b, hd), (-hw + b, hd), (-hw, hd - b), (-hw, -hd + b)]


def ngon2(rx_, ry_, n, phase=0.0):
    return [(rx_ * math.cos(phase + 2 * math.pi * i / n),
             ry_ * math.sin(phase + 2 * math.pi * i / n)) for i in range(n)]


def ring(pts2, t, axis='z'):
    """Lift a cross-section into 3D at position `t` along `axis`."""
    if axis == 'z':
        return [(u, v, t) for u, v in pts2]
    if axis == 'y':
        return [(u, t, v) for u, v in pts2]
    return [(t, u, v) for u, v in pts2]


def place(pts3, off=(0.0, 0.0, 0.0), rot=IDENT):
    out = []
    for p in pts3:
        q = mvec(rot, p) if rot is not IDENT else p
        out.append((q[0] + off[0], q[1] + off[1], q[2] + off[2]))
    return out


class Mesh:
    """Vertices plus (index-tuple, material) faces. Vertices are shared inside
    a loft, so a box is 8 vertices and not 24 -- the per-frame transform cost is
    linear in vertices, and this model is transformed every single frame."""

    def __init__(self):
        self.v = []
        self.f = []

    def loft(self, rings, mat, cap0=True, cap1=True, matf=None):
        n = len(rings[0])
        base = len(self.v)
        for r in rings:
            if len(r) != n:
                raise ValueError('loft rings must agree in length')
            self.v.extend(r)
        for k in range(len(rings) - 1):
            a = base + k * n
            b = a + n
            for i in range(n):
                j = (i + 1) % n
                m = matf(k, i) if matf else mat
                if m is not None:
                    self.f.append(((a + i, a + j, b + j, b + i), m))
        if cap0:
            self.f.append((tuple(base + i for i in range(n - 1, -1, -1)), mat))
        if cap1:
            last = base + (len(rings) - 1) * n
            self.f.append((tuple(range(last, last + n)), mat))

    def poly(self, pts, mat):
        base = len(self.v)
        self.v.extend(pts)
        self.f.append((tuple(range(base, base + len(pts))), mat))

    # -- primitives --------------------------------------------------------
    def box(self, mat, size, off=(0, 0, 0), rot=IDENT, bev=0.0, taper=1.0,
            axis='z', matf=None):
        """A slab. `taper` scales the far cross-section, which is how every
        tapered limb segment in the model is made."""
        hu, hv, ht = size[0] / 2.0, size[1] / 2.0, size[2] / 2.0
        r0 = ring(rect2(hu, hv, bev), -ht, axis)
        r1 = ring(rect2(hu * taper, hv * taper, bev * taper), ht, axis)
        self.loft([place(r0, off, rot), place(r1, off, rot)], mat, matf=matf)

    def tube(self, mat, r0, r1, length, n=10, off=(0, 0, 0), rot=IDENT,
             axis='z', phase=0.0):
        a = ring(ngon2(r0, r0, n, phase), -length / 2.0, axis)
        b = ring(ngon2(r1, r1, n, phase), length / 2.0, axis)
        self.loft([place(a, off, rot), place(b, off, rot)], mat)

    def pod(self, mat, profile, n=10, off=(0, 0, 0), rot=IDENT, axis='y',
            phase=0.0, matf=None):
        """A lofted hull from (position, half-width, half-height) rings. The
        cockpit pod, the shoulder yokes and the missile-rack shells are all
        this; a closed profile (zero radius at both ends) needs no caps."""
        rings = []
        for t, a, b in profile:
            rings.append(place(ring(ngon2(max(a, 1e-4), max(b, 1e-4), n, phase),
                                    t, axis), off, rot))
        cap0 = profile[0][1] > 1e-3
        cap1 = profile[-1][1] > 1e-3
        self.loft(rings, mat, cap0=cap0, cap1=cap1, matf=matf)

    def grid_face(self, corners, nu, nv, colf, inset=0.0):
        """Subdivide a planar quad into nu x nv cells, each coloured by
        colf(i, j). This is how the missile tubes, the hazard chevrons and the
        armour panel lines are drawn: as geometry, not as texture, because the
        renderer has no texture stage and a quad is cheaper than one anyway."""
        p00, p10, p11, p01 = corners

        def at(u, v):
            a = [p00[k] + (p10[k] - p00[k]) * u for k in range(3)]
            b = [p01[k] + (p11[k] - p01[k]) * u for k in range(3)]
            return tuple(a[k] + (b[k] - a[k]) * v for k in range(3))

        for i in range(nu):
            for j in range(nv):
                m = colf(i, j)
                if m is None:
                    continue
                u0, u1 = (i + inset) / nu, (i + 1 - inset) / nu
                v0, v1 = (j + inset) / nv, (j + 1 - inset) / nv
                self.poly([at(u0, v0), at(u1, v0), at(u1, v1), at(u0, v1)], m)


class Part:
    """A mesh bound to a bone, with its faces pre-analysed.

    Normals are made to point away from the part's own centroid at build time.
    Every primitive here is star-shaped about its centre, so this is exact, and
    it means the loft generators never have to agree on a winding convention --
    a class of bug that costs an afternoon and shows up as one face of one limb
    being inside-out from one angle.
    """

    def __init__(self, name, frame, mesh, group, trust_winding=False,
                 ao=None, wear_amp=0.09, sec=None, temp=None):
        """`trust_winding` turns the outward-from-centroid pass OFF, for a mesh
        that already has a consistent winding of its own -- an STL, say. The
        centroid trick is exact for a star-shaped primitive and badly wrong for
        a whole mech: a facet inside the armpit points *toward* the body centre,
        and reorienting it would turn it inside out.

        `ao` is a per-face occlusion factor in [0, 1], folded into the same
        per-face brightness multiplier the weathering uses -- so occlusion
        costs the shader exactly nothing at frame time."""
        self.name = name
        self.frame = frame
        self.group = group
        self.v = mesh.v
        self.faces = []           # (idx, mat, local_normal, local_centroid)
        self.volume = 0.0
        self.mass = 0.0
        cx = sum(p[0] for p in mesh.v) / len(mesh.v)
        cy = sum(p[1] for p in mesh.v) / len(mesh.v)
        cz = sum(p[2] for p in mesh.v) / len(mesh.v)
        self.centroid = (cx, cy, cz)
        # crc32, not hash(): hash() of a str is salted per process, so the
        # weathering pattern came out different on every launch and no two
        # runs of the program ever drew the same frame. Invisible to the eye
        # -- it is a +-5% brightness jitter -- but it makes the renderer
        # unreproducible, which showed up the moment a pixel diff was used to
        # check an optimisation and the control run disagreed with itself on
        # 7% of pixels.
        self.sec = sec
        # Keep occlusion unfolded as well as folded: the shader wants it baked
        # into brightness, and the diagnostics want the number itself.
        self.aoraw = list(ao) if ao is not None else None
        self.temp = list(temp) if temp is not None else None
        rng = random.Random(zlib.crc32(name.encode()) & 0xffff)
        self.wear = []
        self.wear_plain = []
        for _fi, (idx, mat) in enumerate(mesh.f):
            pts = [mesh.v[i] for i in idx]
            nx = ny = nz = 0.0
            for k in range(len(pts)):
                a, b = pts[k - 1], pts[k]
                nx += (a[1] - b[1]) * (a[2] + b[2])
                ny += (a[2] - b[2]) * (a[0] + b[0])
                nz += (a[0] - b[0]) * (a[1] + b[1])
            area2 = math.sqrt(nx * nx + ny * ny + nz * nz)
            if area2 < 1e-12:
                continue                     # degenerate; a zero-width bevel
            fx = sum(p[0] for p in pts) / len(pts)
            fy = sum(p[1] for p in pts) / len(pts)
            fz = sum(p[2] for p in pts) / len(pts)
            n = (nx / area2, ny / area2, nz / area2)
            if not trust_winding and (
                    (fx - cx) * n[0] + (fy - cy) * n[1]
                    + (fz - cz) * n[2]) < 0:
                n = (-n[0], -n[1], -n[2])
                idx = tuple(reversed(idx))
            # Divergence theorem: 3V = sum over faces of (p . n) * area.
            self.volume += (fx * n[0] + fy * n[1] + fz * n[2]) * area2 / 2.0
            self.mass += ((fx * n[0] + fy * n[1] + fz * n[2]) * area2 / 2.0
                          / 3.0) * DENSITY.get(mat, 2.0)
            self.faces.append((idx, mat, n, (fx, fy, fz)))
            # Deterministic per-face weathering: a few percent of brightness,
            # fixed at build time so it does not crawl as the model turns.
            w = 1.0 + rng.uniform(-wear_amp, wear_amp * 0.78)
            self.wear_plain.append(w)
            self.wear.append(w * (AO_FLOOR + (1.0 - AO_FLOOR) * ao[_fi])
                             if ao is not None else w)
        self.volume /= 3.0
        self.mass = abs(self.mass)
        self.volume = abs(self.volume)


class MeshView:
    """Just enough of Mesh's shape for Part to consume an indexed triangle
    soup. The loft builders and the STL loader produce the same two fields, so
    Part does not need to know which it is looking at."""

    __slots__ = ('v', 'f')

    def __init__(self, verts, faces, mat):
        self.v = verts
        self.f = [(f, mat) for f in faces]
