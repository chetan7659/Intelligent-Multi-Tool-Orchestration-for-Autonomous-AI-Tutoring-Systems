from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult
import re, json




class Flashcards(BaseTool):
    name = "flashcards"
    description = "Generate interactive flashcards for revision and memory retention"
    category = "assessment"
    required_params = ["user_info", "topic", "count", "difficulty", "subject"]
    optional_params = ["include_examples"]
    param_defaults = {
        "count": 10,
        "difficulty": "medium",
        "include_examples": True,
    }

    # JSON-Schema-style definition aligned with the Yophoria task spec.
    json_schema = {
        "type": "object",
        "required": ["user_info", "topic", "count", "difficulty", "subject"],
        "properties": {
            "user_info": {
                "type": "object",
                "required": ["user_id", "name", "grade_level", "learning_style_summary", 
                             "emotional_state_summary", "mastery_level_summary"],
                "properties": {
                    "user_id": {"type": "string", "description": "Unique identifier for the student", "example": "student123"},
                    "name": {"type": "string", "description": "Student's full name", "example": "Charlie"},
                    "grade_level": {"type": "string", "description": "Student's current grade level", "example": "8"},
                    "learning_style_summary": {"type": "string", "description": "Summary of student's preferred learning style", "example": "Kinesthetic learner, learns best through practice and repetition"},
                    "emotional_state_summary": {"type": "string", "description": "Current emotional state of the student", "example": "Focused and motivated to improve"},
                    "mastery_level_summary": {"type": "string", "description": "Current mastery level description", "example": "Level 6 Good understanding, ready for application"}
                }
            },
            "topic": {"type": "string", "description": "The topic for flashcard generation", "example": "Photosynthesis"},
            "count": {"type": "integer", "minimum": 1, "maximum": 20, "description": "Number of flashcards to generate", "example": 5},
            "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"], "description": "Difficulty level of the flashcards", "example": "medium"},
            "include_examples": {"type": "boolean", "description": "Whether to include examples in flashcards", "default": True},
            "subject": {"type": "string", "description": "Academic subject area", "example": "Biology"},
        },
    }

    def get_trigger_phrases(self):
        return ["flashcard", "flash card", "memorize", "recall", "review cards", "study cards"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        topic = params["topic"]
        subject = params["subject"]
        # Prefer spec-standard 'count', fall back to legacy 'num_cards'
        num_cards = min(int(params.get("count") or params.get("num_cards", 10)), 20)

        difficulty = params.get("difficulty", "medium")
        include_examples = bool(params.get("include_examples", True))
        
        data = {
            "flashcards": [
                {
                    "title": f"{topic} Concept {i+1}",
                    "question": f"What is a key aspect of {topic}?",
                    "answer": f"This is the explanation of aspect {i+1} of {topic} in {subject}.",
                    "example": f"For instance, when looking at {topic}..." if include_examples else "",
                } for i in range(num_cards)
            ],
            "topic": topic,
            "adaptation_details": f"Generated {num_cards} cards at {difficulty} difficulty, tailored for this subject.",
            "difficulty": difficulty
        }
        return ToolResult(success=True, data=data, metadata={"tool": self.name})


