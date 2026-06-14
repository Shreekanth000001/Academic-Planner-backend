# worker.py
import asyncio
from arq import worker
from arq.connections import RedisSettings
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
import uuid
from datetime import date

# Re-use your database engine and models
from database import engine 
from models import Upload, UploadStatus, Schedule, StudyTask, PlanType, User

async def startup(ctx):
    """
    Runs when the background worker boots up.
    We inject dependencies into the context dictionary (ctx).
    """
    # Define an independent session factory for the worker process
    ctx["session_factory"] = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    print("Background worker initialized successfully.")

async def shutdown(ctx):
    """Runs when the worker safely terminates."""
    print("Background worker shutting down.")


async def process_syllabus(ctx, upload_id: str):
    """
    The Core Task. 
    Downloads, processes (OCR/LLM), and commits the schedule to the DB inside a transaction.
    """
    session_factory = ctx["session_factory"]
    
    async with session_factory() as session:
        # 1. Fetch the Upload Record
        upload_uuid = uuid.UUID(upload_id)
        upload = await session.get(Upload, upload_uuid)
        
        if not upload or upload.status != UploadStatus.PENDING:
            print(f"Aborting: Upload {upload_id} not found or already processed.")
            return

        # 2. Update status to PROCESSING immediately to handle job visibility
        upload.status = UploadStatus.PROCESSING
        await session.commit()
        await session.refresh(upload)

        try:
            # --- ARCHITECTURAL PLACEHOLDER FOR OCR & AZURE OPENAI ---
            # Imagine this takes 20 seconds. It runs completely out-of-band of your API.
            print(f"Processing file from URL: {upload.file_url}")
            await asyncio.sleep(5) # Simulating heavy model/OCR latency
            
            # Simulated structured JSON output from Azure OpenAI
            mock_llm_output = {
                "title": "Systems Programming Core",
                "exam_date": "2026-06-15",
                "tasks": [
                    {"topic_name": "Introduction to POSIX", "assigned_date": "2026-05-26", "order_index": 1, "estimated_minutes": 90},
                    {"topic_name": "Memory Management & mmap", "assigned_date": "2026-05-27", "order_index": 2, "estimated_minutes": 120}
                ]
            }
            # --------------------------------------------------------

            # 3. ATOMIC DATABASE TRANSACTION (All-or-Nothing)
            # Create the Schedule entity
            new_schedule = Schedule(
                user_id=upload.user_id,
                upload_id=upload.id,
                title=mock_llm_output["title"],
                exam_date=date.fromisoformat(mock_llm_output["exam_date"])
            )
            session.add(new_schedule)
            # Flush assigns an ID to new_schedule without committing the transaction yet
            await session.flush() 

            # Map and add the StudyTasks
            for task_data in mock_llm_output["tasks"]:
                task = StudyTask(
                    schedule_id=new_schedule.id,
                    topic_name=task_data["topic_name"],
                    assigned_date=date.fromisoformat(task_data["assigned_date"]),
                    order_index=task_data["order_index"],
                    estimated_minutes=task_data["estimated_minutes"]
                )
                session.add(task)

            # Update upload parent record to COMPLETED
            upload.status = UploadStatus.COMPLETED
            
            # Commit everything simultaneously. If any insert fails, Postgres rolls back the entire state.
            await session.commit()
            print(f"Successfully finalized Schedule {new_schedule.id} for Upload {upload_id}")

        except Exception as e:
            # Error Boundaries: Capture failure, rollback the active transaction, 
            # and flag the upload so the frontend can display an error to the student.
            await session.rollback()
            upload.status = UploadStatus.FAILED
            upload.error_message = str(e)
            await session.commit()
            print(f"Task processing failed for Upload {upload_id}: {e}")


# Worker Configuration Class required by ARQ's CLI
class WorkerSettings:
    functions = [process_syllabus]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(host="localhost", port=6379)