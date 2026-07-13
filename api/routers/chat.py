import uuid
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from core.security import get_current_user
from database import get_session
from models import User, Upload, SyllabusChunks
from config import settings

router = APIRouter(prefix="/chat", tags=["Chat"])

class ChatRequest(BaseModel):
    upload_id:str
    question:str
    history: List[Dict[str, str]] = []

@router.post("")
async def chat_with_syllabus(
    payload: ChatRequest,
    current_user : User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    
    upload_uuid = uuid.UUID(payload.upload_id)

    stmt = select(Upload).where(
        Upload.id == upload_uuid,
        Upload.user_id == current_user.id
    )

    result = await session.execute(stmt)
    if not result.scalars().first():
        raise HTTPException(status_code=403, detail="Unauthorized access to this document")

    search_query = payload.question

    openai_client = AsyncOpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=settings.GITHUB_PAT_TOKEN
    )

    if payload.history:
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in payload.history[-4:]])

        rewrite_prompt = f"""
        Given the following chat history and the user's new question, rewrite the user's question into a standalone question that can be understood without the history.
        Do NOT answer the question. Just rewrite it.
        
        Chat History:
        {history_text}
        """

        rewrite_response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": rewrite_prompt},
                {"role": "user", "content": payload.question}
            ]
        )
        search_query = rewrite_response.choices[0].message.content
        print(f"Original: {payload.question} | Rewritten for Vector DB: {search_query}")

    embed_response = await openai_client.embeddings.create(
        input = [payload.question],
        model="text-embedding-3-small"
    )
    question_vector = embed_response.data[0].embedding


    vector_stmt = (
        select(SyllabusChunks.text_content)
        .where(SyllabusChunks.upload_id == upload_uuid)
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

    final_messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": system_prompt}
    ]
    
    # 2. Use explicit string literals so the type checker trusts us
    for msg in payload.history:
        if msg["role"] == "ai":
            final_messages.append({"role": "assistant", "content": msg["content"]})
        else:
            final_messages.append({"role": "user", "content": msg["content"]})
            
    # Append the newest raw question
    final_messages.append({"role": "user", "content": payload.question})

    chat_response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=final_messages
    )

    final_answer = chat_response.choices[0].message.content

    return {"answer": final_answer}