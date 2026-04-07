# Prototype bridge — `glove80-bridge`

A macOS menu-bar app that turns the Glove80 into a MIDI instrument.

This is the **Device 0.5 → 0.8 reference implementation**. It captures HID
events from the Glove80 via `CGEventTap`, computes MIDI notes from a
keycode → note table, classifies velocity from inter-note intervals, runs a
per-hand pitch-bend glide engine, and emits MIDI through a virtual CoreMIDI
port that DAWs can subscribe to.

> **Do not run this alongside Device 1.0 firmware.** Both implementations
> generate MIDI from the same physical key events; running them together will
> double every note.

## Files

| File                  | Purpose |
|-----------------------|---------|
| `tray_app.py`         | Menu-bar app entrypoint, MIDI dispatcher, mode controller, R1 glide engine |
| `physical_layout.py`  | Keycode → MIDI note maps, isomorphic anchor math, bass register tables |
| `hid_reader_macos.py` | `CGEventTap` capture, USB keyboard-type filter, hardware timestamps |
| `hid_reader.py`       | Linux `evdev` capture (incomplete — Linux not supported in this prototype) |
| `midi_output.py`      | python-rtmidi virtual CoreMIDI port wrapper + ALSA fallback |
| `pitch_map.py`        | Default note → MIDI mapping table for chromatic mode |
| `glove80_bridge.py`   | Headless bridge entrypoint (no menu bar) |
| `stock_bridge.py`     | Bare-minimum reference bridge for testing CoreMIDI plumbing |
| `config.py`           | JSON config loader |
| `bridge_config.json`  | Default config (base note, scale, channel, octave) |
| `requirements.txt`    | `python-rtmidi`, `pyobjc-framework-Quartz`, `rumps` |

## Quick start

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 tray_app.py
```

Then grant Accessibility permission in System Settings → Privacy & Security
when prompted, and click **Start Bridge** in the 🎹 menu-bar icon.

See the parent [`prototype/README.md`](../README.md) for the full architecture
narrative and the lessons learned.
