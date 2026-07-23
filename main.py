"""
main.py — CLI test harness for the ExcelAgent.

Use this to verify the ReAct loop manually before wiring up the Streamlit UI.
Run with: uv run python main.py
"""

from agent import ExcelAgent


def main() -> None:
    agent = ExcelAgent()
    print("Excel AI Assistant (type 'quit' to exit, 'reset' to clear history)\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("Goodbye!")
            break
        if user_input.lower() == "reset":
            agent.reset()
            print("History cleared.\n")
            continue

        response = agent.chat(user_input)
        print(f"\nAgent: {response}\n")


if __name__ == "__main__":
    main()
