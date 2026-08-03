"""Number and bar formatting for the readouts."""

def commas(n):
    return '{:,}'.format(int(n))


def bar_str(frac, n=10):
    if frac < 0:
        frac = 0.0
    if frac > 1:
        frac = 1.0
    full = int(frac * n)
    rem = frac * n - full
    s = '█' * full
    if full < n:
        s += ' ▏▎▍▌▋▊▉'[int(rem * 8)]
    return (s + ' ' * n)[:n]
