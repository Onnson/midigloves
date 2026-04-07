"""
Configuration persistence for the Glove80 MIDI Bridge.

Saves and loads bridge settings (tuning, scale, octave offset, intervals,
MIDI channel, velocity) to a JSON file.
"""

import json
import os

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(CONFIG_DIR, "bridge_config.json")

# Scale definitions: intervals from root
SCALES = {
    'chromatic':   [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    'major':       [0, 2, 4, 5, 7, 9, 11],
    'minor':       [0, 2, 3, 5, 7, 8, 10],
    'pentatonic':  [0, 2, 4, 7, 9],
    'blues':       [0, 3, 5, 6, 7, 10],
    'dorian':      [0, 2, 3, 5, 7, 9, 10],
    'mixolydian':  [0, 2, 4, 5, 7, 9, 10],
    'phrygian':    [0, 1, 3, 5, 7, 8, 10],
    'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
    'melodic_minor':  [0, 2, 3, 5, 7, 9, 11],
    'whole_tone':     [0, 2, 4, 6, 8, 10],
}

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

DEFAULT_CONFIG = {
    'lh_base': 36,            # C2 — left half base (octaves 2-3)
    'rh_base': 60,            # C4 — right half base (octaves 4-5)
    'col_interval': 2,        # whole step per column
    'row_interval': 1,        # semitone per row
    'thumb_base': 24,         # C1 — thumb register base
    'thumb_col_interval': 2,
    'thumb_row_interval': 1,
    'include_thumbs': True,
    'include_r6': True,
    'scale': 'chromatic',
    'root': 0,                # C
    'channel': 0,             # MIDI channel 1 (global fallback)
    'lh_channel': 0,          # MIDI channel 1 for left hand
    'rh_channel': 1,          # MIDI channel 2 for right hand
    'thumb_channel': 2,       # MIDI channel 3 for thumbs
    'per_zone_channels': True,  # Use separate channels per zone
    'velocity': 100,
    'octave_offset': 0,
    'octave_offset_min': -4,
    'octave_offset_max': 4,
    'pitch_bend_range': 12,   # semitones in each direction — set Ableton to match
}


def load_config(path=None):
    """Load config from JSON file, falling back to defaults."""
    filepath = path or CONFIG_PATH
    config = dict(DEFAULT_CONFIG)
    try:
        with open(filepath, 'r') as f:
            stored = json.load(f)
            config.update(stored)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return config


def save_config(config, path=None):
    """Save config to JSON file."""
    filepath = path or CONFIG_PATH
    with open(filepath, 'w') as f:
        json.dump(config, f, indent=2)


def is_in_scale(midi_note, root, scale_name):
    """Check if a MIDI note is in the given scale."""
    intervals = SCALES.get(scale_name, SCALES['chromatic'])
    degree = (midi_note - root) % 12
    return degree in intervals


def snap_to_scale(midi_note, root, scale_name):
    """Snap a MIDI note to the nearest note in the given scale.

    If the note is already in scale, returns it unchanged.
    Otherwise returns the closest in-scale note (preferring upward on ties).
    """
    intervals = SCALES.get(scale_name, SCALES['chromatic'])
    if not intervals:
        return midi_note

    degree = (midi_note - root) % 12
    if degree in intervals:
        return midi_note

    # Search outward from the note for the nearest in-scale note
    for offset in range(1, 7):
        # Check above
        up = midi_note + offset
        if up <= 127 and ((up - root) % 12) in intervals:
            return up
        # Check below
        down = midi_note - offset
        if down >= 0 and ((down - root) % 12) in intervals:
            return down

    return midi_note
