from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    PROJECT_NAME: str = "AI PDF Assistant API"
    PROJECT_VERSION: str = "0.1.0"

    # SQLite default database URL
    DATABASE_URL: str = "sqlite:///./ai_pdf_assistant.db"

    # JWT Security Configuration
    SECRET_KEY: str = "Enter Your Secret Key"
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
