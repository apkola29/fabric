#!/usr/bin/env python3
"""Tests for toolchain_io.py: the runner that every other toolchain module uses for child processes and HTTP.

They run real child processes (the interpreter that runs the tests) and a server on the loopback
address. Nothing leaves the machine and the real home folder is never read. Run from the project folder:

    python -m unittest scripts.test_toolchain_io -v
"""

import http.client
import http.server
import json
import os
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import toolchain_io  # noqa: E402
from toolchain_io import CommandResult, HttpResult, SystemRunner  # noqa: E402

PY = sys.executable
WINDOWS = os.name == "nt"

# Spawns a grandchild that sleeps, records both process ids, then sleeps itself.
TREE_SCRIPT = (
    "import os, subprocess, sys, time\n"
    "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
    "with open(sys.argv[1], 'w') as handle:\n"
    "    handle.write('%d %d' % (os.getpid(), child.pid))\n"
    "time.sleep(120)\n"
)


def pid_alive(pid):
    if WINDOWS:
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = kernel.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel.CloseHandle(handle)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_dead(pid, seconds=10.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if not pid_alive(pid):
            return True
        time.sleep(0.1)
    return not pid_alive(pid)


def read_pids(path, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            text = Path(path).read_text()
            if len(text.split()) == 2:
                return [int(part) for part in text.split()]
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    return []


class RunTests(unittest.TestCase):
    def setUp(self):
        self.runner = SystemRunner()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_captures_output_and_exit_code(self):
        result = self.runner.run([PY, "-c", "import sys; print('out'); sys.stderr.write('err'); sys.exit(3)"])
        self.assertIsInstance(result, CommandResult)
        self.assertEqual(3, result.returncode)
        self.assertEqual("out", result.stdout.strip())
        self.assertEqual("err", result.stderr.strip())

    def test_missing_executable_is_127_and_never_raises(self):
        self.assertEqual(CommandResult(127, "", "not found"), self.runner.run(["no-such-command-xyz-123"]))
        self.assertEqual(127, self.runner.run([]).returncode)
        self.assertEqual(127, self.runner.run([""]).returncode)

    def test_input_reaches_standard_input(self):
        script = "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read().decode('utf-8').upper().encode('utf-8'))"
        result = self.runner.run([PY, "-c", script], input="hello \u00e9")
        self.assertEqual("HELLO \u00c9", result.stdout)

    def test_environment_is_an_overlay_and_none_removes(self):
        probe = "import os; print(os.environ.get('TC_A'), os.environ.get('TC_B'), 'PATH' in os.environ or 'Path' in os.environ)"
        with mock.patch.dict(os.environ, {"TC_B": "inherited"}):
            result = self.runner.run([PY, "-c", probe], env={"TC_A": "given"})
            self.assertEqual("given inherited True", result.stdout.strip())
            result = self.runner.run([PY, "-c", probe], env={"TC_B": None})
            self.assertEqual("None None True", result.stdout.strip())

    def test_working_directory(self):
        result = self.runner.run([PY, "-c", "import os; print(os.getcwd())"], cwd=self.tmp.name)
        self.assertEqual(os.path.realpath(self.tmp.name).lower(), os.path.realpath(result.stdout.strip()).lower())

    def test_invalid_utf8_is_replaced(self):
        result = self.runner.run([PY, "-c", "import sys; sys.stdout.buffer.write(b'a\\xff\\xfeb')"])
        self.assertEqual("a\ufffd\ufffdb", result.stdout)

    def test_line_endings_are_not_translated(self):
        result = self.runner.run([PY, "-c", "import sys; sys.stdout.buffer.write(b'a\\r\\nb\\n')"])
        self.assertEqual("a\r\nb\n", result.stdout)

    def test_timeout_is_124_keeps_partial_output_and_kills_the_whole_tree(self):
        pidfile = Path(self.tmp.name) / "pids.txt"
        started = time.monotonic()
        result = self.runner.run([PY, "-c", TREE_SCRIPT, str(pidfile)], timeout=4)
        self.assertEqual(124, result.returncode)
        self.assertLess(time.monotonic() - started, 40)
        pids = read_pids(pidfile)
        self.assertEqual(2, len(pids), "the child never wrote its process ids")
        for pid in pids:
            self.assertTrue(wait_dead(pid), "process %d is still running after the timeout" % pid)

    def test_timeout_returns_the_output_written_so_far(self):
        script = "import sys, time; print('partial', flush=True); time.sleep(120)"
        result = self.runner.run([PY, "-c", script], timeout=3)
        self.assertEqual(124, result.returncode)
        self.assertIn("partial", result.stdout)

    def test_unusable_input_never_raises(self):
        self.assertEqual(126, self.runner.run([PY, "-c", "pass", "bad\x00arg"]).returncode)
        self.assertEqual(127, self.runner.run([PY], cwd=str(Path(self.tmp.name) / "missing")).returncode)

    def test_which_finds_a_path_and_rejects_the_rest(self):
        self.assertTrue(self.runner.which(PY))
        self.assertIsNone(self.runner.which("no-such-command-xyz-123"))
        self.assertIsNone(self.runner.which(""))
        self.assertIsNone(self.runner.which(None))


@unittest.skipUnless(WINDOWS, "command shims are a Windows matter")
class ShimTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.shim = self.dir / "tc-echo-shim.cmd"
        self.shim.write_bytes(b"@echo off\r\necho first=%1\r\necho second=%2\r\n")
        self.runner = SystemRunner()

    def test_a_cmd_shim_runs_with_its_arguments(self):
        result = self.runner.run([str(self.shim), "one", "two words"])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("first=one", result.stdout)
        self.assertIn('second="two words"', result.stdout)

    def test_a_shim_is_found_by_name_through_the_path(self):
        with mock.patch.dict(os.environ, {"PATH": str(self.dir) + os.pathsep + os.environ.get("PATH", "")}):
            found = self.runner.which("tc-echo-shim")
            self.assertTrue(found and found.lower().endswith(".cmd"))
            result = self.runner.run(["tc-echo-shim", "x"])
            self.assertIn("first=x", result.stdout)

    def test_shell_metacharacters_are_refused_before_a_shim_runs(self):
        marker = self.dir / "injected.txt"
        for argument in ("a&echo x>" + str(marker), "a|b", "a<b", 'a"b', "a^b", "%PATH%"):
            result = self.runner.run([str(self.shim), argument])
            self.assertEqual(126, result.returncode, argument)
            self.assertEqual("", result.stdout)
        self.assertFalse(marker.exists())


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def reply(self, status, body=b"", headers=()):
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_request(self):
        length = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(length) if length else b""
        port = self.server.server_address[1]
        path = self.path
        if path == "/ok":
            self.reply(200, b'{"a": 1}', [("Content-Type", "application/json"), ("X-Test", "Value")])
        elif path == "/echo":
            echo = {"method": self.command, "body": data.decode("utf-8"), "custom": self.headers.get("X-Custom"),
                    "agent": self.headers.get("User-Agent")}
            self.reply(200, json.dumps(echo).encode("utf-8"))
        elif path == "/missing":
            self.reply(404, b"nope")
        elif path == "/same":
            self.reply(302, b"", [("Location", "/ok")])
        elif path == "/other":
            self.reply(302, b"", [("Location", "http://localhost:%d/ok" % port)])
        elif path == "/loop":
            self.reply(302, b"", [("Location", "/loop")])
        elif path == "/big":
            self.send_response(200)
            self.send_header("Content-Length", str(6 * 1024 * 1024))
            self.end_headers()
            try:
                for _ in range(6):
                    self.wfile.write(b"a" * 1024 * 1024)
            except OSError:
                pass
        elif path == "/slow":
            time.sleep(2.0)
            self.reply(200, b"late")
        elif path == "/auth":
            self.reply(401, b"", [("WWW-Authenticate", 'Bearer realm="x"'), ("Set-Cookie", "a=1"), ("Set-Cookie", "b=2")])
        else:
            self.reply(404, b"")

    do_GET = do_POST = do_HEAD = do_PUT = handle_request


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = _Server(("127.0.0.1", 0), _Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.runner = SystemRunner()

    def url(self, path):
        return "http://127.0.0.1:%d%s" % (self.port, path)

    def test_get_returns_status_lowercase_headers_and_body(self):
        result = self.runner.http("GET", self.url("/ok"))
        self.assertIsInstance(result, HttpResult)
        self.assertEqual(200, result.status)
        self.assertEqual("Value", result.headers["x-test"])
        self.assertEqual("application/json", result.headers["content-type"])
        self.assertEqual({"a": 1}, json.loads(result.body))
        self.assertIsNone(result.error)

    def test_post_sends_body_and_headers_and_a_default_user_agent(self):
        result = self.runner.http("POST", self.url("/echo"), headers={"X-Custom": "yes"}, body=b'{"k": "v"}')
        echo = json.loads(result.body)
        self.assertEqual({"method": "POST", "body": '{"k": "v"}', "custom": "yes", "agent": "fabric-automation-toolchain"}, echo)
        result = self.runner.http("GET", self.url("/echo"), headers={"user-agent": "mine"})
        self.assertEqual("mine", json.loads(result.body)["agent"])

    def test_an_http_error_status_is_a_result_not_an_exception(self):
        result = self.runner.http("GET", self.url("/missing"))
        self.assertEqual(404, result.status)
        self.assertEqual(b"nope", result.body)
        self.assertIsNone(result.error)

    def test_repeated_headers_are_joined(self):
        result = self.runner.http("GET", self.url("/auth"))
        self.assertEqual(401, result.status)
        self.assertIn("bearer", result.headers["www-authenticate"].lower())
        self.assertEqual("a=1, b=2", result.headers["set-cookie"])

    def test_redirect_to_the_same_host_is_followed(self):
        result = self.runner.http("GET", self.url("/same"))
        self.assertEqual(200, result.status)
        self.assertEqual({"a": 1}, json.loads(result.body))

    def test_redirect_to_another_host_is_not_followed(self):
        result = self.runner.http("GET", self.url("/other"))
        self.assertEqual(302, result.status)
        self.assertNotEqual(b'{"a": 1}', result.body)

    def test_a_redirect_loop_ends(self):
        result = self.runner.http("GET", self.url("/loop"), timeout=10)
        self.assertEqual(302, result.status)

    def test_redirect_rule(self):
        allowed = toolchain_io._redirect_allowed
        split = urllib.parse.urlsplit
        self.assertTrue(allowed(split("https://a.example/x"), split("https://a.example/y")))
        self.assertTrue(allowed(split("http://A.example/x"), split("https://a.example/y")))
        self.assertFalse(allowed(split("https://a.example/x"), split("http://a.example/y")))
        self.assertFalse(allowed(split("https://a.example/x"), split("https://b.example/y")))
        self.assertFalse(allowed(split("https://a.example/x"), split("ftp://a.example/y")))

    def test_a_body_over_the_limit_is_cut_and_reported(self):
        result = self.runner.http("GET", self.url("/big"), timeout=20)
        self.assertEqual(200, result.status)
        self.assertEqual("too-large", result.error)
        self.assertLessEqual(len(result.body), toolchain_io.MAX_BODY)

    def test_a_slow_server_is_a_timeout_with_status_zero(self):
        result = self.runner.http("GET", self.url("/slow"), timeout=0.4)
        self.assertEqual(0, result.status)
        self.assertEqual("timeout", result.error)

    def test_a_refused_connection_is_status_zero(self):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        result = self.runner.http("GET", "http://127.0.0.1:%d/x" % port, timeout=10)
        self.assertEqual(0, result.status)
        self.assertIn(result.error, ("refused", "connect", "timeout", "reset"))

    def test_errors_never_hold_a_url_or_a_host(self):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        for url in ("http://127.0.0.1:%d/secret-path" % port, "file:///etc/hosts", "ftp://127.0.0.1/x", "not a url", "http://"):
            result = self.runner.http("GET", url, timeout=10)
            self.assertEqual(0, result.status, url)
            self.assertTrue(result.error and result.error.replace("-", "").isalpha(), url)
            for forbidden in ("127.0.0.1", "secret-path", "://", "etc"):
                self.assertNotIn(forbidden, result.error)

    def test_other_schemes_are_refused_before_any_request(self):
        self.assertEqual(HttpResult(0, {}, b"", "unsupported-scheme"), self.runner.http("GET", "file:///does-not-matter"))

    def test_loopback_requests_never_use_a_proxy(self):
        with mock.patch.dict(os.environ, {"http_proxy": "http://127.0.0.1:9", "HTTP_PROXY": "http://127.0.0.1:9"}):
            result = self.runner.http("GET", self.url("/ok"))
        self.assertEqual(200, result.status)


class ClassifyTests(unittest.TestCase):
    def test_exceptions_map_to_a_short_vocabulary(self):
        cases = [
            (socket.timeout(), "timeout"),
            (TimeoutError(), "timeout"),
            (urllib.error.URLError(socket.gaierror(11001, "x")), "dns"),
            (urllib.error.URLError(ConnectionRefusedError()), "refused"),
            (urllib.error.URLError(ssl.SSLCertVerificationError("x")), "tls"),
            (ssl.SSLError("x"), "tls"),
            (ConnectionResetError(), "reset"),
            (http.client.BadStatusLine("x"), "protocol"),
            (urllib.error.URLError("anything"), "error"),
            (OSError("weird"), "connect"),
            (ValueError("x"), "error"),
        ]
        for exc, expected in cases:
            self.assertEqual(expected, toolchain_io.classify_exception(exc), repr(exc))


class SafeDetailTests(unittest.TestCase):
    HOST = "feed" + "." + "contoso" + "." + "example"
    FEED = "pkgs." + "visual" + "studio.com"
    ADDRESS = "10." + "1.2.3"

    def test_urls_hosts_and_addresses_are_removed(self):
        text = "GET https://%s/npm/registry/x failed at %s port 443 via %s (%s)" % (self.FEED, self.HOST, self.ADDRESS, self.FEED)
        detail = toolchain_io.safe_detail(text)
        for forbidden in (self.FEED, self.HOST, "://", self.ADDRESS, "visual", "https"):
            self.assertNotIn(forbidden, detail)
        self.assertIn("failed", detail)

    def test_paths_and_addresses_with_a_user_are_removed(self):
        windows = "C:" + "\\Us" + "ers\\someone\\project\\x.txt"
        posix = "/ho" + "me/someone/x"
        text = "cannot read %s and %s and ~/x and mailbox%shost.example" % (windows, posix, "@")
        detail = toolchain_io.safe_detail(text)
        for forbidden in ("someone", "Users", "project", "~", "host.example", "home", "mailbox"):
            self.assertNotIn(forbidden, detail)

    def test_only_safe_characters_survive_and_the_length_is_capped(self):
        detail = toolchain_io.safe_detail("a\tb\n<script>c</script> `d` $e %f \u00e9 {g} " + "z" * 500)
        self.assertRegex(detail, r"^[A-Za-z0-9 ._:=/-]*$")
        self.assertLessEqual(len(detail), 80)
        self.assertEqual(40, len(toolchain_io.safe_detail("a" * 100, limit=40)))
        self.assertEqual("", toolchain_io.safe_detail(None))
        self.assertEqual("E404 not found", toolchain_io.safe_detail("E404 not found"))

    def test_safe_detail_is_idempotent(self):
        once = toolchain_io.safe_detail("see https://%s/x for E404 and 1.6.0" % self.HOST)
        self.assertEqual(once, toolchain_io.safe_detail(once))
        self.assertIn("1.6.0", once)


class KillTreeTests(unittest.TestCase):
    def test_kill_tree_ends_a_child_and_its_grandchild(self):
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "pids.txt"
            proc = toolchain_io.popen_tree([PY, "-c", TREE_SCRIPT, str(pidfile)])
            try:
                pids = read_pids(pidfile)
                self.assertEqual(2, len(pids))
                toolchain_io.kill_tree(proc)
                for pid in pids:
                    self.assertTrue(wait_dead(pid), "process %d survived kill_tree" % pid)
            finally:
                toolchain_io.kill_tree(proc)

    def test_launch_errors_carry_a_posix_style_code(self):
        with self.assertRaises(toolchain_io.LaunchError) as caught:
            toolchain_io.popen_tree(["no-such-command-xyz-123"])
        self.assertEqual(127, caught.exception.returncode)

    def test_without_inheritance_the_given_environment_is_the_whole_environment(self):
        script = "import json, os, sys; json.dump(sorted(name.upper() for name in os.environ), sys.stdout)"
        given = {"TC_ONLY_GIVEN": "1", "TC_REMOVED": None}
        for name in ("SYSTEMROOT", "SYSTEMDRIVE", "PROGRAMDATA"):  # without these a Microsoft Store Python writes folders into its working directory
            given[name] = os.environ.get(name, "")
        with mock.patch.dict(os.environ, {"TC_ONLY_IN_PARENT": "secret"}), tempfile.TemporaryDirectory() as work:
            for inherit, expected_parent_visible in ((False, False), (True, True)):
                proc = toolchain_io.popen_tree([PY, "-c", script], cwd=work, env=given, stdout=subprocess.PIPE, inherit=inherit)
                out, _ = proc.communicate(timeout=60)
                names = json.loads(out.decode("utf-8"))
                self.assertIn("TC_ONLY_GIVEN", names)
                self.assertNotIn("TC_REMOVED", names)
                self.assertEqual(expected_parent_visible, "TC_ONLY_IN_PARENT" in names, "inherit=%s" % inherit)
            self.assertEqual([], os.listdir(work))


if __name__ == "__main__":
    unittest.main()
