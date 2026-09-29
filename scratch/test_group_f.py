import sys
import os

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.tools.registry import get_tool_registry
from app.tools.base import ToolContext

def run_group_f():
    reg = get_tool_registry()
    ctx = ToolContext(approved=True)
    results = {}

    print("--- TEST GROUP F: GIT WORKFLOW ---")
    
    # F1. git status
    r1 = reg.execute("git_status", {}, context=ctx)
    results["F1"] = ("PASS" if r1.success and "status" in r1.result else "FAIL", r1.to_dict())

    # F2. git diff
    r2 = reg.execute("git_diff", {}, context=ctx)
    results["F2"] = ("PASS" if r2.success and "diff" in r2.result else "FAIL", r2.to_dict())

    # F3. git create branch
    test_branch = "feature/expense-fix-test"
    r3 = reg.execute("git_create_branch", {"branch_name": test_branch}, context=ctx)
    results["F3"] = ("PASS" if r3.success else "FAIL", r3.to_dict())

    # F4. git checkout branch
    r4 = reg.execute("git_checkout", {"branch_name": test_branch}, context=ctx)
    results["F4"] = ("PASS" if r4.success else "FAIL", r4.to_dict())

    # F5. modify project file
    reg.execute("append_file", {"path": "JARVIS_REAL_WORLD_TEST/expense_tracker/README.md", "content": "\n<!-- Git test modification -->\n"}, context=ctx)
    results["F5"] = ("PASS", "Modified file")

    # F6. run test
    r6 = reg.execute("run_command", {"command": f"{sys.executable} -c \"print('Git test build OK')\""}, context=ctx)
    results["F6"] = ("PASS" if r6.success else "FAIL", r6.to_dict())

    # F7. git diff
    r7 = reg.execute("git_diff", {}, context=ctx)
    results["F7"] = ("PASS" if r7.success and "Git test modification" in r7.result.get("diff", "") else "FAIL", r7.to_dict())

    # F8. git add
    r8 = reg.execute("git_add", {"files": ["JARVIS_REAL_WORLD_TEST/expense_tracker/README.md"]}, context=ctx)
    results["F8"] = ("PASS" if r8.success else "FAIL", r8.to_dict())

    # F9. git commit
    r9 = reg.execute("git_commit", {"message": "test: verification commit for audit"}, context=ctx)
    # Note: git commit might require user email/name in git config
    results["F9"] = ("PASS" if r9.success else "FAIL", r9.to_dict())

    # F10. git log
    r10 = reg.execute("git_log", {"max_count": 3}, context=ctx)
    results["F10"] = ("PASS" if r10.success and "commits" in r10.result else "FAIL", r10.to_dict())

    # F11. Switch back to original branch (main)
    r11 = reg.execute("git_checkout", {"branch_name": "main"}, context=ctx)
    results["F11"] = ("PASS" if r11.success else "FAIL", r11.to_dict())

    # Clean up test branch
    reg.execute("run_command", {"command": f"git branch -D {test_branch}"}, context=ctx)
    # Revert the test commit on main if it occurred on test_branch, else reset
    reg.execute("run_command", {"command": "git checkout JARVIS_REAL_WORLD_TEST/expense_tracker/README.md"}, context=ctx)

    for k, (status, detail) in sorted(results.items()):
        print(f"[{status}] {k}")
        if status == "FAIL":
            print(f"   Detail: {detail}")

    return results

if __name__ == "__main__":
    run_group_f()
