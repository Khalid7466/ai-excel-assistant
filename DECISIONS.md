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

*More ADRs will be added as decisions are made.*
