# hackertime — idea list

Terminal ambiance with a hacker bent. House rules that have worked so far:
pure-Python stdlib, no pip installs, no runtime network calls, data baked in at
build time where possible, and **real data wherever we can get it** — the things
that read best are the ones that are actually true.

Status as of 2026-08-02.

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
in plan view, so `t` stays the single entry and the single exit. Pause is inert
there for the same reason: unpausing added the orbit spin on top of the ease
holding the plan's heading square, the two fought, and from overhead that read
as the plan drifting off true. Leaving plan view always resumes spinning — the
pause belongs to the mode, not to the orbit you left, and carrying it back out
just looked like the city had frozen.

The auto-fit had a related "nearly right" bug. It framed the city by projecting
the eight corners of the plot, which means the frame tracked the silhouette of
a **rotating square** — 41% wider corner-on than edge-on. So the city pulled
away as a corner came round and crept back in on the flats: measured, a 15%
breathing at low tilt rising to **42% at 80 degrees**, plus a centre that
drifted as the square swung. The low-pass filter on the fit had been hiding the
speed of it, not the fact of it.

The fix is to fit the **cylinder circumscribing the plot** instead of the plot
itself. A circle centred on the plot is rotationally symmetric, so substituting
th = phi - az removes the azimuth from the projection algebra entirely and the
framing is constant by construction, not merely smoothed. Measured 0.0000%
variation over a full turn at four elevations. A constant fit has to be the
safe one, so the framing now sits where the corner-on framing used to — the
loosest point of the old swing — and some of the 0.94 margin went back to the
city to compensate, since there is no longer a swing to leave room for.

Worth noting what the residual measurement showed: a live orbit still moves the
fit by ~4% *while the scan is running*, because the tallest building keeps
changing. That one is real and should stay smoothed rather than removed.

A smaller note on top of that: a key that is deliberately inert should be
*silently* inert. Flashing "t FOR ORBIT" to explain why the arrow key did
nothing was worse than doing nothing quietly — nobody needs to be told off by
their own skyline.

**Street level (`W`) — and what the earlier work paid for.**

A first-person walk mode turned out to be mostly *already built*, and that is
the interesting part. `bsp_order` is exact for any camera position, including
one standing inside the plot, and the backface and roof tests were already
per-block against the camera's true world position because perspective forced
them to be. Both carried over untouched, and the ray-cast harness confirmed it:
**0 pixel disagreements** from inside the city, the same bar the BSP cleared
from orbit. Work done properly for one reason paid out for a different one.

Four things genuinely had to be built, and three of them were only found by
measuring.

*The clamp was hiding a missing clip.* `if zv < 1.0: zv = 1.0` is safe only
because the orbit camera is 210 units from a 100-unit plot. It is two bugs at
street level: a wall straddling the eye plane folds inside out, and a wall you
walk toward stops growing. The fix is Sutherland-Hodgman against `zv >= ZNEAR`,
run on the camera-space triples *before* the divide — all three components are
linear in world position there, so the crossing point is exact. `Raster.fill`
already handled the resulting 3-to-5-gons, being a general convex fill, which is
also why true pitch cost nothing.

*Clipping is necessary but not sufficient.* A clipped vertex projects to ~1e5
px. `fill` clamps its spans, but `line` steps one pixel at a time and merely
*tests* each for being on screen: a single clipped grid line measured **91 ms**.
Needed a screen-space segment clip as well (2075x faster on that case). And
`fill` derives its gradient from the polygon's own extent, so a clipped wall put
the whole visible surface into one slice of the ramp and rendered flat — hence
the `yref` parameter, defaulted so nothing that does not clip moves a pixel.

*Two culls, both wrong the first time, both caught by rasterising.* Painter's
has no occlusion culling, so from inside the city everything is drawn at close
range unless thrown away first. The first attempt tested the footprint's four
corners against a 2D wedge. That is only right at zero pitch: looking up, a tall
block's top has a larger `zv` than its base and swings toward the centre of the
screen, so a block whose *footprint* is outside can be plainly visible — 64
wrongly dropped over 408 sample views. The second was the distance cull reading
the footprint *centre*, so a district-sized block with its near edge in your
face got dropped. Both fixed by testing the whole box: `xr`, `zv` and the plane
functions are linear, so the extreme over an axis-aligned box is its centre plus
the extents weighted by |coefficient| — exact, and cheaper than projecting eight
corners. Result: 0 visible blocks culled, and street level runs at **1.1-1.4 ms
a frame against orbit's 6.1-6.3** — cheaper than the view it replaced.

*The measurement that answered the wrong question.* The first street survey
measured the gap between neighbouring blocks and found 75 of 238 under 0.4
units, which said "widen the streets". A second measurement — occupancy grid,
distance transform, flood fill — said the opposite: the shipped layout is
already **one connected component** for a 0.3-radius walker, 24% of the plot
traversable, all 39 districts reachable. Connectivity is the wrong question too.
The one that matters is dynamic, and only a fuzz over half a million substeps
asked it: a walker wedged in a gap narrower than twice its radius has **no legal
position at all** — pushing it off one wall pushes it into the other, for ever.
The shipped layout leaves it up to 0.13 units inside a building and no number of
resolution passes fixes it (16 passes still left 0.047). Shrinking the walker
does not work either; at radius 0.14 it is still 0.04 inside, because the layout
emits blocks as thin as 0.04 whatever you do. Street level therefore relays out
at `STREET 0.50, min_plot 4.0` — 124 blocks instead of 261, and **zero
penetration over 580k substeps across two trees**. *Reachable is not the same as
walkable, and neither is visible in a static measurement.*

Two pre-existing bugs surfaced on the way and were fixed on their own merits.
`Keyboard._parse` consumed a fixed three characters for a CSI sequence, so every
parameterised escape spilled its parameters into the stream as ordinary keys:
shift+Up arrived as `ESC ; 2 A` and that bare `2` switched the palette, a mouse
click emitted `2`, `3` and `4`, and a bracketed paste emitted `0`, which reset
the view. Harmless while the arrows were a secondary control; not once they
steer. An unrecognised CSI is now swallowed rather than reported as `ESC`, since
`ESC` ascends the tree and no terminal sends parameters to mean "the user
pressed Escape". Separately, the roof outline was stroked on all four edges
regardless of `roof_vis`, so from below the two *far* rooflines were drawn
through solid wall — 31 pixels a frame at `--tilt 6`, and unmissable from the
street where no roof is ever visible.

The mode law from plan view held up as written: walk mode is `walk`, a position,
a pitch, a forced pause, a fixed focal length and its own layout, `W` is the
single entry and single exit, and `SPACE`, `t`, `j`/`k` are silently inert
inside it. It also *rebinds* `w` and `s` (windows and starfield) to movement,
which the law permits precisely because one piece of code puts the whole set
back — verified by driving it through a pty and comparing the variable set
before entry and after exit.

One last note on method. The golden-frame gate — orbit and plan view must be
byte-identical, 91 frames each — was worth more than any other test here, and it
only worked once the harness itself was made deterministic. Baseline differed
from *itself* until `PYTHONHASHSEED` was pinned, because `Node.seed` is
`hash(name) & 0xffff` and Python randomises string hashing per process. A
regression gate that has not been shown to pass against itself is measuring
nothing. It is also why the free-camera projection was added *beside* the orbit
one rather than replacing it: the general form is an algebraic superset, but
subtracting the eye first reassociates the sums, and an ULP is enough to flip an
`int(ceil(...))` and move a pixel.

Two bugs the user found in the first hour of actually walking around, both of
which every harness above was blind to for the same reason: they are *sign and
naming* errors, and the harnesses all compared the renderer against itself.

**The turn keys were mirrored, and so was the compass.** `xr = dx·ca + dy·sa`
rotates the world by `-az`, so a thing on your screen-right has the *smaller*
bearing: `az` counts anticlockwise. LEFT must therefore *add*. The same sign
flipped the compass strip — it was placing labels at `bearing - az`, so the mark
for a tower on your right appeared on your left. Nothing caught it because the
ray-cast harness derived the view direction from the same `az` and agreed with
itself perfectly; the id-buffer compared the painter against a ray cast, not
against the word "left". The compass labels were separately in a left-handed
order (E was world `-x`), so *both* halves had to be fixed together, and the
check that finally settled it was the only one that couples the two independent
paths: over 48000 samples, does the sign of a landmark's compass offset match the
sign of its screen x? A self-consistent renderer can be consistently backwards.

**A directory of nothing but files claimed to be a leaf.** `node.children` holds
subdirectories only; loose bytes get a synthetic `(files here)` district that
`layout()` manufactures on the fly. So ENTER's `if n.children:` test disagreed
with `layout()` about whether there was a city to draw, and a folder of 47 GB of
model weights — the single most interesting thing in that tree — refused to open.
The fix (`enterable()`) mirrors `layout()`'s own `kids` test deliberately, so the
two cannot drift apart again. The general lesson: when two places decide "is
there anything here", they are one predicate, and writing it twice guarantees
they will eventually disagree. Worth auditing the codebase for the other copies.

**The ground grid is three states, not two.** `g` used to toggle it; it now
cycles solid → x-ray → off. The measurement that justified it: a treemap fills
the *entire* plot, so essentially every grid line is under a building. On a fixed
frame the solid pass leaves 265 grid pixels of 2069 in orbit and 112 of 1277 at
street level — **87–92% of the ground plane is hidden**, which is why the grid
had always read as a few strokes near the plot edge rather than as a floor. Drawn
after the blocks it reads as a proper ground plane, and at eye level it is a
perspective grid running to the vanishing point, which is the only thing down
there that says where on the plot you are.

Two things that measurement got wrong first, both worth remembering:

- **Comparing two live captures measures the animation, not the change.** The
  first diff of solid against x-ray lit up the whole city, because between the
  two captures the stars twinkled, the window lights flickered and the survey
  beam swept. Anything compared across separate runs has to go through the
  deterministic-clock harness the golden gate already uses; a screenshot diff of
  an animated scene is noise with a signal somewhere in it.
- **`ras.px` is a list of rows, so `zip` over it compares rows.** The first pixel
  counts were 3–57 and looked plausible enough to quote. They were counts of
  differing *rows*. A number that is not absurd is not thereby correct — the
  check is whether it could be that number for the wrong reason.

And a design point: the x-ray pass is drawn *brighter* than the solid one
(`2.5` against `0.85`), not dimmer. The instinct was that an overlay should
recede, but this one has to cross lit building faces, and at the solid pass's
weight it simply vanished against them. It still goes before the reticle, which
must win. No palette clips a channel at 2.5.

---

### mechmodel.py — turntable rig for a battlemech

The fourth program, and the first whose subject is not real data: a 65-tonne
reverse-jointed walker modelled from a reference screenshot, orbiting on a
turntable. It reuses dscape's raster, emitter, keyboard and orbit camera
verbatim and replaces everything underneath.

**The geometry layer is different in kind, and that is the whole point.**
dscape gets its painter's order *exactly*, for free, because its blocks sit on
a guillotine treemap and the plan's own cuts are a BSP. Nothing in a mech is
axis-aligned and there is no plan, so facets carry true normals and sort by
mean camera-space depth. That sort is wrong wherever two hulls interpenetrate
— which here is only ever inside a joint, a bearing sunk into a limb or a ram
buried in a calf, where the seam is hidden by the very parts that create it.
Worth knowing that the cheap answer is fine when you can arrange for its
failure mode to be invisible.

**One primitive, not twenty.** Everything — armour plate, hydraulic ram,
cockpit blister, missile rack, splayed toe — is a *loft*: a stack of
cross-section rings joined ring to ring by quads and closed with n-gon caps. A
box is two rectangular rings; a ram is two circular ones; the torso pod is nine
ellipse rings on an egg profile. `Raster.fill` already takes any convex polygon,
so the caps cost nothing. Detail that would be texture in a real engine is
*geometry* instead: `grid_face` subdivides a planar quad into a coloured cell
grid, and that one function draws the missile bores, the hazard chevrons and
the heat-sink louvres.

**Normals are oriented outward from each part's own centroid at build time.**
Every primitive here is star-shaped about its centre, so this is exact, and it
means the loft generators never have to agree on a winding convention. That is
a class of bug that costs an afternoon and shows up as one facet of one limb
being inside-out from one angle only.

**The mass column is measured, not typed.** Each part's volume is the
divergence theorem taken over its own hull — `3V = Σ (p·n)·area` — times the
density of its material. The one chosen number is the density itself,
calibrated once so the machine weighs what its class is rated for. Same
instinct as everywhere else in this repo: if a panel is going to show a number,
make the number true.

Lessons that generalise:

- **A photograph's lighting is a specification.** The first cut used dscape's
  night palette and one Lambert term, and the model read as a dark green
  cut-out. Three changes fixed it together and none of them alone would have:
  a daylight palette, a dim fill light roughly opposite the key so no flank
  goes flat black, and a *hemisphere ambient* — upward faces tinted toward the
  sky colour, downward faces toward a ground-bounce colour. The hemisphere term
  is what tells a horizontal surface from a vertical one on the side the sun
  never reaches, and at 0.16 it costs one `lerp` per facet.

- **Detail finer than a pixel averages to mud.** The cockpit laminate was five
  bands over 0.84 world units, which at this resolution is 1.8 pixels a band:
  it rendered as a grey smudge and read as nothing. Two panes and one mullion
  survive the downsample. Decide detail density in *screen* space, the same
  lesson the window-light budget already taught.

- **Paint the facet, don't float the decal.** A unit flash over a curved hull
  has to guess an offset radius and z-fights when it guesses wrong. Painting a
  quad the loft already generated is on the surface by construction.

- **Never write to `sys.stdout` from a signal handler.** This one was found by
  soak and would never have been found by eye. The frame emitter holds the
  `BufferedWriter`'s lock for most of every frame — one 20 KB write into a pty
  — and re-entering it from a handler raises `RuntimeError`, which the
  defensive `except Exception: pass` wrapped around the teardown then swallows.
  The process exits 0 having restored *nothing*: raw mode still set, cursor
  still hidden. It failed **60 teardowns out of 60** and looked completely
  clean from the outside. dscape already had this right — its handler only
  appends to a `quitting` list and the frame loop tears down at the top of the
  next iteration, where nothing is half-written. That pattern is now the house
  rule, not an accident of how dscape happened to be written.

- **A pty harness must keep draining through teardown.** Stop reading and the
  child blocks on write, never gets round to processing the quit key, and
  `waitpid` hangs forever. Two harnesses hit this before it was written down.

- **Also: `--frames N` from the start.** Every measurement here — the size
  sweep, the timing runs, the PNG inspections — goes through it, and adding it
  early cost nothing.

Verified: 0 failures over 56 terminal-size × flag combinations and all six
palettes; 300 random keypresses including every unbound key and parameterised
CSI sequences, no traceback, clean exit; 60/60 signal teardowns restoring the
terminal; 9.4 ms/frame at 80×24 rising to 20.3 ms at 240×70, so 30 fps holds
with room to spare.

**Then it was pointed at a real mesh, and that is the version that looks good.**
The hand-built mech was a decent exercise and a mediocre model; a 243k-triangle
STL of the actual machine is not close. The interesting work is entirely in
getting from 243,000 triangles to something a terminal can draw at frame rate.

**The budget is screen space, not taste.** At half-block resolution the model
covers roughly 150×400 pixels. A few thousand facets is already one facet per
handful of pixels, so the target is not a compromise between fidelity and
speed — past a few thousand there is nothing left to see. Measured: 6,132
facets renders in 30 ms at 170×48.

**Vertex clustering, not quadric edge collapse.** Snap every corner to a grid
cell, keep one representative, drop triangles whose corners collapse together.
O(n) in one pass, where the collapse is a priority queue over 364,000 edges and
minutes of Python. Two details carry the quality:

- the representative is the **area-weighted mean** of the corners that landed in
  the cell, not the cell centre — the centre quantises every surface onto a
  lattice and the model comes out stair-stepped, the mean leaves flat panels
  flat;
- every new triangle is **re-oriented against the original facet normal**,
  which is the only reason to keep the STL's stored normals at all. Clustering
  can reverse a winding, and on a backface-culled render a reversed facet is a
  hole you see straight through the model.

Cost, against the source: under 1% of enclosed volume and under 2% of surface
area at the middle level. Both reported in the panel, both measured.

**Search the *right* curve.** Hitting a facet budget started as a bisection over
grid resolution: nine full clusterings of a quarter-million triangles per level.
Face count over a surface grows as the *square* of the grid resolution, so one
probe predicts the answer outright — `n' = n·sqrt(target/faces)` converges in
two or three. 16.7 s of build became 7.1 s, and most of the rest was a second
mistake: the occupancy grid, which depends only on the source, was being rebuilt
identically once per level.

**Real ambient occlusion, and it is what makes a monochrome mesh readable.**
Under three lights a single-material mesh is a grey statue — every depth cue has
to come from the normal, and a normal knows nothing about the arm hanging in
front of the chest. So: burn the dense mesh into a voxel occupancy grid, flood
the *outside*, call everything unreached solid, then fire a fixed 13-direction
hemisphere per facet and count what lands inside. It sees other parts, not just
local curvature. Folded into the same per-face brightness multiplier the
weathering already used, so it costs the shader exactly nothing at frame time.

Two lessons came out of it, both about being wrong quietly:

- **Size a sampling lattice from the longest edge, never from the area.** The
  first voxelisation sampled each triangle proportional to its area, and this
  mesh — like most printable STLs — is full of *slivers*: triangles whose area
  is near zero but whose edges run across a dozen voxels. Those got three
  samples, left their span unmarked, and the outside flood walked straight into
  the interior. Nothing raised, nothing looked wrong: the grid still had a
  model-shaped shell in it, `solid` had just silently come to mean `shell`.
- **Which is why it now cross-checks itself.** The mesh's own enclosed volume
  says how many cells should be solid. A conservative voxelisation overshoots
  that by about half a cell of thickness over the whole surface and *never*
  undershoots — so coming in low is proof of a leak. 50 interior cells where
  the volume demanded 41,000. That check is now permanent and its result is on
  the panel.

**Normalise occlusion against the mesh, not against theory.** Theory says an
unoccluded facet sees the whole hemisphere. A facet on a real machine is
surrounded by panel gaps, bolt heads and its own neighbours, so the raw mean
here is 0.35 and shading straight off it drags the entire model into shadow.
The 85th percentile is what this surface actually achieves with nothing in the
way; that is the number worth calling "open".

**The right generalisation of the panel.** The STL is a single watertight shell
— every edge used exactly twice, one vertex-connected component — so there are
no parts to list, select or explode. Rather than invent a decomposition, the
panel became a *mesh report*: welded vertex count, edge manifoldness, decimation
error against the source, and the displacement and mass the machine would have
if it were really built 12 m tall (142 m³, 44 t at the calibrated plate
density). All measured. `j`, `k`, `e` and `i` go silently inert, per the mode
law, because there is genuinely nothing for them to act on.

**Cache it beside the source.** Seven seconds cold, 0.19 s warm — a
length-prefixed JSON report plus `array` blobs, invalidated on source size and
mtime, byte-order stamped, written through a temp file, and any failure to read
one just means rebuild. `.mmesh`, gitignored.

And once more, the key soak earned its keep: cycling detail selected a `Part`
that had never been given its explode vector, and the frame loop crashed on the
first press. Nothing about looking at the render would have found it.

Verified after the mesh work: 110 size × flag combinations and all six palettes,
0 failures; 300 random keypresses, no traceback, clean exit; 60/60 signal
teardowns; 24.4 ms/frame at 80×24 to 38.6 ms at 240×70 on the middle detail
level, with `d` there to buy it back.

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
