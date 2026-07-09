from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

token_auth_scheme = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(token_auth_scheme)) -> str:
    raw_token = credentials.credentials
    
    try:

        unverified_payload = jwt.decode(raw_token, options={"verify_signature": False})
        
        # The 'sub' (Subject) claim in a JWT is the User's ID
        user_id = unverified_payload.get("sub")
        
        if not user_id:
            raise ValueError("Token missing 'sub' claim")
            
        print(f"Intercepted Request from User: {user_id}")
        return user_id

    except Exception as e:
        print(f"Auth Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )