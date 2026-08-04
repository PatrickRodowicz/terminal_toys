# Marauder

The MAD-3R: General Motors' attack and direct fire support 'Mech, in production
since the Star League and still the shape most people mean by "heavy 'Mech".
Digitigrade, no hands — the PPCs are the arms.

Everything below is from Sarna and nothing has been rounded, averaged or filled
in. **A field nobody sourced is absent from this file**, and the scanner draws
only the blocks it has data for — so the honest failure mode of an incomplete
canon.md is a shorter readout, never a confident wrong one.

Note what is *not* here. Sarna gives this design's weapon locations, which the
Timber Wolf's page does not — the PPCs and medium lasers in the arm gauntlets,
the AC/5 in the right torso — but the panel has nowhere to put a location, so
they are recorded in Notes below rather than invented into the table. And there
is no `walk_mp` / `run_mp`: the page states the speeds in km/h and never the
movement points, and converting one to the other is a rules calculation, not a
quotation.

## Model

| field | value       |
| ----- | ----------- |
| stl   | mad-3r4.stl |
| up    | z           |

## Identity

| field    | value          |
| -------- | -------------- |
| name     | MARAUDER       |
| config   | MAD-3R         |
| origin   | General Motors |
| intro    | 2819           |

## Chassis

| field     | value           |
| --------- | --------------- |
| mass_t    | 75              |
| chassis   | GM Marauder     |
| engine    | Vlar 300        |
| armour    | Valiant Lamellor|
| armour_t  | 11.5            |
| heatsinks | 16 single       |

## Mobility

| field   | value |
| ------- | ----- |
| cruise  | 43.2  |
| flank   | 64.8  |

## Weapons

| weapon             | count |
| ------------------ | ----- |
| PPC                | 2     |
| Medium Laser       | 2     |
| Autocannon/5       | 1     |

## Notes

- Sarna names the weapons: two Magna Hellstar PPCs and two Magna Mk II medium
  lasers in the arm gauntlets, and a General Motors Whirlwind autocannon/5 in
  the right torso. The table quotes types and counts because that is what the
  panel displays; the manufacturers and locations are here so they are not lost.
- `intro` is the infobox production year for this variant, 2819. The design
  itself is older: the first Marauder was built by General Motors in 2612, and
  the SLDF Royal -1R dates from that year. 2819 is the -3R.
- No `podspace`: it is not an OmniMech, so the field does not apply — as opposed
  to applying and being unknown.
- The engine is described in prose as "a powerful nineteen-ton fusion engine",
  which is a component mass, not the machine's. The scanner's density comes from
  `mass_t` over its own measured displacement and takes nothing from here.

## Sources

- https://www.sarna.net/wiki/Marauder
