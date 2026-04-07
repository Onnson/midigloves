# `firmware/config/` — Glove80 build config

The project-specific build configuration that turns the generic ZMK build into
the Glove80 MIDI instrument. This directory is what you pass to
`west init -l firmware/config` and `-DZMK_CONFIG=...` at build time.

## Files

| File             | Purpose |
|------------------|---------|
| `west.yml`       | West manifest — pulls darknao/zmk + stuffmatic USB/BLE MIDI + this repo's midigloves module |
| `glove80.keymap` | Keymap: base / lower / magic / instrument layers, `&inst` macros, R1 controls (lands in M1, carried from prototype) |
| `glove80.conf`   | Kconfig overrides: NKRO, split BLE timings, RGB, `CONFIG_MIDIGLOVES*` (lands across M1 + M4) |

## Status

**Milestone 0: scaffold.** Only `west.yml` is in its final form. The keymap
and `.conf` files land during Milestone 1 (carried over from the prototype
and adapted to the new module include paths).
