import asyncio
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

async def t():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    res = await model.generate_content_async('Hello')
    print(res.text)

if __name__ == "__main__":
    asyncio.run(t())
