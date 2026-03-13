"""
Database connection manager.
- MongoDB (via motor) for scheme storage
- Redis for ephemeral sessions (24hr TTL)
- Falls back to in-memory storage if DBs unavailable (hackathon mode)
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# --- MongoDB ---
_mongo_client = None
_mongo_db = None

# --- Redis ---
_redis_client = None

# --- In-memory fallback ---
_in_memory_schemes: list[dict] = []
_in_memory_sessions: dict[str, dict] = {}


def get_mongo_url() -> str:
    return os.getenv("MONGODB_URL", "mongodb+srv://sandeepcodez24:23AD55%24anDeeP@mlappcluster1.ikzbjb0.mongodb.net/")


def get_mongo_db_name() -> str:
    return os.getenv("MONGODB_DB_NAME", "govscheme")


def get_redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


async def connect_mongodb():
    """Connect to MongoDB. Falls back to in-memory if unavailable."""
    global _mongo_client, _mongo_db
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        _mongo_client = AsyncIOMotorClient(get_mongo_url(), serverSelectionTimeoutMS=3000)
        # Test connection
        await _mongo_client.admin.command("ping")
        _mongo_db = _mongo_client[get_mongo_db_name()]
        logger.info("✅ Connected to MongoDB")
        return True
    except Exception as e:
        logger.warning(f"⚠️  MongoDB unavailable ({e}). Using in-memory storage.")
        _mongo_client = None
        _mongo_db = None
        return False


async def connect_redis():
    """Connect to Redis. Falls back to in-memory dict if unavailable."""
    global _redis_client
    try:
        import redis.asyncio as aioredis
        _redis_client = aioredis.from_url(get_redis_url(), decode_responses=True)
        await _redis_client.ping()
        logger.info("✅ Connected to Redis")
        return True
    except Exception as e:
        logger.warning(f"⚠️  Redis unavailable ({e}). Using in-memory sessions.")
        _redis_client = None
        return False


async def disconnect():
    """Clean shutdown of all DB connections."""
    global _mongo_client, _redis_client
    if _mongo_client:
        _mongo_client.close()
        logger.info("MongoDB disconnected")
    if _redis_client:
        await _redis_client.close()
        logger.info("Redis disconnected")


def get_db():
    """Get MongoDB database instance (or None if using in-memory)."""
    return _mongo_db


def get_redis():
    """Get Redis client (or None if using in-memory)."""
    return _redis_client


def is_using_memory() -> bool:
    """Check if we're running in in-memory fallback mode."""
    return _mongo_db is None


# --- In-memory helpers ---

def get_memory_schemes() -> list[dict]:
    return _in_memory_schemes


def set_memory_schemes(schemes: list[dict]):
    global _in_memory_schemes
    _in_memory_schemes = schemes


def get_memory_sessions() -> dict[str, dict]:
    return _in_memory_sessions


async def load_schemes_from_files():
    """Load scheme data from JSON files into in-memory storage."""
    global _in_memory_schemes
    base_dir = Path(__file__).resolve().parent.parent.parent.parent  # hackathon root

    schemes = []

    # Load schemes_eligibility.json
    elig_path = base_dir / "schemes_eligibility.json"
    if elig_path.exists():
        with open(elig_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "schemes" in data:
                schemes.extend(data["schemes"])
            elif isinstance(data, list):
                schemes.extend(data)
        logger.info(f"Loaded {len(schemes)} schemes from schemes_eligibility.json")

    # Load schemes_part2.json
    part2_path = base_dir / "schemes_part2.json"
    if part2_path.exists():
        with open(part2_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                schemes.extend(data)
            elif isinstance(data, dict) and "schemes" in data:
                schemes.extend(data["schemes"])
        logger.info(f"Total schemes after part2: {len(schemes)}")

    _in_memory_schemes = schemes
    return schemes
