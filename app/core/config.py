from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    PROJECT_NAME: str = "AI PDF Assistant API"
    PROJECT_VERSION: str = "0.1.0"

    # SQLite default database URL
    DATABASE_URL: str = "sqlite:///./ai_pdf_assistant.db"

    # JWT Security Configuration
    SECRET_KEY: str = "57f89d6e4e70c9d6f8e4a04d9b0a4d6c8e4a04d9b0a4d6c8e4a04d9b0a4d6c8e"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Gemini API Configuration
    GEMINI_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
