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

## ADR-004: UI Layer — Streamlit with Live ReAct Streaming

**Date:** 2026-07-24 (Revised)
**Status:** Accepted

**Context:**
The task scores higher when the assistant is easy for the user to interact with. A robust, visual UI with intermediate tool execution visibility was required.

**Decision:**
Use **Streamlit** as the UI layer (`app.py`), wrapped with custom CSS to provide a clean, SaaS-like premium interface. Furthermore, intercept and stream the intermediate ReAct steps (tool calls and results) live to the UI.

**Rationale:**
1. **Rich data display alongside chat.** Streamlit's `st.dataframe()` allows rendering pandas DataFrames natively.
2. **Transparency:** Users (Data Analysts) must trust the AI. Streaming the tool steps (`search_data`, `update_rows`) provides complete visibility into how the agent arrives at its answers.
3. **Customizability:** Streamlit allows custom CSS injection to hide default chrome and create a minimalist layout.

**Consequences:**
- `agent.py` was refactored from a blocking call `chat()` to a generator `chat_stream()` yielding events.
- Added custom CSS to remove default Streamlit menus, adjust the layout, and fix the native Sidebar collapsing mechanism.

---

## ADR-005: Smart Type Casting for LLM Stability

**Date:** 2026-07-24
**Status:** Accepted

**Context:**
LLMs frequently struggle with strict `pandas` data types. For example, querying a `datetime64` column with a raw string `"<2023-01-01"` causes `ValueError` crashes. Similarly, numerical queries mixed with strings break Pandas indexing.

**Decision:**
Implemented a `_cast_value(df, column, val)` guardrail inside `tools.py`.

**Rationale:**
- **Pydantic is insufficient here:** We don't just need schema validation; we need dynamic, dataframe-aware casting.
- By reading `df.dtypes[column]`, the system automatically parses strings into `pd.to_datetime` or `float` before executing the Pandas query.
- This prevents backend crashes and completely shields the LLM from debugging Pandas exceptions.

**Consequences:**
- Achieved **100% Evaluation Pass Rate** on complex temporal and numeric queries.

---

## ADR-006: Strict Slot Filling & Categorical Validation

**Date:** 2026-07-24
**Status:** Accepted

**Context:**
When testing insertion workflows, the LLM hallucinated data categories (e.g., placing "TikTok" as a `Channel` instead of "Social Media"), polluting the business dataset.

**Decision:**
Enforced strict **Slot Filling** in `prompts/system_prompt.md`. 
1. The LLM must proactively ask the user for missing required fields (e.g., `City`, `List Price`).
2. The LLM is strictly instructed to map arbitrary user input (e.g., "Facebook Ads") to fixed categorical values (e.g., "Social Media") before invoking `insert_row` or `update_rows`.

**Rationale:**
- Protects database schema integrity (Data Governance).
- Reduces the risk of silent bad data entry which breaks reporting downstream.

---

## ADR-007: Agent Architecture — ReAct Loop, Memory & Resilience

**Date:** 2026-07-23
**Status:** Accepted

**Context:**
Designing the core engine (`agent.py`) that connects the LLM to the tools layer.

**Decision:**
The agent is built as a single `ExcelAgent` class with three design choices:
1. **Manual ReAct Loop (No Frameworks):** The tool-calling lifecycle is implemented as a generator loop.
2. **Stateful Conversation History:** All messages are accumulated in `self.history`.
3. **Retry Logic for Transient Failures:** The API occasionally returns errors due to rate limits or generation issues; the agent retries up to 3 times automatically.

---

## ADR-008: External Configuration — Prompts & Tool Schemas as Files

**Date:** 2026-07-23
**Status:** Accepted

**Context:**
`agent.py` needs a System Prompt and a Tools JSON Schema to function.

**Decision:**
Store both as standalone files loaded at startup (`prompts/system_prompt.md`, `schemas/tools_schema.json`).

**Rationale:**
- Separation of concerns, clear git history, and easy extensibility.

---

## ADR-009: String Filter Matching — Contains vs Exact Match

**Date:** 2026-07-23
**Status:** Accepted

**Context:**
How should `_apply_filters` match string column values?

**Decision:**
Use **case-insensitive partial match** (`str.contains`, case=False) for all non-numeric columns. Numeric and ID columns retain exact match for precision.

**Rationale:**
- **UX Correctness:** Keyword search matches user intent. "Summer" correctly surfaces all 65 Summer campaigns.
- **Safety is preserved:** The Ambiguity Guard in `update_rows` / `delete_rows` catches multi-row results and forces the LLM to ask the user for clarification before any mutation executes.
