"""Note Maker tool — matches the Yophoria task-spec schema exactly.

Uses the new json_schema attribute so the validator enforces enums,
required fields, and types from a single source of truth.
"""
from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult


class NoteMaker(BaseTool):
    name = "note_maker"
    description = ("Generates structured study notes in outline, bullet, narrative, "
                   "or structured format, adapted to the student's level and style.")
    category = "learning"

    required_params = ["user_info", "chat_history", "topic", "subject", "note_taking_style"]
    optional_params = ["include_examples", "include_analogies"]
    param_defaults = {
        "include_examples": True,
        "include_analogies": False,
        "note_taking_style": "outline",
    }

    json_schema = {
        "type": "object",
        "required": ["user_info", "chat_history", "topic", "subject", "note_taking_style"],
        "properties": {
            "user_info": {
                "type": "object",
                "required": ["user_id", "name", "grade_level", "learning_style_summary", 
                             "emotional_state_summary", "mastery_level_summary"],
                "properties": {
                    "user_id": {"type": "string", "description": "Unique identifier for the student", "example": "student123"},
                    "name": {"type": "string", "description": "Student's full name", "example": "Harry"},
                    "grade_level": {"type": "string", "description": "Student's current grade level", "example": "10"},
                    "learning_style_summary": {"type": "string", "description": "Summary of student's preferred learning style", "example": "Prefers outlines and structured notes"},
                    "emotional_state_summary": {"type": "string", "description": "Current emotional state of the student", "example": "Relaxed and attentive"},
                    "mastery_level_summary": {"type": "string", "description": "Current mastery level description", "example": "Level 7 Proficient"}
                }
            },
            "chat_history": {
                "type": "array",
                "description": "Recent conversation history to provide context",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string", "enum": ["user", "assistant"], "description": "Role of the message sender"},
                        "content": {"type": "string", "description": "Content of the message"}
                    }
                }
            },
            "topic": {
                "type": "string",
                "description": "The main topic for note generation",
                "example": "Water Cycle"
            },
            "subject": {
                "type": "string",
                "description": "Academic subject area",
                "example": "Environmental Science"
            },
            "note_taking_style": {
                "type": "string",
                "enum": ["outline", "bullet_points", "narrative", "structured"],
                "description": "Preferred format for the notes"
            },
            "include_examples": {
                "type": "boolean",
                "description": "Whether to include examples in the notes",
                "default": True
            },
            "include_analogies": {
                "type": "boolean",
                "description": "Whether to include analogies in the notes",
                "default": False
            }
        }
    }

    def get_trigger_phrases(self) -> List[str]:
        return ["take notes", "make notes", "study notes", "outline", "summarize into notes"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        topic = params["topic"]
        subject = params["subject"]
        style = params.get("note_taking_style", "outline")
        include_examples = bool(params.get("include_examples", True))
        include_analogies = bool(params.get("include_analogies", False))

        # Deterministic mock output shaped to the spec's response format.
        sections = [
            {
                "title": f"Introduction to {topic}",
                "content": f"{topic} is a core idea in {subject}. "
                           f"This section gives the background needed before details.",
                "key_points": [
                    f"{topic} belongs to {subject}",
                    f"Why {topic} matters",
                ],
                "examples": [f"A simple case of {topic}"] if include_examples else [],
                "analogies": [f"{topic} is like a recipe: it gives you a procedure."]
                             if include_analogies else [],
            },
            {
                "title": f"Core ideas of {topic}",
                "content": f"The central ideas behind {topic}, organised for a "
                           f"{style} note format.",
                "key_points": [
                    f"Definition of {topic}",
                    f"Main properties of {topic}",
                    f"How {topic} is applied in {subject}",
                ],
                "examples": [f"Worked example of {topic}"] if include_examples else [],
                "analogies": [] if not include_analogies else
                             [f"Think of {topic} as a toolbox for {subject} problems."],
            },
        ]

        data = {
            "topic": topic,
            "title": f"Study notes on {topic}",
            "summary": f"A {style.replace('_', ' ')} overview of {topic} "
                       f"covering definition, key ideas, and applications.",
            "note_sections": sections,
            "key_concepts": [topic, f"{topic} prerequisites", f"{topic} applications"],
            "connections_to_prior_learning": [
                f"Builds on foundational ideas in {subject}",
            ],
            "visual_elements": [],
            "practice_suggestions": [
                f"Explain {topic} in your own words",
                f"Create three flashcards about {topic}",
            ],
            "source_references": [],
            "note_taking_style": style,
        }
        return ToolResult(success=True, data=data, metadata={"tool": self.name})
