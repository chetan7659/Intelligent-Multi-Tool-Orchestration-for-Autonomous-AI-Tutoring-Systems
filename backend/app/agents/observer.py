"""Observer / Reflection node.

Runs AFTER tool execution. Decides whether the output is usable or whether
recovery should be triggered.

Rule-based checks run FIRST (cheap and definitive):
  - execution_success == False → fail
  - tool_output is empty / not a dict → fail
  - tool_output looks like an LLM mock response → fail
  - required response keys are missing or empty → fail

Only if rule-based checks pass AND the output looks thin does the LLM
judge get invoked. This keeps 90%+ of cases purely rule-based.

Outputs:
  observation:        short description of what happened
  quality_ok:         bool
  quality_reason:     why it passed or failed
  suggested_recovery: "retry_same_tool" | "switch_tool" | "clarify" | "give_up" | "none"
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.graph.state import OrchestratorState
from app.tools.registry import registry
from app.agents.llm_client import get_llm_client
from app.agents.logger import info, warn, append_step, STAGE_OBSERVER


# ── Rule-based checks ─────────────────────────────────────────────────────────

# Signals that the LLM fell back to the mock response in llm_client.py
_MOCK_SIGNALS = [
    ("mock", True),
]
_MOCK_STRINGS = [
    "please configure GROQ_API_KEY",
    '"mock": true',
]


# Per-tool minimum viable response signatures. If any of these keys is
# present with a non-empty value, the output is probably real.
_EXPECTED_KEYS: Dict[str, List[str]] = {
    "flashcards":          ["cards", "flashcards"],
    "note_maker":          ["note_sections", "summary"],
    "concept_explainer":   ["explanation", "simple_definition", "detailed_explanation"],
    "quiz_me":             ["questions"],
    "mock_test":           ["questions"],
    "summary_generator":   ["executive_summary", "summary", "key_points"],
    "mind_map":            ["central_node", "nodes"],
    "step_by_step_solver": ["steps"],
    "mnemonic_generator":  ["mnemonics"],
    "direct_chat_responder": ["response"],
}


def _looks_mock(output: Dict[str, Any]) -> bool:
    """Detect the llm_client.py mock response shape."""
    for key, val in _MOCK_SIGNALS:
        if output.get(key) == val:
            return True
    raw = output.get("raw_response", "")
    if isinstance(raw, str) and any(s in raw for s in _MOCK_STRINGS):
        return True
    return False


def _has_expected_keys(tool_name: str, output: Dict[str, Any]) -> bool:
    expected = _EXPECTED_KEYS.get(tool_name)
    if not expected:
        # Unknown tool — be lenient, accept any non-empty dict
        return bool(output)
    return any(bool(output.get(k)) for k in expected)


def _rule_check(
    tool_name: str,
    output: Dict[str, Any],
    success: bool,
    error: str,
) -> Dict[str, Any]:
    """Returns dict with quality_ok, observation, reason, recovery."""
    if not success:
        return {
            "quality_ok": False,
            "observation": f"tool '{tool_name}' reported failure",
            "quality_reason": error or "execution_success=False",
            "suggested_recovery": "switch_tool",
        }

    if not isinstance(output, dict) or not output:
        return {
            "quality_ok": False,
            "observation": f"tool '{tool_name}' returned no data",
            "quality_reason": "empty or non-dict output",
            "suggested_recovery": "retry_same_tool",
        }

    if _looks_mock(output):
        return {
            "quality_ok": False,
            "observation": "LLM client returned a mock response",
            "quality_reason": "GROQ_API_KEY likely not configured or API call failed",
            "suggested_recovery": "give_up",  # no point retrying; it's config
        }

    if not _has_expected_keys(tool_name, output):
        return {
            "quality_ok": False,
            "observation": f"tool '{tool_name}' output is missing expected keys",
            "quality_reason": f"none of {_EXPECTED_KEYS.get(tool_name, [])} present",
            "suggested_recovery": "retry_same_tool",
        }

    # Size heuristic: suspiciously small responses deserve a second look
    total_chars = sum(
        len(str(v)) for v in output.values()
    )
    if total_chars < 80:
        # Passed structural checks but output feels thin — leave decision
        # to LLM judge (if enabled) or accept.
        return {
            "quality_ok": True,
            "observation": f"tool '{tool_name}' returned a small but structurally valid response",
            "quality_reason": f"total_chars={total_chars} (below threshold 80)",
            "suggested_recovery": "none",
            "_thin": True,
        }

    return {
        "quality_ok": True,
        "observation": f"tool '{tool_name}' returned a valid response",
        "quality_reason": f"structure ok, total_chars={total_chars}",
        "suggested_recovery": "none",
    }


# ── LLM judge (optional, only when rule-based is uncertain) ───────────────────

_JUDGE_PROMPT = """You are quality-checking the output of an educational tool.

Student asked: "{message}"
Tool used: {tool_name}
Tool output (abridged):
{output_preview}

Is this output useful and relevant to what the student asked?

Respond with ONLY JSON:
{{
  "useful": true | false,
  "reason": "one short sentence"
}}
"""


async def _llm_judge(
    message: str,
    tool_name: str,
    output: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    preview = json.dumps(output, default=str)[:800]
    prompt = _JUDGE_PROMPT.format(
        message=message, tool_name=tool_name, output_preview=preview,
    )
    llm = get_llm_client()
    raw = await llm.generate(prompt, max_tokens=128, temperature=0.0)

    cleaned = raw.replace("```json", "").replace("```", "").strip()
    start = cleaned.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(cleaned)):
        if cleaned[i] == "{":
            depth += 1
        elif cleaned[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


# ── Node ──────────────────────────────────────────────────────────────────────

async def observer_node(state: OrchestratorState) -> OrchestratorState:
    """Rule-first, LLM-fallback quality check on tool output."""
    tool_name = state.get("selected_tool", "")
    output = state.get("tool_output", {}) or {}
    success = state.get("execution_success", False)
    error = state.get("error_message", "") or ""

    result = _rule_check(tool_name, output, success, error)

    # If rule-based passed but output looked thin, optionally invoke LLM judge.
    # To keep latency low we only do this for high-stakes tools AND only if
    # the tool output isn't huge (which would blow the judge prompt budget).
    is_thin = result.pop("_thin", False)
    if result["quality_ok"] and is_thin and tool_name in {
        "concept_explainer", "note_maker", "summary_generator"
    }:
        judge = await _llm_judge(
            message=state.get("raw_message", ""),
            tool_name=tool_name,
            output=output,
        )
        if judge and judge.get("useful") is False:
            result = {
                "quality_ok": False,
                "observation": f"LLM judge: output not useful for '{tool_name}'",
                "quality_reason": judge.get("reason", ""),
                "suggested_recovery": "retry_same_tool",
            }

    update = {
        **state,
        "observation": result["observation"],
        "quality_ok": result["quality_ok"],
        "quality_reason": result["quality_reason"],
        "suggested_recovery": result["suggested_recovery"],
    }

    logger_fn = info if result["quality_ok"] else warn
    return append_step(update, logger_fn(
        STAGE_OBSERVER,
        f"quality_ok={result['quality_ok']}: {result['observation']}",
        reason=result["quality_reason"],
        suggested_recovery=result["suggested_recovery"],
    ))
