#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar  7 02:09:49 2025

@author: krishna
"""


import sys
import subprocess
import shutil
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDockWidget, QLabel, QPushButton,
    QVBoxLayout, QFileDialog, QProgressBar, QMessageBox, QScrollArea,
    QSlider, QHBoxLayout, QComboBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from ccplot.hdf import HDF
from ccplot.utils import calipso_time2dt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ccplot GUI - Beta v1.0")
        self.resize(1980, 1080)

        self.data_file = None
        self.times = []

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        self.setCentralWidget(central_widget)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.plot_label = QLabel("No plot yet")
        self.scroll_area.setWidget(self.plot_label)
        layout.addWidget(self.scroll_area)

        dock = QDockWidget("Controls", self)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        controls = QWidget()
        dock.setWidget(controls)
        v_layout = QVBoxLayout(controls)

        self.open_btn = QPushButton("Open HDF file")
        self.open_btn.clicked.connect(self.open_file)
        v_layout.addWidget(self.open_btn)

        self.start_time_label = QLabel("Start Time: N/A")
        self.end_time_label = QLabel("End Time: N/A")
        v_layout.addWidget(self.start_time_label)
        v_layout.addWidget(self.end_time_label)

        v_layout.addWidget(QLabel("Time Subsetting Sliders"))
        self.start_slider = QSlider(Qt.Horizontal)
        self.end_slider = QSlider(Qt.Horizontal)
        v_layout.addWidget(self.start_slider)
        v_layout.addWidget(self.end_slider)

        # Altitude sliders layout
        alt_layout = QHBoxLayout()
        self.alt_bottom_slider = QSlider(Qt.Horizontal)
        self.alt_top_slider = QSlider(Qt.Horizontal)
        self.alt_bottom_slider.setRange(0, 20000)
        self.alt_top_slider.setRange(5000, 40000)
        self.alt_bottom_slider.setValue(0)
        self.alt_top_slider.setValue(30000)
        alt_layout.addWidget(QLabel("Altitude Bottom"))
        alt_layout.addWidget(self.alt_bottom_slider)
        alt_layout.addWidget(QLabel("Altitude Top"))
        alt_layout.addWidget(self.alt_top_slider)
        v_layout.addLayout(alt_layout)

        # Colormap dropdown
        v_layout.addWidget(QLabel("Colormap:"))
        self.cmap_dropdown = QComboBox()
        cmap_path = "/media/krishna/Linux/tools/ccplot-2.1.4/cmap"
        self.cmaps = [f for f in os.listdir(cmap_path) if f.endswith(".cmap")]
        self.cmap_dropdown.addItems(self.cmaps)
        v_layout.addWidget(self.cmap_dropdown)

        self.plot_btn = QPushButton("Plot Data")
        self.plot_btn.clicked.connect(self.plot_data)
        v_layout.addWidget(self.plot_btn)

        self.progress_bar = QProgressBar()
        v_layout.addWidget(self.progress_bar)

        self.save_btn = QPushButton("Save Plot As...")
        self.save_btn.clicked.connect(self.save_plot)
        v_layout.addWidget(self.save_btn)

        v_layout.addStretch()

        self.status_label = QLabel("Status: Ready")
        v_layout.addWidget(self.status_label)

    def open_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open HDF", "", "HDF Files (*.hdf *.HDF)")
        if not fname:
            return

        self.data_file = fname
        self.times.clear()

        try:
            with HDF(fname) as hdf:
                profile_time = hdf['Profile_UTC_Time'][:, 0]
                self.times = [calipso_time2dt(t) for t in profile_time]

            self.start_time_label.setText(f"Start Time: {self.times[0]}")
            self.end_time_label.setText(f"End Time: {self.times[-1]}")

            self.start_slider.setRange(0, len(self.times)-2)
            self.end_slider.setRange(1, len(self.times)-1)
            self.start_slider.setValue(0)
            self.end_slider.setValue(len(self.times)-1)

            self.status_label.setText("File loaded successfully.")
        except Exception as e:
            QMessageBox.critical(self, "File Error", f"Error opening file:\n{e}")

    def plot_data(self):
        if not self.data_file or not self.times:
            QMessageBox.warning(self, "Warning", "Please load a file first.")
            return

        start_idx = self.start_slider.value()
        end_idx = self.end_slider.value()

        if start_idx >= end_idx:
            QMessageBox.warning(self, "Error", "End time must be after start time.")
            return

        start_time = self.times[start_idx].strftime('%H:%M:%S')
        end_time = self.times[end_idx].strftime('%H:%M:%S')

        alt_bottom = self.alt_bottom_slider.value()
        alt_top = self.alt_top_slider.value()

        cmap_selected = self.cmap_dropdown.currentText()

        cmd = [
            "ccplot", "-o", "calipso_test1.png",
            "-c", f"{os.path.join('/media/krishna/Linux/tools/ccplot-2.1.4/cmap', cmap_selected)}",
            "-a", "30",
            "-x", f"{start_time}..{end_time}",
            "-y", f"{alt_bottom}..{alt_top}",
            "calipso532", self.data_file
        ]

        self.status_label.setText("Plotting...")
        self.progress_bar.setValue(30)

        try:
            subprocess.run(cmd, check=True)
            self.plot_label.setPixmap(QPixmap("calipso_test1.png"))
            self.status_label.setText("Plot successful.")
            self.progress_bar.setValue(100)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Plot failed:\n{e}")
            self.progress_bar.setValue(0)

    def save_plot(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Plot", "", "PNG (*.png)")
        if fname:
            shutil.copy("calipso_test1.png", fname)
            self.status_label.setText(f"Plot saved to: {fname}")

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
