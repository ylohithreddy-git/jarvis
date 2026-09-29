import sys
import os

# Ensure backend directory is in sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.tools.registry import get_tool_registry
from app.tools.base import ToolContext

def run_group_b():
    reg = get_tool_registry()
    ctx = ToolContext(approved=True)
    base = "JARVIS_REAL_WORLD_TEST/expense_tracker"
    results = {}

    print("--- TEST GROUP B: FILESYSTEM ---")
    # B1: Inspect project tree
    r1 = reg.execute("list_directory_tree", {"path": base, "max_depth": 2}, context=ctx)
    results["B1"] = ("PASS" if r1.success else "FAIL", r1.to_dict())

    # B2: Read README
    r2 = reg.execute("read_file", {"path": f"{base}/README.md"}, context=ctx)
    results["B2"] = ("PASS" if r2.success and "Expense Tracker" in r2.result.get("content", "") else "FAIL", r2.to_dict())

    # B3: Read app.py
    r3 = reg.execute("read_file", {"path": f"{base}/app.py"}, context=ctx)
    results["B3"] = ("PASS" if r3.success and "def calculate_total" in r3.result.get("content", "") else "FAIL", r3.to_dict())

    # B4: Read expenses.csv
    r4 = reg.execute("read_file", {"path": f"{base}/expenses.csv"}, context=ctx)
    results["B4"] = ("PASS" if r4.success and "Groceries" in r4.result.get("content", "") else "FAIL", r4.to_dict())

    # B5: Read test file
    r5 = reg.execute("read_file", {"path": f"{base}/tests/test_app.py"}, context=ctx)
    results["B5"] = ("PASS" if r5.success and "TestExpenseTracker" in r5.result.get("content", "") else "FAIL", r5.to_dict())

    # B6: Create new analysis file
    analysis_code = "# analysis.py\nprint('Running monthly expense analysis')\n"
    r6 = reg.execute("create_file", {"path": f"{base}/analysis.py", "content": analysis_code}, context=ctx)
    results["B6"] = ("PASS" if r6.success and os.path.exists(r6.result.get("absolute_path", "")) else "FAIL", r6.to_dict())

    # B7: Update app.py
    updated_app = r3.result.get("content", "") + "\n# Updated by JARVIS audit\n"
    r7 = reg.execute("update_file", {"path": f"{base}/app.py", "content": updated_app}, context=ctx)
    results["B7"] = ("PASS" if r7.success else "FAIL", r7.to_dict())

    # B8: Append data
    new_expense = "2026-09-06,Coffee,4.50,Morning espresso\n"
    r8 = reg.execute("append_file", {"path": f"{base}/expenses.csv", "content": new_expense}, context=ctx)
    results["B8"] = ("PASS" if r8.success else "FAIL", r8.to_dict())

    # B9: Search files
    r9 = reg.execute("search_files", {"path": base, "pattern": "Groceries"}, context=ctx)
    results["B9"] = ("PASS" if r9.success and len(r9.result.get("matches", [])) > 0 else "FAIL", r9.to_dict())

    # B10: Compare two files (diff)
    r10 = reg.execute("diff_files", {"path_a": f"{base}/app.py", "path_b": f"{base}/analysis.py"}, context=ctx)
    results["B10"] = ("PASS" if r10.success and r10.result.get("has_diff") else "FAIL", r10.to_dict())

    # B11: Copy file
    r11 = reg.execute("copy_file", {"src": f"{base}/expenses.csv", "dest": f"{base}/expenses_backup.csv"}, context=ctx)
    results["B11"] = ("PASS" if r11.success else "FAIL", r11.to_dict())

    # B12: Move file
    r12 = reg.execute("move_file", {"src": f"{base}/expenses_backup.csv", "dest": f"{base}/expenses_backup2.csv"}, context=ctx)
    results["B12"] = ("PASS" if r12.success else "FAIL", r12.to_dict())

    # B13: Rename file
    r13 = reg.execute("rename_file", {"old_path": f"{base}/expenses_backup2.csv", "new_path": f"{base}/expenses_temp.csv"}, context=ctx)
    results["B13"] = ("PASS" if r13.success else "FAIL", r13.to_dict())

    # B14: Delete temporary file
    r14 = reg.execute("delete_file", {"path": f"{base}/expenses_temp.csv"}, context=ctx)
    results["B14"] = ("PASS" if r14.success else "FAIL", r14.to_dict())

    # B15: Get file info
    r15 = reg.execute("get_file_info", {"path": f"{base}/app.py"}, context=ctx)
    results["B15"] = ("PASS" if r15.success and r15.result.get("size", 0) > 0 else "FAIL", r15.result)

    # B16: Directory tree
    r16 = reg.execute("list_directory_tree", {"path": base}, context=ctx)
    results["B16"] = ("PASS" if r16.success and len(r16.result.get("tree", [])) > 0 else "FAIL", r16.to_dict())

    # Security B17: ../ escape attempt
    r17 = reg.execute("read_file", {"path": "../../../../../../windows/win.ini"}, context=ctx)
    results["B17"] = ("PASS" if not r17.success and r17.error.get("code") == "PATH_SECURITY_ERROR" else "FAIL", r17.to_dict())

    # Security B18: Absolute path outside workspace
    r18 = reg.execute("read_file", {"path": "C:/Windows/System32/drivers/etc/hosts"}, context=ctx)
    results["B18"] = ("PASS" if not r18.success and r18.error.get("code") == "PATH_SECURITY_ERROR" else "FAIL", r18.to_dict())

    # Security B19: Nested traversal
    r19 = reg.execute("read_file", {"path": f"{base}/sub/../../../../etc/passwd"}, context=ctx)
    results["B19"] = ("PASS" if not r19.success and r19.error.get("code") == "PATH_SECURITY_ERROR" else "FAIL", r19.to_dict())

    # Security B20: Windows drive or backslash traversal
    r20 = reg.execute("read_file", {"path": f"{base}/..\\..\\..\\Windows\\System32"}, context=ctx)
    results["B20"] = ("PASS" if not r20.success and r20.error.get("code") == "PATH_SECURITY_ERROR" else "FAIL", r20.to_dict())

    for k, (status, detail) in sorted(results.items()):
        print(f"[{status}] {k}")
        if status == "FAIL":
            print(f"   Detail: {detail}")

    return results

if __name__ == "__main__":
    run_group_b()
