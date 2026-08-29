import requests

try:
    res = requests.post("http://localhost:5000/api/start_tunnel")
    print("Status:", res.status_code)
    print("Body:", res.text)
except Exception as e:
    print("Error connecting to server:", e)
