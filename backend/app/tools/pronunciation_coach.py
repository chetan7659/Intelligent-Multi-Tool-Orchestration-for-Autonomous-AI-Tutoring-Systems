from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult
import re, json




class PronunciationCoach(BaseTool):
    name = "pronunciation_coach"
    description = "Helps improve pronunciation through guided practice"
    category = "communication"
    required_params = ["words_or_text", "language"]
    optional_params = ["focus_area", "difficulty", "native_language"]
    param_defaults = {"focus_area": "general", "difficulty": "beginner", "native_language": "English"}

    def get_trigger_phrases(self):
        return ["pronounce", "pronunciation", "how to say", "say correctly", "phonetics", "accent"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        text = params["words_or_text"]
        language = params["language"]

        words = text.split()[:10]  # limit to 10 words
        data = {
            "language": language,
            "words": [
                {
                    "word": word,
                    "phonetic": f"/{word.lower()}/",
                    "syllables": "-".join(list(word)),
                    "stress_pattern": "Primary stress on first syllable",
                    "sound_guide": f"Say '{word}' like...",
                    "common_mistakes": [f"Don't pronounce the silent letters in '{word}'"],
                    "practice_sentence": f"Practice: '{word}' sounds like this in context.",
                    "audio_tip": "Open mouth wider for vowel sounds",
                } for word in words
            ],
            "general_tips": [
                f"Focus on the unique sounds in {language} that differ from your native language",
                "Record yourself and compare with native speakers",
                "Practice tongue placement for difficult sounds",
            ],
            "mouth_exercises": ["Tongue twisters", "Minimal pairs practice", "Vowel stretching"],
        }
        return ToolResult(success=True, data=data, metadata={"tool": self.name})


