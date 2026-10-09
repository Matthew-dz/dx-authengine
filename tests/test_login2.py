import requests
import json

url = 'http://127.0.0.1:8000/api/v1/login'
data = {'username': 'rayden', 'password': '1234'}
response = requests.post(url, json=data)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
