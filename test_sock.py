import socket

print("Testing direct socket to ipinfo.io port 80...")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect(("ipinfo.io", 80))
    print("Socket connected!")
    s.close()
except Exception as e:
    print("Socket connection error:", e)
    
print("Testing direct socket to google.com port 80...")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect(("google.com", 80))
    print("Socket connected!")
    s.close()
except Exception as e:
    print("Socket connection error:", e)
