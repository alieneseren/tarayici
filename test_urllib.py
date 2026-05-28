import urllib.request
print("google.com:")
try:
    print(urllib.request.urlopen("http://google.com", timeout=5).getcode())
except Exception as e:
    print("Error:", e)

print("ipinfo.io:")
try:
    print(urllib.request.urlopen("http://ipinfo.io", timeout=5).getcode())
except Exception as e:
    print("Error:", e)

print("example.com:")
try:
    print(urllib.request.urlopen("http://example.com", timeout=5).getcode())
except Exception as e:
    print("Error:", e)
