import asyncio
import os
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class RefundDecision(BaseModel):
    is_approved: bool
    reason: str

async def t():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    res = await model.generate_content_async('Check refund for bob, transaction, refund, 15')
    print("Text:", res.text)

if __name__ == "__main__":
    asyncio.run(t())
