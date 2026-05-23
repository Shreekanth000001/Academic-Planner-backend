from fastapi import FastAPI, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from typing import List

# Import your database dependency and your User model
from database import get_session
from models import User

app = FastAPI(title="AI Academic Planner API")

@app.get("/users/test-dml", response_model=List[User])
async def test_dml_connection(session: AsyncSession = Depends(get_session)):
    """
    Validates SQLModel DML mapping against Prisma's DDL schema.
    """
    try:
        # 1. The Query Builder: Constructs the SQL statement (does not execute it yet)
        statement = select(User).limit(5)
        
        # 2. Execution: Sends the query over the async network pool to PgBouncer
        result = await session.exec(statement)
        
        # 3. Hydration: Parses the raw DB bytes into Python SQLModel/Pydantic objects
        users = result.all()
        
        return users
    
    except Exception as e:
        # If there is a mapping mismatch, the Exception will tell you exactly which column/table failed.
        print(f"CRITICAL DML FAILURE: {e}")
        raise HTTPException(status_code=500, detail=f"Database mapping error. Check server logs.")