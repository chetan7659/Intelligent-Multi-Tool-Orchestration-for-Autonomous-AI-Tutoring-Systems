from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult
import re, json




class RhymeRapComposer(BaseTool):
    name = "rhyme_rap_composer"
    description = "Turns topics into rhymes or rap for fun and memorable learning"
    category = "communication"
    required_params = ["topic", "subject"]
    optional_params = ["style", "length", "difficulty", "include_facts"]
    param_defaults = {"style": "rap", "length": "short", "include_facts": True}

    def get_trigger_phrases(self):
        return ["rhyme", "rap", "song", "poem", "make it fun", "creative", "catchy"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        topic = params["topic"]
        subject = params["subject"]
        style = params.get("style", "rap")

        data = {
            "topic": topic,
            "subject": subject,
            "style": style,
            "verses": [
                {
                    "verse_number": 1,
                    "lyrics": f"Yo, let me tell you 'bout {topic} today,\nIn {subject} class, listen to what I say,\nIt's not that hard, just follow my lead,\n{topic} is exactly what you need!",
                    "educational_content": f"Introduces {topic} and its importance in {subject}",
                },
                {
                    "verse_number": 2,
                    "lyrics": f"First thing to know about {topic} right here,\nThe concept is simple when you see it clear,\nApply the formula, step by step,\nYou'll ace your exam, no need to fret!",
                    "educational_content": f"Covers key aspects of {topic}",
                },
            ],
            "chorus": f"Oh {topic}, {topic},\nMake it stick in your brain!\n{topic}, {topic},\nLet's do it again!",
            "key_facts_embedded": [f"Key fact 1 about {topic}", f"Key fact 2 about {topic}"],
            "memory_hooks": [f"Rhyme to remember: {topic} rhymes with..."],
            "beat_description": "Medium tempo, 90 BPM, educational hip-hop style",
        }
        return ToolResult(success=True, data=data, metadata={"tool": self.name})


