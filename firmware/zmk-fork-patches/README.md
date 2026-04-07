# `zmk-fork-patches/` — unavoidable patches against darknao/zmk

Most of the Device 1.0 firmware lives in the out-of-tree module under
[`../module/`](../module/) — exactly so contributors don't have to patch a
fork to consume it. But a handful of hooks into ZMK internals are
unavoidable: the RGB brightness scale has an upstream bug, the split transport
needs new event types for scale propagation, and the app's CMakeLists needs
to include our module. Those live here as `.patch` files with an
`apply.sh` helper.

## Upstream pin

| Field  | Value |
|--------|-------|
| Repo   | [`darknao/zmk`](https://github.com/darknao/zmk) |
| Branch | `rgb-layer-25.08` |
| Commit | `8aeaaa66fbb4b94948c8763e06f1920ab0b69480` |

The fork itself carries `zmkfirmware/zephyr` at `v3.5.0+zmk-fixes`, which is
what `west update` will resolve from `zmk/app/west.yml`.

## Patches (land across Milestones 1 + 2 + 4)

| File | Milestone | Why |
|------|-----------|-----|
| `rgb-underglow-brightness.patch`     | M1 | `/0xFF` → `/100` brightness scale fix + brightness getter export |
| `split-sync-instrument-state.patch`  | M1 | Layer-bitmask piggyback for per-hand instrument state (mode, semi offset, iso anchor) |
| `app-cmake-module-include.patch`     | M1 | Wire the `midigloves` module into the app's CMakeLists / Kconfig / DTS |
| `split-event-scale.patch`            | M2 | Add `ZMK_SPLIT_TRANSPORT_PERIPHERAL_EVENT_TYPE_SCALE` for scale state propagation |
| `zephyr-usb-midi-composite.patch`    | M1 | (conditional) USB composite interface numbering fix for stuffmatic module |
| `zephyr-ble-midi-adv.patch`          | M4 | (conditional) Add BLE-MIDI service UUID to BLE adv payload |

## Usage

```sh
# From the west workspace root, after `west update`:
firmware/zmk-fork-patches/apply.sh
```

`apply.sh` `git apply`s each patch from the correct cwd. It's idempotent: if a
patch is already applied, it skips and moves on. To revert a patch, run
`git checkout` against the modified files inside the `zmk` subdirectory.

## Status

**Milestone 0: scaffold.** Only this README exists. Patches land as the
milestones that need them begin — the first three (M1) are the initial
carry-over from
[`../../prototype/firmware/zmk-patches/modifications.patch`](../../prototype/firmware/zmk-patches/modifications.patch),
split into focused files and re-derived against a clean darknao checkout.
