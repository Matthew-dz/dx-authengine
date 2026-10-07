import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

for model in ["gemini-3.8-flash-lite", "gemini-3.5-flash-lite"]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {"contents": [{"parts":[{"text": "Hello"}]}]}
    headers = {'Content-Type': 'application/json'}
    print(f"Testing {model}...")
    start = time.time()
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"Time taken: {time.time() - start:.2f}s")
        print("Status:", response.status_code)
        print("Response:", response.text[:100])
    except Exception as e:
        print("Error:", e)
