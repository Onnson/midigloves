# Instrument mode mapping (v0)

## Reserved control row
- R1 (entire top row across both halves) is reserved for control buttons (10 keys total).
- Octave Down/Up are NOT on R1.

## Octave shift buttons
- LH R2/C6 = Octave Down
- RH R2/C6 = Octave Up

## Thumb octave (octave 0)
Thumb keys define a full chromatic octave C0..B0 with an enharmonic label in the scheme:

LH-T4: C0
LH-T1: C#0
LH-T5: D0
LH-T2: D#0
LH-T6: E0
LH-T3: F0 (E#0)
RH-T3: F#0
RH-T6: G0
RH-T2: G#0
RH-T5: A0
RH-T1: A#0
RH-T4: B0

## Main-field octave blocks (left = C1 & C3, right = C2 & C4)

### Left-hand base block = octave 1 (C1..B1)
LH-R6/C6: C1
LH-R5/C6: C#1
LH-R6/C5: D1
LH-R5/C5: D#1
LH-R6/C4: E1
LH-R5/C4: F1 (E#1)
LH-R6/C3: G1
LH-R5/C3: F#1
LH-R6/C2: A1
LH-R5/C2: G#1
LH-R5/C1: A#1
LH-R4/C1: B1

### Left-hand transposed block = octave 3 (C3..B3)
Same physical positions as the octave-1 block above, but +2 octaves (add 24 semitones):
- LH positions map to the same pitch classes, but with octave number 3 instead of 1.

### Right-hand base block = octave 2 (C2..B2)
RH-R6/C6: C2
RH-R5/C6: C#2
RH-R6/C5: D2
RH-R5/C5: D#2
RH-R6/C4: E2
RH-R5/C4: F2 (E#2)
RH-R6/C3: G2
RH-R5/C3: F#2
RH-R6/C2: A2
RH-R5/C2: G#2
RH-R5/C1: A#2
RH-R4/C1: B2

### Right-hand transposed block = octave 4 (C4..B4)
Same physical positions as the octave-2 block above, but +2 octaves (add 24 semitones):
- RH positions map to the same pitch classes, but with octave number 4 instead of 2.

## Notes
- There is no R6/C1 physical position on this layout region, so the octave blocks use C6..C2 plus two keys on column C1 (R5 and R4).
- Remaining keys not listed here are currently “free space” and can be assigned later.
