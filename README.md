# Audio_Processor

Two ways of implementing digital audio processor:

# SW Audio processor

Relies on built-in soundcard and the PyAudio package. It allows to read the bytstream from the computer's soundcard, process it and write it back.
The stream continuity is not guaranteed and can be heavily dependant on the computer's workload. A good compromise between sound quality and the
waveform visualization capabilities has been achieved.

Folder contents:

- "Audio_Processor.py" - main Python script to run the program at the PC side

- "mainQWdg.ui" - widget template for the main window

- "DSP_Diagram.png" - to be replaced with the diagram that shows the working principle
