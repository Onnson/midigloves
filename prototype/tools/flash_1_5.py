#!/usr/bin/env python3
"""
Flash 1.5 — Transform standard-instrument.json for the Glove80 instrument layer.

Changes:
1. Move layer toggle from Magic pos 79 to Magic pos 54 (LH T3)
2. Fix dead R6 bass keys: F21→KP_N4, F22→KP_N5, F23→KP_N6, F24→KP_N7
3. Enable NKRO (HID_NKRO = y)
4. Add vel hold-tap behavior via Custom Defined Behaviors DTSI
5. Replace all 68 note &kp bindings with &vel hold-taps in instrument layer

Usage:
    python3 flash_1_5.py                          # Full transform with velocity
    python3 flash_1_5.py --no-velocity            # Skip velocity hold-taps
    python3 flash_1_5.py --input other.json       # Custom input file
"""

import json
import argparse
import sys


VEL_DTSI = r"""/ {
    behaviors {
        vel: vel {
            compatible = "zmk,behavior-hold-tap";
            label = "VELOCITY";
            #binding-cells = <2>;
            flavor = "hold-preferred";
            tapping-term-ms = <30>;
            bindings = <&kp>, <&kp>;
            hold-while-undecided;
        };
    };
};"""

# Instrument layer positions that are NOTE KEYS (get velocity hold-tap)
# Excludes: R1 controls (0-9), Magic/Enter hold-tap (64), RH iso toggle (79)
NOTE_POSITIONS = set(range(10, 64)) | set(range(65, 79))
# Position 64 = &lt 2 RET (mode toggle, not a note)
# Position 79 = &kp KP_N3 (RH iso toggle, not a note)

# R6 bass key replacements: F21-F24 → KP_N4-N7
BASS_REPLACEMENTS = {
    "F21": "KP_N4",
    "F22": "KP_N5",
    "F23": "KP_N6",
    "F24": "KP_N7",
}


def kp(key):
    return {"value": "&kp", "params": [{"value": key}]}


def vel(hold_key, tap_key="KP_N0"):
    return {"value": "&vel", "params": [{"value": hold_key}, {"value": tap_key}]}


def tog(layer):
    return {"value": "&tog", "params": [{"value": layer}]}


def none():
    return {"value": "&none"}


def transform(layout, add_velocity=True):
    changes = []

    # --- 1. Move layer toggle ---
    magic = layout["layers"][2]

    # Magic pos 54 (LH_T3): &none → &tog 3
    old_54 = magic[54].get("value", "?")
    magic[54] = tog(3)
    changes.append(f"Magic pos 54: {old_54} → &tog 3 (layer toggle)")

    # Magic pos 79: keep as-is (backup toggle, overridden by instrument layer anyway)
    changes.append(f"Magic pos 79: kept as {magic[79].get('value', '?')} (backup)")

    # --- 2. Fix dead R6 bass keys ---
    instrument = layout["layers"][3]

    for pos in range(80):
        binding = instrument[pos]
        if binding.get("value") == "&kp" and binding.get("params"):
            key = binding["params"][0]["value"]
            if key in BASS_REPLACEMENTS:
                new_key = BASS_REPLACEMENTS[key]
                instrument[pos] = kp(new_key)
                changes.append(f"Instrument pos {pos}: &kp {key} → &kp {new_key}")

    # --- 3. Enable NKRO ---
    nkro_found = False
    for param in layout.get("config_parameters", []):
        if param["paramName"] == "HID_NKRO":
            old_val = param["value"]
            param["value"] = "y"
            nkro_found = True
            changes.append(f"HID_NKRO: {old_val} → y")
            break
    if not nkro_found:
        layout.setdefault("config_parameters", []).append({
            "paramName": "HID_NKRO",
            "value": "y"
        })
        changes.append("HID_NKRO: added (y)")

    # --- 4 & 5. Velocity hold-taps ---
    if add_velocity:
        # Add vel DTSI to custom_defined_behaviors
        layout["custom_defined_behaviors"] = VEL_DTSI
        changes.append("Custom DTSI: vel hold-tap behavior added")

        # Replace note key &kp bindings with &vel
        vel_count = 0
        for pos in NOTE_POSITIONS:
            binding = instrument[pos]
            if binding.get("value") == "&kp" and binding.get("params"):
                key = binding["params"][0]["value"]
                instrument[pos] = vel(key)
                vel_count += 1
        changes.append(f"Instrument layer: {vel_count} note keys → &vel hold-taps")

    # Update metadata
    layout["title"] = "standard-instrument-1.5"
    suffix = "+velocity" if add_velocity else ""
    layout["notes"] = (
        f"Bridge 1.5: Layer toggle at Magic+LH_T3. "
        f"R6 bass fixed (KP_N4-N7). NKRO enabled. "
        f"{suffix}"
    )
    layout["tags"] = ["instrument", "velocity"] if add_velocity else ["instrument"]

    return changes


def main():
    parser = argparse.ArgumentParser(description="Flash 1.5 firmware JSON transform")
    parser.add_argument("--input", "-i", default="standard-instrument.json",
                        help="Input JSON file (default: standard-instrument.json)")
    parser.add_argument("--output", "-o", default="standard-instrument-1.5.json",
                        help="Output JSON file")
    parser.add_argument("--no-velocity", action="store_true",
                        help="Skip velocity hold-tap changes")
    args = parser.parse_args()

    with open(args.input, "r") as f:
        layout = json.load(f)

    # Verify structure
    assert layout.get("keyboard") == "glove80", "Not a Glove80 layout"
    assert len(layout.get("layers", [])) == 4, f"Expected 4 layers, got {len(layout.get('layers', []))}"
    for i, name in enumerate(["Base", "Lower", "Magic", "Instrument"]):
        assert len(layout["layers"][i]) == 80, f"Layer {name} has {len(layout['layers'][i])} bindings"

    changes = transform(layout, add_velocity=not args.no_velocity)

    with open(args.output, "w") as f:
        json.dump(layout, f, indent=2)

    print(f"Input:  {args.input}")
    print(f"Output: {args.output}")
    print(f"Changes ({len(changes)}):")
    for c in changes:
        print(f"  • {c}")

    # Count final instrument layer composition
    instrument = layout["layers"][3]
    vel_count = sum(1 for b in instrument if b.get("value") == "&vel")
    kp_count = sum(1 for b in instrument if b.get("value") == "&kp")
    other = 80 - vel_count - kp_count
    print(f"\nInstrument layer: {vel_count} vel + {kp_count} kp + {other} other = 80")


if __name__ == "__main__":
    main()
