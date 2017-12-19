file = open('/home/pi/improved_streaming/dump.txt', 'r')
i = 0
for line in file:
    i = i + 1
    for m in range(len(line)) :
        if line[m] == '|' :
            print (str(i) + str(line[m:m+3]))
            break
