"""LangGraph Workflow — EduOrchestrator Brain.

The compiled graph IS the supervisor. Conditional edges control all
sequencing, retry, and recovery.

Flow:

  START
    → context_analyzer
    → reasoner                 (ReAct-style thought — runs before selection)
    → tool_selector            (hybrid ranker + schema-filter + LLM pick)
    → parameter_extractor
    → inference                (personalization + rule-based fill)
    → schema_validator
        ├─ VALID   → tool_executor
        │              ├─ SUCCESS → observer
        │              │             ├─ quality_ok  → response_formatter → mood → END
        │              │             └─ quality_bad → error_handler
        │              └─ FAIL    → error_handler
        └─ INVALID → error_handler

  error_handler emits `recovery_action`:
    "repair_params" → schema_validator
    "clarify"       → clarification → response_formatter → END
    "switch_tool"   → parameter_extractor
    "give_up"       → response_formatter → END
"""
from langgraph.graph import StateGraph, END

from app.graph.state import OrchestratorState
from app.agents.context_analyzer import context_analyzer_node
from app.agents.reasoner import reasoner_node
from app.agents.tool_selector import tool_selector_node
from app.agents.parameter_extractor import parameter_extractor_node
from app.agents.observer import observer_node
from app.agents.mood_reflection import mood_reflection_node
from app.agents.agents import (
    inference_node,
    schema_validator_node,
    tool_executor_node,
    response_formatter_node,
    error_handler_node,
    clarification_node,
)
from app.config import settings


# ── Routing conditions ────────────────────────────────────────────────────────

def route_after_validation(state: OrchestratorState) -> str:
    if state.get("is_valid", False):
        return "tool_executor"
    if state.get("retry_count", 0) >= settings.MAX_RETRIES:
        return "response_formatter"
    return "error_handler"


def route_after_execution(state: OrchestratorState) -> str:
    """SUCCESS → observer | FAIL → error_handler | retries exhausted → formatter."""
    if state.get("execution_success", False):
        return "observer"
    if state.get("retry_count", 0) >= settings.MAX_RETRIES:
        return "response_formatter"
    return "error_handler"


def route_after_observer(state: OrchestratorState) -> str:
    """GOOD output → formatter | BAD output → error_handler for recovery."""
    if state.get("quality_ok", True):
        return "response_formatter"
    if state.get("retry_count", 0) >= settings.MAX_RETRIES:
        return "response_formatter"
    return "error_handler"


def route_after_error(state: OrchestratorState) -> str:
    action = state.get("recovery_action", "give_up")
    if state.get("retry_count", 0) >= settings.MAX_RETRIES:
        return "response_formatter"
    if action == "repair_params":
        return "schema_validator"
    if action == "clarify":
        return "clarification"
    if action == "switch_tool":
        return "parameter_extractor"
    return "response_formatter"


# ── Build ─────────────────────────────────────────────────────────────────────

def build_workflow() -> StateGraph:
    workflow = StateGraph(OrchestratorState)

    workflow.add_node("context_analyzer", context_analyzer_node)
    workflow.add_node("reasoner", reasoner_node)
    workflow.add_node("tool_selector", tool_selector_node)
    workflow.add_node("parameter_extractor", parameter_extractor_node)
    workflow.add_node("inference", inference_node)
    workflow.add_node("schema_validator", schema_validator_node)
    workflow.add_node("tool_executor", tool_executor_node)
    workflow.add_node("observer", observer_node)
    workflow.add_node("response_formatter", response_formatter_node)
    workflow.add_node("mood_reflection", mood_reflection_node)
    workflow.add_node("error_handler", error_handler_node)
    workflow.add_node("clarification", clarification_node)

    workflow.set_entry_point("context_analyzer")

    workflow.add_edge("context_analyzer", "reasoner")
    workflow.add_edge("reasoner", "tool_selector")
    workflow.add_edge("tool_selector", "parameter_extractor")
    workflow.add_edge("parameter_extractor", "inference")
    workflow.add_edge("inference", "schema_validator")

    workflow.add_conditional_edges(
        "schema_validator",
        route_after_validation,
        {
            "tool_executor": "tool_executor",
            "error_handler": "error_handler",
            "response_formatter": "response_formatter",
        },
    )

    workflow.add_conditional_edges(
        "tool_executor",
        route_after_execution,
        {
            "observer": "observer",
            "error_handler": "error_handler",
            "response_formatter": "response_formatter",
        },
    )

    workflow.add_conditional_edges(
        "observer",
        route_after_observer,
        {
            "response_formatter": "response_formatter",
            "error_handler": "error_handler",
        },
    )

    workflow.add_conditional_edges(
        "error_handler",
        route_after_error,
        {
            "schema_validator": "schema_validator",
            "parameter_extractor": "parameter_extractor",
            "clarification": "clarification",
            "response_formatter": "response_formatter",
        },
    )

    workflow.add_edge("clarification", "response_formatter")
    workflow.add_edge("response_formatter", "mood_reflection")
    workflow.add_edge("mood_reflection", END)

    return workflow


_compiled_workflow = None


def get_workflow():
    global _compiled_workflow
    if _compiled_workflow is None:
        graph = build_workflow()
        _compiled_workflow = graph.compile()
    return _compiled_workflow


async def run_orchestrator(
    message: str,
    session_id: str,
    student_id: str,
    conversation_history: list = None,
    student_profile: dict = None,
) -> dict:
    """Main entry point: run the full LangGraph orchestration pipeline.
    Returns the final state dict including `response_envelope`.
    """
    workflow = get_workflow()
    windowed_history = (conversation_history or [])[-5:]

    initial_state: OrchestratorState = {
        "session_id": session_id,
        "student_id": student_id,
        "raw_message": message,
        "conversation_history": windowed_history,
        "student_profile": student_profile or {},

        "intent": "",
        "subject": "",
        "difficulty": "",
        "mood": "",
        "keywords": [],

        "reasoning": {},

        "selected_tool": "",
        "tool_confidence": 0.0,
        "fallback_tools": [],
        "tool_candidates": [],

        "extracted_params": {},
        "inferred_params": {},
        "personalization_plan": {},

        "validated_params": {},
        "validation_errors": [],
        "is_valid": False,

        "tool_output": {},
        "execution_success": False,
        "execution_time_ms": 0,

        "observation": "",
        "quality_ok": True,
        "quality_reason": "",
        "suggested_recovery": "",

        "formatted_response": "",
        "response_envelope": {},

        "error_message": "",
        "retry_count": 0,
        "recovery_action": "",
        "clarification_needed": None,

        "workflow_steps": [],
        "final_response": "",
    }

    final_state = await workflow.ainvoke(initial_state)
    return final_state
