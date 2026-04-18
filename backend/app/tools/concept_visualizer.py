from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult
import re, json




class ConceptVisualizer(BaseTool):
    name = "concept_visualizer"
    description = "Converts abstract ideas into visual representations using AI"
    category = "learning"
    required_params = ["concept", "subject"]
    optional_params = ["visualization_type", "complexity", "elements"]
    param_defaults = {"visualization_type": "diagram", "complexity": "medium", "elements": []}

    def get_trigger_phrases(self):
        return ["visualize", "show me", "draw", "diagram", "picture", "visual representation"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        concept, subject = params["concept"], params["subject"]
        viz_type = params.get("visualization_type", "diagram")

        prompt = f"""Create a visual representation plan for "{concept}" in {subject} as a {viz_type}.
Return ONLY valid JSON:
{{
  "concept": "{concept}",
  "visualization_type": "{viz_type}",
  "title": "Visual title",
  "description": "What this visualization shows",
  "elements": [
    {{"id": "1", "label": "Element 1", "type": "node", "x": 100, "y": 100, "color": "#4CAF50", "size": "large"}},
    {{"id": "2", "label": "Element 2", "type": "node", "x": 300, "y": 100, "color": "#2196F3", "size": "medium"}}
  ],
  "connections": [
    {{"from": "1", "to": "2", "label": "connects to", "style": "arrow"}}
  ],
  "legend": [{{"color": "#4CAF50", "meaning": "Main concept"}}],
  "interpretation": "How to read this visualization"
}}"""

        if llm_client:
            raw = await llm_client.generate(prompt)
            try:
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                data = json.loads(m.group()) if m else {"raw_response": raw}
            except Exception:
                data = {"raw_response": raw}
        else:
            data = {
                "concept": concept, "visualization_type": viz_type,
                "title": f"Visual Map: {concept}",
                "description": f"A {viz_type} showing the structure of {concept} in {subject}",
                "elements": [
                    {"id": "1", "label": concept, "type": "central_node", "x": 400, "y": 300, "color": "#FF6B6B", "size": "xl"},
                    {"id": "2", "label": "Property A", "type": "node", "x": 200, "y": 150, "color": "#4ECDC4", "size": "large"},
                    {"id": "3", "label": "Property B", "type": "node", "x": 600, "y": 150, "color": "#45B7D1", "size": "large"},
                    {"id": "4", "label": "Application 1", "type": "leaf", "x": 100, "y": 400, "color": "#96CEB4", "size": "medium"},
                    {"id": "5", "label": "Application 2", "type": "leaf", "x": 700, "y": 400, "color": "#FFEAA7", "size": "medium"},
                ],
                "connections": [
                    {"from": "1", "to": "2", "label": "has", "style": "solid"},
                    {"from": "1", "to": "3", "label": "has", "style": "solid"},
                    {"from": "2", "to": "4", "label": "leads to", "style": "dashed"},
                    {"from": "3", "to": "5", "label": "leads to", "style": "dashed"},
                ],
                "legend": [{"color": "#FF6B6B", "meaning": "Core concept"}, {"color": "#4ECDC4", "meaning": "Properties"}],
                "interpretation": f"Start from the center ({concept}) and follow the arrows to understand its properties and applications.",
            }
        return ToolResult(success=True, data=data, metadata={"tool": self.name})


