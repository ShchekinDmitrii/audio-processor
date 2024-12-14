#!/usr/bin/env python3

import sys

import numpy as np
import serial
import serial.tools.list_ports
import struct
import gc

from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt5 import uic
from PyQt5.QtCore import QCoreApplication, QTimer, Qt

import pyqtgraph as pg
from pyqtgraph.dockarea import DockArea, Dock
from pyqtgraph import mkPen

import threading
import queue

from scipy.fftpack import fft


def unpack_24bit_audio(byte_array):
    # Ensure the byte array length is a multiple of 3 (since each sample is 3 bytes)
    assert len(byte_array) % 3 == 0, "Byte array length must be a multiple of 3."
    samples = []
    # Iterate through the bytearray 3 bytes at a time
    for i in range(0, len(byte_array), 3):
        # Unpack 3 bytes (little-endian format)
        sample_bytes = byte_array[i:i+3]
        # Unpack the 3 bytes as a signed integer (24 bits stored in a 32-bit integer)
        # We pad the byte with an additional byte (for sign extension) to make it 32-bit
        sample = struct.unpack('<i', sample_bytes + (b'\x00' if sample_bytes[2] < 0x80 else b'\xFF'))[0]
        samples.append(sample)
    return samples

class DSP_Audio(QMainWindow):
    com = None
    connected = False
    ports = []
    baudrate = 115200
    #FFT----------------------
    WaveSize = 1024
    RATE = 44100

    def __init__(self):
        super(DSP_Audio, self).__init__()
        self.ports = list(serial.tools.list_ports.comports())

        self.wave_queue = queue.Queue()

        self.StateTimer = QTimer()
        self.StateTimer.timeout.connect(self.visualize)

        self.initUI()

    def initUI(self):
        self.setCentralWidget(uic.loadUi("mainQWdg.ui"))
        self.centralWidget().setAutoFillBackground(True)
        self.setWindowTitle('Digital Audio Processor')

        for item in self.ports:
            self.centralWidget().COM_ComboBox.addItem(item[0])

        self.centralWidget().ConnectButton.clicked.connect(self.Connect)

        self.statusBar().showMessage("COM ports: "+str([p[0] for p in self.ports]))
        self.statusBar().setStyleSheet("background-color : rgb(66,66,68)")

        self.show()

        penBlue = mkPen(color=(0, 150, 240), width=5)
        penRed = mkPen(color=(240, 40, 50), width=5)
        penViolet = mkPen(color=(170, 40, 255), width=3)
        penCian = mkPen(color=(50, 200, 200), width=3)

        self.Waveform_Display = QMainWindow()
        self.Waveform_Display.setWindowTitle('Waveform visualizer')
        waveform_area = DockArea()
        self.Waveform_Display.setCentralWidget(waveform_area)
        self.Waveform_Display.resize(1900,1000)
        main_dock = Dock("Generated test signal (SIN)",size=(1900,1000))
        main_dock.hideTitleBar()
        waveform_area.addDock(main_dock, 'left')

        self.WaveformPlot = pg.PlotWidget()
        self.WaveformPlot.setTitle("Waveform:", color="w", size="18pt", font="Arial")
        self.WaveformCurve = self.WaveformPlot.plot(pen=penCian)
        main_dock.addWidget(self.WaveformPlot)
        self.SpectralPlot = pg.PlotWidget()
        self.SpectralPlot.setTitle("FFT: ", color="w", size="18pt", font="Arial")
        self.SpectralCurve = self.SpectralPlot.plot(pen=penViolet)
        self.SpectralPlot.setLogMode(x=True, y=True)
        self.SpectralPlot.setXRange(
                    np.log10(40), np.log10(self.RATE / 2))
        self.f = np.linspace(0, self.RATE, self.WaveSize)
        main_dock.addWidget(self.SpectralPlot)

        self.Waveform_Display.show()

    def closeForm(self):
        if self.connected:
            try:
                self.connected = False
                self.StateTimer.stop()
                if self.audio_thread is not None:
                    self.audio_thread.join()
                print("Timers stopped, devices disconnected")
            except:
                print("No device was connected")
        self.close()
        gc.collect()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.closeForm()

    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Message',
            "Are you sure to quit?", QMessageBox.Yes |
            QMessageBox.No, QMessageBox.No)
        if reply==QMessageBox.Yes:
            event.accept()
            QCoreApplication.instance().quit()
        else:
            event.ignore()

    def Connect(self):
        if self.connected==False:
            self.connected = True
            # Start the thread to handle input and playback
            self.audio_thread = threading.Thread(target=self.audio_processing_thread)
            self.audio_thread.start()
            self.StateTimer.start(0)
        else:
            self.connected = False
            self.StateTimer.stop()
            if self.audio_thread is not None:
                self.audio_thread.join()

    def audio_processing_thread(self):
        try:
            self.centralWidget().ConnectButton.setStyleSheet("background-color: rgb(255, 170, 0)")
            self.centralWidget().ConnectButton.repaint()
            device = self.ports[self.centralWidget().COM_ComboBox.currentIndex()]
            com = serial.Serial(str(device[0]),
                        baudrate=self.baudrate,bytesize=serial.EIGHTBITS,parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE,timeout=1000,xonxoff=0)
            self.centralWidget().ConnectButton.setStyleSheet("background-color: rgb(135, 135, 138)")
            self.centralWidget().ConnectButton.repaint()
            self.statusBar().showMessage("CONNECTED: Port "+str(device[0]))

            req = bytearray()
            req.append(np.uint8(0x57)) #request of the next data chunk
            while self.connected:
                com.write(req)
                while (com.inWaiting()<3072):
                    continue
                buff = com.read(3072)
                if (self.wave_queue.qsize()==0):
                    self.wave_queue.put(buff)

            com.close()
            self.centralWidget().ConnectButton.setStyleSheet("background-color: rgb(66, 66, 68)")
            self.centralWidget().ConnectButton.repaint()
            self.statusBar().showMessage("COM ports: "+str([p[0] for p in self.ports]))
        except:
            self.statusBar().showMessage("Please select valid devices")

    def visualize(self):
        try:
            if (self.wave_queue.qsize() > 0):
                audio_bytes = self.wave_queue.get_nowait()
                samples = unpack_24bit_audio(audio_bytes)
                self.WaveformCurve.setData(samples)
                sp_data = fft(samples)
                sp_data = np.abs(sp_data[0:int(self.WaveSize)]
                                ) * 2 / (128 * self.WaveSize)
                self.SpectralCurve.setData(self.f, sp_data)
        except queue.Empty:
            pass  # No data to visualize at the moment

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = DSP_Audio()
    sys.exit(app.exec_())
