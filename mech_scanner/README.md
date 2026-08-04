# mech_scanner

A targeting and diagnostics sight for a BattleMech, drawn in a terminal.

A 3D model on a slow-orbiting camera, rendered at half-block resolution with
true per-facet normals, dressed as the cockpit display of a machine that has
just designated a target. Point it at an STL and it renders that; the reference
model is a Timber Wolf (Inner Sphere codename *Mad Cat*).

Pure Python standard library. No pip installs, no network at runtime, nothing
to build. Python 3.8+.

```
python3 scan.py                   # the first mech in mechs/
python3 scan.py timber_wolf       # a named mech
python3 scan.py --list            # what is available
python3 scan.py --stats           # the mesh report, then exit
python3 scan.py path/to/thing.stl # a bare mesh, with no lore attached
python3 -m mechscan --builtin     # the procedural mech instead
```

Each machine is a directory under [`mechs/`](#mechs) holding its mesh and a
`canon.md` of sourced facts. Adding a mech is adding a directory.

---

## Contents

- [What it does](#what-it-does)
- [Mechs](#mechs)
- [Controls](#controls)
- [Changing target](#changing-target)
- [Command line](#command-line)
- [How it is put together](#how-it-is-put-together)
- [The mesh pipeline](#the-mesh-pipeline)
- [The frame loop](#the-frame-loop)
- [Rules the code follows](#rules-the-code-follows)
- [Tools](#tools)
- [Performance](#performance)
- [Known limits and open work](#known-limits-and-open-work)
- [Layout](#layout)

---

## What it does

The reference STL is 242,976 triangles and the renderer can afford a few
thousand, so the mesh goes through a pipeline before anything is drawn:
vertex-cluster decimation to a facet budget, a voxel occupancy grid flooded
from the outside to find what is solid, a hemisphere of rays per facet for real
ambient occlusion, and a morphological segmentation that splits the hull into
the machine's own limbs. That is seconds of work, so the result is cached
beside the source file and is a few milliseconds thereafter. Three levels of
detail are built; `d` cycles them.

A few thousand facets is not a compromise. At half-block resolution the model
covers roughly 150×400 pixels, so it is already one facet per handful of
pixels, and more would be invisible.

The display carries:

**Four sensor channels** (`v`), each a different question asked of the same
mesh and each answered from something already measured.

| Channel | What it draws |
|---|---|
| OPTICAL | The lit hull: key light, fill, sheen, hemisphere ambient, fog. |
| THERMAL | False colour from a heat field with the fusion plant as its source — a point at the *measured* centroid of the torso section, inverse-square falloff, plus a weaker trapping term from occlusion. |
| LIDAR | A range return, drawn as a point cloud, brightness by range and by how square each facet sits to the beam. |
| XRAY | The inversion: the near skin drops to a ghost and the far side of the hull is drawn bright, with the reactor marked and pulsing. |

**Two panel pages** (`m`). COMBAT is what a gunner would want — designation,
tonnage, loadout, heat sinks, speeds, and the armour spread over the sections
the segmentation found. MESH is the renderer's own report — welded vertex count, whether
every edge is used exactly twice, decimation error against the source, facets
drawn, frame rate.

**A scan that measures something.** SCAN is not a progress bar. It fills with
the *bearing* swept since the scan began and completes on a full revolution;
the percentage beside it is how much of the hull has actually returned. A
bright wipe runs down the target while the sweep is live and holds back the
geometry it has not reached, and the lock brackets stay dim until the sweep
finishes.

**Cockpit chrome** (`f`). Viewport corners, a crew line, and a bearing tape and
elevation ladder driven by the camera's real azimuth and tilt — readouts that
happen to look like chrome, rather than chrome pretending to be readouts.

**A cold start** (`b`), reporting this run's real load numbers.

With `--builtin`, or with no STL to hand, it draws a mech assembled here out of
lofted convex hulls on a 17-bone skeleton — articulated, so `j`/`k` walk the
structure list, `e` pulls it apart and `i` gives it an idle sway.

---

## Mechs

Each machine is a directory under `mechs/`:

```
mechs/
├── timber_wolf/          TIMBER WOLF (MAD CAT) PRIME
│   ├── timber_wolf.stl   the geometry
│   ├── canon.md          the facts, with their sources
│   └── reference.png     optional, never read by the program
├── marauder/             MARAUDER MAD-3R
├── atlas/                ATLAS AS7-D
├── catapult/             CATAPULT CPLT-C1
├── archer/               ARCHER ARC-2R
└── _template/
    └── canon.md          the format, documented — a leading _ is skipped
```

```
python3 scan.py --list          # what is available
python3 scan.py timber_wolf     # by name
python3 scan.py mechs/whatever  # or by path, from anywhere
```

Canon used to be a dict inside the program, which meant it knew about exactly
one machine and applied its stats to whatever mesh it was handed. Pointing it
at a torus knot produced a confident report of a 75-tonne Timber Wolf Prime
with an arm L and a leg R. Now the facts are **data that travels with the
mesh**, and adding a machine is adding a directory.

### canon.md

Markdown tables — the one structured form that is both trivially parseable with
the standard library and pleasant to read and edit as a document. Anything that
is not a table row is prose and is ignored, so the file explains itself.

```markdown
## Identity

| field    | value       |
| -------- | ----------- |
| name     | TIMBER WOLF |
| codename | MAD CAT     |
| config   | PRIME       |
| origin   | Clan Wolf   |

## Weapons

| weapon          | count |
| --------------- | ----- |
| ER Large Laser  | 2     |

## Sources

- https://www.sarna.net/wiki/Timber_Wolf_(Mad_Cat)
```

Fields: `name` `codename` `config` `origin` `intro` `mass_t` `chassis`
`engine` `armour` `armour_t` `heatsinks` `podspace` `cruise` `flank` `walk_mp`
`run_mp`, plus `stl` and `up` under `## Model` for how to load the mesh. Only
`name` is required. See [`mechs/_template/canon.md`](mechs/_template/canon.md),
which documents the format at length.

Three rules govern the file, and they are the point of the whole design:

1. **Every field needs a source**, and the sources go at the bottom. `--stats`
   prints them beside the measurements.
2. **A field nobody sourced is absent** — not zero, not a plausible guess.
   Every block on the panel is conditional on the data existing, so an
   incomplete `canon.md` gives a *shorter* readout, never a confident wrong
   one. A mech with no sourced engine simply has no AIRFRAME block.
3. **Geometry never supplies lore and lore never supplies geometry.** Nothing
   in a `canon.md` is derived from the mesh, and nothing in the mesh report is
   derived from canon — the built-mesh cache holds measurements only, which is
   why it stays valid regardless of what you claim the mesh depicts.

### A mesh with no facts

A bare `.stl` path, a mech directory with no `canon.md`, or `--canon none`, all
give the same thing: the COMBAT page becomes **SURVEY**, and everything on it
is measured.

```
    UNIDENTIFIED                  TIMBER WOLF
    no canon source               MAD CAT  PRIME
    ────────────────────          ────────────────────
    height        12.0 m          75 t       Clan Wolf
    width         10.1 m
    depth         11.2 m          ARMOUR ─────── 12.0 t
                                  by measured skin area
    MEASURED ───────────           torso   ██████  7.1 t
    volume      138.6 m³           arm L   ▋       0.8 t
    surface     449.0 m²           arm R   ▋       0.9 t
    watertight       yes           leg L   █▎      1.6 t
    sealed           yes           leg R   █▎      1.6 t

    SECTIONS ───────────          LOADOUT ─────── PRIME
              vol   skin          2x ER Large Laser
     core   63.0%  59.3%          2x ER Medium Laser
     upper L  6.3%  6.9%          1x Medium Pulse Laser
     upper R  6.4%  7.1%          ...
     lower L 12.2% 13.4%
     lower R 12.2% 13.3%
```

There is **no mass** on the survey, because mass is not a property of a mesh:
turning a volume into a tonnage needs a density, and picking a density to reach
a tonnage you already believe is circular.

The sections also change their names, because they change their meaning. What
the segmentation finds is the largest eroded core plus up to two outboard
components on each side of the measured mirror plane, split by height. On the
Timber Wolf those *are* a torso, two arms and two legs, and saying so reports a
fact. On anything else, calling one `arm L` invents an anatomy the geometry
never claimed — so they become `core`, `upper L/R` and `lower L/R`.

There may be fewer than five. The Marauder yields three — a core and two legs,
its arms never parting from the trunk — and the ones it does not yield are
absent from the panel, the report and the target cycle rather than listed at
0.0 t, which would read as a limb that had been shot off.

The two columns above are worth a second look. On the reference mesh the core
is 63.0% of the displacement but only 59.3% of the surface, which is exactly
why armour is spread by area and not by volume.

---

## Controls

```
SPACE  pause turntable    v      sensor channel
<- ->  orbit              c      cutaway plane
^ v    tilt               - =    move the cut
[ ]    zoom               j k    target section
, .    spin rate          m      panel: combat/mesh
d      detail             f      cockpit chrome
a      occlusion          b      replay startup
w      wireframe          l      labels
g      grid               S      cast shadow
s      starfield          L      lighting
i      idle animation     p 1-6  palette
e      exploded view      z      zen (hide HUD)
r      frame rate cap     0      reset
n N    next / prev mech   h      this help
                          q      quit
```

`r` steps the cap through 10 / 15 / 24 / 30 / 60 / 120 / uncapped. This is an
ambient display meant to sit in the corner of a screen, so the cap is a real
control and not a formality — at 200×60 the renderer will happily eat a core
drawing frames nobody is looking at. Default 60; `--fps` sets it at launch and
`--fps 0` starts uncapped.

`n` and `N` step through `mechs/` **without leaving the sight** — see
[Changing target](#changing-target) below.

`j`/`k` cycle NO TARGET → torso → arm L → arm R → leg L → leg R, skipping any
section this machine does not have — the Marauder has no separable arms, so it
cycles NO TARGET → torso → leg L → leg R. **NO TARGET is a real state, not a
sentinel to skip past**: a gunner who wants the whole machine with nothing
highlighted has to be able to get there.

`e` and `i` are **silently inert** on a loaded mesh, which is one rigid
watertight shell with no joints to move. A key that is deliberately inert
should say nothing at all — an explanatory flash every time you press it is
worse than no response.

---

## Changing target

`n` and `N` step through `mechs/` in place. There is no restart and no pause:
the build runs on a worker thread while the sight keeps drawing the machine you
are still looking at.

```
┌ TARGET ACQUISITION ───────────────── 3.1 s ┐
│ ATLAS                                      │
│ [OK] reading as7-d4.stl                    │
│ [OK] analysing 84,468 facets               │
│ [OK] voxelising at 80^3                    │
│ [OK] segmenting limbs                      │
│ [OK] mirror plane 62% symmetric            │
│ [··] decimating 84,468 facets to 14,000    │
└────────────────────────────────────────────┘
```

Those lines are the mesh pipeline's own progress messages, arriving as the
stages finish. **Nothing on the readout is invented**: every line is work that
actually ran, and a warm cache says `3 levels from cache` rather than miming
four seconds it did not spend.

There is deliberately **no progress bar**. The number of stages is not known
before they happen, so a bar would be guessing at its own denominator — and
this program has already learned once what a bar that cannot honestly reach
100% does to a display (see the scan, above). Elapsed seconds is the readout
instead, because it is the one number that is actually known. It stops when the
build stops, so what is left on screen is what the acquisition cost.

Measured on a cold cache: the Atlas takes **6.8 s** to build, during which the
sight kept drawing at **25.4 fps against a 30 fps cap**. The worker and the
frame loop share one interpreter, so a build is a visible tax on the frame rate
— but it is a tax, not a freeze, and a warm cache costs 0.2 s.

The swap itself happens in the frame loop, at the top of a frame, before
anything has read the rig. Half a frame drawn against the old mesh and half
against the new is the same class of bug `Scan.bind` already guards against.
On the swap the target selection drops to NO TARGET and **the sweep starts
over**, so the acquisition wipe runs down the new hull and the lock brackets
stay dim until the sensor has actually seen it. That is not decoration: it has
not been seen yet.

A build that fails does not take the sight with it. The box turns red, keeps
the reason on screen for three seconds, and leaves you on the machine you had.

---

## Command line

| Flag | Effect |
|---|---|
| `--builtin` | The procedural mech, ignoring any STL. |
| `--up {z,y}` | Which axis the mesh calls up. Overrides the mech's `canon.md`. |
| `--faces N` | One custom facet budget, replacing the three levels. |
| `--lod {0,1,2}` | Starting detail level. Default 1 (medium). |
| `--voxels N` | Occupancy grid resolution on the longest axis. Default 80. |
| `--ao-radius F` | Occlusion reach, in voxels. Default 4. |
| `--no-ao` | Skip occlusion. |
| `--no-cache` | Rebuild the mesh cache instead of reading it. |
| `--cache-dir DIR` | Where built meshes are cached. Default `cache/` inside the project. |
| `--canon {auto,none}` | `none` ignores the mech's `canon.md` and shows the measured survey. |
| `--list` | List the available mechs and exit. |
| `--palette NAME` | `field` (default, daylight) \| `matrix` \| `amber` \| `ice` \| `plasma` \| `blood` |
| `--lighting {full,key,flat}` | Shading cost. See below. |
| `--sensor NAME` | Channel to start in. |
| `--tilt --az --dist --speed` | Starting camera tilt, azimuth, range and spin rate. |
| `--blocks {quad,half}` | 2×2 sub-pixels per cell, or 1×2. |
| `--zen` | Hide the HUD. |
| `--no-stars --no-shadow --no-idle --no-boot --no-chrome` | Turn features off at launch. |
| `--seed N` | Pin the callsign, pilot and hull number. |
| `--fps F` | Frame rate cap, 0 for uncapped. Default 60. `r` cycles it live. |
| `--stats` | Print the mesh report and exit. |
| `--frames N` | Render N frames and exit. Harness use. |
| `--dt SECONDS` | Pin the simulation timestep instead of reading the wall clock. Harness use — see [Tools](#tools). |

`--lighting key` drops the fill light, the sheen, the hemisphere ambient and
the fog, and is about 20% cheaper at the shading stage while still reading as
three-dimensional. `--lighting flat` drops lighting altogether, which on a
single-material mesh like the STL leaves a featureless green silhouette. It is
the fastest thing the renderer can draw and it buys about a millisecond over
`key`, which is why `key` is the one worth reaching for.

---

## How it is put together

The program was a single 4,000-line file. It is now a package, split along the
seams the problem actually has: the mesh pipeline knows nothing about the
terminal, the renderer knows nothing about the HUD, and the frame loop knows
only the order to call them in.

```
mechscan/
├── ansi.py         escape codes, the SGR caches, colour maths, the quadrant glyphs
├── raster.py       the pixel buffer: 1×2 (or 2×2) per cell, scanline fills, clipped lines
├── emit.py         raster + overlay → one string of ANSI, once per frame
├── keyboard.py     non-blocking raw-mode key input
├── math3d.py       3×3 matrices as flat 9-tuples, vectors, a 2D convex hull
├── text.py         number and bar formatting
│
├── materials.py    what the machine is made of, and the density model
├── palettes.py     six screen palettes and the hue collapse that makes five of them
├── canon.py        reading a mech directory and its canon.md
├── lighting.py     the world-fixed light rig; the three lighting modes
├── sweep.py        the sensor sweep: what the instrument has actually seen
├── acquire.py      changing target while the sight runs: the worker thread
├── rig.py          what is being drawn, and the measurements taken off it at load
├── app.py          state, input, and the frame loop
├── cli.py          argument parsing, model selection, --stats
│
├── mesh/           STL in, drawable Model out
│   ├── stl.py          read binary or ASCII STL; weld, count edges, measure
│   ├── decimate.py     vertex clustering to a facet budget
│   ├── voxels.py       the occupancy grid: burn, flood the outside, cross-check
│   ├── occlusion.py    a hemisphere of rays per facet, marched against the grid
│   ├── segment.py      erosion + connected components + watershed → the limbs
│   ├── thermal.py      the reactor heat field
│   ├── shadow.py       ground shadow as height bands, precomputed at load
│   ├── model.py        the Model, and the normalise that stands it on the ground
│   ├── cache.py        the built-mesh cache beside the source file
│   ├── pipeline.py     load_models(): the whole thing, cached
│   ├── build.py        loft primitives, and the Part that binds a mesh to a bone
│   ├── frames.py       one bone of a skeleton
│   ├── builtin.py      the procedural mech
│   └── report.py       the --stats report
│
├── render/         the renderer
│   ├── camera.py       the turntable, and the fit that frames the model
│   ├── view.py         every toggle resolved once a frame into derived flags
│   ├── sensors.py      the four channels and their fixed colour ramps
│   ├── scene.py        sky, ground, grid, cast shadow
│   └── facets.py       the hot path: transform, gather, shade, fill
│
└── hud/            the head-up display
    ├── overlay.py      the character layer that sits over the raster
    ├── panels.py       the combat / mesh / structure pages
    ├── reticle.py      lock brackets and the instrument strip
    ├── chrome.py       cockpit furniture and the crew
    ├── boot.py         the cold start
    ├── acquire.py      the target acquisition readout
    └── help.py         the key list
```

`scan.py` at the top level is a three-line launcher; `python3 -m mechscan` is
the same thing.

**Why a package now.** Everything else in `terminal_toys/` is deliberately a
single file, so it can be `scp`'d anywhere and run. That rule is dropped here
and only here: at four thousand lines the file had stopped being portable in
any useful sense and had started being unnavigable. The directory is still
self-contained — copy `mech_scanner/` and it runs — so what was actually
valuable about the rule survives.

**The two big types.** `Rig` is what is being drawn; `View` is how. Both exist
because the frame loop owns two dozen toggles and passing them one at a time to
four render functions is how a signature grows to twenty arguments and how a
mode ends up half-applied because one call site was missed.

---

## The mesh pipeline

Each stage exists because the one before it is not enough, and several of them
carry a cross-check because the failure being guarded against is *silent*.

**Read and measure** (`mesh/stl.py`). Welds vertices at a tolerance relative to
the diagonal, then checks that every edge is used exactly twice. That is what
watertight means, and it is what makes the enclosed volume a real number rather
than a hopeful one. The header check is the size arithmetic, not the leading
word — plenty of binary STLs in the wild start with `solid`.

**Decimate** (`mesh/decimate.py`). Vertex clustering: snap every corner to a
grid cell, keep one representative per cell, drop triangles whose corners
collapse together. Clustering rather than quadric edge collapse because this is
O(n) in one pass where the collapse is a priority queue over 364,000 edges and
minutes of Python. The representative is the *area-weighted mean* of the
corners that landed in the cell, not the cell centre — the centre quantises
every surface onto a lattice and the model comes out visibly stair-stepped.

Finding the grid resolution that hits a facet budget is not a binary search.
Face count over a surface grows as the *square* of the resolution, so one probe
predicts the answer: `n' = n · √(target/f)`. That converges in two or three
passes where bisecting took nine, and each pass is a full clustering of a
quarter-million triangles.

**Voxelise** (`mesh/voxels.py`). Burn the dense mesh into a lattice, flood the
outside from every boundary face, and call everything unreached solid.

The sampling lattice on each triangle is sized from its **longest edge**, not
its area. Sizing from area leaks: an STL like this is full of slivers —
triangles whose area is near zero but whose edges run across a dozen voxels —
and those get three samples, leave their span unmarked, and let the outside
flood walk straight into the interior. The failure is silent: the grid still
looks like a model, "solid" just quietly comes to mean "shell", and occlusion
stops seeing anything it should. So the solid cell count is checked against the
mesh's own enclosed volume, and `--stats` reports `sealed`.

**Occlude** (`mesh/occlusion.py`). Thirteen fixed directions in the hemisphere
about each facet's normal, marched out to a radius against the grid. This is
occlusion in the real sense — it sees the arm hanging in front of the chest,
which a curvature estimate never can, and that is the whole reason the grid
exists. Fixed directions rather than random ones, so a facet gets the same
answer every run and the cache means something.

Normalised against the mesh's own open-sky value (the 85th percentile) rather
than against 1.0. Theory says an unoccluded facet sees the whole hemisphere,
but a facet on a real machine is surrounded by panel gaps, bolt heads and its
own neighbours, so the raw mean here is 0.35 and shading straight off it drags
the entire model into shadow.

**Segment** (`mesh/segment.py`). Split the hull into TORSO, LA, RA, LL, RL.

The first attempt sliced the grid horizontally and took connected components
per slice — a Reeb graph of the height function. It found the legs and the
missile pods cleanly and *failed* on the arms, giving one arm 2.9% of the hull
and the other 0.9%: above the hips an arm and the side of the torso fall in the
same 2D component wherever they overlap in plan view, and no amount of
per-slice connectivity will part them. That is measured, not suspected.

Morphology fits the shape of the problem instead. A mech's joints are its
narrow places — ankle, knee, hip, shoulder, elbow — so erosion breaks them
first and the limbs fall off on their own. Erode to a core, take 3D connected
components as seeds, then grow every seed at once back over the full solid. The
simultaneous flood is a watershed: it assigns each cell to whichever core
reaches it first, which puts the boundary in the joint where it belongs.

Erosion depth is **not** a constant — it has to scale with voxel resolution, and
at 96³ a depth of 6 parts the limbs cleanly while at 80³ the same depth erases
them. So it is swept, and bilateral symmetry decides: the right depth is the
deepest one that still finds at least two outboard components on *each* side of
the measured mirror plane, which is what a mech with two arms and two legs must
produce. Nothing in the search knows the machine is symmetric, so when it
agrees, that agreement is evidence rather than assumption.

Left and right come from a measured **mirror plane**, not from which way the
STL happens to face. The obvious shortcut — lateral axis = whichever way the
legs are furthest apart — is a coin flip on this mesh: the Mad Cat is modelled
mid-stride and its legs are separated diagonally, 35.3 grid units one way
against 38.1 the other. Structure is symmetric even when pose is not, and the
symmetric mass outweighs the stride. The plane scores 0.686 against a worst case
of 0.327, and it is not 1.0 precisely because the stride is real.

**Per-section volume comes from labelled voxel counts, not from fan integrals.**
An earlier version summed signed tetrahedron volumes per section on the
argument that the divergence theorem would sort out the open boundary. It does
not: the fan integral is only volume for a *closed* surface. The evidence was
the arms coming out 3.1 m³ against 5.8 m³ — a near 2:1 split between two limbs
whose facet counts agreed to within 4%. The watershed assigns every solid cell
to exactly one section, so the counts are a true partition, and the legs now
agree exactly.

**Cache** (`mesh/cache.py`). Keyed on the source path, its size and mtime, the
facet budget, the up-axis, the occlusion radius and the grid resolution — so a
stale cache is a miss, never a wrong answer. Warm load is about 0.02 s against
about 25 s cold.

**Nothing in `cache/` is precious.** Every byte of it is derived from the source
STL; delete the directory and the next run rebuilds it. The files used to sit
beside the source mesh, which meant pointing the renderer at a model in
somebody else's directory left six ~350 KB files in it. They now go in one
directory inside the project, named by a digest of the absolute source path so
two files with the same basename cannot collide, with the readable stem on the
front so the directory can be skimmed by a human deciding what to bin.

Canon is deliberately *not* part of the key, because nothing canon touches is
stored there: the report holds measurements only, and tonnage is derived at
display time from whatever canon table the run attached. The same built mesh is
therefore valid whether or not you claim to know what it depicts.

---

## The frame loop

`app.py`, and it reads as a table of contents. Every stage is one call into
`render/` or `hud/`.

```
input → acquire → camera → sky → ground and grid → scan state
      → pose and transform → cast shadow → gather faces → shade and fill
      → overlay → targeting frame → cockpit chrome → flash
      → acquisition readout → boot sequence → paint
```

The `# ---- name ----` comments marking those stages are **load-bearing**:
`tools/profile.py` splits the loop on exactly those markers to attribute frame
time, so renaming one silently changes what the numbers mean.

Two ordering constraints were bugs first:

- **The scan block runs before the transform.** It can swap the level of
  detail, and `world` is built from `parts` — changing one after the other has
  been computed leaves the two indexed against different meshes.
- **`drawn` is taken before the instrument channels consume the queue**, so the
  mesh panel reports the same facet count in every channel.
- **A target swap happens in `acquire`, at the top of the frame**, before
  anything has read `rig` — same reason as the first.
- **The flash is drawn after the chrome.** It used to go up with the panels,
  and the viewport frame was then drawn straight through `LOCK · ARCHER`,
  cutting the message in half. An alert the decoration can carve up is not an
  alert.

**Painter's algorithm over individual facets**, sorted by mean camera-space
depth. The sibling program `dscape.py` can do better than a sort, because its
blocks sit on a guillotine plan whose own cuts give an exact order; nothing here
is axis-aligned, so there is no such plan. The sort is wrong only where two
hulls interpenetrate, which in this model happens exclusively inside joints — a
bearing sunk into a limb, a ram buried in a calf — where the seam is hidden by
the very parts that create it.

**The backface test is against the eye**, not against a global azimuth. Under
perspective the two disagree at the edges of a wide model, and the disagreement
is a hole you can see through. XRAY is exactly the mode that wants the far
side, so it is the one mode that skips the test.

---

## Rules the code follows

**Canon is attached, never assumed.** There is no measurement that can tell you
what a mesh depicts, and a wrong guess puts invented tonnage on screen next to
measured geometry — the one thing this program is built not to do. So facts
travel with the mesh in its own directory, and a mesh with no `canon.md` gets
the measured survey. See [Mechs](#mechs).

**Sarna owns the fiction.** `mechs/timber_wolf/canon.md` is quoted from
[sarna.net](https://www.sarna.net/wiki/Timber_Wolf_(Mad_Cat)) and nothing in it
is rounded, averaged or filled in. Note what is deliberately *absent*: Sarna
lists the Prime's nine weapons but assigns none of them to a body location, so
neither does that table. An earlier draft put the ER larges "in the arms" and
the LRM-20s "in the side torsos" — the sort of thing everyone knows and nobody
sourced. If a location is wanted it has to come from the wiki, not from the
shape of the mesh.

That file also has no `quirk` field. Weak Head Armor is a tabletop rules modifier,
not something true about the machine in the fiction, and the panel is a lore
readout.

**Two sources and no third, and every line says which it is.** CANON is Sarna's;
everything else is measured off the mesh. Where they meet is stated: the armour
spread is Sarna's twelve tons distributed over *measured* skin area, and the
mean density is Sarna's 75 tons over the *measured* displacement — that way
round, because the wiki owns the tonnage and the mesh owns the geometry, and
neither is asked to supply the other's number.

Armour is spread by **area**, not volume, because armour is a skin. An arm has
far more skin per cubic metre than the torso does; distributing by displacement
would have quietly armoured the torso at the limbs' expense. Measured, the
torso is 59.3% of the skin but 63.0% of the volume.

**Measure, don't assert.** Every claim in this README that carries a number is
one that was measured, and several of them replaced a plausible guess that
turned out to be wrong. The failures are kept in the comments beside the code
that fixed them, because the failure is usually more informative than the fix.

**A control run first.** Before trusting any A/B measurement, run the new build
against *itself*. That has caught a false result twice here: once because the
per-facet weathering used `hash()` of a string, which Python salts per process,
so no two runs ever drew the same frame; and once because the cockpit chrome
carries a wall-clock mission timer and a blinking REC lamp, so two runs a
second apart differ regardless of the renderer.

**A mode is a set of variables.** Only one piece of code may leave it, and a key
that is deliberately inert must be *silently* inert.

---

## Tools

`tools/` holds the harnesses. They are the reason changes to this program can
be made with any confidence, and they are all standard library.

| Tool | What it proves |
|---|---|
| `sweep.py` | Every terminal shape × every mode × every palette exits cleanly with no traceback. Catches layout that only works at one width — which has bitten the armour column, the elevation ladder and the crew line. |
| `keysoak.py` | 300 random keys, bound and unbound, through a real pty. Catches state combinations nobody types. It found the explode direction that existed only for the visible level of detail. |
| `teardown.py` | SIGTERM/SIGHUP/SIGINT at 60 random points; asserts the terminal is restored every time. |
| `pixeldiff.py` | Two builds, frame by frame, byte for byte, with a control run. Reach for this before and after any change meant to be invisible. |
| `profile.py` | Per-stage frame cost, split on the frame loop's own markers. |

Two flags exist purely for these: `--frames N` and `--dt SECONDS`. The frame
loop integrates real wall-clock time, so without a pinned `dt` two runs land at
different azimuths and a pixel comparison measures the speed of the host rather
than the renderer.

Run harnesses under `bash -c`. `fish` does not word-split unquoted variables,
which has produced spurious failures in this project more than once.

---

## Performance

Measured at 200×60, medium detail, on the reference mesh:

| Stage | ms/frame | Share |
|---|---|---|
| shade and fill | 7.65 | 45% |
| paint (the emitter) | 3.76 | 22% |
| gather faces | 3.73 | 22% |
| ground and grid | 0.83 | 5% |
| cast shadow | 0.49 | 3% |
| everything else | 0.6 | 3% |
| **total** | **17.1** | |

The renderer is built around one fact: **the turntable moves the eye, not the
mech, and the lights are world-fixed.** So for a facet that has not moved,
`n·SUN`, `n·FILL`, the sheen, the hemisphere ambient and the weathering are all
exactly the numbers they were last frame. Only fog and the selection tint vary.
World vertices, world normals and lit colours are therefore cached against
everything that *can* move them — the frame matrix, the lighting mode, the
palette, the occlusion toggle, the sensor — so an idle sway or an explode still
recomputes. That makes them exact, not approximate, and the pixel diff is what
checks it.

`shade()` and `lerp()` are inlined in the hot loops **including their `int()`
truncations**, which is what makes the fast path bit-for-bit identical to the
version that called them rather than merely close to it.

The emitter is the remaining untouched target. It is a per-*cell* loop — twelve
thousand iterations at 200×60 regardless of how much geometry there was — so it
is a different job from everything upstream of it.

**One note from the refactor.** The package runs 5–9% faster than the single
file did, for a reason worth recording. `main()` had five nested helper
functions (`proj`, `otext`, `draw_grid`, `field`, `btext`) closing over 27
variables, including `ca`, `sa`, `ce`, `se`, `Fl`, `OX`, `OY`, `MCZ`, `SUBX`,
`ras` and `ov`. Closed-over variables become *cells*, and every read is a
`LOAD_DEREF` through a cell object rather than a `LOAD_FAST` into a slot —
306 of them against 49 plain locals. Splitting the closures into module
functions that take arguments turned all of that back into fast locals. The
speedup was not the goal and was not designed for; it fell out of removing the
closures, and it was verified rather than assumed.

---

## Known limits and open work

Honest list. Each of these is a real limitation, not a to-do that will silently
never happen.

- **The torso is not split into CT / LT / RT.** Everything that is not a limb is
  TORSO. Splitting it needs a rule that is not topological, since the side
  torsos do not separate under erosion at any depth that keeps the arms.
- **No head section.** The Mad Cat's cockpit is a canopy faired into the torso
  and never becomes its own component, so HD will not come from topology. It
  needs a geometric rule, and would have to be labelled as one.
- **The cutaway clips but does not cap.** A true cross-section needs the
  occupancy grid kept at runtime; the grid is discarded after load.
- **No aspect angle.** The mirror plane gives the lateral axis but not its
  sign, so front cannot be told from rear. The strip therefore carries bearing
  and range only, and does not claim to know which way the target is facing.
- **`--builtin` still reports "MADCAT-X, 65.44 t".** The procedural mech is an
  invention, and by this project's own sourcing rule it should stop borrowing
  the name. Its tonnage comes from a calibrated density model rather than from
  any source, which is the one place a density is still asked to produce a mass.
- **Segmentation finds between one and five sections**, and cannot find a limb
  that never parts from the trunk. The Marauder's arms are gauntlets slung
  under wide shoulders and no erosion depth separates them, so its readout is a
  torso and two legs and its arms are counted as torso. That is honest — the
  counts still partition the solid exactly — but it is not the same as the
  machine not having arms.
- **The segmentation commits to a single erosion depth**, and on some meshes no
  single depth sees everything. The Catapult's ear pods part at depth 8 and its
  legs at depth 5, and it is scored at 8, so it reports a torso and two arms and
  its legs go unfound. Merging seeds across depths would fix it and is a
  different algorithm; the present one at least never reports a limb it did not
  measure.
- **The emitter is unoptimised**, at 15–25% of the frame. See above.

---

## Layout

```
mech_scanner/
├── README.md            this file
├── scan.py              launcher; python3 -m mechscan is equivalent
├── mechs/               one directory per machine
│   ├── timber_wolf/         mesh + canon.md + reference image
│   ├── marauder/ atlas/ catapult/ archer/
│   └── _template/           the canon.md format, documented
├── mechscan/            the package
├── tools/               measurement harnesses
└── cache/               built meshes (gitignored, disposable)
```

The design journal for this program — what was tried, what was measured, what
was thrown away — lives in `../ideas.md` under *mechmodel.py*.
