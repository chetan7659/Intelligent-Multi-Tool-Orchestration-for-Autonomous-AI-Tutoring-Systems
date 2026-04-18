from typing import Any, Optional, List, Dict, Annotated
from typing_extensions import TypedDict
import operator


class OrchestratorState(TypedDict, total=False):
    # Input
    session_id: str
    student_id: str
    raw_message: str
    conversation_history: List[Dict[str, str]]
    student_profile: Dict[str, Any]

    # Agent 1: Context Analyzer outputs
    intent: str
    subject: str
    difficulty: str
    mood: str
    keywords: List[str]

    # Reasoner output (ReAct-style thought)
    reasoning: Dict[str, Any]

    # Agent 2: Tool Selector outputs
    selected_tool: str
    tool_confidence: float
    fallback_tools: List[str]
    tool_candidates: List[Dict[str, Any]]

    # Agent 3: Parameter Extractor outputs
    extracted_params: Dict[str, Any]
    inferred_params: Dict[str, Any]
    personalization_plan: Dict[str, Any]

    # Agent 4: Schema Validator outputs
    validated_params: Dict[str, Any]
    validation_errors: List[str]
    is_valid: bool

    # Agent 5: Tool Executor outputs
    tool_output: Dict[str, Any]
    execution_success: bool
    execution_time_ms: int

    # Observer outputs (reflection layer)
    observation: str
    quality_ok: bool
    quality_reason: str
    suggested_recovery: str

    # Agent 6: Response Formatter outputs
    formatted_response: str
    response_envelope: Dict[str, Any]

    # Error Handler outputs
    error_message: str
    retry_count: int
    recovery_action: str          # "repair_params" | "clarify" | "switch_tool" | "give_up"

    # Clarifier outputs
    clarification_needed: Optional[str]

    # Workflow tracking
    workflow_steps: Annotated[List[str], operator.add]
    final_response: str
