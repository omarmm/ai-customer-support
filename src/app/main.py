from fastapi import FastAPI

from src.app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}
