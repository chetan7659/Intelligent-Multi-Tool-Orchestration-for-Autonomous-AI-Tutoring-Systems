from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult




class QuickPrompts(BaseTool):
    name = "quick_prompts"
    description = "Generate creative prompts for brainstorming ideas"
    category = "creative"
    required_params = ["subject_or_theme"]
    optional_params = ["num_prompts", "prompt_type", "difficulty", "age_group"]
    param_defaults = {"num_prompts": 8, "prompt_type": "mixed", "difficulty": "intermediate", "age_group": "teen"}

    def get_trigger_phrases(self):
        return ["prompt", "brainstorm", "give me ideas", "creative prompts", "writing prompts", "idea starters"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        theme = params["subject_or_theme"]
        n = min(int(params.get("num_prompts", 8)), 20)
        types = ["creative_writing", "research", "discussion", "project", "experiment", "debate", "visual", "reflection"]

        data = {
            "theme": theme,
            "prompts": [
                {
                    "id": i + 1,
                    "type": types[i % len(types)],
                    "prompt": f"Prompt {i+1}: [{types[i % len(types)].replace('_',' ').title()} prompt about {theme}]",
                    "starter_sentence": f"I want to explore {theme} by...",
                    "thinking_questions": [f"What do you know about {theme}?", f"What surprises you about {theme}?"],
                    "difficulty": params.get("difficulty", "intermediate"),
                } for i in range(n)
            ],
            "category_breakdown": {t: sum(1 for i in range(n) if types[i % len(types)] == t) for t in types},
            "warm_up_prompt": f"In one sentence, what do you already know about {theme}?",
            "challenge_prompt": f"Advanced challenge: How does {theme} connect to something completely different?",
        }
        return ToolResult(success=True, data=data, metadata={"tool": self.name})


