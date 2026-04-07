# USB + MIDI + Ableton integration notes (for implementing agents)

## USB first
- Prefer USB as the active ZMK output endpoint for low-latency performance use.

## ZMK output selection (important for development)
- ZMK supports an Output Selection behavior to choose USB vs BLE when both are connected.
- Default: output goes to USB when both are connected.
- The selected output is remembered (persisted), so a “force USB” binding can be used during dev.

## Ableton mapping + feedback (relevant now, critical for Clip mode later)
- Ableton “Making custom MIDI Mappings”:
  - Enable Remote on the MIDI Input port to map controls.
  - For visual feedback (lights/feedback on knobs), enable Remote on the MIDI Output port for the same device.

## RGB implementation hint from the community
- There are community Glove80 ZMK configs that mention “per layer / per key RGB underglow” (useful prior art for implementing per-key/per-layer lighting behavior in a ZMK fork).
