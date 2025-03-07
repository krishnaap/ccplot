#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar  7 02:09:49 2025

@author: krishna
"""

#!/usr/bin/env python3
"""
GUI Code v5
-----------
1) Uses a fixed window size of 1980x1080 (not resizable at the window level).
2) Replaces the main layout with a QSplitter, so the left panel is resizable horizontally
   relative to the right panel.
3) Uses setScaledContents(True) on the plot label so the image fits the given space.
4) Hard-coded colormap path: /media/krishna/Linux/tools/ccplot-2.1.4/cmap/calipso-backscatter.cmap
"""

import sys
import re
import subprocess
import shutil
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QFileDialog, QLabel, QPushButton,
    QVBoxLayout, QTimeEdit, QSpinBox,
    QScrollArea, QSplitter, QSizePolicy
)
from PyQt5.QtCore import QTime, Qt
from PyQt5.QtGui import QPixmap


def parse_filename_datetime(fname):
    """
    Parse date/time from typical CAL_LID or CloudSat filenames.
    Example: 'CAL_LID_L1-ValStage1-V3-01.2007-06-12T03-42-18ZN.hdf'
    Returns (start_dt, end_dt) or (None, None) if unknown.
    """
    # 1) For CAL_LID_... e.g. 'CAL_LID_L1-ValStage1-V3-01.2007-06-12T03-42-18ZN.hdf'
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

    # 2) CloudSat style: e.g. 2006224184641_01550_CS_2B-GEOPROF...
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ccplot GUI - v5")

        # Fix the outer window to 1980×1080
        self.setFixedSize(1980, 1080)

        self.data_file = None
        self.start_dt = None
        self.end_dt = None
        self.current_plot_path = None

        # Main container: use a splitter horizontally
        splitter = QSplitter(Qt.Horizontal, self)
        self.setCentralWidget(splitter)

        # LEFT: scroll area with controls
        left_container = QScrollArea()
        left_container.setWidgetResizable(True)
        splitter.addWidget(left_container)

        # Widget inside scroll area
        controls_widget = QWidget()
        left_container.setWidget(controls_widget)

        v_layout = QVBoxLayout(controls_widget)

        # Info label
        self.info_label = QLabel("File info will appear here.")
        v_layout.addWidget(self.info_label)

        # Open button
        self.open_btn = QPushButton("Open HDF File")
        self.open_btn.clicked.connect(self.open_file)
        v_layout.addWidget(self.open_btn)

        # Time edits
        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setDisplayFormat("HH:mm:ss")
        self.start_time_edit.setTime(QTime(0, 0, 0))
        v_layout.addWidget(self.start_time_edit)

        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setDisplayFormat("HH:mm:ss")
        self.end_time_edit.setTime(QTime(0, 0, 0))
        v_layout.addWidget(self.end_time_edit)

        # Alt spin
        self.alt_spin = QSpinBox()
        self.alt_spin.setRange(1, 40000)
        self.alt_spin.setValue(30000)
        self.alt_spin.setPrefix("Altitude max: ")
        v_layout.addWidget(self.alt_spin)

        # Plot button
        self.plot_btn = QPushButton("Plot Data")
        self.plot_btn.clicked.connect(self.plot_data)
        v_layout.addWidget(self.plot_btn)

        # Save button
        self.save_btn = QPushButton("Save Plot As...")
        self.save_btn.clicked.connect(self.save_plot)
        v_layout.addWidget(self.save_btn)

        # Spacer
        v_layout.addStretch()

        # RIGHT: label to show the plot
        self.plot_label = QLabel("No plot yet")
        self.plot_label.setStyleSheet("background-color: #efefef;")
        # Make sure it expands to fill space but scale image
        self.plot_label.setScaledContents(True)
        self.plot_label.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )
        splitter.addWidget(self.plot_label)

        # Adjust splitter so left panel is smaller, right bigger
        splitter.setStretchFactor(0, 0)  # left
        splitter.setStretchFactor(1, 1)  # right

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
                    f"Loaded file:\n{fname}\n\n"
                    f"Parsed start time: {start_dt}\nParsed end time:   {end_dt}"
                )
                self.start_time_edit.setTime(
                    QTime(start_dt.hour, start_dt.minute, start_dt.second)
                )
                self.end_time_edit.setTime(
                    QTime(end_dt.hour, end_dt.minute, end_dt.second)
                )
            else:
                info_text = (
                    f"Loaded file:\n{fname}\n\n"
                    "Date/time not parsed."
                )
            self.info_label.setText(info_text)
            self.plot_label.setText("File loaded: " + fname)

    def plot_data(self):
        if not self.data_file:
            self.info_label.setText("No file loaded. Open a file first.")
            return

        cmd = ["ccplot"]

        # Output file
        self.current_plot_path = "calipso_test1.png"
        cmd += ["-o", self.current_plot_path]

        # Hard-coded colormap path
        cmd += ["-c", "/media/krishna/Linux/tools/ccplot-2.1.4/cmap/calipso-backscatter.cmap"]

        # Alpha
        cmd += ["-a", "30"]

        # Time subset
        start_t = self.start_time_edit.time()
        end_t = self.end_time_edit.time()
        st_str = start_t.toString("H:mm:ss")
        en_str = end_t.toString("H:mm:ss")
        cmd += ["-x", f"{st_str}..{en_str}"]

        # Vertical range
        max_alt = self.alt_spin.value()
        cmd += ["-y", f"0..{max_alt}"]

        # For demonstration, assume calipso532
        ccplot_product = "calipso532"
        cmd += [ccplot_product, self.data_file]

        self.info_label.setText("Running: " + " ".join(cmd))
        try:
            proc = subprocess.run(cmd, capture_output=True)
            if proc.returncode != 0:
                err_str = proc.stderr.decode()
                self.info_label.setText(f"ccplot error:\n{err_str}")
                return

            # If success, show the image scaled in the label
            pix = QPixmap(self.current_plot_path)
            self.plot_label.setPixmap(pix)
            self.info_label.setText("Plot generated successfully.")

        except Exception as e:
            self.info_label.setText(f"Exception: {str(e)}")

    def save_plot(self):
        if not self.current_plot_path:
            self.info_label.setText("No plot to save. Generate a plot first.")
            return

        out_name, _ = QFileDialog.getSaveFileName(
            self, "Save Plot As", "",
            "PNG Images (*.png);;All Files (*)"
        )
        if out_name:
            try:
                shutil.copy(self.current_plot_path, out_name)
                self.info_label.setText(f"Plot saved to: {out_name}")
            except Exception as e:
                self.info_label.setText(f"Save error: {e}")


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
