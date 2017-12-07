def main():
    sensorSamplingRate = set_sampling_time()
    print(sensorSamplingRate)
            
    try:
        pid = 0
        listPID = []
        for i in range(3):
            pid = os.fork()
            if pid > 0 : # child process
                listPID.append(pid)
                fout = open('{0}.txt'.format(SENSORS[i]), 'w')
                fout.write('File created for sensor {0}\n'.format(SENSORS[i]))
                live_sampling(DEVICE_FOLDER[i], sensorSamplingRate[i], fout)
                break
            pid = 0
            
        while True:    
            for pid in listPID:
                os.waitpid(pid, 0)
##            for i in range(3):
##                data[i] = read_temp(DEVICE_FOLDER[i])
##                print('Sensor {0}'.format(data[i]))
        
    except (KeyboardInterrupt, Exception) as e:
        print(e)
        GPIO.cleanup()
        os.kill(pid, signal.SIGKILL)
        print("Pro")