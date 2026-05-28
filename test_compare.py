import socket

print("TEST 1: socket.socket()")
try:
    s = socket.socket()
    s.settimeout(5)
    s.connect(("google.com", 80))
    print("TEST 1 SUCCESS!")
    s.close()
except Exception as e:
    print("TEST 1 ERROR:", e)

print("TEST 2: socket.socket(AF_INET)")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect(("google.com", 80))
    print("TEST 2 SUCCESS!")
    s.close()
except Exception as e:
    print("TEST 2 ERROR:", e)

print("TEST 3: create_connection")
try:
    s = socket.create_connection(("google.com", 80), timeout=5)
    print("TEST 3 SUCCESS!")
    s.close()
except Exception as e:
    print("TEST 3 ERROR:", e)
