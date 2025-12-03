import time
import asyncio
async def test(num:int):
    for i in range(num):
        if i % 100 == 0:
            print(i)
            time.sleep(1)

if __name__ == "__main__":
    asyncio_task = asyncio.run(test(1000))
    # await asyncio.sleep(1)
    print('test')