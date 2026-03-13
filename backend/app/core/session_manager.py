"""
Session Manager — Redis-backed session CRUD with 24hr TTL.
Falls back to in-memory dict when Redis is unavailable.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from app.models.session import Session, SessionState, CitizenProfile
from app.db.database import get_redis, get_memory_sessions

logger = logging.getLogger(__name__)

SESSION_TTL = 86400  # 24 hours in seconds


class SessionManager:
    """Manage citizen conversation sessions."""

    @staticmethod
    async def get_or_create(session_id: str, channel: str = "whatsapp") -> Session:
        """Load existing session or create a new one."""
        existing = await SessionManager.get(session_id)
        if existing:
            return existing

        # Create new session
        session = Session(
            session_id=session_id,
            channel=channel,
            state=SessionState.GREETING,
        )

        # Initialize with all scheme IDs as candidates
        from app.db.scheme_orm import get_all_schemes
        all_schemes = await get_all_schemes()
        session.candidates = [s.id for s in all_schemes]

        await SessionManager.save(session)
        logger.info(f"Created new session: {session_id} with {len(session.candidates)} candidates")
        return session

    @staticmethod
    async def get(session_id: str) -> Optional[Session]:
        """Get session by ID."""
        redis = get_redis()
        if redis:
            data = await redis.get(f"session:{session_id}")
            if data:
                return Session(**json.loads(data))
            return None
        else:
            # In-memory fallback
            sessions = get_memory_sessions()
            if session_id in sessions:
                return Session(**sessions[session_id])
            return None

    @staticmethod
    async def save(session: Session):
        """Save session to Redis or memory."""
        session.updated_at = datetime.utcnow()
        data = session.model_dump(mode="json")

        redis = get_redis()
        if redis:
            await redis.set(
                f"session:{session.session_id}",
                json.dumps(data, default=str),
                ex=SESSION_TTL,
            )
        else:
            sessions = get_memory_sessions()
            sessions[session.session_id] = data

    @staticmethod
    async def delete(session_id: str):
        """Delete a session."""
        redis = get_redis()
        if redis:
            await redis.delete(f"session:{session_id}")
        else:
            sessions = get_memory_sessions()
            sessions.pop(session_id, None)

    @staticmethod
    async def update_profile(session_id: str, **kwargs) -> Session:
        """Update profile fields and save."""
        session = await SessionManager.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        for key, value in kwargs.items():
            if hasattr(session.profile, key):
                setattr(session.profile, key, value)

        await SessionManager.save(session)
        return session

    @staticmethod
    async def add_question(session_id: str, question_id: str) -> Session:
        """Record that a question was asked."""
        session = await SessionManager.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.questions_asked.append(question_id)
        session.question_count += 1
        session.current_question = question_id

        await SessionManager.save(session)
        return session
