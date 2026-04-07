#!/usr/bin/env python3
"""
Glove80 MIDI Bridge — macOS Menu Bar App

A tray app that turns the Glove80 into a MIDI instrument.
Key features:
  - Start/Stop bridge from the menu bar
  - Bypass mode: suppresses ALL Glove80 keys when active (no OS shortcuts)
  - Scale, root note, octave, velocity, channel selection
  - Panic button (all notes off)
  - Keyboard type detection (isolate Glove80 from built-in keyboard)

Requirements:
    pip install python-rtmidi pyobjc-framework-Quartz rumps
"""

import sys
import os
import time
import threading
import logging

import rumps

# Global debug logger — set GLOVE80_DEBUG=1 to enable
_log = logging.getLogger('glove80')
if os.environ.get('GLOVE80_DEBUG'):
    _log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug.log')
    _handler = logging.FileHandler(_log_path, mode='w')
    _handler.setFormatter(logging.Formatter('%(message)s'))
    _log.addHandler(_handler)
    _log.setLevel(logging.DEBUG)
else:
    _log.addHandler(logging.NullHandler())
    _log.setLevel(logging.CRITICAL)

from midi_output import create_midi_output
from physical_layout import (
    R1_CONTROLS,
    CONTROL_KEYS,
    GRID_POSITION,
    THUMB_POSITION,
    R6_BASS,
    R6_BASS_NOTES,
    KEY_BASS_SEMI_DN,
    KEY_BASS_SEMI_UP,
    KEY_MODE_TOGGLE,
    KEY_MODE_TOGGLE_RH,
    build_note_map,
    build_isomorphic_from_anchor,
    notational_iso_anchor_pitch,
    note_name,
    NOTE_NAMES as PITCH_NAMES,
)
from config import load_config, save_config
from hid_reader_macos import MacOSKeyCapture, detect_keyboard_types, get_usb_keyboards


# ---------------------------------------------------------------------------
# Pitch Bend Glide Engine
# ---------------------------------------------------------------------------

PITCH_BEND_CENTER = 8192
GLIDE_STEPS = 15
GLIDE_INTERVAL = 0.013  # ~13ms per step → ~200ms total glide
TAP_THRESHOLD = 0.25    # seconds — release faster than this = tap (permanent)


class PitchGlide:
    """Manages smooth pitch bend glide for one zone (MIDI channel).

    Set Ableton's pitch bend range to ±12 semitones for full octave glides.
    """

    def __init__(self, raw_send, channel, bend_range=12):
        self._raw_send = raw_send
        self._channel = channel
        self._bend_range = bend_range  # semitones in each direction
        self._units_per_semi = PITCH_BEND_CENTER / bend_range
        self._current_bend = PITCH_BEND_CENTER
        self._target_bend = PITCH_BEND_CENTER
        self._glide_thread = None
        self._glide_gen = 0  # incremented on each _start_glide for thread versioning
        self._stop_flag = False
        self._at_target = False

    def update(self, raw_send, channel):
        self._raw_send = raw_send
        self._channel = channel

    def glide_semitones(self, semitones):
        """Glide by N semitones from current resting position (center)."""
        offset = int(semitones * self._units_per_semi)
        self._target_bend = max(0, min(16383, PITCH_BEND_CENTER + offset))
        self._at_target = False
        self._start_glide()

    def glide_to_center(self):
        """Glide back to center (no pitch offset)."""
        self._target_bend = PITCH_BEND_CENTER
        self._at_target = False
        self._start_glide()

    def snap_to_center(self):
        """Instantly reset to center — used after tap commits the shift."""
        self._glide_gen += 1  # invalidate any running glide thread
        self._current_bend = PITCH_BEND_CENTER
        self._target_bend = PITCH_BEND_CENTER
        self._at_target = True
        self._send_bend(PITCH_BEND_CENTER)

    def reset(self):
        """Full reset — stop everything, center immediately."""
        self.snap_to_center()

    def _start_glide(self):
        # Signal any existing glide thread to stop at its next tick by giving
        # it a unique generation ID. The old thread captures its gen at launch;
        # a new _start_glide increments the gen so the old thread exits on its
        # next tick. Do NOT join — this runs on the CGEventTap callback thread
        # and a blocking join injects up to 50ms latency into every key event.
        self._glide_gen += 1
        self._glide_thread = threading.Thread(
            target=self._glide_loop, args=(self._glide_gen,), daemon=True
        )
        self._glide_thread.start()

    def _glide_loop(self, my_gen):
        start = self._current_bend
        target = self._target_bend
        delta = target - start
        if delta == 0:
            self._at_target = True
            return
        step = delta / GLIDE_STEPS
        for i in range(GLIDE_STEPS):
            # Exit if a newer glide has started (versioned via _glide_gen)
            # or if snap_to_center signalled a hard stop.
            if self._stop_flag or self._glide_gen != my_gen:
                return
            self._current_bend = int(start + step * (i + 1))
            self._send_bend(self._current_bend)
            time.sleep(GLIDE_INTERVAL)
        self._current_bend = target
        self._send_bend(target)
        self._at_target = True

    def _send_bend(self, value):
        raw = self._raw_send
        if raw:
            lsb = value & 0x7F
            msb = (value >> 7) & 0x7F
            raw([0xE0 | self._channel, lsb, msb])


class Glove80TrayApp(rumps.App):
    """macOS menu bar app for the Glove80 MIDI Bridge."""

    def __init__(self):
        super().__init__(
            name="Glove80 MIDI",
            title="G80",
            quit_button=None,
        )

        self.config = load_config()
        self.midi_port = None
        self.key_capture = None
        self.bridge_active = False
        self.bypass_active = True  # When True, ALL Glove80 keys are suppressed

        # Per-zone octave offsets
        self.lh_octave = self.config.get('lh_octave', 0)
        self.rh_octave = self.config.get('rh_octave', 0)
        self.thumb_octave = self.config.get('thumb_octave', 0)

        # Build zone lookup: keycode → zone index (0=lh, 1=rh, 2=thumb)
        self._key_zones = {}
        for kc, (row, col) in GRID_POSITION.items():
            self._key_zones[kc] = 0 if col < 6 else 1
        for kc in THUMB_POSITION:
            self._key_zones[kc] = 2
        for kc in R6_BASS:
            self._key_zones[kc] = 2  # R6 bass = thumb zone

        self.note_map = {}
        # Flat 256-slot array for O(1) active note tracking (no dict hash).
        # Index = evdev keycode, value = (midi_note, channel) or None.
        self._active_notes = [None] * 256
        # Sequence counter for last-pressed anchor ordering (replaces wall time).
        self._last_note_seq = 0
        # Lock protecting note_map / _fast_lookup rebuilds from concurrent
        # access in the CGEventTap callback thread. Uncontested during
        # steady-state play, only held briefly during rebuild.
        self._note_map_lock = threading.RLock()

        # Fast lookup: pre-computed array indexed by evdev keycode
        self._fast_lookup = [None] * 256
        self._velocity = self.config.get('velocity', 92)  # fallback from tray menu
        self._raw_send = None

        # Sticky 3-state velocity system
        self._current_velocity = 92  # starts normal
        # Per-zone last note-on time (hardware timestamp): [lh, rh, thumb]
        # Eliminates cross-hand BLE jitter from velocity INI.
        self._last_note_on_time = [0.0, 0.0, 0.0]
        self._vel_soft = self.config.get('vel_soft', 60)
        self._vel_normal = self.config.get('vel_normal', 92)
        self._vel_hard = self.config.get('vel_hard', 120)
        self._vel_fast_threshold = self.config.get('vel_fast_threshold', 0.05)   # < 50ms = hard
        self._vel_slow_threshold = self.config.get('vel_slow_threshold', 0.30)   # > 300ms = soft
        KEY_KP0_EVDEV = 82  # soft signal from firmware vel hold-tap
        self._vel_soft_signal = KEY_KP0_EVDEV

        # Pitch bend glide engines (created on bridge start) — LH and RH only, not thumbs
        self._glides = [None, None]  # 0=lh, 1=rh
        # Track press times for tap vs hold detection
        self._r1_press_times = {}  # keycode → press_timestamp
        self._r1_semitones = {}    # keycode → semitone_amount (for committing on tap)

        # Bass register semitone offset (global, shifts all bass + thumb notes)
        self._bass_semi_offset = 0

        # Mode toggle: 'dual_octave' or 'isomorphic', per zone (0=lh, 1=rh)
        self._grid_mode = ['dual_octave', 'dual_octave']
        # Track last note released per zone for anchor recentering
        self._last_note_released = [None, None]  # (keycode, midi_note, row, col) per zone
        self._last_toggle_time = 0  # debounce

        self._rebuild_note_map()
        self._build_menu()

    def _rebuild_note_map(self):
        with self._note_map_lock:
            self.note_map = build_note_map(
                lh_base=self.config.get('lh_base', 36),
                rh_base=self.config.get('rh_base', 60),
                col_interval=self.config['col_interval'],
                row_interval=self.config['row_interval'],
                thumb_base=self.config['thumb_base'] + self._bass_semi_offset,
                thumb_col_interval=self.config['thumb_col_interval'],
                thumb_row_interval=self.config['thumb_row_interval'],
                include_thumbs=self.config['include_thumbs'],
                include_r6=self.config['include_r6'],
            )
            # Apply bass semi offset to R6 bass notes
            if self._bass_semi_offset != 0:
                for kc in R6_BASS_NOTES:
                    if kc in self.note_map:
                        self.note_map[kc] += self._bass_semi_offset
            self._rebuild_fast_lookup()

    def _rebuild_bass_and_thumbs(self):
        """Rebuild ONLY thumb + R6 bass note_map entries.
        Preserves grid entries so iso mode mappings survive a bass semi shift."""
        with self._note_map_lock:
            # Build a fresh map just to get thumb + R6 values with the new offset
            fresh = build_note_map(
                lh_base=self.config.get('lh_base', 36),
                rh_base=self.config.get('rh_base', 60),
                col_interval=self.config['col_interval'],
                row_interval=self.config['row_interval'],
                thumb_base=self.config['thumb_base'] + self._bass_semi_offset,
                thumb_col_interval=self.config['thumb_col_interval'],
                thumb_row_interval=self.config['thumb_row_interval'],
                include_thumbs=self.config['include_thumbs'],
                include_r6=self.config['include_r6'],
            )
            # Overwrite only the thumb + R6 bass entries — leave grid alone
            for kc in THUMB_POSITION:
                if kc in fresh:
                    self.note_map[kc] = fresh[kc]
            for kc in R6_BASS_NOTES:
                if kc in fresh:
                    self.note_map[kc] = fresh[kc] + self._bass_semi_offset
            self._rebuild_fast_lookup()

    def _rebuild_fast_lookup(self):
        """Pre-compute array for O(1) keycode → (note, zone, row, col) lookup.
        Row/col are None for non-grid keys. Extended tuple eliminates
        GRID_POSITION.get() from the hot path in _handle_note."""
        self._fast_lookup = [None] * 256
        for kc, note in self.note_map.items():
            if kc < 256:
                zone = self._key_zones.get(kc, 0)
                pos = GRID_POSITION.get(kc)
                if pos:
                    self._fast_lookup[kc] = (note, zone, pos[0], pos[1])
                else:
                    self._fast_lookup[kc] = (note, zone, None, None)

        # Cache zone octave offsets and channels as a flat tuple for fast access
        self._zone_octaves = (self.lh_octave, self.rh_octave, self.thumb_octave)
        self._zone_channels = (
            self.config.get('lh_channel', 0) if self.config.get('per_zone_channels', True) else self.config.get('channel', 0),
            self.config.get('rh_channel', 1) if self.config.get('per_zone_channels', True) else self.config.get('channel', 0),
            self.config.get('thumb_channel', 2) if self.config.get('per_zone_channels', True) else self.config.get('channel', 0),
        )
        # Update glide engines with current channels (LH and RH only)
        for i in range(min(2, len(self._glides))):
            if self._glides[i]:
                self._glides[i].update(self._raw_send, self._zone_channels[i])

    def _build_menu(self):
        self.status_item = rumps.MenuItem("-- Bridge Inactive --")
        self.status_item.set_callback(None)

        self.toggle_item = rumps.MenuItem("Start Bridge", callback=self.toggle_bridge)

        self.bypass_item = rumps.MenuItem("Key Bypass: ON", callback=self.toggle_bypass)
        self.bypass_item.state = 1


        # Per-zone octave offset submenus
        self.lh_octave_menu = rumps.MenuItem(f"Left Hand Oct ({self.lh_octave:+d})")
        self.rh_octave_menu = rumps.MenuItem(f"Right Hand Oct ({self.rh_octave:+d})")
        self.thumb_octave_menu = rumps.MenuItem(f"Thumbs Oct ({self.thumb_octave:+d})")

        for menu, current, zone in [
            (self.lh_octave_menu, self.lh_octave, 'lh'),
            (self.rh_octave_menu, self.rh_octave, 'rh'),
            (self.thumb_octave_menu, self.thumb_octave, 'thumb'),
        ]:
            for off in range(-4, 5):
                label = f"{off:+d}" if off != 0 else "0 (default)"
                item = rumps.MenuItem(label, callback=self._make_zone_octave_cb(zone, off))
                if off == current:
                    item.state = 1
                menu.add(item)

        # Velocity submenu
        self.velocity_menu = rumps.MenuItem("Velocity")
        for vel in [40, 60, 80, 100, 110, 120, 127]:
            item = rumps.MenuItem(str(vel), callback=self._make_velocity_cb(vel))
            if vel == self.config['velocity']:
                item.state = 1
            self.velocity_menu.add(item)

        # Zone channels submenu
        self.zone_ch_toggle = rumps.MenuItem(
            "Per-Zone Channels: ON" if self.config.get('per_zone_channels', True) else "Per-Zone Channels: OFF",
            callback=self.toggle_zone_channels
        )
        self.zone_ch_toggle.state = 1 if self.config.get('per_zone_channels', True) else 0

        self.lh_ch_menu = rumps.MenuItem(f"LH Channel (Ch {self.config.get('lh_channel', 0) + 1})")
        self.rh_ch_menu = rumps.MenuItem(f"RH Channel (Ch {self.config.get('rh_channel', 1) + 1})")
        self.thumb_ch_menu = rumps.MenuItem(f"Thumbs Channel (Ch {self.config.get('thumb_channel', 2) + 1})")

        for menu, zone, current in [
            (self.lh_ch_menu, 'lh', self.config.get('lh_channel', 0)),
            (self.rh_ch_menu, 'rh', self.config.get('rh_channel', 1)),
            (self.thumb_ch_menu, 'thumb', self.config.get('thumb_channel', 2)),
        ]:
            for ch in range(16):
                item = rumps.MenuItem(f"Ch {ch + 1}", callback=self._make_zone_channel_cb(zone, ch))
                if ch == current:
                    item.state = 1
                menu.add(item)

        self.panic_item = rumps.MenuItem("All Notes Off (Panic)", callback=self.panic)
        self.detect_item = rumps.MenuItem("Detect Keyboard Type...", callback=self.detect_kb)
        self.devices_item = rumps.MenuItem("Show USB Devices", callback=self.show_devices)
        self.quit_item = rumps.MenuItem("Quit", callback=self.quit_app)

        self.menu = [
            self.status_item,
            None,
            self.toggle_item,
            self.bypass_item,
            None,
            self.lh_octave_menu,
            self.rh_octave_menu,
            self.thumb_octave_menu,
            None,
            self.velocity_menu,
            None,
            self.zone_ch_toggle,
            self.lh_ch_menu,
            self.rh_ch_menu,
            self.thumb_ch_menu,
            None,
            self.panic_item,
            self.detect_item,
            self.devices_item,
            None,
            self.quit_item,
        ]

    # --- Bridge Control ---

    def toggle_bridge(self, sender):
        if self.bridge_active:
            self._stop_bridge()
        else:
            self._start_bridge()

    def _start_bridge(self):
        try:
            self.midi_port = create_midi_output("Glove80 Instrument")
            self.midi_port.open()

            # Cache direct reference to rtmidi send for minimal overhead
            if hasattr(self.midi_port, '_midi_out'):
                self._raw_send = self.midi_port._midi_out.send_message
            else:
                self._raw_send = None

            # Initialize pitch bend glide engines — LH and RH only (not thumbs)
            bend_range = self.config.get('pitch_bend_range', 12)
            for i in range(2):
                ch = self._zone_channels[i]
                self._glides[i] = PitchGlide(self._raw_send, ch, bend_range)
            self._r1_press_times = {}
            self._r1_semitones = {}

            kb_type = self.config.get('keyboard_type')
            if kb_type is not None:
                kb_type = int(kb_type)
            self.key_capture = MacOSKeyCapture(keyboard_type=kb_type)
            self.key_capture.set_callback(self._key_callback)
            self.key_capture.start()

            self.bridge_active = True
            self.title = "G80 [ON]"
            self.status_item.title = "Bridge Active — Glove80 Instrument"
            self.toggle_item.title = "Stop Bridge"
        except RuntimeError as e:
            rumps.alert("Error", str(e))

    def _stop_bridge(self):
        # Reset pitch bends
        for g in self._glides:
            if g:
                g.reset()
        self._r1_press_times = {}
        self._r1_semitones = {}

        # Release all sounding notes
        if self.midi_port:
            for kc in range(256):
                held = self._active_notes[kc]
                if held is not None:
                    self.midi_port.note_off(held[0], held[1])
                    self._active_notes[kc] = None

        if self.key_capture:
            self.key_capture.stop()
            self.key_capture = None
        if self.midi_port:
            self.midi_port.close()
            self.midi_port = None

        self.bridge_active = False
        self.title = "G80"
        self.status_item.title = "-- Bridge Inactive --"
        self.toggle_item.title = "Start Bridge"

    # --- Bypass ---

    def toggle_bypass(self, sender):
        self.bypass_active = not self.bypass_active
        if self.bypass_active:
            self.bypass_item.title = "Key Bypass: ON"
            self.bypass_item.state = 1
        else:
            self.bypass_item.title = "Key Bypass: OFF"
            self.bypass_item.state = 0

    # --- Key Handling ---

    def _key_callback(self, evdev_keycode, is_press, hw_timestamp=None):
        """Called by MacOSKeyCapture. Returns True to suppress the key.

        hw_timestamp: hardware timestamp in seconds (Mach monotonic time)
        passed from the CGEventTap. Used for jitter-free velocity INI.
        """
        # Fast note path first (most common case)
        if evdev_keycode < 256 and self._fast_lookup[evdev_keycode] is not None:
            self._handle_note(evdev_keycode, is_press, hw_timestamp)
            return True

        # Mode toggle — LH Enter toggles zone 0, RH KP3 toggles zone 1
        # Both are debounced to prevent key-repeat flood
        if evdev_keycode == KEY_MODE_TOGGLE and is_press:
            now = hw_timestamp if hw_timestamp is not None else time.perf_counter()
            if now - self._last_toggle_time > 0.3:
                self._last_toggle_time = now
                self._handle_mode_toggle(force_zone=0)
            return True

        if evdev_keycode == KEY_MODE_TOGGLE_RH and is_press:
            now = hw_timestamp if hw_timestamp is not None else time.perf_counter()
            if now - self._last_toggle_time > 0.3:
                self._last_toggle_time = now
                self._handle_mode_toggle(force_zone=1)
            return True

        # Velocity soft signal from firmware (KP_N0 = quick staccato tap)
        if evdev_keycode == self._vel_soft_signal and is_press:
            self._current_velocity = self._vel_soft
            _log.debug(f"VEL soft signal (KP_N0) → velocity locked to {self._vel_soft}")
            return True

        # Bass register semitone controls.
        # Only rebuild thumb + R6 bass entries — NEVER touch the grid note_map
        # because the grid may be in iso mode and a full rebuild would wipe it.
        if evdev_keycode == KEY_BASS_SEMI_DN and is_press:
            self._bass_semi_offset -= 1
            self._rebuild_bass_and_thumbs()
            _log.debug(f"BASS semi DOWN → offset={self._bass_semi_offset}")
            return True
        if evdev_keycode == KEY_BASS_SEMI_UP and is_press:
            self._bass_semi_offset += 1
            self._rebuild_bass_and_thumbs()
            _log.debug(f"BASS semi UP → offset={self._bass_semi_offset}")
            return True

        # R1 pitch controls
        r1 = R1_CONTROLS.get(evdev_keycode)
        if r1 is not None:
            zone_idx, action = r1
            self._handle_r1(zone_idx, action, is_press)
            return True

        return self.bypass_active

    def _handle_note(self, keycode, is_press, hw_timestamp=None):
        # Fast path: single array lookup — (base_note, zone, row, col)
        # row/col are None for non-grid keys. Extended tuple eliminates
        # GRID_POSITION.get() from the hot path.
        entry = self._fast_lookup[keycode]
        base_midi = entry[0]
        zone_idx = entry[1]
        midi_note = base_midi + self._zone_octaves[zone_idx] * 12

        if midi_note < 0:
            midi_note = 0
        elif midi_note > 127:
            midi_note = 127

        ch = self._zone_channels[zone_idx]
        raw = self._raw_send

        if _log.isEnabledFor(logging.DEBUG):
            zone = ('lh', 'rh', 'thumb')[zone_idx]
            mode = self._grid_mode[zone_idx] if zone_idx < 2 else 'n/a'
            d = 'ON ' if is_press else 'OFF'
            _log.debug(f"{d} kc={keycode:3d} base={base_midi:3d} oct={self._zone_octaves[zone_idx]:+d} final={midi_note:3d}({note_name(midi_note)}) zone={zone} mode={mode}")

        if is_press:
            active = self._active_notes
            if active[keycode] is not None:
                return
            # Sticky velocity: per-zone INI eliminates cross-hand BLE jitter.
            # hw_timestamp is from CGEventGetTimestamp (kernel HID interrupt
            # time), immune to callback scheduling latency.
            now = hw_timestamp if hw_timestamp is not None else time.perf_counter()
            prev = self._last_note_on_time[zone_idx]
            if prev > 0:
                delta = now - prev
                if delta < self._vel_fast_threshold:
                    self._current_velocity = self._vel_hard
                elif delta < self._vel_slow_threshold:
                    self._current_velocity = self._vel_normal
                else:
                    self._current_velocity = self._vel_soft
            self._last_note_on_time[zone_idx] = now

            vel = self._current_velocity
            if raw:
                raw([0x90 | ch, midi_note, vel])
            else:
                self.midi_port.note_on(midi_note, vel, ch)
            active[keycode] = (midi_note, ch)
            # Track last pressed note for iso anchor — user holds key and
            # palms toggle. Row/col come from the extended _fast_lookup tuple
            # (no dict lookup).
            if zone_idx < 2:
                row = entry[2]
                col = entry[3]
                if row is not None:
                    # Use sequence counter instead of wall time for cross-hand
                    # ordering — the timestamp was only used to pick which hand
                    # had the "most recent" activity, a UI concern not tied to
                    # absolute time.
                    self._last_note_seq += 1
                    self._last_note_released[zone_idx] = (keycode, base_midi, row, col, self._last_note_seq)
        else:
            held = self._active_notes[keycode]
            if held is not None:
                self._active_notes[keycode] = None
                if raw:
                    raw([0x80 | held[1], held[0], 0])
                else:
                    self.midi_port.note_off(held[0], held[1])

    def _handle_r1(self, zone_idx, action, is_press):
        """Handle R1 pitch control keys.

        All modulation glides (never jumps).
        Tap (quick press+release) = permanent shift.
        Hold + release = temporary bend, returns to center.
        Thumbs (zone 2) are excluded from pitch bend.
        """
        zone_name = ('lh', 'rh')[zone_idx] if zone_idx < 2 else None
        glide = self._glides[zone_idx] if zone_idx < 2 else None

        if action == 'reset' and is_press:
            if zone_name:
                # Reset octave to 0
                current = getattr(self, f'{zone_name}_octave')
                if current != 0:
                    self._shift_zone_octave(zone_name, -current)
                if glide:
                    glide.reset()
            return

        # Determine semitone amount for this action
        if action == 'semi_down':
            semitones = -1
        elif action == 'semi_up':
            semitones = 1
        elif action == 'oct_down':
            semitones = -12
        elif action == 'oct_up':
            semitones = 12
        else:
            return

        if glide is None:
            # Thumbs — just do instant octave shift, no glide
            if is_press and abs(semitones) >= 12:
                self._shift_zone_octave('thumb', semitones // 12)
            return

        # Build a unique key for tracking this press
        press_key = (zone_idx, action)

        if is_press:
            # Start gliding toward target
            self._r1_press_times[press_key] = time.perf_counter()
            self._r1_semitones[press_key] = semitones
            glide.glide_semitones(semitones)

        else:
            # Release — check tap vs hold
            press_time = self._r1_press_times.pop(press_key, 0)
            held_semitones = self._r1_semitones.pop(press_key, 0)
            duration = time.perf_counter() - press_time

            if duration < TAP_THRESHOLD:
                # TAP = permanent shift
                _log.debug(f"R1 TAP zone={zone_name} action={action} semi={held_semitones} mode={self._grid_mode[zone_idx]} dur={duration:.3f}s")
                if self._grid_mode[zone_idx] == 'isomorphic':
                    # In iso mode: shift every note in the iso map directly
                    shift = held_semitones if abs(held_semitones) < 12 else held_semitones
                    side_cols = (0, 6) if zone_idx == 0 else (6, 12)
                    for kc, (r, c) in GRID_POSITION.items():
                        if side_cols[0] <= c < side_cols[1] and kc in self.note_map:
                            self.note_map[kc] = max(0, min(127, self.note_map[kc] + shift))
                    self._rebuild_fast_lookup()
                else:
                    # In dual-octave: adjust base and rebuild
                    if abs(held_semitones) >= 12:
                        self._shift_zone_octave(zone_name, held_semitones // 12)
                    else:
                        base_key = f'{zone_name}_base'
                        self.config[base_key] = self.config.get(base_key, 36 if zone_name == 'lh' else 60) + held_semitones
                        self._rebuild_note_map()
                        self._rebuild_fast_lookup()
                glide.snap_to_center()
            else:
                # HOLD = temporary, glide back
                glide.glide_to_center()

    def _rebuild_current_mode(self):
        """Rebuild note map respecting current grid mode for each zone."""
        # Start with dual-octave base
        self._rebuild_note_map()
        # Overlay isomorphic for any zone that's in isomorphic mode
        for zi in range(2):
            if self._grid_mode[zi] == 'isomorphic':
                side = 'lh' if zi == 0 else 'rh'
                base_key = f'{side}_base'
                base = self.config.get(base_key, 36 if zi == 0 else 60)
                anchor_col = 0 if zi == 0 else 6
                iso_map = build_isomorphic_from_anchor(0, anchor_col, base, side=side)
                for kc, note in iso_map.items():
                    self.note_map[kc] = note
        self._rebuild_fast_lookup()

    def _handle_mode_toggle(self, force_zone=None):
        """Toggle grid mode for a zone."""
        _log.debug(f"MODE_TOGGLE force_zone={force_zone} modes={self._grid_mode} last_released={[x[:4] if x else None for x in self._last_note_released]}")

        active = self._active_notes
        key_zones = self._key_zones
        if force_zone is not None:
            # Per-hand Enter: target only the specified zone
            zones_with_notes = set()
            for kc in range(256):
                if active[kc] is None:
                    continue
                zi = key_zones.get(kc)
                if zi == force_zone:
                    zones_with_notes.add(zi)
            target_zones = [force_zone]
        else:
            # Determine which zone to toggle based on recent activity
            zones_with_notes = set()
            for kc in range(256):
                if active[kc] is None:
                    continue
                zi = key_zones.get(kc)
                if zi is not None and zi < 2:
                    zones_with_notes.add(zi)

            # If no notes currently held, use last released note to pick zone
            # If no activity at all, toggle both
            if not zones_with_notes:
                lh_time = self._last_note_released[0][4] if self._last_note_released[0] else 0
                rh_time = self._last_note_released[1][4] if self._last_note_released[1] else 0
                if lh_time == 0 and rh_time == 0:
                    target_zones = [0, 1]
                elif lh_time >= rh_time:
                    target_zones = [0]
                else:
                    target_zones = [1]
            else:
                target_zones = list(zones_with_notes)

        for zi in target_zones:
            if zones_with_notes and zi in zones_with_notes:
                # Notes playing — switch to isomorphic anchored on last PRESSED
                # grid key in this zone. Fallback to scanning active held keys
                # if _last_note_released is somehow unset (shouldn't happen —
                # it's updated on press).
                anchor = self._last_note_released[zi]
                if anchor is None:
                    for kc in range(256):
                        if active[kc] is None:
                            continue
                        if key_zones.get(kc) == zi and kc in GRID_POSITION:
                            pos = GRID_POSITION[kc]
                            anchor = (kc, None, pos[0], pos[1])
                            break
                if anchor:
                    _, _, row, col = anchor[:4]
                    side = 'lh' if zi == 0 else 'rh'
                    # Compute anchor_pitch NOTATIONALLY from (row, col), not
                    # from note_map / _last_note_released[...][1]. The stored
                    # value can be either a 2oct pitch (irregular C D E G A B
                    # intervals) or an iso ±12 octave-extension pitch, either
                    # of which corrupts the seed for re-anchoring. Pure chromatic
                    # (row + col*2 from the hand base) is the only seed that's
                    # stable across mode toggles and re-anchors.
                    anchor_pitch = notational_iso_anchor_pitch(row, col, side=side)
                    anchor_pitch += self._zone_octaves[zi] * 12
                    iso_map = build_isomorphic_from_anchor(row, col, anchor_pitch, side=side)
                    for kc, note in iso_map.items():
                        self.note_map[kc] = note
                    self._grid_mode[zi] = 'isomorphic'
            else:
                # No notes — simple toggle
                if self._grid_mode[zi] == 'isomorphic':
                    self._grid_mode[zi] = 'dual_octave'
                else:
                    self._grid_mode[zi] = 'isomorphic'

        # Reset pitch bend on mode switch to avoid voicing artifacts
        for zi in target_zones:
            if zi < len(self._glides) and self._glides[zi]:
                self._glides[zi].snap_to_center()

        # Rebuild only what's needed
        if all(m == 'dual_octave' for m in self._grid_mode):
            # Both zones back to dual-octave — full rebuild
            self.config['lh_base'] = 36
            self.config['rh_base'] = 60
            self._rebuild_note_map()
        else:
            # At least one zone switched — just rebuild fast lookup
            # The iso map was already set in the loop above
            # For zones toggling to dual-octave without anchor, rebuild their portion
            for zi in target_zones:
                if self._grid_mode[zi] == 'dual_octave':
                    # Rebuild just this zone's keys from dual-octave
                    side_nm = build_note_map(
                        lh_base=self.config.get('lh_base', 36),
                        rh_base=self.config.get('rh_base', 60),
                        col_interval=self.config['col_interval'],
                        row_interval=self.config['row_interval'],
                    )
                    col_lo = 0 if zi == 0 else 6
                    col_hi = 6 if zi == 0 else 12
                    for kc, (r, c) in GRID_POSITION.items():
                        if col_lo <= c < col_hi and kc in side_nm:
                            self.note_map[kc] = side_nm[kc]
            self._rebuild_fast_lookup()

    def _shift_zone_octave(self, zone, direction):
        lo = self.config['octave_offset_min']
        hi = self.config['octave_offset_max']
        if zone == 'lh':
            new_val = self.lh_octave + direction
            if lo <= new_val <= hi:
                self.lh_octave = new_val
                self._update_zone_menu(self.lh_octave_menu, new_val, "Left Hand")
        elif zone == 'rh':
            new_val = self.rh_octave + direction
            if lo <= new_val <= hi:
                self.rh_octave = new_val
                self._update_zone_menu(self.rh_octave_menu, new_val, "Right Hand")
        elif zone == 'thumb':
            new_val = self.thumb_octave + direction
            if lo <= new_val <= hi:
                self.thumb_octave = new_val
                self._update_zone_menu(self.thumb_octave_menu, new_val, "Thumbs")
        self._zone_octaves = (self.lh_octave, self.rh_octave, self.thumb_octave)

    def _update_zone_menu(self, menu, current_val, zone_label):
        menu.title = f"{zone_label} Oct ({current_val:+d})"
        for item in menu.values():
            label = item.title
            if label == "0 (default)":
                item.state = 1 if current_val == 0 else 0
            else:
                item.state = 1 if label == f"{current_val:+d}" else 0

    # --- Panic ---

    def panic(self, sender):
        if self.midi_port:
            for kc in range(256):
                held = self._active_notes[kc]
                if held is not None:
                    self.midi_port.note_off(held[0], held[1])
                    self._active_notes[kc] = None
            for g in self._glides:
                if g:
                    g.reset()
            self._r1_press_times = {}
            self._r1_semitones = {}
            for ch in range(16):
                self.midi_port.cc(123, 0, ch)
            rumps.notification("Glove80 MIDI", "Panic", "All notes off + pitch bend reset.")

    # --- Detection ---

    def detect_kb(self, sender):
        rumps.alert(
            "Detect Keyboard Type",
            "After clicking OK, press a few keys on your Glove80,\n"
            "then a few keys on your Mac keyboard.\n"
            "Detection runs for 5 seconds."
        )
        try:
            types = detect_keyboard_types(5)
            if types:
                lines = [f"Type {t}: {c} keypresses" for t, c in types]
                lines.append("")
                lines.append("The Glove80 is typically the non-standard number.")
                lines.append("Set it in bridge_config.json as 'keyboard_type'.")
                rumps.alert("Detected Keyboard Types", "\n".join(lines))
            else:
                rumps.alert("No Keys Detected", "No keypresses were detected.")
        except RuntimeError as e:
            rumps.alert("Error", str(e))

    def show_devices(self, sender):
        devices = get_usb_keyboards()
        if not devices:
            rumps.alert("USB Devices", "No USB devices found.")
            return
        lines = [f"{d['name']}  VID:{d['vendor_id']}  PID:{d['product_id']}" for d in devices]
        rumps.alert("USB Devices", "\n".join(lines))

    # --- Config Callbacks ---

    def _save_current_config(self):
        self.config['lh_octave'] = self.lh_octave
        self.config['rh_octave'] = self.rh_octave
        self.config['thumb_octave'] = self.thumb_octave
        save_config(self.config)


    def toggle_zone_channels(self, sender):
        current = self.config.get('per_zone_channels', True)
        self.config['per_zone_channels'] = not current
        if self.config['per_zone_channels']:
            self.zone_ch_toggle.title = "Per-Zone Channels: ON"
            self.zone_ch_toggle.state = 1
        else:
            self.zone_ch_toggle.title = "Per-Zone Channels: OFF"
            self.zone_ch_toggle.state = 0
        self._rebuild_fast_lookup()
        self._save_current_config()

    def _make_zone_channel_cb(self, zone, ch):
        def cb(sender):
            key = f'{zone}_channel'
            self.config[key] = ch
            menu = {'lh': self.lh_ch_menu, 'rh': self.rh_ch_menu, 'thumb': self.thumb_ch_menu}[zone]
            label = {'lh': 'LH', 'rh': 'RH', 'thumb': 'Thumbs'}[zone]
            menu.title = f"{label} Channel (Ch {ch + 1})"
            for item in menu.values():
                item.state = 0
            sender.state = 1
            self._rebuild_fast_lookup()
            self._save_current_config()
        return cb

    def _make_zone_octave_cb(self, zone, offset):
        def cb(sender):
            if zone == 'lh':
                self.lh_octave = offset
                self._update_zone_menu(self.lh_octave_menu, offset, "Left Hand")
            elif zone == 'rh':
                self.rh_octave = offset
                self._update_zone_menu(self.rh_octave_menu, offset, "Right Hand")
            elif zone == 'thumb':
                self.thumb_octave = offset
                self._update_zone_menu(self.thumb_octave_menu, offset, "Thumbs")
            self._zone_octaves = (self.lh_octave, self.rh_octave, self.thumb_octave)
            self._save_current_config()
        return cb

    def _make_velocity_cb(self, vel):
        def cb(sender):
            self.config['velocity'] = vel
            self._velocity = vel
            for item in self.velocity_menu.values():
                item.state = 0
            sender.state = 1
            self._save_current_config()
        return cb


    # --- Quit ---

    def quit_app(self, sender):
        self._stop_bridge()
        self._save_current_config()
        rumps.quit_application()


def main():
    app = Glove80TrayApp()
    app.run()


if __name__ == "__main__":
    main()
