import uuid, time
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from app.database import get_db, ConversationSession, ConversationMessage, StudentProfile, ToolExecutionLog
from app.graph.workflow import run_orchestrator
from app.tools.registry import registry
from app.auth import verify_token, get_optional_user, get_current_user_id
from app.persistence import (
    resolve_user_id,
    get_or_create_session,
    save_user_message,
    save_assistant_message,
    log_tool_execution,
    update_session_metadata,
    load_conversation_history,
    commit_transaction,
)
from app.services.analytics import compute_student_analytics
from app.database import AsyncSessionLocal

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    student_id: Optional[str] = None
    student_profile: Optional[Dict[str, Any]] = None


class ToolResultOut(BaseModel):
    tool_name: str
    success: bool
    output: Dict[str, Any]
    confidence: float
    execution_time_ms: int
    error: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    response: str
    tool_used: Optional[str] = None
    tool_result: Optional[ToolResultOut] = None
    extracted_params: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    workflow_steps: List[str] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionCreateRequest(BaseModel):
    student_id: Optional[str] = None


# ── Health ─────────────────────────────────────────────────────────────────────
@router.get("/health")
async def health():
    return {"status": "healthy", "tools_loaded": len(registry.names()), "timestamp": datetime.utcnow().isoformat()}


@router.get("/")
async def root():
    return {"name": "EduOrchestrator API", "version": "3.0.0", "docs": "/docs"}


# ── Tools ──────────────────────────────────────────────────────────────────────
@router.get("/tools")
async def list_tools():
    return {
        "total": len(registry.names()),
        "tools": registry.schemas(),
        "by_category": {cat: [t.name for t in tools] for cat, tools in registry.by_category().items()},
    }


@router.get("/tools/{tool_name}")
async def get_tool(tool_name: str):
    tool = registry.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    return tool.get_schema()


# ── Sessions ───────────────────────────────────────────────────────────────────
@router.post("/sessions")
async def create_session(
    req: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    session_id = str(uuid.uuid4())
    session, _ = await get_or_create_session(db, session_id, user_id)
    committed = await commit_transaction(db)

    if not committed:
        raise HTTPException(status_code=500, detail="Failed to create session")

    return {"session_id": session_id, "user_id": user_id, "created_at": datetime.utcnow()}


@router.get("/sessions")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """List all conversation sessions for the authenticated user."""
    result = await db.execute(
        select(ConversationSession)
        .where(ConversationSession.user_id == user_id)
        .where(ConversationSession.is_archived == False)
        .order_by(ConversationSession.updated_at.desc())
        .limit(50)
    )
    sessions = result.scalars().all()
    return {
        "sessions": [
            {
                "session_id": s.id,
                "user_id": s.user_id,
                "title": s.title,
                "primary_subject": s.primary_subject,
                "message_count": s.message_count,
                "tools_used": s.tools_used or [],
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ]
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(
        select(ConversationSession).where(
            ConversationSession.id == session_id,
            ConversationSession.user_id == user_id,  # Enforce ownership
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    msgs = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.session_id == session_id)
        .order_by(ConversationMessage.created_at)
    )
    messages = msgs.scalars().all()

    return {
        "session_id": session_id,
        "user_id": session.user_id,
        "title": session.title,
        "message_count": session.message_count,
        "messages": [{"role": m.role, "content": m.content, "tool_used": m.tool_used, "created_at": m.created_at} for m in messages],
    }


# ── Chat — main orchestration endpoint ─────────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_optional_user),  # Optional auth — falls back to dev user
):
    # ── Step 1: Resolve user_id (handles dev-mode user provisioning) ──────────
    user_id = await resolve_user_id(db, user, req.student_id)

    # ── Step 2: Normalize session_id to valid UUID ────────────────────────────
    raw_session_id = req.session_id or ""
    try:
        uuid.UUID(raw_session_id)
        session_id = raw_session_id
    except (ValueError, AttributeError):
        session_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, raw_session_id or str(uuid.uuid4())))

    # ── Step 3: Get or create session + load history ─────────────────────────
    db_ok = True
    try:
        session, is_new = await get_or_create_session(db, session_id, user_id)

        # Load conversation history for context
        history = await load_conversation_history(db, session_id, limit=10)

        # Save user message
        user_msg_id = await save_user_message(db, session_id, user_id, req.message)

        # Commit pre-chat writes (session + user message)
        pre_committed = await commit_transaction(db)
        if not pre_committed:
            print("[chat] WARNING: Pre-chat commit failed, continuing without DB")
            db_ok = False
    except Exception as db_err:
        print(f"[chat] WARNING: DB pre-chat error (non-fatal): {db_err}")
        try:
            await db.rollback()
        except Exception:
            pass
        db_ok = False
        history = []

    # ── Step 4: Run LangGraph pipeline (always runs regardless of DB) ────────
    t_start = time.time()
    try:
        final_state = await run_orchestrator(
            message=req.message,
            session_id=session_id,
            student_id=user_id,
            conversation_history=history,
            student_profile=req.student_profile or {},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestration error: {e}")

    elapsed_ms = int((time.time() - t_start) * 1000)
    tool_name = final_state.get("selected_tool")
    tool_output = final_state.get("tool_output", {})
    confidence = final_state.get("tool_confidence", 0.0)
    formatted = final_state.get("final_response", "")
    exec_success = final_state.get("execution_success", False)

    # ── Step 5: Save assistant message + tool log (post-chat) ────────────────
    assistant_msg_id = str(uuid.uuid4())  # fallback if DB write fails

    if db_ok:
        try:
            # Save assistant message with full metadata
            assistant_msg_id = await save_assistant_message(
                db,
                session_id=session_id,
                user_id=user_id,
                content=formatted,
                tool_used=tool_name,
                tool_params=final_state.get("validated_params"),
                tool_response=tool_output if exec_success else None,
                confidence=confidence,
                intent=final_state.get("intent"),
                subject=final_state.get("subject"),
                difficulty=final_state.get("difficulty"),
                mood=final_state.get("mood"),
                workflow_steps=final_state.get("workflow_steps", []),
                latency_ms=elapsed_ms,
            )

            # Update session metadata (title, subject, tools_used)
            await update_session_metadata(
                session,
                tool_name=tool_name,
                subject=final_state.get("subject"),
                title=req.message,
            )

            # Log tool execution (linked to assistant message_id)
            if tool_name:
                await log_tool_execution(
                    db,
                    session_id=session_id,
                    user_id=user_id,
                    message_id=assistant_msg_id,  # CRITICAL: links tool log to message
                    tool_name=tool_name,
                    tool_category=registry.get(tool_name).category if registry.get(tool_name) else None,
                    input_params=final_state.get("validated_params"),
                    output=tool_output if exec_success else None,
                    confidence=confidence,
                    success=exec_success,
                    error_message=final_state.get("error_message") if not exec_success else None,
                    execution_time_ms=final_state.get("execution_time_ms"),
                    retry_count=final_state.get("retry_count", 0),
                    fallback_tools=final_state.get("fallback_tools"),
                )

            # Commit all post-chat writes
            post_committed = await commit_transaction(db)
            if post_committed:
                print(f"[chat] SUCCESS: Session={session_id}, UserMsg + AssistantMsg + ToolLog committed")
                
                # Background Update Analytics
                async def update_analytics_task():
                    async with AsyncSessionLocal() as bg_session:
                        try:
                            await compute_student_analytics(bg_session, user_id)
                            await bg_session.commit()
                        except Exception as e:
                            print(f"[analytics_task] Failed: {e}")
                
                background_tasks.add_task(update_analytics_task)
            else:
                print("[chat] WARNING: Post-chat commit failed")
        except Exception as db_err:
            print(f"[chat] WARNING: DB post-chat error: {db_err}")
            try:
                await db.rollback()
            except Exception:
                pass

    # ── Step 6: Build response ────────────────────────────────────────────────
    tool_result = None
    if tool_name and tool_output:
        tool_result = ToolResultOut(
            tool_name=tool_name, success=exec_success, output=tool_output,
            confidence=confidence, execution_time_ms=final_state.get("execution_time_ms", 0),
            error=final_state.get("error_message") if not exec_success else None,
        )

    return ChatResponse(
        session_id=session_id, message_id=assistant_msg_id, response=formatted,
        tool_used=tool_name, tool_result=tool_result,
        extracted_params=final_state.get("validated_params"),
        confidence=confidence,
        workflow_steps=final_state.get("workflow_steps", []),
    )


# ── User profile ───────────────────────────────────────────────────────────────
@router.get("/me")
async def get_profile(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    user: dict = Depends(verify_token),
):
    result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        # Auto-create profile for authenticated user
        profile = StudentProfile(
            user_id=user_id,
            email=user.get("email"),
            full_name=user.get("user_metadata", {}).get("full_name") if isinstance(user.get("user_metadata"), dict) else None,
        )
        db.add(profile)
        await db.commit()
    return {
        "user_id": profile.user_id, "email": profile.email, "full_name": profile.full_name,
        "learning_level": profile.learning_level, "total_sessions": profile.total_sessions,
        "total_messages": profile.total_messages, "token_balance": profile.token_balance,
        "streak_days": profile.streak_days,
    }

@router.get("/me/analytics")
async def get_analytics(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Get the active analytics for the strictly logged in user, computes on demand if missing."""
    from app.database import StudentAnalytics
    result = await db.execute(select(StudentAnalytics).where(StudentAnalytics.user_id == user_id))
    analytics = result.scalar_one_or_none()
    
    if not analytics:
        # compute on demand if nothing exists yet
        analytics = await compute_student_analytics(db, user_id)
        await db.commit()
        
    return {
        "total_tool_calls": analytics.total_tool_calls,
        "favourite_tool": analytics.favourite_tool,
        "favourite_subject": analytics.favourite_subject,
        "avg_confidence": analytics.avg_confidence,
        "tools_breakdown": analytics.tools_breakdown,
        "subjects_breakdown": analytics.subjects_breakdown,
        "difficulty_progression": analytics.difficulty_progression,
        "weekly_activity": analytics.weekly_activity,
        "last_computed_at": analytics.last_computed_at.isoformat() if analytics.last_computed_at else None,
    }

@router.post("/me/analytics/compute")
async def force_compute_analytics(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Force recompute analytics for debugging/manual trigger."""
    analytics = await compute_student_analytics(db, user_id)
    await db.commit()
    
    return {"message": "Analytics computed and updated successfully."}
