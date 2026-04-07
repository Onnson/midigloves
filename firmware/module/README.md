# `midigloves` — Zephyr out-of-tree module

This is the firmware core of the Glove80 MIDI instrument. It's packaged as a
standard Zephyr out-of-tree module so any ZMK build can consume it by adding
a single entry to its `west.yml`.

## What it contains (landing across Milestones 1–4)

| Subsystem | Files | Milestone |
|-----------|-------|-----------|
| Instrument state machine | `src/instrument.c`, `include/midigloves/instrument.h` | M1 |
| RGB rendering + out-of-scale dimming | `src/instrument_rgb.c` | M1 + M2 |
| `&inst` behavior | `src/behavior_instrument.c`, `dts/behaviors/instrument.dtsi`, binding YAML | M1 |
| `&inst_ht` hold-tap (tap=bass shift, hold=bass glide) | `src/behavior_instrument_ht.c`, `dts/behaviors/instrument_ht.dtsi`, binding YAML | M1 |
| USB + BLE MIDI dispatch, channel routing, panic | `src/midi.c`, `include/midigloves/midi.h` | M1 + M3 + M4 |
| Three-channel pitch-bend glide engine | `src/midi_glide.c` | M1 |
| Scale state, mask rotation, SysEx handler | `src/scale.c`, `include/midigloves/scale.h` | M2 + M3 |

## Channel routing

| MIDI ch | Zone                           | Voice role |
|---------|--------------------------------|------------|
| 1       | `ZONE_GRID`, hand 0 (LH)       | Melody / lead |
| 2       | `ZONE_GRID`, hand 1 (RH)       | Harmony / counter |
| 3       | `ZONE_THUMB` ∪ `ZONE_BASS`     | Bass / pedal |

See [`../../docs/midi-protocol.md`](../../docs/midi-protocol.md) for the
full protocol spec (retrigger semantics, bend range, panic sequence).

## Kconfig

```
CONFIG_MIDIGLOVES=y          # top-level gate
CONFIG_MIDIGLOVES_USB=y      # USB-MIDI transport (default on)
CONFIG_MIDIGLOVES_BLE=y      # BLE-MIDI transport (default off, on after M4)
```

## Consuming from your own build

Add this module as a west project in your build config's `west.yml`:

```yaml
- name: midigloves
  url: https://github.com/Onnson/midigloves
  revision: main
  path: modules/midigloves
  import:
    path-prefix: firmware/module
```

Then enable `CONFIG_MIDIGLOVES=y` in your `prj.conf`. See
[`../config/`](../config/) for the Glove80-specific build config that we use.

## Status

**Milestone 0: scaffold.** The module currently contains only `module.yml`,
`CMakeLists.txt`, and `Kconfig`. Source files land in subsequent milestones.
A build that enables `CONFIG_MIDIGLOVES=y` at this stage links an empty
library successfully.
