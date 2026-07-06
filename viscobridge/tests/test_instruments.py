import pytest

from viscobridge.instruments import SerialInstrument


class FakeSerial:
    """Stands in for pyserial's Serial, scripted with canned replies."""

    def __init__(self, replies):
        self._replies = list(replies)
        self.is_open = True
        self.written = []
        self.timeout = 1.0

    def write(self, data):
        self.written.append(data)

    def read_until(self, expected=b"\r"):
        return self._replies.pop(0)

    def reset_input_buffer(self):
        pass

    def close(self):
        self.is_open = False


def make_instrument(replies):
    inst = SerialInstrument("COM_TEST")
    inst._serial = FakeSerial(replies)
    return inst


def test_zero_parses_offset():
    inst = make_instrument([b"Z040000\r"])
    inst._zero()
    assert inst._zero_offset == 0x0400


def test_set_speed_encodes_rpm_as_hex_times_ten():
    inst = make_instrument([b"V00\r"])
    inst.set_speed(10.0)
    assert inst._serial.written[0] == b"V0064\r"  # 10.0 RPM * 10 = 100 = 0x0064


def test_read_decodes_torque_and_temperature():
    inst = make_instrument([b"R0000428704\r"])
    inst._zero_offset = 0x0400
    inst._rpm = 5.0
    rpm, torque_pct, temp_c = inst.read()
    assert rpm == 5.0
    vvvv = 0x0000
    expected_torque = (vvvv - 0x0400) / (0x2B00 - 0x0400) * 100.0
    assert torque_pct == max(0.0, expected_torque)
    tttt = 0x4287
    expected_temp = (tttt - 0x2700) / 40.0
    assert temp_c == pytest.approx(expected_temp)


def test_read_rejects_malformed_reply():
    inst = make_instrument([b"XX\r"])
    with pytest.raises(Exception):
        inst.read()
