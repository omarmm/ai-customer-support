from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.rag.chunking.composition import build_chunking_service

settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.chunking_service = build_chunking_service(settings)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}
