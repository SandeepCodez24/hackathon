"""
FastAPI main application entry point.
GovScheme WhatsApp Chatbot — Backend Server
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import connect_mongodb, connect_redis, disconnect, load_schemes_from_files
from app.db.scheme_orm import seed_schemes_to_db, get_all_schemes
from app.api.schemes import router as schemes_router
from app.api.session_api import router as session_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("🚀 Starting GovScheme Backend...")

    # Connect databases (gracefully falls back to in-memory)
    mongo_ok = await connect_mongodb()
    redis_ok = await connect_redis()

    # Load and seed scheme data
    schemes = await load_schemes_from_files()
    count = await seed_schemes_to_db(schemes)
    logger.info(f"📋 {count} schemes loaded and ready")

    mode = "MongoDB + Redis" if (mongo_ok and redis_ok) else "In-Memory (hackathon mode)"
    logger.info(f"💾 Storage mode: {mode}")
    logger.info("✅ GovScheme Backend ready!")

    yield

    # Shutdown
    await disconnect()
    logger.info("👋 GovScheme Backend stopped")


app = FastAPI(
    title="GovScheme WhatsApp Chatbot API",
    description=(
        "Government Scheme Recommendation System — "
        "AI-powered eligibility matching for 78+ Indian government schemes. "
        "WhatsApp-first, multi-language, voice-enabled."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(schemes_router)
app.include_router(session_router)


@app.get("/", tags=["health"])
async def root():
    """Health check endpoint."""
    all_schemes = await get_all_schemes()
    return {
        "status": "ok",
        "service": "GovScheme WhatsApp Chatbot API",
        "version": "1.0.0",
        "schemes_loaded": len(all_schemes),
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Detailed health check."""
    from app.db.database import is_using_memory, get_redis
    return {
        "status": "healthy",
        "storage": "in-memory" if is_using_memory() else "mongodb",
        "sessions": "in-memory" if get_redis() is None else "redis",
    }
