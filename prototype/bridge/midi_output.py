"""
Virtual MIDI port output for Glove80 bridge.

Supports two backends:
  - ALSA sequencer (Linux, via alsa-midi)
  - rtmidi (cross-platform: Linux ALSA + macOS CoreMIDI, via python-rtmidi)

The bridge tries rtmidi first (works everywhere), falls back to alsa-midi on Linux.
"""

import sys


class MidiOutput:
    """Abstract MIDI output interface."""

    def __init__(self, port_name="Glove80 Instrument"):
        self.port_name = port_name

    def open(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def note_on(self, note, velocity=100, channel=0):
        raise NotImplementedError

    def note_off(self, note, channel=0):
        raise NotImplementedError

    def cc(self, control, value, channel=0):
        raise NotImplementedError

    def all_notes_off(self, channel=0):
        """Send note-off for all 128 MIDI notes + CC 123."""
        self.cc(123, 0, channel)
        for n in range(128):
            self.note_off(n, channel)


class RtMidiOutput(MidiOutput):
    """Cross-platform MIDI output via python-rtmidi (ALSA/CoreMIDI/WinMM)."""

    def __init__(self, port_name="Glove80 Instrument"):
        super().__init__(port_name)
        self._midi_out = None

    def open(self):
        import rtmidi
        self._midi_out = rtmidi.MidiOut()
        self._midi_out.open_virtual_port(self.port_name)
        print(f"MIDI virtual port created: {self.port_name} (rtmidi)")
        print(f"Connect your DAW to this port to receive MIDI")

    def close(self):
        if self._midi_out:
            self._midi_out.close_port()
            del self._midi_out
            self._midi_out = None

    def note_on(self, note, velocity=100, channel=0):
        if self._midi_out:
            status = 0x90 | (channel & 0x0F)
            self._midi_out.send_message([status, note & 0x7F, velocity & 0x7F])

    def note_off(self, note, channel=0):
        if self._midi_out:
            status = 0x80 | (channel & 0x0F)
            self._midi_out.send_message([status, note & 0x7F, 0])

    def cc(self, control, value, channel=0):
        if self._midi_out:
            status = 0xB0 | (channel & 0x0F)
            self._midi_out.send_message([status, control & 0x7F, value & 0x7F])


class AlsaMidiOutput(MidiOutput):
    """ALSA sequencer MIDI output (Linux only, via alsa-midi)."""

    def __init__(self, port_name="Glove80 Instrument"):
        super().__init__(port_name)
        self._client = None
        self._port = None

    def open(self):
        import alsa_midi
        self._client = alsa_midi.SequencerClient(self.port_name)
        self._port = self._client.create_port(
            self.port_name,
            caps=alsa_midi.PortCaps.READ | alsa_midi.PortCaps.SUBS_READ,
            type=alsa_midi.PortType.MIDI_GENERIC | alsa_midi.PortType.APPLICATION,
        )
        client_info = self._client.get_client_info()
        print(f"ALSA MIDI port created: {client_info.client_id}:{self._port.port_id} ({self.port_name})")
        print(f"Connect your DAW to this port to receive MIDI")

    def close(self):
        if self._client:
            self._client.close()
            self._client = None

    def note_on(self, note, velocity=100, channel=0):
        if self._client is None:
            return
        import alsa_midi
        event = alsa_midi.NoteOnEvent(note=note, velocity=velocity, channel=channel)
        self._client.event_output(event, port=self._port)
        self._client.drain_output()

    def note_off(self, note, channel=0):
        if self._client is None:
            return
        import alsa_midi
        event = alsa_midi.NoteOffEvent(note=note, velocity=0, channel=channel)
        self._client.event_output(event, port=self._port)
        self._client.drain_output()

    def cc(self, control, value, channel=0):
        if self._client is None:
            return
        import alsa_midi
        event = alsa_midi.ControlChangeEvent(channel=channel, param=control, value=value)
        self._client.event_output(event, port=self._port)
        self._client.drain_output()


def create_midi_output(port_name="Glove80 Instrument"):
    """Create the best available MIDI output for the current platform."""
    # Try rtmidi first (cross-platform)
    try:
        import rtmidi  # noqa: F401
        return RtMidiOutput(port_name)
    except ImportError:
        pass

    # Fall back to alsa-midi on Linux
    if sys.platform == "linux":
        try:
            import alsa_midi  # noqa: F401
            return AlsaMidiOutput(port_name)
        except ImportError:
            pass

    raise RuntimeError(
        "No MIDI backend available. Install one of:\n"
        "  pip install python-rtmidi   (cross-platform, recommended)\n"
        "  pip install alsa-midi       (Linux only)"
    )
