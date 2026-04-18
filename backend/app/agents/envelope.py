"""Response normalization.

Wraps every tool output into a uniform envelope. After the reasoner /
observer upgrade, `meta` also carries the reasoning trace, candidate
list, and observation so the envelope is fully auditable:

    {
        "tool": "flashcards",
        "arguments": {...},               # NEW: validated params sent to the tool
        "result": {...},                  # tool's raw data
        "meta": {
            "reasoning": {
                "thought": "...",
                "intent": "...",
                "constraints": [...],
                "confidence": 0.9,
                "source": "rule"|"llm"
            },
            "candidates": [{"tool": ..., "score": ..., "reason": ...}],
            "observation": "...",
            "quality_ok": true,
            "difficulty": "medium",
            "mastery_level": 6,
            "emotion": "focused",
            "teaching_style": "visual",
            "adaptation_reasons": [...],
            "execution_time_ms": 412,
            "confidence": 0.83,
            "retry_count": 0,
            "success": true
        },
        "presentation": "markdown for the chat UI",
        "clarification_needed": null
    }

Backward-compat: callers still find `data` in the envelope (alias of result),
so the existing routes.py / frontend don't break.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_envelope(
    tool_name: str,
    data: Dict[str, Any],
    presentation: str,
    plan: Optional[Dict[str, Any]],
    execution_time_ms: int,
    confidence: float,
    retry_count: int,
    success: bool,
    arguments: Optional[Dict[str, Any]] = None,
    reasoning: Optional[Dict[str, Any]] = None,
    candidates: Optional[List[Dict[str, Any]]] = None,
    observation: Optional[str] = None,
    quality_ok: Optional[bool] = None,
    error: Optional[str] = None,
    clarification: Optional[str] = None,
) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "execution_time_ms": execution_time_ms,
        "confidence": round(confidence, 3),
        "retry_count": retry_count,
        "success": success,
    }
    if plan:
        meta["difficulty"] = plan.get("difficulty")
        meta["mastery_level"] = plan.get("mastery_level")
        meta["emotion"] = plan.get("emotion")
        meta["teaching_style"] = plan.get("teaching_style")
        meta["adaptation_reasons"] = plan.get("adaptation_reasons", [])
    if reasoning:
        meta["reasoning"] = reasoning
    if candidates:
        meta["candidates"] = candidates
    if observation is not None:
        meta["observation"] = observation
    if quality_ok is not None:
        meta["quality_ok"] = quality_ok
    if error:
        meta["error"] = error

    return {
        "tool": tool_name,
        "arguments": arguments or {},
        "result": data or {},
        "data": data or {},           # backward-compat alias
        "meta": meta,
        "presentation": presentation,
        "clarification_needed": clarification,
    }
