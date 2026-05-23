# main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import text
from database import get_session

app = FastAPI(title="AI Academic Planner API")

@app.get("/health")
async def health_check(session: AsyncSession = Depends(get_session)):
    """
    Dependency Injection in action: FastAPI automatically calls get_session(),
    passes the session to this function, and executes the `finally` cleanup block
    after the return statement.
    """
    try:
        # We use SQLAlchemy's 'text' construct for raw SQL execution
        result = await session.exec(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        # Log the actual error to your observability stack (e.g., Sentry/Datadog)
        # Return a sanitized 503 to the client.
        print(f"\n🚨 ACTUAL DATABASE ERROR: {repr(e)}\n")
        raise HTTPException(status_code=503, detail="Database connection failed")
    