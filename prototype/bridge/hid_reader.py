"""
Keyboard input reader for Glove80 instrument mode bridge.

Uses Linux evdev to read key events from the Glove80 keyboard device.
When instrument mode is active, exclusively grabs the device so keypresses
don't reach the OS as typed characters.

The Glove80 firmware emits standard HID keycodes in its instrument layer.
This module reads those keycodes via evdev and passes them to the bridge
for MIDI translation.
"""

import os
import sys

from evdev import InputDevice, categorize, ecodes, list_devices

# Glove80 USB identifiers
GLOVE80_VID = 0x16c0  # Van Ooijen Technische Informatica (shared VID used by MoErgo)
GLOVE80_PID = 0x27db  # Glove80 keyboard product ID


def find_glove80_device():
    """Find the Glove80 keyboard evdev device.

    Searches by name ("glove80", "moergo") and VID:PID (16c0:27db).
    Returns the device path or None if not found.
    """
    for path in list_devices():
        try:
            dev = InputDevice(path)
            name_lower = dev.name.lower()
            vid_match = dev.info.vendor == GLOVE80_VID and dev.info.product == GLOVE80_PID
            name_match = "glove80" in name_lower or "moergo" in name_lower

            if vid_match or name_match:
                caps = dev.capabilities()
                if ecodes.EV_KEY in caps:
                    print(f"Found Glove80: {dev.name} at {dev.path}")
                    print(f"  VID:PID: {dev.info.vendor:#06x}:{dev.info.product:#06x}")
                    print(f"  phys: {dev.phys}")
                    return dev.path
            dev.close()
        except (PermissionError, OSError):
            continue
    return None


def list_keyboard_devices():
    """List all keyboard input devices for manual selection."""
    devices = []
    for path in list_devices():
        try:
            dev = InputDevice(path)
            caps = dev.capabilities()
            if ecodes.EV_KEY in caps:
                key_caps = caps[ecodes.EV_KEY]
                has_letters = ecodes.KEY_A in key_caps and ecodes.KEY_Z in key_caps
                if has_letters:
                    devices.append((dev.path, dev.name, dev.phys))
            dev.close()
        except (PermissionError, OSError):
            continue
    return devices


class HidReader:
    """Reads key events from the Glove80 via evdev."""

    def __init__(self, device_path=None):
        self.device_path = device_path
        self._device = None
        self._grabbed = False

    def open(self, device_path=None):
        """Open the evdev device."""
        path = device_path or self.device_path
        if path is None:
            path = find_glove80_device()
        if path is None:
            raise RuntimeError(
                "Glove80 not found. Available keyboards:\n"
                + "\n".join(f"  {p}: {n}" for p, n, _ in list_keyboard_devices())
                + "\nUse --device /dev/input/eventN to specify manually."
            )
        self._device = InputDevice(path)
        self.device_path = path
        print(f"Opened device: {self._device.name} ({path})")

    def grab(self):
        """Exclusively grab the device (keypresses won't reach OS)."""
        if self._device and not self._grabbed:
            self._device.grab()
            self._grabbed = True
            print("Device grabbed exclusively (keypresses suppressed from OS)")

    def ungrab(self):
        """Release exclusive grab."""
        if self._device and self._grabbed:
            self._device.ungrab()
            self._grabbed = False
            print("Device released (keypresses go to OS again)")

    def close(self):
        """Close the device."""
        if self._grabbed:
            self.ungrab()
        if self._device:
            self._device.close()
            self._device = None

    def read_events(self):
        """Generator that yields (keycode, is_press) tuples.

        Blocks until events are available. Yields key press and release
        events only (ignores repeat/hold events).
        """
        if self._device is None:
            raise RuntimeError("Device not opened")
        for event in self._device.read_loop():
            if event.type == ecodes.EV_KEY:
                # value: 0=release, 1=press, 2=repeat (hold)
                if event.value in (0, 1):
                    yield event.code, event.value == 1

    @property
    def is_grabbed(self):
        return self._grabbed
