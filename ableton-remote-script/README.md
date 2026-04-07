# `ableton-remote-script/` — Bridge 3.0

An Ableton Live Remote Script (Python, loaded by Live at startup) that reads
Live's active scale via the Live Object Model and sends it to the Glove80 as
a short SysEx message. The firmware applies the scale to its RGB rendering
and dims out-of-scale keys.

This replaces the Device 0.5 → 0.8 Python bridge entirely. The old bridge
captured keystrokes and generated MIDI; this one does neither — the firmware
is now a real MIDI device and this script just pushes scale state back to it.

## What lives here

| Path                      | Purpose |
|---------------------------|---------|
| `Glove80/__init__.py`     | Remote Script entrypoint (Live calls `create_instance`) |
| `Glove80/Glove80.py`      | `ControlSurface` subclass: LOM listeners + SysEx encoder + send |
| `tests/test_mask_encoding.py` | Offline pytest — verifies SysEx bytes for canonical scales, no Live needed |

## Install

```sh
# macOS (Ableton Live 11+)
cp -r Glove80 ~/Music/Ableton/User\ Library/Remote\ Scripts/

# Then in Live:
#   Preferences → Link MIDI → Control Surfaces
#   Control Surface: Glove80
#   Input:           Glove80
#   Output:          Glove80
```

## What the bridge does

- On load, subscribes to `song.root_note`, `song.scale_intervals`, `song.scale_mode` observers
- Whenever any of the three changes, computes a 12-bit interval mask and sends
  `F0 7D 01 <root> <mask_lsb> <mask_msb> F7` to the Glove80 MIDI output
- On script load, pushes the current Live scale immediately so the keyboard
  matches whatever was set before the script loaded
- On script unload, removes the listeners cleanly

## Offline tests

```sh
python3 -m pytest ableton-remote-script/tests/
```

These are pure-Python unit tests of the SysEx encoder — no Live, no MIDI, no
Glove80 required. Runs in CI.

## SysEx protocol

See [`../docs/scale-sysex.md`](../docs/scale-sysex.md) for the complete spec.
The format is deliberately simple so alternative bridges (Logic, Reaper, Bitwig,
standalone Python scripts) can be written without reference to this code.

## Status

**Milestone 3.** Files land when the firmware SysEx handler (M3) is ready.
During Milestones 0–2 only this README exists.
