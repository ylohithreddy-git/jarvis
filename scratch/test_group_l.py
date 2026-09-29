import sys
import os
import time

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.tools.registry import get_tool_registry
from app.tools.base import ToolContext

def run_group_l():
    reg = get_tool_registry()
    ctx = ToolContext(approved=True)
    results = {}

    print("--- TEST GROUP L: APPLICATION CONTROL ---")

    # L1: Launch Notepad
    r1 = reg.execute("run_command", {"command": "cmd /c start notepad.exe"}, context=ctx)
    results["L1"] = ("PASS" if r1.success else "FAIL", r1.to_dict())

    time.sleep(1)

    # L2: Verify process
    r2 = reg.execute("run_command", {"command": 'tasklist /fi "IMAGENAME eq notepad.exe"'}, context=ctx)
    exists = "notepad.exe" in r2.result.get("stdout", "").lower()
    results["L2"] = ("PASS" if r2.success and exists else "FAIL", r2.to_dict())

    # L3: Close
    r3 = reg.execute("run_command", {"command": "taskkill /F /IM notepad.exe"}, context=ctx)
    results["L3"] = ("PASS" if r3.success else "FAIL", r3.to_dict())

    time.sleep(1)

    # L4: Verify stopped
    r4 = reg.execute("run_command", {"command": 'tasklist /fi "IMAGENAME eq notepad.exe"'}, context=ctx)
    stopped = "notepad.exe" not in r4.result.get("stdout", "").lower()
    results["L4"] = ("PASS" if r4.success and stopped else "FAIL", r4.to_dict())

    # Invalid executable test
    r5 = reg.execute("run_command", {"command": "non_existent_app_99999.exe"}, context=ctx)
    results["L_invalid"] = ("PASS" if not r5.success and r5.error.get("exit_code") != 0 else "FAIL", r5.to_dict())

    for k, (status, detail) in sorted(results.items()):
        print(f"[{status}] {k}")
        if status == "FAIL":
            print(f"   Detail: {detail}")

    return results

if __name__ == "__main__":
    run_group_l()
