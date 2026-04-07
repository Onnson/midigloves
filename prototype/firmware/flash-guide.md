# Glove80 Firmware Flash & Recovery Guide

## Prerequisites

Before flashing custom firmware, complete these steps:

### 1. Back Up Current Config

**If configured via my.moergo.com:**
1. Log in at https://my.moergo.com/
2. Open your current layout
3. Settings → enable "Local Backup and Restore"
4. Export → save JSON file locally

**If using stock factory layout:** nothing to back up.

### 2. Download Restore-Point UF2

1. Go to https://my.moergo.com/
2. Open "Glove80 Factory Default Layout" (or your saved layout)
3. Click Build → download the .uf2
4. Rename to `stock.uf2` (macOS fails on long filenames)
5. Store in `firmware/stock/stock.uf2`

---

## Flashing Procedure

**Flash right half first, then left half.**

### Right Half

1. Power off (slide switch)
2. Connect USB-C from right half to computer
3. Hold C6R6 + C3R3 (stock layout: I + PgDn)
4. While holding, slide power on
5. Confirm: slow-pulsing red LED
6. Drive mounts as `GLV80RHBOOT`
7. Copy `.uf2` file onto the drive
8. Drive auto-unmounts = flash succeeded
9. Disconnect USB-C

### Left Half

1. Power off (slide switch)
2. Connect USB-C from left half to computer
3. Hold C6R6 + C3R3 (stock layout: Magic + E)
4. While holding, slide power on
5. Confirm: slow-pulsing red LED
6. Drive mounts as `GLV80LHBOOT`
7. Copy the same `.uf2` file onto the drive
8. Drive auto-unmounts = flash succeeded
9. Disconnect USB-C

---

## Emergency Recovery

If custom firmware doesn't work, the bootloader is hardware-protected and always accessible.

### Revert to Stock

1. Follow the same flashing procedure above
2. Use `stock.uf2` instead of custom firmware
3. The bootloader (slow-pulsing red LED) works regardless of application firmware state

### Factory Reset (After Firmware Version Change)

Do this on BOTH halves after changing firmware versions.

**Left half:**
1. Power off both halves
2. Hold C6R6 + C3R2 (stock layout: Magic + 3)
3. While holding, power on left half
4. Continue holding 5 seconds
5. Power off

**Right half:**
1. Power off both halves
2. Hold C6R6 + C3R2 (stock layout: PgDn + 8)
3. While holding, power on right half
4. Continue holding 5 seconds
5. Power off

### Re-Pair Halves

1. Power on both halves simultaneously
2. Press Magic + T (RGB toggle) — both halves should light up
3. Press Magic + T again to disable RGB
4. Wait 1 minute for config to persist

---

## LED Status Codes (Bootloader)

| LED | Meaning |
|-----|---------|
| Slow pulsing red | Bootloader active, USB connected, ready |
| Fast flashing red | Bootloader active, no USB connection |
| Solid red or off | Not in bootloader mode |

## Notes

- The UF2 bootloader lives in a write-protected flash region — it cannot be overwritten by flashing application firmware
- MoErgo Layout Editor generates a single .uf2 for both halves; west-based builds produce separate LH/RH files
- Both halves must run the same firmware version to communicate properly
- Keymap-only changes technically only need the left half (central) reflashed, but MoErgo recommends flashing both
