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

@app.post("/uploads/syllabys",status_code=status.HTTP_202_ACCEPTED)
async def upload_syllabus( 
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session)):

    if(file.content_type != "application/pdf"):
        raise HTTPException(status_code=500,detail="Expected PDF Format")
    
    sha256_hash=hashlib.sha256()
    file_path= bytearray()

    while chunk:= await file.read(8019):
        sha256_hash.update(chunk)
        file_path.extend(chunk)

    _, ext= os.path.splitext(file.filename) # type: ignore

    file_unique_name = f"{uuid.uuid4()}{ext}"
    print(file_unique_name)

    try:
        await run_in_threadpool(
            upload_syllabus_bucket,
            bucket="syllabi",
            file_path=file_unique_name,
            file_bytes=bytes(file_path),
            file_type=file.content_type
        )
    except Exception as e:
        print("Exception error: ",e)
        raise HTTPException(status_code=500,detail="unable to upload pdf")

    filehash = sha256_hash.hexdigest()
    public_url=f"{settings.SUPABASE_URL}/storage/v1/object/public/syllabi/{file_unique_name}"
    mock_user_id = "11111111-2222-3333-4444-555555555555" 

    new_upload = Upload(
        user_id=mock_user_id,
        file_url=public_url,
        file_hash=filehash,
        status=UploadStatus.COMPLETED
    )

    session.add(new_upload)

    try:
        await session.commit()
    except Exception as e:
        raise HTTPException(status_code=500,detail="Couldn't commit session - new upload")
    
    print("Uploaded new upload record")
    await enqueue_syllabus_job(upload_id=str(new_upload.id))
    

    return {
        "message": "Upload accepted and queued for processing!"
    }
