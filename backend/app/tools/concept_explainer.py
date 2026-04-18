from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult


class ConceptExplainer(BaseTool):
    name = "concept_explainer"
    description = "Explains concepts in simple terms with examples for better understanding"
    category = "learning"

    required_params = ["user_info", "chat_history", "concept_to_explain", "current_topic", "desired_depth"]
    optional_params = []
    param_defaults = {
        "desired_depth": "intermediate",
    }

    # JSON-Schema-style definition aligned with the Yophoria task spec.
    json_schema = {
        "type": "object",
        "required": ["user_info", "chat_history", "concept_to_explain", "current_topic", "desired_depth"],
        "properties": {
            "user_info": {
                "type": "object",
                "required": ["user_id", "name", "grade_level", "learning_style_summary", 
                             "emotional_state_summary", "mastery_level_summary"],
                "properties": {
                    "user_id": {"type": "string", "description": "Unique identifier for the student", "example": "student123"},
                    "name": {"type": "string", "description": "Student's full name", "example": "Bob"},
                    "grade_level": {"type": "string", "description": "Student's current grade level", "example": "7"},
                    "learning_style_summary": {"type": "string", "description": "Summary of student's preferred learning style", "example": "Auditory learner, prefers simple terms and step-by-step explanations"},
                    "emotional_state_summary": {"type": "string", "description": "Current emotional state of the student", "example": "Curious and engaged in learning"},
                    "mastery_level_summary": {"type": "string", "description": "Current mastery level description", "example": "Level 4 Building foundational knowledge"}
                }
            },
            "chat_history": {
                "type": "array",
                "description": "Recent conversation history for context",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string", "enum": ["user", "assistant"]},
                        "content": {"type": "string"}
                    }
                }
            },
            "concept_to_explain": {
                "type": "string",
                "description": "The specific concept to explain",
                "example": "photosynthesis"
            },
            "current_topic": {
                "type": "string",
                "description": "Broader topic context",
                "example": "biology"
            },
            "desired_depth": {
                "type": "string",
                "enum": ["basic", "intermediate", "advanced", "comprehensive"],
                "description": "Level of detail for the explanation",
                "example": "medium"
            }
        }
    }

    def get_trigger_phrases(self) -> List[str]:
        return ["explain", "what is", "what are", "tell me about", "help me understand", "I don't understand"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        concept = params.get("concept_to_explain", "the concept")
        topic = params.get("current_topic", "general")
        depth = params.get("desired_depth", "intermediate")

        prompt = f"""Explain the concept "{concept}" from {topic} with a "{depth}" level of detail.

Return ONLY valid JSON exactly matching the following format:
{{
  "explanation": "Main explanation text",
  "examples": ["Practical example 1", "Practical example 2"],
  "related_concepts": ["Concept 1", "Concept 2"],
  "visual_aids": ["Suggestion for visual representation 1"],
  "practice_questions": ["Question 1", "Question 2"],
  "source_references": ["Reference link 1"]
}}"""

        if llm_client:
            raw = await llm_client.generate(prompt)
            import json, re
            try:
                json_match = re.search(r'\{.*\}', raw, re.DOTALL)
                data = json.loads(json_match.group()) if json_match else {"raw_response": raw}
            except Exception:
                data = {"raw_response": raw}
        else:
            data = {
                "explanation": f"The concept '{concept}' is an important part of '{topic}'. At a '{depth}' level, it revolves around specific foundational processes.",
                "examples": [
                    f"If you encounter {concept} in exams, remember example A.",
                    f"In real life, {concept} looks like example B."
                ],
                "related_concepts": [
                    f"Pre-requisite to {concept}",
                    f"Advanced application of {concept}"
                ],
                "visual_aids": [
                    f"A concept map showing how {concept} links to {topic}."
                ],
                "practice_questions": [
                    f"How does {concept} function?",
                    f"Why is {concept} critical for {topic}?"
                ],
                "source_references": [
                    f"Standard textbook on {topic}"
                ]
            }

        return ToolResult(success=True, data=data, metadata={"tool": self.name})
