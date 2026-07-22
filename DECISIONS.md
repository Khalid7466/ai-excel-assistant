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

## ADR-002: LLM Provider — Groq (llama-3.3-70b-versatile)

**Date:** 2026-07-22
**Status:** Accepted

**Context:**
Task requires free LLMs only. Options evaluated:

| Provider | Model | Pros | Cons |
|---|---|---|---|
| Groq | llama-3.3-70b | Fast, free, native tool/function calling | Rate limits on free tier |
| Google Gemini | gemini-1.5-flash | Generous free tier | Slightly slower for tool use |
| OpenRouter | various | Flexible | Varies by model |

**Decision:**
Use **Groq with llama-3.3-70b-versatile** as the primary LLM.

**Rationale:**
- Native OpenAI-compatible function/tool calling API — means our loop code is standard and portable.
- Fastest inference on free tier (often < 1s).
- If Groq rate-limits, swapping to Gemini is a one-line change (same API shape via OpenAI SDK).

**Consequences:**
- Need a `GROQ_API_KEY` in `.env`.
- Hard rate limit: 30 requests/minute on free tier — acceptable for a demo assistant.

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

*More ADRs will be added as decisions are made.*
