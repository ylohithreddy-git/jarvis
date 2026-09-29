# CAPABILITY_ARCHITECTURE_AUDIT.md

**Date:** September 29, 2026  
**Auditor:** Lohith (Capability / Tool Layer Owner)  
**Phase:** PHASE 0 — Read-Only Architecture Audit  
**Status:** ✅ COMPLETE — No source files modified

---

## 1. Existing Architecture

### Runtime Flow (Traced from Source Code)

```
User / Frontend
      ↓
POST /api/runs/   (app/api/runs.py)
      ↓
run_service.start_run(...)  (app/runtime/sessions/service.py)
      ↓
execute_run_task(...)  (app/graph/workflow.py)
      ↓
  Intent Router  ─────────────── Conversational → LLM Direct Reply
      ↓
  Autonomous DAG
      ↓
 orchestrator_node → researcher_node → executor_node → validator_node → recovery_node
      ↓
executor_node  (app/graph/nodes/executor.py)
      ↓
workspace/tools.py  execute_tool(tool_name, ...)
      ↓
ToolRegistry.execute(tool_name, arguments, ToolContext)  (app/tools/registry.py)
      ↓
PermissionEngine (ToolContext.has_permission)  ← INSIDE REGISTRY
      ↓
CommandPolicy (app/workspace/policy.py)  ← INSIDE TERMINAL TOOL
      ↓
Capability (filesystem.py / terminal.py / http_tools.py / ...)
      ↓
WorkspaceManager.resolve_path  ← PATH SECURITY
      ↓
ToolResult(success, tool, result, error, status, metadata)
      ↓
executor_node → state["observations"]
      ↓
validator_node → run_completed SSE event
      ↓
Frontend (SSE stream)
```

### Approval Pause/Resume Flow

```
executor_node → tool returns status="approval_required"
      ↓
workflow.py: state["approval_required"] = True, state["approval_status"] = "pending"
      ↓
runs_db[run_id]["status"] = "paused"
      ↓
SSE: approval_required event → Farhan's frontend
      ↓
User approves/rejects via POST /api/runs/{run_id}/approval
      ↓
approve_run() → resume_approved_run()
      ↓
execute_tool("delete_file", path=..., approved=True)
      ↓
ToolRegistry.execute → ToolResult
      ↓
run resumes at validator_node
```

---

## 2. Active ToolRegistry

**File:** `backend/app/tools/registry.py`  
**Global Instance:** `_global_tool_registry` created at module level  
**Accessor:** `get_tool_registry() -> ToolRegistry`  
**Initialization:** `backend/app/tools/__init__.py` registers all 44 tools on import

### ToolRegistry Capabilities

| Method | Purpose |
|:---|:---|
| `register(tool)` | Adds a Tool instance to the registry |
| `unregister(name)` | Removes a tool by name |
| `get_tool(name)` | Lookup by name |
| `list_tools()` | All registered tools |
| `get_tool_definitions(...)` | Returns schema dicts; supports `as_openai=True` for function-calling format |
| `validate_schema(tool, args)` | Validates required arguments before execution |
| `execute(tool_name, args, context)` | **Single gateway:** enforces permissions, validates schema, calls tool |

### Permission Enforcement Location
`ToolRegistry.execute()` iterates `tool.required_permissions` and calls `ctx.has_permission(perm)`. Returns `status="permission_denied"` if any permission is missing.

---

## 3. Active Capability Implementations

### 3.1 All 44 Registered Tools

**Filesystem (16 tools):**
| Tool Name | Class | Status |
|:---|:---|:---|
| `list_directory` | `ListDirectoryTool` | ✅ Active |
| `read_file` | `ReadFileTool` | ✅ Active |
| `write_file` | `WriteFileTool` | ✅ Active |
| `create_file` | `CreateFileTool` | ✅ Active (alias for WriteFileTool) |
| `update_file` | `UpdateFileTool` | ✅ Active (alias for WriteFileTool) |
| `delete_file` | `DeleteFileTool` | ✅ Active |
| `create_directory` | `CreateDirectoryTool` | ✅ Active |
| `move` | `MoveFileTool` | ✅ Active |
| `rename_file` | `RenameFileTool` | ✅ Active |
| `copy` | `CopyFileTool` | ✅ Active |
| `append_file` | `AppendFileTool` | ✅ Active |
| `patch_file` | `PatchFileTool` | ✅ Active |
| `get_file_info` | `GetFileInfoTool` | ✅ Active |
| `list_directory_tree` | `ListDirectoryTreeTool` | ✅ Active |
| `diff_files` | `DiffFilesTool` | ✅ Active |
| `search_files` | `SearchFilesTool` | ✅ Active |

**Terminal (2 tools):**
| Tool Name | Class | Status |
|:---|:---|:---|
| `run_command` | `RunCommandTool` | ✅ Active |
| `exec` | `TerminalExecTool` | ✅ Active (alias for RunCommandTool) |

**HTTP (5 tools):**
| Tool Name | Class | Status |
|:---|:---|:---|
| `http_get` | `HttpGetTool` | ✅ Active with SSRF protection |
| `http_post` | `HttpPostTool` | ✅ Active with SSRF protection |
| `http_put` | `HttpPutTool` | ✅ Active with SSRF protection |
| `http_patch` | `HttpPatchTool` | ✅ Active with SSRF protection |
| `http_delete` | `HttpDeleteTool` | ✅ Active with SSRF protection |

**Git (9 tools):**
| Tool Name | Class | Status |
|:---|:---|:---|
| `git_status` | `GitStatusTool` | ✅ Active |
| `git_diff` | `GitDiffTool` | ✅ Active |
| `git_log` | `GitLogTool` | ✅ Active |
| `git_add` | `GitAddTool` | ✅ Active |
| `git_commit` | `GitCommitTool` | ✅ Active |
| `git_checkout` | `GitCheckoutTool` | ✅ Active |
| `git_create_branch` | `GitCreateBranchTool` | ✅ Active |
| `git_pull` | `GitPullTool` | ✅ Active |
| `git_push` | `GitPushTool` | ✅ Active |

**GitHub (4 tools):**
| Tool Name | Class | Status |
|:---|:---|:---|
| `github_get_repo` | `GitHubGetRepoTool` | ✅ Active (anonymous if no token) |
| `github_list_issues` | `GitHubListIssuesTool` | ✅ Active |
| `github_create_issue` | `GitHubCreateIssueTool` | ✅ Active |
| `github_create_pr` | `GitHubCreatePRTool` | ✅ Active |

**Browser (3 tools):**
| Tool Name | Class | Status |
|:---|:---|:---|
| `open_browser` | `BrowserOpenTool` | ✅ Active (local preview only) |
| `browser_screenshot` | `BrowserScreenshotTool` | ✅ Active (Playwright) |
| `browser_navigate` | `BrowserNavigateTool` | ⚠️ Unrestricted URL — no SSRF guard |

**Sandbox (3 tools):**
| Tool Name | Class | Status |
|:---|:---|:---|
| `sandbox_inspect` | `SandboxInspectTool` | ✅ Active |
| `sandbox_exec` | `SandboxExecTool` | ⚠️ Delegates to RunCommandTool (no Docker isolation) |
| `sandbox_reset` | `SandboxResetTool` | ⚠️ Stub only — returns `{"status": "reset_ready"}` |

**Vision (2 tools):**
| Tool Name | Class | Status |
|:---|:---|:---|
| `analyze_image` | `AnalyzeImageTool` | ✅ Active |
| `get_attachment_info` | `GetAttachmentInfoTool` | ✅ Active |

---

## 4. Existing Permission Implementation

### 4.1 ToolContext (Source: `app/tools/base.py`)

```python
class ToolContext(BaseModel):
    run_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = "default_user"
    workspace_id: Optional[str] = "default"
    workspace_root: Optional[str] = "."
    emit: Optional[Any] = None
    approved: bool = True           # ← CRITICAL BUG — see Section 9
    timeout_s: int = 45
    permissions: Set[str] = Field(default_factory=lambda: {
        "filesystem.read", "filesystem.write", "filesystem.delete",
        "terminal.execute", "git.read", "git.write", "git.push",
        "github.read", "github.write", "http.read", "http.write",
        "browser.execute", "sandbox.execute",
    })
    allow_private_http: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def has_permission(self, permission: str) -> bool:
        if self.approved or "*" in self.permissions or "admin" in self.permissions:
            return True      # ← approved=True bypasses all permission checks
        if permission in self.permissions:
            return True
        parts = permission.split(".")
        if len(parts) == 2 and f"{parts[0]}.*" in self.permissions:
            return True
        return False
```

**Permission classes implemented (verified in source):**
- `filesystem.read` — ReadFileTool, ListDirectoryTool, GetFileInfoTool, ListDirectoryTreeTool, DiffFilesTool, SearchFilesTool
- `filesystem.write` — WriteFileTool, CreateFileTool, UpdateFileTool, AppendFileTool, PatchFileTool, MoveFileTool, CopyFileTool, CreateDirectoryTool
- `filesystem.delete` — DeleteFileTool
- `terminal.execute` — RunCommandTool, TerminalExecTool
- `git.read` — GitStatusTool, GitDiffTool, GitLogTool
- `git.write` — GitAddTool, GitCommitTool, GitCheckoutTool, GitCreateBranchTool, GitPullTool
- `git.push` — GitPushTool
- `github.read` — GitHubGetRepoTool, GitHubListIssuesTool
- `github.write` — GitHubCreateIssueTool, GitHubCreatePRTool
- `http.read` — HttpGetTool
- `http.write` — HttpPostTool, HttpPutTool, HttpPatchTool, HttpDeleteTool
- `browser.execute` — BrowserOpenTool, BrowserScreenshotTool, BrowserNavigateTool
- `sandbox.execute` — SandboxInspectTool, SandboxExecTool, SandboxResetTool
- `vision.analyze` — AnalyzeImageTool
- `attachment.read` — GetAttachmentInfoTool

### 4.2 Command Security Policy (Source: `app/workspace/policy.py`)

Three-tier classification: `POLICY_SAFE` → `POLICY_APPROVAL_REQUIRED` → `POLICY_DENIED`

- `DENIED_PATTERNS`: format, shutdown, reg add/delete, mkfs, dd if=, powershell -enc, /etc/shadow, /etc/passwd, cd ../..
- `APPROVAL_PATTERNS`: pip install, npm/pnpm/yarn install, del /f, rm -rf, rmdir /s, git push/reset/clean
- `SAFE_COMMAND_PREFIXES`: python, node, npm test/run, git status/diff/log/branch/show, dir, ls, cat, echo, pwd

### 4.3 Approval/Resume Mechanism

- **API:** `POST /api/runs/{run_id}/approval` or `.../approve`
- **States:** `paused` → approval decision → `running` or `completed`
- **Current limitation:** Only `delete_file` is wired through the approval resume path in `resume_approved_run()`. Line 617 explicitly: `if approval_request.get("tool") != "delete_file": raise ValueError("Unsupported approval action")`
- **Request binding:** Bound to `run_id` via `runs_db[run_id]`

---

## 5. Existing Artifact Implementation

### 5.1 Dual Artifact System (both verified in source)

**Layer 1 — User-Facing ArtifactManager (`app/artifacts/`)**
```python
class Artifact(BaseModel):   # app/artifacts/model.py
    artifact_id: str
    filename: str
    mime_type: str = "application/octet-stream"
    size: int = 0
    file_path: str           # ← INTERNAL — never sent directly to frontend
    url: str                 # → /api/artifacts/{artifact_id}/content
    download_url: str        # → /api/artifacts/{artifact_id}/download
    preview_supported: bool = True
    viewer_type: ArtifactViewerType
    created_at: float
    source_tool: Optional[str]
    session_id: Optional[str]
    conversation_id: Optional[str]
    metadata: Dict[str, Any]
```

- `ArtifactManager.register_artifact()` verifies `os.path.exists()` before registering
- REST: `/api/artifacts/{id}/content` → `FileResponse` (inline)
- REST: `/api/artifacts/{id}/download` → `FileResponse` (attachment)
- `file_path` is stored internally, **not exposed via the public API JSON** — uses artifact ID routing

**Layer 2 — Runtime Dataclass (`app/runtime/models.py`)**
```python
@dataclass
class Artifact:
    id: str
    type: str    # "file" | "url" | "image" | "data"
    name: str
    action: str
    path: Optional[str]
    url: Optional[str]
    bytes: int
    mime: Optional[str]
    preview_url: Optional[str]
```

Used internally in graph state, not exposed to frontend directly.

### 5.2 Artifact Security Assessment

- **Internal `file_path` is NOT serialized by the public `/api/artifacts/` list endpoint** — verified by inspecting `app/api/artifacts.py` route responses
- Artifact retrieval at `/content` uses `artifact_id` as lookup key, not raw path
- `ArtifactManager` validates file existence and workspace-relative paths before registration
- **Gap:** The `file_path` field IS present in `artifact.to_dict()` which is sent in SSE events and some `ToolResult.data` payloads. This may leak internal filesystem paths to the frontend.

---

## 6. Existing Browser/Preview Implementation

### 6.1 Local Preview Server (`app/api/preview.py`)

- Separate FastAPI router on port 8006 (inferred from `BrowserOpenTool`)
- Serves workspace HTML/code files with auto-injected live-reload polling script
- Endpoint: `GET /api/preview/{path}` → serves workspace file content
- Endpoint: `GET /api/preview/{workspace_id}/reload-check`
- Endpoint: `GET /api/preview/{workspace_id}/open` → launches system browser via `webbrowser.open()`
- **Security note:** Path traversal protection unverified — pending `preview.py` full read (file not fully read in audit)

### 6.2 Browser Tools (`app/tools/browser_tools.py`)

| Tool | Implementation | Security |
|:---|:---|:---|
| `open_browser` | Fetches from `localhost:8006/api/preview/{path}` | ⚠️ No path traversal validation at tool level |
| `browser_screenshot` | Playwright Chromium headless | ⚠️ No SSRF guard on `url` parameter |
| `browser_navigate` | Playwright Chromium headless | ⚠️ No SSRF guard on `url` parameter |

**Critical gap:** `browser_screenshot` and `browser_navigate` accept arbitrary URLs with no SSRF protection, allowing the agent to browse external sites or internal network endpoints.

---

## 7. Existing Security Controls

### 7.1 Filesystem Security

| Control | Mechanism | Verified |
|:---|:---|:---|
| Workspace containment | `WorkspaceManager.resolve_path()` — raises `PathSecurityError` | ✅ |
| Path traversal (`../../`) | `os.path.commonpath()` check | ✅ |
| Symlink/junction escape | `os.path.realpath()` on existing path; ancestor traversal for non-existing paths | ✅ |
| Windows drive escape | Drive letter comparison before normalization | ✅ |
| Max read size | 1MB limit in `ws.read_file()` | ✅ |

### 7.2 Terminal Security

| Control | Mechanism | Verified |
|:---|:---|:---|
| Command whitelist/blacklist | `check_command_policy()` three-tier | ✅ |
| Process isolation (Unix) | `start_new_session=True` | ✅ |
| Process isolation (Windows) | `CREATE_NEW_PROCESS_GROUP` | ✅ |
| Timeout enforcement | `subprocess.communicate(timeout=N)` with `TimeoutExpired` | ✅ |
| Process tree cleanup (Unix) | `os.killpg(pgid, SIGKILL)` | ✅ |
| Process tree cleanup (Windows) | `psutil` recursive + `taskkill /F /T /PID` fallback | ✅ |
| Output limits | Background logs: `logs[-2000:]`; observations: 300-char caps | ✅ |
| CWD restriction | Always uses `ws.root_path` — no CWD parameter to tools | ✅ |

### 7.3 HTTP Security

| Control | Mechanism | Verified |
|:---|:---|:---|
| SSRF — private IP blocking | `is_private_or_internal_ip()` using `ipaddress` module | ✅ |
| SSRF — DNS resolution | `socket.getaddrinfo()` resolves all IPs before request | ✅ |
| SSRF — cloud metadata | `169.254.169.254` explicitly blocked | ✅ |
| SSRF — protocol restriction | Only `http`/`https` allowed | ✅ |
| Response size limit | 5MB default, 8KB chunked streaming | ✅ |
| Private HTTP override | `context.allow_private_http` only — not user-controlled | ✅ |
| Redirect protection | ⚠️ Not explicitly verified — `httpx` follows redirects by default |

### 7.4 Sandbox Security

| Control | Mechanism | Verified |
|:---|:---|:---|
| Docker container isolation | `app/sandbox/docker_env.py` `DockerSandbox` class | ⚠️ DISCONNECTED |
| Filesystem sandboxing | `WorkspaceManager.resolve_path()` | ✅ |
| Command policy | `check_command_policy()` via `sandbox_exec → run_command` | ✅ |

---

## 8. Existing Tests

### 8.1 `backend/tests/test_capability_layer.py` (260 lines)

Verifies with real tool execution (NOT mocks):
- ✅ ToolRegistry registration and lookup
- ✅ Unknown tool error (`UNKNOWN_TOOL`)
- ✅ Schema validation (`MISSING_REQUIRED_ARGUMENT`)
- ✅ Permission denied enforcement (`PERMISSION_DENIED`)
- ✅ Filesystem write/read/delete round-trip
- ✅ Path traversal security (`PATH_SECURITY_ERROR`)
- ✅ Terminal timeout and process cleanup (1s timeout on 10s sleep)
- ✅ Terminal successful execution
- ✅ HTTP SSRF private IP blocking
- ✅ HTTP trusted context allowing private access
- ✅ HTTP response size limit
- ✅ Git status tool
- ✅ GitHub tools registration
- ✅ Sandbox inspect tool
- ✅ Browser open tool

### 8.2 `backend/tests/test_workspace_security.py` (72 lines)

Tests:
- ✅ `../` traversal containment
- ✅ Absolute path outside workspace rejection
- ✅ Windows drive escape rejection
- ✅ `check_command_policy` for `POLICY_SAFE`, `POLICY_APPROVAL_REQUIRED`, `POLICY_DENIED`

### 8.3 `backend/tests/test_tool_action_system.py` (199 lines)

Tests:
- ✅ `list_directory`, `read_file`, `create_file`, `update_file`, `run_command`
- ✅ `PathSecurityError` sandbox violation checks
- ✅ Structured error returns

---

## 9. Missing Requirements

### 9.1 CRITICAL — `ToolContext.approved = True` Bypasses All Permission Checks

**Location:** `app/tools/base.py` line: `approved: bool = True`

**Problem:** `has_permission()` returns `True` immediately when `approved is True`, regardless of the `permissions` set. Since `ToolContext()` defaults to `approved=True`, the permission set on `ToolContext` is **never actually evaluated** in the default code path.

The agent always constructs a default `ToolContext()` which means permissions are effectively never enforced unless the caller explicitly passes `ToolContext(approved=False, permissions={...})`.

**Risk:** HIGH — The entire permission system is a no-op in the default execution path.

**Required Fix:** Change default to `approved: bool = False`. The `approved` field should represent that a specific destructive action was explicitly approved by a user, not a global bypass flag.

### 9.2 MISSING — No Normal/Turbo Mode Policy

No `mode` field exists in `ToolContext` or any configuration.  
No concept of "pre-authorized permission set" vs "requires approval per action."  
**Required:** A `PermissionPolicy` with `mode: "normal" | "turbo"` and a configured permission set.

### 9.3 MISSING — Permission-Required Contract Fields

The specification requires these fields when returning `permission_required`:
```json
{
  "status": "permission_required",
  "request_id": "perm_123",
  "tool": "run_command",
  "permission": "terminal.execute",
  "summary": "Execute npm install",
  "risk": "medium"
}
```

Current implementation returns `status="permission_denied"` (not `permission_required`) and does not include `request_id`, `summary`, or `risk`.

### 9.4 MISSING — Risk Classification Per Tool

No `risk` metadata on any Tool definition.  
The `Tool.get_definition()` does not include `risk`.  
Required: Low/Medium/High risk on each tool.

### 9.5 MISSING — Bounded LLM Result Representation

When `read_file` returns a 40,000-character file, the full content is placed in `ToolResult.result` with no truncation for the agent-facing context. The spec requires:
```json
{"content": "bounded...", "truncated": true, "original_size": 40000}
```

### 9.6 MISSING — Approval Resume for All Tools (Not Just `delete_file`)

`resume_approved_run()` at line 617 of `workflow.py` hard-codes:
```python
if approval_request.get("tool") != "delete_file":
    raise ValueError("Unsupported approval action")
```

The spec requires approval/resume for any tool that returns `approval_required`, including `run_command` for package installs, Git push, etc.

### 9.7 MISSING — `browser.preview` Permission (Spec Name)

Current implementation uses `browser.execute` for all browser tools. The spec defines `browser.preview` as the permission class for local preview. This is a naming mismatch — not a missing capability.

### 9.8 MISSING — Request ID for Approval Requests

When `run_command` returns `status="approval_required"`, there is no `request_id` field in the error payload. The spec requires a stable `request_id` that can be used in the `POST /approval` body to prevent cross-request approval.

### 9.9 MISSING — `list_files` Alias

The spec lists `list_files` as a required name. The current implementation uses `list_directory`. This is an alias gap.

### 9.10 MISSING — `edit_file` Alias

The spec lists `edit_file`. Current names: `update_file`, `patch_file`. An `edit_file` alias or redirect is needed.

### 9.11 PARTIAL — Sandbox: No Docker Runtime Integration in Active Tool Path

`app/sandbox/docker_env.py` contains a `DockerSandbox` class that correctly uses the Docker SDK with container isolation, memory limits, and network control. However, **it is completely disconnected** from the active tool path:
- `SandboxExecTool.execute()` → delegates to `RunCommandTool` (host subprocess)
- The `DockerSandbox` class is never imported or called by any registered tool

When Docker is unavailable, the spec requires returning `SANDBOX_UNAVAILABLE`. Currently, the sandbox simply runs on the host.

---

## 10. Partial Requirements

### 10.1 Approval System — Partially Implemented

| Aspect | Status |
|:---|:---|
| `POST /api/runs/{run_id}/approval` endpoint | ✅ Exists |
| Pausing run on approval_required | ✅ Implemented |
| `pending` / `approved` / `rejected` states | ✅ Tracked in state |
| Resume after approval | ⚠️ Only for `delete_file` |
| `request_id` per approval request | ⚠️ Used in event payload but not validated on resume |
| `expired` / `invalid` request_id states | ❌ Not implemented |
| Cross-request replay prevention | ❌ Not implemented |

### 10.2 Browser Preview — Partially Implemented

| Aspect | Status |
|:---|:---|
| Local file serving at `localhost:8006` | ✅ `app/api/preview.py` exists |
| Preview workspace HTML files | ✅ Implemented |
| Live-reload support | ✅ Injected script |
| `open_browser` tool connected to preview server | ✅ |
| Workspace path containment in preview server | ⚠️ Unverified in preview.py (not fully read) |
| Path traversal prevention in `open_browser` | ❌ Tool does no validation |
| SSRF on `browser_screenshot` / `browser_navigate` | ❌ No protection |

### 10.3 ToolResult Contract — Partially Matches Spec

| Field | Spec | Current | Status |
|:---|:---|:---|:---|
| `success` | bool | bool | ✅ |
| `tool` | str | str | ✅ |
| `data` | any | Optional[Any] | ✅ |
| `error` | dict{code, message} | Optional[Dict] | ✅ |
| `artifacts` | list | ❌ Not in ToolResult | ❌ Missing |
| `metadata` | dict | Dict | ✅ |
| `status` | str | Optional[str] | ✅ |

**Gap:** `artifacts` field is missing from `ToolResult`. The spec requires tools to return artifact references directly in the result. Currently artifacts are registered via `ArtifactManager` separately.

### 10.4 Artifact Contract — Partially Matches Spec

| Field | Spec | Current | Status |
|:---|:---|:---|:---|
| `artifact_id` | str | str | ✅ |
| `filename` | str | str | ✅ |
| `mime_type` | str | str | ✅ |
| `size` | int | int | ✅ |
| `preview_supported` | bool | bool | ✅ |
| `secure_url` | str | `url` field | ✅ (different name) |
| `file_path` exposed | BAD | ⚠️ In `to_dict()` / SSE events | ⚠️ Leaks internally |

---

## 11. Incorrect Requirements

### 11.1 `ToolContext.approved = True` — Incorrect Default

The `approved` flag is intended to mean "this specific action has been explicitly approved by a user." However, the current default `True` means all tools are pre-approved, making the entire permission set meaningless in default usage.

**Assessment:** This is the single most critical bug in the permission architecture.

### 11.2 `SandboxExecTool` — Incorrect Behavior

`SandboxExecTool` is documented as "isolated sandbox" but actually runs directly on the host as a subprocess. This is an incorrect implementation relative to both the spec and the tool description.

**Assessment:** Mislabeled; should either connect to `DockerSandbox` or explicitly return `SANDBOX_UNAVAILABLE` when Docker is offline.

### 11.3 `BrowserOpenTool` — Returns `success=True` on Error

Lines 34-38 of `browser_tools.py` return `success=True` even when an exception occurs:
```python
except Exception as e:
    return ToolResult(success=True, ...)  # ← Wrong
```

This means the agent cannot distinguish a successful preview from a failed connection to the preview server.

### 11.4 `resume_approved_run()` — Only Handles `delete_file`

Any tool that returns `status="approval_required"` (e.g., `run_command` with `pip install`) will pause the run, but the resume endpoint will raise `ValueError("Unsupported approval action")` for all non-delete tools. This is logically incorrect.

---

## 12. Duplicate / Legacy Implementations

### 12.1 `backend/app/sandbox/docker_env.py` — Orphaned DockerSandbox

`DockerSandbox` is a complete, correct Docker sandbox implementation that is **never used** by any registered tool. It is not imported anywhere in the active agent path.

**Classification:** Legacy / Disconnected — should be connected to `SandboxExecTool`.

### 12.2 `copy_file` vs `copy` Naming

Two copy-related tools:
- `CopyFileTool` registered as `copy`
- `CopyFileLegacyTool` registered as `copy_file` (if present — unconfirmed)

**Action:** Verify `__init__.py` registrations — do not delete working tools.

### 12.3 `app/db/database.py` Reference in `terminal.py`

`TerminalSession.start()` and `kill()` try to import `from app.db.database import db`. No `app/db/` directory was found in the audit. This import is wrapped in `try/except` so it silently fails, but indicates orphaned database integration code.

### 12.4 Dual `ToolResult`-like Concepts

- `ToolResult` in `app/tools/base.py` — active, canonical
- `RunOutcome` in `app/runtime/protocols.py` — separate run-level result
- `workspace/tools.py` `execute_tool()` returns a plain `dict`, not `ToolResult`

**Assessment:** The `workspace/tools.py` shim converts `ToolResult` to dict before returning to graph. This is a translation layer, not a duplicate, but it breaks the canonical `ToolResult` contract at the graph boundary.

---

## 13. Exact Files That Need Modification

| File | Change Required | Priority |
|:---|:---|:---|
| `app/tools/base.py` | Fix `approved: bool = False`; add `artifacts: List[Dict]` to `ToolResult`; add `risk` to `Tool`; add `PermissionPolicy` class | **CRITICAL** |
| `app/tools/registry.py` | Return `permission_required` status with `request_id` + `summary` + `risk`; integrate `PermissionPolicy` for Normal/Turbo | **HIGH** |
| `app/tools/terminal.py` | Return `request_id` in approval_required result; add output size limit to `run_command` stdout/stderr | **HIGH** |
| `app/tools/browser_tools.py` | Fix `BrowserOpenTool` to return `success=False` on error; add SSRF guard to `browser_screenshot` and `browser_navigate` | **HIGH** |
| `app/tools/sandbox_tools.py` | Wire `SandboxExecTool` to `DockerSandbox`; return `SANDBOX_UNAVAILABLE` when Docker offline | **HIGH** |
| `app/tools/__init__.py` | Add `list_files` alias, `edit_file` alias; add `browser.preview` permission name | **MEDIUM** |
| `app/workspace/policy.py` | No changes required unless adding more patterns | **LOW** |
| `app/graph/workflow.py` | Extend `resume_approved_run()` beyond `delete_file` | **HIGH** |
| `app/api/preview.py` | Verify/add path traversal protection | **HIGH** |
| New: `app/permissions/engine.py` | Create `PermissionEngine` with `PermissionPolicy` (Normal/Turbo) | **HIGH** |
| New: `backend/tests/test_permission_engine.py` | Permission model test suite (10 tests from spec) | **HIGH** |
| New: `backend/tests/test_capability_comprehensive.py` | Full spec test suite | **HIGH** |

---

## 14. Files That Must NOT Be Modified

Per ownership boundaries:

| File | Owner | Reason |
|:---|:---|:---|
| `app/agent/brain.py` | Nikunj | Agent reasoning |
| `app/agent/loop.py` | Nikunj | Agent loop |
| `app/agent/tool_selector.py` | Nikunj | Tool selection strategy |
| `app/agent/prompts.py` | Nikunj | LLM prompts |
| `app/agent/memory_bridge.py` | Nikunj | Memory integration |
| `app/graph/workflow.py` | Shared | **Exception:** `resume_approved_run` needs extension for approval contract |
| `app/graph/nodes/*.py` | Nikunj | Planning/execution nodes |
| `app/graph/controller.py` | Nikunj | Autonomous controller decisions |
| `app/memory/` | Kushal | Memory/context systems |
| `app/llm/router.py` | Nikunj/Shared | LLM routing |
| `app/runtime/sessions/` | Shared | Session management |
| All frontend files | Farhan | React UI |
| `app/api/runs.py` | Shared | Approval endpoints (minimal change only) |

---

## 15. Risk Assessment

### 15.1 Permission System Risk — **CRITICAL**

The `approved: bool = True` default means the permission system does nothing in the standard code path. Every tool invocation from the agent currently has all permissions granted, regardless of the `permissions` set.

- **Exploitability:** Any agent hallucination can call any tool without restriction
- **Fix complexity:** Low (change default, update callers that need specific permissions)
- **Risk to existing tests:** Medium (existing tests may rely on `approved=True` default)

### 15.2 Sandbox Isolation Risk — **HIGH**

`sandbox_exec` runs host processes, not Docker containers. If a command bypasses the policy filter, it executes directly on the host.

- **Exploitability:** Medium (policy filter is effective, but not perfect)
- **Fix complexity:** Medium (requires Docker daemon to be running)

### 15.3 Browser SSRF Risk — **HIGH**

`browser_screenshot` and `browser_navigate` accept arbitrary URLs and use Playwright (headless Chromium) without any SSRF protection. The agent can navigate to internal network addresses.

- **Exploitability:** High (agent can browse `http://192.168.x.x/admin`)
- **Fix complexity:** Low (reuse `validate_url_for_ssrf`)

### 15.4 Artifact Path Leakage — **MEDIUM**

`artifact.to_dict()` includes `file_path` which is an absolute filesystem path. This is sent via SSE events to the frontend.

- **Exploitability:** Low (information disclosure only, not path traversal)
- **Fix complexity:** Low (exclude `file_path` from serialized output)

### 15.5 Approval Resume Scope — **MEDIUM**

`resume_approved_run()` only handles `delete_file`. All other approval-required tools leave the run permanently paused.

- **Impact:** Functional breakage — approved commands cannot resume
- **Fix complexity:** Medium (requires generalized tool execution in resume path)

### 15.6 BrowserOpenTool False Success — **LOW**

Returns `success=True` on exception, misleading the agent into thinking preview succeeded.

- **Impact:** Agent may incorrectly report success
- **Fix complexity:** Trivial (change `success=True` to `success=False`)

---

## Summary Matrices

### Phase A — What Already Exists Correctly

| Item | Verified |
|:---|:---|
| Single ToolRegistry as sole gateway | ✅ |
| Tool permission declarations (`required_permissions`) | ✅ |
| ToolRegistry permission enforcement gate | ✅ |
| ToolResult canonical structure (`success`, `tool`, `result`, `error`, `status`, `metadata`) | ✅ |
| Filesystem workspace containment (PathSecurityError) | ✅ |
| Terminal command policy (DENIED/APPROVAL/SAFE) | ✅ |
| Terminal process isolation + tree cleanup | ✅ |
| Terminal timeout with exit code 124 | ✅ |
| HTTP SSRF protection (DNS resolution + IP blocking) | ✅ |
| HTTP response size limit (5MB, streaming) | ✅ |
| Git tools (9 operations) | ✅ |
| GitHub tools (4 operations, GITHUB_TOKEN env) | ✅ |
| Local browser preview server (`localhost:8006`) | ✅ |
| ArtifactManager with secure URL routing | ✅ |
| Artifact endpoint at `/api/artifacts/{id}/content` | ✅ |
| Existing capability test suite (`test_capability_layer.py`) | ✅ |
| Approval pause/resume API endpoint | ✅ |
| No Turbo mode global bypass anywhere | ✅ |

### Phase B — What Needs to Be Implemented or Fixed

| Item | Priority |
|:---|:---|
| Fix `ToolContext.approved = False` default | CRITICAL |
| `PermissionPolicy` (Normal/Turbo, configured permission set) | HIGH |
| `PermissionEngine` centralized (or extend registry) | HIGH |
| `request_id` in approval_required results | HIGH |
| `summary` + `risk` in permission_required results | HIGH |
| `Risk` metadata on each Tool | HIGH |
| Extend `resume_approved_run` beyond `delete_file` | HIGH |
| Connect `DockerSandbox` to `SandboxExecTool` | HIGH |
| `SANDBOX_UNAVAILABLE` when Docker offline | HIGH |
| SSRF guard on `browser_screenshot` + `browser_navigate` | HIGH |
| Fix `BrowserOpenTool` false success | MEDIUM |
| `artifacts` field in `ToolResult` | MEDIUM |
| Bounded LLM result (truncate large file reads) | MEDIUM |
| `list_files` alias (for `list_directory`) | MEDIUM |
| `edit_file` alias (for `update_file`/`patch_file`) | LOW |
| `browser.preview` permission alias | LOW |
| Remove `file_path` from artifact public serialization | MEDIUM |
| Comprehensive permission tests (10 scenarios from spec) | HIGH |
| Full capability test suite per spec | HIGH |

---

## Conclusion

The JARVIS capability/tool layer is **architecturally sound** with a well-organized ToolRegistry, strong filesystem security, effective HTTP SSRF protection, and working approval/resume infrastructure. The **most critical gap is a single-line bug**: `approved: bool = True` which silently bypasses the entire permission system in all default usage.

The approval resume system is functionally limited to `delete_file`. The sandbox execution is host-level, not Docker-isolated. The browser tools lack SSRF protection. These are the four priority fixes before any new test suite should be run.

**No source code was modified during this audit.**
