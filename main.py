from contextlib import asynccontextmanager
import asyncio
import uuid

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, desc
from supabase import create_client, Client

from database import get_session
from models import Schedule, StudyTask, User
from config import settings
from job_queue import init_redis,close_redis
from api.routers import uploads, webhooks, chat
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
async def get_schedules(session : AsyncSession = Depends(get_session),
                        current_user: User = Depends(get_current_user)):
    stmt = (
        select(Schedule)
        .where(Schedule.user_id == current_user.id)
        .order_by(desc(Schedule.created_at))
    )
    schedules = await session.execute(stmt)
    sched = schedules.scalars().all()
    print(sched)
    return sched

@app.get("/viewtask")
async def get_tasks( schedule_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)):

    stmt_sched = select(Schedule).where(
        Schedule.id == schedule_id,
        Schedule.user_id == current_user.id
    )
    result_sched = await session.execute(stmt_sched)
    schedule = result_sched.scalars().first()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    stmt_tasks = select(StudyTask).where(StudyTask.schedule_id == schedule_id).order_by(StudyTask.order_index.asc()) 
    result_tasks = await session.execute(stmt_tasks)
    tasks = result_tasks.scalars().all()

    return {
        "upload_id": str(schedule.upload_id),
        "tasks": tasks
    }

@app.delete("/schedules/{schedule_id}")
async def get_delete(schedule_id:uuid.UUID,
                    session:AsyncSession = Depends(get_session),
                    current_user : User = Depends(get_current_user)):
    stmt_schedule_delete=delete(Schedule).where(
        Schedule.id == schedule_id,
        Schedule.user_id == current_user.id).returning(Schedule.id)
    
    result = await session.execute(stmt_schedule_delete)
    
    deleted_id = result.scalar_one_or_none()

    if not deleted_id:
        raise HTTPException(status_code=404, detail="Schedule not found or unauthorized")
    
    await session.commit()

    return {"msg": "Deleted successfully"}

app.include_router(uploads.router)
app.include_router(webhooks.router)
app.include_router(chat.router)