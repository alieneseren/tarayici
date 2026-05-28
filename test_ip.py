import socket

print("Testing direct socket to 8.8.8.8 port 53...")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect(("8.8.8.8", 53))
    print("Socket connected!")
    s.close()
except Exception as e:
    print("Socket connection error:", e)

