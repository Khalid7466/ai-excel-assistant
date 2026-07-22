# AI Excel Assistant

A natural language AI assistant for querying and manipulating Excel data. Built from scratch — no agent frameworks.

## Setup

```bash
# Install dependencies and create virtualenv
uv sync

# Add your API key
cp .env.example .env   # then fill in GROQ_API_KEY

# Run
uv run main.py
```

## Design Decisions

See [DECISIONS.md](DECISIONS.md).

## Data

Place your Excel files under `data/`:
- `data/real_estate_listings.xlsx`
- `data/marketing_campaigns.xlsx`
