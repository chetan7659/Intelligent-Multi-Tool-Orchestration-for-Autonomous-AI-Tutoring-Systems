"""
Persistence layer — all database writes for the chat pipeline.

Handles:
  - Session creation / retrieval
  - User message insert
  - Assistant message insert (with orchestration metadata)
  - Tool execution log insert (linked via message_id)
  - Dev-mode user provisioning (creates auth.users row if missing)

Every function uses explicit commits and comprehensive error logging
so failures are never silent.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import (
    AsyncSessionLocal,
    ConversationSession,
    ConversationMessage,
    ToolExecutionLog,
)


# ── Dev-mode user provisioning ────────────────────────────────────────────────

_DEV_USER_ID = "00000000-0000-0000-0000-000000000001"
_DEV_EMAIL = "dev@localhost"

_dev_user_ensured = False  # module-level flag to avoid repeated checks


async def ensure_dev_user(db: AsyncSession) -> str:
    """
    Ensure a dev-mode user exists in auth.users so FK constraints pass.
    This is ONLY used when no real JWT is present (local development).
    Returns the dev user UUID string.
    """
    global _dev_user_ensured
    if _dev_user_ensured:
        return _DEV_USER_ID

    try:
        result = await db.execute(
            text("SELECT id FROM auth.users WHERE id = :uid"),
            {"uid": _DEV_USER_ID},
        )
        if result.scalar_one_or_none() is None:
            # Insert a minimal row into auth.users for dev mode.
            # The postgres superuser connection can write to auth schema.
            await db.execute(
                text("""
                    INSERT INTO auth.users (
                        instance_id, id, aud, role,
                        email, encrypted_password,
                        email_confirmed_at, created_at, updated_at,
                        raw_app_meta_data, raw_user_meta_data,
                        confirmation_token, recovery_token, email_change_token_new,
                        email_change
                    ) VALUES (
                        '00000000-0000-0000-0000-000000000000',
                        :uid, 'authenticated', 'authenticated',
                        :email, '',
                        NOW(), NOW(), NOW(),
                        '{"provider":"email","providers":["email"]}'::jsonb,
                        '{"full_name":"Dev User"}'::jsonb,
                        '', '', '', ''
                    )
                    ON CONFLICT (id) DO NOTHING
                """),
                {"uid": _DEV_USER_ID, "email": _DEV_EMAIL},
            )
            await db.commit()
            print(f"[persistence] Created dev user in auth.users: {_DEV_USER_ID}")
        _dev_user_ensured = True
    except Exception as e:
        await db.rollback()
        print(f"[persistence] WARNING: Could not ensure dev user: {e}")
        # Try alternative: disable FK checks for this session
        try:
            await db.execute(text("SET session_replication_role = 'replica'"))
            print("[persistence] Disabled FK checks via replication_role (dev fallback)")
            _dev_user_ensured = True
        except Exception as e2:
            print(f"[persistence] WARNING: Could not disable FK checks: {e2}")

    return _DEV_USER_ID


# ── Resolve user_id ───────────────────────────────────────────────────────────

async def resolve_user_id(
    db: AsyncSession,
    jwt_payload: Optional[dict],
    fallback_student_id: Optional[str],
) -> str:
    """
    Determine the user_id to use for DB writes.
    - If JWT is present and valid, use `sub` (already in auth.users).
    - Otherwise, ensure the dev user exists and use the dev UUID.
    """
    if jwt_payload and jwt_payload.get("sub") and not jwt_payload.get("dev_mode"):
        return jwt_payload["sub"]

    # Dev mode — ensure the dev user row exists
    return await ensure_dev_user(db)


# ── Session management ────────────────────────────────────────────────────────

async def get_or_create_session(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> Tuple[ConversationSession, bool]:
    """
    Retrieve an existing session or create a new one.
    Returns (session_obj, is_new).
    """
    result = await db.execute(
        select(ConversationSession).where(ConversationSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    if session:
        return session, False

    session = ConversationSession(id=session_id, user_id=user_id)
    db.add(session)
    await db.flush()  # flush to get the row in-transaction (triggers fire on commit)
    print(f"[persistence] Created session {session_id} for user {user_id}")
    return session, True


# ── Message persistence ──────────────────────────────────────────────────────

async def save_user_message(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    content: str,
) -> str:
    """
    Insert the user's message into conversation_messages.
    Returns the generated message_id (UUID string).
    """
    msg_id = str(uuid.uuid4())
    msg = ConversationMessage(
        id=msg_id,
        session_id=session_id,
        user_id=user_id,
        role="user",
        content=content,
    )
    db.add(msg)
    await db.flush()
    print(f"[persistence] Saved user message {msg_id}")
    return msg_id


async def save_assistant_message(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    content: str,
    *,
    tool_used: Optional[str] = None,
    tool_params: Optional[Dict[str, Any]] = None,
    tool_response: Optional[Dict[str, Any]] = None,
    confidence: Optional[float] = None,
    intent: Optional[str] = None,
    subject: Optional[str] = None,
    difficulty: Optional[str] = None,
    mood: Optional[str] = None,
    workflow_steps: Optional[List[str]] = None,
    latency_ms: Optional[int] = None,
) -> str:
    """
    Insert the assistant's response into conversation_messages
    with full orchestration metadata.
    Returns the generated message_id (UUID string).
    """
    msg_id = str(uuid.uuid4())
    msg = ConversationMessage(
        id=msg_id,
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        content=content,
        tool_used=tool_used,
        tool_params=tool_params,
        tool_response=tool_response,
        confidence=confidence,
        intent=intent,
        subject=subject,
        difficulty=difficulty,
        mood=mood,
        workflow_steps=workflow_steps or [],
        latency_ms=latency_ms,
    )
    db.add(msg)
    await db.flush()
    print(f"[persistence] Saved assistant message {msg_id}")
    return msg_id


# ── Tool execution log ────────────────────────────────────────────────────────

async def log_tool_execution(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    message_id: str,
    *,
    tool_name: str,
    tool_category: Optional[str] = None,
    input_params: Optional[Dict[str, Any]] = None,
    output: Optional[Dict[str, Any]] = None,
    confidence: Optional[float] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    execution_time_ms: Optional[int] = None,
    retry_count: int = 0,
    fallback_tools: Optional[List[str]] = None,
) -> str:
    """
    Insert a tool execution log linked to the assistant message_id.
    Returns the generated log_id (UUID string).
    """
    log_id = str(uuid.uuid4())
    log = ToolExecutionLog(
        id=log_id,
        session_id=session_id,
        user_id=user_id,
        message_id=message_id,  # CRITICAL: links to the assistant message
        tool_name=tool_name,
        tool_category=tool_category,
        input_params=input_params,
        output=output,
        confidence=confidence,
        success=success,
        error_message=error_message,
        execution_time_ms=execution_time_ms,
        retry_count=retry_count,
        fallback_tools=fallback_tools,
    )
    db.add(log)
    await db.flush()
    print(f"[persistence] Saved tool log {log_id} (tool={tool_name}, linked to msg={message_id})")
    return log_id


# ── Session metadata update ──────────────────────────────────────────────────

async def update_session_metadata(
    session: ConversationSession,
    *,
    tool_name: Optional[str] = None,
    subject: Optional[str] = None,
    title: Optional[str] = None,
):
    """
    Update session-level metadata (tools_used, primary_subject, title).
    Note: message_count is handled by the DB trigger (trg_message_count),
    so we do NOT manually increment it here.
    """
    if tool_name:
        tools_used = list(session.tools_used or [])
        if tool_name not in tools_used:
            tools_used.append(tool_name)
        session.tools_used = tools_used

    if not session.primary_subject and subject:
        session.primary_subject = subject

    if not session.title and title:
        session.title = title[:60]

    session.updated_at = datetime.now(timezone.utc)


# ── Load conversation history ────────────────────────────────────────────────

async def load_conversation_history(
    db: AsyncSession,
    session_id: str,
    limit: int = 10,
) -> List[Dict[str, str]]:
    """
    Load the last N messages for the session, oldest-first.
    Returns list of {"role": ..., "content": ...} dicts.
    """
    result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.session_id == session_id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(limit)
    )
    messages = result.scalars().all()
    return [{"role": m.role, "content": m.content} for m in reversed(messages)]


# ── Full commit helper ────────────────────────────────────────────────────────

async def commit_transaction(db: AsyncSession) -> bool:
    """
    Explicitly commit the current transaction.
    Returns True on success, False on failure.
    """
    try:
        await db.commit()
        print("[persistence] Transaction committed successfully")
        return True
    except Exception as e:
        print(f"[persistence] ERROR: Commit failed: {e}")
        await db.rollback()
        return False
