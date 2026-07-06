"""Spindle and instrument-model calibration constants for Brookfield-style
rotational viscometers/rheometers (DV3T family).

Values below are taken from the published DV3T Operating Instructions
(Brookfield Manual No. M13-167-A0415), Appendix D "Spindle Entry Codes
and SMC/SRC Values" (Table D-1) and "Torque Constants" (Table D-2):

    Viscosity (cP)            = TK * SMC * 100 * %Torque / RPM
    Shear Rate (1/s)          = SRC * RPM            (0 if SRC == 0, i.e.
                                 spindle/container geometry without a
                                 defined true shear rate)
    Shear Stress (dyne/cm^2)  = TK * SMC * SRC * %Torque

TK is the torque spring constant of the rheometer model (Table D-2);
SMC/SRC are per-spindle constants (Table D-1). These are the same
constants reported on a DV3T's "Spindle List" / calibration screens, so
they should match a real instrument out of the box; if your unit uses a
Special Spindle (user-defined geometry), edit SMC/SRC in the UI to match
its certificate.
"""
from dataclasses import dataclass


@dataclass
class Spindle:
    name: str
    entry_code: str
    smc: float  # Spindle Multiplier Constant
    src: float  # Shear Rate Constant, (1/s) per RPM; 0 = not defined for this spindle
    description: str = ""


@dataclass
class InstrumentModel:
    name: str
    tk: float  # torque spring constant


# Table D-2: DV3T model torque constants
INSTRUMENT_MODELS: list[InstrumentModel] = [
    InstrumentModel("DV3TLV", 0.09375),
    InstrumentModel("DV3TL3", 0.234375),
    InstrumentModel("DV3TL5", 0.46875),
    InstrumentModel("DV3TRQ", 0.25),
    InstrumentModel("DV3TRH", 0.5),
    InstrumentModel("DV3TRV", 1.0),
    InstrumentModel("DV3THA", 2.0),
    InstrumentModel("DV3TA2", 4.0),
    InstrumentModel("DV3TA3", 5.0),
    InstrumentModel("DV3THB", 8.0),
    InstrumentModel("DV3TB2", 16.0),
    InstrumentModel("DV3TB3", 20.0),
    InstrumentModel("DV3TB5", 40.0),
]

# Table D-1: spindle entry codes, SMC, SRC (subset covering RV/HA/HB/LV
# cylindrical spindles, cone/plate, and the common SC4/DIN/ULA spindles).
DEFAULT_SPINDLES: list[Spindle] = [
    Spindle("RV1", "01", 1.0, 0.0, "Cylindrical, RV/HA/HB series"),
    Spindle("RV2", "02", 4.0, 0.0, "Cylindrical, RV/HA/HB series"),
    Spindle("RV3", "03", 10.0, 0.0, "Cylindrical, RV/HA/HB series"),
    Spindle("RV4", "04", 20.0, 0.0, "Cylindrical, RV/HA/HB series"),
    Spindle("RV5", "05", 40.0, 0.0, "Cylindrical, RV/HA/HB series"),
    Spindle("RV6", "06", 100.0, 0.0, "Cylindrical, RV/HA/HB series"),
    Spindle("RV7", "07", 400.0, 0.0, "Cylindrical, RV/HA/HB series"),
    Spindle("LV1", "61", 6.4, 0.0, "Cylindrical, LV series"),
    Spindle("LV2", "62", 32.0, 0.0, "Cylindrical, LV series"),
    Spindle("LV3", "63", 128.0, 0.0, "Cylindrical, LV series"),
    Spindle("LV4 / 4B2", "64", 640.0, 0.0, "Cylindrical, LV series"),
    Spindle("LV5", "65", 1280.0, 0.0, "Cylindrical, LV series"),
    Spindle("LV-2C", "66", 32.0, 0.212, "Coaxial cylinder, true shear rate"),
    Spindle("LV-3C", "67", 128.0, 0.210, "Coaxial cylinder, true shear rate"),
    Spindle("SA-70", "70", 105.0, 0.677, "Vane/cylinder, true shear rate"),
    Spindle("ULA", "00", 0.64, 1.223, "UL adapter, true shear rate"),
    Spindle("DIN-81", "81", 3.7, 1.29, "DIN coaxial cylinder"),
    Spindle("DIN-82", "82", 3.75, 1.29, "DIN coaxial cylinder"),
    Spindle("DIN-83", "83", 12.09, 1.29, "DIN coaxial cylinder"),
    Spindle("DIN-85", "85", 1.22, 1.29, "DIN coaxial cylinder"),
    Spindle("DIN-86", "86", 3.65, 1.29, "DIN coaxial cylinder"),
    Spindle("DIN-87", "87", 12.13, 1.29, "DIN coaxial cylinder"),
    Spindle("SC4-14", "14", 125.0, 0.40, "Small Sample Adapter"),
    Spindle("SC4-15", "15", 50.0, 0.48, "Small Sample Adapter"),
    Spindle("SC4-16", "16", 128.0, 0.29, "Small Sample Adapter"),
    Spindle("SC4-18", "18", 3.2, 1.32, "Small Sample Adapter"),
    Spindle("SC4-21", "21", 5.0, 0.93, "Small Sample Adapter"),
    Spindle("SC4-25", "25", 512.0, 0.22, "Small Sample Adapter"),
    Spindle("SC4-27", "27", 25.0, 0.34, "Small Sample Adapter"),
    Spindle("SC4-28", "28", 50.0, 0.28, "Small Sample Adapter"),
    Spindle("SC4-29", "29", 100.0, 0.25, "Small Sample Adapter"),
    Spindle("SC4-31", "31", 32.0, 0.34, "Small Sample Adapter"),
    Spindle("SC4-34", "34", 64.0, 0.28, "Small Sample Adapter"),
    Spindle("CP-40 / CPE-40 / CPA-40Z", "40", 0.327, 7.5, "Cone/Plate"),
    Spindle("CP-41 / CPE-41 / CPA-41Z", "41", 1.228, 2.0, "Cone/Plate"),
    Spindle("CP-42 / CPE-42 / CPA-42Z", "42", 0.64, 3.84, "Cone/Plate"),
    Spindle("CP-51 / CPE-51 / CPA-51Z", "51", 5.178, 3.84, "Cone/Plate"),
    Spindle("CP-52 / CPE-52 / CPA-52Z", "52", 9.922, 2.0, "Cone/Plate"),
    Spindle("Custom / Special Spindle", "1xx", 1.0, 0.0, "User-defined (enter SMC/SRC from calibration)"),
]

STEP_TYPES = ["Speed Ramp", "Speed Hold", "Temperature Ramp", "Time Hold"]

# DV3T manual (M13-167-A0415) Section II.7 "Out of Range": at 100% torque the
# instrument's own display shows EEEE for %Torque/Viscosity/Shear Stress.
# There is no overload bit in the RS-232 protocol (Appendix I, Table I-3) --
# the instrument itself never auto-stops on overload, so ViscoBridge does
# this check itself instead of relying on hardware/protocol support.
TORQUE_OVERLOAD_PCT = 100.0
