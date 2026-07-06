from __future__ import annotations

import random
from abc import ABC, abstractmethod

from viscobridge.constants import InstrumentModel, Spindle


class InstrumentError(RuntimeError):
    pass


class InstrumentDriver(ABC):
    """Common interface for anything that can drive a rotational
    viscometer/rheometer: set a target speed/temperature and read back
    the measured torque, speed and temperature."""

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def set_speed(self, rpm: float) -> None: ...

    @abstractmethod
    def set_temperature(self, temp_c: float) -> None: ...

    @abstractmethod
    def read(self) -> tuple[float, float, float]:
        """Returns (rpm, torque_pct, temp_c)."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...


class SimulatedInstrument(InstrumentDriver):
    """Generates plausible torque readings for a chosen fluid model so
    the application can be exercised end-to-end without real hardware.
    """

    def __init__(self, spindle: Spindle, instrument_model: InstrumentModel,
                 fluid_model: str = "power_law",
                 k: float = 2.0, n: float = 0.8, tau0: float = 0.0,
                 mu: float = 50.0, noise_pct: float = 1.5):
        self._spindle = spindle
        self._model = instrument_model
        self.fluid_model = fluid_model
        self.k = k
        self.n = n
        self.tau0 = tau0
        self.mu = mu
        self.noise_pct = noise_pct
        self._connected = False
        self._rpm = 0.0
        self._temp = 25.0

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def set_speed(self, rpm: float) -> None:
        if not self._connected:
            raise InstrumentError("Instrument not connected")
        self._rpm = max(0.0, rpm)

    def set_temperature(self, temp_c: float) -> None:
        if not self._connected:
            raise InstrumentError("Instrument not connected")
        self._temp = temp_c

    def _shear_stress(self, shear_rate: float) -> float:
        if self.fluid_model == "newtonian":
            return self.mu * shear_rate
        if self.fluid_model == "power_law":
            return self.k * shear_rate**self.n
        if self.fluid_model == "bingham":
            return self.tau0 + self.mu * shear_rate
        if self.fluid_model == "herschel_bulkley":
            return self.tau0 + self.k * shear_rate**self.n
        if self.fluid_model == "casson":
            sqrt_tau = (self.tau0**0.5) + (self.mu**0.5) * (shear_rate**0.5)
            return sqrt_tau**2
        raise ValueError(f"Unknown fluid model: {self.fluid_model}")

    def read(self) -> tuple[float, float, float]:
        if not self._connected:
            raise InstrumentError("Instrument not connected")
        # Use an effective SRC of 1.0 when the spindle has no true shear
        # rate (SRC == 0) purely so the simulator can still drive a
        # plausible torque signal; real shear rate/stress reporting
        # still follows the DV3T Appendix D rule (0 when SRC == 0).
        src_for_sim = self._spindle.src or 1.0
        shear_rate = src_for_sim * self._rpm
        torque_pct = 0.0
        if shear_rate > 0 and self._rpm > 0:
            stress = self._shear_stress(shear_rate)
            # torque_pct = stress / (TK * SMC * SRC); rearranged from the
            # DV3T Appendix D relation shear_stress = TK*SMC*SRC*%Torque
            denom = self._model.tk * self._spindle.smc * src_for_sim
            torque_pct = stress / denom if denom else 0.0
            torque_pct *= 1.0 + random.uniform(-self.noise_pct, self.noise_pct) / 100.0
        temp = self._temp + random.uniform(-0.05, 0.05)
        return self._rpm, max(0.0, min(100.0, torque_pct)), temp


# ---------------------------------------------------------------------------
# SerialInstrument: real hardware over RS-232 (or USB-to-RS232 adapter).
#
# This implements Brookfield's documented "DV-III Ultra to Computer Command
# Set" (Appendix G of the DV-III Ultra Operating Instructions manual),
# which the DV3 Ultra+ (firmware-compatible with DV-III Ultra) speaks:
#
#   COMMAND      FROM COMPUTER     RESPONSE FROM INSTRUMENT
#   K(Reset)     <K><CR>           no response
#   E(nable)     <E><CR>           <E><ss><CR>
#   R(etrieve)   <R><CR>           <R><vvvv><tttt><ss><CR>
#   V(elocity)   <V><xxxx><CR>     <V><ss><CR>
#   I(dentify)   <I><CR>           <I><ddd><mm><CR>
#   Z(ero)       <Z><CR>           <Z><vvvv><ss><CR>
#
# vvvv = torque transducer reading, 4 hex digits (~0400h at rest/0%,
#        ~2B00h at 100% torque -- 0x2700 = 9984 counts full scale).
# tttt = temperature reading, 4 hex digits (2700h = 0 degC, 40 counts/degC).
# xxxx = commanded speed in RPM * 10, as 4 hex digits.
# ss   = 2-hex-digit status byte.
# Port settings: 9600 baud, 8 data bits, no parity, 1 stop bit, no handshake.
#
# Note: this command set has no "set temperature" command -- the DV-III
# Ultra only reports its own temperature probe. An external bath/Thermosel
# is controlled through its own separate cable, not through this protocol,
# so set_temperature() here is a no-op.
# ---------------------------------------------------------------------------

TORQUE_FULL_SCALE_COUNTS = 0x2B00 - 0x0400  # ~9984 counts == 100% torque
TEMP_ZERO_COUNTS = 0x2700  # counts at 0 degC
TEMP_COUNTS_PER_DEGREE = 40.0


class SerialInstrument(InstrumentDriver):
    """Driver for a real DV-III Ultra / DV3 Ultra+ rheometer over RS-232
    (directly, or via a USB-to-RS232 adapter), using Brookfield's
    documented Appendix G command set."""

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial = None
        self._zero_offset = 0x0400
        self._rpm = 0.0
        self._status = "00"

    @staticmethod
    def list_ports() -> list[str]:
        """Returns the device names of available serial ports (including
        a USB-to-RS232 adapter's enumerated port)."""
        from serial.tools import list_ports

        return [p.device for p in list_ports.comports()]

    def connect(self) -> None:
        import serial  # imported lazily so the simulated driver works without pyserial

        self._serial = serial.Serial(
            self.port, self.baudrate, bytesize=8, parity="N", stopbits=1, timeout=self.timeout
        )
        self._serial.reset_input_buffer()
        self._send("E")
        self._zero()

    def disconnect(self) -> None:
        if self._serial is not None:
            try:
                self._send("K")
            except InstrumentError:
                pass
            self._serial.close()
            self._serial = None

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    @property
    def zero_offset_counts(self) -> int:
        return self._zero_offset

    def _send(self, body: str, timeout: float | None = None) -> str:
        if self._serial is None or not self._serial.is_open:
            raise InstrumentError("Instrument not connected")
        prev_timeout = self._serial.timeout
        if timeout is not None:
            self._serial.timeout = timeout
        try:
            self._serial.write((body + "\r").encode("ascii"))
            raw = self._serial.read_until(b"\r")
        finally:
            self._serial.timeout = prev_timeout
        reply = raw.decode("ascii", errors="replace").strip()
        if not reply:
            raise InstrumentError(f"No response from instrument to command {body!r}")
        return reply

    def _zero(self) -> None:
        # The Z command physically re-zeros the torque transducer, which
        # the front-panel autozero takes ~15s to do -- give it much more
        # time than the default read timeout used for other commands.
        reply = self._send("Z", timeout=20.0)
        if not reply.startswith("Z") or len(reply) < 7:
            raise InstrumentError(f"Unexpected Zero reply: {reply!r}")
        self._zero_offset = int(reply[1:5], 16)

    def identify(self) -> str:
        """Returns the model code string, e.g. 'DV3RV'. Mainly useful to
        confirm the link is actually talking to the instrument."""
        reply = self._send("I")
        if not reply.startswith("I") or len(reply) < 6:
            raise InstrumentError(f"Unexpected Identify reply: {reply!r}")
        return reply[1:4] + reply[4:6]

    def set_speed(self, rpm: float) -> None:
        xxxx = format(max(0, min(0xFFFF, round(rpm * 10))), "04X")
        reply = self._send(f"V{xxxx}")
        if not reply.startswith("V") or len(reply) < 3:
            raise InstrumentError(f"Unexpected Velocity reply: {reply!r}")
        self._status = reply[1:3]
        self._rpm = rpm

    def set_temperature(self, temp_c: float) -> None:
        # No documented command to set a target temperature on the
        # DV-III Ultra / DV3 Ultra+ -- see module docstring above.
        pass

    def read(self) -> tuple[float, float, float]:
        reply = self._send("R")
        if not reply.startswith("R") or len(reply) < 11:
            raise InstrumentError(
                f"Unexpected Retrieve reply: {reply!r}. Expected <R><vvvv><tttt><ss>."
            )
        vvvv = int(reply[1:5], 16)
        tttt = int(reply[5:9], 16)
        self._status = reply[9:11]
        torque_pct = (vvvv - self._zero_offset) / TORQUE_FULL_SCALE_COUNTS * 100.0
        temp_c = (tttt - TEMP_ZERO_COUNTS) / TEMP_COUNTS_PER_DEGREE
        return self._rpm, max(0.0, torque_pct), temp_c

