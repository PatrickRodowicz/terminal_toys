"""The running sight: state, input, and the frame loop.

The frame loop below reads as a table of contents. Every stage is one call into
render/ or hud/, and the `# ---- name ----` comments are load-bearing: the
profiling harness in tools/ splits the loop on exactly those markers to
attribute frame time, so renaming one silently changes what the numbers mean.

Ordering in the loop is not arbitrary and two of the constraints were bugs:

  * The scan block runs BEFORE the transform. It can swap the level of detail,
    and `world` is built from `parts` -- changing one after the other has been
    computed leaves the two indexed against different meshes.
  * `drawn` is taken before the instrument channels consume the queue, so the
    mesh panel reports the same facet count in every channel.
"""
import math
import os
import random
import shutil
import signal
import sys
import time

from . import canon as canon_mod
from .acquire import Acquisition
from .ansi import BG_DEF, CLEAR, FG_DEF, HIDE, HOME, RESET, SHOW, quant, shade
from .emit import emit
from .hud import acquire as acquire_hud
from .hud import boot as boot_hud
from .hud import chrome as chrome_hud
from .hud import help as help_hud
from .hud import panels, reticle
from .hud.overlay import Overlay
from .keyboard import Keyboard
from .lighting import LIGHT_ARGS, LIGHT_NAMES
from .mesh.builtin import pose_mech
from .mesh.model import LOD_NAMES, LOD_TARGETS
from .mesh.segment import SECTIONS, section_names
from .palettes import PALETTES, PAL_NAMES, palette_materials
from .raster import Raster
from .render import facets, scene
from .render.camera import Camera
from .render.sensors import SENSOR_NAMES
from .render.view import View
from .rig import Rig
from .sweep import Scan
from .text import commas

GRID_SOLID, GRID_XRAY, GRID_OFF = 0, 1, 2
GRID_NAMES = ('GRID', 'GRID X-RAY', 'GRID OFF')

# The frame rate cap, and the rungs `r` steps through. This is an ambient
# display meant to sit in the corner of a screen, so the cap is a real control
# and not a formality: at 200x60 the renderer will happily eat a core to draw
# frames nobody is looking at. 0 means uncapped, which is only useful for
# measurement -- and it is on the ladder so a harness can reach it by keypress
# as well as by flag.
FPS_LADDER = (10.0, 15.0, 24.0, 30.0, 60.0, 120.0, 0.0)


def _fps_label(f):
    return 'UNCAPPED' if not f else '%g FPS' % f


def build_rig(mech, args, note=None, lod=None):
    """A mech directory becomes a Rig. The ONE place that conversion happens.

    Both callers need it and they run in very different places -- the command
    line, once, printing to the terminal; and the acquisition worker thread,
    collecting the same messages into a readout -- which is exactly why it
    should not be written twice with a chance of drifting apart.
    """
    return Rig.from_stl(
        mech.stl, targets=(args.faces,) if args.faces else LOD_TARGETS,
        up=args.up or mech.up, ao_radius=args.ao_radius, vox=args.voxels,
        no_ao=args.no_ao, note=note, use_cache=not args.no_cache,
        lod=args.lod if lod is None else lod, canon=mech.canon,
        cache_dir=args.cache_dir)


def designation(rig, fallback):
    """What to call the machine on screen: its canon name, or its directory."""
    if rig.canon and rig.canon.get('name'):
        return str(rig.canon['name'])
    return fallback.replace('_', ' ').upper()


class App:
    """One running sight. Owns the terminal; put it in a try/finally."""

    def __init__(self, rig, args, mech=None):
        self.rig = rig
        self.args = args
        # Which machine is loaded, or None for the built-in. Needed to know
        # where in mechs/ the n key is stepping FROM; the rig only knows its
        # own mesh path.
        self.mech = mech
        self.acq = None
        self.subx = 2 if args.blocks == 'quad' else 1

        self.pal = args.palette
        self.P = PALETTES[self.pal]
        self.mat = palette_materials(self.pal)

        self.az = math.radians(args.az)
        self.el = math.radians(args.tilt)
        self.dist = args.dist
        self.zoom = 1.0
        self.spin = args.speed
        self.paused = False
        self.grid_mode = GRID_SOLID
        self.zen = args.zen
        self.stars_on = not args.no_stars
        self.shadow_on = not args.no_shadow
        self.idle_on = not args.no_idle
        self.light_mode = LIGHT_ARGS.index(args.lighting)
        self.sensor = SENSOR_NAMES.index(args.sensor.upper())
        self.cutaway = False
        self.cut_z = 0.55
        self.labels = False
        self.wire = False
        self.explode = 0.0
        self.explode_t = 0.0
        self.ao_on = not args.no_ao
        # -1 is NO TARGET, and it is the state you start in. It is a real
        # state, not a sentinel to skip past: a gunner who wants the whole
        # machine and no section highlighted has to be able to get there.
        self.sel = -1
        self.panel_mode = 0        # 0 combat, 1 mesh
        self.show_help = False

        self.chrome_on = not args.no_chrome
        self.crew = chrome_hud.Crew(args.seed)
        self.booting = not args.no_boot
        self.boot_t0 = None

        self.scan = Scan()
        self.flash, self.flash_until = '', 0.0

        self.cam = Camera(self.subx)
        self.kb = Keyboard()
        self.ras = None
        self.cols = self.rows = 0
        self.stars = []
        self.rng = random.Random(7)

        self.sim = 0.0
        self.frame = 0
        # The cap, which is adjustable; distinct from fps_avg, which is
        # the measured rate and only ever a readout.
        self.fps_cap = max(0.0, args.fps)
        self.fps_avg = args.fps or 60.0
        self.drawn = 0

        self._restored = False
        self._quitting = []        # set by a signal, drained by the frame loop

    # -- terminal ----------------------------------------------------------
    def cleanup(self, *_):
        """Teardown must finish come what may: it is the only thing that puts
        the cursor, colours and terminal mode back. Go deaf first, then retry
        once, because a signal already in flight can land between entering here
        and the SIG_IGN taking effect."""
        if self._restored:
            return
        self._restored = True
        for sg in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            try:
                signal.signal(sg, signal.SIG_IGN)
            except Exception:
                pass
        for _attempt in (0, 1):
            try:
                self.kb.restore()
                sys.stdout.write(SHOW + RESET + BG_DEF + FG_DEF + CLEAR + HOME)
                sys.stdout.flush()
                return
            except BaseException:
                continue

    def install_signals(self):
        """A signal handler must not touch sys.stdout.

        The emitter holds the BufferedWriter's lock for most of every frame --
        one 20 KB write into a pty -- and re-entering it from a handler raises
        RuntimeError, which a defensive `except Exception: pass` around the
        teardown then swallows. The result is a process that exits 0 having
        restored nothing: raw mode still set, cursor still hidden. Measured at
        60 teardowns out of 60 before this changed. So the handler only records
        the request, and the frame loop tears down at the top of the next
        iteration, where nothing is half-written and the lock is free.
        """
        for sg in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            try:
                signal.signal(sg, lambda *_: self._quitting.append(True))
            except Exception:
                pass

    def _resize(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.ras = Raster(cols * self.subx, rows * 2)
        sy_max = int(rows * 2 * 0.62)
        rng = self.rng
        self.stars = [(rng.randrange(cols * self.subx), rng.randrange(sy_max),
                       rng.random(), rng.random() * 6.283)
                      for _ in range(int(cols * rows * 0.05))]
        sys.stdout.write(CLEAR)

    def _say(self, msg, now, hold=0.8):
        self.flash, self.flash_until = msg, now + hold

    # -- input -------------------------------------------------------------
    def _key(self, k, now):
        args, rig = self.args, self.rig
        if k == ' ':
            self.paused = not self.paused
            self._say('PAUSED' if self.paused else 'RUNNING', now)
        elif k == 'LEFT':
            self.az -= 0.12
        elif k == 'RIGHT':
            self.az += 0.12
        elif k == 'UP':
            self.el = min(math.radians(78), self.el + 0.05)
        elif k == 'DOWN':
            self.el = max(math.radians(-25), self.el - 0.05)
        elif k == '[':
            self.zoom = max(0.35, self.zoom / 1.09)
        elif k == ']':
            self.zoom = min(4.5, self.zoom * 1.09)
        elif k == ',':
            self.spin = max(-6.0, self.spin - 0.25)
            self._say(f'SPIN {self.spin:+.2f}', now)
        elif k == '.':
            self.spin = min(6.0, self.spin + 0.25)
            self._say(f'SPIN {self.spin:+.2f}', now)
        elif k in ('j', '\t', 'k'):
            # Alive on a loaded mesh too: the shell is one watertight body, but
            # it has been segmented into the machine's own limbs, so there is
            # something to select between after all.
            n_sel = len(SECTIONS) if rig.stl_mode else len(rig.parts)
            # Skip sections the segmentation did not find. A machine whose arms
            # never part from its trunk has no arm to target, and stepping onto
            # an empty one would report it at 0.0 t as though it had been shot
            # off. NO TARGET (-1) is always in the cycle.
            pres = (rig.report or {}).get('sec_present') if rig.stl_mode else None
            for _ in range(n_sel + 1):
                self.sel = (self.sel + (2 if k != 'k' else 0)) % (n_sel + 1) - 1
                if pres is None or self.sel < 0 or self.sel in pres:
                    break
            if rig.stl_mode:
                self._say('NO TARGET' if self.sel < 0 else
                          section_names(rig.canon)[SECTIONS[self.sel]].upper(),
                          now)
        elif k in ('n', 'N'):
            self._cycle_mech(1 if k == 'n' else -1, now)
        elif k == 'b':
            self.booting, self.boot_t0 = True, now
        elif k == 'f':
            self.chrome_on = not self.chrome_on
            self._say('CHROME ON' if self.chrome_on else 'CHROME OFF', now)
        elif k == 'm':
            self.panel_mode = (self.panel_mode + 1) % 2
            self._say(('COMBAT', 'MESH')[self.panel_mode] + ' PANEL', now)
        elif k == 'e':
            # Explode is a displacement of PARTS. A loaded mesh is one rigid
            # shell with no joints to pull apart, so: silently inert.
            if not rig.stl_mode:
                self.explode_t = 0.0 if self.explode_t > 0.5 else 1.0
                self._say('EXPLODED' if self.explode_t else 'ASSEMBLED', now,
                          0.9)
        elif k == 'd':
            if rig.stl_mode and len(rig.lods) > 1:
                rig.set_lod(rig.lod_i + 1)
                self.sel = -1
                self.scan.restart()      # different mesh, different hull
                self._say('%s  %s FACETS'
                          % (LOD_NAMES[rig.lod_i] if rig.lod_i < len(LOD_NAMES)
                             else 'LOD %d' % rig.lod_i,
                             commas(len(rig.parts[0].faces))), now, 1.1)
        elif k == 'a':
            self.ao_on = not self.ao_on
            self._say('OCCLUSION ON' if self.ao_on else 'OCCLUSION OFF', now,
                      0.9)
        elif k == 'w':
            self.wire = not self.wire
            self._say('WIREFRAME' if self.wire else 'SOLID', now)
        elif k == 'l':
            self.labels = not self.labels
        elif k == 'L':
            self.light_mode = (self.light_mode + 1) % 3
            self._say(LIGHT_NAMES[self.light_mode], now, 0.9)
        elif k == 'v':
            self.sensor = (self.sensor + 1) % len(SENSOR_NAMES)
            self._say('SENSOR ' + SENSOR_NAMES[self.sensor], now, 0.9)
        elif k == 'c':
            self.cutaway = not self.cutaway
            self._say('CUTAWAY' if self.cutaway else 'CUTAWAY OFF', now)
        elif k == '-':
            self.cut_z = max(0.02, self.cut_z - 0.04)
        elif k == '=':
            self.cut_z = min(0.99, self.cut_z + 0.04)
        elif k == 'S':
            self.shadow_on = not self.shadow_on
            self._say('SHADOW ON' if self.shadow_on else 'SHADOW OFF', now)
        elif k == 'g':
            self.grid_mode = (self.grid_mode + 1) % 3
            self._say(GRID_NAMES[self.grid_mode], now)
        elif k == 's':
            self.stars_on = not self.stars_on
        elif k == 'i':
            # Idle is a pose on the built-in skeleton. A loaded mesh has no
            # joints to move, so: silently inert.
            if not rig.stl_mode:
                self.idle_on = not self.idle_on
                self._say('IDLE ON' if self.idle_on else 'IDLE OFF', now)
        elif k == 'r':
            # Nearest rung above the current cap, wrapping. Nearest rather than
            # an index, because --fps can start it anywhere.
            cur = self.fps_cap
            nxt = [f for f in FPS_LADDER if f > cur] or [FPS_LADDER[0]]
            self.fps_cap = 0.0 if cur and cur >= max(FPS_LADDER[:-1]) else nxt[0]
            self._say(_fps_label(self.fps_cap), now, 0.9)
        elif k == 'z':
            self.zen = not self.zen
        elif k in ('h', '?'):
            self.show_help = not self.show_help
        elif k == 'p':
            self._set_palette(
                PAL_NAMES[(PAL_NAMES.index(self.pal) + 1) % len(PAL_NAMES)],
                now)
        elif k in '123456':
            self._set_palette(PAL_NAMES[int(k) - 1], now)
        elif k == '0':
            self.az = math.radians(args.az)
            self.el = math.radians(args.tilt)
            self.zoom, self.spin = 1.0, args.speed
            self.dist, self.explode_t, self.wire = args.dist, 0.0, False
            self.grid_mode, self.paused = GRID_SOLID, False
            self.sel = -1                 # target dropped, scan rerun
            self.scan.restart()
            self.scan.sweep = 0.0
            self._say('RESET', now)
        elif k == 'ESC':
            self.show_help = False

    # -- changing target ---------------------------------------------------
    def _cycle_mech(self, step, now):
        """Step through mechs/ and start acquiring the next one.

        Deliberately inert while an acquisition is already running: the
        readout on screen is already saying what is happening, so a flash
        saying it again is noise, and queueing a second build behind the first
        would mean a keypress with an effect several seconds later.
        """
        if self.acq is not None:
            return
        names = canon_mod.available()
        if not names:
            self._say('NO MECHS IN %s' % os.path.basename(canon_mod.mechs_dir()),
                      now, 1.6)
            return
        cur = os.path.basename(self.mech.dir) if self.mech else None
        if cur in names:
            if len(names) == 1:
                self._say('NO OTHER MECH', now, 1.2)
                return
            i = (names.index(cur) + step) % len(names)
        else:
            # Started on the built-in, or on a bare .stl from outside mechs/.
            # Either way there is no position in the cycle to step from, so
            # enter it at whichever end the direction implies.
            i = 0 if step > 0 else len(names) - 1
        try:
            mech = canon_mod.load_dir(
                os.path.join(canon_mod.mechs_dir(), names[i]),
                use_canon=self.args.canon != 'none')
        except (OSError, ValueError) as e:
            self._say('CANNOT LOAD %s: %s' % (names[i], e), now, 2.6)
            return
        args = self.args
        lod = self.rig.lod_i if self.rig.stl_mode else args.lod

        def build(note):
            return build_rig(mech, args, note=note, lod=lod)

        self.acq = Acquisition(names[i], mech, build)

    def _swap_rig(self, rig, name, now):
        """Adopt a freshly built rig. Called from the frame loop only."""
        self.rig = rig
        self.sel = -1
        # A new machine is a new target, so the sweep starts over: the wipe
        # runs down the new hull and the lock brackets stay dim until it has
        # actually been seen. restart() is not optional -- both rigs have one
        # part in stl_mode, so Scan.bind would find the count unchanged and
        # keep scoring the new mesh against the old hull's facet arrays.
        self.scan.restart()
        self.scan.sweep = 0.0
        self._say('LOCK · %s' % designation(rig, name), now, 1.8)
        return rig

    def _set_palette(self, name, now):
        self.pal = name
        self.P = PALETTES[name]
        self.mat = palette_materials(name)
        self._say(name.upper(), now, 0.9)

    # -- the loop ----------------------------------------------------------
    def run(self):
        args, rig = self.args, self.rig
        sys.stdout.write(HIDE + CLEAR)
        t0 = time.time()
        last = t0
        try:
            while True:
                if self._quitting:
                    break
                now = time.time()
                # --dt pins the clock so a pixel-diff harness can compare two
                # runs. Left off, two runs land at different azimuths and the
                # comparison measures the host's speed, not the renderer.
                dt = args.dt or min(0.2, now - last)
                last = now
                if not self.paused:
                    self.sim += dt * self.spin

                sz = shutil.get_terminal_size((100, 30))
                if sz.columns != self.cols or sz.lines != self.rows:
                    self._resize(max(24, sz.columns), max(10, sz.lines))
                cols, rows = self.cols, self.rows
                pxw, pxh = cols * self.subx, rows * 2
                ras = self.ras
                ov = Overlay(rows, cols)

                # ---- input ----
                for k in self.kb.poll():
                    if k in ('q', 'Q'):
                        raise KeyboardInterrupt
                    elif self.booting and k != 'b':
                        # Anything at all skips the POST. Nobody wants to sit
                        # through a boot screen twice, and a sequence you
                        # cannot interrupt is a sequence you come to resent.
                        self.booting = False
                        continue
                    self._key(k, now)

                # ---- acquire ----
                # The swap happens HERE, at the top of the frame, before
                # anything below has read `rig`. Half a frame drawn against the
                # old mesh and half against the new is the same class of bug
                # Scan.bind already guards against, and `rig` is a local bound
                # once outside the loop, so it has to be rebound by hand.
                if self.acq is not None:
                    new = self.acq.ready(now)
                    if new is not None:
                        rig = self._swap_rig(new, self.acq.name, now)
                        self.mech = self.acq.mech
                        self.acq = None
                    elif self.acq.spent(now):
                        self._say('NO LOCK · %s'
                                  % self.acq.name.replace('_', ' ').upper(),
                                  now, 2.0)
                        self.acq = None

                self.explode += (self.explode_t - self.explode) \
                    * min(1.0, dt * 4.0)
                if not self.paused:
                    self.az += dt * self.spin * 0.32

                # ---- camera ----
                panel = 0 if self.zen else min(26, max(0, cols // 4))
                panel_px = panel * self.subx
                cam = self.cam
                cam.update(self.az, self.el, self.dist, self.zoom, rig.ext,
                           self.explode, panel_px, pxw - panel_px, pxh)
                ext = rig.ext
                cutplane = (ext.mz0 + (ext.mz1 - ext.mz0) * self.cut_z) \
                    if self.cutaway else None
                view = View(rig.stl_mode, self.zen, self.sensor,
                            self.light_mode, self.pal, self.mat, self.P,
                            self.ao_on, cutplane, self.dist, ext.mrad)

                # ---- sky ----
                scene.draw_sky(ras, self.P, pxh, self.stars, self.stars_on,
                               self.sim, view.nosun)

                # ---- ground plane and grid ----
                GR = ext.mrad * 3.4
                scene.draw_ground(ras, cam, self.P, GR, view.nosun)
                if self.grid_mode == GRID_SOLID:
                    scene.draw_grid(ras, cam, GR,
                                    quant(shade(self.P['grid'], 0.9)))

                # ---- scan state ----
                # Ahead of the transform, not after it: this block can swap the
                # level of detail, and `world` below is built from `parts`.
                scan = self.scan
                scan.bind(rig.parts, self.az)
                scan.advance(self.az)
                wipey = scan.wipe_y(self.sim, pxh)

                # ---- pose and transform ----
                if not rig.stl_mode:
                    pose_mech(rig.frames, self.sim, self.idle_on)
                for f in rig.order:
                    f.resolve()
                world = facets.world_vertices(rig.parts,
                                              self.explode * ext.mrad * 1.15)

                # ---- cast shadow ----
                scene.draw_shadow(ras, cam, self.P, rig, world, self.explode,
                                  self.shadow_on, view.nosun)
                if self.grid_mode == GRID_XRAY:
                    scene.draw_grid(ras, cam, GR,
                                    quant(shade(self.P['grid'], 1.9)))

                # ---- gather faces ----
                sel_part = (rig.parts[self.sel]
                            if (rig.parts and not rig.stl_mode
                                and self.sel >= 0) else None)
                queue, scan.left = facets.gather(
                    rig.parts, world, cam, view, self.sel, sel_part,
                    scan.seen, scan.left)
                self.drawn = len(queue)

                # ---- shade and fill ----
                sil = [1e9, 1e9, -1e9, -1e9]        # silhouette box, screen px
                if view.wireonly:
                    facets.draw_instrument(
                        ras, queue, cam, view, sil, self.sim,
                        rig.report.get('reactor_m') if rig.report else None)
                else:
                    facets.draw_solid(ras, queue, view, sil, wipey, self.wire)

                # ---- overlay ----
                self._draw_panels(ov, panel, world, cam, now)

                # ---- targeting frame ----
                if not self.zen and sil[2] > sil[0]:
                    reticle.draw_brackets(ov, self.P, sil, panel, rows, cols,
                                          self.subx, not scan.sweeping)
                    # ---- instrument strip ----
                    reticle.draw_strip(
                        ov, self.P, cols, self.sensor, scan, rig.report,
                        rig.parts, self.sel,
                        math.degrees(self.az) % 360.0, math.degrees(self.el),
                        self.dist, rig.mass, rig.canon)

                # ---- cockpit chrome ----
                if self.chrome_on and not self.zen:
                    chrome_hud.draw(ov, self.P, panel, rows, cols, self.crew,
                                    self.az, self.el, wipey, now)

                # ---- flash ----
                # After the chrome, not before it. Row 2, not row 1: the crew
                # line owns the right end of row 1 and a flash landing on it
                # read as a rendering fault. But row 2 carries the viewport
                # frame, which was drawn straight through 'LOCK · ARCHER' and
                # broke it in half -- and an alert that the decoration can cut
                # up is not an alert. It goes on top of everything but the
                # readouts that are themselves modal.
                if self.flash and now < self.flash_until:
                    ov.text(2, max(0, cols - len(self.flash) - 3),
                            ' ' + self.flash + ' ', self.P['panel'],
                            self.P['alert'])

                # ---- acquisition readout ----
                # Over the viewport and not over the screen: the whole point of
                # building on a worker thread is that the sight keeps running,
                # and covering it would throw that away.
                if self.acq is not None:
                    acquire_hud.draw(ov, self.P, rows, cols, panel,
                                     self.acq, now)

                # ---- boot sequence ----
                if self.booting:
                    if self.boot_t0 is None:
                        self.boot_t0 = now
                    checks = boot_hud.checklist(rig.report, len(rig.parts),
                                                rig.canon)
                    self.booting = boot_hud.draw(ov, self.P, rows, cols,
                                                 checks, now - self.boot_t0)

                if self.show_help:
                    help_hud.draw(ov, self.P, rows, cols)

                # ---- paint ----
                sys.stdout.write(emit(ras, ov, rows, cols, self.subx))
                sys.stdout.flush()

                self.frame += 1
                if args.frames and self.frame >= args.frames:
                    break
                el_t = time.time() - now
                self.fps_avg += (1.0 / max(el_t, 1e-3) - self.fps_avg) * 0.1
                if self.fps_cap:
                    time.sleep(max(0.0, 1.0 / self.fps_cap - el_t))
        except (KeyboardInterrupt, BrokenPipeError):
            pass
        finally:
            self.cleanup()

    # -- overlay -----------------------------------------------------------
    def _draw_panels(self, ov, panel, world, cam, now):
        if self.zen:
            return
        rig, P = self.rig, self.P
        H, PN = P['hud'], P['panel']
        rows, cols = self.rows, self.cols
        # Row 0 is the instrument strip and nothing else. It used to carry a
        # facet count and a draw count in the top right of a TARGETING display
        # -- and they were painted over by the strip every frame anyway, so the
        # only thing lost by deleting them is a line of dead code. Numbers
        # about the renderer belong in the mesh panel.
        ov.text(0, 0, ' ' * cols, H, PN)
        if panel > 4:
            if rig.stl_mode and self.panel_mode == 0:
                panels.draw_combat(ov, P, panel, rows, rig.report, self.sel,
                                   rig.canon)
            elif rig.stl_mode:
                panels.draw_mesh(ov, P, panel, rows, rig.report, rig.name,
                                 rig.lod_i, self.ao_on, self.drawn,
                                 self.fps_avg, rig.mass)
            else:
                panels.draw_structure(ov, P, panel, rows, rig.parts, self.sel,
                                      sum(p.mass for p in rig.parts))

        if self.labels:
            for pi, p in enumerate(rig.parts):
                wv = world[pi]
                cx = sum(w[0] for w in wv) / len(wv)
                cy = sum(w[1] for w in wv) / len(wv)
                cz = max(w[2] for w in wv)
                s = cam.project(cx, cy, cz + 0.2)
                c0 = int(s[0] / self.subx) - len(p.name) // 2
                r0 = int(s[1] / 2)
                if 1 <= r0 < rows - 1 and c0 > panel:
                    ov.text(r0, c0, p.name,
                            P['sel'] if pi == self.sel else H, None)
