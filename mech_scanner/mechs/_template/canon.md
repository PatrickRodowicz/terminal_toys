# Machine Name

A directory starting with `_` is skipped by the scanner, so this file is a
document rather than a selectable machine. Copy the directory, drop an STL in
it, and fill this in.

    mechs/my_mech/
        my_mech.stl
        canon.md          <- this file
        reference.png     <- optional, never read by the program

Then:

    python3 scan.py my_mech

## The rules

**Every field needs a source, and the sources go at the bottom.** This program
puts measured geometry and quoted lore on the same screen, and the only thing
that keeps that honest is that each is traceable.

**A field nobody sourced is absent.** Not zero, not a plausible guess. Delete
the row. The panel draws the blocks it has data for and omits the rest, so an
incomplete file gives a shorter readout — never a confident wrong one. There is
no field here you are obliged to supply except `name`; without that there is
nothing to label the machine with, and the scanner falls back to the measured
survey.

**Never derive lore from the mesh, or geometry from the lore.** Do not measure
a limb and write down what you think it weighs. The scanner computes every
measurement itself and will disagree with you.

Anything that is not a table row is prose and is ignored by the parser, so
explain yourself freely — as this file is doing.

## Model

`stl` is optional; without it the scanner takes the only .stl in the directory.
`up` is which axis the file calls up, and is a property of how the mesh was
exported, not of the machine.

| field | value       |
| ----- | ----------- |
| stl   | my_mech.stl |
| up    | z           |

## Identity

Only `name` is required. It is what appears at the top of the panel.

| field    | value        |
| -------- | ------------ |
| name     | MACHINE NAME |
| codename |              |
| config   |              |
| origin   |              |
| intro    |              |

## Chassis

`mass_t` is the whole machine's tonnage and is the number the scanner divides
by its own measured displacement to derive a mean density. `armour_t` is spread
across the sections by *measured skin area* — armour is a skin, so an arm with
more surface per cubic metre gets proportionally more of it.

| field     | value |
| --------- | ----- |
| mass_t    |       |
| chassis   |       |
| engine    |       |
| armour    |       |
| armour_t  |       |
| heatsinks |       |
| podspace  |       |

## Mobility

`cruise` and `flank` are km/h.

| field   | value |
| ------- | ----- |
| walk_mp |       |
| run_mp  |       |
| cruise  |       |
| flank   |       |

## Weapons

Order matters: this is how the loadout is quoted. Give a location only if your
source gives one — and there is currently nowhere to put it, because no source
consulted so far has.

| weapon | count |
| ------ | ----- |
|        |       |

## Notes

Free text. Not displayed; this is for the next person reading the file.

## Sources

- https://example.invalid/where-this-came-from
