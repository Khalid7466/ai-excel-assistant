"""
agent.py — The ReAct (Reason + Act) engine.

Orchestrates the conversation between the user and the LLM, managing tool
execution via tools.py. Implements the loop manually with no external frameworks.
"""

import json
import os
import time
from pathlib import Path

from dataclasses import dataclass
from dotenv import load_dotenv
import openai
from openai import OpenAI, BadRequestError, RateLimitError, NotFoundError, AuthenticationError

from tools import TOOL_FUNCTIONS

# ── Configuration (loaded once at startup) ────────────────────────────────────
SYSTEM_PROMPT: str = (Path(__file__).parent / "prompts" / "system_prompt.md").read_text(encoding="utf-8")
TOOLS_SCHEMA: list = json.loads((Path(__file__).parent / "schemas" / "tools_schema.json").read_text(encoding="utf-8"))

# ── Dynamic Provider Config & Fallback Registry ───────────────────────────────

@dataclass
class LLMProvider:
    name: str
    client: OpenAI
    model: str

def get_available_providers() -> list[LLMProvider]:
    """Dynamically load providers so .env changes apply instantly without app restart."""
    load_dotenv(override=True)
    providers = []

    if os.getenv("LLM_API_KEY"):
        providers.append(LLMProvider(
            name="Custom Override",
            client=OpenAI(api_key=os.getenv("LLM_API_KEY"), base_url=os.getenv("LLM_BASE_URL")),
            model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        ))

    if os.getenv("GROQ_API_KEY"):
        providers.append(LLMProvider(
            name="Groq",
            client=OpenAI(api_key=os.getenv("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1"),
            model="llama-3.3-70b-versatile"
        ))

    if os.getenv("CEREBRAS_API_KEY"):
        providers.append(LLMProvider(
            name="Cerebras",
            client=OpenAI(api_key=os.getenv("CEREBRAS_API_KEY"), base_url="https://api.cerebras.ai/v1"),
            model="llama3.1-70b"
        ))

    if os.getenv("GEMINI_API_KEY"):
        providers.append(LLMProvider(
            name="Gemini",
            client=OpenAI(api_key=os.getenv("GEMINI_API_KEY"), base_url="https://generativelanguage.googleapis.com/v1beta/openai/"),
            model="gemini-1.5-flash"
        ))

    if os.getenv("OPENROUTER_API_KEY"):
        providers.append(LLMProvider(
            name="OpenRouter",
            client=OpenAI(api_key=os.getenv("OPENROUTER_API_KEY"), base_url="https://openrouter.ai/api/v1"),
            model="mistralai/mistral-7b-instruct"
        ))

    if os.getenv("GITHUB_API_KEY"):
        providers.append(LLMProvider(
            name="GitHub Models",
            client=OpenAI(api_key=os.getenv("GITHUB_API_KEY"), base_url="https://models.inference.ai.azure.com"),
            model="gpt-4o-mini"
        ))

    if not providers:
        # Dummy fallback to prevent crashing on initialization
        providers.append(LLMProvider("Dummy", OpenAI(api_key="dummy"), "dummy"))

    return providers

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
        self.provider_idx = 0
        self.history: list[dict] = []

    @property
    def provider(self) -> LLMProvider:
        providers = get_available_providers()
        if self.provider_idx >= len(providers):
            self.provider_idx = 0
        return providers[self.provider_idx]

    def _create_completion(self):
        """
        Invokes the LLM with the current provider.
        If a RateLimitError is hit, silently falls back to the next available provider.
        Also handles temporary Groq tool_use_failed errors.
        """
        providers = get_available_providers()
        if self.provider_idx >= len(providers):
            self.provider_idx = 0

        while self.provider_idx < len(providers):
            provider = providers[self.provider_idx]
            try:
                for attempt in range(3):
                    try:
                        return provider.client.chat.completions.create(
                            model=provider.model,
                            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self.history,
                            tools=TOOLS_SCHEMA,
                            tool_choice="auto",
                        )
                    except BadRequestError as e:
                        if attempt < 2 and "tool_use_failed" in str(e):
                            time.sleep(1)
                            continue
                        raise
            except Exception as e:
                # If tool_use_failed, retry same provider (Groq specific)
                if isinstance(e, BadRequestError) and "tool_use_failed" in str(e):
                    if attempt < 2:
                        time.sleep(1)
                        continue
                
                # For any other API error (including 400 Invalid Key), fallback to next provider
                if self.provider_idx < len(providers) - 1:
                    self.provider_idx += 1
                    continue
                raise e
        raise RuntimeError("No providers available.")

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
            response = self._create_completion()

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

    def chat_stream(self, user_message: str):
        """
        Streaming variant of chat() that yields intermediate events as they happen.

        Yields dicts of the form:
            {"type": "tool_call", "name": str, "args": dict, "result": dict}
            {"type": "final", "content": str}

        This allows the UI (Streamlit) to display each tool call live as the
        agent executes its ReAct loop, rather than waiting for the final answer.
        """
        self.history.append({"role": "user", "content": user_message})

        while True:
            response = self._create_completion()

            message = response.choices[0].message

            if not message.tool_calls:
                content = message.content or ""
                self.history.append({"role": "assistant", "content": content})
                yield {"type": "final", "content": content}
                return

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
                result = TOOL_FUNCTIONS[name](**args)

                self.history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, default=str),
                })

                # Yield tool call event immediately so the UI can render it live
                yield {"type": "tool_call", "name": name, "args": args, "result": result}
