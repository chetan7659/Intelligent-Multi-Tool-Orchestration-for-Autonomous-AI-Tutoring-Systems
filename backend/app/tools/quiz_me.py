from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult
import re, json




class QuizMe(BaseTool):
    name = "quiz_me"
    description = "Generate quizzes to test knowledge with or without exam pressure"
    category = "assessment"
    required_params = ["topic", "subject"]
    optional_params = ["difficulty", "num_questions", "question_type", "time_pressure"]
    param_defaults = {"difficulty": "beginner", "num_questions": 5, "question_type": "mcq", "time_pressure": False}

    def get_trigger_phrases(self):
        return ["quiz", "quiz me", "test me", "practice problems", "question", "test my knowledge"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        topic = params["topic"]
        subject = params["subject"]
        n = min(int(params.get("num_questions", 5)), 15)
        difficulty = params.get("difficulty", "beginner")

        data = {
            "quiz_title": f"{topic} Quiz",
            "subject": subject,
            "topic": topic,
            "difficulty": difficulty,
            "num_questions": n,
            "time_pressure": params.get("time_pressure", False),
            "recommended_time_per_q": "60 seconds" if not params.get("time_pressure") else "30 seconds",
            "questions": [
                {
                    "id": i + 1,
                    "question": f"Q{i+1}: What do you know about this aspect of {topic}?",
                    "options": [
                        {"label": "A", "text": f"This is the correct answer about {topic}", "is_correct": True},
                        {"label": "B", "text": "This is a plausible distractor", "is_correct": False},
                        {"label": "C", "text": "This is another distractor", "is_correct": False},
                        {"label": "D", "text": "This is the last distractor", "is_correct": False},
                    ],
                    "explanation": f"The correct answer explains a key aspect of {topic} in {subject}.",
                    "difficulty": difficulty,
                    "hint": f"Hint: Think about the core principle of {topic}",
                } for i in range(n)
            ],
            "scoring": {"correct": "+1", "incorrect": "0", "skipped": "0"},
            "passing_score": f"{int(n * 0.6)}/{n}",
        }
        return ToolResult(success=True, data=data, metadata={"tool": self.name})
