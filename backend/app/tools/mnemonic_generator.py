from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult




class MnemonicGenerator(BaseTool):
    name = "mnemonic_generator"
    description = "Creates memory aids to improve recall"
    category = "memory"
    required_params = ["items_to_remember", "subject"]
    optional_params = ["mnemonic_type", "style", "language"]
    param_defaults = {"mnemonic_type": "acronym", "style": "fun", "language": "English"}

    def get_trigger_phrases(self):
        return ["mnemonic", "remember", "memory trick", "how to remember", "memorize", "can't remember"]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        items = params["items_to_remember"]
        subject = params["subject"]
        if isinstance(items, str):
            items = [i.strip() for i in items.split(",")]

        initials = "".join(w[0].upper() for w in items if w)
        data = {
            "items": items,
            "subject": subject,
            "mnemonics": [
                {
                    "type": "acronym",
                    "mnemonic": initials,
                    "expansion": " | ".join(items),
                    "sentence": f"Every {subject} student remembers: {initials}",
                    "explanation": f"Each letter stands for: {', '.join(items)}",
                },
                {
                    "type": "story",
                    "mnemonic": f"Imagine a story where {items[0] if items else 'concept'} meets {items[1] if len(items) > 1 else 'idea'}",
                    "explanation": "Visual stories are 6x more memorable than lists",
                },
                {
                    "type": "rhyme",
                    "mnemonic": f"First comes {items[0] if items else 'one'}, then {items[1] if len(items) > 1 else 'two'}, that's how we remember in {subject}!",
                    "explanation": "Rhythm and rhyme activate different memory pathways",
                },
            ],
            "best_recommended": "acronym",
            "why_it_works": "Mnemonics create hooks in long-term memory using familiar patterns",
            "practice_drill": f"Cover the items and recite from the mnemonic 3 times",
        }
        return ToolResult(success=True, data=data, metadata={"tool": self.name})


