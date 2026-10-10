import asyncio
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

async def test():
    print("Testing basic generative ai...")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not set")
        return
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    try:
        response = await model.generate_content_async("Hello")
        print("Response:", response.text)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(test())
