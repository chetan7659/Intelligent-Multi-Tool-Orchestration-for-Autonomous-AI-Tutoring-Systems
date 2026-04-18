from __future__ import annotations

from typing import Any, Dict, List, Tuple


DIFFICULTY_ORDER = ["beginner", "easy", "intermediate", "advanced", "expert"]


def _difficulty_rank(level: str) -> int:
    if not level:
        return 2
    level = level.lower()
    return DIFFICULTY_ORDER.index(level) if level in DIFFICULTY_ORDER else 2


def _clamp_difficulty(level: str, mood: str) -> str:
    rank = _difficulty_rank(level)
    if mood in {"frustrated", "anxious"}:
        rank = max(0, rank - 1)
    elif mood in {"confident", "curious"}:
        rank = min(len(DIFFICULTY_ORDER) - 1, rank + 1)
    return DIFFICULTY_ORDER[rank]


def _normalize_level(profile: Dict[str, Any], state_difficulty: str) -> str:
    mastery = str(profile.get("mastery_level") or profile.get("learning_level") or "").lower()
    if mastery in {"novice", "beginner"}:
        return "beginner"
    if mastery in {"intermediate", "developing"}:
        return "intermediate"
    if mastery in {"advanced", "expert"}:
        return "advanced"
    return state_difficulty or "intermediate"


# Words that are never valid topics — they're either tool trigger words
# themselves OR generic chat verbs/modals that the keyword extractor
# failed to strip. If the top keyword is one of these, skip it and try
# the next one.
_TOOL_WORDS_TO_EXCLUDE_FROM_TOPICS = {
    # Tool names / trigger words
    "flashcard", "flashcards", "quiz", "test", "questions", "question",
    "notes", "note", "summary", "summarize", "mnemonic", "mnemonics",
    "mindmap", "prompt", "prompts", "debate", "pronunciation", "rhyme",
    "rap", "podcast", "slide", "slides", "timeline", "simulation",
    "anchor", "chart", "visualize", "visualization", "explain",
    "explanation", "compare", "comparison", "solve", "solver",
    # Common chat verbs / modals that aren't topics
    "get", "got", "give", "show", "tell", "teach", "make", "create",
    "generate", "build", "find", "use", "try", "please", "would", "could",
    "should", "think", "know", "like", "want", "ready", "okay", "yeah",
    "hey", "hello", "thanks", "good", "great", "maybe", "really",
}


def _first_real_keyword(keywords: list, fallback: str = "general") -> str:
    """Return the first keyword that isn't a tool-trigger word."""
    for kw in (keywords or []):
        if kw and kw.lower() not in _TOOL_WORDS_TO_EXCLUDE_FROM_TOPICS:
            return kw
    return fallback


def infer_parameters(
    message: str,
    extracted: Dict[str, Any],
    schema: Dict[str, Any],
    context: Dict[str, Any],
    profile: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Rule-based inference layer:
    1) fill missing params from context/profile
    2) infer pedagogical defaults from user language
    3) personalize difficulty/format choices
    """
    inferred = dict(extracted or {})
    reasons: List[str] = []
    text = (message or "").lower()
    required = schema.get("required_params", [])
    defaults = schema.get("param_defaults", {})
    mood = context.get("mood", "neutral")
    detected_difficulty = context.get("difficulty", "intermediate")
    level = _normalize_level(profile, detected_difficulty)
    personalized_difficulty = _clamp_difficulty(level, mood)

    if "difficulty" in required or "difficulty" in schema.get("optional_params", []):
        if not inferred.get("difficulty"):
            inferred["difficulty"] = personalized_difficulty
            reasons.append(f"inferred difficulty='{personalized_difficulty}' from mastery+mood")

    # Content intent inference from language patterns
    if "question_type" in required or "question_type" in schema.get("optional_params", []):
        if not inferred.get("question_type"):
            if "practice" in text or "quiz" in text:
                inferred["question_type"] = "practice"
                reasons.append("inferred question_type='practice' from phrasing")
            elif "exam" in text or "test" in text:
                inferred["question_type"] = "assessment"
                reasons.append("inferred question_type='assessment' from phrasing")

    # Common concept/topic inference
    if "prompt" in required and not inferred.get("prompt"):
        inferred["prompt"] = message.strip()
        reasons.append("filled prompt from raw user message")
    if "topic" in required and not inferred.get("topic"):
        subject_fallback = context.get("subject", "general")
        keyword = _first_real_keyword(context.get("keywords", []), subject_fallback)
        inferred["topic"] = keyword
        reasons.append(f"fallback topic from first non-tool keyword: '{keyword}'")
    if "concept" in required and not inferred.get("concept"):
        inferred["concept"] = _first_real_keyword(
            context.get("keywords", []), "the concept"
        )
        reasons.append("fallback concept from first non-tool keyword")
    if "subject" in required and not inferred.get("subject"):
        inferred["subject"] = context.get("subject", "general")
        reasons.append("filled subject from context")

    # Teaching style influences response structure/tool params
    style = str(profile.get("teaching_style") or profile.get("learning_style") or "").lower()
    if style in {"visual", "diagram"}:
        if "response_format" in schema.get("optional_params", []) and not inferred.get("response_format"):
            inferred["response_format"] = "visual-first"
            reasons.append("set response_format='visual-first' from teaching style")
    elif style in {"concise", "bullet"}:
        if "response_format" in schema.get("optional_params", []) and not inferred.get("response_format"):
            inferred["response_format"] = "concise-bullets"
            reasons.append("set response_format='concise-bullets' from teaching style")

    # Last pass defaults for required params
    for param in required:
        if inferred.get(param) in (None, ""):
            if param in defaults:
                inferred[param] = defaults[param]
                reasons.append(f"defaulted required param '{param}' from tool schema")
            elif param == "difficulty":
                inferred[param] = personalized_difficulty
                reasons.append("defaulted difficulty from personalization")
            else:
                inferred[param] = context.get("subject", "general") if param in {"topic", "subject"} else "general"
                reasons.append(f"backfilled required param '{param}' with safe fallback")

    return inferred, reasons


def build_personalization_plan(profile: Dict[str, Any], mood: str, difficulty: str) -> Dict[str, Any]:
    base = {
        "tone": "clear",
        "challenge_adjustment": "none",
        "response_style": "standard",
        "target_difficulty": difficulty,
    }
    if mood in {"frustrated", "anxious"}:
        base["tone"] = "encouraging"
        base["challenge_adjustment"] = "decrease"
    elif mood in {"confident", "curious"}:
        base["tone"] = "challenging"
        base["challenge_adjustment"] = "increase"

    style = str(profile.get("teaching_style") or profile.get("learning_style") or "").lower()
    if style:
        base["response_style"] = style

    base["target_difficulty"] = _clamp_difficulty(difficulty, mood)
    return base


def repair_from_validation_errors(
    params: Dict[str, Any],
    errors: List[str],
    schema: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    fixed = dict(params or {})
    actions: List[str] = []
    defaults = schema.get("param_defaults", {})

    for err in errors or []:
        low = err.lower()
        if "missing" in low or "field required" in low:
            for req in schema.get("required_params", []):
                if req not in fixed or fixed.get(req) in ("", None):
                    fixed[req] = defaults.get(req, "general")
                    actions.append(f"filled missing '{req}'")
        if "int" in low:
            for k, v in list(fixed.items()):
                if isinstance(v, str) and v.isdigit():
                    fixed[k] = int(v)
                    actions.append(f"coerced '{k}' to int")
        if "bool" in low:
            for k, v in list(fixed.items()):
                if isinstance(v, str) and v.lower() in {"true", "false"}:
                    fixed[k] = v.lower() == "true"
                    actions.append(f"coerced '{k}' to bool")

    return fixed, actions
