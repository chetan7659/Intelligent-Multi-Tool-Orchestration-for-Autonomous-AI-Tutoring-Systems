"""Hybrid tool selector.

Three-stage selection:

  1. RANKER (fast, rule-based): Jaccard keyword + intent overlap gives
     top-K candidates with scores. ~5 ms. Same approach as before.

  2. SCHEMA-COMPAT FILTER: For each candidate, check whether its required
     parameters can plausibly be satisfied from the message + context +
     reasoning output. Tools that clearly cannot be satisfied (e.g. a
     comparison tool when the message has only one topic) are downranked
     or dropped.

  3. LLM PICK (only when needed): If top candidates are close in score,
     the reasoning says intent is ambiguous, or the top candidate is a
     fallback chat tool, an LLM is given the top-K list with their
     descriptions and the reasoning object, and picks one with a short
     justification. Otherwise we short-circuit to the ranker winner.

Output into state:
  selected_tool:       str
  tool_confidence:     float
  fallback_tools:      list[str]
  tool_candidates:     list[{tool, score, reason}]   # for envelope/meta
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from app.graph.state import OrchestratorState
from app.tools.registry import registry
from app.agents.llm_client import get_llm_client
from app.agents.logger import info, warn, append_step, STAGE_TOOL_SELECT


# ── Ranker (Stage 1) ──────────────────────────────────────────────────────────

INTENT_HINTS: Dict[str, List[str]] = {
    "learn_concept": ["explain", "concept", "understand"],
    "explain":       ["explain", "concept", "what is", "understand"],
    "practice":      ["practice", "quiz", "questions"],
    "quiz":          ["quiz", "test", "questions"],
    "flashcards":    ["flashcard", "card", "memorize", "recall"],
    "notes":         ["notes", "outline", "summary"],
    "solve":         ["solve", "step", "problem"],
    "review":        ["summary", "review", "recap"],
    "summary":       ["summary", "overview", "recap", "summarize"],
    "memorize":      ["flashcard", "mnemonic", "remember"],
    "mnemonic":      ["mnemonic", "memory trick"],
    "compare":       ["compare", "versus", "difference"],
    "create":        ["create", "generate", "build"],
    "visualize":     ["visual", "diagram", "map"],
    "mind_map":      ["mind map", "concept map"],
    "prepare_exam":  ["exam", "test", "mock"],
    "brainstorm":    ["prompt", "ideas", "brainstorm"],
}


def _tokenize(text: str) -> set:
    return set(re.findall(r"[a-zA-Z]{3,}", (text or "").lower()))


def _tool_tokens(meta: Dict[str, object]) -> set:
    tokens = _tokenize(str(meta.get("name", "")).replace("_", " "))
    tokens |= _tokenize(str(meta.get("description", "")))
    for p in meta.get("trigger_phrases", []) or []:
        tokens |= _tokenize(str(p))
    for p in meta.get("required_params", []) or []:
        tokens |= _tokenize(str(p).replace("_", " "))
    return tokens


def rank_tools(
    intent: str,
    message: str,
    keywords: List[str],
    top_n: int = 8,
) -> List[Tuple[str, float, str]]:
    """Returns list of (tool_name, score, reason)."""
    message_tokens = _tokenize(message) | {k.lower() for k in keywords}
    intent_tokens = set(INTENT_HINTS.get(intent, []))

    scored: List[Tuple[str, float, str]] = []
    for meta in registry.metadata_index():
        tool_name = str(meta["name"])
        tokens = _tool_tokens(meta)
        union = message_tokens | tokens
        overlap = (len(message_tokens & tokens) / len(union)) if union else 0.0
        intent_score = (
            len(intent_tokens & tokens) / max(1, len(intent_tokens))
            if intent_tokens else 0.0
        )
        score = 0.75 * overlap + 0.25 * intent_score

        # Build a short reason string
        hits = list((message_tokens & tokens))[:3]
        reason_bits = []
        if hits:
            reason_bits.append(f"keywords {hits}")
        if intent_tokens & tokens:
            reason_bits.append(f"intent match '{intent}'")
        reason = "; ".join(reason_bits) if reason_bits else "weak match"
        scored.append((tool_name, round(score, 3), reason))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]


# ── Schema-compat filter (Stage 2) ────────────────────────────────────────────

def _can_satisfy_schema(
    tool_name: str,
    message: str,
    reasoning: Dict[str, Any],
    context: Dict[str, Any],
) -> Tuple[bool, str]:
    """Heuristic check: can the required params plausibly be satisfied?

    Returns (can_satisfy, reason). We're conservative — we only flag clear
    impossibilities. Ambiguous cases pass through.
    """
    tool = registry.get(tool_name)
    if not tool:
        return False, "tool missing from registry"

    schema = tool.get_schema()
    js = schema.get("json_schema") or {}
    props = js.get("properties", {}) if isinstance(js, dict) else {}
    required = js.get("required", []) if isinstance(js, dict) else schema.get(
        "required_params", []
    )

    message_lower = (message or "").lower()

    # Comparison tools need two subjects in the message
    if tool_name in {"quick_compare"} and ("topic_a" in required or "topic_b" in required):
        # Heuristic: "X vs Y" or "compare A and B" or "difference between A and B"
        has_two_topics = bool(
            re.search(r"\bvs\b|\bversus\b", message_lower)
            or re.search(r"compare\s+\w+\s+(?:and|with|to)\s+\w+", message_lower)
            or re.search(r"difference\s+between\s+\w+\s+and\s+\w+", message_lower)
        )
        if not has_two_topics:
            return False, "comparison tool needs two explicit topics"

    # Pronunciation needs at least one word to pronounce
    if tool_name == "pronunciation_coach":
        if "pronounce" not in message_lower and "pronunciation" not in message_lower:
            return False, "pronunciation tool not indicated by message"

    # Debate tool needs a side or stance
    if tool_name == "debate_speech_generator":
        has_stance = bool(re.search(
            r"\b(for|against|pro|con|support|oppose|debate)\b", message_lower
        ))
        if not has_stance:
            return False, "debate tool needs a stance"

    return True, "schema satisfiable"


# ── LLM pick (Stage 3) ────────────────────────────────────────────────────────

_PICK_PROMPT = """You are selecting the single best educational tool for a student.

Student said: "{message}"

Reasoning step concluded:
  intent: {intent}
  thought: {thought}
  constraints: {constraints}

Top candidate tools (pre-ranked by keyword+intent scoring):
{candidates_block}

Pick the ONE tool that best serves the student. Consider:
- does the tool's purpose match the student's intent?
- can its required parameters be satisfied from the message?
- is there a better, more specific option?

Return ONLY JSON:
{{
  "selected": "tool_name_exactly_as_listed",
  "reason": "one short sentence"
}}
"""


async def _llm_pick(
    candidates: List[Tuple[str, float, str]],
    message: str,
    reasoning: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Ask the LLM to choose among candidates. Returns None on failure."""
    if not candidates:
        return None

    lines = []
    for name, score, reason in candidates:
        tool = registry.get(name)
        if not tool:
            continue
        desc = tool.description or ""
        lines.append(f"- {name} (score {score:.2f}): {desc[:120]}")
    candidates_block = "\n".join(lines)

    prompt = _PICK_PROMPT.format(
        message=message,
        intent=reasoning.get("intent", "unknown"),
        thought=reasoning.get("thought", ""),
        constraints=reasoning.get("constraints", []),
        candidates_block=candidates_block,
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
                    parsed = json.loads(cleaned[start : i + 1])
                except json.JSONDecodeError:
                    return None
                # Validate the pick is actually in the candidate list
                if parsed.get("selected") in {c[0] for c in candidates}:
                    return parsed
                return None
    return None


# ── Selection strategy ────────────────────────────────────────────────────────

def _needs_llm_pick(
    ranked: List[Tuple[str, float, str]],
    reasoning: Dict[str, Any],
) -> bool:
    """Decide whether to invoke the LLM pick or trust the ranker."""
    if not ranked:
        return False

    top_score = ranked[0][1]
    # Very confident ranker winner → trust it
    if top_score >= 0.5:
        return False
    # Top candidate is the fallback chat tool → always LLM pick
    if ranked[0][0] == "direct_chat_responder":
        return True
    # Two candidates very close → tie-break with LLM
    if len(ranked) >= 2 and (ranked[0][1] - ranked[1][1]) < 0.05 and ranked[0][1] > 0.2:
        return True
    # Ranker winner below threshold AND reasoning is confident → LLM pick
    if top_score < 0.3 and reasoning.get("confidence", 0) >= 0.6:
        return True
    return False


async def tool_selector_node(state: OrchestratorState) -> OrchestratorState:
    """Hybrid selection: rank → schema-filter → (optional) LLM pick."""
    intent = state.get("intent", "learn_concept")
    message = state["raw_message"]
    keywords = state.get("keywords", [])
    reasoning = state.get("reasoning", {}) or {}

    # If reasoning said no tool needed, route to direct chat
    if reasoning.get("requires_tool") is False:
        update = {
            **state,
            "selected_tool": "direct_chat_responder",
            "tool_confidence": reasoning.get("confidence", 0.6),
            "fallback_tools": [],
            "tool_candidates": [{
                "tool": "direct_chat_responder",
                "score": reasoning.get("confidence", 0.6),
                "reason": "reasoning concluded no structured tool needed",
            }],
        }
        return append_step(update, info(
            STAGE_TOOL_SELECT,
            "no structured tool needed per reasoning → direct_chat_responder",
        ))

    # Stage 1: rank
    ranked = rank_tools(intent, message, keywords, top_n=8)

    # Stage 2: schema-compat filter
    context = {
        "subject": state.get("subject", "general"),
        "mastery_level": (state.get("student_profile") or {}).get("mastery_level", 5),
    }
    filtered: List[Tuple[str, float, str]] = []
    dropped: List[Tuple[str, str]] = []
    for name, score, reason in ranked:
        ok, why = _can_satisfy_schema(name, message, reasoning, context)
        if ok:
            filtered.append((name, score, reason))
        else:
            dropped.append((name, why))

    if not filtered:
        # Nothing passed the filter. Fall back to original ranker.
        filtered = ranked

    # Prefer reasoning.intent-aligned tools: boost any candidate whose name
    # matches the reasoning step's intent label. We rewrite the score in
    # place (not just sort by a key) so the displayed candidate list
    # reflects the boost and isn't misleading.
    intent_hint = (reasoning.get("intent") or "").lower()
    if intent_hint and intent_hint not in {"unknown", "open_question"}:
        boosted: List[Tuple[str, float, str]] = []
        for name, score, reason in filtered:
            lname = name.lower()
            if intent_hint in lname or lname in intent_hint:
                new_score = min(1.0, score + 0.3)
                new_reason = f"{reason}; +intent-match boost (+0.30)"
                boosted.append((name, round(new_score, 3), new_reason))
            else:
                boosted.append((name, score, reason))
        filtered = sorted(boosted, key=lambda x: x[1], reverse=True)

    # Context Adaptation: Personalization Boosts
    profile = state.get("student_profile", {}) or {}
    t_style = (profile.get("teaching_style") or profile.get("learning_style") or "").lower()
    e_state = (profile.get("emotional_state") or profile.get("emotion") or state.get("mood") or "").lower()
    m_level = profile.get("mastery_level") or profile.get("learning_level") or 5
    try:
        m_level = int(m_level)
    except:
        m_level = 5

    if t_style or e_state or m_level:
        persona_boosted: List[Tuple[str, float, str]] = []
        for name, score, reason in filtered:
            bonus = 0.0
            p_reasons = []
            
            # Teaching Style Adaptation
            if "visual" in t_style and name in {"concept_visualizer", "mind_map", "timeline_designer", "slide_deck_generator", "visual_story_builder"}:
                bonus += 0.2
                p_reasons.append("visual style")
            elif "socratic" in t_style and name in {"quiz_me", "mock_test"}:
                bonus += 0.2
                p_reasons.append("socratic style")

            # Emotional State Adaptation
            if "anxious" in e_state:
                if name in {"mock_test", "debate_speech_generator"}:
                    bonus -= 0.3
                    p_reasons.append("anxious penalty")
                elif name in {"step_by_step_solver", "concept_explainer"}:
                    bonus += 0.1
                    p_reasons.append("anxious boost")
            elif "focused" in e_state or "motivated" in e_state:
                if name in {"simulation_generator", "mock_test", "debate_speech_generator"}:
                    bonus += 0.2
                    p_reasons.append("focused boost")

            # Mastery Level Adaptation
            if m_level <= 3 and name in {"flashcards", "quick_compare", "anchor_chart_maker"}:
                bonus += 0.15
                p_reasons.append(f"L{m_level} foundation boost")
            elif m_level >= 7 and name in {"podcast_maker", "quick_prompts"}:
                bonus += 0.15
                p_reasons.append(f"L{m_level} advanced boost")

            if bonus != 0.0:
                new_score = max(0.0, min(1.0, score + bonus))
                sign = "+" if bonus > 0 else ""
                new_reason = f"{reason}; {sign}{bonus:.2f} persona ({', '.join(p_reasons)})"
                persona_boosted.append((name, round(new_score, 3), new_reason))
            else:
                persona_boosted.append((name, score, reason))
        
        filtered = sorted(persona_boosted, key=lambda x: x[1], reverse=True)

    top_k = filtered[:3]

    # Stage 3: decide whether to invoke LLM pick
    candidates_for_meta = [
        {"tool": n, "score": s, "reason": r} for n, s, r in top_k
    ]

    selected_name: str
    selected_score: float
    pick_reason: str

    if _needs_llm_pick(filtered, reasoning):
        pick = await _llm_pick(top_k, message, reasoning)
        if pick:
            selected_name = pick["selected"]
            pick_reason = pick.get("reason", "LLM selection")
            # Score is whatever the ranker gave that tool
            selected_score = next(
                (s for n, s, _ in top_k if n == selected_name),
                0.5,
            )
            log_source = "llm_pick"
        else:
            selected_name, selected_score, pick_reason = top_k[0]
            log_source = "ranker_fallback"
    else:
        selected_name, selected_score, pick_reason = top_k[0]
        log_source = "ranker"

    fallbacks = [n for n, s, _ in filtered[1:4] if s > 0.2 and n != selected_name]

    # Safety: if the ranker completely failed AND LLM couldn't help, use
    # concept_explainer as the educational default (NOT direct_chat).
    if selected_score < 0.1 and selected_name == "direct_chat_responder":
        selected_name = "concept_explainer"
        selected_score = 0.4
        pick_reason = "low confidence; educational default"

    # Displayed confidence: blend the ranker score with the reasoning's
    # own confidence. A confident reasoner + weak keyword match shouldn't
    # show as "15% confidence" — that misleads users into distrusting a
    # correct choice. Rule: show max(ranker_score, 0.7 * reasoning_conf)
    # so a strong rule short-circuit can lift a weak ranker.
    reasoning_conf = float(reasoning.get("confidence", 0.0) or 0.0)
    displayed_conf = max(selected_score, 0.7 * reasoning_conf)

    update = {
        **state,
        "selected_tool": selected_name,
        "tool_confidence": round(displayed_conf, 3),
        "fallback_tools": fallbacks,
        "tool_candidates": candidates_for_meta,
    }
    return append_step(update, info(
        STAGE_TOOL_SELECT,
        f"selected={selected_name} conf={displayed_conf:.2f} "
        f"(ranker={selected_score:.2f}, reasoning={reasoning_conf:.2f}) "
        f"via {log_source}; top3={[c['tool'] for c in candidates_for_meta]}; "
        f"dropped={len(dropped)} schema-incompatible",
        reason=pick_reason,
    ))
