import asyncio
import os
from pydantic import BaseModel
from google.antigravity import Agent, LocalAgentConfig
from dotenv import load_dotenv

load_dotenv()

class RefundDecision(BaseModel):
    is_approved: bool
    reason: str

from agent import check_abac_policy

async def t():
    agent = Agent(config=LocalAgentConfig(system_instructions='Use the tool.', tools=[check_abac_policy], api_key=os.getenv('GEMINI_API_KEY')))
    async with agent as a:
        res = await a.chat('Check refund for bob, transaction, refund, 15')
        text = await res.text()
        print("Text:", text)

asyncio.run(t())
