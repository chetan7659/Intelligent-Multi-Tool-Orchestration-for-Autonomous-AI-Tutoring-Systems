"""Schema-aware validator with enum enforcement, numeric bounds, type coercion,
and auto-repair of recoverable errors.

Consumes the new `json_schema` attribute on tools (see tools/base.py) when
available. Falls back to the legacy `required_params`/`optional_params`/
`param_defaults` attrs so existing tools keep working unchanged.

Public API:
  validate_and_repair(params, schema) -> (params, errors, repair_actions, is_valid)

Where `schema` is the dict returned by BaseTool.get_schema().
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


# ── Type coercion ─────────────────────────────────────────────────────────────

_TRUTHY = {"true", "yes", "1", "on"}
_FALSY = {"false", "no", "0", "off"}


def _coerce(value: Any, target_type: str) -> Tuple[Any, bool]:
    """Try to coerce value to target type. Returns (new_value, was_coerced)."""
    if target_type == "string":
        if isinstance(value, str):
            return value, False
        return str(value), True

    if target_type == "integer":
        if isinstance(value, bool):
            return int(value), True
        if isinstance(value, int):
            return value, False
        if isinstance(value, float) and value.is_integer():
            return int(value), True
        if isinstance(value, str) and value.strip().lstrip("-").isdigit():
            return int(value.strip()), True
        return value, False

    if target_type == "number":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value), not isinstance(value, float)
        if isinstance(value, str):
            try:
                return float(value.strip()), True
            except ValueError:
                return value, False
        return value, False

    if target_type == "boolean":
        if isinstance(value, bool):
            return value, False
        if isinstance(value, str):
            low = value.strip().lower()
            if low in _TRUTHY:
                return True, True
            if low in _FALSY:
                return False, True
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return bool(value), True
        return value, False

    if target_type == "array":
        if isinstance(value, list):
            return value, False
        if isinstance(value, str):
            # Comma-separated fallback
            return [p.strip() for p in value.split(",") if p.strip()], True
        return value, False

    if target_type == "object":
        if isinstance(value, dict):
            return value, False
        return value, False

    return value, False


def _type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "null"


# ── Enum snap ─────────────────────────────────────────────────────────────────

def _snap_to_enum(value: Any, enum: List[Any]) -> Tuple[Any, bool]:
    """If value not in enum, try case-insensitive match. Returns (value, was_snapped)."""
    if value in enum:
        return value, False
    if isinstance(value, str):
        low = value.strip().lower()
        for option in enum:
            if isinstance(option, str) and option.lower() == low:
                return option, True
    return value, False


# ── Numeric bounds ────────────────────────────────────────────────────────────

def _clamp(value: Any, minimum: Any, maximum: Any) -> Tuple[Any, bool]:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return value, False

    # Coerce bounds to the same numeric type as value to prevent
    # TypeError: '<' not supported between instances of 'int' and 'str'
    # This happens when json_schema bounds come in as strings or are
    # otherwise of mismatched type (e.g. "1" instead of 1).
    def _to_num(bound: Any) -> Any:
        if bound is None:
            return None
        if isinstance(bound, (int, float)) and not isinstance(bound, bool):
            return bound
        try:
            return type(value)(bound)   # cast to int or float to match value
        except (TypeError, ValueError):
            return None                 # ignore un-coercible bound

    lo = _to_num(minimum)
    hi = _to_num(maximum)

    original = value
    if lo is not None and value < lo:
        value = lo
    if hi is not None and value > hi:
        value = hi
    return value, value != original


# ── Main entry point ──────────────────────────────────────────────────────────

def validate_and_repair(
    params: Dict[str, Any],
    schema: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str], List[str], bool]:
    """
    Validate and auto-repair parameters against a tool schema.

    Returns:
      params:         the repaired dict
      errors:         list of unresolved validation errors (empty if valid)
      repair_actions: list of repairs applied (for logging)
      is_valid:       True iff no unresolved errors remain
    """
    out = dict(params or {})
    errors: List[str] = []
    actions: List[str] = []

    # Prefer new-style JSON Schema if the tool exposes one.
    js = schema.get("json_schema") if schema else None

    if isinstance(js, dict) and isinstance(js.get("properties"), dict):
        props: Dict[str, Dict[str, Any]] = js["properties"]
        required: List[str] = js.get("required", []) or []
        defaults: Dict[str, Any] = schema.get("param_defaults", {}) or {}
    else:
        # Fallback: synthesize a minimal JSON-Schema-ish view from legacy attrs.
        required = schema.get("required_params", []) or []
        optional = schema.get("optional_params", []) or []
        defaults = schema.get("param_defaults", {}) or {}
        type_hints = schema.get("param_types", {}) or {}
        props = {}
        legacy_to_js = {"str": "string", "int": "integer", "float": "number",
                        "bool": "boolean", "list": "array", "dict": "object"}
        for p in required + optional:
            hint = type_hints.get(p, "str")
            props[p] = {"type": legacy_to_js.get(hint, "string")}

    # ── Step 1: fill missing required params from defaults ───────────────────
    for req in required:
        if req not in out or out[req] in (None, ""):
            if req in defaults:
                out[req] = defaults[req]
                actions.append(f"filled missing required '{req}' from default")
            else:
                # Leave it; the post-check will error if still missing.
                pass

    # ── Step 2: apply defaults for optional params that are absent ───────────
    for key, default_val in defaults.items():
        if key not in out and key not in required:
            out[key] = default_val

    # ── Step 3: per-field validation ─────────────────────────────────────────
    for field_name, field_schema in props.items():
        if field_name not in out:
            continue
        value = out[field_name]

        # 3a. Type coercion
        expected = field_schema.get("type")
        if expected:
            current = _type_name(value)
            if current != expected and expected != "object":
                new_value, was_coerced = _coerce(value, expected)
                if was_coerced:
                    actions.append(
                        f"coerced '{field_name}' from {current} to {expected}"
                    )
                    value = new_value
                    out[field_name] = value
                elif current != "null":
                    errors.append(
                        f"'{field_name}' expected {expected}, got {current}"
                    )

        # 3b. Enum snap
        enum = field_schema.get("enum")
        if enum is not None:
            new_value, snapped = _snap_to_enum(value, enum)
            if snapped:
                actions.append(
                    f"snapped '{field_name}' '{value}' → '{new_value}' (enum match)"
                )
                value = new_value
                out[field_name] = value
            if value not in enum:
                errors.append(
                    f"'{field_name}'='{value}' not in allowed values {enum}"
                )

        # 3c. Numeric bounds
        minimum = field_schema.get("minimum")
        maximum = field_schema.get("maximum")
        if minimum is not None or maximum is not None:
            new_value, clamped = _clamp(value, minimum, maximum)
            if clamped:
                actions.append(
                    f"clamped '{field_name}' {value} → {new_value} "
                    f"(bounds {minimum}..{maximum})"
                )
                out[field_name] = new_value

    # ── Step 4: final required-field presence check ──────────────────────────
    for req in required:
        if req not in out or out[req] in (None, ""):
            errors.append(f"missing required field '{req}'")

    return out, errors, actions, len(errors) == 0


# ── Clarification question generation ─────────────────────────────────────────

def generate_clarification(
    missing_fields: List[str],
    schema: Dict[str, Any],
    tool_name: str,
) -> str:
    """Produce a single natural-language clarification question for the user.

    Returns a short question listing what we need, phrased for a student.
    """
    if not missing_fields:
        return ""

    js = schema.get("json_schema") or {}
    props = js.get("properties", {}) if isinstance(js, dict) else {}

    parts: List[str] = []
    for field_name in missing_fields:
        fs = props.get(field_name, {})
        desc = fs.get("description", "").lower()
        enum = fs.get("enum")

        if field_name == "topic":
            parts.append("what topic you want to focus on")
        elif field_name == "subject":
            parts.append("which subject this is for (e.g., biology, algebra)")
        elif field_name == "concept_to_explain":
            parts.append("which concept you'd like explained")
        elif field_name == "current_topic":
            parts.append("the broader topic it fits under")
        elif field_name == "count":
            parts.append("how many items you'd like")
        elif field_name == "difficulty" and enum:
            parts.append(f"the difficulty ({', '.join(enum)})")
        elif field_name == "note_taking_style" and enum:
            parts.append(f"what note style you prefer ({', '.join(enum)})")
        elif field_name == "desired_depth" and enum:
            parts.append(f"how deep to go ({', '.join(enum)})")
        elif desc:
            parts.append(desc)
        else:
            parts.append(f"what to use for {field_name.replace('_', ' ')}")

    if len(parts) == 1:
        return f"Quick question — could you tell me {parts[0]}?"
    head = ", ".join(parts[:-1])
    return f"Before I can help, could you share {head}, and {parts[-1]}?"
