import requests
import time

payload = {
    "order_id": 1,
    "username": "admin"
}

print("Gửi request hoàn tiền...")
start = time.time()
response = requests.post("http://127.0.0.1:8000/api/v1/refund", json=payload)
print(f"Response: {response.status_code}")
print(response.json())
print(f"Thời gian: {time.time() - start}s")
