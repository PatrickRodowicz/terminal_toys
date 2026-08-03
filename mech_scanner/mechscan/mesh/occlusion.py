"""Real ambient occlusion, fired against the occupancy grid.

Occlusion in the real sense: it sees the arm hanging in front of the chest,
which a curvature estimate never can, and that is the whole reason the voxel
grid exists.
"""
import math

def hemi_dirs(nx, ny, nz):
    """Thirteen directions in the hemisphere about a normal: the axis plus two
    rings. Fixed rather than randomised, so a face gets the same answer every
    run and the cached occlusion means something."""
    ux, uy, uz = (0.0, 0.0, 1.0) if abs(nz) < 0.9 else (1.0, 0.0, 0.0)
    ax = uy * nz - uz * ny
    ay = uz * nx - ux * nz
    az = ux * ny - uy * nx
    al = math.sqrt(ax * ax + ay * ay + az * az) or 1.0
    ax, ay, az = ax / al, ay / al, az / al
    bx = ny * az - nz * ay
    by = nz * ax - nx * az
    bz = nx * ay - ny * ax
    dirs = [(nx, ny, nz)]
    for rad, cnt, ph in ((0.55, 6, 0.0), (0.90, 6, 0.4)):
        ct = math.sqrt(1.0 - rad * rad)
        for i in range(cnt):
            th = 2 * math.pi * i / cnt + ph
            c, sn = math.cos(th) * rad, math.sin(th) * rad
            dirs.append((nx * ct + ax * c + bx * sn,
                         ny * ct + ay * c + by * sn,
                         nz * ct + az * c + bz * sn))
    return dirs


def face_ao(verts, faces, solid, dims, org, s, radius_cells=4.0, steps=3):
    """Per-face occlusion: fire the hemisphere, march each ray out to the
    radius, and count the ones that end up inside solid. This is occlusion in
    the real sense -- it sees the arm hanging in front of the chest, which a
    curvature estimate never can, and that is the whole reason for the grid."""
    nxg, nyg, nzg = dims
    ox, oy, oz = org
    inv = 1.0 / s
    out = []
    for ia, ib, ic in faces:
        pa, pb, pc = verts[ia], verts[ib], verts[ic]
        cx = (pa[0] + pb[0] + pc[0]) / 3.0
        cy = (pa[1] + pb[1] + pc[1]) / 3.0
        cz = (pa[2] + pb[2] + pc[2]) / 3.0
        ux, uy, uz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
        vx, vy, vz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
        mx = uy * vz - uz * vy
        my = uz * vx - ux * vz
        mz = ux * vy - uy * vx
        ml = math.sqrt(mx * mx + my * my + mz * mz) or 1.0
        dirs = hemi_dirs(mx / ml, my / ml, mz / ml)
        hit = 0
        for dx, dy, dz in dirs:
            for st in range(1, steps + 1):
                r = radius_cells * st / steps * inv
                i = int((cx + dx * r - ox) * s)
                j = int((cy + dy * r - oy) * s)
                k = int((cz + dz * r - oz) * s)
                if 0 <= i < nxg and 0 <= j < nyg and 0 <= k < nzg \
                        and solid[(k * nyg + j) * nxg + i]:
                    hit += 1
                    break              # blocked: the rest of this ray is moot
        out.append(1.0 - hit / float(len(dirs)))
    return out
