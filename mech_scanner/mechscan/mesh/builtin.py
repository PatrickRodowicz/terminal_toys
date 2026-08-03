"""The procedural mech, for when there is no STL to hand.

Coordinates: +x right, +y forward (the way the mech faces), +z up. One unit is
roughly one metre; the machine stands 11.2 of them to the top of its missile
racks and 6.6 to the hip.
"""
import math

from ..math3d import IDENT, rx, rxyz, ry, rz
from .build import Mesh, Part
from .frames import Frame

# Coordinates: +x right, +y forward (the way the mech faces), +z up. One unit
# is roughly one metre; the machine stands 11.2 of them to the top of its
# missile racks and 6.6 to the hip.
#
# The legs are digitigrade -- reverse-jointed, the way a bird's are. Absolute
# limb angles are thigh +36 (forward and down), shin -48 (back and down), foot
# level. Each frame's rotation is stated as the *difference* from its parent's,
# so the chain cancels at the ankle and the sole lies flat however the leg is
# posed. That is what puts the knee well forward of the hip, the ankle well
# behind it, and the foot back underneath the centre of mass -- the deep Z that
# is the whole silhouette of the class. Anything shallower reads as a column.

def build_mech():
    frames = {}
    order = []

    def F(name, parent, off=(0.0, 0.0, 0.0), rot=IDENT):
        f = Frame(name, frames.get(parent), off, rot)
        frames[name] = f
        order.append(f)
        return f

    parts = []

    def P(name, frame, mesh, group):
        parts.append(Part(name, frames[frame], mesh, group))

    F('root', None, (0.0, 0.0, 0.0))
    F('pelvis', 'root', (0.0, 0.0, 6.60))
    # The pod hangs nose-down off the waist gimbal, which is what gives the
    # class its hunched, forward-leaning stance.
    F('torso', 'pelvis', (0.0, 0.80, 1.80), rx(-12))

    # ---- pelvis and waist ----
    m = Mesh()
    m.box('plate', (3.9, 2.6, 1.20), off=(0, -0.10, 0.10), bev=0.46)
    m.box('metal2', (2.2, 1.9, 1.00), off=(0, -0.15, 0.85), bev=0.32)
    m.box('plate2', (4.3, 1.0, 0.90), off=(0, -1.15, 0.05), bev=0.26)
    for s in (-1, 1):
        m.tube('metal', 0.70, 0.70, 1.05, 12, off=(s * 1.72, -0.10, -0.10),
               rot=ry(90), axis='z')
        m.tube('dark', 0.38, 0.38, 1.18, 8, off=(s * 1.72, -0.10, -0.10),
               rot=ry(90), axis='z')
    P('pelvis', 'pelvis', m, 'core')

    # ---- torso pod ----
    # Nine rings on an egg profile, 5.5 units nose to tail: blunt at the back
    # where the reactor and the heat sinks live, drawn out to a rounded point at
    # the nose. It is the single largest object in the model on purpose -- on
    # the real machine the pod is as long as the legs are tall, and shrinking it
    # is the fastest way to make a mech look like a toy.
    m = Mesh()
    prof = [(-2.55, 0.42, 0.36), (-2.15, 1.30, 1.06), (-1.45, 1.92, 1.44),
            (-0.55, 2.22, 1.60), (0.40, 2.25, 1.58), (1.25, 2.08, 1.42),
            (2.00, 1.66, 1.12), (2.55, 1.06, 0.70), (2.92, 0.30, 0.24)]

    def hullmat(k, i):
        # Panel the hull: the upper band bleaches in the sun, the flanks sit in
        # their own shadow, and one ring back from the nose is a bare collar.
        if k == 6:
            return 'metal2'
        if k == 3 and i in (8, 9):
            return 'haz_y'                # unit flash, port flank
        if k == 4 and i == 8:
            return 'red'
        return 'plate3' if 2 <= i <= 7 else ('plate2' if i in (0, 9) else 'plate')

    m.pod('plate', prof, n=10, off=(0.0, 0.20, 0.05), phase=math.pi / 10,
          matf=hullmat)
    # dorsal spine housing and heat-sink louvres
    m.box('plate2', (1.35, 3.4, 0.60), off=(0, -0.20, 1.42), bev=0.20)
    m.grid_face(((-0.55, -1.85, 1.74), (0.55, -1.85, 1.74),
                 (0.55, 1.35, 1.74), (-0.55, 1.35, 1.74)),
                1, 9, lambda i, j: 'dark' if j % 2 == 0 else None)
    # engine exhaust, aft
    for s in (-1, 1):
        m.tube('metal2', 0.50, 0.60, 0.80, 8, off=(s * 0.72, -2.55, 0.15),
               rot=rx(90), axis='z')
        m.tube('dark', 0.36, 0.36, 0.88, 8, off=(s * 0.72, -2.62, 0.15),
               rot=rx(90), axis='z')
    P('torso hull', 'torso', m, 'core')

    # ---- cockpit ----
    # Offset to port, as on the real thing: the pilot sits beside the reactor
    # rather than above it. The canopy is a blister on the shoulder of the hull,
    # and the laminate is *painted onto its own front face* with grid_face
    # rather than modelled as separate panes -- panes floated at a guessed
    # radius end up inside the blister, invisible, which is exactly what the
    # first cut of this did.
    m = Mesh()
    F('canopy', 'torso', (-1.05, 1.35, 0.58), rxyz(ax=-14, az=-11))
    m.box('plate2', (2.35, 1.85, 1.40), bev=0.36)
    m.grid_face(((-1.00, 0.95, -0.46), (1.00, 0.95, -0.46),
                 (1.00, 0.95, 0.44), (-1.00, 0.95, 0.44)),
                1, 3, lambda i, j: 'dark' if j == 1 else 'glass')
    m.box('dark', (2.10, 0.30, 0.30), off=(0, 0.86, 0.62), bev=0.06)     # brow
    m.box('metal', (2.40, 0.40, 0.20), off=(0, 0.80, -0.68), bev=0.06)   # sill
    m.tube('lamp', 0.12, 0.12, 0.14, 6, off=(-1.05, 0.88, 0.70), rot=rx(90))
    # sensor cluster, on the hull centreline beside the canopy
    m.tube('dark', 0.20, 0.16, 0.70, 8, off=(1.35, 0.55, 0.10), rot=rx(96))
    P('cockpit', 'canopy', m, 'core')

    for s, tag in ((-1, 'L'), (1, 'R')):
        # ---- shoulder yoke and missile rack ----
        # The racks sit high, aft and close inboard, cocked up and out just
        # enough to clear the pod. Splayed wide they read as ears.
        F('yoke' + tag, 'torso', (s * 1.55, -0.95, 1.05),
          rxyz(ax=9, ay=-s * 7))
        m = Mesh()
        m.box('rust', (1.15, 1.70, 1.60), off=(s * 0.40, 0, 0.40), bev=0.32)
        m.tube('metal', 0.52, 0.52, 1.45, 10, off=(s * 0.22, 0, 0.10), rot=ry(90))
        P('yoke ' + tag, 'yoke' + tag, m, 'mount')

        F('rack' + tag, 'yoke' + tag, (s * 0.85, -0.20, 1.60),
          rxyz(ax=7, ay=-s * 5))
        m = Mesh()
        RW, RD, RH = 1.95, 2.60, 1.72
        m.box('plate', (RW, RD, RH), bev=0.28)
        # Tube face: a 5x3 bore grid recessed into the front cap, drawn as its
        # own quads a hair proud of the plate so it cannot z-fight the cap.
        y = RD / 2.0 + 0.015
        m.grid_face(((-RW / 2 + 0.16, y, -RH / 2 + 0.16),
                     (RW / 2 - 0.16, y, -RH / 2 + 0.16),
                     (RW / 2 - 0.16, y, RH / 2 - 0.16),
                     (-RW / 2 + 0.16, y, RH / 2 - 0.16)),
                    5, 3, lambda i, j: 'tube', inset=0.15)
        # Hazard chevrons along the top lip and the outboard flank -- where a
        # ground crew paints them, because that is what you walk into.
        z = RH / 2.0 + 0.015
        m.grid_face(((-RW / 2, -RD / 2, z), (RW / 2, -RD / 2, z),
                     (RW / 2, -RD / 2 + 0.60, z), (-RW / 2, -RD / 2 + 0.60, z)),
                    8, 1, lambda i, j: 'haz_y' if i % 2 == 0 else 'haz_k')
        m.grid_face(((-RW / 2, RD / 2 - 0.60, z), (RW / 2, RD / 2 - 0.60, z),
                     (RW / 2, RD / 2, z), (-RW / 2, RD / 2, z)),
                    8, 1, lambda i, j: 'haz_y' if i % 2 else 'haz_k')
        xf = s * (RW / 2.0 + 0.015)
        m.grid_face(((xf, -RD / 2, -RH / 2 + 0.25), (xf, RD / 2, -RH / 2 + 0.25),
                     (xf, RD / 2, -RH / 2 + 0.62), (xf, -RD / 2, -RH / 2 + 0.62)),
                    10, 1, lambda i, j: 'haz_y' if i % 2 else 'haz_k')
        # reload hatch and unit flash
        m.box('metal2', (1.05, 0.06, 0.85), off=(-s * 0.35, -RD / 2 - 0.02, 0.05))
        m.box('red', (0.38, 0.06, 0.38), off=(s * 0.62, -RD / 2 - 0.04, -0.42))
        P('LRM rack ' + tag, 'rack' + tag, m, 'weapon')

        # ---- arm ----
        # Shoulder ball, upper arm splayed outward and canted forward, elbow,
        # forearm, and a laser pod with a lens on the muzzle. The pods hang to
        # about knee height, which is where the reference carries them.
        F('sh' + tag, 'torso', (s * 2.25, -0.30, -0.20), rxyz(ax=4, ay=-s * 14))
        m = Mesh()
        m.tube('metal', 0.72, 0.72, 1.05, 12, off=(0, 0, 0.05), rot=ry(90))
        m.tube('dark', 0.42, 0.42, 1.16, 8, off=(0, 0, 0.05), rot=ry(90))
        m.box('plate', (1.05, 1.45, 1.90), off=(s * 0.30, 0, -0.85), bev=0.30,
              taper=0.86)
        P('shoulder ' + tag, 'sh' + tag, m, 'mount')

        F('elb' + tag, 'sh' + tag, (0.0, 0.0, -1.95), rxyz(ax=10, ay=s * 9))
        m = Mesh()
        m.tube('metal2', 0.50, 0.50, 0.95, 10, off=(0, 0, 0.05), rot=ry(90))
        m.box('plate2', (0.92, 1.20, 1.60), off=(0, 0.02, -0.90), bev=0.26)
        # hydraulic ram down the back of the forearm
        m.tube('metal', 0.14, 0.14, 1.30, 8, off=(0, -0.68, -0.80))
        m.tube('lamp', 0.10, 0.10, 0.55, 6, off=(0, -0.68, -0.32))
        P('forearm ' + tag, 'elb' + tag, m, 'limb')

        F('gun' + tag, 'elb' + tag, (0.0, 0.14, -1.95), rxyz(ax=5))
        m = Mesh()
        m.pod('plate', [(-0.85, 0.68, 0.60), (-0.22, 0.90, 0.78),
                        (0.62, 0.88, 0.76), (1.05, 0.66, 0.56)],
              n=8, axis='z', phase=math.pi / 8)
        # muzzle: recessed barrel, dark throat, hot lens
        m.tube('metal2', 0.48, 0.38, 0.60, 10, off=(0, 0.05, -1.18))
        m.tube('dark', 0.32, 0.32, 0.16, 10, off=(0, 0.05, -1.50))
        m.tube('lamp', 0.20, 0.20, 0.06, 10, off=(0, 0.05, -1.57))
        m.grid_face(((-0.55, 0.92, 0.10), (0.55, 0.92, 0.10),
                     (0.55, 0.92, 0.42), (-0.55, 0.92, 0.42)),
                    6, 1, lambda i, j: 'haz_y' if i % 2 else 'haz_k')
        P('laser pod ' + tag, 'gun' + tag, m, 'weapon')

        # ---- leg ----
        F('hip' + tag, 'pelvis', (s * 1.75, -0.10, 0.0),
          rxyz(ax=36, ay=-s * 5))
        m = Mesh()
        m.tube('metal', 0.64, 0.64, 1.10, 12, off=(0, 0, 0), rot=ry(90))
        m.box('plate', (1.30, 1.32, 2.90), off=(0, 0.06, -1.55), bev=0.34,
              taper=0.84)
        m.box('plate2', (1.36, 0.52, 1.90), off=(0, 0.70, -1.60), bev=0.20)
        m.box('rust2', (0.48, 0.40, 2.30), off=(s * 0.70, -0.56, -1.55), bev=0.12)
        P('thigh ' + tag, 'hip' + tag, m, 'limb')

        F('knee' + tag, 'hip' + tag, (0.0, 0.0, -3.00), rx(-84))
        m = Mesh()
        # Knee cowl: the surface that takes the weather, so it takes the oxide.
        # It also projects well forward, which is most of what announces a
        # reverse joint from side on.
        m.tube('metal', 0.72, 0.72, 1.15, 12, off=(0, 0, 0.05), rot=ry(90))
        m.pod('rust', [(-0.90, 0.60, 0.74), (-0.30, 0.82, 1.05),
                       (0.35, 0.84, 1.05), (0.80, 0.62, 0.76)],
              n=8, axis='z', off=(0, 0.62, -0.10), phase=math.pi / 8)
        m.box('rust2', (1.05, 0.42, 0.70), off=(0, 1.12, -0.20), bev=0.12)
        P('knee ' + tag, 'knee' + tag, m, 'limb')

        m = Mesh()
        m.box('plate', (1.10, 1.12, 3.20), off=(0, -0.04, -1.85), bev=0.30,
              taper=0.86)
        m.box('plate2', (1.16, 0.44, 2.10), off=(0, -0.62, -1.85), bev=0.16)
        # calf ram, the piece that reads as a machine in motion
        m.tube('metal', 0.16, 0.16, 1.90, 8, off=(s * 0.48, 0.76, -1.45))
        m.tube('metal2', 0.23, 0.23, 1.05, 8, off=(s * 0.48, 0.76, -2.55))
        m.box('green', (0.32, 0.06, 0.32), off=(-s * 0.55, -0.72, -1.15))
        P('shin ' + tag, 'knee' + tag, m, 'limb')

        # ---- ankle shaft and foot ----
        # A short vertical pastern between the shin and the sole. Without it the
        # shin has to reach the ground on its own and the ankle ends up either
        # buried or floating; with it, the leg gets the extra break that makes
        # the digitigrade stance legible.
        F('ankle' + tag, 'knee' + tag, (0.0, 0.0, -3.50), rx(48))
        m = Mesh()
        m.tube('metal', 0.52, 0.52, 0.95, 10, off=(0, 0, 0), rot=ry(90))
        m.box('metal2', (0.86, 0.90, 1.15), off=(0, 0.02, -0.60), bev=0.20)
        m.tube('metal', 0.15, 0.15, 0.95, 8, off=(s * 0.38, 0.50, -0.62))
        P('ankle ' + tag, 'ankle' + tag, m, 'limb')

        m = Mesh()
        # Sole plate, then three splayed toes and a heel spur. Splayed toes are
        # most of what makes a bird leg look like it is carrying something.
        m.box('rust2', (1.85, 2.90, 0.50), off=(0, 0.55, -1.55), bev=0.26)
        for k, txo in ((-1, -0.58), (0, 0.0), (1, 0.58)):
            m.box('rust', (0.52, 1.15, 0.40), off=(txo, 1.95, -1.60),
                  rot=rz(k * 8), bev=0.12, taper=0.8)
        m.box('rust2', (1.15, 0.80, 0.42), off=(0, -1.05, -1.53), bev=0.14,
              taper=0.85)
        m.box('plate2', (1.30, 1.30, 0.55), off=(0, 0.35, -1.22), bev=0.18)
        P('foot ' + tag, 'ankle' + tag, m, 'limb')

    return frames, order, parts


def pose_mech(frames, sim, idle=True):
    """Idle pose. Small, slow and out of phase across the joints -- a machine
    this heavy never quite stops moving, and a rig that is perfectly still
    reads as a photograph rather than as a model."""
    if not idle:
        for f in frames.values():
            f.pose = IDENT
        return
    b = math.sin(sim * 0.9)
    b2 = math.sin(sim * 0.9 + 1.1)
    frames['pelvis'].pose = rxyz(ax=b * 0.7, az=b2 * 0.5)
    frames['torso'].pose = rxyz(ax=-b * 1.1, ay=b2 * 0.6, az=math.sin(sim * 0.6) * 1.4)
    for tag, ph in (('L', 0.0), ('R', 2.1)):
        s = -1 if tag == 'L' else 1
        frames['sh' + tag].pose = rxyz(ax=math.sin(sim * 0.75 + ph) * 1.6,
                                       ay=s * math.sin(sim * 0.5 + ph) * 1.0)
        frames['elb' + tag].pose = rxyz(ax=math.sin(sim * 0.65 + ph) * 1.3)
        frames['rack' + tag].pose = rxyz(ax=math.sin(sim * 0.55 + ph) * 0.9)
