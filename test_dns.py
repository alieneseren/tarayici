import socket

try:
    print("ipinfo.io ->", socket.getaddrinfo("ipinfo.io", 80))
except Exception as e:
    print("DNS error:", e)

try:
    print("google.com ->", socket.getaddrinfo("google.com", 80))
except Exception as e:
    print("DNS error:", e)
