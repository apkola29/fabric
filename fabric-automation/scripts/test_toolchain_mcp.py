#!/usr/bin/env python3
"""Tests for toolchain_mcp.py: reading the tool contract of an MCP server and comparing two contracts.

The stdio tests run a stand-in server (a small Python script written to a temp folder and started with the
interpreter that runs the tests). The legacy mode follows the `initialize` handshake. The modern mode is built from
the 2026-07-28 revision of the specification (versioning, stdio transport, server/discover and tools pages), so those tests
show that the client follows the pages; real servers of that era, tried by hand outside this run, agreed.
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
starts_path = os.environ.get("FAKE_STARTS")
if starts_path:
    with open(starts_path, "a") as handle:
        handle.write("%d\n" % os.getpid())
if mode == "exit":
    sys.exit(3)
if mode in ("silent", "grandchild"):
    while True:
        time.sleep(0.2)
if mode in ("modern-slow", "modern-slow-named", "slow-legacy", "hybrid-locking"):
    time.sleep(3.0)


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
discover_result = {"resultType": "complete", "supportedVersions": ["2026-07-28"], "capabilities": {"tools": {}},
                   "_meta": {M + "serverInfo": {"name": "Fake Modern", "version": "2.0.0"}}, "ttlMs": 0}
loop_count = [0]
is_modern = mode.startswith("modern")
initialized = False
locked = False
held = []
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
    if mode == "exit-on-first":
        sys.exit(3)
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
        if mode == "exit-on-initialize":
            sys.exit(3)
        if mode == "modern-mute":
            continue
        if mode == "modern":
            fail(mid, -32022, "Unsupported protocol version", {"supported": ["2026-07-28", "2025-11-25"], "requested": params.get("protocolVersion")})
        elif mode == "modern-text":
            fail(mid, -32600, "This server only supports protocol versions 2026-07-28 and later")
        elif mode in ("modern-bare", "modern-slow"):
            fail(mid, -32601, "Method not found")
        elif mode in ("modern-via-initialize", "modern-slow-named"):
            fail(mid, -32022, "Unsupported protocol version", {"supported": ["2026-07-28"]})
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
            while held:
                reply(held.pop(), discover_result)
            if mode == "ping":
                send({"jsonrpc": "2.0", "id": "srv-1", "method": "ping"})
                waiting_for_ping = True
        continue
    if method == "notifications/initialized":
        initialized = True
        continue
    if method == "server/discover":
        if mode in ("modern", "modern-text", "modern-bare", "modern-mute", "modern-slow", "modern-slow-named") and modern_meta_ok(params):
            reply(mid, discover_result)
        elif mode == "hybrid-locking":
            locked = True
            held.append(mid)  # answered after initialize, the order seen with real servers that were sent both while they started
        elif mode == "modern-unsupported":
            fail(mid, -32022, "Unsupported protocol version", {"supported": ["2027-01-01"]})
        elif mode == "modern-other":
            reply(mid, {"resultType": "complete", "supportedVersions": ["2027-01-01"], "capabilities": {}})
        elif mode == "legacy-advertised":
            reply(mid, {"resultType": "complete", "supportedVersions": ["2027-01-01", "2025-11-25"], "capabilities": {}})
        elif mode == "exit-on-discover":
            sys.exit(3)
        elif mode == "ignore-discover":
            pass
        elif mode == "legacy-odd-discover":
            reply(mid, {})
        elif mode == "legacy-invalid-params":
            fail(mid, -32602, "Invalid params")
        else:
            fail(mid, -32601, "Method not found")
        continue
    if method == "tools/list":
        if mode == "hybrid-locking" and locked and not modern_meta_ok(params):
            fail(mid, -32600, "Invalid Request")
            continue
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
        self.starts = self.dir / ("starts-%s.txt" % self._testMethodName)
        # a stand-in that is meant to answer discover must not lose the race against a busy machine; the tests of the wait patch it again
        patcher = mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 30.0)
        patcher.start()
        self.addCleanup(patcher.stop)

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

    def test_legacy_messages_follow_the_handshake_in_order_after_the_discover_probe(self):
        self.probe("legacy")
        sent = self.messages()
        self.assertEqual(["server/discover", "initialize", "notifications/initialized", "tools/list"], [m["method"] for m in sent])
        discover, initialize = sent[0], sent[1]
        self.assertEqual("2026-07-28", discover["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"])
        self.assertEqual("2.0", initialize["jsonrpc"])
        self.assertEqual("2025-11-25", initialize["params"]["protocolVersion"])
        self.assertEqual({}, initialize["params"]["capabilities"])
        self.assertEqual("fabric-automation-toolchain", initialize["params"]["clientInfo"]["name"])
        self.assertIn("version", initialize["params"]["clientInfo"])
        self.assertNotIn("id", sent[2])
        self.assertNotIn("_meta", json.dumps(sent[1:]))

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

    def test_a_server_that_answers_discover_is_modern(self):
        result = self.probe("modern")
        self.assertEqual("modern", result["era"])
        self.assertEqual("2026-07-28", result["protocol"])
        self.assertEqual({"name": "Fake Modern", "version": "2.0.0"}, result["server"])
        self.assertEqual(EXPECTED_TOOLS, result["tools"])

    def test_modern_requests_carry_the_metadata_and_there_is_no_handshake(self):
        self.probe("modern")
        sent = self.messages()
        self.assertEqual(["server/discover", "tools/list"], [m["method"] for m in sent])
        meta = sent[0]["params"]["_meta"]
        self.assertEqual("2026-07-28", meta["io.modelcontextprotocol/protocolVersion"])
        self.assertEqual("fabric-automation-toolchain", meta["io.modelcontextprotocol/clientInfo"]["name"])
        self.assertEqual({}, meta["io.modelcontextprotocol/clientCapabilities"])
        self.assertEqual(meta, sent[1]["params"]["_meta"])

    def test_discover_is_the_first_request_and_initialize_is_never_sent_to_a_modern_server(self):
        for mode in ("modern", "modern-text", "modern-bare"):
            if self.log.exists():
                self.log.unlink()
            self.assertEqual("modern", self.probe(mode)["era"], mode)
            self.assertEqual(["server/discover", "tools/list"], [m["method"] for m in self.messages()], mode)

    def test_a_modern_server_that_ignores_initialize_is_captured(self):
        started = time.monotonic()
        result = self.probe("modern-mute", timeout=20)
        self.assertEqual(("modern", EXPECTED_TOOLS), (result["era"], result["tools"]))
        self.assertEqual(["server/discover", "tools/list"], [m["method"] for m in self.messages()])
        self.assertLess(time.monotonic() - started, 15)

    def test_a_server_that_errors_on_discover_gets_the_handshake_on_the_same_process(self):
        for mode in ("legacy", "legacy-invalid-params", "legacy-odd-discover"):
            for path in (self.log, self.starts):
                if path.exists():
                    path.unlink()
            result = self.probe(mode, env={"FAKE_STARTS": str(self.starts)})
            self.assertEqual(("legacy", EXPECTED_TOOLS), (result["era"], result["tools"]), mode)
            self.assertEqual(["server/discover", "initialize", "notifications/initialized", "tools/list"], [m["method"] for m in self.messages()], mode)
            self.assertEqual(1, len(self.starts.read_text().split()), "%s: the server was started again" % mode)

    def test_a_server_that_exits_on_discover_is_started_again_for_the_legacy_handshake(self):
        result = self.probe("exit-on-discover", env={"FAKE_STARTS": str(self.starts)})
        self.assertEqual(("legacy", EXPECTED_TOOLS), (result["era"], result["tools"]))
        started = [int(pid) for pid in self.starts.read_text().split()]
        self.assertEqual(2, len(started))
        self.assertEqual(["server/discover", "initialize", "notifications/initialized", "tools/list"], [m["method"] for m in self.messages()])
        for pid in started:
            self.assertTrue(wait_dead(pid, 5), "process %d is still running" % pid)

    def test_a_server_that_exits_on_every_request_is_started_twice_and_no_more(self):
        self.assertFails("exited", "exit-on-first", env={"FAKE_STARTS": str(self.starts)})
        started = [int(pid) for pid in self.starts.read_text().split()]
        self.assertEqual(2, len(started))
        self.assertEqual(["server/discover", "initialize"], [m["method"] for m in self.messages()])
        for pid in started:
            self.assertTrue(wait_dead(pid, 5), "process %d is still running" % pid)

    def test_a_server_that_never_answers_discover_is_started_again_for_the_handshake_after_a_short_wait(self):
        started = time.monotonic()
        with mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 0.7):
            result = self.probe("ignore-discover", env={"FAKE_STARTS": str(self.starts)}, timeout=30)
        self.assertEqual(("legacy", EXPECTED_TOOLS), (result["era"], result["tools"]))
        self.assertEqual(["server/discover", "initialize", "notifications/initialized", "tools/list"], [m["method"] for m in self.messages()])
        pids = [int(pid) for pid in self.starts.read_text().split()]
        self.assertEqual(2, len(pids))
        for pid in pids:
            self.assertTrue(wait_dead(pid, 5), "process %d is still running" % pid)
        self.assertLess(time.monotonic() - started, 25)

    def test_a_budget_that_ends_before_the_wait_is_a_timeout_and_no_handshake_follows(self):
        started = time.monotonic()
        with mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 30.0):
            self.assertFails("timeout", "ignore-discover", timeout=1.5)
        self.assertLess(time.monotonic() - started, 20)
        self.assertEqual(["server/discover"], [m["method"] for m in self.messages()])

    def test_an_unsupported_version_is_never_a_reason_to_fall_back_to_initialize(self):
        for mode in ("modern-unsupported", "modern-other"):
            if self.log.exists():
                self.log.unlink()
            self.assertIn("mutually", str(self.assertFails("protocol-error", mode)), mode)
            self.assertEqual(["server/discover"], [m["method"] for m in self.messages()], mode)

    def test_a_modern_server_that_is_slow_to_start_is_started_again_and_found_modern(self):
        with mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 0.5):
            result = self.probe("modern-slow", env={"FAKE_STARTS": str(self.starts)}, timeout=40)
        self.assertEqual(("modern", EXPECTED_TOOLS), (result["era"], result["tools"]))
        self.assertEqual({"name": "Fake Modern", "version": "2.0.0"}, result["server"])
        self.assertEqual(["initialize", "server/discover", "tools/list"], [m["method"] for m in self.messages()])
        self.assertEqual(2, len(self.starts.read_text().split()))

    def test_a_modern_server_that_names_its_versions_after_a_slow_start_gives_its_name_too(self):
        with mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 0.5):
            result = self.probe("modern-slow-named", env={"FAKE_STARTS": str(self.starts)}, timeout=40)
        self.assertEqual(("modern", EXPECTED_TOOLS), (result["era"], result["tools"]))
        self.assertEqual({"name": "Fake Modern", "version": "2.0.0"}, result["server"])
        self.assertEqual(["initialize", "server/discover", "tools/list"], [m["method"] for m in self.messages()])

    def test_a_legacy_server_that_is_slow_to_start_is_started_again_and_found_legacy(self):
        with mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 0.5):
            result = self.probe("slow-legacy", env={"FAKE_STARTS": str(self.starts)}, timeout=40)
        self.assertEqual(("legacy", EXPECTED_TOOLS), (result["era"], result["tools"]))
        self.assertEqual(["initialize", "notifications/initialized", "tools/list"], [m["method"] for m in self.messages()])
        self.assertEqual(2, len(self.starts.read_text().split()))

    def test_a_server_that_takes_its_era_from_the_first_request_never_sees_the_discover_that_was_given_up(self):
        # seen with real servers on a busy machine: one that was sent discover and then initialize answered initialize and then
        # refused the legacy tools/list as an invalid request, because discover had settled its era
        with mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 0.5):
            result = self.probe("hybrid-locking", env={"FAKE_STARTS": str(self.starts)}, timeout=40)
        self.assertEqual(("legacy", EXPECTED_TOOLS), (result["era"], result["tools"]))
        self.assertEqual(["initialize", "notifications/initialized", "tools/list"], [m["method"] for m in self.messages()])
        self.assertEqual(2, len(self.starts.read_text().split()))

    def test_an_initialize_error_that_names_modern_versions_after_a_failed_discover_is_modern_with_an_unknown_server(self):
        result = self.probe("modern-via-initialize")
        self.assertEqual(("modern", EXPECTED_TOOLS), (result["era"], result["tools"]))
        self.assertEqual({"name": "unknown", "version": "unknown"}, result["server"])
        self.assertEqual(["server/discover", "initialize", "tools/list"], [m["method"] for m in self.messages()])

    def test_a_discover_result_that_lists_only_handshake_versions_gets_the_handshake(self):
        result = self.probe("legacy-advertised")
        self.assertEqual(("legacy", EXPECTED_TOOLS), (result["era"], result["tools"]))
        self.assertEqual("2025-06-18", result["protocol"])
        self.assertEqual(["server/discover", "initialize", "notifications/initialized", "tools/list"], [m["method"] for m in self.messages()])

    def test_a_server_that_answered_discover_and_then_leaves_on_initialize_is_not_started_again(self):
        self.assertFails("exited", "exit-on-initialize", env={"FAKE_STARTS": str(self.starts)})
        started = [int(pid) for pid in self.starts.read_text().split()]
        self.assertEqual(1, len(started))
        self.assertEqual(["server/discover", "initialize"], [m["method"] for m in self.messages()])
        for pid in started:
            self.assertTrue(wait_dead(pid, 5), "process %d is still running" % pid)

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
            "        print(json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'result': {'tools': [{'name': 't', 'inputSchema': {}}]}}), flush=True)\n"
            "    elif 'id' in msg:\n"
            "        print(json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'error': {'code': -32601, 'message': 'Method not found'}}), flush=True)\n",
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
            "import json, os, sys\n"
            "info = json.loads(os.environ['TC_INFO'])\n"
            "for raw in sys.stdin:\n"
            "    msg = json.loads(raw)\n"
            "    if msg.get('method') == 'initialize':\n"
            "        print(json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'result': {'protocolVersion': '2025-06-18', 'serverInfo': info}}), flush=True)\n"
            "    elif msg.get('method') == 'tools/list':\n"
            "        print(json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'result': {'tools': [{'name': 't', 'inputSchema': {}}]}}), flush=True)\n"
            "    elif 'id' in msg:\n"
            "        print(json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'error': {'code': -32601, 'message': 'Method not found'}}), flush=True)\n",
            encoding="utf-8")
        hostile = {"name": "Srv at " + "https://feed" + ".example/x " + "C:" + chr(92) + "dir", "version": "1.6.0+abc123"}
        result = toolchain_mcp.probe_stdio([PY, str(script)], env={"TC_INFO": json.dumps(hostile)}, timeout=20)
        self.assertEqual({"name": "unknown", "version": "1.6.0+abc123"}, result["server"])
        path_name = "R:" + chr(92) + "scratch" + chr(92) + "ExampleUser" + chr(92) + "server"
        result = toolchain_mcp.probe_stdio([PY, str(script)], env={"TC_INFO": json.dumps({"name": path_name, "version": "build.private.example"})}, timeout=20)
        self.assertEqual({"name": "unknown", "version": "build.private.example"}, result["server"])
        result = toolchain_mcp.probe_stdio([PY, str(script)], env={"TC_INFO": json.dumps({"name": "Fake Server", "version": "1.2.3 beta"})}, timeout=20)
        self.assertEqual({"name": "Fake Server", "version": "unknown"}, result["server"])


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

    def setUp(self):
        patcher = mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 30.0)  # see StdioTests: the budget of each test is what ends it
        patcher.start()
        self.addCleanup(patcher.stop)

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


class ServerInfoTests(unittest.TestCase):
    """The server name and version of a captured contract are labels: a path, an address or a long string never reaches the lock."""

    def info(self, name, version="1.0.0"):
        return toolchain_mcp._server_info({"name": name, "version": version})

    def test_a_plain_name_and_version_pass_through(self):
        for name in ("Fake Server", "fabmcp", "my_server-2.0", "A", "x" * 64, "Microsoft.Fabric.Mcp"):
            self.assertEqual({"name": name, "version": "1.0.0"}, self.info(name), name)
        for version in ("1.6.0", "1.6.0+abc123", "2.0.0-rc.1", "build.private.example", "1" * 64, "v1_2~3"):
            self.assertEqual(version, self.info("n", version)["version"], version)

    def test_a_name_that_is_not_a_plain_label_is_unknown(self):
        names = ("R:" + "\\scratch\\" + "ExampleUser" + "\\server", "alice" + "@" + "example.test", "x" * 65, " lead", "-lead", ".lead", "a/b", "a:b",
                 "Srv\u00e9", "two\nlines", "tab\tname", "trailing\n", "", "https://" + "feed" + ".example/x", "a(b)", "a,b")
        for name in names:
            self.assertEqual("unknown", self.info(name)["name"], repr(name))

    def test_a_version_that_is_not_plain_is_unknown(self):
        versions = ("1.6.0 private", "a/b", "1" * 65, "~1.0", "+1", "-1", ".1", "1.0\n", "", "R:" + "\\x", "alice" + "@" + "x", "1.0 ", "v\u00e91")
        for version in versions:
            self.assertEqual("unknown", self.info("n", version)["version"], repr(version))

    def test_missing_and_non_text_values_are_unknown(self):
        for info in (None, {}, [], "text", 5, {"name": 5, "version": ["1"]}, {"name": None, "version": None}):
            self.assertEqual({"name": "unknown", "version": "unknown"}, toolchain_mcp._server_info(info), repr(info))


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
    NPM_NAMES = ("registry", "cache", "cafile", "ca", "strict_ssl", "ignore_scripts", "offline", "prefer_offline", "fund", "audit",
                 "update_notifier", "loglevel", "userconfig", "globalconfig", "prefix", "proxy", "https_proxy", "noproxy")
    USER = "alice:" + "s3cret"
    AT = "@"

    def test_the_allow_list_is_a_named_constant_with_what_a_process_needs_and_no_credential(self):
        listed = {name.upper() for name in toolchain_mcp.ENV_ALLOW_LIST}
        for name in self.REQUIRED:
            self.assertIn(name.upper(), listed, name)
        self.assertFalse(hasattr(toolchain_mcp, "ENV_ALLOW_PREFIXES"), "a prefix rule lets credentials of the npm configuration through")
        self.assertFalse([name for name in listed if name.startswith(("AZURE_", "PBI_", "GITHUB_", "NPM_", "NODE_OPTIONS"))])
        for name in ("AZURE_CLIENT_SECRET", "AZURE_CLIENT_ID", "AZURE_TENANT_ID", "PBI_MODELING_MCP_ALLOWED_CONNECTION_HOSTS", "NODE_OPTIONS",
                     "GITHUB_TOKEN", "NPM_TOKEN", "PYTHONPATH", "NODE_TLS_REJECT_UNAUTHORIZED"):
            self.assertNotIn(name, listed)

    def test_the_npm_settings_that_pass_are_a_fixed_set_of_names(self):
        self.assertEqual(set(self.NPM_NAMES), set(toolchain_mcp.ENV_ALLOW_NPM))
        self.assertEqual(len(self.NPM_NAMES), len(toolchain_mcp.ENV_ALLOW_NPM))

    def test_only_allow_listed_names_and_the_declared_ones_remain(self):
        parent = {"PATH": "p", "HOME": "h", "SECRET_X": "s", "AZURE_CLIENT_SECRET": "c", "npm_config_registry": "r", "NPM_TOKEN": "t"}
        self.assertEqual({"PATH": "p", "HOME": "h", "npm_config_registry": "r"}, toolchain_mcp.capture_env({}, parent))
        self.assertEqual({"PATH": "p", "HOME": "h", "npm_config_registry": "r"}, toolchain_mcp.capture_env(None, parent))
        self.assertEqual({}, toolchain_mcp.capture_env(None, {"SECRET_X": "s"}))

    def test_every_named_npm_setting_passes_in_either_spelling_and_in_mixed_case(self):
        parent = {}
        for index, name in enumerate(self.NPM_NAMES):
            spelling = ("npm_config_", "NPM_CONFIG_", "Npm_Config_")[index % 3]
            parent[spelling + name] = "proxy.example.test:8080" if name in ("proxy", "https_proxy", "registry") else "value-%d" % index
        self.assertEqual(parent, toolchain_mcp.capture_env({}, parent))

    def test_no_other_npm_setting_passes_least_of_all_one_that_holds_a_credential(self):
        hostile = {"npm_config_//registry.npmjs.org/:_authToken": "t", "npm_config_//registry.npmjs.org/:_auth": "a", "NPM_CONFIG__AUTH": "a",
                   "npm_config__authToken": "t", "npm_config__auth": "a", "npm_config__password": "p", "npm_config_username": "u",
                   "npm_config_certfile": "c", "npm_config_keyfile": "k", "NPM_CONFIG_ALWAYS_AUTH": "true", "npm_config_email": "e",
                   "npm_config_otp": "1", "npm_config_foo": "x", "npm_config_": "x", "npm_config_registry_extra": "x", "NPM_TOKEN": "t",
                   "NPM_CONFIG": "x", "npm_config_https-proxy": "x", "npm_config_cache_min": "1"}
        parent = dict(hostile, npm_config_registry="registry.example.test", NPM_CONFIG_LOGLEVEL="warn")
        self.assertEqual({"npm_config_registry": "registry.example.test", "NPM_CONFIG_LOGLEVEL": "warn"}, toolchain_mcp.capture_env({}, parent))

    def test_names_match_without_regard_to_case(self):
        parent = {"Path": "p", "systemroot": "s", "Http_Proxy": "proxy.example.test:3128", "NPM_CONFIGX": "no", "npm_config": "no"}
        self.assertEqual({"Path": "p", "systemroot": "s", "Http_Proxy": "proxy.example.test:3128"}, toolchain_mcp.capture_env({}, parent))

    def test_the_credentials_of_a_proxy_address_are_removed_and_the_rest_is_kept(self):
        user, at = self.USER, self.AT
        cases = (("http://" + user + at + "proxy.example.test:8080", "http://proxy.example.test:8080"),
                 ("https://" + user + at + "proxy.example.test:8443/", "https://proxy.example.test:8443/"),
                 ("socks5://" + user + at + "proxy.example.test:1080", "socks5://proxy.example.test:1080"),
                 ("http://alice" + at + "proxy.example.test", "http://proxy.example.test"),
                 ("http://alice:p" + at + "ss" + at + "proxy.example.test:8080", "http://proxy.example.test:8080"),
                 ("http://alice:p%40ss" + at + "proxy.example.test:8080", "http://proxy.example.test:8080"),
                 (user + at + "proxy.example.test:3128", "proxy.example.test:3128"),
                 ("http://" + user + at + "[::1]:3128", "http://[::1]:3128"),
                 ("http://[::1]", "http://[::1]"),
                 ("http://" + user + at + "[2001:db8::1]", "http://[2001:db8::1]"),
                 ("http://proxy.example.test:3128", "http://proxy.example.test:3128"),
                 ("http://proxy.example.test:3128/path?token=abc#frag", "http://proxy.example.test:3128/path"),
                 ("proxy.example.test:3128", "proxy.example.test:3128"))
        names = ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy", "npm_config_proxy", "NPM_CONFIG_HTTPS_PROXY",
                 "npm_config_https_proxy", "NPM_CONFIG_PROXY", "npm_config_registry", "NPM_CONFIG_REGISTRY")
        for name in names:
            for value, expected in cases:
                self.assertEqual({name: expected}, toolchain_mcp.capture_env({}, {name: value}), "%s=%s" % (name, value.replace(user, "***")))

    def test_a_proxy_address_that_cannot_be_read_is_dropped(self):
        at = self.AT
        for value in ("http://", "://proxy.example.test", "http://proxy.example.test:port", "http://proxy.example.test:99999", "http://exa mple.test",
                      "http://" + self.USER + at, "::::", "", "  ", "http://proxy.example.test\n:80", "ht tp://proxy.example.test", "-x://h",
                      "http://" + self.USER + at + ":80", "http://pro\x00xy.example.test", "http://a.b:1:2", "http://[::1", "http://:80",
                      "http://proxy.example.test:0", "http://alice:pa/ss" + at + "proxy.example.test", "http://proxy.example.test:\u00b2",
                      "http://proxy.example.test/a b", "http://proxy.example.test/a\nb"):
            for name in ("HTTPS_PROXY", "npm_config_proxy", "npm_config_registry"):
                self.assertEqual({}, toolchain_mcp.capture_env({}, {name: value}), "%s=%r" % (name, value.replace(self.USER, "***")))
        self.assertEqual({}, toolchain_mcp.capture_env({}, {"HTTP_PROXY": 5}))

    def test_a_no_proxy_list_and_the_other_settings_are_not_changed(self):
        parent = {"NO_PROXY": "localhost,.example.test," + self.USER + self.AT + "x", "npm_config_noproxy": "a,b", "SSL_CERT_FILE": "ca.pem"}
        self.assertEqual(parent, toolchain_mcp.capture_env({}, parent))

    def test_a_declared_value_is_passed_as_declared(self):
        declared = {"HTTP_PROXY": "http://" + self.USER + self.AT + "proxy.example.test:8080", "npm_config_registry": "http://" + self.USER + self.AT + "feed.example.test/"}
        self.assertEqual(declared, toolchain_mcp.capture_env(declared, {}))

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


class ModernAnswerTests(unittest.TestCase):
    def test_a_result_that_lists_our_version_is_modern_and_gives_the_server_info(self):
        answer = {"result": {"supportedVersions": ["2026-07-28"], "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "Some Server", "version": "3.4.5"}}}}
        self.assertEqual({"name": "Some Server", "version": "3.4.5"}, toolchain_mcp._modern_answer(answer))

    def test_a_modern_result_without_a_usable_server_info_has_an_unknown_one(self):
        unknown = {"name": "unknown", "version": "unknown"}
        for result in ({"supportedVersions": ["2026-07-28"]}, {"supportedVersions": ["2026-07-28"], "_meta": "text"},
                       {"supportedVersions": ["2026-07-28"], "_meta": {"io.modelcontextprotocol/serverInfo": "text"}}):
            self.assertEqual(unknown, toolchain_mcp._modern_answer({"result": result}), result)

    def test_our_version_wins_when_older_ones_are_listed_too(self):
        info = toolchain_mcp._modern_answer({"result": {"supportedVersions": ["2025-11-25", "2026-07-28"]}})
        self.assertEqual({"name": "unknown", "version": "unknown"}, info)

    def test_a_result_that_lists_a_version_of_the_handshake_era_is_a_legacy_advertisement(self):
        for version in ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"):
            self.assertIsNone(toolchain_mcp._modern_answer({"result": {"supportedVersions": [version]}}), version)
        self.assertIsNone(toolchain_mcp._modern_answer({"result": {"supportedVersions": ["2027-01-01", "2025-11-25"]}}))

    def test_a_result_that_lists_none_of_our_versions_is_a_protocol_error(self):
        for listed in ([], ["2027-01-01"], ["zzz"], [None, 5, {"a": 1}], ["2025-11-26"]):
            with self.assertRaises(toolchain_mcp.McpProbeError) as caught:
                toolchain_mcp._modern_answer({"result": {"supportedVersions": listed}})
            self.assertEqual("protocol-error", caught.exception.code, listed)
            self.assertIn("mutually", str(caught.exception))

    def test_the_unsupported_version_error_is_a_protocol_error_whatever_it_lists(self):
        for data in (None, {"supported": ["2025-11-25"]}, {"supported": ["2027-01-01"]}, {"supported": ["2026-07-28"]}, "text"):
            error = {"code": -32022, "message": "Unsupported protocol version"}
            if data is not None:
                error["data"] = data
            with self.assertRaises(toolchain_mcp.McpProbeError) as caught:
                toolchain_mcp._modern_answer({"error": error})
            self.assertEqual("protocol-error", caught.exception.code, data)

    def test_everything_else_is_not_modern(self):
        for answer in ({"error": {"code": -32601, "message": "Method not found"}}, {"error": {"code": -32602}}, {"error": {"code": -32021}},
                       {"error": "text"}, {"result": {}}, {"result": {"supportedVersions": "2026-07-28"}}, {"result": []}, {"result": None}, {}):
            self.assertIsNone(toolchain_mcp._modern_answer(answer), answer)


class DiscoverTests(unittest.TestCase):
    def server(self, answer=None, error=None):
        server = mock.Mock()
        if error is not None:
            server.call.side_effect = error
        else:
            server.call.return_value = answer
        return server

    def test_the_wait_for_discover_is_a_short_named_constant(self):
        self.assertIsInstance(toolchain_mcp.DISCOVER_WAIT, float)
        self.assertGreater(toolchain_mcp.DISCOVER_WAIT, 0)
        self.assertLessEqual(toolchain_mcp.DISCOVER_WAIT, 5.0)

    def test_discover_carries_the_metadata_and_waits_for_the_shorter_of_the_wait_and_the_budget(self):
        answer = {"result": {"supportedVersions": ["2026-07-28"]}}
        now = time.monotonic()
        deadline = now + 100
        server = self.server(answer)
        with mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 5.0):
            info = toolchain_mcp._discover(server, deadline)
        method, params, limit = server.call.call_args.args
        self.assertEqual("server/discover", method)
        self.assertEqual({"_meta": toolchain_mcp._meta()}, params)
        self.assertTrue(now + 4.9 <= limit <= now + 8.0, limit - now)
        self.assertEqual({"name": "unknown", "version": "unknown"}, info)
        server = self.server(answer)
        with mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 500.0):
            toolchain_mcp._discover(server, deadline)
        self.assertEqual(deadline, server.call.call_args.args[2])

    def test_an_answer_that_is_not_modern_is_none(self):
        for answer in ({"error": {"code": -32601, "message": "Method not found"}}, {"result": {}}):
            self.assertIsNone(toolchain_mcp._discover(self.server(answer), time.monotonic() + 10), answer)

    def test_a_server_that_stays_silent_is_the_silent_marker(self):
        server = self.server(error=toolchain_mcp.McpProbeError("timeout: no answer to server/discover"))
        with mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 0.01):
            self.assertIs(toolchain_mcp._SILENT, toolchain_mcp._discover(server, time.monotonic() + 100))

    def test_a_budget_that_ends_before_the_wait_is_a_timeout(self):
        server = self.server(error=toolchain_mcp.McpProbeError("timeout: no answer to server/discover"))
        with mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 500.0):
            with self.assertRaises(toolchain_mcp.McpProbeError) as caught:
                toolchain_mcp._discover(server, time.monotonic() + 1)
        self.assertEqual("timeout", caught.exception.code)

    def test_every_failure_but_a_timeout_is_raised(self):
        for code in ("exited", "protocol-error", "spawn-failed"):
            server = self.server(error=toolchain_mcp.McpProbeError(code + ": x"))
            with mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 0.01):
                with self.assertRaises(toolchain_mcp.McpProbeError) as caught:
                    toolchain_mcp._discover(server, time.monotonic() + 100)
            self.assertEqual(code, caught.exception.code)


class ScriptedServer:
    """Answers the requests it is sent from a list, in order; an item that is an exception is raised instead."""

    def __init__(self, *steps):
        self.steps, self.sent = list(steps), []

    def call(self, method, params, deadline):
        self.sent.append(method)
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    def notify(self, method):
        self.sent.append(method)


class ScriptedSession:
    def __init__(self, *servers):
        self.servers = list(servers)
        self.server = self.servers.pop(0)
        self.restarts = 0

    def restart(self):
        self.restarts += 1
        self.server = self.servers.pop(0)


TOOLS_ANSWER = {"result": {"tools": [{"name": "t", "inputSchema": {}}]}}
MODERN_ANSWER_OF_SOME_SERVER = {"result": {"supportedVersions": ["2026-07-28"],
                                           "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "Some Server", "version": "1.0"}}}}
LEGACY_ANSWER = {"result": {"protocolVersion": "2025-06-18", "serverInfo": {"name": "Old Server", "version": "0.1"}}}
NOT_FOUND = {"error": {"code": -32601, "message": "Method not found"}}
NAMES_MODERN = {"error": {"code": -32022, "message": "Unsupported protocol version", "data": {"supported": ["2026-07-28"]}}}
NAMES_OTHERS = {"error": {"code": -32022, "message": "Unsupported protocol version", "data": {"supported": ["2027-01-01"]}}}
NO_ANSWER = toolchain_mcp.McpProbeError("timeout: no answer to server/discover")
UNKNOWN_SERVER = {"name": "unknown", "version": "unknown"}


class InitializeTests(unittest.TestCase):
    def start(self, answered, *steps):
        server = ScriptedServer(*steps)
        with mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 0.01):
            return server, toolchain_mcp._initialize(server, time.monotonic() + 100, answered)

    def fails(self, answered, *steps):
        server = ScriptedServer(*steps)
        with mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 0.01):
            with self.assertRaises(toolchain_mcp.McpProbeError) as caught:
                toolchain_mcp._initialize(server, time.monotonic() + 100, answered)
        return server, caught.exception

    def test_a_server_that_accepts_initialize_is_legacy_and_is_not_asked_about_discover_again(self):
        for answered in (True, False):
            server, result = self.start(answered, LEGACY_ANSWER, TOOLS_ANSWER)
            self.assertEqual(("legacy", "2025-06-18", {"name": "Old Server", "version": "0.1"}), (result["era"], result["protocol"], result["server"]))
            self.assertEqual(["initialize", "notifications/initialized", "tools/list"], server.sent)

    def test_a_refusal_after_a_discover_that_was_never_answered_asks_discover_once_more(self):
        server, result = self.start(False, NOT_FOUND, MODERN_ANSWER_OF_SOME_SERVER, TOOLS_ANSWER)
        self.assertEqual(("modern", {"name": "Some Server", "version": "1.0"}), (result["era"], result["server"]))
        self.assertEqual(["initialize", "server/discover", "tools/list"], server.sent)

    def test_a_refusal_after_a_discover_that_was_answered_is_a_protocol_error_without_asking_again(self):
        server, error = self.fails(True, NOT_FOUND)
        self.assertEqual("protocol-error", error.code)
        self.assertIn("initialize failed with code -32601", str(error))
        self.assertEqual(["initialize"], server.sent)

    def test_a_refusal_that_discover_does_not_explain_is_a_protocol_error(self):
        for second in (NO_ANSWER, NOT_FOUND, {"result": {}}):
            server, error = self.fails(False, NOT_FOUND, second)
            self.assertEqual("protocol-error", error.code)
            self.assertIn("initialize failed with code -32601", str(error))
            self.assertEqual(["initialize", "server/discover"], server.sent)

    def test_a_refusal_that_discover_answers_with_other_versions_is_the_error_about_versions(self):
        for second in (NAMES_OTHERS, {"result": {"supportedVersions": ["2027-01-01"]}}):
            server, error = self.fails(False, NOT_FOUND, second)
            self.assertEqual("protocol-error", error.code)
            self.assertIn("mutually", str(error))

    def test_an_error_that_names_modern_versions_gives_the_name_that_discover_gives(self):
        server, result = self.start(False, NAMES_MODERN, MODERN_ANSWER_OF_SOME_SERVER, TOOLS_ANSWER)
        self.assertEqual(("modern", {"name": "Some Server", "version": "1.0"}), (result["era"], result["server"]))
        self.assertEqual(["initialize", "server/discover", "tools/list"], server.sent)

    def test_an_error_that_names_modern_versions_after_an_answered_discover_has_an_unknown_server_and_no_second_discover(self):
        server, result = self.start(True, NAMES_MODERN, TOOLS_ANSWER)
        self.assertEqual(("modern", UNKNOWN_SERVER), (result["era"], result["server"]))
        self.assertEqual(["initialize", "tools/list"], server.sent)

    def test_an_error_that_names_modern_versions_is_modern_even_when_discover_stays_silent_or_errs(self):
        for second in (NO_ANSWER, NOT_FOUND):
            server, result = self.start(False, NAMES_MODERN, second, TOOLS_ANSWER)
            self.assertEqual(("modern", UNKNOWN_SERVER), (result["era"], result["server"]))
            self.assertEqual(["initialize", "server/discover", "tools/list"], server.sent)

    def test_an_error_that_names_modern_versions_and_a_discover_with_other_versions_is_the_error_about_versions(self):
        server, error = self.fails(False, NAMES_MODERN, NAMES_OTHERS)
        self.assertEqual("protocol-error", error.code)
        self.assertIn("mutually", str(error))


class ProbeDecisionTests(unittest.TestCase):
    def probe(self, *servers):
        session = ScriptedSession(*servers)
        with mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 0.01):
            return session, toolchain_mcp._probe(session, time.monotonic() + 100)

    def fails(self, *servers):
        session = ScriptedSession(*servers)
        with mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 0.01):
            with self.assertRaises(toolchain_mcp.McpProbeError) as caught:
                toolchain_mcp._probe(session, time.monotonic() + 100)
        return session, caught.exception

    def test_a_server_that_answers_discover_as_a_modern_one_is_not_started_again(self):
        first = ScriptedServer(MODERN_ANSWER_OF_SOME_SERVER, TOOLS_ANSWER)
        session, result = self.probe(first)
        self.assertEqual(("modern", 0), (result["era"], session.restarts))
        self.assertEqual(["server/discover", "tools/list"], first.sent)

    def test_a_server_that_answers_discover_with_an_error_gets_the_handshake_on_the_same_process(self):
        first = ScriptedServer(NOT_FOUND, LEGACY_ANSWER, TOOLS_ANSWER)
        session, result = self.probe(first)
        self.assertEqual(("legacy", 0), (result["era"], session.restarts))
        self.assertEqual(["server/discover", "initialize", "notifications/initialized", "tools/list"], first.sent)

    def test_a_server_that_stays_silent_is_replaced_before_the_handshake(self):
        first, second = ScriptedServer(NO_ANSWER), ScriptedServer(LEGACY_ANSWER, TOOLS_ANSWER)
        session, result = self.probe(first, second)
        self.assertEqual(("legacy", 1), (result["era"], session.restarts))
        self.assertEqual(["server/discover"], first.sent)
        self.assertEqual(["initialize", "notifications/initialized", "tools/list"], second.sent)

    def test_a_server_that_exits_is_replaced_before_the_handshake(self):
        first, second = ScriptedServer(toolchain_mcp.McpProbeError("exited: code 3")), ScriptedServer(LEGACY_ANSWER, TOOLS_ANSWER)
        session, result = self.probe(first, second)
        self.assertEqual(("legacy", 1), (result["era"], session.restarts))
        self.assertEqual(["initialize", "notifications/initialized", "tools/list"], second.sent)

    def test_a_replacement_that_is_modern_is_found_by_discover_after_a_refused_initialize(self):
        first, second = ScriptedServer(NO_ANSWER), ScriptedServer(NOT_FOUND, MODERN_ANSWER_OF_SOME_SERVER, TOOLS_ANSWER)
        session, result = self.probe(first, second)
        self.assertEqual(("modern", {"name": "Some Server", "version": "1.0"}, 1), (result["era"], result["server"], session.restarts))
        self.assertEqual(["initialize", "server/discover", "tools/list"], second.sent)

    def test_nothing_but_silence_or_an_exit_replaces_the_server(self):
        for failure in ("protocol-error: a line is longer than the limit", "timeout: no answer to server/discover", "spawn-failed: x"):
            first = ScriptedServer(toolchain_mcp.McpProbeError(failure))
            with mock.patch.object(toolchain_mcp, "DISCOVER_WAIT", 500.0):
                session = ScriptedSession(first)
                with self.assertRaises(toolchain_mcp.McpProbeError) as caught:
                    toolchain_mcp._probe(session, time.monotonic() + 100)
            self.assertEqual(failure.split(":")[0], caught.exception.code)
            self.assertEqual(0, session.restarts, failure)
            self.assertEqual(["server/discover"], first.sent)

    def test_a_replacement_that_leaves_too_ends_the_probe(self):
        first = ScriptedServer(toolchain_mcp.McpProbeError("exited: code 3"))
        second = ScriptedServer(toolchain_mcp.McpProbeError("exited: code 3"))
        session, error = self.fails(first, second)
        self.assertEqual(("exited", 1), (error.code, session.restarts))

    def test_a_version_error_on_discover_is_never_answered_with_a_new_server(self):
        first = ScriptedServer(NAMES_OTHERS)
        session, error = self.fails(first)
        self.assertEqual(("protocol-error", 0), (error.code, session.restarts))
        self.assertEqual(["server/discover"], first.sent)


class SessionTests(unittest.TestCase):
    def test_a_restart_closes_the_old_server_first_and_starts_the_new_one_the_same_way(self):
        events = []

        class Recorded:
            count = 0

            def __init__(self, argv, env, cwd):
                Recorded.count += 1
                self.number = Recorded.count
                events.append(("start", self.number, list(argv), dict(env), cwd))

            def close(self):
                events.append(("close", self.number))

        with mock.patch.object(toolchain_mcp, "_Server", Recorded):
            session = toolchain_mcp._Session(["srv", "--x"], {"A": "1"}, "somewhere")
            first = session.server
            session.restart()
            self.assertIsNot(first, session.server)
            session.close()
        self.assertEqual([("start", 1, ["srv", "--x"], {"A": "1"}, "somewhere"), ("close", 1),
                          ("start", 2, ["srv", "--x"], {"A": "1"}, "somewhere"), ("close", 2)], events)


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
