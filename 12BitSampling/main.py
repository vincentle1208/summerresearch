import serial
import time
import threading
import struct
from collections import deque

from datetime import datetime

""" User Parameters """
sampleRate = 100000 # hz per channel

channels = 1 # 1 is ch A alone, 2 is both

macro = True # 12 bit or not

fileName = "dump"

""" Internal """
running = True
ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=1.0)
serWaiting = 0
dataQueue = deque()
frameToken = "af"
tickRate = 0
filePath = "./" + fileName + ".txt"
readCount = 600

if channels == 1:
    if not macro:
        tickRate = sampleRate
    else:
        tickRate = sampleRate * 2
else:
    if not macro:
        tickRate = sampleRate * 4
    else:
        tickRate = sampleRate * 3

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
def decode1Ch(data):
    unpackArg = "<" + str(len(data)) + "B"
    unpacked = struct.unpack(unpackArg, data)
    return list(unpacked)

def decode1ChMacro(data):
    unpackArg = "<" + str(int(len(data) / 2)) + "h"
    unpacked = list(struct.unpack(unpackArg, data))
    for i in unpacked:
        a = (i & 0x00ff) >> 4
        b = (i & 0xff00) << 4
        i = a + b
    return unpacked

def decode2Ch(data):
    # token, count, cha, chb
    unpackArg = "<" + str(len(data)) + "B"
    up = struct.unpack(unpackArg, data)
    return [v for p in zip(up[2::4], up[3::4]) for v in p]

def decode2ChMacro(data):
    # cha + token-nibble, cha, chb + token-nibble, chb
    unpackArg = "<" + str(int(len(data) / 2)) + "h"
    unpacked = struct.unpack(unpackArg, data)
    rmToken = lambda x : x & ~0x000f
    formatted = map(rmToken, unpacked)
    return list(formatted)

def setupBS():
    """ Standard setup procedure. """
    if channels == 1:
        chString = "01"
        if macro:
            modeString = "04"
        else:
            modeString = "02"
    else:
        chString = "03"
        if macro:
            modeString = "03"
        else:
            modeString = "01"
        
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
        toGet = 44000                   # Take 44000 samples in 1 second
        data = ser.read(toGet)
        dataQueue.append(data)
        
def writeToFile(file, data, count):
    # Write to file
    dataStr = ','.join(map(str, data))
    toWrite = dataStr + ','
    file.write(toWrite)
    
def processAndWriteLoop():
    decodeFn = None
    if channels == 1:
        if not macro:
            decodeFn = decode1Ch
        else:
            decodeFn = decode1ChMacro
    else:
        if not macro:
            decodeFn = decode2Ch
        else:
            decodeFn = decode2ChMacro

    fromRange = None
    if macro:
        fromRange = (-32768, 32767)
        #fromRange = (-524288, 524287)
    else:
        fromRange = (0, 255)

    toRangeLambda = getToRange(fromRange, (-5, 5))
    dumpFile = open(filePath, "w")

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
            if (counter == 0):
                print("start: " + str(datetime.now()))
            if (counter == 1) :
                print("Finish 10 SAMPLES" + str(datetime.now()))
            if (counter < 1) :
                writeToFile(dumpFile, voltData, counter)
            if (counter == 1) :
                print("Finish 10 SAMPLES" + str(datetime.now()))
            counter = counter + 1
    
def main():
    # Stop BS and clear out serial buffer
    issueWait(".")
    readAll()
    # Open read stream thread
    readThread = threading.Thread(target = readLoop)
    readThread.start()
    # Start writing loop in main thread
    processAndWriteLoop()
    
""" Go """

main()
