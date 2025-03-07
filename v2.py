#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar  7 02:09:49 2025

@author: krishna
"""

import sys
import re
import subprocess
import shutil
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QWidget, QLabel,
    QPushButton, QTimeEdit, QSpinBox, QVBoxLayout, QFileDialog
)
from PyQt5.QtCore import QTime, Qt
from PyQt5.QtGui import QPixmap, QResizeEvent


def parse_filename_datetime(fname):
    """
    Parse date/time from typical CAL_LID or CloudSat filenames.
    Example: 'CAL_LID_L1-ValStage1-V3-01.2007-06-12T03-42-18ZN.hdf'
    Returns (start_dt, end_dt) or (None, None).
    """
    # 1) CAL_LID pattern
    cal_match = re.match(
        r'^CAL_LID_.*(\d{4})-(\d{2})-(\d{2})T(\d{2})-(\d{2})-(\d{2})Z.*\.hdf$',
        fname
    )
    if cal_match:
        y = int(cal_match.group(1))
        m = int(cal_match.group(2))
        d = int(cal_match.group(3))
        hh = int(cal_match.group(4))
        mm = int(cal_match.group(5))
        ss = int(cal_match.group(6))
        start_dt = datetime(y, m, d, hh, mm, ss)
        end_dt = start_dt + timedelta(minutes=5)  # guess
        return (start_dt, end_dt)

    # 2) CloudSat style: 2006224184641_01550_CS_2B-GEOPROF...
    cs_match = re.match(r'^(\d{7})(\d{6})_.*CS_2B-.*\.hdf$', fname)
    if cs_match:
        yyddd = cs_match.group(1)
        hhmmss = cs_match.group(2)
        year = int(yyddd[:4])
        day_of_year = int(yyddd[4:])
        hour = int(hhmmss[:2])
        minute = int(hhmmss[2:4])
        second = int(hhmmss[4:6])
        start_dt = datetime(year, 1, 1) + timedelta(
            days=day_of_year - 1, hours=hour, minutes=minute, seconds=second
        )
        end_dt = start_dt + timedelta(minutes=2)
        return (start_dt, end_dt)

    return (None, None)


class PlotLabel(QLabel):
    """
    Custom QLabel that stores the original pixmap and scales it
    to fit the available size while keeping the aspect ratio.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._original_pixmap = None
        # We'll not use setScaledContents(True) because we want
        # better control over aspect ratio scaling.

        # Optional styling
        self.setStyleSheet("background-color: #efefef;")

    def setPixmap(self, pix: QPixmap):
        """Store the original pixmap and update scaling."""
        self._original_pixmap = pix
        self.updateScaledPixmap()

    def resizeEvent(self, event: QResizeEvent):
        """On every resize, rescale the stored pixmap."""
        super().resizeEvent(event)
        self.updateScaledPixmap()

    def updateScaledPixmap(self):
        """Scale the original pixmap to current label size, keeping aspect ratio."""
        if self._original_pixmap and not self._original_pixmap.isNull():
            scaled = self._original_pixmap.scaled(
                self.size(), 
                Qt.KeepAspectRatio, 
                transformMode=Qt.SmoothTransformation
            )
            super().setPixmap(scaled)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ccplot GUI - v7")

        # Initially 1980x1080. The user can resize as well.
        self.resize(1980, 1080)

        # Data and plotting info
        self.data_file = None
        self.start_dt = None
        self.end_dt = None
        self.current_plot_path = None

        # Central widget: custom PlotLabel
        self.plot_label = PlotLabel()
        self.plot_label.setText("No plot yet")
        self.setCentralWidget(self.plot_label)

        # Create a dock widget for the side panel
        dock = QDockWidget("Controls", self)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        # side_panel is a normal widget with a layout
        side_panel = QWidget()
        dock.setWidget(side_panel)
        layout = QVBoxLayout(side_panel)

        # Controls
        self.open_btn = QPushButton("Open HDF File")
        self.open_btn.clicked.connect(self.open_file)
        layout.addWidget(self.open_btn)

        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setDisplayFormat("HH:mm:ss")
        self.start_time_edit.setTime(QTime(0,0,0))
        layout.addWidget(self.start_time_edit)

        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setDisplayFormat("HH:mm:ss")
        self.end_time_edit.setTime(QTime(0,0,0))
        layout.addWidget(self.end_time_edit)

        self.alt_spin = QSpinBox()
        self.alt_spin.setRange(1, 40000)
        self.alt_spin.setValue(30000)
        self.alt_spin.setPrefix("Altitude max: ")
        layout.addWidget(self.alt_spin)

        self.plot_btn = QPushButton("Plot Data")
        self.plot_btn.clicked.connect(self.plot_data)
        layout.addWidget(self.plot_btn)

        self.save_btn = QPushButton("Save Plot As...")
        self.save_btn.clicked.connect(self.save_plot)
        layout.addWidget(self.save_btn)

        layout.addStretch()

        # Status label
        self.status_label = QLabel("Status: Ready")
        layout.addWidget(self.status_label)

    def open_file(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, "Open CloudSat/CALIPSO File", "",
            "HDF Files (*.hdf *.HDF)"
        )
        if fname:
            self.data_file = fname
            basename = fname.split('/')[-1]
            start_dt, end_dt = parse_filename_datetime(basename)
            self.start_dt = start_dt
            self.end_dt = end_dt

            if start_dt and end_dt:
                info_text = (
                    f"Loaded file:\n{fname}\n"
                    f"Parsed start time: {start_dt}\n"
                    f"Parsed end time:   {end_dt}"
                )
                self.start_time_edit.setTime(QTime(start_dt.hour, start_dt.minute, start_dt.second))
                self.end_time_edit.setTime(QTime(end_dt.hour, end_dt.minute, end_dt.second))
            else:
                info_text = f"Loaded file:\n{fname}\n(No parseable date/time)"

            self.plot_label.setText("File loaded: " + fname)
            self.status_label.setText(info_text)

    def plot_data(self):
        if not self.data_file:
            self.status_label.setText("No file loaded. Open a file first.")
            return

        cmd = ["ccplot"]
        self.current_plot_path = "calipso_test1.png"
        cmd += ["-o", self.current_plot_path]

        # Hard-coded colormap path
        cmd += ["-c", "/media/krishna/Linux/tools/ccplot-2.1.4/cmap/calipso-backscatter.cmap"]

        # Alpha
        cmd += ["-a", "30"]

        # Time subset
        st = self.start_time_edit.time()
        en = self.end_time_edit.time()
        st_str = st.toString("H:mm:ss")
        en_str = en.toString("H:mm:ss")
        cmd += ["-x", f"{st_str}..{en_str}"]

        # Altitude
        max_alt = self.alt_spin.value()
        cmd += ["-y", f"0..{max_alt}"]

        # Assume calipso532
        cmd += ["calipso532", self.data_file]

        self.status_label.setText("Running: " + " ".join(cmd))

        try:
            proc = subprocess.run(cmd, capture_output=True)
            if proc.returncode != 0:
                err_str = proc.stderr.decode()
                self.status_label.setText(f"ccplot error:\n{err_str}")
                return

            # If success, load the pixmap into self.plot_label
            pix = QPixmap(self.current_plot_path)
            self.plot_label.setPixmap(pix)  # will auto-scale via updateScaledPixmap()
            self.status_label.setText("Plot generated successfully.")
        except Exception as e:
            self.status_label.setText(f"Exception: {str(e)}")

    def save_plot(self):
        if not self.current_plot_path:
            self.status_label.setText("No plot to save. Generate a plot first.")
            return

        out_name, _ = QFileDialog.getSaveFileName(
            self, "Save Plot As", "",
            "PNG Images (*.png);;All Files (*)"
        )
        if out_name:
            try:
                shutil.copy(self.current_plot_path, out_name)
                self.status_label.setText(f"Plot saved to: {out_name}")
            except Exception as e:
                self.status_label.setText(f"Save error: {e}")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
