"""Agent 1: Context Analyzer — Hybrid NLP Intent Parser.

Two-tier classifier:
  1. FAST PATH: deterministic rule-based scoring (sub-ms, $0).
  2. SLOW PATH: LLM fallback triggered ONLY when rule confidence is low.

This gives LLM-level accuracy on ambiguous/novel phrasing without paying
the latency + cost tax on every single turn.
"""
import re
from typing import Any, Dict, List
from app.graph.state import OrchestratorState
from app.agents.llm_client import get_llm_client


# ── Rule-based lexicons ───────────────────────────────────────────────────────
DIFFICULTY_SIGNALS = {
    "beginner": ["struggling", "don't understand", "confused", "help", "basic", "beginner", "simple", "easy", "new to", "start"],
    "intermediate": ["practice", "review", "improve", "better at", "intermediate", "working on"],
    "advanced": ["challenging", "deep dive", "advanced", "complex", "expert", "mastery", "hard"],
    "expert": ["expert", "research", "PhD", "graduate", "professional"],
}

SUBJECT_PATTERNS = {
    "mathematics": ["math", "calculus", "algebra", "geometry", "trigonometry", "statistics", "derivative", "integral", "equation"],
    "physics": ["physics", "force", "motion", "energy", "gravity", "quantum", "thermodynamics", "optics"],
    "chemistry": ["chemistry", "element", "compound", "reaction", "molecule", "periodic", "acid", "base"],
    "biology": ["biology", "cell", "genetics", "evolution", "organism", "ecosystem", "DNA", "protein"],
    "history": ["history", "historical", "war", "civilization", "ancient", "revolution", "century"],
    "literature": ["literature", "poem", "novel", "story", "character", "author", "writing", "essay"],
    "computer_science": ["programming", "code", "algorithm", "data structure", "python", "javascript", "software"],
    "economics": ["economics", "supply", "demand", "market", "GDP", "inflation", "trade"],
    "geography": ["geography", "country", "continent", "climate", "map", "region", "capital"],
    "language": ["language", "grammar", "vocabulary", "pronunciation", "spelling", "sentence"],
}

INTENT_PATTERNS = {
    "learn_concept": ["explain", "what is", "tell me about", "understand", "learn", "teach me"],
    "practice": ["practice", "exercise", "quiz me", "test me", "problems", "questions"],
    "solve_problem": ["solve", "help me with", "how do I", "step by step", "calculate", "find"],
    "review": ["review", "summarize", "summary", "recap", "overview", "key points"],
    "memorize": ["memorize", "remember", "flashcard", "mnemonic", "recall", "retain"],
    "compare": ["compare", "difference", "vs", "versus", "contrast", "similarities"],
    "create": ["create", "make", "generate", "build", "write", "compose"],
    "visualize": ["show me", "visualize", "diagram", "picture", "chart", "map"],
    "prepare_exam": ["exam", "test", "mock test", "prepare", "ready for", "study for"],
    "brainstorm": ["brainstorm", "ideas", "prompts", "creative", "suggest"],
}

MOOD_SIGNALS = {
    "frustrated": ["struggling", "confused", "don't get it", "lost", "stuck", "hard", "difficult"],
    "curious": ["wonder", "curious", "interested", "fascinating", "tell me more"],
    "confident": ["want to master", "ready for", "advanced", "challenging"],
    "anxious": ["exam", "test tomorrow", "worried", "scared", "nervous"],
    "motivated": ["practice", "improve", "better", "learn more", "ready"],
}

VALID_INTENTS = list(INTENT_PATTERNS.keys())
VALID_SUBJECTS = list(SUBJECT_PATTERNS.keys()) + ["general"]
VALID_DIFFICULTIES = list(DIFFICULTY_SIGNALS.keys())
VALID_MOODS = list(MOOD_SIGNALS.keys()) + ["neutral"]

# Rule confidence threshold — below this, call LLM fallback
LLM_FALLBACK_THRESHOLD = 0.5


# ── Rule-based detectors ──────────────────────────────────────────────────────
def detect_difficulty(text: str) -> str:
    text_lower = text.lower()
    scores = {level: 0 for level in DIFFICULTY_SIGNALS}
    for level, signals in DIFFICULTY_SIGNALS.items():
        for signal in signals:
            if signal in text_lower:
                scores[level] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "intermediate"


def detect_subject(text: str) -> str:
    text_lower = text.lower()
    scores = {subj: 0 for subj in SUBJECT_PATTERNS}
    for subj, keywords in SUBJECT_PATTERNS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                scores[subj] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


def detect_intent(text: str) -> str:
    text_lower = text.lower()
    scores = {intent: 0 for intent in INTENT_PATTERNS}
    for intent, patterns in INTENT_PATTERNS.items():
        for p in patterns:
            if p in text_lower:
                scores[intent] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "learn_concept"


def detect_mood(text: str) -> str:
    text_lower = text.lower()
    for mood, signals in MOOD_SIGNALS.items():
        if any(s in text_lower for s in signals):
            return mood
    return "neutral"


def extract_keywords(text: str) -> List[str]:
    """Keyword extraction, preserving first-appearance order.

    1. Preserve first-appearance order — set() destroys ordering, which
       meant downstream topic-fallback picked whichever word landed
       first in the set's hash order (usually wrong).
    2. Stable-sort so longer words come first — longer = more specific
       topic candidates (e.g. "photosynthesis" over "biology").
    """
    stopwords = {"i", "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
                 "of", "with", "is", "am", "are", "was", "were", "be", "been", "have", "has",
                 "do", "does", "can", "could", "would", "should", "will", "may", "might",
                 "me", "my", "you", "your", "we", "our", "it", "its", "some", "any", "this",
                 "that", "these", "those", "need", "want", "help", "get", "got", "give",
                 "show", "tell", "make", "please"}
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    seen = set()
    ordered: List[str] = []
    for w in words:
        if w in stopwords or w in seen:
            continue
        seen.add(w)
        ordered.append(w)
    ordered.sort(key=len, reverse=True)
    return ordered[:10]


# ── Hybrid helpers ────────────────────────────────────────────────────────────
def _compute_rule_confidence(intent: str, subject: str, mood: str) -> float:
    """Rule confidence = how many dimensions returned a non-default value.

    Defaults indicate the keyword dictionaries didn't match anything —
    meaning the message has novel phrasing we should escalate to the LLM.
    """
    score = 0.0
    if intent != "learn_concept":
        score += 0.34
    if subject != "general":
        score += 0.33
    if mood != "neutral":
        score += 0.33
    return score


async def _llm_refine_context(message: str, context_text: str) -> Dict[str, Any]:
    """LLM fallback — structured JSON extraction for ambiguous messages."""
    llm = get_llm_client()
    prompt = f"""You are a context analyzer for an educational tutoring system.
Analyze the student message and return ONLY valid JSON with these exact keys:

{{
  "intent": "one of: {', '.join(VALID_INTENTS)}",
  "subject": "subject domain in lowercase (e.g. mathematics, physics, chemistry, biology, history, literature, computer_science, economics, geography, language, or 'general')",
  "difficulty": "one of: {', '.join(VALID_DIFFICULTIES)}",
  "mood": "one of: {', '.join(VALID_MOODS)}"
}}

Student message: "{message}"
Recent conversation context: "{context_text[:300]}"

Return ONLY the JSON object, no markdown, no explanation.
"""
    try:
        result = await llm.extract_json(prompt)
        return result if isinstance(result, dict) else {}
    except Exception as e:
        print(f"[context_analyzer] LLM fallback failed: {e}")
        return {}


def _safe_enum(value: Any, allowed: List[str], fallback: str) -> str:
    """Coerce LLM output to a valid enum value."""
    if isinstance(value, str) and value.strip().lower() in allowed:
        return value.strip().lower()
    return fallback


# ── Main node ─────────────────────────────────────────────────────────────────
async def context_analyzer_node(state: OrchestratorState) -> OrchestratorState:
    """Agent 1: Hybrid NLP Intent Parser.

    Extracts: intent, subject, difficulty, mood, keywords from raw_message.
    Uses rule-based scoring as the fast path and an LLM fallback only when
    rules return low-confidence (mostly-default) output.
    """
    message = state["raw_message"]
    history = state.get("conversation_history", [])
    profile = state.get("student_profile", {})

    # Combine with recent history for better subject detection
    context_text = message
    if history:
        recent = " ".join(h.get("content", "") for h in history[-3:])
        context_text = f"{recent} {message}"

    # ── FAST PATH: rule-based ────────────────────────────────────────────────
    intent = detect_intent(message)
    subject = detect_subject(context_text)
    difficulty = detect_difficulty(message)
    mood = detect_mood(message)
    keywords = extract_keywords(message)

    rule_confidence = _compute_rule_confidence(intent, subject, mood)
    used_llm = False

    # ── SLOW PATH: LLM fallback for ambiguous messages ───────────────────────
    if rule_confidence < LLM_FALLBACK_THRESHOLD:
        llm_result = await _llm_refine_context(message, context_text)
        if llm_result:
            used_llm = True
            # Only override fields where rules returned their fallback defaults —
            # clear rule-based signals always win.
            if intent == "learn_concept" and "intent" in llm_result:
                intent = _safe_enum(llm_result["intent"], VALID_INTENTS, intent)
            if subject == "general" and "subject" in llm_result:
                subject = _safe_enum(llm_result["subject"], VALID_SUBJECTS, subject)
            if mood == "neutral" and "mood" in llm_result:
                mood = _safe_enum(llm_result["mood"], VALID_MOODS, mood)
            if difficulty == "intermediate" and "difficulty" in llm_result:
                difficulty = _safe_enum(llm_result["difficulty"], VALID_DIFFICULTIES, difficulty)

    # ── Profile overrides: Respect persistent DB profile for neutral signals ──
    if profile:
        # 1. learning_level -> difficulty
        if profile.get("learning_level"):
            level_map = {"beginner": "beginner", "intermediate": "intermediate", "advanced": "advanced", "expert": "advanced"}
            profile_difficulty = level_map.get(profile["learning_level"], difficulty)
            if detect_difficulty(message) == "intermediate":  # default = no signal
                difficulty = profile_difficulty
        
        # 2. emotional_state -> mood
        if profile.get("emotional_state") and detect_mood(message) == "neutral":
            mood = profile["emotional_state"]
        
        # 3. teaching_style (can be used for specific prompt hints)
        # Note: tool_selector already reads this directly from state["student_profile"]

    step_tag = f"✓ Agent 1 (Context Analyzer): intent={intent}, subject={subject}, difficulty={difficulty}, mood={mood}"
    step_tag += f" [rule_conf={rule_confidence:.2f}{', llm=ON' if used_llm else ''}]"

    return {
        **state,
        "intent": intent,
        "subject": subject,
        "difficulty": difficulty,
        "mood": mood,
        "keywords": keywords,
        "workflow_steps": [step_tag],
    }
