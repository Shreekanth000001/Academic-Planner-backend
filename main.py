from contextlib import asynccontextmanager

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from supabase import create_client, Client

from database import get_session
from models import Schedule, StudyTask, User
from config import settings
from job_queue import init_redis,close_redis
from api.routers import uploads, webhooks
from core.security import get_current_user

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",    
]

@asynccontextmanager
async def lifespan(app:FastAPI):
    print("Fastapi Application started")
    await init_redis()

    yield
    
    print("Shutting down: Closing Redis connections...")
    await close_redis()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

def upload_syllabus_bucket(bucket:str,file_path:str, file_bytes:bytes,file_type:str):
    res = supabase.storage.from_(bucket).upload(
        file_path,
        file_bytes,
        file_options={"content-type": file_type}
    )
    return res

@app.get("/schedules")
async def get_schedules(session : AsyncSession = Depends(get_session)):
    schedules = await session.execute(select(Schedule))
    sched = schedules.scalars().all()
    return sched

@app.get("/viewtask")
async def get_tasks( schedule_id: str, # We talked about this earlier, we need to filter by schedule!
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)):

    stmt = select(StudyTask).join(Schedule).where(
        StudyTask.schedule_id == schedule_id,
        Schedule.user_id == current_user.id
    )
    tasks = await session.execute(stmt)

    return tasks.scalars().all()

app.include_router(uploads.router)
app.include_router(webhooks.router)