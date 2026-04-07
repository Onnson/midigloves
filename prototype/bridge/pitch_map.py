"""
Key-to-MIDI pitch mapping for Glove80 instrument mode.

Maps Linux evdev keycodes to base MIDI note numbers.
The firmware instrument layer emits unique keycodes (A-Z, 0-9) for each
instrument key. This module translates those keycodes to MIDI notes.

Layout: 3 octaves at base offset 0
  - Thumb cluster (12 keys): MIDI 24-35 (C1-B1)
  - LH main field (12 keys): MIDI 36-47 (C2-B2)
  - RH main field (12 keys): MIDI 48-59 (C3-B3)

Octave shift applies globally: final_note = base_note + (octave_offset * 12)
"""

from evdev import ecodes

# evdev keycode -> base MIDI note number
# Thumb octave: C1=24 through B1=35
# Keycodes A-L map to chromatic scale C through B
PITCH_MAP = {
    ecodes.KEY_A: 24,   # Thumb C   (LH-T4)
    ecodes.KEY_B: 25,   # Thumb C#  (LH-T1)
    ecodes.KEY_C: 26,   # Thumb D   (LH-T5)
    ecodes.KEY_D: 27,   # Thumb D#  (LH-T2)
    ecodes.KEY_E: 28,   # Thumb E   (LH-T6)
    ecodes.KEY_F: 29,   # Thumb F   (LH-T3)
    ecodes.KEY_G: 30,   # Thumb F#  (RH-T3)
    ecodes.KEY_H: 31,   # Thumb G   (RH-T6)
    ecodes.KEY_I: 32,   # Thumb G#  (RH-T2)
    ecodes.KEY_J: 33,   # Thumb A   (RH-T5)
    ecodes.KEY_K: 34,   # Thumb A#  (RH-T1)
    ecodes.KEY_L: 35,   # Thumb B   (RH-T4)

    # LH main field: C2=36 through B2=47
    # Keycodes M-X map to chromatic scale C through B
    ecodes.KEY_M: 36,   # LH C   (R6/C6)
    ecodes.KEY_N: 37,   # LH C#  (R5/C6)
    ecodes.KEY_O: 38,   # LH D   (R6/C5)
    ecodes.KEY_P: 39,   # LH D#  (R5/C5)
    ecodes.KEY_Q: 40,   # LH E   (R6/C4)
    ecodes.KEY_R: 41,   # LH F   (R5/C4)
    ecodes.KEY_S: 42,   # LH F#  (R5/C3)
    ecodes.KEY_T: 43,   # LH G   (R6/C3)
    ecodes.KEY_U: 44,   # LH G#  (R5/C2)
    ecodes.KEY_V: 45,   # LH A   (R6/C2)
    ecodes.KEY_W: 46,   # LH A#  (R5/C1)
    ecodes.KEY_X: 47,   # LH B   (R4/C1)

    # RH main field: C3=48 through B3=59
    # Keycodes Y, Z, 1-0 map to chromatic scale C through B
    ecodes.KEY_Y: 48,   # RH C   (R6/C6)
    ecodes.KEY_Z: 49,   # RH C#  (R5/C6)
    ecodes.KEY_1: 50,   # RH D   (R6/C5)
    ecodes.KEY_2: 51,   # RH D#  (R5/C5)
    ecodes.KEY_3: 52,   # RH E   (R6/C4)
    ecodes.KEY_4: 53,   # RH F   (R5/C4)
    ecodes.KEY_5: 54,   # RH F#  (R5/C3)
    ecodes.KEY_6: 55,   # RH G   (R6/C3)
    ecodes.KEY_7: 56,   # RH G#  (R5/C2)
    ecodes.KEY_8: 57,   # RH A   (R6/C2)
    ecodes.KEY_9: 58,   # RH A#  (R5/C1)
    ecodes.KEY_0: 59,   # RH B   (R4/C1)
}

# Control keycodes (not notes)
KEY_OCTAVE_DOWN = ecodes.KEY_F13
KEY_OCTAVE_UP = ecodes.KEY_F14
KEY_MODE_TOGGLE = ecodes.KEY_F15  # First R1 control key (adjacent to toggle)

# R1 control strip keycodes (reserved for future use)
CONTROL_KEYS = {
    ecodes.KEY_F15,  # R1 LH control 1
    ecodes.KEY_F16,  # R1 LH control 2
    ecodes.KEY_F17,  # R1 LH control 3
    ecodes.KEY_F18,  # R1 LH control 4
    ecodes.KEY_F19,  # R1 RH control 1
    ecodes.KEY_F20,  # R1 RH control 2
    ecodes.KEY_F21,  # R1 RH control 3
    ecodes.KEY_F22,  # R1 RH control 4
    ecodes.KEY_F23,  # R1 RH control 5
}

# All keycodes the bridge should intercept when in instrument mode
ALL_INSTRUMENT_KEYS = set(PITCH_MAP.keys()) | {KEY_OCTAVE_DOWN, KEY_OCTAVE_UP} | CONTROL_KEYS

OCTAVE_OFFSET_MIN = -4
OCTAVE_OFFSET_MAX = 4
DEFAULT_VELOCITY = 100


def resolve_note(keycode, octave_offset):
    """Resolve a keycode to a MIDI note number with octave offset applied.

    Returns the MIDI note (0-127) or None if the keycode is not a note key.
    """
    base = PITCH_MAP.get(keycode)
    if base is None:
        return None
    note = base + (octave_offset * 12)
    return max(0, min(127, note))


NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def note_name(midi_note):
    """Return human-readable name for a MIDI note number."""
    octave = (midi_note // 12) - 1
    name = NOTE_NAMES[midi_note % 12]
    return f"{name}{octave}"
