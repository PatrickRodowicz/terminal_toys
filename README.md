# terminal_toys

Things that draw on a terminal, in pure Python with no dependencies.

| | |
|---|---|
| [`mech_scanner/`](mech_scanner/) | A BattleMech targeting and diagnostics sight: a mesh rendered at half-block resolution with real occlusion, limb segmentation and four sensor channels. One directory per machine under `mechs/`, each carrying its mesh and a `canon.md` of sourced facts. Has its own [README](mech_scanner/README.md). |
| `dscape.py` | A filesystem as a voxel cityscape, on a guillotine treemap plan. |
| `globe.py` | A dot-matrix spinning Earth. |
| `netmap.py` | Live network cartography. |
| `mech.sh`, `mech2.sh`, `cyberpunk*.sh` | Shell-only ambient dashboards. |

`ideas.md` is the design journal: what was tried, what was measured, and what
was thrown away, per program.
