# Catapult

The CPLT-C1: a jumping fire-support 'Mech whose two Holly LRM 15 launchers sit
in the "ears" either side of the cockpit. In production since 2561, which makes
it one of the oldest designs still fielded.

Everything below is from Sarna and nothing has been rounded, averaged or filled
in. **A field nobody sourced is absent from this file**, and the scanner draws
only the blocks it has data for — so the honest failure mode of an incomplete
canon.md is a shorter readout, never a confident wrong one.

## Model

| field | value         |
| ----- | ------------- |
| stl   | cplt-c1d5.stl |
| up    | z             |

## Identity

| field  | value                |
| ------ | -------------------- |
| name   | CATAPULT             |
| config | CPLT-C1              |
| origin | Hollis Incorporated  |
| intro  | 2561                 |

## Chassis

| field     | value           |
| --------- | --------------- |
| mass_t    | 65              |
| chassis   | Hollis Mark II  |
| engine    | Magna 260       |
| armour    | Durallex Heavy  |
| armour_t  | 10              |
| heatsinks | 15 single       |

## Mobility

| field   | value |
| ------- | ----- |
| cruise  | 43.2  |
| flank   | 64.0  |

## Weapons

| weapon        | count |
| ------------- | ----- |
| LRM-15        | 2     |
| Medium Laser  | 4     |

## Notes

- **The variant is inferred from the mesh filename and may be wrong.** The file
  is `cplt-c1d5.stl`; Sarna lists no CPLT-C1D, so this is read as a CPLT-C1 with
  the sculptor's own revision suffix — the same pattern as `mad-3r4.stl` for the
  MAD-3R. If the mesh is something else, the fix is this file, not the program.
- `flank` is 64.0 because that is the number in Sarna's infobox. The prose gives
  the cruising speed as 43.2 km/h, and 64.0 is not 1.5× that; the infobox has
  evidently dropped a digit somewhere. Quoted as found rather than corrected,
  because correcting it would mean computing it, and computing it is the one
  thing this file may not do.
- No jump field, and the Catapult jumps: four Anderson Model 21 jets in the rear
  side torsos, for 120 metres. There is nowhere to put it on the panel, so it is
  recorded here rather than dropped.
- Sarna names the weapons: two Holly LRM 15 launchers in the ears, four Martell
  medium lasers below the cockpit.
- No `walk_mp` / `run_mp`: the page gives the speeds in km/h and never the
  movement points, and converting one to the other is a rules calculation rather
  than a quotation.

## Sources

- https://www.sarna.net/wiki/Catapult
