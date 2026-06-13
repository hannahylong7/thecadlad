from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import init_db, close_db
from app.routes.sessions import router as sessions_router
from app.core.config import settings

import logging

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="CAD Agent API",
    description="Agentic CAD modeling via CadQuery + GPT-5.4 with human-in-the-loop approval",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_router)


@app.get("/health")
async def health():
    from app.models.orm import Session
    try:
        await Session.all().count()
        db_status = "ok"
    except Exception:
        db_status = "error"
 
    status = "ok" if db_status == "ok" else "degraded"
    return {
        "status": status,
        "model": settings.model,
        "database": db_status,
    }