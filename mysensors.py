'''
/*
 * Copyright 2010-2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License").
 * You may not use this file except in compliance with the License.
 * A copy of the License is located at
 *
 *  http://aws.amazon.com/apache2.0
 *
 * or in the "license" file accompanying this file. This file is distributed
 * on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
 * express or implied. See the License for the specific language governing
 * permissions and limitations under the License.
 */
 '''

from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import logging
import time
import argparse

import os
import glob
import time
import sys
import signal
import RPi.GPIO as GPIO

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
##    time.sleep(int(speed))
    return temp_c

def set_sampling_time():
    print('Time for sampling should be set in scaled of seconds')
    print(16*'*')
    samplingTimes = input('Sampling time for Temperature sensors :   ')
    print(16*'*')
    return samplingTimes

def live_sampling(sensor, speed, fileWrite) :
    data = read_temp(sensor, speed)
    #fileWrite.write('{0}\n'.format(data))
    return data
####################################################

# Custom MQTT message callback
def customCallback(client, userdata, message):
    print("Received a new message: ")
    print(message.payload)
    print("from topic: ")
    print(message.topic)
    print("--------------\n\n")


# Read in command-line parameters
parser = argparse.ArgumentParser()
parser.add_argument("-e", "--endpoint", action="store", required=True, dest="host", help="Your AWS IoT custom endpoint")
parser.add_argument("-r", "--rootCA", action="store", required=True, dest="rootCAPath", help="Root CA file path")
parser.add_argument("-c", "--cert", action="store", dest="certificatePath", help="Certificate file path")
parser.add_argument("-k", "--key", action="store", dest="privateKeyPath", help="Private key file path")
parser.add_argument("-w", "--websocket", action="store_true", dest="useWebsocket", default=False,
                    help="Use MQTT over WebSocket")
parser.add_argument("-id", "--clientId", action="store", dest="clientId", default="basicPubSub",
                    help="Targeted client id")
parser.add_argument("-t", "--topic", action="store", dest="topic", default="sdk/test/Python", help="Targeted topic")

args = parser.parse_args()
host = args.host
rootCAPath = args.rootCAPath
certificatePath = args.certificatePath
privateKeyPath = args.privateKeyPath
useWebsocket = args.useWebsocket
clientId = args.clientId
topic = args.topic

if args.useWebsocket and args.certificatePath and args.privateKeyPath:
    parser.error("X.509 cert authentication and WebSocket are mutual exclusive. Please pick one.")
    exit(2)

if not args.useWebsocket and (not args.certificatePath or not args.privateKeyPath):
    parser.error("Missing credentials for authentication.")
    exit(2)

# Configure logging
logger = logging.getLogger("AWSIoTPythonSDK.core")
logger.setLevel(logging.DEBUG)
streamHandler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

# Init AWSIoTMQTTClient
myAWSIoTMQTTClient = None
if useWebsocket:
    myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId, useWebsocket=True)
    myAWSIoTMQTTClient.configureEndpoint(host, 443)
    myAWSIoTMQTTClient.configureCredentials(rootCAPath)
else:
    myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId)
    myAWSIoTMQTTClient.configureEndpoint(host, 8883)
    myAWSIoTMQTTClient.configureCredentials(rootCAPath, privateKeyPath, certificatePath)

# AWSIoTMQTTClient connection configuration
myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
myAWSIoTMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
myAWSIoTMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
myAWSIoTMQTTClient.configureConnectDisconnectTimeout(300)  # 5 mins
myAWSIoTMQTTClient.configureMQTTOperationTimeout(120)  # 2 mins

# Connect and subscribe to AWS IoT
myAWSIoTMQTTClient.connect()
myAWSIoTMQTTClient.subscribe(topic, 1, customCallback)
time.sleep(2)

# Publish to the same topic in a loop forever
loopCount = 0

def main():
    sensorSamplingRate = set_sampling_time()
    print(sensorSamplingRate)

    try:
        temp = [1, 1, 1]
        while True:
            for i in range(3):
                temp[i] = live_sampling(DEVICE_FOLDER[i], sensorSamplingRate, "")
                print('Sensor {0} is {1}'.format(SENSORS[i], temp[i]))
            messageObject = ("{0} : {1},{2} : {3},{4} : {5}".
                             format(SENSORS[0], temp[0], SENSORS[1], temp[1],
                                    SENSORS[2], temp[2]))
            myAWSIoTMQTTClient.publish("/TemperatureSensors", messageObject, 1)
            time.sleep(int(sensorSamplingRate))
            
    except (KeyboardInterrupt, Exception) as e:
        print(e)
        print("Program successfully terminated")
        
        
if __name__ == '__main__':
    main()
