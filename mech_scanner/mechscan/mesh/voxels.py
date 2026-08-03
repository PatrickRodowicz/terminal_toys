"""The occupancy grid: what is inside the hull.

Burn the dense mesh into a lattice, flood the outside, and call everything
unreached solid. Occlusion, segmentation and the reactor position are all read
off the result, so the leak this module is written to avoid would be felt three
modules away -- hence the cross-check at the end.
"""
import math
from collections import deque

from .stl import stl_bounds

def voxel_solid(tris, res, density=1.5, want_volume=None):
    """Burn the dense mesh into an occupancy grid, flood the outside, and call
    everything unreached solid.

    The sampling lattice on each triangle is sized from its LONGEST EDGE, not
    its area. Sizing from area leaks: an STL like this is full of slivers --
    triangles whose area is near zero but whose edges run across a dozen voxels
    -- and those get three samples, leave their span unmarked, and let the
    outside flood walk straight into the interior. The failure is silent: the
    grid still looks like a model, 'solid' just quietly comes to mean 'shell',
    and occlusion stops seeing anything it should. Caught by checking the
    interior voxel count against the enclosed volume, which is the sort of
    cross-check worth building in.
    """
    x0, y0, z0, x1, y1, z1 = stl_bounds(tris)
    ext = max(x1 - x0, y1 - y0, z1 - z0) or 1.0
    s = res / ext
    nx = int((x1 - x0) * s) + 3
    ny = int((y1 - y0) * s) + 3
    nz = int((z1 - z0) * s) + 3
    cell = ext / res
    ox, oy, oz = x0 - cell, y0 - cell, z0 - cell
    grid = bytearray(nx * ny * nz)
    for t in tris:
        ax, ay, az = t[3], t[4], t[5]
        ux, uy, uz = t[6] - ax, t[7] - ay, t[8] - az
        vx, vy, vz = t[9] - ax, t[10] - ay, t[11] - az
        wx, wy, wz = vx - ux, vy - uy, vz - uz
        e2 = max(ux * ux + uy * uy + uz * uz,
                 vx * vx + vy * vy + vz * vz,
                 wx * wx + wy * wy + wz * wz)
        m = int(math.sqrt(e2) * density * s) + 1
        for ia in range(m + 1):
            fa = ia / m
            for ib in range(m + 1 - ia):
                fb = ib / m
                i = int((ax + ux * fa + vx * fb - ox) * s)
                j = int((ay + uy * fa + vy * fb - oy) * s)
                k = int((az + uz * fa + vz * fb - oz) * s)
                grid[(k * ny + j) * nx + i] = 1
    shell = sum(grid)

    nxy = nx * ny
    total = nxy * nz
    out = bytearray(total)
    q = deque()

    def seed(p):
        if not grid[p] and not out[p]:
            out[p] = 1
            q.append(p)

    for j in range(ny):
        for i in range(nx):
            seed((0 * ny + j) * nx + i)
            seed(((nz - 1) * ny + j) * nx + i)
    for k in range(nz):
        for i in range(nx):
            seed((k * ny + 0) * nx + i)
            seed((k * ny + ny - 1) * nx + i)
        for j in range(ny):
            seed((k * ny + j) * nx + 0)
            seed((k * ny + j) * nx + nx - 1)
    while q:
        p = q.popleft()
        k, rem = divmod(p, nxy)
        j, i = divmod(rem, nx)
        if i > 0:
            seed(p - 1)
        if i < nx - 1:
            seed(p + 1)
        if j > 0:
            seed(p - nx)
        if j < ny - 1:
            seed(p + nx)
        if k > 0:
            seed(p - nxy)
        if k < nz - 1:
            seed(p + nxy)
    solid = bytearray(total)
    for p in range(total):
        if not out[p]:
            solid[p] = 1
    nsolid = sum(solid)
    # Cross-check, because the leak this function is written to avoid is
    # *silent*: a leaked grid still looks like a model, it just stops having an
    # inside. The mesh's own enclosed volume says how many cells should be
    # solid; a conservative voxelisation overshoots that by about half a cell
    # of thickness over the whole surface, and never undershoots. Coming in
    # low means the flood got in.
    ok = True
    if want_volume:
        expect = want_volume * s ** 3
        ok = nsolid >= expect * 0.92
    return solid, (nx, ny, nz), (ox, oy, oz), s, shell, nsolid, ok
