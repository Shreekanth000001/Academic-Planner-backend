import asyncio
import uuid
from database import engine, AsyncSession # Make sure this imports your pure SQLAlchemy session
from models import User

async def seed_user():
    print("Connecting to Supabase Postgres...")
    # Using the exact async context manager we just learned about
    async with AsyncSession(engine) as session:
        # The exact ID your main.py is trying to use
        mock_id = uuid.UUID("11111111-2222-3333-4444-555555555555") 
        
        new_user = User(
            id=mock_id,
            email="critic@founder-startup.com",
            clerk_id="mock_clerk_123"
        )
        
        session.add(new_user)
        
        try:
            await session.commit()
            print(f"SUCCESS: Inserted user {mock_id} into Postgres.")
        except Exception as e:
            print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(seed_user())