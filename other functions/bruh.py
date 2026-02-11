import time
import requests

url = "http://127.0.0.1:5000/"

while True:
    try:
        r = requests.get(url)
        print(f"Refreshed: {r.status_code}")
    except Exception as e:
        print("Error:", e)
    time.sleep(3)
