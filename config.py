# config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Supabase provides a transaction pooler URL (port 6543) and a direct URL (port 5432).
    # For serverless FastAPI, use the transaction pooler URL.
    # Replace 'postgresql://' with 'postgresql+asyncpg://' to use the async driver.
    DATABASE_URL: str 
    SUPABASE_URL: str 
    SUPABASE_SERVICE_KEY: str 
    
    # Model config reads from a .env file locally
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()