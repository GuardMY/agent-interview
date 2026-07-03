import logging
import logging.handlers
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import settings
from app.db.database import async_session_factory, init_db
from app.db.seed import seed_job_positions, seed_question_bank

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Persistent log file with rotation
_log_dir = Path(settings.log_dir)
_log_dir.mkdir(parents=True, exist_ok=True)
_file_handler = logging.handlers.RotatingFileHandler(
    _log_dir / "interview.log",
    maxBytes=settings.log_max_bytes,
    backupCount=settings.log_backup_count,
    encoding="utf-8",
)
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
logging.getLogger().addHandler(_file_handler)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Starting AI Interview Agent server...")
    await init_db()

    # Seed question bank and job positions from JSON (idempotent)
    async with async_session_factory() as seed_db:
        await seed_question_bank(seed_db)
        await seed_job_positions(seed_db)

    logger.info("Database initialized.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="AI Interview Agent",
    description="Autonomous technical interviewer API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server (localhost:3000) and any other origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "version": "1.0.0"}
