from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult




class StepByStepSolver(BaseTool):
    name = "step_by_step_solver"
    description = "Solves problems with clear, structured explanations"
    category = "assessment"
    required_params = ["problem", "subject"]
    optional_params = ["show_working", "difficulty", "hints_only"]
    param_defaults = {"show_working": True, "hints_only": False}

    def get_trigger_phrases(self):
        return ["solve", "help me solve", "step by step", "how do I", "walk me through", "show working"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        problem = params["problem"]
        subject = params["subject"]

        data = {
            "problem": problem,
            "subject": subject,
            "approach": f"To solve this {subject} problem, we use a systematic approach",
            "steps": [
                {"step": 1, "title": "Understand the Problem", "action": f"Read '{problem}' carefully and identify what we need to find.", "explanation": "Identifying knowns and unknowns is the first key step."},
                {"step": 2, "title": "Identify the Method", "action": "Select the appropriate formula/method for this type of problem.", "explanation": "Choosing the right tool saves time and ensures accuracy."},
                {"step": 3, "title": "Set Up", "action": "Write out the formula/framework and substitute known values.", "explanation": "Proper setup prevents errors in later steps."},
                {"step": 4, "title": "Solve", "action": "Perform the calculation or apply the method step by step.", "explanation": "Take it one operation at a time."},
                {"step": 5, "title": "Verify", "action": "Check your answer makes sense in context.", "explanation": "Always sanity-check your final answer."},
            ],
            "final_answer": f"The solution to the given problem in {subject}.",
            "common_mistakes": ["Skipping the verification step", "Not clearly defining variables", "Arithmetic errors in step 4"],
            "similar_problems": [f"Try similar problem: variant 1", f"Try similar problem: variant 2"],
            "key_formulas_used": [f"Primary formula for this type of {subject} problem"],
        }
        return ToolResult(success=True, data=data, metadata={"tool": self.name})


