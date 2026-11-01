#!/usr/bin/env python3
"""The toolchain kit: pinned skills, MCP servers and tools for the factory, and the commands that check them.

Reads toolchain/toolchain.json (the manifest), toolchain/profiles.json (the job profiles) and
toolchain/toolchain.lock.json (the lock that `lock` writes), and offers:

    list      the profiles, the locked skills and the servers
    verify    the checks that keep the toolchain fail-closed (offline unless --live or --contracts)
    render    the MCP configuration of a profile for Copilot CLI, VS Code or Claude Code, or a neutral load plan
    lock      resolve the manifest into the lock (git refs, package versions, MCP tool contracts)
    update    what an upstream refresh would change, and which profile it would break
    fetch     vendor the locked skills into the local pack
    install   copy skills and MCP configuration into a host (a plan unless --apply)
    doctor    what is missing on this machine

Standard library only. Everything that touches the outside world (runner, resolvers, probes, environment, home folder)
goes through a Deps object, so the tests run without a network, a subprocess or the real home folder.
Exit status: 0 ok, 1 a check failed, 2 usage error, 3 `update --check --fail-on-update` found a change.
"""

from __future__ import annotations

import argparse
import copy
import datetime
import difflib
import fnmatch
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import sys
import tempfile
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import toolchain_io  # noqa: E402
import toolchain_mcp  # noqa: E402
import toolchain_sources  # noqa: E402

DEFAULT_ROOT = Path(__file__).resolve().parent.parent

SCHEMA = 1
MODES = ("dev", "agent", "executor")
NETWORKS = ("none", "microsoft-cloud", "internet")
CREDENTIALS = ("none", "azure-identity", "entra-delegated", "github")
ACCESS = ("read", "read-write")
TRANSPORTS = ("stdio", "http")
STATUSES = ("ga", "public-preview", "preview", "beta", "unverified")
ECOSYSTEMS = ("npm", "pypi", "nuget")
REASONS = ("timeout", "spawn-failed", "exited", "protocol-error", "no-tools", "install-blocked", "needs-sign-in",
           "not-installed", "network", "unresolved", "skipped")
HOSTS = ("copilot-cli", "vscode", "claude-code")
RENDER_TARGETS = HOSTS + ("load-plan",)
PROJECT_HOSTS = ("copilot-cli", "vscode")  # the hosts whose project MCP file `render --write-project` writes
CONTRACT_STATUSES = ("captured", "unavailable", "needs-sign-in", "open", "skipped")
OFFLINE_LAUNCHERS = ("npx", "uvx")  # the launchers that take --offline: they run what is already installed instead of downloading
MARKER = ".toolchain-managed.json"
MODE_CEILINGS = {  # the widest allow rules that the untrusted modes may be given (dev has none)
    "agent": {"network": ("none",), "credentials": ("none",), "access": ("read",)},
    "executor": {"network": ("none", "microsoft-cloud"), "credentials": ("none", "azure-identity"), "access": ("read",)},
}
RENDER_HINT = "run: python scripts/toolchain.py render --write-project"
INSTALL_HINT = "run: python scripts/toolchain.py install --apply"
CLAUDE_HINT = INSTALL_HINT + " --host claude-code"  # render --write-project never writes the .mcp.json of Claude Code
DEFAULT_HOSTS = ("copilot-cli", "vscode")  # what install and verify --live work on without --host: Claude Code only when it is asked for
LOCK_HINT = "run `python scripts/toolchain.py lock`"
NO_LOCK_SKILLS = "it selects skills, but there is no lock to resolve them from"

ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
SKILL_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
SHARED_FOLDER_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
RESERVED_FOLDERS = ("skills",)  # the folder that holds the skills, beside which a shared folder is installed
ENV_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
ENV_DEFAULT_RE = re.compile(r"[A-Za-z0-9._:/-]{1,64}")
SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
MIN_VERSION_RE = re.compile(r"\d+(?:\.\d+)*")
# What may follow the numbers of a version: -beta.2, +build, a letter right after them (1.8.0rc1) or after a dot (1.8.0.post1, 1.8.0.dev3).
# A dot that no letter follows, and a dot that would end the suffix, close a sentence ("fab 1.8.0.") and are not part of the version.
# read_version reads the same grammar.
VERSION_SUFFIX = r"(?:(?:-|\+|\.(?=[A-Za-z])|(?=[A-Za-z]))[0-9A-Za-z](?:[0-9A-Za-z.+-]*[0-9A-Za-z+-])?)?"
EXACT_VERSION_RE = re.compile(r"\d+(?:\.\d+)+" + VERSION_SUFFIX)
READ_VERSION_RE = re.compile(r"(\d+(?:\.\d+)+)(" + VERSION_SUFFIX + ")")
NPM_EXACT_RE = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z][0-9A-Za-z.+-]*)?")
LOCK_VERSION_RE = re.compile(r"[^\s\x00-\x1f\x7f]{1,64}")
NPM_NAME_RE = re.compile(r"(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*")
OTHER_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
TAG_GLOB_RE = re.compile(r"[A-Za-z0-9*?][A-Za-z0-9._*?-]*")
BRANCH_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")
HEADER_NAME_RE = re.compile(r"[A-Za-z0-9-]+")
DETAIL_RE = re.compile(r"[A-Za-z0-9 ._:=/-]{0,80}")
SERVER_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}")
# What a server calls its version: a digit first (after an optional v), at most 64 characters, and no run of two or more dotted
# alphabetic labels, which would be a host name. "unknown" stands for what a probe said that is not plain.
SERVER_VERSION_RE = re.compile(r"unknown|(?=.{1,64}\Z)(?!.*[A-Za-z]{2,}(?:\.[A-Za-z]{2,})+)v?[0-9][0-9A-Za-z.+_~-]*")
TOOL_NAME_RE = re.compile(r"[A-Za-z0-9_.-]{1,128}")
NPM_INTEGRITY_RE = re.compile(r"sha512-[A-Za-z0-9+/]{16,}={0,2}")
NUGET_INTEGRITY_RE = re.compile(r"sha256-[A-Za-z0-9+/]{16,}={0,2}")
HEX64_RE = re.compile(r"[0-9a-f]{64}")
INTEGRITY_FIELD = {"npm": "integrity", "pypi": "sha256", "nuget": "integrity"}
INTEGRITY_FORM = {"npm": NPM_INTEGRITY_RE, "pypi": HEX64_RE, "nuget": NUGET_INTEGRITY_RE}
INTEGRITY_WORDS = {"npm": "a sha512 integrity string", "pypi": "64 lower-case hex digits or null", "nuget": "a sha256 integrity string or null"}
PACKAGE_REASONS = ("network", "unresolved")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
SECRET_HEADERS = {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key", "api-key",
                  "ocp-apim-subscription-key", "x-functions-key"}


class ToolchainError(Exception):
    """A fail-closed refusal. `problems` holds every reason when there are several."""

    def __init__(self, message, problems=None):
        super().__init__(message)
        self.problems = list(problems) if problems else [message]


class UsageError(ToolchainError):
    """The command line asks for something that does not exist (exit status 2)."""


class Profiles(dict):
    """The parsed profiles file. `base` is the toolchain folder that the instruction paths are relative to."""

    base = None


class Lock(dict):
    """The parsed lock. `digest` is the digest of the file it was read from (line endings normalised)."""

    digest = None


# ---------------------------------------------------------------- files

def read_text_lf(path, label=None):
    """A text file as str with the byte-order mark dropped and CRLF turned into LF, so a Windows checkout compares equal."""
    label = label or Path(path).name
    try:
        return Path(path).read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
    except OSError as exc:
        raise ToolchainError("%s: cannot read the file (%s)" % (label, type(exc).__name__))
    except UnicodeDecodeError:
        raise ToolchainError("%s: the file is not valid UTF-8" % label)


def digest_text(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _unique_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate key '%s'" % key)
        out[key] = value
    return out


def _refuse_constant(name):
    raise ValueError("the constant %s is not allowed" % name)


def parse_json(text, label):
    try:
        return json.loads(text, object_pairs_hook=_unique_keys, parse_constant=_refuse_constant)
    except ValueError as exc:
        raise ToolchainError("%s: not valid JSON (%s)" % (label, str(exc)[:120]))


def read_json(path, label=None):
    label = label or Path(path).name
    return parse_json(read_text_lf(path, label), label)


def dump_json(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def write_atomic(path, text):
    """Write LF-only text next to its target and swap it in, so a reader never sees half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=str(path.parent), prefix="toolchain-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
        toolchain_io.replace_retrying(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


def write_stdout(text):
    """Print generated text with LF endings even where the console would turn them into CRLF."""
    raw = getattr(sys.stdout, "buffer", None)
    if raw is None:
        sys.stdout.write(text)
        return
    sys.stdout.flush()
    raw.write(text.encode("utf-8"))
    raw.flush()


def remove_tree(path):
    """Remove a folder, also one with read-only files, and wait for what Windows refuses to delete for a moment.

    What is not a real folder is unlinked: a file, or a link, whose target is left alone."""
    def retry(function, target, _info):
        toolchain_io.make_writable(target)
        function(target)

    def unlink_link():
        try:
            os.unlink(path)
        except OSError as refused:
            try:
                os.rmdir(path)  # Windows removes a junction like an empty folder
            except OSError:
                raise refused from None  # what the link itself said: a file link that is held for a moment is a PermissionError, which is waited for

    if is_link(path):
        toolchain_io.retrying(unlink_link)
    elif os.path.isdir(path):
        toolchain_io.retrying(lambda: shutil.rmtree(path, onerror=retry))
    else:
        toolchain_io.make_writable(path)
        toolchain_io.retrying(lambda: os.unlink(path))


def display_path(path, root, home):
    """A path for a message: relative to the project, or with the home folder written as $HOME, never a user name."""
    path = Path(path)
    for base, prefix in ((root, ""), (home, "$HOME/")):
        try:
            relative = path.resolve().relative_to(Path(base).resolve()).as_posix()
        except (ValueError, OSError):
            continue
        return prefix + relative if relative != "." else (prefix.rstrip("/") or ".")
    return path.name


def expand_home(value, home):
    return value.replace("$HOME", str(home), 1) if value.startswith("$HOME/") else value


def license_accepted(env, name):
    """The operator accepted a license when the variable holds exactly `true` (any case). The kit never sets it."""
    return str(env.get(name, "")).lower() == "true"


class Deps:
    """The outside world: runner, resolvers, probes, environment, home folder and clock. Tests pass fakes."""

    _HOME = {
        "resolve_git_ref": toolchain_sources, "fetch_git": toolchain_sources, "read_plugin": toolchain_sources,
        "read_shared_entries": toolchain_sources, "lint_skill": toolchain_sources,
        "resolve_package": toolchain_sources, "vendor_skills": toolchain_sources, "digest_tree": toolchain_sources,
        "probe_stdio": toolchain_mcp, "probe_http": toolchain_mcp, "contract_diff": toolchain_mcp,
    }

    def __init__(self, runner=None, env=None, home=None, clock=None, **functions):
        unknown = sorted(set(functions) - set(self._HOME))
        if unknown:
            raise TypeError("unknown dependency: %s" % ", ".join(unknown))
        self._runner = runner
        self.env = os.environ if env is None else env
        self._home = home
        self.clock = clock or (lambda: datetime.datetime.now(datetime.timezone.utc))
        self._functions = functions

    @property
    def runner(self):
        if self._runner is None:
            self._runner = toolchain_io.SystemRunner()
        return self._runner

    @property
    def home(self):
        return Path(self._home) if self._home is not None else Path.home()

    def today(self):
        return self.clock().astimezone(datetime.timezone.utc).strftime("%Y-%m-%d")

    def stamp(self):
        return self.clock().astimezone(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def derive(self, **functions):
        """The same outside world with some of its functions replaced."""
        return Deps(runner=self._runner, env=self.env, home=self._home, clock=self.clock, **dict(self._functions, **functions))

    def __getattr__(self, name):
        functions = self.__dict__.get("_functions", {})
        if name in functions:
            return functions[name]
        module = self._HOME.get(name)
        if module is None:
            raise AttributeError(name)
        return getattr(module, name)


# ---------------------------------------------------------------- schema checks (each returns problems as text)

def _shown(value):
    return str(value).replace("\n", " ")[:40]


def _keys(value, where, out, required=(), optional=()):
    if not isinstance(value, dict):
        out.append("%s: must be an object" % where)
        return False
    for key in required:
        if key not in value:
            out.append("%s: missing key '%s'" % (where, key))
    for key in value:
        if key not in required and key not in optional:
            out.append("%s: unknown key '%s'" % (where, key))
    return True


def _text(value, where, out, pattern=None, limit=2000):
    if not isinstance(value, str) or not value.strip():
        out.append("%s: must be a non-empty string" % where)
        return False
    if len(value) > limit or CONTROL_RE.search(value):
        out.append("%s: is too long or holds a control character" % where)
        return False
    if pattern is not None and not pattern.fullmatch(value):
        out.append("%s: '%s' is not an allowed value" % (where, _shown(value)))
        return False
    return True


def _enum(value, where, out, vocabulary):
    if not isinstance(value, str) or value not in vocabulary:
        out.append("%s: '%s' is not one of: %s" % (where, _shown(value), ", ".join(vocabulary)))
        return False
    return True


def _date(value, where, out):
    """A YYYY-MM-DD text that names a real day."""
    if not _text(value, where, out, DATE_RE):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        out.append("%s: '%s' is not a real date" % (where, _shown(value)))
        return False
    return True


def _list(value, where, out):
    if not isinstance(value, list):
        out.append("%s: must be a list" % where)
        return False
    return True


def _text_list(value, where, out, pattern=None, unique=True, minimum=0):
    if not _list(value, where, out):
        return
    if len(value) < minimum:
        out.append("%s: must hold at least %d item(s)" % (where, minimum))
    seen = set()
    for index, item in enumerate(value):
        _text(item, "%s[%d]" % (where, index), out, pattern)
        if unique and isinstance(item, str):
            if item in seen:
                out.append("%s: '%s' is listed twice" % (where, _shown(item)))
            seen.add(item)


def _enum_list(value, where, out, vocabulary):
    if _list(value, where, out):
        if not value:
            out.append("%s: must not be empty" % where)
        seen = set()
        for index, item in enumerate(value):
            _enum(item, "%s[%d]" % (where, index), out, vocabulary)
            if item in seen:
                out.append("%s: '%s' is listed twice" % (where, _shown(item)))
            seen.add(item)


def _flag(value, where, out):
    if not isinstance(value, bool):
        out.append("%s: must be true or false" % where)


def _count(value, where, out):
    if type(value) is not int or value < 0:
        out.append("%s: must be a whole number, zero or more" % where)


def _schema(value, where, out):
    if type(value) is not int or value != SCHEMA:
        out.append("%s: must be %d" % (where, SCHEMA))


def _relpath(value, where, out):
    if not _text(value, where, out, limit=200):
        return False
    if (value.startswith("/") or "\\" in value or re.match(r"[A-Za-z]:", value)
            or any(part in ("", ".", "..") for part in value.split("/"))):
        out.append("%s: '%s' must be a relative path with forward slashes and no '..'" % (where, _shown(value)))
        return False
    return True


def _homepath(value, where, out):
    if not _text(value, where, out, limit=200):
        return
    if not value.startswith("$HOME/"):
        out.append("%s: '%s' must start with $HOME/" % (where, _shown(value)))
    else:
        _relpath(value[len("$HOME/"):], where, out)


def _url(value, where, out):
    if not _text(value, where, out, limit=400):
        return False
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment
            or any(ch.isspace() for ch in value)):
        out.append("%s: '%s' must be an https URL without credentials" % (where, _shown(value)))
        return False
    return True


def _url_list(value, where, out):
    if _list(value, where, out):
        for index, item in enumerate(value):
            _url(item, "%s[%d]" % (where, index), out)


def _detail(value, where, out):
    if not isinstance(value, str) or not DETAIL_RE.fullmatch(value):
        out.append("%s: must be at most 80 characters from [A-Za-z0-9 ._:=/-]" % where)
    elif toolchain_io.safe_detail(value) != " ".join(value.split()):  # a text that the shared filter would have cut something out of
        out.append("%s: must not hold a URL or a host name, a path, an address or a secret" % where)


def _check_modes(modes, out):
    if not isinstance(modes, dict) or not modes:
        out.append("modes: must be a non-empty object")
        return
    for mode, spec in modes.items():
        where = "modes.%s" % mode
        if mode not in MODES:
            out.append("%s: unknown mode (allowed: %s)" % (where, ", ".join(MODES)))
        if not _keys(spec, where, out, ("allow",), ("summary",)):
            continue
        if "summary" in spec:
            _text(spec["summary"], where + ".summary", out)
        allow = spec.get("allow")
        if not _keys(allow, where + ".allow", out, ("network", "credentials", "access", "unattended")):
            continue
        _enum_list(allow.get("network"), where + ".allow.network", out, NETWORKS)
        _enum_list(allow.get("credentials"), where + ".allow.credentials", out, CREDENTIALS)
        _enum_list(allow.get("access"), where + ".allow.access", out, ACCESS)
        _enum(allow.get("unattended"), where + ".allow.unattended", out, ("any", "required"))
        ceiling = MODE_CEILINGS.get(mode)
        if ceiling:
            for key in ("network", "credentials", "access"):
                for value in allow.get(key) if isinstance(allow.get(key), list) else ():
                    if isinstance(value, str) and value not in ceiling[key]:
                        out.append("%s.allow.%s: mode %s may not allow %s '%s'" % (where, key, mode, key, value))
            if allow.get("unattended") == "any":
                out.append("%s.allow.unattended: mode %s may not allow unattended 'any' (it must be \"required\")" % (where, mode))


def _check_hosts(hosts, out):
    if not isinstance(hosts, dict) or not hosts:
        out.append("hosts: must be a non-empty object")
        return
    for host, spec in hosts.items():
        where = "hosts.%s" % host
        if host not in HOSTS:
            out.append("%s: unknown host (allowed: %s)" % (where, ", ".join(HOSTS)))
        if not _keys(spec, where, out, ("binary", "mcp_project", "skills_project"), ("title", "mcp_user", "skills_user", "docs")):
            continue
        if "title" in spec:
            _text(spec["title"], where + ".title", out)
        _text(spec.get("binary"), where + ".binary", out, ID_RE)
        _relpath(spec.get("mcp_project"), where + ".mcp_project", out)
        _relpath(spec.get("skills_project"), where + ".skills_project", out)
        for key in ("mcp_user", "skills_user"):
            if spec.get(key) is not None:
                _homepath(spec[key], "%s.%s" % (where, key), out)
        if "docs" in spec:
            _url_list(spec["docs"], where + ".docs", out)


def _check_package(package, where, out):
    if not _keys(package, where, out, ("ecosystem", "name", "track")):
        return
    ecosystem = package.get("ecosystem")
    if _enum(ecosystem, where + ".ecosystem", out, ECOSYSTEMS):
        _text(package.get("name"), where + ".name", out, NPM_NAME_RE if ecosystem == "npm" else OTHER_NAME_RE)
    track = package.get("track")
    if track != "latest" and not (isinstance(track, str) and EXACT_VERSION_RE.fullmatch(track)):
        out.append("%s.track: '%s' must be \"latest\" or an exact version" % (where, _shown(track)))


def _label(kind, index, item):
    """A name for a list entry in a message: its id when it has a valid one, its position otherwise."""
    ident = item.get("id") if isinstance(item, dict) else None
    return "%s.%s" % (kind, ident) if isinstance(ident, str) and ID_RE.fullmatch(ident) else "%s[%d]" % (kind, index)


def _check_tools(tools, out):
    if not _list(tools, "tools", out):
        return
    seen = set()
    for index, tool in enumerate(tools):
        where = _label("tools", index, tool)
        if not _keys(tool, where, out, ("id", "command", "version_args", "min", "needed_for", "required"),
                     ("alternatives", "package")):
            continue
        if _text(tool.get("id"), where + ".id", out, ID_RE):
            if tool["id"] in seen:
                out.append("%s: duplicate tool id" % where)
            seen.add(tool["id"])
        _text(tool.get("command"), where + ".command", out, ID_RE)
        _text_list(tool.get("version_args"), where + ".version_args", out, unique=False, minimum=1)
        if "alternatives" in tool:
            _text_list(tool["alternatives"], where + ".alternatives", out, ID_RE)
        _text(tool.get("min"), where + ".min", out, MIN_VERSION_RE)
        _text(tool.get("needed_for"), where + ".needed_for", out)
        _flag(tool.get("required"), where + ".required", out)
        if "package" in tool:
            _check_package(tool["package"], where + ".package", out)


def _check_track(track, where, out):
    if not isinstance(track, dict):
        out.append("%s: must be an object" % where)
        return
    kind = track.get("kind")
    if kind == "tag":
        if _keys(track, where, out, ("kind", "pattern")):
            _text(track.get("pattern"), where + ".pattern", out, TAG_GLOB_RE, limit=80)
    elif kind == "branch":
        if _keys(track, where, out, ("kind", "name")):
            _text(track.get("name"), where + ".name", out, BRANCH_RE, limit=120)
    elif kind == "commit":
        if _keys(track, where, out, ("kind", "sha")):
            _text(track.get("sha"), where + ".sha", out, COMMIT_RE)
    else:
        out.append("%s: kind '%s' is not one of: tag, branch, commit" % (where, _shown(kind)))


def _check_shared(shared, where, plugin_names, source_id, taken, out):
    """The folders at the root of a plugin that the skills of every plugin of the source reach as ../../<folder>/."""
    if not _list(shared, where, out):
        return
    for index, item in enumerate(shared):
        sw = "%s[%d]" % (where, index)
        if not _keys(item, sw, out, ("folder", "plugin")):
            continue
        folder = item.get("folder")
        if _text(folder, sw + ".folder", out, SHARED_FOLDER_RE):
            if folder in RESERVED_FOLDERS:
                out.append("%s.folder: '%s' is reserved (it is the skills folder)" % (sw, folder))
            elif folder in taken and taken[folder] == source_id:
                out.append("%s.folder: '%s' is listed twice" % (sw, folder))
            elif folder in taken:
                out.append("%s.folder: '%s' is already declared by skill source '%s'" % (sw, folder, taken[folder]))
            else:
                taken[folder] = source_id
        if _text(item.get("plugin"), sw + ".plugin", out, ID_RE) and item["plugin"] not in plugin_names:
            out.append("%s.plugin: '%s' is not a plugin of skill source '%s'" % (sw, item["plugin"], source_id))


def _check_sources(sources, out):
    ids = set()
    folders = {}
    if not _list(sources, "skill_sources", out):
        return ids
    for index, source in enumerate(sources):
        where = _label("skill_sources", index, source)
        if not _keys(source, where, out, ("id", "repo", "track", "plugins"), ("title", "marketplace", "license", "notes", "shared")):
            continue
        if _text(source.get("id"), where + ".id", out, ID_RE):
            if source["id"] in ids:
                out.append("%s: duplicate source id" % where)
            ids.add(source["id"])
        for key in ("title", "marketplace", "license", "notes"):
            if key in source:
                _text(source[key], "%s.%s" % (where, key), out)
        _url(source.get("repo"), where + ".repo", out)
        _check_track(source.get("track"), where + ".track", out)
        plugins = source.get("plugins")
        if not _list(plugins, where + ".plugins", out):
            continue
        if not plugins:
            out.append("%s.plugins: must not be empty" % where)
        names = set()
        for position, plugin in enumerate(plugins):
            pw = "%s.plugins[%d]" % (where, position)
            if not _keys(plugin, pw, out, ("name", "path")):
                continue
            if _text(plugin.get("name"), pw + ".name", out, ID_RE):
                if plugin["name"] in names:
                    out.append("%s: duplicate plugin name '%s'" % (pw, plugin["name"]))
                names.add(plugin["name"])
            _relpath(plugin.get("path"), pw + ".path", out)
        if "shared" in source:
            _check_shared(source["shared"], where + ".shared", names, source.get("id"), folders, out)
    return ids


def _check_quarantine(quarantine, source_ids, out):
    if not _list(quarantine, "quarantine", out):
        return
    seen = set()
    for index, item in enumerate(quarantine):
        where = "quarantine[%d]" % index
        if not _keys(item, where, out, ("source", "skill", "reason"), ("design",)):
            continue
        if _text(item.get("source"), where + ".source", out, ID_RE) and item["source"] not in source_ids:
            out.append("%s.source: '%s' is not a skill source of the manifest" % (where, item["source"]))
        _text(item.get("skill"), where + ".skill", out, SKILL_RE)
        _text(item.get("reason"), where + ".reason", out)
        if "design" in item:
            _text(item["design"], where + ".design", out)
        pair = (item.get("source"), item.get("skill"))
        if pair in seen:
            out.append("%s: '%s' is quarantined twice" % (where, _shown(item.get("skill"))))
        seen.add(pair)


def _env_map(env, where, out):
    if not isinstance(env, dict):
        out.append("%s: must be an object" % where)
        return
    for name, spec in env.items():
        item = "%s.%s" % (where, name)
        if not ENV_NAME_RE.fullmatch(name):
            out.append("%s: not a valid variable name" % item)
        if not _keys(spec, item, out, ("from_env",), ("default",)):
            continue
        _text(spec.get("from_env"), item + ".from_env", out, ENV_NAME_RE)
        if "default" in spec:
            _text(spec["default"], item + ".default", out, ENV_DEFAULT_RE)


def _headers(headers, where, out):
    if not isinstance(headers, dict):
        out.append("%s: must be an object" % where)
        return
    for name, value in headers.items():
        item = "%s.%s" % (where, name)
        if not HEADER_NAME_RE.fullmatch(name):
            out.append("%s: not a valid header name" % item)
        elif name.lower() in SECRET_HEADERS:
            out.append("%s: a header that carries a credential must not be written into the manifest" % item)
        _text(value, item, out, limit=200)


def _check_variant(variant, where, transport, out):
    if not _keys(variant, where, out, ("credentials", "network", "access", "unattended"), ("summary", "args", "env", "tools_read_only")):
        return
    _enum(variant.get("credentials"), where + ".credentials", out, CREDENTIALS)
    _enum(variant.get("network"), where + ".network", out, NETWORKS)
    _enum(variant.get("access"), where + ".access", out, ACCESS)
    unattended = variant.get("unattended")
    if not (unattended is True or unattended is False or unattended == "unverified"):
        out.append("%s.unattended: '%s' is not one of: true, false, \"unverified\"" % (where, _shown(unattended)))
    if "tools_read_only" in variant:
        promise = variant["tools_read_only"]
        if not isinstance(promise, bool):
            out.append("%s.tools_read_only: '%s' is not true or false" % (where, _shown(promise)))
        elif promise and variant.get("access") != "read":
            out.append("%s.tools_read_only: only a variant with access \"read\" can promise read-only tools" % where)
        elif promise and transport == "http":
            out.append("%s.tools_read_only: an http variant cannot be checked, its tools are not captured" % where)
    if "summary" in variant:
        _text(variant["summary"], where + ".summary", out)
    if transport == "http" and ("args" in variant or "env" in variant):
        out.append("%s: an http variant has no args and no env" % where)
    if "args" in variant:
        _text_list(variant["args"], where + ".args", out, unique=False)
        if isinstance(variant["args"], list) and any(isinstance(a, str) and "{package}" in a for a in variant["args"]):
            out.append("%s.args: the {package} placeholder belongs in launch.args only" % where)
    if "env" in variant:
        _env_map(variant["env"], where + ".env", out)


def _check_servers(servers, out):
    if not _list(servers, "mcp_servers", out):
        return
    seen = set()
    for index, server in enumerate(servers):
        where = _label("mcp_servers", index, server)
        if not _keys(server, where, out, ("id", "transport", "status", "variants"),
                     ("title", "summary", "docs", "url", "headers", "package", "launch", "eula", "env")):
            continue
        if _text(server.get("id"), where + ".id", out, ID_RE):
            if server["id"] in seen:
                out.append("%s: duplicate server id" % where)
            seen.add(server["id"])
        transport = server.get("transport")
        _enum(transport, where + ".transport", out, TRANSPORTS)
        _enum(server.get("status"), where + ".status", out, STATUSES)
        for key in ("title", "summary"):
            if key in server:
                _text(server[key], "%s.%s" % (where, key), out)
        if "docs" in server:
            _url_list(server["docs"], where + ".docs", out)
        if transport == "http":
            if "url" not in server:
                out.append("%s: an http server needs a url" % where)
            else:
                _url(server["url"], where + ".url", out)
            if "headers" in server:
                _headers(server["headers"], where + ".headers", out)
            for key in ("package", "launch", "eula", "env"):
                if key in server:
                    out.append("%s: an http server must not have '%s'" % (where, key))
        elif transport == "stdio":
            for key in ("url", "headers"):
                if key in server:
                    out.append("%s: a stdio server must not have '%s'" % (where, key))
            for key in ("package", "launch"):
                if key not in server:
                    out.append("%s: a stdio server needs a '%s'" % (where, key))
            if "package" in server:
                _check_package(server["package"], where + ".package", out)
            if "launch" in server:
                _check_launch(server["launch"], where + ".launch", out)
            if "env" in server:
                _env_map(server["env"], where + ".env", out)
            if "eula" in server:
                _check_eula(server, where, out)
        variants = server.get("variants")
        if not isinstance(variants, dict) or not variants:
            out.append("%s.variants: must be a non-empty object" % where)
            continue
        eula = server.get("eula")
        license_env = eula.get("env") if isinstance(eula, dict) else None
        for name, variant in variants.items():
            if not ID_RE.fullmatch(name):
                out.append("%s.variants: '%s' is not a valid variant name" % (where, _shown(name)))
            _check_variant(variant, "%s.variants.%s" % (where, name), transport, out)
            if license_env and isinstance(variant, dict) and isinstance(variant.get("env"), dict) and license_env in variant["env"]:
                out.append("%s.variants.%s.env.%s: the license variable is set at the server level only" % (where, name, license_env))


def _check_launch(launch, where, out):
    if not _keys(launch, where, out, ("command", "args")):
        return
    _text(launch.get("command"), where + ".command", out, ID_RE)
    args = launch.get("args")
    _text_list(args, where + ".args", out, unique=False)
    if isinstance(args, list) and not any(isinstance(a, str) and "{package}" in a for a in args):
        out.append("%s.args: must hold the {package} placeholder, or the launch would not use the locked version" % where)


def _check_eula(server, where, out):
    eula = server["eula"]
    if not _keys(eula, where + ".eula", out, ("url", "accept", "env")):
        return
    _url(eula.get("url"), where + ".eula.url", out)
    _enum(eula.get("accept"), where + ".eula.accept", out, ("operator",))
    if not _text(eula.get("env"), where + ".eula.env", out, ENV_NAME_RE):
        return
    passed = server.get("env", {}).get(eula["env"]) if isinstance(server.get("env"), dict) else None
    if not isinstance(passed, dict) or passed.get("from_env") != eula["env"]:
        out.append("%s.env: must pass %s through, so the operator can accept the license" % (where, eula["env"]))
    elif str(passed.get("default", "")).lower() != "false":
        out.append("%s.env.%s: the license variable must default to \"false\"" % (where, eula["env"]))


def _iter_packages(manifest):
    for kind, items in (("mcp_servers", manifest.get("mcp_servers")), ("tools", manifest.get("tools"))):
        for item in items if isinstance(items, list) else ():
            package = item.get("package") if isinstance(item, dict) else None
            if isinstance(package, dict) and isinstance(package.get("ecosystem"), str) and isinstance(package.get("name"), str):
                yield "%s.%s" % (kind, item.get("id")), package


def _check_package_conflicts(manifest, out):
    seen = {}
    for where, package in _iter_packages(manifest):
        key = "%s:%s" % (package["ecosystem"], package["name"])
        if key in seen and seen[key][1] != package:
            out.append("%s.package: %s is declared with a different track than in %s" % (where, key, seen[key][0]))
        seen.setdefault(key, (where, package))


def validate_manifest(manifest):
    out = []
    if not _keys(manifest, "manifest", out, ("schema", "default_profile", "modes", "hosts", "skill_sources", "mcp_servers"),
                 ("name", "about", "store", "tools", "quarantine", "update")):
        return out
    _schema(manifest.get("schema"), "schema", out)
    for key in ("name", "about"):
        if key in manifest:
            _text(manifest[key], key, out)
    _text(manifest.get("default_profile"), "default_profile", out, ID_RE)
    if "store" in manifest:
        _relpath(manifest["store"], "store", out)
    _check_modes(manifest.get("modes"), out)
    _check_hosts(manifest.get("hosts"), out)
    _check_tools(manifest.get("tools", []), out)
    source_ids = _check_sources(manifest.get("skill_sources"), out)
    _check_quarantine(manifest.get("quarantine", []), source_ids, out)
    _check_servers(manifest.get("mcp_servers"), out)
    if "update" in manifest and _keys(manifest["update"], "update", out, (), ("policy", "weekly_check")):
        if "policy" in manifest["update"]:
            _text(manifest["update"]["policy"], "update.policy", out)
        if "weekly_check" in manifest["update"]:
            _flag(manifest["update"]["weekly_check"], "update.weekly_check", out)
    _check_package_conflicts(manifest, out)
    return out


def validate_profiles(data):
    out = []
    if not _keys(data, "profiles file", out, ("schema", "profiles"), ("about",)):
        return out
    _schema(data.get("schema"), "schema", out)
    if "about" in data:
        _text(data["about"], "about", out)
    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        out.append("profiles: must be a non-empty object")
        return out
    for name, profile in profiles.items():
        where = "profiles.%s" % name
        if not ID_RE.fullmatch(name):
            out.append("profiles: '%s' is not a valid profile name" % _shown(name))
        if not _keys(profile, where, out, ("mode", "skills", "mcp", "instructions"), ("title", "design", "summary", "tools")):
            continue
        _enum(profile.get("mode"), where + ".mode", out, MODES)
        for key in ("title", "design", "summary"):
            if key in profile:
                _text(profile[key], "%s.%s" % (where, key), out)
        if "tools" in profile:
            _text_list(profile["tools"], where + ".tools", out, ID_RE)
        if _list(profile.get("skills"), where + ".skills", out):
            for index, selector in enumerate(profile["skills"]):
                sw = "%s.skills[%d]" % (where, index)
                if not _keys(selector, sw, out, ("source", "plugin", "names")):
                    continue
                _text(selector.get("source"), sw + ".source", out, ID_RE)
                _text(selector.get("plugin"), sw + ".plugin", out, ID_RE)
                names = selector.get("names")
                if names != "*":
                    _text_list(names, sw + ".names", out, SKILL_RE, minimum=1)
        if _list(profile.get("mcp"), where + ".mcp", out):
            for index, entry in enumerate(profile["mcp"]):
                mw = "%s.mcp[%d]" % (where, index)
                if _keys(entry, mw, out, ("server", "variant")):
                    _text(entry.get("server"), mw + ".server", out, ID_RE)
                    _text(entry.get("variant"), mw + ".variant", out, ID_RE)
        if _list(profile.get("instructions"), where + ".instructions", out):
            seen = set()
            for index, path in enumerate(profile["instructions"]):
                _relpath(path, "%s.instructions[%d]" % (where, index), out)
                if path in seen:
                    out.append("%s.instructions: '%s' is listed twice" % (where, _shown(path)))
                seen.add(path)
    return out


def _check_tool_entry(tool, where, out):
    if _keys(tool, where, out, ("schema", "read_only", "destructive", "idempotent")):
        if not isinstance(tool.get("schema"), str) or not SHA256_RE.fullmatch(tool["schema"]):
            out.append("%s.schema: must be a sha256 digest" % where)
        for key in ("read_only", "destructive", "idempotent"):
            if tool.get(key) is not None and not isinstance(tool.get(key), bool):
                out.append("%s.%s: must be true, false or null" % (where, key))


def _check_tools_map(tools, where, out):
    if not isinstance(tools, dict):
        out.append("%s: must be an object" % where)
        return
    for name, tool in tools.items():
        if not isinstance(name, str) or not TOOL_NAME_RE.fullmatch(name):
            out.append("%s: '%s' is not a valid tool name" % (where, _shown(name)))
        _check_tool_entry(tool, "%s.%s" % (where, _shown(name)), out)


def _check_contract(contract, where, out):
    if not isinstance(contract, dict):
        out.append("%s: must be an object" % where)
        return
    status = contract.get("status")
    if not _enum(status, where + ".status", out, CONTRACT_STATUSES):
        return
    if status == "captured":
        if _keys(contract, where, out, ("status", "era", "protocol", "server", "package_version", "launch", "captured", "tools")):
            _enum(contract.get("era"), where + ".era", out, ("legacy", "modern"))
            _text(contract.get("protocol"), where + ".protocol", out, DATE_RE)
            if _keys(contract.get("server"), where + ".server", out, ("name", "version")):
                for key, pattern in (("name", SERVER_NAME_RE), ("version", SERVER_VERSION_RE)):
                    value = contract["server"].get(key)
                    if _text(value, "%s.server.%s" % (where, key), out, pattern) and toolchain_mcp.suspect(value):
                        out.append("%s.server.%s: must not read like a token, a host name or an address" % (where, key))
            _text(contract.get("package_version"), where + ".package_version", out, LOCK_VERSION_RE)
            _text(contract.get("launch"), where + ".launch", out, SHA256_RE)
            _date(contract.get("captured"), where + ".captured", out)
            _check_tools_map(contract.get("tools"), where + ".tools", out)
    elif status == "needs-sign-in":
        _keys(contract, where, out, ("status",))
    elif status == "open":
        if _keys(contract, where, out, ("status",), ("tools",)) and "tools" in contract:
            _check_tools_map(contract["tools"], where + ".tools", out)
    elif _keys(contract, where, out, ("status", "reason"), ("detail",)):
        _enum(contract.get("reason"), where + ".reason", out, REASONS)
        if "detail" in contract:
            _detail(contract["detail"], where + ".detail", out)


def _check_lock_package(entry, where, out, ecosystem=None):
    if not isinstance(entry, dict):
        out.append("%s: must be an object" % where)
        return
    status = entry.get("status")
    if status == "resolved":
        field = INTEGRITY_FIELD.get(ecosystem)
        optional = ("integrity", "sha256") if field is None else (field,)
        required = ("status", "version", "via") + (("integrity",) if ecosystem == "npm" else ())
        if _keys(entry, where, out, required, tuple(k for k in optional if k not in required)):
            _text(entry.get("version"), where + ".version", out, LOCK_VERSION_RE)
            _text(entry.get("via"), where + ".via", out, re.compile(r"[a-z0-9-]{1,20}"))
            if field is None:
                for key in ("integrity", "sha256"):
                    if entry.get(key) is not None:
                        _text(entry[key], "%s.%s" % (where, key), out, re.compile(r"[A-Za-z0-9+/=:_-]{8,200}"))
            elif entry.get(field) is not None or ecosystem == "npm":
                if not isinstance(entry.get(field), str) or not INTEGRITY_FORM[ecosystem].fullmatch(entry[field]):
                    out.append("%s.%s: must be %s" % (where, field, INTEGRITY_WORDS[ecosystem]))
    elif status == "unresolved":
        if _keys(entry, where, out, ("status", "reason"), ("detail",)):
            _enum(entry.get("reason"), where + ".reason", out, PACKAGE_REASONS)
            if "detail" in entry:
                _detail(entry["detail"], where + ".detail", out)
    else:
        out.append("%s.status: '%s' is not one of: resolved, unresolved" % (where, _shown(status)))


def _check_lock_shared(shared, where, plugin_names, out):
    if not isinstance(shared, dict):
        out.append("%s: must be an object" % where)
        return
    for folder, entry in shared.items():
        sw = "%s.%s" % (where, folder)
        if not isinstance(folder, str) or not SHARED_FOLDER_RE.fullmatch(folder) or folder in RESERVED_FOLDERS:
            out.append("%s: not a valid shared folder name" % sw)
        if not _keys(entry, sw, out, ("plugin", "digest", "files", "bytes")):
            continue
        if _text(entry.get("plugin"), sw + ".plugin", out, ID_RE) and entry["plugin"] not in plugin_names:
            out.append("%s.plugin: '%s' is not a plugin of this source" % (sw, entry["plugin"]))
        if not isinstance(entry.get("digest"), str) or not SHA256_RE.fullmatch(entry["digest"]):
            out.append("%s.digest: must be a sha256 digest" % sw)
        for key in ("files", "bytes"):
            _count(entry.get(key), "%s.%s" % (sw, key), out)


def _check_lock_sources(sources, out):
    if not isinstance(sources, dict):
        out.append("skill_sources: must be an object")
        return
    for sid, source in sources.items():
        where = "skill_sources.%s" % sid
        if not _keys(source, where, out, ("repo", "commit", "plugins"), ("tag", "shared")):
            continue
        _url(source.get("repo"), where + ".repo", out)
        if source.get("tag") is not None:
            _text(source["tag"], where + ".tag", out, limit=120)
        _text(source.get("commit"), where + ".commit", out, COMMIT_RE)
        plugins = source.get("plugins")
        if "shared" in source:
            _check_lock_shared(source["shared"], where + ".shared", set(plugins) if isinstance(plugins, dict) else set(), out)
        if not isinstance(plugins, dict):
            out.append("%s.plugins: must be an object" % where)
            continue
        for pname, plugin in plugins.items():
            pw = "%s.plugins.%s" % (where, pname)
            if not _keys(plugin, pw, out, ("path", "skills"), ("version", "agents", "bundled_mcp")):
                continue
            _relpath(plugin.get("path"), pw + ".path", out)
            if plugin.get("version") is not None:
                _text(plugin["version"], pw + ".version", out, limit=64)
            for key in ("agents", "bundled_mcp"):
                if key in plugin:
                    _text_list(plugin[key], "%s.%s" % (pw, key), out, unique=False)
            skills = plugin.get("skills")
            if not isinstance(skills, dict):
                out.append("%s.skills: must be an object" % pw)
                continue
            for name, skill in skills.items():
                sw = "%s.skills.%s" % (pw, name)
                if not SKILL_RE.fullmatch(name):
                    out.append("%s: not a valid skill name" % sw)
                if not _keys(skill, sw, out, ("path", "digest", "files", "bytes", "description_chars", "install_hints", "findings")):
                    continue
                _relpath(skill.get("path"), sw + ".path", out)
                if not isinstance(skill.get("digest"), str) or not SHA256_RE.fullmatch(skill["digest"]):
                    out.append("%s.digest: must be a sha256 digest" % sw)
                for key in ("files", "bytes", "description_chars", "install_hints"):
                    _count(skill.get(key), "%s.%s" % (sw, key), out)
                if _list(skill.get("findings"), sw + ".findings", out):
                    for index, finding in enumerate(skill["findings"]):
                        _text(finding, "%s.findings[%d]" % (sw, index), out, limit=200)


def validate_lock(lock):
    out = []
    if not _keys(lock, "lock", out, ("schema", "generated", "inputs_digest", "skill_sources", "packages", "contracts")):
        return out
    _schema(lock.get("schema"), "schema", out)
    _text(lock.get("generated"), "generated", out, DATE_RE)
    _text(lock.get("inputs_digest"), "inputs_digest", out, SHA256_RE)
    _check_lock_sources(lock.get("skill_sources"), out)
    if isinstance(lock.get("packages"), dict):
        for key, entry in lock["packages"].items():
            if not re.fullmatch(r"(?:npm|pypi|nuget):\S+", key):
                out.append("packages: '%s' is not a package key like npm:name" % _shown(key))
            _check_lock_package(entry, "packages.%s" % key, out, key.partition(":")[0] if key.partition(":")[0] in ECOSYSTEMS else None)
    else:
        out.append("packages: must be an object")
    if isinstance(lock.get("contracts"), dict):
        for key, entry in lock["contracts"].items():
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*", key):
                out.append("contracts: '%s' is not a contract key like server/variant" % _shown(key))
            _check_contract(entry, "contracts.%s" % key, out)
    else:
        out.append("contracts: must be an object")
    return out


# ---------------------------------------------------------------- loading and the model

def load_manifest(path):
    data = read_json(path, "toolchain.json")
    problems = validate_manifest(data)
    if problems:
        raise ToolchainError("toolchain.json is invalid (%d problem(s))" % len(problems), ["toolchain.json: " + p for p in problems])
    return data


def load_profiles(path):
    data = read_json(path, "profiles.json")
    problems = validate_profiles(data)
    if problems:
        raise ToolchainError("profiles.json is invalid (%d problem(s))" % len(problems), ["profiles.json: " + p for p in problems])
    profiles = Profiles(data)
    profiles.base = Path(path).parent
    return profiles


def load_lock(path):
    text = read_text_lf(path, "toolchain.lock.json")
    data = parse_json(text, "toolchain.lock.json")
    problems = validate_lock(data)
    if problems:
        raise ToolchainError("toolchain.lock.json is invalid (%d problem(s))" % len(problems), ["toolchain.lock.json: " + p for p in problems])
    lock = Lock(data)
    lock.digest = digest_text(text)
    return lock


def lock_digest(lock):
    return getattr(lock, "digest", None) or digest_text(dump_json(lock))


def package_key(package):
    return "%s:%s" % (package["ecosystem"], package["name"])


def declared_packages(manifest):
    """{"<ecosystem>:<name>": package} for every server package and every tool package."""
    packages = {}
    for _where, package in _iter_packages(manifest):
        packages.setdefault(package_key(package), dict(package))
    return packages


def inputs_digest(manifest):
    """What the lock was resolved from, and what decides how a server is launched and which mode may use it.

    A lock whose stored digest differs from this one is stale. Titles, summaries, notes, docs and statuses are left out, because
    they change nothing that is resolved or launched."""
    servers = {}
    for server in manifest["mcp_servers"]:
        servers[server["id"]] = {
            "transport": server.get("transport"), "url": server.get("url"), "headers": server.get("headers", {}),
            "launch": server.get("launch"), "package": server.get("package"), "env": server.get("env", {}), "eula": server.get("eula"),
            "variants": {name: {"args": v.get("args", []), "env": v.get("env", {}), "credentials": v["credentials"], "network": v["network"],
                                "access": v["access"], "unattended": v["unattended"], "tools_read_only": v.get("tools_read_only") is True}
                         for name, v in server["variants"].items()}}
    payload = {
        "skill_sources": [{"id": s["id"], "repo": s["repo"], "track": s["track"], "shared": s.get("shared", []),
                           "plugins": [{"name": p["name"], "path": p["path"]} for p in s["plugins"]]} for s in manifest["skill_sources"]],
        "packages": declared_packages(manifest),
        "quarantine": [{"source": q["source"], "skill": q["skill"]} for q in manifest.get("quarantine", [])],
        "servers": servers,
        "modes": {name: spec["allow"] for name, spec in manifest["modes"].items()},
    }
    return digest_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def servers_by_id(manifest):
    return {s["id"]: s for s in manifest["mcp_servers"]}


def quarantine_map(manifest):
    return {(q["source"], q["skill"]): q for q in manifest.get("quarantine", [])}


def exact_version(ecosystem, version):
    if not isinstance(version, str) or not EXACT_VERSION_RE.fullmatch(version):
        return False
    return ecosystem != "npm" or bool(NPM_EXACT_RE.fullmatch(version))


def package_spec(package, lock):
    """name@version for the locked, exact version of a package; refuses anything that could float."""
    key = package_key(package)
    entry = ((lock or {}).get("packages") or {}).get(key)
    if entry is None:
        raise ToolchainError("package %s is not in the lock" % key)
    if entry.get("status") != "resolved":
        raise ToolchainError("package %s is unresolved in the lock" % key)
    version = entry.get("version")
    if not exact_version(package["ecosystem"], version):
        raise ToolchainError("package %s has no exact version in the lock ('%s' could float)" % (key, _shown(version)))
    if package["track"] != "latest" and package["track"] != version:
        raise ToolchainError("package %s is pinned to %s in the manifest, but the lock has %s" % (key, package["track"], version))
    return package["name"] + "@" + version  # the same form for npm, uvx and dnx


def package_info(package, lock):
    entry = lock["packages"][package_key(package)]
    info = {"ecosystem": package["ecosystem"], "name": package["name"], "version": entry["version"]}
    for key in ("integrity", "sha256"):
        if entry.get(key):
            info[key] = entry[key]
    return info


def find_server(manifest, server_id, variant):
    server = servers_by_id(manifest).get(server_id)
    if server is None:
        raise ToolchainError("server '%s' is not in the manifest" % server_id)
    spec = server["variants"].get(variant)
    if spec is None:
        raise ToolchainError("server '%s' has no variant '%s'" % (server_id, variant))
    return server, spec


def server_launch(manifest, lock, server_id, variant):
    """How to start a server variant: {"transport","command","args","env","url","headers"}, with an exact package version."""
    server, spec = find_server(manifest, server_id, variant)
    if server["transport"] == "http":
        return {"transport": "http", "command": None, "args": [], "env": {}, "url": server["url"],
                "headers": dict(server.get("headers", {}))}
    pinned = package_spec(server["package"], lock)
    launch = server["launch"]
    env = copy.deepcopy(server.get("env", {}))
    env.update(copy.deepcopy(spec.get("env", {})))
    return {"transport": "stdio", "command": launch["command"],
            "args": [a.replace("{package}", pinned) for a in launch["args"]] + list(spec.get("args", [])),
            "env": env, "url": None, "headers": {}}


def launch_digest(launch):
    """The digest of how a stdio variant starts: its command, its arguments (with the exact package version) and its declared environment.

    A captured contract carries it, so that it describes the server as it was launched when it was captured and nothing else."""
    body = {"command": launch["command"], "args": launch["args"], "env": launch["env"]}
    return digest_text(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True))


def current_launch(manifest, packages, server_id, variant):
    """launch_digest of a stdio variant under the given locked packages, or None when there is no launch to compare (a hosted server, a package that cannot be pinned)."""
    try:
        launch = server_launch(manifest, {"packages": packages}, server_id, variant)
    except ToolchainError:
        return None
    return launch_digest(launch) if launch["transport"] == "stdio" else None


# ---------------------------------------------------------------- the rules of the modes

def mode_violations(mode, mode_def, server_id, variant_name, variant):
    allow = mode_def["allow"]
    out = []
    for attribute in ("network", "credentials", "access"):
        if variant[attribute] not in allow[attribute]:
            out.append("server %s/%s: %s '%s' is not allowed in mode %s (allowed: %s)"
                       % (server_id, variant_name, attribute, variant[attribute], mode, ", ".join(allow[attribute])))
    if allow["unattended"] == "required" and variant["unattended"] is not True:
        out.append("server %s/%s: unattended is %s, but mode %s needs an unattended server (true)"
                   % (server_id, variant_name, json.dumps(variant["unattended"]), mode))
    return out


def select_skills(manifest, lock, profile):
    """(entries, problems): the skills a profile loads as resolved entries, and the rules broken on the way."""
    entries, problems = [], []
    if profile["skills"] and lock is None:
        return entries, [NO_LOCK_SKILLS]
    mode = profile["mode"]
    pinned_only = mode in ("agent", "executor")
    sources = {s["id"]: s for s in manifest["skill_sources"]}
    quarantine = quarantine_map(manifest)
    for selector in profile["skills"]:
        sid, plugin, names = selector["source"], selector["plugin"], selector["names"]
        source = sources.get(sid)
        if source is None:
            problems.append("skill source '%s' is not in the manifest" % sid)
            continue
        if plugin not in [p["name"] for p in source["plugins"]]:
            problems.append("plugin '%s' is not a plugin of source '%s'" % (plugin, sid))
            continue
        locked_source = (lock.get("skill_sources") or {}).get(sid)
        locked_plugin = ((locked_source or {}).get("plugins") or {}).get(plugin)
        if locked_plugin is None:
            problems.append("the lock has no entry for %s/%s" % (sid, plugin))
            continue
        commit = locked_source.get("commit")
        if pinned_only and not (isinstance(commit, str) and COMMIT_RE.fullmatch(commit)):
            problems.append("source '%s' has no commit in the lock, and mode %s takes skills from pinned sources only" % (sid, mode))
            continue
        available = locked_plugin.get("skills") or {}
        wanted = []
        if names == "*":
            wanted = [n for n in sorted(available) if (sid, n) not in quarantine]
        else:
            for name in names:
                if (sid, name) in quarantine:
                    problems.append("skill '%s' of %s is quarantined (%s)" % (name, sid, quarantine[(sid, name)]["reason"]))
                elif name not in available:
                    problems.append("skill '%s' is not in the lock for %s/%s" % (name, sid, plugin))
                else:
                    wanted.append(name)
        for name in wanted:
            skill = available[name]
            digest = skill.get("digest")
            if pinned_only and not (isinstance(digest, str) and SHA256_RE.fullmatch(digest)):
                problems.append("skill '%s' has no digest in the lock, and mode %s takes pinned skills only" % (name, mode))
                continue
            entries.append({"source": sid, "plugin": plugin, "name": name, "commit": commit, "path": skill.get("path"),
                            "digest": digest})
    first = {}
    for entry in entries:
        other = first.setdefault(entry["name"], entry)
        if other["digest"] != entry["digest"]:
            problems.append("skill '%s' is selected from %s/%s and from %s/%s with different content"
                            % (entry["name"], other["source"], other["plugin"], entry["source"], entry["plugin"]))
    return entries, problems


def select_shared(manifest, lock, entries):
    """(shared, problems): the shared folders of the sources that supply the selected upstream skills, as resolved entries."""
    shared, problems = [], []
    used = {entry["source"] for entry in entries}
    for source in manifest["skill_sources"]:
        if source["id"] not in used:
            continue
        locked = (lock.get("skill_sources") or {}).get(source["id"]) or {}
        held = locked.get("shared") or {}
        for item in source.get("shared", []):
            entry = held.get(item["folder"])
            plugin = (locked.get("plugins") or {}).get(item["plugin"])
            if not isinstance(entry, dict) or entry.get("plugin") != item["plugin"] or plugin is None:
                problems.append("the lock has no shared folder '%s' for source '%s'" % (item["folder"], source["id"]))
                continue
            shared.append({"folder": item["folder"], "source": source["id"], "plugin": item["plugin"], "commit": locked.get("commit"),
                           "path": "%s/%s" % (plugin.get("path"), item["folder"]), "digest": entry.get("digest"),
                           "files": entry.get("files"), "bytes": entry.get("bytes")})
    return sorted(shared, key=lambda s: s["folder"]), problems


def instruction_problems(profile, base):
    out = []
    for rel in profile["instructions"]:
        parts = rel.split("/")[:-1]
        linked = next(("/".join(parts[:n]) for n in range(1, len(parts) + 1) if is_link(Path(base).joinpath(*parts[:n]))), None)
        if linked is not None:
            out.append("instructions '%s' is behind a link: its folder '%s' is a link" % (rel, linked))
            continue
        try:
            info = os.lstat(Path(base) / rel)
        except OSError:
            out.append("instructions file '%s' does not exist" % rel)
            continue
        if not stat.S_ISREG(info.st_mode):
            out.append("instructions '%s' is not a regular file" % rel)
    return out


def profile_problems(manifest, profiles, lock, name, base=None, instructions=True):
    """The rules of section 3 for one profile, as plain sentences (empty when the profile is valid)."""
    profile = profiles["profiles"][name]
    problems = []
    mode_def = manifest["modes"].get(profile["mode"])
    if mode_def is None:
        problems.append("mode '%s' is not defined in the manifest" % profile["mode"])
    servers = servers_by_id(manifest)
    listed = set()
    for entry in profile["mcp"]:
        if entry["server"] in listed:
            problems.append("server '%s' is listed twice" % entry["server"])
        listed.add(entry["server"])
        server = servers.get(entry["server"])
        if server is None:
            problems.append("server '%s' is not in the manifest" % entry["server"])
            continue
        variant = server["variants"].get(entry["variant"])
        if variant is None:
            problems.append("server '%s' has no variant '%s'" % (entry["server"], entry["variant"]))
        elif mode_def is not None:
            problems.extend(mode_violations(profile["mode"], mode_def, entry["server"], entry["variant"], variant))
    tools = {tool["id"]: tool for tool in manifest.get("tools", [])}
    for tool_id in profile.get("tools", []):
        if tool_id not in tools:
            problems.append("tool %s is not a tool of the manifest" % tool_id)
        elif "package" not in tools[tool_id]:
            problems.append("tool %s has no package, so it cannot be pinned" % tool_id)
    entries, skill_problems = select_skills(manifest, lock, profile)
    problems.extend(skill_problems)
    if lock is not None:
        problems.extend(select_shared(manifest, lock, entries)[1])
    base = base if base is not None else getattr(profiles, "base", None)
    if base is not None and (profile["skills"] or profile["mcp"]):
        try:
            owned = repo_skill_folders(base)
        except ToolchainError as exc:
            problems.extend(exc.problems)
            owned = {}
        locked_names = {entry["name"] for entry in entries}
        problems.extend("the repo-owned skill '%s' has the same name as a locked skill" % n for n in sorted(owned) if n in locked_names)
    if instructions and base is not None:
        problems.extend(instruction_problems(profile, base))
    return problems


def check_profiles(manifest, profiles, lock, base=None, only=None):
    """Every rule of section 3, for all profiles or the named ones. [] when everything is valid."""
    names = list(profiles["profiles"]) if only is None else list(only)
    problems = []
    for name in names:
        if name not in profiles["profiles"]:
            raise UsageError("profile '%s' does not exist" % name)
        problems.extend("profile %s: %s" % (name, p) for p in profile_problems(manifest, profiles, lock, name, base))
    return problems


def bundled_names(lock):
    """{lower-case name: 'source/plugin'} of the MCP servers that the locked upstream plugins bundle."""
    names = {}
    for source_id, source in (lock.get("skill_sources") or {}).items():
        for plugin_name, plugin in (source.get("plugins") or {}).items():
            for name in plugin.get("bundled_mcp") or ():
                names.setdefault(str(name).lower(), "%s/%s" % (source_id, plugin_name))
    return names


def profile_findings(manifest, profiles, lock, name, base=None):
    """[(level, check, message)] for one profile: V2 rules, V3 packages (of its servers and its tools) and contracts, V4 launch lines, V6 files,
    V8 skill findings, V10 and V11 contracts of the variants it uses, V12 names, V13 read-only promises."""
    profile = profiles["profiles"][name]
    mode = profile["mode"]
    base = base if base is not None else getattr(profiles, "base", None)
    out = [("FAIL", "V2", m) for m in profile_problems(manifest, profiles, lock, name, base, instructions=False)]
    if base is not None:
        out.extend(("FAIL", "V6", m) for m in instruction_problems(profile, base))
    if lock is None:
        return out
    servers = servers_by_id(manifest)
    taken = bundled_names(lock)
    for item in profile["mcp"]:
        server = servers.get(item["server"])
        if server is None or item["variant"] not in server["variants"]:
            continue
        label = "%s/%s" % (item["server"], item["variant"])
        clash = taken.get(item["server"].lower())
        if clash:
            out.append(("FAIL", "V12", "server %s has the name of an MCP server that the plugin %s bundles, and a host lets the plugin's "
                                       "server replace a project server of the same name (rename it in toolchain.json)" % (item["server"], clash)))
        if mode != "dev" and server["transport"] == "stdio" and server["launch"]["command"] not in OFFLINE_LAUNCHERS:
            out.append(("FAIL", "V4", "server %s launches through %s, which has no offline form; agent and executor profiles may launch only through %s"
                                      % (item["server"], _shown(server["launch"]["command"]), " or ".join(OFFLINE_LAUNCHERS))))
        contract = (lock.get("contracts") or {}).get(label) or {}
        if mode != "dev" and server["transport"] == "stdio" and contract and contract.get("status") != "captured":
            out.append(("WARN", "V10", "contract %s is %s: a change of its tools cannot be noticed before a job starts" % (label, contract.get("status"))))
        if contract.get("status") == "captured" and not contract.get("tools"):
            out.append(("FAIL", "V11", "contract %s is captured but lists no tool" % label))
        if server["variants"][item["variant"]].get("tools_read_only") is True and contract.get("status") == "captured":
            loud = sorted(t for t, info in contract["tools"].items() if info.get("read_only") is not True)
            if loud:
                more = " (+%d more)" % (len(loud) - 8) if len(loud) > 8 else ""
                out.append(("FAIL", "V13", "server %s is declared to list only read-only tools, but its locked contract has %d tool(s) that the "
                                           "server does not annotate read-only: %s%s" % (label, len(loud), ", ".join(loud[:8]), more)))
        if label not in (lock.get("contracts") or {}):
            out.append(("FAIL", "V3", "the lock has no contract entry for %s" % label))
        if "package" not in server:
            continue
        key = package_key(server["package"])
        entry = (lock.get("packages") or {}).get(key)
        if entry is None:
            out.append(("FAIL", "V3", "package %s is not in the lock" % key))
        elif entry.get("status") != "resolved":
            out.append(("WARN" if mode == "dev" else "FAIL", "V3",
                        "server %s: package %s is unresolved in the lock (%s)" % (item["server"], key, entry.get("reason"))))
        else:
            try:
                launch = server_launch(manifest, lock, item["server"], item["variant"])
            except ToolchainError as exc:
                out.append(("FAIL", "V4", "server %s: %s" % (label, exc)))
            else:
                if contract.get("status") == "captured" and contract.get("launch") != launch_digest(launch):
                    out.append(("FAIL", "V10", "contract %s was captured for another launch; capture it again (python scripts/toolchain.py lock --contracts)" % label))
    tools = {tool["id"]: tool for tool in manifest.get("tools", [])}
    for tool_id in profile.get("tools", []):
        tool = tools.get(tool_id)
        if tool is None or "package" not in tool:
            continue  # profile_problems names it
        key = package_key(tool["package"])
        entry = (lock.get("packages") or {}).get(key)
        if entry is None:
            out.append(("FAIL", "V3", "package %s is not in the lock (tool %s)" % (key, tool_id)))
        elif entry.get("status") != "resolved":
            out.append(("WARN" if mode == "dev" else "FAIL", "V3", "package %s is unresolved in the lock (tool %s)" % (key, tool_id)))
        else:
            try:
                package_spec(tool["package"], lock)
            except ToolchainError as exc:
                out.append(("FAIL", "V4", "tool %s: %s" % (tool_id, exc)))
    for entry in select_skills(manifest, lock, profile)[0]:
        locked = lock["skill_sources"][entry["source"]]["plugins"][entry["plugin"]]["skills"][entry["name"]]
        label = "%s/%s/%s" % (entry["source"], entry["plugin"], entry["name"])
        if locked.get("findings"):
            out.append(("FAIL" if mode == "agent" else "WARN", "V8", "skill %s has findings: %s" % (label, "; ".join(locked["findings"]))))
        if mode == "agent" and locked.get("install_hints", 0) > 0:
            out.append(("WARN", "V8", "skill %s has %d install step(s), which are inert in agent mode" % (label, locked["install_hints"])))
    return out


def repo_skill_findings(folders, deps):
    """[(skill name, finding)]: what the linter says about each repo-owned skill folder ({name: folder}). We own their text, so a finding fails in every mode."""
    return [(name, finding) for name, folder in folders.items() for finding in deps.lint_skill(folder).get("findings") or ()]


def resolve_profile(manifest, profiles, lock, name, base=None, deps=None):
    """Everything a host or a loader needs for one profile. Raises ToolchainError for every failure that `verify` reports for it.

    That includes the lint findings of the repo-owned skills that the profile loads. In dev mode a server whose package is
    unresolved is a warning in verify, so it is left out of the result and named in `omitted`: an unpinned launch is never rendered."""
    if name not in profiles["profiles"]:
        raise UsageError("profile '%s' does not exist" % name)
    if lock is None:
        raise ToolchainError("there is no lock (%s)" % LOCK_HINT)
    deps = deps or Deps()
    profile = profiles["profiles"][name]
    base = base if base is not None else getattr(profiles, "base", None)
    folder = Path(base) if base is not None else DEFAULT_ROOT / "toolchain"
    failures = [message for level, _check, message in profile_findings(manifest, profiles, lock, name, base) if level == "FAIL"]
    owned = {}
    if profile["skills"] or profile["mcp"]:
        try:
            owned = repo_skill_folders(folder)
        except ToolchainError as exc:
            failures.extend(m for m in exc.problems if m not in failures)
    failures.extend("repo-owned skill %s: %s" % pair for pair in repo_skill_findings(owned, deps))
    if failures:
        raise ToolchainError("profile %s does not verify" % name, ["profile %s: %s" % (name, m) for m in failures])
    entries = select_skills(manifest, lock, profile)[0]
    skills, seen = [], set()
    for entry in entries:
        if entry["name"] not in seen:
            seen.add(entry["name"])
            skills.append(entry)
    shared = select_shared(manifest, lock, entries)[0]
    servers = servers_by_id(manifest)
    mcp, omitted = [], []
    for item in profile["mcp"]:
        server = servers[item["server"]]
        if "package" in server and ((lock.get("packages") or {}).get(package_key(server["package"])) or {}).get("status") != "resolved":
            omitted.append({"server": item["server"], "variant": item["variant"], "reason": "its package is unresolved in the lock"})
            continue
        launch = server_launch(manifest, lock, item["server"], item["variant"])
        package = package_info(server["package"], lock) if "package" in server else None
        contract = copy.deepcopy((lock.get("contracts") or {}).get("%s/%s" % (item["server"], item["variant"])))
        mcp.append({"id": item["server"], "variant": item["variant"], **launch, "package": package, "contract": contract})
    declared = {tool["id"]: tool for tool in manifest.get("tools", [])}
    tools = []
    for tool_id in profile.get("tools", []):
        tool = declared[tool_id]
        if ((lock.get("packages") or {}).get(package_key(tool["package"])) or {}).get("status") != "resolved":
            omitted.append({"tool": tool_id, "reason": "its package is unresolved in the lock"})
            continue
        tools.append({"id": tool_id, "command": tool["command"], **package_info(tool["package"], lock)})
    repo = []
    for repo_name, repo_folder in owned.items():
        measured = deps.digest_tree(repo_folder)
        repo.append({"name": repo_name, "path": "toolchain/skills/" + repo_name, "digest": measured["digest"],
                     "files": measured["files"], "bytes": measured["bytes"]})
    instructions = []
    for rel in profile["instructions"]:
        instructions.append({"path": rel, "digest": digest_text(read_text_lf(folder / rel, rel))})
    return {"name": name, "mode": profile["mode"], "skills": skills, "shared": shared, "repo_skills": repo, "mcp": mcp, "tools": tools, "omitted": omitted,
            "instructions": instructions, "lock": lock_digest(lock)}


# ---------------------------------------------------------------- renderings

def omitted_note(item):
    """The note for a server or a tool that a dev profile leaves out, because its package is unresolved in the lock."""
    if "tool" in item:
        return "note: tool %s is left out: %s" % (item["tool"], item["reason"])
    return "note: server %s is not rendered: %s" % (item["server"], item["reason"])


def _env_value(host, spec):
    if host == "vscode":
        return "${env:%s}" % spec["from_env"]
    if spec.get("default") is not None:
        return "${%s:-%s}" % (spec["from_env"], spec["default"])
    return "${%s}" % spec["from_env"]


def _render_server(host, item):
    if item["transport"] == "http":
        entry = {"type": "http", "url": item["url"]}
        if item["headers"]:
            entry["headers"] = dict(item["headers"])
    else:
        entry = {"type": "local" if host == "copilot-cli" else "stdio", "command": item["command"], "args": list(item["args"])}
        if item["env"]:
            entry["env"] = {name: _env_value(host, spec) for name, spec in item["env"].items()}
    if host == "copilot-cli":
        entry["tools"] = ["*"]
    return entry


def _load_plan(resolved):
    return {
        "schema": SCHEMA,
        "profile": resolved["name"],
        "mode": resolved["mode"],
        "lock": resolved["lock"],
        "skills": [{"name": s["name"], "source": s["source"], "plugin": s["plugin"], "commit": s["commit"],
                    "path": s["path"], "digest": s["digest"], "store_path": "skills/" + s["name"]} for s in resolved["skills"]],
        "shared": [{"folder": s["folder"], "source": s["source"], "plugin": s["plugin"], "commit": s["commit"], "path": s["path"],
                    "digest": s["digest"], "store_path": s["folder"]} for s in resolved["shared"]],
        "repo_skills": [{"name": r["name"], "path": r["path"], "digest": r["digest"], "files": r["files"], "bytes": r["bytes"]}
                        for r in resolved["repo_skills"]],
        "mcp": [_plan_server(m, resolved["mode"]) for m in resolved["mcp"]],
        "tools": [_plan_tool(t, resolved["mode"]) for t in resolved["tools"]],
        "instructions": [dict(i) for i in resolved["instructions"]],
    }


def _plan_tool(t, mode):
    """One pinned command-line tool of a load plan. A job installs the pinned version before it starts; a developer's machine fetches it when needed."""
    entry = {"id": t["id"], "command": t["command"], "ecosystem": t["ecosystem"], "package": t["name"], "version": t["version"]}
    entry.update({key: t[key] for key in ("integrity", "sha256") if key in t})
    entry["provisioning"] = "on-demand" if mode == "dev" else "preinstalled"
    return entry


def _plan_server(m, mode):
    """One server of a load plan. A job (any mode but dev) must not download at launch: the launcher is told to use what is on disk."""
    args = list(m["args"])
    offline = m["package"] is not None and mode != "dev" and m["command"] in OFFLINE_LAUNCHERS
    if offline and args[:1] != ["--offline"]:
        args.insert(0, "--offline")
    entry = {"id": m["id"], "variant": m["variant"], "transport": m["transport"], "command": m["command"], "args": args,
             "env": [{"name": n, "from_env": spec["from_env"], "default": spec.get("default")} for n, spec in m["env"].items()],
             "url": m["url"], "headers": dict(m["headers"]), "package": m["package"]}
    if m["package"] is not None:
        entry["provisioning"] = "preinstalled" if offline else "on-demand"  # preinstalled is claimed only where the launcher was told to stay offline
    entry["contract"] = m["contract"]
    return entry


def render(host, resolved):
    """The configuration of one resolved profile for a host (copilot-cli, vscode, claude-code) or as a neutral load plan."""
    if host == "load-plan":
        if resolved["mode"] != "dev":
            uncaptured = sorted("%s/%s" % (m["id"], m["variant"]) for m in resolved["mcp"]
                                if m["transport"] == "stdio" and (m["contract"] or {}).get("status") != "captured")
            if uncaptured:
                raise ToolchainError("profile %s cannot start a job: the lock has no captured contract for %s "
                                     "(capture them on a machine where the operator accepted the license)" % (resolved["name"], ", ".join(uncaptured)))
        return _load_plan(resolved)
    if host not in HOSTS:
        raise ToolchainError("unknown host '%s' (known: %s)" % (host, ", ".join(RENDER_TARGETS)))
    servers = {item["id"]: _render_server(host, item) for item in resolved["mcp"]}
    return {"servers" if host == "vscode" else "mcpServers": servers}


# ---------------------------------------------------------------- the lock: resolve, merge, compare

PROBE_TIMEOUT = 120
BOUND_VARIABLES = ("npm_config_before", "uv_exclude_newer")  # how npm and uv are told not to take a version that is newer than a date
SKILL_KEYS = ("path", "digest", "files", "bytes", "description_chars", "install_hints", "findings")
TOOL_KEYS = ("schema", "read_only", "destructive", "idempotent")


def skipped(detail):
    return {"status": "skipped", "reason": "skipped", "detail": detail}


def used_variants(manifest, profiles):
    """[(server id, variant)] that some profile uses, in manifest order."""
    used = {(m["server"], m["variant"]) for p in profiles["profiles"].values() for m in p["mcp"]}
    return [(s["id"], v) for s in manifest["mcp_servers"] for v in s["variants"] if (s["id"], v) in used]


def clean_package(result, package):
    """A resolver's answer reduced to what the lock may hold. A pinned package must resolve to its pin."""
    ecosystem = package["ecosystem"]
    if isinstance(result, dict) and result.get("status") == "resolved":
        version = result.get("version")
        pin = package["track"]
        if exact_version(ecosystem, version) and (pin == "latest" or version == pin):
            field = INTEGRITY_FIELD[ecosystem]
            value = result.get(field)
            value = value if isinstance(value, str) and INTEGRITY_FORM[ecosystem].fullmatch(value) else None
            if ecosystem == "npm" and value is None:
                return {"status": "unresolved", "reason": "unresolved", "detail": "no integrity"}
            entry = {"status": "resolved", "version": version}
            if field in result or ecosystem == "npm":
                entry[field] = value
            via = result.get("via")
            entry["via"] = via if isinstance(via, str) and re.fullmatch(r"[a-z0-9-]{1,20}", via) else "unknown"
            return entry
        return {"status": "unresolved", "reason": "unresolved", "detail": "unexpected version"}
    reason = result.get("reason") if isinstance(result, dict) else None
    detail = result.get("detail") if isinstance(result, dict) else ""
    return {"status": "unresolved", "reason": reason if reason in PACKAGE_REASONS else "unresolved", "detail": toolchain_io.safe_detail(detail)}


def plugin_entry(plugin, info):
    skills = {name: {key: skill[key] for key in SKILL_KEYS if key in skill} for name, skill in sorted(info["skills"].items())}
    return {"path": plugin["path"], "version": info.get("version"), "skills": skills,
            "agents": list(info.get("agents", [])), "bundled_mcp": list(info.get("bundled_mcp", []))}


def shared_by_plugin(source):
    """{plugin name: sorted folders} for the shared folders that a source declares."""
    folders = {}
    for item in source.get("shared", []):
        folders.setdefault(item["plugin"], []).append(item["folder"])
    return {plugin: tuple(sorted(names)) for plugin, names in folders.items()}


def check_shared_coverage(source, shared, deps, git_dir, commit):
    """The skills of every plugin of a source reach a shared folder as ../../<folder>/, and only one copy of it is installed.

    So whatever another plugin carries of that folder must be in the canonical one with the same content."""
    paths = {p["name"]: p["path"] for p in source["plugins"]}
    for folder, held in sorted(shared.items()):
        canonical = held["plugin"]
        others = [p for p in source["plugins"] if p["name"] != canonical]
        if not others:
            continue
        reference = deps.read_shared_entries(git_dir, commit, paths[canonical], folder, deps.runner)
        for plugin in others:
            entries = deps.read_shared_entries(git_dir, commit, plugin["path"], folder, deps.runner)
            differing = sorted(rel for rel, digest in entries.items() if reference.get(rel) != digest)
            if differing:
                more = " (and %d more)" % (len(differing) - 3) if len(differing) > 3 else ""
                raise ToolchainError("the shared folder %s of plugin %s is not covered by plugin %s: %d file(s) are absent there or differ, first: %s%s"
                                     % (folder, plugin["name"], canonical, len(differing), ", ".join(_clean_label(r) for r in differing[:3]), more))


def resolve_source(source, deps, store):
    """The lock entry of one skill source: the ref, the commit, every plugin's skills with their digests and the shared folders.

    The cache folder of the commit is fetched anew every time: whatever is already there is not trusted, and `fetch_git` replaces it."""
    ref = deps.resolve_git_ref(source["repo"], source["track"], deps.runner)
    commit = ref.get("commit")
    if not (isinstance(commit, str) and COMMIT_RE.fullmatch(commit)):
        raise toolchain_sources.SourceError("unresolved: no commit")
    git_dir = Path(store) / ".cache" / commit[:12]
    declared = shared_by_plugin(source)
    git_dir.parent.mkdir(parents=True, exist_ok=True)
    deps.fetch_git(source["repo"], commit, git_dir, deps.runner)
    plugins, shared = {}, {}
    for p in source["plugins"]:
        folders = declared.get(p["name"], ())
        if folders:
            info = deps.read_plugin(git_dir, commit, p["path"], deps.runner, shared=folders)
            held = info.get("shared") if isinstance(info, dict) else None
            for folder in folders:
                entry = held.get(folder) if isinstance(held, dict) else None
                if not isinstance(entry, dict):
                    raise toolchain_sources.SourceError("missing: the shared folder %s is not reported" % folder)
                shared[folder] = {"plugin": p["name"], "digest": entry.get("digest"), "files": entry.get("files"), "bytes": entry.get("bytes")}
        else:
            info = deps.read_plugin(git_dir, commit, p["path"], deps.runner)
        plugins[p["name"]] = plugin_entry(p, info)
    check_shared_coverage(source, shared, deps, git_dir, commit)
    shared = dict(sorted(shared.items()))
    tag = ref.get("tag") if source["track"]["kind"] == "tag" else None
    entry = {"repo": source["repo"], "tag": tag, "commit": commit, "plugins": dict(sorted(plugins.items()))}
    if shared:
        entry["shared"] = shared
    return entry


def probe_environment(spec, base, eula, license_envs=()):
    """The variables that a probe declares to the server it starts: the ones the variant names, each from the operator's environment
    or else its default, and the license variable of this server when the operator set it. A variable that the operator set to an empty
    text counts as not set (the license variable too).

    Nothing else of the operator's environment is in it. The probe adds the few variables that every process needs and the registry
    settings (toolchain_mcp.capture_env), and a token or a password of the operator's shell never reaches a server.
    The kit never sets a license variable. It is handed on only to the server that declares it, and only when the operator set it."""
    own = eula["env"] if eula else None
    env = {own: base[own]} if own is not None and base.get(own) else {}
    for name, item in spec.items():
        if name == own or name in license_envs:
            continue
        value = base.get(item["from_env"])
        if value is None or value == "":  # an empty value counts as not set, the way ${NAME:-default} reads it in a host file
            value = item.get("default")
        if value is not None:
            env[name] = value
    return env


def license_variables(manifest):
    return {s["eula"]["env"] for s in manifest["mcp_servers"] if s.get("eula")}


def _clean_label(value):
    return CONTROL_RE.sub(" ", str(value))[:120]


def _server_label(value, pattern):
    """What a server calls itself, or "unknown" when that is not a plain label (a path, an address, a long text, a token or a host name)."""
    return value if isinstance(value, str) and pattern.fullmatch(value) and not toolchain_mcp.suspect(value) else "unknown"


def capture_contract(manifest, packages, server, variant, deps):
    """One contract entry for the lock. A server whose license the operator has not accepted is never launched."""
    if server["transport"] == "http":
        result = deps.probe_http(server["url"], headers=dict(server.get("headers", {})), runner=deps.runner)
        status = result.get("status") if isinstance(result, dict) else None
        if status in ("open", "needs-sign-in"):
            return {"status": status}
        return {"status": "unavailable", "reason": "network", "detail": ""}
    eula = server.get("eula")
    if eula and not license_accepted(deps.env, eula["env"]):
        return skipped("license not accepted")
    try:
        launch = server_launch(manifest, {"packages": packages}, server["id"], variant)
    except ToolchainError:
        return {"status": "unavailable", "reason": "unresolved", "detail": ""}
    argv = [launch["command"]] + launch["args"]
    try:
        probe = deps.probe_stdio(argv, env=probe_environment(launch["env"], deps.env, eula, license_variables(manifest)),
                                 timeout=PROBE_TIMEOUT)
    except toolchain_mcp.McpProbeError as exc:
        return unavailable_from(exc)
    contract = {
        "status": "captured", "era": probe.get("era"), "protocol": _clean_label(probe.get("protocol", "")),
        "server": {"name": _server_label((probe.get("server") or {}).get("name"), SERVER_NAME_RE),
                   "version": _server_label((probe.get("server") or {}).get("version"), SERVER_VERSION_RE)},
        "package_version": packages[package_key(server["package"])]["version"],
        "launch": launch_digest(launch),
        "captured": deps.today(),
        "tools": {name: {key: tool.get(key) for key in TOOL_KEYS} for name, tool in sorted((probe.get("tools") or {}).items())},
    }
    problems = []
    _check_contract(contract, "contract", problems)
    if problems or not contract["tools"]:
        return {"status": "unavailable", "reason": "no-tools" if not problems else "protocol-error", "detail": ""}
    return contract


def bounded_environment(env, captured):
    """`env` with the resolution of dependencies bounded by the day of the capture: npm and uv refuse a version published after the bound.

    The bound is midnight, UTC, at the start of the day after `captured`, so everything that existed on the day of the capture is allowed.
    An entry of the operator's environment under either name, in any case, gives way to it."""
    bound = (datetime.date.fromisoformat(captured) + datetime.timedelta(days=1)).isoformat() + "T00:00:00Z"
    bounded = {name: value for name, value in env.items() if name.lower() not in BOUND_VARIABLES}
    bounded.update({"npm_config_before": bound, "UV_EXCLUDE_NEWER": bound})
    return bounded


def unavailable_from(error):
    """An unavailable contract from a probe error: the reason code comes first in the message, the rest is sanitised."""
    message = str(error)
    match = re.match(r"[a-z-]+", message)
    reason = match.group(0) if match and match.group(0) in REASONS else "protocol-error"
    rest = message[len(match.group(0)):].lstrip(" :-") if match else ""
    return {"status": "unavailable", "reason": reason, "detail": toolchain_io.safe_detail(rest)}


def merge_contract(old, new, version, launch=None):
    """Keep what was captured unless the package or the way it is launched changed. `new` is None when no capture was attempted.

    `launch` is the digest of how the variant launches now; a captured contract that was bound to another launch describes another server.
    A contract that is captured again with nothing else changed keeps the date of its first capture, so the lock stays as it was."""
    status = old.get("status") if isinstance(old, dict) else None
    if new is not None and new["status"] == "captured":
        if status == "captured" and without_date(old) == without_date(new):
            return old
        return new
    if status == "captured" and version is not None and old.get("package_version") == version and launch is not None and old.get("launch") == launch:
        return old
    if new is not None:
        return old if status in ("needs-sign-in", "open") and new["status"] == "unavailable" else new
    if status == "captured":
        return skipped("package version changed" if old.get("package_version") != version else "launch changed")
    return old if status is not None else skipped("contracts not captured")


def without_date(contract):
    return {key: value for key, value in contract.items() if key != "captured"}


def launch_changed(old, merged, version, launch):
    """Whether `merge_contract` let go of a captured contract of the same package version because the variant launches differently now."""
    return (isinstance(old, dict) and old.get("status") == "captured" and merged.get("status") != "captured" and version is not None
            and old.get("package_version") == version and launch is not None and old.get("launch") != launch)


def strip_generated(lock):
    return {key: value for key, value in lock.items() if key != "generated"}


def lock_package_problems(manifest, lock):
    """(missing, differs): the declared packages that the lock lacks, and the pinned ones that it does not lock at the version that the manifest pins.

    A package that follows `latest` is whatever the lock holds, so it is never a difference."""
    missing, differs = [], []
    for key, package in declared_packages(manifest).items():
        entry = (lock.get("packages") or {}).get(key)
        if entry is None:
            missing.append("package %s" % key)
        elif package["track"] != "latest" and entry.get("version") != package["track"]:
            held = "no resolved version" if entry.get("version") is None else "version %s" % _shown(entry["version"])
            differs.append("the lock has %s for package %s, but the manifest pins %s" % (held, key, package["track"]))
    return missing, differs


def refresh_digest(manifest, old, deps, profiles=None):
    """`lock --no-network`: (lock, notes). The old lock with the digest of the edited manifest and nothing else changed, except that a
    captured contract is dropped when its variant launches differently now.

    That is only honest when the lock still agrees with the manifest about where the skills come from and which versions the packages
    are pinned to, and a captured contract stays only while its variant launches the way it did when the contract was captured.
    Given the profiles, a contract of a variant that no profile uses is left out, as `lock` leaves it out, and not replaced by a placeholder."""
    missing, differs = lock_source_problems(manifest, old)
    if missing or differs:
        raise ToolchainError("a changed source or plugin path needs a lock with the network",
                             ["the lock has no entry for %s" % m for m in missing] + differs)
    missing, differs = lock_package_problems(manifest, old)
    if missing or differs:
        raise ToolchainError("a changed package pin needs a lock with the network",
                             ["the lock has no entry for %s" % m for m in missing] + differs)
    lock = copy.deepcopy(dict(old))
    lock["inputs_digest"] = inputs_digest(manifest)
    used = None if profiles is None else {"%s/%s" % pair for pair in used_variants(manifest, profiles)}
    notes = []
    for key, contract in list(lock["contracts"].items()):
        sid, _, variant = key.partition("/")
        launch = current_launch(manifest, lock["packages"], sid, variant)
        if contract.get("status") == "captured" and launch is not None and contract.get("launch") != launch:
            if used is None or key in used:
                lock["contracts"][key] = skipped("launch changed")
            else:
                del lock["contracts"][key]
            notes.append("dropped the captured contract of %s: its launch changed" % key)
    lock["generated"] = deps.today() if strip_generated(lock) != strip_generated(old) else old["generated"]
    return Lock(lock), notes


def build_lock(manifest, profiles, old, deps, store, contracts=False, only=None):
    """Resolve the manifest into a new lock in memory: (lock, notes). Raises ToolchainError with every failure."""
    known_packages = declared_packages(manifest)
    only_sources, only_packages = set(), set()
    if only:
        if old is None:
            raise UsageError("--only needs an existing lock to carry the rest over")
        known_sources = {s["id"] for s in manifest["skill_sources"]}
        for name in only:
            by_name = [k for k, p in known_packages.items() if p["name"] == name]
            if name in known_sources:
                only_sources.add(name)
            elif name in known_packages:
                only_packages.add(name)
            elif len(by_name) == 1:
                only_packages.add(by_name[0])
            else:
                raise UsageError("'%s' is neither a skill source nor a package of the manifest" % name)
    failures, notes = [], []
    old_sources = (old or {}).get("skill_sources", {})
    old_packages = (old or {}).get("packages", {})
    old_contracts = (old or {}).get("contracts", {})

    sources = {}
    for source in manifest["skill_sources"]:
        sid = source["id"]
        if only and sid not in only_sources:
            if sid in old_sources:
                sources[sid] = copy.deepcopy(old_sources[sid])
            else:
                failures.append("skill source %s: the existing lock has no entry, so --only cannot carry it over" % sid)
            continue
        try:
            sources[sid] = resolve_source(source, deps, store)
        except toolchain_sources.SourceError as exc:
            failures.append("skill source %s: %s" % (sid, toolchain_io.safe_detail(exc) or "could not be resolved"))
        except ToolchainError as exc:
            failures.append("skill source %s: %s" % (sid, exc))

    packages = {}
    for key, package in known_packages.items():
        if only and key not in only_packages:
            if key in old_packages:
                packages[key] = copy.deepcopy(old_packages[key])
            else:
                failures.append("package %s: the existing lock has no entry, so --only cannot carry it over" % key)
            continue
        entry = clean_package(deps.resolve_package(package["ecosystem"], package["name"], package["track"], deps.runner), package)
        previous = old_packages.get(key)
        if (entry["status"] != "resolved" and previous and previous.get("status") == "resolved"
                and package["track"] in ("latest", previous.get("version"))):
            notes.append("kept the locked version of %s: it could not be resolved now" % key)
            entry = copy.deepcopy(previous)
        packages[key] = entry
    if failures:
        raise ToolchainError("the lock cannot be resolved", failures)

    servers = servers_by_id(manifest)
    wanted = used_variants(manifest, profiles)
    merged = {}
    for sid, variant in wanted:
        key = "%s/%s" % (sid, variant)
        server = servers[sid]
        pkg_key = package_key(server["package"]) if "package" in server else None
        version = packages[pkg_key].get("version") if pkg_key else None
        in_scope = contracts and (not only or pkg_key in only_packages)
        new = capture_contract(manifest, packages, server, variant, deps) if in_scope else None
        launch = current_launch(manifest, packages, sid, variant)
        old_contract = old_contracts.get(key)
        merged[key] = merge_contract(old_contract, new, version, launch)
        if new is not None and new["status"] != "captured" and merged[key] is not new:
            notes.append("kept the captured contract of %s: the new capture is %s" % (key, new["status"]))
        if launch_changed(old_contract, merged[key], version, launch):
            notes.append("dropped the captured contract of %s: its launch changed" % key)
    for key, contract in old_contracts.items():
        sid, _, variant = key.partition("/")
        server = servers.get(sid)
        if key in merged or server is None or variant not in server["variants"] or contract.get("status") != "captured":
            continue
        pkg_key = package_key(server["package"]) if "package" in server else None
        if pkg_key and packages.get(pkg_key, {}).get("version") == contract.get("package_version"):
            launch = current_launch(manifest, packages, sid, variant)
            if launch is not None and contract.get("launch") != launch:
                notes.append("dropped the captured contract of %s: its launch changed" % key)
                continue
            merged[key] = copy.deepcopy(contract)

    lock = {"schema": SCHEMA, "generated": deps.today(), "inputs_digest": inputs_digest(manifest),
            "skill_sources": dict(sorted(sources.items())), "packages": dict(sorted(packages.items())),
            "contracts": dict(sorted(merged.items()))}
    problems = validate_lock(lock)
    if problems:
        raise ToolchainError("the resolved lock is invalid", problems)
    if old is not None and strip_generated(lock) == strip_generated(old):
        lock["generated"] = old["generated"]
    return Lock(lock), notes


def _describe_package(entry):
    if entry is None:
        return None
    if entry.get("status") != "resolved":
        return "unresolved (%s)" % entry.get("reason")
    return entry["version"]


def plugin_diff(old, new):
    before = (old or {}).get("skills", {})
    after = (new or {}).get("skills", {})
    added, removed = sorted(set(after) - set(before)), sorted(set(before) - set(after))
    changed = sorted(n for n in set(before) & set(after) if before[n]["digest"] != after[n]["digest"])
    renamed = []
    for gone in list(removed):
        for came in list(added):
            if before[gone]["digest"] == after[came]["digest"]:
                renamed.append({"from": gone, "to": came})
                removed.remove(gone)
                added.remove(came)
                break
    description = [{"skill": n, "chars": [before[n]["description_chars"], after[n]["description_chars"]]}
                   for n in sorted(set(before) & set(after)) if before[n]["description_chars"] != after[n]["description_chars"]]
    versions = [(old or {}).get("version"), (new or {}).get("version")]
    entry = {"version": versions if versions[0] != versions[1] else None, "added": added, "removed": removed, "changed": changed,
             "renamed": renamed, "description": description, "plugin_added": old is None, "plugin_removed": new is None}
    return entry if any(entry[k] for k in entry) else None


def diff_locks(old, new, deps):
    """What differs between two locks, for people: sources, plugins and skills, packages and contracts."""
    empty = {"skill_sources": {}, "packages": {}, "contracts": {}}
    old = old or empty
    diff = {"sources": [], "plugins": [], "packages": [], "contracts": []}
    for sid in sorted(set(old["skill_sources"]) | set(new["skill_sources"])):
        a, b = old["skill_sources"].get(sid), new["skill_sources"].get(sid)
        if a is None or b is None or a["commit"] != b["commit"] or a.get("tag") != b.get("tag"):
            diff["sources"].append({"id": sid, "tag": [a and a.get("tag"), b and b.get("tag")],
                                    "commit": [a and a["commit"], b and b["commit"]]})
        plugins_a, plugins_b = (a or {}).get("plugins", {}), (b or {}).get("plugins", {})
        for name in sorted(set(plugins_a) | set(plugins_b)):
            entry = plugin_diff(plugins_a.get(name), plugins_b.get(name))
            if entry:
                diff["plugins"].append({"source": sid, "plugin": name, **entry})
    for key in sorted(set(old["packages"]) | set(new["packages"])):
        a, b = old["packages"].get(key), new["packages"].get(key)
        if a != b:
            note = "same version, different hash" if a and b and a.get("version") == b.get("version") and a.get("status") == "resolved" else None
            diff["packages"].append({"key": key, "old": _describe_package(a), "new": _describe_package(b), "note": note})
    for key in sorted(set(old["contracts"]) | set(new["contracts"])):
        a, b = old["contracts"].get(key), new["contracts"].get(key)
        if a == b:
            continue
        item = {"key": key, "old": a and a["status"], "new": b and b["status"], "added": [], "removed": [], "changed": []}
        if a and b and a["status"] == "captured" and b["status"] == "captured":
            delta = deps.contract_diff(a["tools"], b["tools"])
            for kind in ("added", "removed", "changed"):
                item[kind] = sorted(delta.get(kind, []))
        diff["contracts"].append(item)
    return diff


def what_breaks(manifest, profiles, old, new):
    """[{"profile","problems","newly_broken"}] for every profile that does not verify against the new lock."""
    out = []
    for name in profiles["profiles"]:
        problems = [m for level, _check, m in profile_findings(manifest, profiles, new, name) if level == "FAIL"]
        if not problems:
            continue
        before = [m for level, _check, m in profile_findings(manifest, profiles, old, name) if level == "FAIL"] if old is not None else None
        out.append({"profile": name, "problems": problems, "newly_broken": before is not None and not before})
    return out


def _short(value):
    return "none" if value is None else (str(value)[:12] if COMMIT_RE.fullmatch(str(value)) else str(value))


def format_report(diff, breaks, markdown=False, notes=(), show_notes=True, manifest_edited=False):
    """The gap analysis as lines of text, or as Markdown for a CI step summary. `notes` are what the resolution said about itself: a note
    that starts with 'kept' means that part of the check did not run (a package that could not be resolved now, a contract that could not
    be captured), so 'no upstream change' is then said for what could be checked, and the notes follow the report when `show_notes`.
    `manifest_edited` says that the lock inputs changed while nothing changed upstream: exit 3 of the check, and the reader has to know why."""
    lines = []
    heading = (lambda t: "## " + t) if markdown else (lambda t: t)
    bullet = "- " if markdown else "  "
    sub = "  - " if markdown else "    "
    if manifest_edited:
        lines.append("The lock inputs changed (the manifest was edited); nothing changed upstream.")
    if diff["sources"]:
        lines.append(heading("Skill sources"))
        for s in diff["sources"]:
            lines.append("%s%s: tag %s -> %s, commit %s -> %s" % (bullet, s["id"], _short(s["tag"][0]), _short(s["tag"][1]),
                                                                  _short(s["commit"][0]), _short(s["commit"][1])))
    if diff["plugins"]:
        lines.append(heading("Plugins and skills"))
        for p in diff["plugins"]:
            lines.append("%s%s/%s%s" % (bullet, p["source"], p["plugin"],
                                        ": version %s -> %s" % (_short(p["version"][0]), _short(p["version"][1])) if p["version"] else ""))
            if p["plugin_added"]:
                lines.append(sub + "plugin is new")
            if p["plugin_removed"]:
                lines.append(sub + "plugin is gone")
            for label, key in (("skills added", "added"), ("skills removed", "removed"), ("skills changed", "changed")):
                if p[key]:
                    lines.append("%s%s: %s" % (sub, label, ", ".join(p[key])))
            if p["renamed"]:
                lines.append("%sskills renamed: %s" % (sub, ", ".join("%s -> %s" % (r["from"], r["to"]) for r in p["renamed"])))
            if p["description"]:
                lines.append("%sdescription length changed: %s" % (sub, ", ".join("%s %d -> %d" % (d["skill"], *d["chars"]) for d in p["description"])))
    if diff["packages"]:
        lines.append(heading("Packages"))
        for p in diff["packages"]:
            lines.append("%s%s: %s -> %s%s" % (bullet, p["key"], _short(p["old"]), _short(p["new"]), " (%s)" % p["note"] if p["note"] else ""))
    if diff["contracts"]:
        lines.append(heading("Contracts"))
        for c in diff["contracts"]:
            parts = ["%s %s" % (k, ", ".join(c[k])) for k in ("added", "removed", "changed") if c[k]]
            lines.append("%s%s: %s -> %s%s" % (bullet, c["key"], _short(c["old"]), _short(c["new"]), "; tools " + "; ".join(parts) if parts else ""))
    if not any(diff.values()):
        partial = any(note.startswith("kept ") for note in notes)
        lines.append("No upstream change was found, but part of the check did not run (see the notes)." if partial else "No upstream change.")
    lines.append(heading("What breaks"))
    if not breaks:
        lines.append(bullet + "nothing: every profile still verifies")
    for b in breaks:
        lines.append("%sprofile %s%s" % (bullet, b["profile"], " (newly broken)" if b["newly_broken"] else ""))
        lines.extend(sub + p for p in b["problems"])
    if notes and show_notes:
        lines.append(heading("Notes"))
        lines.extend(bullet + note for note in notes)
    return lines


# ---------------------------------------------------------------- the project on disk

class Project:
    """The folders and files of one project: the manifest, the profiles and the lock."""

    def __init__(self, root):
        self.root = Path(root)
        self.dir = self.root / "toolchain"
        self.lock_path = self.dir / "toolchain.lock.json"
        self.manifest = self.profiles = self.lock = None

    def load(self, lock="require", fresh=False):
        self.manifest = load_manifest(self.dir / "toolchain.json")
        self.profiles = load_profiles(self.dir / "profiles.json")
        missing = check_default_profile(self.manifest, self.profiles)
        if missing:
            raise ToolchainError("toolchain.json: " + missing)
        if lock != "skip":
            if self.lock_path.is_file():
                self.lock = load_lock(self.lock_path)
            elif lock == "require":
                raise ToolchainError("lock file missing: " + LOCK_HINT)
        if fresh and self.lock is not None and self.lock["inputs_digest"] != inputs_digest(self.manifest):
            raise ToolchainError("the lock is stale: the manifest changed since it was resolved (%s)" % LOCK_HINT)
        return self

    def store(self, override=None):
        return Path(override) if override else self.root / self.manifest.get("store", ".factory/pack")

    def profile_name(self, name):
        name = name or self.manifest["default_profile"]
        if name not in self.profiles["profiles"]:
            raise UsageError("profile '%s' does not exist (known: %s)" % (name, ", ".join(self.profiles["profiles"])))
        return name

    def shown(self, path, deps):
        return display_path(path, self.root, deps.home)


def check_default_profile(manifest, profiles):
    if manifest["default_profile"] not in profiles["profiles"]:
        return "default_profile '%s' is not a profile of profiles.json" % manifest["default_profile"]
    return None


def found_hosts(manifest, deps, among=None):
    return [h for h, spec in manifest["hosts"].items() if (among is None or h in among) and deps.runner.which(spec["binary"])]


def select_hosts(manifest, deps, requested, defaults=None):
    """The hosts to work on: the ones asked for, or else those of `defaults` (all when None) whose binary is on PATH."""
    if requested:
        for host in requested:
            if host not in manifest["hosts"]:
                raise UsageError("host '%s' is not in the manifest (known: %s)" % (host, ", ".join(manifest["hosts"])))
        return list(dict.fromkeys(requested))
    return found_hosts(manifest, deps, defaults)


def repo_skill_folders(base):
    """The skills this repository owns under <toolchain folder>/skills: {name: folder}. A link is refused, the folder of a skill and anything
    inside it: they are read from real folders only, and a link inside one would be measured as a text that names its target."""
    root = Path(base) / "skills"
    if is_link(root):
        raise ToolchainError("toolchain/skills is a link; the toolchain reads the skills of this repository from real folders only")
    if not root.is_dir():
        return {}
    found = {}
    for entry in sorted(root.iterdir()):
        if entry.is_dir() and (entry / "SKILL.md").is_file():
            linked = link_inside(entry)
            if linked is not None:
                raise ToolchainError("toolchain/skills/%s is a link; the toolchain reads the skills of this repository from real folders only"
                                     % _shown(linked.relative_to(root).as_posix()))
            found[entry.name] = entry
    for name in found:
        if not SKILL_RE.fullmatch(name):
            raise ToolchainError("toolchain/skills/%s: a skill folder is named with lower-case letters, digits and hyphens" % _shown(name))
    return found


def read_marker(path):
    data = read_json(path, MARKER)
    problems = []
    if _keys(data, MARKER, problems, ("profile", "lock", "skills"), ("shared",)):
        _text(data.get("profile"), "profile", problems, ID_RE)
        _text(data.get("lock"), "lock", problems, SHA256_RE)
        if isinstance(data.get("skills"), dict):
            for name, digest in data["skills"].items():
                if not SKILL_RE.fullmatch(name) or not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                    problems.append("skills.%s: must map a skill name to a sha256 digest" % _shown(name))
        else:
            problems.append("skills: must be an object")
        if "shared" in data:
            if isinstance(data["shared"], dict):
                for folder, digest in data["shared"].items():
                    if (not SHARED_FOLDER_RE.fullmatch(folder) or folder in RESERVED_FOLDERS
                            or not isinstance(digest, str) or not SHA256_RE.fullmatch(digest)):
                        problems.append("shared.%s: must map a shared folder name to a sha256 digest" % _shown(folder))
            else:
                problems.append("shared: must be an object")
    if problems:
        raise ToolchainError("%s is invalid" % MARKER, ["%s: %s" % (MARKER, p) for p in problems])
    return data


def _pack_folder_problem(deps, folder, digest, what, linked):
    """The FAIL for a folder of the local pack that is behind a link, cannot be measured or differs from the lock; None when it holds the locked content."""
    if linked:
        return ("FAIL", "the local pack holds %s behind a link; the toolchain reads the pack from real folders only" % what)
    measured = _measured(deps, folder)
    if measured is None:
        return ("FAIL", "the local pack holds %s that cannot be measured (it is not a readable folder)" % what)
    if measured != digest:
        return ("FAIL", "the local pack holds %s with content that differs from the lock" % what)
    return None


def store_problems(store, skills, lock, deps, shared=()):
    """[(level, message)] about the local pack: absent or stale (WARN), or a skill or shared folder that does not match the lock, is behind a link
    or cannot be measured (FAIL). A link inside a folder is measured as part of its content, so it makes the content differ."""
    manifest_path = Path(store) / "MANIFEST.json"
    if not manifest_path.is_file():
        return [("WARN", "the local pack has no MANIFEST.json")]
    try:
        pack = read_json(manifest_path, "MANIFEST.json")
    except ToolchainError as exc:
        return [("WARN", str(exc))]
    out = []
    listed = pack.get("skills") if isinstance(pack, dict) and isinstance(pack.get("skills"), dict) else {}
    listed_shared = pack.get("shared") if isinstance(pack, dict) and isinstance(pack.get("shared"), dict) else {}
    if not isinstance(pack, dict) or pack.get("lock_inputs_digest") != lock["inputs_digest"]:
        out.append(("WARN", "the local pack was built from another lock"))
    skills_dir = Path(store) / "skills"
    for skill in skills:
        folder = skills_dir / skill["name"]
        entry = listed.get(skill["name"])
        if not isinstance(entry, dict) or entry.get("digest") != skill["digest"]:
            out.append(("WARN", "the local pack does not list skill %s at the locked digest" % skill["name"]))
        elif not folder.is_dir():
            out.append(("WARN", "the local pack lacks the folder of skill %s" % skill["name"]))
        else:
            problem = _pack_folder_problem(deps, folder, skill["digest"], "skill " + skill["name"], is_link(skills_dir) or is_link(folder))
            if problem:
                out.append(problem)
    for item in shared:
        folder = Path(store) / item["folder"]
        entry = listed_shared.get(item["folder"])
        if not isinstance(entry, dict) or entry.get("digest") != item["digest"]:
            out.append(("WARN", "the local pack does not list shared folder %s at the locked digest" % item["folder"]))
        elif not folder.is_dir():
            out.append(("WARN", "the local pack lacks the shared folder %s" % item["folder"]))
        else:
            problem = _pack_folder_problem(deps, folder, item["digest"], "the shared folder " + item["folder"], is_link(folder))
            if problem:
                out.append(problem)
    return out


# ---------------------------------------------------------------- verify

class Findings:
    def __init__(self):
        self.items = []

    def add(self, level, check, message):
        self.items.append({"level": level, "check": check, "message": message})

    def count(self, level):
        return sum(1 for i in self.items if i["level"] == level)


def lock_source_problems(manifest, lock):
    """(missing, differs): what the lock lacks of the manifest's skill sources and plugins, and where it says something else than the manifest."""
    missing, differs = [], []
    for source in manifest["skill_sources"]:
        sid = source["id"]
        locked = (lock.get("skill_sources") or {}).get(sid)
        if locked is None:
            missing.append("skill source %s" % sid)
            continue
        if locked.get("repo") != source["repo"]:
            differs.append("the lock took skill source %s from another repository than the manifest names" % sid)
        track, tag = source["track"], locked.get("tag")
        if track["kind"] == "tag":
            if tag is None:
                differs.append("the lock has no tag for skill source %s, but the manifest follows the tags that match %s" % (sid, track["pattern"]))
            elif not fnmatch.fnmatchcase(tag, track["pattern"]):
                differs.append("the lock has the tag %s for skill source %s, which does not match the track pattern %s" % (tag, sid, track["pattern"]))
        elif tag is not None:
            follows = "follows the branch %s" % track["name"] if track["kind"] == "branch" else "pins a commit"
            differs.append("the lock has the tag %s for skill source %s, but the manifest %s, so there is no tag" % (tag, sid, follows))
        if track["kind"] == "commit" and locked.get("commit") != track["sha"]:
            differs.append("the lock has the commit %s for skill source %s, but the manifest pins %s"
                           % (str(locked.get("commit"))[:12], sid, track["sha"][:12]))
        for plugin in source["plugins"]:
            locked_plugin = (locked.get("plugins") or {}).get(plugin["name"])
            if locked_plugin is None:
                missing.append("plugin %s/%s" % (sid, plugin["name"]))
            elif locked_plugin.get("path") != plugin["path"]:
                differs.append("the lock has the plugin %s/%s at another path than the manifest names" % (sid, plugin["name"]))
        declared = {item["folder"]: item["plugin"] for item in source.get("shared", [])}
        held = locked.get("shared") or {}
        for folder, plugin in sorted(declared.items()):
            entry = held.get(folder)
            if entry is None:
                missing.append("shared folder %s of skill source %s" % (folder, sid))
            elif entry.get("plugin") != plugin:
                differs.append("the lock takes the shared folder %s of skill source %s from the plugin %s, but the manifest names %s"
                               % (folder, sid, entry.get("plugin"), plugin))
        for folder in sorted(set(held) - set(declared)):
            differs.append("the lock holds the shared folder %s for skill source %s, which the manifest does not declare" % (folder, sid))
    return missing, differs


def _check_lock_coverage(manifest, lock, f):
    stale = lock["inputs_digest"] != inputs_digest(manifest)
    if stale:
        f.add("FAIL", "V3", "the lock is stale: the manifest changed since it was resolved (%s)" % LOCK_HINT)
    missing, differs = lock_source_problems(manifest, lock)
    missing.extend("package %s" % key for key in declared_packages(manifest) if key not in lock["packages"])
    for item in missing:
        f.add("FAIL", "V3", "the lock has no entry for %s (%s)" % (item, LOCK_HINT))
    for message in differs:
        f.add("FAIL", "V3", "%s (%s)" % (message, LOCK_HINT))
    if not stale and not missing and not differs:
        f.add("PASS", "V3", "the lock is fresh and covers every source, plugin and package")
    for key, contract in lock["contracts"].items():
        if contract["status"] == "captured" and not contract["tools"]:
            f.add("FAIL", "V11", "contract %s is captured but lists no tool" % key)


def _check_quarantine_list(manifest, lock, f):
    for item in manifest.get("quarantine", []):
        plugins = (lock["skill_sources"].get(item["source"]) or {}).get("plugins", {})
        if not any(item["skill"] in p["skills"] for p in plugins.values()):
            f.add("WARN", "V7", "quarantined skill %s/%s is not in the lock any more: the quarantine list is stale" % (item["source"], item["skill"]))


def _check_project_files(project, deps, manifest, profiles, lock, f):
    name = manifest["default_profile"]
    try:
        resolved = resolve_profile(manifest, profiles, lock, name, deps=deps)
    except ToolchainError as exc:
        f.add("FAIL", "V5", "cannot render the default profile %s: %s" % (name, "; ".join(exc.problems)))
        return
    for host in PROJECT_HOSTS:
        if host not in manifest["hosts"]:
            continue
        rel = manifest["hosts"][host]["mcp_project"]
        path = project.root / rel
        if not path.is_file():
            f.add("FAIL", "V5", "%s is missing (%s)" % (rel, RENDER_HINT))
            continue
        try:
            same = read_text_lf(path, rel) == dump_json(render(host, resolved))
        except ToolchainError:
            same = False  # a file that cannot be read as text is not the rendering
        if same:
            f.add("PASS", "V5", "%s equals the rendering of profile %s" % (rel, name))
        else:
            f.add("FAIL", "V5", "%s differs from the rendering of profile %s (%s)" % (rel, name, RENDER_HINT))


def _entries_missing(path, host, rendering, label, level, f, needs_one=False, hint=None, replace_hint=None):
    """Compare the servers of a host file with a rendering. With needs_one the file is compared only when it already holds a server
    of the rendering: a user file that holds none was not written by this kit, so what it lacks is not a defect.
    The `hint`, the command that puts the servers in place, ends each line that it is given for; a line about an entry that differs
    ends with `replace_hint` when there is one, because install keeps an entry of the user's own unless it is forced."""
    container = "servers" if host == "vscode" else "mcpServers"
    try:
        current = read_json(path, label)
    except ToolchainError as exc:
        f.add(level, "V9", str(exc))
        return
    servers = current.get(container) if isinstance(current, dict) else None
    servers = servers if isinstance(servers, dict) else {}
    if needs_one and not any(sid in servers for sid in rendering[container]):
        return
    tail = " (%s)" % hint if hint else ""
    replace_tail = " (%s)" % (replace_hint or hint) if (replace_hint or hint) else ""
    for sid, entry in rendering[container].items():
        if sid not in servers:
            f.add(level, "V9", "%s lacks the server %s%s" % (label, sid, tail))
        elif servers[sid] != entry:
            f.add(level, "V9", "%s holds a different entry for the server %s%s" % (label, sid, replace_tail))


def has_skills(resolved):
    """Whether a profile installs anything into a skills folder: upstream skills, the skills of this repository, or a shared folder."""
    return bool(resolved["skills"] or resolved["repo_skills"] or resolved["shared"])


def hosts_label(path, owners):
    """A folder for a message: just its path for one host, with the host names when several hosts share it."""
    return path if len(owners) < 2 else "%s (%s)" % (path, ", ".join(owners))


def skills_dir_problems(project, deps, resolved, directory, label, marker, hint):
    """What the marker and the disk say about one skills folder compared with what the profile needs:
    (skill problems, shared-folder problems) as plain sentences. A skill the profile needs must be in the marker and on disk with
    the locked digest; a managed entry that the profile does not need is left over. `hint` is the install command that puts the
    profile in place for the hosts of this folder."""
    name = resolved["name"]
    skills, shared = [], []
    if marker["profile"] != name:
        skills.append("%s was installed for profile %s, not profile %s (%s)" % (label, marker["profile"], name, hint))
    needed = {s["name"]: ("locked", s["digest"]) for s in resolved["skills"]}
    needed.update({r["name"]: ("repo", r["digest"]) for r in resolved["repo_skills"]})
    for skill, (kind, digest) in needed.items():
        recorded = marker["skills"].get(skill)
        folder = directory / skill
        if recorded is None:
            skills.append("skill %s of profile %s is not installed in %s" % (skill, name, label))
        elif not folder.is_dir():
            skills.append("managed skill %s is missing from %s" % (skill, label))
        else:
            measured = _measured(deps, folder)
            if measured is None:
                skills.append("managed skill %s in %s cannot be measured (it is not a readable folder)" % (skill, label))
            elif measured != recorded:
                skills.append("managed skill %s in %s differs from its recorded digest" % (skill, label))
            if recorded != digest:
                skills.append("repo-owned skill %s changed since it was installed in %s" % (skill, label) if kind == "repo"
                              else "managed skill %s in %s differs from the lock" % (skill, label))
    skills.extend("managed skill %s in %s is left over from profile %s" % (skill, label, marker["profile"])
                  for skill in marker["skills"] if skill not in needed)
    recorded_shared = marker.get("shared", {})
    for item in resolved["shared"]:
        folder = directory.parent / item["folder"]
        where = project.shown(folder, deps)
        if item["folder"] not in recorded_shared:
            shared.append((where, "of profile %s is not installed (the skills in %s link to it)" % (name, label)))
        elif not folder.is_dir():
            shared.append((where, "is missing (the skills in %s link to it)" % label))
        else:
            measured = _measured(deps, folder)
            if measured is None:
                shared.append((where, "cannot be measured (it is not a readable folder)"))
            elif measured != item["digest"]:
                shared.append((where, "differs from the lock"))
    wanted_shared = {item["folder"] for item in resolved["shared"]}
    shared.extend((project.shown(directory.parent / folder, deps), "is left over from profile %s" % marker["profile"])
                  for folder in recorded_shared if folder not in wanted_shared)
    return skills, shared


def _check_skills_dir(project, deps, lock, resolved, directory, label, required, hint, f):
    marker_path = directory / MARKER
    if not marker_path.is_file():
        if required:
            f.add("FAIL", "V9", "%s has no managed skills marker (%s)" % (label, hint))
        return
    try:
        marker = read_marker(marker_path)
    except ToolchainError as exc:
        f.add("FAIL", "V9", "%s: %s" % (label, "; ".join(exc.problems)))
        return
    if marker["lock"] != lock_digest(lock):
        f.add("FAIL", "V9", "%s was installed from another lock: the marker is stale" % label)
    skills, shared = skills_dir_problems(project, deps, resolved, directory, label, marker, hint)
    for problem in skills:
        f.add("FAIL", "V9", problem)
    for where, detail in shared:
        f.add("FAIL", "V9", "shared folder %s %s" % (where, detail))


def _check_precedence(project, manifest, resolved, name, f, check, hint):
    """Copilot CLI reads a project .mcp.json before .github/mcp.json, so one that is not the rendering of the profile hides the pinned servers."""
    claude, copilot = manifest["hosts"].get("claude-code"), manifest["hosts"].get("copilot-cli")
    if not claude or not copilot:
        return
    path = project.root / claude["mcp_project"]
    if not path.is_file():
        return
    try:
        same = read_text_lf(path, claude["mcp_project"]) == dump_json(render("claude-code", resolved))
    except ToolchainError:
        same = False
    if not same:
        f.add("FAIL", check, "%s takes precedence over %s for Copilot CLI and differs from the rendering of profile %s (%s, or delete it)"
              % (claude["mcp_project"], copilot["mcp_project"], name, hint))


def install_command(profile, default, hosts=(), scope="project", replace_mcp=False):
    """The install command that puts `profile` in place for `hosts`: --host for a host that install does not pick on its own (Claude Code),
    --profile unless the profile is the default one, because that is what install and render --write-project do without it, and
    --scope user when the folder or file that a report is about is the user's, because install writes the project's without it.
    With replace_mcp the command replaces the MCP entries that differ and nothing else: --force replaces whatever differs, a skill that
    somebody edited included, so the skills are left out."""
    command = INSTALL_HINT
    if any(host not in DEFAULT_HOSTS for host in hosts):
        command += " --host " + " ".join(hosts)
    if profile != default:
        command += " --profile " + profile
    if scope == "user":
        command += " --scope user"
    if replace_mcp:
        command += " --skip-skills --force"
    return command


def mcp_hint(host, profile, default):
    """What to run for a project MCP file that is missing or differs: render --write-project writes the Copilot CLI and VS Code files of the
    default profile, and install writes the .mcp.json of Claude Code and every other profile."""
    if profile != default:
        return install_command(profile, default, [host])
    return CLAUDE_HINT if host == "claude-code" else RENDER_HINT


def _check_tool_pins(manifest, deps, resolved, f):
    """Run each pinned command-line tool of a profile and compare what it prints with the pin. A difference, a missing tool or an
    unreadable version fails a job (agent and executor profiles) and only warns for a developer."""
    level = "WARN" if resolved["mode"] == "dev" else "FAIL"
    declared = {tool["id"]: tool for tool in manifest.get("tools", [])}
    name = resolved["name"]
    for pinned in resolved["tools"]:
        tool = declared[pinned["id"]]
        path = find_tool(tool, deps)
        if path is None:
            f.add(level, "V9", "profile %s: tool %s is not on PATH, so it cannot be compared with the pinned version %s" % (name, pinned["id"], pinned["version"]))
            continue
        result = deps.runner.run([path] + tool["version_args"], timeout=30)
        printed = "%s %s" % (result.stdout or "", result.stderr or "")
        read = read_version(printed)
        if result.returncode != 0 or read is None:
            f.add(level, "V9", "profile %s: the version of tool %s could not be read, so it cannot be compared with the pinned version %s"
                  % (name, pinned["id"], pinned["version"]))
        elif at_pin(printed, pinned["version"]):
            f.add("PASS", "V9", "profile %s: tool %s is at the pinned version %s" % (name, pinned["id"], pinned["version"]))
        else:
            f.add(level, "V9", "profile %s: tool %s is version %s, not the pinned version %s; install the pinned version"
                  % (name, pinned["id"], show_version(read), pinned["version"]))


def _check_live(project, deps, manifest, profiles, lock, f, hosts, names, store):
    hosts = select_hosts(manifest, deps, hosts, DEFAULT_HOSTS)
    default = manifest["default_profile"]
    if not hosts:
        f.add("INFO", "V9", "no host binary found on PATH, so there is nothing live to check (pass --host)")
    for name in names:
        try:
            resolved = resolve_profile(manifest, profiles, lock, name, deps=deps)
        except ToolchainError as exc:
            level = "WARN" if profiles["profiles"][name]["mode"] == "dev" else "FAIL"
            f.add(level, "V9", "profile %s: live checks skipped, the profile cannot be resolved: %s" % (name, "; ".join(exc.problems)))
            continue
        _check_tool_pins(manifest, deps, resolved, f)
        has = has_skills(resolved)
        folders = {}
        for host in hosts:
            spec = manifest["hosts"][host]
            rendering = render(host, resolved)
            if resolved["mcp"]:
                path = project.root / spec["mcp_project"]
                if path.is_file():
                    _entries_missing(path, host, rendering, spec["mcp_project"], "FAIL", f)
                else:
                    f.add("FAIL", "V9", "%s is missing, so %s has no MCP servers for profile %s (%s)"
                          % (spec["mcp_project"], host, name, mcp_hint(host, name, default)))
            if host == "copilot-cli":
                _check_precedence(project, manifest, resolved, name, f, "V9", install_command(name, default, ["claude-code"]))
            user_level = resolved["mode"] == "dev"  # install writes no user-level file or folder for an agent or executor profile, so there is nothing to compare
            if spec.get("mcp_user") and user_level:
                user = Path(expand_home(spec["mcp_user"], deps.home))
                if user.is_file():
                    _entries_missing(user, host, rendering, project.shown(user, deps), "WARN", f, needs_one=True,
                                     hint=install_command(name, default, [host], "user"),
                                     replace_hint=install_command(name, default, [host], "user", replace_mcp=True))
            folders.setdefault(project.root / spec["skills_project"], [spec["skills_project"], [], has, "project"])[1].append(host)
            if spec.get("skills_user") and user_level:
                directory = Path(expand_home(spec["skills_user"], deps.home))
                folders.setdefault(directory, [project.shown(directory, deps), [], False, "user"])[1].append(host)
        for directory, (text, owners, required, scope) in folders.items():
            _check_skills_dir(project, deps, lock, resolved, directory, hosts_label(text, owners), required,
                              install_command(name, default, owners, scope), f)
        pack = project.store(store)
        if (pack / "MANIFEST.json").is_file() and resolved["skills"]:
            for level, message in store_problems(pack, resolved["skills"], lock, deps, resolved["shared"]):
                f.add(level, "V9", "profile %s: %s" % (name, message))
    f.add("INFO", "V9", "live checks done for %d host(s)" % len(hosts))


def _check_contracts(manifest, profiles, lock, deps, names, f):
    servers = servers_by_id(manifest)
    seen = set()
    for name in names:
        for item in profiles["profiles"][name]["mcp"]:
            key = "%s/%s" % (item["server"], item["variant"])
            server = servers.get(item["server"])
            contract = lock["contracts"].get(key)
            if key in seen or server is None or contract is None:
                continue
            seen.add(key)
            if contract["status"] in ("unavailable", "skipped"):
                f.add("WARN", "V10", "contract %s is %s (%s)" % (key, contract["status"], contract.get("detail") or contract.get("reason")))
                continue
            if contract["status"] != "captured":
                f.add("INFO", "V10", "contract %s is %s: a hosted server is not launched" % (key, contract["status"]))
                continue
            eula = server.get("eula")
            if eula and not license_accepted(deps.env, eula["env"]):
                f.add("WARN", "V10", "contract %s was not checked: the license of %s is not accepted (the operator sets %s)" % (key, item["server"], eula["env"]))
                continue
            try:
                launch = server_launch(manifest, lock, item["server"], item["variant"])
            except ToolchainError as exc:
                f.add("FAIL", "V10", "%s: %s" % (key, exc))
                continue
            if contract["package_version"] != lock["packages"][package_key(server["package"])]["version"]:
                f.add("WARN", "V10", "contract %s was captured for package version %s, not the locked one" % (key, contract["package_version"]))
                continue
            # profile_findings already fails every profile that uses it (V10); a launch line that nobody reviewed is not run
            if contract.get("launch") != launch_digest(launch):
                f.add("WARN", "V10", "contract %s was not launched: it was captured for another launch (capture it again with python scripts/toolchain.py lock --contracts)" % key)
                continue
            try:
                live = deps.probe_stdio([launch["command"]] + launch["args"],
                                        env=bounded_environment(probe_environment(launch["env"], deps.env, eula, license_variables(manifest)), contract["captured"]),
                                        timeout=PROBE_TIMEOUT)
            except toolchain_mcp.McpProbeError as exc:
                f.add("FAIL", "V10", "contract %s could not be checked: %s" % (key, unavailable_from(exc)["reason"]))
                continue
            delta = deps.contract_diff(contract["tools"], live.get("tools") or {})
            drift = ["%s %s" % (k, ", ".join(_clean_label(name) for name in sorted(delta.get(k, [])))) for k in ("added", "removed", "changed") if delta.get(k)]
            if drift:
                f.add("FAIL", "V10", "contract drift in %s: tools %s" % (key, "; ".join(drift)))
            else:
                f.add("PASS", "V10", "contract %s matches the live server" % key)


def _check_repo_skills(project, deps, profiles, names, f):
    """The skills of this repository go with every non-empty profile. We own their text, so a lint finding fails in every mode."""
    if not any(profiles["profiles"][n]["skills"] or profiles["profiles"][n]["mcp"] for n in names):
        return
    try:
        owned = repo_skill_folders(project.dir)
    except ToolchainError as exc:
        for problem in exc.problems:
            f.add("FAIL", "V8", problem)
        return
    for name, finding in repo_skill_findings(owned, deps):
        f.add("FAIL", "V8", "repo-owned skill %s: %s" % (name, finding))


def _lint_once(lint):
    """`lint` that answers from memory for a folder it has linted already, so that one verify run lints each skill once."""
    done = {}

    def once(folder):
        key = str(folder)
        if key not in done:
            done[key] = lint(folder)
        return done[key]
    return once


def run_verify(project, deps, profile_names=None, mode=None, live=False, hosts=None, contracts=False, store=None):
    f = Findings()
    deps = deps.derive(lint_skill=_lint_once(deps.lint_skill))
    manifest = profiles = lock = None
    try:
        manifest = load_manifest(project.dir / "toolchain.json")
        f.add("PASS", "V1", "toolchain.json is valid (%d servers, %d skill sources)" % (len(manifest["mcp_servers"]), len(manifest["skill_sources"])))
    except ToolchainError as exc:
        for problem in exc.problems:
            f.add("FAIL", "V1", problem)
    try:
        profiles = load_profiles(project.dir / "profiles.json")
        f.add("PASS", "V1", "profiles.json is valid (%d profiles)" % len(profiles["profiles"]))
    except ToolchainError as exc:
        for problem in exc.problems:
            f.add("FAIL", "V1", problem)
    if manifest and profiles:
        missing = check_default_profile(manifest, profiles)
        if missing:
            f.add("FAIL", "V1", "toolchain.json: " + missing)
    if project.lock_path.is_file():
        try:
            lock = load_lock(project.lock_path)
        except ToolchainError as exc:
            for problem in exc.problems:
                f.add("FAIL", "V3", problem)
    else:
        f.add("FAIL", "V3", "lock file missing: " + LOCK_HINT)
    names = []
    if profiles:
        names = list(profile_names) if profile_names else list(profiles["profiles"])
        for name in names:
            if name not in profiles["profiles"]:
                raise UsageError("profile '%s' does not exist (known: %s)" % (name, ", ".join(profiles["profiles"])))
        if mode:
            names = [n for n in names if profiles["profiles"][n]["mode"] == mode]
    if manifest and lock:
        _check_lock_coverage(manifest, lock, f)
        _check_quarantine_list(manifest, lock, f)
    for name in names:
        findings = (profile_findings(manifest, profiles, lock, name) if manifest
                    else [("FAIL", "V6", m) for m in instruction_problems(profiles["profiles"][name], profiles.base)])
        if lock is None:
            findings = [x for x in findings if x[2] != NO_LOCK_SKILLS]
        for level, check, message in findings:
            f.add(level, check, "profile %s: %s" % (name, message))
        if not findings:
            mode_name = profiles["profiles"][name]["mode"]
            if lock is not None:
                f.add("PASS", "V2", "profile %s (mode %s) verifies" % (name, mode_name))
            else:
                f.add("INFO", "V2", "profile %s (mode %s): its mode rules hold, but the lock is missing, so its skills and packages were not checked" % (name, mode_name))
    if manifest and profiles and lock and manifest["default_profile"] in names:
        _check_project_files(project, deps, manifest, profiles, lock, f)
    if profiles:
        _check_repo_skills(project, deps, profiles, names, f)
    project.manifest, project.profiles, project.lock = manifest, profiles, lock
    if live and manifest and profiles and lock:
        _check_live(project, deps, manifest, profiles, lock, f, hosts, [n for n in (profile_names or [manifest["default_profile"]]) if n in names], store)
    if contracts and manifest and profiles and lock:
        _check_contracts(manifest, profiles, lock, deps, names, f)
    return f


def cmd_verify(args, deps, root):
    if args.offline and args.contracts:
        raise UsageError("--offline and --contracts contradict each other: contracts launch servers and use the network")
    f = run_verify(Project(root), deps, args.profile, args.mode, args.live, args.host, args.contracts, args.store)
    fails, warns = f.count("FAIL"), f.count("WARN")
    ok = not fails and not (args.strict and warns)
    if args.json:
        print(json.dumps({"ok": ok, "failures": fails, "warnings": warns, "findings": f.items}, indent=2, ensure_ascii=False))
    else:
        for item in f.items:
            print("[%s] %s: %s" % (item["level"], item["check"], item["message"]))
        print("Result: %d failure(s), %d warning(s)" % (fails, warns))
    return 0 if ok else 1


# ---------------------------------------------------------------- list

def _skill_count(profile, lock, manifest, owned=0):
    """The unique upstream skills of a profile plus the repo-owned ones that a non-empty profile carries."""
    if any(s["names"] == "*" for s in profile["skills"]) and lock is None:
        return None
    if lock is not None:
        names = {entry["name"] for entry in select_skills(manifest, lock, profile)[0]}
    else:
        names = {n for s in profile["skills"] for n in s["names"]}
    return len(names) + (owned if profile["skills"] or profile["mcp"] else 0)


def _table(headers, rows):
    widths = [max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    return ["  ".join(str(c).ljust(widths[i]) for i, c in enumerate(r)).rstrip() for r in [headers] + rows]


def _variant_row(server, name, spec, lock):
    package = server.get("package")
    entry = (lock["packages"].get(package_key(package)) if lock and package else None)
    version = (entry.get("version") if entry and entry["status"] == "resolved" else ("unresolved" if entry else "not locked")) if package else "-"
    return [server["id"], name, server["transport"], server["status"], spec["network"], spec["credentials"], spec["access"],
            json.dumps(spec["unattended"]), version]


def cmd_list(args, deps, root):
    project = Project(root).load(lock="optional")
    manifest, profiles, lock = project.manifest, project.profiles, project.lock
    result = {}
    lines = []
    quarantine = quarantine_map(manifest)
    if args.profile:
        name = project.profile_name(args.profile)
        profile = profiles["profiles"][name]
        entries, problems = select_skills(manifest, lock, profile)
        shared = select_shared(manifest, lock, entries)[0] if lock is not None else []
        unique, seen = [], set()
        for e in entries:
            if e["name"] not in seen:
                seen.add(e["name"])
                unique.append(e)
        owned = []
        if profile["skills"] or profile["mcp"]:
            for repo_name, repo_folder in repo_skill_folders(project.dir).items():
                measured = deps.digest_tree(repo_folder)
                owned.append({"name": repo_name, "path": "toolchain/skills/" + repo_name, "digest": measured["digest"],
                              "files": measured["files"], "bytes": measured["bytes"]})
        servers = servers_by_id(manifest)
        declared = {tool["id"]: tool for tool in manifest.get("tools", [])}
        tool_rows = []
        for tool_id in profile.get("tools", []):
            tool = declared.get(tool_id)
            if tool is None or "package" not in tool:
                continue
            key = package_key(tool["package"])
            entry = lock["packages"].get(key) if lock else None
            version = entry.get("version") if entry and entry["status"] == "resolved" else ("unresolved" if entry else "not locked")
            tool_rows.append([tool_id, tool["command"], key, version])
        result["profile"] = {"name": name, "mode": profile["mode"], "title": profile.get("title"), "problems": problems,
                             "skills": unique, "repo_skills": owned,
                             "shared": [{"folder": s["folder"], "source": s["source"], "plugin": s["plugin"]} for s in shared],
                             "mcp": [{"server": m["server"], "variant": m["variant"]} for m in profile["mcp"]],
                             "tools": [dict(zip(("id", "command", "package", "version"), r)) for r in tool_rows]}
        lines.append("Profile %s (mode %s): %s" % (name, profile["mode"], profile.get("title", "")))
        lines.append("Skills: %d%s" % (len(unique) + len(owned), "" if not problems else " (%s)" % "; ".join(problems)))
        lines.extend("  %s/%s/%s  %s" % (e["source"], e["plugin"], e["name"], e["digest"][7:19]) for e in unique)
        lines.extend("  %s  %s  (repo-owned)" % (r["path"], r["digest"][7:19]) for r in owned)
        lines.append("Shared folders: %s" % (", ".join("%s (%s/%s)" % (s["folder"], s["source"], s["plugin"]) for s in shared) or "none"))
        rows = [_variant_row(servers[m["server"]], m["variant"], servers[m["server"]]["variants"][m["variant"]], lock)
                for m in profile["mcp"] if m["server"] in servers and m["variant"] in servers[m["server"]]["variants"]]
        lines.append("Servers: %d" % len(rows))
        lines.extend("  " + t for t in _table(["SERVER", "VARIANT", "TRANSPORT", "STATUS", "NETWORK", "CREDENTIALS", "ACCESS", "UNATTENDED", "PACKAGE"], rows)[1:])
        lines.append("Tools: %d" % len(tool_rows))
        lines.extend("  " + t for t in _table(["TOOL", "COMMAND", "PACKAGE", "VERSION"], tool_rows)[1:])
    if args.skills:
        if lock is None:
            raise ToolchainError("lock file missing: " + LOCK_HINT)
        rows = []
        for sid, source in lock["skill_sources"].items():
            for pname, plugin in source["plugins"].items():
                for sname, skill in plugin["skills"].items():
                    rows.append([sid, pname, sname, skill["digest"][7:19], "quarantined" if (sid, sname) in quarantine else ""])
        result["skills"] = [dict(zip(("source", "plugin", "name", "digest", "quarantined"), r[:4] + [bool(r[4])])) for r in rows]
        lines.extend(_table(["SOURCE", "PLUGIN", "SKILL", "DIGEST", "NOTE"], rows))
    if args.servers:
        rows = [_variant_row(s, v, spec, lock) for s in manifest["mcp_servers"] for v, spec in s["variants"].items()]
        result["servers"] = [dict(zip(("server", "variant", "transport", "status", "network", "credentials", "access", "unattended", "package"), r))
                             for r in rows]
        lines.extend(_table(["SERVER", "VARIANT", "TRANSPORT", "STATUS", "NETWORK", "CREDENTIALS", "ACCESS", "UNATTENDED", "PACKAGE"], rows))
    if not (args.profile or args.skills or args.servers):
        rows = []
        owned = len(repo_skill_folders(project.dir))
        for name, profile in profiles["profiles"].items():
            count = _skill_count(profile, lock, manifest, owned)
            rows.append([name, profile["mode"], "?" if count is None else count, len(profile["mcp"]), profile.get("title", "")])
        result["profiles"] = [dict(zip(("name", "mode", "skills", "servers", "title"), r)) for r in rows]
        lines.extend(_table(["PROFILE", "MODE", "SKILLS", "SERVERS", "TITLE"], rows))
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else "\n".join(lines))
    return 0


# ---------------------------------------------------------------- render

def cmd_render(args, deps, root):
    project = Project(root).load(fresh=True)
    if not args.write_project and not args.host:
        raise UsageError("render needs --host, or --write-project")
    name = project.profile_name(args.profile)
    resolved = resolve_profile(project.manifest, project.profiles, project.lock, name, deps=deps)
    for item in resolved["omitted"]:
        print(omitted_note(item), file=sys.stderr)
    if args.write_project:
        targets = []
        for host in PROJECT_HOSTS:
            if host not in project.manifest["hosts"]:
                continue
            rel = project.manifest["hosts"][host]["mcp_project"]
            path = project.root / rel
            refuse_links(path, project.root, project.root, deps.home)
            targets.append((rel, path, dump_json(render(host, resolved))))
        for rel, path, text in targets:
            unchanged = path.is_file() and read_text_lf(path, rel) == text
            if not unchanged:
                write_atomic(path, text)
            print("%s %s (profile %s)" % ("unchanged" if unchanged else "wrote", rel, name))
        return 0
    text = dump_json(render(args.host, resolved))
    if args.output:
        write_atomic(args.output, text)
        print("wrote %s" % Path(args.output).name)
    else:
        write_stdout(text)
    return 0


# ---------------------------------------------------------------- lock, update, fetch

def _lock_summary(lock):
    sources = lock["skill_sources"]
    skills = sum(len(p["skills"]) for s in sources.values() for p in s["plugins"].values())
    unresolved = [k for k, p in lock["packages"].items() if p["status"] != "resolved"]
    captured = sum(1 for c in lock["contracts"].values() if c["status"] == "captured")
    return "%d skill source(s), %d skill(s), %d package(s) (%d unresolved), %d contract(s) (%d captured)" % (
        len(sources), skills, len(lock["packages"]), len(unresolved), len(lock["contracts"]), captured), unresolved


def cmd_lock(args, deps, root):
    project = Project(root).load(lock="skip")
    old = load_lock(project.lock_path) if project.lock_path.is_file() else None
    if args.no_network:
        if old is None:
            raise ToolchainError("--no-network needs an existing lock: " + LOCK_HINT)
        new, notes = refresh_digest(project.manifest, old, deps, project.profiles)
    else:
        store = project.store()
        refuse_resolve_links(project, deps, store)
        new, notes = build_lock(project.manifest, project.profiles, old, deps, store, args.contracts, args.only)
    for note in notes:
        print("note: " + note)
    if args.check:
        differs = old is None or strip_generated(new) != strip_generated(old)
        if differs:
            print("the lock is out of date with the resolved result:")
            print("\n".join(format_report(diff_locks(old, new, deps), [])))
        else:
            print("the lock is current")
        return 1 if differs else 0
    write_atomic(project.lock_path, dump_json(new))
    summary, unresolved = _lock_summary(new)
    print("wrote toolchain/toolchain.lock.json: " + summary)
    for key in unresolved:
        print("WARN: package %s is unresolved (%s)" % (key, new["packages"][key].get("reason")))
    return 0


def clear_summary(path):
    """A summary that an earlier check left behind must not outlive a check that did not finish: it is removed before the work starts."""
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise ToolchainError("cannot replace the summary file: %s" % (exc.strerror or exc.__class__.__name__))


def cmd_update(args, deps, root):
    if args.summary_file:
        clear_summary(args.summary_file)
    project = Project(root).load(lock="skip")
    manifest, profiles = project.manifest, project.profiles
    old = load_lock(project.lock_path) if project.lock_path.is_file() else None
    store = project.store()
    refuse_resolve_links(project, deps, store)
    new, notes = build_lock(manifest, profiles, old, deps, store, args.contracts)
    diff = diff_locks(old, new, deps)
    changed = old is None or strip_generated(new) != strip_generated(old)
    manifest_edited = old is not None and changed and not any(diff.values())
    breaks = what_breaks(manifest, profiles, old, new)
    report = {"changed": changed, "notes": notes, **diff, "breaks": breaks}
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for note in notes:
            print("note: " + note)
        if old is None:
            print("There is no current lock: everything below is new.")
        print("\n".join(format_report(diff, breaks, notes=notes, show_notes=False, manifest_edited=manifest_edited)))
    if args.summary_file:
        write_atomic(args.summary_file, "# Toolchain update check\n\n" + "\n".join(format_report(diff, breaks, markdown=True, notes=notes, manifest_edited=manifest_edited)) + "\n")
    if args.write:
        if breaks and not args.force:
            print("not written: %d profile(s) would not verify (use --force to write anyway)" % len(breaks), file=sys.stderr)
            return 1
        write_atomic(project.lock_path, dump_json(new))
        print("wrote toolchain/toolchain.lock.json")
    return 3 if (args.fail_on_update and changed) else 0


def cmd_fetch(args, deps, root):
    project = Project(root).load(fresh=True)
    manifest, profiles, lock = project.manifest, project.profiles, project.lock
    names = [project.profile_name(n) for n in args.profile] if args.profile else [n for n, p in profiles["profiles"].items() if p["skills"]]
    deps = deps.derive(lint_skill=_lint_once(deps.lint_skill))  # every selected profile is resolved, and a repo-owned skill is linted once
    selection, shared = set(), set()
    for name in names:
        resolved = resolve_profile(manifest, profiles, lock, name, deps=deps)
        selection.update((s["source"], s["plugin"], s["name"]) for s in resolved["skills"])
        shared.update((s["source"], s["folder"]) for s in resolved["shared"])
    if not selection:
        print("nothing to fetch: the selected profiles load no skill")
        return 0
    store = project.store(args.store)
    refuse_store_links(project, deps, store)
    quarantined = tuple(sorted({q["skill"] for q in manifest.get("quarantine", [])}))
    try:
        pack = deps.vendor_skills(lock, sorted(selection), store, deps.runner, quarantine=quarantined, **({"shared": sorted(shared)} if shared else {}))
    except toolchain_sources.SourceError as exc:
        raise ToolchainError("fetch failed: %s" % (toolchain_io.safe_detail(exc) or "could not vendor the skills"))
    skills = pack.get("skills", {})
    print("fetched %d skill(s), %d file(s)%s, into %s" % (len(skills), sum(s.get("files", 0) for s in skills.values()),
                                                         ", %d shared folder(s)" % len(shared) if shared else "", project.shown(store, deps)))
    return 0


# ---------------------------------------------------------------- install

def make_op(action, text, extra=(), apply=None, label=None):
    """One step of an install plan. `text` is the line the plan prints, `label` names a step that prints none (an error says which step failed)."""
    return {"action": action, "text": text, "extra": list(extra), "apply": apply, "label": label}


def apply_op(op):
    """Carry out one step. Whatever the toolchain refuses keeps its own words; any other failure (a full disk, a locked file) is named with the step."""
    try:
        op["apply"]()
    except ToolchainError:
        raise
    except Exception as exc:
        raise ToolchainError("install failed while applying %s: %s" % (op["text"] or op["label"] or op["action"],
                                                                       toolchain_io.safe_detail(exc) or type(exc).__name__)) from None


def copy_tree(source, target):
    """Copy a folder of files. A link is refused, the folder itself and everything in it: skills are copied, never linked."""
    refusal = ToolchainError("%s holds a symbolic link; skills are copied, never linked" % Path(source).name)
    if is_link(source):
        raise refusal
    for folder, dirs, names in os.walk(source):
        relative = Path(folder).relative_to(source)
        (Path(target) / relative).mkdir(parents=True, exist_ok=True)
        for entry in dirs + names:
            if is_link(Path(folder) / entry):
                raise refusal
        for name in names:
            shutil.copyfile(Path(folder) / name, Path(target) / relative / name)


REPARSE_POINT = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT


def is_link(path):
    """A symbolic link or, on Windows, a reparse point such as a junction.

    A OneDrive placeholder is a reparse point too, but it is an ordinary file or folder to everything else, so it does not count."""
    if os.path.islink(path):
        return True
    try:
        info = os.lstat(path)
    except OSError:
        return False
    if not getattr(info, "st_file_attributes", 0) & REPARSE_POINT:
        return False
    tag = getattr(info, "st_reparse_tag", None)
    return tag is None or ((tag & 0xFFFF0FFF) != 0x9000001A and tag != 0x80000021)


def link_inside(folder):
    """The folder itself when it is a link, else a link below it at any depth, else None. Each entry is tested before the walk goes into
    it, and the first link ends the walk, so the walk never enters a link, also not a junction, which os.walk would follow."""
    if is_link(folder):
        return Path(folder)
    for current, dirs, names in os.walk(folder):
        for entry in dirs + names:
            if is_link(Path(current) / entry):
                return Path(current) / entry
    return None


def link_label(path, root, home):
    path = Path(os.path.abspath(path))
    for base, prefix in ((root, ""), (home, "$HOME/")):
        try:
            return prefix + path.relative_to(Path(os.path.abspath(base))).as_posix()
        except ValueError:
            continue
    return path.name


def refuse_links(path, boundary, root, home):
    """Refuse to write where `path`, or a folder between it and `boundary`, is a link. The boundary itself is the user's choice."""
    boundary, current = Path(os.path.abspath(boundary)), Path(os.path.abspath(path))
    while current != boundary and boundary in current.parents:
        if is_link(current):
            raise ToolchainError("%s is a link; the toolchain does not write through links" % link_label(current, root, home))
        current = current.parent


def refuse_store_links(project, deps, store):
    """The pack folder and the folders between it and the project folder must not be links. A pack elsewhere (--store) is refused
    when the folder itself is a link: what lies above it is the user's choice."""
    store, root = Path(os.path.abspath(store)), Path(os.path.abspath(project.root))
    refuse_links(store, root if root in store.parents else store.parent, project.root, deps.home)


def refuse_resolve_links(project, deps, store):
    """What `lock` and `update` resolve into: the pack folder and what lies above it, as for a fetch, and the folder of the git caches in it."""
    refuse_store_links(project, deps, store)
    refuse_links(Path(store) / ".cache", store, project.root, deps.home)


def _copier(source, dest, digest, deps, what, guard):
    """Copy a folder next to its target, check the copy, and only then swap it in. The old folder is put back when the swap fails."""
    def run():
        guard(dest)
        if not Path(source).is_dir():
            raise ToolchainError("%s: its source folder is missing (fetch it first)" % what)
        dest.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".toolchain-new-", dir=str(dest.parent)))
        backup = None
        try:
            os.chmod(staging, 0o755)
            copy_tree(source, staging)
            if deps.digest_tree(staging)["digest"] != digest:
                raise ToolchainError("%s: the copy does not match its locked digest" % what)
            if os.path.lexists(dest):
                backup = dest.parent / (".toolchain-old-%s-%s" % (dest.name, secrets.token_hex(6)))
                toolchain_io.replace_retrying(dest, backup)
            try:
                toolchain_io.replace_retrying(staging, dest)
            except BaseException:
                if backup is not None:
                    toolchain_io.replace_retrying(backup, dest)
                    backup = None
                raise
            if backup is not None:
                remove_tree(backup)
        finally:
            if staging.exists():
                remove_tree(staging)
    return run


def _remover(folder, guard):
    def run():
        guard(folder)
        remove_tree(folder)
    return run


def _marker_writer(path, marker, guard):
    def run():
        guard(path)
        write_atomic(path, dump_json(marker))
    return run


def store_op(project, deps, resolved, store):
    refuse_store_links(project, deps, store)
    problems = store_problems(store, resolved["skills"], project.lock, deps, resolved["shared"])
    label = project.shown(store, deps)
    if not problems:
        return make_op("same", "= store %s is current" % label)
    quarantined = tuple(sorted({q["skill"] for q in project.manifest.get("quarantine", [])}))
    selection = sorted((s["source"], s["plugin"], s["name"]) for s in resolved["skills"])
    shared = sorted({(s["source"], s["folder"]) for s in resolved["shared"]})

    def run():
        refuse_store_links(project, deps, store)
        try:
            deps.vendor_skills(project.lock, selection, store, deps.runner, quarantine=quarantined, **({"shared": shared} if shared else {}))
        except toolchain_sources.SourceError as exc:
            raise ToolchainError("fetch failed: %s" % (toolchain_io.safe_detail(exc) or "could not vendor the skills"))
        remaining = store_problems(store, resolved["skills"], project.lock, deps, resolved["shared"])
        if remaining:
            raise ToolchainError("the local pack is still not usable after the fetch", [m for _level, m in remaining])
    return make_op("add", "+ store %s: fetch %d skill(s) (%s)" % (label, len(selection), sorted({m for _l, m in problems})[0]), apply=run)


def _measured(deps, folder):
    """The digest of a folder, or None for one that cannot be measured (a file in its place, a file in it that cannot be read)."""
    try:
        return deps.digest_tree(folder)["digest"]
    except toolchain_sources.SourceError:
        return None


def _has_content(deps, folder, digest):
    """Whether a folder that the kit did not install holds exactly the pinned content. A folder that cannot be measured does not."""
    return _measured(deps, folder) == digest


def _managed_ops(kind, wanted, managed, base, base_label, force, deps, guard):
    """The operations that make `base` hold the wanted folders: (ops, what the marker should record afterwards).

    `kind` is "skill" or "shared". The marker says what the kit installed and with which content. A managed folder whose content
    is no longer the recorded one was edited by its owner, so it is neither replaced nor removed without --force. One that cannot
    be measured counts as edited."""
    noun = "shared folder" if kind == "shared" else kind
    ending = "the profile no longer needs it" if kind == "shared" else "it left the profile"
    ops, target = [], {}
    for name, item in wanted.items():
        dest = base / name
        guard(dest)
        copier = _copier(item["source"], dest, item["digest"], deps, "%s %s" % (noun, name), guard)
        if not os.path.lexists(dest):
            ops.append(make_op("add", "+ %s %s -> %s/%s" % (kind, name, base_label, name), apply=copier))
            target[name] = item["digest"]
        elif name not in managed:
            if _has_content(deps, dest, item["digest"]):
                # What an install that stopped before it wrote its marker, or a copy made by hand, leaves: exactly what the lock pins.
                ops.append(make_op("same", "= %s %s" % (kind, name)))
                target[name] = item["digest"]
            elif force:
                ops.append(make_op("change", "~ %s %s: replace %s/%s (forced)" % (kind, name, base_label, name), apply=copier))
                target[name] = item["digest"]
            else:
                ops.append(make_op("conflict", "! %s %s: %s/%s exists and is not managed by the toolchain (use --force to replace it)"
                                   % (kind, name, base_label, name)))
        else:
            actual = _measured(deps, dest)
            if actual == item["digest"]:
                ops.append(make_op("same", "= %s %s" % (kind, name)))
                target[name] = item["digest"]
            elif actual != managed[name] and not force:
                ops.append(make_op("conflict", "! %s %s: modified since it was installed; use --force to replace it" % (kind, name)))
                target[name] = managed[name]
            else:
                ops.append(make_op("change", "~ %s %s: replace %s/%s" % (kind, name, base_label, name), apply=copier))
                target[name] = item["digest"]
    for name in managed:
        folder = base / name
        if name in wanted or not os.path.lexists(folder):
            continue
        guard(folder)
        if not force and _measured(deps, folder) != managed[name]:
            ops.append(make_op("conflict", "! %s %s: modified since it was installed; use --force to remove it" % (kind, name)))
            target[name] = managed[name]
        else:
            ops.append(make_op("change", "~ %s %s: remove it, %s" % (kind, name, ending), apply=_remover(folder, guard)))
    return ops, target


def skill_ops(project, deps, resolved, directory, hosts, force, store, boundary):
    """The operations that make one skills folder, and the shared folders beside it, hold the profile's content and nothing else that the kit put there."""
    label = project.shown(directory, deps)
    guard = lambda path: refuse_links(path, boundary, project.root, deps.home)
    guard(directory)
    wanted = {s["name"]: {"source": Path(store) / "skills" / s["name"], "digest": s["digest"]} for s in resolved["skills"]}
    for item in resolved["repo_skills"]:
        wanted[item["name"]] = {"source": project.root / item["path"], "digest": item["digest"]}
    wanted_shared = {s["folder"]: {"source": Path(store) / s["folder"], "digest": s["digest"]} for s in resolved["shared"]}
    marker_path = directory / MARKER
    marker = None
    if marker_path.is_file():
        try:
            marker = read_marker(marker_path)
        except ToolchainError:
            marker = None
    managed = marker["skills"] if marker else {}
    managed_shared = marker.get("shared", {}) if marker else {}
    ops = [make_op("note", "# skills folder %s (%s)" % (label, ", ".join(hosts)))] if wanted or managed or wanted_shared or managed_shared else []
    skill_changes, target = _managed_ops("skill", wanted, managed, directory, label, force, deps, guard)
    parent = directory.parent
    shared_changes, shared_target = _managed_ops("shared", wanted_shared, managed_shared, parent, project.shown(parent, deps), force, deps, guard)
    ops.extend(skill_changes)
    ops.extend(shared_changes)
    new_marker = {"profile": resolved["name"], "lock": resolved["lock"], "skills": dict(sorted(target.items()))}
    if shared_target:
        new_marker["shared"] = dict(sorted(shared_target.items()))
    if marker == new_marker:
        ops.append(make_op("same", "= marker %s/%s" % (label, MARKER)))
    elif target or shared_target or marker_path.is_file():
        exists = marker_path.is_file()
        ops.append(make_op("change" if exists else "add", "%s marker %s/%s" % ("~" if exists else "+", label, MARKER),
                           apply=_marker_writer(marker_path, new_marker, guard)))
    return ops


def known_renderings(project, host, deps=None):
    texts = set()
    for name in project.profiles["profiles"]:
        try:
            texts.add(dump_json(render(host, resolve_profile(project.manifest, project.profiles, project.lock, name, deps=deps))))
        except ToolchainError:
            continue
    return texts


def mcp_project_op(project, deps, resolved, host, spec, force):
    rel = spec["mcp_project"]
    path = project.root / rel
    refuse_links(path, project.root, project.root, deps.home)
    text = dump_json(render(host, resolved))

    def write():
        refuse_links(path, project.root, project.root, deps.home)
        write_atomic(path, text)
    if not path.exists():
        return make_op("add", "+ mcp %s %s" % (host, rel), apply=write)
    try:
        current = read_text_lf(path, rel)
    except ToolchainError:
        current = None
    if current == text:
        return make_op("same", "= mcp %s %s" % (host, rel))
    if current is not None and current in known_renderings(project, host, deps):
        return make_op("change", "~ mcp %s %s: replace the rendering of another profile" % (host, rel), apply=write)
    if force:
        return make_op("change", "~ mcp %s %s: differs from every rendering, replaced (--force)" % (host, rel), apply=write)
    diff = [l.rstrip("\n") for l in difflib.unified_diff((current or "").splitlines(True), text.splitlines(True), "current", "rendered", n=1)][:40]
    return make_op("conflict", "! mcp %s %s differs from every rendering of the toolchain (use --force to replace it)" % (host, rel), diff)


def mcp_user_ops(project, deps, resolved, host, spec, force):
    """Merge the profile's servers into the user's MCP file: add what is missing, keep everything else, back up first."""
    path = Path(expand_home(spec["mcp_user"], deps.home))
    refuse_links(path, deps.home, project.root, deps.home)
    label = project.shown(path, deps)
    container = "servers" if host == "vscode" else "mcpServers"
    wanted = render(host, resolved)[container]
    existing = read_json(path, label) if path.exists() else None
    if existing is not None and (not isinstance(existing, dict) or not isinstance(existing.get(container, {}), dict)):
        raise ToolchainError("%s: expected an object with a '%s' object; it is left untouched" % (label, container))
    current = (existing or {}).get(container, {})
    ops, writes = [], {}
    for sid, entry in wanted.items():
        if sid not in current:
            ops.append(make_op("add", "+ mcp-user %s %s: add server %s" % (host, label, sid)))
            writes[sid] = entry
        elif current[sid] == entry:
            ops.append(make_op("same", "= mcp-user %s %s: server %s is unchanged" % (host, label, sid)))
        elif force:
            ops.append(make_op("change", "~ mcp-user %s %s: replace server %s (--force)" % (host, label, sid)))
            writes[sid] = entry
        else:
            ops.append(make_op("conflict", "! mcp-user %s %s: server %s differs (use --force to replace it)" % (host, label, sid)))

    def run():
        refuse_links(path, deps.home, project.root, deps.home)
        if path.exists():
            backup = path.with_name(path.name + ".bak-" + deps.stamp())
            counter = 1
            while backup.exists():
                backup = path.with_name("%s.bak-%s-%d" % (path.name, deps.stamp(), counter))
                counter += 1
            shutil.copyfile(path, backup)
        merged = copy.deepcopy(existing) if existing is not None else {}
        merged.setdefault(container, {}).update(copy.deepcopy(writes))
        write_atomic(path, dump_json(merged))
    if writes:
        ops.append(make_op("write", None, apply=run, label="write " + label))
    return ops


def cmd_install(args, deps, root):
    project = Project(root).load(fresh=True)
    manifest, profiles, lock = project.manifest, project.profiles, project.lock
    name = project.profile_name(args.profile)
    if args.scope == "user" and profiles["profiles"][name]["mode"] != "dev":
        raise UsageError("a user-level file is shared by everything this user runs; install agent and executor profiles into a project folder, "
                         "and let a job load them from the pack with the load plan")
    resolved = resolve_profile(manifest, profiles, lock, name, deps=deps)
    hosts = select_hosts(manifest, deps, args.host, DEFAULT_HOSTS)
    if not hosts:
        print("no host found: none of the binaries (%s) is on PATH; pass --host to choose one"
              % ", ".join(sorted(manifest["hosts"][h]["binary"] for h in DEFAULT_HOSTS if h in manifest["hosts"])))
        return 2
    store = project.store(args.store)
    ops = []
    if not args.skip_skills:
        folders = {}
        for host in hosts:
            spec = manifest["hosts"][host]
            where = spec["skills_project"] if args.scope == "project" else spec.get("skills_user")
            if where is None:
                ops.append(make_op("note", "# %s has no skills folder at this scope" % host))
                continue
            directory = project.root / where if args.scope == "project" else Path(expand_home(where, deps.home))
            folders.setdefault(directory, []).append(host)
        if folders and resolved["skills"]:
            ops.append(store_op(project, deps, resolved, store))
        boundary = project.root if args.scope == "project" else deps.home
        for directory, owners in folders.items():
            ops.extend(skill_ops(project, deps, resolved, directory, owners, args.force, store, boundary))
    if not args.skip_mcp:
        for item in resolved["omitted"]:
            ops.append(make_op("note", omitted_note(item)))
        if "claude-code" in hosts and len(hosts) > 1:
            ops.append(make_op("note", "note: claude-code writes %s, which Copilot CLI reads before %s"
                               % (manifest["hosts"]["claude-code"]["mcp_project"], manifest["hosts"]["copilot-cli"]["mcp_project"])))
        for host in hosts:
            spec = manifest["hosts"][host]
            if args.scope == "project":
                ops.append(mcp_project_op(project, deps, resolved, host, spec, args.force))
            elif spec.get("mcp_user"):
                ops.extend(mcp_user_ops(project, deps, resolved, host, spec, args.force))
            else:
                ops.append(make_op("note", "# %s has no user MCP file in this version; use --scope project" % host))
    for op in ops:
        if op["text"]:
            print(op["text"])
            for line in op["extra"]:
                print("    " + line)
    counts = {a: sum(1 for o in ops if o["action"] == a and o["text"]) for a in ("add", "change", "same", "conflict")}
    summary = "profile %s, %d to add, %d to change, %d unchanged, %d conflict(s)" % (name, counts["add"], counts["change"], counts["same"], counts["conflict"])
    if args.apply:
        for op in ops:
            if op["apply"] and op["action"] in ("add", "change", "write"):
                apply_op(op)
        print("applied: " + summary)
    else:
        print("plan: " + summary)
        print("nothing was changed: add --apply to carry out the plan")
    return 1 if counts["conflict"] else 0


# ---------------------------------------------------------------- doctor

def parse_version(text):
    match = re.search(r"\d+(?:\.\d+)+", text) or re.search(r"\d+", text)
    return tuple(int(part) for part in match.group(0).split(".")) if match else None


def at_least(found, minimum):
    wanted = tuple(int(part) for part in minimum.split("."))
    size = max(len(found), len(wanted))
    return found + (0,) * (size - len(found)) >= wanted + (0,) * (size - len(wanted))


def read_version(text):
    """(numbers, suffix) of the first version that a text holds: ((4, 0, 0), '-beta.4') for 'tool 4.0.0-beta.4'; None when it holds no number."""
    match = READ_VERSION_RE.search(text) or re.search(r"(\d+)()", text)
    return (tuple(int(part) for part in match.group(1).split(".")), match.group(2) or "") if match else None


def show_version(read):
    return ".".join(map(str, read[0])) + read[1]


def at_pin(printed, pinned):
    """Whether what a tool printed is the pinned version: the same numbers (1.8 is 1.8.0) and the same pre-release or build suffix."""
    found, wanted = read_version(printed), read_version(pinned)
    if found is None or wanted is None:
        return False
    size = max(len(found[0]), len(wanted[0]))
    return found[0] + (0,) * (size - len(found[0])) == wanted[0] + (0,) * (size - len(wanted[0])) and found[1] == wanted[1]


def find_tool(tool, deps):
    """The path of a manifest tool on PATH, trying its alternative names; None when it is not there."""
    return next((p for p in (deps.runner.which(c) for c in [tool["command"]] + tool.get("alternatives", [])) if p), None)


def tool_pins(manifest, lock, profile):
    """{tool id: pinned version} for the tools of a profile whose package the lock resolves to an exact version."""
    declared = {tool["id"]: tool for tool in manifest.get("tools", [])}
    pins = {}
    for tool_id in profile.get("tools", []):
        tool = declared.get(tool_id)
        entry = ((lock.get("packages") or {}).get(package_key(tool["package"])) if tool and "package" in tool else None) or {}
        if entry.get("status") == "resolved" and exact_version(tool["package"]["ecosystem"], entry.get("version")):
            pins[tool_id] = entry["version"]
    return pins


def _doctor_tools(manifest, deps, f, pins=None):
    """The tools of the manifest on this machine. A tool that the selected profile pins is compared with its pin, the others with their minimum."""
    pins = pins or {}
    for tool in manifest.get("tools", []):
        path = find_tool(tool, deps)
        level = "FAIL" if tool["required"] else "WARN"
        check = "tool %s" % tool["id"]
        if path is None:
            f.add(level, check, "not found on PATH; needed for %s" % tool["needed_for"])
            continue
        result = deps.runner.run([path] + tool["version_args"], timeout=30)
        printed = "%s %s" % (result.stdout or "", result.stderr or "")
        version = parse_version(printed)
        if result.returncode != 0 or version is None:
            f.add("WARN", check, "found, but its version could not be read")
        elif tool["id"] in pins:
            if at_pin(printed, pins[tool["id"]]):
                f.add("PASS", check, "version %s (pinned)" % show_version(read_version(printed)))
            else:
                f.add("WARN", check, "version %s is not the pinned version %s; install the pinned version" % (show_version(read_version(printed)), pins[tool["id"]]))
        elif not at_least(version, tool["min"]):
            f.add(level, check, "version %s is older than the minimum %s; needed for %s" % (".".join(map(str, version)), tool["min"], tool["needed_for"]))
        else:
            f.add("PASS", check, "version %s (minimum %s)" % (".".join(map(str, version)), tool["min"]))


def _doctor_lock(project, manifest, profiles, name, f):
    if not project.lock_path.is_file():
        f.add("FAIL", "lock", "missing: " + LOCK_HINT)
        return None
    try:
        lock = load_lock(project.lock_path)
    except ToolchainError as exc:
        f.add("FAIL", "lock", "invalid (%d problem(s)); first: %s" % (len(exc.problems), exc.problems[0]))
        return None
    if lock["inputs_digest"] != inputs_digest(manifest):
        f.add("FAIL", "lock", "stale: the manifest changed since it was resolved (%s)" % LOCK_HINT)
    else:
        f.add("PASS", "lock", "present, valid and fresh (generated %s)" % lock["generated"])
    wanted = ["%s/%s" % (m["server"], m["variant"]) for m in profiles["profiles"][name]["mcp"]]
    counts = {}
    for key in wanted:
        status = (lock["contracts"].get(key) or {"status": "missing"})["status"]
        counts[status] = counts.get(status, 0) + 1
    f.add("INFO", "contracts", "profile %s uses %d: %s" % (name, len(wanted), ", ".join("%d %s" % (n, s) for s, n in sorted(counts.items())) or "none"))
    return lock


def _doctor_skills(project, deps, resolved, rel, owners, f, hint):
    """The managed skills of one skills folder, printed once for the hosts that share it. `hint` is the install command that puts them right."""
    directory = project.root / rel
    check = "host %s skills" % ", ".join(owners)
    marker_path = directory / MARKER
    if not marker_path.is_file():
        if has_skills(resolved):
            f.add("WARN", check, "no skills are installed in %s (%s)" % (rel, hint))
        return
    try:
        marker = read_marker(marker_path)
    except ToolchainError:
        f.add("WARN", check, "the managed marker in %s is unreadable" % rel)
        return
    skills, shared = skills_dir_problems(project, deps, resolved, directory, rel, marker, hint)
    for problem in skills:
        f.add("FAIL", check, problem)
    if marker["lock"] != resolved["lock"]:
        f.add("WARN", check, "the managed skills in %s were installed from another lock (%s)" % (rel, hint))
    elif not skills:
        f.add("PASS", check, "the managed skills in %s match the lock" % rel)
    check = "host %s shared" % ", ".join(owners)
    for where, detail in shared:
        f.add("FAIL", check, "%s %s; %s" % (where, detail, hint))
    if not shared:
        for item in resolved["shared"]:
            f.add("PASS", check, "%s equals the lock" % project.shown(directory.parent / item["folder"], deps))


def _doctor_hosts(project, deps, manifest, resolved, hosts, f):
    name, default = resolved["name"], manifest["default_profile"]
    for host in hosts:
        spec = manifest["hosts"][host]
        path = project.root / spec["mcp_project"]
        if not path.is_file():
            f.add("WARN", "host %s mcp" % host, "%s is missing (%s)" % (spec["mcp_project"], mcp_hint(host, name, default)))
        else:
            try:
                same = read_text_lf(path, spec["mcp_project"]) == dump_json(render(host, resolved))
            except ToolchainError:
                same = False  # a file that cannot be read as text is not the rendering
            if same:
                f.add("PASS", "host %s mcp" % host, "%s equals the rendering of profile %s" % (spec["mcp_project"], name))
            else:
                f.add("WARN", "host %s mcp" % host, "%s differs from the rendering of profile %s (%s)" % (spec["mcp_project"], name, mcp_hint(host, name, default)))
        if host == "copilot-cli":
            _check_precedence(project, manifest, resolved, name, f, "host copilot-cli mcp", install_command(name, default, ["claude-code"]))
    folders = {}
    for host in hosts:
        folders.setdefault(manifest["hosts"][host]["skills_project"], []).append(host)
    for rel, owners in folders.items():
        _doctor_skills(project, deps, resolved, rel, owners, f, install_command(name, default, owners))


def cmd_doctor(args, deps, root):
    project = Project(root).load(lock="skip")
    manifest, profiles = project.manifest, project.profiles
    name = project.profile_name(args.profile)
    f = Findings()
    pins = {}
    if project.lock_path.is_file():
        try:
            pins = tool_pins(manifest, load_lock(project.lock_path), profiles["profiles"][name])
        except ToolchainError:
            pass  # the lock check below says what is wrong with it; without a usable lock the tools keep the check of their minimum
    _doctor_tools(manifest, deps, f, pins)
    for host, spec in manifest["hosts"].items():
        found = deps.runner.which(spec["binary"])
        f.add("PASS" if found else "INFO", "host %s" % host, "found on PATH" if found else "not found on PATH (%s)" % spec["binary"])
    if args.offline:
        f.add("INFO", "sign-in", "sign-in checks skipped offline")
    else:
        for tool, argv in (("gh", ["auth", "status", "--no-refresh"]), ("az", ["account", "show"])):
            path = deps.runner.which(tool)
            if path:
                result = deps.runner.run([path] + argv, timeout=30)
                if tool == "gh" and result.returncode != 0 and "unknown flag" in (result.stdout + result.stderr).lower():
                    # gh before 2.103.0 has no --no-refresh and, before that version, no token refresh either: a plain call is the same check.
                    result = deps.runner.run([path, "auth", "status"], timeout=30)
                signed_in = result.returncode == 0
                f.add("PASS" if signed_in else "WARN", "sign-in %s" % tool, "signed in" if signed_in else "not signed in")
    lock = _doctor_lock(project, manifest, profiles, name, f)
    resolved = None
    if lock is not None:
        try:
            resolved = resolve_profile(manifest, profiles, lock, name, deps=deps)
        except ToolchainError as exc:
            f.add("WARN", "profile %s" % name, "cannot be resolved: %s" % "; ".join(exc.problems))
    if resolved is not None:
        _doctor_hosts(project, deps, manifest, resolved, select_hosts(manifest, deps, args.host), f)
    servers = servers_by_id(manifest)
    for item in profiles["profiles"][name]["mcp"]:
        server = servers.get(item["server"])
        if server is None:
            continue
        if server["transport"] == "http" and not args.offline:
            result = deps.probe_http(server["url"], headers=dict(server.get("headers", {})), runner=deps.runner)
            status = result.get("status") if isinstance(result, dict) else None
            if status == "open":
                f.add("PASS", "server %s" % item["server"], "reachable")
            elif status == "needs-sign-in":
                f.add("PASS", "server %s" % item["server"], "reachable, needs a sign-in")
            else:
                f.add("WARN", "server %s" % item["server"], "not reachable")
        if server.get("eula"):
            eula = server["eula"]
            accepted = license_accepted(deps.env, eula["env"])
            f.add("INFO", "license %s" % item["server"], "the operator must accept the license (%s) by setting %s=true; the kit never sets it; currently %s"
                  % (eula["url"], eula["env"], "accepted" if accepted else "not accepted"))
        if lock is not None and "package" in server:
            entry = lock["packages"].get(package_key(server["package"]))
            if entry is None or entry["status"] != "resolved":
                f.add("WARN", "package %s" % package_key(server["package"]), "unresolved in the lock (server %s)" % item["server"])
    fails = f.count("FAIL")
    if args.json:
        print(json.dumps({"ok": not fails, "findings": f.items}, indent=2, ensure_ascii=False))
    else:
        for item in f.items:
            print("[%s] %s: %s" % (item["level"], item["check"], item["message"]))
    return 1 if fails else 0


# ---------------------------------------------------------------- command line

def build_parser():
    parser = argparse.ArgumentParser(prog="toolchain.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=None, help="project folder (default: the parent of the scripts folder)")
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--root", type=Path, default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    def command(name, help_text):
        return sub.add_parser(name, parents=[shared], help=help_text, description=help_text)

    p = command("list", "list the profiles, the locked skills or the servers")
    p.add_argument("--profile", metavar="NAME")
    p.add_argument("--skills", action="store_true")
    p.add_argument("--servers", action="store_true")
    p.add_argument("--json", action="store_true")

    p = command("verify", "check the manifest, the profiles, the lock and the generated files")
    p.add_argument("--offline", action="store_true", help="no network (the default; contradicts --contracts)")
    p.add_argument("--strict", action="store_true", help="a warning fails too")
    p.add_argument("--profile", nargs="+", action="extend", metavar="NAME")
    p.add_argument("--mode", choices=MODES)
    p.add_argument("--live", action="store_true", help="also check what is installed for each host")
    p.add_argument("--host", nargs="+", action="extend", choices=HOSTS,
                   help="the hosts to check with --live (default: copilot-cli and vscode when they are on PATH; claude-code only when named)")
    p.add_argument("--contracts", action="store_true", help="launch the stdio servers and compare their tools with the lock")
    p.add_argument("--store", metavar="DIR")
    p.add_argument("--json", action="store_true")

    p = command("render", "render the MCP configuration of a profile")
    p.add_argument("--profile", metavar="NAME")
    p.add_argument("--host", choices=RENDER_TARGETS)
    p.add_argument("--output", metavar="FILE")
    p.add_argument("--write-project", action="store_true", help="write .github/mcp.json and .vscode/mcp.json")

    p = command("lock", "resolve the manifest into the lock")
    p.add_argument("--contracts", action="store_true", help="also launch the servers and capture their tool contracts")
    p.add_argument("--only", nargs="+", action="extend", metavar="SOURCE_OR_PACKAGE")
    p.add_argument("--check", action="store_true", help="resolve into memory and fail when the lock differs")
    p.add_argument("--no-network", action="store_true", help="only re-derive inputs_digest from the manifest")

    p = command("update", "show what an upstream refresh would change and break")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    p.add_argument("--fail-on-update", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--summary-file", metavar="PATH")
    p.add_argument("--contracts", action="store_true")
    p.add_argument("--force", action="store_true", help="with --write, write even when a profile would not verify")

    p = command("fetch", "vendor the locked skills into the local pack")
    p.add_argument("--store", metavar="DIR")
    p.add_argument("--profile", nargs="+", action="extend", metavar="NAME")

    p = command("install", "copy skills and MCP configuration into a host (a plan unless --apply)")
    p.add_argument("--host", nargs="+", action="extend", choices=HOSTS,
                   help="the hosts to install for (default: copilot-cli and vscode when they are on PATH; claude-code only when named, "
                        "because its .mcp.json is read by Copilot CLI before .github/mcp.json)")
    p.add_argument("--profile", metavar="NAME")
    p.add_argument("--scope", choices=("project", "user"), default="project", help="user is for dev profiles only")
    p.add_argument("--store", metavar="DIR")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--skip-skills", action="store_true")
    p.add_argument("--skip-mcp", action="store_true")

    p = command("doctor", "check this machine for what the toolchain needs")
    p.add_argument("--profile", metavar="NAME")
    p.add_argument("--host", nargs="+", action="extend", choices=HOSTS)
    p.add_argument("--offline", action="store_true", help="do not probe hosted servers and do not ask gh or az whether you are signed in")
    p.add_argument("--json", action="store_true")
    return parser


COMMANDS = {"list": cmd_list, "verify": cmd_verify, "render": cmd_render, "lock": cmd_lock, "update": cmd_update,
            "fetch": cmd_fetch, "install": cmd_install, "doctor": cmd_doctor}


def main(argv=None, deps=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    root = Path(args.root) if getattr(args, "root", None) else DEFAULT_ROOT
    try:
        return COMMANDS[args.command](args, deps or Deps(), root)
    except ToolchainError as exc:
        print("error: %s" % exc, file=sys.stderr)
        for problem in exc.problems:
            if problem != str(exc):
                print("  - %s" % problem, file=sys.stderr)
        return 2 if isinstance(exc, UsageError) else 1
    except (OSError, toolchain_sources.SourceError) as exc:  # a full disk, a locked file, a folder that cannot be read: a sentence without paths, never a traceback
        print("error: %s" % (toolchain_io.safe_detail(exc) or type(exc).__name__), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
