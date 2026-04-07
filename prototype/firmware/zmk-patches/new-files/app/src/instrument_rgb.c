/*
 * Copyright (c) 2026 Tal Onn Sella
 * SPDX-License-Identifier: MIT
 *
 * Instrument mode RGB renderer — 12 chromatic colors, per-hand dynamic,
 * with bass coloring at reduced saturation and iso anchor accuracy.
 *
 * Performance model: a static const pos_table maps each of 80 keymap
 * positions to (zone, hand, row, col). Colors are cached in a 80-entry
 * array, invalidated only on state change (semi/mode/bass shift or
 * peripheral decode). The render loop reads cached hex and applies
 * brightness via a mul-shift approximation (no integer division).
 */

#include <zmk/instrument_rgb.h>
#include <zmk/instrument_mode.h>
#include <zmk/rgb_underglow.h>
#include <zmk/rgb_underglow_layer.h>
#include <zephyr/logging/log.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

/* ═══════════════════════════════════════════════════════════════════
 * 12 chromatic note colors — C=red through B=magenta
 * ═══════════════════════════════════════════════════════════════════ */

static const uint32_t NOTE_COLORS[12] = {
    0xFF0000, /* C  — red         */
    0xFF4500, /* C# — red-orange  */
    0xFFA500, /* D  — orange      */
    0xFFFF00, /* D# — yellow      */
    0x80FF00, /* E  — yellow-green*/
    0x00FF00, /* F  — green       */
    0x00E05F, /* F# — spring green  */
    0x00FFFF, /* G  — cyan        */
    0x0000FF, /* G# — blue        */
    0x8000FF, /* A  — blue-violet */
    0x7A00FF, /* A# — deep purple */
    0xFF00FF, /* B  — magenta     */
};

#define COLOR_CTRL 0xB3B3B3  /* control keys: white at ~70% */

/* All rendering at sustained brightness (75% of user-set brightness) */
#define SUSTAIN_PCT 75

/* ═══════════════════════════════════════════════════════════════════
 * Position zones and table
 * ═══════════════════════════════════════════════════════════════════ */

#define ZONE_CTRL  0
#define ZONE_GRID  1
#define ZONE_THUMB 2
#define ZONE_BASS  3

struct pos_info {
    uint8_t zone;
    uint8_t hand;
    uint8_t row;
    uint8_t col;
};

#define C ZONE_CTRL
#define G ZONE_GRID
#define T ZONE_THUMB
#define B ZONE_BASS
#define L 0
#define R 1

static const struct pos_info pos_table[80] = {
    /* R1: controls (pos 0-9) */
    {C,L,0,0}, {C,L,0,1}, {C,L,0,2}, {C,L,0,3}, {C,L,0,4},
    {C,R,0,0}, {C,R,0,1}, {C,R,0,2}, {C,R,0,3}, {C,R,0,4},
    /* R2: grid row 3 (pos 10-21) */
    {G,L,3,0}, {G,L,3,1}, {G,L,3,2}, {G,L,3,3}, {G,L,3,4}, {G,L,3,5},
    {G,R,3,0}, {G,R,3,1}, {G,R,3,2}, {G,R,3,3}, {G,R,3,4}, {G,R,3,5},
    /* R3: grid row 2 (pos 22-33) */
    {G,L,2,0}, {G,L,2,1}, {G,L,2,2}, {G,L,2,3}, {G,L,2,4}, {G,L,2,5},
    {G,R,2,0}, {G,R,2,1}, {G,R,2,2}, {G,R,2,3}, {G,R,2,4}, {G,R,2,5},
    /* R4: grid row 1 (pos 34-45) */
    {G,L,1,0}, {G,L,1,1}, {G,L,1,2}, {G,L,1,3}, {G,L,1,4}, {G,L,1,5},
    {G,R,1,0}, {G,R,1,1}, {G,R,1,2}, {G,R,1,3}, {G,R,1,4}, {G,R,1,5},
    /* R5 LH: grid row 0 (pos 46-51) */
    {G,L,0,0}, {G,L,0,1}, {G,L,0,2}, {G,L,0,3}, {G,L,0,4}, {G,L,0,5},
    /* Thumb inner (pos 52-57)
     * RH T2 (pos 56) swapped with RH T4 outer to put A and A# on
     * different rows (so their similar colors aren't physically adjacent) */
    {T,L,1,0}, {T,L,1,1}, {T,L,1,2},
    {T,R,1,3}, {T,R,0,5}, {T,R,1,5},
    /* R5 RH: grid row 0 (pos 58-63) */
    {G,R,0,0}, {G,R,0,1}, {G,R,0,2}, {G,R,0,3}, {G,R,0,4}, {G,R,0,5},
    /* R6 LH (pos 64-68): toggle, bass_semi_dn, bass×3 */
    {C,L,0,0},  /* pos 64: mode toggle */
    {C,L,0,1},  /* pos 65: bass semi down */
    {B,L,0,0}, {B,L,0,1}, {B,L,0,2},  /* pos 66-68: bass A0, A#0, B0 */
    /* Thumb outer (pos 69-74) — RH T4 (pos 74) gets A1 (was A#1) */
    {T,L,0,0}, {T,L,0,1}, {T,L,0,2},
    {T,R,0,3}, {T,R,0,4}, {T,R,1,4},
    /* R6 RH (pos 75-79): bass×3, bass_semi_up, mode_rh */
    {B,R,0,0}, {B,R,0,1}, {B,R,0,2},  /* pos 75-77: C2, C#2, D2 */
    {C,R,0,1},  /* pos 78: bass semi up */
    {C,R,0,0},  /* pos 79: mode toggle */
};

#undef C
#undef G
#undef T
#undef B
#undef L
#undef R

/* Exported accessors for instrument_mode.c */
uint8_t instrument_pos_row(uint8_t pos) {
    return (pos < 80) ? pos_table[pos].row : 0;
}
uint8_t instrument_pos_zone(uint8_t pos) {
    return (pos < 80) ? pos_table[pos].zone : 0;
}
uint8_t instrument_pos_hand(uint8_t pos) {
    return (pos < 80) ? pos_table[pos].hand : 0;
}
uint8_t instrument_pos_col(uint8_t pos) {
    return (pos < 80) ? pos_table[pos].col : 0;
}

/* Forward-declare the per-col semitone tables (defined below) so the
 * accessor above can reference them. Non-static linkage so the render
 * path and the iso anchor K computation share one source of truth. */
extern const uint8_t TWO_OCT_LOWER_OFFSETS[6];
extern const uint8_t TWO_OCT_UPPER_OFFSETS[6];

/* Return the raw 2oct note class (0-11) for a given grid (row, col) without
 * applying semi_offset. Used by both the render path and instrument_mode's
 * iso anchor K computation. */
int instrument_note_class_2oct_raw(uint8_t row, uint8_t col) {
    if (col >= 6) return 0;
    return (row % 2) ? TWO_OCT_UPPER_OFFSETS[col]
                     : TWO_OCT_LOWER_OFFSETS[col];
}

/* Base note classes for bass keys (at offset 0):
 * LH: pos 66=A0(9), 67=A#0(10), 68=B0(11)
 * RH: pos 75=C2(0), 76=C#2(1), 77=D2(2) */
static const int8_t bass_base_class[] = {9, 10, 11, 0, 1, 2};

/* Direct-index table: pos → bass_index (or -1) */
static const int8_t bass_idx_table[80] = {
    [0 ... 65] = -1,
    [66] = 0, [67] = 1, [68] = 2,
    [69 ... 74] = -1,
    [75] = 3, [76] = 4, [77] = 5,
    [78 ... 79] = -1,
};

/* ═══════════════════════════════════════════════════════════════════
 * Note class computation
 * ═══════════════════════════════════════════════════════════════════ */

/* 2oct per-column semitone offsets — must match bridge
 * physical_layout.py::build_note_map LOWER/UPPER_COL_OFFSETS.
 *   lower (row%2==0) col 0..5 → C  D  E  G  A  B   (0 2 4 7 9 11)
 *   upper (row%2==1) col 0..5 → C# D# F  F# G# A#  (1 3 5 6 8 10)
 * All 12 chromatic notes per block, no duplicates. */
const uint8_t TWO_OCT_LOWER_OFFSETS[6] = {0, 2, 4, 7, 9, 11};
const uint8_t TWO_OCT_UPPER_OFFSETS[6] = {1, 3, 5, 6, 8, 10};

static int note_class_for_grid(const struct pos_info *p,
                               const struct instrument_hand_state *st) {
    int raw;
    if (st->mode == 0) {
        /* 2oct: per-col offset table, separate for lower/upper row in block */
        const uint8_t *tbl = (p->row % 2) ? TWO_OCT_UPPER_OFFSETS
                                          : TWO_OCT_LOWER_OFFSETS;
        raw = tbl[p->col] + st->semi_offset;
    } else {
        /* iso: continuous grid + anchor offset */
        raw = st->iso_anchor_offset + p->col * 2 + p->row + st->semi_offset;
    }
    return ((raw % 12) + 12) % 12;
}

static int note_class_for_thumb(const struct pos_info *p) {
    int raw = p->col * 2 + p->row + instrument_mode_get_bass_offset();
    return ((raw % 12) + 12) % 12;
}

/* ═══════════════════════════════════════════════════════════════════
 * Color computation with brightness scaling
 *
 * Brightness scale: channel * brt / 100 → replaced with
 *   (channel * brt * 655) >> 16
 * Accurate to within 1 LSB for channel ∈ [0,255] and brt ∈ [0,100].
 * ═══════════════════════════════════════════════════════════════════ */

static inline uint8_t scale8(uint8_t ch, uint8_t brt) {
    return (uint8_t)(((uint32_t)ch * brt * 655U) >> 16);
}

static struct led_rgb scale_color(uint32_t hex, uint8_t brightness) {
    struct led_rgb c;
    c.r = scale8((uint8_t)((hex >> 16) & 0xFF), brightness);
    c.g = scale8((uint8_t)((hex >> 8) & 0xFF), brightness);
    c.b = scale8((uint8_t)(hex & 0xFF), brightness);
    return c;
}

/* Desaturate a hex color by N/100 toward white */
static uint32_t desaturate_pct(uint32_t hex, uint8_t pct) {
    uint8_t r = ((hex >> 16) & 0xFF);
    uint8_t g = ((hex >> 8) & 0xFF);
    uint8_t b = (hex & 0xFF);
    r = r + ((0xFF - r) * pct) / 100;
    g = g + ((0xFF - g) * pct) / 100;
    b = b + ((0xFF - b) * pct) / 100;
    return ((uint32_t)r << 16) | ((uint32_t)g << 8) | b;
}

static uint32_t desaturate(uint32_t hex) {
    return desaturate_pct(hex, 25);
}

/* Special color for A/A#/B in desaturated bass context. */
static uint32_t desat_bass_color(int note_class) {
    switch (note_class) {
    case 9:  return desaturate_pct(0x4000FF, 15);
    case 10: return desaturate_pct(0xA000FF, 25);
    case 11: return desaturate_pct(0xFF40FF, 35);
    default: return desaturate(NOTE_COLORS[note_class]);
    }
}

static uint32_t compute_color_for_pos(uint8_t pos) {
    const struct pos_info *p = &pos_table[pos];

    switch (p->zone) {
    case ZONE_CTRL:
        return COLOR_CTRL;

    case ZONE_GRID: {
        const struct instrument_hand_state *st = instrument_mode_get_hand(p->hand);
        int nc = note_class_for_grid(p, st);
        return NOTE_COLORS[nc];
    }

    case ZONE_THUMB: {
        int nc = note_class_for_thumb(p);
        return desat_bass_color(nc);
    }

    case ZONE_BASS: {
        int bi = bass_idx_table[pos];
        if (bi < 0) return 0;
        int8_t boff = instrument_mode_get_bass_offset();
        int nc = ((bass_base_class[bi] + boff) % 12 + 12) % 12;
        return desat_bass_color(nc);
    }

    default:
        return 0;
    }
}

/* ═══════════════════════════════════════════════════════════════════
 * Color cache — invalidated on state change, rebuilt lazily at render
 * ═══════════════════════════════════════════════════════════════════ */

static uint32_t color_cache[80];
static bool color_cache_valid = false;

void instrument_rgb_invalidate_cache(void) {
    color_cache_valid = false;
}

static void rebuild_color_cache(void) {
    for (int pos = 0; pos < 80; pos++) {
        color_cache[pos] = compute_color_for_pos((uint8_t)pos);
    }
    color_cache_valid = true;
}

/* ═══════════════════════════════════════════════════════════════════
 * Render all pixels at sustained brightness
 * ═══════════════════════════════════════════════════════════════════ */

void instrument_rgb_render(struct led_rgb *pixels, int num_pixels) {
    if (!color_cache_valid) {
        rebuild_color_cache();
    }

    uint8_t max_brt = zmk_rgb_underglow_get_brightness();
    /* sustain_brt = max_brt * SUSTAIN_PCT / 100 — still needs one divide,
     * but only once per render (not per pixel). */
    uint8_t sustain_brt = (uint8_t)((uint32_t)max_brt * SUSTAIN_PCT / 100);

    for (int i = 0; i < num_pixels; i++) {
        uint8_t pos = (uint8_t)rgb_pixel_lookup(i);

        if (pos >= 80) {
            pixels[i] = (struct led_rgb){.r = 0, .g = 0, .b = 0};
            continue;
        }

        pixels[i] = scale_color(color_cache[pos], sustain_brt);
    }
}

/* ═══════════════════════════════════════════════════════════════════
 * Trigger refresh
 * ═══════════════════════════════════════════════════════════════════ */

#include <zmk/events/underglow_color_changed.h>

void instrument_rgb_trigger_refresh(void) {
    if (!instrument_mode_is_active()) {
        return;
    }

    raise_zmk_underglow_color_changed((struct zmk_underglow_color_changed){
        .layers = BIT(CONFIG_ZMK_INSTRUMENT_LAYER), .wakeup = true});
}
