import asyncio
import os
from google.antigravity import Agent, LocalAgentConfig
from dotenv import load_dotenv

load_dotenv()

async def test():
    print("Testing basic agent...")
    config = LocalAgentConfig(
        system_instructions="You are a helpful assistant.",
        api_key=os.getenv("GEMINI_API_KEY")
    )
    async with Agent(config=config) as agent:
        print("Agent created, chatting...")
        try:
            response = await asyncio.wait_for(agent.chat("Hello"), timeout=10)
            print("Response:", response.text)
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    asyncio.run(test())
