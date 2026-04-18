"""Agent 1: Context Analyzer — NLP Intent Parser.
Analyzes student message, extracts intent, subject, difficulty, mood.
"""
import re
from typing import Any, Dict, List
from app.graph.state import OrchestratorState


# Rule-based intent patterns (used before/alongside LLM)
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

    Two tweaks matter downstream:
    1. We preserve the order in which keywords first appear in the text.
       The old `list(set(...))` call was O(1) faster but destroyed ordering,
       which meant the topic-fallback in reasoning_engine picked whichever
       word landed first in the set's hash order — usually wrong.
    2. After ordering, we stable-sort so that longer words come first
       among keywords of equal position. Longer words are more specific
       topic candidates (e.g. "photosynthesis" over "biology").
    """
    stopwords = {"i", "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
                 "of", "with", "is", "am", "are", "was", "were", "be", "been", "have", "has",
                 "do", "does", "can", "could", "would", "should", "will", "may", "might",
                 "me", "my", "you", "your", "we", "our", "it", "its", "some", "any", "this",
                 "that", "these", "those", "need", "want", "help", "get", "got", "give",
                 "show", "tell", "make", "please"}
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    # Preserve first-appearance order
    seen = set()
    ordered: List[str] = []
    for w in words:
        if w in stopwords or w in seen:
            continue
        seen.add(w)
        ordered.append(w)
    # Stable sort: longer keywords first (more specific)
    ordered.sort(key=len, reverse=True)
    return ordered[:10]


async def context_analyzer_node(state: OrchestratorState) -> OrchestratorState:
    """
    Agent 1: NLP Intent Parser.
    Extracts: intent, subject, difficulty, mood, keywords from raw_message.
    """
    message = state["raw_message"]
    history = state.get("conversation_history", [])
    profile = state.get("student_profile", {})

    # Combine with recent history for better context
    context_text = message
    if history:
        recent = " ".join(h.get("content", "") for h in history[-3:])
        context_text = f"{recent} {message}"

    # Rule-based fast analysis
    intent = detect_intent(message)
    subject = detect_subject(context_text)
    difficulty = detect_difficulty(message)
    mood = detect_mood(message)
    keywords = extract_keywords(message)

    # Override with student profile if set
    if profile.get("learning_level"):
        level_map = {"beginner": "beginner", "intermediate": "intermediate", "advanced": "advanced"}
        profile_difficulty = level_map.get(profile["learning_level"], difficulty)
        # Only override if message doesn't give explicit signal
        if detect_difficulty(message) == "intermediate":  # default = no signal
            difficulty = profile_difficulty

    return {
        **state,
        "intent": intent,
        "subject": subject,
        "difficulty": difficulty,
        "mood": mood,
        "keywords": keywords,
        "workflow_steps": [f"✓ Agent 1 (Context Analyzer): intent={intent}, subject={subject}, difficulty={difficulty}, mood={mood}"],
    }
