# `zmk-patches` — prototype firmware modifications

Patches and net-new source files that turn an unmodified [`darknao/zmk`
`rgb-layer-25.08`](https://github.com/darknao/zmk) checkout into the Glove80
MIDI instrument prototype firmware.

## Upstream pin

| Field    | Value |
|----------|-------|
| Repo     | [`darknao/zmk`](https://github.com/darknao/zmk) |
| Branch   | `rgb-layer-25.08` |
| Commit   | `8aeaaa66fbb4b94948c8763e06f1920ab0b69480` |

The fork itself sits on top of `zmkfirmware/zephyr` at `v3.5.0+zmk-fixes`,
which is what `west update` will resolve from `zmk/app/west.yml`.

## What's in here

### `modifications.patch`

A `git diff` against the upstream fork covering **seven existing files** that
the prototype modifies in place:

| File                                  | Why we touch it |
|---------------------------------------|-----------------|
| `app/CMakeLists.txt`                  | Add the new `instrument_*.c` and `behavior_instrument.c` sources |
| `app/Kconfig`                         | Add `CONFIG_ZMK_INSTRUMENT_MODE` and friends |
| `app/dts/behaviors.dtsi`              | Include `instrument.dtsi` so `&inst` is available everywhere |
| `app/include/zmk/rgb_underglow.h`     | Export the brightness getter the instrument render path needs |
| `app/src/rgb_underglow.c`             | Brightness `/0xFF`→`/100` fix; instrument hook in `set_layer`; brightness getter |
| `app/src/split/bluetooth/central.c`   | Encode instrument state into the layer bitmask before sending to peripheral |
| `app/src/split/bluetooth/service.c`   | Decode instrument state on the peripheral side; mutex around `layers` |

### `new-files/`

Net-new source files added by the prototype, mirroring their target paths
under `zmk/app/`:

| File                                                      | Purpose |
|-----------------------------------------------------------|---------|
| `app/dts/behaviors/instrument.dtsi`                       | Devicetree declaration for the `&inst` behavior |
| `app/dts/bindings/behaviors/zmk,behavior-instrument.yaml` | Binding schema for `&inst` |
| `app/include/zmk/instrument_mode.h`                       | Per-hand state struct, command defines |
| `app/include/zmk/instrument_rgb.h`                        | Render API + position table accessors |
| `app/src/instrument_mode.c`                               | State machine, event listeners, split sync encode/decode, iso anchor logic |
| `app/src/instrument_rgb.c`                                | 80-entry position table, 12 chromatic note colors, color cache, render loop |
| `app/src/behaviors/behavior_instrument.c`                 | The `&inst` behavior implementation |

## How to apply

```sh
# Inside an unmodified darknao/zmk @ rgb-layer-25.08 / 8aeaaa66:
git apply /path/to/midigloves/prototype/firmware/zmk-patches/modifications.patch
cp -r /path/to/midigloves/prototype/firmware/zmk-patches/new-files/app/* app/
```

Then build per the parent [`prototype/README.md`](../../README.md#how-to-rebuild-the-prototype-firmware).

## Why a patch instead of a Zephyr module?

Because the prototype was written **iteratively, in place** inside the ZMK
fork. Several of the modifications (the brightness fix, the split sync
encoding, the layer-change hook) cross the boundary between application code
and core firmware in ways that would be awkward to expose through a clean
out-of-tree module API. Device 1.0 will refactor the instrument code into a
proper Zephyr module to make it easier for others to integrate, but the
prototype is preserved here in its original form because that's the form
that was actually built and validated.
