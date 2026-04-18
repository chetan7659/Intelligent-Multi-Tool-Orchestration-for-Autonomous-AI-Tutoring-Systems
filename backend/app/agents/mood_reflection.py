"""Agent 7: Mood Reflection Node — Personalization Engine.

Reviews the formatted response and rewrites tone/style based on student's
detected mood and mastery level. This ensures the AI genuinely adapts its
teaching methodology, not just its content.
"""
from app.graph.state import OrchestratorState
from app.agents.llm_client import get_llm_client

# Teaching style matrix keyed by mood
MOOD_TEACHING_STYLE = {
    "frustrated": {
        "tone": "warm, encouraging, patient, and reassuring",
        "style": "break it into very small steps, use relatable analogies, validate their feelings first",
        "opening": "start with empathy: acknowledge that it's okay to find this hard",
    },
    "anxious": {
        "tone": "calm, structured, confidence-building, and reassuring",
        "style": "use a numbered step-by-step structure, avoid overwhelming details, focus on what they already know",
        "opening": "start by reminding them what they already know well",
    },
    "curious": {
        "tone": "enthusiastic, exploratory, and engaging",
        "style": "go deeper with interesting facts, connect ideas to bigger concepts, ask a thought-provoking follow-up question",
        "opening": "match their curiosity energy, start with a fascinating hook",
    },
    "confident": {
        "tone": "concise, direct, and intellectually challenging",
        "style": "skip basics, go deeper, challenge them with edge cases or harder extensions",
        "opening": "assume prior knowledge, dive straight into the substance",
    },
    "motivated": {
        "tone": "energetic, actionable, and goal-oriented",
        "style": "give a clear path forward, include a practice challenge at the end",
        "opening": "affirm their drive and immediately give them something to act on",
    },
    "neutral": {
        "tone": "clear, professional, and educational",
        "style": "standard educational explanation with examples",
        "opening": "introduce the topic clearly",
    },
}


async def mood_reflection_node(state: OrchestratorState) -> OrchestratorState:
    """
    Agent 7: Mood Reflection — Personalization Engine.
    Rewrites the formatted response to match the student's emotional state
    and mastery level using Llama 3.3 70B.
    """
    mood = state.get("mood", "neutral")
    difficulty = state.get("difficulty", "intermediate")
    subject = state.get("subject", "general")
    formatted_response = state.get("formatted_response", "")
    personalization = state.get("personalization_plan", {})
    response_style = personalization.get("response_style", "standard")

    # Only rewrite if mood is non-neutral and response is non-empty
    if not formatted_response or mood == "neutral":
        return {
            **state,
            "workflow_steps": [f"✓ Agent 7 (Mood Reflection): no rewrite needed (mood={mood})"],
        }

    style = MOOD_TEACHING_STYLE.get(mood, MOOD_TEACHING_STYLE["neutral"])
    llm = get_llm_client()

    prompt = f"""You are a highly empathetic AI tutor personalizing a lesson response.

STUDENT CONTEXT:
- Emotional State (mood): {mood}
- Mastery Level: {difficulty}
- Subject: {subject}

TEACHING STYLE INSTRUCTIONS:
- Tone: {style["tone"]}
- Style: {style["style"]}
- Opening instruction: {style["opening"]}
- Preferred teaching style: {response_style}

ORIGINAL RESPONSE TO REWRITE:
\"\"\"
{formatted_response}
\"\"\"

TASK:
Rewrite the response above while:
1. Keeping ALL the factual content and key information intact.
2. Completely changing the TONE and STYLE to match the student's emotional state.
3. Adding a short motivational closer (1 sentence) appropriate for a {mood} student.
4. Keeping it roughly the same length. Do NOT add unnecessary padding.
5. If Preferred teaching style is visual, use compact bullets and structure cues.
6. If Preferred teaching style is concise, keep sentences short and direct.

Output ONLY the rewritten response. No preamble, no explanation.
"""

    try:
        rewritten = await llm.generate(prompt, max_tokens=1500, temperature=0.6)
        # Accept the rewrite only if the LLM returned a non-empty response
        if rewritten and len(rewritten) > 50:
            final = rewritten
        else:
            final = formatted_response
    except Exception:
        final = formatted_response

    return {
        **state,
        "formatted_response": final,
        "final_response": final,
        "workflow_steps": [f"✓ Agent 7 (Mood Reflection): rewrote response for mood={mood} ({len(final)} chars)"],
    }
