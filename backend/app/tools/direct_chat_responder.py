from typing import Any, Dict, List
from app.tools.base import BaseTool, ToolResult

class DirectChatResponder(BaseTool):
    name = "direct_chat_responder"
    description = "Provides a direct, markdown-formatted conversational answer, answering tasks like coding, writing, or general questions that don't need a structured UI component."
    category = "general"

    required_params = ["topic", "prompt"]
    optional_params = ["subject", "difficulty"]
    param_defaults = {}

    def get_trigger_phrases(self) -> List[str]:
        return [
            "write code",
            "generate python",
            "how to",
            "write a script",
            "answer this",
            "code",
            "chat",
            "write a",
            "who is",
            "what is",
            "when is",
            "where is",
            "which is",
        ]

    async def execute(self, params: Dict[str, Any], llm_client=None) -> ToolResult:
        params = self.apply_defaults(params)
        prompt_text = params.get("prompt", "")
        topic = params.get("topic", "")
        subject = params.get("subject", "general")
        difficulty = params.get("difficulty", "intermediate")

        if not prompt_text:
            prompt_text = f"Provide a detailed response about {topic}."

        system_prompt = f"""You are a highly intelligent, expert educational tutor.
The user requires a direct, unformatted conversational answer.

Topic Context: {topic}
Subject Area: {subject}
Audience Level: {difficulty}

INSTRUCTIONS:
1. Respond to the User Request elegantly using Markdown.
2. If they ask for code, write clean, well-commented code blocks.
3. If they ask for a general explanation, write a clear, coherent response.
4. DO NOT wrap your response in JSON. Write raw Markdown text.

User Request: "{prompt_text}"
"""

        if llm_client:
            # Generate pure markdown response using Groq 70B
            raw_response = await llm_client.generate(system_prompt, max_tokens=2048)
        else:
            raw_response = f"Simulated code response to: {prompt_text}\n\n```python\nprint('Hello World')\n```"

        data = {
            "topic": topic,
            "response": raw_response
        }

        return ToolResult(success=True, data=data, metadata={"tool": self.name})
