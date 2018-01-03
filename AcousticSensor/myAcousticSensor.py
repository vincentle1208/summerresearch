import serial

import logging
import time
import argparse

import threading
import struct
from collections import deque
import sys

from datetime import datetime
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

""" User Parameters """
sampleRate = 20000 # hz per channel
channels = 1 # 1 is ch A alone, 2 is both
macro = True # 12 bit or not
fileName = "data"

""" Internal """
running = True
ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=1.0)
serWaiting = 0
dataQueue = deque()
frameToken = "af"
tickRate = 0
filePath = "./" + fileName + ".txt"
readCount = 600

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
myAWSIoTMQTTClient.configureDrainingFrequency(100)  # Draining: 2 Hz
myAWSIoTMQTTClient.configureConnectDisconnectTimeout(300)  # 5 mins
myAWSIoTMQTTClient.configureMQTTOperationTimeout(120)  # 2 mins

# Connect and subscribe to AWS IoT
myAWSIoTMQTTClient.connect()
myAWSIoTMQTTClient.subscribe(topic, 1, customCallback)
time.sleep(0.1)

##################################################

if channels == 1:
    if not macro:
        tickRate = sampleRate
    else:
        tickRate = sampleRate * 2

""" Serial helpers """
def issue(message):
    global serWaiting
    ser.write(message.encode())
    serWaiting += len(message)
    
def issueWait(message):
    global serWaiting
    ser.write(message.encode())
    serWaiting += len(message)
    clearWaiting()
    
def read(count):
    return ser.read(count)
    
def readAll():
    return ser.read(ser.inWaiting())
    
def clearWaiting():
    global serWaiting
    r = ser.read(serWaiting)
    serWaiting = serWaiting - len(r)

""" Utilities """
def freqToHexTicks(freq):
    ticks = int((freq ** -1) / 0.000000025)
    print(ticks)
    hexTicks = hex(ticks)[2:]
    zeroAdds = "0" * (4 % len(hexTicks))
    combined = zeroAdds + hexTicks
    return combined[2:], combined[:2]
    
def getToRange(fromRange, toRange):
    fr, tr = fromRange, toRange
    slope = float(tr[1] - tr[0]) / float(fr[1] - fr[0])
    return lambda v : round((10**6) * (tr[0] + slope * float(v - fr[0])), 1)
    
""" Decoding """
def decode1ChMacro(data):
    unpackArg = "<" + str(int(len(data) / 2)) + "h"
    unpacked = list(struct.unpack(unpackArg, data))
    for i in unpacked:
        a = (i & 0x00ff) >> 4
        b = (i & 0xff00) << 4
        i = a + b
    return unpacked

def setupBS():
    """ Standard setup procedure. """
    if channels == 1:
        chString = "01"
        if macro:
            modeString = "04"
        else:
            modeString = "02"
        
    issueWait("!")
    issueWait(
        "[21]@[" + modeString + "]s" # Stream mode (Macro Analogue Chop (is 03))
        + "[37]@[" + chString + "]sn[00]s" # Analogue ch enable (both)
        + "[2e]@[%s]sn[%s]s" % freqToHexTicks(tickRate) # Clock ticks
        + "[14]@[03]sn[00]s" # Clock scale (Doesn't work for streaming mode)
        + "[36]@[" + frameToken + "]s" # Stream data token
        + "[66]@[5a]sn[b2]s" # High
        + "[64]@[35]sn[1b]s" # Low
    )
    issueWait("U")
    issueWait(">")
    readAll()
    
def startStream():
    read(2) # ?!?!?!
    issueWait("T")
    
def readLoop():
    setupBS()
    startStream()
    while running:
        data = bytearray()
        toGet = 20000                   # Take 44000 samples in 1 second
        data = ser.read(toGet)
        dataQueue.append(data)
        time.sleep(1)
        
def writeToFile(file, data, count):
    # Write to file
    dataStr = ','.join(map(str, data))
    #for i in range(len(data)/100):
     #   print data[i]
    strData = dataStr + ',' + '\n'
    toWrite = str(datetime.now()) + '\n'
    file.write(toWrite)
    return strData
    
def main():
    try :
        dumpFile = open(filePath, 'w')
        # Stop BS and clear out serial buffer
        issueWait(".")
        readAll()
        # Open read stream thread
        readThread = threading.Thread(target = readLoop)
        readThread.start()
        # Start writing loop in main thread

        decodeFn = decode1ChMacro
        fromRange = (-32768, 32767)
        toRangeLambda = getToRange(fromRange, (-5, 5))
        
        counter = 0
        while True:
            #time.sleep(0.1)
            while len(dataQueue):
                # Pop data
                data = dataQueue.popleft()
                # Decode
                levelData = decodeFn(data)
                # Voltify
                voltData = list(map(toRangeLambda, levelData))
                # Write
                messageObject = writeToFile(dumpFile, voltData, counter)
                myAWSIoTMQTTClient.publish("/AcousticSensor", messageObject, 1)
    
    except (KeyboardInterrupt, Exception) as e:
        running = False
        print (e)
        print ("Program terminated successfully")
        
if __name__ == '__main__':
    main()
