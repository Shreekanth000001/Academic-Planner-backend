from contextlib import asynccontextmanager
import uuid
import hashlib
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import APIRouter, Depends, UploadFile
from fastapi import FastAPI,UploadFile,File, Depends,status,HTTPException,Request
from fastapi.concurrency import run_in_threadpool 
from core.security import get_current_user
from supabase import create_client, Client

from database import get_session
from models import Upload,UploadStatus, User
from config import settings
from job_queue import init_redis,close_redis,enqueue_syllabus_job

router = APIRouter(
    prefix="/upload",
    tags=["Uploads"]
)

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

def upload_syllabus_bucket(bucket:str,file_path:str, file_bytes:bytes,file_type:str):
    res = supabase.storage.from_(bucket).upload(
        file_path,
        file_bytes,
        file_options={"content-type": file_type}
    )
    return res

@router.post("/syllabys", status_code=status.HTTP_202_ACCEPTED)
async def upload_syllabus( 
    file: UploadFile = File(...),
    user_id: User = Depends(get_current_user),
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

    new_upload = Upload(
        user_id=user_id.id,
        file_url=public_url,
        file_hash=filehash,
        status=UploadStatus.PENDING
    )

    session.add(new_upload)

    try:
        await session.commit()
    except Exception as e:
        raise HTTPException(status_code=500,detail="Couldn't commit session - new upload")
    
    print("Uploaded new upload record")
    await enqueue_syllabus_job(upload_id=str(new_upload.id))
    

    return {
        "message": "Upload accepted and queued for processing!",
        "upload_id": str(new_upload.id)
    }

@router.get("/{upload_id}/status")
async def get_upload_status(
    upload_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    stmt = select(Upload.status).where(
        Upload.id == upload_id,
        Upload.user_id == current_user.id
    )
    result = await session.execute(stmt)
    status = result.scalar_one_or_none()
    
    if not status:
        raise HTTPException(status_code=404, detail="Upload not found")
        
    return {"status": status.value}
