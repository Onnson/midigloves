# Prototype firmware — Device 0.5 / 0.8

ZMK config and custom-module sources for the Glove80 MIDI instrument
prototype. Builds against [`darknao/zmk` `rgb-layer-25.08`](https://github.com/darknao/zmk)
at commit `8aeaaa66`, which is a fork of mainline ZMK with per-layer RGB
underglow control.

## Files

| Path                        | What it is |
|-----------------------------|------------|
| `config/glove80.keymap`     | The instrument-layer keymap with `&vel` hold-taps, `&inst` macros, R1 controls, bass register, mode toggles |
| `config/glove80.conf`       | Kconfig overrides — NKRO, debounce, BLE split timings, RGB enable |
| `config/west.yml`           | West manifest pointing at `darknao/zmk` |
| `zmk-patches/modifications.patch` | `git diff` against the unmodified `darknao/zmk` fork — see [`zmk-patches/README.md`](zmk-patches/README.md) |
| `zmk-patches/new-files/`    | Net-new source files added by the prototype |
| `flash-guide.md`            | Step-by-step flash + recovery procedure |

## Build

See [`../README.md`](../README.md#how-to-rebuild-the-prototype-firmware) for
the full sequence (west init, patch apply, build, flash).
