#!/usr/bin/env python3
"""Minimal MCP client of the toolchain kit: read the tool contract of a server, probe a hosted URL, compare two contracts.

probe_stdio starts a server and talks newline-delimited JSON-RPC over its standard streams. It tries the handshake
of the legacy era first (`initialize`, `notifications/initialized`, `tools/list`). The 2026-07-28 revision of the
specification made the protocol stateless: there is no handshake and every request carries `_meta`. A server of
that era refuses `initialize` and names the versions it supports, and then the probe switches to `server/discover`
and `tools/list` with the metadata. Whatever happens, the child and its descendants are ended before the call
returns. Server messages are never copied into an error: an error holds a reason code and a short fixed detail.
Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from toolchain_io import WINDOWS, LaunchError, SystemRunner, kill_tree, popen_tree, safe_detail, terminate_tree  # noqa: E402

LEGACY_VERSION = "2025-11-25"
MODERN_VERSION = "2026-07-28"
META = "io.modelcontextprotocol/"
CLIENT_INFO = {"name": "fabric-automation-toolchain", "version": "1"}
MAX_LINE = 16 * 1024 * 1024
MAX_PAGES = 200
GRACE = 1.0  # seconds a server gets to leave by itself once its input is closed
DISCOVER_WAIT = 10.0  # seconds to wait for server/discover when it only serves to tell the eras apart
UNSUPPORTED_VERSION = -32022
METHOD_NOT_FOUND = -32601

# What a server process needs in order to start and to reach its package feed. Nothing else of this process's
# environment is passed on: a variable such as PBI_MODELING_MCP_ALLOWED_CONNECTION_HOSTS adds hosts that receive access
# tokens, and a secret in the operator's shell must never reach a capture that is declared credential-free. Names are
# matched without regard to case. SystemDrive and ProgramData are there because a Windows child that lacks both writes a
# literal %SystemDrive%\ProgramData folder tree into its working directory (seen with the Microsoft Store Python); the
# other locations and the processor names are what installers and .NET hosts look up.
ENV_ALLOW_LIST = (
    "PATH", "PATHEXT", "SystemRoot", "windir", "ComSpec", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
    "SystemDrive", "ProgramData", "ALLUSERSPROFILE", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "CommonProgramFiles",
    "CommonProgramFiles(x86)", "CommonProgramW6432", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "PROCESSOR_ARCHITEW6432",
    "DOTNET_ROOT", "DOTNET_ROOT(x86)",
    "LANG", "LC_ALL",
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "NODE_EXTRA_CA_CERTS",
)
ENV_ALLOW_PREFIXES = ("npm_config_",)

_EOF = object()
_TOO_LONG = object()
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_VERSION_WORDS = re.compile(r"version|protocol|support", re.IGNORECASE)
_PLAIN_VERSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+_~-]{0,63}")


class McpProbeError(Exception):
    """The message starts with a lock reason code (timeout, spawn-failed, exited, protocol-error, no-tools) and then a short detail."""

    @property
    def code(self):
        return str(self).split(":", 1)[0].strip()


def _fail(code, detail=""):
    return McpProbeError("%s: %s" % (code, detail) if detail else code)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _parse(line):
    try:
        message = json.loads(line.decode("utf-8", "replace"))
    except ValueError:
        return None
    return message if isinstance(message, dict) else None


def _error_code(error):
    code = error.get("code") if isinstance(error, dict) else None
    return code if isinstance(code, int) and not isinstance(code, bool) else 0


def _named_versions(error):
    """The protocol versions that a JSON-RPC error names. Free text counts only when it talks about versions or support."""
    if not isinstance(error, dict):
        return []
    found, text, structured = [], str(error.get("message") or ""), False
    data = error.get("data")
    if isinstance(data, dict):
        for key in ("supported", "supportedVersions", "versions"):
            if isinstance(data.get(key), list):
                structured = True
                found += [item for item in data[key] if isinstance(item, str)]
        text += " " + " ".join(value for value in data.values() if isinstance(value, str))
    elif isinstance(data, list):
        structured = True
        found += [item for item in data if isinstance(item, str)]
    elif isinstance(data, str):
        text += " " + data
    if not structured and _VERSION_WORDS.search(text):
        found += _DATE.findall(text)
    return sorted({item for item in found if _DATE.fullmatch(item)})


def _meta():
    return {META + "protocolVersion": MODERN_VERSION, META + "clientInfo": dict(CLIENT_INFO), META + "clientCapabilities": {}}


def _declared_value(name, spec, parent):
    """The value of one declared variable: a string as it is, or {"from_env", "default"} read from the parent.

    A parent value counts when it is set and not empty, the way ${NAME:-default} reads it in the host files. None means "not set"."""
    if spec is None or isinstance(spec, str):
        return spec
    if isinstance(spec, dict):
        source = spec.get("from_env") or name
        value = parent.get(source) if isinstance(source, str) else None
        if isinstance(value, str) and value:
            return value
        default = spec.get("default")
        if default is None or isinstance(default, str):
            return default
    raise _fail("spawn-failed", "bad environment declaration")


def capture_env(declared=None, parent=None):
    """The whole environment of a server started for contract capture.

    It holds the variables of ENV_ALLOW_LIST (and the npm_config_ ones) that the parent has, and then exactly the variables
    that `declared` names: {name: "value"} or {name: {"from_env": "SOURCE", "default": "value"}}. A declared name replaces an
    allow-listed one of the same name and None removes it. Everything else in the parent environment stays behind."""
    parent = os.environ if parent is None else parent
    allowed = {name.upper() for name in ENV_ALLOW_LIST}
    prefixes = tuple(prefix.upper() for prefix in ENV_ALLOW_PREFIXES)
    child = {key: value for key, value in parent.items() if key.upper() in allowed or key.upper().startswith(prefixes)}
    for name, spec in (declared or {}).items():
        if not isinstance(name, str) or not name or "=" in name or "\x00" in name:
            raise _fail("spawn-failed", "bad environment name")
        value = _declared_value(name, spec, parent)
        for existing in [key for key in child if key == name or (WINDOWS and key.upper() == name.upper())]:
            del child[existing]
        if value is not None:
            child[name] = value
    return child


class _Server:
    def __init__(self, argv, env, cwd):
        try:
            self.proc = popen_tree(argv, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, inherit=False)
        except LaunchError as exc:
            raise _fail("spawn-failed", exc.message) from None
        self.lines = queue.Queue(maxsize=256)
        self.stop = threading.Event()
        self.last_id = 0
        self.reader = threading.Thread(target=self._pump, daemon=True)
        self.reader.start()

    def _put(self, item):
        while not self.stop.is_set():
            try:
                self.lines.put(item, timeout=0.2)
                return
            except queue.Full:
                continue

    def _pump(self):
        stream = self.proc.stdout
        try:
            while not self.stop.is_set():
                line = stream.readline(MAX_LINE + 1)
                if not line:
                    break
                if len(line) > MAX_LINE and not line.endswith(b"\n"):
                    while True:
                        rest = stream.readline(65536)
                        if not rest or rest.endswith(b"\n"):
                            break
                    self._put(_TOO_LONG)
                else:
                    self._put(line)
        except (OSError, ValueError):
            pass
        finally:
            self._put(_EOF)

    def _exit_detail(self):
        try:
            code = self.proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            return "the server closed its output"
        return "code %d" % code

    def send(self, message):
        data = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
        try:
            self.proc.stdin.write(data)
            self.proc.stdin.flush()
        except (OSError, ValueError):
            raise _fail("exited", self._exit_detail()) from None

    def notify(self, method):
        self.send({"jsonrpc": "2.0", "method": method})

    def _answer_request(self, message):
        """A server may ask the client something (ping, or a capability the client never declared)."""
        if message.get("id") is None:
            return
        if message.get("method") == "ping":
            self.send({"jsonrpc": "2.0", "id": message["id"], "result": {}})
        else:
            self.send({"jsonrpc": "2.0", "id": message["id"], "error": {"code": METHOD_NOT_FOUND, "message": "Method not found"}})

    def call(self, method, params, deadline):
        self.last_id += 1
        wanted = self.last_id
        self.send({"jsonrpc": "2.0", "id": wanted, "method": method, "params": params})
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _fail("timeout", "no answer to " + method)
            try:
                item = self.lines.get(timeout=remaining)
            except queue.Empty:
                raise _fail("timeout", "no answer to " + method) from None
            if item is _EOF:
                raise _fail("exited", self._exit_detail())
            if item is _TOO_LONG:
                raise _fail("protocol-error", "a line is longer than the limit")
            message = _parse(item)
            if message is None:
                continue
            if "method" in message:
                self._answer_request(message)
            elif message.get("id") == wanted and ("result" in message or "error" in message):
                return message

    def close(self):
        self.stop.set()
        try:
            self.proc.stdin.close()
        except (OSError, ValueError):
            pass
        try:
            self.proc.wait(timeout=GRACE)
        except subprocess.TimeoutExpired:
            terminate_tree(self.proc)
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
        kill_tree(self.proc)
        self.reader.join(timeout=2)
        if not self.reader.is_alive():
            try:
                self.proc.stdout.close()
            except (OSError, ValueError):
                pass


def _server_info(info):
    info = info if isinstance(info, dict) else {}
    name = info.get("name")
    version = info.get("version")
    if isinstance(version, str) and not _PLAIN_VERSION.fullmatch(version):
        version = safe_detail(version, 64)
    return {"name": safe_detail(name, 64) if isinstance(name, str) else "", "version": version if isinstance(version, str) else ""}


def _flag(value):
    return value if isinstance(value, bool) else None


def _contract(tool):
    annotations = tool.get("annotations") if isinstance(tool.get("annotations"), dict) else {}
    schema = hashlib.sha256(_canonical(tool.get("inputSchema")).encode("utf-8", "surrogatepass")).hexdigest()
    return {"schema": "sha256:" + schema, "read_only": _flag(annotations.get("readOnlyHint")),
            "destructive": _flag(annotations.get("destructiveHint")), "idempotent": _flag(annotations.get("idempotentHint"))}


def _list_tools(server, deadline, meta):
    tools, seen, cursor = {}, set(), None
    for _ in range(MAX_PAGES):
        params = {}
        if meta is not None:
            params["_meta"] = meta
        if cursor is not None:
            params["cursor"] = cursor
        answer = server.call("tools/list", params, deadline)
        if "error" in answer:
            code = _error_code(answer["error"])
            if code == METHOD_NOT_FOUND:
                raise _fail("no-tools", "the server has no tools")
            raise _fail("protocol-error", "tools/list failed with code %d" % code)
        result = answer.get("result")
        page = result.get("tools") if isinstance(result, dict) else None
        if not isinstance(page, list):
            raise _fail("protocol-error", "tools/list answered without a tool list")
        if meta is not None and result.get("resultType") not in (None, "complete"):
            raise _fail("protocol-error", "tools/list did not complete")
        for entry in page:
            name = entry.get("name") if isinstance(entry, dict) else None
            if not isinstance(name, str) or not name or len(name) > 256:
                raise _fail("protocol-error", "a tool without a usable name")
            if name in tools:
                raise _fail("protocol-error", "a tool name is listed twice")
            tools[name] = _contract(entry)
        cursor = result.get("nextCursor")
        if not cursor:
            break
        if not isinstance(cursor, str) or cursor in seen:
            raise _fail("protocol-error", "the pages do not end")
        seen.add(cursor)
    else:
        raise _fail("protocol-error", "too many pages")
    if not tools:
        raise _fail("no-tools", "the server lists no tools")
    return {name: tools[name] for name in sorted(tools)}


def _discover(server, deadline, expected_modern):
    """server/discover. Returns the server info, or None when the server turns out not to be modern.

    expected_modern: the refusal of `initialize` already named a modern version, so discover only adds the server info and an
    answer that does not fit is no reason to doubt the era. Otherwise it is the probe that tells the two eras apart."""
    limit = deadline if expected_modern else min(deadline, time.monotonic() + DISCOVER_WAIT)
    try:
        answer = server.call("server/discover", {"_meta": _meta()}, limit)
    except McpProbeError as exc:
        if exc.code == "timeout" and not expected_modern:
            return None
        raise
    result = answer.get("result")
    if isinstance(result, dict) and isinstance(result.get("supportedVersions"), list):
        if MODERN_VERSION not in result["supportedVersions"]:
            raise _fail("protocol-error", "no mutually supported protocol version")
        meta = result.get("_meta") if isinstance(result.get("_meta"), dict) else {}
        return _server_info(meta.get(META + "serverInfo"))
    if _error_code(answer.get("error")) == UNSUPPORTED_VERSION:
        raise _fail("protocol-error", "no mutually supported protocol version")
    return _server_info(None) if expected_modern else None


def _modern(server, deadline, info):
    return {"era": "modern", "protocol": MODERN_VERSION, "server": info, "tools": _list_tools(server, deadline, _meta())}


def _legacy(server, deadline, answer):
    result = answer.get("result")
    protocol = safe_detail(result.get("protocolVersion"), 32) if isinstance(result, dict) else ""
    if not protocol:
        raise _fail("protocol-error", "initialize answered without a protocol version")
    server.notify("notifications/initialized")
    return {"era": "legacy", "protocol": protocol, "server": _server_info(result.get("serverInfo")),
            "tools": _list_tools(server, deadline, None)}


def _probe(server, deadline):
    requested = LEGACY_VERSION
    while True:
        params = {"protocolVersion": requested, "capabilities": {}, "clientInfo": dict(CLIENT_INFO)}
        answer = server.call("initialize", params, deadline)
        if "error" not in answer:
            return _legacy(server, deadline, answer)
        error = answer["error"]
        named = _named_versions(error)
        if any(version >= MODERN_VERSION for version in named):
            return _modern(server, deadline, _discover(server, deadline, True))
        older = [version for version in named if version < LEGACY_VERSION]
        if older and requested == LEGACY_VERSION:
            requested = older[-1]
            continue
        info = _discover(server, deadline, False)
        if info is None:
            raise _fail("protocol-error", "initialize failed with code %d" % _error_code(error))
        return _modern(server, deadline, info)


def probe_stdio(argv, *, env=None, cwd=None, timeout=60):
    """Start `argv` and return {"era", "protocol", "server": {"name", "version"}, "tools": {name: contract}}.

    `timeout` is the budget of the whole call, the start of the process included. `env` holds the variables the variant
    declares (see capture_env); the child gets those and the allow-listed ones, never the rest of this process's environment."""
    if not isinstance(argv, (list, tuple)) or not argv:
        raise _fail("spawn-failed", "no command")
    deadline = time.monotonic() + timeout
    server = _Server(list(argv), capture_env(env), cwd)
    try:
        return _probe(server, deadline)
    except McpProbeError:
        raise
    except Exception as exc:
        raise _fail("protocol-error", "unexpected " + type(exc).__name__) from None
    finally:
        server.close()


def probe_http(url, *, headers=None, runner=None, timeout=15):
    """Post a legacy `initialize` to a hosted server and report only how it answered: open, needs-sign-in or error.

    The body, the session id and the challenge of the answer are never returned."""
    runner = runner or SystemRunner()
    sent = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    for name, value in (headers or {}).items():
        for existing in [key for key in sent if key.lower() == str(name).lower()]:
            del sent[existing]
        sent[str(name)] = str(value)
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                       "params": {"protocolVersion": LEGACY_VERSION, "capabilities": {}, "clientInfo": dict(CLIENT_INFO)}},
                      separators=(",", ":")).encode("utf-8")
    try:
        status = int(runner.http("POST", url, headers=sent, body=body, timeout=timeout).status)
    except Exception:  # a runner never raises, but a stand-in might
        return {"status": "error", "http_status": 0}
    if 200 <= status < 300:
        return {"status": "open", "http_status": status}
    if status in (401, 403):
        return {"status": "needs-sign-in", "http_status": status}
    return {"status": "error", "http_status": status}


def _signature(tool):
    tool = tool if isinstance(tool, dict) else {}
    return tuple(tool.get(key) for key in ("schema", "read_only", "destructive", "idempotent"))


def contract_diff(locked, live):
    """Compare two "tools" maps: the names added, removed and changed (schema or any of the three hints)."""
    locked, live = locked or {}, live or {}
    return {"added": sorted(set(live) - set(locked)),
            "removed": sorted(set(locked) - set(live)),
            "changed": sorted(name for name in set(locked) & set(live) if _signature(locked[name]) != _signature(live[name]))}
