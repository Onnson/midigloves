# MIDI protocol

This document specifies the MIDI behavior of the midigloves Device 1.0
firmware: channel assignment, note generation, velocity, pitch bend, panic,
and retrigger semantics. It is the contract between the firmware and any
DAW or MIDI host.

For the host-to-firmware scale SysEx format, see
[`scale-sysex.md`](scale-sysex.md).

## Transport

- **USB-MIDI**: class-compliant USB-MIDI 1.0 (audio class `0x01` / subclass
  `0x03` / MIDIStreaming). Works on any host without drivers.
- **BLE-MIDI**: standard BLE-MIDI GATT service (UUID
  `03B80E5A-EDE8-4B33-A024-BC5E9C7B1B25`). Works with macOS Audio MIDI Setup,
  iOS, most modern DAWs.
- Both transports are active simultaneously when available.
- The firmware sends each MIDI message to every active transport. The host
  picks which port to listen to.

## Channels

| MIDI channel | Source                                | Voice role          |
|--------------|---------------------------------------|---------------------|
| 1            | Left hand main grid (`ZONE_GRID` / hand 0)  | Melody / lead |
| 2            | Right hand main grid (`ZONE_GRID` / hand 1) | Harmony / counter |
| 3            | Bass register (`ZONE_THUMB` ∪ `ZONE_BASS`)  | Bass / pedal |

Channels 4–16 are unused in Device 1.0 and reserved for a future MPE upgrade.

**Routing rule** (in `firmware/module/src/midi.c`):

```c
uint8_t channel_for_pos(uint8_t pos) {
    return (instrument_pos_zone(pos) == ZONE_GRID)
        ? instrument_pos_hand(pos)   // 0 or 1
        : 2;
}
```

The 1-indexed channel number sent on the wire is `channel_for_pos(pos) + 1`.

## Note On / Note Off

- **Note On**: `0x90 | (ch-1)`, `note`, `velocity`
- **Note Off**: `0x80 | (ch-1)`, `note`, `0`
- Note numbers follow the MIDI standard (middle C = 60)
- Layout: each half has two 2-row × 6-column blocks; block 0 starts at the
  hand's configured base note, block 1 = base + 12. Per-column offsets
  within a block (matches [`physical_layout.py`](../prototype/bridge/physical_layout.py)
  carried from the prototype):

  ```
  Upper row: C#  D#  F   F#  G#  A#   (+1 +3 +5 +6 +8 +10)
  Lower row: C   D   E   G   A   B    ( 0 +2 +4 +7 +9 +11)
  ```

- All 12 chromatic notes per octave block, no duplicates.

## Velocity

**Device 1.0: fixed 92.** Every Note On uses velocity 92.

This is a deliberate simplification — the prototype's sticky 3-tier velocity
classifier is preserved as a reference algorithm in
[`../prototype/bridge/tray_app.py`](../prototype/bridge/tray_app.py) but not
ported to firmware until the post-1.0 velocity phase.

Why: honest velocity measurement requires peripheral-side event
timestamping, which is an ABI change to ZMK's split transport. Not blocking
for v1 ship but worth doing cleanly.

## Retrigger semantics

The firmware maintains an 80-slot held-notes table mapping position → (note,
channel). Any time a state change causes a key's note to change while it's
held (semi shift, iso mode toggle, bass semi tap, octave shift), the firmware
emits:

1. Note Off for the old `(note, channel)`
2. Note On for the new `(note, channel)` at fixed velocity 92

Same-position re-press with the old entry still in the table (shouldn't
happen but we guard) does the same Note Off → Note On sequence.

**Cross-channel retrigger** (e.g., if a key somehow moved zones mid-hold) is
handled correctly because the held-notes entry stores the channel the original
Note On used, not the current position's zone.

## Pitch bend

- Bend range is set to **±12 semitones** via RPN 0/0 (`CC 101 0`, `CC 100 0`,
  `CC 6 12`) on all three channels at module init and after any panic
- Per-channel state, independent: ch1, ch2, ch3 bends don't interfere
- Message format: `0xE0 | (ch-1)`, LSB, MSB — 14-bit value 0x0000..0x3FFF,
  center 0x2000

### Glide engine

Each of the three channels has its own software glide engine driven by a
`k_timer` at 13 ms tick rate:

- `midigloves_glide_set_target(channel, semitones, ramp_ms)` sets a new target
  and ramp duration
- The tick handler interpolates from current bend toward target, sends
  Pitch Bend messages, re-arms until the target is reached
- Each call to `set_target` increments a per-channel generation counter; in-
  flight ticks from the previous call check their captured generation and
  exit early

### Glide triggers

- **R1 LH glide keys** drive channel 1
- **R1 RH glide keys** drive channel 2
- **R6 bass_semi_dn** (LH R6 col 1) — hold-tap (`&inst_ht`, 150 ms tapping-term):
  - Tap → discrete bass register semitone shift (preserved from prototype)
  - Hold → channel 3 bend down until release
- **R6 bass_semi_up** (RH R6 col 4) — same hold-tap, opposite direction

## Control Change

- `CC 123` (All Notes Off) and `CC 120` (All Sound Off) are sent on all three
  channels as part of the panic sequence
- No other CCs are sent in Device 1.0

## Panic

The firmware emits a panic sequence in three situations:

1. Exiting the instrument layer (any key that toggles layer 3 off)
2. USB disconnect while the instrument layer is active
3. On receipt of a `CC 123` from the host (mirrors it, stopping any local sources)

The panic sequence, sent per channel on channels 1, 2, and 3:

```
CC 123  0    (All Notes Off)
CC 120  0    (All Sound Off)
```

Between the two CCs on a given channel, the firmware also iterates its held-
notes table and sends explicit Note Off messages for every entry. This
belt-and-suspenders approach handles synths that ignore CC 123.

After a panic, pitch bend is **not** reset to center — the host is assumed
to do this on receipt of `All Sound Off`. If your synth keeps a stuck bend,
send `RPN 0/0` or a pitch bend to 0x2000 manually.

## Manufacturer SysEx

The firmware responds to a single SysEx message for scale updates:

```
F0 7D 01 <root> <mask_lsb> <mask_msb> F7
```

Manufacturer ID `0x7D` is the MIDI Manufacturers Association's reserved
"non-commercial / educational" ID. Command byte `0x01` = "set scale". See
[`scale-sysex.md`](scale-sysex.md) for the full spec.

All other inbound SysEx is ignored.

## What the firmware does NOT send

- Program Change
- Channel Pressure
- Poly Aftertouch
- System Common / Real Time
- MPE configuration (CC 127)
- Any CC other than panic 123/120 and RPN 0/0 at init

If you need any of these in your workflow, add them to `firmware/module/src/midi.c`
and send a PR.
