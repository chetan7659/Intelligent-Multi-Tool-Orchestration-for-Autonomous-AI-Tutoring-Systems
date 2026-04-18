from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult




class SummaryGenerator(BaseTool):
    name = "summary_generator"
    description = "Produces concise summaries of topics or lessons"
    category = "memory"
    required_params = ["topic_or_text", "subject"]
    optional_params = ["length", "format", "include_key_points", "audience"]
    param_defaults = {"length": "medium", "format": "structured", "include_key_points": True, "audience": "student"}

    def get_trigger_phrases(self):
        return ["summarize", "summary", "tldr", "brief overview", "key points", "wrap up", "overview"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        topic = params["topic_or_text"]
        subject = params["subject"]
        length = params.get("length", "medium")
        word_count = {"short": 100, "medium": 250, "long": 500}.get(length, 250)

        data = {
            "topic": topic,
            "subject": subject,
            "length": length,
            "target_word_count": word_count,
            "executive_summary": f"{topic} is a core concept in {subject} that covers fundamental principles and their applications. Understanding {topic} enables students to tackle more complex problems in the subject.",
            "key_points": [
                {"point": f"Key Point 1: Definition and scope of {topic}", "importance": "high"},
                {"point": f"Key Point 2: Main principles of {topic}", "importance": "high"},
                {"point": f"Key Point 3: Applications in {subject}", "importance": "medium"},
                {"point": f"Key Point 4: Common examples", "importance": "medium"},
                {"point": f"Key Point 5: Connections to other topics", "importance": "low"},
            ],
            "structured_summary": {
                "introduction": f"This summary covers {topic} as part of {subject}.",
                "main_body": f"{topic} encompasses several important aspects. First, its definition establishes the scope. Second, key principles guide its application. Third, examples in {subject} make it concrete.",
                "conclusion": f"Mastering {topic} is essential for progress in {subject}.",
            },
            "quick_revision_bullets": [
                f"✓ {topic} = core concept in {subject}",
                f"✓ Key principle: [main rule/formula]",
                f"✓ Remember: [most important fact]",
                f"✓ Don't confuse with: [similar concept]",
            ],
            "further_reading": [f"Chapter on {topic} in your {subject} textbook", f"Practice problems on {topic}"],
        }
        return ToolResult(success=True, data=data, metadata={"tool": self.name})


