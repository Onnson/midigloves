#!/usr/bin/env python3
"""
Glove80 Instrument Mode Bridge

Reads key events from the Glove80 keyboard (via evdev) and translates
instrument-mode keycodes into MIDI note events on a virtual ALSA port.

Architecture:
  Glove80 (ZMK instrument layer) → USB HID → evdev → this bridge → ALSA MIDI → Ableton

Usage:
  python3 glove80_bridge.py                    # Auto-detect Glove80
  python3 glove80_bridge.py --device /dev/input/event5  # Manual device
  python3 glove80_bridge.py --list             # List available keyboards

The bridge starts in instrument mode (device grabbed, keypresses → MIDI).
Pressing the mode toggle key (F13 area) or Ctrl+C exits cleanly.
"""

import argparse
import signal
import sys

from hid_reader import HidReader, list_keyboard_devices
from midi_output import create_midi_output
from pitch_map import (
    PITCH_MAP,
    KEY_OCTAVE_DOWN,
    KEY_OCTAVE_UP,
    ALL_INSTRUMENT_KEYS,
    OCTAVE_OFFSET_MIN,
    OCTAVE_OFFSET_MAX,
    DEFAULT_VELOCITY,
    resolve_note,
    note_name,
)


class InstrumentBridge:
    """Main bridge: evdev key events → MIDI notes."""

    def __init__(self, device_path=None, midi_port_name="Glove80 Instrument"):
        self.reader = HidReader(device_path)
        self.midi = create_midi_output(midi_port_name)
        self.octave_offset = 0
        self.active_notes = {}  # keycode -> midi_note (currently sounding)
        self._running = False

    def start(self):
        """Initialize devices and enter the event loop."""
        print("=== Glove80 Instrument Mode Bridge ===")
        print()

        self.midi.open()
        print()

        self.reader.open()
        self.reader.grab()
        print()

        print(f"Octave offset: {self.octave_offset:+d}")
        print(f"Base range: {note_name(24)} - {note_name(59)}")
        print(f"Current range: {note_name(resolve_note(list(PITCH_MAP.keys())[0], self.octave_offset))} - "
              f"{note_name(resolve_note(list(PITCH_MAP.keys())[-1], self.octave_offset))}")
        print()
        print("Playing! Press keys to send MIDI. Ctrl+C to quit.")
        print()

        self._running = True
        try:
            self._event_loop()
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.stop()

    def stop(self):
        """Clean shutdown."""
        self._running = False
        # Release all sounding notes
        for keycode, midi_note in list(self.active_notes.items()):
            self.midi.note_off(midi_note)
        self.active_notes.clear()

        self.reader.close()
        self.midi.close()
        print("Bridge stopped.")

    def _event_loop(self):
        """Main event loop: read keys, emit MIDI."""
        for keycode, is_press in self.reader.read_events():
            if not self._running:
                break

            if keycode in PITCH_MAP:
                self._handle_note(keycode, is_press)
            elif keycode == KEY_OCTAVE_DOWN and is_press:
                self._handle_octave_shift(-1)
            elif keycode == KEY_OCTAVE_UP and is_press:
                self._handle_octave_shift(+1)

    def _handle_note(self, keycode, is_press):
        """Handle a note key press or release."""
        if is_press:
            # If this key already has a sounding note (e.g. from before
            # an octave shift), send note-off for the old note first
            if keycode in self.active_notes:
                self.midi.note_off(self.active_notes[keycode])

            midi_note = resolve_note(keycode, self.octave_offset)
            if midi_note is not None:
                self.midi.note_on(midi_note, DEFAULT_VELOCITY)
                self.active_notes[keycode] = midi_note
                print(f"  ON  {note_name(midi_note):>4s} ({midi_note:3d})")
        else:
            # Release: send note-off for whatever note this key started
            if keycode in self.active_notes:
                midi_note = self.active_notes.pop(keycode)
                self.midi.note_off(midi_note)
                print(f"  OFF {note_name(midi_note):>4s} ({midi_note:3d})")

    def _handle_octave_shift(self, direction):
        """Shift octave offset up or down."""
        new_offset = self.octave_offset + direction
        if OCTAVE_OFFSET_MIN <= new_offset <= OCTAVE_OFFSET_MAX:
            self.octave_offset = new_offset
            low = resolve_note(list(PITCH_MAP.keys())[0], self.octave_offset)
            high = resolve_note(list(PITCH_MAP.keys())[-1], self.octave_offset)
            print(f"  Octave: {self.octave_offset:+d}  "
                  f"(range: {note_name(low)} - {note_name(high)})")
        else:
            print(f"  Octave limit reached ({self.octave_offset:+d})")


def main():
    parser = argparse.ArgumentParser(
        description="Glove80 Instrument Mode Bridge — keyboard to MIDI translator"
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
    args = parser.parse_args()

    if args.list:
        devices = list_keyboard_devices()
        if not devices:
            print("No keyboard devices found. Try running as root or add user to 'input' group.")
        else:
            print("Available keyboard devices:")
            for path, name, phys in devices:
                print(f"  {path}: {name}")
                print(f"    phys: {phys}")
        return

    bridge = InstrumentBridge(
        device_path=args.device,
        midi_port_name=args.port,
    )

    signal.signal(signal.SIGTERM, lambda *_: bridge.stop())

    bridge.start()


if __name__ == "__main__":
    main()
