import sys
import os

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.tools.registry import get_tool_registry
from app.tools.base import ToolContext

def run_group_g():
    reg = get_tool_registry()
    ctx = ToolContext(approved=True, allow_private_http=False)
    results = {}

    print("--- TEST GROUP G: HTTP / API WORKFLOW ---")

    # Safe public API
    # G1: GET
    r1 = reg.execute("http_get", {"url": "https://jsonplaceholder.typicode.com/posts/1"}, context=ctx)
    results["G1"] = ("PASS" if r1.success and r1.result.get("status_code") == 200 else "FAIL", r1.to_dict())

    # G2: Query parameters
    r2 = reg.execute("http_get", {"url": "https://jsonplaceholder.typicode.com/comments", "params": {"postId": 1}}, context=ctx)
    results["G2"] = ("PASS" if r2.success and len(r2.result.get("data", [])) > 0 else "FAIL", r2.to_dict())

    # G3: Headers
    r3 = reg.execute("http_get", {"url": "https://jsonplaceholder.typicode.com/posts/1", "headers": {"X-Test": "Jarvis"}}, context=ctx)
    results["G3"] = ("PASS" if r3.success and r3.result.get("status_code") == 200 else "FAIL", r3.to_dict())

    # G4: JSON response
    r4 = reg.execute("http_get", {"url": "https://jsonplaceholder.typicode.com/posts/1"}, context=ctx)
    is_json = isinstance(r4.result.get("data"), dict) if r4.result else False
    results["G4"] = ("PASS" if r4.success and is_json else "FAIL", r4.to_dict())

    # G5: POST
    r5 = reg.execute("http_post", {"url": "https://jsonplaceholder.typicode.com/posts", "data": {"title": "jarvis test", "body": "testing", "userId": 1}}, context=ctx)
    results["G5"] = ("PASS" if r5.success and r5.result.get("status_code") == 201 else "FAIL", r5.to_dict())

    # G6: PUT
    r6 = reg.execute("http_put", {"url": "https://jsonplaceholder.typicode.com/posts/1", "data": {"title": "updated", "body": "updated body", "userId": 1}}, context=ctx)
    results["G6"] = ("PASS" if r6.success and r6.result.get("status_code") == 200 else "FAIL", r6.to_dict())

    # G7: PATCH
    r7 = reg.execute("http_patch", {"url": "https://jsonplaceholder.typicode.com/posts/1", "data": {"title": "patched"}}, context=ctx)
    results["G7"] = ("PASS" if r7.success and r7.result.get("status_code") == 200 else "FAIL", r7.to_dict())

    # G8: DELETE
    r8 = reg.execute("http_delete", {"url": "https://jsonplaceholder.typicode.com/posts/1"}, context=ctx)
    results["G8"] = ("PASS" if r8.success and r8.result.get("status_code") == 200 else "FAIL", r8.to_dict())

    # G9: Invalid endpoint / 404
    r9 = reg.execute("http_get", {"url": "https://jsonplaceholder.typicode.com/non_existent_resource_xyz_123"}, context=ctx)
    results["G9"] = ("PASS" if not r9.success and r9.error.get("status_code") == 404 else "FAIL", r9.to_dict())

    # G10: Timeout test
    r10 = reg.execute("http_get", {"url": "https://httpbin.org/delay/10", "timeout": 1}, context=ctx)
    results["G10"] = ("PASS" if not r10.success and "timed out" in str(r10.error).lower() else "FAIL", r10.to_dict())

    # G11: Large response size limit
    # Test setting a small max_bytes or testing a large resource
    r11 = reg.execute("http_get", {"url": "https://jsonplaceholder.typicode.com/photos", "max_bytes": 100}, context=ctx)
    results["G11"] = ("PASS" if not r11.success and r11.error.get("code") == "RESPONSE_SIZE_EXCEEDED" else "FAIL", r11.to_dict())

    # G12: HTTP error status
    r12 = reg.execute("http_get", {"url": "https://httpbin.org/status/500"}, context=ctx)
    results["G12"] = ("PASS" if not r12.success and r12.error.get("status_code") == 500 else "FAIL", r12.to_dict())

    # --- SECURITY TESTS ---
    # G13: localhost SSRF block
    r13 = reg.execute("http_get", {"url": "http://localhost:8000/test"}, context=ctx)
    results["G13"] = ("PASS" if not r13.success and r13.error.get("code") == "SSRF_BLOCKED" else "FAIL", r13.to_dict())

    # G14: 127.0.0.1 SSRF block
    r14 = reg.execute("http_get", {"url": "http://127.0.0.1:8000/test"}, context=ctx)
    results["G14"] = ("PASS" if not r14.success and r14.error.get("code") == "SSRF_BLOCKED" else "FAIL", r14.to_dict())

    # G15: private IP (192.168.1.1, 10.0.0.1) SSRF block
    r15 = reg.execute("http_get", {"url": "http://192.168.1.1/admin"}, context=ctx)
    results["G15"] = ("PASS" if not r15.success and r15.error.get("code") == "SSRF_BLOCKED" else "FAIL", r15.to_dict())

    # G16: cloud metadata address (169.254.169.254)
    r16 = reg.execute("http_get", {"url": "http://169.254.169.254/latest/meta-data/"}, context=ctx)
    results["G16"] = ("PASS" if not r16.success and r16.error.get("code") == "SSRF_BLOCKED" else "FAIL", r16.to_dict())

    # G17: Redirect to blocked address
    r17 = reg.execute("http_get", {"url": "https://httpbin.org/redirect-to?url=http://127.0.0.1"}, context=ctx)
    results["G17"] = ("PASS" if not r17.success and ("blocked" in str(r17.error).lower() or r17.error.get("code") in ("SSRF_BLOCKED", "HTTP_ERROR")) else "FAIL", r17.to_dict())

    for k, (status, detail) in sorted(results.items()):
        print(f"[{status}] {k}")
        if status == "FAIL":
            print(f"   Detail: {detail}")

    return results

if __name__ == "__main__":
    run_group_g()
