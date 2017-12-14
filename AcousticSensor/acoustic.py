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
from bitlib import *

import logging
import time
import argparse

import os
import glob
import time
import sys
import signal
import RPi.GPIO as GPIO

# Folder directory definitions
MY_DEVICE = 0 # one open device only
MY_CHANNEL = 0 # channel to capture and display
MY_PROBE_FILE = "" # default probe file if unspecified 
MY_MODE = BL_MODE_FAST # preferred capture mode
MY_RATE = 5000000 # default sample rate we'll use for capture.
MY_SIZE = 10000 # number of samples we'll capture (simply a connectivity test)
TRUE = 1

MODES = ("FAST","DUAL","MIXED","LOGIC","STREAM")
SOURCES = ("POD","BNC","X10","X20","X50","ALT","GND")

# LED PINs
LED = 2

#GPIO Setup
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

#Initilise LEDs

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
#formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#streamHandler.setFormatter(formatter)
#logger.addHandler(streamHandler)

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

def main():

    try:
        # Open the first device found (only)
        #
        print ("Starting: Attempting to open one device...")
        if BL_Open(MY_PROBE_FILE,1):
            #
            # Open succeeded (report versions).
            #
            print (" Library: %s (%s)" % (
                BL_Version(BL_VERSION_LIBRARY),
                BL_Version(BL_VERSION_BINDING)))
            #
            # Select this device (optional, it's already selected).
            #
            BL_Select(BL_SELECT_DEVICE,MY_DEVICE)
            #
            # Report the link, device and channel information.
            #
            print ("    Link: %s" % BL_Name(0))
            print ("BitScope: %s (%s)" % (BL_Version(BL_VERSION_DEVICE),BL_ID()))
            print ("Channels: %d (%d analog + %d logic)" % (
                BL_Count(BL_COUNT_ANALOG)+BL_Count(BL_COUNT_LOGIC),
                BL_Count(BL_COUNT_ANALOG),BL_Count(BL_COUNT_LOGIC)))
            #
            # Determine which modes the device supports.
            #
            print ("   Modes:" + "".join(["%s" % (
                (" " + MODES[i]) if i == BL_Mode(i) else "") for i in range(len(MODES))]))
            #
            # Report canonic capture specification in LOGIC (if supported) or FAST mode (otherwise.
            #
            BL_Mode(BL_MODE_LOGIC) == BL_MODE_LOGIC or BL_Mode(BL_MODE_FAST)
            print (" Capture: %d @ %.0fHz = %fs (%s)" % (
                BL_Size(),BL_Rate(),
                BL_Time(),MODES[BL_Mode()]))
            #
            # Report the maximum offset range (if the device supports offsets).
            #
            BL_Range(BL_Count(BL_COUNT_RANGE));
            if BL_Offset(-1000) != BL_Offset(1000):
                print ("  Offset: %+.4gV to %+.4gV" % (
                    BL_Offset(1000), BL_Offset(-1000)))
            #
            # Report the input source provided by the device and their respective ranges.
            #
            for i in range(len(SOURCES)):
                if i == BL_Select(2,i):
                    print ("     %s: " % SOURCES[i] + " ".join(["%5.2fV" % BL_Range(n) for n in range(BL_Count(3)-1,-1,-1)]))
            #
            # Set up to capture MY_SIZE samples at MY_RATE from CH-A via the POD input using the highest range.
            #
            BL_Mode(MY_MODE) # prefered capture mode
            BL_Intro(BL_ZERO); # optional, default BL_ZERO
            BL_Delay(BL_ZERO); # optional, default BL_ZERO
            BL_Rate(MY_RATE); # optional, default BL_MAX_RATE
            BL_Size(MY_SIZE); # optional default BL_MAX_SIZE
            BL_Select(BL_SELECT_CHANNEL,MY_CHANNEL); # choose the channel
            BL_Trigger(BL_ZERO,BL_TRIG_RISE); # optional when untriggered */
            BL_Select(BL_SELECT_SOURCE,BL_SOURCE_POD); # use the POD input */
            BL_Range(BL_Count(BL_COUNT_RANGE)); # maximum range
            BL_Offset(BL_ZERO); # optional, default 0
            BL_Enable(TRUE); # at least one channel must be initialised 
            while True:
                #
                # Perform an (untriggered) trace (this is the actual data capture).
                #
                BL_Trace()
                #
                # Acquire (i.e. upload) the captured data (which may be less than MY_SIZE!).
                #
                DATA = BL_Acquire()
                ## Publish on MQTT Client
                messageObject = (",".join(["%f" % DATA[n] for n in range(len(DATA))]))
                myAWSIoTMQTTClient.publish("/AcousticSensor", messageObject, 1)
                #print (" Data(%d): " % MY_SIZE + ", ".join(["%f" % DATA[n] for n in range(len(DATA))]))
                #time.sleep(1)            
            # Close the library to release resources (we're done).
            #
            BL_Close()
            print ("Finished: Library closed, resources released.")
        else:
            print ("  FAILED: device not found (check your probe file).")
            
    except (KeyboardInterrupt, Exception) as e:
        print(e)
        print("Program successfully terminated")
        
        
if __name__ == '__main__':
    sys.exit(main())
