import numpy as np
import matplotlib.pylab as plt

hist = np.array([0,0,0,0,0,0,0,0,0])

def run_FIR(data, coeff):
    global hist
    data_length = len(data)
    data_processed = np.zeros(data_length)
    fir_length = len(coeff)
    fir_length_1 = fir_length - 1
    for i in range(data_length):
        if i < fir_length_1:
            data_temp = 0
            for j in range(fir_length):
                if (i-j<0):
                    data_temp += coeff[j] * hist[j-i-1]
                else:
                    data_temp += coeff[j] * data[i-j]
            data_processed[i] = data_temp
        else:
            data_temp = 0
            for j in range(fir_length):
                data_temp += coeff[j] * data[i-j]
            data_processed[i] = data_temp
    for j in range(fir_length_1):
        hist[j] = data[-j]
    return data_processed

#x = np.linspace(0, 10*np.pi, 100)
#y = np.sin(x)+np.sin(3*x)+np.sin(15*x)+np.sin(-5*x)
#w = np.sin(x)+np.sin(3*x)
x = [100, 200, 400, 800, 1600, 2000, 2500, 3000, 3200, 3500, 4000, 4500, 5000, 5500, 6000, 6400, 12800]
y = [1, 1, 0.991, 0.98, 0.9823, 1, 0.8497, 0.7923, 0.7647, 0.7196, 0.6524, 0.5806, 0.5034, 0.4298, 0.3548, 0.2986, 0.0225]

x_2 = [100, 200, 400, 800, 1600, 2000, 2500, 3000, 3200, 3500, 4000, 4500, 4750, 5000, 5250, 5500, 6000, 6400, 12800]
y_2 = [0.048, 0.1037, 0.2079, 0.42, 0.812, 0.9868, 1.183, 1.3538, 1.4034, 1.4811, 1.5674, 1.6258, 1.6293, 1.3793, 1.6438, 1.6316, 1.5887, 1.5347, 0.6126]
#coeff= np.array([0,2,4,6,8,6,4,2,0,0])

#z = run_FIR(y,coeff)

plt.figure()
plt.subplot(1,2,1)
plt.title("Low-pass filter")
plt.plot(x, np.log10(y), color='b')
plt.ylabel("Gain, dB")
plt.xlabel("Frequency, Hz")
plt.grid()
plt.subplot(1,2,2)
plt.title("High-pass filter")
plt.plot(x_2, np.log10(y_2)-0.2, color='r')
plt.grid()
plt.xlabel("Frequency, Hz")
plt.show()

