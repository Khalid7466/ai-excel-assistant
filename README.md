# AI Excel Assistant

Natural language AI assistant for Excel data — built **without** heavy agent frameworks (like LangChain/LlamaIndex). Uses raw API calls with a custom ReAct loop, Ambiguity Guardrails, and Streaming Tool Calls for maximum control and efficiency.

![App Screenshot](./.streamlit/screenshot.png) *(Add screenshot later)*

## Features

- **Natural Language Interface**: Read, filter, insert, update, and delete Excel records using plain English.
- **Provider Agnostic**: Easily switch between Groq, Cerebras, Google Gemini, OpenRouter, or GitHub Models (any OpenAI-compatible API).
- **Ambiguity Guardrails**: Prevents destructive mutations (Update/Delete) unless exact match criteria or exact row IDs are provided. Refuses ambiguous commands.
- **Slot Filling**: Automatically extracts and fills missing required fields for insertions based on schema constraints.
- **Robust ReAct Loop**: Implements self-correction on schema errors (automatically retries up to 3 times on `tool_use_failed`).
- **Live Streaming UI**: Watch the agent think and execute tools in real-time using Streamlit.
- **State Mutability**: The agent maintains a sandbox dataset, ensuring production files remain intact while allowing full CRUD operations.
- **Comprehensive Evaluation**: Custom multi-turn evaluation framework that tracks cross-dataset reasoning, state retention, and error recovery.

## Getting Started

### 1. Requirements

- Python 3.14+
- [`uv`](https://docs.astral.sh/uv/) for ultra-fast dependency management

### 2. Installation

Clone the repository and install dependencies:

```bash
git clone <your-repo-url>
cd ai-excel-assistant
uv sync
```

### 3. Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Open `.env` and set your preferred LLM provider. By default, it's configured for Groq. Add your `GROQ_API_KEY` (or your chosen provider's key):

```env
GROQ_API_KEY=your_api_key_here
```

### 4. Running the Application

Launch the Streamlit interface:

```bash
uv run streamlit run app.py
```

Open your browser to `http://localhost:8501`.

## Architecture & Testing

See [tests/README.md](./tests/README.md) for a deep dive into the testing layers, including:
1. **Unit Testing Layer**: Isolated tests for `tools.py` and the `ExcelAgent` ReAct loop with mocked LLM calls.
2. **Evaluation Framework**: A robust multi-turn evaluator that tests the model's actual reasoning across 16 advanced scenarios.

To run the unit tests:
```bash
uv run pytest tests/unit_tests/ -v
```

To run the full evaluation suite:
```bash
uv run python -m tests.evaluation.evaluator
```

## License

MIT License
