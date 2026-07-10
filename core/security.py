from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models import User

token_auth_scheme = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(token_auth_scheme),
    session: AsyncSession = Depends(get_session)
) -> User:
    raw_token = credentials.credentials
    
    try:
        unverified_payload = jwt.decode(raw_token, options={"verify_signature": False})
        clerk_id = unverified_payload.get("sub")
        
        if not clerk_id:
            raise ValueError("Token missing 'sub' claim")
            
        stmt = select(User).where(User.clerk_id == clerk_id)
        result = await session.execute(stmt)
        db_user = result.scalar_one_or_none()
        
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="User identity not found in local database"
            )
            
        return db_user

    except HTTPException:
        raise
    except Exception as e:
        print(f"Auth Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )