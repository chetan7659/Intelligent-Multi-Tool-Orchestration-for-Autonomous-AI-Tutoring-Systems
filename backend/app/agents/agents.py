"""Core pipeline nodes.

Public function names are preserved so graph/workflow.py imports keep working:
  - inference_node          (personalization + param filling)
  - schema_validator_node   (uses the new JSON-Schema-aware validator)
  - tool_executor_node      (unchanged behavior, added structured logs)
  - response_formatter_node (now emits the normalized envelope)
  - error_handler_node      (repair → clarify → fallback tool → give up)
  - clarification_node      (NEW: generates clarification question)
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.graph.state import OrchestratorState
from app.tools.registry import registry
from app.agents.llm_client import get_llm_client

from app.agents.personalization import (
    build_plan,
    apply_plan_to_params,
    PersonalizationPlan,
)
from app.agents.validator import validate_and_repair, generate_clarification
from app.agents.envelope import build_envelope
from app.agents.logger import (
    info, warn, error as log_error, append_step, append_steps,
    STAGE_PERSONALIZE, STAGE_VALIDATE, STAGE_EXECUTE,
    STAGE_FORMAT, STAGE_ERROR, STAGE_CLARIFY,
)
from app.agents.reasoning_engine import infer_parameters


# ── Inference / Personalization ───────────────────────────────────────────────

def _build_plan_from_state(state: OrchestratorState) -> PersonalizationPlan:
    """Extract mastery/emotion/style inputs from the available state.

    Priority: explicit student_profile fields → context analyzer output →
    sensible defaults.
    """
    profile = state.get("student_profile", {}) or {}

    mastery = (
        profile.get("mastery_level")
        or profile.get("learning_level")
        or 5
    )
    emotion = (
        profile.get("emotional_state")
        or profile.get("emotion")
        or state.get("mood")
        or "neutral"
    )
    style = (
        profile.get("teaching_style")
        or profile.get("learning_style")
        or "direct"
    )
    return build_plan(mastery_level=mastery, emotion=emotion, teaching_style=style)


async def inference_node(state: OrchestratorState) -> OrchestratorState:
    """Merges: legacy rule-based inference + deterministic personalization plan.

    - reasoning_engine.infer_parameters handles topic/subject/prompt backfills
      from keywords and message text (still useful for generic tools).
    - personalization.build_plan/apply_plan_to_params handles the
      mastery/emotion/style-driven knobs per task spec.
    """
    tool_name = state.get("selected_tool", "concept_explainer")
    tool = registry.get(tool_name)
    if not tool:
        update = {**state, "inferred_params": state.get("extracted_params", {})}
        return append_step(update, warn(
            STAGE_PERSONALIZE,
            f"tool '{tool_name}' not found — passing extracted params through",
        ))

    schema = tool.get_schema()
    profile = state.get("student_profile", {}) or {}
    context = {
        "subject": state.get("subject", "general"),
        "difficulty": state.get("difficulty", "intermediate"),
        "mood": state.get("mood", "neutral"),
        "keywords": state.get("keywords", []),
    }

    # Step 1: deterministic personalization plan — this OWNS difficulty,
    # depth, count, note_style per task spec, so it must run FIRST so the
    # rule-based layer below can't clobber it.
    plan = _build_plan_from_state(state)
    personalized = apply_plan_to_params(
        plan, dict(state.get("extracted_params") or {}), schema
    )

    # Step 2: rule-based fills (topic/subject/prompt from keywords etc.) —
    # these only touch fields the plan didn't set.
    inferred, reasons = infer_parameters(
        message=state.get("raw_message", ""),
        extracted=personalized,
        schema=schema,
        context=context,
        profile=profile,
    )

    update = {
        **state,
        "inferred_params": inferred,
        "personalization_plan": plan.to_dict(),
    }
    entries = [
        info(
            STAGE_PERSONALIZE,
            f"plan: mastery L{plan.mastery_level}, emotion={plan.emotion}, "
            f"style={plan.teaching_style} → difficulty={plan.difficulty}, "
            f"depth={plan.desired_depth}, count={plan.item_count}",
            reasons=plan.adaptation_reasons,
        ),
        info(
            STAGE_PERSONALIZE,
            f"merged plan + context fills → {len(inferred)} params; "
            f"rule-based reasons: {len(reasons)}",
        ),
    ]
    return append_steps(update, entries)


# ── Schema Validator ──────────────────────────────────────────────────────────

async def schema_validator_node(state: OrchestratorState) -> OrchestratorState:
    """JSON-Schema-aware validation with auto-repair."""
    tool_name = state.get("selected_tool", "concept_explainer")
    tool = registry.get(tool_name)

    params = dict(state.get("inferred_params") or state.get("extracted_params") or {})

    if not tool:
        update = {
            **state,
            "validated_params": params,
            "validation_errors": [f"Tool '{tool_name}' not found"],
            "is_valid": False,
        }
        return append_step(update, log_error(
            STAGE_VALIDATE, f"tool '{tool_name}' not found"
        ))

    schema = tool.get_schema()
    repaired, errors, actions, is_valid = validate_and_repair(params, schema)

    update = {
        **state,
        "validated_params": repaired,
        "validation_errors": errors,
        "is_valid": is_valid,
    }

    if is_valid and actions:
        entry = info(
            STAGE_VALIDATE,
            f"VALID after {len(actions)} auto-repair(s)",
            repairs=actions,
        )
    elif is_valid:
        entry = info(STAGE_VALIDATE, "VALID (no repairs needed)")
    else:
        entry = warn(
            STAGE_VALIDATE,
            f"INVALID: {len(errors)} unresolved error(s); {len(actions)} repair(s) applied",
            errors=errors, repairs=actions,
        )
    return append_step(update, entry)


# ── Tool Executor ─────────────────────────────────────────────────────────────

async def tool_executor_node(state: OrchestratorState) -> OrchestratorState:
    """Execute the selected tool."""
    tool_name = state.get("selected_tool", "concept_explainer")
    params = state.get("validated_params", {})
    retry_count = state.get("retry_count", 0)

    tool = registry.get(tool_name)
    if not tool:
        update = {
            **state,
            "execution_success": False,
            "tool_output": {},
            "error_message": f"Tool '{tool_name}' not found in registry",
        }
        return append_step(update, log_error(
            STAGE_EXECUTE, f"tool '{tool_name}' not found"
        ))

    llm_client = get_llm_client()
    start_ms = int(time.time() * 1000)

    try:
        result = await tool.execute(params, llm_client=llm_client)
        elapsed = int(time.time() * 1000) - start_ms
        update = {
            **state,
            "tool_output": result.data,
            "execution_success": result.success,
            "execution_time_ms": elapsed,
            "error_message": result.error or "",
        }
        entry = info(
            STAGE_EXECUTE,
            f"{tool_name} executed in {elapsed}ms, success={result.success}",
        )
        return append_step(update, entry)
    except Exception as e:
        elapsed = int(time.time() * 1000) - start_ms
        update = {
            **state,
            "tool_output": {},
            "execution_success": False,
            "execution_time_ms": elapsed,
            "error_message": str(e),
            "retry_count": retry_count + 1,
        }
        return append_step(update, log_error(
            STAGE_EXECUTE, f"{tool_name} raised: {str(e)[:120]}",
            retry_count=retry_count + 1,
        ))


# ── Response Formatter (builds envelope + presentation string) ────────────────

_PRESENTATION_TEMPLATES = {
    "quiz_me": "🧠 **{title}** | {num_questions} questions | Difficulty: {difficulty}",
    "mock_test": "📝 **{test_title}** | {total_questions} questions | Time: {time_limit_minutes} min",
    "flashcards": "🃏 **{topic} Flashcards** | {total_cards} cards",
    "concept_explainer": "💡 **{concept}** — {simple_definition}",
    "note_maker": "📝 **{title}** ({note_taking_style})\n\n{summary}",
    "summary_generator": "📄 **Summary: {topic}**\n\n{executive_summary}",
    "quick_compare": "⚖️ **{topic_a} vs {topic_b}** — comparison ready.",
    "step_by_step_solver": "🔢 **Problem solved step-by-step.**",
    "mnemonic_generator": "🧠 **Memory aid** for {items} — {count} mnemonic(s) generated.",
    "anchor_chart_maker": "📊 **Anchor Chart: {title}** — {count} sections.",
    "mind_map": "🗺️ **Mind Map** centered on '{central_node}'.",
    "concept_visualizer": "🎨 **Visual: {title}** — {description}",
    "debate_speech_generator": "🎤 **{topic} — {side}** ({estimated_duration})",
    "pronunciation_coach": "🗣️ Pronunciation guide for {count} word(s).",
    "rhyme_rap_composer": "🎵 **{topic}** rap/song — {style}",
    "quick_prompts": "💭 {count} creative prompts on '{theme}'.",
    "visual_story_builder": "📖 **{title}** — {num_panels}-panel story.",
    "podcast_maker": "🎙️ **{episode_title}** — {duration_minutes} min.",
    "simulation_generator": "⚗️ **{simulation_name}** — {description}",
    "slide_deck_generator": "📊 **{presentation_title}** — {num_slides} slides.",
    "timeline_designer": "📅 **{timeline_title}** — {count} events.",
    "direct_chat_responder": "{response}",
}


def _safe_format(template: str, data: Dict[str, Any]) -> str:
    # Flatten list counts so templates can use {count}, {<key>_count}
    kwargs: Dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, (str, int, float)):
            kwargs[k] = v
        elif isinstance(v, list):
            kwargs[f"{k}_count"] = len(v)
            kwargs.setdefault("count", len(v))
        elif isinstance(v, dict):
            text = v.get("text") or v.get("title") or ""
            if text:
                kwargs[k] = text

    # Tool-specific little adjustments
    if "items" in data and isinstance(data["items"], list):
        kwargs["items"] = ", ".join(str(x) for x in data["items"][:3])

    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return "✅ Your content is ready."


async def response_formatter_node(state: OrchestratorState) -> OrchestratorState:
    """Produce the final response envelope and presentation string."""
    tool_name = state.get("selected_tool", "") or "unknown"
    tool_output = state.get("tool_output", {}) or {}
    arguments = state.get("validated_params", {}) or {}
    confidence = state.get("tool_confidence", 0.0)
    success = state.get("execution_success", False)
    plan = state.get("personalization_plan") or {}
    reasoning = state.get("reasoning") or None
    candidates = state.get("tool_candidates") or None
    observation = state.get("observation") or None
    quality_ok = state.get("quality_ok")
    exec_ms = state.get("execution_time_ms", 0)
    retries = state.get("retry_count", 0)
    err = state.get("error_message") or None
    clarification = state.get("clarification_needed") or None

    if success and tool_output and quality_ok is not False:
        template = _PRESENTATION_TEMPLATES.get(tool_name, "✅ **{tool_name}** ready")
        presentation = _safe_format(template, {**tool_output, "tool_name": tool_name})
    elif clarification:
        presentation = clarification
    elif err:
        presentation = (
            f"I couldn't complete that because: {err}. "
            "Could you share a bit more detail and I'll try again?"
        )
    elif quality_ok is False:
        presentation = (
            "I ran the request but the output didn't look quite right. "
            "Could you rephrase or give me a bit more detail?"
        )
    else:
        presentation = "I wasn't able to complete that request."

    # Append a small metadata footer to the presentation for the chat UI
    if success and plan and quality_ok is not False:
        presentation += (
            f"\n\n*difficulty: {plan.get('difficulty')} | "
            f"mastery L{plan.get('mastery_level')} | "
            f"style: {plan.get('teaching_style')} | "
            f"confidence: {confidence:.0%}*"
        )

    envelope = build_envelope(
        tool_name=tool_name,
        data=tool_output,
        presentation=presentation,
        plan=plan,
        execution_time_ms=exec_ms,
        confidence=confidence,
        retry_count=retries,
        success=success and (quality_ok is not False),
        arguments=arguments,
        reasoning=reasoning,
        candidates=candidates,
        observation=observation,
        quality_ok=quality_ok,
        error=err,
        clarification=clarification,
    )

    update = {
        **state,
        "formatted_response": presentation,
        "final_response": presentation,
        "response_envelope": envelope,
    }
    return append_step(update, info(
        STAGE_FORMAT,
        f"envelope built ({len(presentation)} chars); success={success}, "
        f"quality_ok={quality_ok}",
    ))


# ── Clarifier ────────────────────────────────────────────────────────────────

async def clarification_node(state: OrchestratorState) -> OrchestratorState:
    """Produce a clarification question when required fields are unfilled
    even after extraction + inference + repair.
    """
    tool_name = state.get("selected_tool", "concept_explainer")
    tool = registry.get(tool_name)
    if not tool:
        return {**state, "clarification_needed": None}

    schema = tool.get_schema()
    errors = state.get("validation_errors", []) or []

    missing: List[str] = []
    for err in errors:
        low = err.lower()
        if "missing required" in low:
            # Parse "'X' not in allowed" or "missing required field 'X'"
            import re
            m = re.search(r"'([^']+)'", err)
            if m:
                missing.append(m.group(1))

    # Deduplicate while preserving order
    seen = set()
    missing = [m for m in missing if not (m in seen or seen.add(m))]

    if not missing:
        return {**state, "clarification_needed": None}

    question = generate_clarification(missing, schema, tool_name)

    update = {**state, "clarification_needed": question}
    return append_step(update, info(
        STAGE_CLARIFY,
        f"asking for: {missing}",
        question=question,
    ))


# ── Error Handler ─────────────────────────────────────────────────────────────

async def error_handler_node(state: OrchestratorState) -> OrchestratorState:
    """Four-tier recovery:
      1. Quality failure from observer → follow observer's suggested_recovery.
      2. Validation errors look recoverable → another pass.
      3. Required fields truly missing → route to clarifier.
      4. Execution failure with fallbacks available → switch tool.
      5. Out of options → give_up.

    The routing decision is encoded in `recovery_action` so the graph
    dispatches via its conditional edges.
    """
    from app.config import settings

    retry_count = state.get("retry_count", 0)
    fallbacks = list(state.get("fallback_tools", []) or [])
    current_tool = state.get("selected_tool", "concept_explainer")
    validation_errors = state.get("validation_errors", []) or []
    suggested = state.get("suggested_recovery", "") or ""

    # Give-up condition
    if retry_count >= settings.MAX_RETRIES:
        update = {
            **state,
            "recovery_action": "give_up",
            "retry_count": retry_count + 1,
        }
        return append_step(update, warn(
            STAGE_ERROR, f"max retries ({settings.MAX_RETRIES}) reached — giving up",
        ))

    # ── Tier 1: observer-driven recovery ───────────────────────────────
    if suggested == "give_up":
        update = {
            **state,
            "recovery_action": "give_up",
            "retry_count": retry_count + 1,
        }
        return append_step(update, warn(
            STAGE_ERROR, "observer suggests giving up",
            reason=state.get("quality_reason"),
        ))

    if suggested == "retry_same_tool":
        # Reset execution fields, let it run again. Don't change the tool.
        update = {
            **state,
            "recovery_action": "switch_tool",   # re-enters extractor path
            "retry_count": retry_count + 1,
            "execution_success": False,
            "tool_output": {},
            "is_valid": False,
        }
        return append_step(update, info(
            STAGE_ERROR, f"observer says retry '{current_tool}' — re-running pipeline",
        ))

    if suggested == "switch_tool" and fallbacks:
        new_tool = fallbacks[0]
        remaining = fallbacks[1:]
        update = {
            **state,
            "selected_tool": new_tool,
            "fallback_tools": remaining,
            "recovery_action": "switch_tool",
            "retry_count": retry_count + 1,
            "is_valid": False,
            "validation_errors": [],
            "execution_success": False,
        }
        return append_step(update, warn(
            STAGE_ERROR, f"observer says switch tool: {current_tool} → {new_tool}",
        ))

    if suggested == "clarify":
        update = {
            **state,
            "recovery_action": "clarify",
            "retry_count": retry_count + 1,
        }
        return append_step(update, info(
            STAGE_ERROR, "observer says clarify",
        ))

    # ── Tier 2/3: validation-driven recovery (existing logic) ──────────
    has_missing_required = any(
        "missing required" in e.lower() for e in validation_errors
    )

    if has_missing_required:
        update = {
            **state,
            "recovery_action": "clarify",
            "retry_count": retry_count + 1,
        }
        return append_step(update, info(
            STAGE_ERROR, "missing required fields — routing to clarifier",
            errors=validation_errors,
        ))

    # ── Tier 4: fallback tool ──────────────────────────────────────────
    if fallbacks:
        new_tool = fallbacks[0]
        remaining = fallbacks[1:]
        update = {
            **state,
            "selected_tool": new_tool,
            "fallback_tools": remaining,
            "retry_count": retry_count + 1,
            "is_valid": False,
            "validation_errors": [],
            "execution_success": False,
            "recovery_action": "switch_tool",
        }
        return append_step(update, warn(
            STAGE_ERROR, f"switching tool: {current_tool} → {new_tool}",
            remaining_fallbacks=remaining,
        ))

    # ── Tier 5: give up ────────────────────────────────────────────────
    update = {
        **state,
        "recovery_action": "give_up",
        "retry_count": retry_count + 1,
    }
    return append_step(update, warn(
        STAGE_ERROR, "no fallback tools available — giving up",
    ))
