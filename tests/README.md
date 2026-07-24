# AI Excel Assistant: Testing Architecture

Evaluating an autonomous Agent that mutates production data is fundamentally different from evaluating standard LLM generations. It requires a rigorous, deterministic, and multi-layered approach.

This directory contains our **Two-Layer Testing Architecture**, designed to ensure both the internal Python logic and the Agent's reasoning capabilities are production-ready.

---

## Layer 1: Unit Testing (`tests/unit_tests/`)

**Purpose:** Fast, deterministic, and cost-free validation of the core Python logic.

In this layer, the LLM is completely removed from the equation. We strictly test the backend mechanisms and the `ExcelAgent` loop structure using `unittest.mock`. 

- **`test_tools.py`**: Tests the stateless CRUD operations. 
  - Validates `pandas` filtering logic (e.g., `str.contains` vs `==`).
  - Tests the hardcoded Guardrails (Ambiguity Rejection for >1 row updates, Slot Filling validation for missing `insert_row` fields).
  - *Isolation:* Filesystem operations are mocked; tests never touch real `.xlsx` files.
- **`test_agent.py`**: Tests the `ExcelAgent` class.
  - Mocks the `Groq` API client to simulate LLM responses.
  - Tests the **ReAct Loop**: Verifies that tool calls are correctly parsed, executed, and appended to the history, triggering a second LLM turn.
  - Tests **Resilience**: Verifies the Retry Logic by mocking `tool_use_failed` API errors and ensuring the agent recovers.

**How to run:**
```bash
uv run pytest tests/unit_tests/ -v
```

---

## Layer 2: Production Evaluation (`tests/evaluation/`)

**Purpose:** Assessing the LLM's actual reasoning, tool selection accuracy, and safety in an isolated sandbox.

Standard LLM evaluations (like RAGAS) focus on semantic quality. Agent evaluations must focus on **Actions, Trajectory, and System Impact**. We base our evaluation on four pillars:
1. **Trajectory & Efficiency:** Does the agent pick the right tool with the exact JSON arguments in the minimum number of steps?
2. **State Mutability:** If the agent deletes a row, does the Excel file actually shrink by 1 row? (Deterministic Verification).
3. **Robustness:** How does the agent handle ambiguous prompts or missing data? Does it fail safely?
4. **Out-of-Domain Rejection:** Does it refuse to answer questions outside its dataset?

### Evaluation Structure

- **`dataset.json`**: The Ground Truth dataset. It contains explicit test cases representing different Archetypes (Happy Path, Aggregations, Ambiguity, Slot Filling, Multi-turn, Temporal Reasoning).
- **`evaluator.py`**: The evaluation engine. 
- **`sandbox/`**: An auto-generated, disposable directory where the evaluator copies the production `.xlsx` files before running. This allows the LLM to execute real `insert` and `delete` commands without destroying real data.

### How `evaluator.py` Works:
1. For each test case, it sets up the `sandbox/`.
2. It sends the prompt to the live `Groq API`.
3. It analyzes the `agent.history` to verify if the expected tools were called (Trajectory).
4. For mutations (e.g., `delete_rows`), it loads the sandbox `.xlsx` file via pandas and uses strict `assert` statements to prove the row was physically removed (State Mutability).

**How to run:**
```bash
# Note: Consumes Groq API tokens.
uv run python tests/evaluation/evaluator.py
```
