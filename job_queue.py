# queue.py
from arq import create_pool
from arq.connections import RedisSettings

redis_pool = None

async def init_redis():
    global redis_pool
    redis_pool = await create_pool(RedisSettings(host="localhost", port=6379))
    print("Redis initiated")
    
async def close_redis():
    global redis_pool
    if redis_pool:
        await redis_pool.close()

async def enqueue_syllabus_upload(upload_id:str):
    if redis_pool is None:
        raise RuntimeError("FATAL: Redis memory buffer is offline. Cannot queue task.")
    
    await redis_pool.enqueue_job("process_syllabus",upload_id, _job_id=upload_id)
    print(f"Task safely dumped to memory buffer: {upload_id}")