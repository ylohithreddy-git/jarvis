import sys
import os

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.tools.registry import get_tool_registry
from app.tools.base import ToolContext

def run_group_d_mode1():
    reg = get_tool_registry()
    ctx = ToolContext(approved=True)
    base = "JARVIS_REAL_WORLD_TEST/expense_tracker"
    
    # 0. Set up clean initial buggy state
    # Reset expenses.csv to 5 items totaling 265.50
    expenses_csv = """date,category,amount,description
2026-09-01,Groceries,45.50,Supermarket shopping
2026-09-02,Utilities,120.00,Electric bill
2026-09-03,Entertainment,15.00,Cinema ticket
2026-09-04,Transport,30.25,Metro pass
2026-09-05,Dining,54.75,Dinner with colleagues
"""
    reg.execute("write_file", {"path": f"{base}/expenses.csv", "content": expenses_csv}, context=ctx)
    
    # Introduce bug into app.py
    buggy_app = """import csv
import sys
import os

def load_expenses(csv_file="expenses.csv"):
    if not os.path.exists(csv_file):
        return []
    expenses = []
    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row["amount"] = float(row["amount"])
                expenses.append(row)
            except (ValueError, KeyError):
                continue
    return expenses

def calculate_total(expenses):
    # BUG: Multiplying sum by 1.10
    return sum(item["amount"] for item in expenses) * 1.10

def get_category_breakdown(expenses):
    breakdown = {}
    for item in expenses:
        cat = item.get("category", "Other")
        breakdown[cat] = breakdown.get(cat, 0.0) + item["amount"]
    return breakdown

def main():
    expenses = load_expenses("expenses.csv")
    total = calculate_total(expenses)
    print(f"Total: {total}")

if __name__ == "__main__":
    main()
"""
    reg.execute("write_file", {"path": f"{base}/app.py", "content": buggy_app}, context=ctx)

    print("=== MODE 1: CAPABILITY-ONLY DEBUGGING WORKFLOW ===")
    
    # Step 1: Run the test suite via terminal
    print("\n[Step 1] Running test suite via ToolRegistry.execute('run_command')...")
    test_cmd = f"{sys.executable} -m unittest {base}/tests/test_app.py"
    r_test1 = reg.execute("run_command", {"command": test_cmd}, context=ctx)
    print("Test exit code:", r_test1.result.get("exit_code") if r_test1.result else r_test1.error.get("exit_code"))
    print("Test failure output sample:\n", (r_test1.result.get("stderr") if r_test1.result else r_test1.error.get("message", ""))[:400])

    # Step 2: Read failing test file via ToolRegistry.execute('read_file')
    print("\n[Step 2] Reading failing test file via ToolRegistry.execute('read_file')...")
    r_read_test = reg.execute("read_file", {"path": f"{base}/tests/test_app.py"}, context=ctx)
    print("Test file content length:", len(r_read_test.result.get("content", "")))

    # Step 3: Read implementation file via ToolRegistry.execute('read_file')
    print("\n[Step 3] Reading implementation file via ToolRegistry.execute('read_file')...")
    r_read_app = reg.execute("read_file", {"path": f"{base}/app.py"}, context=ctx)
    app_code = r_read_app.result.get("content", "")
    print("Identified bug in app.py: '* 1.10' found:", "* 1.10" in app_code)

    # Step 4: Fix code using patch_file or update_file via ToolRegistry
    print("\n[Step 4] Applying fix via ToolRegistry.execute('patch_file')...")
    r_patch = reg.execute("patch_file", {
        "path": f"{base}/app.py",
        "find": "return sum(item[\"amount\"] for item in expenses) * 1.10",
        "replace": "return sum(item[\"amount\"] for item in expenses)"
    }, context=ctx)
    print("Patch success:", r_patch.success, r_patch.result)

    # Step 5: Rerun tests via ToolRegistry.execute('run_command')
    print("\n[Step 5] Rerunning test suite via ToolRegistry.execute('run_command')...")
    r_test2 = reg.execute("run_command", {"command": test_cmd}, context=ctx)
    print("Test success:", r_test2.success)
    print("Test exit code:", r_test2.result.get("exit_code") if r_test2.result else r_test2.error)
    print("Test stderr (unittest output):\n", r_test2.result.get("stderr", "").strip() if r_test2.result else "")

if __name__ == "__main__":
    run_group_d_mode1()
