# worker.py
import asyncio
from arq import worker
from arq.connections import RedisSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
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
    ctx["session_factory"] = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    print("Background worker initialized successfully.")

async def shutdown(ctx):
    """Runs when the worker safely terminates."""
    print("Background worker shutting down.")


async def process_syllabus(ctx,upload_id: str):
    session_factory = ctx["session_factory"]

    async with session_factory() as session:
        try: 
            upload_uuid= uuid.UUID(upload_id)
            upload = await session.get(Upload,upload_uuid)

            if not upload:
                return
            
            new_schedule=Schedule(
                user_id=upload.user_id,
                upload_id= upload.id,
                title="Systems Programming Core",
                exam_date= date.fromisoformat("2026-06-15")
            )

            session.add(new_schedule)

            await session.flush()

            upload.status = UploadStatus.COMPLETED

            
            llmoutput = {"tasks": [
                {"topic_name": "Introduction to POSIX", "assigned_date": "2026-05-26", "order_index": 1, "estimated_minutes": 90},
                {"topic_name": "Memory Management & mmap", "assigned_date": "2026-05-27", "order_index": 2, "estimated_minutes": 120}
            ]
            }

            for task in llmoutput["tasks"]:
                new_task=StudyTask(
                schedule_id=new_schedule.id,
                topic_name=task["topic_name"],
                assigned_date= date.fromisoformat(task["assigned_date"]),
                order_index= task["order_index"],
                estimated_minutes= task["estimated_minutes"]
            )
                session.add(new_task)

            await session.commit()
        except Exception as e:
            await session.rollback()
            print("problem in arq:",e)




# Worker Configuration Class required by ARQ's CLI
class WorkerSettings:
    functions = [process_syllabus]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(host="localhost", port=6379)