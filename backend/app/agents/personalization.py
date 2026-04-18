"""Deterministic Personalization Engine.

Implements a fixed mapping from (mastery_level, emotional_state, teaching_style)
to concrete parameter adjustments. No LLM involved — this layer must be
predictable and auditable.

This replaces the ad-hoc clamping in reasoning_engine.py for the personalization
concerns; reasoning_engine.py still handles generic fill-in of missing params
from context.

Inputs come from either:
  - the student_profile (preferred, authoritative), or
  - the Context Analyzer output (best-effort heuristic fallback).

Outputs a PersonalizationPlan that downstream nodes apply to tool params.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional


# ── Canonical vocabularies ────────────────────────────────────────────────────

# Difficulty terms the tool schemas use. Tools may only accept a subset (enum),
# so the validator will snap the chosen value to the tool's allowed set.
DIFFICULTY_EASY = "easy"
DIFFICULTY_MEDIUM = "medium"
DIFFICULTY_HARD = "hard"

# Desired-depth terms used by concept explainer–style tools.
DEPTH_BASIC = "basic"
DEPTH_INTERMEDIATE = "intermediate"
DEPTH_ADVANCED = "advanced"
DEPTH_COMPREHENSIVE = "comprehensive"

# Note-taking styles used by note maker–style tools.
NOTE_OUTLINE = "outline"
NOTE_BULLETS = "bullet_points"
NOTE_NARRATIVE = "narrative"
NOTE_STRUCTURED = "structured"


# ── Mastery → base difficulty ─────────────────────────────────────────────────
# Task spec: Levels 1–3 foundation, 4–6 developing, 7–9 advanced, 10 mastery.
# Mapping chosen so each bucket lands on the exact enum the flashcard tool uses.

def mastery_to_difficulty(mastery_level: int) -> str:
    """Strict bucket: 1–3 → easy, 4–6 → medium, 7–10 → hard."""
    lvl = _clamp_mastery(mastery_level)
    if lvl <= 3:
        return DIFFICULTY_EASY
    if lvl <= 6:
        return DIFFICULTY_MEDIUM
    return DIFFICULTY_HARD


def mastery_to_depth(mastery_level: int) -> str:
    """Map mastery to concept explainer 'desired_depth' enum."""
    lvl = _clamp_mastery(mastery_level)
    if lvl <= 3:
        return DEPTH_BASIC
    if lvl <= 6:
        return DEPTH_INTERMEDIATE
    if lvl <= 9:
        return DEPTH_ADVANCED
    return DEPTH_COMPREHENSIVE


def mastery_to_count(mastery_level: int, base: int = 5) -> int:
    """Suggested item count (flashcards, questions). Higher mastery → more items."""
    lvl = _clamp_mastery(mastery_level)
    if lvl <= 3:
        return max(1, base - 2)        # 3 items for shaky foundations
    if lvl <= 6:
        return base                    # 5 items baseline
    return min(20, base + 5)           # 10 items for proficient+


def _clamp_mastery(value: Any) -> int:
    """Coerce any mastery input (int, string, None) to 1–10."""
    if isinstance(value, bool):
        return 5
    try:
        n = int(value)
    except (TypeError, ValueError):
        if isinstance(value, str):
            val_lower = value.strip().lower()
            if val_lower == "beginner": return 2
            if val_lower == "intermediate": return 5
            if val_lower == "advanced": return 8
            if val_lower == "expert": return 10
            
            # Try parsing strings like "Level 7: Proficient"
            import re
            m = re.search(r"\b([1-9]|10)\b", value)
            if m:
                n = int(m.group(1))
            else:
                return 5
        else:
            return 5
    return max(1, min(10, n))


# ── Emotional state overrides ─────────────────────────────────────────────────
# Applied AFTER mastery mapping. Order: compute base → apply emotion override.

# Canonical emotion vocab per task spec. We also map common synonyms.
EMOTION_ALIASES = {
    "focused": "focused",
    "motivated": "focused",         # spec groups them
    "confident": "focused",
    "curious": "focused",
    "anxious": "anxious",
    "nervous": "anxious",
    "worried": "anxious",
    "confused": "confused",
    "frustrated": "confused",
    "lost": "confused",
    "stuck": "confused",
    "tired": "tired",
    "exhausted": "tired",
    "neutral": "neutral",
}


def normalize_emotion(raw: Optional[str]) -> str:
    if not raw:
        return "neutral"
    return EMOTION_ALIASES.get(str(raw).strip().lower(), "neutral")


# Difficulty ladder for emotion-driven shifts.
_DIFFICULTY_LADDER = [DIFFICULTY_EASY, DIFFICULTY_MEDIUM, DIFFICULTY_HARD]
_DEPTH_LADDER = [DEPTH_BASIC, DEPTH_INTERMEDIATE, DEPTH_ADVANCED, DEPTH_COMPREHENSIVE]


def _shift(value: str, ladder: list, delta: int) -> str:
    try:
        idx = ladder.index(value)
    except ValueError:
        return value
    new_idx = max(0, min(len(ladder) - 1, idx + delta))
    return ladder[new_idx]


# ── Teaching style → parameter hints ──────────────────────────────────────────
# Task spec styles: direct, socratic, visual, flipped_classroom.

TEACHING_STYLE_ALIASES = {
    "direct": "direct",
    "socratic": "socratic",
    "visual": "visual",
    "flipped": "flipped_classroom",
    "flipped_classroom": "flipped_classroom",
    "flipped classroom": "flipped_classroom",
}


def normalize_teaching_style(raw: Optional[str]) -> str:
    if not raw:
        return "direct"
    return TEACHING_STYLE_ALIASES.get(str(raw).strip().lower(), "direct")


# Per-style hints. Downstream params_for_tool() knows how to apply these to
# each tool schema; we don't hardcode tool names here, only semantic hints.
_STYLE_HINTS: Dict[str, Dict[str, Any]] = {
    "direct": {
        "note_taking_style": NOTE_OUTLINE,
        "include_examples": False,
        "include_analogies": False,
        "verbosity": "concise",
    },
    "socratic": {
        "note_taking_style": NOTE_STRUCTURED,
        "include_examples": True,
        "include_analogies": False,
        "verbosity": "inquisitive",
        "prefer_questions": True,
    },
    "visual": {
        "note_taking_style": NOTE_BULLETS,
        "include_examples": True,
        "include_analogies": True,
        "verbosity": "rich",
    },
    "flipped_classroom": {
        "note_taking_style": NOTE_NARRATIVE,
        "include_examples": True,
        "include_analogies": False,
        "verbosity": "applied",
        "assume_prior_knowledge": True,
    },
}


# ── Plan object ───────────────────────────────────────────────────────────────

@dataclass
class PersonalizationPlan:
    """The concrete adjustments this layer decides on. All fields are
    intentionally simple so they can be serialized into state and logged."""
    mastery_level: int
    emotion: str
    teaching_style: str

    # Computed difficulty knobs
    difficulty: str              # easy / medium / hard
    desired_depth: str           # basic / intermediate / advanced / comprehensive
    item_count: int              # suggested count for flashcards/questions

    # Style knobs
    note_taking_style: str
    include_examples: bool
    include_analogies: bool

    # Narrative metadata for logging / meta envelope
    adaptation_reasons: list = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Builder ───────────────────────────────────────────────────────────────────

def build_plan(
    mastery_level: Any,
    emotion: Optional[str],
    teaching_style: Optional[str],
) -> PersonalizationPlan:
    """Deterministic: given the three inputs, produces one and only one plan.

    Apply order is strict and spec-driven:
      1. Mastery determines base difficulty + depth + count.
      2. Emotion overrides can shift these.
      3. Teaching style fills in style-only knobs (note format, examples, etc.).
    """
    lvl = _clamp_mastery(mastery_level)
    emo = normalize_emotion(emotion)
    style = normalize_teaching_style(teaching_style)

    reasons: list = []

    # Step 1: mastery → base knobs
    difficulty = mastery_to_difficulty(lvl)
    depth = mastery_to_depth(lvl)
    count = mastery_to_count(lvl)
    reasons.append(
        f"mastery L{lvl} → difficulty={difficulty}, depth={depth}, count={count}"
    )

    # Step 2: emotion overrides
    if emo == "confused":
        # Simpler content + fewer items
        new_diff = _shift(difficulty, _DIFFICULTY_LADDER, -1)
        new_depth = _shift(depth, _DEPTH_LADDER, -1)
        new_count = max(1, count - 2)
        shifts = []
        if new_diff != difficulty:
            shifts.append(f"difficulty {difficulty}→{new_diff}")
        if new_depth != depth:
            shifts.append(f"depth {depth}→{new_depth}")
        if new_count != count:
            shifts.append(f"count {count}→{new_count}")
        if shifts:
            reasons.append("emotion=confused → " + ", ".join(shifts))
        difficulty, depth, count = new_diff, new_depth, new_count
    elif emo == "anxious":
        new_diff = _shift(difficulty, _DIFFICULTY_LADDER, -1)
        new_count = max(1, count - 1)
        shifts = []
        if new_diff != difficulty:
            shifts.append(f"difficulty {difficulty}→{new_diff}")
        if new_count != count:
            shifts.append(f"count {count}→{new_count}")
        if shifts:
            reasons.append("emotion=anxious → " + ", ".join(shifts))
        difficulty, count = new_diff, new_count
    elif emo == "focused":
        new_diff = _shift(difficulty, _DIFFICULTY_LADDER, +1)
        new_depth = _shift(depth, _DEPTH_LADDER, +1)
        new_count = min(20, count + 2)
        shifts = []
        if new_diff != difficulty:
            shifts.append(f"difficulty {difficulty}→{new_diff}")
        if new_depth != depth:
            shifts.append(f"depth {depth}→{new_depth}")
        if new_count != count:
            shifts.append(f"count {count}→{new_count}")
        if shifts:
            reasons.append("emotion=focused → " + ", ".join(shifts))
        difficulty, depth, count = new_diff, new_depth, new_count
    elif emo == "tired":
        # Minimal cognitive load — cap everything low regardless of mastery
        if difficulty != DIFFICULTY_EASY:
            reasons.append(f"emotion=tired → difficulty {difficulty}→easy (cap)")
            difficulty = DIFFICULTY_EASY
        if depth not in (DEPTH_BASIC, DEPTH_INTERMEDIATE):
            reasons.append(f"emotion=tired → depth {depth}→basic (cap)")
            depth = DEPTH_BASIC
        if count > 3:
            reasons.append(f"emotion=tired → count {count}→3 (cap)")
            count = 3

    # Step 3: teaching style knobs
    hints = _STYLE_HINTS[style]
    reasons.append(
        f"teaching_style={style} → note_style={hints['note_taking_style']}, "
        f"examples={hints['include_examples']}, analogies={hints['include_analogies']}"
    )

    return PersonalizationPlan(
        mastery_level=lvl,
        emotion=emo,
        teaching_style=style,
        difficulty=difficulty,
        desired_depth=depth,
        item_count=count,
        note_taking_style=hints["note_taking_style"],
        include_examples=hints["include_examples"],
        include_analogies=hints["include_analogies"],
        adaptation_reasons=reasons,
    )


# ── Apply to tool params ──────────────────────────────────────────────────────

# Map semantic plan fields to the actual parameter names different tools use.
# Key = plan attribute, value = list of tool-param names it may fulfill.
_PLAN_TO_PARAM_NAMES = {
    "difficulty": ["difficulty"],
    "desired_depth": ["desired_depth"],
    "item_count": ["count", "num_questions", "num_cards", "total_questions"],
    "note_taking_style": ["note_taking_style"],
    "include_examples": ["include_examples"],
    "include_analogies": ["include_analogies"],
}


def apply_plan_to_params(
    plan: PersonalizationPlan,
    params: Dict[str, Any],
    tool_schema: Dict[str, Any],
) -> Dict[str, Any]:
    """Fill params from the plan, but only for fields the tool actually accepts.

    Never overwrites an explicitly-set value — the student's words win.
    """
    if not tool_schema:
        return params

    accepted = set(tool_schema.get("required_params", []))
    accepted |= set(tool_schema.get("optional_params", []))

    out = dict(params or {})
    plan_dict = plan.to_dict()

    for plan_key, candidate_names in _PLAN_TO_PARAM_NAMES.items():
        for param_name in candidate_names:
            if param_name in accepted and (
                param_name not in out or out[param_name] in (None, "")
            ):
                out[param_name] = plan_dict[plan_key]
                break  # one tool-param slot fulfilled per plan field

    return out
