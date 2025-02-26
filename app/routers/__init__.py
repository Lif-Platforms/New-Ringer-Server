from fastapi import APIRouter
from .main import main_router

# Create router instance
router = APIRouter()

# Include routers
router.include_router(main_router, tags=["main"])