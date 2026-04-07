#!/usr/bin/env python3
"""
Glove80 Stock Firmware MIDI Bridge

Reads key events from a stock-firmware Glove80 (via evdev) and translates
them into MIDI note/CC events on a virtual MIDI port.

No firmware flashing required — the Glove80 stays completely stock.
The bridge exclusively grabs the Glove80 device so keypresses don't
reach the OS as typed characters.

Architecture:
  Glove80 (stock firmware) → USB HID → evdev → this bridge → MIDI → DAW

Isomorphic layout:
  Right/left = ±whole step (2 semitones)
  Down/up    = ±semitone (1 semitone)
  Thumb keys = bass register (1 octave below main grid)
  R1 strip   = transport controls + octave shift

Usage:
  python3 stock_bridge.py                    # Auto-detect Glove80
  python3 stock_bridge.py --device /dev/input/event5
  python3 stock_bridge.py --list             # List keyboards
  python3 stock_bridge.py --layout           # Print current pitch layout
"""

import argparse
import signal
import sys

from midi_output import create_midi_output
from physical_layout import (
    GRID_POSITION,
    THUMB_POSITION,
    CONTROL_KEYS,
    TRANSPORT_CC,
    KEY_OCTAVE_DOWN,
    KEY_OCTAVE_UP,
    build_note_map,
    all_bridge_keys,
    note_name,
    print_layout,
)
from config import (
    load_config,
    save_config,
    is_in_scale,
    SCALES,
    NOTE_NAMES,
)

IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform == "linux"

if IS_LINUX:
    from hid_reader import HidReader, list_keyboard_devices
elif IS_MACOS:
    from hid_reader_macos import MacOSKeyCapture, get_usb_keyboards, detect_keyboard_types


class StockBridge:
    """Main bridge: stock Glove80 key events → MIDI. Cross-platform."""

    def __init__(self, device_path=None, midi_port_name="Glove80 Instrument",
                 config_path=None, keyboard_type=None):
        self.midi = create_midi_output(midi_port_name)
        self.config = load_config(config_path)
        self.config_path = config_path
        self.octave_offset = self.config['octave_offset']
        self.note_map = {}
        self.active_notes = {}   # keycode → midi_note (currently sounding)
        self._running = False
        self._rebuild_note_map()

        # Platform-specific input
        if IS_LINUX:
            self.reader = HidReader(device_path)
            self.mac_capture = None
        elif IS_MACOS:
            self.reader = None
            self.mac_capture = MacOSKeyCapture(keyboard_type=keyboard_type)
            self.mac_capture.set_callback(self._macos_key_callback)
        else:
            raise RuntimeError(f"Unsupported platform: {sys.platform}")

    def _rebuild_note_map(self):
        """Rebuild the keycode → MIDI note map from current config."""
        self.note_map = build_note_map(
            lh_base=self.config.get('lh_base', 36),
            rh_base=self.config.get('rh_base', 60),
            col_interval=self.config['col_interval'],
            row_interval=self.config['row_interval'],
            thumb_base=self.config['thumb_base'],
            thumb_col_interval=self.config['thumb_col_interval'],
            thumb_row_interval=self.config['thumb_row_interval'],
            include_thumbs=self.config['include_thumbs'],
            include_r6=self.config['include_r6'],
        )

    def start(self):
        """Initialize devices and enter the event loop."""
        print("=== Glove80 Stock Firmware MIDI Bridge ===")
        print(f"Platform: {sys.platform}")
        print()

        self.midi.open()
        print()

        if IS_LINUX:
            self.reader.open()
            self.reader.grab()
        elif IS_MACOS:
            self.mac_capture.start()
        print()

        scale = self.config['scale']
        root = NOTE_NAMES[self.config['root']]
        print(f"Scale: {scale} / Root: {root}")
        print(f"Channel: {self.config['channel'] + 1} / Velocity: {self.config['velocity']}")
        print(f"Octave offset: {self.octave_offset:+d}")
        print(f"Grid intervals: col={self.config['col_interval']} row={self.config['row_interval']}")

        notes = sorted(set(self.note_map.values()))
        if notes:
            print(f"Range: {note_name(min(notes))} - {note_name(max(notes))}")
        print()
        print("Playing! Press keys to send MIDI. Ctrl+C to quit.")
        print()

        self._running = True
        try:
            if IS_LINUX:
                self._event_loop_linux()
            elif IS_MACOS:
                self._event_loop_macos()
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.stop()

    def stop(self):
        """Clean shutdown."""
        self._running = False
        # Release all sounding notes
        for keycode, midi_note in list(self.active_notes.items()):
            self.midi.note_off(midi_note, self.config['channel'])
        self.active_notes.clear()

        if IS_LINUX and self.reader:
            self.reader.close()
        elif IS_MACOS and self.mac_capture:
            self.mac_capture.stop()
        self.midi.close()

        # Persist octave offset
        self.config['octave_offset'] = self.octave_offset
        save_config(self.config, self.config_path)
        print("Bridge stopped. Config saved.")

    def _process_key(self, keycode, is_press):
        """Process a single key event. Returns True if handled."""
        # Octave shift (F9/F10 on R1)
        if keycode == KEY_OCTAVE_DOWN and is_press:
            self._handle_octave_shift(-1)
            return True
        if keycode == KEY_OCTAVE_UP and is_press:
            self._handle_octave_shift(+1)
            return True

        # Transport controls (R1 strip, excluding octave keys)
        if keycode in CONTROL_KEYS and keycode not in (KEY_OCTAVE_DOWN, KEY_OCTAVE_UP):
            self._handle_transport(keycode, is_press)
            return True

        # Note keys
        if keycode in self.note_map:
            self._handle_note(keycode, is_press)
            return True

        return False

    def _event_loop_linux(self):
        """Linux event loop: blocking evdev read."""
        for keycode, is_press in self.reader.read_events():
            if not self._running:
                break
            self._process_key(keycode, is_press)

    def _event_loop_macos(self):
        """macOS event loop: CGEventTap runs on background thread, main thread waits."""
        import time
        while self._running:
            time.sleep(0.1)

    def _macos_key_callback(self, evdev_keycode, is_press):
        """Called by MacOSKeyCapture on the tap thread. Returns True to suppress."""
        return self._process_key(evdev_keycode, is_press)

    def _handle_note(self, keycode, is_press):
        """Handle a note key press or release."""
        channel = self.config['channel']
        velocity = self.config['velocity']
        scale = self.config['scale']
        root = self.config['root']

        base_midi = self.note_map[keycode]
        midi_note = base_midi + (self.octave_offset * 12)
        midi_note = max(0, min(127, midi_note))

        # Scale filter: skip notes not in the selected scale
        if scale != 'chromatic' and not is_in_scale(midi_note, root, scale):
            return

        if is_press:
            # Ignore key repeat — if this key is already held, do nothing
            if keycode in self.active_notes:
                return

            self.midi.note_on(midi_note, velocity, channel)
            self.active_notes[keycode] = midi_note
            print(f"  ON  {note_name(midi_note):>4s} ({midi_note:3d})")
        else:
            if keycode in self.active_notes:
                old_note = self.active_notes.pop(keycode)
                self.midi.note_off(old_note, channel)
                print(f"  OFF {note_name(old_note):>4s} ({old_note:3d})")

    def _handle_transport(self, keycode, is_press):
        """Handle R1 transport/control keys."""
        control_name = CONTROL_KEYS.get(keycode)
        cc_num = TRANSPORT_CC.get(control_name)
        if cc_num is None:
            return

        channel = self.config['channel']
        if is_press:
            self.midi.cc(cc_num, 127, channel)
            print(f"  CC  {cc_num:3d} = 127 ({control_name})")
        else:
            self.midi.cc(cc_num, 0, channel)

    def _handle_octave_shift(self, direction):
        """Shift octave offset up or down."""
        lo = self.config['octave_offset_min']
        hi = self.config['octave_offset_max']
        new_offset = self.octave_offset + direction
        if lo <= new_offset <= hi:
            self.octave_offset = new_offset
            notes = sorted(set(
                max(0, min(127, n + self.octave_offset * 12))
                for n in self.note_map.values()
            ))
            lo_note = note_name(notes[0]) if notes else "?"
            hi_note = note_name(notes[-1]) if notes else "?"
            print(f"  Octave: {self.octave_offset:+d}  (range: {lo_note} - {hi_note})")
        else:
            print(f"  Octave limit reached ({self.octave_offset:+d})")


def main():
    parser = argparse.ArgumentParser(
        description="Glove80 Stock Firmware MIDI Bridge — no firmware flashing required"
    )
    parser.add_argument(
        "--device", "-d",
        help="evdev device path (e.g. /dev/input/event5). Auto-detects if omitted."
    )
    parser.add_argument(
        "--port", "-p",
        default="Glove80 Instrument",
        help="MIDI port name (default: 'Glove80 Instrument')"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available keyboard devices and exit"
    )
    parser.add_argument(
        "--layout",
        action="store_true",
        help="Print current isomorphic pitch layout and exit"
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to config JSON file (default: bridge/bridge_config.json)"
    )
    parser.add_argument(
        "--lh-base", type=int,
        help="Base MIDI note for left half (default: 36 = C2)"
    )
    parser.add_argument(
        "--rh-base", type=int,
        help="Base MIDI note for right half (default: 60 = C4)"
    )
    parser.add_argument(
        "--scale",
        choices=list(SCALES.keys()),
        help="Scale filter (default: chromatic)"
    )
    parser.add_argument(
        "--root", type=int, choices=range(12),
        help="Root note 0-11 (0=C, 1=C#, ..., 11=B)"
    )
    parser.add_argument(
        "--velocity", type=int,
        help="Note velocity 1-127 (default: 100)"
    )
    parser.add_argument(
        "--channel", type=int,
        help="MIDI channel 1-16 (default: 1)"
    )

    if IS_MACOS:
        parser.add_argument(
            "--keyboard-type", type=int,
            help="macOS keyboard type ID to filter (use --detect to find it)"
        )
        parser.add_argument(
            "--detect",
            action="store_true",
            help="Detect keyboard type IDs (press keys on each keyboard for 5 seconds)"
        )
        parser.add_argument(
            "--usb-devices",
            action="store_true",
            help="List connected USB devices"
        )

    args = parser.parse_args()

    # Platform-specific: list devices
    if args.list:
        if IS_LINUX:
            devices = list_keyboard_devices()
            if not devices:
                print("No keyboard devices found. Try: sudo usermod -aG input $USER")
            else:
                print("Available keyboard devices:")
                for path, name, phys in devices:
                    print(f"  {path}: {name}")
                    print(f"    phys: {phys}")
        elif IS_MACOS:
            devices = get_usb_keyboards()
            if not devices:
                print("No USB devices found.")
            else:
                print("USB devices:")
                for d in devices:
                    print(f"  {d['name']}  VID:{d['vendor_id']}  PID:{d['product_id']}")
        return

    # macOS-specific: detect keyboard types
    if IS_MACOS and getattr(args, 'detect', False):
        print("Press keys on your Glove80 and your main keyboard...")
        print("Detecting for 5 seconds...")
        types = detect_keyboard_types(5)
        if types:
            print("\nDetected keyboard type IDs:")
            for kb_type, count in types:
                print(f"  Type {kb_type}: {count} keypresses")
            print("\nThe Glove80 is typically the non-standard (higher) number.")
            print(f"Use: --keyboard-type <ID>")
        else:
            print("No keypresses detected.")
        return

    if IS_MACOS and getattr(args, 'usb_devices', False):
        devices = get_usb_keyboards()
        if not devices:
            print("No USB devices found.")
        else:
            for d in devices:
                print(f"  {d['name']}  VID:{d['vendor_id']}  PID:{d['product_id']}")
        return

    # Load config and apply CLI overrides
    config = load_config(args.config)
    if args.lh_base is not None:
        config['lh_base'] = args.lh_base
    if args.rh_base is not None:
        config['rh_base'] = args.rh_base
    if args.scale is not None:
        config['scale'] = args.scale
    if args.root is not None:
        config['root'] = args.root
    if args.velocity is not None:
        config['velocity'] = max(1, min(127, args.velocity))
    if args.channel is not None:
        config['channel'] = max(0, min(15, args.channel - 1))

    if args.layout:
        note_map = build_note_map(
            lh_base=config.get('lh_base', 36),
            rh_base=config.get('rh_base', 60),
            col_interval=config['col_interval'],
            row_interval=config['row_interval'],
            thumb_base=config['thumb_base'],
            thumb_col_interval=config['thumb_col_interval'],
            thumb_row_interval=config['thumb_row_interval'],
            include_thumbs=config['include_thumbs'],
            include_r6=config['include_r6'],
        )
        print_layout(note_map)
        print(f"\nTotal note keys: {len(note_map)}")
        unique_notes = sorted(set(note_map.values()))
        print(f"Unique pitches: {len(unique_notes)} ({note_name(unique_notes[0])} - {note_name(unique_notes[-1])})")
        return

    # Save any CLI overrides
    save_config(config, args.config)

    # Resolve keyboard type for macOS
    keyboard_type = None
    if IS_MACOS:
        keyboard_type = getattr(args, 'keyboard_type', None)

    bridge = StockBridge(
        device_path=getattr(args, 'device', None) if IS_LINUX else None,
        midi_port_name=args.port,
        config_path=args.config,
        keyboard_type=keyboard_type,
    )

    signal.signal(signal.SIGTERM, lambda *_: bridge.stop())
    bridge.start()


if __name__ == "__main__":
    main()
