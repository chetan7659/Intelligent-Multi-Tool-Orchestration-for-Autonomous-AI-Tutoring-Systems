from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, DateTime, Text, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ARRAY, TIMESTAMP
from datetime import datetime
import uuid
from app.config import settings

DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=settings.DEBUG, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(PG_UUID(as_uuid=False), nullable=False, unique=True, index=True)
    email = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    learning_level = Column(String, default="beginner", nullable=False)
    emotional_state = Column(String, default="neutral", nullable=False)
    teaching_style = Column(String, default="direct", nullable=False)
    preferred_subjects = Column(ARRAY(String), default=[], nullable=False)
    tool_usage_stats = Column(JSONB, default={}, nullable=False)
    total_sessions = Column(Integer, default=0, nullable=False)
    total_messages = Column(Integer, default=0, nullable=False)
    streak_days = Column(Integer, default=0, nullable=False)
    last_active_at = Column(TIMESTAMP(timezone=True), nullable=True)
    token_balance = Column(Integer, default=100, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"
    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(PG_UUID(as_uuid=False), nullable=False, index=True)
    title = Column(Text, nullable=True)
    primary_subject = Column(Text, nullable=True)
    message_count = Column(Integer, default=0, nullable=False)
    tools_used = Column(ARRAY(String), default=[], nullable=False)   # text[] NOT json
    is_archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(PG_UUID(as_uuid=False), nullable=False, index=True)
    user_id = Column(PG_UUID(as_uuid=False), nullable=False, index=True)
    role = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    tool_used = Column(Text, nullable=True)
    tool_params = Column(JSONB, nullable=True)
    tool_response = Column(JSONB, nullable=True)
    confidence = Column(Float, nullable=True)
    intent = Column(Text, nullable=True)
    subject = Column(Text, nullable=True)
    difficulty = Column(Text, nullable=True)
    mood = Column(Text, nullable=True)
    workflow_steps = Column(ARRAY(String), nullable=True)   # text[] NOT json
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False)


class ToolExecutionLog(Base):
    __tablename__ = "tool_execution_logs"
    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(PG_UUID(as_uuid=False), nullable=False, index=True)
    user_id = Column(PG_UUID(as_uuid=False), nullable=False, index=True)
    message_id = Column(PG_UUID(as_uuid=False), nullable=True)
    tool_name = Column(Text, nullable=False, index=True)
    tool_category = Column(Text, nullable=True)
    input_params = Column(JSONB, nullable=True)
    output = Column(JSONB, nullable=True)
    confidence = Column(Float, nullable=True)
    fallback_tools = Column(ARRAY(String), nullable=True)   # text[] NOT json
    retry_count = Column(Integer, default=0, nullable=False)
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False)


class StudentAnalytics(Base):
    __tablename__ = "student_analytics"
    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(PG_UUID(as_uuid=False), nullable=False, unique=True)
    total_tool_calls = Column(Integer, default=0, nullable=False)
    favourite_tool = Column(Text, nullable=True)
    favourite_subject = Column(Text, nullable=True)
    avg_confidence = Column(Float, nullable=True)
    tools_breakdown = Column(JSONB, default={}, nullable=False)
    subjects_breakdown = Column(JSONB, default={}, nullable=False)
    difficulty_progression = Column(JSONB, default={}, nullable=False)
    weekly_activity = Column(JSONB, default={}, nullable=False)
    last_computed_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False)


async def get_db():
    """Yield an async DB session. Routes handle commits explicitly
    via persistence.commit_transaction(). We only rollback on
    unhandled exceptions that propagate out of the route."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db():
    # Don't auto-create tables — schema is managed in Supabase directly
    pass

