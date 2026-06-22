# worker.py
import uuid
from datetime import date,datetime
import fitz
import os
import json

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

async def process_schedule(session, schedule_id,doc_chunks):
    print("gathering schedules")

    full_text = "\n".join(doc_chunks)

    system_promt = """
    You are an academic planner. Review the provided syllabus text.
    Break it down into individual study tasks or topics.
    You MUST return your response as a valid JSON object with a key named "tasks", containing an array of objects.
    Example structure:
    {
        "tasks": [
            {"topic_name": "Introduction to Database Systems", "order_index": 1, "estimated_minutes": 60},
            {"topic_name": "Relational Algebra", "order_index": 2, "estimated_minutes": 90}
        ]
    }"""

    openai_client = AsyncOpenAI(base_url="https://models.inference.ai.azure.com",
                        api_key=settings.GITHUB_PAT_TOKEN)
    

    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type":"json_object"},
        messages=[
            {"role":"system", "content":system_promt},
            {"role":"user","content":full_text}
        ]
    )

    raw_json_string = response.choices[0].message.content

    parsed_json = json.loads(raw_json_string) #type:ignore

    for task in parsed_json.get("tasks",[]):
        new_study_tasks = StudyTask(
            schedule_id = schedule_id,
            topic_name = task.get("topic_name"),
            assigned_date = datetime.now(),
            order_index = task.get("order_index"),
            estimated_minutes = task.get("estimated_minutes"),
            )
        session.add(new_study_tasks)
    await session.commit()
    print(f"Successfully saved {len(parsed_json.get('tasks', []))} tasks to Supabase!")


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
            
            stmt1 = select(Schedule).where(Schedule.upload_id == upload_uuid)

            result1 = await session.execute(stmt1)

            scheduled= result1.scalars().first()

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

            await process_schedule(session,scheduled.id,doc_chunks) #type:ignore

        except Exception as e:
            await session.rollback()
            print("problem in arq:",e)


class WorkerSettings:
    functions = [process_syllabus]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(host="localhost", port=6379)