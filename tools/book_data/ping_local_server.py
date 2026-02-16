import time
import requests

URL = "http://127.0.0.1:5000/"
INTERVAL_SECONDS = 3

while True:
    try:
        r = requests.get(URL)
        print(f"Refreshed: {r.status_code}")
    except Exception as e:
        print("Error:", e)
    time.sleep(INTERVAL_SECONDS)
