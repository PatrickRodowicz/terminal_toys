# hackertime — idea list

Terminal ambiance with a hacker bent. House rules that have worked so far:
pure-Python stdlib, no pip installs, no runtime network calls, data baked in at
build time where possible, and **real data wherever we can get it** — the things
that read best are the ones that are actually true.

Status as of 2026-07-24.

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

---

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
mesh. Low novelty now that the sphere exists, but nearly free.

*Effort:* tiny.

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

Both programs now duplicate: ANSI/SGR helpers with colour caching, the
framebuffer and run-length emitter, the raw-mode non-blocking keyboard, the
palette structure, and the layer/z-buffer idea. If a third program happens,
pulling these into a small shared module is the obvious move — though it does
cost the single-file portability that makes these easy to `scp` around.

Contrast tuning matters more than it sounds: colours were measured against an
actual screenshot of the target terminal, because a translucent background over
a wallpaper makes anything below ~3:1 contrast effectively invisible.
