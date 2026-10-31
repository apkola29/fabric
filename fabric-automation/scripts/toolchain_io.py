#!/usr/bin/env python3
"""Runner abstraction of the toolchain kit: child processes and HTTP behind one small interface.

Every module of the kit reaches the machine through a runner, so a test passes a fake with the same
methods and needs no network. SystemRunner is the real one. It never raises, ends the whole process
tree on a timeout, finds a command only in the absolute folders of PATH (never in the current folder),
runs the .cmd shims of Windows (npx, npm, az, code) correctly, refuses arguments that a shim would hand
to the command interpreter, and never puts a URL or a host name into an error. Standard library only.
"""

from __future__ import annotations

import functools
import hashlib
import http.client
import ipaddress
import ntpath
import os
import posixpath
import re
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
MAX_HASHED = 200 * 1024 * 1024
USER_AGENT = "fabric-automation-toolchain"
WINDOWS = os.name == "nt"
_WINDOWS_ENDINGS = (".exe", ".cmd", ".bat")  # tried by hand for a name without an ending, whatever PATHEXT lists
_DEFAULT_PATHEXT = ".COM;.EXE;.BAT;.CMD;.VBS;.JS;.WS;.MSC"  # what shutil.which assumes when PATHEXT is not set


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


class HashResult(NamedTuple):
    status: int  # 0 when the request never got an answer
    sha256: str | None  # the hex digest of the whole body; None for any other outcome
    size: int  # the bytes that were read
    error: str | None  # a short word such as "too-large", "timeout" or "incomplete", never a URL or a host


class LaunchError(Exception):
    """A command that could not be started. returncode is 127 (not found) or 126 (cannot execute)."""

    def __init__(self, returncode, message):
        super().__init__(message)
        self.returncode = returncode
        self.message = message


_GLUED = re.compile(r"[\\/@]|.:.|^~")  # a path, an address, a user:secret pair or a home reference: the whole word goes
_NAME_RUN = re.compile(r"[A-Za-z0-9_.-]+")
_IPV4 = re.compile(r"(?<![A-Za-z0-9])\d{1,3}(?:\.\d{1,3}){3}(?![A-Za-z0-9])")
_IPV6_CHARS = frozenset("0123456789abcdefABCDEF:.")
_TOKEN = re.compile(r"[A-Za-z0-9_=-]{24,}")
_UNSAFE = re.compile(r"[^A-Za-z0-9 ._:=/-]")


def _host_like(run):
    """A run of name characters that has a dot between two labels and ends in a label that starts with two letters or more (a.b.example)."""
    labels = [label for label in (part.strip("-") for part in run.split(".")) if label]
    return len(labels) >= 2 and len(labels[-1]) >= 2 and labels[-1][0].isalpha()


def _ipv6_like(word):
    return word.count(":") >= 2 and set(word) <= _IPV6_CHARS


def _token_like(word):
    """A long word of letters, digits and _=- that mixes letters and digits: a key, a hash or a password rather than a word."""
    return _TOKEN.fullmatch(word) is not None and any(char.isdigit() for char in word) and any(char.isalpha() for char in word)


def safe_detail(text, limit=80):
    """Text that may be stored in a lock or shown in a message: no URL, host, address, path or token, only [A-Za-z0-9 ._:=/-].

    A word that holds a slash, a backslash, an at sign, a colon between two characters or starts with a tilde is removed whole
    (a URL, a path, an address, user:secret). The host and address rules run after the character filter, so that a letter
    outside the safe set next to a name cannot hide it. A word of 24 characters or more that mixes letters and digits is removed."""
    text = "" if text is None else str(text)
    words = [word for word in text.split() if not _GLUED.search(word)]
    text = _UNSAFE.sub(" ", " ".join(words))
    text = _NAME_RUN.sub(lambda match: " " if _host_like(match.group()) else match.group(), text)
    text = _IPV4.sub(" ", text)
    words = [word for word in text.split() if not _ipv6_like(word) and not _token_like(word)]
    return " ".join(words)[:limit].rstrip()


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


# The pauses, in seconds, between the attempts to move or delete a file or folder that something else has open for a moment (a sync
# client such as OneDrive, a virus scanner, the search indexer): about six seconds in all. A folder that was just written is the usual
# case, and Windows then answers "access denied" to the rename of the folder or of a file in it until the other process lets go.
RETRY_DELAYS = (0.05, 0.1, 0.2, 0.4, 0.8, 1.6, 3.2)


def transient_refusal(exc):
    """True for what Windows answers while another process has the file or folder open: access denied, a sharing violation or a lock violation.

    Anywhere else a refusal is a real one (the file may not be written), and it is not worth waiting for."""
    return bool(WINDOWS and isinstance(exc, OSError) and (isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in (5, 32, 33)))


def retrying(action, sleep=None):
    """Run `action` and run it again after a short pause while it fails with a transient refusal. Any other failure, and the refusal
    that is still there after the last pause, is raised."""
    for delay in RETRY_DELAYS:
        try:
            return action()
        except OSError as exc:
            if not transient_refusal(exc):
                raise
            (sleep or time.sleep)(delay)
    return action()


def replace_retrying(source, target, sleep=None):
    """os.replace that waits for a file or folder that Windows refuses to move for a moment."""
    retrying(lambda: os.replace(source, target), sleep)


def _is_absolute(path):
    """An absolute path in the style of the family that WINDOWS names. On Windows it needs a drive or a share as well: `\\x` and `C:x`
    depend on the current drive or folder."""
    if WINDOWS:
        return ntpath.isabs(path) and bool(ntpath.splitdrive(path)[0])
    return posixpath.isabs(path)


def _may_run(path):
    """An existing file; on POSIX one that this user may execute."""
    return os.path.isfile(path) and (WINDOWS or os.access(path, os.X_OK))


def _file_names(name):
    """The lists of file names that the search tries for `name`, in order. Every folder is searched for all the names of a list before
    the next list is tried."""
    if not WINDOWS:
        return [[name]]
    listed = [ending for ending in (os.environ.get("PATHEXT") or _DEFAULT_PATHEXT).split(";") if ending]
    suffix = ntpath.splitext(name)[1]
    known = {ending.upper() for ending in listed + list(_WINDOWS_ENDINGS)}
    names = [[name] if suffix.upper() in known else [name + ending for ending in listed]]
    if not suffix:
        names += [[name + ending] for ending in _WINDOWS_ENDINGS]
    return names


def which(name):
    """The absolute path of the launcher that `name` stands for, or None.

    Only the absolute folders of PATH are searched. An empty entry, a dot and any relative entry are skipped on every system, so the
    current folder is never consulted: shutil.which always starts there on Windows, and on POSIX an empty entry of PATH means it.
    On Windows the name is tried with each ending of PATHEXT and then with .exe, .cmd and .bat. A name with a directory part is checked
    as a file and returned as it is, but only when it is absolute."""
    if not name or not isinstance(name, str):
        return None
    module = ntpath if WINDOWS else posixpath
    if module.dirname(name):
        return name if _is_absolute(name) and _may_run(name) else None
    path = os.environ.get("PATH")
    folders = [entry for entry in (os.defpath if path is None else path).split(";" if WINDOWS else ":") if entry and _is_absolute(entry)]
    for names in _file_names(name):
        for folder in folders:
            for file_name in names:
                found = module.join(folder, file_name)
                if _may_run(found):
                    return found
    return None


# A .cmd or .bat file is run by the command interpreter, which reads these characters as syntax.
_SHIM_UNSAFE = re.compile(r'[&|<>^%"\r\n]')


def resolve_command(argv, finder=which):
    """argv with the executable replaced by its full path. Raises LaunchError for a command that cannot be run safely.

    A command that the finder does not turn into an absolute path is not found: it is never started under its bare name, because the
    search of the operating system looks in the current folder first on Windows."""
    if not argv or not all(isinstance(part, str) for part in argv) or not argv[0]:
        raise LaunchError(127, "not found")
    found = finder(argv[0])
    if not found or not isinstance(found, str) or not _is_absolute(found):
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


def _system_taskkill():
    """taskkill.exe of the system folder by absolute path, or None. The search path and the current folder are never consulted."""
    for root in (os.environ.get("SystemRoot"), os.environ.get("windir"), "C:\\Windows"):
        if root and os.path.isabs(root):
            exe = os.path.join(root, "System32", "taskkill.exe")
            if os.path.isfile(exe):
                return exe
    return None


def _taskkill(pid):
    exe = _system_taskkill()
    if exe is None:
        return
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


_DEFAULT_PORTS = {"http": 80, "https": 443}


def _effective_port(parts):
    """The port of a URL, with the default of its scheme when none is written; None when the port is not a valid number."""
    try:
        port = parts.port
    except ValueError:
        return None
    return port if port is not None else _DEFAULT_PORTS.get(parts.scheme.lower())


def _redirect_allowed(old, new):
    """Same host and same port, and never from https to http. An upgrade between the default ports (80 to 443) is the one port change allowed."""
    if new.scheme.lower() not in ("http", "https"):
        return False
    if old.scheme.lower() == "https" and new.scheme.lower() != "https":
        return False
    if (old.hostname or "").lower() != (new.hostname or "").lower():
        return False
    old_port, new_port = _effective_port(old), _effective_port(new)
    if old_port is None or new_port is None:
        return False
    return old_port == new_port or (old_port == _DEFAULT_PORTS.get(old.scheme.lower()) and new_port == _DEFAULT_PORTS.get(new.scheme.lower()))


def _is_loopback(host):
    host = host.strip("[]").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _read_some(stream, size):
    """Up to `size` bytes, as soon as some have arrived: read() would wait for all of them and so hide a server that trickles."""
    return getattr(stream, "read1", stream.read)(size)


def _collect(status, headers, stream, deadline):
    chunks, total, error = [], 0, None
    try:
        while True:
            chunk = _read_some(stream, min(65536, MAX_BODY + 1 - total))
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


def _hash_body(status, headers, stream, deadline, max_bytes):
    """Read a body in pieces and hash it without keeping it. Only a complete body of 200 gets a digest."""
    try:
        if status != 200:
            return HashResult(status, None, 0, None)
        declared = headers.get("Content-Length")
        declared = int(declared) if declared and declared.strip().isdigit() else None
        if declared is not None and declared > max_bytes:
            return HashResult(status, None, 0, "too-large")
        digest, total, error = hashlib.sha256(), 0, None
        try:
            while True:
                chunk = _read_some(stream, min(65536, max_bytes + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    error = "too-large"
                    break
                digest.update(chunk)
                if time.monotonic() > deadline:
                    error = "timeout"
                    break
        except (OSError, http.client.HTTPException) as exc:
            error = classify_exception(exc)
        if error is None and declared is not None and total != declared:
            error = "incomplete"
        return HashResult(status, digest.hexdigest() if error is None else None, total, error)
    finally:
        stream.close()


def _http(method, url, headers, body, timeout, read=_collect, total=None):
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
    deadline = time.monotonic() + (timeout if total is None else total)
    try:
        response = urllib.request.build_opener(*handlers).open(request, timeout=timeout)
    except urllib.error.HTTPError as err:
        return read(err.code, err.headers, err, deadline)
    return read(response.status, response.headers, response, deadline)


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

    def http_hash(self, url, *, headers=None, timeout=20, max_bytes=MAX_HASHED, total=300):
        """GET a body that may be large and give its SHA-256 without keeping it. `timeout` is the wait for each read, `total` the
        time for the whole body. A transport problem is a result, never an exception."""
        try:
            result = _http("GET", url, headers, None, timeout, read=functools.partial(_hash_body, max_bytes=max_bytes), total=total)
        except Exception as exc:
            return HashResult(0, None, 0, classify_exception(exc))
        if isinstance(result, HttpResult):  # the request failed before there was an answer
            return HashResult(result.status, None, 0, result.error)
        return result
