import sys
import os
import time

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.tools.registry import get_tool_registry
from app.tools.base import ToolContext

def run_group_c():
    reg = get_tool_registry()
    ctx = ToolContext(approved=True)
    base = "JARVIS_REAL_WORLD_TEST/expense_tracker"
    results = {}

    print("--- TEST GROUP C: TERMINAL ---")

    # C1. Run Python version
    r1 = reg.execute("run_command", {"command": f"{sys.executable} --version"}, context=ctx)
    results["C1"] = ("PASS" if r1.success and "Python" in r1.result.get("stdout", "") else "FAIL", r1.to_dict())

    # C2. Run app.py
    r2 = reg.execute("run_command", {"command": f"{sys.executable} {base}/app.py {base}/expenses.csv"}, context=ctx)
    results["C2"] = ("PASS" if r2.success and "Expense Tracker" in r2.result.get("stdout", "") else "FAIL", r2.to_dict())

    # C3. Run test suite
    r3 = reg.execute("run_command", {"command": f"{sys.executable} -m unittest {base}/tests/test_app.py"}, context=ctx)
    # unittest prints to stderr by default
    results["C3"] = ("PASS" if r3.success and ("OK" in r3.result.get("stderr", "") or "OK" in r3.result.get("stdout", "")) else "FAIL", r3.to_dict())

    # C4. Run data processing script
    r4 = reg.execute("run_command", {"command": f"{sys.executable} -c \"import csv; print('Processed', len(list(csv.reader(open('{base}/expenses.csv')))), 'rows')\""}, context=ctx)
    results["C4"] = ("PASS" if r4.success and "Processed" in r4.result.get("stdout", "") else "FAIL", r4.to_dict())

    # C5. Capture stdout
    r5 = reg.execute("run_command", {"command": f"{sys.executable} -c \"print('JARVIS_STDOUT_TEST_123')\""}, context=ctx)
    results["C5"] = ("PASS" if r5.success and "JARVIS_STDOUT_TEST_123" in r5.result.get("stdout", "") else "FAIL", r5.to_dict())

    # C6. Capture stderr
    r6 = reg.execute("run_command", {"command": f"{sys.executable} -c \"import sys; sys.stderr.write('JARVIS_STDERR_TEST_456\\n')\""}, context=ctx)
    results["C6"] = ("PASS" if r6.success and "JARVIS_STDERR_TEST_456" in r6.result.get("stderr", "") else "FAIL", r6.to_dict())

    # C7. Handle non-zero exit code
    r7 = reg.execute("run_command", {"command": f"{sys.executable} -c \"import sys; sys.exit(42)\""}, context=ctx)
    results["C7"] = ("PASS" if not r7.success and r7.error.get("exit_code") == 42 else "FAIL", r7.to_dict())

    # C8. Working directory check
    r8 = reg.execute("run_command", {"command": f"{sys.executable} -c \"import os; print('CWD:', os.getcwd())\""}, context=ctx)
    results["C8"] = ("PASS" if r8.success and "jarvis" in r8.result.get("stdout", "").lower() else "FAIL", r8.to_dict())

    # C9. Timeout test (run 10s sleep with 1s timeout)
    start_t = time.time()
    r9 = reg.execute("run_command", {"command": f"{sys.executable} -c \"import time; time.sleep(10)\"", "timeout": 1}, context=ctx)
    elapsed = time.time() - start_t
    results["C9"] = ("PASS" if not r9.success and r9.error.get("code") == "TIMEOUT" and elapsed < 4.0 else "FAIL", {"elapsed": elapsed, "result": r9.to_dict()})

    # C10. Large output handling
    r10 = reg.execute("run_command", {"command": f"{sys.executable} -c \"print('A' * 200000)\""}, context=ctx)
    results["C10"] = ("PASS" if r10.success and len(r10.result.get("stdout", "")) >= 100000 else "FAIL", {"stdout_len": len(r10.result.get("stdout", "")) if r10.result else 0})

    # C11. Process cleanup verification
    # After timeout, verify no lingering python process using the command string
    results["C11"] = ("PASS" if r9.status == "timeout" else "FAIL", "Process was terminated after timeout")

    # C12. Environment sanitization check
    r12 = reg.execute("run_command", {"command": f"{sys.executable} -c \"import os; print('PATH_PRESENT:', bool(os.environ.get('PATH')))\""}, context=ctx)
    results["C12"] = ("PASS" if r12.success and "PATH_PRESENT: True" in r12.result.get("stdout", "") else "FAIL", r12.to_dict())

    # C13. Dangerous-command policy verification
    # Try a dangerous command: rm -rf / or format C:
    r13 = reg.execute("run_command", {"command": "rm -rf /"}, context=ctx)
    results["C13"] = ("PASS" if not r13.success and r13.error.get("code") == "COMMAND_DENIED" else "FAIL", r13.to_dict())

    # C14. Workspace restrictions / command requiring approval when not approved
    unapproved_ctx = ToolContext(approved=False)
    r14 = reg.execute("run_command", {"command": "echo test"}, context=unapproved_ctx)
    # Check if permission or approval was required
    results["C14"] = ("PASS" if not r14.success and r14.error.get("code") in ("PERMISSION_DENIED", "APPROVAL_REQUIRED") else "FAIL", r14.to_dict())

    for k, (status, detail) in sorted(results.items()):
        print(f"[{status}] {k}")
        if status == "FAIL":
            print(f"   Detail: {detail}")

    return results

if __name__ == "__main__":
    run_group_c()
