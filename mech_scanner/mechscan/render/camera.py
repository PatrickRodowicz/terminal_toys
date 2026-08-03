"""The turntable camera.

An orbit about the model's own vertical axis. The framing is refitted every
frame because the terminal can be resized and the model can be pulled apart,
but it is fitted to the bounding CYLINDER rather than to the corners of a box:
a cylinder's projection does not depend on the azimuth at all, so the framing
is exactly constant as the turntable turns instead of breathing every quarter
revolution.

`project` is the general form and is used for the ground, the grid, the shadow
and the labels -- geometry measured in tens of vertices. The hot path, the
model's own few thousand vertices, does not call it: render/facets.py inlines
the same arithmetic, because at that count the call and its cell lookups cost
more than the multiply-add inside them. The two are kept in step by hand, and
the pixel-diff harness is what checks that they still are.
"""
import math

# Sixteen points around the bounding cylinder. Even at a wide field of view the
# extreme of the projected outline is within a fraction of a cell of one of
# these, and the cost is fixed regardless of facet count.
FIT_RING = [(math.cos(a * math.pi / 8), math.sin(a * math.pi / 8))
            for a in range(16)]


class Camera:
    """Orbit position, and the fit that frames the model in the viewport."""

    __slots__ = ('subx', 'az', 'el', 'dist', 'zoom', 'ca', 'sa', 'ce', 'se',
                 'x', 'y', 'z', 'fl', 'ox', 'oy', 'mcz')

    def __init__(self, subx):
        self.subx = subx
        self.az = self.el = 0.0
        self.dist = self.zoom = 1.0
        self.ca = self.ce = 1.0
        self.sa = self.se = 0.0
        self.x = self.y = self.z = 0.0
        self.fl = 1.0
        self.ox = self.oy = 0.0
        self.mcz = 0.0

    def update(self, az, el, dist, zoom, ext, explode, panel_px, avail_w, pxh):
        """Place the eye and refit the framing.

        `ext` is the model's rest-pose extent (see rig.Extent); `explode` grows
        the fitted cylinder by the displacement, so pulling the machine apart
        pulls the camera back with it instead of flinging the parts off screen.
        """
        self.az, self.el, self.dist, self.zoom = az, el, dist, zoom
        ca, sa = math.cos(az), math.sin(az)
        ce, se = math.cos(el), math.sin(el)
        self.ca, self.sa, self.ce, self.se = ca, sa, ce, se
        self.mcz = mcz = ext.mcz
        self.x = dist * ce * sa
        self.y = -dist * ce * ca
        self.z = dist * se + mcz

        eg = explode * ext.mrad * 1.15
        fr_ = ext.mrad + eg
        us, vs = [], []
        for cth, sth in FIT_RING:
            xr, yr = fr_ * cth, fr_ * sth
            for cz_ in (ext.mz0 - mcz - eg, ext.mz1 - mcz + eg):
                zv = yr * ce - cz_ * se + dist
                if zv < 1.0:
                    zv = 1.0
                us.append(self.subx * xr / zv)
                vs.append(-(yr * se + cz_ * ce) / zv)
        du = (max(us) - min(us)) or 1e-6
        dv = (max(vs) - min(vs)) or 1e-6
        self.fl = fl = min(avail_w / du, (pxh - 4) / dv) * 0.93 * zoom
        self.ox = panel_px + avail_w / 2 - fl * (min(us) + max(us)) / 2
        self.oy = pxh / 2 - fl * (min(vs) + max(vs)) / 2

    def project(self, x, y, z):
        """World -> (screen x, screen y, camera-space depth).

        The model is small next to `dist`, so no near plane can be crossed; the
        clamp is only there so a degenerate pose cannot raise over a raw
        terminal.
        """
        z -= self.mcz
        ca, sa, ce, se = self.ca, self.sa, self.ce, self.se
        xr = x * ca + y * sa
        yr = -x * sa + y * ca
        zv = yr * ce - z * se + self.dist
        if zv < 0.6:
            zv = 0.6
        return (self.ox + self.fl * self.subx * xr / zv,
                self.oy - self.fl * (yr * se + z * ce) / zv, zv)
