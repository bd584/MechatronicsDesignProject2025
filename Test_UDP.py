import socket
import time

UDP_IP = "138.38.229.217"   # Raspberry Pi IP
UDP_PORT = 50002            # Port Simulink receives on

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def send_cmd(cmd):
    # send single-byte integer (1,2,3,4)
    sock.sendto(bytes([cmd]), (UDP_IP, UDP_PORT))

# Option 1: explicit sleeps
# send_cmd(1)  # Start
# time.sleep(1)
# send_cmd(2)  # Forward
# time.sleep(1)
# send_cmd(3)  # Backward
# time.sleep(1)
# send_cmd(4)  # Stop

# Option 2: loop with a 1s delay
commands = [1, 2, 3, 4]
for cmd in commands:
    send_cmd(cmd)
    time.sleep(1)