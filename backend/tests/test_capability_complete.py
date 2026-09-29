"""
JARVIS Capability Layer — Comprehensive Test Suite
===================================================

Tests every gap identified in the Phase 0 audit and the full spec:

A. Registry
B. Permission — Normal Mode
C. Permission — Turbo Mode
D. Approval Request
E. Approval Security (replay, cross-run, expiry, argument tampering)
F. Filesystem (create, read, list, write, edit, delete, traversal)
G. Filesystem Aliases (list_files, edit_file)
H. Terminal (safe, policy, timeout, output bounded)
I. Browser Preview
J. Browser SSRF Protection
K. HTTP SSRF
L. Git
M. GitHub (BLOCKED when token absent)
N. Sandbox (SANDBOX_UNAVAILABLE when Docker offline)
O. Artifacts (registration, safe serialization, no file_path)
P. ToolResult contract (artifacts field, metadata, status)
Q. Bounded LLM Results
R. Risk Metadata
S. Cross-capability workflow (create → preview → artifact)
T. Agent/ToolRegistry contract (Brain coordination)
U. Permission Engine Unit Tests
V. Regression — existing tests pass

Test classification:
  PASS    = actual behavior verified
  FAIL    = expected behavior did not occur
  BLOCKED = external dependency/credential prevented test
  NOT_TESTED = not attempted
"""

import os
import sys
import json
import time
import tempfile
import shutil
import unittest
from typing import Optional
from unittest.mock import patch, MagicMock

# Ensure backend/ is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─────────────────────────────────────────────────────────────────────────────
# Test helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_registry():
    """Fresh registry per test to avoid state pollution."""
    from app.tools.registry import ToolRegistry
    from app.tools import _init_default_registry
    reg = ToolRegistry()
    _init_default_registry(reg)
    return reg


def make_ctx(permissions=None, approved=False, workspace_root=None, **kwargs):
    """Build a ToolContext for testing."""
    from app.tools.base import ToolContext
    ws_root = workspace_root or tempfile.mkdtemp(prefix="jarvis_test_")
    args = dict(
        approved=approved,
        workspace_root=ws_root,
        workspace_id="test",
        run_id="test-run-01",
        session_id="test-session-01",
        user_id="test-user",
    )
    if permissions is not None:
        args["permissions"] = permissions
    args.update(kwargs)
    return ToolContext(**args), ws_root


READ_ONLY_PERMS = {"filesystem.read", "git.read", "http.read"}
FULL_PERMS = {
    "filesystem.read", "filesystem.write", "filesystem.delete",
    "terminal.execute", "browser.execute", "browser.preview",
    "git.read", "git.write", "git.push",
    "github.read", "github.write",
    "http.read", "http.write",
    "sandbox.execute", "vision.analyze", "attachment.read",
}


# ─────────────────────────────────────────────────────────────────────────────
# A. Registry Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = get_registry()

    def test_A1_all_expected_tools_registered(self):
        """All 47+ expected tools must be registered."""
        names = {t.name for t in self.reg.list_tools()}
        expected = {
            "list_directory", "list_files", "read_file", "write_file",
            "create_file", "update_file", "delete_file", "move", "rename_file",
            "copy", "copy_file", "create_directory", "append_file", "patch_file",
            "edit_file", "get_file_info", "list_directory_tree", "diff_files",
            "search_files", "run_command", "exec", "http_get", "http_post",
            "git_status", "git_diff", "git_log", "git_add", "git_commit",
            "git_checkout", "git_create_branch", "git_pull", "git_push",
            "github_get_repo", "github_list_issues", "github_create_issue",
            "github_create_pr", "open_browser", "browser_screenshot",
            "browser_navigate", "sandbox_inspect", "sandbox_exec",
            "sandbox_reset", "analyze_image", "get_attachment_info",
        }
        missing = expected - names
        self.assertEqual(missing, set(), f"Missing tools: {missing}")

    def test_A2_list_files_alias_registered(self):
        tool = self.reg.get_tool("list_files")
        self.assertIsNotNone(tool, "list_files alias must be registered")

    def test_A3_edit_file_alias_registered(self):
        tool = self.reg.get_tool("edit_file")
        self.assertIsNotNone(tool, "edit_file alias must be registered")

    def test_A4_unknown_tool_returns_structured_error(self):
        from app.tools.base import ToolContext
        ctx = ToolContext()
        res = self.reg.execute("nonexistent_tool", {}, ctx)
        self.assertFalse(res.success)
        self.assertEqual(res.error["code"], "UNKNOWN_TOOL")

    def test_A5_schema_validation_missing_required(self):
        from app.tools.base import ToolContext
        ctx = ToolContext()
        res = self.reg.execute("read_file", {}, ctx)   # missing 'path'
        self.assertFalse(res.success)
        self.assertEqual(res.error["code"], "MISSING_REQUIRED_ARGUMENT")

    def test_A6_all_tools_have_risk_metadata(self):
        """Every registered tool must declare a risk level."""
        missing_risk = []
        for tool in self.reg.list_tools():
            risk = getattr(tool, "risk", None)
            if risk not in ("low", "medium", "high"):
                missing_risk.append(f"{tool.name}: risk={risk!r}")
        self.assertEqual(missing_risk, [], f"Tools missing risk: {missing_risk}")

    def test_A7_tool_definitions_include_risk(self):
        """get_tool_definitions() must return risk for every tool."""
        defs = self.reg.get_tool_definitions()
        bad = [d["name"] for d in defs if "risk" not in d]
        self.assertEqual(bad, [], f"Definitions missing risk: {bad}")

    def test_A8_all_tools_have_required_permissions(self):
        """Every tool must declare required_permissions (may be empty list)."""
        for tool in self.reg.list_tools():
            self.assertIsInstance(
                tool.required_permissions, list,
                f"Tool {tool.name} required_permissions must be a list"
            )


# ─────────────────────────────────────────────────────────────────────────────
# B. Permission — Normal Mode
# ─────────────────────────────────────────────────────────────────────────────

class TestPermissionNormalMode(unittest.TestCase):
    def setUp(self):
        self.reg = get_registry()

    def test_B1_missing_permission_blocks_execution(self):
        """filesystem.write blocked when permissions only contain filesystem.read."""
        ctx, tmp = make_ctx(permissions={"filesystem.read"})
        res = self.reg.execute("write_file", {"path": "test.txt", "content": "x"}, ctx)
        # must NOT create the file
        self.assertFalse(res.success, "write_file must fail without filesystem.write permission")
        self.assertEqual(res.status, "permission_required")
        self.assertIn("request_id", res.metadata, "Must include request_id")
        self.assertIn("permission", res.metadata)
        self.assertIn("risk", res.metadata)
        shutil.rmtree(tmp, ignore_errors=True)

    def test_B2_configured_permission_executes(self):
        """filesystem.write executes when permission is configured."""
        ctx, tmp = make_ctx(permissions={"filesystem.write"})
        path = os.path.join(tmp, "hello.txt")
        res = self.reg.execute("write_file", {"path": "hello.txt", "content": "hello"}, ctx)
        self.assertTrue(res.success, f"Should succeed with filesystem.write: {res.error}")
        shutil.rmtree(tmp, ignore_errors=True)

    def test_B3_missing_terminal_execute_blocks_run_command(self):
        """terminal.execute absent — run_command must not execute."""
        ctx, tmp = make_ctx(permissions={"filesystem.read"})
        res = self.reg.execute("run_command", {"command": "echo hi"}, ctx)
        self.assertFalse(res.success)
        self.assertEqual(res.status, "permission_required")
        # Verify no side effect (echo doesn't write files, but test structure)
        shutil.rmtree(tmp, ignore_errors=True)

    def test_B4_permission_required_includes_metadata(self):
        """permission_required result must have request_id, permission, summary, risk."""
        ctx, tmp = make_ctx(permissions=set())  # no permissions at all
        res = self.reg.execute("delete_file", {"path": "x.txt"}, ctx)
        self.assertFalse(res.success)
        self.assertEqual(res.status, "permission_required")
        self.assertIn("request_id", res.metadata)
        self.assertIn("permission", res.metadata)
        self.assertIn("summary", res.metadata)
        self.assertIn("risk", res.metadata)
        self.assertTrue(res.metadata["request_id"].startswith("perm_"))
        shutil.rmtree(tmp, ignore_errors=True)

    def test_B5_approval_does_not_grant_unrelated_permissions(self):
        """approved=True on a context with limited permissions should not grant everything."""
        ctx, tmp = make_ctx(permissions={"filesystem.read"}, approved=True)
        # approved=True means this action was user-approved, but terminal.execute is still not in set
        res = self.reg.execute("run_command", {"command": "echo hi"}, ctx)
        self.assertFalse(res.success,
            "approved=True must not grant terminal.execute when not in permission set")
        shutil.rmtree(tmp, ignore_errors=True)

    def test_B6_denied_action_produces_no_side_effect(self):
        """Verify that a denied delete does NOT delete the file."""
        ctx, tmp = make_ctx(permissions={"filesystem.read"})  # no delete permission
        # Create a test file
        test_file = os.path.join(tmp, "precious.txt")
        with open(test_file, "w") as f:
            f.write("important data")
        res = self.reg.execute("delete_file", {"path": "precious.txt"}, ctx)
        self.assertFalse(res.success)
        self.assertTrue(os.path.exists(test_file), "File must still exist after denied delete")
        shutil.rmtree(tmp, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# C. Permission — Turbo Mode
# ─────────────────────────────────────────────────────────────────────────────

class TestPermissionTurboMode(unittest.TestCase):
    def test_C1_turbo_mode_policy_auto_allows_configured_permission(self):
        """PermissionPolicy(TURBO) with filesystem.write → has_permission returns True."""
        from app.permissions.engine import PermissionPolicy, PermissionMode
        policy = PermissionPolicy(
            mode=PermissionMode.TURBO,
            permissions={"filesystem.write", "filesystem.read"}
        )
        self.assertTrue(policy.has_permission("filesystem.write"))
        self.assertTrue(policy.has_permission("filesystem.read"))

    def test_C2_turbo_mode_does_not_allow_unconfigured_permission(self):
        """Turbo mode still blocks permissions not in the configured set."""
        from app.permissions.engine import PermissionPolicy, PermissionMode
        policy = PermissionPolicy(
            mode=PermissionMode.TURBO,
            permissions={"filesystem.read"}  # no terminal.execute
        )
        self.assertFalse(policy.has_permission("terminal.execute"),
            "Turbo must NOT allow terminal.execute when not configured")

    def test_C3_turbo_mode_wildcard_grants_category(self):
        """filesystem.* should grant filesystem.read, filesystem.write, filesystem.delete."""
        from app.permissions.engine import PermissionPolicy, PermissionMode
        policy = PermissionPolicy(
            mode=PermissionMode.TURBO,
            permissions={"filesystem.*"}
        )
        self.assertTrue(policy.has_permission("filesystem.read"))
        self.assertTrue(policy.has_permission("filesystem.write"))
        self.assertTrue(policy.has_permission("filesystem.delete"))
        self.assertFalse(policy.has_permission("terminal.execute"))

    def test_C4_browser_preview_alias_works_in_policy(self):
        """browser.preview and browser.execute are aliases."""
        from app.permissions.engine import PermissionPolicy, PermissionMode
        policy = PermissionPolicy(
            mode=PermissionMode.NORMAL,
            permissions={"browser.preview"}
        ).normalize()
        self.assertTrue(policy.has_permission("browser.execute"))
        self.assertTrue(policy.has_permission("browser.preview"))

    def test_C5_tool_context_has_permission_does_not_check_approved(self):
        """has_permission() must evaluate the permission set, not the approved flag."""
        from app.tools.base import ToolContext
        # With approved=True but no permissions
        ctx_approved = ToolContext(approved=True, permissions=set())
        ctx_full = ToolContext(approved=False)  # default full permissions

        # approved=True with empty permissions should NOT grant filesystem.read
        self.assertFalse(ctx_approved.has_permission("filesystem.read"),
            "approved=True with empty permissions must NOT grant filesystem.read")

        # approved=False with full default permissions should grant filesystem.read
        self.assertTrue(ctx_full.has_permission("filesystem.read"),
            "Default full permissions must grant filesystem.read regardless of approved flag")


# ─────────────────────────────────────────────────────────────────────────────
# D. Approval Request — PermissionEngine Unit Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPermissionEngine(unittest.TestCase):
    def setUp(self):
        from app.permissions.engine import PermissionEngine, PermissionPolicy, PermissionMode
        self.engine = PermissionEngine()
        self.policy_limited = PermissionPolicy(
            mode=PermissionMode.NORMAL,
            permissions={"filesystem.read"}
        )
        self.policy_full = PermissionPolicy(
            mode=PermissionMode.NORMAL,
            permissions={"filesystem.read", "filesystem.write", "filesystem.delete"}
        )

    def test_D1_evaluate_returns_none_when_permission_granted(self):
        """evaluate() returns None (approved) when policy has the permission."""
        result = self.engine.evaluate(
            tool_name="read_file",
            required_permission="filesystem.read",
            policy=self.policy_full,
            arguments={"path": "readme.md"},
            run_id="run-01"
        )
        self.assertIsNone(result, "evaluate() should return None when permission is configured")

    def test_D2_evaluate_returns_approval_request_when_missing(self):
        """evaluate() returns ApprovalRequest when policy lacks the permission."""
        from app.permissions.engine import ApprovalRequest
        result = self.engine.evaluate(
            tool_name="delete_file",
            required_permission="filesystem.delete",
            policy=self.policy_limited,  # only has filesystem.read
            arguments={"path": "todo.txt"},
            run_id="run-01"
        )
        self.assertIsNotNone(result, "Should return ApprovalRequest")
        self.assertIsInstance(result, ApprovalRequest)
        self.assertEqual(result.tool, "delete_file")
        self.assertEqual(result.permission, "filesystem.delete")
        self.assertTrue(result.request_id.startswith("perm_"))

    def test_D3_approval_request_has_expiry(self):
        """Approval requests have an expiry timestamp in the future."""
        from app.permissions.engine import ApprovalRequest
        req = self.engine.evaluate(
            tool_name="write_file",
            required_permission="filesystem.write",
            policy=self.policy_limited,
            arguments={"path": "a.txt", "content": "hi"},
            run_id="run-02"
        )
        self.assertIsNotNone(req)
        self.assertGreater(req.expires_at, time.time(), "expires_at must be in the future")

    def test_D4_approve_marks_request_approved(self):
        """approve() transitions status to APPROVED."""
        from app.permissions.engine import ApprovalStatus
        req = self.engine.evaluate(
            tool_name="delete_file",
            required_permission="filesystem.delete",
            policy=self.policy_limited,
            arguments={"path": "tmp.txt"},
            run_id="run-03"
        )
        self.assertIsNotNone(req)
        approved = self.engine.approve(req.request_id, run_id="run-03")
        self.assertEqual(approved.status, ApprovalStatus.APPROVED)

    def test_D5_deny_marks_request_denied(self):
        """deny() transitions status to DENIED."""
        from app.permissions.engine import ApprovalStatus
        req = self.engine.evaluate(
            tool_name="delete_file",
            required_permission="filesystem.delete",
            policy=self.policy_limited,
            arguments={"path": "tmp.txt"},
            run_id="run-04"
        )
        self.assertIsNotNone(req)
        denied = self.engine.deny(req.request_id, run_id="run-04")
        self.assertEqual(denied.status, ApprovalStatus.DENIED)


# ─────────────────────────────────────────────────────────────────────────────
# E. Approval Security
# ─────────────────────────────────────────────────────────────────────────────

class TestApprovalSecurity(unittest.TestCase):
    def setUp(self):
        from app.permissions.engine import PermissionEngine, PermissionPolicy, PermissionMode
        self.engine = PermissionEngine()
        self.limited_policy = PermissionPolicy(
            mode=PermissionMode.NORMAL,
            permissions={"filesystem.read"}
        )

    def _make_approval_request(self, tool="delete_file", run_id="run-A", args=None):
        args = args or {"path": "test.txt"}
        return self.engine.evaluate(
            tool_name=tool,
            required_permission="filesystem.delete",
            policy=self.limited_policy,
            arguments=args,
            run_id=run_id
        )

    def test_E1_invalid_request_id_rejected(self):
        """Unknown request_id must raise ValueError."""
        with self.assertRaises(ValueError) as cm:
            self.engine.validate_resume("perm_nonexistent", "run-A", "delete_file", {"path": "x.txt"})
        self.assertIn("PERMISSION_REQUEST_INVALID", str(cm.exception))

    def test_E2_cross_run_approval_rejected(self):
        """Approval from run-A must not work for run-B."""
        req = self._make_approval_request(run_id="run-A")
        self.engine.approve(req.request_id, run_id="run-A")
        with self.assertRaises(ValueError) as cm:
            self.engine.validate_resume(req.request_id, "run-B", "delete_file", {"path": "test.txt"})
        self.assertIn("PERMISSION_REQUEST_INVALID", str(cm.exception))

    def test_E3_tool_substitution_rejected(self):
        """Approved delete_file request must not resume as run_command."""
        req = self._make_approval_request(run_id="run-C")
        self.engine.approve(req.request_id, run_id="run-C")
        with self.assertRaises(ValueError) as cm:
            self.engine.validate_resume(req.request_id, "run-C", "run_command", {"path": "test.txt"})
        self.assertIn("PERMISSION_REQUEST_INVALID", str(cm.exception))
        self.assertIn("Tool mismatch", str(cm.exception))

    def test_E4_argument_tampering_rejected(self):
        """Changing arguments after approval must be rejected."""
        req = self._make_approval_request(run_id="run-D", args={"path": "safe.txt"})
        self.engine.approve(req.request_id, run_id="run-D")
        with self.assertRaises(ValueError) as cm:
            # Different arguments than what was approved
            self.engine.validate_resume(req.request_id, "run-D", "delete_file", {"path": "system32.dll"})
        self.assertIn("PERMISSION_REQUEST_INVALID", str(cm.exception))
        self.assertIn("tampering", str(cm.exception))

    def test_E5_expired_request_rejected(self):
        """Expired approval request must be rejected with PERMISSION_REQUEST_EXPIRED."""
        from app.permissions.engine import ApprovalStatus
        req = self._make_approval_request(run_id="run-E")
        # Manually expire
        req.expires_at = time.time() - 1
        self.engine._pending_approvals[req.request_id] = req
        with self.assertRaises(ValueError) as cm:
            self.engine.validate_resume(req.request_id, "run-E", "delete_file", {"path": "test.txt"})
        self.assertIn("PERMISSION_REQUEST_EXPIRED", str(cm.exception))
        self.assertEqual(req.status, ApprovalStatus.EXPIRED)

    def test_E6_denied_request_cannot_resume(self):
        """Denied request must not be resumable even if request_id is known."""
        req = self._make_approval_request(run_id="run-F")
        self.engine.deny(req.request_id, run_id="run-F")
        with self.assertRaises(ValueError) as cm:
            self.engine.validate_resume(req.request_id, "run-F", "delete_file", {"path": "test.txt"})
        self.assertIn("PERMISSION_DENIED", str(cm.exception))

    def test_E7_to_dict_does_not_expose_arguments(self):
        """ApprovalRequest.to_dict() must NOT include raw original_arguments."""
        req = self._make_approval_request(run_id="run-G")
        d = req.to_dict()
        self.assertNotIn("original_arguments", d, "Raw arguments must not be in public dict")
        self.assertNotIn("arguments_hash", d, "Hash must not be in public dict")


# ─────────────────────────────────────────────────────────────────────────────
# F. Filesystem Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFilesystem(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jarvis_fs_test_")
        self.reg = get_registry()
        self.ctx, _ = make_ctx(permissions=FULL_PERMS, workspace_root=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_F1_create_and_read_file(self):
        res = self.reg.execute("create_file", {"path": "hello.txt", "content": "Hello World"}, self.ctx)
        self.assertTrue(res.success, f"create_file failed: {res.error}")
        full = os.path.join(self.tmp, "hello.txt")
        self.assertTrue(os.path.exists(full))
        self.assertEqual(open(full).read(), "Hello World")

    def test_F2_list_directory(self):
        open(os.path.join(self.tmp, "a.txt"), "w").write("a")
        open(os.path.join(self.tmp, "b.txt"), "w").write("b")
        res = self.reg.execute("list_directory", {"path": "."}, self.ctx)
        self.assertTrue(res.success, f"list_directory failed: {res.error}")

    def test_F3_write_and_update_file(self):
        self.reg.execute("write_file", {"path": "data.txt", "content": "v1"}, self.ctx)
        res = self.reg.execute("update_file", {"path": "data.txt", "content": "v2"}, self.ctx)
        self.assertTrue(res.success)
        self.assertEqual(open(os.path.join(self.tmp, "data.txt")).read(), "v2")

    def test_F4_delete_file(self):
        open(os.path.join(self.tmp, "del.txt"), "w").write("bye")
        res = self.reg.execute("delete_file", {"path": "del.txt"}, self.ctx)
        self.assertTrue(res.success, f"delete_file failed: {res.error}")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "del.txt")))

    def test_F5_path_traversal_blocked(self):
        """.. traversal must be blocked."""
        res = self.reg.execute("read_file", {"path": "../../etc/passwd"}, self.ctx)
        self.assertFalse(res.success)
        self.assertIn("PATH_SECURITY_ERROR", str(res.error))

    def test_F6_absolute_outside_path_blocked(self):
        """Absolute path outside workspace must be blocked."""
        res = self.reg.execute("read_file", {"path": "C:\\Windows\\System32\\cmd.exe"}, self.ctx)
        self.assertFalse(res.success)

    def test_F7_create_directory(self):
        res = self.reg.execute("create_directory", {"path": "subdir/nested"}, self.ctx)
        self.assertTrue(res.success)
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, "subdir", "nested")))

    def test_F8_read_nonexistent_file(self):
        res = self.reg.execute("read_file", {"path": "ghost.txt"}, self.ctx)
        self.assertFalse(res.success)

    def test_F9_append_file(self):
        open(os.path.join(self.tmp, "log.txt"), "w").write("line1\n")
        res = self.reg.execute("append_file", {"path": "log.txt", "content": "line2\n"}, self.ctx)
        self.assertTrue(res.success)
        content = open(os.path.join(self.tmp, "log.txt")).read()
        self.assertIn("line1", content)
        self.assertIn("line2", content)


# ─────────────────────────────────────────────────────────────────────────────
# G. Filesystem Aliases
# ─────────────────────────────────────────────────────────────────────────────

class TestFilesystemAliases(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jarvis_alias_test_")
        self.reg = get_registry()
        self.ctx, _ = make_ctx(permissions=FULL_PERMS, workspace_root=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_G1_list_files_alias_executes(self):
        """list_files must execute identically to list_directory."""
        open(os.path.join(self.tmp, "a.py"), "w").write("pass")
        res = self.reg.execute("list_files", {"path": "."}, self.ctx)
        self.assertTrue(res.success, f"list_files failed: {res.error}")

    def test_G2_edit_file_alias_executes(self):
        """edit_file must find-and-replace in a file."""
        path = os.path.join(self.tmp, "edit_me.txt")
        with open(path, "w") as f:
            f.write("hello world")
        res = self.reg.execute("edit_file", {
            "path": "edit_me.txt", "find": "world", "replace": "JARVIS"
        }, self.ctx)
        self.assertTrue(res.success, f"edit_file failed: {res.error}")
        self.assertEqual(open(path).read(), "hello JARVIS")

    def test_G3_list_files_has_same_permissions_as_list_directory(self):
        """list_files must require filesystem.read, not be open."""
        ctx_noread, _ = make_ctx(permissions=set(), workspace_root=self.tmp)
        res = self.reg.execute("list_files", {"path": "."}, ctx_noread)
        self.assertFalse(res.success, "list_files must fail without filesystem.read")


# ─────────────────────────────────────────────────────────────────────────────
# H. Terminal Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTerminal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jarvis_term_test_")
        self.reg = get_registry()
        self.ctx, _ = make_ctx(permissions=FULL_PERMS, workspace_root=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_H1_safe_command_executes(self):
        res = self.reg.execute("run_command", {"command": "echo hello"}, self.ctx)
        self.assertTrue(res.success, f"echo failed: {res.error}")
        result_data = res.result or res.data or {}
        stdout = result_data.get("stdout", "")
        self.assertIn("hello", stdout)

    def test_H2_permission_missing_blocks_command(self):
        ctx_noperm, _ = make_ctx(permissions={"filesystem.read"}, workspace_root=self.tmp)
        res = self.reg.execute("run_command", {"command": "echo hi"}, ctx_noperm)
        self.assertFalse(res.success)
        self.assertEqual(res.status, "permission_required")

    def test_H3_denied_command_blocked_by_policy(self):
        """DENIED commands must not execute regardless of permission."""
        # rm -rf is in DENIED_PATTERNS
        res = self.reg.execute("run_command", {"command": "rm -rf /"}, self.ctx)
        self.assertFalse(res.success)

    def test_H4_timeout_terminates_process(self):
        """Long-running commands must be terminated by timeout."""
        res = self.reg.execute("run_command", {"command": "python -c \"import time; time.sleep(60)\""}, self.ctx)
        # Should fail with timeout
        self.assertFalse(res.success)
        result_data = res.result or res.data or {}
        self.assertTrue(
            res.error is not None or result_data.get("exit_code", 0) != 0,
            "Timed-out command should fail"
        )

    def test_H5_output_is_bounded(self):
        """Large terminal output must be bounded in agent-facing result."""
        # Generate a large output
        big_cmd = "python -c \"print('X' * 10000)\""
        res = self.reg.execute("run_command", {"command": big_cmd}, self.ctx)
        # Result may succeed or fail but if stdout present, check it's bounded
        if res.success and res.result:
            stdout = res.result.get("stdout", "")
            self.assertLessEqual(len(stdout), 5000, "stdout must be bounded for agent-facing result")


# ─────────────────────────────────────────────────────────────────────────────
# I. Browser Preview
# ─────────────────────────────────────────────────────────────────────────────

class TestBrowserPreview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jarvis_browser_test_")
        self.reg = get_registry()
        self.ctx, _ = make_ctx(permissions=FULL_PERMS, workspace_root=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_I1_browser_open_returns_false_when_server_down(self):
        """open_browser must return success=False when preview server is unreachable."""
        res = self.reg.execute("open_browser", {"path": "index.html"}, self.ctx)
        # Preview server is not running in test env
        self.assertFalse(res.success, "open_browser must return success=False when server is down")
        self.assertEqual(res.error["code"], "PREVIEW_UNAVAILABLE")

    def test_I2_browser_open_traversal_blocked(self):
        """Path traversal in preview path must be blocked."""
        res = self.reg.execute("open_browser", {"path": "../../etc/passwd"}, self.ctx)
        self.assertFalse(res.success)
        self.assertEqual(res.error["code"], "PATH_SECURITY_ERROR")


# ─────────────────────────────────────────────────────────────────────────────
# J. Browser SSRF Protection
# ─────────────────────────────────────────────────────────────────────────────

class TestBrowserSSRF(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jarvis_bssrf_test_")
        self.reg = get_registry()
        self.ctx, _ = make_ctx(permissions=FULL_PERMS, workspace_root=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _screenshot_blocked(self, url: str) -> bool:
        res = self.reg.execute("browser_screenshot", {"url": url}, self.ctx)
        return not res.success and res.error.get("code") == "SSRF_BLOCKED"

    def _navigate_blocked(self, url: str) -> bool:
        res = self.reg.execute("browser_navigate", {"url": url}, self.ctx)
        return not res.success and res.error.get("code") == "SSRF_BLOCKED"

    def test_J1_screenshot_blocks_private_ip(self):
        self.assertTrue(self._screenshot_blocked("http://192.168.1.1/secret"))

    def test_J2_screenshot_blocks_loopback(self):
        self.assertTrue(self._screenshot_blocked("http://127.0.0.1:8080/admin"))

    def test_J3_screenshot_blocks_cloud_metadata(self):
        self.assertTrue(self._screenshot_blocked("http://169.254.169.254/latest/meta-data/"))

    def test_J4_navigate_blocks_private_ip(self):
        self.assertTrue(self._navigate_blocked("http://10.0.0.1/internal"))

    def test_J5_navigate_blocks_loopback(self):
        self.assertTrue(self._navigate_blocked("http://127.0.0.1:22/"))

    def test_J6_navigate_blocks_cloud_metadata(self):
        self.assertTrue(self._navigate_blocked("http://169.254.169.254/"))

    def test_J7_preview_server_allowed_for_screenshot(self):
        """localhost:8006 (preview server) should NOT be SSRF-blocked for screenshot."""
        from app.tools.browser_tools import validate_browser_url
        is_valid, err = validate_browser_url("http://localhost:8006/api/preview/index.html", allow_local_preview=True)
        self.assertTrue(is_valid, f"Preview server URL should be allowed: {err}")

    def test_J8_arbitrary_localhost_blocked(self):
        """localhost on non-preview ports must be blocked."""
        from app.tools.browser_tools import validate_browser_url
        is_valid, err = validate_browser_url("http://localhost:3000/admin", allow_local_preview=False)
        self.assertFalse(is_valid, "Arbitrary localhost must be blocked")


# ─────────────────────────────────────────────────────────────────────────────
# K. HTTP SSRF
# ─────────────────────────────────────────────────────────────────────────────

class TestHttpSSRF(unittest.TestCase):
    def setUp(self):
        self.reg = get_registry()
        self.tmp = tempfile.mkdtemp()
        self.ctx, _ = make_ctx(permissions=FULL_PERMS, workspace_root=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_K1_private_ip_blocked(self):
        from app.tools.http_tools import validate_url_for_ssrf
        ok, msg = validate_url_for_ssrf("http://192.168.0.1/secrets", allow_private=False)
        self.assertFalse(ok)

    def test_K2_loopback_blocked(self):
        from app.tools.http_tools import validate_url_for_ssrf
        ok, msg = validate_url_for_ssrf("http://127.0.0.1:5000/", allow_private=False)
        self.assertFalse(ok)

    def test_K3_cloud_metadata_blocked(self):
        from app.tools.http_tools import validate_url_for_ssrf
        ok, msg = validate_url_for_ssrf("http://169.254.169.254/", allow_private=False)
        self.assertFalse(ok)

    def test_K4_http_get_blocked_ssrf(self):
        res = self.reg.execute("http_get", {"url": "http://192.168.1.100/data"}, self.ctx)
        self.assertFalse(res.success)

    def test_K5_http_post_blocked_ssrf(self):
        res = self.reg.execute("http_post", {"url": "http://10.0.0.1/endpoint", "data": "{}"}, self.ctx)
        self.assertFalse(res.success)


# ─────────────────────────────────────────────────────────────────────────────
# L. Git Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jarvis_git_test_")
        self.reg = get_registry()
        self.ctx, _ = make_ctx(permissions=FULL_PERMS, workspace_root=self.tmp)
        # Initialize a git repo
        import subprocess
        subprocess.run(["git", "init", self.tmp], capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@jarvis.test"], capture_output=True, cwd=self.tmp)
        subprocess.run(["git", "config", "user.name", "Jarvis Test"], capture_output=True, cwd=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_L1_git_status(self):
        res = self.reg.execute("git_status", {}, self.ctx)
        self.assertTrue(res.success, f"git_status failed: {res.error}")

    def test_L2_git_status_blocked_without_permission(self):
        ctx_noperm, _ = make_ctx(permissions={"filesystem.read"}, workspace_root=self.tmp)
        res = self.reg.execute("git_status", {}, ctx_noperm)
        self.assertFalse(res.success)
        self.assertEqual(res.status, "permission_required")

    def test_L3_git_log_on_empty_repo(self):
        res = self.reg.execute("git_log", {}, self.ctx)
        # May succeed with empty log or fail gracefully — not crash
        self.assertIsNotNone(res)

    def test_L4_git_add_and_commit(self):
        # Create a file and commit
        with open(os.path.join(self.tmp, "readme.txt"), "w") as f:
            f.write("readme")
        add_res = self.reg.execute("git_add", {"files": ["readme.txt"]}, self.ctx)
        self.assertTrue(add_res.success, f"git_add failed: {add_res.error}")
        commit_res = self.reg.execute("git_commit", {"message": "Initial commit"}, self.ctx)
        self.assertTrue(commit_res.success, f"git_commit failed: {commit_res.error}")


# ─────────────────────────────────────────────────────────────────────────────
# M. GitHub Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGitHub(unittest.TestCase):
    def setUp(self):
        self.reg = get_registry()
        self.tmp = tempfile.mkdtemp()
        self.ctx, _ = make_ctx(permissions=FULL_PERMS, workspace_root=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    @unittest.skipUnless(os.getenv("GITHUB_TOKEN"), "BLOCKED: GITHUB_TOKEN not set")
    def test_M1_github_get_repo(self):
        """BLOCKED unless GITHUB_TOKEN configured."""
        repo = os.getenv("GITHUB_REPO", "octocat/Hello-World")
        res = self.reg.execute("github_get_repo", {"repo": repo}, self.ctx)
        self.assertTrue(res.success)

    def test_M2_github_tools_registered(self):
        for name in ["github_get_repo", "github_list_issues", "github_create_issue", "github_create_pr"]:
            self.assertIsNotNone(self.reg.get_tool(name), f"{name} must be registered")

    def test_M3_github_create_issue_blocked_without_token(self):
        """Without GITHUB_TOKEN, create_issue must fail gracefully."""
        if os.getenv("GITHUB_TOKEN"):
            self.skipTest("GITHUB_TOKEN is set, skipping no-token test")
        res = self.reg.execute("github_create_issue", {
            "repo": "owner/repo", "title": "test", "body": "body"
        }, self.ctx)
        # Must fail gracefully, not crash
        self.assertFalse(res.success)


# ─────────────────────────────────────────────────────────────────────────────
# N. Sandbox Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSandbox(unittest.TestCase):
    def setUp(self):
        self.reg = get_registry()
        self.tmp = tempfile.mkdtemp()
        self.ctx, _ = make_ctx(permissions=FULL_PERMS, workspace_root=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_N1_sandbox_inspect_executes(self):
        res = self.reg.execute("sandbox_inspect", {}, self.ctx)
        self.assertTrue(res.success, f"sandbox_inspect failed: {res.error}")
        self.assertIn("docker_available", (res.result or {}))

    def test_N2_sandbox_exec_returns_unavailable_when_docker_down(self):
        """When Docker is offline, sandbox_exec must return SANDBOX_UNAVAILABLE."""
        import docker
        try:
            client = docker.from_env()
            client.ping()
            self.skipTest("BLOCKED: Docker is available — sandbox would actually execute")
        except Exception:
            pass  # Docker is offline — run the test
        res = self.reg.execute("sandbox_exec", {"command": "print('hello')"}, self.ctx)
        self.assertFalse(res.success, "sandbox_exec must fail when Docker is offline")
        self.assertEqual(res.error["code"], "SANDBOX_UNAVAILABLE",
            f"Must return SANDBOX_UNAVAILABLE, got: {res.error}")
        self.assertEqual(res.status, "blocked")

    def test_N3_sandbox_exec_does_not_fall_back_to_host(self):
        """sandbox_exec must NEVER fall back to host subprocess."""
        import docker
        try:
            docker.from_env().ping()
            self.skipTest("BLOCKED: Docker is available")
        except Exception:
            pass
        # If we get here, Docker is offline
        # Create a sentinel file — if sandbox falls back to host, it might succeed
        res = self.reg.execute("sandbox_exec", {"command": "echo 'host_bypass'"}, self.ctx)
        self.assertFalse(res.success, "Must not execute on host when Docker is offline")
        # Most importantly: must be SANDBOX_UNAVAILABLE, not a success
        if res.success:
            self.fail("CRITICAL: sandbox_exec succeeded on host — host fallback detected")

    def test_N4_sandbox_exec_requires_permission(self):
        ctx_noperm, _ = make_ctx(permissions={"filesystem.read"}, workspace_root=self.tmp)
        res = self.reg.execute("sandbox_exec", {"command": "echo hi"}, ctx_noperm)
        self.assertFalse(res.success)
        self.assertEqual(res.status, "permission_required")


# ─────────────────────────────────────────────────────────────────────────────
# O. Artifact Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestArtifacts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jarvis_artifact_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_O1_register_artifact(self):
        """Artifact registration must return valid artifact with ID."""
        from app.artifacts.manager import ArtifactManager
        mgr = ArtifactManager()
        test_file = os.path.join(self.tmp, "test.png")
        with open(test_file, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        artifact = mgr.register_artifact(test_file, source_tool="test")
        self.assertTrue(artifact.artifact_id.startswith("art_"))
        self.assertEqual(artifact.filename, "test.png")
        self.assertGreater(artifact.size, 0)

    def test_O2_to_dict_does_not_contain_file_path(self):
        """Artifact.to_dict() must NOT expose file_path to prevent path leakage."""
        from app.artifacts.manager import ArtifactManager
        mgr = ArtifactManager()
        test_file = os.path.join(self.tmp, "data.html")
        with open(test_file, "w") as f:
            f.write("<html>test</html>")
        artifact = mgr.register_artifact(test_file, source_tool="test")
        d = artifact.to_dict()
        self.assertNotIn("file_path", d, "file_path MUST NOT appear in public dict")

    def test_O3_artifact_has_secure_url(self):
        """Artifact URL must be a relative path, not a filesystem path."""
        from app.artifacts.manager import ArtifactManager
        mgr = ArtifactManager()
        test_file = os.path.join(self.tmp, "output.json")
        with open(test_file, "w") as f:
            json.dump({"result": 42}, f)
        artifact = mgr.register_artifact(test_file, source_tool="test")
        self.assertTrue(artifact.url.startswith("/api/"), f"URL must be relative: {artifact.url}")

    def test_O4_register_nonexistent_file_raises(self):
        """Registering a nonexistent file must raise FileNotFoundError."""
        from app.artifacts.manager import ArtifactManager
        mgr = ArtifactManager()
        with self.assertRaises(FileNotFoundError):
            mgr.register_artifact("/tmp/nonexistent_12345.png", source_tool="test")

    def test_O5_artifact_preview_supported_flag(self):
        """preview_supported must be True for HTML and False for unknown types."""
        from app.artifacts.manager import ArtifactManager
        mgr = ArtifactManager()
        html_file = os.path.join(self.tmp, "page.html")
        with open(html_file, "w") as f:
            f.write("<html></html>")
        artifact = mgr.register_artifact(html_file, source_tool="test")
        self.assertTrue(artifact.preview_supported)

    def test_O6_artifact_retrieval_by_id(self):
        """Artifacts must be retrievable by artifact_id."""
        from app.artifacts.manager import ArtifactManager
        mgr = ArtifactManager()
        test_file = os.path.join(self.tmp, "lookup.txt")
        with open(test_file, "w") as f:
            f.write("content")
        artifact = mgr.register_artifact(test_file, source_tool="test")
        retrieved = mgr.get_artifact(artifact.artifact_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.artifact_id, artifact.artifact_id)

    def test_O7_unknown_artifact_id_returns_none(self):
        """Unknown artifact_id must return None, not crash."""
        from app.artifacts.manager import ArtifactManager
        mgr = ArtifactManager()
        result = mgr.get_artifact("art_doesnotexist")
        self.assertIsNone(result)


# ─────────────────────────────────────────────────────────────────────────────
# P. ToolResult Contract
# ─────────────────────────────────────────────────────────────────────────────

class TestToolResult(unittest.TestCase):
    def test_P1_toolresult_has_artifacts_field(self):
        """ToolResult must have an artifacts field defaulting to []."""
        from app.tools.base import ToolResult
        res = ToolResult(success=True, tool="test_tool", result={"ok": True})
        self.assertIsInstance(res.artifacts, list)
        self.assertEqual(res.artifacts, [])

    def test_P2_toolresult_success_status_auto(self):
        from app.tools.base import ToolResult
        res = ToolResult(success=True, tool="t", result={})
        self.assertEqual(res.status, "completed")
        res_fail = ToolResult(success=False, tool="t", error={"code": "ERR"})
        self.assertEqual(res_fail.status, "failed")

    def test_P3_toolresult_to_dict_includes_artifacts(self):
        from app.tools.base import ToolResult
        artifact_info = {"artifact_id": "art_abc", "filename": "out.png"}
        res = ToolResult(success=True, tool="test", result={}, artifacts=[artifact_info])
        d = res.to_dict()
        self.assertIn("artifacts", d)
        self.assertEqual(d["artifacts"], [artifact_info])

    def test_P4_permission_required_result_structure(self):
        """Permission-required result must have correct structure."""
        from app.tools.base import ToolResult
        res = ToolResult(
            success=False, tool="run_command",
            status="permission_required",
            error={"code": "PERMISSION_REQUIRED", "message": "Permission required"},
            metadata={
                "request_id": "perm_abc123",
                "permission": "terminal.execute",
                "summary": "Execute npm install",
                "risk": "medium"
            }
        )
        d = res.to_dict()
        self.assertEqual(d["status"], "permission_required")
        self.assertEqual(d["metadata"]["risk"], "medium")
        self.assertEqual(d["metadata"]["permission"], "terminal.execute")

    def test_P5_data_result_sync(self):
        """result and data fields must be kept in sync."""
        from app.tools.base import ToolResult
        res = ToolResult(success=True, tool="t", result={"x": 1})
        self.assertEqual(res.data, {"x": 1})
        res2 = ToolResult(success=True, tool="t", data={"y": 2})
        self.assertEqual(res2.result, {"y": 2})


# ─────────────────────────────────────────────────────────────────────────────
# Q. Bounded LLM Results
# ─────────────────────────────────────────────────────────────────────────────

class TestBoundedResults(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jarvis_bound_test_")
        self.reg = get_registry()
        self.ctx, _ = make_ctx(permissions=FULL_PERMS, workspace_root=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_Q1_large_file_read_is_bounded(self):
        """read_file of large file must return bounded agent-facing result."""
        big_content = "A" * 20000
        path = os.path.join(self.tmp, "bigfile.txt")
        with open(path, "w") as f:
            f.write(big_content)
        # The file is NOT corrupted by bounding
        self.assertEqual(open(path).read(), big_content, "File must be unmodified on disk")

        res = self.reg.execute("read_file", {"path": "bigfile.txt"}, self.ctx)
        self.assertTrue(res.success, f"read_file should succeed: {res.error}")
        result_data = res.result or {}
        content = result_data.get("content", "")
        self.assertLessEqual(len(content), 9000, f"Agent-facing content must be bounded, got {len(content)}")
        # Must indicate truncation
        if len(big_content) > 8000:
            self.assertTrue(result_data.get("truncated", False), "truncated must be True for large files")

    def test_Q2_underlying_file_not_corrupted(self):
        """Bounding result must NOT modify the underlying file."""
        big_content = "B" * 15000
        path = os.path.join(self.tmp, "intact.txt")
        with open(path, "w") as f:
            f.write(big_content)
        self.reg.execute("read_file", {"path": "intact.txt"}, self.ctx)
        actual = open(path).read()
        self.assertEqual(actual, big_content, "File must be unmodified after bounded read")


# ─────────────────────────────────────────────────────────────────────────────
# R. Risk Metadata
# ─────────────────────────────────────────────────────────────────────────────

class TestRiskMetadata(unittest.TestCase):
    def test_R1_read_file_is_low_risk(self):
        from app.tools.filesystem import ReadFileTool
        self.assertEqual(ReadFileTool.risk, "low")

    def test_R2_delete_file_is_high_risk(self):
        from app.tools.filesystem import DeleteFileTool
        self.assertEqual(DeleteFileTool.risk, "high")

    def test_R3_run_command_is_high_risk(self):
        from app.tools.terminal import RunCommandTool
        self.assertEqual(RunCommandTool.risk, "high")

    def test_R4_git_push_is_high_risk(self):
        from app.tools.git_tools import GitPushTool
        self.assertEqual(GitPushTool.risk, "high")

    def test_R5_git_status_is_low_risk(self):
        from app.tools.git_tools import GitStatusTool
        self.assertEqual(GitStatusTool.risk, "low")

    def test_R6_sandbox_exec_is_high_risk(self):
        from app.tools.sandbox_tools import SandboxExecTool
        self.assertEqual(SandboxExecTool.risk, "high")


# ─────────────────────────────────────────────────────────────────────────────
# S. Cross-Capability Workflow (End-to-End)
# ─────────────────────────────────────────────────────────────────────────────

class TestEndToEndWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jarvis_e2e_test_")
        self.reg = get_registry()
        self.ctx, _ = make_ctx(permissions=FULL_PERMS, workspace_root=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_S1_create_website_files(self):
        """Create index.html, style.css, app.js in workspace."""
        html = self.reg.execute("create_file", {
            "path": "index.html",
            "content": "<!DOCTYPE html><html><head><link rel='stylesheet' href='style.css'></head><body><h1>JARVIS Demo</h1><script src='app.js'></script></body></html>"
        }, self.ctx)
        css = self.reg.execute("create_file", {
            "path": "style.css",
            "content": "body { font-family: sans-serif; background: #0a0a0a; color: #e5e5e5; }"
        }, self.ctx)
        js = self.reg.execute("create_file", {
            "path": "app.js",
            "content": "console.log('JARVIS Demo loaded');"
        }, self.ctx)
        self.assertTrue(html.success, f"HTML failed: {html.error}")
        self.assertTrue(css.success, f"CSS failed: {css.error}")
        self.assertTrue(js.success, f"JS failed: {js.error}")
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "index.html")))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "style.css")))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "app.js")))

    def test_S2_register_html_artifact(self):
        """After creating HTML, register it as an artifact."""
        html_path = os.path.join(self.tmp, "demo.html")
        with open(html_path, "w") as f:
            f.write("<!DOCTYPE html><html><body><h1>Demo</h1></body></html>")
        from app.artifacts.manager import ArtifactManager
        mgr = ArtifactManager()
        artifact = mgr.register_artifact(html_path, source_tool="create_file", session_id="test-session")
        pub = artifact.to_dict()
        self.assertNotIn("file_path", pub, "Public artifact must not contain file_path")
        self.assertEqual(pub["filename"], "demo.html")
        self.assertTrue(pub["preview_supported"])
        self.assertTrue(pub["artifact_id"].startswith("art_"))

    def test_S3_full_workflow_no_false_success(self):
        """End-to-end: create → list → read → verify, all truthful."""
        create_res = self.reg.execute("create_file", {"path": "workflow.txt", "content": "step1"}, self.ctx)
        self.assertTrue(create_res.success)
        list_res = self.reg.execute("list_files", {"path": "."}, self.ctx)
        self.assertTrue(list_res.success)
        read_res = self.reg.execute("read_file", {"path": "workflow.txt"}, self.ctx)
        self.assertTrue(read_res.success)
        # No success claimed for missing file
        miss_res = self.reg.execute("read_file", {"path": "missing_file.txt"}, self.ctx)
        self.assertFalse(miss_res.success)


# ─────────────────────────────────────────────────────────────────────────────
# T. Agent/Brain Coordination Contract
# ─────────────────────────────────────────────────────────────────────────────

class TestBrainCoordinationContract(unittest.TestCase):
    def setUp(self):
        self.reg = get_registry()

    def test_T1_tool_definitions_are_llm_serializable(self):
        """All tool definitions must be JSON-serializable (for LLM function calling)."""
        defs = self.reg.get_tool_definitions()
        for d in defs:
            try:
                json.dumps(d)
            except TypeError as e:
                self.fail(f"Tool definition for '{d.get('name')}' is not JSON-serializable: {e}")

    def test_T2_openai_format_tool_definitions(self):
        """as_openai=True must produce valid OpenAI function calling format."""
        defs = self.reg.get_tool_definitions(as_openai=True)
        for d in defs:
            self.assertIn("type", d)
            self.assertEqual(d["type"], "function")
            self.assertIn("function", d)
            fn = d["function"]
            self.assertIn("name", fn)
            self.assertIn("description", fn)
            self.assertIn("parameters", fn)

    def test_T3_agent_never_directly_calls_filesystem(self):
        """Verify app/agent/ does not directly import filesystem modules."""
        agent_dir = os.path.join(os.path.dirname(__file__), "..", "app", "agent")
        if not os.path.isdir(agent_dir):
            self.skipTest("Agent directory not found")
        dangerous_imports = ["subprocess", "os.system", "pathlib.Path", "open(", "requests.get", "httpx", "aiohttp"]
        for fname in os.listdir(agent_dir):
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(agent_dir, fname)
            content = open(fpath, encoding="utf-8", errors="ignore").read()
            for d_import in dangerous_imports:
                # Some subprocess/os usage might be legitimate (non-direct env access)
                # We just record them — a direct import of filesystem.py would be critical
                pass  # We do the specific check below
        # Specific critical check: agent must not import filesystem.py directly
        for fname in os.listdir(agent_dir):
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(agent_dir, fname)
            content = open(fpath, encoding="utf-8", errors="ignore").read()
            self.assertNotIn("from app.tools.filesystem import",  content,
                f"{fname} imports filesystem directly — must go through ToolRegistry")
            self.assertNotIn("from app.tools.terminal import RunCommandTool", content,
                f"{fname} imports RunCommandTool directly — must go through ToolRegistry")

    def test_T4_toolresult_success_truthful(self):
        """Brain must never see success=True for genuinely failed operations."""
        from app.tools.base import ToolContext
        ctx = ToolContext()
        res = self.reg.execute("read_file", {"path": "/nonexistent/path/file.txt"}, ctx)
        self.assertFalse(res.success, "Non-existent file read must return success=False")

    def test_T5_permission_required_result_consumable_by_brain(self):
        """Brain can identify permission_required and handle it."""
        ctx, tmp = make_ctx(permissions={"filesystem.read"})
        res = self.reg.execute("delete_file", {"path": "x.txt"}, ctx)
        self.assertFalse(res.success)
        self.assertEqual(res.status, "permission_required")
        # Brain-consumable check: key fields present
        self.assertIn("request_id", res.metadata)
        self.assertIn("permission", res.metadata)
        self.assertIn("risk", res.metadata)
        d = res.to_dict()
        self.assertEqual(d["status"], "permission_required")
        shutil.rmtree(tmp, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# U. PermissionEngine Unit Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPermissionEngineUnit(unittest.TestCase):
    def test_U1_default_normal_policy(self):
        from app.permissions.engine import PermissionPolicy, PermissionMode
        policy = PermissionPolicy.default_normal()
        self.assertEqual(policy.mode, PermissionMode.NORMAL)
        self.assertTrue(policy.has_permission("filesystem.read"))
        self.assertTrue(policy.has_permission("terminal.execute"))

    def test_U2_read_only_policy(self):
        from app.permissions.engine import PermissionPolicy
        policy = PermissionPolicy.read_only()
        self.assertTrue(policy.has_permission("filesystem.read"))
        self.assertFalse(policy.has_permission("filesystem.write"))
        self.assertFalse(policy.has_permission("filesystem.delete"))
        self.assertFalse(policy.has_permission("terminal.execute"))

    def test_U3_from_dict_roundtrip(self):
        from app.permissions.engine import PermissionPolicy, PermissionMode
        data = {"mode": "turbo", "permissions": ["filesystem.read", "filesystem.write"]}
        policy = PermissionPolicy.from_dict(data)
        self.assertEqual(policy.mode, PermissionMode.TURBO)
        self.assertTrue(policy.has_permission("filesystem.read"))

    def test_U4_expire_old_requests(self):
        """expire_old_requests() must mark expired pending requests."""
        from app.permissions.engine import PermissionEngine, PermissionPolicy, PermissionMode, ApprovalStatus
        engine = PermissionEngine()
        policy = PermissionPolicy(mode=PermissionMode.NORMAL, permissions=set())
        req = engine.evaluate("delete_file", "filesystem.delete", policy, {"path": "x.txt"}, run_id="run-X")
        req.expires_at = time.time() - 1  # force expiry
        count = engine.expire_old_requests()
        self.assertGreaterEqual(count, 1)
        self.assertEqual(req.status, ApprovalStatus.EXPIRED)

    def test_U5_clear_run_removes_requests(self):
        """clear_run() removes all requests for a run."""
        from app.permissions.engine import PermissionEngine, PermissionPolicy, PermissionMode
        engine = PermissionEngine()
        policy = PermissionPolicy(mode=PermissionMode.NORMAL, permissions=set())
        req = engine.evaluate("delete_file", "filesystem.delete", policy, {"path": "y.txt"}, run_id="run-Y")
        engine.clear_run("run-Y")
        self.assertIsNone(engine.get_request(req.request_id))


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
