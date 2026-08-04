# Atlas

The AS7-D. Built to Aleksandr Kerensky's own specification in 2755: "A 'Mech as
powerful as possible, as impenetrable as possible, and as ugly and foreboding as
conceivable, so that fear itself will be our ally." The death's-head cockpit is
the whole design brief in one line.

Everything below is from Sarna and nothing has been rounded, averaged or filled
in. **A field nobody sourced is absent from this file**, and the scanner draws
only the blocks it has data for — so the honest failure mode of an incomplete
canon.md is a shorter readout, never a confident wrong one.

## Model

| field | value    |
| ----- | -------- |
| stl   | as7-d4.stl |
| up    | z        |

## Identity

| field  | value  |
| ------ | ------ |
| name   | ATLAS  |
| config | AS7-D  |
| origin | SLDF   |
| intro  | 2755   |

## Chassis

| field     | value                   |
| --------- | ----------------------- |
| mass_t    | 100                     |
| chassis   | Foundation Type 10X     |
| engine    | Vlar 300                |
| armour    | Durallex Special Heavy  |
| armour_t  | 19                      |
| heatsinks | 20 single               |

## Mobility

| field   | value |
| ------- | ----- |
| cruise  | 32.4  |
| flank   | 54.0  |

## Weapons

| weapon         | count |
| -------------- | ----- |
| Autocannon/20  | 1     |
| LRM-20         | 1     |
| SRM-6          | 1     |
| Medium Laser   | 4     |

## Notes

- Sarna names the weapons: a Defiance 'Mech Hunter AC/20, a FarFire Maxi-Rack
  LRM 20, a TharHes Maxi SRM 6 and four Defiance B3M medium lasers. The table
  quotes types and counts because that is what the panel displays; the
  manufacturers are here so they are not lost.
- `origin` is the SLDF because the design was commissioned to Kerensky's
  specification for it. Manufacture was never single-source: Sarna lists
  Defiance Industries, Independence Weaponry, Robinson Standard BattleWorks and
  Yori 'Mech Works, which is why no one of them is named as the origin.
- Sarna notes the armouring is "particularly thick on the front chest and legs".
  The scanner spreads the nineteen tons by *measured skin area* and knows
  nothing about that distribution, so its per-section figures are the even
  spread, not the Atlas's actual one.
- No `walk_mp` / `run_mp`: the page gives the speeds in km/h and never the
  movement points, and converting one to the other is a rules calculation rather
  than a quotation.

## Sources

- https://www.sarna.net/wiki/Atlas
