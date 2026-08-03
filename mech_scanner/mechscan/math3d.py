"""3x3 matrices, vectors, and the one 2D hull the shadow needs.

Matrices are flat 9-tuples, row-major. Every rotation used here is orthonormal,
which is what lets normals be transformed by the same matrix as positions
instead of by its inverse transpose.
"""
import math

# 3x3 matrices are flat 9-tuples, row-major. Every rotation used here is
# orthonormal, which is what lets normals be transformed by the same matrix as
# positions instead of by its inverse transpose.
IDENT = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def mmul(a, b):
    return (a[0] * b[0] + a[1] * b[3] + a[2] * b[6],
            a[0] * b[1] + a[1] * b[4] + a[2] * b[7],
            a[0] * b[2] + a[1] * b[5] + a[2] * b[8],
            a[3] * b[0] + a[4] * b[3] + a[5] * b[6],
            a[3] * b[1] + a[4] * b[4] + a[5] * b[7],
            a[3] * b[2] + a[4] * b[5] + a[5] * b[8],
            a[6] * b[0] + a[7] * b[3] + a[8] * b[6],
            a[6] * b[1] + a[7] * b[4] + a[8] * b[7],
            a[6] * b[2] + a[7] * b[5] + a[8] * b[8])


def mvec(m, v):
    x, y, z = v
    return (m[0] * x + m[1] * y + m[2] * z,
            m[3] * x + m[4] * y + m[5] * z,
            m[6] * x + m[7] * y + m[8] * z)


def rx(deg):
    """Rotate about +x. Positive takes +y toward +z, so a positive angle on a
    limb frame swings its downward axis *forward*."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (1.0, 0.0, 0.0, 0.0, c, -s, 0.0, s, c)


def ry(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (c, 0.0, s, 0.0, 1.0, 0.0, -s, 0.0, c)


def rz(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (c, -s, 0.0, s, c, 0.0, 0.0, 0.0, 1.0)


def rxyz(ax=0.0, ay=0.0, az=0.0):
    return mmul(mmul(rz(az), ry(ay)), rx(ax))


def normed(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def hull2d(pts):
    """Monotone-chain convex hull. Used only on the eight ground-projected
    corners of a part's bounding box, to give the cast shadow a silhouette
    instead of an axis-aligned smear."""
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2:
                (ax, ay), (bx, by) = out[-2], out[-1]
                if (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax) > 0:
                    break
                out.pop()
            out.append(p)
        return out

    lo = half(pts)
    hi = half(reversed(pts))
    return lo[:-1] + hi[:-1]
