from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from viscobridge import io_utils, report, settings
from viscobridge.instruments import InstrumentDriver, InstrumentError, SerialInstrument, SimulatedInstrument
from viscobridge.models import DataPoint, Run, TestStep
from viscobridge.ui.calibration_dialog import CalibrationDialog
from viscobridge.ui.compare_dialog import CompareDialog
from viscobridge.ui.connect_dialog import ConnectDialog
from viscobridge.ui.fit_dialog import FitDialog
from viscobridge.ui.method_editor import MethodEditor
from viscobridge.ui.plot_widget import PlotWidget
from viscobridge.ui.temp_calibration_dialog import TempCalibrationDialog
from viscobridge.ui.temp_fit_dialog import TempFitDialog

DATA_COLUMNS = ["Time (s)", "RPM", "Torque (%)", "Temp (C)", "Shear Rate (1/s)",
                "Shear Stress (dyne/cm^2)", "Viscosity (cP)"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ViscoBridge")
        self.resize(1200, 800)

        self.instrument: InstrumentDriver | None = None
        self.run: Run | None = None
        self.step_queue: list[TestStep] = []
        self.current_step: TestStep | None = None
        self.step_elapsed = 0.0
        self.run_elapsed = 0.0
        self.manual_mode_active = False
        self.last_fit_result = None
        self.instrument_id = ""
        self.zero_offset_counts: int | None = None
        self.last_calibration_record: dict | None = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        self._build_ui()
        self._build_menu()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)

        splitter = QSplitter()
        outer.addWidget(splitter)

        self.method_editor = MethodEditor()
        splitter.addWidget(self.method_editor)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        btn_row = QHBoxLayout()
        self.connect_btn = QPushButton("Connect...")
        self.start_btn = QPushButton("Start Run")
        self.stop_btn = QPushButton("Stop Run")
        self.fit_btn = QPushButton("Fit Flow Curve...")
        self.save_btn = QPushButton("Save Run...")
        self.load_btn = QPushButton("Load Run...")
        self.export_btn = QPushButton("Export CSV...")
        self.report_btn = QPushButton("Export Report...")
        self.compare_btn = QPushButton("Compare Runs...")
        for b in (self.connect_btn, self.start_btn, self.stop_btn, self.fit_btn,
                  self.save_btn, self.load_btn, self.export_btn, self.report_btn,
                  self.compare_btn):
            btn_row.addWidget(b)
        right_layout.addLayout(btn_row)

        self.connect_btn.clicked.connect(self.toggle_connect)
        self.start_btn.clicked.connect(self.start_run)
        self.stop_btn.clicked.connect(self.stop_run)
        self.fit_btn.clicked.connect(self.open_fit_dialog)
        self.save_btn.clicked.connect(self.save_run)
        self.load_btn.clicked.connect(self.load_run)
        self.export_btn.clicked.connect(self.export_csv)
        self.report_btn.clicked.connect(self.export_report)
        self.compare_btn.clicked.connect(self.open_compare_dialog)
        self.stop_btn.setEnabled(False)

        manual_row = QHBoxLayout()
        manual_row.addWidget(QLabel("Manual run speed (RPM):"))
        self.manual_speed_spin = QDoubleSpinBox()
        self.manual_speed_spin.setRange(0.1, 250.0)
        self.manual_speed_spin.setValue(10.0)
        self.manual_speed_spin.setDecimals(1)
        manual_row.addWidget(self.manual_speed_spin)
        self.manual_start_btn = QPushButton("Start Manual Run (runs until stopped)")
        manual_row.addWidget(self.manual_start_btn)
        manual_row.addStretch()
        right_layout.addLayout(manual_row)

        self.manual_start_btn.clicked.connect(self.start_manual_run)

        dashboard = QWidget()
        grid = QGridLayout(dashboard)
        self.viscosity_plot = PlotWidget("Shear Rate (1/s)", "Viscosity (cP)", "Viscosity vs Shear Rate")
        self.stress_plot = PlotWidget("Shear Rate (1/s)", "Shear Stress (dyne/cm^2)", "Shear Stress vs Shear Rate")
        self.viscosity_time_plot = PlotWidget("Time (s)", "Viscosity (cP)", "Viscosity vs Time")
        self.temp_plot = PlotWidget("Time (s)", "Temperature (C)", "Temperature vs Time")
        grid.addWidget(self.viscosity_plot, 0, 0)
        grid.addWidget(self.stress_plot, 0, 1)
        grid.addWidget(self.viscosity_time_plot, 1, 0)
        grid.addWidget(self.temp_plot, 1, 1)
        right_layout.addWidget(dashboard, stretch=2)

        self.data_table = QTableWidget(0, len(DATA_COLUMNS))
        self.data_table.setHorizontalHeaderLabels(DATA_COLUMNS)
        right_layout.addWidget(self.data_table, stretch=1)

        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)

        self.statusBar().showMessage("Disconnected")

    def _build_menu(self):
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction("Save Run...", self.save_run)
        file_menu.addAction("Load Run...", self.load_run)
        file_menu.addAction("Export CSV...", self.export_csv)
        file_menu.addAction("Export Report...", self.export_report)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        analysis_menu = self.menuBar().addMenu("&Analysis")
        analysis_menu.addAction("Fit Flow Curve...", self.open_fit_dialog)
        analysis_menu.addAction("Fit Temperature Dependence...", self.open_temp_fit_dialog)
        analysis_menu.addAction("Compare Runs...", self.open_compare_dialog)

        instrument_menu = self.menuBar().addMenu("&Instrument")
        instrument_menu.addAction("Calibration Check (30s, no spindle)...", self.open_calibration_dialog)
        instrument_menu.addAction("Temperature Calibration...", self.open_temp_calibration_dialog)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction("About", self._show_about)

    def _show_about(self):
        QMessageBox.information(
            self, "About ViscoBridge",
            "ViscoBridge (Python/PySide6 edition)\n\n"
            "Rotational viscometer/rheometer control and rheological "
            "analysis: step-based test methods, live data acquisition, "
            "flow curve model fitting, and reporting."
        )

    # --------------------------------------------------------- instrument
    def toggle_connect(self):
        if self.instrument is not None and self.instrument.is_connected:
            if self.timer.isActive():
                self.stop_run()
            self.instrument.disconnect()
            self.instrument = None
            self.connect_btn.setText("Connect...")
            self.statusBar().showMessage("Disconnected")
            return

        dlg = ConnectDialog(self)
        if dlg.exec() != ConnectDialog.Accepted:
            return

        method = self.method_editor.get_method()
        if dlg.use_simulated():
            self.instrument = SimulatedInstrument(method.spindle, method.instrument_model,
                                                    fluid_model="power_law", k=3.0, n=0.75)
            status = "Connected (simulated instrument)"
        else:
            port = dlg.port()
            if not port:
                QMessageBox.warning(self, "No port", "Select or enter a serial port.")
                return
            self.instrument = SerialInstrument(
                port, baudrate=dlg.baudrate(),
                temp_zero_counts=settings.load_temp_zero_counts(),
                temp_counts_per_degree=settings.load_temp_counts_per_degree(),
            )
            status = f"Connected to {port} @ {dlg.baudrate()} baud"

        try:
            self.instrument.connect()
        except Exception as exc:
            QMessageBox.critical(self, "Connection failed", str(exc))
            self.instrument = None
            return

        self.instrument_id = ""
        self.zero_offset_counts = None
        if isinstance(self.instrument, SerialInstrument):
            try:
                self.instrument_id = self.instrument.identify()
            except InstrumentError:
                pass
            self.zero_offset_counts = self.instrument.zero_offset_counts

        self.connect_btn.setText("Disconnect")
        self.statusBar().showMessage(status)

    # --------------------------------------------------------------- run
    def start_run(self):
        if self.instrument is None or not self.instrument.is_connected:
            QMessageBox.warning(self, "Not connected", "Connect to an instrument before starting a run.")
            return
        method = self.method_editor.get_method()
        if not method.steps:
            QMessageBox.warning(self, "No steps", "Add at least one test step to the method.")
            return

        sample = self.method_editor.get_sample()
        self.run = Run(
            method=method,
            sample=sample,
            timestamp=datetime.now(timezone.utc).isoformat(),
            instrument_id=self.instrument_id,
            zero_offset_counts=self.zero_offset_counts,
            calibration_check=self.last_calibration_record,
        )
        self.step_queue = list(method.steps)
        self.current_step = None
        self.run_elapsed = 0.0
        self.last_fit_result = None
        self.data_table.setRowCount(0)
        for plot in (self.viscosity_plot, self.stress_plot, self.viscosity_time_plot, self.temp_plot):
            plot.clear()

        self._advance_step()
        self.timer.start(int(self.current_step.interval_s * 1000) if self.current_step else 1000)
        self.manual_mode_active = False
        self.start_btn.setEnabled(False)
        self.manual_start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def _advance_step(self):
        if not self.step_queue:
            self.current_step = None
            return
        self.current_step = self.step_queue.pop(0)
        self.step_elapsed = 0.0
        if self.current_step.target_temp_c is not None and self.instrument:
            self.instrument.set_temperature(self.current_step.target_temp_c)

    def start_manual_run(self):
        # Unconditional run: holds a single fixed speed with no duration
        # limit, so it never auto-stops (unlike a method run's step queue) -
        # only an explicit Stop Run click ends it.
        if self.instrument is None or not self.instrument.is_connected:
            QMessageBox.warning(self, "Not connected", "Connect to an instrument before starting a manual run.")
            return
        if self.timer.isActive():
            QMessageBox.warning(self, "Run in progress", "Stop the current run before starting a manual run.")
            return

        rpm = self.manual_speed_spin.value()
        method = self.method_editor.get_method()
        manual_step = TestStep(
            step_type="Speed Hold",
            start_speed_rpm=rpm,
            end_speed_rpm=rpm,
            duration_s=float("inf"),
            interval_s=1.0,
        )
        method.steps = [manual_step]

        sample = self.method_editor.get_sample()
        self.run = Run(
            method=method,
            sample=sample,
            timestamp=datetime.now(timezone.utc).isoformat(),
            instrument_id=self.instrument_id,
            zero_offset_counts=self.zero_offset_counts,
            calibration_check=self.last_calibration_record,
        )
        self.step_queue = []
        self.current_step = manual_step
        self.step_elapsed = 0.0
        self.run_elapsed = 0.0
        self.last_fit_result = None
        self.data_table.setRowCount(0)
        for plot in (self.viscosity_plot, self.stress_plot, self.viscosity_time_plot, self.temp_plot):
            plot.clear()

        self.manual_mode_active = True
        self.timer.start(int(manual_step.interval_s * 1000))
        self.start_btn.setEnabled(False)
        self.manual_start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.statusBar().showMessage(f"Manual run: holding {rpm:.1f} RPM (runs until stopped)")

    def stop_run(self):
        # Stopping the poll timer alone does not stop the spindle -- the
        # instrument keeps spinning at its last commanded speed until a new
        # speed command is sent, so Stop must explicitly command 0 RPM.
        self.timer.stop()
        stop_error = None
        if self.instrument is not None and self.instrument.is_connected:
            try:
                self.instrument.set_speed(0.0)
            except InstrumentError as exc:
                stop_error = str(exc)

        was_manual = self.manual_mode_active
        self.manual_mode_active = False
        self.current_step = None
        self.step_queue = []
        self.start_btn.setEnabled(True)
        self.manual_start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        if stop_error:
            self.statusBar().showMessage("Stop command failed -- spindle may still be rotating!")
            QMessageBox.critical(
                self, "Stop command failed",
                "Sending the 0 RPM stop command to the instrument failed:\n"
                f"{stop_error}\n\n"
                "The spindle may still be rotating at its last commanded speed. "
                "Use the instrument's front panel or power switch to stop it."
            )
        else:
            self.statusBar().showMessage("Manual run stopped" if was_manual else "Run stopped")

    def _tick(self):
        if self.current_step is None or self.run is None or self.instrument is None:
            self.stop_run()
            return

        step = self.current_step
        frac = min(self.step_elapsed / step.duration_s, 1.0) if step.duration_s > 0 else 1.0
        if step.step_type in ("Speed Ramp",):
            target_rpm = step.start_speed_rpm + (step.end_speed_rpm - step.start_speed_rpm) * frac
        else:
            target_rpm = step.start_speed_rpm

        try:
            self.instrument.set_speed(target_rpm)
            rpm, torque_pct, temp_c = self.instrument.read()
        except InstrumentError as exc:
            QMessageBox.critical(self, "Instrument error", str(exc))
            self.stop_run()
            return

        spindle = self.run.method.spindle
        tk = self.run.method.instrument_model.tk
        # DV3T Appendix D: Viscosity(cP) = TK*SMC*100*%Torque/RPM;
        # ShearRate(1/s) = SRC*RPM (0 if spindle has no defined true shear
        # rate); ShearStress(dyne/cm^2) = TK*SMC*SRC*%Torque.
        viscosity_cp = (tk * spindle.smc * 100.0 * torque_pct / rpm) if rpm > 0 else 0.0
        shear_rate = spindle.src * rpm
        shear_stress = tk * spindle.smc * spindle.src * torque_pct

        point = DataPoint(self.run_elapsed, rpm, torque_pct, temp_c, shear_rate, shear_stress, viscosity_cp)
        self.run.points.append(point)
        self._append_row(point)
        self._update_plots()

        self.step_elapsed += step.interval_s
        self.run_elapsed += step.interval_s
        if self.step_elapsed >= step.duration_s:
            self._advance_step()
            if self.current_step is None:
                self.stop_run()
                self.statusBar().showMessage("Run complete")
                return
        self.timer.setInterval(int(max(self.current_step.interval_s, 0.05) * 1000))

    def _append_row(self, p: DataPoint):
        row = self.data_table.rowCount()
        self.data_table.insertRow(row)
        values = [p.t_s, p.rpm, p.torque_pct, p.temp_c, p.shear_rate, p.shear_stress, p.viscosity_cp]
        for col, val in enumerate(values):
            self.data_table.setItem(row, col, QTableWidgetItem(f"{val:.3f}"))
        self.data_table.scrollToBottom()

    def _update_plots(self):
        if not self.run or not self.run.points:
            return
        t = [p.t_s for p in self.run.points]
        rpm = [p.rpm for p in self.run.points]
        temp = [p.temp_c for p in self.run.points]
        gamma = [p.shear_rate for p in self.run.points]
        visc = [p.viscosity_cp for p in self.run.points]

        stress = [p.shear_stress for p in self.run.points]

        self.viscosity_plot.clear()
        self.stress_plot.clear()
        if self.run.method.spindle.src:
            self.viscosity_plot.set_labels("Shear Rate (1/s)", "Viscosity (cP)", "Viscosity vs Shear Rate")
            self.viscosity_plot.plot_xy(gamma, visc, label="Viscosity")
            self.stress_plot.set_labels("Shear Rate (1/s)", "Shear Stress (dyne/cm^2)", "Shear Stress vs Shear Rate")
            self.stress_plot.plot_xy(gamma, stress, label="Shear Stress")
        else:
            # This spindle has no defined true shear rate (SRC == 0, e.g.
            # cylindrical RV/HA/HB spindles), so shear_rate is always 0 and
            # plotting against it would just stack every point at x=0.
            self.viscosity_plot.set_labels("RPM (no true shear rate for this spindle)",
                                            "Viscosity (cP)", "Viscosity vs RPM")
            self.viscosity_plot.plot_xy(rpm, visc, label="Viscosity")
            self.stress_plot.set_labels("RPM (no true shear rate for this spindle)",
                                         "Shear Stress (dyne/cm^2)", "Shear Stress vs RPM")
            self.stress_plot.plot_xy(rpm, stress, label="Shear Stress")
        self.viscosity_time_plot.clear()
        self.viscosity_time_plot.plot_xy(t, visc, label="Viscosity", marker="none", linestyle="-")
        self.temp_plot.clear()
        self.temp_plot.plot_xy(t, temp, label="Temp", marker="none", linestyle="-")

    def open_calibration_dialog(self):
        if self.instrument is None or not self.instrument.is_connected:
            QMessageBox.warning(self, "Not connected", "Connect to an instrument before running a calibration check.")
            return
        if self.timer.isActive():
            QMessageBox.warning(self, "Run in progress", "Stop the current run before running a calibration check.")
            return
        dlg = CalibrationDialog(self.instrument, duration_s=30.0, parent=self)
        dlg.exec()
        if dlg.last_record is not None:
            self.last_calibration_record = dlg.last_record

    def open_temp_calibration_dialog(self):
        if not isinstance(self.instrument, SerialInstrument) or not self.instrument.is_connected:
            QMessageBox.warning(
                self, "Not connected",
                "Connect to a real instrument (not simulated) before calibrating temperature.",
            )
            return
        if self.timer.isActive():
            QMessageBox.warning(self, "Run in progress", "Stop the current run before calibrating temperature.")
            return
        dlg = TempCalibrationDialog(self.instrument, parent=self)
        dlg.exec()
        if dlg.new_zero_counts is not None:
            self.instrument.temp_zero_counts = dlg.new_zero_counts
            self.instrument.temp_counts_per_degree = dlg.new_counts_per_degree
            settings.save_temp_calibration(dlg.new_zero_counts, dlg.new_counts_per_degree)
            self.statusBar().showMessage(
                f"Temperature calibration saved: zero={dlg.new_zero_counts} counts, "
                f"{dlg.new_counts_per_degree:.3f} counts/degC"
            )

    # ----------------------------------------------------------- analysis
    def open_fit_dialog(self):
        if not self.run or not self.run.points:
            QMessageBox.information(self, "No data", "Run a test (or load one) before fitting a model.")
            return
        gamma = np.array([p.shear_rate for p in self.run.points])
        tau = np.array([p.shear_stress for p in self.run.points])
        dlg = FitDialog(gamma, tau, parent=self)
        dlg.exec()
        if dlg.last_result is not None:
            self.last_fit_result = dlg.last_result

    def open_compare_dialog(self):
        dlg = CompareDialog(parent=self)
        dlg.exec()

    def open_temp_fit_dialog(self):
        if not self.run or not self.run.points:
            QMessageBox.information(self, "No data", "Run a test (or load one) before fitting a model.")
            return
        temp = np.array([p.temp_c for p in self.run.points])
        visc = np.array([p.viscosity_cp for p in self.run.points])
        if len(set(np.round(temp, 1))) < 3:
            QMessageBox.information(
                self, "Not enough temperature variation",
                "This run doesn't span enough distinct temperatures to fit a "
                "temperature-dependence model. Use a Temperature Sweep test."
            )
            return
        dlg = TempFitDialog(temp, visc, parent=self)
        dlg.exec()

    # --------------------------------------------------------------- i/o
    def save_run(self):
        if not self.run:
            QMessageBox.information(self, "No run", "There is no run to save yet.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Run", filter="ViscoBridge Run (*.vbr)")
        if path:
            # Qt's native dialog on Linux doesn't auto-append the filter's
            # extension, so a name typed without ".vbr" would otherwise be
            # invisible to *.vbr-filtered Open dialogs elsewhere in the app.
            if not path.lower().endswith(".vbr"):
                path += ".vbr"
            io_utils.save_run(self.run, path)
            self.statusBar().showMessage(f"Saved run to {path}")

    def load_run(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Run", filter="ViscoBridge Run (*.vbr)")
        if not path:
            return
        self.run = io_utils.load_run(path)
        self.data_table.setRowCount(0)
        for plot in (self.viscosity_plot, self.stress_plot, self.viscosity_time_plot, self.temp_plot):
            plot.clear()
        for p in self.run.points:
            self._append_row(p)
        self._update_plots()
        self.statusBar().showMessage(f"Loaded run from {path}")

    def export_csv(self):
        if not self.run:
            QMessageBox.information(self, "No run", "There is no run to export yet.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", filter="CSV Files (*.csv)")
        if path:
            if not path.lower().endswith(".csv"):
                path += ".csv"
            io_utils.export_csv(self.run, path)
            self.statusBar().showMessage(f"Exported CSV to {path}")

    def export_report(self):
        if not self.run:
            QMessageBox.information(self, "No run", "There is no run to report on yet.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Report", filter="HTML Report (*.html)")
        if path:
            if not path.lower().endswith(".html"):
                path += ".html"
            fit_result = self.last_fit_result if self.run.points else None
            report.generate_html_report(self.run, path, fit_result=fit_result)
            self.statusBar().showMessage(f"Exported report to {path}")
