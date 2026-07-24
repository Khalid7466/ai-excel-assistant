# Architecture Decision Records (ADRs)

Every significant decision made in this project is recorded here with its context, options considered, and the rationale for the final choice.

---

## ADR-001: No Agent Frameworks

**Date:** 2026-07-22
**Status:** Accepted (required by task constraints)

**Context:**
The task explicitly forbids LangChain, LlamaIndex, AutoGen, CrewAI, and similar frameworks.

**Decision:**
Build the tool-calling loop manually using the LLM provider's raw API.

**Consequences:**
- We own every line of the orchestration logic — nothing is hidden.
- The code is easier to explain and defend in a live call.
- Debugging is straightforward: one Python file, no framework magic.

---

## ADR-002: LLM Provider — Dynamic Configuration & Rate Limit Fallback

**Date:** 2026-07-23 (Revised)
**Status:** Accepted

**Context:**
Task requires free LLMs. Groq is extremely fast and provides `llama-3.3-70b-versatile`, but its free tier imposes strict rate limits (TPD: Tokens Per Day). A single provider approach proved fragile under evaluation workloads.

**Decision:**
Use a **Dynamic Provider Registry** backed by the `openai` Python SDK, with **Automatic Rate Limit Fallback**.
- Supported Providers: Groq, Cerebras, Google Gemini, OpenRouter, GitHub Models.
- The `agent.py` dynamically loads any provided API keys from `.env` at startup.
- If the primary provider hits a rate limit (HTTP 429 `RateLimitError`), the agent automatically and silently falls back to the next available provider.

**Rationale:**
- All major providers now offer OpenAI-compatible endpoints, allowing a single `openai` client to interact with any of them by just changing `base_url`.
- Silently falling back provides a seamless user experience, preventing the application from crashing when a provider's daily or minute quota is exhausted.
- Users can easily add or remove providers via the `.env` file without touching the codebase.

**Consequences:**
- Replaced the specific `groq` package with the generic `openai` package.
- `agent.py` now maintains a stateful `provider_idx` during its ReAct loop.
- The system is incredibly resilient to individual API rate limits or downtimes.

---

## ADR-003: Data Handling — pandas + openpyxl

**Date:** 2026-07-22
**Status:** Accepted

**Context:**
Need to read, query, insert, update, and delete rows in `.xlsx` files.

**Decision:**
Use **pandas** for all data operations, backed by **openpyxl** engine for writing.

**Rationale:**
- `pandas` gives us powerful filtering/querying in a few lines.
- `openpyxl` preserves the `.xlsx` format on write (unlike `xlwt` which is `.xls` only).
- No need for a database — the Excel files ARE the data store, as specified by the task.

**Consequences:**
- All mutations load the file, modify in memory, and write back. Acceptable for demo-scale data.
- No concurrent write safety — not a concern for a single-user CLI assistant.

---

## ADR-004: UI Layer — Streamlit

**Date:** 2026-07-22
**Status:** Accepted

**Context:**
The task scores higher when the assistant is easy for the user to interact with ("the easier for the user to get answers, the higher your score"). Three UI options were evaluated:

| Option | Description |
|---|---|
| Terminal CLI | Plain `input()` loop — no visual interface |
| Gradio | Pure Python, designed for ML model demos |
| Streamlit | Pure Python, designed for data applications |

**Decision:**
Use **Streamlit** as the UI layer.

**Rationale:**

1. **Rich data display alongside chat.** The task involves two structured Excel datasets (real estate listings, marketing campaigns). Streamlit's `st.dataframe()` and `st.bar_chart()` allow showing the actual filtered table next to the AI's answer — something a terminal or Gradio's `ChatInterface` cannot do cleanly.

2. **Pure Python, zero backend knowledge required.** Streamlit compiles the entire UI from a Python script. No HTML, CSS, JavaScript, or server routing needed.

3. **Purpose-built chat primitives.** `st.chat_message()` and `st.chat_input()` produce a polished chat interface with minimal code.

4. **Better fit than Gradio for this task.** Gradio's `ChatInterface` is optimized for text-in/text-out model demos. Adding a live DataFrame view or chart next to the chat response requires significant workarounds. Streamlit handles this natively.

5. **Industry recognition.** Streamlit is the standard tool for AI/data demos in the ML community. Explaining the choice in a live defense call requires no justification.

**Consequences:**
- Add `streamlit` as a dependency via `uv add streamlit`.
- Entry point changes from `uv run main.py` to `uv run streamlit run app.py`.
- README setup section must be updated accordingly.
***

## ADR-005: Static Schema Injection vs Schema Tool

**Date:** 2026-07-22
**Status:** Accepted

**Context:**
The LLM needs to know the exact column names and data types of the two Excel files to formulate accurate filters and inserts. 

**Decision:**
Inject the full schema of the two datasets directly into the **System Prompt** at startup, rather than providing a `get_schema()` tool.

**Rationale:**
- **Latency and Cost:** For a small, static dataset architecture (2 files), using a `get_schema` tool forces the LLM into a two-step reasoning process (Fetch Schema -> Answer Query) for every interaction, doubling the API cost and response time.
- **Context Window:** The schemas for these two files are small enough to easily fit within the System Prompt without overwhelming the context window.

---

## ADR-006: Tools Layer Architecture & Safety Guardrails

**Date:** 2026-07-22
**Status:** Accepted

**Context:**
Designing the interface between the LLM Agent and the Excel datasets requires balancing data safety (preventing mass deletions/corruptions) with code maintainability and testability.

**Decision:**
The Tools Layer (`tools.py`) is designed as a standalone, stateless Python module with the following backend guardrails:
1. **Ambiguity Check (Update/Delete):** Tools accept flexible `filters`, but if a filter matches > 1 row, the Python code refuses to execute and forces the LLM to ask the user for clarification (Tool-Level Safety).
2. **Slot Filling Validation (Inserts):** Enforces strict required fields. If the LLM omits them, the tool returns an error forcing the LLM to proactively ask the user.
3. **In-Memory Testing Isolation:** The test suite (`test_tools.py`) strictly uses `unittest.mock.patch` to intercept pandas file operations. It tests the guardrails entirely in memory without ever touching production data files.

**Rationale:**
- **Agent-Level vs Tool-Level Safety:** Relying on the LLM to "be careful" (Agent-Level Safety) is prone to hallucinations. Hardcoding these checks in Python provides an unbreakable guardrail against data loss.
- **Testing Integrity:** Mocking the filesystem ensures the test suite is fast, idempotent, and completely isolated from the real `.xlsx` state.

---

## ADR-007: Agent Architecture — ReAct Loop, Memory & Resilience

**Date:** 2026-07-23
**Status:** Accepted

**Context:**
Designing the core engine (`agent.py`) that connects the LLM to the tools layer. Three architectural questions needed answers: how to implement the reasoning loop, how to manage conversation state, and how to handle LLM provider failures.

**Decision:**
The agent is built as a single `ExcelAgent` class with three design choices:

1. **Manual ReAct Loop (No Frameworks):** The tool-calling lifecycle is implemented as a `while True` loop. Each iteration calls the Groq API; if the response contains tool calls, they are executed and their results (including errors) are appended as `tool` messages before the next iteration. The loop exits only when the LLM returns a plain text response.

2. **Stateful Conversation History:** All messages (user, assistant, tool results) are accumulated in `self.history` and sent in full with every API call, giving the LLM complete context across turns.

3. **Retry Logic for Transient Failures:** The Groq free-tier API occasionally returns `tool_use_failed` errors due to model generation issues. The agent retries up to 3 times with a 1-second backoff before propagating the error.

**Rationale:**
- **ReAct Loop:** Building the loop manually (per ADR-001) means every decision the LLM makes is visible and debuggable in plain Python. No framework abstractions hide the flow.
- **Stateful History:** Multi-turn workflows like Slot Filling (asking the user for missing fields across multiple messages) are impossible without full history. A stateless design would lose context between turns.
- **Retry Logic:** LLM inference on free-tier APIs is probabilistic and occasionally flaky. A simple retry is the minimum production-grade resilience pattern with negligible cost (max 3 extra seconds). Failing fast without retry would degrade UX unnecessarily.

---

## ADR-008: External Configuration — Prompts & Tool Schemas as Files

**Date:** 2026-07-23
**Status:** Accepted

**Context:**
`agent.py` needs a System Prompt and a Tools JSON Schema to function. Where should these live?

**Decision:**
Store both as standalone files loaded at startup:
- `prompts/system_prompt.md` — the agent's instructions and rules.
- `schemas/tools_schema.json` — the 5 tool definitions in Groq/OpenAI JSON Schema format.

**Rationale:**
- **Separation of Concerns:** `agent.py` becomes a pure engine with zero hardcoded configuration. A non-developer (e.g., a Product Manager) can tune the prompt without touching Python.
- **Git History Clarity:** Prompt iteration history is tracked separately from code logic changes, making reviews easier.
- **Extensibility:** Adding a new prompt variant (e.g., for a different language) is a new file, not a code change.

---

## ADR-009: String Filter Matching — Contains vs Exact Match

**Date:** 2026-07-23
**Status:** Accepted (Revised)

**Context:**
How should `_apply_filters` match string column values? A user asking to "delete the Summer campaign" will likely pass `{"Campaign Name": "Summer"}` — but no row has that exact name; real rows are named "Summer Promo - Facebook 2024 Q1".

**First Answer (Rejected):**
Use exact, case-insensitive matching (`str.lower() == val.lower()`). Simple and predictable, but means the LLM must know the full, exact name — which it never will from a natural language query. This produced a silent "No rows found" instead of meaningful feedback.

**Why That Was Wrong:**
The system is a natural-language interface. Users think in keywords, not exact record names. An exact match forces the LLM to hallucinate precise names, defeating the purpose of an AI assistant.

**Revised Decision:**
Use **case-insensitive partial match** (`str.contains`, case=False) for all non-numeric columns. Numeric and ID columns retain exact match for precision.

**Rationale:**
- **UX Correctness:** Keyword search matches user intent. "Summer" correctly surfaces all 65 Summer campaigns.
- **Safety is preserved:** The Ambiguity Guard in `update_rows` / `delete_rows` (ADR-006) catches the multi-row result and forces the LLM to ask the user for clarification before any mutation executes. Contains matching and the Ambiguity Guard are designed to work together.
- **Implementation Note:** Fixed a secondary bug — newer pandas versions return `StringDtype` instead of `object` for text columns from Excel. The check was updated from `dtype == object` to `pd.api.types.is_numeric_dtype()` to handle both correctly.

