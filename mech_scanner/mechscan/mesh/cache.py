"""The built-mesh cache.

Building a level of detail is seconds of decimation, voxelisation and ray
casting; reading one back is a few milliseconds. Nothing in here is precious --
every byte of it is derived from the source STL and can be rebuilt by deleting
the directory and waiting about twenty-five seconds.

Everything the result depends on is in the key: the source path, its size and
mtime, the facet budget, the up-axis, the occlusion radius and the grid
resolution. A stale cache is therefore a miss, never a wrong answer. Canon is
deliberately NOT in the key, because nothing canon touches is stored here --
see the note in pipeline.py about where mass lives.

The files used to sit beside the source STL, which meant pointing the renderer
at a model in somebody else's directory left six ~350 KB files in it. They now
go in one cache directory inside the project, named by a digest of the absolute
source path, so an arbitrary STL anywhere on disk is cached without writing
next to it.
"""
import array
import hashlib
import json
import os
import struct
import sys

from .model import Model

CACHE_MAGIC = b'MMSH'
# 9: the report no longer carries built_mass / built_density, which were canon
# and not measurement. Bumping this invalidates every v8 file, which costs one
# rebuild and is the whole point of having a version in the header.
CACHE_VER = 9
CACHE_HEAD = '<HHIIId'
CACHE_HLEN = len(CACHE_MAGIC) + struct.calcsize(CACHE_HEAD)

# Default: inside the project, beside the package. Self-contained, one place to
# delete, and it never litters the directory the STL happens to live in.
DEFAULT_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'cache')


def cache_path(path, target, up, ao_radius, vox, cache_dir=None):
    """One file per (source, budget, up, radius, grid).

    The digest is of the ABSOLUTE source path, so two different files with the
    same basename cannot collide; the readable stem is kept on the front so the
    directory can be read by a human deciding what to delete.
    """
    st = os.stat(path)
    ap = os.path.abspath(path)
    stem = os.path.basename(path)[:40]
    digest = hashlib.sha1(ap.encode('utf-8', 'replace')).hexdigest()[:12]
    name = '%s.%s.%d-%d-%s-%g-%d.mmesh' % (stem, digest, target, st.st_size,
                                           up, ao_radius, vox)
    return os.path.join(cache_dir or DEFAULT_CACHE_DIR, name)


def cache_read(cp, mtime):
    try:
        d = open(cp, 'rb').read()
    except OSError:
        return None
    try:
        if len(d) < CACHE_HLEN or d[:len(CACHE_MAGIC)] != CACHE_MAGIC:
            return None
        ver, order, jlen, nv, nf, mt = struct.unpack(
            CACHE_HEAD, d[len(CACHE_MAGIC):CACHE_HLEN])
        if ver != CACHE_VER or order != (sys.byteorder != 'little'):
            return None
        if abs(mt - mtime) > 1e-6:
            return None
        o = CACHE_HLEN
        report = json.loads(d[o:o + jlen].decode('utf-8'))
        o += jlen
        va = array.array('f')
        va.frombytes(d[o:o + nv * 12])
        o += nv * 12
        fa = array.array('i')
        fa.frombytes(d[o:o + nf * 12])
        o += nf * 12
        aa = array.array('f')
        aa.frombytes(d[o:o + nf * 4])
        o += nf * 4
        sec = bytearray(d[o:o + nf])
        o += nf
        ta = array.array('f')
        ta.frombytes(d[o:o + nf * 4])
        if (len(va) != nv * 3 or len(fa) != nf * 3 or len(aa) != nf
                or len(sec) != nf or len(ta) != nf):
            return None
    except Exception:
        return None       # a truncated or foreign cache just means rebuild
    verts = [(va[i * 3], va[i * 3 + 1], va[i * 3 + 2]) for i in range(nv)]
    faces = [(fa[i * 3], fa[i * 3 + 1], fa[i * 3 + 2]) for i in range(nf)]
    return Model(verts, faces, list(aa), report, sec, list(ta))


def cache_write(cp, m, mtime):
    j = json.dumps(m.report).encode('utf-8')
    head = CACHE_MAGIC + struct.pack(
        CACHE_HEAD, CACHE_VER, sys.byteorder != 'little',
        len(j), len(m.verts), len(m.faces), mtime)
    try:
        os.makedirs(os.path.dirname(cp), exist_ok=True)
        tmp = '%s.%d.tmp' % (cp, os.getpid())
        with open(tmp, 'wb') as fh:
            fh.write(head)
            fh.write(j)
            fh.write(array.array('f', [c for v in m.verts for c in v]).tobytes())
            fh.write(array.array('i', [c for f in m.faces for c in f]).tobytes())
            fh.write(array.array('f', m.ao).tobytes())
            fh.write(bytes(m.sec))
            fh.write(array.array('f', m.temp).tobytes())
        os.replace(tmp, cp)
    except OSError:
        pass          # a read-only directory is no reason to fail to draw
