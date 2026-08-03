"""The pixel buffer.

1x2 pixels per terminal cell (or 2x2 in quad mode -- see SUBX in the app).
Spans are written with slice assignment, which is the only reason this runs at
frame rate in pure Python.
"""
import math

from .ansi import lerp, quant

class Raster:
    """Pixel buffer at 1x2 per terminal cell, emitted as half-blocks. Spans are
    written with slice assignment, which is the only reason this runs at frame
    rate in pure Python."""

    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = [[None] * w for _ in range(h)]

    def clear(self, c=None):
        w = self.w
        for row in self.px:
            row[:] = [c] * w

    def hband(self, y0, y1, c):
        px, w = self.px, self.w
        if y0 < 0:
            y0 = 0
        if y1 > self.h:
            y1 = self.h
        row = [c] * w
        for y in range(y0, y1):
            px[y] = row[:]

    def point(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = c

    def fill(self, pts, c0, c1=None):
        """Scanline-fill a convex polygon, lerping c0 (top) -> c1 (bottom)."""
        n = len(pts)
        ys = [p[1] for p in pts]
        ymin, ymax = min(ys), max(ys)
        y0 = int(math.ceil(ymin - 0.5))
        y1 = int(math.floor(ymax - 0.5))
        if y0 < 0:
            y0 = 0
        if y1 >= self.h:
            y1 = self.h - 1
        if y1 < y0:
            return
        span = (ymax - ymin) or 1.0
        px, W = self.px, self.w
        grad = c1 is not None and c1 != c0
        for y in range(y0, y1 + 1):
            yc = y + 0.5
            xs = []
            for i in range(n):
                ax, ay = pts[i]
                bx, by = pts[i - 1]
                if (ay <= yc < by) or (by <= yc < ay):
                    xs.append(ax + (bx - ax) * (yc - ay) / (by - ay))
            if len(xs) < 2:
                continue
            if len(xs) > 2:
                xs.sort()
            elif xs[0] > xs[1]:
                xs.reverse()
            c = quant(lerp(c0, c1, (yc - ymin) / span)) if grad else c0
            row = px[y]
            for i in range(0, len(xs) - 1, 2):
                xa = int(math.ceil(xs[i] - 0.5))
                xb = int(math.floor(xs[i + 1] - 0.5)) + 1
                if xa < 0:
                    xa = 0
                if xb > W:
                    xb = W
                if xb > xa:
                    row[xa:xb] = [c] * (xb - xa)

    def fill3(self, a, b, c, col):
        """fill(), specialised to a triangle in one flat colour.

        Worth its own method because of what the facets actually measure: on
        the STL at 80x24 a facet covers 0.93 scanlines and 2.3 pixels. At that
        size the generic fill's per-scanline overhead -- a fresh list, a loop
        over every edge, two appends, a length test, sometimes a sort -- IS the
        cost, and the slice assignment the whole raster design exists to reach
        is writing two pixels. Sorting the three vertices once and walking the
        long edge against one short edge removes all of it.

        The arithmetic is deliberately kept in the same order as fill() --
        dx precomputed but still divided by dy, never multiplied by a
        reciprocal -- so this is bit-for-bit the same picture, which was
        checked rather than assumed.
        """
        if a[1] > b[1]:
            a, b = b, a
        if b[1] > c[1]:
            b, c = c, b
        if a[1] > b[1]:
            a, b = b, a
        ay, by, cy = a[1], b[1], c[1]
        y0 = int(math.ceil(ay - 0.5))
        y1 = int(math.floor(cy - 0.5))
        if y0 < 0:
            y0 = 0
        if y1 >= self.h:
            y1 = self.h - 1
        if y1 < y0:
            return
        dyl = cy - ay
        if dyl == 0.0:
            return
        ax, bx, cx = a[0], b[0], c[0]
        dxl = cx - ax
        d1x, d1y = bx - ax, by - ay
        d2x, d2y = cx - bx, cy - by
        px, W = self.px, self.w
        for y in range(y0, y1 + 1):
            yc = y + 0.5
            xl = ax + dxl * (yc - ay) / dyl
            if yc < by:
                if d1y == 0.0:
                    continue
                xr = ax + d1x * (yc - ay) / d1y
            else:
                if d2y == 0.0:
                    continue
                xr = bx + d2x * (yc - by) / d2y
            if xl > xr:
                xl, xr = xr, xl
            xa = int(math.ceil(xl - 0.5))
            xb = int(math.floor(xr - 0.5)) + 1
            if xa < 0:
                xa = 0
            if xb > W:
                xb = W
            if xb > xa:
                px[y][xa:xb] = [col] * (xb - xa)

    def line(self, x0, y0, x1, y1, c):
        dx, dy = x1 - x0, y1 - y0
        steps = int(max(abs(dx), abs(dy)))
        if steps <= 0:
            self.point(int(x0), int(y0), c)
            return
        sx, sy = dx / steps, dy / steps
        px, W, H = self.px, self.w, self.h
        x, y = x0, y0
        for _ in range(steps + 1):
            xi, yi = int(x), int(y)
            if 0 <= xi < W and 0 <= yi < H:
                px[yi][xi] = c
            x += sx
            y += sy

    def line_c(self, x0, y0, x1, y1, c):
        """line(), but clipped to the viewport first (Liang-Barsky), so a
        segment whose endpoint landed far off screen costs nothing to skip."""
        dx, dy = x1 - x0, y1 - y0
        t0, t1 = 0.0, 1.0
        for p, q in ((-dx, x0), (dx, self.w - 1 - x0),
                     (-dy, y0), (dy, self.h - 1 - y0)):
            if p == 0.0:
                if q < 0.0:
                    return
            else:
                r = q / p
                if p < 0.0:
                    if r > t1:
                        return
                    if r > t0:
                        t0 = r
                else:
                    if r < t0:
                        return
                    if r < t1:
                        t1 = r
        self.line(x0 + t0 * dx, y0 + t0 * dy,
                  x0 + t1 * dx, y0 + t1 * dy, c)
