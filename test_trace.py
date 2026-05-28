import socket

old_connect = socket.socket.connect

def my_connect(self, address):
    print(f"Intercepted connect to: {address}")
    return old_connect(self, address)

socket.socket.connect = my_connect

print("Connecting to google.com:80...")
try:
    s = socket.socket()
    s.settimeout(5)
    s.connect(("google.com", 80))
except Exception as e:
    print("Error:", e)

print("Connecting to ipinfo.io:80 using create_connection...")
try:
    socket.create_connection(("ipinfo.io", 80), timeout=5)
except Exception as e:
    print("Error:", e)
