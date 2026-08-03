"""
 MECHSCAN // targeting and diagnostics rig for a battlemech
 ---------------------------------------------------------
 A 3D model on a slow-orbiting camera, drawn in a terminal at half-block
 resolution, dressed as the sight of a combat mech that has just designated a
 target. Pure standard library: no pip installs, no network at runtime.

 Each machine is a directory under mechs/ holding its mesh and a canon.md of
 sourced facts; adding a mech is adding a directory. The reference model is
 242,976 triangles and the renderer can afford a few thousand, so the mesh goes through
 a pipeline first: vertex-cluster decimation to a facet budget, a voxel
 occupancy grid flooded from the outside to find what is solid, a hemisphere of
 rays per facet for real ambient occlusion, and a morphological segmentation
 that splits the hull into the machine's own limbs. That is seconds of work, so
 the result is cached in cache/ and is a few milliseconds thereafter.
 Three levels of detail are built; d cycles them.

 A few thousand facets is not a compromise. At this resolution the model covers
 maybe 150x400 pixels, so it is already one facet per handful of pixels.

 The display has two panels. COMBAT (default, and only with a canon source)
 is what a gunner would want:
 designation, tonnage, loadout, heat sinks, speeds, and the armour spread over
 the machine's five sections. MESH (m) is the renderer's own report -- welded
 vertex count, whether every edge is used exactly twice, the decimation error
 against the source, facets drawn and frame rate.

 Two sources and no third, and every line says which it is. Canon is Sarna's
 and is quoted, never rounded or filled in -- Sarna assigns no body location to
 any Prime weapon, so neither does this program. Everything else is measured
 off the mesh. Where they meet is stated: the armour spread is Sarna's twelve
 tons distributed over MEASURED skin area, and the density is Sarna's 75 tons
 over the measured displacement.

 Canon travels with the mesh and is never assumed. Point this at a bare STL,
 or at a mech directory with no canon.md, and it renders it happily -- but the
 panel drops to SURVEY: measured dimensions, volume, area and section shares,
 and no mass, because mass is not a property of a mesh.

 SCAN is not a progress bar. It fills with BEARING swept since the scan began
 and completes on a full revolution; the percentage beside it is how much of
 the hull actually returned. A bright wipe runs down the target while the sweep
 is live and holds back the geometry it has not reached.

 With --builtin, or with no STL to hand, it draws a mech assembled here out of
 lofted convex hulls on a 17-bone skeleton -- articulated, so j and k walk the
 structure list and e pulls it apart.

 Usage:
   python3 scan.py                      the first mech in mechs/
   python3 scan.py timber_wolf          a named mech
   python3 scan.py --list               what is available
   python3 scan.py path/to/thing.stl    a bare mesh, with no lore attached
   python3 scan.py --builtin            the procedural mech instead
   python3 scan.py --faces 20000        one custom facet budget
   python3 scan.py --palette ice        field | matrix | amber | ice | plasma | blood
   python3 scan.py --stats              print the mesh report and exit
   python3 scan.py --lighting key       cheaper shading, still solid-looking
   (also --tilt --az --dist --speed --fps --blocks --zen --lod --voxels
    --ao-radius --no-ao --no-cache --no-stars --no-shadow --no-idle --frames
    --no-chrome --no-boot --seed --dt --canon --cache-dir --up)

 Live controls (h for the full list):
   f     cockpit chrome: viewport frame, and a bearing tape and elevation
         ladder driven by the camera's real azimuth and tilt.
   b     replay the startup sequence.
   m     panel: combat / mesh
   j k   target section -- NO TARGET, then the five the segmentation found.
         Named as mech sections with canon, geometrically without; see
         mesh/segment.py.
   SPACE pause spin   q quit         h help        0 reset
   <- -> orbit        ^ v tilt       [ ] zoom      , . spin rate
   d     detail       a occlusion    w wireframe   l labels   S shadow
   v     sensor: optical / thermal / lidar / xray. LIDAR is a range return
         drawn as a point cloud; XRAY drops the near skin to a ghost and
         draws the far side bright, with the reactor marked.
   c     cutaway plane, - and = to move the station
   L     lighting: full / key / flat -- key drops the fill light, sheen,
         ambient and fog; flat drops lighting altogether, which on a
         one-material mesh leaves a silhouette.
   r     frame rate cap: 10/15/24/30/60/120/uncapped. Default 60.
   p     palette      1-6 direct     g grid x3     z zen      s stars
   e     explode      i idle -- the built-in model only, and silently inert
         on a loaded mesh, which is one rigid shell with no joints to move.
"""

__version__ = '1.0'
