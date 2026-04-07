# Architecture

This document describes the Device 1.0 architecture of midigloves. The
Device 0.5 → 0.8 prototype architecture (Python bridge + CGEventTap) is
preserved under [`../prototype/`](../prototype/) for reference and is not
described here.

## High-level data flow

```
 ┌──────────────────────────────────────────────────────────────┐
 │                 Glove80 hardware (2× nRF52840)               │
 │                                                              │
 │  LH (central)                      RH (peripheral)           │
 │  ┌────────────────┐                ┌────────────────┐        │
 │  │  matrix scan   │                │  matrix scan   │        │
 │  │       │        │                │       │        │        │
 │  │       ▼        │                │       ▼        │        │
 │  │  ZMK keymap    │                │  ZMK keymap    │        │
 │  │       │        │                │       │        │        │
 │  │       ▼        │   split BLE    │       │        │        │
 │  │  instrument  ◄─┼────────────────┼── key events   │        │
 │  │  state machine │                │                │        │
 │  │   │     │      │                │                │        │
 │  │   │     ▼      │   split event  │       ▼        │        │
 │  │   │   scale ───┼────────────────┼──► scale sync  │        │
 │  │   │     │      │                │       │        │        │
 │  │   ▼     ▼      │                │       ▼        │        │
 │  │  midi   rgb    │                │  rgb (cache)   │        │
 │  │   │     │      │                │       │        │        │
 │  └───┼─────┼──────┘                └───────┼────────┘        │
 │      │     │                               │                 │
 │      │     └──────── 80 per-key LEDs ──────┘                 │
 │      │                                                       │
 │      ├──── USB-MIDI (class-compliant, wired)                 │
 │      └──── BLE-MIDI  (GATT, wireless)                        │
 └──────┬───────────────────────────────────────────────────────┘
        │
        ▼
 ┌──────────────────────────┐
 │    Host (Mac / iPad /    │
 │    Linux / etc.)         │
 │                          │
 │   MIDI in  ─── notes, pitch bend, CC on ch1 / ch2 / ch3      ─▶ DAW
 │   MIDI out ─── SysEx F0 7D 01 root mask_lo mask_hi F7        ◀─ DAW
 │                                                              │
 │   (Ableton Live: the ableton-remote-script/ observes Live's  │
 │    scale and generates the SysEx above)                      │
 └──────────────────────────────────────────────────────────────┘
```

## The Glove80 is a real USB-MIDI device

Layers 0–2 (Base / Lower / Magic) still type to the host via USB HID. Layer 3
(Instrument) doesn't generate keystrokes — it generates MIDI. Both classes
coexist as a USB composite device. BLE exposes a matching pair: HoG for
typing and BLE-MIDI for playing, on the same paired slot.

This is a **hard** structural change from the prototype, which hijacked HID
keystrokes on the Mac via `CGEventTap` and translated them to MIDI in a
Python bridge. In Device 1.0 the host never sees instrument-layer keystrokes
at all — the firmware generates MIDI directly.

## Three MIDI channels

| Ch | Source zone                                | Role              | Pitch bend control        |
|----|--------------------------------------------|-------------------|---------------------------|
| 1  | `ZONE_GRID`, hand 0 (LH main grid)         | Melody / lead     | R1 LH glide keys          |
| 2  | `ZONE_GRID`, hand 1 (RH main grid)         | Harmony / counter | R1 RH glide keys          |
| 3  | `ZONE_THUMB` ∪ `ZONE_BASS` (thumbs + R6)   | Bass / pedal      | R6 bass_semi_dn/up (hold) |

The routing rule in `firmware/module/src/midi.c` is one line:

```c
uint8_t channel_for_pos(uint8_t pos) {
    return (instrument_pos_zone(pos) == ZONE_GRID)
        ? instrument_pos_hand(pos)   // 0 or 1 → ch1 or ch2
        : 2;                         // thumbs + bass → ch3
}
```

Channels 4–16 are reserved for a future MPE upgrade (one channel per note
per hand) if pressure sensors ever get added to the Glove80.

## Two transports, one MIDI surface

Both USB-MIDI and BLE-MIDI are always active when available. The host picks
which port to listen to; the firmware sends notes to everywhere it can.
SysEx reception works the same way — the firmware accepts scale updates from
either transport and dispatches into a single handler.

## Scale state and RGB rendering

The firmware stores two values:

- `active_root`: 0–11 (C to B)
- `active_scale_mask`: 12-bit, bit `i` set means note class `i` is in-scale

The 80-entry RGB color cache is rebuilt whenever scale state changes. On the
grid (and only on the grid — bass/thumb/control keys keep their styling), an
out-of-scale note class gets the 20% saturation + 50% brightness transform
baked into its cached color. Render is unchanged: per pixel per frame, read
from the cache, scale by global brightness, write to the LED buffer.

## Split half sync

The RH peripheral needs the same instrument and scale state as the LH central
to render matching colors. Two sync channels:

1. **Layer-bitmask piggyback** (carried from prototype): the 16-bit
   per-hand instrument state (mode, semi offset, iso anchor offset) rides
   inside the high bits of the ZMK layer bitmask split sync. Cheap and
   works — it was proven in Device 0.8.
2. **New `ZMK_SPLIT_TRANSPORT_PERIPHERAL_EVENT_TYPE_SCALE` event** (new in
   Device 1.0): a dedicated 3-byte event carrying `{root, mask_low, mask_high}`
   for scale propagation. Supports arbitrary custom scales from the bridge,
   not just a 4-bit index.

The new event is a small patch against darknao/zmk's split transport types
union — see [`../firmware/zmk-fork-patches/`](../firmware/zmk-fork-patches/).

## Ableton Live Remote Script ("Bridge 3.0")

A small Python script that lives inside Live, subscribes to scale observers on
Live's Song object (`root_note`, `scale_intervals`, `scale_mode`), builds the
12-bit mask, and sends it to the Glove80 as SysEx. About 80 lines of Python.
No macOS menu bar, no keystroke capture, no DAW-specific MIDI plumbing — just
"when Live's scale changes, tell the keyboard about it".

See [`../ableton-remote-script/`](../ableton-remote-script/) and
[`scale-sysex.md`](scale-sysex.md) for specifics.

## What's in firmware, what's in the DAW

| Concern                 | Location |
|-------------------------|----------|
| Keycode → MIDI note map | Firmware (single source of truth) |
| Three-channel routing   | Firmware |
| Velocity (v1: fixed 92) | Firmware |
| Pitch-bend glide        | Firmware (`k_timer`-driven, generation counter) |
| Note On/Off retrigger   | Firmware (80-slot held-notes table) |
| Panic on layer exit     | Firmware |
| Out-of-scale dimming    | Firmware (baked into RGB color cache) |
| Active scale detection  | DAW-side (Ableton Remote Script observes LOM) |
| Scale → SysEx encoding  | DAW-side |
| SysEx → scale state     | Firmware |

The old prototype's `physical_layout.py` was the source of truth for note
mapping on the host side; `instrument_rgb.c` was the source on the firmware
side. The two had to stay in sync by hand and drifted multiple times. In
Device 1.0 the firmware is the single source of truth — the DAW has no idea
what notes the grid plays, it only sends scale information.
