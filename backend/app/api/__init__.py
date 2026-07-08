from fastapi import APIRouter

from app.api.rest_sessions import router as sessions_router
from app.api.rest_resume import router as resume_router
from app.api.ws_interview import router as ws_router

api_router = APIRouter()
api_router.include_router(sessions_router, prefix="/api")
api_router.include_router(resume_router, prefix="/api")
api_router.include_router(ws_router)

__all__ = ["api_router"]
