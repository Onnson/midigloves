# `usb_midi_test` — USB-MIDI driver vetting sample

**Throwaway Zephyr sample app.** Its only job is to prove that
[`stuffmatic/zephyr-usb-midi`](https://github.com/stuffmatic/zephyr-usb-midi)
actually works on the Glove80 hardware before we integrate it into the real
firmware. This is the first verification step of Milestone 1.

If this sample doesn't work, nothing downstream will, and we'd rather discover
that in 50 lines of code than 2,000.

## What it does

- Pulls in only the `zephyr-usb-midi` module — no HID, no ZMK, no instrument logic
- Configures the device as a single USB-MIDI interface
- On boot, sends one Note On (middle C = MIDI 60) on channel 1
- Echoes any received SysEx to the log

## How to build + flash

```sh
# From the west workspace root:
west build -s firmware/samples/usb_midi_test -b glove80_lh
```

Flash the resulting `build/zephyr/zmk.uf2` to the **left half only**.
(The right half isn't involved — this test doesn't touch split transport.)

## How to verify

1. Plug the LH half into a Mac via USB-C
2. **Audio MIDI Setup**: a device called "Glove80 USB-MIDI Test" should appear
3. **Ableton Live** → Preferences → Link MIDI → Input: enable the test device
4. Arm a MIDI track. The Note On should arrive at boot.
5. Send a SysEx from Live (or any SysEx utility) — it should echo in the
   Zephyr log over RTT / J-Link / console

If all four checks pass, proceed to Milestone 1.2 (port the prototype
instrument module). If they don't, debug here — do not proceed to composite
integration until this sample is green.

## Status

**Milestone 1.1.** Files land when Milestone 1 begins. During Milestone 0
only this README exists.
