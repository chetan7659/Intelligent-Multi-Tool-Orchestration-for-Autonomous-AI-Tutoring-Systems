from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ToolResult(BaseModel):
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class BaseTool(ABC):
    """Abstract base class for all educational tools.

    Two schema styles are supported:

      1. LEGACY (still works for all existing tools):
         required_params / optional_params / param_defaults / param_types.

      2. NEW (JSON-Schema-aware, for richer validation):
         json_schema — dict following a subset of JSON Schema draft-07,
         supporting: type, enum, minimum, maximum, description, required.

    When both are present the validator prefers json_schema.
    """

    name: str = ""
    description: str = ""
    category: str = ""

    # Legacy schema attrs
    required_params: List[str] = []
    optional_params: List[str] = []
    param_defaults: Dict[str, Any] = {}
    param_types: Dict[str, type] = {}

    # New: optional JSON-Schema-style definition
    json_schema: Optional[Dict[str, Any]] = None

    def get_schema(self) -> Dict[str, Any]:
        type_map = {
            key: (
                val.__name__
                if hasattr(val, "__name__")
                else str(val)
            )
            for key, val in self.param_types.items()
        }
        schema = {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "required_params": self.required_params,
            "optional_params": self.optional_params,
            "param_defaults": self.param_defaults,
            "param_types": type_map,
            "output_format": self.get_output_format(),
            "example_trigger_phrases": self.get_trigger_phrases(),
        }
        if self.json_schema:
            schema["json_schema"] = self.json_schema
        return schema

    def get_trigger_phrases(self) -> List[str]:
        return []

    def get_output_format(self) -> str:
        return "json"

    def apply_defaults(self, params: Dict[str, Any]) -> Dict[str, Any]:
        result = {**self.param_defaults, **params}
        return result

    def validate_params(self, params: Dict[str, Any]) -> tuple[bool, List[str]]:
        errors = []
        for req in self.required_params:
            if req not in params or params[req] is None:
                errors.append(f"Missing required parameter: {req}")
        return len(errors) == 0, errors

    @abstractmethod
    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        """Execute the tool with the given parameters."""
        pass

    def _build_prompt(self, template: str, params: Dict[str, Any]) -> str:
        """Fill a prompt template with parameters."""
        try:
            return template.format(**params)
        except KeyError as e:
            return template + f"\n\nParameters: {params}"
