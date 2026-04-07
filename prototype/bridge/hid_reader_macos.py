"""
Keyboard input reader for Glove80 bridge — macOS backend.

Uses Quartz CGEventTap to capture keyboard events at the system level,
filtered by kCGKeyboardEventKeyboardType to isolate the Glove80 from
the built-in keyboard.

Alternatively, if keyboard_type is not configured, captures from all
keyboards (the user can toggle the bridge on/off to switch between
MIDI and typing).

Requires:
    pip install pyobjc-framework-Quartz pyobjc-framework-IOKit

macOS Accessibility permission required:
    System Settings → Privacy & Security → Accessibility → enable Terminal
"""

import sys
import threading
import subprocess
import json
import ctypes
import ctypes.util

if sys.platform != "darwin":
    raise ImportError("hid_reader_macos is macOS only")

import Quartz


# ═══════════════════════════════════════════════════════════════════
# Mach timebase — for converting CGEventGetTimestamp (mach ticks)
# to seconds. Eliminates callback scheduling jitter from velocity INI.
# ═══════════════════════════════════════════════════════════════════

class _MachTimebaseInfo(ctypes.Structure):
    _fields_ = [("numer", ctypes.c_uint32), ("denom", ctypes.c_uint32)]


def _init_mach_timebase():
    """Returns (numer, denom) such that seconds = ticks * numer / denom / 1e9."""
    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c"))
        tb = _MachTimebaseInfo()
        libc.mach_timebase_info(ctypes.byref(tb))
        return (tb.numer, tb.denom)
    except Exception:
        return (1, 1)  # fallback: treat ticks as nanoseconds


_MACH_NUMER, _MACH_DENOM = _init_mach_timebase()
_MACH_SCALE = _MACH_NUMER / (_MACH_DENOM * 1e9)


def mach_ticks_to_seconds(ticks):
    """Convert Mach absolute time ticks to seconds (monotonic)."""
    return ticks * _MACH_SCALE

# Glove80 USB identifiers
GLOVE80_VID = 0x16c0  # Van Ooijen Technische Informatica (shared VID)
GLOVE80_PID = 0x27db  # Glove80 keyboard

# macOS keycodes → evdev-compatible keycode numbers
# CGEvent keycodes are different from evdev. We map macOS keycodes
# to a common namespace that physical_layout.py uses.
# The physical_layout module uses evdev ecodes, so we need a translation.
# We'll map macOS keycode → evdev keycode for all keys the Glove80 sends.

# macOS virtual keycode → evdev KEY_* code
# Reference: Events.h (Carbon) and linux/input-event-codes.h
# macOS modifier key → CGEvent flag bit (for detecting press vs release)
MODIFIER_FLAGS = {
    56:  0x00020002,  # LShift → kCGEventFlagMaskShift (left)
    60:  0x00020004,  # RShift
    59:  0x00040001,  # LCtrl → kCGEventFlagMaskControl (left)
    62:  0x00042000,  # RCtrl
    58:  0x00080020,  # LAlt → kCGEventFlagMaskAlternate (left)
    61:  0x00080040,  # RAlt
    55:  0x00100008,  # LCmd → kCGEventFlagMaskCommand (left)
    54:  0x00100010,  # RCmd
}

MACOS_TO_EVDEV = {
    # Number row
    24: 13,    # = (kVK_ANSI_Equal → KEY_EQUAL)
    18: 2,     # 1 → KEY_1
    19: 3,     # 2 → KEY_2
    20: 4,     # 3 → KEY_3
    21: 5,     # 4 → KEY_4
    23: 6,     # 5 → KEY_5
    22: 7,     # 6 → KEY_6
    26: 8,     # 7 → KEY_7
    28: 9,     # 8 → KEY_8
    25: 10,    # 9 → KEY_9
    29: 11,    # 0 → KEY_0
    27: 12,    # - → KEY_MINUS

    # QWERTY row
    48: 15,    # Tab → KEY_TAB
    12: 16,    # Q → KEY_Q
    13: 17,    # W → KEY_W
    14: 18,    # E → KEY_E
    15: 19,    # R → KEY_R
    17: 20,    # T → KEY_T
    16: 21,    # Y → KEY_Y
    32: 22,    # U → KEY_U
    34: 23,    # I → KEY_I
    31: 24,    # O → KEY_O
    35: 25,    # P → KEY_P
    42: 43,    # \ → KEY_BACKSLASH

    # Home row
    53: 1,     # Esc → KEY_ESC
    0:  30,    # A → KEY_A
    1:  31,    # S → KEY_S
    2:  32,    # D → KEY_D
    3:  33,    # F → KEY_F
    5:  34,    # G → KEY_G
    4:  35,    # H → KEY_H
    38: 36,    # J → KEY_J
    40: 37,    # K → KEY_K
    37: 38,    # L → KEY_L
    41: 39,    # ; → KEY_SEMICOLON
    39: 40,    # ' → KEY_APOSTROPHE

    # Bottom row
    50: 41,    # ` → KEY_GRAVE
    6:  44,    # Z → KEY_Z
    7:  45,    # X → KEY_X
    8:  46,    # C → KEY_C
    9:  47,    # V → KEY_V
    11: 48,    # B → KEY_B
    45: 49,    # N → KEY_N
    46: 50,    # M → KEY_M
    43: 51,    # , → KEY_COMMA
    47: 52,    # . → KEY_DOT
    44: 53,    # / → KEY_SLASH
    116: 104,  # PgUp → KEY_PAGEUP

    # Function keys (R1 control strip)
    122: 59,   # F1 → KEY_F1
    120: 60,   # F2 → KEY_F2
    99:  61,   # F3 → KEY_F3
    118: 62,   # F4 → KEY_F4
    96:  63,   # F5 → KEY_F5
    97:  64,   # F6 → KEY_F6
    98:  65,   # F7 → KEY_F7
    100: 66,   # F8 → KEY_F8
    101: 67,   # F9 → KEY_F9
    109: 68,   # F10 → KEY_F10
    103: 87,   # F11 → KEY_F11
    # F12: macOS 111 → skipped (not used in instrument layer)
    105: 183,  # F13 → KEY_F13
    107: 184,  # F14 → KEY_F14
    113: 185,  # F15 → KEY_F15
    106: 186,  # F16 → KEY_F16
    64:  187,  # F17 → KEY_F17
    79:  188,  # F18 → KEY_F18
    80:  189,  # F19 → KEY_F19
    # F13-F20 removed — macOS CGEventTap does NOT fire for any F-key above F12.
    # All replaced with KP keycodes in firmware.

    # Keypad keys (instrument layer R6 bass + thumbs + controls)
    # macOS kVK_ANSI_KeypadN → evdev KEY_KPN
    82:  82,   # KP0 → KEY_KP0
    83:  79,   # KP1 → KEY_KP1
    84:  80,   # KP2 → KEY_KP2
    85:  81,   # KP3 → KEY_KP3
    86:  75,   # KP4 → KEY_KP4
    87:  76,   # KP5 → KEY_KP5
    88:  77,   # KP6 → KEY_KP6
    89:  71,   # KP7 → KEY_KP7 (evdev 71, NOT 78 which is KPPLUS)
    91:  72,   # KP8 → KEY_KP8
    92:  73,   # KP9 → KEY_KP9
    65:  83,   # KP_Decimal → KEY_KPDOT
    67:  55,   # KP_Multiply → KEY_KPASTERISK
    69:  78,   # KP_Plus → KEY_KPPLUS
    75:  98,   # KP_Divide → KEY_KPSLASH
    76:  96,   # KP_Enter → KEY_KPENTER
    78:  74,   # KP_Minus → KEY_KPMINUS

    # Thumb keys (modifiers + actions)
    # macOS keycodes: 56=LShift, 60=RShift, 59=LCtrl, 62=RCtrl,
    #                 58=LAlt/LOpt, 61=RAlt/ROpt, 55=LCmd, 54=RCmd
    56:  42,   # LShift → KEY_LEFTSHIFT
    60:  54,   # RShift → KEY_RIGHTSHIFT
    59:  29,   # LCtrl → KEY_LEFTCTRL
    62:  97,   # RCtrl → KEY_RIGHTCTRL
    58:  56,   # LAlt/LOpt → KEY_LEFTALT
    61:  100,  # RAlt/ROpt → KEY_RIGHTALT
    55:  125,  # LCmd → KEY_LEFTMETA
    54:  126,  # RCmd → KEY_RIGHTMETA
    51:  14,   # Backspace → KEY_BACKSPACE
    117: 111,  # Delete → KEY_DELETE
    36:  28,   # Return → KEY_ENTER
    49:  57,   # Space → KEY_SPACE

    # R6 navigation row
    115: 102,  # Home → KEY_HOME
    119: 107,  # End → KEY_END
    123: 105,  # Left → KEY_LEFT
    124: 106,  # Right → KEY_RIGHT
    126: 103,  # Up → KEY_UP
    125: 108,  # Down → KEY_DOWN
    33:  26,   # [ → KEY_LEFTBRACE
    30:  27,   # ] → KEY_RIGHTBRACE
    121: 109,  # PgDn → KEY_PAGEDOWN
}


# Precomputed flat array for O(1) macOS keycode → evdev lookup.
# Replaces MACOS_TO_EVDEV.get() in the hot path — no hash, no dict.
_MACOS_EVDEV_ARRAY = [None] * 256
for _mac_kc, _evdev_kc in MACOS_TO_EVDEV.items():
    if 0 <= _mac_kc < 256:
        _MACOS_EVDEV_ARRAY[_mac_kc] = _evdev_kc


def get_usb_keyboards():
    """List USB keyboards via system_profiler for device identification."""
    devices = []
    try:
        result = subprocess.run(
            ["system_profiler", "SPUSBDataType", "-json"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            _walk_usb(data, devices)
    except Exception:
        pass
    return devices


def _walk_usb(node, devices):
    if isinstance(node, dict):
        if "_name" in node:
            vid = node.get("vendor_id", "")
            pid = node.get("product_id", "")
            if vid and pid:
                devices.append({
                    "name": node["_name"],
                    "vendor_id": vid,
                    "product_id": pid,
                })
        for v in node.values():
            _walk_usb(v, devices)
    elif isinstance(node, list):
        for item in node:
            _walk_usb(item, devices)


def detect_keyboard_types(duration=5):
    """Tap key events for `duration` seconds and return observed keyboard type IDs.

    The user should press keys on each connected keyboard during the detection
    window. The Glove80 will typically have a different keyboard type ID than
    the built-in keyboard.

    Returns list of (keyboard_type_id, count) tuples sorted by count desc.
    """
    type_counts = {}

    def cb(proxy, event_type, event, refcon):
        if event_type == Quartz.kCGEventKeyDown:
            kb_type = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventKeyboardType
            )
            type_counts[kb_type] = type_counts.get(kb_type, 0) + 1
        return event

    mask = Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap,
        Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionListenOnly,
        mask, cb, None,
    )
    if tap is None:
        raise RuntimeError(
            "Cannot create CGEventTap. Grant Accessibility permission:\n"
            "System Settings → Privacy & Security → Accessibility"
        )

    source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
    loop = Quartz.CFRunLoopGetCurrent()
    Quartz.CFRunLoopAddSource(loop, source, Quartz.kCFRunLoopCommonModes)
    Quartz.CGEventTapEnable(tap, True)

    import time
    time.sleep(duration)

    Quartz.CGEventTapEnable(tap, False)

    return sorted(type_counts.items(), key=lambda x: -x[1])


class MacOSKeyCapture:
    """Captures keyboard events via CGEventTap, optionally filtered by keyboard type."""

    def __init__(self, keyboard_type=None):
        """
        Args:
            keyboard_type: if set, only capture events from this keyboard type ID.
                          Use detect_keyboard_types() to find the Glove80's ID.
        """
        self.keyboard_type = keyboard_type
        self.enabled = True
        self._tap = None
        self._run_loop_ref = None
        self._thread = None
        self._ready = threading.Event()
        self._event_callback = None  # set by the bridge

    def set_callback(self, callback):
        """Set the event callback: callback(evdev_keycode, is_press) -> bool.

        Returns True if the key was handled (should be suppressed).
        """
        self._event_callback = callback

    def start(self):
        self._thread = threading.Thread(target=self._run_tap, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise RuntimeError(
                "Failed to create CGEventTap.\n"
                "Grant Accessibility permission:\n"
                "System Settings → Privacy & Security → Accessibility"
            )
        print("Key capture started (CGEventTap)")
        if self.keyboard_type is not None:
            print(f"  Filtering keyboard type: {self.keyboard_type}")
        else:
            print("  Capturing ALL keyboards (no type filter)")

    def _cg_callback(self, proxy, event_type, event, refcon):
        # Cache attribute accesses as locals (CPython micro-optimization
        # for the hot callback path on the CoreFoundation run loop).
        if not self.enabled:
            return event

        if event_type == Quartz.kCGEventTapDisabledByTimeout:
            Quartz.CGEventTapEnable(self._tap, True)
            return event

        callback = self._event_callback
        kb_filter = self.keyboard_type
        evdev_arr = _MACOS_EVDEV_ARRAY

        # Event type classification FIRST, keyboard filter inside the branch
        # that needs it. Saves the field extraction on non-key events.

        # Handle modifier key events (Shift, Ctrl, Alt, Cmd)
        if event_type == Quartz.kCGEventFlagsChanged:
            if kb_filter is not None:
                kb_type = Quartz.CGEventGetIntegerValueField(
                    event, Quartz.kCGKeyboardEventKeyboardType
                )
                if kb_type != kb_filter:
                    return event
            mac_keycode = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventKeycode
            )
            if mac_keycode >= 256:
                return event
            evdev_keycode = evdev_arr[mac_keycode]
            if evdev_keycode is None:
                return event

            # Determine press/release from flags
            flags = Quartz.CGEventGetFlags(event)
            modifier_flag = MODIFIER_FLAGS.get(mac_keycode)
            is_press = bool(flags & modifier_flag) if modifier_flag else True

            if callback:
                # Hardware timestamp (mach ticks → seconds) for jitter-free INI
                hw_ts = mach_ticks_to_seconds(Quartz.CGEventGetTimestamp(event))
                handled = callback(evdev_keycode, is_press, hw_ts)
                if handled:
                    return None
            return event

        # Regular key events
        if kb_filter is not None:
            kb_type = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventKeyboardType
            )
            if kb_type != kb_filter:
                return event

        mac_keycode = Quartz.CGEventGetIntegerValueField(
            event, Quartz.kCGKeyboardEventKeycode
        )
        if mac_keycode >= 256:
            return event
        evdev_keycode = evdev_arr[mac_keycode]
        if evdev_keycode is None:
            return event  # Unknown key, pass through

        is_press = event_type == Quartz.kCGEventKeyDown

        if callback:
            # Hardware timestamp captured at HID interrupt time in the kernel
            hw_ts = mach_ticks_to_seconds(Quartz.CGEventGetTimestamp(event))
            handled = callback(evdev_keycode, is_press, hw_ts)
            if handled:
                return None  # Suppress the key event
        return event

    def _run_tap(self):
        mask = (
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown) |
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp) |
            Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
        )
        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            mask, self._cg_callback, None,
        )
        if self._tap is None:
            return

        source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        self._run_loop_ref = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(
            self._run_loop_ref, source, Quartz.kCFRunLoopCommonModes
        )
        Quartz.CGEventTapEnable(self._tap, True)
        self._ready.set()
        Quartz.CFRunLoopRun()

    def stop(self):
        self.enabled = False
        if self._tap:
            Quartz.CGEventTapEnable(self._tap, False)
        if self._run_loop_ref:
            Quartz.CFRunLoopStop(self._run_loop_ref)
        print("Key capture stopped")

    def set_enabled(self, enabled):
        self.enabled = enabled
        if self._tap:
            Quartz.CGEventTapEnable(self._tap, enabled)
