"""Reading an STL, and measuring what came in.

The reference model is 242,976 triangles; the renderer can afford a few
thousand. That is not a compromise -- at half-block resolution the model covers
roughly 150x400 pixels, so a few thousand facets is already one facet per
handful of pixels and more would be invisible. This module reads the source and
reports on it; decimate.py, voxels.py and occlusion.py do the reduction.
"""
import math, struct

def load_stl(path):
    """Read binary or ASCII STL into a flat list of 12-float tuples
    (nx, ny, nz, then three vertices). The stored facet normal is kept: it is
    the only record of the original surface once the geometry is decimated,
    and it is what tells a clustered triangle which way round it should face."""
    d = open(path, 'rb').read()
    if len(d) < 84:
        raise ValueError('%s: too short to be an STL' % path)
    n = struct.unpack('<I', d[80:84])[0]
    if len(d) == 84 + 50 * n:
        return [r[:12] for r in struct.iter_unpack('<12fH', d[84:84 + 50 * n])]
    # ASCII: the header check has to be the size arithmetic above, not the
    # leading word. Plenty of binary STLs in the wild start with "solid".
    txt = d.decode('utf-8', 'replace')
    if 'facet' not in txt:
        raise ValueError('%s: not a recognisable STL' % path)
    out = []
    nrm = (0.0, 0.0, 1.0)
    vs = []
    for line in txt.splitlines():
        w = line.split()
        if not w:
            continue
        if w[0] == 'facet' and len(w) >= 5:
            nrm = (float(w[2]), float(w[3]), float(w[4]))
            vs = []
        elif w[0] == 'vertex' and len(w) >= 4:
            vs.append((float(w[1]), float(w[2]), float(w[3])))
        elif w[0] == 'endfacet' and len(vs) == 3:
            out.append(nrm + vs[0] + vs[1] + vs[2])
    if not out:
        raise ValueError('%s: no facets found' % path)
    return out


def stl_bounds(tris):
    x0 = y0 = z0 = 1e30
    x1 = y1 = z1 = -1e30
    for t in tris:
        for k in (3, 6, 9):
            a, b, c = t[k], t[k + 1], t[k + 2]
            if a < x0: x0 = a
            if a > x1: x1 = a
            if b < y0: y0 = b
            if b > y1: y1 = b
            if c < z0: z0 = c
            if c > z1: z1 = c
    return (x0, y0, z0, x1, y1, z1)


def analyse_stl(tris):
    """Facts about the source mesh, for the panel. Welds at a tolerance
    relative to the diagonal, then checks that every edge is used exactly twice
    -- which is what 'watertight' means and what makes the enclosed volume a
    real number rather than a hopeful one."""
    x0, y0, z0, x1, y1, z1 = stl_bounds(tris)
    diag = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2 + (z1 - z0) ** 2)
    inv = 1.0 / max(diag * 1e-6, 1e-12)
    vid = {}
    idx = []
    for t in tris:
        tri = []
        for k in (3, 6, 9):
            key = (int(t[k] * inv), int(t[k + 1] * inv), int(t[k + 2] * inv))
            i = vid.get(key)
            if i is None:
                i = len(vid)
                vid[key] = i
            tri.append(i)
        idx.append(tri)
    edges = {}
    for a, b, c in idx:
        for u, v in ((a, b), (b, c), (c, a)):
            e = (u, v) if u < v else (v, u)
            edges[e] = edges.get(e, 0) + 1
    manifold = all(v == 2 for v in edges.values())
    vol = area = 0.0
    for t in tris:
        ax, ay, az = t[3], t[4], t[5]
        bx, by, bz = t[6], t[7], t[8]
        cx, cy, cz = t[9], t[10], t[11]
        vol += (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx)
                + az * (bx * cy - by * cx))
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        mx = uy * vz - uz * vy
        my = uz * vx - ux * vz
        mz = ux * vy - uy * vx
        area += math.sqrt(mx * mx + my * my + mz * mz)
    return {
        'src_tris': len(tris), 'src_verts': len(vid), 'edges': len(edges),
        'watertight': manifold,
        'bbox': (x1 - x0, y1 - y0, z1 - z0),
        'volume': abs(vol) / 6.0, 'area': area / 2.0,
    }
