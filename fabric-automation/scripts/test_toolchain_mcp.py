#!/usr/bin/env python3
"""Tests for toolchain_mcp.py: reading the tool contract of an MCP server and comparing two contracts.

The stdio tests run a stand-in server (a small Python script written to a temp folder and started with the
interpreter that runs the tests). The legacy mode follows the `initialize` handshake. The modern mode is built from
the 2026-07-28 revision of the specification (versioning, stdio transport, server/discover and tools pages), because no real
server of that era was available: those tests show that the client follows the pages, not that a real server agrees.
Run from the project folder:

    python -m unittest scripts.test_toolchain_mcp -v
"""

import hashlib
import json
import os
import queue
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import toolchain_io  # noqa: E402
import toolchain_mcp  # noqa: E402
from toolchain_io import HttpResult  # noqa: E402
from test_toolchain_io import PY, WINDOWS, pid_alive, read_pids, wait_dead  # noqa: E402

FAKE_SERVER = r'''
import json, os, subprocess, sys, time

mode = sys.argv[1] if len(sys.argv) > 1 else "legacy"
log_path = os.environ.get("FAKE_LOG")
pid_path = os.environ.get("FAKE_PIDFILE")
ignore_eof = os.environ.get("FAKE_IGNORE_EOF") == "1"
M = "io.modelcontextprotocol/"
TOOLS = [
    {"name": "docs_search", "description": "Search", "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]},
     "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}},
    {"name": "item_delete", "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}},
     "annotations": {"readOnlyHint": False, "destructiveHint": True}},
    {"name": "alpha_plain", "inputSchema": {"type": "object"}},
]
if mode == "bigline":
    TOOLS = [dict(TOOLS[0], description="d" * 6000)]


def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def reply(mid, result):
    send({"jsonrpc": "2.0", "id": mid, "result": result})


def fail(mid, code, message, data=None):
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    send({"jsonrpc": "2.0", "id": mid, "error": error})


child_pid = 0
if mode == "grandchild":
    child_pid = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"]).pid
if pid_path:
    with open(pid_path, "w") as handle:
        handle.write("%d %d" % (os.getpid(), child_pid))
dump_path = os.environ.get("FAKE_ENV_DUMP")
if dump_path:
    with open(dump_path, "w") as handle:
        json.dump(dict(os.environ), handle)
if mode == "exit":
    sys.exit(3)
if mode in ("silent", "grandchild"):
    while True:
        time.sleep(0.2)


def modern_meta_ok(params):
    meta = params.get("_meta")
    return (isinstance(meta, dict) and meta.get(M + "protocolVersion") == "2026-07-28"
            and isinstance(meta.get(M + "clientInfo"), dict) and isinstance(meta.get(M + "clientCapabilities"), dict))


def page(cursor):
    if mode == "pages":
        return (TOOLS[2:], None) if cursor == "p2" else (TOOLS[:2], "p2")
    if mode == "loop":
        loop_count[0] += 1
        return [{"name": "loop_tool_%d" % loop_count[0], "inputSchema": {"type": "object"}}], "same"
    if mode == "duplicate":
        return [TOOLS[0], TOOLS[0]], None
    if mode == "empty":
        return [], None
    return TOOLS, None


legacy_result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                 "serverInfo": {"name": "Fake Server", "version": "1.2.3"}}
loop_count = [0]
is_modern = mode.startswith("modern")
initialized = False
waiting_for_ping = False
queued = None

if mode == "garbage":
    print("starting fake server")
    print("{not json")
    print("42")
    print("[1, 2]")
    print("")
    sys.stderr.write("noise on stderr\n")
    send({"jsonrpc": "2.0", "method": "notifications/message", "params": {"level": "info", "data": "hello"}})
    send({"jsonrpc": "2.0", "id": 999, "result": {}})

for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue
    if log_path:
        with open(log_path, "a") as handle:
            handle.write(raw + "\n")
    if mode == "chatty":
        spam = (json.dumps({"jsonrpc": "2.0", "method": "notifications/message", "params": {"level": "info", "data": "spam"}}) + "\n") * 5000
        while True:
            sys.stdout.write(spam)
            sys.stdout.flush()
    msg = json.loads(raw)
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if method is None:
        if mid == "srv-1":
            waiting_for_ping = False
            if queued is not None:
                reply(queued, {"tools": TOOLS})
                queued = None
        continue
    if method == "initialize":
        if mode == "modern":
            fail(mid, -32022, "Unsupported protocol version", {"supported": ["2026-07-28", "2025-11-25"], "requested": params.get("protocolVersion")})
        elif mode == "modern-text":
            fail(mid, -32600, "This server only supports protocol versions 2026-07-28 and later")
        elif mode == "modern-bare":
            fail(mid, -32601, "Method not found")
        elif mode == "modern-unsupported":
            fail(mid, -32022, "Unsupported protocol version", {"supported": ["2027-01-01"]})
        elif mode == "modern-other":
            fail(mid, -32022, "Unsupported protocol version", {"supported": ["2026-07-28"]})
        elif mode == "legacy-error":
            fail(mid, -32603, "Internal error 2026-09-01 at startup")
        elif mode == "legacy-strict" and params.get("protocolVersion") != "2025-06-18":
            fail(mid, -32602, "Unsupported protocol version", {"supported": ["2025-06-18"], "requested": params.get("protocolVersion")})
        else:
            reply(mid, legacy_result)
            if mode == "ping":
                send({"jsonrpc": "2.0", "id": "srv-1", "method": "ping"})
                waiting_for_ping = True
        continue
    if method == "notifications/initialized":
        initialized = True
        continue
    if method == "server/discover":
        if mode in ("modern", "modern-text", "modern-bare") and modern_meta_ok(params):
            reply(mid, {"resultType": "complete", "supportedVersions": ["2026-07-28"], "capabilities": {"tools": {}},
                        "_meta": {M + "serverInfo": {"name": "Fake Modern", "version": "2.0.0"}}, "ttlMs": 0})
        elif mode == "modern-unsupported":
            fail(mid, -32022, "Unsupported protocol version", {"supported": ["2027-01-01"]})
        elif mode == "modern-other":
            reply(mid, {"resultType": "complete", "supportedVersions": ["2027-01-01"], "capabilities": {}})
        else:
            fail(mid, -32601, "Method not found")
        continue
    if method == "tools/list":
        if is_modern:
            if not modern_meta_ok(params):
                fail(mid, -32602, "missing request metadata")
                continue
        elif not initialized:
            fail(mid, -32602, "not initialized")
            continue
        if mode == "no-method":
            fail(mid, -32601, "Method not found")
            continue
        if mode == "tools-error":
            fail(mid, -32603, "boom at the-host")
            continue
        if waiting_for_ping:
            queued = mid
            continue
        tools, cursor = page(params.get("cursor"))
        result = {"tools": tools}
        if cursor:
            result["nextCursor"] = cursor
        if is_modern:
            result["resultType"] = "complete"
        reply(mid, result)
        continue
    fail(mid, -32601, "Method not found")

if ignore_eof:
    while True:
        time.sleep(0.2)
'''


def schema_digest(schema):
    text = json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


SEARCH_SCHEMA = {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}
EXPECTED_TOOLS = {
    "alpha_plain": {"schema": schema_digest({"type": "object"}), "read_only": None, "destructive": None, "idempotent": None},
    "docs_search": {"schema": schema_digest(SEARCH_SCHEMA), "read_only": True, "destructive": False, "idempotent": True},
    "item_delete": {"schema": schema_digest({"type": "object", "properties": {"id": {"type": "string"}}}),
                    "read_only": False, "destructive": True, "idempotent": None},
}


class StdioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        cls.script = cls.dir / "fake_server.py"
        cls.script.write_text(FAKE_SERVER, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.log = self.dir / ("log-%s.txt" % self._testMethodName)
        self.pids = self.dir / ("pids-%s.txt" % self._testMethodName)

    def probe(self, mode, *, env=None, timeout=30, argv=None, cwd=None):
        full = {"FAKE_LOG": str(self.log), "FAKE_PIDFILE": str(self.pids)}
        full.update(env or {})
        return toolchain_mcp.probe_stdio(argv or [PY, str(self.script), mode], env=full, cwd=cwd or str(self.dir), timeout=timeout)

    def messages(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def assertFails(self, code, mode, **kwargs):
        with self.assertRaises(toolchain_mcp.McpProbeError) as caught:
            self.probe(mode, **kwargs)
        self.assertEqual(code, caught.exception.code, str(caught.exception))
        self.assertTrue(str(caught.exception).startswith(code), str(caught.exception))
        return caught.exception

    def assertGone(self, wait=3.0):
        pids = read_pids(self.pids, seconds=1.0)
        self.assertTrue(pids, "the stand-in server never wrote its process ids")
        for pid in pids:
            if pid:
                self.assertTrue(wait_dead(pid, wait), "process %d is still running" % pid)

    def test_legacy_handshake_and_the_shape_of_the_contract(self):
        result = self.probe("legacy")
        self.assertEqual({"era", "protocol", "server", "tools"}, set(result))
        self.assertEqual("legacy", result["era"])
        self.assertEqual("2025-06-18", result["protocol"])
        self.assertEqual({"name": "Fake Server", "version": "1.2.3"}, result["server"])
        self.assertEqual(EXPECTED_TOOLS, result["tools"])
        self.assertEqual(sorted(EXPECTED_TOOLS), list(result["tools"]))

    def test_legacy_messages_follow_the_handshake_in_order(self):
        self.probe("legacy")
        sent = self.messages()
        self.assertEqual(["initialize", "notifications/initialized", "tools/list"], [m["method"] for m in sent])
        initialize = sent[0]
        self.assertEqual("2.0", initialize["jsonrpc"])
        self.assertEqual("2025-11-25", initialize["params"]["protocolVersion"])
        self.assertEqual({}, initialize["params"]["capabilities"])
        self.assertEqual("fabric-automation-toolchain", initialize["params"]["clientInfo"]["name"])
        self.assertIn("version", initialize["params"]["clientInfo"])
        self.assertNotIn("id", sent[1])
        self.assertNotIn("_meta", json.dumps(sent))

    def test_pages_are_followed_with_the_cursor(self):
        result = self.probe("pages")
        self.assertEqual(EXPECTED_TOOLS, result["tools"])
        lists = [m for m in self.messages() if m["method"] == "tools/list"]
        self.assertEqual(2, len(lists))
        self.assertNotIn("cursor", lists[0]["params"])
        self.assertEqual("p2", lists[1]["params"]["cursor"])

    def test_garbage_on_standard_output_and_noise_on_standard_error_are_ignored(self):
        self.assertEqual(EXPECTED_TOOLS, self.probe("garbage")["tools"])

    def test_requests_from_the_server_are_answered(self):
        self.assertEqual(EXPECTED_TOOLS, self.probe("ping", timeout=8)["tools"])
        replies = [m for m in self.messages() if m.get("id") == "srv-1"]
        self.assertEqual([{"jsonrpc": "2.0", "id": "srv-1", "result": {}}], replies)

    def test_modern_era_when_the_error_names_the_versions(self):
        result = self.probe("modern")
        self.assertEqual("modern", result["era"])
        self.assertEqual("2026-07-28", result["protocol"])
        self.assertEqual({"name": "Fake Modern", "version": "2.0.0"}, result["server"])
        self.assertEqual(EXPECTED_TOOLS, result["tools"])

    def test_modern_requests_carry_the_metadata_and_no_handshake(self):
        self.probe("modern")
        sent = self.messages()
        self.assertEqual(["initialize", "server/discover", "tools/list"], [m["method"] for m in sent])
        self.assertNotIn("notifications/initialized", [m["method"] for m in sent])
        meta = sent[1]["params"]["_meta"]
        self.assertEqual("2026-07-28", meta["io.modelcontextprotocol/protocolVersion"])
        self.assertEqual("fabric-automation-toolchain", meta["io.modelcontextprotocol/clientInfo"]["name"])
        self.assertEqual({}, meta["io.modelcontextprotocol/clientCapabilities"])
        self.assertEqual(meta, sent[2]["params"]["_meta"])

    def test_modern_era_when_only_the_message_names_the_versions(self):
        self.assertEqual("modern", self.probe("modern-text")["era"])

    def test_modern_era_when_the_error_names_nothing_but_discover_answers(self):
        self.assertEqual("modern", self.probe("modern-bare")["era"])

    def test_a_date_in_an_unrelated_error_does_not_make_a_server_modern(self):
        error = self.assertFails("protocol-error", "legacy-error")
        self.assertIn("initialize failed", str(error))
        self.assertNotIn("2026", str(error))
        self.assertNotIn("startup", str(error))

    def test_a_legacy_server_that_refuses_our_version_is_asked_again_with_one_it_names(self):
        result = self.probe("legacy-strict")
        self.assertEqual("legacy", result["era"])
        self.assertEqual(EXPECTED_TOOLS, result["tools"])
        asked = [m["params"]["protocolVersion"] for m in self.messages() if m["method"] == "initialize"]
        self.assertEqual(["2025-11-25", "2025-06-18"], asked)

    def test_no_mutually_supported_modern_version_is_a_protocol_error(self):
        self.assertIn("mutually", str(self.assertFails("protocol-error", "modern-unsupported")))

    def test_a_discover_result_that_lacks_our_version_is_a_protocol_error(self):
        self.assertIn("mutually", str(self.assertFails("protocol-error", "modern-other")))

    def test_a_silent_server_times_out_and_is_gone(self):
        started = time.monotonic()
        self.assertFails("timeout", "silent", timeout=3.0)
        self.assertLess(time.monotonic() - started, 30)
        self.assertGone()

    def test_a_server_that_never_stops_talking_still_runs_into_the_deadline(self):
        started = time.monotonic()
        self.assertFails("timeout", "chatty", timeout=2.0)
        self.assertLess(time.monotonic() - started, 30)
        self.assertGone()

    def test_a_grandchild_of_a_silent_server_is_gone_too(self):
        self.assertFails("timeout", "grandchild", timeout=4.0)
        pids = read_pids(self.pids, seconds=1.0)
        self.assertEqual(2, len(pids))
        self.assertTrue(pids[1], "the stand-in server never started its child")
        self.assertGone()

    def test_a_server_that_ignores_end_of_input_is_killed_after_a_success(self):
        started = time.monotonic()
        result = self.probe("legacy", env={"FAKE_IGNORE_EOF": "1"})
        self.assertEqual(EXPECTED_TOOLS, result["tools"])
        self.assertLess(time.monotonic() - started, 30)
        self.assertGone(wait=0.5)

    def test_a_server_that_exits_at_once_is_exited(self):
        error = self.assertFails("exited", "exit")
        self.assertIn("3", str(error))

    def test_a_missing_executable_is_spawn_failed_without_the_path(self):
        missing = str(self.dir / "no-such-server-xyz")
        with self.assertRaises(toolchain_mcp.McpProbeError) as caught:
            toolchain_mcp.probe_stdio([missing, "legacy"], timeout=5)
        self.assertEqual("spawn-failed", caught.exception.code)
        self.assertNotIn("no-such-server", str(caught.exception))
        self.assertNotIn(self.tmp.name, str(caught.exception))
        for bad in ([], [""]):
            with self.assertRaises(toolchain_mcp.McpProbeError) as caught:
                toolchain_mcp.probe_stdio(bad, timeout=5)
            self.assertEqual("spawn-failed", caught.exception.code)

    def test_an_empty_tool_list_is_no_tools(self):
        self.assertFails("no-tools", "empty")

    def test_a_server_without_tools_support_is_no_tools(self):
        self.assertFails("no-tools", "no-method")

    def test_an_error_answer_is_a_protocol_error_without_the_server_text(self):
        error = self.assertFails("protocol-error", "tools-error")
        self.assertNotIn("the-host", str(error))
        self.assertNotIn("boom", str(error))

    def test_duplicate_tool_names_are_a_protocol_error(self):
        self.assertFails("protocol-error", "duplicate")

    def test_a_cursor_that_never_ends_is_a_protocol_error(self):
        self.assertIn("do not end", str(self.assertFails("protocol-error", "loop")))

    def test_a_line_over_the_limit_is_a_protocol_error(self):
        with mock.patch.object(toolchain_mcp, "MAX_LINE", 2000):
            self.assertIn("longer than the limit", str(self.assertFails("protocol-error", "bigline", timeout=10)))

    def test_environment_and_working_directory_reach_the_server(self):
        script = self.dir / "env_server.py"
        script.write_text(
            "import json, os, sys\n"
            "for raw in sys.stdin:\n"
            "    msg = json.loads(raw)\n"
            "    if msg.get('method') == 'initialize':\n"
            "        info = {'name': os.environ.get('TC_NAME', ''), 'version': os.path.basename(os.getcwd())}\n"
            "        print(json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'result': {'protocolVersion': '2025-06-18', 'serverInfo': info}}), flush=True)\n"
            "    elif msg.get('method') == 'tools/list':\n"
            "        print(json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'result': {'tools': [{'name': 't', 'inputSchema': {}}]}}), flush=True)\n",
            encoding="utf-8")
        work = self.dir / "workdir"
        work.mkdir(exist_ok=True)
        result = toolchain_mcp.probe_stdio([PY, str(script)], env={"TC_NAME": "from-env"}, cwd=str(work), timeout=20)
        self.assertEqual({"name": "from-env", "version": "workdir"}, result["server"])
        self.assertEqual(["t"], list(result["tools"]))

    def dump_env(self, declared=None, parent=None):
        """The environment the stand-in server saw, with upper-case names, when this process has the given extra variables."""
        dump = self.dir / ("env-%s.json" % self._testMethodName)
        env = {"FAKE_ENV_DUMP": str(dump)}
        env.update(declared or {})
        with mock.patch.dict(os.environ, parent or {}):
            self.probe("legacy", env=env)
        return {name.upper(): value for name, value in json.loads(dump.read_text(encoding="utf-8")).items()}

    def interpreter_additions(self):
        """The variables the interpreter of the stand-in server puts into its own environment when it is given almost nothing."""
        script = "import json, os, sys; json.dump(sorted(name.upper() for name in os.environ), sys.stdout)"
        given = {name: os.environ.get(name, "") for name in ("SYSTEMROOT", "SYSTEMDRIVE", "PROGRAMDATA")}
        proc = toolchain_io.popen_tree([PY, "-c", script], cwd=str(self.dir), env=given, stdout=subprocess.PIPE, inherit=False)
        out, _ = proc.communicate(timeout=60)
        return set(json.loads(out.decode("utf-8")))

    @unittest.skipUnless(WINDOWS, "a Windows child without the system drive variable writes a literal %SystemDrive% folder tree")
    def test_the_child_leaves_nothing_in_its_working_directory(self):
        work = self.dir / ("work-%s" % self._testMethodName)
        work.mkdir(exist_ok=True)
        self.probe("legacy", cwd=str(work))
        self.assertEqual([], os.listdir(work))

    def test_the_child_does_not_inherit_the_environment_of_the_parent(self):
        parent = {"SECRET_X": "secret-value", "PBI_MODELING_MCP_ALLOWED_CONNECTION_HOSTS": "tokens.example", "AZURE_CLIENT_ID": "id-value",
                  "AZURE_TENANT_ID": "tenant-value", "NODE_OPTIONS": "--require=hook.js", "GITHUB_TOKEN": "token-value", "PYTHONPATH": "elsewhere"}
        seen = self.dump_env({"DECLARED_WITH_DEFAULT": {"from_env": "DECLARED_WITH_DEFAULT", "default": "fallback"}}, parent)
        for name in parent:
            self.assertNotIn(name, seen)
        self.assertEqual("fallback", seen["DECLARED_WITH_DEFAULT"])
        self.assertEqual(os.environ["PATH"], seen["PATH"])
        known = {name.upper() for name in toolchain_mcp.ENV_ALLOW_LIST} | {"DECLARED_WITH_DEFAULT", "FAKE_ENV_DUMP", "FAKE_LOG", "FAKE_PIDFILE"}
        self.assertEqual([], sorted(set(seen) - known - self.interpreter_additions()), "variables that nobody allowed or declared reached the child")

    def test_a_declared_variable_takes_the_value_of_the_parent_only_when_the_parent_sets_it(self):
        declared = {"TC_WITH_DEFAULT": {"from_env": "TC_WITH_DEFAULT", "default": "fallback"}, "TC_NO_DEFAULT": {"from_env": "TC_NO_DEFAULT"},
                    "TC_RENAMED": {"from_env": "TC_SOURCE_NAME", "default": "renamed-default"}, "TC_OWN_NAME": {"default": "own-default"},
                    "TC_LITERAL": "fixed"}
        seen = self.dump_env(declared, {})
        self.assertEqual("fallback", seen["TC_WITH_DEFAULT"])
        self.assertNotIn("TC_NO_DEFAULT", seen)
        self.assertEqual("renamed-default", seen["TC_RENAMED"])
        self.assertEqual("own-default", seen["TC_OWN_NAME"])
        self.assertEqual("fixed", seen["TC_LITERAL"])
        seen = self.dump_env(declared, {"TC_WITH_DEFAULT": "from-parent", "TC_NO_DEFAULT": "also-parent", "TC_SOURCE_NAME": "renamed-parent",
                                        "TC_OWN_NAME": "own-parent", "TC_LITERAL": "parent-must-not-win"})
        self.assertEqual("from-parent", seen["TC_WITH_DEFAULT"])
        self.assertEqual("also-parent", seen["TC_NO_DEFAULT"])
        self.assertEqual("renamed-parent", seen["TC_RENAMED"])
        self.assertEqual("own-parent", seen["TC_OWN_NAME"])
        self.assertEqual("fixed", seen["TC_LITERAL"])
        seen = self.dump_env(declared, {"TC_WITH_DEFAULT": ""})
        self.assertEqual("fallback", seen["TC_WITH_DEFAULT"], "an empty value counts as not set, as in the ${NAME:-default} form the hosts use")

    def test_the_variables_a_process_needs_to_start_are_passed_on(self):
        parent = {"HTTPS_PROXY": "http://proxy.test:3128", "NO_PROXY": "localhost", "SSL_CERT_FILE": "ca-bundle.pem", "NODE_EXTRA_CA_CERTS": "extra-ca.pem",
                  "npm_config_registry": "https://registry.test/", "NPM_CONFIG_CACHE": "npm-cache", "LANG": "en_US.UTF-8", "LC_ALL": "C"}
        seen = self.dump_env({}, parent)
        for name, value in parent.items():
            self.assertEqual(value, seen[name.upper()], name)
        self.assertIn("SYSTEMROOT" if WINDOWS else "PATH", seen)

    def test_a_credential_reaches_the_child_only_when_the_variant_declares_it(self):
        parent = {"AZURE_CLIENT_ID": "id-value", "PBI_MODELING_MCP_ACCEPT_EULA": "true"}
        seen = self.dump_env({}, parent)
        self.assertNotIn("AZURE_CLIENT_ID", seen)
        self.assertNotIn("PBI_MODELING_MCP_ACCEPT_EULA", seen)
        seen = self.dump_env({"AZURE_CLIENT_ID": {"from_env": "AZURE_CLIENT_ID"}, "PBI_MODELING_MCP_ACCEPT_EULA": {"from_env": "PBI_MODELING_MCP_ACCEPT_EULA", "default": "false"}}, parent)
        self.assertEqual("id-value", seen["AZURE_CLIENT_ID"])
        self.assertEqual("true", seen["PBI_MODELING_MCP_ACCEPT_EULA"])
        seen = self.dump_env({"PBI_MODELING_MCP_ACCEPT_EULA": {"from_env": "PBI_MODELING_MCP_ACCEPT_EULA", "default": "false"}}, {})
        self.assertEqual("false", seen["PBI_MODELING_MCP_ACCEPT_EULA"])

    def test_a_declaration_the_probe_cannot_read_is_a_spawn_failure(self):
        for bad in ({"X": 5}, {"X": ["a"]}, {"": "v"}, {"A=B": "v"}, {"X": {"default": 7}}):
            with self.assertRaises(toolchain_mcp.McpProbeError) as caught:
                toolchain_mcp.probe_stdio([PY, str(self.script)], env=bad, timeout=5)
            self.assertEqual("spawn-failed", caught.exception.code, bad)

    def test_server_name_and_version_are_sanitised(self):
        script = self.dir / "name_server.py"
        script.write_text(
            "import json, sys\n"
            "name = 'Srv at ' + 'https://feed' + '.example/x ' + 'C:' + chr(92) + 'dir'\n"
            "for raw in sys.stdin:\n"
            "    msg = json.loads(raw)\n"
            "    if msg.get('method') == 'initialize':\n"
            "        info = {'name': name, 'version': '1.6.0+abc123'}\n"
            "        print(json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'result': {'protocolVersion': '2025-06-18', 'serverInfo': info}}), flush=True)\n"
            "    elif msg.get('method') == 'tools/list':\n"
            "        print(json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'result': {'tools': [{'name': 't', 'inputSchema': {}}]}}), flush=True)\n",
            encoding="utf-8")
        result = toolchain_mcp.probe_stdio([PY, str(script)], timeout=20)
        self.assertEqual("Srv at", result["server"]["name"])
        self.assertEqual("1.6.0+abc123", result["server"]["version"])


@unittest.skipUnless(WINDOWS, "command shims are a Windows matter")
class ShimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        script = cls.dir / "fake_server.py"
        script.write_text(FAKE_SERVER, encoding="utf-8")
        cls.shim = cls.dir / "tc-fake-shim.cmd"
        cls.shim.write_bytes(('@echo off\r\n"%s" "%s" %%*\r\n' % (PY, script)).encode("utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_a_server_started_through_a_cmd_shim_found_on_the_path(self):
        with mock.patch.dict(os.environ, {"PATH": str(self.dir) + os.pathsep + os.environ.get("PATH", "")}):
            result = toolchain_mcp.probe_stdio(["tc-fake-shim", "legacy"], cwd=str(self.dir), timeout=30)
        self.assertEqual(EXPECTED_TOOLS, result["tools"])

    def test_the_whole_chain_behind_a_shim_is_killed_on_a_timeout(self):
        pids = self.dir / "chain-pids.txt"
        with self.assertRaises(toolchain_mcp.McpProbeError) as caught:
            toolchain_mcp.probe_stdio([str(self.shim), "grandchild"], env={"FAKE_PIDFILE": str(pids)}, cwd=str(self.dir), timeout=3)
        self.assertEqual("timeout", caught.exception.code)
        found = read_pids(pids, seconds=1.0)
        self.assertEqual(2, len(found))
        for pid in found:
            self.assertTrue(wait_dead(pid, 5), "process %d is still running" % pid)

    def test_shell_syntax_in_an_argument_is_refused(self):
        with self.assertRaises(toolchain_mcp.McpProbeError) as caught:
            toolchain_mcp.probe_stdio([str(self.shim), "legacy&calc"], cwd=str(self.dir), timeout=5)
        self.assertEqual("spawn-failed", caught.exception.code)


class _FakeHttp:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def http(self, method, url, *, headers=None, body=None, timeout=20):
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body, "timeout": timeout})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class ProbeHttpTests(unittest.TestCase):
    def run_probe(self, result, **kwargs):
        runner = _FakeHttp(result)
        return toolchain_mcp.probe_http("https://mcp.example.test/v1", runner=runner, **kwargs), runner

    def test_two_hundred_is_open(self):
        for status in (200, 202):
            result, _ = self.run_probe(HttpResult(status, {}, b'{"result": {}}', None))
            self.assertEqual({"status": "open", "http_status": status}, result)

    def test_unauthorised_and_forbidden_need_a_sign_in(self):
        for status in (401, 403):
            result, _ = self.run_probe(HttpResult(status, {"www-authenticate": 'Bearer realm="private-realm"'}, b"", None))
            self.assertEqual({"status": "needs-sign-in", "http_status": status}, result)

    def test_everything_else_is_an_error(self):
        for status in (0, 301, 400, 404, 405, 429, 500, 503):
            result, _ = self.run_probe(HttpResult(status, {}, b"", "timeout" if status == 0 else None))
            self.assertEqual({"status": "error", "http_status": status}, result)

    def test_the_result_never_holds_a_body_a_session_id_a_challenge_or_the_address(self):
        answer = HttpResult(401, {"mcp-session-id": "session-value-123", "www-authenticate": "Bearer resource_metadata=secret-meta"},
                            b"secret-body-text", None)
        result, _ = self.run_probe(answer)
        text = json.dumps(result)
        for forbidden in ("session-value", "secret-meta", "secret-body", "mcp.example", "Bearer"):
            self.assertNotIn(forbidden, text)
        self.assertEqual({"status", "http_status"}, set(result))

    def test_the_request_is_an_initialize_post_that_accepts_json_and_event_streams(self):
        _, runner = self.run_probe(HttpResult(200, {}, b"", None), headers={"X-VARIANTS": "v1"})
        call = runner.calls[0]
        self.assertEqual("POST", call["method"])
        self.assertEqual("https://mcp.example.test/v1", call["url"])
        self.assertEqual("application/json, text/event-stream", call["headers"]["Accept"])
        self.assertEqual("application/json", call["headers"]["Content-Type"])
        self.assertEqual("v1", call["headers"]["X-VARIANTS"])
        body = json.loads(call["body"])
        self.assertEqual("initialize", body["method"])
        self.assertEqual("2.0", body["jsonrpc"])
        self.assertEqual("fabric-automation-toolchain", body["params"]["clientInfo"]["name"])

    def test_given_headers_can_override_the_defaults_but_not_leak_back(self):
        given = {"Accept": "application/json"}
        _, runner = self.run_probe(HttpResult(200, {}, b"", None), headers=given)
        self.assertEqual("application/json", runner.calls[0]["headers"]["Accept"])
        self.assertEqual({"Accept": "application/json"}, given)

    def test_the_timeout_is_passed_on(self):
        _, runner = self.run_probe(HttpResult(200, {}, b"", None), timeout=3.5)
        self.assertEqual(3.5, runner.calls[0]["timeout"])

    def test_a_runner_that_raises_still_gives_an_error_result(self):
        result, _ = self.run_probe(RuntimeError("boom at https://mcp.example.test"))
        self.assertEqual({"status": "error", "http_status": 0}, result)

    def test_the_default_runner_is_the_real_one(self):
        with mock.patch.object(toolchain_mcp, "SystemRunner") as system:
            system.return_value = _FakeHttp(HttpResult(200, {}, b"", None))
            self.assertEqual("open", toolchain_mcp.probe_http("https://mcp.example.test/v1")["status"])


def tool(schema="sha256:a", read_only=True, destructive=False, idempotent=True):
    return {"schema": schema, "read_only": read_only, "destructive": destructive, "idempotent": idempotent}


class ContractDiffTests(unittest.TestCase):
    def test_equal_contracts_have_no_difference(self):
        locked = {"a": tool(), "b": tool("sha256:b")}
        self.assertEqual({"added": [], "removed": [], "changed": []}, toolchain_mcp.contract_diff(locked, dict(locked)))

    def test_added_removed_and_changed_names_are_sorted(self):
        locked = {"keep": tool(), "gone-b": tool(), "gone-a": tool(), "edit-b": tool(), "edit-a": tool()}
        live = {"keep": tool(), "new-b": tool(), "new-a": tool(), "edit-b": tool("sha256:other"), "edit-a": tool(read_only=False)}
        self.assertEqual({"added": ["new-a", "new-b"], "removed": ["gone-a", "gone-b"], "changed": ["edit-a", "edit-b"]},
                         toolchain_mcp.contract_diff(locked, live))

    def test_each_compared_field_counts(self):
        base = {"t": tool()}
        for change in ({"schema": "sha256:z"}, {"read_only": False}, {"destructive": True}, {"idempotent": None}):
            live = {"t": dict(tool(), **change)}
            self.assertEqual(["t"], toolchain_mcp.contract_diff(base, live)["changed"], change)

    def test_fields_outside_the_contract_are_not_compared(self):
        self.assertEqual([], toolchain_mcp.contract_diff({"t": dict(tool(), note="x")}, {"t": dict(tool(), note="y")})["changed"])

    def test_empty_and_missing_inputs(self):
        self.assertEqual({"added": ["a"], "removed": [], "changed": []}, toolchain_mcp.contract_diff({}, {"a": tool()}))
        self.assertEqual({"added": [], "removed": ["a"], "changed": []}, toolchain_mcp.contract_diff({"a": tool()}, {}))
        self.assertEqual({"added": [], "removed": [], "changed": []}, toolchain_mcp.contract_diff(None, None))

    def test_the_inputs_are_not_changed(self):
        locked, live = {"a": tool()}, {"a": tool("sha256:z"), "b": tool()}
        before = json.dumps([locked, live], sort_keys=True)
        toolchain_mcp.contract_diff(locked, live)
        self.assertEqual(before, json.dumps([locked, live], sort_keys=True))


class CaptureEnvTests(unittest.TestCase):
    REQUIRED = ("PATH", "PATHEXT", "SystemRoot", "windir", "ComSpec", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
                "LANG", "LC_ALL", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "SSL_CERT_FILE", "NODE_EXTRA_CA_CERTS", "SystemDrive", "ProgramData")

    def test_the_allow_list_is_a_named_constant_with_what_a_process_needs_and_no_credential(self):
        listed = {name.upper() for name in toolchain_mcp.ENV_ALLOW_LIST}
        for name in self.REQUIRED:
            self.assertIn(name.upper(), listed, name)
        self.assertEqual(("npm_config_",), toolchain_mcp.ENV_ALLOW_PREFIXES)
        self.assertFalse([name for name in listed if name.startswith(("AZURE_", "PBI_", "GITHUB_", "NPM_", "NODE_OPTIONS"))])
        for name in ("AZURE_CLIENT_SECRET", "AZURE_CLIENT_ID", "AZURE_TENANT_ID", "PBI_MODELING_MCP_ALLOWED_CONNECTION_HOSTS", "NODE_OPTIONS",
                     "GITHUB_TOKEN", "NPM_TOKEN", "PYTHONPATH", "NODE_TLS_REJECT_UNAUTHORIZED"):
            self.assertNotIn(name, listed)

    def test_only_allow_listed_names_and_the_declared_ones_remain(self):
        parent = {"PATH": "p", "HOME": "h", "SECRET_X": "s", "AZURE_CLIENT_SECRET": "c", "npm_config_registry": "r", "NPM_TOKEN": "t"}
        self.assertEqual({"PATH": "p", "HOME": "h", "npm_config_registry": "r"}, toolchain_mcp.capture_env({}, parent))
        self.assertEqual({"PATH": "p", "HOME": "h", "npm_config_registry": "r"}, toolchain_mcp.capture_env(None, parent))
        self.assertEqual({}, toolchain_mcp.capture_env(None, {"SECRET_X": "s"}))

    def test_names_match_without_regard_to_case_and_the_prefix_needs_its_underscore(self):
        parent = {"Path": "p", "systemroot": "s", "Http_Proxy": "h", "NPM_CONFIG_X": "1", "npm_Config_y": "2", "NPM_CONFIGX": "no", "npm_config": "no"}
        self.assertEqual({"Path": "p", "systemroot": "s", "Http_Proxy": "h", "NPM_CONFIG_X": "1", "npm_Config_y": "2"}, toolchain_mcp.capture_env({}, parent))

    def test_declared_values(self):
        parent = {"SET": "from-parent", "EMPTY": "", "OTHER": "other-parent"}
        declared = {"A": {"from_env": "SET", "default": "d"}, "B": {"from_env": "EMPTY", "default": "d"}, "C": {"from_env": "UNSET", "default": "d"},
                    "D": {"from_env": "UNSET"}, "E": "literal", "F": {"from_env": "OTHER"}, "SET": {"default": "own"}, "G": None, "H": ""}
        self.assertEqual({"A": "from-parent", "B": "d", "C": "d", "E": "literal", "F": "other-parent", "SET": "from-parent", "H": ""},
                         toolchain_mcp.capture_env(declared, parent))

    def test_a_declared_variable_replaces_an_allow_listed_one_and_none_removes_it(self):
        parent = {"PATH": "from-parent", "HOME": "h"}
        self.assertEqual({"PATH": "declared", "HOME": "h"}, toolchain_mcp.capture_env({"PATH": "declared"}, parent))
        self.assertEqual({"HOME": "h"}, toolchain_mcp.capture_env({"PATH": None}, parent))

    @unittest.skipUnless(WINDOWS, "Windows names are not case sensitive")
    def test_on_windows_a_declared_name_replaces_the_same_name_in_another_case(self):
        self.assertEqual({"Path": "declared"}, toolchain_mcp.capture_env({"Path": "declared"}, {"PATH": "from-parent"}))

    def test_declarations_it_cannot_read_are_refused(self):
        for bad in ({"X": 5}, {"X": ["a"]}, {"X": {"default": 7}}, {"X": True}, {"": "v"}, {"A=B": "v"}, {"A\x00B": "v"}, {5: "v"}):
            with self.assertRaises(toolchain_mcp.McpProbeError) as caught:
                toolchain_mcp.capture_env(bad, {})
            self.assertEqual("spawn-failed", caught.exception.code, bad)

    def test_inputs_are_not_changed_and_the_default_parent_is_this_process(self):
        parent, declared = {"PATH": "p", "SECRET_X": "s"}, {"A": {"from_env": "PATH"}}
        before = json.dumps([parent, declared], sort_keys=True)
        toolchain_mcp.capture_env(declared, parent)
        self.assertEqual(before, json.dumps([parent, declared], sort_keys=True))
        with mock.patch.dict(os.environ, {"TC_PARENT_ONLY": "x", "PATH": "path-here"}):
            seen = toolchain_mcp.capture_env({"B": {"from_env": "TC_PARENT_ONLY"}})
        self.assertEqual("path-here", seen["PATH"])
        self.assertEqual("x", seen["B"])
        self.assertNotIn("TC_PARENT_ONLY", seen)


class DeadlineTests(unittest.TestCase):
    def test_an_expired_deadline_is_a_timeout_even_when_messages_are_waiting(self):
        server = object.__new__(toolchain_mcp._Server)
        server.lines = queue.Queue()
        server.last_id = 0
        server.proc = mock.Mock()
        for _ in range(5):
            server.lines.put(b'{"jsonrpc": "2.0", "method": "notifications/message"}\n')
        with self.assertRaises(toolchain_mcp.McpProbeError) as caught:
            server.call("tools/list", {}, time.monotonic() - 1)
        self.assertEqual("timeout", caught.exception.code)
        self.assertEqual(5, server.lines.qsize())

    def test_messages_that_are_not_the_answer_are_skipped_until_it_comes(self):
        server = object.__new__(toolchain_mcp._Server)
        server.lines = queue.Queue()
        server.last_id = 6
        server.proc = mock.Mock()
        for line in (b"not json\n", b'{"id": 99, "result": {}}\n', b'{"jsonrpc": "2.0", "method": "notifications/message"}\n',
                     b'{"jsonrpc": "2.0", "id": 7, "result": {"tools": []}}\n'):
            server.lines.put(line)
        answer = server.call("tools/list", {}, time.monotonic() + 5)
        self.assertEqual({"tools": []}, answer["result"])


class ProcessAliveHelperTests(unittest.TestCase):
    def test_the_liveness_helper_sees_this_process(self):
        self.assertTrue(pid_alive(os.getpid()))


if __name__ == "__main__":
    unittest.main()
