from arq import create_pool
from arq.connections import RedisSettings

import asyncio

redis_pool = None

async def enque_syllabus_job():
    global redis_pool
    redis_pool = await create_pool(RedisSettings(host="localhost",port=6379))

    upload_id = "09759f56-67b8-43e9-81c1-b59626841c1a"

    await redis_pool.enqueue_job(
        'process_syllabus',
        upload_id,
        _job_id=upload_id
    )
    print("redis initiated")
    await redis_pool.close()

if __name__ == "__main__":
    asyncio.run(enque_syllabus_job())