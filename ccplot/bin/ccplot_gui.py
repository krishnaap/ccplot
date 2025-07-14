#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple GUI for ccplot using PyQt5.

This application wraps the command-line `ccplot` tool with a basic
interface for selecting an input HDF file and plotting a subset of the
profiles.  It is based on a user contributed script.

The GUI depends on PyQt5 which is not installed by default when
installing ccplot.  Install ``PyQt5`` separately to use the GUI.
"""

import sys
import subprocess
import shutil
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QWidget, QVBoxLayout,
    QLabel, QPushButton, QSpinBox, QFileDialog, QProgressBar,
    QScrollArea, QMessageBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

from ccplot.hdf import HDF
from ccplot.hdfeos import HDFEOS
from ccplot.utils import calipso_time2dt, cloudsat_time2dt


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ccplot GUI")
        self.resize(1200, 800)

        self.data_file = None
        self.current_plot_path = "ccplot_gui_plot.png"
        self.times = []

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        layout.addWidget(self.scroll_area)

        self.plot_label = QLabel("No plot yet")
        self.scroll_area.setWidget(self.plot_label)
        self.setCentralWidget(central_widget)

        dock = QDockWidget("Controls", self)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        controls = QWidget()
        vbox = QVBoxLayout(controls)

        self.open_btn = QPushButton("Open HDF File")
        self.open_btn.clicked.connect(self.open_file)
        vbox.addWidget(self.open_btn)

        self.start_time_label = QLabel("Start Time: N/A")
        self.end_time_label = QLabel("End Time: N/A")
        vbox.addWidget(self.start_time_label)
        vbox.addWidget(self.end_time_label)

        self.slider_label = QLabel("Subset Time (profiles):")
        vbox.addWidget(self.slider_label)

        self.slider_start = QSpinBox()
        self.slider_end = QSpinBox()
        vbox.addWidget(QLabel("Start Profile"))
        vbox.addWidget(self.slider_start)
        vbox.addWidget(QLabel("End Profile"))
        vbox.addWidget(self.slider_end)

        self.alt_spin = QSpinBox()
        self.alt_spin.setRange(1000, 40000)
        self.alt_spin.setValue(30000)
        self.alt_spin.setPrefix("Altitude max: ")
        vbox.addWidget(self.alt_spin)

        self.plot_btn = QPushButton("Plot Data")
        self.plot_btn.clicked.connect(self.plot_data)
        vbox.addWidget(self.plot_btn)

        self.progress_bar = QProgressBar()
        vbox.addWidget(self.progress_bar)

        self.save_btn = QPushButton("Save Plot As...")
        self.save_btn.clicked.connect(self.save_plot)
        vbox.addWidget(self.save_btn)

        self.status_label = QLabel("Status: Ready")
        vbox.addWidget(self.status_label)

        dock.setWidget(controls)

    def open_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open HDF", "", "HDF files (*.hdf *.HDF)")
        if not fname:
            return

        self.data_file = fname
        self.times = []

        try:
            if "CAL_LID" in fname:
                with HDF(fname) as f:
                    tvals = f['Profile_UTC_Time'][:, 0]
                    self.times = [calipso_time2dt(t) for t in tvals]
            elif "2B-GEOPROF" in fname:
                with HDFEOS(fname) as f:
                    swath = f['2B-GEOPROF']
                    start_time_str = swath.attributes['start_time']
                    start_dt = datetime.strptime(start_time_str, '%Y%m%d%H%M%S')
                    tvals = swath['Profile_time'][:]
                    self.times = [cloudsat_time2dt(t, start_dt) for t in tvals]
            else:
                raise ValueError("Unsupported file type")

            self.start_time_label.setText(f"Start Time: {self.times[0]}")
            self.end_time_label.setText(f"End Time: {self.times[-1]}")

            n_profiles = len(self.times)
            self.slider_start.setRange(0, n_profiles - 2)
            self.slider_end.setRange(1, n_profiles - 1)
            self.slider_end.setValue(n_profiles - 1)

            self.status_label.setText("File loaded successfully.")

        except Exception as exc:
            QMessageBox.critical(self, "File Error", f"Error reading HDF file:\n{exc}")
            self.status_label.setText(f"Error: {exc}")

    def plot_data(self):
        if not self.data_file or not self.times:
            QMessageBox.warning(self, "Error", "Load an HDF file first.")
            return

        start_idx = self.slider_start.value()
        end_idx = self.slider_end.value()
        if start_idx >= end_idx:
            QMessageBox.warning(self, "Invalid Selection", "End profile must be greater than start profile.")
            return

        self.progress_bar.setValue(10)

        start_time = self.times[start_idx].strftime('%H:%M:%S')
        end_time = self.times[end_idx].strftime('%H:%M:%S')
        y_max = self.alt_spin.value()

        cmd = [
            "ccplot",
            "-o", self.current_plot_path,
            "-c", "calipso-backscatter.cmap",
            "-a", "30",
            "-x", f"{start_time}..{end_time}",
            "-y", f"0..{y_max}",
            "calipso532",
            self.data_file,
        ]

        self.status_label.setText("Running ccplot…")
        self.progress_bar.setValue(50)

        try:
            subprocess.run(cmd, check=True)
            pix = QPixmap(self.current_plot_path)
            self.plot_label.setPixmap(pix)
            self.status_label.setText("Plot generated successfully.")
            self.progress_bar.setValue(100)
        except subprocess.CalledProcessError as exc:
            QMessageBox.critical(self, "Plot Error", f"Error running ccplot:\n{exc}")
            self.status_label.setText("Plot error.")
            self.progress_bar.setValue(0)

    def save_plot(self):
        if not self.current_plot_path:
            QMessageBox.warning(self, "No plot", "Plot first before saving.")
            return

        fname, _ = QFileDialog.getSaveFileName(self, "Save plot as", "", "PNG (*.png);;All files (*)")
        if fname:
            shutil.copy(self.current_plot_path, fname)
            self.status_label.setText(f"Saved plot to {fname}")


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
