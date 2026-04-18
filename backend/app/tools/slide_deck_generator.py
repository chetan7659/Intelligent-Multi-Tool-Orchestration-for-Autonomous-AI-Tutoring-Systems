from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult




class SlideDeckGenerator(BaseTool):
    name = "slide_deck_generator"
    description = "Create presentation slides for lessons and teaching"
    category = "structured"
    required_params = ["topic", "subject"]
    optional_params = ["num_slides", "audience", "presentation_style", "include_activities", "color_theme"]
    param_defaults = {"num_slides": 10, "audience": "students", "presentation_style": "educational", "include_activities": True, "color_theme": "modern_blue"}

    def get_trigger_phrases(self):
        return ["slides", "presentation", "slide deck", "powerpoint", "lesson slides", "present"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        topic = params["topic"]
        subject = params["subject"]
        n = min(int(params.get("num_slides", 10)), 20)
        theme = params.get("color_theme", "modern_blue")

        slide_templates = [
            {"type": "title", "layout": "center_title"},
            {"type": "agenda", "layout": "bullet_list"},
            {"type": "concept", "layout": "two_column"},
            {"type": "example", "layout": "full_content"},
            {"type": "activity", "layout": "interactive"},
            {"type": "diagram", "layout": "visual_center"},
            {"type": "summary", "layout": "key_points"},
            {"type": "quiz", "layout": "question_answer"},
            {"type": "resources", "layout": "link_list"},
            {"type": "conclusion", "layout": "closing"},
        ]

        slides = []
        for i in range(min(n, len(slide_templates))):
            t = slide_templates[i]
            slides.append({
                "slide_number": i + 1,
                "type": t["type"],
                "layout": t["layout"],
                "title": [
                    f"{topic}: A Complete Guide",
                    "Today's Agenda",
                    f"Core Concept: {topic}",
                    f"Example: {topic} in Action",
                    "Let's Practice!",
                    f"Visual Overview of {topic}",
                    f"Key Takeaways: {topic}",
                    "Quick Knowledge Check",
                    "Further Resources",
                    "Thank You & Questions",
                ][i],
                "content": {
                    "main_text": f"Content for slide {i+1} about {topic}",
                    "bullet_points": [f"Key point {j+1} about {topic}" for j in range(3)],
                    "speaker_notes": f"Instructor note for slide {i+1}: Emphasize the importance of {topic} here.",
                    "visual_suggestion": f"Image/diagram suggestion for {topic} slide {i+1}",
                    "animation": "fade_in",
                },
                "estimated_time_minutes": 2,
            })

        data = {
            "presentation_title": f"{topic}: A Complete Guide",
            "subject": subject, "topic": topic,
            "num_slides": len(slides),
            "total_time_minutes": len(slides) * 2,
            "color_theme": theme,
            "font": "Inter",
            "slides": slides,
            "presenter_guide": {
                "introduction": f"Start by asking students what they already know about {topic}",
                "pacing": "Spend 2 minutes per slide, pause for questions on concept slides",
                "closing": f"End with the quiz slide to assess understanding of {topic}",
            },
        }
        return ToolResult(success=True, data=data, metadata={"tool": self.name})


