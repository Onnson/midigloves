# midigloves

Turn the [MoErgo Glove80](https://www.moergo.com/) ergonomic keyboard into a
chromatic MIDI instrument with per-key RGB feedback that mirrors the active
musical scale.

This repository is the in-progress home for **Device 1.0** — a native USB-MIDI
and BLE-MIDI firmware that runs on the Glove80's two nRF52840 halves, paired
with a tiny Ableton Live Remote Script that pushes the active scale back to
the keyboard so out-of-scale keys dim while in-scale keys glow at full
chromatic color.

## Status

- **Device 1.0 / Bridge 3.0** — under active design. The firmware will be a
  composite USB device (HID + USB-MIDI) so the Glove80 keeps working as a
  normal keyboard for layers 0–2 and becomes a real MIDI instrument on layer 3.
  BLE-MIDI ships in parallel for wireless play. The bridge becomes an Ableton
  Live Remote Script that observes Live's scale settings and sends the active
  scale to the keyboard via SysEx.
- **Device 0.5 → 0.8 prototype** — fully functional Python-bridge based
  implementation that proved out the layout, the chromatic-color rendering,
  the isomorphic layer, the bass register, the per-hand semitone shift, and
  the pitch-bend glide controls. **Preserved verbatim under
  [`prototype/`](prototype/).** Read [`prototype/README.md`](prototype/README.md)
  for what it does, what it costs, and how to run it.

## Why

The Glove80 has 80 individually-addressable RGB LEDs and two nRF52840 MCUs
running open-source ZMK firmware. That is the closest thing to a programmable
chromatic instrument hidden inside a normal keyboard. With a layout designed
around two-octave grids and a per-hand semitone shift, you can play melodies,
harmonies, and bass lines with the same muscle memory you already have for
typing — and the keys can light up to tell you what notes you're playing and
which ones belong to the current key.

## Layout philosophy (carried over from the prototype)

Each half has a **2-row × 6-column block** that covers a full octave:

```
Upper row:  C#  D#  F   F#  G#  A#
Lower row:  C   D   E   G   A   B
```

All 12 chromatic notes per octave block, no duplicates, both rows ascending.
Two blocks per half = 2 octaves per hand. The block scheme rhymes with the
white-key / black-key visual division of a piano while staying playable with a
typist's muscle memory. A separate **bass register** lives on the bottom row
and thumbs and gets its own MIDI channel.

## Three MIDI channels

| Channel | Source           | Notes               |
|---------|------------------|---------------------|
| 1       | Left hand grid   | Melody / lead       |
| 2       | Right hand grid  | Harmony / counter   |
| 3       | Bass register    | Bass / pedal        |

This split is designed so a DAW like Ableton Live can route each channel to a
different instrument or MIDI effect chain.

## Hardware

- [MoErgo Glove80](https://www.moergo.com/) — 80-key split contoured ergonomic
  keyboard with 80 per-key RGB LEDs and two nRF52840 MCUs.
- USB-C connection from the left half (the central) to the host.
- Wireless play over BLE with the optional batteries.

## Firmware base

- [ZMK firmware](https://github.com/zmkfirmware/zmk) — the open-source mechanical
  keyboard firmware platform.
- [darknao/zmk `rgb-layer-25.08`](https://github.com/darknao/zmk) — a fork of
  ZMK that adds per-layer RGB underglow control. The prototype builds on top
  of this fork; Device 1.0 will pull the same fork plus out-of-tree Zephyr
  modules for USB-MIDI and BLE-MIDI.

## Repository layout

```
midigloves/
├── README.md                  ← you are here
├── LICENSE                    ← MIT
├── .gitignore
└── prototype/                 ← the working Device 0.5 / 0.8 implementation
    ├── README.md              ← how the prototype works, how to build it
    ├── bridge/                ← Python macOS menu-bar bridge (CGEventTap → MIDI)
    ├── firmware/              ← ZMK config + zmk-patches needed to rebuild
    ├── uf2/                   ← prebuilt UF2s for left and right halves
    ├── editor-exports/        ← MoErgo editor JSON / .keymap exports
    ├── docs/                  ← design notes, RGB scheme, USB-MIDI research
    └── tools/                 ← color computation, flashing helpers
```

The Device 1.0 source tree will land at the repository root once the design
work is complete.

## License

[MIT](LICENSE) — use it, fork it, mod it, ship it.
