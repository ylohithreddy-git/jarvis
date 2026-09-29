import sys
import os
import asyncio
from unittest.mock import MagicMock

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Mock the missing third-party LLM libraries for this architectural verification
sys.modules['groq'] = MagicMock()
sys.modules['litellm'] = MagicMock()

from app.runtime.protocols import RunRequest, RunOutcome
from app.runtime.events.emitter import NullEmitter
from app.agent.loop import run_agent_loop
import app.agent.loop as loop_mod

def test_agent_react_plumbing():
    req = RunRequest(
        run_id="run_qa_sim_1",
        session_id="sess_qa_sim_1",
        user_id="user_qa",
        workspace_id="default",
        objective="Read README.md and summarize what this project does.",
        workspace_root="."
    )
    emitter = NullEmitter()

    # We will simulate 2 turns from the LLM:
    # Turn 1: Model calls tool read_file
    # Turn 2: Model provides final answer based on observation
    turn_responses = [
        ("<thought>I need to read README.md to understand this project.</thought>\n<tool_call>\n{\"name\": \"read_file\", \"arguments\": {\"path\": \"JARVIS_REAL_WORLD_TEST/expense_tracker/README.md\"}}\n</tool_call>", "I need to read README.md to understand this project."),
        ("This project is an Expense Tracker CLI tool that calculates totals from expenses.csv.", None)
    ]
    call_idx = 0

    def mock_call_llm(system, user, model="openai/gpt-oss-120b", provider="groq", tools=None, emit=None):
        nonlocal call_idx
        resp = turn_responses[call_idx]
        call_idx += 1
        return resp

    # Temporarily patch call_llm inside loop_mod
    orig_call_llm = loop_mod.call_llm
    loop_mod.call_llm = mock_call_llm

    try:
        outcome = asyncio.run(run_agent_loop(req, emitter))
        print("Agent ReAct loop completed!")
        print("Final Status:", outcome.status)
        print("Final Reply:", outcome.reply)
        print("Total Events Emitted:", len(emitter.events))
        event_names = [e["event"] for e in emitter.events]
        print("Emitted Event Sequence:", event_names)
        
        # Verify tool was called
        tool_started_events = [e for e in emitter.events if e["event"] == "tool_started"]
        print("Tool Started Events:", len(tool_started_events))
        if tool_started_events:
            print("Tool called:", tool_started_events[0]["data"])

        tool_completed_events = [e for e in emitter.events if e["event"] == "tool_completed"]
        print("Tool Completed Events:", len(tool_completed_events))
        if tool_completed_events:
            print("Tool completion:", tool_completed_events[0]["data"])

    finally:
        loop_mod.call_llm = orig_call_llm

if __name__ == "__main__":
    test_agent_react_plumbing()
