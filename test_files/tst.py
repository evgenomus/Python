import serial
import time


ser = serial.Serial('COM1')  # open serial port
print(ser.name)   
ser2 = serial.Serial('COM2')  # open serial port
print(ser2.name) 
counter = 0

if(ser.isOpen() == True and ser2.isOpen() == True):
   print('here')

time.sleep(5)
while counter < 5:
    ser.write(b'Hi!\n')
    a = ser.write(b'Hi!\n')
    counter += 1
    print('Hi!', a)
    b = ser2.read_all()
    print(f'b {b}')
    c = input('Input ')
    c += ' '
    ser.write(bytes(c, 'utf-8'))
    d = ser2.read_all()
    print(f'd {d}, c {c}')
    time.sleep(1)


ser.close()