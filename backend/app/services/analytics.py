from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from app.database import StudentAnalytics, ToolExecutionLog, ConversationMessage

async def compute_student_analytics(db: AsyncSession, user_id: str) -> StudentAnalytics:
    """
    Computes all analytics for a given student from their historical interactions
    and updates/inserts the corresponding row in student_analytics.
    """
    # 1. Total Tool Calls & Tools Breakdown
    tools_result = await db.execute(
        select(ToolExecutionLog.tool_name, func.count(ToolExecutionLog.id))
        .where(ToolExecutionLog.user_id == user_id)
        .group_by(ToolExecutionLog.tool_name)
    )
    tools_counts = tools_result.all()
    
    total_tool_calls = sum(count for _, count in tools_counts)
    tools_breakdown = {name: count for name, count in tools_counts if name}
    favourite_tool = max(tools_breakdown, key=tools_breakdown.get) if tools_breakdown else None

    # 2. Average Confidence
    conf_result = await db.execute(
        select(func.avg(ToolExecutionLog.confidence))
        .where(ToolExecutionLog.user_id == user_id)
    )
    avg_confidence = conf_result.scalar_one_or_none() or 0.0

    # 3. Subjects Breakdown & Favourite Subject
    subjects_result = await db.execute(
        select(ConversationMessage.subject, func.count(ConversationMessage.id))
        .where(ConversationMessage.user_id == user_id)
        .where(ConversationMessage.subject.isnot(None))
        .group_by(ConversationMessage.subject)
    )
    subjects_counts = subjects_result.all()
    subjects_breakdown = {subj: count for subj, count in subjects_counts if subj}
    favourite_subject = max(subjects_breakdown, key=subjects_breakdown.get) if subjects_breakdown else None

    # 4. Difficulty Progression
    diff_result = await db.execute(
        select(ConversationMessage.difficulty, func.count(ConversationMessage.id))
        .where(ConversationMessage.user_id == user_id)
        .where(ConversationMessage.difficulty.isnot(None))
        .group_by(ConversationMessage.difficulty)
    )
    diff_counts = diff_result.all()
    difficulty_progression = {diff: count for diff, count in diff_counts if diff}

    # 5. Weekly Activity
    # Get counts per day for the last 7 days
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    # Cast created_at to Date to group by day
    activity_result = await db.execute(
        select(func.date(ConversationMessage.created_at).label("day"), func.count(ConversationMessage.id))
        .where(ConversationMessage.user_id == user_id)
        .where(ConversationMessage.created_at >= seven_days_ago)
        .group_by("day")
    )
    activity_counts = activity_result.all()
    weekly_activity = {str(day): count for day, count in activity_counts if day}

    # 6. Fetch existing or create new StudentAnalytics row
    sa_result = await db.execute(
        select(StudentAnalytics).where(StudentAnalytics.user_id == user_id)
    )
    analytics = sa_result.scalar_one_or_none()

    if not analytics:
        analytics = StudentAnalytics(user_id=user_id)
        db.add(analytics)

    # 7. Update row
    analytics.total_tool_calls = total_tool_calls
    analytics.favourite_tool = favourite_tool
    analytics.favourite_subject = favourite_subject
    analytics.avg_confidence = round(avg_confidence, 2)
    analytics.tools_breakdown = tools_breakdown
    analytics.subjects_breakdown = subjects_breakdown
    analytics.difficulty_progression = difficulty_progression
    analytics.weekly_activity = weekly_activity
    analytics.last_computed_at = datetime.now(timezone.utc)

    # Flush but don't commit - caller handles commit
    await db.flush()

    return analytics
