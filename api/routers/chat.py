from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from openai import AsyncOpenAI

from core.security import get_current_user
from database import get_session
from models import User, Upload, SyllabusChunks
from config import settings

router = APIRouter(prefix="/chat", tags=["Chat"])

class ChatRequest(BaseModel):
    upload_id:str
    question:str

@router.post("")
async def chat_with_syllabus(
    payload: ChatRequest,
    current_user : User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    stmt = select(Upload).where(
        Upload.id == payload.upload_id,
        Upload.user_id == current_user.id
    )

    result = await session.execute(stmt)
    if not result.scalars().first():
        raise HTTPException(status_code=403, detail="Unauthorized access to this document")
    
    openai_client = AsyncOpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=settings.GITHUB_PAT_TOKEN
    )

    embed_response = await openai_client.embeddings.create(
        input = [payload.question],
        model="text-embedding-3-small"
    )
    question_vector = embed_response.data[0].embedding

    vector_stmt = (
        select(SyllabusChunks.text_content)
        .where(SyllabusChunks.upload_id == [payload.upload_id])
        .order_by(SyllabusChunks.embedding.cosine_distance(question_vector))
               .limit(3)
    )

    vector_result = await session.execute(vector_stmt)
    top_chunks = vector_result.scalars().all()

    if not top_chunks:
        return {"answer": "I couldn't find any information in the syllabus to answer that."}

    context_string = "\n\n---\n\n".join(top_chunks)
    
    system_prompt = f"""
    You are an academic assistant. Answer the user's question using ONLY the provided syllabus context. 
    If the answer is not in the context, say "I don't know based on the provided syllabus."
    
    CONTEXT:
    {context_string}
    """

    chat_response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload.question}
        ]
    )

    final_answer = chat_response.choices[0].message.content

    return {"answer": final_answer}