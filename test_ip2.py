import socket

try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect(("192.178.24.174", 80))
    print("google IP port 80 connected!")
    s.close()
except Exception as e:
    print("google IP port 80 error:", e)

try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect(("8.8.8.8", 80))
    print("8.8.8.8 port 80 connected!")
    s.close()
except Exception as e:
    print("8.8.8.8 port 80 error:", e)
