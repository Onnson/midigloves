/*
 * Copyright (c) 2026 Tal Onn Sella
 * SPDX-License-Identifier: MIT
 *
 * Instrument mode RGB renderer — computes per-key chromatic colors
 * at runtime with sustained brightness.
 */

#pragma once

#include <zephyr/drivers/led_strip.h>

void instrument_rgb_render(struct led_rgb *pixels, int num_pixels);
void instrument_rgb_trigger_refresh(void);
void instrument_rgb_invalidate_cache(void);
