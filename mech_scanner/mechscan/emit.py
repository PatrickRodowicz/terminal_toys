"""Raster plus overlay to one string of ANSI, once per frame.

The last stage, and the one that has never been optimised: it is a per-CELL
Python loop, so at 200x60 it is twelve thousand iterations regardless of how
much geometry there was. Everything upstream of here is per-facet and has been
worked over; this is per-cell and has not. It measures 15-25% of the frame.

Two pixels per cell in half-block mode and four in quad mode. In quad mode the
four sub-pixels are reduced to two colours by luminance -- brightest and
darkest -- and the glyph is the 4-bit mask of which sub-cells took the bright
one. That is a two-colour approximation of a four-colour cell, and it is what
the quadrant glyphs can express.
"""

from .ansi import BG_DEF, FG_DEF, HOME, QUAD, RESET, bg, fg


def emit(ras, ov, rows, cols, subx):
    px = ras.px
    out = [HOME]
    for r in range(rows):
        orow = ov[r]
        ptop = px[r * 2]
        pbot = px[r * 2 + 1]
        line = []
        cfg = cbg = -1
        for c in range(cols):
            o = orow[c]
            if o is not None:
                chx, f_, b_ = o
                if f_ is None:
                    t = ptop[c * subx]
                    f_ = t if t is not None else (200, 200, 200)
            elif subx == 1:
                t = ptop[c]
                b_ = pbot[c]
                if t == b_:
                    chx, f_ = '█', t
                    b_ = None
                else:
                    chx, f_ = '▀', t
            else:
                x2 = c + c
                pa = ptop[x2]
                pb = ptop[x2 + 1]
                pc = pbot[x2]
                pd = pbot[x2 + 1]
                if pa == pb == pc == pd:
                    chx, f_, b_ = '█', pa, None
                else:
                    la = pa[0] + pa[1] + pa[2]
                    lb = pb[0] + pb[1] + pb[2]
                    lc = pc[0] + pc[1] + pc[2]
                    ld = pd[0] + pd[1] + pd[2]
                    hi = lo = la
                    f_ = b_ = pa
                    if lb > hi:
                        hi, f_ = lb, pb
                    if lb < lo:
                        lo, b_ = lb, pb
                    if lc > hi:
                        hi, f_ = lc, pc
                    if lc < lo:
                        lo, b_ = lc, pc
                    if ld > hi:
                        hi, f_ = ld, pd
                    if ld < lo:
                        lo, b_ = ld, pd
                    if hi == lo:
                        chx, f_, b_ = '█', pa, None
                    else:
                        mid = (hi + lo) * 0.5
                        m = 1 if la >= mid else 0
                        if lb >= mid:
                            m |= 2
                        if lc >= mid:
                            m |= 4
                        if ld >= mid:
                            m |= 8
                        chx = QUAD[m]
            if f_ != cfg:
                line.append(fg(f_) if f_ is not None else FG_DEF)
                cfg = f_
            if b_ != cbg:
                line.append(bg(b_) if b_ is not None else BG_DEF)
                cbg = b_
            line.append(chx)
        line.append(RESET)
        out.append(''.join(line))
        if r < rows - 1:
            out.append('\n')
    return ''.join(out)
