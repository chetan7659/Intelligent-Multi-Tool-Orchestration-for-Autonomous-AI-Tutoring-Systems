from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult


class AnchorChartMaker(BaseTool):
    name = "anchor_chart_maker"
    description = "Create structured visual charts for classroom learning and concept clarity"
    category = "learning"

    required_params = ["topic", "subject"]
    optional_params = ["key_concepts", "grade_level", "chart_style", "num_sections"]
    param_defaults = {
        "key_concepts": [],
        "grade_level": "middle_school",
        "chart_style": "standard",
        "num_sections": 4,
    }

    def get_trigger_phrases(self) -> List[str]:
        return ["anchor chart", "visual chart", "classroom chart", "concept chart", "make a chart"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        topic = params["topic"]
        subject = params["subject"]
        grade_level = params.get("grade_level", "middle_school")
        num_sections = params.get("num_sections", 4)

        prompt = f"""Create a detailed anchor chart for the topic "{topic}" in the subject "{subject}" for {grade_level} students.

Structure the anchor chart with exactly {num_sections} sections. Return ONLY valid JSON in this format:
{{
  "title": "Anchor Chart: {topic}",
  "subject": "{subject}",
  "grade_level": "{grade_level}",
  "sections": [
    {{
      "heading": "Section title",
      "icon": "emoji icon",
      "content": ["bullet 1", "bullet 2", "bullet 3"],
      "color": "#hex_color"
    }}
  ],
  "key_vocabulary": ["word1", "word2", "word3"],
  "summary": "One sentence summary",
  "remember_this": "Key takeaway for students"
}}"""

        if llm_client:
            raw = await llm_client.generate(prompt)
            import json, re
            try:
                json_match = re.search(r'\{.*\}', raw, re.DOTALL)
                data = json.loads(json_match.group()) if json_match else {}
            except Exception:
                data = {"raw_response": raw}
        else:
            data = {
                "title": f"Anchor Chart: {topic}",
                "subject": subject,
                "grade_level": grade_level,
                "sections": [
                    {
                        "heading": "What is it?",
                        "icon": "📖",
                        "content": [f"Definition of {topic}", "Core principle", "Origin/Background"],
                        "color": "#4CAF50",
                    },
                    {
                        "heading": "Key Concepts",
                        "icon": "🔑",
                        "content": [f"Concept 1 of {topic}", "Concept 2", "Concept 3"],
                        "color": "#2196F3",
                    },
                    {
                        "heading": "Examples",
                        "icon": "💡",
                        "content": [f"Example 1 for {topic}", "Example 2", "Real-world application"],
                        "color": "#FF9800",
                    },
                    {
                        "heading": "Remember This!",
                        "icon": "⭐",
                        "content": ["Key formula or rule", "Common mistake to avoid", "Pro tip"],
                        "color": "#E91E63",
                    },
                ],
                "key_vocabulary": [f"{topic} term 1", f"{topic} term 2", f"{topic} term 3"],
                "summary": f"This anchor chart covers the fundamentals of {topic} in {subject}.",
                "remember_this": f"The most important thing about {topic} is understanding its core principle.",
            }

        return ToolResult(success=True, data=data, metadata={"tool": self.name, "params": params})
