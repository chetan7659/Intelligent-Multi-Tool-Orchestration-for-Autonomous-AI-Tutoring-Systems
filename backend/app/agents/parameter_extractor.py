"""Agent 3: Schema-aware Parameter Extractor.

Renders the tool's JSON schema (required/optional/enum/bounds) directly into
the extraction prompt so the LLM knows exactly what to produce. Parses the
response with a tolerant loose-JSON parser, never raises. Only extracts
values present in the conversation; inference is done later.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.graph.state import OrchestratorState
from app.tools.registry import registry
from app.agents.llm_client import get_llm_client
from app.agents.logger import info, warn, append_step, STAGE_EXTRACT


# ── Prompt building ───────────────────────────────────────────────────────────

def _render_schema_for_prompt(schema: Dict[str, Any]) -> str:
    """Render the tool schema as a compact readable block for the LLM."""
    js = schema.get("json_schema") or {}
    props: Dict[str, Dict[str, Any]] = js.get("properties", {}) if isinstance(js, dict) else {}
    required: List[str] = js.get("required", []) if isinstance(js, dict) else []

    # Fallback: synthesize from legacy attrs
    if not props:
        legacy_to_js = {"str": "string", "int": "integer", "float": "number",
                        "bool": "boolean", "list": "array"}
        type_hints = schema.get("param_types", {}) or {}
        all_fields = list(schema.get("required_params", [])) + \
                     list(schema.get("optional_params", []))
        for f in all_fields:
            props[f] = {"type": legacy_to_js.get(type_hints.get(f, "str"), "string")}
        required = list(schema.get("required_params", []))

    lines: List[str] = []
    for name, spec in props.items():
        tag = "REQUIRED" if name in required else "optional"
        t = spec.get("type", "string")
        bits = [f"- {name} ({tag}, {t})"]
        if "enum" in spec:
            bits.append(f"    allowed values: {spec['enum']}")
        if "minimum" in spec or "maximum" in spec:
            bits.append(
                f"    range: {spec.get('minimum', '-inf')}..{spec.get('maximum', '+inf')}"
            )
        if "description" in spec:
            bits.append(f"    description: {spec['description']}")
        lines.append("\n".join(bits))
    return "\n".join(lines) if lines else "(no schema declared)"


def _build_extraction_prompt(
    tool_name: str,
    tool_description: str,
    schema_block: str,
    recent_history: str,
    user_message: str,
    context: Dict[str, Any],
) -> str:
    return f"""You are a parameter extraction specialist for the tool '{tool_name}'.

Tool description: {tool_description}

Tool input schema:
{schema_block}

Recent conversation:
{recent_history}

Context from analyzer:
- detected subject:    {context.get('subject', 'general')}
- detected difficulty: {context.get('difficulty', 'intermediate')}
- detected intent:     {context.get('intent', 'learn_concept')}

User's current message:
\"\"\"{user_message}\"\"\"

INSTRUCTIONS:
1. Extract ONLY values explicitly stated in the user's message or recent history.
2. Do NOT invent or infer values — missing fields are handled by a later step.
3. For enum fields, return only an exact allowed value.
4. For integer fields, return a JSON integer (not a string).
5. Return ONLY a valid JSON object. No markdown, no commentary.

Example:
{{"topic": "derivatives", "subject": "calculus"}}

If no fields can be extracted, return: {{}}
"""


# ── JSON repair helper ────────────────────────────────────────────────────────

def _parse_json_loose(raw: str) -> Optional[Dict[str, Any]]:
    """Tolerant JSON parse: strips markdown, finds first balanced object."""
    if not raw:
        return None
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    start = cleaned.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(cleaned)):
        c = cleaned[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                block = cleaned[start : i + 1]
                try:
                    return json.loads(block)
                except json.JSONDecodeError:
                    return None
    return None


# ── Node ──────────────────────────────────────────────────────────────────────

async def parameter_extractor_node(state: OrchestratorState) -> OrchestratorState:
    """Schema-aware extraction: explicit-only, structured JSON output."""
    message = state["raw_message"]
    tool_name = state.get("selected_tool", "concept_explainer")
    tool = registry.get(tool_name)

    if not tool:
        fallback = {
            "topic": message[:60],
            "subject": state.get("subject", "general"),
        }
        update = {**state, "extracted_params": fallback}
        return append_step(update, warn(
            STAGE_EXTRACT,
            f"tool '{tool_name}' not found — using emergency fallback",
            fallback_keys=list(fallback.keys()),
        ))

    schema = tool.get_schema()
    schema_block = _render_schema_for_prompt(schema)

    history = state.get("conversation_history", []) or []
    recent = "\n".join(
        f"{m.get('role', 'user')}: {m.get('content', '')}"
        for m in history[-4:]
    ) or "(no prior messages)"

    prompt = _build_extraction_prompt(
        tool_name=tool.name,
        tool_description=tool.description,
        schema_block=schema_block,
        recent_history=recent,
        user_message=message,
        context={
            "subject": state.get("subject"),
            "difficulty": state.get("difficulty"),
            "intent": state.get("intent"),
        },
    )

    llm = get_llm_client()
    raw = await llm.generate(prompt, max_tokens=512, temperature=0.1)
    parsed = _parse_json_loose(raw)

    if not isinstance(parsed, dict):
        update = {**state, "extracted_params": {}}
        return append_step(update, warn(
            STAGE_EXTRACT,
            f"LLM output unparseable for {tool_name}; continuing with empty extraction",
            preview=(raw or "")[:120],
        ))

    update = {**state, "extracted_params": parsed}
    return append_step(update, info(
        STAGE_EXTRACT,
        f"extracted {len(parsed)} explicit params for {tool_name}",
        params=list(parsed.keys()),
    ))
