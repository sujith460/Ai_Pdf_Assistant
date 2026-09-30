from app.routers.auth import router as auth_router
from app.routers.materials import router as materials_router
from app.routers.users import router as users_router

__all__ = ["users_router", "auth_router", "materials_router"]
