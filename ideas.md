# hackertime — idea list

Terminal ambiance with a hacker bent. House rules that have worked so far:
pure-Python stdlib, no pip installs, no runtime network calls, data baked in at
build time where possible, and **real data wherever we can get it** — the things
that read best are the ones that are actually true.

Status as of 2026-08-01.

---

## Built

### globe.py — dot-matrix spinning Earth
Orthographic sphere, real Natural Earth coastlines, day/night terminator,
great-circle arcs, satellite orbits, city markers, five palettes, live
keybindings.

### netmap.py — live network cartography
Your real TCP/UDP connections plotted on an equirectangular world map.
Great-circle arcs, packets driven by actual `bytes_sent`/`bytes_received`,
real RTT from `tcp_info`, PIDs, country-level geolocation from an embedded
DB-IP table, reverse DNS, live day/night terminator, event log, `--remote` to
map a server over SSH with inbound-connection detection.

### dscape.py — voxel cityscape of a filesystem
Disk usage as an orbiting city. Squarified treemap on the ground plane, each
directory extruded into a block. Footprint area goes as `size^0.55` and height
as `size^0.45`, which multiplies out so that a block's **volume is exactly
proportional to its bytes** — the amount of stuff you see is the amount of disk
it uses. `--footprint count` splits the channels apart instead: ground plan by
file count, height still by bytes, so sprawl means many small files.
Perspective projection with painter's-algorithm boxes, edge lighting, window
lights, aerial-perspective fog, category tints from the extension mix. Real
`os.scandir` walk on a background thread — the city builds itself while the
scan runs, and blocks that haven't finished counting shimmer. Drill down with
ENTER, back out with BKSP — and past the directory you launched in, BKSP walks
*above* the root by starting a fresh scan of the parent, since the tree only
ever grew downward. `t` cranes the camera overhead and stops the spin, snapping
the heading square and pulling the camera back toward orthographic so the city
flattens into a plain treemap; `t` again returns to the orbit. `x` marks a path
and the marks print to stdout on exit. `--print` gives a plain du-style report
instead.

The two decisions that made it readable, both found by looking at renders:
footprints use a 0.55-power compression (raw file counts span five decades, so
one `.cache` swallowed the whole plot), and every block gets a lit roofline
plus a dark vertical corner (without them the skyline was one solid lump).

A signal handler that raises can fire *anywhere* — including inside the
teardown that restores the cursor, colours and terminal mode. Raising
`KeyboardInterrupt` from the SIGTERM/SIGHUP handler meant a second signal
landing during cleanup escaped `main` and dumped a traceback over a terminal
left in raw mode with the cursor hidden. Disarming at the top of cleanup does
not fix it: a signal already in flight lands between entering the function and
the `SIG_IGN` taking effect. The handler now only records the request and the
frame loop notices it where unwinding is safe, and cleanup goes deaf and
retries once. It surfaced roughly once in forty runs under `timeout`.

One deliberate non-fix, recorded so it doesn't get "improved" again: the
starfield thins out and is gone about two thirds down the screen. That began as
a hard cutoff in the placement, and flattening it to a full-height distribution
was a regression — the taper is the effect, not an artefact. It is now a
brightness fade to the same limit, which keeps the look without the seam the
hard edge left in a tall window.

Two encoding lessons from the panel, both found by a user simply asking what
something meant. Colour was doing double duty — file-type category above 2% of
the parent, flat dim below it — so the same channel silently changed meaning
partway down the list; it now always means category, with brightness carrying
significance, and there is a legend in the help overlay because a colour code
nobody can look up may as well be decoration. And the share bar was whole cells
out of nine, so everything under 11% rounded to zero and the column sat empty
for 59 rows out of 62, looking like it meant nothing; it now draws in eighths
so a 0.4% row still shows a sliver, and it keeps its category colour on the
selected row instead of vanishing into the highlight. Columns have headers now.

Bytes lying loose in a directory belong to no subdirectory, so they get a
synthetic **`(files here)` district** of their own — otherwise a Downloads
holding 28 GB of files and two small folders renders as just the two folders,
with 88% of the directory invisible. It is a block like any other: selectable,
labelled, and openable. Opening it does a single on-demand `scandir` of that
one directory and gives every file its own block with its real path, so `x`
marks individual files. Marking the aggregate is refused, because its path is
the directory itself.

Renders with **quadrant glyphs** (U+2580..U+259F) rather than half-blocks: 2×2
sub-cells instead of 1×2, so twice the horizontal detail for about a third more
CPU. Per cell the four sub-pixels are split about the midpoint of their
luminance range — brightest becomes the foreground, darkest the background —
with an equality fast path that catches sky and flat faces. `--blocks half`
reverts. Note the projection has to scale x by the sub-cell count, since a
quadrant cell is half as wide as it is tall.

One bug worth remembering, because it will recur in anything that draws a
live-updating sorted list: the cursor has to hold a *node*, not a row index.
Districts re-sort by size every time the background scan moves, so an index
silently slides onto a different directory while you watch.

The constraint that decides how dense the city gets is the minimum plot size
below which a district stops subdividing — and it has to be derived from the
terminal, not fixed in world units. Held constant, shrinking the font bought
no extra detail at all (the block count was pinned around 118 whatever the
size) while a small terminal turned to mud. It now scales with the pixel
width: ~165 blocks at 80 columns, ~275 at 398. Depth is capped at
`--levels 3`; 4 renders ~400 blocks but sits right on the frame budget at
large sizes and starves the scanner thread of the GIL.

Painter's ordering had the same disease as the backface test, one level up.
Blocks were sorted by the depth of their footprint **centre, minus half their
height**. Height must not enter the key at all: every block stands on the same
ground plane, so whichever *footprint* is nearer occludes the other wherever
they overlap, because a ray descending from the camera always enters the nearer
footprint first. The height term dragged tall blocks toward the camera, so a
tall tower far away outsorted a short block in front of it and painted straight
over it — then snapped back when the two centres crossed. Using the centre was
wrong too: a large footprint whose near edge is closer than its middle lost to
a small one it overlapped. The key is now the nearest footprint corner and
nothing else. Measured on a real tree across 360 degrees, the old key ordered
up to **65 screen-overlapping pairs** wrongly at the worst azimuth, swinging
between 8 and 65 as the camera turned — which is exactly why it read as a few
bad frames followed by a snap.

Backface selection was the subtlest one. Which two walls of a block face the
camera was decided once per frame from the azimuth alone — correct for an
*orthographic* camera, but the projection is perspective, and across a
100-unit plot at distance 210 the view direction swings about 13 degrees. So
for roughly 13 degrees either side of each quarter-turn, blocks out at the
edges were handed their FAR wall, and its window lights sat on the near
silhouette until the global test caught up: lights visibly shining through the
front of a building, then snapping. Measured on a real tree, up to **83% of
blocks** were mis-faced at the worst azimuth. The test is now per block
against the camera's actual world position, which is exact under perspective.
The same position gives the roof test — at a low tilt the camera can sit below
a tall block's roofline, where its roof must not be drawn at all.

Three more of the same shape. `_sub` never recursed — it always emitted leaf
blocks — so every city bottomed out at two levels and `--levels` above 2 was
accepted and silently did nothing. Rotation was `az += k` per *frame*, so `--fps`
silently changed the orbit rate and the spin stuttered whenever the scan got
busy — it has to be per second, against a measured delta. And district labels
were centred on the projected block and drawn unclamped, so the ones near the
edges ran off screen or slid under the HUD panel; they now clamp into the
viewport, skip anything that collides with an already-placed label, and carry
a dark backing so they don't sit directly on a lit roofline. The HUD panel's
telemetry block was also drawn at `rows-3 .. rows-1`, putting its last line on
the same row as the status bar.

The painter's order took three attempts, and the lesson is that **it has no
scalar answer.** Sorting blocks by a number per block — centre depth, then
nearest corner, then nearest point to the camera — is trying to make depth a
property of a block, and it isn't one: for two neighbouring footprints the
near/far answer depends on which side of the edge *between* them the camera
stands. Every scalar key is therefore wrong somewhere on the orbit, and the
nearest-corner key was worst at the cardinal azimuths, where the camera's
ground position falls inside the plot and the "nearest" corner stops being
nearest. Ray-casting the blocks as real boxes and comparing per pixel against
what the painter left on top measured it: **up to 56 wrong pixels a frame**,
which is exactly the "renders through, then snaps" artifact.

The fix came from the layout, not the renderer. squarify slices a strip off
the remaining rectangle each pass, so the plot is a **guillotine partition** —
every block lies wholly on one side of every cut. That is a BSP, and drawing
the far side of each cut first is exact by construction, for any camera, at
any tilt. It is also *cheaper* than the sort it replaced (0.032 ms vs 0.042 ms
per frame at 261 blocks) because the tree depends only on the layout, so it is
built once per relayout and the camera enters only as one comparison per cut.
Verified 0 wrong pixels over 72 camera positions at 19, 261 and 371 blocks.

The general lesson: when a heuristic keeps being *nearly* right, check whether
the data structure already knows the exact answer. Two of these three attempts
were spent inventing better guesses at something the treemap had determined
all along.

Plan view taught the general form of all of these: **a mode is a set of
variables, so only one piece of code may leave it.** Plan view is five
things at once — `plan`, a held heading, a pulled-back camera, a forced
elevation and a forced pause. The tilt keys cleared `plan` and moved the
elevation, but left the other three, dropping the camera into a state that
was neither a plan nor an orbit and that no key could name its way out of.
The fix is not to make tilt restore the rest, it is to make tilt inert while
in plan view, so `t` stays the single entry and the single exit.

---

## Not built yet

### 1. Falling-code rain, fed from something real
Not another Matrix clone — drive the columns from an actual source: `dmesg`,
a log tail, `git log`, disk I/O, filesystem events. Glyphs decay down a
brightness ramp; occasionally a column "locks" and holds a legible word from
the source before dissolving.

*Data:* `journalctl -f`, `/proc/diskstats`, inotify.
*Effort:* small. Highest ambiance-per-line-of-code on this list.

### 2. Live system telemetry dashboard
Per-core CPU, memory, disk I/O, network, load, thermals — all braille-plotted
(`⣿⣷⣤`) for 2×4 sub-cell resolution. `htop` as designed for a submarine.
Genuinely useful *and* ambient, which is a rare combination.

*Data:* `/proc/stat`, `/proc/meminfo`, `/proc/diskstats`, `/sys/class/hwmon`.
*Effort:* medium. The braille plotting is reusable everywhere else.

### 3. Radar / sonar sweep
Rotating sweep line with phosphor persistence, contacts blooming and fading
behind it. Feed it real blips: new processes, inbound connections, filesystem
events. The decay glow is the whole appeal, and it's the natural companion
piece to the globe.

*Data:* `/proc` process table, `ss`, inotify.
*Effort:* small–medium. Shares the palette and framebuffer code.

### 4. Cyberdeck boot sequence / idle console
Scrolling diagnostics, memory checks, `DECRYPTING…` progress bars, glitch
bursts, hex dumps of real files. Pure theatre — the only item here with no
truth claim — but the most straightforwardly "hacker" thing on the list.

*Effort:* small. Worth keeping honestly labelled as decorative.

### 5. Rotating 3D wireframe
Reuse the globe's projection engine for a hypercube, molecule, or terrain
mesh. Low novelty now that the sphere and the cityscape both exist, but
nearly free.

*Effort:* tiny.

### 6. The other disk visualisations
Considered alongside dscape and passed over, worth keeping:
**disk planet** — spherical treemap on globe.py's own engine, prettiest of the
three but spherical area is hard to compare across latitudes;
**the platter** — tilted rotating disc, rings = depth, sectors = size, with a
head arm that seeks to the selection, the most thematically literal option;
**debris field** — big/old files as tumbling asteroids, radius = access age,
good at finding junk but not at explaining a disk.

---

## Follow-ups on what exists

### netmap
- **Session accumulation** — endpoints fade into a persistent "seen this
  session" layer instead of vanishing after ~45s, so the map fills in over
  hours. *(Considered and declined once; noted in case it looks better later.)*
- **Hold-until-dismissed** — the selection freeze currently releases 3s after
  the last keypress; "frozen until ESC" may be the better model.
- **ASN / org lookup** — would explain *who* an endpoint belongs to without
  depending on reverse DNS, which many hosts don't have. Needs a bundled
  table; the ASN database is large, so it's a real size tradeoff.
- **Bandwidth history per endpoint** — sparkline per row rather than a single
  instantaneous number.

### dscape
- **Deletion** — currently marks only, and prints paths on exit so you pipe
  them somewhere yourself. Anything that removes files from inside an ambient
  animation deserves a confirmation flow that doesn't exist yet.
- **Scan cache** — a full home directory is ~2s, but a multi-TB volume is
  minutes; a cache in `~/.cache/` keyed on path+mtime would make restarts free.
- **Mouse picking** — click a block to select it. Needs SGR mouse reporting
  and a screen-space hit test, which the painter's-algorithm order already
  gives us almost for free.
- **Diff mode** — two scans, blocks colored by what grew. The obvious way to
  answer "what ate 40 GB since last week".
- **Age as a channel** — mtime is already stat'd and thrown away. Roof color
  by last-modified would separate live projects from dead ones at a glance.
- ~~**A real depth buffer**~~ — *no longer wanted.* This entry used to claim the
  nearest-corner order was correct for treemaps and only broke on pathological
  layouts. That was wrong: ray-casting the blocks and comparing per pixel found
  up to 56 wrong pixels a frame on an ordinary home directory. The order is now
  a BSP over squarify's guillotine cuts, which is exact for any camera, so a
  per-pixel depth test would buy nothing and cost the span fill. The one real
  constraint left is that the BSP assumes a guillotine partition — if the layout
  ever stops being one, `build_bsp` falls back to an unsorted leaf rather than
  silently mis-ordering, and that leaf is where to look.

### globe
- **Sun-synced lighting** — terminator matched to the true UTC sun position.
  *(Since implemented in netmap; globe still uses a fixed view-space sun.)*
- Satellite ground tracks, cursor targeting reticle, auto-cycling palettes.
- Live feeds if the no-network rule is ever relaxed: ISS position, seismic
  events, flight density, aurora.

---

## A note on where the good material is

A desktop's outbound traffic is inherently local — CDNs exist precisely so the
edge you hit is nearby, which is why netmap clusters around home. Anything
pointed at a **public-facing server** is far livelier: inbound connections from
everywhere, plus the constant background of scanners probing SSH and HTTP.
That applies to the radar sweep as much as to netmap.

## Shared pieces worth factoring out

All three programs now duplicate: ANSI/SGR helpers with colour caching, the
framebuffer and run-length emitter, the raw-mode non-blocking keyboard, the
palette structure, and the layer/z-buffer idea. The third program happened and
the code was still copied rather than factored out, deliberately: single-file
portability is most of why these are pleasant to `scp` around, and dscape
diverged anyway — it needed a half-block pixel buffer with background colours
and a two-colour run-length emitter, where globe and netmap only ever set a
foreground. A shared module would have had to grow both, for three callers.

dscape's own performance note, since it generalises: spans are written with
list **slice assignment** (`row[x0:x1] = [c] * n`), which is the only reason a
filled-polygon rasteriser runs at 100+ fps on a 300×80 terminal in pure
Python. Anything that has to touch every pixel individually — the window
lights — is budgeted per frame and sized from *screen* extent, never world
extent, or distant geometry silently asks for a light per pixel.

Contrast tuning matters more than it sounds: colours were measured against an
actual screenshot of the target terminal, because a translucent background over
a wallpaper makes anything below ~3:1 contrast effectively invisible.

The translucent terminal bites harder than that, though, and dscape found the
sharp edge of it. Emitting SGR 49 — "default background" — is not the same as
emitting a dark colour: on a translucent terminal it is *transparent*. Every
string drawn without an explicit background punched a wallpaper-coloured hole
exactly its own width through the panel behind it, so the HUD rendered as
ragged coloured ribbons in the shape of its own text. It is invisible on an
opaque terminal and obvious on a translucent one. The fix is that overlay text
inherits whatever background the cell already holds, and anything drawn over
the 3D scene carries its own backing. **Never let a filled region be overdrawn
by text that resets the background.**
