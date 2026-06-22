# worker.py
import uuid
from datetime import date,datetime
import fitz
import os

from openai import AsyncOpenAI
from arq import worker
from arq.connections import RedisSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from supabase import create_client, Client
from sqlalchemy import select

from database import engine 
from models import Upload, UploadStatus, Schedule, StudyTask, PlanType, User, SyllabusChunks
from config import settings

async def startup(ctx):

    ctx["session_factory"] = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    print("Background worker initialized successfully.")

async def shutdown(ctx):

    print("Background worker shutting down.")

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

async def process_schedule(session,doc_chunks):
    print("gathering schedules")

    system_promt="This is a syllabus planner app, user is sending syllabus, divide into 2 week schedules to study."

    openai_client = AsyncOpenAI(base_url="https://models.inference.ai.azure.com",
                        api_key=settings.GITHUB_PAT_TOKEN)
    

    await openai_client.chat.completions.create(
        model="chatgpt-4o-latest",
        response_format={"type":"json_object"},
        messages=[
            {"role":"system", "content":"Hi, i am the system"},
            {"role":"user","content":doc_chunks}
        ]
    )


async def process_syllabus(ctx,upload_id: str):
    session_factory = ctx["session_factory"]

    print("Processing wait bro...", datetime.now())

    async with session_factory() as session:
        try: 
            print("inside try",datetime.now())
            upload_uuid= uuid.UUID(upload_id)
            upload = await session.get(Upload,upload_uuid)

            if not upload:
                return

            stmt = select(Schedule).where(Schedule.upload_id == upload_uuid)

            result = await session.execute(stmt)

            scheduled= result.scalars().first()

            if scheduled:
                 print("schedule:", scheduled.id , "upload: ", upload.id, "time: ", datetime.now())
            else:
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


            print("outside the else statement: ", datetime.now())
            file_url = upload.file_url
            file_id = file_url.split("syllabi/")[-1]
            print("File id:",file_id)
            file_bytes= supabase.storage.from_('syllabi').download(file_id)
            if file_bytes:
                print("Downloaded i guess", datetime.now())

                doc=fitz.open(stream=file_bytes, filetype="pdf")
                extracted_text = ""

                for page in doc:
                    extracted_text += page.get_text() #type:ignore

                if len(extracted_text.strip()) == 0:
                    print("Scanned pdf detected, OCR not supported yet, upload text pdf.")
                    return

                openai_client = AsyncOpenAI(
                    base_url="https://models.inference.ai.azure.com",
                    api_key=settings.GITHUB_PAT_TOKEN
                            )
                
                def chunking_text(text,chunk_size=1000,overlap=200):
                    chunks=[]
                    start=0

                    while start < len(text):
                        end= start + chunk_size
                        chunks.append(text[start:end])
                        start += chunk_size - overlap
                    return chunks

                doc_chunks=chunking_text(extracted_text)

                response = await openai_client.embeddings.create(
                input=doc_chunks,
                model="text-embedding-3-small"
                    )
                
                vectors = [item.embedding for item in response.data]

                print("Saving vectors into Supabase pgvector...")

                for chunk_text,chunk_vector in zip(doc_chunks,vectors):
                    new_memory = SyllabusChunks(
                        upload_id = upload_uuid,
                        text_content = chunk_text,
                        embedding = chunk_vector
                    )
                    session.add(new_memory)
                await session.commit()

                print("chunks extracted!")
                print(f"dock chunk lenght{len(doc_chunks)}")
                print(f"vector lenght{len(vectors)}")
                print(f"1st vector : {vectors[0][:5]}...")
                print("\nThe END!")

            await process_schedule(session,doc_chunks)

        except Exception as e:
            await session.rollback()
            print("problem in arq:",e)


class WorkerSettings:
    functions = [process_syllabus]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(host="localhost", port=6379)