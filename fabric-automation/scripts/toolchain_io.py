#!/usr/bin/env python3
"""Runner abstraction of the toolchain kit: child processes and HTTP behind one small interface.

Every module of the kit reaches the machine through a runner, so a test passes a fake with the same
methods and needs no network. SystemRunner is the real one. It never raises, ends the whole process
tree on a timeout, runs the .cmd shims of Windows (npx, npm, az, code) correctly, refuses arguments
that a shim would hand to the command interpreter, and never puts a URL or a host name into an
error. Standard library only.
"""

from __future__ import annotations

import http.client
import ipaddress
import os
import re
import shutil
import signal
import socket
import ssl
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import NamedTuple

MAX_BODY = 5 * 1024 * 1024
USER_AGENT = "fabric-automation-toolchain"
WINDOWS = os.name == "nt"


class CommandResult(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


class RawResult(NamedTuple):
    returncode: int
    stdout: bytes
    stderr: bytes


class HttpResult(NamedTuple):
    status: int  # 0 when the request never got an answer
    headers: dict  # lower-case names; repeated headers are joined with ", "
    body: bytes
    error: str | None  # a short word such as "timeout" or "tls", never a URL or a host


class LaunchError(Exception):
    """A command that could not be started. returncode is 127 (not found) or 126 (cannot execute)."""

    def __init__(self, returncode, message):
        super().__init__(message)
        self.returncode = returncode
        self.message = message


_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://\S*")
_ADDRESS = re.compile(r"\S+@\S+")
_PATH = re.compile(r"(?<![\w.-])(?:[A-Za-z]:)?[\\/]\S*|(?<![\w.-])~\S*")
_HOST = re.compile(r"\b(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}\b")
_IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
_UNSAFE = re.compile(r"[^A-Za-z0-9 ._:=/-]")


def safe_detail(text, limit=80):
    """Text that may be stored in a lock or shown in a message: no URL, host, address or path, only [A-Za-z0-9 ._:=/-]."""
    text = "" if text is None else str(text)
    for pattern in (_URL, _ADDRESS, _PATH, _HOST, _IPV4):
        text = pattern.sub(" ", text)
    text = _UNSAFE.sub(" ", text)
    return " ".join(text.split())[:limit].rstrip()


def classify_exception(exc):
    """A transport failure as one short word: timeout, dns, refused, tls, reset, protocol, connect or error."""
    if isinstance(exc, urllib.error.URLError) and not isinstance(exc, urllib.error.HTTPError):
        return classify_exception(exc.reason) if isinstance(exc.reason, BaseException) else "error"
    if isinstance(exc, ssl.SSLError):
        return "tls"
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "timeout"
    if isinstance(exc, socket.gaierror):
        return "dns"
    if isinstance(exc, ConnectionRefusedError):
        return "refused"
    if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
        return "reset"
    if isinstance(exc, http.client.HTTPException):
        return "protocol"
    if isinstance(exc, OSError):
        return "connect"
    return "error"


def which(name):
    """shutil.which with the .exe, .cmd and .bat endings tried by hand when PATHEXT does not list them."""
    if not name or not isinstance(name, str):
        return None
    found = shutil.which(name)
    if found is None and WINDOWS and not os.path.splitext(name)[1]:
        for ending in (".exe", ".cmd", ".bat"):
            found = shutil.which(name + ending)
            if found:
                break
    return found


# A .cmd or .bat file is run by the command interpreter, which reads these characters as syntax.
_SHIM_UNSAFE = re.compile(r'[&|<>^%"\r\n]')


def resolve_command(argv, finder=which):
    """argv with the executable replaced by its full path. Raises LaunchError for a command that cannot be run safely."""
    if not argv or not all(isinstance(part, str) for part in argv) or not argv[0]:
        raise LaunchError(127, "not found")
    found = finder(argv[0])
    if not found:
        raise LaunchError(127, "not found")
    if WINDOWS and found.lower().endswith((".cmd", ".bat")):
        if any(_SHIM_UNSAFE.search(part) for part in argv[1:]):
            raise LaunchError(126, "unsafe argument for a command shim")
    return [found] + list(argv[1:])


def merged_env(overlay):
    """The inherited environment with the given entries added; a value of None removes the variable."""
    full = dict(os.environ)
    for key, value in (overlay or {}).items():
        key = str(key).upper() if WINDOWS else str(key)
        if value is None:
            full.pop(key, None)
        else:
            full[key] = str(value)
    return full


def popen_tree(argv, *, cwd=None, env=None, stdin=None, stdout=None, stderr=None, finder=which, inherit=True):
    """Start a child that kill_tree can end together with everything it starts. Raises LaunchError.

    With inherit=False, env is the whole environment of the child and nothing is taken from this process."""
    command = resolve_command(argv, finder)
    if cwd is not None and not os.path.isdir(cwd):
        raise LaunchError(127, "not found")
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if WINDOWS else {"start_new_session": True}
    environment = merged_env(env) if inherit else {str(key): str(value) for key, value in (env or {}).items() if value is not None}
    try:
        return subprocess.Popen(command, cwd=cwd, env=environment, stdin=stdin, stdout=stdout, stderr=stderr, **options)
    except FileNotFoundError:
        raise LaunchError(127, "not found") from None
    except (OSError, ValueError):
        raise LaunchError(126, "cannot execute") from None


def _taskkill(pid):
    root = os.environ.get("SystemRoot") or "C:/Windows"
    exe = shutil.which("taskkill") or os.path.join(root, "System32", "taskkill.exe")
    try:
        subprocess.run([exe, "/PID", str(pid), "/T", "/F"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=20, check=False, creationflags=subprocess.CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        pass


def _signal_group(proc, sig):
    try:
        os.killpg(proc.pid, sig)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def _reap(proc):
    try:
        proc.wait(timeout=5)
    except (subprocess.TimeoutExpired, OSError):
        pass


def kill_tree(proc):
    """End a child and everything it started. Safe to call twice and on a child that has already ended."""
    if WINDOWS:
        _taskkill(proc.pid)
    else:
        _signal_group(proc, signal.SIGKILL)
    try:
        proc.kill()
    except OSError:
        pass
    _reap(proc)


def terminate_tree(proc):
    """Ask a child and its descendants to end (SIGTERM to the process group). Windows has no such request, so it ends them."""
    if WINDOWS:
        kill_tree(proc)
    else:
        _signal_group(proc, signal.SIGTERM)


def _drain(proc):
    try:
        return proc.communicate(timeout=5)
    except subprocess.TimeoutExpired as exc:
        out, err = exc.stdout or b"", exc.stderr or b""
    except (OSError, ValueError):
        out, err = b"", b""
    for pipe in (proc.stdout, proc.stderr, proc.stdin):
        try:
            pipe.close()
        except (OSError, ValueError, AttributeError):
            pass
    return out, err


class _SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urllib.parse.urlsplit(req.full_url)
        new = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        if not _redirect_allowed(old, new):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _redirect_allowed(old, new):
    """Same host only, and never from https to http."""
    if new.scheme.lower() not in ("http", "https"):
        return False
    if old.scheme.lower() == "https" and new.scheme.lower() != "https":
        return False
    return (old.hostname or "").lower() == (new.hostname or "").lower()


def _is_loopback(host):
    host = host.strip("[]").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _collect(status, headers, stream, deadline):
    chunks, total, error = [], 0, None
    try:
        while True:
            chunk = stream.read(min(65536, MAX_BODY + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_BODY:
                error = "too-large"
                break
            if time.monotonic() > deadline:
                error = "timeout"
                break
    except (OSError, http.client.HTTPException) as exc:
        error = classify_exception(exc)
    finally:
        stream.close()
    lowered = {}
    for name, value in headers.items():
        key = name.lower()
        lowered[key] = lowered[key] + ", " + value if key in lowered else value
    return HttpResult(status, lowered, b"".join(chunks)[:MAX_BODY], error)


def _http(method, url, headers, body, timeout):
    parts = urllib.parse.urlsplit(str(url))
    if parts.scheme.lower() not in ("http", "https"):
        return HttpResult(0, {}, b"", "unsupported-scheme")
    if not parts.hostname:
        return HttpResult(0, {}, b"", "bad-url")
    handlers = [_SameHostRedirect()]
    if _is_loopback(parts.hostname):
        handlers.append(urllib.request.ProxyHandler({}))
    sent = {"User-Agent": USER_AGENT}
    for name, value in (headers or {}).items():
        for existing in [key for key in sent if key.lower() == str(name).lower()]:
            del sent[existing]
        sent[str(name)] = str(value)
    request = urllib.request.Request(str(url), data=body, method=method.upper(), headers=sent)
    deadline = time.monotonic() + timeout
    try:
        response = urllib.request.build_opener(*handlers).open(request, timeout=timeout)
    except urllib.error.HTTPError as err:
        return _collect(err.code, err.headers, err, deadline)
    return _collect(response.status, response.headers, response, deadline)


class SystemRunner:
    def which(self, name):
        return which(name)

    def run_bytes(self, argv, *, cwd=None, env=None, timeout=60, input=None):
        """run() without decoding; the object reads of git need it, because a blob is not text."""
        data = None
        if input is not None:
            data = bytes(input) if isinstance(input, (bytes, bytearray)) else str(input).encode("utf-8")
        try:
            proc = popen_tree(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL if data is None else subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, finder=self.which)
        except LaunchError as exc:
            return RawResult(exc.returncode, b"", exc.message.encode("ascii"))
        try:
            out, err = proc.communicate(data, timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_tree(proc)
            out, err = _drain(proc)
            return RawResult(124, out, err + (b"\n" if err else b"") + b"timed out")
        except Exception:
            kill_tree(proc)
            return RawResult(126, b"", b"cannot execute")
        except BaseException:
            kill_tree(proc)
            raise
        return RawResult(proc.returncode, out, err)

    def run(self, argv, *, cwd=None, env=None, timeout=60, input=None):
        raw = self.run_bytes(argv, cwd=cwd, env=env, timeout=timeout, input=input)
        return CommandResult(raw.returncode, raw.stdout.decode("utf-8", "replace"), raw.stderr.decode("utf-8", "replace"))

    def http(self, method, url, *, headers=None, body=None, timeout=20):
        try:
            return _http(str(method), url, headers, body, timeout)
        except Exception as exc:  # the contract is that a transport problem is a result, never an exception
            return HttpResult(0, {}, b"", classify_exception(exc))
