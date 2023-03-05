import serial
from datetime import datetime
import time

# Getting the current date and time

HEADERSIZE = 8

ser = serial.Serial('COM5')  # open serial port
print(ser.name)   
counter = 0

while counter < 10:
    date_time = datetime.now()
    str_date_time = date_time.strftime("%H:%M:%S")

    a = 'NewData ' + str_date_time + '\n'
    a = f'{len(a) :< {HEADERSIZE}}'+ a
    ba = bytes(a, 'utf-8')
    ser.write(a.encode()) 
    ba = ser.write(bytes(a, 'utf-8'))
    print(ba)
    ser.flush()
    with open('data.txt', 'a') as f:
        f.write(f'Send from COM:\n\t{a}')
    
    counter += 1
    print(f'Left: {10 - counter}')
    time.sleep(10)


ser.close()