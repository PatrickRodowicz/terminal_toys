"""Ground shadow, precomputed at load."""

from ..lighting import SUN
from ..math3d import hull2d

SHADOW_BANDS = 14

def shadow_bands(verts, nbands=SHADOW_BANDS):
    """Ground shadow as a stack of height bands, each hulled separately.

    One hull over the whole model is a blob that loses the gap between the
    legs. Banding by height keeps the legs apart and the arms distinct for
    almost nothing, and because the model is static under an orbiting camera --
    the turntable moves the eye, not the mech -- the whole thing is computed
    once at load and only projected at frame time.
    """
    if not verts or SUN[2] <= 0.05:
        return []
    z0 = min(v[2] for v in verts)
    z1 = max(v[2] for v in verts)
    span = (z1 - z0) or 1.0
    buckets = [[] for _ in range(nbands)]
    for x, y, z in verts:
        b = int((z - z0) / span * nbands)
        if b >= nbands:
            b = nbands - 1
        t = z / SUN[2]
        buckets[b].append((x - SUN[0] * t, y - SUN[1] * t))
    out = []
    for b in buckets:
        h = hull2d(b)
        if len(h) >= 3:
            out.append(h)
    return out
