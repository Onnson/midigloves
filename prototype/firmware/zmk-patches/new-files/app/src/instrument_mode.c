/*
 * Copyright (c) 2026 Tal Onn Sella
 * SPDX-License-Identifier: MIT
 *
 * Instrument mode state machine — per-hand musical state tracking
 * with bass offset, iso anchor, and note position tracking.
 */

#include <zmk/instrument_mode.h>
#include <zmk/instrument_rgb.h>
#include <zmk/keymap.h>
#include <zmk/event_manager.h>
#include <zmk/events/layer_state_changed.h>
#include <zmk/events/position_state_changed.h>
#include <zmk/events/split_peripheral_layer_changed.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

#if IS_ENABLED(CONFIG_ZMK_SPLIT_BLE) && IS_ENABLED(CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
int zmk_split_central_update_layers(uint32_t new_layers);
zmk_keymap_layers_state_t zmk_keymap_layer_state(void);
#endif

/* Zone types — must match instrument_rgb.c */
#define ZONE_CTRL  0
#define ZONE_GRID  1
#define ZONE_THUMB 2
#define ZONE_BASS  3

/* Import pos_table accessors from instrument_rgb.c */
uint8_t instrument_pos_row(uint8_t pos);
uint8_t instrument_pos_col(uint8_t pos);
uint8_t instrument_pos_zone(uint8_t pos);
uint8_t instrument_pos_hand(uint8_t pos);
int instrument_note_class_2oct_raw(uint8_t row, uint8_t col);
void instrument_rgb_invalidate_cache(void);

static struct instrument_hand_state hand_state[2] = {
    {.mode = 0, .semi_offset = 0, .iso_anchor_offset = 0},
    {.mode = 0, .semi_offset = 0, .iso_anchor_offset = 0},
};

static int8_t bass_semi_offset = 0; /* global bass+thumb register offset */

/* Mutex protecting hand_state[], bass_semi_offset, and last_note_pos[]
 * between the event listener context and the RGB render context
 * (which may run from a different work queue / BLE RX context on the
 * peripheral via instrument_mode_decode_state). */
static K_MUTEX_DEFINE(inst_state_mutex);

static bool active = false;
static uint8_t last_note_pos[2] = {46, 58}; /* default: LH R5 C6, RH R5 C1 */

static bool is_grid_pos(uint8_t pos) {
    /* Only GRID positions are valid iso anchor candidates.
     * Matches bridge behavior (bridge only tracks grid keys in
     * _last_note_released). Thumbs/bass have no valid grid row/col. */
    if (pos >= 80) return false;
    return instrument_pos_zone(pos) == ZONE_GRID;
}

/* Per-hand count of currently-held grid keys. Used by MODE_TOG to
 * decide between toggle (no notes held) vs re-anchor (notes held). */
static uint8_t held_grid_count[2] = {0, 0};

/* ═══════════════════════════════════════════════════════════════════
 * Iso anchor computation
 *
 * When switching from 2oct to iso, K corrects the row-block geometry
 * so the anchor key keeps its note. K = 0 for rows 0-1, K = 10 for rows 2-3.
 * semi_offset is applied separately in the render formula.
 * ═══════════════════════════════════════════════════════════════════ */

/* Compute the iso anchor offset K so that at the anchor position the iso
 * formula (K + row + col*2 + semi) mod 12 matches the 2oct note class
 * (per-col lookup + row_in_block + semi) mod 12. Because semi_offset cancels
 * on both sides, we only need to solve:
 *   K + anchor_row + anchor_col*2  ≡  TWO_OCT[anchor_row%2][anchor_col]  (mod 12)
 * so K = (TWO_OCT_class - anchor_row - anchor_col*2) mod 12.
 *
 * Under the OLD strict-isomorphic 2oct layout (col*2 + row_in_block), K was
 * only ever 0 or 10 depending on the anchor row. The new per-col table
 * layout (C D E G A B / C# D# F F# G# A#) makes K depend on col as well,
 * with K ∈ {0, 1, 9, 10, 11} across the 24 grid positions. */
static int8_t compute_iso_anchor_k(uint8_t pos) {
    uint8_t zone = instrument_pos_zone(pos);
    if (zone != ZONE_GRID) {
        return 0; /* non-grid anchor: no geometric correction */
    }
    uint8_t row = instrument_pos_row(pos);
    uint8_t col = instrument_pos_col(pos);
    int anchor_class = instrument_note_class_2oct_raw(row, col);
    int iso_linear = row + col * 2;
    return (int8_t)(((anchor_class - iso_linear) % 12 + 12) % 12);
}

/* ═══════════════════════════════════════════════════════════════════ */

bool instrument_mode_is_active(void) { return active; }

void instrument_mode_set_active(bool val) { active = val; }

const struct instrument_hand_state *instrument_mode_get_hand(uint8_t hand) {
    return &hand_state[hand & 1];
}

int8_t instrument_mode_get_bass_offset(void) { return bass_semi_offset; }

void instrument_mode_note_played(uint8_t hand, uint8_t position) {
    last_note_pos[hand & 1] = position;
}

static int8_t wrap12(int8_t val) {
    return ((val % 12) + 12) % 12;
}

void instrument_mode_apply_command(uint8_t hand, uint8_t cmd) {
    struct instrument_hand_state *st = &hand_state[hand & 1];

    k_mutex_lock(&inst_state_mutex, K_FOREVER);

    switch (cmd) {
    case INST_CMD_SEMI_INC:
        st->semi_offset = wrap12(st->semi_offset + 1);
        break;
    case INST_CMD_SEMI_DEC:
        st->semi_offset = wrap12(st->semi_offset - 1);
        break;
    case INST_CMD_SEMI_RST:
        st->semi_offset = 0;
        st->iso_anchor_offset = 0;
        break;
    case INST_CMD_MODE_TOG:
        /* Match bridge behavior:
         *   - If holding grid note(s): stay iso + re-anchor on last pressed
         *   - If no grid note held: flip between 2oct/iso */
        if (held_grid_count[hand & 1] > 0) {
            /* Always land in iso with new anchor */
            st->iso_anchor_offset = compute_iso_anchor_k(last_note_pos[hand & 1]);
            st->mode = 1;
        } else if (st->mode == 0) {
            /* No notes held, currently 2oct → go to iso */
            st->iso_anchor_offset = compute_iso_anchor_k(last_note_pos[hand & 1]);
            st->mode = 1;
        } else {
            /* No notes held, currently iso → go to 2oct */
            st->iso_anchor_offset = 0;
            st->mode = 0;
        }
        break;
    case INST_CMD_BASS_SEMI_INC:
        bass_semi_offset = wrap12(bass_semi_offset + 1);
        break;
    case INST_CMD_BASS_SEMI_DEC:
        bass_semi_offset = wrap12(bass_semi_offset - 1);
        break;
    case INST_CMD_OCT_INC:
    case INST_CMD_OCT_DEC:
        /* Octave shifts are handled entirely by the bridge —
         * firmware has no octave state to track. */
        k_mutex_unlock(&inst_state_mutex);
        return;
    default:
        k_mutex_unlock(&inst_state_mutex);
        return;
    }

    LOG_DBG("inst h=%d mode=%d semi=%d bass=%d iso_k=%d",
            hand & 1, st->mode, st->semi_offset,
            bass_semi_offset, st->iso_anchor_offset);

    k_mutex_unlock(&inst_state_mutex);

    if (active) {
        instrument_rgb_invalidate_cache();
        instrument_rgb_trigger_refresh();
#if IS_ENABLED(CONFIG_ZMK_SPLIT_BLE) && IS_ENABLED(CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
        zmk_split_central_update_layers(zmk_keymap_layer_state());
#endif
    }
}

uint16_t instrument_mode_encode_state(void) {
    uint16_t enc = 0;
    k_mutex_lock(&inst_state_mutex, K_FOREVER);
    enc |= (wrap12(hand_state[0].semi_offset) & 0xF);       /* bits 0-3 */
    enc |= (hand_state[0].mode & 1) << 4;                    /* bit 4 */
    enc |= (wrap12(hand_state[1].semi_offset) & 0xF) << 5;  /* bits 5-8 */
    enc |= (hand_state[1].mode & 1) << 9;                    /* bit 9 */
    enc |= (wrap12(bass_semi_offset) & 0xF) << 10;           /* bits 10-13 */
    enc |= (hand_state[0].iso_anchor_offset == 10 ? 1 : 0) << 14; /* bit 14 */
    enc |= (hand_state[1].iso_anchor_offset == 10 ? 1 : 0) << 15; /* bit 15 */
    k_mutex_unlock(&inst_state_mutex);
    return enc;
}

void instrument_mode_decode_state(uint16_t enc) {
    k_mutex_lock(&inst_state_mutex, K_FOREVER);
    /* Clamp decoded semi offsets to 0-11 to defend against bit-rot */
    hand_state[0].semi_offset = (int8_t)(enc & 0xF);
    if (hand_state[0].semi_offset > 11) hand_state[0].semi_offset = 0;
    hand_state[0].mode = (enc >> 4) & 1;
    hand_state[1].semi_offset = (int8_t)((enc >> 5) & 0xF);
    if (hand_state[1].semi_offset > 11) hand_state[1].semi_offset = 0;
    hand_state[1].mode = (enc >> 9) & 1;
    bass_semi_offset = (int8_t)((enc >> 10) & 0xF);
    if (bass_semi_offset > 11) bass_semi_offset = 0;

    /* The 1-bit iso_anchor_offset fields in the split encoding (bits 14/15)
     * are lossy under the new per-col 2oct layout — the correct K can be
     * 0, 1, 9, 10, or 11 depending on the anchor's (row, col), not just
     * {0, 10}. Ignore the encoded value and recompute K locally from our
     * own last_note_pos for any hand in iso mode. This works because:
     *   - The peripheral tracks its own RH last_note_pos from its local
     *     matrix scan (events get raised locally before being forwarded).
     *   - LH K on peripheral is irrelevant (peripheral only renders RH).
     *   - Central computes K correctly in apply_command and never calls
     *     decode_state on itself, so this path only executes on peripheral.
     */
    (void)((enc >> 14) & 1); /* bit 14 ignored — see above */
    (void)((enc >> 15) & 1); /* bit 15 ignored — see above */
    for (int h = 0; h < 2; h++) {
        if (hand_state[h].mode == 1) {
            hand_state[h].iso_anchor_offset =
                compute_iso_anchor_k(last_note_pos[h]);
        } else {
            hand_state[h].iso_anchor_offset = 0;
        }
    }
    k_mutex_unlock(&inst_state_mutex);

    /* Invalidate color cache so the next render recomputes with new state */
    instrument_rgb_invalidate_cache();
}

/* ═══════════════════════════════════════════════════════════════════
 * Event listeners
 * ═══════════════════════════════════════════════════════════════════ */

static int instrument_mode_event_listener(const zmk_event_t *eh) {
    /* Layer state changes */
    const struct zmk_layer_state_changed *layer_ev = as_zmk_layer_state_changed(eh);
    if (layer_ev != NULL) {
        if (layer_ev->layer == CONFIG_ZMK_INSTRUMENT_LAYER) {
            bool was_active = active;
            active = layer_ev->state;
            LOG_DBG("inst layer %s", active ? "ON" : "OFF");
            if (active && !was_active) {
                instrument_rgb_invalidate_cache();
                instrument_rgb_trigger_refresh();
            }
        }
        return ZMK_EV_EVENT_BUBBLE;
    }

    /* Position state changes — track grid presses for iso anchor + held count.
     * Anchor = last pressed GRID key (matches bridge behavior — thumbs/bass
     * have no valid grid row/col so they can't be iso anchors).
     * MUST bubble the event so the split transport still forwards keys. */
    const struct zmk_position_state_changed *pos_ev = as_zmk_position_state_changed(eh);
    if (pos_ev != NULL && active) {
        uint8_t pos = pos_ev->position;
        if (is_grid_pos(pos)) {
            uint8_t hand = instrument_pos_hand(pos);
            if (pos_ev->state) {
                /* Press: update anchor + increment held count */
                last_note_pos[hand] = pos;
                if (held_grid_count[hand] < 255) {
                    held_grid_count[hand]++;
                }
            } else {
                /* Release: decrement held count */
                if (held_grid_count[hand] > 0) {
                    held_grid_count[hand]--;
                }
            }
        }
    }

    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(instrument_mode, instrument_mode_event_listener);
ZMK_SUBSCRIPTION(instrument_mode, zmk_layer_state_changed);
ZMK_SUBSCRIPTION(instrument_mode, zmk_position_state_changed);
