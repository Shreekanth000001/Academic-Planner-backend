# queue.py
from arq import create_pool
from arq.connections import RedisSettings
from config import settings

# Global holder for the Redis connection pool
redis_pool = None

async def init_redis():
    """
    Initializes the Redis connection pool at FastAPI startup.
    Using Upstash or a local Docker Redis instance.
    """
    global redis_pool
    # Parse your REDIS_URL if needed, or pass host/port explicitly
    redis_pool = await create_pool(RedisSettings(host="localhost", port=6379))
    print("Redis queue pool initialized.")

async def close_redis():
    """Cleans up the pool at shutdown."""
    if redis_pool:
        await redis_pool.close()

async def enqueue_syllabus_job(upload_id: str):
    """
    Pushes the job to the queue. 
    Only pass the ID (primitive type). Never pass complex database objects 
    or massive file buffers over a message broker.
    """
    if not redis_pool:
        raise RuntimeError("Redis pool is not initialized.")
    
    # 'process_syllabus' is the name of the function the worker will execute
    await redis_pool.enqueue_job("process_syllabus", upload_id=upload_id)