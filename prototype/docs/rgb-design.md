# Instrument mode: per-key RGB semantics (v0)

## Requirement
- True per-key RGB from day 1 (not just global underglow effects).

## What the official docs imply
- MoErgo’s RGB documentation presents RGB as “underglow” with global effect controls (toggle/effects/brightness/hue/saturation/speed) and battery-saving dim/off behavior.
- Therefore, implementers should assume per-key semantics require firmware-side customization rather than only using stock “effect cycling”.

## Proposed RGB semantics (v0)
Pick a color palette later; define semantics now:

- In-scale: on, medium brightness.
- Root: brightest (or distinct hue).
- Chord tones / “currently held notes”: highlight overlay (higher brightness or alternate hue).
- Out-of-scale: dim or off.
- Octave shift state:
  - LH R2/C6 and RH R2/C6 show current octave offset (e.g., different colors for -2..+2, blinking at extremes).

## Hardware capability reminder
- Glove80 technical spec states: “Per-key LEDs: 80 individually addressable RGB LEDs”.
- User’s unit has underglow LEDs on both halves (per MoErgo RGB doc, this is configuration-dependent).
