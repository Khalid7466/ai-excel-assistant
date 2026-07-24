"""
evaluator.py — Production-Grade Agent Evaluation Framework

Runs the Ground Truth dataset against the ExcelAgent to measure Trajectory, 
Robustness, and Deterministic State Mutability.
"""

import json
import os
import shutil
import time
from pathlib import Path

import pandas as pd

import tools
from agent import ExcelAgent

# ── Paths ──────────────────────────────────────────────────────────────────────
EVAL_DIR = Path(__file__).parent
DATASET_PATH = EVAL_DIR / "dataset.json"
SANDBOX_DIR = EVAL_DIR / "sandbox"
PROD_DATA_DIR = Path(tools.__file__).parent / "data"

def setup_sandbox():
    """Create fresh copies of production data in the sandbox."""
    if SANDBOX_DIR.exists():
        shutil.rmtree(SANDBOX_DIR)
    SANDBOX_DIR.mkdir()

    for file_name in ["real_estate_listings.xlsx", "marketing_campaigns.xlsx"]:
        shutil.copy(PROD_DATA_DIR / file_name, SANDBOX_DIR / file_name)

    # Patch tools.py to use sandbox
    tools.FILES = {
        "real_estate": SANDBOX_DIR / "real_estate_listings.xlsx",
        "marketing": SANDBOX_DIR / "marketing_campaigns.xlsx",
    }


def evaluate():
    print("="*60)
    print("AI Excel Assistant - Production Evaluation Framework")
    print("="*60)

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    passed = 0
    total = len(dataset)
    results = []

    for idx, test in enumerate(dataset):
        print(f"\n[{idx+1}/{total}] Running: {test['id']} - {test['category']}")
        print(f"Query: {test['query']}")
        
        setup_sandbox()
        agent = ExcelAgent()
        
        start_time = time.time()
        try:
            if isinstance(test.get("query"), list):
                final_response = ""
                for q in test["query"]:
                    final_response = agent.chat(q)
            else:
                final_response = agent.chat(test["query"])
            error = None
        except Exception as e:
            final_response = ""
            error = str(e)
            print(f"  [CRASH] {error}")
            results.append({"id": test["id"], "pass": False, "reason": "Crash"})
            continue

        latency = time.time() - start_time
        history = agent.history

        # ── Evaluation Logic ──────────────────────────────────────────────────
        is_pass = False
        reason = ""

        # Find all tool calls in history
        tool_calls = []
        for msg in history:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    tool_calls.append(tc["function"])

        expected_tool = test.get("expected_tool")
        check_type = test["check_type"]

        if check_type == "out_of_domain":
            if tool_calls:
                reason = f"Failed: Expected no tools, but called {tool_calls[0]['name']}"
            else:
                is_pass = True
                reason = "Passed: Correctly rejected or asked for clarification without tools."
                
        elif check_type == "slot_filling":
            # Slot filling succeeds if the agent ultimately asks for the missing fields,
            # either proactively or after the Python tool rejects a partial payload.
            expected_words = test.get("expected_reply_contains", [])
            has_asked = all(word.lower() in final_response.lower() for word in expected_words)
            if has_asked:
                is_pass = True
                reason = "Passed: Correctly asked the user for missing required fields."
            else:
                reason = f"Failed: Did not ask for missing fields. Final Response: {final_response}"
                
        elif check_type == "tool_call":
            if not tool_calls:
                reason = "Failed: No tools called."
            elif tool_calls[0]["name"] != expected_tool:
                reason = f"Failed: Called {tool_calls[0]['name']}, expected {expected_tool}"
            else:
                # Check subset of args
                args = json.loads(tool_calls[0]["arguments"])
                subset = test.get("expected_args_subset", {})
                if all(args.get(k) == v or (isinstance(v, dict) and all(args.get(k, {}).get(k2) == v2 for k2, v2 in v.items())) for k, v in subset.items()):
                    is_pass = True
                    reason = "Passed: Correct tool and arguments."
                else:
                    reason = f"Failed: Args mismatch. Got {args}"

        elif check_type == "ambiguity_recovery":
            if not tool_calls:
                reason = "Failed: Did not attempt tool call."
            elif tool_calls[0]["name"] != expected_tool:
                reason = f"Failed: Called {tool_calls[0]['name']}, expected {expected_tool}"
            else:
                # Did it recover and ask the user?
                has_ambiguity_error = any(msg.get("role") == "tool" and "Ambiguity Error" in str(msg.get("content")) for msg in history)
                if has_ambiguity_error and len(tool_calls) == 1:
                    is_pass = True
                    reason = "Passed: Caught ambiguity and recovered gracefully."
                else:
                    reason = "Failed: Did not handle ambiguity correctly."

        elif check_type.startswith("state_mutation"):
            if not tool_calls or expected_tool not in [tc["name"] for tc in tool_calls]:
                reason = f"Failed: Correct tool {expected_tool} not called."
            else:
                target = test["mutation_target"]
                df = pd.read_excel(tools.FILES[target["dataset"]])
                
                if check_type == "state_mutation_delete":
                    if target["id_value"] not in df[target["id_column"]].values:
                        is_pass = True
                        reason = "Passed: Row successfully deleted."
                    else:
                        reason = "Failed: Row still exists in dataset."
                        
                elif check_type == "state_mutation_update":
                    row = df[df[target["id_column"]] == target["id_value"]].iloc[0]
                    if row[target["check_column"]] == target["expected_value"]:
                        is_pass = True
                        reason = "Passed: Row successfully updated."
                    else:
                        reason = f"Failed: Value is {row[target['check_column']]}, expected {target['expected_value']}"
                        
                elif check_type == "state_mutation_insert":
                    # Just check if dataset length increased by 1 (originally 1000 for both)
                    if len(df) > 1000:
                        is_pass = True
                        reason = "Passed: Row successfully inserted."
                    else:
                        reason = "Failed: Dataset length did not increase."
                        
        elif check_type == "schema_recovery":
            # Pass if we see a ValueError in the tool response history, and a subsequent tool call
            has_value_error = any(msg.get("role") == "tool" and "does not exist in dataset" in str(msg.get("content")) for msg in history)
            if has_value_error and len(tool_calls) > 1:
                is_pass = True
                reason = "Passed: Caught schema error and recovered autonomously."
            else:
                reason = "Failed: Did not hit schema error and recover."
                
        elif check_type == "cross_dataset":
            # Pass if it called query_data at least twice on different datasets
            datasets_queried = set()
            for tc in tool_calls:
                if tc["name"] == "query_data":
                    args = json.loads(tc["arguments"])
                    if "dataset" in args:
                        datasets_queried.add(args["dataset"])
            
            if len(datasets_queried) == 2:
                is_pass = True
                reason = "Passed: Reasoned across multiple datasets successfully."
            else:
                reason = f"Failed: Did not query multiple datasets. Found: {datasets_queried}"

        # Record Result
        if is_pass:
            print(f"  [PASS] {reason} ({latency:.1f}s)")
            passed += 1
        else:
            print(f"  [FAIL] {reason} ({latency:.1f}s)")
            print(f"  Final Response: {final_response}")

        results.append({"id": test["id"], "pass": is_pass, "reason": reason})

    print("="*60)
    print(f"Final Score: {passed}/{total} ({(passed/total)*100:.1f}%)")
    print("="*60)

if __name__ == "__main__":
    evaluate()
