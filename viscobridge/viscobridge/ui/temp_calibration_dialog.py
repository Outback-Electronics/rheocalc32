from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from viscobridge.instruments import InstrumentError, SerialInstrument


class TempCalibrationDialog(QDialog):
    """Calibrates the temperature-sensor zero offset (and, optionally,
    its counts-per-degree slope) against known reference temperatures.

    Single point: immerse the probe in one known reference (an ice-water
    bath at 0.0 degC is the simplest) and solve for the zero offset only,
    keeping the existing slope.

    Multi point: capture raw counts at several known reference
    temperatures (e.g. ice bath, room temp, a warm bath) and least-squares
    fit both the offset and the counts-per-degree slope.

    Either way, the result is applied to the live instrument and
    persisted (viscobridge.settings) so it survives app restarts and
    reboots until recalibrated."""

    def __init__(self, instrument: SerialInstrument, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Temperature Calibration")
        self.instrument = instrument
        self.new_zero_counts: int | None = None
        self.new_counts_per_degree: float | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Immerse the temperature probe in a known-temperature reference\n"
            "and wait for the reading to stabilize before capturing.\n"
            "A stirred ice-water bath at 0.0 degC is the easiest reliable point."
        ))
        layout.addWidget(QLabel(
            f"Current saved calibration: zero={self.instrument.temp_zero_counts} counts, "
            f"{self.instrument.temp_counts_per_degree:.3f} counts/degC"
        ))

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Single point", "Multi point (curve fit)"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self.mode_combo)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_single_point_page())
        self.stack.addWidget(self._build_multi_point_page())
        layout.addWidget(self.stack)

        self.result_label = QLabel("No reading captured yet.")
        layout.addWidget(self.result_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.save_button = buttons.button(QDialogButtonBox.Save)
        self.save_button.setEnabled(False)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ---------------------------------------------------------- single point
    def _build_single_point_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.single_ref_temp_spin = QDoubleSpinBox()
        self.single_ref_temp_spin.setRange(-50.0, 150.0)
        self.single_ref_temp_spin.setDecimals(2)
        self.single_ref_temp_spin.setSuffix(" degC")
        self.single_ref_temp_spin.setValue(0.0)
        form.addRow("Known reference temperature", self.single_ref_temp_spin)
        layout.addLayout(form)

        capture_btn = QPushButton("Capture reading")
        capture_btn.clicked.connect(self._capture_single)
        layout.addWidget(capture_btn)
        return page

    def _capture_single(self):
        tttt = self._read_raw_counts()
        if tttt is None:
            return
        ref_temp_c = self.single_ref_temp_spin.value()
        slope = self.instrument.temp_counts_per_degree
        zero_counts = round(tttt - ref_temp_c * slope)
        old_temp_c = (tttt - self.instrument.temp_zero_counts) / slope

        self.new_zero_counts = zero_counts
        self.new_counts_per_degree = slope
        self.result_label.setText(
            f"Raw reading: {tttt} counts (currently decodes to {old_temp_c:.2f} degC).\n"
            f"At reference {ref_temp_c:.2f} degC, new zero offset would be "
            f"{zero_counts} counts (slope kept at {slope:.3f} counts/degC)."
        )
        self.save_button.setEnabled(True)

    # ----------------------------------------------------------- multi point
    def _build_multi_point_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        row = QHBoxLayout()
        self.multi_ref_temp_spin = QDoubleSpinBox()
        self.multi_ref_temp_spin.setRange(-50.0, 150.0)
        self.multi_ref_temp_spin.setDecimals(2)
        self.multi_ref_temp_spin.setSuffix(" degC")
        row.addWidget(QLabel("Known reference temperature"))
        row.addWidget(self.multi_ref_temp_spin)
        add_btn = QPushButton("Capture point")
        add_btn.clicked.connect(self._capture_multi_point)
        row.addWidget(add_btn)
        remove_btn = QPushButton("Remove selected")
        remove_btn.clicked.connect(self._remove_selected_point)
        row.addWidget(remove_btn)
        layout.addLayout(row)

        self.points_table = QTableWidget(0, 2)
        self.points_table.setHorizontalHeaderLabels(["Reference (degC)", "Raw counts"])
        layout.addWidget(self.points_table)

        fit_btn = QPushButton("Compute fit")
        fit_btn.clicked.connect(self._compute_fit)
        layout.addWidget(fit_btn)
        return page

    def _capture_multi_point(self):
        tttt = self._read_raw_counts()
        if tttt is None:
            return
        ref_temp_c = self.multi_ref_temp_spin.value()
        row = self.points_table.rowCount()
        self.points_table.insertRow(row)
        self.points_table.setItem(row, 0, QTableWidgetItem(f"{ref_temp_c:.2f}"))
        self.points_table.setItem(row, 1, QTableWidgetItem(str(tttt)))

    def _remove_selected_point(self):
        rows = sorted({idx.row() for idx in self.points_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.points_table.removeRow(row)

    def _compute_fit(self):
        n = self.points_table.rowCount()
        if n < 2:
            QMessageBox.warning(
                self, "Not enough points",
                "Capture at least two points at different known reference temperatures "
                "before computing a fit.",
            )
            return
        ref_temps = np.array([float(self.points_table.item(r, 0).text()) for r in range(n)])
        raw_counts = np.array([float(self.points_table.item(r, 1).text()) for r in range(n)])
        if len(set(ref_temps.round(6))) < 2:
            QMessageBox.warning(
                self, "Not enough distinct temperatures",
                "All captured points use the same reference temperature -- capture points "
                "at two or more distinct temperatures to fit both offset and slope.",
            )
            return

        # raw_counts = slope * ref_temp + zero_counts
        slope, zero_counts = np.polyfit(ref_temps, raw_counts, 1)

        self.new_zero_counts = round(zero_counts)
        self.new_counts_per_degree = float(slope)
        self.result_label.setText(
            f"Fit over {n} points: zero offset = {self.new_zero_counts} counts, "
            f"slope = {self.new_counts_per_degree:.3f} counts/degC."
        )
        self.save_button.setEnabled(True)

    # --------------------------------------------------------------- shared
    def _read_raw_counts(self) -> int | None:
        try:
            return self.instrument.read_raw_temp_counts()
        except InstrumentError as exc:
            QMessageBox.critical(self, "Read failed", str(exc))
            return None

    def _on_mode_changed(self, index: int):
        self.stack.setCurrentIndex(index)
        self.save_button.setEnabled(False)
        self.result_label.setText("No reading captured yet.")

    def _save(self):
        if self.new_zero_counts is None or self.new_counts_per_degree is None:
            return
        self.accept()
