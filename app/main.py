from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.database import Base, engine
import app.models  # Ensures models are registered with Base.metadata before create_all
from app.routers import auth_router, materials_router, users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for database initialization on startup."""
    # Create database tables if they do not exist
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="FastAPI Backend Foundation for AI PDF Assistant",
    lifespan=lifespan,
)

# Include routers
app.include_router(users_router)
app.include_router(auth_router)
app.include_router(materials_router)


@app.get("/", tags=["Health Check"])
def health_check() -> dict[str, str]:
    """Health check endpoint to verify that the API is running."""
    return {"message": "AI PDF Assistant API is running"}
