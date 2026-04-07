# Device 0.5 → 0.8 prototype

This directory holds the **first working implementation** of the Glove80 MIDI
instrument: a Python bridge running on macOS that captures Glove80 HID
keycodes via `CGEventTap`, computes MIDI notes from a layout table, classifies
velocity from inter-note intervals, runs a per-hand pitch-bend glide engine,
and emits MIDI through a virtual CoreMIDI port that any DAW can consume. The
firmware side is a custom ZMK module that handles the instrument layer state
machine and renders 12 chromatic note colors per key on the underglow LEDs at
runtime.

The prototype is **complete and playable**. Tal used it for several days
inside Ableton Live and confirmed everything works end to end. We're keeping
it here because:

1. It is the **reference implementation** for the layout, the chromatic color
   table, the iso-mode anchor logic, the bass register state, and the velocity
   classifier. Device 1.0 ports these algorithms to native firmware C.
2. It is **standalone reproducible** — given the build instructions below
   and the right Glove80 hardware, you can rebuild and flash the same UF2s
   that are in [`uf2/`](uf2/).
3. It documents the **architectural decisions** (and the bugs discovered the
   hard way) that informed the Device 1.0 plan.

You should **not run the prototype bridge alongside Device 1.0**. The two
will fight over the same Glove80 HID events. Once Device 1.0 ships, the
prototype is reference-only.

---

## What's in here

| Path                        | What it is |
|-----------------------------|------------|
| [`bridge/`](bridge/)        | Python macOS menu-bar bridge — CGEventTap, MIDI generation, glide, velocity, scale rendering |
| [`firmware/`](firmware/)    | ZMK config + custom-module patches needed to rebuild the prototype firmware |
| [`uf2/`](uf2/)              | Prebuilt UF2 binaries for both halves at Device 0.5 and Device 0.8 |
| [`editor-exports/`](editor-exports/) | MoErgo Layout Editor JSON / `.keymap` exports from intermediate iterations |
| [`docs/`](docs/)            | Design notes — instrument mapping, RGB scheme, USB-MIDI research, preliminary hardware research |
| [`tools/`](tools/)          | `chords2color.py` (chord → key color CLI), `flash_1_5.py` (Mac flasher) |

---

## What the prototype does

### Bridge (Python, runs on macOS)

- **Captures Glove80 HID events** via `CGEventTap`, filtering by USB keyboard
  type so the built-in MacBook keyboard is ignored.
- **Maps keycodes to MIDI notes** using a 2-row × 6-column block layout. Each
  half has two octave blocks; the lower row of each block is `C D E G A B`,
  the upper row is `C# D# F F# G# A#`. Bass register and thumb keys live on
  separate rows with their own offsets.
- **Three modes per hand**: 2-octave (default), isomorphic (anchored on the
  last pressed grid key), and chromatic shift via per-hand semitone controls.
- **Sticky 3-tier velocity classifier** computed from inter-note interval
  using `mach_timebase_info` hardware timestamps to avoid scheduling jitter.
  Soft = 60, Normal = 92, Hard = 120.
- **Per-hand pitch-bend glide** engine driven by R1 control keys, with a
  generation counter so concurrent glides don't fight.
- **Bass semi shift** that preserves iso-mode state in the grid.
- **Menu bar app** with octave shift, scale, root, channel, panic, and
  pause/resume.

### Firmware (custom ZMK module)

- **4 layers**: Base, Lower, Magic, Instrument (layer 3).
- **Per-key RGB underglow** computes 12 chromatic note colors at runtime —
  C is red, B is magenta, the wheel rotates one hue per semitone.
- **Per-hand state machine**: mode (2oct / iso), semitone offset, iso anchor
  position. All packed into 16 bits piggybacked on the layer bitmask for
  cross-half BLE sync.
- **Color cache**: 80-entry pre-rendered cache invalidated only on state
  change, replacing per-pixel-per-frame note class computation in the
  render loop. Major performance win.
- **`&inst` behavior** for instrument-mode commands (mode toggle, semi shift,
  bass semi shift) called from the keymap.
- **Bass and thumb keys** rendered at 25% desaturation so the bass register
  is visually distinct from the main grid.

---

## How to rebuild the prototype firmware

### Prerequisites

- A Linux or macOS machine with `west`, the Zephyr SDK 0.17.0, and Python 3.10+
- A Glove80 you're willing to flash (with the stock UF2 backup procedure done
  per [`firmware/flash-guide.md`](firmware/flash-guide.md))

### Steps

1. **Initialize a west workspace**:
   ```sh
   mkdir glove80-workspace && cd glove80-workspace
   python3 -m venv .venv && source .venv/bin/activate
   pip install west
   ```

2. **Clone darknao's ZMK fork** at the exact revision the prototype was
   built against:
   ```sh
   git clone https://github.com/darknao/zmk
   cd zmk && git checkout 8aeaaa66fbb4b94948c8763e06f1920ab0b69480 && cd ..
   ```

3. **Apply the prototype's modifications and add the new files**:
   ```sh
   cd zmk
   git apply /path/to/midigloves/prototype/firmware/zmk-patches/modifications.patch
   cp -r /path/to/midigloves/prototype/firmware/zmk-patches/new-files/app/* app/
   cd ..
   ```
   See [`firmware/zmk-patches/README.md`](firmware/zmk-patches/README.md) for
   what these patches do.

4. **Copy the prototype config into a sibling directory** that west will
   discover:
   ```sh
   cp -r /path/to/midigloves/prototype/firmware/config ./config
   ```

5. **Run `west init` against the config manifest, then `west update`**:
   ```sh
   west init -l config
   west update
   ```
   This pulls the right Zephyr revision (carried in the upstream `zmk` fork's
   `app/west.yml`) and the rest of the dependencies.

6. **Export the Zephyr SDK** location:
   ```sh
   export ZEPHYR_SDK_INSTALL_DIR=/path/to/zephyr-sdk-0.17.0
   ```

7. **Build both halves**:
   ```sh
   west build -s zmk/app -b glove80_lh -- -DZMK_CONFIG="$(pwd)/config"
   mv build build_lh
   west build -s zmk/app -b glove80_rh -d build_rh -- -DZMK_CONFIG="$(pwd)/config"
   ```

8. **Flash** per [`firmware/flash-guide.md`](firmware/flash-guide.md). Right
   half first, left half second, factory reset and re-pair BLE after.

The resulting `zmk.uf2` files in `build_lh/zephyr/` and `build_rh/zephyr/`
should be byte-equivalent (modulo timestamps) to the prebuilt versions in
[`uf2/`](uf2/).

---

## How to run the prototype bridge

### Prerequisites

- macOS (uses `CGEventTap` and CoreMIDI — Linux/Windows are not supported by
  the prototype)
- Python 3.10+
- A virtual CoreMIDI port destination (Ableton Live, Logic, or any DAW)

### Steps

1. **Create a virtual environment**:
   ```sh
   cd prototype/bridge
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Grant Accessibility permission** to your terminal in System Settings →
   Privacy & Security → Accessibility. The bridge uses `CGEventTap` which
   requires this.

3. **Plug in the Glove80** and detect its USB keyboard type:
   ```sh
   python3 -c "from hid_reader_macos import detect_keyboard_types; print(detect_keyboard_types())"
   ```
   The Glove80 typically reports `keyboard_type=40`. Set this in
   `bridge_config.json` if it differs.

4. **Run the bridge**:
   ```sh
   python3 tray_app.py
   ```
   A 🎹 menu-bar icon should appear. The bridge is paused by default; click
   the icon and choose **Start Bridge** to enable note generation.

5. **In your DAW**, select `Glove80` as a MIDI input and arm a track.

### Caveats

- The prototype bridge **must not run alongside Device 1.0 firmware** — they
  will both try to generate notes from the same key events.
- macOS will mark the bridge as a "process that monitors keyboard input" the
  first time it runs. This is correct.
- The Glove80 must be in the **Instrument layer** (layer 3) for note generation
  to fire. Use the keymap's mode toggle (Magic + LH R1 C2 by default).

---

## What we learned (carry-over to Device 1.0)

The prototype taught us seven things that the Device 1.0 plan takes for granted:

1. **`time.time()` is wall-clock and corrupts inter-note interval math** —
   `time.perf_counter()` (Python) and `mach_absolute_time()` (macOS hardware
   timestamps) are mandatory. The firmware equivalent is `k_uptime_get()` and
   the event-carried timestamp.
2. **BLE jitter on the right half** is real and asymmetric — RH events arrive
   up to one connection interval (7.5–15ms) later than LH events. This
   requires per-zone INI tracking, not a single shared "last note time".
3. **Mocking the bass / iso state in two places leads to drift** — the bridge
   and firmware both maintain "what is the current iso anchor" and they
   disagreed twice in two days. Single source of truth is non-negotiable.
4. **The MoErgo Layout Editor rejects custom behaviors** — anything beyond
   stock ZMK requires `west build`. The editor JSONs in `editor-exports/`
   are documentation, not the build path.
5. **Returning anything but `ZMK_EV_EVENT_BUBBLE` (=0)** from a position event
   listener blocks the split transport. Found the hard way.
6. **`CGEventTap` callbacks must not block** — a 50ms `thread.join` in the
   pitch-bend handler caused macOS to disable the tap. The prototype's
   `PitchGlide` uses a generation counter so the start path returns
   immediately.
7. **F13–F20 are dead on macOS CGEventTap** — undocumented but reliable.
   The prototype uses keypad keycodes (`KP_N0`–`KP_N9`) instead.

---

## License

Same as the parent project: [MIT](../LICENSE).
