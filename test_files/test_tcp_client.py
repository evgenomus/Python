#!/usr/bin/python           # This is client.py file

import socket               # Import socket module
from datetime import datetime

HEADERSIZE = 8

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)         # Create a socket object
host = "10.23.0.51" # Get local machine name
port = 35000               # Reserve a port for your service.

print ('Connecting to ', host, port)
client.connect((host, port))
print("Connecnted")
c = 9
new_msg = True
while True:
    msg = client.recv(8)
    full_msg = ''
    if new_msg:
        print(f'Msg arrived, size = {msg[:HEADERSIZE]}\n')
        try:
            msgLen = int(msg[:HEADERSIZE])
        except:
            print("worng len")
        
        new_msg = False

    full_msg += str(msg[:HEADERSIZE])

    date_time = datetime.now()
    str_date_time = date_time.strftime("%H:%M:%S")        
    print (f'{str_date_time} SERVER >> ', msg[HEADERSIZE:])
    new_msg = True
    full_msg = ''

    print(full_msg)
    c -= 1
#s.close 