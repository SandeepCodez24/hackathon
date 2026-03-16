import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ATLAS_URL = "mongodb+srv://sandeepcodez24:23AD55%24anDeeP@mlappcluster1.ikzbjb0.mongodb.net/"
DB_NAME = "govscheme"

async def seed():
    from motor.motor_asyncio import AsyncIOMotorClient

    logger.info("🔌 Connecting to MongoDB Atlas...")
    client = AsyncIOMotorClient(ATLAS_URL, serverSelectionTimeoutMS=10000)

    await client.admin.command("ping")
    logger.info("✅ Connected to MongoDB Atlas!")

    db = client[DB_NAME]

    base_dir = Path(__file__).resolve().parent.parent.parent
    schemes = []

    elig_path = base_dir / "schemes_eligibility.json"
    if elig_path.exists():
        with open(elig_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "schemes" in data:
                schemes.extend(data["schemes"])
            elif isinstance(data, list):
                schemes.extend(data)
        logger.info(f"📂 Loaded {len(schemes)} from schemes_eligibility.json")

    part2_path = base_dir / "schemes_part2.json"
    if part2_path.exists():
        with open(part2_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                schemes.extend(data)
            elif isinstance(data, dict) and "schemes" in data:
                schemes.extend(data["schemes"])
        logger.info(f"📂 Total: {len(schemes)} schemes loaded")

    await db.schemes.delete_many({})
    logger.info("🗑️  Cleared existing schemes collection")

    if schemes:
        result = await db.schemes.insert_many(schemes)
        logger.info(f"✅ Inserted {len(result.inserted_ids)} schemes into Atlas")

    count = await db.schemes.count_documents({})
    logger.info(f"📋 Verification: {count} schemes in database")

    pipeline = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    async for doc in db.schemes.aggregate(pipeline):
        logger.info(f"   • {doc['_id']}: {doc['count']} schemes")

    await db.schemes.create_index("id", unique=True)
    await db.schemes.create_index("category")
    await db.schemes.create_index("type")
    logger.info("📇 Created indexes on id, category, type")

    client.close()
    logger.info("🏁 Seeding to Atlas complete!")

if __name__ == "__main__":
    asyncio.run(seed())
