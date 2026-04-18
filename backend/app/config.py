from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "EduOrchestrator"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/eduorchestrator"

    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""   # Project Settings → API → JWT Secret

    HUGGINGFACE_API_TOKEN: str = ""
    HF_MODEL_ID: str = "meta-llama/Llama-3.1-8B-Instruct"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-pro"

    ALLOWED_ORIGINS: list = ["http://localhost:3000"]
    CONFIDENCE_THRESHOLD: float = 0.70
    MAX_RETRIES: int = 3

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
