from __future__ import annotations

from PySide6.QtCore import QSettings

from viscobridge.instruments import TEMP_COUNTS_PER_DEGREE, TEMP_ZERO_COUNTS

_KEY_TEMP_ZERO_COUNTS = "instrument/temp_zero_counts"
_KEY_TEMP_COUNTS_PER_DEGREE = "instrument/temp_counts_per_degree"


def load_temp_zero_counts() -> int:
    """Returns the persisted calibrated zero-count offset for this
    machine, or the built-in fallback if no calibration has been saved
    yet. Persists across app restarts and reboots via QSettings
    (registry / plist / ini depending on OS)."""
    settings = QSettings()
    value = settings.value(_KEY_TEMP_ZERO_COUNTS, None)
    if value is None:
        return TEMP_ZERO_COUNTS
    return int(value)


def save_temp_zero_counts(counts: int) -> None:
    settings = QSettings()
    settings.setValue(_KEY_TEMP_ZERO_COUNTS, int(counts))
    settings.sync()


def load_temp_counts_per_degree() -> float:
    """Returns the persisted calibrated counts-per-degree slope, or the
    built-in fallback if no multi-point calibration has been saved yet."""
    settings = QSettings()
    value = settings.value(_KEY_TEMP_COUNTS_PER_DEGREE, None)
    if value is None:
        return TEMP_COUNTS_PER_DEGREE
    return float(value)


def save_temp_counts_per_degree(counts_per_degree: float) -> None:
    settings = QSettings()
    settings.setValue(_KEY_TEMP_COUNTS_PER_DEGREE, float(counts_per_degree))
    settings.sync()


def save_temp_calibration(zero_counts: int, counts_per_degree: float) -> None:
    """Persists both the offset and slope together, as produced by a
    single- or multi-point calibration run."""
    save_temp_zero_counts(zero_counts)
    save_temp_counts_per_degree(counts_per_degree)
