import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    JWT_SECRET: str
    DATABASE_URL: str = "gatekeeper_saas.db"
    YOUR_DOMAIN: str = "http://localhost:8000"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"

settings = Settings()