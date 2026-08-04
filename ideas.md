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

#### Making it fast — and what measuring first was worth

Asked to find more speed, I predicted the emitter would dominate at large
terminal sizes, because it scales with cell count and the frame cost had grown
with the terminal. **Wrong.** Instrumenting the frame loop at its own stage
boundaries: the emitter is 3–15%, and `shade` is 57–59% at *every* size, with
`gather` another 19–28%. Splitting `shade` in two explained why the size
independence: the lighting arithmetic is ~8.5 ms/frame regardless of terminal
size, because it is per-facet and ~3100 facets survive the backface cull no
matter how big the window is.

The number that reframed everything was **0.93 scanlines and 2.3 pixels per
facet** at 80×24. The raster's whole design — spans written by list slice
assignment — is built to make long runs cheap, and at this facet size there are
no long runs. The per-scanline *fixed* cost is the entire bill: a fresh list, a
loop over every edge, two appends, a length test, sometimes a sort. Which
means the biggest single win was something that looks like a rounding error:
**every facet was being filled with a top-to-bottom gradient**, costing a
`lerp` and a `quant` on every scanline, to shade a facet one pixel tall.

Four changes, all of them things measurement pointed at rather than things that
looked slow:

- **A triangle-only rasteriser.** Sort three vertices once, walk the long edge
  against one short edge, no allocation per scanline.
- **The gradient only where it can be seen** (`GRAD_MIN_H`, 5 px). Not global:
  the built-in model's facets are big loft quads and the gradient is what makes
  a cylindrical limb read as round — dropping it there flattens the legs
  visibly. The STL's facets are a pixel tall and it shows nothing. Same code,
  opposite answers, so the test has to be per facet.
- **The shader inlined**, `shade`/`lerp`/`quant` unrolled to scalar arithmetic,
  `ndl**9` as three squarings instead of a `pow`.
- **A world-normal cache.** The turntable spins the *camera*, not the mech, so
  on a still pose every normal equals last frame's. Keyed on the frame matrix
  itself, so a pose that really moves fails the comparison and recomputes.

Result on the STL: **20.8 → 13.0 ms** at 80×24 and 38.5 → 25.3 at 240×70. The
built-in model gains only ~10%, because its large facets keep the gradient —
worth stating plainly rather than quoting the good number twice.

**The lesson that cost the most time: the renderer was not reproducible.**
Per-facet weathering seeded from `random.Random(hash(name) & 0xffff)` — and
`hash()` of a *str* is salted per process, so every launch weathered the mesh
differently. Invisible (±5% brightness jitter), and harmless until a pixel diff
was used to check an optimisation: variants disagreed with the reference on 25%
of pixels, and the differences did not correlate with the changes. A **control
run of a build against itself came back 92.969% identical** — the harness was
measuring noise. Two causes, both found only because of that control: the
salted hash, and the spin integrating real wall-clock `dt`, so frame 40 lands
at a different azimuth every run. Fixed with `zlib.crc32` and a pinned `dt`.
*Always run the null comparison.* A diff harness that cannot show 100% on
identical inputs cannot show anything.

With that fixed the claims are provable rather than plausible: forcing the
gradient on, the optimised renderer is **100% pixel-identical** to the original
on both models at both sizes — that is the rasteriser, the inlined projection,
the normal cache and the inlined shader, all proved equivalent rather than
argued to be. The exact-inlined shader costs 0.7 ms over a loose float version
that was 95% identical; worth paying to be able to say *identical*. And the
normal cache — the one change justified by an argument about invalidation
rather than by algebra — was driven under idle sway and mid-explode, where
every limb frame changes every frame, and matched at every sampled frame.

**On `--lighting`, which was asked for as "turn lighting off for speed".**
Measuring it honestly meant reporting that the obvious version is a bad deal:
fully unlit is the fastest thing the renderer can draw, but on a
single-material mesh every facet takes the same colour and the mech becomes a
**featureless green silhouette** — and it only buys ~1 ms over keeping the key
light. So `L` cycles three states: `full`, `key` (key light alone — still
solid-looking, ~20% off the shading stage), and `flat` (kept, documented as a
speed floor rather than a view). `--no-shadow` already existed and saves ~0.8
ms, about 3%; the cast shadow was never the problem.

Still on the table, unmeasured: the emitter is 15% at 240×70 and untouched.

#### Segmenting the mesh into the machine's own limbs

The mesh is the Timber Wolf, Inner Sphere codename Mad Cat, and **the fiction is
not mine to invent — [Sarna](https://www.sarna.net/wiki/Timber_Wolf_(Mad_Cat)) is
the authority.** That is a working rule, not a courtesy: an earlier draft of this
program stated that the ER large lasers sit in the arms and the LRM-20s in the
side torsos. Sarna lists the Prime's nine weapons and assigns **none** of them a
body location. The placement was the kind of thing everyone knows and nobody
sourced. The `CANON` table now carries only sourced fields and deliberately has
no weapon locations in it.

The same rule inverted the mass model, for the better. Mass used to be 65 t of
hand-calibrated guesswork times a guessed 0.31 t/m³ density. Now **Sarna owns
the tonnage (75 t) and the mesh owns the geometry**, and the density is the
*derived* figure: 75 t ÷ 138.6 m³ = 0.541 t/m³. Each side supplies only what it
actually knows.

BattleTech also hands over the target set — HD, CT, LT, RT, LA, RA, LL, RL — so
nothing had to be invented there either. Two approaches, and the first one
failed:

- **Slice topology (a Reeb graph of the height function).** Connected components
  per horizontal slice, linked between slices. Found the legs and the LRM pods
  cleanly and **failed on the arms**: 2.9% of the hull against 0.9%, with 65% of
  the machine dumped in the torso. Above the hips an arm and the torso side land
  in the *same* 2D component wherever they overlap in plan view.
- **Erosion + watershed.** A mech's joints are its narrow places, so erosion
  breaks them first and the limbs fall off on their own. Erode to a core, take 3D
  connected components as seeds, then flood all seeds simultaneously back over
  the solid — the boundary lands in the joint where it belongs.

Three things had to be measured rather than assumed:

**The mirror plane.** The obvious shortcut — lateral axis = whichever way the
legs are furthest apart — is a *coin flip* here: the Mad Cat is modelled
mid-stride and its legs are separated diagonally, 35.3 grid units one way against
38.1 the other. Searching for the plane that best maps the solid onto itself
gives 21°, scoring 0.686 against a worst case of 0.327 — and correctly not 1.0,
because the stride is real. That also yields the facing direction, which the
aspect-angle readout will want.

**Erosion depth is not a constant.** At 96³ a depth of 6 parts the limbs; at the
default 80³ the same depth erases them and leaves two lumps. So it is swept, and
**bilateral symmetry decides**: the right depth is the deepest that still finds
two outboard components on *each* side of the mirror plane. Nothing in the search
knows the machine is symmetric, so when the answer comes out symmetric that is
evidence, not assumption.

**Pick per side, never globally.** "The two largest remaining components" chose
two pieces off the same shoulder and left the other arm unlabelled.

Then a self-inflicted one worth recording. Per-section volume was first computed
as signed tetrahedron fans, on the argument that the divergence theorem would
absorb the open boundary. **It does not** — the fan integral is volume only for a
*closed* surface, and for an open patch the answer depends on where the rim sits
relative to the origin. The symptom was the arms coming out 3.1 m³ against 5.8 m³
while their facet counts agreed to within 4%. Counting labelled voxels is a true
partition and has no such problem: arms 8.7 / 8.8 m³, legs 16.9 / 16.9, torso
87.3, summing to the measured 138.6.

Also fixed: `built_volume` moved with the detail level (142.4 m³ at low against
138.8 at high) because the normalising scale was taken from the *decimated*
bounding box, which decimation pulls inward. The source owns the height; a level
of detail does not get a vote on how big the machine is.

`j`/`k` are alive again on a loaded mesh — they cycle the five sections and the
selection highlights on the model, which is the only check that the labels landed
on the right *geometry* rather than merely plausible percentages. `e` (explode)
and `i` (idle) are still inert on a mesh.

#### The targeting HUD: sensor channels, lock frame, cutaway

Four sensor channels on `v`, each asking a different question of the same mesh
and each answering it from something already measured:

- **OPTICAL** — the lit hull.
- **THERMAL** — false colour from ambient occlusion. Occlusion measures how
  enclosed a facet is, and an enclosed facet is one heat cannot leave, so deep
  joints read hot and open plate reads cold. A real property of the geometry,
  not a gradient painted over a picture.
- **LIDAR / XRAY** — contours on a dark instrument field; XRAY additionally
  keeps the far side of the hull by being the one channel that skips the
  backface test.

Two things that had to be *looked at* before they worked, neither of which any
timing or unit test would have caught:

**Outlining every facet shows nothing.** The first wireframe drew all ~6,000
triangle edges and produced an illegible scribble that filled the silhouette.
The fix is to draw only facets grazing the view — `|n·view| < 0.42` — which
traces contours instead of a mesh. That is the difference between a wireframe
and a scan return.

**A sensor channel must not render sunlight.** The first version kept the sky
gradient, the daylit ground and the hard cast sun shadow behind a lidar trace,
and drew the trace in the palette's grid olive — olive lines on olive ground.
There is no sun in a lidar return: scan channels now clear to a dark field,
skip the shadow and the ground fill, and use a fixed phosphor that no palette
can override. Same reasoning as the heat ramp: an instrument that changes
colour when you press `p` is decoration.

Thermal needed its ramp compressed into the middle too — raw per-facet
occlusion swings hard between neighbours and across the full ramp it read as
camouflage rather than heat.

The lock brackets track the model's **real projected silhouette**, accumulated
facet by facet in the fill loop rather than guessed from the bounding sphere.
That is why they tighten correctly onto the legs when the cutaway removes the
upper body — which is the visible proof the number is real.

Cost, at 160×48: lidar 13.6 ms, thermal 15.3, optical 19.5, xray 21.0. The scan
channels are the fastest things the program draws because they never fill.

Open: the cutaway **clips**, it does not cap. A true cross-section wants the
occupancy grid kept at runtime so the cut face can be filled from solid cells
and coloured by section — which would also give cross-sectional area as a real
number. The grid is currently discarded after load.

#### What the HUD was still getting wrong

The first pass built the four features and got the *display* wrong in five ways
at once, all of which came back as one round of feedback and all of which were
fair.

**The panel was a build report in a cockpit.** Source triangle count, welded
vertices, decimation error, watertight. Every one of those is a number about
the renderer, and none of them is a number about the machine you have just
targeted. They moved to a MESH panel behind `m`, and the default panel is now
armour, loadout, heat sinks, speeds and quirk.

The interesting question was where the armour figures come from, because Sarna
gives twelve tons of ferro-fibrous and **no per-location table** — I checked
the page and searched the wiki specifically for it. So the panel spreads the
canon twelve tons over the *measured skin area* of each segmented section and
says so on the line beneath. Area, not volume: armour is a skin. Distributing
by volume would have been the easier change and quietly wrong, because an arm
has far more surface per cubic metre than the torso — 6.9% of the skin against
6.3% of the displacement, which is a real difference in tonnage.

**The scan bar loaded forever.** It was `(sim * 0.7) % 1.0` — a barber pole. It
now counts real sensor coverage: a byte per facet, set the first time that
facet survives the backface test. That gave a bar that *filled* honestly and
then stalled at 96% and still never finished, because at a fixed tilt part of
the hull never turns to face the sensor at any bearing at all. So the
completion test is a full **revolution** of bearing, which terminates and means
something, and the coverage figure is reported alongside as the fraction a
sweep at this elevation can return. XRAY reaches 100%, which is the check that
the number is measuring what it claims: that is the one channel that does not
need the far side to turn towards you.

**Thermal was measuring the wrong quantity.** It false-coloured ambient
occlusion, on the argument that an enclosed facet is one heat cannot leave.
That is true, but it is the *trapping* term — and the machine is built around
a Starfire 375 XL, so the reactor is hotter than everything else put together
and the display was painting a cold torso. It now has a point source at the
**measured centroid of the torso section**, falling off as an inverse square,
with occlusion kept as the weaker second term. Torso mean 0.53 peaking at 1.00,
arms 0.29, legs 0.21, feet coldest at 0.05 — and the two sides agree to within
0.02, which is a free symmetry check on the segmentation as well.

The built-in mech got the same treatment, because without a heat field its
per-facet slot still held the *selection* flag, so picking a part in THERMAL
made it read white-hot.

**Two bugs found only by looking.** The lock frame's silhouette box was
accumulated in the fill loop only, so in LIDAR and XRAY — the channels you
would actually scan with — it stayed empty and the whole targeting frame
vanished. Once the instrument strip moved to own row 0, that took every readout
on the display with it. And THERMAL was still drawing a blue sky, daylit olive
ground and a hard sun shadow: I had gated all of that on `wireonly` rather than
on "is this an instrument channel", so I fixed the sunlight for two of the
three sensor channels and left it in the third.

**No target is a state.** `j`/`k` cycle through −1, so you can look at the whole
machine with nothing highlighted, which is where the program now starts.

**The help was a page and a half of prose.** It is a key table now. The prose
that was worth keeping went into the docstring and into comments beside the
things they describe; the rest was explaining decisions to someone who had not
asked.

#### Cockpit chrome

`mech.sh` and `mech2.sh` are the reference for atmosphere here — a scene player
with radio chatter, and a live dashboard with a sweep radar, gauge stack,
waveform and event ticker. Both have something this program did not: *things
happening*. This program has something neither can have: the mech is actually
there. So the chrome is built to be driven by the model rather than to sit
beside it.

The bearing tape and the elevation ladder are readouts wearing chrome's
clothes: the tape slides under a fixed caret on the camera's real azimuth, the
ladder tracks its real tilt. The viewport corners are deliberately *thin*
(`┌─│`) against the lock frame's heavy (`┏━┃`), because one is fixed and one
moves and they must never read as the same object. The boresight is a broken
cross so the centre of the sight is a gap you can see through.

The only invented data is the crew — callsign, pilot, hull number — rolled once
at launch from `--seed`, faction-neutral by request. It sheds the hull number
first on a narrow viewport, because at 90 columns the full line ran across the
top of the lock bracket.

Two things measured rather than assumed: the ladder labels are three wide
(`+20`) and the first version reserved four columns on the right, so they ran
off the last column and vanished entirely; and the armour tonnage in the combat
panel is `'%4.1f t'`, six characters, written at `panel - 5` — it spilled two
cells into the model. Both are now right-aligned off the panel edge rather than
a hand-counted column, which is the fix that stays fixed.

All of it is behind `f`, and `--no-chrome` starts without it.

#### Two sensors with one picture, a scan that did nothing, and a paper doll

**LIDAR and XRAY were the same instrument twice.** Both drew grazing-angle
contours; XRAY only added the far side at 62% brightness, which on a mostly
convex hull lands *inside* the silhouette and reads as noise. Two channels that
produce the same image are one channel with two names.

They now answer different questions. LIDAR is a **range return**, so it is
drawn as one: a point per vertex and centroid of every facet the beam reaches,
brightness by range and by how square the facet sits to the beam. No contour
filter — a point cloud does not scribble the way six thousand outlines did, and
the density thinning around the curve of the hull *is* the shape of the return.
XRAY **inverts**: the near skin drops to a faint ghost and the far side is
drawn bright, which is the whole meaning of the channel — you are looking
through the front of the machine at the inside of its back — with the reactor
marked, because on a diagnostic x-ray the power plant is the one thing you
could not miss.

The free information that made the inversion possible was already there and
being thrown away: the grazing test took `abs(n·v)`, and the *sign* of that dot
is exactly near-side versus far-side.

Measured, and it changed the design: drawing every back-facing outline in full
cost 32.5 ms/frame against the old channel's 22.8, and **67 ms at high detail**
— fifteen frames a second for a display whose whole job is to be ambient. The
inversion is what carries the meaning, not the density, so the far side got the
same grazing filter as the near. 23.4 ms, and it still reads as an x-ray.

**The scan now drives the picture.** Two things happen while the bearing
sweeps. A bright line runs down the target and holds back the geometry it has
not reached (compared in *screen* space — at these tilts a horizontal world
plane projects to within a pixel of a horizontal screen line, and screen space
costs two comparisons against numbers the fill loop already computed for the
gradient test). And the level of detail **steps up twice** as the sweep
progresses: the sensor cannot resolve what it has not looked at yet, so the
mesh starts coarse and earns its way to full. Naming a level with `--lod`, or
pressing `d`, takes manual control — an automatic that overrides a deliberate
keypress is a bug.

That block had to move *ahead* of the world transform. It can swap the level of
detail, and `world` is built from `parts`; changing one after the other has
been computed leaves the two indexed against different meshes.

**The paper doll is taken off the mesh, not drawn.** An orthographic projection
of the hull onto the plane the mirror search found, with a depth buffer so each
cell keeps whatever section is nearest the viewer. So the outline is *this*
machine's silhouette — the shoulder pods, the gap between the legs, the forward
hunch — and the regions on it are the same measured sections the panel quotes
tonnages for. Facets are sampled at their vertices and centroid rather than
scan-converted: at sixteen cells across there are nineteen facets per cell, so
rasterising each one is a lot of arithmetic to reach the same answer.

Which way round the machine is facing is still unresolved — the mirror plane
gives the axis but not its sign — so this may be the back view, and nothing on
it is labelled FRONT.

Two look-only fixes. Drawn over the render with a transparent background it was
illegible: olive hull showing through every gap turned the diagram into
camouflage, so it got a bezel. And the unselected-section dim was set to 0.46
against the *wrong* background — on the dark bezel that came out at (69,77,86),
which reads as a hole in the silhouette rather than as a part you are not
aiming at.

**The startup sequence** runs inside the frame loop rather than as a blocking
prologue, which means the last half second can wipe the panel away and reveal a
display that has been turning behind it the whole time, and nothing has to be
special-cased in the signal teardown. The numbers on it are this run's real
ones — facet count, watertightness, grid size, solid cells, sections found,
whether the reactor trace located — so the POST reports on work that actually
happened. Any key skips it; `b` replays it.

#### Where the frame time actually went

The sweep-driven level of detail was scrapped: stepping up to LOD HIGH looked
right and cost 36 ms/frame optical and 49 ms xray against 20 and 23 at medium,
which is not a price an ambient display gets to charge. Medium is the default
again and the wipe stays, because the wipe was the part that was free. The
paper doll came out too.

Then the profile, at the frame loop's own stage boundaries:

| stage | LOD 1 @200x60 | LOD 2 @200x60 |
|---|---|---|
| shade | 12.31 ms (51%) | 22.32 ms (53%) |
| gather | 4.02 | 9.95 |
| paint | 4.64 | 4.70 |
| **total** | **24.02** | **41.87** |

**The shader was recomputing constants.** The lights are world-fixed and the
turntable moves the *eye*, so for a facet that has not moved, `n·SUN`, `n·FILL`,
the sheen, the hemisphere ambient and the weathering are all exactly the
numbers they were last frame. Only fog (range) and the selection tint actually
vary. The lit colour is now cached against everything it genuinely depends on
— frame matrix, lighting mode, palette, occlusion toggle, sensor — and the
per-frame shader is fog, tint and fill. The same reasoning then applied one
stage earlier: on a loaded mesh the world-vertex transform produced the same
five thousand vertices every frame.

Three smaller ones, all in the hottest loop. The silhouette box lived in four
*list slots* updated eight times per facet — it now lives in four locals and is
written back once. The gather loop unpacked `(idx, mat, ln, lc)` per facet and
used one of the four. And screen positions were `(x, y, z)` triples, so every
facet built three fresh `(x, y)` pairs plus a tuple to hold them: five
allocations where two will do, fixed by splitting depth into its own list.

| | before | after |
|---|---|---|
| LOD 1 @200x60 | 24.02 ms | **18.12** (−25%) |
| LOD 2 @200x60 | 41.87 ms | **28.96** (−31%) |
| LOD 1 @80x24 | — | **9.76** |

All of it **pixel-identical**, each step proven against the step before it
across six lighting/sensor/palette combinations at two sizes.

Two things the harness caught that mattered more than the timings.

First, the control run failed — new against *new* scored 12/55 on some cases.
The chrome carries a `T+MM:SS` mission clock off the wall clock and a REC lamp
blinking on `now % 1.4`, so two runs a second apart differ in the top row no
matter what the renderer does. This is the second time in this file that a
control run has been the thing that saved the measurement, and it is now the
first thing the harness prints.

Second, with the clock excluded, five frames still differed at 200x60 — and it
was the lock brackets, which brightened 1.2 s after the *process started*. That
meant the sight said LOCK before the sensor had seen the far side of the
target, and the frame it changed on depended on how fast the host happened to
be running. Lock now follows the sweep. A performance harness found a design
bug, which is not what it was for.

Finally, the failure mode for a cache is not wrong arithmetic, it is an
incomplete key. So a build that drops every cache at the top of each frame --
semantically the uncached renderer -- was compared against the real one with
the pose *moving*, since a static pose can hide a missing key by never changing
the thing the key forgot. Identical on all six cases.

Open: the torso is one 60% lump by request — CT/LT/RT is a later job. HD will not
come from topology at all, since the Mad Cat's cockpit is a canopy faired into the
torso and never becomes its own component; it needs a geometric rule and should be
labelled as one. And `--builtin` still reports "MADCAT-X, 65.44 t", which is *my*
procedural invention and not the canonical machine — it should stop borrowing the
name.

#### Breaking the single file up, and what a closure costs

At 4,034 lines the file had stopped being portable in any useful sense and had
started being unnavigable, so it became a package: `mech_scanner/`, with the
mesh pipeline, the renderer and the HUD in separate subpackages and the frame
loop reduced to the order it calls them in. The single-file rule still holds for
every other program here; it is dropped for this one, and the directory is still
self-contained, which is what was actually valuable about the rule.

Two things worth recording.

**The acceptance test was pixel identity, and the mechanical part of the move
was done by slicing rather than retyping.** The pure functions — everything from
the ANSI codes to the segmentation to the built-in mech, lines 95 to 2346 — were
cut out of the original by line range and given module headers, so the moved code
is provably the same code. Only `main()` was rewritten. Then a script compared the
package's code statements against the original's, in both directions, with
docstrings stripped: everything the package added was an import or a rename I had
made deliberately, and everything the original lost was inside `main()`. That
caught an off-by-one that had dropped a `class` line and left a docstring
dangling at module scope — which happens to still be valid Python, so it would
have surfaced later as a confusing ImportError rather than a syntax error.

Then 64 comparisons: twenty flag combinations across three terminal sizes,
byte-for-byte on the emitted frames, plus the chrome compared with its
wall-clock row masked and the boot sequence checked on its POST text. All
identical, control clean. `--dt` was added to make that possible at all, since
the frame loop integrates real time and two runs otherwise land at different
azimuths.

**The package came out 5–9% faster, and the reason is worth knowing.** That was
not a goal and nothing was optimised. `main()` had five nested helper functions
— `proj`, `otext`, `draw_grid`, `field`, `btext` — and a nested function that
reads an enclosing local turns that local into a *cell*: every access becomes a
`LOAD_DEREF` through a cell object instead of a `LOAD_FAST` into a slot. Those
five closures captured 27 variables between them, including `ca`, `sa`, `ce`,
`se`, `Fl`, `OX`, `OY`, `MCZ`, `SUBX`, `ras` and `ov` — which is to say, most of
what the hot loops read. Disassembling the original: **306 `LOAD_DEREF` against
49 `LOAD_FAST`**. Splitting the closures into module-level functions taking
arguments turned all of it back into fast locals.

Which is a real lesson and not a Python trivia point: a convenience closure
inside a long function silently taxes every other line in that function, and
the tax is invisible at the source level. Verified by disassembly rather than
assumed from the timing, because "it got faster and I think I know why" is how
folklore gets written down as fact.

#### Pointing it at something that is not a Mad Cat

"Can we point it at an arbitrary STL?" turned out to have two answers. It
always could — the pipeline is generic, and a torus knot goes through
decimation, voxelisation, occlusion and segmentation without complaint. But
every canon fact was applied unconditionally, so the panel reported that torus
knot as a 75-tonne Timber Wolf Prime with an arm L and a leg R, and `--stats`
gave it a mean density of 0.037 t/m³ without blinking. The rendering was fine.
The readout was inventing.

The fix is the same rule the CANON table already had, applied one level up:
nothing in a mesh says what the object *is*, and there is no measurement that
can tell you. Facet count cannot, silhouette cannot. So canon is now attached
deliberately — `--canon auto` means the bundled `mc.stl` and nothing else — and
without it the COMBAT page becomes SURVEY: measured dimensions, volume, area,
watertight and sealed, and the section shares by both volume and skin. **No
mass.** A mesh has a volume; turning that into a tonnage needs a density, and
picking a density that produces the tonnage you already believe is circular.

The section names change with it, which is the part worth recording. What the
segmentation actually finds is the largest eroded core plus up to two outboard
components per side of the mirror plane, split by height. On the Timber Wolf
those *are* a torso, two arms and two legs, and naming them so reports a fact.
On anything else, calling one 'arm L' invents an anatomy the geometry never
claimed — so they become core / upper L / upper R / lower L / lower R, which
describes exactly what was measured. Same labels, same algorithm, honest names.

Falling out of that: `built_mass` and `built_density` left the cached mesh
report entirely. They were never measurements, and holding them there would
have meant keying the cache on the canon choice. Now the report is measurement
only and the cache is canon-independent — the same built mesh is valid whether
or not you claim to know what it depicts. Cache version bumped to 9, which
costs one rebuild and is what a version field is for.

Two smaller things done at the same time. The `.mmesh` files used to be written
beside the source STL, so pointing the renderer at a model in somebody else's
directory left six ~350 KB files in it; they now live in one `cache/` directory
inside the project, named by a digest of the absolute source path so two files
called `model.stl` cannot collide. And the frame rate cap became a real control
— default 60, `r` steps through 10/15/24/30/60/120/uncapped — because this is
meant to sit in the corner of a screen and at 200×60 it will otherwise eat a
core drawing frames nobody is looking at.

The pixel-diff harness earned its keep again on the way through, and then
needed fixing itself: the first case came back 0/55 while the same case at
another size was 55/55. Not a rendering change — the *old* build was running
against a cold cache and printing its load progress to stdout before the first
frame, which shifted the frame stream by one. The harness now warms both caches
and throws the output away before it compares anything. A harness that can
report a spurious total failure is a harness you will eventually believe.

#### Canon as data: one directory per machine

The last piece of the arbitrary-mesh work. Canon was still a dict inside
`canon.py`, which meant the program knew about exactly one machine and the only
question it could answer was "is this that machine, or nothing?". Now a mech is
a directory:

    mechs/timber_wolf/
        timber_wolf.stl
        canon.md
        reference.png

and `scan.py timber_wolf` renders that mesh with those facts. Adding a machine
is adding a directory, and the scanner can be pointed at any of them.

The format is markdown tables. That was chosen over YAML (not in the standard
library, and this project takes no dependencies) and over JSON (nobody wants to
write prose in it) — a markdown table is trivially parseable with `str.split`
and is a pleasant document to read and edit, and everything that is *not* a
table row is prose the parser ignores, so the file explains itself. The Timber
Wolf's canon.md carries its own note about why no weapon has a body location,
which is exactly where that note belongs: next to the data, not in the renderer.

Three rules moved from code into the format, and writing them down as rules is
what made the panel code fall out:

1. Every field needs a source; the sources are in the file and `--stats` prints
   them beside the measurements.
2. **A field nobody sourced is absent.** Not zero, not a plausible default. So
   every block on the combat page became conditional on its data existing, and
   an incomplete canon.md now gives a *shorter* readout instead of a confident
   wrong one. A mech with no sourced engine has no AIRFRAME block at all.
3. Geometry never supplies lore and lore never supplies geometry — already
   true, but now structurally enforced, since the two live in different files.

Two things fell out of rule 2 that were worth having anyway. The panel had been
displaying a hardcoded `375 XL` on the HEAT block while carrying the real
`Starfire 375 XL` in the canon table and never showing it; and `armour` and
`intro` were parsed and thrown away. Making every line conditional on a field
meant every field had to have a line, and those three surfaced.

One self-inflicted regression, caught by diffing the panel against the previous
build: the armour caption was changed from the hardcoded `ferro-fibrous, by
area` to the canon armour name interpolated in, which rendered as `composite
a-2 ferro-fibr` at 24 columns and said nothing. The caption's job is to say
*how the tonnage was distributed* — it is the one line on that page mixing a
canon number with a measured one — so it is now `by measured skin area` and the
armour type went to AIRFRAME with the rest of the construction trivia.

The pixel-diff trap fired twice more on the way through and both times looked
like a regression:

- All 50 frames differing, with the visible text identical — the REC lamp
  blinking on `now % 1.4`. That is why the harness passes `--no-chrome`, and I
  had left it off by hand.
- All 50 differing again with `--no-chrome` on — the *reference* build was
  running against a cold cache and printing its load progress to stdout before
  the first frame, shifting the frame stream by one. Same cause as the one
  `pixeldiff.py` was taught to warm up for; this was a hand-run comparison that
  did not get the benefit.

Both are the same lesson in different clothes: the comparison has to be of the
thing under test and nothing else, and a harness will happily tell you the
world has ended when what actually happened is that a clock ticked.

Also gone in the tidy-up: `refactordiff.py`, whose reference file only exists in
git history now and whose job `pixeldiff.py` does generically; the `reference/`
directory, folded into the mech; and the launcher's old name, since a project
called mech_scanner containing a `mechmodel.py` was one legacy too many. That
rename collided with the package's own `scan.py` (the sensor sweep), which is
now `sweep.py` — a better name for it regardless.

#### The second machine, and what it proved about the first

Adding a Marauder MAD-3R was the first real test of "adding a mech is adding a
directory", and the canon side passed without touching a line of code: drop the
STL in `mechs/marauder/`, write a `canon.md` off Sarna, `python3 scan.py
marauder`. Rule 2 did its job unprompted — the Marauder is not an OmniMech so
there is no pod space, and Sarna gives its speeds in km/h but never its walk and
run MP, so both blocks are simply absent and the panel is shorter. Converting
43.2 km/h to 4 MP is a rules calculation, not a quotation, and the whole point
of the rule is that the file may not do it.

The geometry side did not pass, and the failure was worth having. The
segmentation's acceptance test was **two outboard components on each side of
the mirror plane** — bilateral evidence, and correct evidence, but written while
looking at exactly one machine. A Timber Wolf has two arms and two legs. A
Marauder's arms are gauntlets slung under wide shoulders, and no erosion depth
parts them from the trunk. At depth 5 the sweep found a clean core plus one lobe
on each side at 0.28 of the height — its two legs, perfectly — and *threw the
result away*, fell through to the one-lump fallback, and reported the entire
machine as torso with all 11.5 tons of armour on it.

The fix is that two per side is the *preferred* answer and one per side is an
*accepted* one: the sweep keeps the deepest symmetric-but-thin result as it goes
and uses it only if nothing better turns up. Bilateral agreement is still the
evidence — a lone lobe on one side and nothing on the other is refused as noise.
The Marauder now gives a core and two legs at 27.8 and 28.3 m³, agreeing to
1.8%, which is the same free symmetry check the Timber Wolf's legs give.

Two smaller things fell out of it:

- **A section that does not exist must be absent, not zero.** The panel, the
  report and the `j`/`k` target cycle all take their list from
  `segment.present()` now. Listing `arm L 0.0 t` on a machine whose arms never
  parted reads as a limb that has been shot off, which is a worse lie than
  saying nothing.
- **With one lobe on a side, height decides leg from arm.** With two, the lower
  is a leg by construction; with one there is nothing to be lower than, so it is
  a leg only if it hangs below the trunk's own centroid. A machine could have
  outboard shoulder pods and no separable legs, and calling those legs because
  they were the only thing there would be the same error one level down.

The generalising lesson: **an acceptance test written against one specimen
encodes that specimen.** `len(left) >= 2 and len(right) >= 2` was not a bug in
its own terms — it is exactly the right test for a mech with four limbs, and it
came with a comment explaining why symmetry made it evidence rather than
assumption. What it lacked was any way to succeed *partially*. All-or-nothing
acceptance turns a correct partial answer into the worst available answer, and
the fallback branch is where that damage lands.

`pixeldiff.py` earned another entry in its own troubleshooting section on the
way through: the run that had to prove the Timber Wolf unchanged came back 18
control failures out of 20. `cache_path()` does not put `CACHE_VER` in the
filename, only in the file header, so with the version bumped the old and new
builds each rejected and overwrote the other's cache file, every run rebuilt
cold, and the load progress shifted the frame stream. The two builds get
separate cache directories now. A cache version bump is precisely when this tool
is wanted, and it was precisely the case that broke it. With that fixed: 20
comparisons, 0 differing, 0 control failures.

Three more machines went in behind the Marauder — an Atlas AS7-D, a Catapult
CPLT-C1 and an Archer — and five meshes is enough to see what the segmentation
actually does. The Archer and the Atlas give all five sections with the limbs
matching side to side within 2%. The Marauder gives three. The Catapult gives
three, and interestingly not the three you would guess: its ear pods part from
the trunk at erosion depth 8 and its legs only at depth 5, and since the sweep
commits to one depth it scores the ears and never sees the legs. The new
height test then labelled the ears **arms** rather than legs, which is right
twice over — they sit above the trunk's centroid, and the CPLT-C1 really does
mount its LRM-15s in its arms.

That is the next honest limitation: one depth cannot see a machine whose joints
are of different thicknesses. Merging seeds across depths would fix it and is a
different algorithm. What the current one gets right is that it never reports a
limb it did not measure.

The other thing four canon files taught, which one never could: **a canon.md
can spill the panel, because the panel cannot know how long a field is.**
`_field` right-aligned its value to the panel edge and clipped only when the
value collided with the key, so 'Earthwerks Incorporated' ran three cells past
the panel and into the mech. Every value on that page now comes from a file
outside the program, so its length is not something the layout can know in
advance and clipping is the only defence. The temptation was to shorten the
field in the canon.md instead — which is letting the layout dictate the data,
exactly backwards.

#### Changing target without leaving the sight

Five mechs in `mechs/` and the only way to look at a different one was to quit
and relaunch, which is a poor answer for a program whose whole point is that
you leave it running in a corner. `n` and `N` now step through the directory in
place.

The interesting part is not the key, it is that **a build cannot happen on the
frame loop**. Cold, the Atlas takes 6.8 seconds of decimation, voxelisation,
occlusion and segmentation, and a sight that freezes for seven seconds has
failed at the one thing it does. So the build runs on a worker thread while the
display keeps turning the machine you are still looking at. Measured: 25.4 fps
against a 30 fps cap during the build. The worker and the frame loop share one
interpreter, so it is a visible tax — but a tax, not a freeze, and degrading
while it works is honest in a way a spinner is not.

Four rules made it safe, and each is a bug that did not happen:

- **The worker touches nothing but its own object.** In particular it does not
  write to stdout: the emitter holds the writer's lock for most of every frame,
  so a second writer lands in the middle of one. The pipeline's `note` callback
  appends to a list instead — which is also where the readout comes from.
- **The swap happens in the frame loop, at the top of a frame.** `rig` is a
  local bound once outside the loop, so half a frame against the old mesh and
  half against the new is one missed rebinding away. Same hazard `Scan.bind`
  was already written to guard against.
- **`scan.restart()` on the swap is not optional.** Both rigs have exactly one
  part in stl_mode, so `bind()` finds the part count unchanged, keeps the old
  `seen` arrays and scores the new mesh against the old hull's facet indices.
  The docstring on `bind` warns about precisely this for level-of-detail
  switches; a mech swap is the same thing with a bigger difference.
- **The thread is a daemon,** so a signal teardown does not wait seven seconds
  for a decimation before restoring the terminal. Verified: six teardowns
  landed mid-build across all three signals, zero failures.

Restarting the scan turned out to be free flavour as well as correctness. The
acquisition wipe runs down the new hull and the lock brackets stay dim until
the sensor has swept it — which is not decoration, because it genuinely has not
been seen yet.

**The readout is the pipeline's own progress messages.** `reading as7-d4.stl`,
`analysing 84,468 facets`, `voxelising at 80^3`, `mirror plane 62% symmetric`,
`decimating 84,468 facets to 14,000`. Nothing on it is written for the
occasion, which is the whole reason it is worth watching — the same principle
as the cold-start POST reporting this run's real numbers. A warm cache says
`3 levels from cache` rather than miming work it did not do; that needed a new
note in `load_models`, because a cache hit used to say nothing at all and a
readout with no lines on it looks like a hang.

And **no progress bar**, which is the one design decision here worth arguing
about. The number of stages is not known before they happen, so a bar would be
guessing at its own denominator — and this project has already learned what
that costs, when the scan bar asymptoted at 96% because some of the hull never
faces the sensor at any bearing. Elapsed seconds instead: the one number
actually known, frozen when the build stops, so what is left on screen is what
the acquisition cost. `MIN_HOLD` does keep the box up for 1.15 s even on a warm
cache, which is padding — but padding the *duration* of a true readout is a
different thing from inventing its content.

Two small ones, both found by driving a real pty rather than by reading:

- The box title was composed as a frame string plus an overlapping title
  string, and left a stray letter poking out of the rule: `┌TARGET ACQUISITION
  N ────`. Fixed by composing one string of exactly the right width and
  recolouring a slice of it in place. Two overlapping writes to the same cells
  are never worth the cleverness.
- The `LOCK · ARCHER` flash went up with the panels and the cockpit chrome was
  drawn *after* it, straight through the middle: `LOCK · AR│HER`. The flash now
  draws on top of the chrome. An alert the decoration can cut in half is not an
  alert — and this had never shown up before only because every existing flash
  was short enough to miss the frame.

Timber Wolf still 20/20 byte-identical through all of it, which is the point of
keeping that harness pointed at a fixed mech.

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
