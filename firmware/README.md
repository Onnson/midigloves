# `firmware/` — Device 1.0 firmware

The Glove80 MIDI instrument firmware. Built on top of the
[darknao/zmk](https://github.com/darknao/zmk) `rgb-layer-25.08` fork of ZMK,
with our own out-of-tree Zephyr module under [`module/`](module/) adding the
instrument state machine, chromatic RGB rendering, three-channel USB/BLE MIDI
dispatch, pitch-bend glide, and Ableton scale crosstalk.

## Layout

| Path                  | Purpose |
|-----------------------|---------|
| [`module/`](module/)  | The `midigloves` Zephyr out-of-tree module — all the new code |
| [`config/`](config/)  | Glove80-specific build config: keymap, Kconfig, west manifest |
| [`zmk-fork-patches/`](zmk-fork-patches/) | Small unavoidable patches against darknao/zmk (brightness fix, split-sync hooks, CMake wiring) |
| [`samples/usb_midi_test/`](samples/usb_midi_test/) | Throwaway Zephyr sample that verifies the USB-MIDI module works on the Glove80 before we touch the real build |

## Prerequisites

- Linux or macOS with Python 3.10+ and west (`pip install west`)
- [Zephyr SDK 0.17.0](https://github.com/zephyrproject-rtos/sdk-ng/releases/tag/v0.17.0)
- A MoErgo Glove80 (instructions assume you've made a stock backup first — see `../prototype/firmware/flash-guide.md`)

## Build

```sh
# One-time workspace init
python3 -m venv .venv && source .venv/bin/activate
pip install west
west init -l firmware/config
west update
export ZEPHYR_SDK_INSTALL_DIR=~/zephyr-sdk-0.17.0

# Apply the unavoidable ZMK fork patches
firmware/zmk-fork-patches/apply.sh

# Build both halves
west build -s zmk/app -b glove80_lh -- -DZMK_CONFIG="$(pwd)/firmware/config"
mv build build_lh
west build -s zmk/app -b glove80_rh -d build_rh -- -DZMK_CONFIG="$(pwd)/firmware/config"
```

UF2s end up at `build_lh/zephyr/zmk.uf2` and `build_rh/zephyr/zmk.uf2`.

## Flash

See [`../docs/building-and-flashing.md`](../docs/building-and-flashing.md) for
the full procedure (right half first, factory reset + BLE re-pair after any
firmware version change). A summary lives in
[`../prototype/firmware/flash-guide.md`](../prototype/firmware/flash-guide.md)
and still applies verbatim to Device 1.0.

## Status

**Milestone 0: scaffold.** The module directory, config directory, and patch
directory exist with stub content. Nothing here builds into a working
instrument yet — the first working build lands at Milestone 1.

## Current state

The working firmware is still the Device 0.8 prototype under
[`../prototype/firmware/`](../prototype/firmware/). Device 1.0 is under
active development. See
[`../README.md`](../README.md) and the Device 1.0 plan for the roadmap.
