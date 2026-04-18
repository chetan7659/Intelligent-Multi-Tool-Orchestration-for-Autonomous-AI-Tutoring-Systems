from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult
import re, json




class DebateSpeechGenerator(BaseTool):
    name = "debate_speech_generator"
    description = "Generates debate topics and structured speeches for practice"
    category = "communication"
    required_params = ["topic"]
    optional_params = ["side", "speech_type", "duration_minutes", "subject", "include_counterarguments"]
    param_defaults = {"side": "for", "speech_type": "debate", "duration_minutes": 5, "include_counterarguments": True}

    def get_trigger_phrases(self):
        return ["debate", "speech", "argument", "persuade", "argue for", "pros and cons"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        topic = params["topic"]
        side = params.get("side", "for")
        duration = params.get("duration_minutes", 5)

        data = {
            "topic": topic,
            "side": side,
            "estimated_duration": f"{duration} minutes",
            "speech_structure": {
                "hook": f"Opening hook for {side} position on '{topic}'",
                "thesis": f"My position is that {topic} is {'beneficial' if side == 'for' else 'problematic'} because...",
                "argument_1": {
                    "point": "First main argument",
                    "evidence": "Supporting evidence and statistics",
                    "explanation": "Why this supports your position",
                },
                "argument_2": {
                    "point": "Second main argument",
                    "evidence": "Supporting evidence",
                    "explanation": "Connection to thesis",
                },
                "argument_3": {
                    "point": "Third main argument",
                    "evidence": "Supporting examples",
                    "explanation": "Broader impact",
                },
                "counterargument": f"Some argue against this position, however...",
                "rebuttal": "Counter the opposition with: ...",
                "conclusion": f"In conclusion, {topic} {('benefits' if side == 'for' else 'harms')} us because of these compelling reasons.",
            },
            "power_words": ["compelling", "evidently", "fundamentally", "critically", "undeniably"],
            "transition_phrases": ["Furthermore,", "In addition,", "Most importantly,", "As a result,"],
            "practice_tips": ["Maintain eye contact", "Speak at 130-150 words per minute", "Use pauses for emphasis"],
        }
        return ToolResult(success=True, data=data, metadata={"tool": self.name})


