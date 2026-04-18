from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult




class QuickCompare(BaseTool):
    name = "quick_compare"
    description = "Compare two topics side-by-side for better understanding"
    category = "memory"
    required_params = ["topic_a", "topic_b"]
    optional_params = ["subject", "comparison_criteria", "format"]
    param_defaults = {"subject": "general", "format": "table", "comparison_criteria": []}

    def get_trigger_phrases(self):
        return ["compare", "difference between", "vs", "versus", "contrast", "similarities", "how are they different"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        a, b = params["topic_a"], params["topic_b"]
        subject = params.get("subject", "general")

        criteria = ["Definition", "Key Properties", "Applications", "Formula/Rule",
                    "Advantages", "Limitations", "When to Use", "Examples"]

        data = {
            "topic_a": a, "topic_b": b, "subject": subject,
            "comparison_table": [
                {
                    "criterion": c,
                    "topic_a": f"{a}: {c.lower()} description",
                    "topic_b": f"{b}: {c.lower()} description",
                } for c in criteria
            ],
            "similarities": [
                f"Both {a} and {b} are concepts in {subject}",
                f"Both require understanding of fundamental {subject} principles",
                f"Both have practical applications in real-world {subject} problems",
            ],
            "key_differences": [
                f"{a} focuses on X while {b} focuses on Y",
                f"{a} is used when... while {b} is used when...",
                f"The main distinction: {a} vs {b} in terms of scope/application",
            ],
            "quick_rule": f"Use {a} when [condition A]. Use {b} when [condition B].",
            "memory_trick": f"'{a}' sounds like [association] — '{b}' sounds like [association]",
            "venn_diagram": {
                "only_a": [f"Unique to {a}: property 1", f"Unique to {a}: property 2"],
                "shared": [f"Both share: characteristic 1", f"Both share: characteristic 2"],
                "only_b": [f"Unique to {b}: property 1", f"Unique to {b}: property 2"],
            },
        }
        return ToolResult(success=True, data=data, metadata={"tool": self.name})


