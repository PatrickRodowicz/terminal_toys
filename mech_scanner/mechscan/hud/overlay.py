"""The character layer that sits over the raster.

One cell per terminal cell, each either None (show the pixels underneath) or
(glyph, foreground, background). A foreground of None means 'take the colour of
the pixel underneath', which is what lets the chrome read as glass over the
render rather than as a panel laid on top of it; a background of None means the
same for the cell behind.
"""


class Overlay:
    __slots__ = ('rows', 'cols', 'cells')

    def __init__(self, rows, cols):
        self.rows = rows
        self.cols = cols
        self.cells = [[None] * cols for _ in range(rows)]

    def __getitem__(self, r):
        return self.cells[r]

    def text(self, r, c, s, f=None, b=None):
        if r < 0 or r >= self.rows:
            return
        row = self.cells[r]
        cols = self.cols
        for i, ch in enumerate(s):
            x = c + i
            if 0 <= x < cols:
                row[x] = (ch, f, b)
