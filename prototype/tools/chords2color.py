#!/usr/bin/env python3
"""
chords2color — Translate chord names or song URLs into chromatic color notation.

Usage:
    python3 chords2color.py Am F C G           # direct chord input
    python3 chords2color.py "Am F C G | Dm G"  # with bar separators
    python3 chords2color.py https://tabs.ultimate-guitar.com/...  # URL input

Each note gets its Glove80 chromatic color:
    C=🔴 C#=🟠 D=🟧 D#=🟡 E=🟢 F=💚
    F#=🟩 G=🩵 G#=🔵 A=🟣 A#=💜 B=🩷
"""

import sys
import re

# ═══════════════════════════════════════════════════════════════════
# Note → color mapping (matches instrument_rgb.c NOTE_COLORS)
# ═══════════════════════════════════════════════════════════════════

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

NOTE_COLORS_HEX = {
    'C':  (0xFF, 0x00, 0x00),  # red
    'C#': (0xFF, 0x45, 0x00),  # red-orange
    'D':  (0xFF, 0xA5, 0x00),  # orange
    'D#': (0xFF, 0xFF, 0x00),  # yellow
    'E':  (0x80, 0xFF, 0x00),  # yellow-green
    'F':  (0x00, 0xFF, 0x00),  # green
    'F#': (0x00, 0xE0, 0x5F),  # spring green
    'G':  (0x00, 0xFF, 0xFF),  # cyan
    'G#': (0x00, 0x00, 0xFF),  # blue
    'A':  (0x80, 0x00, 0xFF),  # blue-violet
    'A#': (0x7A, 0x00, 0xFF),  # deep purple
    'B':  (0xFF, 0x00, 0xFF),  # magenta
}

# Enharmonic equivalents
ENHARMONIC = {
    'Db': 'C#', 'Eb': 'D#', 'Fb': 'E', 'Gb': 'F#',
    'Ab': 'G#', 'Bb': 'A#', 'Cb': 'B',
    'E#': 'F', 'B#': 'C',
}

NOTE_TO_SEMI = {name: i for i, name in enumerate(NOTE_NAMES)}
for flat, sharp in ENHARMONIC.items():
    NOTE_TO_SEMI[flat] = NOTE_TO_SEMI[sharp]

# ═══════════════════════════════════════════════════════════════════
# Chord → notes
# ═══════════════════════════════════════════════════════════════════

CHORD_INTERVALS = {
    '':      [0, 4, 7],           # major
    'm':     [0, 3, 7],           # minor
    '7':     [0, 4, 7, 10],       # dominant 7th
    'm7':    [0, 3, 7, 10],       # minor 7th
    'maj7':  [0, 4, 7, 11],       # major 7th
    'M7':    [0, 4, 7, 11],       # major 7th alt
    'dim':   [0, 3, 6],           # diminished
    'aug':   [0, 4, 8],           # augmented
    'sus2':  [0, 2, 7],           # suspended 2nd
    'sus4':  [0, 5, 7],           # suspended 4th
    '6':     [0, 4, 7, 9],        # 6th
    'm6':    [0, 3, 7, 9],        # minor 6th
    '9':     [0, 4, 7, 10, 14],   # 9th
    'm9':    [0, 3, 7, 10, 14],   # minor 9th
    'add9':  [0, 4, 7, 14],       # add 9
    '5':     [0, 7],              # power chord
    'dim7':  [0, 3, 6, 9],        # diminished 7th
    'm7b5':  [0, 3, 6, 10],       # half-diminished
    '7sus4': [0, 5, 7, 10],       # 7sus4
    '11':    [0, 4, 7, 10, 14, 17], # 11th
    '13':    [0, 4, 7, 10, 14, 21], # 13th
}

def parse_chord(chord_str):
    """Parse a chord string into (root_note, quality, bass_note)."""
    chord_str = chord_str.strip()
    if not chord_str:
        return None

    # Handle slash chords: Am/E
    bass = None
    if '/' in chord_str:
        parts = chord_str.split('/')
        chord_str = parts[0]
        bass_str = parts[1]
        if bass_str and bass_str[0].isupper():
            bass = normalize_note(bass_str)

    # Extract root note (1 or 2 chars)
    if len(chord_str) >= 2 and chord_str[1] in '#b':
        root = chord_str[:2]
        quality = chord_str[2:]
    else:
        root = chord_str[0]
        quality = chord_str[1:]

    root = normalize_note(root)
    if root is None:
        return None

    return (root, quality, bass)


def normalize_note(note_str):
    """Normalize a note string to sharp notation."""
    if note_str in NOTE_TO_SEMI:
        if note_str in ENHARMONIC:
            return ENHARMONIC[note_str]
        return note_str
    return None


def chord_to_notes(root, quality):
    """Return list of note names for a chord."""
    intervals = CHORD_INTERVALS.get(quality)
    if intervals is None:
        intervals = CHORD_INTERVALS['']  # default to major

    root_semi = NOTE_TO_SEMI[root]
    notes = []
    for interval in intervals:
        semi = (root_semi + interval) % 12
        notes.append(NOTE_NAMES[semi])
    return notes


# ═══════════════════════════════════════════════════════════════════
# Terminal color output
# ═══════════════════════════════════════════════════════════════════

def ansi_bg(r, g, b):
    return f"\033[48;2;{r};{g};{b}m"

def ansi_fg(r, g, b):
    return f"\033[38;2;{r};{g};{b}m"

RESET = "\033[0m"

def colored_circle(note):
    """Return a colored circle character for a note."""
    rgb = NOTE_COLORS_HEX.get(note, (128, 128, 128))
    return f"{ansi_fg(*rgb)}●{RESET}"

def colored_block(note):
    """Return a colored block with note name."""
    rgb = NOTE_COLORS_HEX.get(note, (128, 128, 128))
    # Use contrasting text color
    brightness = rgb[0] * 0.299 + rgb[1] * 0.587 + rgb[2] * 0.114
    text = "\033[30m" if brightness > 128 else "\033[97m"
    return f"{ansi_bg(*rgb)}{text} {note:2s} {RESET}"


def display_chord(chord_str):
    """Display a chord as colored notation."""
    parsed = parse_chord(chord_str)
    if parsed is None:
        print(f"  {chord_str}: ???")
        return

    root, quality, bass = parsed
    notes = chord_to_notes(root, quality)

    # Chord name
    name = f"{root}{quality}"
    if bass:
        name += f"/{bass}"

    # Color circles
    circles = " ".join(colored_circle(n) for n in notes)

    # Color blocks with names
    blocks = " ".join(colored_block(n) for n in notes)

    # Bass note
    bass_str = ""
    if bass:
        bass_str = f"  bass: {colored_circle(bass)}"

    print(f"  {name:8s}  {circles}  {blocks}{bass_str}")


# ═══════════════════════════════════════════════════════════════════
# URL parsing (basic)
# ═══════════════════════════════════════════════════════════════════

def extract_chords_from_text(text):
    """Extract chord names from text (lyrics + chords format)."""
    chord_pattern = re.compile(
        r'\b([A-G][#b]?(?:m|min|maj|dim|aug|sus[24]|add[29]|'
        r'M?7|m7b5|dim7|7sus4|[5679]|11|13)?(?:/[A-G][#b]?)?)\b'
    )
    chords = []
    seen_in_line = set()
    for line in text.split('\n'):
        # Heuristic: chord lines have mostly chords, few lowercase words
        words = line.split()
        if not words:
            continue
        chord_count = sum(1 for w in words if chord_pattern.fullmatch(w))
        if chord_count > 0 and chord_count >= len(words) * 0.5:
            for w in words:
                m = chord_pattern.fullmatch(w)
                if m and m.group(1) not in seen_in_line:
                    chords.append(m.group(1))
                    seen_in_line.add(m.group(1))
            seen_in_line.clear()
    return chords


def fetch_url(url):
    """Fetch URL content. Tries requests first, falls back to urllib."""
    try:
        import requests
        resp = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        return resp.text
    except ImportError:
        import urllib.request
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode('utf-8', errors='replace')


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

def print_legend():
    """Print the color legend."""
    print("\n  Color Legend:")
    for name in NOTE_NAMES:
        rgb = NOTE_COLORS_HEX[name]
        print(f"    {colored_block(name)}  {colored_circle(name)}  {name}")
    print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print_legend()
        print("  Example: python3 chords2color.py Am F C G")
        print("  Example: python3 chords2color.py 'Am F C G | Dm G C Am'")
        return

    args = " ".join(sys.argv[1:])

    # Check if it's a URL
    if args.startswith('http://') or args.startswith('https://'):
        print(f"\n  Fetching: {args}")
        try:
            html = fetch_url(args)
            # Strip HTML tags for basic parsing
            clean = re.sub(r'<[^>]+>', ' ', html)
            chords = extract_chords_from_text(clean)
            if not chords:
                print("  No chords found in page.")
                return
            print(f"  Found {len(chords)} chords:\n")
            seen = set()
            for c in chords:
                if c not in seen:
                    display_chord(c)
                    seen.add(c)
        except Exception as e:
            print(f"  Error fetching URL: {e}")
        print_legend()
        return

    # Direct chord input — split by spaces and |
    chords = [c.strip() for c in re.split(r'[\s|]+', args) if c.strip()]

    print()
    bar = []
    for token in sys.argv[1:]:
        if token == '|':
            if bar:
                print("    " + "  ".join(
                    " ".join(colored_circle(n) for n in chord_to_notes(*parse_chord(c)[:2]))
                    for c in bar if parse_chord(c)
                ))
                bar = []
            print("    ─────")
        else:
            for c in token.split():
                bar.append(c)

    # Print remaining bar
    if bar:
        for c in bar:
            display_chord(c)

    print_legend()


if __name__ == '__main__':
    main()
