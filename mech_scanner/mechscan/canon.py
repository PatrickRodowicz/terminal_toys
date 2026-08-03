"""Sourced facts about a machine, read from a mech directory.

A mech lives in its own directory under mechs/:

    mechs/timber_wolf/
        timber_wolf.stl      the geometry
        canon.md             the facts, with their sources
        reference.png        optional, not read by the program

Canon used to be a dict in this file, which meant the program only knew about
one machine and applied its stats to whatever mesh it was handed. Now it is
data: point the scanner at a directory and it renders that mesh with those
facts, and adding a mech is adding a directory.

Three rules survive the move from code to data, and they are the point of the
whole thing:

  * Everything in a canon.md must have a source, and the file carries its own
    sources. --stats prints them.
  * A field nobody sourced is ABSENT, not zero and not guessed. The panel draws
    the blocks it has data for and silently omits the rest, so an incomplete
    canon.md degrades into a shorter readout rather than a confident wrong one.
  * Geometry never supplies lore and lore never supplies geometry. Nothing in
    here is derived from the mesh, and the mesh report contains no tonnage.

Point the scanner at a bare .stl instead and there is no canon at all: the
display drops to the measured survey. That is also what you get for a mech
directory with no canon.md.
"""
import os
import re

CANON_FILE = 'canon.md'
MECHS_DIR = 'mechs'

# key -> (coercion, human name). A key not in here is ignored, so a canon.md
# can carry notes for a reader without the parser having to know about them.
# Everything is optional: see the second rule above.
FIELDS = {
    'name':      (str, 'designation'),
    'codename':  (str, 'codename'),
    'config':    (str, 'configuration'),
    'origin':    (str, 'origin'),
    'intro':     (int, 'introduced'),
    'mass_t':    (float, 'mass, tons'),
    'chassis':   (str, 'chassis'),
    'engine':    (str, 'engine'),
    'armour':    (str, 'armour type'),
    'armour_t':  (float, 'armour, tons'),
    'heatsinks': (str, 'heat sinks'),
    'podspace':  (float, 'pod space, tons'),
    'cruise':    (float, 'cruising speed, km/h'),
    'flank':     (float, 'flank speed, km/h'),
    'walk_mp':   (int, 'walk MP'),
    'run_mp':    (int, 'run MP'),
    # Model-loading hints. Not lore -- properties of the file on disk -- but
    # they belong beside it, and the alternative is remembering --up y for one
    # mech and not another.
    'stl':       (str, 'mesh file'),
    'up':        (str, 'up axis'),
}

_ROW = re.compile(r'^\s*\|(.*)\|\s*$')
_RULE = re.compile(r'^[\s|:-]+$')
_HEAD = re.compile(r'^(#+)\s*(.*?)\s*$')
_BULLET = re.compile(r'^\s*[-*]\s+(.*?)\s*$')


def _cells(line):
    return [c.strip() for c in _ROW.match(line).group(1).split('|')]


def parse(text):
    """A canon.md into (fields, weapons, sources, notes).

    Markdown tables, because they are the one structured form that is both
    trivially parseable with the standard library and pleasant to read and edit
    as a document. The alternative was YAML, which is not in the standard
    library, or JSON, which nobody wants to write prose in.

    Any `| key | value |` table row anywhere in the file sets a field. The
    `## Weapons` section is the exception: its rows are (name, count) pairs and
    order matters, because that is how the loadout is quoted. Anything that is
    not a table row is prose and is ignored, so the file can explain itself.
    """
    fields, weapons, sources, notes = {}, [], [], []
    section = ''
    for raw in text.split('\n'):
        line = raw.rstrip()
        if not line.strip():
            continue
        m = _HEAD.match(line)
        if m:
            section = m.group(2).strip().lower()
            continue
        if section == 'sources':
            b = _BULLET.match(line)
            if b:
                sources.append(b.group(1))
            continue
        if not _ROW.match(line) or _RULE.match(line):
            if section == 'notes':
                b = _BULLET.match(line)
                notes.append(b.group(1) if b else line.strip())
            continue
        cells = _cells(line)
        if len(cells) < 2:
            continue
        key, val = cells[0], cells[1]
        low = key.lower()
        if low in ('field', 'key', 'weapon', 'name') and val.lower() in (
                'value', 'count', 'qty'):
            continue                      # a header row
        if section == 'weapons':
            try:
                weapons.append((key, int(val)))
            except ValueError:
                continue
            continue
        spec = FIELDS.get(low)
        if spec is None:
            continue
        try:
            fields[low] = spec[0](val)
        except ValueError:
            # A malformed value is dropped rather than guessed at. The field
            # goes absent, and absent is a state the display handles.
            continue
    return fields, weapons, sources, notes


class Mech:
    """One mech directory: a mesh, and optionally the facts about it."""

    __slots__ = ('dir', 'stl', 'canon', 'up', 'sources', 'notes', 'title')

    def __init__(self, directory, stl, canon, up, sources, notes, title):
        self.dir = directory
        self.stl = stl
        self.canon = canon        # dict, or None for no sourced facts
        self.up = up
        self.sources = sources
        self.notes = notes
        self.title = title

    @property
    def name(self):
        if self.canon and self.canon.get('name'):
            return self.canon['name']
        return os.path.basename(self.stl)


def _find_stl(directory, named=None):
    if named:
        p = os.path.join(directory, named)
        if os.path.exists(p):
            return p
    stls = sorted(f for f in os.listdir(directory) if f.lower().endswith('.stl'))
    if not stls:
        raise ValueError('%s contains no .stl' % directory)
    return os.path.join(directory, stls[0])


def load_dir(directory, use_canon=True):
    """Read a mech directory.

    The canon.md is optional. Without one -- or with --canon none -- this is
    just a mesh in a folder, and the display says so.
    """
    directory = os.path.abspath(directory)
    md = os.path.join(directory, CANON_FILE)
    fields = weapons = sources = notes = None
    title = os.path.basename(directory)
    if use_canon and os.path.exists(md):
        fields, weapons, sources, notes = parse(open(md, encoding='utf-8').read())
        for ln in open(md, encoding='utf-8'):
            m = _HEAD.match(ln)
            if m and len(m.group(1)) == 1:
                title = m.group(2)
                break
    stl = _find_stl(directory, (fields or {}).get('stl'))
    up = (fields or {}).get('up', 'z')
    canon = None
    if fields:
        canon = dict(fields)
        canon['weapons'] = tuple(weapons)
        # A canon table with no designation cannot label anything, so it is
        # not a canon table. Better to fall back to the survey than to put an
        # unnamed machine's tonnage on screen.
        if not canon.get('name'):
            canon = None
    return Mech(directory, stl, canon, up, sources or [], notes or [], title)


def mechs_dir():
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), MECHS_DIR)


def available():
    """Mech directories, for --list and for the 'no such mech' message.

    Anything starting with _ is skipped, which is how _template stays a
    document rather than becoming a selectable machine.
    """
    root = mechs_dir()
    if not os.path.isdir(root):
        return []
    return sorted(d for d in os.listdir(root)
                  if not d.startswith('_')
                  and os.path.isdir(os.path.join(root, d)))


def resolve(target):
    """A command-line argument into a directory to load.

    Accepts a mech name ('timber_wolf'), a path to a mech directory, or None
    for the first mech in mechs/.
    """
    if target is None:
        names = available()
        if not names:
            return None
        return os.path.join(mechs_dir(), names[0])
    if os.path.isdir(target):
        return target
    cand = os.path.join(mechs_dir(), target)
    if os.path.isdir(cand):
        return cand
    return None
