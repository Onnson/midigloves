# midigloves — Zephyr out-of-tree module
#
# Implements the Glove80 MIDI instrument: per-hand state machine, chromatic
# RGB rendering with scale-aware dimming, USB/BLE MIDI dispatch, three-channel
# note routing, R1 + bass pitch-bend glide, and Ableton scale SysEx handling.
#
# Source files are added incrementally across Milestones 1–4 of the Device 1.0
# plan. This file stays tiny until then — during Milestone 0 the module
# compiles as an empty library so `west build` succeeds end-to-end.

if(CONFIG_MIDIGLOVES)
  zephyr_library_named(midigloves)
  zephyr_library_include_directories(include)

  # Sources land here as the milestones progress:
  #   M1: src/instrument.c src/instrument_rgb.c src/behavior_instrument.c
  #       src/behavior_instrument_ht.c src/midi.c src/midi_glide.c
  #   M2: src/scale.c
endif()
