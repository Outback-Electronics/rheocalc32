from __future__ import annotations

import csv
import json

from viscobridge.models import Run, TestMethod


def save_run(run: Run, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(run.to_json())


def load_run(path: str) -> Run:
    with open(path, "r", encoding="utf-8") as f:
        return Run.from_json(f.read())


def save_method(method: TestMethod, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(method.to_dict(), f, indent=2)


def load_method(path: str) -> TestMethod:
    with open(path, "r", encoding="utf-8") as f:
        return TestMethod.from_dict(json.load(f))


def export_csv(run: Run, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Time (s)", "RPM", "Torque (%)", "Temp (C)",
                          "Shear Rate (1/s)", "Shear Stress (dyne/cm^2)", "Viscosity (cP)"])
        for p in run.points:
            writer.writerow([p.t_s, p.rpm, p.torque_pct, p.temp_c,
                              p.shear_rate, p.shear_stress, p.viscosity_cp])
