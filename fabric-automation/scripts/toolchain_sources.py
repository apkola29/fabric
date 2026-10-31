#!/usr/bin/env python3
"""Sources of the toolchain kit: skill digests, skill lint, git and package resolvers, and vendoring a pinned pack.

A skill folder has one digest, computed the same way from a folder on disk and from git objects. Files are sorted by their
POSIX path. A file that holds no NUL byte is text and has CRLF turned into LF before it is hashed, so a checkout with either
line ending gives the same digest (git itself only ever adds or removes a CR before an LF, and only in files without a NUL).
A symbolic link counts as a file that holds its target, and file modes are ignored. vendor_skills uses the digest to prove
that what it wrote is what the lock says.

resolve_package never raises for a network problem. The git functions raise SourceError("<code>: <detail>"). Neither puts a
URL, a host name, a path or any text of the remote into what it returns or raises: the detail comes from a fixed vocabulary.
Standard library only.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import urllib.parse
from pathlib import Path
from typing import NamedTuple

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from toolchain_io import WINDOWS, SystemRunner, safe_detail  # noqa: E402

MAX_TREE_BYTES = 100 * 1024 * 1024
MAX_TREE_FILES = 5000
MAX_LINT_FILE = 2 * 1024 * 1024
GIT_ENV = {"GIT_TERMINAL_PROMPT": "0"}
LOCAL_TIMEOUT = 120
NETWORK_TIMEOUT = 300
NPM_TIMEOUT = 90
HTTP_TIMEOUT = 20
SKILL_DESCRIPTION_LIMIT = 1024
SKILL_NAME_LIMIT = 64


class SourceError(Exception):
    """The message is "<reason code>: <short detail>". The code is what a lock may store."""

    @property
    def code(self):
        return str(self).split(":", 1)[0].strip()


def _fail(code, detail=""):
    detail = safe_detail(detail)
    return SourceError("%s: %s" % (code, detail) if detail else code)


# ---- digests -------------------------------------------------------------------------------------------------------

def _normalise(data):
    return data if b"\x00" in data else data.replace(b"\r\n", b"\n")


def _hashed(data):
    """(sha256 of the normalised content, its length)."""
    data = _normalise(data)
    return hashlib.sha256(data).digest(), len(data)


def _combine(entries):
    """entries: (relative path, content digest, content length). The digest of a tree is the digest of its sorted entries."""
    outer = hashlib.sha256()
    files = size = 0
    for rel, digest, length in sorted(entries, key=lambda entry: entry[0].encode("utf-8", "surrogateescape")):
        outer.update(rel.encode("utf-8", "surrogateescape") + b"\x00" + digest)
        files += 1
        size += length
    return {"digest": "sha256:" + outer.hexdigest(), "files": files, "bytes": size}


def _walk(directory, prefix="", top=True):
    """(relative POSIX path, full path, is a link) of every file and link below a folder. A top-level .git is skipped."""
    try:
        with os.scandir(directory) as scanner:
            entries = sorted(scanner, key=lambda entry: entry.name)
    except OSError:
        raise _fail("unresolved", "cannot read a folder") from None
    for entry in entries:
        if top and entry.name == ".git":
            continue
        rel = prefix + entry.name
        if entry.is_symlink():
            yield rel, entry.path, True
        elif entry.is_dir(follow_symlinks=False):
            yield from _walk(entry.path, rel + "/", False)
        elif entry.is_file(follow_symlinks=False):
            yield rel, entry.path, False


def _read_entry(path, is_link):
    try:
        if is_link:
            return os.readlink(path).encode("utf-8", "surrogateescape")
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        raise _fail("unresolved", "cannot read a file") from None


def digest_tree(root):
    """The digest of a folder on disk: {"digest": "sha256:<hex>", "files": n, "bytes": n}. `bytes` counts the hashed (normalised) content."""
    root = Path(root)
    if not root.is_dir():
        raise _fail("unresolved", "not a folder")
    return _combine((rel,) + _hashed(_read_entry(path, is_link)) for rel, path, is_link in _walk(str(root)))


# ---- git ----------------------------------------------------------------------------------------------------------

_SHA = re.compile(r"[0-9a-fA-F]{40}")


class _Entry(NamedTuple):
    path: str
    mode: str
    sha: str
    size: int


def _sha(value):
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise _fail("unresolved", "not a 40 character commit id")
    return value.lower()


def _relative(path, what="path"):
    """A POSIX path of safe components without a trailing slash ("" is the root of the repository)."""
    if not isinstance(path, str) or any(ord(char) < 32 or char == "\x7f" for char in path):
        raise _fail("unresolved", "unsafe " + what)
    path = path.rstrip("/")
    parts = path.split("/") if path else []
    if any(part in ("", ".", "..") or "\\" in part for part in parts):
        raise _fail("unresolved", "unsafe " + what)
    return "/".join(parts)


def _check_url(url):
    """Only https and file addresses are used; returns True for a file address. Anything else never reaches git."""
    try:
        parts = urllib.parse.urlsplit(url) if isinstance(url, str) else None
    except ValueError:
        parts = None
    if parts is None or any(char.isspace() or ord(char) < 32 for char in url):
        raise _fail("unresolved", "unsupported repository url")
    if parts.scheme not in ("https", "file") or (parts.scheme == "https" and not parts.hostname):
        raise _fail("unresolved", "unsupported repository url")
    return parts.scheme == "file"


def _network_argv(url, *args):
    """git without any stored credential; the file protocol is allowed only for a file address (tests and local mirrors)."""
    argv = ["git", "-c", "credential.helper="]
    if _check_url(url):
        argv += ["-c", "protocol.file.allow=always"]
    return argv + list(args)


_GIT_FAILURES = (
    (re.compile(r"authentication failed|could not read username|terminal prompts disabled|returned error: 40[13]|http 40[13]|"
                r"access denied|permission denied|\bsso\b|saml", re.I), "network", "authentication required"),
    (re.compile(r"could not resolve host|name or service not known|no such host|temporary failure in name resolution", re.I), "network", "dns"),
    (re.compile(r"timed out|timeout", re.I), "network", "timeout"),
    (re.compile(r"connection refused|failed to connect|unable to connect|couldn.t connect|network is unreachable", re.I), "network", "connect"),
    (re.compile(r"\bssl\b|\btls\b|certificate|schannel", re.I), "network", "tls"),
    (re.compile(r"not our ref|couldn.t find remote ref|unadvertised object|reference is not a tree|bad object|"
                r"invalid object", re.I), "unresolved", "commit not found"),
    (re.compile(r"does not appear to be a git repository|not a git repository|repository not found|repository .* not found|"
                r"returned error: 404|http 404|does not exist|no such file", re.I), "unresolved", "repository not found"),
)


def _git_failure(result):
    """A SourceError for a failed git command, from a fixed vocabulary and never from the text of the remote."""
    if result.returncode == 127:
        return _fail("not-installed", "git")
    if result.returncode == 124:
        return _fail("network", "timeout")
    text = result.stderr or ""
    for pattern, code, detail in _GIT_FAILURES:
        if pattern.search(text):
            return _fail(code, detail)
    return _fail("network", "git exit %d" % result.returncode)


def _run_bytes(runner, argv, *, input=None, timeout=LOCAL_TIMEOUT):
    """Binary-safe run. A stand-in runner without run_bytes gets the real one: reading a local object store needs no network."""
    method = getattr(runner, "run_bytes", None) or SystemRunner().run_bytes
    return method(argv, env=GIT_ENV, timeout=timeout, input=input)


def _has_commit(runner, git_dir, sha):
    result = runner.run(["git", "--git-dir", str(git_dir), "cat-file", "-e", sha + "^{commit}"], env=GIT_ENV, timeout=60)
    return result.returncode == 0


def _tree_entries(runner, git_dir, sha, subpath, limits=True):
    """The files of a tree of a commit, with paths relative to it. A link is a blob (its content is the target)."""
    rev = sha if not subpath else "%s:%s" % (sha, subpath)
    raw = _run_bytes(runner, ["git", "--git-dir", str(git_dir), "ls-tree", "-r", "-l", "-z", rev])
    if raw.returncode == 127:
        raise _fail("not-installed", "git")
    if raw.returncode != 0:
        raise _fail("unresolved", "path not found in the commit")
    entries, total = [], 0
    for item in raw.stdout.split(b"\x00"):
        if not item:
            continue
        meta, tab, name = item.partition(b"\t")
        fields = meta.split()
        if not tab or len(fields) != 4:
            raise _fail("unresolved", "unreadable tree listing")
        mode, kind, sha_hex, size = fields
        if kind == b"commit":
            raise _fail("unresolved", "a submodule inside the tree")
        if kind != b"blob" or not size.isdigit():
            raise _fail("unresolved", "unreadable tree listing")
        try:
            path = name.decode("utf-8")
        except UnicodeDecodeError:
            raise _fail("unresolved", "a path is not UTF-8") from None
        entries.append(_Entry(path, mode.decode("ascii"), sha_hex.decode("ascii"), int(size)))
        total += int(size)
        if limits and (len(entries) > MAX_TREE_FILES or total > MAX_TREE_BYTES):
            raise _fail("unresolved", "tree too large")
    return entries


def _read_blobs(runner, git_dir, shas):
    """{object id: bytes} for these blobs, from one `git cat-file --batch`."""
    unique = list(dict.fromkeys(shas))
    if not unique:
        return {}
    raw = _run_bytes(runner, ["git", "--git-dir", str(git_dir), "cat-file", "--batch"], input=("\n".join(unique) + "\n").encode("ascii"))
    if raw.returncode != 0:
        raise _fail("unresolved", "git could not read the objects")
    data, position, blobs = raw.stdout, 0, {}
    for sha in unique:
        end = data.find(b"\n", position)
        header = data[position:end].split(b" ") if end >= 0 else []
        if len(header) != 3 or header[1] != b"blob" or not header[2].isdigit():
            raise _fail("unresolved", "an object is missing")
        size, start = int(header[2]), end + 1
        content = data[start:start + size]
        if len(content) != size:
            raise _fail("unresolved", "git answered too little")
        blobs[sha] = content
        position = start + size + 1
    return blobs


def digest_git_tree(git_dir, commit, subpath, runner=None):
    """The digest of `subpath` at `commit`, from git objects: the same digest as digest_tree of a checkout with LF or CRLF."""
    runner = runner or SystemRunner()
    sha = _sha(commit)
    sub = _relative(subpath, "path")
    entries = _tree_entries(runner, git_dir, sha, sub)
    blobs = _read_blobs(runner, git_dir, [entry.sha for entry in entries])
    return _combine((entry.path,) + _hashed(blobs[entry.sha]) for entry in entries)


_VERSION = re.compile(r"[vV]?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?")


def _version_key(text):
    """A sort key by semantic version precedence, or None when the text is not a version. A release outranks its pre-releases."""
    match = _VERSION.fullmatch(text) if isinstance(text, str) else None
    if not match:
        return None
    numbers = tuple(int(group) if group is not None else 0 for group in match.groups()[:4])
    pre = match.group(5)
    if pre is None:
        return numbers, 1, ()
    identifiers = pre.split(".")
    if not all(identifiers):
        return None
    return numbers, 0, tuple((0, int(ident), "") if ident.isdigit() else (1, 0, ident) for ident in identifiers)


def _highest(names):
    """The name with the highest version, a release before any pre-release; None when there is none."""
    keyed = [(key, name) for name, key in ((name, _version_key(name)) for name in names) if key is not None]
    releases = [item for item in keyed if item[0][1] == 1]
    pool = releases or keyed
    return max(pool, key=lambda item: item[0])[1] if pool else None


def _ls_remote(url, runner, kind):
    result = runner.run(_network_argv(url, "ls-remote", kind, url), env=GIT_ENV, timeout=NETWORK_TIMEOUT)
    if result.returncode != 0:
        raise _git_failure(result)
    refs = {}
    for line in (result.stdout or "").splitlines():
        sha, tab, ref = line.partition("\t")
        if tab and _SHA.fullmatch(sha):
            refs[ref.strip()] = sha.lower()
    return refs


def resolve_git_ref(url, track, runner=None):
    """Anonymously resolve a track to {"ref", "tag", "commit"}. Raises SourceError("network"/"unresolved": detail)."""
    runner = runner or SystemRunner()
    track = track if isinstance(track, dict) else {}
    kind = track.get("kind")
    if kind == "commit":
        sha = _sha(track.get("sha"))
        return {"ref": sha, "tag": None, "commit": sha}
    if kind == "tag":
        pattern = track.get("pattern")
        if not isinstance(pattern, str) or not pattern.strip() or any(char.isspace() or ord(char) < 32 for char in pattern):
            raise _fail("unresolved", "bad tag pattern")
        refs = _ls_remote(url, runner, "--tags")
        found = {}
        for ref, sha in refs.items():
            if ref.startswith("refs/tags/"):
                name = ref[len("refs/tags/"):]
                peeled = name.endswith("^{}")
                found.setdefault(name[:-3] if peeled else name, {})["peeled" if peeled else "direct"] = sha
        matching = [name for name in found if fnmatch.fnmatchcase(name, pattern)]
        best = _highest(matching)
        if best is None:
            raise _fail("unresolved", "no tag matches the pattern")
        return {"ref": "refs/tags/" + best, "tag": best, "commit": found[best].get("peeled") or found[best]["direct"]}
    if kind == "branch":
        name = track.get("name")
        if not isinstance(name, str) or not name or name.startswith(("-", "/")) or re.search(r"[\s\x00-\x1f\x7f~^:?*\[\\]|\.\.|@\{", name):
            raise _fail("unresolved", "bad branch name")
        refs = _ls_remote(url, runner, "--heads")
        sha = refs.get("refs/heads/" + name)
        if sha is None:
            raise _fail("unresolved", "no such branch")
        return {"ref": "refs/heads/" + name, "tag": None, "commit": sha}
    raise _fail("unresolved", "unknown track kind")


def fetch_git(url, commit, dest, runner=None):
    """Make `dest` a bare git dir that holds exactly that commit, fetched anonymously and shallow. Returns dest."""
    runner = runner or SystemRunner()
    sha = _sha(commit)
    _check_url(url)
    dest = Path(dest)
    if dest.is_dir() and _has_commit(runner, dest, sha):
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    created = runner.run(["git", "init", "--bare", "--quiet", str(dest)], env=GIT_ENV, timeout=60)
    if created.returncode != 0:
        raise _git_failure(created)
    fetched = runner.run(_network_argv(url, "--git-dir", str(dest), "fetch", "--quiet", "--depth", "1", "--no-tags", url, sha),
                         env=GIT_ENV, timeout=NETWORK_TIMEOUT)
    if fetched.returncode != 0:
        raise _git_failure(fetched)
    if not _has_commit(runner, dest, sha):
        raise _fail("unresolved", "the commit did not arrive")
    return dest


# ---- skill lint ---------------------------------------------------------------------------------------------------

_LINE_BREAK = re.compile(r"\r\n|\n|\r")
_KEY = re.compile(r"([A-Za-z0-9_][A-Za-z0-9_.-]*)[ \t]*:(?:[ \t]+(.*))?")
_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_ESCAPES = {"0": "\x00", "a": "\x07", "b": "\x08", "t": "\t", "\t": "\t", "n": "\n", "v": "\x0b", "f": "\x0c", "r": "\r", "e": "\x1b",
            " ": " ", '"': '"', "/": "/", "\\": "\\", "N": "\x85", "_": "\xa0", "L": "\u2028", "P": "\u2029"}
_HEX_WIDTH = {"x": 2, "u": 4, "U": 8}
_HINT_ENDINGS = (".md", ".txt", ".json", ".py", ".ps1", ".sh", ".yml", ".yaml")
_HINT = re.compile(
    r"(?<![\w.-])(?:"
    r"(?:python3?|py)[ \t]+-m[ \t]+pip3?[ \t]+install\b|uv[ \t]+pip[ \t]+install\b|pip3?[ \t]+install\b"
    r"|npm[ \t]+(?:install|i|exec)\b|npx[ \t]+\S|dotnet[ \t]+tool[ \t]+install\b|winget[ \t]+install\b|brew[ \t]+install\b"
    r"|(?:apt|apt-get)[ \t]+install\b|choco[ \t]+install\b|Install-Module\b|az[ \t]+extension[ \t]+add\b)", re.IGNORECASE)


def _fold(lines):
    """Fold the lines of a flow scalar: a line break is a space and each blank line is a line break."""
    out, blanks = "", 0
    for line in lines:
        if not line:
            blanks += 1
            continue
        if out:
            out += "\n" * blanks if blanks else " "
        out += line
        blanks = 0
    return out


def _quoted(rest, block, double):
    """(value, problem) of a quoted scalar that starts in `rest` and may go on in the indented lines after it."""
    text = "\n".join([rest] + block)
    quote = '"' if double else "'"
    out, i = [], 1
    while i < len(text):
        char = text[i]
        if double and char == "\\":
            i += 1
            escape = text[i] if i < len(text) else ""
            if escape == "\n":
                i += 1
                while i < len(text) and text[i] in " \t":
                    i += 1
            elif escape in _ESCAPES:
                out.append(_ESCAPES[escape])
                i += 1
            elif escape in _HEX_WIDTH:
                digits = text[i + 1:i + 1 + _HEX_WIDTH[escape]]
                if len(digits) != _HEX_WIDTH[escape] or not re.fullmatch(r"[0-9a-fA-F]+", digits):
                    return None, "bad escape in a quoted value"
                out.append(chr(int(digits, 16)))
                i += 1 + len(digits)
            else:
                return None, "bad escape in a quoted value"
        elif char == quote:
            if not double and text[i + 1:i + 2] == "'":
                out.append("'")
                i += 2
                continue
            tail = text[i + 1:].split("\n", 1)[0].strip()
            if tail and not tail.startswith("#"):
                return None, "text after the closing quote"
            return "".join(out), None
        elif char == "\n":
            while out and out[-1] in " \t":
                out.pop()
            breaks = 0
            while i < len(text) and text[i] in " \t\n":
                breaks += text[i] == "\n"
                i += 1
            out.append("\n" * (breaks - 1) if breaks > 1 else " ")
        else:
            out.append(char)
            i += 1
    return None, "unterminated quoted value"


def _block(header, lines):
    """(value, problem) of a folded (>) or literal (|) block scalar. Trailing line breaks are not part of the value."""
    match = re.fullmatch(r"([|>])([1-9]?)([+-]?)([1-9]?)[ \t]*(?:#.*)?", header)
    if not match:
        return None, "bad block scalar header"
    explicit = int(match.group(2) or match.group(4) or 0)
    filled = [line for line in lines if line.strip()]
    indent = explicit or (len(filled[0]) - len(filled[0].lstrip(" ")) if filled else 0)
    content = [line[indent:] if line.strip() and line[:indent].strip() == "" else line.strip() for line in lines]
    while content and not content[-1]:
        content.pop()
    if match.group(1) == "|":
        return "\n".join(content), None
    out = ""
    for line in content:
        if not line:
            out += "\n"
        else:
            out += (" " if out and not out.endswith("\n") else "") + line
    return out, None


def _scalar(rest, block):
    """(value, problem) of a top-level key. The value is None when it is not a scalar (a list, a map or a flow collection)."""
    rest = rest.strip()
    if rest[:1] in ("|", ">"):
        return _block(rest, block)
    if rest[:1] == '"':
        return _quoted(rest, block, True)
    if rest[:1] == "'":
        return _quoted(rest, block, False)
    if rest[:1] in ("[", "{", "&", "*", "!"):
        return None, None
    lines = [line.strip() for line in block]
    if rest == "" or rest.startswith("#"):
        content = [line for line in lines if line and not line.startswith("#")]
        if not content:
            return "", None
        if content[0].startswith("- ") or content[0] == "-" or _KEY.fullmatch(content[0]):
            return None, None
        return _fold(lines), None
    first = re.split(r"\s#", rest, maxsplit=1)[0].rstrip()
    return _fold([first] + lines), None


def _frontmatter(text):
    """({key: scalar or None}, problems) of the frontmatter of a SKILL.md, or (None, problems) when there is none."""
    lines = _LINE_BREAK.split(text.removeprefix("\ufeff"))
    if lines[0].rstrip() != "---":
        return None, ["no frontmatter"]
    end = next((index for index in range(1, len(lines)) if lines[index].rstrip() in ("---", "...")), None)
    if end is None:
        return None, ["frontmatter is not closed"]
    body, fields, problems, i = lines[1:end], {}, [], 0
    while i < len(body):
        line = body[i]
        if not line.strip() or line.lstrip().startswith("#") and not line[:1].isspace():
            i += 1
            continue
        match = None if line[:1].isspace() else _KEY.fullmatch(line.rstrip())
        if match is None:
            problems.append("frontmatter line %d is not key: value" % (i + 2))
            i += 1
            continue
        j = i + 1
        while j < len(body) and (not body[j].strip() or body[j][:1] in (" ", "\t") or body[j].startswith("- ") or body[j].rstrip() == "-"):
            j += 1
        value, problem = _scalar(match.group(2) or "", body[i + 1:j])
        if problem:
            problems.append("frontmatter line %d: %s" % (i + 2, problem))
        if match.group(1) in fields:
            problems.append("frontmatter line %d: duplicate key" % (i + 2))
        fields.setdefault(match.group(1), value)
        i = j
    return fields, problems


def _count_hints(files):
    total = 0
    for rel, data in files.items():
        if rel.lower().endswith(_HINT_ENDINGS) and len(data) <= MAX_LINT_FILE:
            total += len(_HINT.findall(data.decode("utf-8", "replace")))
    return total


def _lint_files(files, dirname):
    """The lint of a skill given as {relative path: bytes}. `dirname` is the name of its folder."""
    result = {"name": None, "name_ok": False, "description_chars": 0, "frontmatter_ok": False, "install_hints": _count_hints(files), "findings": []}
    findings = result["findings"]
    raw = files.get("SKILL.md")
    if raw is None:
        findings.append("no SKILL.md")
        return result
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", "replace")
        findings.append("SKILL.md is not valid UTF-8")
    fields, problems = _frontmatter(text)
    findings.extend(problems)
    if fields is None:
        return result
    result["frontmatter_ok"] = not problems
    name, description = fields.get("name"), fields.get("description")
    if not isinstance(name, str) or not name.strip():
        findings.append("missing name")
    else:
        name = name.strip()
        result["name"] = name
        ok = True
        if len(name) > SKILL_NAME_LIMIT:
            findings.append("name longer than 64 characters")
            ok = False
        if not _NAME.fullmatch(name):
            findings.append("name must use lower-case letters, digits and hyphens")
            ok = False
        if name != dirname:
            findings.append("name does not match folder")
            ok = False
        result["name_ok"] = ok
    if not isinstance(description, str) or not description.strip():
        findings.append("missing description")
    else:
        result["description_chars"] = len(description.strip())
        if result["description_chars"] > SKILL_DESCRIPTION_LIMIT:
            findings.append("description longer than 1024 characters")
    return result


def lint_skill(root):
    """Lint a skill folder on disk: {"name", "name_ok", "description_chars", "frontmatter_ok", "install_hints", "findings"}."""
    root = Path(root)
    files = {}
    if root.is_dir():
        for rel, path, is_link in _walk(str(root)):
            if is_link or not (rel == "SKILL.md" or rel.lower().endswith(_HINT_ENDINGS)):
                continue
            if rel != "SKILL.md" and os.path.getsize(path) > MAX_LINT_FILE:
                continue
            files[rel] = _read_entry(path, False)
    return _lint_files(files, root.resolve().name if root.name in ("", ".") else root.name)


# ---- plugins -----------------------------------------------------------------------------------------------------

_PLUGIN_MANIFESTS = (".claude-plugin/plugin.json", "plugin.json", ".github/plugin/plugin.json")
_PLAIN_VERSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+_~-]{0,63}")
_SERVER_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,63}")


def _json_of(data):
    try:
        return json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def read_plugin(git_dir, commit, plugin_path, runner=None):
    """The skills, agents and bundled MCP server names of one plugin at a commit, read from git objects."""
    runner = runner or SystemRunner()
    sha = _sha(commit)
    base = _relative(plugin_path, "plugin path")
    if not base:
        raise _fail("unresolved", "unsafe plugin path")
    listing = _tree_entries(runner, git_dir, sha, base, limits=False)
    grouped, wanted = {}, {}
    for entry in listing:
        parts = entry.path.split("/")
        if parts[0] == "skills" and len(parts) >= 3:
            grouped.setdefault(parts[1], []).append(entry._replace(path="/".join(parts[2:])))
        elif entry.path in _PLUGIN_MANIFESTS or entry.path == ".mcp.json":
            wanted[entry.path] = entry
    extra = _read_blobs(runner, git_dir, [entry.sha for entry in wanted.values()])
    version = None
    for candidate in _PLUGIN_MANIFESTS:
        if candidate in wanted:
            document = _json_of(extra[wanted[candidate].sha])
            value = document.get("version") if isinstance(document, dict) else None
            version = value if isinstance(value, str) and _PLAIN_VERSION.fullmatch(value) else None
            break
    names = []
    if ".mcp.json" in wanted:
        document = _json_of(extra[wanted[".mcp.json"].sha])
        servers = (document.get("mcpServers") or document.get("servers")) if isinstance(document, dict) else None
        names = sorted(name if _SERVER_NAME.fullmatch(name) else safe_detail(name, 64) for name in servers if isinstance(name, str)) if isinstance(servers, dict) else []
    agents = sorted(entry.path[len("agents/"):] for entry in listing
                    if entry.path.startswith("agents/") and entry.path.count("/") == 1 and entry.path.endswith(".md"))
    skills = {}
    for name in sorted(grouped):
        entries = grouped[name]
        if not any(entry.path == "SKILL.md" for entry in entries):
            continue
        if len(entries) > MAX_TREE_FILES or sum(entry.size for entry in entries) > MAX_TREE_BYTES:
            raise _fail("unresolved", "skill too large")
        blobs = _read_blobs(runner, git_dir, [entry.sha for entry in entries])
        contents = {entry.path: blobs[entry.sha] for entry in entries}
        tree = _combine((rel,) + _hashed(data) for rel, data in contents.items())
        lint = _lint_files({rel: data for rel, data in contents.items() if rel == "SKILL.md" or rel.lower().endswith(_HINT_ENDINGS)}, name)
        skills[name] = {"path": "%s/skills/%s" % (base, name), "digest": tree["digest"], "files": tree["files"], "bytes": tree["bytes"],
                        "description_chars": lint["description_chars"], "install_hints": lint["install_hints"], "findings": lint["findings"]}
    return {"version": version, "skills": skills, "agents": agents, "bundled_mcp": names}


# ---- packages ----------------------------------------------------------------------------------------------------

_NAMES = {
    "npm": re.compile(r"(?:@[A-Za-z0-9][A-Za-z0-9._~-]*/)?[A-Za-z0-9][A-Za-z0-9._~-]*"),
    "pypi": re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"),
    "nuget": re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*"),
}
_EXACT = re.compile(r"[0-9][0-9A-Za-z.+!_~-]{0,63}")
_INTEGRITY = re.compile(r"sha(?:256|384|512)-[A-Za-z0-9+/]+={0,2}")
_HEX64 = re.compile(r"[0-9a-fA-F]{64}")
_NPM_CODE = re.compile(r"npm (?:error|ERR!) code ([A-Z][A-Z0-9_]+)")
ACCEPT_NPM = "application/vnd.npm.install-v1+json; q=1.0, application/json; q=0.8, */*; q=0.1"


def _unresolved(reason, detail):
    return {"status": "unresolved", "reason": reason, "detail": safe_detail(detail)}


def _stage_failure(label, status, error):
    """(label, kind) of an HTTP answer that did not give a usable document: kinds are notfound and network."""
    if error or status == 0:
        return "%s %s" % (label, safe_detail(error or "failed", 20)), "network"
    if status in (404, 410):
        return label + " not found", "notfound"
    return "%s http %d" % (label, status), "network"


def _get(runner, url, label, headers=None):
    """(parsed JSON object, None) or (None, (label, kind)). The label never holds the URL or text of the answer."""
    try:
        answer = runner.http("GET", url, headers=headers, timeout=HTTP_TIMEOUT)
        status, error, body = int(answer.status), answer.error, answer.body
    except Exception:  # a runner never raises, but a stand-in might
        return None, (label + " failed", "network")
    if status != 200 or error:
        return None, _stage_failure(label, status, error)
    document = _json_of(body if isinstance(body, bytes) else b"")
    if not isinstance(document, dict):
        return None, (label + " bad answer", "bad")
    return document, None


def _npm_failure(code):
    if code in ("E404", "E410", "ETARGET"):
        return "npm not found", "notfound"
    if code in ("E401", "E403"):
        return "npm auth", "network"
    if code and (code.startswith(("ENOTFOUND", "EAI_")) or code in ("ETIMEDOUT", "ECONNRESET", "ECONNREFUSED", "ESOCKETTIMEDOUT", "EHOSTUNREACH")):
        return "npm network", "network"
    if code and ("CERT" in code or code.startswith(("UNABLE_TO", "SELF_SIGNED", "DEPTH_ZERO"))):
        return "npm tls", "network"
    return "npm failed", "fail"


def _npm_candidates(payload):
    """(version, integrity or None, valid) from the JSON of `npm view`: an object, an array of objects or a bare string."""
    items = payload if isinstance(payload, list) else [payload]
    found = []
    for item in items:
        if isinstance(item, str):
            version, integrity, present = item, None, False
        elif isinstance(item, dict):
            version = item.get("version")
            dist = item.get("dist") if isinstance(item.get("dist"), dict) else {}
            present = "dist.integrity" in item or "integrity" in dist
            integrity = item.get("dist.integrity", dist.get("integrity"))
        else:
            continue
        if not isinstance(version, str) or not _EXACT.fullmatch(version) or _version_key(version) is None:
            continue
        if present and not (isinstance(integrity, str) and _INTEGRITY.fullmatch(integrity)):
            continue
        found.append((version, integrity if present else None))
    return found


def _npm_cli(runner, name, pin):
    spec = name if pin is None else name + "@" + pin
    try:
        result = runner.run(["npm", "view", spec, "version", "dist.integrity", "--json"], timeout=NPM_TIMEOUT)
        returncode, stdout, stderr = int(result.returncode), result.stdout or "", result.stderr or ""
    except Exception:  # a runner never raises, but a stand-in might
        return None, ("npm failed", "fail")
    if returncode == 127:
        return None, ("npm missing", "skip")
    if returncode == 124:
        return None, ("npm timeout", "network")
    try:
        payload = json.loads(stdout)
    except ValueError:
        payload = None
    if returncode != 0:
        code = None
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict) and isinstance(payload["error"].get("code"), str):
            code = payload["error"]["code"] if re.fullmatch(r"[A-Z][A-Z0-9_]{1,40}", payload["error"]["code"]) else None
        if code is None:
            match = _NPM_CODE.search(stderr) or _NPM_CODE.search(stdout)
            code = match.group(1) if match else None
        return None, _npm_failure(code)
    candidates = [item for item in _npm_candidates(payload) if pin is None or item[0] == pin]
    releases = [item for item in candidates if _version_key(item[0])[1] == 1]
    best = max(releases or candidates, key=lambda item: _version_key(item[0])) if candidates else None
    if best is None:
        return None, ("npm bad answer", "bad")
    return {"status": "resolved", "version": best[0], "integrity": best[1], "via": "npm-cli"}, None


def _npm_registry(runner, name, pin):
    document, failure = _get(runner, "https://registry.npmjs.org/" + urllib.parse.quote(name, safe="@"), "registry", {"Accept": ACCEPT_NPM})
    if failure:
        return None, failure
    tags = document.get("dist-tags") if isinstance(document.get("dist-tags"), dict) else {}
    versions = document.get("versions") if isinstance(document.get("versions"), dict) else {}
    version = pin or tags.get("latest")
    if not isinstance(version, str) or not _EXACT.fullmatch(version):
        return None, ("registry bad answer", "bad")
    if version not in versions:
        return None, ("registry not found", "notfound") if pin else ("registry bad answer", "bad")
    dist = versions[version].get("dist") if isinstance(versions[version], dict) else None
    integrity = dist.get("integrity") if isinstance(dist, dict) else None
    if integrity is not None and not (isinstance(integrity, str) and _INTEGRITY.fullmatch(integrity)):
        return None, ("registry bad answer", "bad")
    return {"status": "resolved", "version": version, "integrity": integrity, "via": "npm-registry"}, None


def _npm_jsdelivr(runner, name, pin):
    document, failure = _get(runner, "https://data.jsdelivr.com/v1/packages/npm/" + urllib.parse.quote(name, safe="@/"), "jsdelivr")
    if failure:
        return None, failure
    listed = document.get("versions") if isinstance(document.get("versions"), list) else []
    versions = [item.get("version") if isinstance(item, dict) else item for item in listed]
    versions = [version for version in versions if isinstance(version, str) and _EXACT.fullmatch(version)]
    if pin:
        if pin not in versions:
            return None, ("jsdelivr not found", "notfound")
        version = pin
    else:
        tags = document.get("tags") if isinstance(document.get("tags"), dict) else {}
        latest = tags.get("latest")
        version = latest if isinstance(latest, str) and _EXACT.fullmatch(latest) else _highest(versions)
    if version is None:
        return None, ("jsdelivr bad answer", "bad")
    return {"status": "resolved", "version": version, "integrity": None, "via": "jsdelivr"}, None


def _resolve_npm(runner, name, pin):
    stages = []
    for stage in (_npm_cli, _npm_registry, _npm_jsdelivr):
        result, failure = stage(runner, name, pin)
        if result is not None:
            return result
        stages.append(failure)
    kinds = {kind for _, kind in stages}
    reason = "network" if kinds & {"network", "fail"} else "unresolved"
    return _unresolved(reason, " - ".join(label for label, _ in stages))


def _resolve_pypi(runner, name, pin):
    quoted = urllib.parse.quote(name, safe="")
    url = "https://pypi.org/pypi/%s/json" % quoted if pin is None else "https://pypi.org/pypi/%s/%s/json" % (quoted, urllib.parse.quote(pin, safe=""))
    document, failure = _get(runner, url, "pypi")
    if failure:
        label, kind = failure
        return _unresolved("network" if kind == "network" else "unresolved", "not found" if kind == "notfound" else label.replace("pypi ", "", 1))
    info = document.get("info") if isinstance(document.get("info"), dict) else {}
    version = info.get("version")
    if not isinstance(version, str) or not _EXACT.fullmatch(version) or (pin is not None and version != pin):
        return _unresolved("unresolved", "bad answer")
    # Chosen by file name, so that the hash does not depend on the order in which PyPI happens to list the files.
    files = [item for item in (document.get("urls") if isinstance(document.get("urls"), list) else [])
             if isinstance(item, dict) and item.get("packagetype") in ("sdist", "bdist_wheel")]
    digest = None
    for item in sorted(files, key=lambda item: str(item.get("filename") or "")):
        digests = item.get("digests") if isinstance(item.get("digests"), dict) else {}
        if isinstance(digests.get("sha256"), str) and _HEX64.fullmatch(digests["sha256"]):
            digest = digests["sha256"].lower()
            break
    return {"status": "resolved", "version": version, "sha256": digest, "via": "pypi"}


def _resolve_nuget(runner, name, pin):
    url = "https://api.nuget.org/v3-flatcontainer/%s/index.json" % urllib.parse.quote(name.lower(), safe="")
    document, failure = _get(runner, url, "nuget")
    if failure:
        label, kind = failure
        return _unresolved("network" if kind == "network" else "unresolved", "not found" if kind == "notfound" else label.replace("nuget ", "", 1))
    keyed = [(_version_key(text), text) for text in (document.get("versions") if isinstance(document.get("versions"), list) else [])
             if isinstance(text, str) and _EXACT.fullmatch(text)]
    keyed = [(key, text) for key, text in keyed if key is not None]
    if not keyed:
        return _unresolved("unresolved", "no usable version")
    if pin is not None:
        wanted = _version_key(pin)
        match = [text for key, text in keyed if key == wanted]
        if not match:
            return _unresolved("unresolved", "version not found")
        return {"status": "resolved", "version": match[0], "integrity": None, "via": "nuget"}
    releases = [item for item in keyed if item[0][1] == 1]
    best = max(releases or keyed, key=lambda item: item[0])
    return {"status": "resolved", "version": best[1], "integrity": None, "via": "nuget"}


_RESOLVERS = {"npm": _resolve_npm, "pypi": _resolve_pypi, "nuget": _resolve_nuget}


def resolve_package(ecosystem, name, track, runner=None):
    """Resolve a package to {"status": "resolved", "version", "integrity" or "sha256", "via"} or {"status": "unresolved", "reason", "detail"}.

    track is "latest" or an exact version. A network problem is an unresolved answer, never an exception."""
    if ecosystem not in _RESOLVERS:
        return _unresolved("unresolved", "unknown ecosystem")
    if not isinstance(name, str) or len(name) > 214 or not _NAMES[ecosystem].fullmatch(name):
        return _unresolved("unresolved", "bad package name")
    if track == "latest":
        pin = None
    elif isinstance(track, str) and _EXACT.fullmatch(track):
        pin = track
    else:
        return _unresolved("unresolved", "track must be latest or an exact version")
    return _RESOLVERS[ecosystem](runner or SystemRunner(), name, pin)


# ---- vendoring ---------------------------------------------------------------------------------------------------

_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_RESERVED = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", re.IGNORECASE)
_BAD_PART = re.compile(r'[\\:*?"<>|\x00-\x1f]')


def _is_link(path):
    if os.path.islink(path):
        return True
    if WINDOWS:
        try:
            return getattr(os.lstat(path), "st_reparse_tag", 0) == getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", -1)
        except OSError:
            return False
    return False


def _rmtree(path):
    def retry(function, target, _info):
        os.chmod(target, stat.S_IWRITE)
        function(target)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=retry)


def _remove(path):
    if not os.path.lexists(path):
        return
    if _is_link(path):
        try:
            os.unlink(path)
        except OSError:
            os.rmdir(path)
    elif os.path.isdir(path):
        _rmtree(path)
    else:
        os.chmod(path, stat.S_IWRITE)
        os.unlink(path)


def _safe_skill_name(name):
    return isinstance(name, str) and _SAFE_NAME.fullmatch(name) is not None and name == name.rstrip(". ") and not _RESERVED.fullmatch(name)


def _file_parts(rel):
    parts = rel.split("/")
    for part in parts:
        if (not part or part in (".", "..") or part.lower() == ".git" or _BAD_PART.search(part) or part != part.rstrip(". ")
                or _RESERVED.fullmatch(part)):
            raise _fail("unresolved", "unsafe path in a skill")
    return parts


def _quarantined(quarantine, source, skill):
    for item in quarantine or ():
        if isinstance(item, str):
            where, name = None, item
        elif isinstance(item, dict):
            where, name = item.get("source"), item.get("skill", item.get("name"))
        elif isinstance(item, (tuple, list)) and len(item) in (2, 3):
            where, name = item[0], item[-1]
        else:
            continue
        if name == skill and (where is None or where == source):
            return True
    return False


def _pick(lock, selection, quarantine):
    sources = lock.get("skill_sources") if isinstance(lock, dict) else None
    if not isinstance(sources, dict):
        raise _fail("unresolved", "the lock has no skill sources")
    picked = {}
    for item in selection:
        try:
            source_id, plugin_name, skill = item
        except (TypeError, ValueError):
            raise _fail("unresolved", "bad selection") from None
        if not all(isinstance(part, str) for part in (source_id, plugin_name, skill)):
            raise _fail("unresolved", "bad selection")
        if _quarantined(quarantine, source_id, skill):
            raise _fail("quarantined", skill)
        source = sources.get(source_id)
        plugin = (source.get("plugins") or {}).get(plugin_name) if isinstance(source, dict) else None
        entry = (plugin.get("skills") or {}).get(skill) if isinstance(plugin, dict) else None
        if not isinstance(entry, dict):
            raise _fail("unresolved", "skill is not in the lock: " + skill)
        if not _safe_skill_name(skill):
            raise _fail("unresolved", "unsafe skill name")
        path, digest = entry.get("path"), entry.get("digest")
        if not isinstance(path, str) or not _relative(path, "skill path") or not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise _fail("unresolved", "the lock entry of %s is not usable" % skill)
        commit = _sha(source.get("commit"))
        if skill in picked:
            if picked[skill]["digest"] != digest:
                raise _fail("conflict", skill)
            continue
        picked[skill] = {"name": skill, "source": source_id, "plugin": plugin_name, "commit": commit, "repo": source.get("repo"),
                         "path": _relative(path, "skill path"), "digest": digest}
    return picked


def _stage(runner, cache, info, destination):
    entries = _tree_entries(runner, cache, info["commit"], info["path"])
    blobs = _read_blobs(runner, cache, [entry.sha for entry in entries])
    for entry in entries:
        target = destination.joinpath(*_file_parts(entry.path))
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(_normalise(blobs[entry.sha]))
        except OSError:
            raise _fail("unresolved", "cannot write a file") from None
    measured = digest_tree(destination)
    if measured["digest"] != info["digest"]:
        raise _fail("digest mismatch", info["name"])
    return measured


def vendor_skills(lock, selection, store, runner=None, quarantine=()):
    """Write the selected skills of a lock into `store`/skills from the locked commits and verify every one against the lock.

    All or nothing: the skills are staged and checked first, and only then does the store change. Returns the MANIFEST dict."""
    runner = runner or SystemRunner()
    store = Path(store)
    picked = _pick(lock, selection, quarantine)
    skills_dir = store / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    measured, missing = {}, []
    for name, info in picked.items():
        target = skills_dir / name
        if target.is_dir() and not _is_link(target):
            current = digest_tree(target)
            if current["digest"] == info["digest"]:
                measured[name] = current
                continue
        missing.append(name)
    staging = store / (".staging-%d" % os.getpid())
    if missing:
        try:
            _remove(staging)
            staging.mkdir(parents=True)
            fetched = {}
            for name in missing:
                info = picked[name]
                if info["commit"] not in fetched:
                    fetched[info["commit"]] = fetch_git(info["repo"], info["commit"], store / ".cache" / info["commit"][:12], runner)
                measured[name] = _stage(runner, fetched[info["commit"]], info, staging / name)
            for name in missing:
                _remove(skills_dir / name)
                os.replace(staging / name, skills_dir / name)
        finally:
            _remove(staging)
    for child in list(skills_dir.iterdir()):
        if child.name not in picked and (child.is_dir() or _is_link(child)):
            _remove(child)
    manifest = {"schema": 1, "lock_inputs_digest": lock.get("inputs_digest"), "skills": {
        name: {"source": picked[name]["source"], "plugin": picked[name]["plugin"], "commit": picked[name]["commit"],
               "digest": picked[name]["digest"], "files": measured[name]["files"], "bytes": measured[name]["bytes"]}
        for name in sorted(picked)}}
    temporary = store / "MANIFEST.json.tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    os.replace(temporary, store / "MANIFEST.json")
    return manifest
