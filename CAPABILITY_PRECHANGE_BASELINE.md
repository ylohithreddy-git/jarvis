# CAPABILITY_PRECHANGE_BASELINE.md

**Date:** September 29, 2026  
**Phase:** A — Pre-Change Baseline  
**Environment:** Python 3.13.2, Windows 11 AMD64  
**Test Runner:** pytest 9.1.1  

---

## Test Command

```
python -m pytest tests/test_capability_layer.py tests/test_workspace_security.py tests/test_tool_action_system.py -v --tb=short
```

---

## Results

**Total:** 32  
**PASS:** 30  
**FAIL:** 2  
**BLOCKED:** 0  
**NOT_TESTED:** 0  

---

## Failures (2)

### FAIL 1 — `test_permission_denied_when_permission_missing`

```
tests/test_capability_layer.py::TestCapabilityLayer::test_permission_denied_when_permission_missing
AssertionError: True is not false
```

**Root cause:** `ToolContext.approved = True` by default. `has_permission()` returns `True` immediately when `approved is True`, bypassing permission set evaluation. Writing to a `read_only_ctx` (permissions={"filesystem.read"}) succeeds because `approved=True` grants everything.

### FAIL 2 — `test_destructive_operations_require_explicit_permissions`

```
tests/test_capability_layer.py::TestCapabilityLayer::test_destructive_operations_require_explicit_permissions
AssertionError: True is not false
```

**Root cause:** Same bug. `ToolContext(permissions={"filesystem.read","filesystem.write"})` still allows `terminal.execute` because `approved=True` bypasses permission check.

---

## Passing Tests (30)

| Test | File | Status |
|:---|:---|:---|
| test_browser_open_tool | test_capability_layer.py | PASS |
| test_filesystem_path_containment_security | test_capability_layer.py | PASS |
| test_filesystem_write_read_delete | test_capability_layer.py | PASS |
| test_git_status_tool | test_capability_layer.py | PASS |
| test_github_tools_registration | test_capability_layer.py | PASS |
| test_http_ssrf_allowed_via_trusted_context_policy | test_capability_layer.py | PASS |
| test_http_ssrf_blocked_destinations | test_capability_layer.py | PASS |
| test_http_streaming_response_size_limit | test_capability_layer.py | PASS |
| test_sandbox_inspect_tool | test_capability_layer.py | PASS |
| test_schema_validation_missing_required_argument | test_capability_layer.py | PASS |
| test_terminal_successful_execution | test_capability_layer.py | PASS |
| test_terminal_timeout_and_process_cleanup | test_capability_layer.py | PASS |
| test_tool_registry_registration_and_lookup | test_capability_layer.py | PASS |
| test_tool_registry_unknown_tool | test_capability_layer.py | PASS |
| test_absolute_outside_path | test_workspace_security.py | PASS |
| test_command_policy | test_workspace_security.py | PASS |
| test_dot_dot_traversal | test_workspace_security.py | PASS |
| test_file_operations_containment | test_workspace_security.py | PASS |
| test_nested_path | test_workspace_security.py | PASS |
| test_normal_relative_path | test_workspace_security.py | PASS |
| test_windows_path_traversal | test_workspace_security.py | PASS |
| test_1_list_directory | test_tool_action_system.py | PASS |
| test_2_read_file | test_tool_action_system.py | PASS |
| test_3_create_file | test_tool_action_system.py | PASS |
| test_4_update_file | test_tool_action_system.py | PASS |
| test_5_run_command | test_tool_action_system.py | PASS |
| test_6_security_outside_workspace_rejected | test_tool_action_system.py | PASS |
| test_7_tool_failure_structured | test_tool_action_system.py | PASS |
| test_8_agent_node_tool_execution | test_tool_action_system.py | PASS |
| test_9_existing_execute_tool_compatibility | test_tool_action_system.py | PASS |

---

## Key Pre-Change Observations

1. **Permission bypass confirmed:** `ToolContext.approved=True` bypasses entire permission set
2. **Filesystem security:** Path containment working correctly
3. **HTTP SSRF:** Private IP blocking working
4. **Terminal:** Timeout and process isolation working
5. **Terminal stdout/stderr:** No output size limits implemented
6. **Sandbox:** Inspects workspace but executes on host via RunCommandTool
7. **BrowserOpenTool:** Returns success=True even on connection failure
8. **ToolResult:** No `artifacts` field
9. **Artifact.to_dict():** No `file_path` — ALREADY SAFE (file_path excluded from to_dict)
10. **browser_screenshot / browser_navigate:** No SSRF protection
11. **SandboxExecTool:** Delegates to RunCommandTool — no Docker isolation
12. **Approval resume:** Hard-coded to delete_file only
13. **Normal/Turbo mode:** Not implemented
14. **PermissionEngine:** Not implemented — permission logic in ToolContext only
15. **Risk metadata:** Not on tools
16. **list_files alias:** Missing
17. **edit_file alias:** Missing
