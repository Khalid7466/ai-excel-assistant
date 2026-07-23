"""
agent.py — The ReAct (Reason + Act) engine.

Orchestrates the conversation between the user and the LLM, managing tool
execution via tools.py. Implements the loop manually with no external frameworks.
"""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq, BadRequestError

from tools import TOOL_FUNCTIONS

load_dotenv()

# ── Configuration (loaded once at startup) ────────────────────────────────────

SYSTEM_PROMPT: str = (Path(__file__).parent / "prompts" / "system_prompt.md").read_text(encoding="utf-8")
TOOLS_SCHEMA: list = json.loads((Path(__file__).parent / "schemas" / "tools_schema.json").read_text(encoding="utf-8"))
MODEL = "llama-3.3-70b-versatile"

# ── Agent ─────────────────────────────────────────────────────────────────────

class ExcelAgent:
    """
    A stateful AI agent that manages two Excel datasets via natural language.

    Maintains a conversation history across turns and runs a ReAct loop
    internally: the LLM decides when to call tools, the Python backend executes
    them, and results (including errors) are fed back to the LLM as tool
    messages until a final text response is produced.
    """

    def __init__(self) -> None:
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.history: list[dict] = []

    def reset(self) -> None:
        """Clear conversation history to start a fresh session."""
        self.history = []

    def chat(self, user_message: str) -> str:
        """
        Process a user message and return the agent's final response.

        Runs the full ReAct loop: sends the message to the LLM, executes any
        requested tools, feeds results back, and repeats until the LLM produces
        a plain text response.

        Args:
            user_message: The raw natural-language input from the user.

        Returns:
            The agent's final text response to display to the user.
        """
        self.history.append({"role": "user", "content": user_message})

        while True:
            # Retry up to 3 times for transient Groq tool generation failures
            for attempt in range(3):
                try:
                    response = self.client.chat.completions.create(
                        model=MODEL,
                        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self.history,
                        tools=TOOLS_SCHEMA,
                        tool_choice="auto",
                    )
                    break
                except BadRequestError as e:
                    if attempt < 2 and "tool_use_failed" in str(e):
                        time.sleep(1)
                        continue
                    raise

            message = response.choices[0].message

            # ── Path A: Final text answer (or clarification question) ──────────
            if not message.tool_calls:
                content = message.content or ""
                self.history.append({"role": "assistant", "content": content})
                return content

            # ── Path B: Tool execution ─────────────────────────────────────────
            # Append the LLM's tool-call request to history first
            self.history.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            })

            for tool_call in message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                # Execute the corresponding Python function from tools.py
                result = TOOL_FUNCTIONS[name](**args)

                # Append result to history (success or error — same path)
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, default=str),
                })

            # Loop: LLM reads the tool result(s) and decides what to do next
