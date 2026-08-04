"""The target acquisition readout.

A framed block over the viewport, deliberately not over the whole screen: the
point of doing the build on a worker thread is that the sight keeps running,
and covering it would throw that away. The current target stays visible and
turning behind the box, which is what the sequence is *for*.

The lines are the mesh pipeline's own progress messages, arriving as they
happen. See acquire.py for why there is no progress bar.
"""
BOX_W = 46
MAX_LINES = 8
# Below these the box is more intrusive than informative, and the flash line
# has already named the target, so nothing said only here is lost.
MIN_W, MIN_H = 26, 9


def _elide(s, n):
    """Shorten to n cells keeping the head and the TAIL.

    An exception here reads 'ValueError: <long absolute path>: <the reason>',
    so plain truncation keeps the class and the start of a path nobody needs
    and throws away the only part worth reading.
    """
    if len(s) <= n:
        return s
    if n < 8:
        return s[:n]
    head = (n - 1) // 3
    return s[:head] + '…' + s[-(n - head - 1):]


def _tick(i, n, done):
    """OK for a stage that has finished. The LAST line is the stage still
    running -- until the build finishes, at which point it has finished too."""
    return 'OK' if (done or i < n - 1) else '··'


def draw(ov, P, rows, cols, panel, acq, now):
    H, HD, PN = P['hud'], P['hud_dim'], P['panel']
    avail = cols - panel
    w = min(BOX_W, avail - 2)
    if w < MIN_W or rows < MIN_H:
        return
    lines = acq.lines[-MAX_LINES:]
    # Frame row, designation row, the stages, an error row if there is one,
    # frame row. At least one body row even before the first stage arrives, so
    # the box does not open as a seam with no inside.
    nbody = max(1, len(lines) + (1 if acq.err else 0))
    h = min(nbody + 3, rows - 3)
    lines = lines[-max(0, h - 3 - (1 if acq.err else 0)):]
    c0 = panel + max(0, (avail - w) // 2)
    # Low in the viewport rather than centred: the machine is drawn about the
    # middle of the screen and this is a readout ABOUT it, not a replacement.
    r0 = max(1, min(rows - h - 2, int(rows * 0.56)))
    # Fill and frame EVERY row up front. Drawing the side bars per content row
    # instead leaves a gap in the edge on any row that has no content yet,
    # which the box has for its first few frames.
    for r in range(r0, r0 + h):
        ov.text(r, c0, ' ' * w, HD, PN)
    for r in range(r0 + 1, r0 + h - 1):
        ov.text(r, c0, '│', HD, PN)
        ov.text(r, c0 + w - 1, '│', HD, PN)
    ov.text(r0 + h - 1, c0, '└' + '─' * (w - 2) + '┘', HD, PN)

    if acq.err:
        title, tcol = 'ACQUISITION FAILED', P['alert']
    elif acq.finished:
        title, tcol = 'LOCK', P['sel']
    else:
        title, tcol = 'TARGET ACQUISITION', H
    # Elapsed, not remaining, and not a percentage: the only number here that
    # is known rather than guessed. It freezes when the build finishes, so what
    # is left on screen is what the acquisition actually cost -- which is also
    # the honest way to show that a warm cache took 0.0 s.
    # max(0) because t0 is stamped in the keypress, which happens AFTER the
    # frame took its `now` -- so the first frame of an acquisition is a
    # fraction of a millisecond in the past, and prints as '-0.0 s'.
    el = '%.1f s' % max(0.0, (acq.t1 or now) - acq.t0)
    # Composed as ONE string of exactly w cells and then recoloured in place.
    # Writing the frame and the title as two overlapping strings is how the
    # first version left a stray letter of the title poking out of the rule.
    stamp = ' %s ' % el
    tag = ' %s ' % title
    fill = w - 2 - len(tag) - len(stamp)
    if fill < 0:
        tag, fill = tag[:len(tag) + fill], 0
    ov.text(r0, c0, '┌' + tag + '─' * fill + stamp + '┐', HD, PN)
    ov.text(r0, c0 + 1, tag, tcol, PN)

    ov.text(r0 + 1, c0 + 2, acq.name.replace('_', ' ').upper()[:w - 4],
            P['sel'], PN)

    done = acq.finished
    r = r0 + 1
    for i, ln in enumerate(lines):
        r += 1
        if r >= r0 + h - 1:
            break
        ok = _tick(i, len(lines), done)
        ov.text(r, c0 + 2, '[%s] ' % ok, H if ok == 'OK' else HD, PN)
        ov.text(r, c0 + 7, ln[:w - 9], H if ok == 'OK' else HD, PN)
    if acq.err and r + 1 < r0 + h - 1:
        ov.text(r + 1, c0 + 2, _elide(acq.err, w - 4), P['alert'], PN)
