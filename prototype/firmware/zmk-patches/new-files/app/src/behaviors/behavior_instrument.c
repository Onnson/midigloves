/*
 * Copyright (c) 2026 Tal Onn Sella
 * SPDX-License-Identifier: MIT
 *
 * &inst behavior — dispatches instrument mode commands.
 * Usage: &inst COMMAND HAND
 *   param1 = command (INST_CMD_SEMI_INC, etc.)
 *   param2 = hand (0=LH, 1=RH)
 */

#define DT_DRV_COMPAT zmk_behavior_instrument

#include <zephyr/device.h>
#include <drivers/behavior.h>
#include <zephyr/logging/log.h>
#include <zmk/instrument_mode.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

#if DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT)

static int on_binding_pressed(struct zmk_behavior_binding *binding,
                              struct zmk_behavior_binding_event event) {
    LOG_DBG("inst cmd=%d hand=%d pos=%d", binding->param1, binding->param2, event.position);
    instrument_mode_apply_command(binding->param2, binding->param1);
    return ZMK_BEHAVIOR_OPAQUE;
}

static int on_binding_released(struct zmk_behavior_binding *binding,
                               struct zmk_behavior_binding_event event) {
    return ZMK_BEHAVIOR_OPAQUE;
}

static const struct behavior_driver_api behavior_instrument_driver_api = {
    .binding_pressed = on_binding_pressed,
    .binding_released = on_binding_released,
};

BEHAVIOR_DT_INST_DEFINE(0, NULL, NULL, NULL, NULL, POST_KERNEL,
                        CONFIG_KERNEL_INIT_PRIORITY_DEFAULT,
                        &behavior_instrument_driver_api);

#endif /* DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT) */
