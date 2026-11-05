#!/usr/bin/env python3
"""The catalog of the MCP servers that the instruction layer names, and the text that is generated from it.

toolchain/catalog.json is read by a person from the pages of Microsoft Learn (and the READMEs they point to). It records, for each server,
where it runs, its release stage, what it needs, the pages it was read from with their dates, its tools by kind, the tools that give
knowledge, and the tools that no agent calls (the flagged ones). The stdio servers that the lock measured take their tool lists from the lock.

`python scripts/toolchain.py instructions` checks, and with --write rewrites, what is generated from it: the blocks of AGENTS.md that sit between
BEGIN GENERATED and END GENERATED comments, and the reference toolchain/skills/factory-router/references/mcp-servers.md. A fact that a person
checked is thereby written once, and the text that every session reads cannot drift from it.

Standard library only.
"""

from __future__ import annotations

import json
import re

SCHEMA = 1
GROUPS = ("pinned", "listed", "also", "related")
HOSTINGS = ("remote", "local", "customer")
STATUSES = ("ga", "public-preview", "preview", "beta", "unverified")  # the vocabulary of the manifest
KINDS = ("read", "write", "destructive", "mixed")  # mixed: one tool that reads and also writes or deletes; the operation or the statement that a call names decides which
SOURCES = ("lock", "page", "none")
ENDPOINTS = ("one URL", "one URL per item", "one URL, or one URL per item", "two URLs per item", "command", "extension", "local URL", "customer")
AREAS = ("permissions", "row-level or object-level security", "security settings", "capacity, tenant or workspace settings", "connections", "schedules",
         "sensitivity labels", "credentials", "license")
AREA_LABELS = {"permissions": "permissions (tier T3)", "row-level or object-level security": "row-level or object-level security (tier T3)",
               "security settings": "security settings (tier T3)", "capacity, tenant or workspace settings": "capacity, tenant or workspace settings (tier T3)",
               "connections": "connections (tier T3)", "schedules": "schedules (tier T3)", "sensitivity labels": "sensitivity labels (tier T3)",
               "credentials": "credentials (rule 2)", "license": "license (never accepted for anyone)"}
SIGN_IN_WORDS = {"none": "none", "azure-identity": "Azure identity", "entra-delegated": "Entra"}
STAGE_WORDS = {"ga": "generally available", "public-preview": "public preview", "preview": "preview", "beta": "beta",
               "unverified": "not stated on the pages that were read"}
REGIONS = ("pinned", "others", "flagged", "knowledge", "skills")
REFERENCE_PATH = ("skills", "factory-router", "references", "mcp-servers.md")
WHERE = {"command": "local, started by a command", "extension": "local, inside an extension of VS Code", "local URL": "local, started by a command and reached at a local address",
         "customer": "hosted by the customer"}
LOCK_KIND_WORDS = {"read": "annotated read-only", "write": "annotated neither read-only nor destructive", "destructive": "annotated destructive"}
READ_ONLY_SWITCHES = ("--read-only", "--readonly")
# A name that says it touches one of these (for a tool that is not read-only), or that it returns a secret (for every kind), has to be flagged by name, or named by a statement of `changes`, under an area
# that its words belong to. A word that no area owns (`modify`) says only that the tool changes something, and any area will do.
AREA_WORDS = {
    "permissions": "role roles permission permissions grant revoke share invite assign acl",
    "row-level or object-level security": "role roles rls ols acl security",
    "security settings": "security policy policies immutability retention firewall nsg",
    "capacity, tenant or workspace settings": "capacity tenant settings setting tier domain domains diagnostics immutability retention policy quota quotas",
    "connections": "connection connections gateway",
    "schedules": "schedule schedules trigger triggers continuous",
    "sensitivity labels": "label labels",
    "credentials": "token secret secrets password credential credentials sas key keys certificate certificates keyvault authenticate sign",
    "license": "license eula",
}
GENERIC_WORDS = frozenset(["modify"])
WORD_AREAS = {}
for _area, _words in AREA_WORDS.items():
    for _word in _words.split():
        WORD_AREAS.setdefault(_word, set()).add(_area)
PROTECTED_WORDS = frozenset(WORD_AREAS) | GENERIC_WORDS
SECRET_WORDS = frozenset("token secret secrets password credential credentials sas keyvault key keys certificate certificates".split())
# (server, tool) pairs that are reviewed and left out of that check, each with the reason: a name that says more than the tool does.
PROTECTED_REVIEWED = {
    ("fabric-rti-local", "activator_create_trigger"):
        "it creates an Activator trigger with an e-mail or Teams alert, which is no schedule, permission, connection or setting; the server annotates it as destructive, so rule 6 asks for approval, and no job loads the server",
}

ID_RE = re.compile(r"[a-z][a-z0-9-]*")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
URL_RE = re.compile(r"https://[^\s|`<>\"]+")
TOOL_RE = re.compile(r"[A-Za-z][A-Za-z0-9_. -]*")
CONTRACT_RE = re.compile(r"[a-z][a-z0-9-]*/[a-z][a-z0-9-]*")
LEARN_PREFIX = "https://learn.microsoft.com/en-us/"
REGION_RE = re.compile(r"<!-- BEGIN GENERATED (?P<name>[a-z]+) -->\n(?P<body>.*?)<!-- END GENERATED (?P=name) -->", re.S)
SKILLS_TAG_RE = re.compile(r"https://github\.com/microsoft/skills-for-fabric/blob/(v[0-9][0-9.]*)/")


class CatalogError(Exception):
    """The catalog, or what is generated from it, is not as it has to be. `problems` holds every reason."""

    def __init__(self, message, problems=None):
        super().__init__(message)
        self.problems = list(problems) if problems else [message]


# ---------------------------------------------------------------- the file

def parse(text, label="catalog.json"):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("duplicate key '%s'" % key)
            out[key] = value
        return out

    try:
        return json.loads(text, object_pairs_hook=unique)
    except ValueError as exc:
        raise CatalogError("%s: not valid JSON (%s)" % (label, str(exc)[:120]))


def _scalar(value):
    return json.dumps(value, ensure_ascii=False)


def _inline(value):
    if isinstance(value, dict):
        return "{" + ", ".join("%s: %s" % (_scalar(k), _inline(v)) for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_inline(v) for v in value) + "]"
    return _scalar(value)


def _fits(value, room):
    if isinstance(value, dict):
        return all(not isinstance(v, dict) and (not isinstance(v, list) or all(not isinstance(i, (dict, list)) for i in v)) for v in value.values()) \
            and len(_inline(value)) <= room
    return len(_inline(value)) <= room


def _dump(value, level):
    pad, inner = "  " * level, "  " * (level + 1)
    if isinstance(value, dict):
        if not value:
            return "{}"
        if level > 0 and _fits(value, 118 - len(pad)):
            return _inline(value)
        return "{\n" + ",\n".join("%s%s: %s" % (inner, _scalar(k), _dump(v, level + 1)) for k, v in value.items()) + "\n" + pad + "}"
    if isinstance(value, list):
        if not value:
            return "[]"
        if _fits(value, 118 - len(pad)):
            return _inline(value)
        if all(not isinstance(v, (dict, list)) for v in value):
            lines, line = [], ""
            for item in value:
                piece = _scalar(item) + ","
                if line and len(inner) + len(line) + 1 + len(piece) > 118:
                    lines.append(inner + line)
                    line = piece
                else:
                    line = (line + " " + piece) if line else piece
            lines.append(inner + line.rstrip(","))
            return "[\n" + "\n".join(lines) + "\n" + pad + "]"
        return "[\n" + ",\n".join(inner + _dump(v, level + 1) for v in value) + "\n" + pad + "]"
    return _scalar(value)


def dump(catalog):
    """The canonical text of a catalog: indented, with a list of names filled across lines, so that a change is a small diff."""
    return _dump(catalog, 0) + "\n"


# ---------------------------------------------------------------- structure

def _keys(value, where, problems, required=(), optional=()):
    if not isinstance(value, dict):
        problems.append("%s: must be an object" % where)
        return False
    for key in required:
        if key not in value:
            problems.append("%s: missing key '%s'" % (where, key))
    for key in value:
        if key not in required and key not in optional:
            problems.append("%s: unknown key '%s'" % (where, key))
    return True


def _text(value, where, problems, limit=420):
    if not isinstance(value, str) or not value.strip():
        problems.append("%s: must be a non-empty text" % where)
    elif "|" in value or "\n" in value or len(value) > limit or value != value.strip():
        problems.append("%s: one line of at most %d characters, trimmed, with no vertical bar" % (where, limit))


def _strings(value, where, problems, pattern=None, allow_empty=False):
    if not isinstance(value, list) or (not value and not allow_empty):
        problems.append("%s: must be a%s list" % (where, "" if allow_empty else " non-empty"))
        return []
    for item in value:
        if not isinstance(item, str) or (pattern is not None and not pattern.fullmatch(item)):
            problems.append("%s: '%s' is not an acceptable name" % (where, str(item)[:40]))
    if len(set(value)) != len(value):
        problems.append("%s: a name is listed twice" % where)
    return [i for i in value if isinstance(i, str)]


def _strings_of_text(value, where, problems):
    """A non-empty list of lines of text (each one line, no vertical bar)."""
    if not isinstance(value, list) or not value:
        problems.append("%s: must be a non-empty list" % where)
        return []
    for n, item in enumerate(value):
        _text(item, "%s[%d]" % (where, n), problems)
    return [i for i in value if isinstance(i, str)]


def _pages(value, where, problems):
    if not isinstance(value, list) or not value:
        problems.append("%s: must be a non-empty list" % where)
        return
    seen = set()
    for index, page in enumerate(value):
        here = "%s[%d]" % (where, index)
        if not _keys(page, here, problems, ("url",), ("updated",)):
            continue
        url = page.get("url")
        if not isinstance(url, str) or not URL_RE.fullmatch(url):
            problems.append("%s.url: must be an https address" % here)
            continue
        if url in seen:
            problems.append("%s: the page is listed twice" % here)
        seen.add(url)
        updated = page.get("updated")
        if url.startswith("https://learn.microsoft.com/"):
            if not (isinstance(updated, str) and DATE_RE.fullmatch(updated)):
                problems.append("%s.updated: a Learn page has the date of its updated_at, as YYYY-MM-DD" % here)
        elif "updated" in page:
            problems.append("%s.updated: only a Learn page has a date" % here)


def _tools(value, where, problems):
    """The tool names of a `tools` entry that this catalog lists itself (a lock-sourced entry lists none)."""
    names = []
    if not _keys(value, where, problems, ("from",), ("groups", "contract", "kinds", "note")):
        return names
    source = value.get("from")
    if source not in SOURCES:
        problems.append("%s.from: one of %s" % (where, ", ".join(SOURCES)))
        return names
    allowed = {"lock": ("contract", "kinds"), "page": ("groups",), "none": ("note",)}[source]
    for key in ("groups", "contract", "kinds", "note"):
        if key in value and key not in allowed:
            problems.append("%s: '%s' does not go with from=%s" % (where, key, source))
    if source == "lock":
        contract = value.get("contract")
        if not isinstance(contract, str) or not CONTRACT_RE.fullmatch(contract):
            problems.append("%s.contract: a lock key such as fabric-local/full" % where)
        if "kinds" in value and value["kinds"] != "variant":
            problems.append("%s.kinds: only 'variant' is known" % where)
    elif source == "none":
        _text(value.get("note"), where + ".note", problems, 700)
    else:
        groups = value.get("groups")
        if not isinstance(groups, list) or not groups:
            problems.append("%s.groups: must be a non-empty list" % where)
            return names
        for index, group in enumerate(groups):
            here = "%s.groups[%d]" % (where, index)
            if not _keys(group, here, problems, ("kind", "names"), ("set",)):
                continue
            if group.get("kind") not in KINDS:
                problems.append("%s.kind: one of %s" % (here, ", ".join(KINDS)))
            if "set" in group:
                _text(group["set"], here + ".set", problems, 80)
            names += _strings(group.get("names"), here + ".names", problems, TOOL_RE)
        if len(set(names)) != len(names):
            problems.append("%s: a tool is listed in two groups" % where)
    return names


def check_structure(catalog):
    """The problems of the shape of a parsed catalog, each as a sentence; none when it is well formed."""
    problems = []
    if not _keys(catalog, "catalog", problems, ("schema", "read", "directory", "skills", "servers")):
        return problems
    if catalog.get("schema") != SCHEMA:
        problems.append("schema: must be %d" % SCHEMA)
    if not (isinstance(catalog.get("read"), str) and DATE_RE.fullmatch(catalog["read"])):
        problems.append("read: the date on which a person read the pages, as YYYY-MM-DD")
    directory = catalog.get("directory")
    if _keys(directory, "directory", problems, ("pages", "servers", "remote", "local")):
        _pages(directory.get("pages"), "directory.pages", problems)
        for index, page in enumerate(directory.get("pages") if isinstance(directory.get("pages"), list) else []):
            if isinstance(page, dict) and isinstance(page.get("url"), str) and not page["url"].startswith("https://learn.microsoft.com/"):
                problems.append("directory.pages[%d]: the directory is read from pages of Learn, each with its date" % index)
        for key in ("servers", "remote", "local"):
            if not isinstance(directory.get(key), int) or isinstance(directory.get(key), bool) or directory[key] < 0:
                problems.append("directory.%s: a count" % key)
    skills = catalog.get("skills")
    if _keys(skills, "skills", problems, ("pages", "facts")):
        _pages(skills.get("pages"), "skills.pages", problems)
        if not isinstance(skills.get("facts"), list) or not skills["facts"]:
            problems.append("skills.facts: must be a non-empty list")
        else:
            for index, fact in enumerate(skills["facts"]):
                _text(fact, "skills.facts[%d]" % index, problems)
    servers = catalog.get("servers")
    if not isinstance(servers, list) or not servers:
        problems.append("servers: must be a non-empty list")
        return problems
    seen = set()
    for index, server in enumerate(servers):
        where = "servers[%d]" % index
        if not _keys(server, where, problems, ("id", "group", "name", "hosting", "use", "endpoint", "needs", "pages", "tools", "knowledge", "flagged"),
                     ("short", "status", "directory")):
            continue
        sid = server.get("id")
        if not isinstance(sid, str) or not ID_RE.fullmatch(sid):
            problems.append("%s.id: lower-case words joined by hyphens" % where)
            continue
        where = "server %s" % sid
        if sid in seen:
            problems.append("%s: the id is used twice" % where)
        seen.add(sid)
        group = server.get("group")
        if group not in GROUPS:
            problems.append("%s.group: one of %s" % (where, ", ".join(GROUPS)))
        if server.get("hosting") not in HOSTINGS:
            problems.append("%s.hosting: one of %s" % (where, ", ".join(HOSTINGS)))
        if server.get("endpoint") not in ENDPOINTS:
            problems.append("%s.endpoint: one of %s" % (where, "; ".join(ENDPOINTS)))
        for key in ("name", "use"):
            _text(server.get(key), where + "." + key, problems)
        if group == "pinned":
            for key in ("short", "status"):
                if key in server:
                    problems.append("%s: a pinned server takes its %s from the manifest" % (where, key))
        else:
            _text(server.get("short"), where + ".short", problems, 80)
            if server.get("status") not in STATUSES:
                problems.append("%s.status: one of %s" % (where, ", ".join(STATUSES)))
        if "directory" in server and server["directory"] is not True:
            problems.append("%s.directory: true, or absent" % where)
        if group == "listed" and server.get("directory") is not True:
            problems.append("%s: a listed server is one of the directory" % where)
        if group in ("also", "related") and server.get("directory"):
            problems.append("%s: a server of the directory is pinned or listed" % where)
        needs = server.get("needs")
        if not isinstance(needs, list) or not needs:
            problems.append("%s.needs: must be a non-empty list" % where)
        else:
            for n, sentence in enumerate(needs):
                _text(sentence, "%s.needs[%d]" % (where, n), problems)
        _pages(server.get("pages"), where + ".pages", problems)
        listed = _tools(server.get("tools"), where + ".tools", problems)
        tools = server.get("tools") if isinstance(server.get("tools"), dict) else {}
        if group in ("related",) and tools.get("from") == "lock":
            problems.append("%s: a related server is not in the lock" % where)
        if tools.get("from") == "lock" and isinstance(tools.get("contract"), str) and tools["contract"].split("/")[0] != sid:
            problems.append("%s.tools.contract: the contract of another server (a lock key starts with the id of the server)" % where)
        knowledge = server.get("knowledge")
        if not isinstance(knowledge, list):
            problems.append("%s.knowledge: must be a list" % where)
        else:
            named = []
            for n, entry in enumerate(knowledge):
                here = "%s.knowledge[%d]" % (where, n)
                if _keys(entry, here, problems, ("tools", "what")):
                    named += _strings(entry.get("tools"), here + ".tools", problems, TOOL_RE)
                    _text(entry.get("what"), here + ".what", problems)
            if len(set(named)) != len(named):
                problems.append("%s.knowledge: a tool is listed in two entries" % where)
        flagged = server.get("flagged")
        if not isinstance(flagged, list):
            problems.append("%s.flagged: must be a list" % where)
        else:
            areas = []
            for n, entry in enumerate(flagged):
                here = "%s.flagged[%d]" % (where, n)
                if _keys(entry, here, problems, ("area", "tools"), ("note", "changes")):
                    if entry.get("area") not in AREAS:
                        problems.append("%s.area: one of %s" % (here, "; ".join(AREAS)))
                    areas.append(entry.get("area"))
                    names = _strings(entry.get("tools"), here + ".tools", problems, TOOL_RE, allow_empty=True)
                    if "note" in entry:
                        _text(entry["note"], here + ".note", problems)
                        if not names:
                            problems.append("%s.note: a note goes with the tools of the entry, and this entry names none" % here)
                    changes = []
                    if "changes" in entry:
                        changes = _strings_of_text(entry["changes"], here + ".changes", problems)
                    if not names and not changes:
                        problems.append("%s: a flagged entry names a tool that is never called, or a change that is never made through any tool" % here)
            if len(set(areas)) != len(areas):
                problems.append("%s.flagged: an area is listed twice" % where)
    return problems


def load(text, label="catalog.json"):
    catalog = parse(text, label)
    problems = check_structure(catalog)
    if problems:
        raise CatalogError("%s: %d problem(s)" % (label, len(problems)), problems)
    return catalog


# ---------------------------------------------------------------- tools of a server

def contract_tools(lock, key):
    """{name: kind} of a locked contract, in the order that the lock has them: as the server reported its annotations (a tool that says both read-only and destructive counts as destructive)."""
    entry = (lock.get("contracts") or {}).get(key)
    if not isinstance(entry, dict) or entry.get("status") != "captured":
        return None
    out = {}
    for name, tool in entry["tools"].items():
        out[name] = "destructive" if tool.get("destructive") else ("read" if tool.get("read_only") else "write")
    return out


def server_tools(server, lock):
    """[(set, kind or None, [names])] of a server: from its pages, or from its locked contract. None where it lists none."""
    tools = server["tools"]
    if tools["from"] == "none":
        return []
    if tools["from"] == "page":
        return [(group.get("set"), group["kind"], list(group["names"])) for group in tools["groups"]]
    found = contract_tools(lock, tools["contract"])
    if found is None:
        return None
    if tools.get("kinds") == "variant":
        return [(None, None, list(found))]
    return [(None, kind, [n for n, k in found.items() if k == kind]) for kind in KINDS if any(k == kind for k in found.values())]


def tool_names(server, lock):
    groups = server_tools(server, lock)
    return None if groups is None else [n for _set, _kind, names in groups for n in names]


def name_words(name):
    """The lower-case words of a tool name, split at hyphens, underscores, dots, spaces and camel case (RLSRole is rls and role)."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    return set(re.findall(r"[a-z]+", spaced.lower()))


def unflagged_tools(server, lock):
    """[name] of the tools of a server whose name says that it touches a protected area (when the tool is not read-only) or returns a secret (whatever its kind), and that is neither flagged by name nor named
    by a statement of `changes` under an area that the words of its name belong to (AREA_WORDS)."""
    covered = {}
    for entry in server["flagged"]:
        for name in entry["tools"] + [n for c in entry.get("changes", []) for n in re.findall(r"`([^`]+)`", c)]:
            covered.setdefault(name, set()).add(entry["area"])
    out = []
    for _set, kind, names in server_tools(server, lock) or []:
        for name in names:
            words = name_words(name)
            risky = bool(words & SECRET_WORDS) or (kind != "read" and bool(words & PROTECTED_WORDS))
            needed = set()
            for word in words & PROTECTED_WORDS:
                needed |= WORD_AREAS.get(word, set(AREAS))
            if risky and not (covered.get(name, set()) & needed) and (server["id"], name) not in PROTECTED_REVIEWED:
                out.append(name)
    return out


def check_against(catalog, manifest, lock):
    """The problems of a well-formed catalog against the manifest and the lock; none when they agree."""
    problems = []
    servers = catalog["servers"]
    pinned = [s["id"] for s in servers if s["group"] == "pinned"]
    manifest_ids = [s["id"] for s in manifest["mcp_servers"]]
    for sid in sorted(set(manifest_ids) - set(pinned)):
        problems.append("server %s: the manifest pins it and the catalog does not list it" % sid)
    for sid in sorted(set(pinned) - set(manifest_ids)):
        problems.append("server %s: the catalog lists it as pinned and the manifest does not pin it" % sid)
    by_id = {s["id"]: s for s in manifest["mcp_servers"]}
    for server in servers:
        where = "server %s" % server["id"]
        if server["group"] == "pinned" and server["id"] in by_id:
            urls = {page["url"] for page in server["pages"]}
            for doc in by_id[server["id"]].get("docs", []):
                if doc not in urls:
                    problems.append("%s: the manifest names %s as its documentation and the catalog does not cite it" % (where, doc))
            transport = by_id[server["id"]]["transport"]
            if (server["hosting"] == "remote") != (transport == "http"):
                problems.append("%s: hosted as %s, yet the manifest says its transport is %s" % (where, server["hosting"], transport))
            for name in server_sign_in_words(by_id[server["id"]]):
                if name is None:
                    problems.append("%s: a sign-in of the manifest has no word in the table" % where)
        listed = tool_names(server, lock)
        if listed is None:
            problems.append("%s: its contract %s is not captured in the lock" % (where, server["tools"].get("contract")))
            continue
        if server["tools"]["from"] == "lock" and server["group"] != "pinned":
            problems.append("%s: only a pinned server has a contract in the lock" % where)
        if server["tools"]["from"] == "lock":
            for name, tool in lock["contracts"][server["tools"]["contract"]]["tools"].items():
                if tool.get("read_only") and tool.get("destructive"):
                    problems.append("%s: the lock records the tool %s as read-only and as destructive" % (where, name))
        for entry in server["knowledge"]:
            for name in entry["tools"]:
                if name not in listed:
                    problems.append("%s: the knowledge tool %s is not one of its tools" % (where, name))
        for entry in server["flagged"]:
            for name in entry["tools"]:
                if name not in listed:
                    problems.append("%s: the flagged tool %s is not one of its tools" % (where, name))
                if any(name in k["tools"] for k in server["knowledge"]):
                    problems.append("%s: the tool %s is a knowledge tool and is flagged as never called" % (where, name))
            for change in entry.get("changes", []):
                for name in re.findall(r"`([^`]+)`", change):
                    if name not in listed:
                        problems.append("%s: a statement of changes names `%s`, which is not one of its tools (a word in back ticks there is a tool of the server)" % (where, name))
        for name in unflagged_tools(server, lock):
            problems.append("%s: the name of the tool %s says that it touches a protected area or returns a secret, and the catalog neither flags it nor names it in a statement of changes" % (where, name))
        for page in server["pages"]:
            match = SKILLS_TAG_RE.match(page["url"])
            if match:
                tag = (lock.get("skill_sources") or {}).get("skills-for-fabric", {}).get("tag")
                if match.group(1) != tag:
                    problems.append("%s: it cites the skills repository at %s and the lock pins %s: read the page again" % (where, match.group(1), tag))
    in_directory = [s for s in servers if s.get("directory")]
    directory = catalog["directory"]
    if len(in_directory) != directory["servers"]:
        problems.append("directory: %d servers are marked as listed by Fabric and the directory counts %d" % (len(in_directory), directory["servers"]))
    for hosting in ("remote", "local"):
        if len([s for s in in_directory if s["hosting"] == hosting]) != directory[hosting]:
            problems.append("directory: the number of %s servers is not %d" % (hosting, directory[hosting]))
    if directory["remote"] + directory["local"] != directory["servers"]:
        problems.append("directory: remote and local servers do not add up to the servers")
    for sid in sorted(set(manifest_ids) & {"fabric-core", "fabric-iq", "fabric-sql", "fabric-local"}):
        if not next(s for s in servers if s["id"] == sid).get("directory"):
            problems.append("server %s: the directory lists it" % sid)
    for sid, name in sorted(PROTECTED_REVIEWED):
        server = next((s for s in servers if s["id"] == sid), None)
        names = tool_names(server, lock) if server is not None else []
        if names is None:
            continue  # the contract is not captured: reported above
        if name not in names:
            problems.append("server %s: the tool %s is reviewed and left out of the check of protected names, and the server no longer has it" % (sid, name))
        elif any(name in e["tools"] or any(name in re.findall(r"`([^`]+)`", c) for c in e.get("changes", [])) for e in server["flagged"]):
            problems.append("server %s: the tool %s is reviewed and left out of the check of protected names, and the catalog flags it: drop the exception" % (sid, name))
    return problems


def server_sign_in_words(server):
    return [SIGN_IN_WORDS.get(v["credentials"]) for v in server["variants"].values()]


# ---------------------------------------------------------------- generated text

def _code(names):
    return ", ".join("`%s`" % n for n in names)


def sign_in_cell(server):
    """The sign-in cell of a manifest server: a bare word for its only variant `default`, else a back-ticked variant and its word, joined by '; '."""
    words = {name: SIGN_IN_WORDS[spec["credentials"]] for name, spec in server["variants"].items()}
    if list(words) == ["default"]:
        return words["default"]
    return "; ".join("`%s` %s" % (name, word) for name, word in words.items())


def doc_key(url):
    """The address of a page as the tables write it: without the scheme and the host and language of Microsoft Learn."""
    return url[len(LEARN_PREFIX):] if url.startswith(LEARN_PREFIX) else re.sub(r"^https://", "", url)


def _table(headers, rows):
    return ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)] + ["| " + " | ".join(row) + " |" for row in rows]


def _group_table(servers, header, hosting_word):
    rows = []
    for server in servers:
        name = server["short"] + (", " + server["hosting"] if hosting_word else "")
        rows.append([name, server["use"], "`%s`" % doc_key(server["pages"][0]["url"])])
    return _table([header, "What it does", "Documentation (a path on learn.microsoft.com/en-us/, or a host and path)"], rows)


def pinned_region(catalog, manifest):
    by_id = {s["id"]: s for s in manifest["mcp_servers"]}
    rows = [["`%s`" % s["id"], sign_in_cell(by_id[s["id"]]), s["use"]] for s in catalog["servers"] if s["group"] == "pinned"]
    return "\n".join(_table(["Server", "Sign-in", "Use it for"], rows)) + "\n"


def others_region(catalog):
    servers, directory = catalog["servers"], catalog["directory"]
    pinned_in_directory = len([s for s in servers if s["group"] == "pinned" and s.get("directory")])
    lines = ["Fabric's own directory of its MCP servers (%s, updated %s) lists %d: %d remote and %d local. The kit pins %d of them, and the others are here."
             % (directory["pages"][0]["url"], directory["pages"][0]["updated"], directory["servers"], directory["remote"], directory["local"], pinned_in_directory), ""]
    lines += _group_table([s for s in servers if s["group"] == "listed"], "Listed by Fabric, not pinned", True)
    lines += ["", "Microsoft also publishes these outside that directory, under the same rules:", ""]
    lines += _group_table([s for s in servers if s["group"] == "also"], "Published outside the directory", True)
    lines += ["", "The directory itself names two related integrations that Microsoft does not host for you:", ""]
    lines += _group_table([s for s in servers if s["group"] == "related"], "Related to Fabric, not hosted by Microsoft", False)
    return "\n".join(lines) + "\n"


def flagged_region(catalog):
    """One table, a row for each area: the tools that are never called, and the changes that are never made through any tool (a statement of a tool that can run any, a call with a protected argument)."""
    rows = []
    for area in AREAS:
        tools, changes = [], []
        for server in catalog["servers"]:
            for entry in server["flagged"]:
                if entry["area"] != area:
                    continue
                if entry["tools"]:
                    text = "`%s`: %s" % (server["id"], _code(entry["tools"]))
                    if "note" in entry:
                        text += " (%s)" % entry["note"]
                    tools.append(text)
                changes += ["`%s`: %s" % (server["id"], change) for change in entry.get("changes", [])]
        if tools or changes:
            rows.append([AREA_LABELS[area], "; ".join(tools) or "none", "; ".join(changes) or "none"])
    return "\n".join(_table(["Area", "Never called: the tools, by server", "Never made, through any tool: the change, by server"], rows)) + "\n"


def knowledge_region(catalog):
    rows = []
    for server in catalog["servers"]:
        for entry in server["knowledge"]:
            rows.append(["%s (`%s`)" % (server["name"], server["id"]), _code(entry["tools"]), entry["what"]])
    return "\n".join(_table(["Knowledge tools of", "Tools", "What they give"], rows)) + "\n"


def skills_region(catalog, manifest, lock, own):
    quarantined = manifest.get("quarantine") or []
    rows = []
    for source in manifest["skill_sources"]:
        locked = (lock.get("skill_sources") or {}).get(source["id"], {})
        blocked = {q["skill"] for q in quarantined if q["source"] == source["id"]}
        plugins = ", ".join("`%s` (%d)" % (name, len([s for s in entry["skills"] if s not in blocked])) for name, entry in locked.get("plugins", {}).items())
        rows.append(["`%s` (%s)" % (source["id"], source["title"]), plugins, locked.get("tag", "not locked")])
    lines = _table(["Skills source", "Plugins (skills that can load)", "Pinned at"], rows) + [""]
    lines += ["- " + fact for fact in catalog["skills"]["facts"]]
    if quarantined:
        lines.append("- Quarantined, never loaded: " + _code([q["skill"] for q in quarantined]) + ".")
    if own:
        lines.append("- The kit's own skills (" + _code(own) + ") load with every profile that has any skill or server.")
    lines.append("- Read from: " + ", ".join("`%s`" % doc_key(p["url"]) for p in catalog["skills"]["pages"]) + ".")
    return "\n".join(lines) + "\n"


def regions(catalog, manifest, lock, own_skills):
    return {"pinned": pinned_region(catalog, manifest), "others": others_region(catalog), "flagged": flagged_region(catalog),
            "knowledge": knowledge_region(catalog), "skills": skills_region(catalog, manifest, lock, own_skills)}


def splice(text, generated):
    """(text with every generated block replaced, problems): each block is there exactly once, and no other block is."""
    problems, found = [], {}
    for match in REGION_RE.finditer(text):
        name = match.group("name")
        if name in found:
            problems.append("the block '%s' is there twice" % name)
        found[name] = match
    for name in sorted(set(found) - set(generated)):
        problems.append("the block '%s' is not one that the catalog generates" % name)
    for name in sorted(set(generated) - set(found)):
        problems.append("the block '%s' is missing: put its BEGIN GENERATED and END GENERATED comments where it goes" % name)
    if text.count("<!-- BEGIN GENERATED") != len(REGION_RE.findall(text)) or text.count("<!-- END GENERATED") != len(REGION_RE.findall(text)):
        problems.append("a BEGIN GENERATED or END GENERATED comment has no partner, or is not written as <!-- BEGIN GENERATED name -->")
    if problems:
        return text, problems
    return REGION_RE.sub(lambda m: "<!-- BEGIN GENERATED %s -->\n%s<!-- END GENERATED %s -->" % (m.group("name"), generated[m.group("name")], m.group("name")), text), []


# ---------------------------------------------------------------- the reference

def _count(n, word):
    return "%d %s" % (n, word)


def _server_section(server, manifest_server, lock):
    group_words = {"pinned": "pinned in the manifest", "listed": "listed by Fabric, not pinned", "also": "published by Microsoft outside the directory",
                   "related": "related to Fabric"}
    stage = STAGE_WORDS[manifest_server["status"] if manifest_server else server["status"]]
    lines = ["## `%s`: %s" % (server["id"], server["name"]), ""]
    where = WHERE.get(server["endpoint"]) or "%s, %s" % (server["hosting"], server["endpoint"])
    lines.append("- Group: %s. Runs: %s. Stage: %s." % (group_words[server["group"]], where, stage))
    if manifest_server:
        lines.append("- Sign-in: %s." % sign_in_cell(manifest_server))
    lines.append("- Needs and limits:")
    lines += ["  - " + sentence for sentence in server["needs"]]
    lines.append("- Read from: " + "; ".join("`%s`%s" % (doc_key(p["url"]), " (updated %s)" % p["updated"] if "updated" in p else "") for p in server["pages"]) + ".")
    tools = server["tools"]
    groups = server_tools(server, lock)
    if tools["from"] == "none":
        lines.append("- Tools: " + tools["note"])
    elif tools["from"] == "lock":
        prefix = tools["contract"].split("/")[0] + "/"
        variants = sorted((k, e) for k, e in lock["contracts"].items() if k.startswith(prefix) and e.get("status") == "captured")
        entry = lock["contracts"][tools["contract"]]
        counts = "; ".join("`%s` %d" % (k.split("/")[1], len(e["tools"])) for k, e in variants)
        lines.append("- Tools: the lock's contract `%s`, measured at %s on %s (variants: %s)." % (tools["contract"], entry["package_version"], entry["captured"], counts))
        if tools.get("kinds") == "variant":
            args = (((manifest_server or {}).get("variants") or {}).get(tools["contract"].split("/")[1]) or {}).get("args") or []
            switch = ("The kit starts this variant with the server's read-only switch, so none of its commands writes" if any(a in READ_ONLY_SWITCHES for a in args)
                      else "The kit does not start this variant with the server's read-only switch, so a command of it can write")
            lines.append("  - %d tools, each one a namespace of commands or a single command. %s; the server's own annotations of a namespace tool do not say which of its commands write, "
                         "so no kinds are listed." % (len(groups[0][2]), switch))
            lines.append("  - " + _code(groups[0][2]))
        else:
            for _set, kind, names in groups:
                lines.append("  - %s (%d): %s" % (LOCK_KIND_WORDS[kind], len(names), _code(names)))
    else:
        total = sum(len(names) for _s, _k, names in groups)
        lines.append("- Tools (%d, from the pages):" % total)
        current = object()
        for tool_set, kind, names in groups:
            if tool_set != current:
                current = tool_set
                if tool_set:
                    lines.append("  - %s:" % tool_set)
            lines.append("  %s- %s (%d): %s" % ("  " if tool_set else "", kind, len(names), _code(names)))
    for entry in server["knowledge"]:
        lines.append("- Knowledge: %s: %s." % (_code(entry["tools"]), entry["what"]))
    for entry in server["flagged"]:
        text = AREA_LABELS[entry["area"]]
        if entry["tools"]:
            lines.append("- Never called, %s: %s%s." % (text, _code(entry["tools"]), " (%s)" % entry["note"] if "note" in entry else ""))
        for change in entry.get("changes", []):
            lines.append("- Never made, through any tool, %s: %s." % (text, change))
    return lines + [""]


def render_reference(catalog, manifest, lock):
    by_id = {s["id"]: s for s in manifest["mcp_servers"]}
    out = ["# MCP servers and their tools", "",
           "This file is generated from `toolchain/catalog.json`, the lock and the manifest by `python scripts/toolchain.py instructions --write`. Do not edit it.",
           "A person read the pages named below on %s. A change of the catalog is checked against them by a model family other than the one that wrote it (rule 9 of AGENTS.md)." % catalog["read"],
           "The weekly fact check shows a page that changed as drift, and a person refreshes the catalog in a reviewed pull request.", "",
           "How to use it:", "",
           "- A server that the lock measured (a stdio server that was launched and listed its tools) has a contract: a tool of it that is missing, renamed or changed against the lock is a contract drift. Stop and report it.",
           "- Any other server has no measured contract, and its entry here is a person's reading of its pages. Where the entry lists tools, compare the names that the server lists with them (names only, not schemas): "
           "a tool that the work needs and the server does not list, or a tool that it lists and this file does not, is a difference to report to the person before you go on. "
           "Where the entry lists no tools, tell the person what the server listed before you call one.",
           "- The kinds. Where a person listed the tools from the pages: `read` only reads, `write` creates or changes, `destructive` deletes, removes or replaces, and `mixed` is one tool that reads and also writes or deletes, "
           "where the operation or the statement that a call names decides which. Where the lock measured the tools: the annotations that the server reported (read-only; destructive, the protocol's hint that a tool may perform "
           "destructive updates; or neither). They are the server's own words and no review of what each tool does.",
           "- A call that changes the live state of a tenant or of Azure needs the approval that the rules ask for in a session (rule 6 of AGENTS.md; rule 2 of \"How to work\" in the preamble), and a job makes no change through an MCP tool. "
           "A tool that changes only a file on the machine works within the access of its profile.",
           "- \"Never called\" lists the tools that no agent calls. \"Never made\" lists the changes that no agent makes through any tool that can run them (a statement, a call with a protected argument), in a session or in a job.", "",
           "| Server | Group | Runs | Stage |", "|---|---|---|---|"]
    for server in catalog["servers"]:
        manifest_server = by_id.get(server["id"])
        stage = STAGE_WORDS[manifest_server["status"] if manifest_server else server["status"]]
        out.append("| `%s` | %s | %s | %s |" % (server["id"], server["group"], server["hosting"], stage))
    out.append("")
    for server in catalog["servers"]:
        out += _server_section(server, by_id.get(server["id"]), lock)
    return "\n".join(out).rstrip("\n") + "\n"
