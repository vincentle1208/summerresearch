import os
import glob
import time
import sys
import signal
import RPi.GPIO as GPIO
from multiprocessing import Pool

os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')

# Folder directory definitions
BASE_DIR = '/sys/bus/w1/devices/'
DEVICE_FOLDER = ['1', '1', '1']
FILE_OPENED = ['1', '1', '1']

SENSOR_COUNT = 0
SENSORS = ['1', '1', '1']
for name in glob.glob(BASE_DIR + '28*'):
    DEVICE_FOLDER[SENSOR_COUNT] = name + '/w1_slave'
    SENSORS[SENSOR_COUNT] = DEVICE_FOLDER[SENSOR_COUNT].split('00000')[1].split('/')[0]
    SENSOR_COUNT += 1
print('Available sensors: {0} {1} {2}'. format(SENSORS[0], SENSORS[1], SENSORS[2]))

# LED PINs
LED = 2

#GPIO Setup
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(LED, GPIO.OUT)

#Initilise LEDs
GPIO.output(LED, 0)

def read_temp_raw(sensor):
    f = open(sensor, 'r')
    lines = f.readlines()
    f.close()
    return lines

def read_temp(sensor, speed):
    lines = read_temp_raw(sensor)
    equals_pos = lines[1].find('t=')
    
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
    time.sleep(int(speed))
    return temp_c

def set_sampling_time():
    samplingTimes = [1, 1, 1]
    print('Time for sampling should be set in scaled of seconds')
    print(16*'*')
    for i in range(3):
        samplingTimes[i] = input('Sampling time for sensor {0} :   '.format(SENSORS[i]))
    print(16*'*')
    return samplingTimes

def live_sampling(sensor, speed, fileWrite) :
    data = read_temp(sensor, speed)
    fileWrite.write('{0}\n'.format(data))
    return data
    
def main():
    sensorSamplingRate = set_sampling_time()
    print(sensorSamplingRate)
    
    filesWrite = [1, 1, 1]
    for i in range(3):
        filesWrite[i] = open('{0}.txt'.format(SENSORS[i]), 'w')
        filesWrite[i].write('File created for sensor {0}\n'.format(SENSORS[i]))
        
    try:
            
        while True:
            for i in range(3):
                temp = live_sampling(DEVICE_FOLDER[i], sensorSamplingRate[i], filesWrite[i])
                print('Sensor {0} is {1}'.format(SENSORS[i], temp))
        
    except (KeyboardInterrupt, Exception) as e:
        print(e)
        GPIO.cleanup()
        for i in range(3):
            filesWrite[i].close()
        print("Program successfully terminated")

if __name__ == '__main__':
    main()