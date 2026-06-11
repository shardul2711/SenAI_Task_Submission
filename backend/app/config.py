import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "crm_intelligence"
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "Shardul@27"
    
    OPENAI_API_KEY: str = ""
    
    JWT_SECRET: str = "8f9b2d86a7d7efb4e073c683b54d6f0f5b9d3c5f8e02d6b38c2e9b1a2d5f8c6e"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
