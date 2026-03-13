"""
Scheme CRUD operations.
Works with MongoDB when available, falls back to in-memory JSON.
"""

import logging
from typing import Optional
from app.db.database import get_db, is_using_memory, get_memory_schemes
from app.models.scheme import Scheme, SchemeListResponse

logger = logging.getLogger(__name__)


async def get_all_schemes() -> list[Scheme]:
    """Get all schemes from database or memory."""
    if is_using_memory():
        raw = get_memory_schemes()
    else:
        db = get_db()
        cursor = db.schemes.find({}, {"_id": 0})
        raw = await cursor.to_list(length=200)

    return [Scheme(**s) for s in raw]


async def get_scheme_by_id(scheme_id: str) -> Optional[Scheme]:
    """Get single scheme by ID."""
    if is_using_memory():
        for s in get_memory_schemes():
            if s.get("id") == scheme_id:
                return Scheme(**s)
        return None
    else:
        db = get_db()
        doc = await db.schemes.find_one({"id": scheme_id}, {"_id": 0})
        return Scheme(**doc) if doc else None


async def filter_schemes(
    category: Optional[str] = None,
    state: Optional[str] = None,
    occupation: Optional[str] = None,
    keyword: Optional[str] = None,
) -> list[Scheme]:
    """Filter schemes by category, state, occupation, or keyword."""
    all_schemes = await get_all_schemes()
    results = all_schemes

    if category:
        cat_lower = category.lower()
        results = [s for s in results if cat_lower in s.category.lower()]

    if state:
        state_lower = state.lower()
        results = [
            s for s in results
            if (
                s.eligibility_rules.state is None
                or s.eligibility_rules.state == "ALL"
                or (isinstance(s.eligibility_rules.state, list) and
                    any(state_lower in st.lower() for st in s.eligibility_rules.state))
                or (isinstance(s.eligibility_rules.state, str) and
                    state_lower in s.eligibility_rules.state.lower())
            )
        ]

    if occupation:
        occ_lower = occupation.lower()
        results = [
            s for s in results
            if (
                s.eligibility_rules.occupation is None
                or (isinstance(s.eligibility_rules.occupation, str) and
                    occ_lower in s.eligibility_rules.occupation.lower())
                or (isinstance(s.eligibility_rules.occupation, list) and
                    any(occ_lower in o.lower() for o in s.eligibility_rules.occupation))
            )
        ]

    if keyword:
        kw_lower = keyword.lower()
        results = [
            s for s in results
            if (
                kw_lower in s.name.lower()
                or kw_lower in s.category.lower()
                or kw_lower in s.benefit.lower()
                or kw_lower in s.ministry.lower()
            )
        ]

    return results


async def get_scheme_categories() -> list[str]:
    """Get unique scheme categories."""
    all_schemes = await get_all_schemes()
    categories = sorted(set(s.category for s in all_schemes))
    return categories


async def seed_schemes_to_db(schemes: list[dict]) -> int:
    """Seed schemes into MongoDB (if available)."""
    if is_using_memory():
        from app.db.database import set_memory_schemes
        set_memory_schemes(schemes)
        logger.info(f"Loaded {len(schemes)} schemes into memory")
        return len(schemes)

    db = get_db()
    # Clear existing and insert fresh
    await db.schemes.delete_many({})
    if schemes:
        await db.schemes.insert_many(schemes)
    logger.info(f"Seeded {len(schemes)} schemes into MongoDB")
    return len(schemes)
