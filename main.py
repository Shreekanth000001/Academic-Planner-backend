import hashlib
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from supabase import create_client, Client
import uuid
import os

# Import your config, database session, and models
from config import settings
from database import get_session
from models import Upload, UploadStatus, User
from job_queue import enqueue_syllabus_job
from config import settings

app = FastAPI(title="Academic Planner API")

# 2. Your router from yesterday
from fastapi import APIRouter, UploadFile, File, Depends
router = APIRouter()

# Initialize Supabase Client
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

async def verify_clerk_token(token: str) -> User:
    """
    Mock dependency. In production, you MUST decode the Clerk JWT here,
    query the DB for the user, and return the User object. 
    If you accept `user_id` as a raw string from the frontend, you have an 
    Insecure Direct Object Reference (IDOR) vulnerability.
    """
    # Placeholder: Assuming the token resolved to a valid user in the DB
    # user = await session.exec(select(User).where(User.clerk_id == decoded_id))
    pass

def upload_to_supabase_storage(bucket: str, file_path: str, file_bytes: bytes, content_type: str):
    """
    Synchronous wrapper for Supabase storage upload. 
    We isolate this so we can push it to a threadpool.
    """
    res = supabase.storage.from_(bucket).upload(
        path=file_path,
        file=file_bytes,
        file_options={"content-type": content_type}
    )
    return res

@router.post("/uploads/syllabus", status_code=status.HTTP_202_ACCEPTED)
async def upload_syllabus(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    # current_user: User = Depends(verify_clerk_token) # Uncomment when auth is wired
):
    """
    Ingests a PDF, hashes it, uploads to Storage, and queues the DB record.
    """
    # 1. Validation
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Unsupported Media Type. PDF only.")

    # 2. Memory-Safe File Hashing (The Idempotency Key)
    sha256_hash = hashlib.sha256()
    file_bytes = bytearray()
    
    # Read in 8KB chunks to prevent RAM exhaustion
    while chunk := await file.read(8192):
        sha256_hash.update(chunk)
        file_bytes.extend(chunk) # Keep in memory ONLY if files are strictly < 10MB
        
    file_hash = sha256_hash.hexdigest()
    
    # Reset file pointer if you needed to read it again via the file object
    await file.seek(0)

    # 3. Deduplication Check
    # Is this exact file already in the database for this user?
    # query = select(Upload).where(Upload.file_hash == file_hash, Upload.user_id == current_user.id)
    # existing_upload = (await session.exec(query)).first()
    # if existing_upload:
    #     return {"message": "File already processed", "upload_id": existing_upload.id}

    # 1. Grab the file extension (e.g., ".pdf")
    _, ext = os.path.splitext(file.filename)
    mock_user_id = "123e4567-e89b-12d3-a456-426614174000" 
    
    # 2. Generate a perfectly unique filename
    unique_filename = f"{uuid.uuid4()}{ext}"
    
    try:
        await run_in_threadpool(
            upload_to_supabase_storage,
            bucket="syllabi", # Make sure you created this bucket in Supabase dashboard
            file_path=unique_filename,
            file_bytes=bytes(file_bytes),
            content_type=file.content_type
        )
    except Exception as e:
        print(f"Storage Error: {e}")
        raise HTTPException(status_code=502, detail="Failed to upload file to cloud storage!")

    # 5. Database Transaction
    # The file is safely in the cloud. Now we write the 'PENDING' record.
    # We construct the public URL (or signed URL depending on your bucket privacy settings)
    public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/syllabi/{unique_filename}"

    new_upload = Upload(
        user_id=uuid.UUID(mock_user_id), # Replace with current_user.id
        file_url=public_url,
        file_hash=file_hash,
        status=UploadStatus.PENDING
    )

    session.add(new_upload)
    
    try:
        await session.commit()
        await session.refresh(new_upload)
    except Exception as e:
        await session.rollback()
        # In a perfect system, you would trigger a cleanup of the orphaned S3 file here.
        raise HTTPException(status_code=500, detail="Database transaction failed.")

    # 6. The Producer Handoff (The non-blocking trigger)
    await enqueue_syllabus_job(str(new_upload.id))

    return {
        "message": "Upload accepted and queued for processing!",
        "upload_id": new_upload.id,
        "status": new_upload.status
    }
app.include_router(router)