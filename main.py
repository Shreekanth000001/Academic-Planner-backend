from contextlib import asynccontextmanager
import uuid
import hashlib
import os

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI,UploadFile,File, Depends,status,HTTPException
from fastapi.concurrency import run_in_threadpool 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from supabase import create_client, Client

from database import get_session
from models import Upload,UploadStatus, Schedule, StudyTask
from config import settings
from job_queue import init_redis,close_redis,enqueue_syllabus_job
from api.routers import uploads, webhooks

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",    
]


# class upload(BaseModel):
#     file: UploadFile = File(...),#Files(...) is giving an error[tuple[Any]] can't be assingned
#     session: AsyncSession = Depends(get_session)

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
    allow_credentials=True,         # Allows cookie-based session transport/Auth headers if needed
    allow_methods=["*"],            # Allows all standard HTTP methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],            # Allows all incoming headers (Content-Type, Authorization, etc.)
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
async def get_tasks(session: AsyncSession = Depends(get_session)):
    tasks = await session.execute(select(StudyTask))
    task= tasks.scalars().all()
    return task

app.include_router(uploads.router)
app.include_router(webhooks.router)