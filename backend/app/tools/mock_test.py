from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult
import re, json




class MockTest(BaseTool):
    name = "mock_test"
    description = "Create practice exams tailored for speed and accuracy improvement"
    category = "assessment"
    required_params = ["subject", "topics"]
    optional_params = ["difficulty", "num_questions", "time_limit_minutes", "question_types", "exam_board"]
    param_defaults = {
        "difficulty": "intermediate",
        "num_questions": 20,
        "time_limit_minutes": 40,
        "question_types": ["mcq", "short_answer"],
        "exam_board": "general",
    }

    def get_trigger_phrases(self):
        return ["mock test", "practice exam", "full test", "timed test", "exam prep", "simulate exam"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        subject = params["subject"]
        topics = params.get("topics", [subject])
        if isinstance(topics, str):
            topics = [topics]
        n = min(int(params.get("num_questions", 20)), 30)

        questions = []
        for i in range(n):
            q_type = ["mcq", "short_answer", "true_false"][i % 3]
            topic = topics[i % len(topics)]
            if q_type == "mcq":
                questions.append({
                    "id": i + 1, "type": "mcq", "topic": topic,
                    "question": f"Which of the following best describes {topic}?",
                    "options": {"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"},
                    "correct_answer": "A",
                    "explanation": f"Option A is correct because it accurately describes {topic}.",
                    "marks": 1,
                    "difficulty": params.get("difficulty", "intermediate"),
                })
            elif q_type == "true_false":
                questions.append({
                    "id": i + 1, "type": "true_false", "topic": topic,
                    "question": f"True or False: {topic} is a fundamental concept in {subject}.",
                    "correct_answer": "True",
                    "explanation": f"This is true because {topic} forms a core part of {subject}.",
                    "marks": 1, "difficulty": "easy",
                })
            else:
                questions.append({
                    "id": i + 1, "type": "short_answer", "topic": topic,
                    "question": f"Briefly explain the significance of {topic} in {subject}.",
                    "model_answer": f"{topic} is significant in {subject} because it provides the foundation for understanding...",
                    "key_points": [f"Key point 1 about {topic}", f"Key point 2 about {topic}"],
                    "marks": 3, "difficulty": params.get("difficulty", "intermediate"),
                })

        data = {
            "test_title": f"{subject} Mock Exam",
            "subject": subject,
            "topics_covered": topics,
            "total_questions": n,
            "total_marks": sum(q.get("marks", 1) for q in questions),
            "time_limit_minutes": params.get("time_limit_minutes", 40),
            "instructions": [
                "Read each question carefully before answering",
                f"You have {params.get('time_limit_minutes', 40)} minutes",
                "Attempt all questions",
                "Show working for calculation questions",
            ],
            "questions": questions,
            "marking_scheme": {"A": "90-100%", "B": "80-89%", "C": "70-79%", "D": "60-69%", "F": "Below 60%"},
        }
        return ToolResult(success=True, data=data, metadata={"tool": self.name})


