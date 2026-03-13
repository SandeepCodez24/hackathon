"""
Database seeder — loads scheme data from JSON files into the database.
Run: python -m data.seed_db
"""

import asyncio
import json
import sys
import logging
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import (
    connect_mongodb,
    connect_redis,
    disconnect,
    load_schemes_from_files,
)
from app.db.scheme_orm import seed_schemes_to_db, get_all_schemes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed():
    """Load and seed all scheme data."""
    logger.info("🌱 Starting database seed...")

    # Connect (will fallback to memory if not available)
    await connect_mongodb()

    # Load from JSON files
    schemes = await load_schemes_from_files()
    logger.info(f"📂 Loaded {len(schemes)} schemes from JSON files")

    # Seed to database
    count = await seed_schemes_to_db(schemes)
    logger.info(f"✅ Seeded {count} schemes successfully")

    # Verify
    all_schemes = await get_all_schemes()
    logger.info(f"📋 Verification: {len(all_schemes)} schemes in database")

    # Print categories
    categories = set(s.category for s in all_schemes)
    logger.info(f"📁 Categories ({len(categories)}):")
    for cat in sorted(categories):
        cat_count = len([s for s in all_schemes if s.category == cat])
        logger.info(f"   • {cat}: {cat_count} schemes")

    await disconnect()
    logger.info("🏁 Seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed())
