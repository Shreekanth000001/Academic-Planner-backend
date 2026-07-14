from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):

    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY:str
    GITHUB_PAT_TOKEN:str
    CLERK_WEBHOOK_SECRET:str
    STRIPE_SECRET_KEY:str
    STRIPE_PRICE_ID:str
    STRIPE_WEBHOOK_SECRET:str

    model_config = SettingsConfigDict(env_file=".env",extra="ignore")

settings = Settings() # type: ignore
