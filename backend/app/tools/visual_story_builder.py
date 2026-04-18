from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult




class VisualStoryBuilder(BaseTool):
    name = "visual_story_builder"
    description = "Create engaging visual stories with structured panels"
    category = "creative"
    required_params = ["topic", "subject"]
    optional_params = ["num_panels", "story_type", "characters", "setting", "age_group"]
    param_defaults = {"num_panels": 6, "story_type": "educational", "age_group": "teen"}

    def get_trigger_phrases(self):
        return ["story", "visual story", "comic", "narrative", "story board", "panel", "educational story"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        topic = params["topic"]
        subject = params["subject"]
        n_panels = min(int(params.get("num_panels", 6)), 12)

        panel_types = ["introduction", "rising_action", "complication", "climax", "resolution", "lesson"]

        data = {
            "title": f"The Story of {topic}",
            "subject": subject,
            "topic": topic,
            "characters": [
                {"name": "Alex", "role": "student", "description": "Curious learner struggling with " + topic},
                {"name": "Prof. Sage", "role": "mentor", "description": "Wise teacher who guides Alex"},
            ],
            "setting": f"A futuristic {subject} classroom where concepts come alive",
            "panels": [
                {
                    "panel": i + 1,
                    "type": panel_types[i % len(panel_types)],
                    "scene_description": f"Panel {i+1}: Scene depicting {['introduction of', 'exploration of', 'challenge with', 'breakthrough in', 'mastery of', 'celebration of'][i % 6]} {topic}",
                    "dialogue": [
                        {"character": "Alex", "text": f"I wonder how {topic} works..."},
                        {"character": "Prof. Sage", "text": f"Let me show you! {topic} is fascinating because..."},
                    ],
                    "educational_caption": f"Key learning: {topic} fact/concept {i+1}",
                    "visual_elements": [f"Visual element: {['textbook', 'formula board', 'experiment', 'lightbulb', 'trophy', 'stars'][i % 6]}"],
                    "mood": ["curious", "excited", "challenged", "discovering", "confident", "triumphant"][i % 6],
                } for i in range(n_panels)
            ],
            "moral_of_story": f"Persistence and curiosity are the keys to mastering {topic} in {subject}.",
            "discussion_questions": [f"What did Alex learn about {topic}?", f"How can you apply this in your own {subject} learning?"],
        }
        return ToolResult(success=True, data=data, metadata={"tool": self.name})


