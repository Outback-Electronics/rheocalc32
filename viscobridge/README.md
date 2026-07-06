# ViscoBridge (Python / PySide6)

An independent, from-scratch rotational viscometer/rheometer control and
analysis application, compatible with Brookfield DV3T / DV-III Ultra
instruments. Not affiliated with, endorsed by, or sponsored by Brookfield
Engineering Laboratories / AMETEK. "Brookfield", "RheoCalc", and "DV3T" are
trademarks of their respective owners, referenced here only to describe
hardware compatibility.

## Features

- **Method editor** — sample info, spindle selection (with editable
  SRC/SMC calibration constants), and a step table (speed ramps, speed
  holds, time holds, temperature ramps).
- **Instrument drivers** — pluggable `InstrumentDriver` interface with a
  `SimulatedInstrument` (generates realistic torque from a chosen fluid
  model: Newtonian, Power Law, Bingham, Herschel-Bulkley, Casson) for
  testing without hardware, and a `SerialInstrument` for real
  RS-232/USB-serial Brookfield-protocol instruments.
- **Live acquisition & plotting** — real-time viscosity vs. shear rate,
  torque vs. time, and temperature vs. time plots while a run executes.
- **Flow curve model fitting** — least-squares fits to Newtonian, Power
  Law, Bingham, Herschel-Bulkley, and Casson models with R² and fitted
  parameters (consistency index, flow index, yield stress, viscosity).
- **Run management** — save/load runs as `.vbr` (JSON) files, export
  to CSV.
- **Test templates** — one-click presets (Flow Curve, Thixotropic Index
  Up-Down, Temperature Sweep, Time Hold stability check) to populate the
  step table, RheoCalc Test-Wizard style.
- **Run comparison** — overlay viscosity-vs-shear-rate curves from
  multiple saved `.vbr` runs on one plot to compare samples/batches.
- **Printable reports** — export a self-contained HTML report per run
  with sample/method info, step table, embedded flow-curve chart, fit
  results, and the full data table (opens and prints from any browser).

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m viscobridge
```

## Desktop shortcut (Linux)

To get a clickable icon (application menu + Desktop) instead of running
from a terminal each time:

```bash
scripts/install-desktop-shortcut.sh
```

This installs a `viscobridge.desktop` entry pointing at
`scripts/viscobridge.sh`, which runs `python -m viscobridge` with the
system `python3` -- the dependencies from `requirements.txt` must
already be installed for it (same as running from a terminal; no
virtualenv is created). Run the installer once per machine/checkout
location -- it embeds this checkout's absolute path, so re-run it if you
move or re-clone the repo.

If double-clicking the icon appears to do nothing, check
`/tmp/viscobridge-launch.log` -- Terminal=false hides output, so
`scripts/viscobridge.sh` writes it there and pops an error dialog
(zenity/kdialog/xmessage, whichever is installed) if the launch fails.

## Notes on accuracy and connecting to a real DV3T / DV3 Ultra+

The spindle SMC/SRC values and instrument-model TK (torque) constants
bundled in `constants.py` are taken directly from Brookfield's published
DV3T Operating Instructions (Manual No. M13-167-A0415), Appendix D —
`Viscosity (cP) = TK * SMC * 100 * %Torque / RPM`,
`Shear Rate (1/s) = SRC * RPM`,
`Shear Stress (dyne/cm^2) = TK * SMC * SRC * %Torque`.
If you're using a Special Spindle (custom geometry), edit SMC/SRC in the
Method panel to match its calibration certificate.

**Real hardware:** `instruments.py`'s `SerialInstrument` implements
Brookfield's documented "DV-III Ultra to Computer Command Set" (Appendix
G of the DV-III Ultra Operating Instructions manual), which the DV3
Ultra+ also speaks (it runs DV-III Ultra-compatible firmware). This is a
real, published protocol — not a guess:

- Single-letter ASCII commands terminated by `\r`: `K` (reset), `E`
  (enable), `R` (retrieve reading), `V` + 4 hex digits (set speed,
  RPM*10), `I` (identify), `Z` (zero).
- `connect()` sends `E` then `Z` to calibrate a zero-torque offset that's
  subtracted from every subsequent reading.
- `read()` parses the `<R><vvvv><tttt><ss>` reply: `vvvv` is the torque
  transducer count (4 hex digits, ~0x0400 at 0% torque, ~0x2B00 at 100%),
  `tttt` is the temperature count (4 hex digits, 0x2700 = 0 degC, 40
  counts/degC), `ss` is a status byte.
- Port settings: 9600 baud, 8 data bits, no parity, 1 stop bit, no
  handshake.
- The DV-III Ultra command set has no "set temperature" command — it only
  reports its own probe reading. An external bath/Thermosel is controlled
  through its own separate cable, so `set_temperature()` here is a
  documented no-op.

If you're on a different model whose USB virtual COM port doesn't speak
this protocol, verify readings against the instrument's own display
before trusting the GUI.

Use **Connect...** in the toolbar to pick "Real instrument" and a serial
port (auto-detected, including USB-serial enumeration), or "Simulated
instrument" to exercise the app without hardware.
