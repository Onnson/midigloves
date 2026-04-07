"""
Physical layout mapping for the Glove80 custom macOS firmware.

Maps evdev keycodes to physical grid positions based on the ACTUAL keymap
from 40645926-84f0-4cd5-849e-92a6a535e06f_standard.keymap.

Row order: bottom (R5) = row 0 (lowest pitch), top (R2) = row 3 (highest pitch).
This puts C2 at bottom-left (Shift key) and ascending upward.

Split halves:
  LH COL6(pinky)..COL1(index) = columns 0..5
  RH COL1(index)..COL6(pinky) = columns 6..11
"""

# ---------------------------------------------------------------------------
# Evdev keycode constants (cross-platform, no evdev import)
# ---------------------------------------------------------------------------

KEY_ESC = 1
KEY_1 = 2
KEY_2 = 3
KEY_3 = 4
KEY_4 = 5
KEY_5 = 6
KEY_6 = 7
KEY_7 = 8
KEY_8 = 9
KEY_9 = 10
KEY_0 = 11
KEY_MINUS = 12
KEY_EQUAL = 13
KEY_BACKSPACE = 14
KEY_TAB = 15
KEY_Q = 16
KEY_W = 17
KEY_E = 18
KEY_R = 19
KEY_T = 20
KEY_Y = 21
KEY_U = 22
KEY_I = 23
KEY_O = 24
KEY_P = 25
KEY_LEFTBRACE = 26
KEY_RIGHTBRACE = 27
KEY_ENTER = 28
KEY_LEFTCTRL = 29
KEY_A = 30
KEY_S = 31
KEY_D = 32
KEY_F = 33
KEY_G = 34
KEY_H = 35
KEY_J = 36
KEY_K = 37
KEY_L = 38
KEY_SEMICOLON = 39
KEY_APOSTROPHE = 40
KEY_GRAVE = 41
KEY_LEFTSHIFT = 42
KEY_BACKSLASH = 43
KEY_Z = 44
KEY_X = 45
KEY_C = 46
KEY_V = 47
KEY_B = 48
KEY_N = 49
KEY_M = 50
KEY_COMMA = 51
KEY_DOT = 52
KEY_SLASH = 53
KEY_RIGHTSHIFT = 54
KEY_LEFTALT = 56
KEY_SPACE = 57
KEY_F1 = 59
KEY_F2 = 60
KEY_F3 = 61
KEY_F4 = 62
KEY_F5 = 63
KEY_F6 = 64
KEY_F7 = 65
KEY_F8 = 66
KEY_F9 = 67
KEY_F10 = 68
KEY_F11 = 87
KEY_RIGHTCTRL = 97
KEY_SYSRQ = 99
KEY_RIGHTALT = 100
KEY_HOME = 102
KEY_UP = 103
KEY_PAGEUP = 104
KEY_LEFT = 105
KEY_RIGHT = 106
KEY_END = 107
KEY_DOWN = 108
KEY_PAGEDOWN = 109
KEY_DELETE = 111
KEY_KPASTERISK = 55
KEY_KP7 = 71
KEY_KP8 = 72
KEY_KP9 = 73
KEY_KPMINUS = 74
KEY_KP4 = 75
KEY_KP5 = 76
KEY_KP6 = 77
KEY_KPPLUS = 78
KEY_KP1 = 79
KEY_KP2 = 80
KEY_KP3 = 81
KEY_KP0 = 82
KEY_KPDOT = 83
KEY_KPENTER = 96
KEY_KPSLASH = 98
KEY_LEFTMETA = 125
KEY_RIGHTMETA = 126


# ---------------------------------------------------------------------------
# Main note grid: R5 (bottom, row 0) through R2 (top, row 3)
#
# Based on actual keymap layer_Base:
#   R5: LSHFT Z X C V B | N M , . / RSHFT
#   R4: [capsword] A S D F G | H J K L ; RALT
#   R3: TAB Q W E R T | Y U I O P \
#   R2: ` 1 2 3 4 5 | 6 7 8 9 0 '
#
# Row 0 = R5 (bottom, C starts here)
# Row 1 = R4
# Row 2 = R3
# Row 3 = R2 (top)
# ---------------------------------------------------------------------------

GRID_POSITION = {
    # Row 0 (R5, bottom) — C2/C4 start here
    # LH: Shift Z X C V B
    KEY_LEFTSHIFT:  (0, 0),
    KEY_Z:          (0, 1),
    KEY_X:          (0, 2),
    KEY_C:          (0, 3),
    KEY_V:          (0, 4),
    KEY_B:          (0, 5),
    # RH: N M , . / F10
    KEY_N:          (0, 6),
    KEY_M:          (0, 7),
    KEY_COMMA:      (0, 8),
    KEY_DOT:        (0, 9),
    KEY_SLASH:      (0, 10),
    KEY_F10:        (0, 11),  # RH C6R5 (was RSHFT, now F10 in instrument layer)

    # Row 1 (R4)
    # LH: F3 A S D F G  (F3 = C#2 position, was capsword/dead)
    KEY_F3:         (1, 0),   # LH C6R4 (was capsword, now F3 in instrument layer)
    KEY_A:          (1, 1),
    KEY_S:          (1, 2),
    KEY_D:          (1, 3),
    KEY_F:          (1, 4),
    KEY_G:          (1, 5),
    # RH: H J K L ; F9
    KEY_H:          (1, 6),
    KEY_J:          (1, 7),
    KEY_K:          (1, 8),
    KEY_L:          (1, 9),
    KEY_SEMICOLON:  (1, 10),
    KEY_F9:         (1, 11),  # RH C6R4 (was RALT, now F9 in instrument layer)

    # Row 2 (R3)
    # LH: Tab Q W E R T
    KEY_TAB:        (2, 0),
    KEY_Q:          (2, 1),
    KEY_W:          (2, 2),
    KEY_E:          (2, 3),
    KEY_R:          (2, 4),
    KEY_T:          (2, 5),
    # RH: Y U I O P \
    KEY_Y:          (2, 6),
    KEY_U:          (2, 7),
    KEY_I:          (2, 8),
    KEY_O:          (2, 9),
    KEY_P:          (2, 10),
    KEY_BACKSLASH:  (2, 11),

    # Row 3 (R2, top)
    # LH: ` 1 2 3 4 5
    KEY_GRAVE:      (3, 0),
    KEY_1:          (3, 1),
    KEY_2:          (3, 2),
    KEY_3:          (3, 3),
    KEY_4:          (3, 4),
    KEY_5:          (3, 5),
    # RH: 6 7 8 9 0 '
    KEY_6:          (3, 6),
    KEY_7:          (3, 7),
    KEY_8:          (3, 8),
    KEY_9:          (3, 9),
    KEY_0:          (3, 10),
    KEY_APOSTROPHE: (3, 11),
}


# ---------------------------------------------------------------------------
# Thumb keys — instrument layer keycodes
#
# Physical layout (from keymap position defines):
#   Inner row (T1,T2,T3): closer to main keys
#     LH: DEL, LEFT, RIGHT | RH: KP_DIVIDE, HOME, END
#   Outer row (T4,T5,T6): further from main keys
#     LH: SPACE, KP_MULTIPLY, KP_MINUS | RH: KP_PLUS, KP_ENTER, KP_DOT
#
# All F13+ keycodes replaced — macOS CGEventTap doesn't fire for F13-F20.
# ---------------------------------------------------------------------------

THUMB_POSITION = {
    # Outer row (row 0) — "main" thumb row
    KEY_SPACE:     (0, 0),   # LH T4
    KEY_KPASTERISK:(0, 1),   # LH T5 (was F13/LCTRL)
    KEY_KPMINUS:   (0, 2),   # LH T6 (was F14/LALT)
    KEY_KPPLUS:    (0, 3),   # RH T6 (was F16/UP)
    KEY_KPENTER:   (0, 4),   # RH T5 (was F17/RCTRL)
    KEY_KPDOT:     (1, 4),   # RH T4 — A1 (swapped with HOME)

    # Inner row (row 1)
    KEY_DELETE: (1, 0),   # LH T1 — unchanged
    KEY_LEFT:   (1, 1),   # LH T2 — unchanged
    KEY_RIGHT:  (1, 2),   # LH T3 — unchanged
    KEY_KPSLASH:(1, 3),   # RH T3 (was F15/DOWN)
    KEY_HOME:   (0, 5),   # RH T2 — A#1 (swapped with KPDOT)
    KEY_END:    (1, 5),   # RH T1 — unchanged
}


# ---------------------------------------------------------------------------
# R6 main row — bass extension, instrument layer keycodes
#
# LH R6: [toggle] [bass_semi↓] KP9(C4) KP4(C3) KP5(C2) — pinky to index
# RH R6: KP6(C2) KP7(C3) KP1(C4) [bass_semi↑] [mode_rh] — index to pinky
# LH Enter = LH mode toggle, RH KP3 = RH mode toggle
# KP8 = bass semi down, KP2 = bass semi up (repurposed from bass notes)
# ---------------------------------------------------------------------------

# Mode toggle keys — per hand (LH Enter, RH KP3)
KEY_MODE_TOGGLE    = KEY_ENTER  # LH Enter
KEY_MODE_TOGGLE_RH = KEY_KP3    # RH Enter equivalent in instrument layer

# Bass semitone control keys
KEY_BASS_SEMI_DN = KEY_KP8   # LH R6 C5 (was G#0 bass)
KEY_BASS_SEMI_UP = KEY_KP2   # RH R6 C5 (was D#2 bass)

# R6 bass notes — MIDI values stored directly (not computed from col formula)
# 6 bass keys (3 per side) after R6/C5 repurposed as controls
R6_BASS_NOTES = {
    KEY_KP9:  21,   # LH C4R6 — A0
    KEY_KP4:  22,   # LH C3R6 — A#0
    KEY_KP5:  23,   # LH C2R6 — B0
    KEY_KP6:  36,   # RH C2R6 — C2
    KEY_KP7:  37,   # RH C3R6 — C#2
    KEY_KP1:  38,   # RH C4R6 — D2
}

# Legacy alias — kept for import compatibility with tray_app.py zone registration
R6_BASS = R6_BASS_NOTES


# ---------------------------------------------------------------------------
# R1 control strip — based on actual keymap
#   LH: ESC, F1(lt), F2(lt), F5, F12
#   RH: MINUS, EQUAL, LBKT, RBKT, BSPC
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# R1 control strip — pitch control per hand
#   LH (5 keys): Oct-  Oct+  Semi-  Semi+  Reset
#                 ESC   F1    F2     F5     F12
#   RH (5 keys): Oct-  Oct+  Semi-  Semi+  Reset
#                 -     =     [      ]      Bspc
# ---------------------------------------------------------------------------

# R1 key → (zone_index, action)
# zone 0=lh, 1=rh
R1_CONTROLS = {
    KEY_ESC:        (0, 'reset'),
    KEY_F1:         (0, 'oct_down'),
    KEY_F2:         (0, 'oct_up'),
    KEY_F5:         (0, 'semi_down'),
    KEY_F11:        (0, 'semi_up'),
    KEY_MINUS:      (1, 'semi_down'),
    KEY_EQUAL:      (1, 'semi_up'),
    KEY_LEFTBRACE:  (1, 'oct_down'),
    KEY_RIGHTBRACE: (1, 'oct_up'),
    KEY_BACKSPACE:  (1, 'reset'),
}

# Legacy — kept for import compatibility
CONTROL_KEYS = {k: f'r1_{v[1]}' for k, v in R1_CONTROLS.items()}
TRANSPORT_CC = {}
KEY_OCTAVE_DOWN = KEY_ESC
KEY_OCTAVE_UP = KEY_F1


# ---------------------------------------------------------------------------
# Note map generation
# ---------------------------------------------------------------------------

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def note_name(midi_note):
    """Return human-readable name for a MIDI note number."""
    octave = (midi_note // 12) - 1
    return f"{NOTE_NAMES[midi_note % 12]}{octave}"


def build_note_map(lh_base=36, rh_base=60, col_interval=2, row_interval=1,
                   thumb_base=24, thumb_col_interval=2, thumb_row_interval=1,
                   r6_base=None, include_r6=False, include_thumbs=True,
                   base_note=None):
    """Generate isomorphic keycode → MIDI note mapping with split halves.

    Each half has 2 octave blocks of 2 rows × 6 cols = 12 notes each.
    Block 0 (rows 0-1 = R5,R4): starts at base (C2 or C4)
    Block 1 (rows 2-3 = R3,R2): starts at base+12 (C3 or C5)

    Within each block, per-column semitone offset (lower row):
        lower row col 0..5 → C  D  E  G  A  B   (0 2 4 7 9 11)
        upper row col 0..5 → C# D# F  F# G# A#  (1 3 5 6 8 10)
    All 12 chromatic notes per octave block, no duplicates, both rows ascending.
    """
    if base_note is not None:
        lh_base = base_note
        rh_base = base_note

    # Per-column semitone offsets within a 2-row block
    LOWER_COL_OFFSETS = [0, 2, 4, 7, 9, 11]
    UPPER_COL_OFFSETS = [1, 3, 5, 6, 8, 10]

    note_map = {}

    # Main grid — 2 octave blocks per half
    for keycode, (row, col) in GRID_POSITION.items():
        if col < 6:
            base = lh_base
            local_col = col
        else:
            base = rh_base
            local_col = col - 6

        # Which octave block: rows 0-1 = block 0, rows 2-3 = block 1
        block = row // 2
        row_in_block = row % 2

        col_offset = (UPPER_COL_OFFSETS if row_in_block == 1 else LOWER_COL_OFFSETS)[local_col]
        note = base + (block * 12) + col_offset
        if 0 <= note <= 127:
            note_map[keycode] = note

    # Thumb keys
    if include_thumbs:
        for keycode, (row, col) in THUMB_POSITION.items():
            note = thumb_base + (col * thumb_col_interval) + (row * thumb_row_interval)
            if 0 <= note <= 127:
                note_map[keycode] = note

    # R6 bass extension — notes stored directly in R6_BASS_NOTES
    if include_r6:
        for keycode, note in R6_BASS_NOTES.items():
            if 0 <= note <= 127:
                note_map[keycode] = note

    return note_map


def notational_iso_anchor_pitch(anchor_row, anchor_col, side='lh',
                                 lh_base=36, rh_base=60):
    """Return the pure-chromatic iso pitch at a grid position.

    Unlike build_note_map (which uses the irregular per-column 2oct
    offsets C D E G A B / C# D# F F# G# A#), this returns a strictly
    isomorphic pitch where moving one row up adds one semitone and
    moving one col right adds two semitones. This is the correct
    baseline for seeding iso mode — using note_map[anchor_key] as the
    seed instead would fold in either the 2oct table's irregular jumps
    or (worse) an iso ±12 octave-resolution shift from a previous
    iso session, causing cascading drift on re-anchor.

    Args:
        anchor_row, anchor_col: grid position of the anchor
        side: 'lh' or 'rh' — determines base pitch and local col
        lh_base, rh_base: hand base pitches (MIDI numbers); defaults
            match build_note_map's C2 / C4 convention

    Returns:
        MIDI pitch (int) at the anchor position under pure iso math.
        Does NOT include any zone octave offset — the caller adds that.
    """
    base = lh_base if side == 'lh' else rh_base
    local_col = anchor_col if side == 'lh' else anchor_col - 6
    return base + anchor_row + local_col * 2


def build_isomorphic_from_anchor(anchor_row, anchor_col, anchor_pitch,
                                  col_interval=2, row_interval=1, side='lh'):
    """Build isomorphic note map for one half, anchored at a specific position.

    The anchor position keeps its pitch. All other positions are calculated
    relative to it using the isomorphic intervals.

    Args:
        anchor_row, anchor_col: grid position of the anchor note
        anchor_pitch: MIDI note at the anchor position
        col_interval: semitones per column (default 2 = whole step)
        row_interval: semitones per row (default 1 = semitone)
        side: 'lh' (cols 0-5) or 'rh' (cols 6-11)

    Returns:
        dict of keycode → MIDI note for that half only
    """
    col_lo, col_hi = (0, 6) if side == 'lh' else (6, 12)

    # Compute base iso pitch for each key in this half
    entries = []  # list of (keycode, row, col, base_pitch)
    for keycode, (row, col) in GRID_POSITION.items():
        if col < col_lo or col >= col_hi:
            continue
        base = anchor_pitch + (col - anchor_col) * col_interval + (row - anchor_row) * row_interval
        entries.append((keycode, row, col, base))

    # Octave extension: with the iso formula on a 4x6 grid we get 24 positions
    # but only ~14 distinct pitches — many pairs collide. For each duplicate
    # pair, the physically closer one to the anchor keeps the anchor octave;
    # the farther one is shifted by ±12 depending on its physical row relative
    # to the anchor: above the anchor (higher row = farther from user) → +12,
    # below the anchor (lower row = closer to user) → -12. This puts the
    # anchor in the middle of the two-octave range and keeps the "up = higher
    # pitch / down = lower pitch" geometry intact.
    from collections import defaultdict
    by_pitch = defaultdict(list)
    for kc, r, c, p in entries:
        by_pitch[p].append((kc, r, c))

    note_map = {}
    for pitch, group in by_pitch.items():
        if len(group) == 1:
            kc, _, _ = group[0]
            if 0 <= pitch <= 127:
                note_map[kc] = pitch
        else:
            # Sort by Manhattan distance from anchor ascending: closer keeps
            # the anchor octave, farther gets shifted by ±12 based on its
            # physical row relative to the anchor (see comment above).
            def dist(g):
                return abs(g[1] - anchor_row) + abs(g[2] - anchor_col)
            sorted_group = sorted(group, key=dist)
            for i, (kc, r, c) in enumerate(sorted_group):
                if i == 0:
                    final_pitch = pitch
                elif r > anchor_row:
                    final_pitch = pitch + 12   # farther duplicate is above anchor
                elif r < anchor_row:
                    final_pitch = pitch - 12   # farther duplicate is below anchor
                else:
                    final_pitch = pitch + 12   # same row fallback (unreached in 4x6)
                if 0 <= final_pitch <= 127:
                    note_map[kc] = final_pitch
    return note_map


def all_bridge_keys(note_map):
    """Return set of all keycodes the bridge handles."""
    keys = set(note_map.keys())
    keys.update(CONTROL_KEYS.keys())
    return keys


def print_layout(note_map):
    """Print the current layout as a readable grid."""
    print("\n=== Main Grid (bottom R5 → top R2) ===")
    print(f"{'Row':<5}", end="")
    for c in range(12):
        side = "LH" if c < 6 else "RH"
        col = c if c < 6 else c - 6
        print(f" {side}C{col:<3}", end="")
    print()

    for row in range(4):
        label = f"R{5-row}"
        print(f"{label:<5}", end="")
        for col in range(12):
            found = False
            for kc, (r, c) in GRID_POSITION.items():
                if r == row and c == col and kc in note_map:
                    print(f" {note_name(note_map[kc]):<5}", end="")
                    found = True
                    break
            if not found:
                print(f" {'---':<5}", end="")
        print()

    print("\n=== Thumb Keys ===")
    for row in range(2):
        label = "Outer" if row == 0 else "Inner"
        print(f"{label:<6}", end="")
        for col in range(6):
            found = False
            for kc, (r, c) in THUMB_POSITION.items():
                if r == row and c == col and kc in note_map:
                    print(f" {note_name(note_map[kc]):<5}", end="")
                    found = True
                    break
            if not found:
                print(f" {'---':<5}", end="")
        print()
