from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult
import re, json




class MindMap(BaseTool):
    name = "mind_map"
    description = "Build connected idea maps to understand relationships between concepts"
    category = "learning"
    required_params = ["central_topic"]
    optional_params = ["subject", "depth", "branches", "style"]
    param_defaults = {"depth": 3, "branches": 5, "style": "radial", "subject": "general"}

    def get_trigger_phrases(self):
        return ["mind map", "idea map", "brainstorm", "concept map", "map out", "connections"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        central = params["central_topic"]
        subject = params.get("subject", "general")
        branches = int(params.get("branches", 5))

        data = {
            "central_node": {"id": "root", "text": central, "level": 0, "color": "#FF6B6B"},
            "branches": [
                {
                    "id": f"branch_{i}",
                    "text": f"Aspect {i+1} of {central}",
                    "level": 1,
                    "color": ["#4ECDC4","#45B7D1","#96CEB4","#FFEAA7","#DDA0DD"][i % 5],
                    "children": [
                        {
                            "id": f"sub_{i}_{j}",
                            "text": f"Sub-concept {j+1}",
                            "level": 2,
                            "color": "#E8E8E8",
                        } for j in range(2)
                    ],
                } for i in range(min(branches, 5))
            ],
            "subject": subject,
            "style": params.get("style", "radial"),
            "total_nodes": 1 + branches + branches * 2,
        }
        return ToolResult(success=True, data=data, metadata={"tool": self.name})


