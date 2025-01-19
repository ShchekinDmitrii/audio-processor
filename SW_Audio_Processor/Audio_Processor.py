import sys
import pyaudio
import numpy as np
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QApplication
from PyQt5 import uic
import pyqtgraph as pg
from pyqtgraph import mkPen
from pyqtgraph.Qt import QtCore, QtGui
import threading
import queue
import struct
from scipy.fftpack import fft

class AudioVisualizer(QMainWindow):
    SILENCE = chr(0)
    active_FIR = True
    coeff_FIR = np.array([0, 2, 4, 6, 8, 6, 4, 2, 0, 0], dtype=np.int16)
    hist_FIR = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.int16)
    def __init__(self):
        super().__init__()

        # Initialize PyAudio
        self.p = pyaudio.PyAudio()

        # Stream parameters
        self.CHUNK = 512
        self.FRAME = 1024 * 2
        self.NUM_CHUNKS = self.FRAME // self.CHUNK
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 44100

        # Queue for sharing audio data between threads
        self.audio_queue = queue.Queue()

        # Stream placeholders (will be set on start)
        self.input_stream = None
        self.output_stream = None
        self.audio_thread = None
        self.audio_active = False
        self.visualization = True

        # Timer for real-time visualization
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_visualization)

        # Set up UI
        self.init_ui()

    def init_ui(self):
        # Set up main window layout
        self.setWindowTitle('Software Audio Processor')

        self.setCentralWidget(uic.loadUi("./SW_Audio_Processor/mainQWdg.ui"))
        self.centralWidget().StartAudioButton.clicked.connect(self.start_audio)
        self.centralWidget().StopAudioButton.clicked.connect(self.stop_audio)
        self.centralWidget().checkBoxVisualize.clicked.connect(self.switchVisualizationMode)
        self.centralWidget().checkBox_FIR.clicked.connect(self.toggleFIR)

        penViolet = mkPen(color=(170, 40, 255), width=3)
        penCian = mkPen(color=(50, 200, 200), width=3)

        # Set up the PyQtGraph plotting window for audio visualization
        self.win_wave = pg.GraphicsLayoutWidget(title="Real-Time Audio Waveform")
        self.plot = self.win_wave.addPlot(title="Waveform")
        self.curve = self.plot.plot(pen=penCian)
        #self.plot.setYRange(-32768, 32768)  # Set Y-axis range for 16-bit PCM
        self.plot.setXRange(0, self.FRAME)
        self.win_fft = pg.GraphicsLayoutWidget(title="Real-Time Audio Spectrum")
        self.plotFFT = self.win_fft.addPlot(title="FFT")
        self.curveFFT = self.plotFFT.plot(pen=penViolet)
        self.plotFFT.setLogMode(x=True, y=False)
        self.plotFFT.setXRange(
                    np.log10(20), np.log10(self.RATE / 2))

        self.f = np.linspace(0, self.RATE, self.FRAME)

        layout = QVBoxLayout()
        layout.addWidget(self.win_wave)  # Add the graph to the layout
        layout.addWidget(self.win_fft)  # Add the graph to the layout

        self.centralWidget().groupVisualizer.setLayout(layout)

    def start_audio(self):
        """Start the audio streams, processing, and visualization."""
        self.audio_active = True
        # Start the thread to handle input and playback
        self.audio_thread = threading.Thread(target=self.audio_processing_thread)
        self.audio_thread.start()

        # Start the timer to update the plot (visualization only)
        if self.visualization == True:
            self.timer.start(0)  # Update as quickly as possible

    def stop_audio(self):
        """Stop the audio streams and visualization."""
        # Stop the visualization timer
        self.timer.stop()

        # Signal the audio thread to stop
        self.audio_active = False
        if self.audio_thread is not None:
            self.audio_thread.join()

    def update_visualization(self):
        """Update the plot with the latest audio data from the queue."""
        try:
            # Get the latest audio data from the queue for visualization
            if self.audio_queue.qsize() >= self.NUM_CHUNKS:
                audio_data = self.audio_queue.get_nowait()
                for ch in range(0,self.NUM_CHUNKS-1):
                    audio_data += self.audio_queue.get_nowait()
                # Convert the binary data into NumPy array for visualization
                #audio_data_np = np.frombuffer(audio_data, dtype=np.int16)
                #
                #audio_data_np = audio_data
                audio_data_np = struct.unpack(str(self.FRAME) + 'h', audio_data)
                # Update the waveform plot
                self.curve.setData(audio_data_np)
                sp_data = fft(audio_data_np)
                sp_data = np.abs(sp_data[0:int(self.FRAME)]
                                ) * 2 / (128 * self.FRAME)
                self.curveFFT.setData(self.f, sp_data)
        except queue.Empty:
            pass  # No data to visualize at the moment

    def audio_processing_thread(self):
        """Handle audio input, playback, and data sharing in a separate thread."""
        # Open input audio stream
        self.input_stream = self.p.open(format=self.FORMAT,
                                        channels=self.CHANNELS,
                                        rate=self.RATE,
                                        input=True,
                                        frames_per_buffer=self.CHUNK)

        # Open output audio stream
        self.output_stream = self.p.open(format=self.FORMAT,
                                         channels=self.CHANNELS,
                                         rate=self.RATE,
                                         output=True,
                                         frames_per_buffer=self.CHUNK)

        # Audio processing loop that runs in a separate thread
        while self.audio_active:
            # Read audio data from the input stream
            data = self.input_stream.read(self.CHUNK)

            if self.active_FIR:
                data_processed = self.run_FIR(data, self.coeff_FIR)
            else:
                data_processed = data

            # Send the audio data to the visualization queue
            if self.visualization == True:
                self.audio_queue.put(data_processed)

            # Play back the audio data
            try:
                self.output_stream.write(data_processed)
                free = self.output_stream.get_write_available() # How much space is left in the buffer?
                if free > self.CHUNK: # Is there a lot of space in the buffer?
                    tofill = free - self.CHUNK
                    self.output_stream.write(self.SILENCE * tofill) # Fill it with silence
            except pyaudio.paOutputUnderflow:
                free = self.output_stream.get_write_available() # How much space is left in the buffer?
                if free > self.CHUNK: # Is there a lot of space in the buffer?
                    tofill = free - self.CHUNK
                    self.output_stream.write(self.SILENCE * tofill) # Fill it with silence

        # Close the input and output streams when done
        self.input_stream.stop_stream()
        self.input_stream.close()
        self.output_stream.stop_stream()
        self.output_stream.close()

    def switchVisualizationMode(self):
        if (self.centralWidget().checkBoxVisualize.isChecked()):
            if self.visualization == False:
                self.visualization = True
                self.timer.start(0)
        else:
            if self.visualization == True:
                self.visualization = False
                self.timer.stop()
    
    def toggleFIR(self):
        if (self.centralWidget().checkBox_FIR.isChecked()):
            self.active_FIR = True
            print(self.active_FIR)
        else:
            self.active_FIR = False
            print(self.active_FIR)

    def closeEvent(self, event):
        """Handle application close event and stop audio properly."""
        self.stop_audio()
        self.p.terminate()
        event.accept()

    def run_FIR(self, data, coeff):
        data_array = np.array(struct.unpack(str(self.CHUNK) + 'h', data), np.int16)
        data_length = len(data_array)
        data_processed = np.zeros(data_length,dtype=np.int16)
        fir_length = len(coeff)
        fir_length_1 = fir_length - 1
        for i in range(data_length):
            if i < fir_length_1:
                data_temp = np.int32(0)
                for j in range(fir_length):
                    if (i-j<0):
                        data_temp += coeff[j] * np.int32(self.hist_FIR[j-i-1])
                    else:
                        data_temp += coeff[j] * np.int32(data_array[i-j])
                data_processed[i] = np.int16(data_temp >> 5)
            else:
                data_temp = np.int32(0)
                for j in range(fir_length):
                    data_temp += coeff[j] * np.int32(data_array[i-j])
                data_processed[i] = np.int16(data_temp >> 5)
        for j in range(fir_length_1):
            self.hist_FIR[j] = data_array[-j]
        return struct.pack(str(self.CHUNK) + 'h', *data_processed)

# Start the PyQt application
if __name__ == '__main__':
    app = QApplication(sys.argv)
    visualizer = AudioVisualizer()
    visualizer.show()
    sys.exit(app.exec_())
