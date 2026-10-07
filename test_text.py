import asyncio
import os
from google.antigravity import Agent, LocalAgentConfig
from dotenv import load_dotenv

load_dotenv()

async def t():
    agent = Agent(config=LocalAgentConfig(system_instructions='You are a helpful assistant.', api_key=os.getenv('GEMINI_API_KEY')))
    async with agent as a:
        res = await a.chat('Hello')
        print(res.text)

asyncio.run(t())
