"""The key list.

Keys only. This was a page and a half of prose at one point, which is a strange
thing to put behind a key you press mid-orbit to remember what 'v' does. The
prose that was worth keeping is in the module docstrings and in the comments
beside the things they describe; the rest was explaining decisions to someone
who did not ask.
"""

HELP = [
    'MECHMODEL // controls',
    '',
    'SPACE  pause turntable    v      sensor channel',
    '<- ->  orbit              c      cutaway plane',
    '^ v    tilt               - =    move the cut',
    '[ ]    zoom               j k    target section',
    ', .    spin rate          m      panel: combat/mesh',
    'd      detail             f      cockpit chrome',
    'a      occlusion          b      replay startup',
    'w      wireframe          l      labels',
    'g      grid               S      cast shadow',
    's      starfield          L      lighting',
    'i      idle animation     p 1-6  palette',
    'e      exploded view      z      zen (hide HUD)',
    'r      frame rate cap     0      reset',
    'h      this help          q      quit',
]


def draw(ov, P, rows, cols):
    HD, PN = P['hud_dim'], P['panel']
    bw = min(cols - 4, 66)
    bh = len(HELP) + 2
    c0 = (cols - bw) // 2
    r0 = max(0, (rows - bh) // 2)
    ov.text(r0, c0, '┌' + '─' * (bw - 2) + '┐', HD, PN)
    for i, ln in enumerate(HELP):
        ov.text(r0 + 1 + i, c0, '│', HD, PN)
        ov.text(r0 + 1 + i, c0 + bw - 1, '│', HD, PN)
        ov.text(r0 + 1 + i, c0 + 2, ln[:bw - 4],
                P['sel'] if i == 0 else P['hud'], PN)
    ov.text(r0 + bh - 1, c0, '└' + '─' * (bw - 2) + '┘', HD, PN)
