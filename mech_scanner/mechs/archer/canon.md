# Archer

The ARC-2R: a missile boat that has been in production since 2474, with a
Doombud LRM 20 in each side torso behind hinged bay doors — which is what the
mesh has open.

Everything below is from Sarna and nothing has been rounded, averaged or filled
in. **A field nobody sourced is absent from this file**, and the scanner draws
only the blocks it has data for — so the honest failure mode of an incomplete
canon.md is a shorter readout, never a confident wrong one.

## Model

| field | value                     |
| ----- | ------------------------- |
| stl   | arc-1a-doors-open4.stl    |
| up    | z                         |

## Identity

| field  | value                   |
| ------ | ----------------------- |
| name   | ARCHER                  |
| config | ARC-2R                  |
| origin | Earthwerks Incorporated |
| intro  | 2474                    |

## Chassis

| field     | value            |
| --------- | ---------------- |
| mass_t    | 70               |
| chassis   | Earthwerk Archer |
| engine    | VOX 280          |
| armour    | Maximillian 100  |
| armour_t  | 13               |
| heatsinks | 10 single        |

## Mobility

| field   | value |
| ------- | ----- |
| cruise  | 44.1  |
| flank   | 64.8  |

## Weapons

| weapon        | count |
| ------------- | ----- |
| LRM-20        | 2     |
| Medium Laser  | 4     |

## Notes

- **The variant here does not match the mesh filename, deliberately.** The file
  is `arc-1a-doors-open4.stl`, but the ARC-1A is the 2458 Terran Hegemony
  prototype built with primitive technology, and Sarna publishes no stat line
  for it at all — so quoting the -1A would mean quoting nothing. These are the
  standard ARC-2R's figures, which is what the rest of this STL set is (MAD-3R,
  AS7-D, CPLT-C1) and what the open bay doors belong to. If the mesh really is
  the prototype, the fix is this file, not the program.
- The bay doors are canon and so is closing them: "some Archer pilots were known
  to keep their missile bay doors closed in order to fool the enemy, but this
  trick has since lost its effect."
- Sarna names the weapons: two Doombud LRM 20 launchers with 480 rounds between
  them, and four Diverse Optics Type 18 medium lasers.
- `cruise` is 44.1 km/h as the page states it. That is not 10.8 × an integer, so
  it does not correspond to a whole number of movement points; quoted as found.
- `origin` is Earthwerks because Sarna lists it first and the chassis is an
  "Earthwerk Archer". Production has been very widely licensed since — Bowie,
  Defiance, Diplass, Gorton/Kingsley/Thorpe, LexaTech and Vandenberg are all
  listed — so the single name is the origin and not the whole story.
- No `walk_mp` / `run_mp`: the page gives the speeds in km/h and never the
  movement points, and converting one to the other is a rules calculation rather
  than a quotation.

## Sources

- https://www.sarna.net/wiki/Archer
