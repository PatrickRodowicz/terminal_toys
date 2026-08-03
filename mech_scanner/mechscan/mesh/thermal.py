"""Where the heat is."""

# The heat field. Sarna gives this machine a Starfire 375 XL, and a fusion
# plant is hotter than everything else on the mech put together -- so a
# thermal channel whose brightest thing was an armpit was measuring the wrong
# quantity. Occlusion is a real property, but it is the *trapping* term, not
# the source.
#
# The source is a point at the measured centroid of the TORSO section. The
# engine is not placed by hand and it is not eyeballed off the silhouette: it
# is where the mass of the torso actually is, which for an XL plant filling
# the centre and both sides is the honest available answer. Falloff is inverse
# square, as a point source radiating into a solid must be. Occlusion stays in
# as the second term, weaker: heat that reaches the skin in a joint has a
# harder time leaving it.
REACTOR_R = 0.20         # half-strength distance, as a fraction of mech height
REACTOR_MIX = 0.76       # weight of the source term against the trapping term


def heat_field(verts, faces, ao, core, height):
    """Per-facet temperature in [0, 1]: reactor proximity plus trapping.

    Baked at build time and cached, so the thermal channel costs the shader a
    single list index at frame time -- the same trick occlusion already uses.
    Normalised against its own maximum rather than against a theoretical one,
    because the maximum is the skin nearest the plant and that is exactly the
    thing the ramp's top end should mean.
    """
    if core is None or not faces:
        return [0.0] * len(faces)
    kx, ky, kz = core
    r2 = (REACTOR_R * height) ** 2 or 1.0
    out = []
    for fi, (ia, ib, ic) in enumerate(faces):
        pa, pb, pc = verts[ia], verts[ib], verts[ic]
        dx = (pa[0] + pb[0] + pc[0]) / 3.0 - kx
        dy = (pa[1] + pb[1] + pc[1]) / 3.0 - ky
        dz = (pa[2] + pb[2] + pc[2]) / 3.0 - kz
        q = 1.0 / (1.0 + (dx * dx + dy * dy + dz * dz) / r2)
        trap = 1.0 - (ao[fi] if fi < len(ao) else 1.0)
        out.append(REACTOR_MIX * q + (1.0 - REACTOR_MIX) * trap)
    hi = max(out) or 1.0
    return [min(1.0, v / hi) for v in out]
