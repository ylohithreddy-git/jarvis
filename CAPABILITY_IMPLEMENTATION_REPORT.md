# CAPABILITY IMPLEMENTATION REPORT

**Author:** Lohith (Owner: Capability / Tool Layer)  
**Date:** September 29, 2026  
**Status:** COMPLETE — DEMO READY  

---

## 1. Initial Architecture

Before this implementation, the Capability / Tool Layer consisted of:
- A central `ToolRegistry` in `backend/app/tools/registry.py` registering 44 tools across filesystem, terminal, http, git, github, browser, sandbox, and vision.
- Execution pipeline:
  ```
  Agent/Brain → ToolRegistry.execute() → ToolContext.has_permission() → Tool.execute() → ToolResult
  ```
- While architecturally sound, a critical design defect rendered the permission layer non-functional: `ToolContext.approved = True` by default, causing `has_permission()` to unconditionally return `True` for every tool invocation.

---

## 2. Baseline Test Results

Before modifying production code, a baseline test run was executed on September 29, 2026 using pytest:
- **Total Tests:** 32
- **PASS:** 30
- **FAIL:** 2 (`test_permission_denied_when_permission_missing`, `test_destructive_operations_require_explicit_permissions`)
- **BLOCKED:** 0
- **NOT_TESTED:** 0

Both baseline failures were caused directly by the `approved: bool = True` permission bypass bug.

---

## 3. Bugs and Gaps Found in Audit

1. **Permission Bypass (CRITICAL):** `ToolContext.approved = True` bypassed all permission evaluation in all active execution paths, including `app/agent/loop.py`.
2. **Missing Permission Engine (HIGH):** No central engine existed to manage permission policies, modes, approval request generation, or approval lifecycle.
3. **Missing Normal/Turbo Policy (HIGH):** No distinction between interactive approval mode and pre-authorized automated execution.
4. **Approval Resume Hardcoded to `delete_file` (HIGH):** `app/graph/workflow.py` line 617 rejected any tool other than `delete_file` on resume.
5. **Sandbox Disconnected (HIGH):** `SandboxExecTool` delegated directly to `RunCommandTool` on the host; `DockerSandbox` was orphaned and unused.
6. **Browser Tools Lacked SSRF Protection (HIGH):** `browser_screenshot` and `browser_navigate` accepted arbitrary internal/private URLs.
7. **`permission_required` Contract Incomplete (HIGH):** Missing `request_id`, `summary`, `risk`, and used incorrect status string (`permission_denied`).
8. **Missing Tool Risk Metadata (HIGH):** No tools declared risk classifications (`low`, `medium`, `high`).
9. **BrowserOpenTool False Success (MEDIUM):** Returned `success=True` even when the local preview server was completely offline.
10. **ToolResult Missing `artifacts` Field (MEDIUM):** Artifact references were not attached to `ToolResult`.
11. **Unbounded Agent Results (MEDIUM):** Large file reads and command outputs were passed in full to the LLM context.
12. **Missing Compatibility Aliases (LOW):** `list_files` (for `list_directory`) and `edit_file` (for `patch_file`) were not registered.

---

## 4. Changes Made

### A. Central Permission Engine (`backend/app/permissions/`)
- Created `app/permissions/engine.py` and `app/permissions/__init__.py`.
- Implemented `PermissionEngine`, `PermissionPolicy`, `PermissionMode` (`NORMAL` vs `TURBO`), and `ApprovalRequest`.
- Cryptographic SHA-256 argument binding prevents replay attacks and parameter tampering during approval resume.
- Approval requests have strict expiration timestamps (TTL = 300s).

### B. Core Tool Contracts (`backend/app/tools/base.py`)
- **CRITICAL FIX:** Changed `ToolContext.approved: bool = True` → `approved: bool = False`.
- Re-architected `has_permission()` to evaluate only the configured permissions set, category wildcards, and semantic aliases. The `approved` flag no longer acts as a global permission bypass.
- Added `artifacts: List[Dict[str, Any]] = Field(default_factory=list)` to `ToolResult`.
- Added `risk: str = "medium"` to `Tool` base class and updated `get_definition()` to expose it.

### C. Tool Registry (`backend/app/tools/registry.py`)
- Emits structured `permission_required` results containing `request_id`, `permission`, `summary`, `risk`, `run_id`, and `session_id`.
- Added post-execution bounding: automatically bounds large strings (`content`, `stdout`, `stderr`, directory listings) before delivery to Agent/Brain.

### D. Sandbox Architecture (`backend/app/tools/sandbox_tools.py`)
- Connected `SandboxExecTool` to `DockerSandbox` (`app/sandbox/docker_env.py`).
- If Docker daemon is unavailable, returns `success=False`, `status="blocked"`, error code `SANDBOX_UNAVAILABLE`.
- **NEVER** falls back to host subprocess execution.
- `SandboxResetTool` safely discovers and terminates orphaned `fraiday_sandbox_` Docker containers.

### E. Browser Tools & SSRF (`backend/app/tools/browser_tools.py`)
- Implemented `validate_browser_url()` providing strict SSRF protection for `browser_screenshot` and `browser_navigate`.
- Blocks private IPv4/IPv6, loopback, link-local, and cloud metadata (169.254.169.254).
- Controlled exception: permits authorized local preview server (`localhost:8006`).
- Fixed `BrowserOpenTool`: returns `success=False` with `PREVIEW_UNAVAILABLE` on connection failure; never reports false success.

### F. Multi-Workspace Context Support (`backend/app/workspace/manager.py` & tools)
- Added `root_path` support to `get_workspace_manager(workspace_id, root_path)`.
- Tools dynamically respect `context.workspace_root` and `context.workspace_id` while remaining 100% backward-compatible.

### G. Approval Resume Generalization (`backend/app/graph/workflow.py`)
- Removed hardcoded `delete_file` restriction in `resume_approved_run`.
- Approved tools execute through `ToolRegistry.execute()` with validated parameters and an approved execution context.

### H. Tool Compatibility Aliases (`backend/app/tools/__init__.py`)
- Registered `list_files` → alias for `ListDirectoryTool`.
- Registered `edit_file` → alias for `PatchFileTool`.
- Registered `copy_file` → compatibility alias for `CopyFileTool`.

### I. Artifact Privacy (`backend/app/artifacts/model.py`)
- Explicitly documented and verified that `Artifact.to_dict()` excludes internal `file_path`, preventing path leaks to frontend/SSE.

---

## 5. Permission Architecture

```
User Request
     ↓
Nikunj Brain / Agent Loop
     ↓
ToolRegistry.execute(tool_name, arguments, context)
     ↓
Permission Evaluation (ToolContext.permissions)
     ├── Configured & Authorized?
     │         YES → Execute Tool Capability
     │
     └── Not Authorized?
               NO  → Return ToolResult:
                     status = "permission_required"
                     error.code = "PERMISSION_REQUIRED"
                     metadata = {
                         request_id: "perm_...",
                         permission: "terminal.execute",
                         summary: "...",
                         risk: "high"
                     }
```

---

## 6. Normal Mode vs Turbo Mode

| Feature | Normal Mode | Turbo Mode |
|:---|:---|:---|
| **Semantics** | Pre-authorized permissions execute; any unconfigured action pauses for user approval | Automatically allows configured permissions without interactive prompting |
| **Bypass Policy** | Strictly enforced | Strictly enforced |
| **Unconfigured Perms** | Produces `permission_required` | Produces `permission_required` |
| **Path Traversal Protection** | Active (cannot bypass) | Active (cannot bypass) |
| **SSRF Protection** | Active (cannot bypass) | Active (cannot bypass) |
| **Command Policy (DENIED)** | Active (cannot bypass) | Active (cannot bypass) |
| **Docker Sandbox Isolation** | Active (cannot bypass) | Active (cannot bypass) |

---

## 7. Approval & Resume Lifecycle

1. **Request Creation:** On permission failure, `PermissionEngine` creates an `ApprovalRequest` with a unique `request_id`, arguments SHA-256 hash, and 5-minute expiry.
2. **Run Pause:** Agent runtime pauses execution and emits `permission_required` via SSE.
3. **Approval:** Frontend/User posts approval decision to `/api/runs/{run_id}/approval`.
4. **Integrity Validation:** On resume, `validate_resume()` checks:
   - Request exists and status is `APPROVED`
   - Request has not expired
   - Matching `run_id` (cross-run rejected)
   - Matching `tool` (tool substitution rejected)
   - Matching arguments hash (tampering/replay rejected)
5. **Execution:** Resumes through `ToolRegistry.execute()`.

---

## 8. Sandbox Architecture

```
sandbox_exec Tool
       ↓
Check Docker Daemon Status
       ├── Offline → Return status="blocked", code="SANDBOX_UNAVAILABLE" (No host fallback)
       └── Online  → DockerSandbox.execute_python()
                           ├── Container: python:3.11-slim
                           ├── Memory Limit: 512m
                           ├── Network: Disabled (default)
                           ├── Timeout: 30s
                           └── Output limit: 8000 chars
```

---

## 9. Browser Security & Local Preview

- **Authorized Local Preview:** Local preview at `localhost:8006` is verified for workspace file serving (`index.html`, `style.css`, `app.js`).
- **SSRF Validation:** `browser_screenshot` and `browser_navigate` validate URLs against private IPv4, private IPv6, link-local, loopback, and AWS/GCP/Azure metadata services (169.254.169.254).
- **Truthful Status:** `BrowserOpenTool` connects via HTTP; on failure, reports `PREVIEW_UNAVAILABLE`.

---

## 10. Artifact Architecture

- Artifacts verified on disk before registration via `ArtifactManager`.
- Generated `artifact_id` format: `art_<hex10>`.
- Public URLs: `/api/artifacts/{artifact_id}/content` and `/api/artifacts/{artifact_id}/download`.
- `Artifact.to_dict()` safely omits internal `file_path`.
- `ToolResult.artifacts` embeds public metadata for Brain and UI.

---

## 11. ToolResult Contract

```json
{
  "success": true,
  "tool": "create_file",
  "result": { "path": "index.html", "lines": 15 },
  "data": { "path": "index.html", "lines": 15 },
  "error": null,
  "status": "completed",
  "artifacts": [],
  "metadata": {}
}
```

```json
{
  "success": false,
  "tool": "run_command",
  "result": null,
  "data": null,
  "error": {
    "code": "PERMISSION_REQUIRED",
    "message": "Tool 'run_command' requires permission 'terminal.execute'"
  },
  "status": "permission_required",
  "artifacts": [],
  "metadata": {
    "request_id": "perm_70d10c0e352e",
    "permission": "terminal.execute",
    "summary": "Execute 'run_command' — requires terminal.execute",
    "risk": "high"
  }
}
```

---

## 12. Bounded LLM Results Strategy

To protect the LLM context window from token exhaustion:
- `read_file` content: bounded at 8,000 characters. If truncated: `truncated: true`, `original_size: <int>`.
- `run_command` stdout/stderr: bounded at 4,000 characters.
- `list_directory` entries: bounded at 200 items.
- `search_files` matches: bounded at 100 items.
- **Integrity Guarantee:** Underlying files on disk are never truncated or modified by bounding.

---

## 13. Brain / ToolRegistry Coordination Contract

- Nikunj's Brain obtains tool definitions via `ToolRegistry.get_tool_definitions()`.
- Brain invokes capabilities **exclusively** via `ToolRegistry.execute()`.
- Static AST scan verified that `app/agent/` contains **zero** direct imports of `subprocess`, `os.system`, `pathlib.Path`, `requests`, `httpx`, `aiohttp`, `Playwright`, or `docker`.
- Brain is never told an action succeeded unless `ToolResult.success == True`.

---

## 14. Full Test Suite Results

**Test Runner:** `pytest 9.1.1` (Python 3.13.2, Windows 11 AMD64)  
**Command:**
```powershell
python -m pytest tests/test_capability_layer.py tests/test_workspace_security.py tests/test_tool_action_system.py tests/test_capability_complete.py -v --tb=short
```

| Test File | Total | PASS | FAIL | BLOCKED (Skipped) |
|:---|:---:|:---:|:---:|:---:|
| `test_capability_layer.py` | 16 | 16 | 0 | 0 |
| `test_workspace_security.py` | 7 | 7 | 0 | 0 |
| `test_tool_action_system.py` | 9 | 9 | 0 | 0 |
| `test_capability_complete.py` | 107 | 106 | 0 | 1 (`test_M1_github_get_repo`) |
| **TOTAL** | **139** | **138** | **0** | **1** |

---

## 15. Remaining Blockers (External Dependencies)

1. **Docker Daemon:** Docker Desktop service is offline in this environment. The capability layer correctly handles this by returning `SANDBOX_UNAVAILABLE` on `sandbox_exec` without falling back to host execution.
2. **GitHub Token:** `GITHUB_TOKEN` environment variable is not configured. `test_M1_github_get_repo` is truthfully marked `SKIPPED (BLOCKED)`.
3. **LLM Credentials:** `GROQ_API_KEY` is not set. Brain agent execution tests requiring live LLM inference remain blocked until keys are provided.

---

## 16. Files Modified and Created

### Files Created
- `backend/app/permissions/engine.py` (Central Permission Engine, Policy, Approval lifecycle)
- `backend/app/permissions/__init__.py` (Exports)
- `backend/tests/test_capability_complete.py` (Comprehensive 107-test capability suite)
- `backend/tests/demo_real_world_workflow.py` (End-to-end real world demo script)
- `CAPABILITY_PRECHANGE_BASELINE.md` (Pre-change baseline test report)
- `CAPABILITY_IMPLEMENTATION_REPORT.md` (This document)
- `CAPABILITY_FINAL_READINESS.md` (Final readiness verdict)

### Files Modified
- `backend/app/tools/base.py` (Fixed `approved=False` bypass, added `artifacts`, added `risk`)
- `backend/app/tools/registry.py` (Integrated `permission_required` metadata, bounded LLM results)
- `backend/app/tools/__init__.py` (Registered `list_files`, `edit_file`, `copy_file` aliases)
- `backend/app/tools/filesystem.py` (Dynamic workspace resolution via `_get_workspace`, risk metadata)
- `backend/app/tools/terminal.py` (Dynamic workspace resolution, risk metadata)
- `backend/app/tools/git_tools.py` (Context passing for workspace isolation, risk metadata)
- `backend/app/tools/browser_tools.py` (SSRF protection, truthful error reporting, risk metadata)
- `backend/app/tools/sandbox_tools.py` (Docker integration, SANDBOX_UNAVAILABLE, risk metadata)
- `backend/app/artifacts/model.py` (Exclusion of `file_path` from public serialization)
- `backend/app/workspace/manager.py` (Added `root_path` parameter to `get_workspace_manager`)
- `backend/app/graph/workflow.py` (Generalized approval resume through ToolRegistry)
- `backend/app/agent/loop.py` (Context creation uses `approved=False`)
- `backend/tests/test_capability_layer.py` (Updated assertions to reflect `permission_required` specification)
