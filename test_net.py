import urllib.request
import os

print("Proxies:", urllib.request.getproxies())
print("HTTP_PROXY:", os.environ.get("HTTP_PROXY"))
print("HTTPS_PROXY:", os.environ.get("HTTPS_PROXY"))
print("http_proxy:", os.environ.get("http_proxy"))
print("https_proxy:", os.environ.get("https_proxy"))

try:
    print("Trying ipinfo.io...")
    req = urllib.request.urlopen("http://ipinfo.io", timeout=5)
    print("Success:", req.read().decode('utf-8')[:50])
except Exception as e:
    print("Error:", e)
