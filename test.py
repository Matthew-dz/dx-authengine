import asyncio
from app.agent import process_refund_request

async def test():
    try:
        res = await process_refund_request("bob", "transaction", "refund", 15)
        print("Type:", type(res))
        print("Dir:", dir(res))
        print("Value:", res)
    except Exception as e:
        print("Error:", repr(e))

if __name__ == '__main__':
    asyncio.run(test())
