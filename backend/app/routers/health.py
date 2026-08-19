"""Health/root endpoint."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root():
    return {"service": "NexusCRM", "status": "ok"}
