/*
 * Copyright (c) 2026 Tal Onn Sella
 * SPDX-License-Identifier: MIT
 *
 * Instrument mode state machine for Glove80 MIDI instrument.
 * Tracks per-hand musical state (mode, semitone offset, bass offset,
 * iso anchor) and drives dynamic RGB rendering with note pulsing.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

/* Commands for &inst behavior — param1 */
#define INST_CMD_SEMI_INC       0
#define INST_CMD_SEMI_DEC       1
#define INST_CMD_SEMI_RST       2
#define INST_CMD_MODE_TOG       3
#define INST_CMD_OCT_INC        4
#define INST_CMD_OCT_DEC        5
#define INST_CMD_BASS_SEMI_INC  6
#define INST_CMD_BASS_SEMI_DEC  7

/* Hand identifiers — param2 */
#define INST_HAND_LH 0
#define INST_HAND_RH 1

struct instrument_hand_state {
    uint8_t mode;              /* 0=dual_octave, 1=isomorphic */
    int8_t  semi_offset;       /* 0..11 semitones (mod 12) */
    int8_t  iso_anchor_offset; /* K value for iso color accuracy */
};

bool instrument_mode_is_active(void);
void instrument_mode_set_active(bool active);
void instrument_mode_apply_command(uint8_t hand, uint8_t cmd);
const struct instrument_hand_state *instrument_mode_get_hand(uint8_t hand);
int8_t instrument_mode_get_bass_offset(void);
void instrument_mode_note_played(uint8_t hand, uint8_t position);

/*
 * Split sync: encode both hands' state into 16 bits for piggybacking
 * on the layer bitmask upper bits.
 */
uint16_t instrument_mode_encode_state(void);
void instrument_mode_decode_state(uint16_t encoded);
