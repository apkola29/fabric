#!/usr/bin/env python3
"""Tests for toolchain.py: the model (schemas, mode rules, quarantine, packages), the renderings, and the commands.

Nothing here uses the network, a real subprocess or the real home folder. The resolvers, the probes and the runner are
replaced by fakes through the Deps object, and HOME, USERPROFILE and Path.home point to a temporary folder. A synthetic
lock is built from the real manifest and profiles, and smaller fixture manifests exercise the rules. Package specs are
joined at run time (name + "@" + version), because the repository scanner reads a spec in source as an e-mail address.
Run from the project folder:

    python -m unittest scripts.test_toolchain -v
"""

import contextlib
import copy
import datetime
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import toolchain  # noqa: E402
import toolchain_mcp  # noqa: E402
import toolchain_sources  # noqa: E402

REAL = HERE.parent / "toolchain"
Result = namedtuple("Result", "returncode stdout stderr")
NOW = datetime.datetime(2026, 10, 30, 12, 0, 0, tzinfo=datetime.timezone.utc)
STAMP = "20261030T120000Z"
EULA_ENV = "ACME_ACCEPT_EULA"


def pin(name, version):
    return name + "@" + version


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fake_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest_files(files):
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(rel.encode("utf-8") + b"\0" + hashlib.sha256(files[rel]).digest())
    return "sha256:" + h.hexdigest()


def tree_digest(root):
    root = Path(root)
    files = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    return {"digest": digest_files(files), "files": len(files), "bytes": sum(len(v) for v in files.values())}


def skill_files(name):
    return {"SKILL.md": ("---\nname: %s\ndescription: a test skill\n---\n\nBody of %s.\n" % (name, name)).encode("utf-8"),
            "references/notes.md": b"notes\n"}


def skill_digest(name):
    return digest_files(skill_files(name))


def fake_contract_diff(locked, live):
    keys = ("schema", "read_only", "destructive", "idempotent")
    return {"added": sorted(set(live) - set(locked)), "removed": sorted(set(locked) - set(live)),
            "changed": sorted(n for n in set(locked) & set(live) if any(locked[n].get(k) != live[n].get(k) for k in keys))}


# ---------------------------------------------------------------- fixtures

def variant(network="none", credentials="none", access="read", unattended=True, **more):
    return {"credentials": credentials, "network": network, "access": access, "unattended": unattended, **more}


def small_manifest():
    allow_all = {"network": ["none", "microsoft-cloud", "internet"],
                 "credentials": ["none", "azure-identity", "entra-delegated", "github"],
                 "access": ["read", "read-write"], "unattended": "any"}
    return {
        "schema": 1, "default_profile": "dev-a", "store": ".factory/pack",
        "modes": {
            "dev": {"allow": allow_all},
            "agent": {"allow": {"network": ["none"], "credentials": ["none"], "access": ["read"], "unattended": "required"}},
            "executor": {"allow": {"network": ["none", "microsoft-cloud"], "credentials": ["none", "azure-identity"],
                                   "access": ["read"], "unattended": "required"}},
        },
        "hosts": {
            "copilot-cli": {"binary": "copilot", "mcp_project": ".github/mcp.json", "mcp_user": "$HOME/.copilot/mcp-config.json",
                            "skills_project": ".github/skills", "skills_user": "$HOME/.copilot/skills"},
            "vscode": {"binary": "code", "mcp_project": ".vscode/mcp.json", "mcp_user": None,
                       "skills_project": ".github/skills", "skills_user": "$HOME/.copilot/skills"},
            "claude-code": {"binary": "claude", "mcp_project": ".mcp.json", "mcp_user": None,
                            "skills_project": ".claude/skills", "skills_user": "$HOME/.claude/skills"},
        },
        "tools": [
            {"id": "git", "command": "git", "version_args": ["--version"], "min": "2.30", "needed_for": "everything", "required": True},
            {"id": "python", "command": "python", "alternatives": ["python3", "py"], "version_args": ["--version"], "min": "3.10",
             "needed_for": "the checks", "required": True},
            {"id": "gh", "command": "gh", "version_args": ["--version"], "min": "2.40", "needed_for": "publishing", "required": False},
            {"id": "az", "command": "az", "version_args": ["--version"], "min": "2.60", "needed_for": "sign-in", "required": False},
            {"id": "fab", "command": "fab", "version_args": ["--version"], "min": "1.0", "needed_for": "the CLI", "required": False,
             "package": {"ecosystem": "pypi", "name": "acme-cli", "track": "latest"}},
        ],
        "skill_sources": [{"id": "src", "repo": "https://github.com/acme/skills.git", "track": {"kind": "tag", "pattern": "v*"},
                           "plugins": [{"name": "core", "path": "plugins/core"}, {"name": "extra", "path": "plugins/extra"}]}],
        "quarantine": [{"source": "src", "skill": "risky", "reason": "retired format"}],
        "mcp_servers": [
            {"id": "npm-srv", "transport": "stdio", "status": "ga",
             "package": {"ecosystem": "npm", "name": "@acme/tool", "track": "latest"},
             "launch": {"command": "npx", "args": ["-y", "{package}"]},
             "env": {"ACME_MODE": {"from_env": "ACME_MODE", "default": "safe"}},
             "variants": {
                 "offline": variant(args=["--offline"]),
                 "online": variant("microsoft-cloud", "azure-identity", args=["--online"],
                                   env={"ACME_TARGET": {"from_env": "ACME_TARGET"}}),
                 "writer": variant(access="read-write"),
                 "manual": variant(unattended=False),
                 "unknown": variant(unattended="unverified"),
                 "internet": variant("internet"),
                 "gh": variant(credentials="github"),
                 "entra": variant(credentials="entra-delegated"),
             }},
            {"id": "py-srv", "transport": "stdio", "status": "beta",
             "package": {"ecosystem": "pypi", "name": "acme-py", "track": "latest"},
             "launch": {"command": "uvx", "args": ["{package}"]},
             "variants": {"default": variant("microsoft-cloud", "azure-identity", args=["--all"])}},
            {"id": "nuget-srv", "transport": "stdio", "status": "unverified",
             "package": {"ecosystem": "nuget", "name": "Acme.Nuget", "track": "latest"},
             "launch": {"command": "dnx", "args": ["{package}", "--yes"]},
             "variants": {"default": variant("internet")}},
            {"id": "licensed", "transport": "stdio", "status": "public-preview",
             "package": {"ecosystem": "npm", "name": "@acme/licensed", "track": "latest"},
             "launch": {"command": "npx", "args": ["-y", "{package}"]},
             "eula": {"url": "https://github.com/acme/licensed/blob/main/EULA.txt", "accept": "operator", "env": EULA_ENV},
             "env": {EULA_ENV: {"from_env": EULA_ENV, "default": "false"}},
             "variants": {"offline": variant(args=["--start", "--readonly"])}},
            {"id": "hosted", "transport": "http", "status": "preview", "url": "https://mcp.example.invalid/v1/mcp",
             "headers": {"X-VARIANTS": "Acme.V1"},
             "variants": {"default": variant("microsoft-cloud", "entra-delegated", "read-write", False)}},
            {"id": "docs", "transport": "http", "status": "ga", "url": "https://docs.example.invalid/mcp",
             "variants": {"default": variant("internet")}},
        ],
    }


def small_profiles():
    return toolchain.Profiles({"schema": 1, "profiles": {
        "dev-a": {"mode": "dev", "title": "Everything",
                  "skills": [{"source": "src", "plugin": "core", "names": "*"},
                             {"source": "src", "plugin": "extra", "names": ["gamma"]}],
                  "mcp": [{"server": "npm-srv", "variant": "online"}, {"server": "py-srv", "variant": "default"},
                          {"server": "nuget-srv", "variant": "default"}, {"server": "licensed", "variant": "offline"},
                          {"server": "hosted", "variant": "default"}, {"server": "docs", "variant": "default"}],
                  "instructions": ["instructions/base.md"]},
        "agent-ok": {"mode": "agent", "skills": [{"source": "src", "plugin": "core", "names": ["alpha-core"]}],
                     "mcp": [{"server": "npm-srv", "variant": "offline"}], "instructions": ["instructions/base.md"]},
        "agent-empty": {"mode": "agent", "skills": [], "mcp": [], "instructions": []},
    }})


PACKAGE_VERSIONS = {"npm": "1.6.0", "pypi": "1.8.0", "nuget": "0.5.0"}


def synthetic_lock(manifest, profiles, today="2026-10-01"):
    """A lock that follows section 4 for any manifest and profiles, with invented counts and digests."""
    picked = {}
    for profile in profiles["profiles"].values():
        for selector in profile["skills"]:
            if selector["names"] != "*":
                picked.setdefault((selector["source"], selector["plugin"]), set()).update(selector["names"])
    sources = {}
    for index, source in enumerate(manifest["skill_sources"]):
        plugins = {}
        for position, plugin in enumerate(source["plugins"]):
            names = set(picked.get((source["id"], plugin["name"]), ())) | {"alpha-" + plugin["name"], "beta-" + plugin["name"]}
            if position == 0:
                names |= {q["skill"] for q in manifest.get("quarantine", []) if q["source"] == source["id"]}
            plugins[plugin["name"]] = {
                "path": plugin["path"], "version": "0.%d.0" % (index + 1),
                "skills": {n: {"path": plugin["path"] + "/skills/" + n, "digest": skill_digest(n), "files": 2, "bytes": 200,
                               "description_chars": 120, "install_hints": 0, "findings": []} for n in sorted(names)},
                "agents": ["Helper.agent.md"], "bundled_mcp": ["bundled"]}
        sources[source["id"]] = {"repo": source["repo"], "tag": "v0.%d.0" % (index + 1) if source["track"]["kind"] == "tag" else None,
                                 "commit": str(index + 1) * 40, "plugins": dict(sorted(plugins.items()))}
    packages = {}
    for key, package in sorted(toolchain.declared_packages(manifest).items()):
        eco = package["ecosystem"]
        entry = {"status": "resolved", "version": PACKAGE_VERSIONS[eco] if package["track"] == "latest" else package["track"]}
        if eco == "npm":
            entry.update(integrity="sha512-" + fake_hash(key)[:40], via="npm-cli")
        elif eco == "pypi":
            entry.update(sha256=fake_hash(key), via="pypi")
        else:
            entry.update(via="nuget")
        packages[key] = entry
    wanted = {(m["server"], m["variant"]) for p in profiles["profiles"].values() for m in p["mcp"]}
    contracts = {}
    for server in manifest["mcp_servers"]:
        for name, spec in server["variants"].items():
            if (server["id"], name) not in wanted:
                continue
            key = "%s/%s" % (server["id"], name)
            if server["transport"] == "http":
                contracts[key] = {"status": "open"} if spec["credentials"] == "none" else {"status": "needs-sign-in"}
                continue
            package = server["package"]["name"]
            version = packages[toolchain.package_key(server["package"])]["version"]
            contracts[key] = {"status": "captured", "era": "legacy", "protocol": "2025-11-25",
                              "server": {"name": package, "version": version}, "package_version": version,
                              "tools": {t: {"schema": "sha256:" + fake_hash(package + t), "read_only": True, "destructive": False,
                                            "idempotent": True} for t in ("tool_a", "tool_b")}}
    return toolchain.Lock({"schema": 1, "generated": today, "inputs_digest": toolchain.inputs_digest(manifest),
                           "skill_sources": dict(sorted(sources.items())), "packages": packages,
                           "contracts": dict(sorted(contracts.items()))})


def write_project(root, manifest, profiles, lock=None):
    tdir = Path(root) / "toolchain"
    write(tdir / "toolchain.json", toolchain.dump_json(manifest))
    write(tdir / "profiles.json", toolchain.dump_json(profiles))
    write(tdir / "instructions" / "base.md", "# Preamble\n\nBe careful.\n")
    write(tdir / "skills" / "router" / "SKILL.md", "---\nname: router\ndescription: routes work\n---\n")
    if lock is not None:
        write(tdir / "toolchain.lock.json", toolchain.dump_json(lock))


def copy_real_project(root, with_lock=True):
    """The real manifest, profiles, instructions and router skill, with a synthetic lock."""
    shutil.copytree(REAL, Path(root) / "toolchain", ignore=shutil.ignore_patterns("toolchain.lock.json"))
    manifest = toolchain.load_manifest(REAL / "toolchain.json")
    profiles = toolchain.load_profiles(REAL / "profiles.json")
    lock = synthetic_lock(manifest, profiles)
    if with_lock:
        write(Path(root) / "toolchain" / "toolchain.lock.json", toolchain.dump_json(lock))
    return manifest, profiles, lock


def write_store(store, lock, names, inputs=None):
    """A fake local pack holding the named skills with the content that the synthetic digests describe."""
    for name in names:
        for rel, data in skill_files(name).items():
            write(Path(store) / "skills" / name / rel, data)
    entries = {n: {"source": "src", "plugin": "core", "commit": "1" * 40, "digest": skill_digest(n), "files": 2, "bytes": 200} for n in names}
    write(Path(store) / "MANIFEST.json", toolchain.dump_json({"schema": 1, "lock_inputs_digest": inputs or lock["inputs_digest"], "skills": entries}))


class FakeRunner:
    """The three runner methods, answering from tables. `which` knows only the names in `found`."""

    def __init__(self, found=(), answers=None):
        self.found = {name: "/opt/fake/bin/" + name for name in found}
        self.answers = dict(answers or {})
        self.calls = []

    def which(self, name):
        return self.found.get(name)

    def run(self, argv, *, cwd=None, env=None, timeout=60, input=None):
        self.calls.append(list(argv))
        key = (Path(argv[0]).name.split(".")[0],) + tuple(argv[1:])
        return Result(*self.answers.get(key, (0, "", "")))

    def http(self, method, url, *, headers=None, body=None, timeout=20):
        raise AssertionError("the network must not be used")


GOOD_TOOLS = {("git", "--version"): (0, "git version 2.43.0.windows.1\n", ""), ("python", "--version"): (0, "Python 3.11.9\n", ""),
              ("gh", "--version"): (0, "gh version 2.45.0 (2024-03-01)\n", ""), ("az", "--version"): (0, "azure-cli  2.61.0\n", "")}


def forbidden(name):
    def call(*args, **kwargs):
        raise AssertionError("%s must not be called here" % name)
    return call


def make_deps(home, runner=None, env=None, clock=None, **functions):
    table = {name: forbidden(name) for name in toolchain.Deps._HOME}
    table.update(digest_tree=tree_digest, contract_diff=fake_contract_diff)
    table.update(functions)
    return toolchain.Deps(runner=runner or FakeRunner(), env={} if env is None else env, home=home, clock=clock or (lambda: NOW), **table)


class Upstream:
    """What the resolvers and probes see: tables that start equal to a lock, and that a test may change."""

    def __init__(self, manifest, lock):
        self.manifest = manifest
        self.refs, self.plugins, self.packages, self.tools, self.http_status = {}, {}, {}, {}, {}
        self.fail_refs = set()
        self.calls = {"probe_stdio": [], "probe_http": [], "fetch_git": [], "resolve_package": []}
        for source in lock["skill_sources"].values():
            self.refs[source["repo"]] = {"tag": source["tag"], "commit": source["commit"]}
            for plugin in source["plugins"].values():
                self.plugins[plugin["path"]] = {"version": plugin["version"], "skills": copy.deepcopy(plugin["skills"]),
                                                "agents": list(plugin["agents"]), "bundled_mcp": list(plugin["bundled_mcp"])}
        self.packages = copy.deepcopy(dict(lock["packages"]))
        for contract in lock["contracts"].values():
            if contract["status"] == "captured":
                self.tools[contract["server"]["name"]] = copy.deepcopy(contract["tools"])
        for server in manifest["mcp_servers"]:
            if server["transport"] == "http":
                self.http_status[server["url"]] = "open" if server["variants"]["default"]["credentials"] == "none" else "needs-sign-in"

    def resolve_git_ref(self, url, track, runner):
        if url in self.fail_refs:
            raise toolchain_sources.SourceError("network: fake failure")
        ref = self.refs[url]
        return {"ref": "refs/tags/" + ref["tag"] if ref["tag"] else "refs/heads/main", "tag": ref["tag"], "commit": ref["commit"]}

    def fetch_git(self, url, commit, dest, runner):
        self.calls["fetch_git"].append(commit)
        Path(dest).mkdir(parents=True, exist_ok=True)
        return Path(dest)

    def read_plugin(self, git_dir, commit, plugin_path, runner):
        return copy.deepcopy(self.plugins[plugin_path])

    def resolve_package(self, ecosystem, name, track, runner):
        self.calls["resolve_package"].append((ecosystem, name, track))
        return copy.deepcopy(self.packages["%s:%s" % (ecosystem, name)])

    def probe_stdio(self, argv, env=None, cwd=None, timeout=60):
        self.calls["probe_stdio"].append({"argv": list(argv), "env": env})
        for arg in argv:
            name, _, version = arg.rpartition("@")
            if name in self.tools:
                return {"era": "legacy", "protocol": "2025-11-25", "server": {"name": name, "version": version},
                        "tools": copy.deepcopy(self.tools[name])}
        raise toolchain_mcp.McpProbeError("exited: the fake server is gone")

    def probe_http(self, url, headers=None, runner=None, timeout=15):
        self.calls["probe_http"].append(url)
        return {"status": self.http_status.get(url, "error"), "http_status": 200}

    def deps(self, home, runner=None, env=None, clock=None, **more):
        table = dict(resolve_git_ref=self.resolve_git_ref, fetch_git=self.fetch_git, read_plugin=self.read_plugin,
                     resolve_package=self.resolve_package, probe_stdio=self.probe_stdio, probe_http=self.probe_http)
        table.update(more)
        return make_deps(home, runner=runner, env=env, clock=clock, **table)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tcx-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        patched = mock.patch.dict(os.environ, {"HOME": str(self.home), "USERPROFILE": str(self.home)})
        patched.start()
        self.addCleanup(patched.stop)
        home = mock.patch.object(Path, "home", return_value=self.home)
        home.start()
        self.addCleanup(home.stop)
        self.root = self.tmp / "project"
        self.root.mkdir()

    def small_project(self, manifest=None, profiles=None, with_lock=True):
        self.manifest = manifest or small_manifest()
        self.profiles = profiles or small_profiles()
        self.lock = synthetic_lock(self.manifest, self.profiles)
        write_project(self.root, self.manifest, self.profiles, self.lock if with_lock else None)
        return self.root

    def real_project(self, with_lock=True):
        self.manifest, self.profiles, self.lock = copy_real_project(self.root, with_lock)
        return self.root

    def deps(self, **kwargs):
        return make_deps(self.home, **kwargs)

    def cli(self, *argv, deps=None, root=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = toolchain.main(["--root", str(root or self.root)] + list(argv), deps or self.deps())
        return code, out.getvalue(), err.getvalue()

    def rewrite_lock(self, change):
        lock = copy.deepcopy(dict(self.lock))
        change(lock)
        self.lock = toolchain.Lock(lock)
        write(self.root / "toolchain" / "toolchain.lock.json", toolchain.dump_json(lock))

    def rewrite_manifest(self, change):
        manifest = copy.deepcopy(self.manifest)
        change(manifest)
        self.manifest = manifest
        write(self.root / "toolchain" / "toolchain.json", toolchain.dump_json(manifest))

    def rewrite_profiles(self, change):
        profiles = copy.deepcopy(dict(self.profiles))
        change(profiles)
        self.profiles = toolchain.Profiles(profiles)
        write(self.root / "toolchain" / "profiles.json", toolchain.dump_json(profiles))

    def resolved(self, name="dev-a"):
        return toolchain.resolve_profile(self.manifest, self.profiles, self.lock, name, self.root / "toolchain")

    def assertProblem(self, problems, fragment):
        self.assertTrue(any(fragment in p for p in problems), "no problem mentions %r in %r" % (fragment, problems))

    def assertNoProblem(self, problems, fragment):
        self.assertFalse(any(fragment in p for p in problems), "unexpected problem %r in %r" % (fragment, problems))


def at(obj, path):
    for step in path:
        obj = obj[step]
    return obj


# ---------------------------------------------------------------- schemas

class SchemaTests(Base):
    def test_the_real_data_loads_and_the_fixtures_are_valid(self):
        manifest = toolchain.load_manifest(REAL / "toolchain.json")
        profiles = toolchain.load_profiles(REAL / "profiles.json")
        self.assertEqual("dev-factory", manifest["default_profile"])
        self.assertEqual(REAL, profiles.base)
        self.assertEqual([], toolchain.validate_manifest(small_manifest()))
        self.assertEqual([], toolchain.validate_profiles(small_profiles()))
        self.assertEqual([], toolchain.validate_lock(synthetic_lock(small_manifest(), small_profiles())))

    MANIFEST_PATHS = [
        [], ["modes", "dev"], ["modes", "dev", "allow"], ["hosts", "copilot-cli"], ["tools", 0], ["tools", 4, "package"],
        ["skill_sources", 0], ["skill_sources", 0, "track"], ["skill_sources", 0, "plugins", 0], ["quarantine", 0],
        ["mcp_servers", 0], ["mcp_servers", 0, "package"], ["mcp_servers", 0, "launch"], ["mcp_servers", 0, "env", "ACME_MODE"],
        ["mcp_servers", 0, "variants", "offline"], ["mcp_servers", 0, "variants", "online", "env", "ACME_TARGET"],
        ["mcp_servers", 3, "eula"], ["update"],
    ]

    def test_an_unknown_key_is_refused_at_every_level_of_the_manifest(self):
        for path in self.MANIFEST_PATHS:
            with self.subTest(path=path):
                manifest = small_manifest()
                manifest["update"] = {"policy": "by hand"}
                at(manifest, path)["bogus"] = 1
                self.assertProblem(toolchain.validate_manifest(manifest), "unknown key 'bogus'")

    def test_an_unknown_key_is_refused_at_every_level_of_the_profiles(self):
        for path in ([], ["profiles", "dev-a"], ["profiles", "dev-a", "skills", 0], ["profiles", "dev-a", "mcp", 0]):
            with self.subTest(path=path):
                profiles = dict(small_profiles())
                profiles = copy.deepcopy(profiles)
                at(profiles, path)["bogus"] = 1
                self.assertProblem(toolchain.validate_profiles(profiles), "unknown key 'bogus'")

    def test_an_unknown_key_is_refused_at_every_level_of_the_lock(self):
        lock = synthetic_lock(small_manifest(), small_profiles())
        lock["packages"]["npm:@acme/tool"]["bogus"] = 1
        paths = [[], ["skill_sources", "src"], ["skill_sources", "src", "plugins", "core"],
                 ["skill_sources", "src", "plugins", "core", "skills", "alpha-core"], ["packages", "npm:@acme/tool"],
                 ["contracts", "npm-srv/online"], ["contracts", "npm-srv/online", "server"],
                 ["contracts", "npm-srv/online", "tools", "tool_a"], ["contracts", "hosted/default"]]
        for path in paths:
            with self.subTest(path=path):
                bad = copy.deepcopy(dict(synthetic_lock(small_manifest(), small_profiles())))
                at(bad, path)["bogus"] = 1
                self.assertProblem(toolchain.validate_lock(bad), "unknown key 'bogus'")
        unresolved = copy.deepcopy(dict(lock))
        unresolved["packages"]["npm:@acme/tool"] = {"status": "unresolved", "reason": "network", "detail": "", "bogus": 1}
        self.assertProblem(toolchain.validate_lock(unresolved), "unknown key 'bogus'")

    def test_a_bad_enum_value_is_refused(self):
        variant_path = ["mcp_servers", 0, "variants", "offline"]
        cases = [(["mcp_servers", 0], "transport", "ftp"), (["mcp_servers", 0], "status", "stable"),
                 (variant_path, "network", "lan"), (variant_path, "credentials", "token"), (variant_path, "access", "write"),
                 (variant_path, "unattended", "maybe"), (variant_path, "unattended", 1), (variant_path, "unattended", None),
                 (["mcp_servers", 0, "package"], "ecosystem", "gem"), (["mcp_servers", 0, "package"], "track", "^1.2.0"),
                 (["mcp_servers", 0, "package"], "track", "1.x"), (["mcp_servers", 0, "package"], "track", ""),
                 (["skill_sources", 0, "track"], "kind", "svn"), (["modes", "dev", "allow"], "unattended", "sometimes"),
                 (["modes", "dev", "allow"], "network", ["lan"]), (["mcp_servers", 3, "eula"], "accept", "user")]
        for path, key, value in cases:
            with self.subTest(path=path, key=key, value=value):
                manifest = small_manifest()
                at(manifest, path)[key] = value
                problems = toolchain.validate_manifest(manifest)
                self.assertTrue(any(key in p for p in problems), problems)

    def test_the_read_only_tools_flag_is_a_boolean_on_a_read_variant_of_a_stdio_server(self):
        flag = lambda path, value: (lambda m: (at(m, path).__setitem__("tools_read_only", value), m)[1])(small_manifest())
        self.assertEqual([], toolchain.validate_manifest(flag(["mcp_servers", 0, "variants", "offline"], True)))
        self.assertEqual([], toolchain.validate_manifest(flag(["mcp_servers", 0, "variants", "offline"], False)))
        for value in ("yes", 1, None):
            with self.subTest(value=value):
                self.assertProblem(toolchain.validate_manifest(flag(["mcp_servers", 0, "variants", "offline"], value)),
                                   "tools_read_only: '%s' is not true or false" % value)
        self.assertProblem(toolchain.validate_manifest(flag(["mcp_servers", 0, "variants", "writer"], True)),
                           'tools_read_only: only a variant with access "read" can promise read-only tools')
        self.assertProblem(toolchain.validate_manifest(flag(["mcp_servers", 5, "variants", "default"], True)),
                           "tools_read_only: an http variant cannot be checked")

    def test_an_unknown_mode_host_or_profile_mode_is_refused(self):
        manifest = small_manifest()
        manifest["modes"]["ops"] = copy.deepcopy(manifest["modes"]["dev"])
        manifest["hosts"]["emacs"] = copy.deepcopy(manifest["hosts"]["vscode"])
        problems = toolchain.validate_manifest(manifest)
        self.assertProblem(problems, "modes.ops: unknown mode")
        self.assertProblem(problems, "hosts.emacs: unknown host")
        profiles = copy.deepcopy(dict(small_profiles()))
        profiles["profiles"]["dev-a"]["mode"] = "ops"
        self.assertProblem(toolchain.validate_profiles(profiles), "mode")

    def test_a_wrong_type_is_refused(self):
        cases = [([], "schema", "1"), ([], "schema", True), ([], "schema", 2), (["tools", 0], "required", "yes"),
                 (["tools", 0], "version_args", "--version"), (["hosts", "copilot-cli"], "docs", "https://example.invalid/x"),
                 (["skill_sources", 0], "plugins", {}), (["mcp_servers", 0], "variants", []), (["mcp_servers", 0], "docs", "x"),
                 (["mcp_servers", 0, "variants", "offline"], "args", "--offline"), (["mcp_servers", 0], "env", []),
                 (["mcp_servers", 0, "launch"], "args", "-y"), ([], "quarantine", {}), ([], "mcp_servers", {}),
                 (["modes", "dev", "allow"], "access", "read")]
        for path, key, value in cases:
            with self.subTest(path=path, key=key, value=value):
                manifest = small_manifest()
                at(manifest, path)[key] = value
                self.assertTrue(toolchain.validate_manifest(manifest))
        self.assertTrue(toolchain.validate_manifest([]))
        self.assertTrue(toolchain.validate_profiles({"schema": 1, "profiles": []}))
        self.assertTrue(toolchain.validate_lock({"schema": 1}))

    def test_a_duplicate_id_is_refused(self):
        for key, index in (("mcp_servers", 0), ("tools", 0), ("skill_sources", 0), ("quarantine", 0)):
            with self.subTest(key=key):
                manifest = small_manifest()
                manifest[key].append(copy.deepcopy(manifest[key][index]))
                self.assertTrue(toolchain.validate_manifest(manifest))
        manifest = small_manifest()
        manifest["skill_sources"][0]["plugins"].append({"name": "core", "path": "plugins/other"})
        self.assertProblem(toolchain.validate_manifest(manifest), "duplicate plugin name")
        manifest = small_manifest()
        manifest["mcp_servers"].append(copy.deepcopy(manifest["mcp_servers"][0]))
        self.assertProblem(toolchain.validate_manifest(manifest), "duplicate server id")

    def test_a_variant_needs_all_four_attributes(self):
        for key in ("credentials", "network", "access", "unattended"):
            with self.subTest(key=key):
                manifest = small_manifest()
                del manifest["mcp_servers"][0]["variants"]["offline"][key]
                self.assertProblem(toolchain.validate_manifest(manifest), "missing key '%s'" % key)

    def test_the_transport_decides_what_a_server_needs(self):
        def problems(change):
            manifest = small_manifest()
            change(manifest)
            return toolchain.validate_manifest(manifest)
        self.assertProblem(problems(lambda m: m["mcp_servers"][0].pop("package")), "stdio server needs a 'package'")
        self.assertProblem(problems(lambda m: m["mcp_servers"][0].pop("launch")), "stdio server needs a 'launch'")
        self.assertProblem(problems(lambda m: m["mcp_servers"][4].pop("url")), "http server needs a url")
        self.assertProblem(problems(lambda m: m["mcp_servers"][4].update(package={"ecosystem": "npm", "name": "x", "track": "latest"})),
                           "http server must not have 'package'")
        self.assertProblem(problems(lambda m: m["mcp_servers"][0].update(url="https://x.example.invalid")), "stdio server must not have 'url'")
        self.assertProblem(problems(lambda m: m["mcp_servers"][4]["variants"]["default"].update(args=["x"])), "http variant")

    def test_a_launch_must_use_the_package_placeholder_and_a_variant_must_not(self):
        manifest = small_manifest()
        manifest["mcp_servers"][0]["launch"]["args"] = ["-y", "@acme/tool"]
        self.assertProblem(toolchain.validate_manifest(manifest), "{package}")
        manifest = small_manifest()
        manifest["mcp_servers"][0]["variants"]["offline"]["args"] = ["{package}"]
        self.assertProblem(toolchain.validate_manifest(manifest), "launch.args only")
        manifest = small_manifest()
        manifest["mcp_servers"][0]["launch"]["command"] = "npx -y"
        self.assertTrue(toolchain.validate_manifest(manifest))

    def test_a_credential_in_a_header_or_a_url_is_refused(self):
        manifest = small_manifest()
        manifest["mcp_servers"][4]["headers"]["Authorization"] = "x"
        self.assertProblem(toolchain.validate_manifest(manifest), "credential")
        for url in ("http://mcp.example.invalid/x", "https://" + "user:secret" + "@mcp.example.invalid/x", "https://mcp.example.invalid/x#frag", "mcp.example.invalid"):
            with self.subTest(url=url):
                manifest = small_manifest()
                manifest["mcp_servers"][4]["url"] = url
                self.assertTrue(toolchain.validate_manifest(manifest))
        manifest = small_manifest()
        manifest["skill_sources"][0]["repo"] = "file:///somewhere/repo.git"
        self.assertTrue(toolchain.validate_manifest(manifest))

    def test_a_path_that_leaves_the_project_is_refused(self):
        cases = [(["hosts", "copilot-cli"], "skills_project", "../outside"), (["hosts", "copilot-cli"], "mcp_project", "/etc/mcp.json"),
                 (["hosts", "copilot-cli"], "mcp_project", "C:/mcp.json"), (["hosts", "vscode"], "skills_project", ".github\\skills"),
                 (["hosts", "claude-code"], "mcp_user", "elsewhere/mcp.json"), (["hosts", "claude-code"], "skills_user", "$HOME/../x"),
                 ([], "store", "../pack"), (["skill_sources", 0, "plugins", 0], "path", "../plugins"),
                 (["hosts", "vscode"], "mcp_project", ".vscode//mcp.json")]
        for path, key, value in cases:
            with self.subTest(path=path, key=key, value=value):
                manifest = small_manifest()
                at(manifest, path)[key] = value
                self.assertTrue(toolchain.validate_manifest(manifest))
        profiles = copy.deepcopy(dict(small_profiles()))
        profiles["profiles"]["dev-a"]["instructions"] = ["../secret.md"]
        self.assertTrue(toolchain.validate_profiles(profiles))

    def test_a_package_declared_twice_with_different_tracks_is_refused(self):
        manifest = small_manifest()
        manifest["tools"][4]["package"] = {"ecosystem": "npm", "name": "@acme/tool", "track": "2.0.0"}
        self.assertProblem(toolchain.validate_manifest(manifest), "different track")

    def test_the_license_variable_must_be_passed_through_and_default_to_false(self):
        manifest = small_manifest()
        manifest["mcp_servers"][3]["env"][EULA_ENV]["default"] = "true"
        self.assertProblem(toolchain.validate_manifest(manifest), "default")
        manifest = small_manifest()
        del manifest["mcp_servers"][3]["env"][EULA_ENV]
        self.assertProblem(toolchain.validate_manifest(manifest), "pass %s through" % EULA_ENV)
        manifest = small_manifest()
        del manifest["mcp_servers"][3]["env"][EULA_ENV]["default"]
        self.assertProblem(toolchain.validate_manifest(manifest), "default")

    def test_the_default_profile_must_exist(self):
        self.small_project()
        self.rewrite_manifest(lambda m: m.update(default_profile="nope"))
        code, out, err = self.cli("verify")
        self.assertEqual(1, code)
        self.assertIn("default_profile 'nope' is not a profile", out)
        self.assertIsNotNone(toolchain.check_default_profile(self.manifest, self.profiles))

    def test_the_lock_is_validated_strictly(self):
        def problems(change):
            lock = copy.deepcopy(dict(synthetic_lock(small_manifest(), small_profiles())))
            change(lock)
            return toolchain.validate_lock(lock)
        self.assertProblem(problems(lambda l: l.update(schema=2)), "schema")
        self.assertProblem(problems(lambda l: l.update(generated="yesterday")), "generated")
        self.assertProblem(problems(lambda l: l.update(inputs_digest="sha256:abc")), "inputs_digest")
        self.assertProblem(problems(lambda l: l["skill_sources"]["src"].update(commit="main")), "commit")
        self.assertProblem(problems(lambda l: l["skill_sources"]["src"]["plugins"]["core"]["skills"]["alpha-core"].update(digest="md5:1")), "digest")
        self.assertProblem(problems(lambda l: l["skill_sources"]["src"]["plugins"]["core"]["skills"]["alpha-core"].update(files=-1)), "files")
        self.assertProblem(problems(lambda l: l["skill_sources"]["src"]["plugins"]["core"]["skills"]["alpha-core"].update(files=True)), "files")
        self.assertProblem(problems(lambda l: l["contracts"]["hosted/default"].update(status="mystery")), "status")
        self.assertProblem(problems(lambda l: l["packages"].__setitem__("rubygems:x", {"status": "resolved", "version": "1.0.0", "via": "x"})), "package key")
        self.assertProblem(problems(lambda l: l["contracts"].__setitem__("noslash", {"status": "needs-sign-in"})), "contract key")
        self.assertProblem(problems(lambda l: l["contracts"]["npm-srv/online"].update(era="future")), "era")
        self.assertProblem(problems(lambda l: l["contracts"]["npm-srv/online"]["tools"]["tool_a"].update(schema="x")), "schema")

    def test_a_reason_detail_may_not_hold_a_url_or_a_host(self):
        feed = "pkgs." + "contoso." + "invalid"
        for detail in ("see https://" + feed + "/x", "// " + feed, "fails at " + feed, "x" * 81, "bad;chars", "a@b"):
            with self.subTest(detail=detail):
                lock = copy.deepcopy(dict(synthetic_lock(small_manifest(), small_profiles())))
                lock["packages"]["npm:@acme/tool"] = {"status": "unresolved", "reason": "network", "detail": detail}
                self.assertTrue(toolchain.validate_lock(lock))
        lock = copy.deepcopy(dict(synthetic_lock(small_manifest(), small_profiles())))
        lock["packages"]["npm:@acme/tool"] = {"status": "unresolved", "reason": "network", "detail": "E404 version 1.6.0 not found"}
        self.assertEqual([], toolchain.validate_lock(lock))
        lock["packages"]["npm:@acme/tool"] = {"status": "unresolved", "reason": "internal-feed", "detail": ""}
        self.assertProblem(toolchain.validate_lock(lock), "reason")
        lock["contracts"]["hosted/default"] = {"status": "skipped", "reason": "skipped", "detail": "license not accepted"}
        lock["packages"]["npm:@acme/tool"] = {"status": "unresolved", "reason": "network", "detail": ""}
        self.assertEqual([], toolchain.validate_lock(lock))


class JsonFileTests(Base):
    def test_a_duplicate_key_is_an_error_not_a_silent_override(self):
        path = self.tmp / "toolchain.json"
        write(path, '{"schema": 1, "schema": 1}\n')
        with self.assertRaises(toolchain.ToolchainError) as caught:
            toolchain.load_manifest(path)
        self.assertIn("duplicate key", str(caught.exception))

    def test_a_byte_order_mark_and_crlf_are_accepted(self):
        text = toolchain.dump_json(small_manifest())
        path = self.tmp / "toolchain.json"
        write(path, b"\xef\xbb\xbf" + text.replace("\n", "\r\n").encode("utf-8"))
        self.assertEqual(small_manifest()["default_profile"], toolchain.load_manifest(path)["default_profile"])

    def test_bad_files_are_errors_not_crashes(self):
        path = self.tmp / "toolchain.json"
        with self.assertRaises(toolchain.ToolchainError):
            toolchain.load_manifest(self.tmp / "missing.json")
        for content in (b"not json", b'{"schema": NaN}', b"\xff\xfe\x00", b""):
            write(path, content)
            with self.assertRaises(toolchain.ToolchainError, msg=content):
                toolchain.load_manifest(path)

    def test_an_invalid_file_lists_every_problem_and_names_the_file(self):
        manifest = small_manifest()
        manifest["bogus"] = 1
        manifest["mcp_servers"][0]["transport"] = "ftp"
        path = self.tmp / "toolchain.json"
        write(path, toolchain.dump_json(manifest))
        with self.assertRaises(toolchain.ToolchainError) as caught:
            toolchain.load_manifest(path)
        self.assertGreaterEqual(len(caught.exception.problems), 2)
        self.assertTrue(all(p.startswith("toolchain.json: ") for p in caught.exception.problems))

    def test_a_write_is_atomic_and_uses_lf(self):
        path = self.tmp / "out" / "file.json"
        toolchain.write_atomic(path, "a\nb\n")
        self.assertEqual(b"a\nb\n", path.read_bytes())
        with mock.patch.object(os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                toolchain.write_atomic(path, "new\n")
        self.assertEqual(b"a\nb\n", path.read_bytes())
        self.assertEqual(["file.json"], sorted(p.name for p in path.parent.iterdir()))

    def test_the_json_output_is_deterministic(self):
        obj = {"b": [1, 2], "a": {"z": "\u00e9"}}
        self.assertEqual('{\n  "b": [\n    1,\n    2\n  ],\n  "a": {\n    "z": "\u00e9"\n  }\n}\n', toolchain.dump_json(obj))


# ---------------------------------------------------------------- the rules of the modes

class ModeRuleTests(Base):
    def problems(self, mode, *servers, skills=(), manifest=None, lock=None):
        manifest = manifest or small_manifest()
        profiles = toolchain.Profiles({"schema": 1, "profiles": {"p": {
            "mode": mode, "skills": list(skills), "mcp": [{"server": s, "variant": v} for s, v in servers], "instructions": []}}})
        lock = lock or synthetic_lock(manifest, profiles)
        return toolchain.check_profiles(manifest, profiles, lock)

    def test_an_offline_read_only_unattended_variant_is_valid_in_every_mode(self):
        for mode in toolchain.MODES:
            self.assertEqual([], self.problems(mode, ("npm-srv", "offline")), mode)

    def test_an_empty_profile_is_valid_and_asserts_load_nothing(self):
        for mode in toolchain.MODES:
            self.assertEqual([], self.problems(mode), mode)
        self.small_project()
        self.assertEqual([], toolchain.check_profiles(self.manifest, self.profiles, None, only=["agent-empty"]))
        self.assertEqual([], toolchain.resolve_profile(self.manifest, self.profiles, self.lock, "agent-empty")["mcp"])

    def test_a_networked_variant_is_refused_in_the_agent_mode(self):
        problems = self.problems("agent", ("npm-srv", "internet"))
        self.assertProblem(problems, "network 'internet' is not allowed in mode agent")
        self.assertEqual(1, len(problems), problems)

    def test_a_credentialed_variant_is_refused_in_the_agent_mode(self):
        for variant_name in ("gh", "entra"):
            problems = self.problems("agent", ("npm-srv", variant_name))
            self.assertProblem(problems, "credentials")
            self.assertEqual(1, len(problems), problems)

    def test_a_write_variant_is_refused_in_the_agent_mode(self):
        problems = self.problems("agent", ("npm-srv", "writer"))
        self.assertProblem(problems, "access 'read-write' is not allowed in mode agent")
        self.assertEqual(1, len(problems), problems)

    def test_a_variant_that_is_not_known_to_be_unattended_is_refused_where_unattended_is_required(self):
        for variant_name in ("manual", "unknown"):
            for mode in ("agent", "executor"):
                problems = self.problems(mode, ("npm-srv", variant_name))
                self.assertProblem(problems, "needs an unattended server")
                self.assertEqual(1, len(problems), problems)

    def test_the_executor_may_use_microsoft_cloud_and_azure_identity_but_nothing_more(self):
        self.assertEqual([], self.problems("executor", ("npm-srv", "online")))
        self.assertEqual([], self.problems("executor", ("py-srv", "default")))
        self.assertProblem(self.problems("executor", ("npm-srv", "internet")), "network 'internet'")
        self.assertProblem(self.problems("executor", ("npm-srv", "entra")), "credentials 'entra-delegated'")
        self.assertProblem(self.problems("executor", ("npm-srv", "gh")), "credentials 'github'")
        self.assertProblem(self.problems("executor", ("npm-srv", "writer")), "access 'read-write'")

    def test_a_hosted_signed_in_server_breaks_every_rule_at_once(self):
        problems = self.problems("agent", ("hosted", "default"))
        for attribute in ("network", "credentials", "access", "unattended"):
            self.assertProblem(problems, attribute)

    def test_the_dev_mode_allows_everything(self):
        every = [("npm-srv", v) for v in small_manifest()["mcp_servers"][0]["variants"]]
        self.assertEqual([], self.problems("dev", *every[:1]))
        for variant_name in small_manifest()["mcp_servers"][0]["variants"]:
            self.assertEqual([], self.problems("dev", ("npm-srv", variant_name)), variant_name)
        self.assertEqual([], self.problems("dev", ("hosted", "default")))

    def test_one_profile_may_not_list_a_server_twice(self):
        problems = self.problems("dev", ("npm-srv", "offline"), ("npm-srv", "online"))
        self.assertProblem(problems, "server 'npm-srv' is listed twice")

    def test_unknown_servers_variants_and_modes_are_refused(self):
        self.assertProblem(self.problems("dev", ("ghost", "default")), "server 'ghost' is not in the manifest")
        self.assertProblem(self.problems("dev", ("npm-srv", "ghost")), "has no variant 'ghost'")
        manifest = small_manifest()
        del manifest["modes"]["executor"]
        self.assertProblem(self.problems("executor", manifest=manifest), "mode 'executor' is not defined")

    def test_the_agent_mode_takes_skills_from_pinned_sources_only(self):
        skills = [{"source": "src", "plugin": "core", "names": ["alpha-core"]}]
        manifest = small_manifest()
        profiles = toolchain.Profiles({"schema": 1, "profiles": {"p": {"mode": "agent", "skills": skills, "mcp": [], "instructions": []}}})
        lock = copy.deepcopy(dict(synthetic_lock(manifest, profiles)))
        self.assertEqual([], toolchain.check_profiles(manifest, profiles, lock))
        del lock["skill_sources"]["src"]["commit"]
        self.assertProblem(toolchain.check_profiles(manifest, profiles, lock), "has no commit in the lock")
        lock["skill_sources"]["src"]["commit"] = "main"
        self.assertProblem(toolchain.check_profiles(manifest, profiles, lock), "has no commit in the lock")
        lock["skill_sources"]["src"]["commit"] = "1" * 40
        del lock["skill_sources"]["src"]["plugins"]["core"]["skills"]["alpha-core"]["digest"]
        self.assertProblem(toolchain.check_profiles(manifest, profiles, lock), "has no digest")
        dev = toolchain.Profiles({"schema": 1, "profiles": {"p": {"mode": "dev", "skills": skills, "mcp": [], "instructions": []}}})
        lock["skill_sources"]["src"]["commit"] = "main"
        self.assertEqual([], [p for p in toolchain.check_profiles(manifest, dev, lock) if "commit" in p])

    def test_the_instruction_files_must_exist(self):
        self.small_project()
        self.assertEqual([], toolchain.check_profiles(self.manifest, toolchain.load_profiles(self.root / "toolchain" / "profiles.json"), self.lock))
        (self.root / "toolchain" / "instructions" / "base.md").unlink()
        problems = toolchain.check_profiles(self.manifest, toolchain.load_profiles(self.root / "toolchain" / "profiles.json"), self.lock)
        self.assertProblem(problems, "instructions file 'instructions/base.md' does not exist")


# ---------------------------------------------------------------- skills and the quarantine

class QuarantineTests(Base):
    def skills(self, names, mode="dev", plugin="core"):
        manifest = small_manifest()
        profiles = toolchain.Profiles({"schema": 1, "profiles": {"p": {
            "mode": mode, "skills": [{"source": "src", "plugin": plugin, "names": names}], "mcp": [], "instructions": []}}})
        lock = synthetic_lock(manifest, profiles)
        return manifest, profiles, lock

    def test_a_wildcard_expands_to_the_plugin_minus_the_quarantine(self):
        manifest, profiles, lock = self.skills("*")
        self.assertIn("risky", lock["skill_sources"]["src"]["plugins"]["core"]["skills"])
        names = [s["name"] for s in toolchain.resolve_profile(manifest, profiles, lock, "p")["skills"]]
        self.assertEqual(["alpha-core", "beta-core"], names)

    def test_an_explicit_quarantined_name_is_an_error(self):
        manifest, profiles, lock = self.skills(["alpha-core", "risky"])
        problems = toolchain.check_profiles(manifest, profiles, lock)
        self.assertProblem(problems, "skill 'risky' of src is quarantined (retired format)")
        with self.assertRaises(toolchain.ToolchainError):
            toolchain.resolve_profile(manifest, profiles, lock, "p")

    def test_the_quarantine_holds_in_every_mode(self):
        for mode in toolchain.MODES:
            manifest, profiles, lock = self.skills(["risky"], mode=mode)
            self.assertProblem(toolchain.check_profiles(manifest, profiles, lock), "quarantined")

    def test_a_quarantine_names_a_source_of_the_manifest(self):
        manifest = small_manifest()
        manifest["quarantine"][0]["source"] = "ghost"
        self.assertProblem(toolchain.validate_manifest(manifest), "not a skill source")

    def test_the_real_quarantined_skill_never_reaches_a_profile(self):
        self.real_project()
        for name in self.profiles["profiles"]:
            resolved = toolchain.resolve_profile(self.manifest, self.profiles, self.lock, name, self.root / "toolchain")
            self.assertNotIn("fabriciq-ontology-cli", [s["name"] for s in resolved["skills"]], name)
        self.assertIn("fabriciq-ontology-cli", self.lock["skill_sources"]["skills-for-fabric"]["plugins"]["fabric-skills"]["skills"])


class SkillRuleTests(Base):
    def problems(self, selectors, lock_change=None, mode="dev"):
        manifest = small_manifest()
        profiles = toolchain.Profiles({"schema": 1, "profiles": {"p": {"mode": mode, "skills": selectors, "mcp": [], "instructions": []}}})
        lock = copy.deepcopy(dict(synthetic_lock(manifest, profiles)))
        if lock_change:
            lock_change(lock)
        return toolchain.check_profiles(manifest, profiles, lock), manifest, profiles, lock

    def test_a_skill_must_exist_in_the_lock(self):
        problems = self.problems([{"source": "src", "plugin": "core", "names": ["ghost"]}],
                                 lambda l: l["skill_sources"]["src"]["plugins"]["core"]["skills"].pop("ghost"))[0]
        self.assertProblem(problems, "skill 'ghost' is not in the lock for src/core")

    def test_a_source_and_a_plugin_must_exist_in_the_manifest_and_the_lock(self):
        self.assertProblem(self.problems([{"source": "ghost", "plugin": "core", "names": "*"}])[0], "skill source 'ghost' is not in the manifest")
        self.assertProblem(self.problems([{"source": "src", "plugin": "ghost", "names": "*"}])[0], "plugin 'ghost' is not a plugin")
        problems = self.problems([{"source": "src", "plugin": "core", "names": "*"}], lambda l: l["skill_sources"]["src"]["plugins"].pop("core"))[0]
        self.assertProblem(problems, "the lock has no entry for src/core")

    def test_the_same_skill_from_two_plugins_must_have_the_same_content(self):
        both = [{"source": "src", "plugin": "core", "names": ["shared"]}, {"source": "src", "plugin": "extra", "names": ["shared"]}]
        problems, manifest, profiles, lock = self.problems(both)
        self.assertEqual([], problems)
        resolved = toolchain.resolve_profile(manifest, profiles, lock, "p")
        self.assertEqual(["shared"], [s["name"] for s in resolved["skills"]])
        lock["skill_sources"]["src"]["plugins"]["extra"]["skills"]["shared"]["digest"] = "sha256:" + "0" * 64
        self.assertProblem(toolchain.check_profiles(manifest, profiles, lock), "skill 'shared' is selected from src/core and from src/extra with different content")

    def test_skills_without_a_lock_are_an_error_and_no_skills_are_not(self):
        manifest = small_manifest()
        profiles = small_profiles()
        self.assertProblem(toolchain.check_profiles(manifest, profiles, None, only=["dev-a"]), "no lock")
        self.assertEqual([], toolchain.check_profiles(manifest, profiles, None, only=["agent-empty"]))
        with self.assertRaises(toolchain.ToolchainError):
            toolchain.resolve_profile(manifest, profiles, None, "agent-empty")


# ---------------------------------------------------------------- packages and launch lines

class PackageTests(Base):
    def launch(self, server, variant_name, lock=None, manifest=None):
        manifest = manifest or small_manifest()
        lock = lock or synthetic_lock(manifest, small_profiles())
        return toolchain.server_launch(manifest, lock, server, variant_name)

    def test_the_package_is_expanded_for_npm_pypi_and_nuget(self):
        npm = self.launch("npm-srv", "online")
        self.assertEqual(("npx", ["-y", pin("@acme/tool", "1.6.0"), "--online"]), (npm["command"], npm["args"]))
        pypi = self.launch("py-srv", "default")
        self.assertEqual(("uvx", [pin("acme-py", "1.8.0"), "--all"]), (pypi["command"], pypi["args"]))
        nuget = self.launch("nuget-srv", "default")
        self.assertEqual(("dnx", [pin("Acme.Nuget", "0.5.0"), "--yes"]), (nuget["command"], nuget["args"]))

    def test_an_unscoped_npm_package_expands_to_name_and_version(self):
        manifest = small_manifest()
        manifest["mcp_servers"][0]["package"]["name"] = "plain-tool"
        launch = self.launch("npm-srv", "offline", manifest=manifest)
        self.assertEqual(["-y", pin("plain-tool", "1.6.0"), "--offline"], launch["args"])

    def test_the_server_env_is_merged_with_the_variant_env_and_the_variant_wins(self):
        manifest = small_manifest()
        manifest["mcp_servers"][0]["variants"]["online"]["env"]["ACME_MODE"] = {"from_env": "OTHER_MODE"}
        env = self.launch("npm-srv", "online", manifest=manifest)["env"]
        self.assertEqual({"ACME_MODE": {"from_env": "OTHER_MODE"}, "ACME_TARGET": {"from_env": "ACME_TARGET"}}, env)
        self.assertEqual({"ACME_MODE": {"from_env": "ACME_MODE", "default": "safe"}}, self.launch("npm-srv", "offline")["env"])

    def test_a_hosted_server_launches_with_its_url_and_headers_and_needs_no_lock(self):
        launch = toolchain.server_launch(small_manifest(), None, "hosted", "default")
        self.assertEqual(("http", None, [], "https://mcp.example.invalid/v1/mcp", {"X-VARIANTS": "Acme.V1"}),
                         (launch["transport"], launch["command"], launch["args"], launch["url"], launch["headers"]))

    def test_an_unresolved_or_missing_package_is_refused(self):
        manifest = small_manifest()
        lock = copy.deepcopy(dict(synthetic_lock(manifest, small_profiles())))
        lock["packages"]["npm:@acme/tool"] = {"status": "unresolved", "reason": "network", "detail": ""}
        with self.assertRaises(toolchain.ToolchainError) as caught:
            toolchain.server_launch(manifest, lock, "npm-srv", "offline")
        self.assertIn("package npm:@acme/tool is unresolved in the lock", str(caught.exception))
        del lock["packages"]["npm:@acme/tool"]
        with self.assertRaises(toolchain.ToolchainError) as caught:
            toolchain.server_launch(manifest, lock, "npm-srv", "offline")
        self.assertIn("is not in the lock", str(caught.exception))

    def test_a_floating_version_is_refused(self):
        manifest = small_manifest()
        for version in ("latest", "^1.6.0", "~1.6", "1.x", "*", ">=1.0.0", "1", "1.6", "1.6.0 || 2.0.0", "next", "main"):
            with self.subTest(version=version):
                lock = copy.deepcopy(dict(synthetic_lock(manifest, small_profiles())))
                lock["packages"]["npm:@acme/tool"]["version"] = version
                with self.assertRaises(toolchain.ToolchainError) as caught:
                    toolchain.server_launch(manifest, lock, "npm-srv", "offline")
                self.assertIn("no exact version", str(caught.exception))

    def test_an_exact_version_is_accepted_with_a_prerelease_or_build_suffix(self):
        manifest = small_manifest()
        for version in ("1.6.0", "0.3.20-beta.1", "10.0.0-rc.1+build.5", "2.0.0+20260101"):
            with self.subTest(version=version):
                lock = copy.deepcopy(dict(synthetic_lock(manifest, small_profiles())))
                lock["packages"]["npm:@acme/tool"]["version"] = version
                self.assertEqual(pin("@acme/tool", version), toolchain.server_launch(manifest, lock, "npm-srv", "offline")["args"][1])
        lock = copy.deepcopy(dict(synthetic_lock(manifest, small_profiles())))
        lock["packages"]["pypi:acme-py"]["version"] = "2024.1"
        self.assertEqual(pin("acme-py", "2024.1"), toolchain.server_launch(manifest, lock, "py-srv", "default")["args"][0])
        lock["packages"]["pypi:acme-py"]["version"] = "1.0rc1"
        self.assertEqual(pin("acme-py", "1.0rc1"), toolchain.server_launch(manifest, lock, "py-srv", "default")["args"][0])

    def test_a_pinned_package_must_resolve_to_its_pin(self):
        manifest = small_manifest()
        manifest["mcp_servers"][0]["package"]["track"] = "1.5.0"
        lock = synthetic_lock(manifest, small_profiles())
        self.assertEqual(pin("@acme/tool", "1.5.0"), toolchain.server_launch(manifest, lock, "npm-srv", "offline")["args"][1])
        lock = copy.deepcopy(dict(lock))
        lock["packages"]["npm:@acme/tool"]["version"] = "1.6.0"
        with self.assertRaises(toolchain.ToolchainError) as caught:
            toolchain.server_launch(manifest, lock, "npm-srv", "offline")
        self.assertIn("pinned to 1.5.0", str(caught.exception))

    def test_no_rendered_launch_line_holds_a_floating_word(self):
        self.real_project()
        for name in self.profiles["profiles"]:
            resolved = toolchain.resolve_profile(self.manifest, self.profiles, self.lock, name, self.root / "toolchain")
            for item in resolved["mcp"]:
                for arg in item["args"]:
                    self.assertNotRegex(arg, r"latest|next|\^|~|\*", (name, item["id"]))
                    self.assertNotIn("{package}", arg)


class InputsDigestTests(Base):
    def test_the_digest_is_deterministic_and_tracks_exactly_what_the_lock_depends_on(self):
        base = toolchain.inputs_digest(small_manifest())
        self.assertRegex(base, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(base, toolchain.inputs_digest(small_manifest()))

        def digest(change):
            manifest = small_manifest()
            change(manifest)
            return toolchain.inputs_digest(manifest)
        same = [lambda m: m["mcp_servers"][0].update(title="A new title"), lambda m: m["mcp_servers"][0]["variants"]["offline"].update(summary="x"),
                lambda m: m["modes"]["dev"].update(summary="x"), lambda m: m.update(about="changed text"),
                lambda m: m["mcp_servers"][0]["variants"]["offline"].update(network="internet")]
        for change in same:
            self.assertEqual(base, digest(change))
        different = [lambda m: m["mcp_servers"][0]["variants"]["offline"].update(args=["--other"]),
                     lambda m: m["quarantine"].append({"source": "src", "skill": "more", "reason": "x"}),
                     lambda m: m["quarantine"].clear(),
                     lambda m: m["mcp_servers"][0]["package"].update(track="1.5.0"),
                     lambda m: m["skill_sources"][0].update(track={"kind": "branch", "name": "main"}),
                     lambda m: m["tools"][4]["package"].update(name="other-cli"),
                     lambda m: m["skill_sources"][0]["plugins"].pop(),
                     lambda m: m["mcp_servers"].pop(1)]
        for change in different:
            self.assertNotEqual(base, digest(change))

    def test_the_digest_is_the_hash_of_the_canonical_json_of_the_four_inputs(self):
        manifest = small_manifest()
        payload = {"skill_sources": manifest["skill_sources"],
                   "packages": {"npm:@acme/tool": manifest["mcp_servers"][0]["package"], "npm:@acme/licensed": manifest["mcp_servers"][3]["package"],
                                "pypi:acme-py": manifest["mcp_servers"][1]["package"], "nuget:Acme.Nuget": manifest["mcp_servers"][2]["package"],
                                "pypi:acme-cli": manifest["tools"][4]["package"]},
                   "variants": {s["id"]: {v: spec.get("args", []) for v, spec in s["variants"].items()} for s in manifest["mcp_servers"]},
                   "quarantine": manifest["quarantine"]}
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        self.assertEqual("sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(), toolchain.inputs_digest(manifest))


NPM = pin("@acme/tool", "1.6.0")
LICENSED = pin("@acme/licensed", "1.6.0")
PY = pin("acme-py", "1.8.0")
NUGET = pin("Acme.Nuget", "0.5.0")


def golden(host):
    stdio = {"npm-srv": ("npx", ["-y", NPM, "--online"], {"ACME_MODE": ("safe", "ACME_MODE"), "ACME_TARGET": (None, "ACME_TARGET")}),
             "py-srv": ("uvx", [PY, "--all"], {}), "nuget-srv": ("dnx", [NUGET, "--yes"], {}),
             "licensed": ("npx", ["-y", LICENSED, "--start", "--readonly"], {EULA_ENV: ("false", EULA_ENV)})}
    servers = {}
    for sid, (command, args, env) in stdio.items():
        entry = {"type": "local" if host == "copilot-cli" else "stdio", "command": command, "args": args}
        if env:
            if host == "vscode":
                entry["env"] = {name: "${env:%s}" % source for name, (_default, source) in env.items()}
            else:
                entry["env"] = {name: "${%s:-%s}" % (source, default) if default else "${%s}" % source for name, (default, source) in env.items()}
        if host == "copilot-cli":
            entry["tools"] = ["*"]
        servers[sid] = entry
    servers["hosted"] = {"type": "http", "url": "https://mcp.example.invalid/v1/mcp", "headers": {"X-VARIANTS": "Acme.V1"}}
    servers["docs"] = {"type": "http", "url": "https://docs.example.invalid/mcp"}
    if host == "copilot-cli":
        servers["hosted"]["tools"] = servers["docs"]["tools"] = ["*"]
    order = ["npm-srv", "py-srv", "nuget-srv", "licensed", "hosted", "docs"]
    return {"servers" if host == "vscode" else "mcpServers": {sid: servers[sid] for sid in order}}


class RenderTests(Base):
    def setUp(self):
        super().setUp()
        self.small_project()

    def assertGolden(self, expected, actual):
        self.assertEqual(expected, actual)
        self.assertEqual(json.dumps(expected), json.dumps(actual), "the key order differs")

    def test_copilot_cli_gets_local_and_http_servers_with_tools_and_env_defaults(self):
        rendered = toolchain.render("copilot-cli", self.resolved())
        self.assertGolden(golden("copilot-cli"), rendered)
        self.assertEqual("${ACME_MODE:-safe}", rendered["mcpServers"]["npm-srv"]["env"]["ACME_MODE"])
        self.assertEqual("${ACME_TARGET}", rendered["mcpServers"]["npm-srv"]["env"]["ACME_TARGET"])
        self.assertEqual("${%s:-false}" % EULA_ENV, rendered["mcpServers"]["licensed"]["env"][EULA_ENV])
        self.assertEqual({"X-VARIANTS": "Acme.V1"}, rendered["mcpServers"]["hosted"]["headers"])
        self.assertNotIn("env", rendered["mcpServers"]["py-srv"])
        self.assertNotIn("headers", rendered["mcpServers"]["docs"])

    def test_vscode_gets_servers_stdio_and_env_references_without_defaults_or_tools(self):
        rendered = toolchain.render("vscode", self.resolved())
        self.assertGolden(golden("vscode"), rendered)
        self.assertEqual("${env:ACME_MODE}", rendered["servers"]["npm-srv"]["env"]["ACME_MODE"])
        self.assertTrue(all("tools" not in s for s in rendered["servers"].values()))

    def test_claude_code_gets_mcp_servers_stdio_and_env_defaults_without_tools(self):
        rendered = toolchain.render("claude-code", self.resolved())
        self.assertGolden(golden("claude-code"), rendered)
        self.assertEqual("${ACME_MODE:-safe}", rendered["mcpServers"]["npm-srv"]["env"]["ACME_MODE"])
        self.assertTrue(all("tools" not in s for s in rendered["mcpServers"].values()))

    def test_every_launch_line_holds_the_locked_exact_version(self):
        for host in toolchain.HOSTS:
            text = toolchain.dump_json(toolchain.render(host, self.resolved()))
            for spec in (NPM, LICENSED, PY, NUGET):
                self.assertIn(spec, text, (host, spec))
            self.assertNotIn("latest", text)

    def test_the_load_plan_holds_the_pinned_skills_servers_contracts_and_instructions(self):
        lock_file = self.root / "toolchain" / "toolchain.lock.json"
        expected_lock = "sha256:" + hashlib.sha256(lock_file.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for lock in (self.lock, toolchain.load_lock(lock_file)):
            resolved = toolchain.resolve_profile(self.manifest, self.profiles, lock, "agent-ok", self.root / "toolchain")
            plan = toolchain.render("load-plan", resolved)
            expected = {
                "schema": 1, "profile": "agent-ok", "mode": "agent", "lock": expected_lock,
                "skills": [{"name": "alpha-core", "source": "src", "plugin": "core", "commit": "1" * 40,
                            "path": "plugins/core/skills/alpha-core", "digest": skill_digest("alpha-core"), "store_path": "skills/alpha-core"}],
                "mcp": [{"id": "npm-srv", "variant": "offline", "transport": "stdio", "command": "npx", "args": ["-y", NPM, "--offline"],
                         "env": [{"name": "ACME_MODE", "from_env": "ACME_MODE", "default": "safe"}], "url": None, "headers": {},
                         "package": {"ecosystem": "npm", "name": "@acme/tool", "version": "1.6.0",
                                     "integrity": self.lock["packages"]["npm:@acme/tool"]["integrity"]},
                         "contract": self.lock["contracts"]["npm-srv/offline"]}],
                "instructions": [{"path": "instructions/base.md", "digest": toolchain.digest_text("# Preamble\n\nBe careful.\n")}],
            }
            self.assertGolden(expected, plan)

    def test_the_load_plan_describes_http_servers_pypi_hashes_and_env_without_default(self):
        plan = toolchain.render("load-plan", self.resolved())
        by_id = {m["id"]: m for m in plan["mcp"]}
        self.assertEqual([None, "https://mcp.example.invalid/v1/mcp", {"X-VARIANTS": "Acme.V1"}, [], None, {"status": "needs-sign-in"}],
                         [by_id["hosted"]["command"], by_id["hosted"]["url"], by_id["hosted"]["headers"], by_id["hosted"]["args"],
                          by_id["hosted"]["package"], by_id["hosted"]["contract"]])
        self.assertEqual({"ecosystem": "pypi", "name": "acme-py", "version": "1.8.0", "sha256": self.lock["packages"]["pypi:acme-py"]["sha256"]},
                         by_id["py-srv"]["package"])
        self.assertEqual({"ecosystem": "nuget", "name": "Acme.Nuget", "version": "0.5.0"}, by_id["nuget-srv"]["package"])
        self.assertIn({"name": "ACME_TARGET", "from_env": "ACME_TARGET", "default": None}, by_id["npm-srv"]["env"])
        self.assertEqual(["alpha-core", "beta-core", "gamma"], [s["name"] for s in plan["skills"]])

    def test_a_crlf_lock_and_crlf_instructions_give_the_same_load_plan(self):
        lf = toolchain.render("load-plan", self.resolved("agent-ok"))
        tdir = self.root / "toolchain"
        for name in ("toolchain.lock.json", "instructions/base.md"):
            path = tdir / name
            path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        lock = toolchain.load_lock(tdir / "toolchain.lock.json")
        crlf = toolchain.render("load-plan", toolchain.resolve_profile(self.manifest, toolchain.load_profiles(tdir / "profiles.json"), lock, "agent-ok"))
        self.assertEqual(lf, crlf)

    def test_the_output_follows_the_profile_order_and_an_empty_profile_renders_empty(self):
        self.assertEqual(["npm-srv", "py-srv", "nuget-srv", "licensed", "hosted", "docs"], list(toolchain.render("copilot-cli", self.resolved())["mcpServers"]))
        self.assertEqual({"mcpServers": {}}, toolchain.render("claude-code", self.resolved("agent-empty")))
        self.assertEqual({"servers": {}}, toolchain.render("vscode", self.resolved("agent-empty")))
        self.assertEqual([], toolchain.render("load-plan", self.resolved("agent-empty"))["skills"])

    def test_an_unknown_host_is_refused(self):
        with self.assertRaises(toolchain.ToolchainError):
            toolchain.render("emacs", self.resolved())

    def test_the_real_default_profile_renders_for_the_three_hosts(self):
        project = self.tmp / "real"
        project.mkdir()
        manifest, profiles, lock = copy_real_project(project)
        resolved = toolchain.resolve_profile(manifest, profiles, lock, "dev-factory", project / "toolchain")
        ids = ["fabric-local", "fabric-core", "fabric-iq", "powerbi-authoring-local", "fabric-sql", "azure-mcp", "microsoft-learn"]
        copilot = toolchain.render("copilot-cli", resolved)["mcpServers"]
        self.assertEqual(ids, list(copilot))
        self.assertEqual({"X-VARIANTS": "Fabric.Routing.FabricIQ.V1"}, copilot["fabric-iq"]["headers"])
        self.assertEqual("${PBI_MODELING_MCP_ACCEPT_EULA:-false}", copilot["powerbi-authoring-local"]["env"]["PBI_MODELING_MCP_ACCEPT_EULA"])
        self.assertEqual("${env:PBI_MODELING_MCP_ACCEPT_EULA}", toolchain.render("vscode", resolved)["servers"]["powerbi-authoring-local"]["env"]["PBI_MODELING_MCP_ACCEPT_EULA"])
        self.assertEqual(["-y", pin("@microsoft/fabric-mcp", "1.6.0"), "server", "start", "--mode", "all", "--read-only"], copilot["fabric-local"]["args"])
        for name in profiles["profiles"]:
            res = toolchain.resolve_profile(manifest, profiles, lock, name, project / "toolchain")
            for target in toolchain.RENDER_TARGETS:
                json.dumps(toolchain.render(target, res))

    def test_the_cli_prints_a_rendering_and_can_write_it_to_a_file(self):
        code, out, err = self.cli("render", "--profile", "dev-a", "--host", "vscode")
        self.assertEqual((0, ""), (code, err))
        self.assertEqual(toolchain.dump_json(golden("vscode")), out)
        target = self.tmp / "out.json"
        self.assertEqual(0, self.cli("render", "--profile", "dev-a", "--host", "claude-code", "--output", str(target))[0])
        self.assertEqual(toolchain.dump_json(golden("claude-code")).encode("utf-8"), target.read_bytes())
        self.assertEqual(toolchain.dump_json(golden("copilot-cli")), self.cli("render", "--host", "copilot-cli")[1])

    def test_write_project_writes_both_files_with_lf_and_is_idempotent(self):
        code, out, _ = self.cli("render", "--write-project")
        self.assertEqual(0, code)
        self.assertIn("wrote .github/mcp.json (profile dev-a)", out)
        self.assertIn("wrote .vscode/mcp.json (profile dev-a)", out)
        for rel, host in ((".github/mcp.json", "copilot-cli"), (".vscode/mcp.json", "vscode")):
            raw = (self.root / rel).read_bytes()
            self.assertNotIn(b"\r", raw)
            self.assertEqual(toolchain.dump_json(golden(host)).encode("utf-8"), raw)
        self.assertFalse((self.root / ".mcp.json").exists())
        again = self.cli("render", "--write-project")[1]
        self.assertIn("unchanged .github/mcp.json", again)

    def test_a_dev_profile_with_an_unresolved_package_does_not_render(self):
        self.rewrite_lock(lambda l: l["packages"].__setitem__("npm:@acme/tool", {"status": "unresolved", "reason": "network", "detail": ""}))
        code, out, err = self.cli("render", "--profile", "dev-a", "--host", "copilot-cli")
        self.assertEqual(1, code)
        self.assertIn("package npm:@acme/tool is unresolved in the lock", err)
        self.assertEqual("", out)
        self.assertEqual(1, self.cli("render", "--write-project")[0])
        self.assertFalse((self.root / ".github").exists())
        self.assertEqual(0, self.cli("render", "--profile", "agent-empty", "--host", "copilot-cli")[0])

    def test_a_stale_lock_is_refused(self):
        self.rewrite_manifest(lambda m: m["mcp_servers"][0]["variants"]["offline"].update(args=["--changed"]))
        code, out, err = self.cli("render", "--host", "copilot-cli")
        self.assertEqual(1, code)
        self.assertIn("the lock is stale", err)

    def test_render_needs_a_target(self):
        self.assertEqual(2, self.cli("render")[0])
        self.assertEqual(2, self.cli("render", "--profile", "nope", "--host", "vscode")[0])


# ---------------------------------------------------------------- verify

class VerifyTests(Base):
    def setUp(self):
        super().setUp()
        self.small_project()
        self.assertEqual(0, self.cli("render", "--write-project")[0])

    def verify(self, *args, deps=None):
        return self.cli("verify", *args, deps=deps)

    def test_a_valid_project_passes_without_the_network(self):
        code, out, err = self.verify("--offline")
        self.assertEqual((0, ""), (code, err), out)
        self.assertIn("Result: 0 failure(s), 0 warning(s)", out)
        self.assertIn("[PASS] V5: .github/mcp.json equals the rendering of profile dev-a", out)

    def test_the_real_manifest_and_profiles_pass_with_a_synthetic_lock(self):
        project = self.tmp / "real"
        project.mkdir()
        copy_real_project(project)
        self.assertEqual(0, self.cli("render", "--write-project", root=project)[0])
        code, out, err = self.cli("verify", root=project)
        self.assertEqual(0, code, out + err)
        self.assertIn("Result: 0 failure(s), 0 warning(s)", out)
        self.assertIn("profile dev-factory (mode dev) verifies", out)

    def test_the_output_is_deterministic_and_free_of_absolute_paths(self):
        first = self.verify()
        self.assertEqual(first, self.verify())
        for text in first[1:]:
            self.assertNotIn(str(self.tmp), text)
            self.assertNotIn(str(self.home), text)

    def test_v1_a_schema_error_is_a_failure_that_names_the_file_and_the_key(self):
        self.rewrite_manifest(lambda m: m["mcp_servers"][0].update(bogus=1))
        code, out, _ = self.verify()
        self.assertEqual(1, code)
        self.assertIn("[FAIL] V1: toolchain.json: mcp_servers.npm-srv: unknown key 'bogus'", out)

    def test_v1_a_broken_profiles_file_does_not_hide_the_other_checks(self):
        (self.root / "toolchain" / "profiles.json").write_text("{not json", encoding="utf-8")
        code, out, _ = self.verify()
        self.assertEqual(1, code)
        self.assertIn("[FAIL] V1: profiles.json: not valid JSON", out)
        self.assertIn("[PASS] V1: toolchain.json is valid", out)

    def test_a_missing_lock_is_a_failure_not_a_crash_and_v1_and_v6_still_run(self):
        (self.root / "toolchain" / "toolchain.lock.json").unlink()
        (self.root / "toolchain" / "instructions" / "base.md").unlink()
        code, out, err = self.verify()
        self.assertEqual(1, code)
        self.assertNotIn("Traceback", err)
        self.assertIn("[FAIL] V3: lock file missing: run `python scripts/toolchain.py lock`", out)
        self.assertIn("[PASS] V1: toolchain.json is valid", out)
        self.assertIn("[FAIL] V6: profile dev-a: instructions file 'instructions/base.md' does not exist", out)

    def test_a_missing_lock_does_not_repeat_itself_under_every_profile(self):
        (self.root / "toolchain" / "toolchain.lock.json").unlink()
        out = self.verify()[1]
        self.assertEqual(1, out.count("[FAIL]"), out)
        self.assertIn("so its skills and packages were not checked", out)

    def test_v2_a_rule_violation_names_the_profile_and_the_server(self):
        self.rewrite_profiles(lambda p: p["profiles"]["agent-ok"]["mcp"].__setitem__(0, {"server": "npm-srv", "variant": "online"}))
        code, out, _ = self.verify()
        self.assertEqual(1, code)
        self.assertIn("[FAIL] V2: profile agent-ok: server npm-srv/online: network 'microsoft-cloud' is not allowed in mode agent (allowed: none)", out)

    def test_v2_the_profile_selection_and_the_mode_filter(self):
        self.rewrite_profiles(lambda p: p["profiles"]["agent-ok"]["mcp"].__setitem__(0, {"server": "npm-srv", "variant": "online"}))
        self.assertEqual(0, self.verify("--profile", "dev-a")[0])
        self.assertEqual(1, self.verify("--profile", "dev-a", "agent-ok")[0])
        code, out, _ = self.verify("--mode", "agent")
        self.assertEqual(1, code)
        self.assertIn("profile agent-empty (mode agent) verifies", out)
        self.assertNotIn("profile dev-a", out)
        self.assertEqual(2, self.verify("--profile", "ghost")[0])

    def test_v3_a_stale_lock_fails(self):
        self.rewrite_manifest(lambda m: m["quarantine"].append({"source": "src", "skill": "more", "reason": "x"}))
        code, out, _ = self.verify()
        self.assertEqual(1, code)
        self.assertIn("[FAIL] V3: the lock is stale: the manifest changed since it was resolved", out)

    def test_v3_the_lock_must_cover_every_source_plugin_package_and_used_contract(self):
        def change(lock):
            del lock["skill_sources"]["src"]["plugins"]["extra"]
            del lock["packages"]["pypi:acme-py"]
            del lock["contracts"]["py-srv/default"]
        self.rewrite_lock(change)
        out = self.verify()[1]
        self.assertIn("the lock has no entry for plugin src/extra", out)
        self.assertIn("the lock has no entry for package pypi:acme-py", out)
        self.assertIn("profile dev-a: the lock has no contract entry for py-srv/default", out)
        self.rewrite_lock(lambda l: l["skill_sources"].pop("src"))
        self.assertIn("the lock has no entry for skill source src", self.verify()[1])

    def test_v3_an_unresolved_package_is_a_warning_in_dev_and_a_failure_in_agent_and_executor(self):
        self.rewrite_manifest(lambda m: m.update(default_profile="agent-empty"))
        self.assertEqual(0, self.cli("render", "--write-project")[0])
        unresolved = {"status": "unresolved", "reason": "network", "detail": "E404"}
        self.rewrite_lock(lambda l: l["packages"].__setitem__("npm:@acme/tool", unresolved))
        code, out, _ = self.verify("--profile", "dev-a")
        self.assertEqual(0, code, out)
        self.assertIn("[WARN] V3: profile dev-a: server npm-srv: package npm:@acme/tool is unresolved in the lock (network)", out)
        self.assertEqual(1, self.verify("--profile", "dev-a", "--strict")[0])
        code, out, _ = self.verify("--profile", "agent-ok")
        self.assertEqual(1, code)
        self.assertIn("[FAIL] V3: profile agent-ok: server npm-srv: package npm:@acme/tool is unresolved in the lock (network)", out)
        self.rewrite_profiles(lambda p: p["profiles"].update({"exec": {"mode": "executor", "skills": [], "instructions": [],
                                                                         "mcp": [{"server": "npm-srv", "variant": "online"}]}}))
        self.rewrite_lock(lambda l: l["contracts"].__setitem__("npm-srv/online", copy.deepcopy(self.lock["contracts"]["npm-srv/offline"])))
        out = self.verify("--profile", "exec")[1]
        self.assertIn("[FAIL] V3: profile exec: server npm-srv: package npm:@acme/tool is unresolved", out)

    def test_v4_a_floating_locked_version_is_a_failure_and_names_the_server(self):
        for version in ("latest", "^1.6.0"):
            self.rewrite_lock(lambda l: l["packages"]["npm:@acme/tool"].update(version=version))
            code, out, _ = self.verify("--profile", "dev-a")
            self.assertEqual(1, code, version)
            self.assertIn("[FAIL] V4: profile dev-a: server npm-srv/online: package npm:@acme/tool has no exact version in the lock", out)

    def test_v5_the_generated_project_files_must_exist_and_equal_the_rendering(self):
        self.assertEqual(0, self.verify()[0])
        (self.root / ".vscode" / "mcp.json").unlink()
        code, out, _ = self.verify()
        self.assertEqual(1, code)
        self.assertIn("[FAIL] V5: .vscode/mcp.json is missing (run: python scripts/toolchain.py render --write-project)", out)
        self.cli("render", "--write-project")
        path = self.root / ".github" / "mcp.json"
        path.write_text(path.read_text(encoding="utf-8").replace("--online", "--changed"), encoding="utf-8", newline="\n")
        code, out, _ = self.verify()
        self.assertEqual(1, code)
        self.assertIn("[FAIL] V5: .github/mcp.json differs from the rendering of profile dev-a (run: python scripts/toolchain.py render --write-project)", out)

    def test_v5_a_crlf_copy_of_a_generated_file_still_passes(self):
        for rel in (".github/mcp.json", ".vscode/mcp.json"):
            path = self.root / rel
            path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        lock = self.root / "toolchain" / "toolchain.lock.json"
        lock.write_bytes(lock.read_bytes().replace(b"\n", b"\r\n"))
        for name in ("toolchain.json", "profiles.json"):
            path = self.root / "toolchain" / name
            path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        code, out, _ = self.verify()
        self.assertEqual(0, code, out)
        (self.root / ".github" / "mcp.json").write_bytes(b"\xef\xbb\xbf" + toolchain.dump_json(golden("copilot-cli")).encode("utf-8"))
        self.assertEqual(0, self.verify()[0])

    def test_v5_only_concerns_the_default_profile_when_it_is_selected(self):
        (self.root / ".github" / "mcp.json").unlink()
        self.assertEqual(1, self.verify()[0])
        self.assertEqual(0, self.verify("--profile", "agent-ok")[0])

    def test_v6_an_instructions_path_must_be_a_regular_file(self):
        path = self.root / "toolchain" / "instructions" / "base.md"
        path.unlink()
        self.assertIn("[FAIL] V6: profile dev-a: instructions file 'instructions/base.md' does not exist", self.verify()[1])
        path.mkdir()
        self.assertIn("[FAIL] V6: profile dev-a: instructions 'instructions/base.md' is not a regular file", self.verify()[1])

    def test_v7_a_stale_quarantine_entry_is_a_warning(self):
        self.rewrite_lock(lambda l: l["skill_sources"]["src"]["plugins"]["core"]["skills"].pop("risky"))
        code, out, _ = self.verify()
        self.assertEqual(0, code)
        self.assertIn("[WARN] V7: quarantined skill src/risky is not in the lock any more", out)
        self.assertEqual(1, self.verify("--strict")[0])

    def test_v8_skill_findings_warn_in_dev_and_fail_in_agent(self):
        def change(lock):
            lock["skill_sources"]["src"]["plugins"]["core"]["skills"]["alpha-core"]["findings"] = ["name does not match folder"]
        self.rewrite_lock(change)
        code, out, _ = self.verify()
        self.assertEqual(1, code)
        self.assertIn("[WARN] V8: profile dev-a: skill src/core/alpha-core has findings: name does not match folder", out)
        self.assertIn("[FAIL] V8: profile agent-ok: skill src/core/alpha-core has findings: name does not match folder", out)

    def test_v8_install_steps_are_inert_in_agent_mode(self):
        self.rewrite_lock(lambda l: l["skill_sources"]["src"]["plugins"]["core"]["skills"]["alpha-core"].update(install_hints=2))
        code, out, _ = self.verify()
        self.assertEqual(0, code)
        self.assertIn("[WARN] V8: profile agent-ok: skill src/core/alpha-core has 2 install step(s), which are inert in agent mode", out)
        self.assertNotIn("profile dev-a: skill src/core/alpha-core has 2", out)

    def test_v11_a_captured_contract_needs_at_least_one_tool(self):
        self.rewrite_lock(lambda l: l["contracts"]["npm-srv/offline"].update(tools={}))
        code, out, _ = self.verify()
        self.assertEqual(1, code)
        self.assertIn("[FAIL] V11: contract npm-srv/offline is captured but lists no tool", out)

    def test_json_output_and_strict_mode(self):
        code, out, _ = self.verify("--json")
        report = json.loads(out)
        self.assertEqual((0, True, 0), (code, report["ok"], report["failures"]))
        self.rewrite_lock(lambda l: l["skill_sources"]["src"]["plugins"]["core"]["skills"].pop("risky"))
        report = json.loads(self.verify("--json", "--strict")[1])
        self.assertEqual((False, 1), (report["ok"], report["warnings"]))

    def test_offline_and_contracts_contradict_each_other(self):
        self.assertEqual(2, self.verify("--offline", "--contracts")[0])


class BundledNameTests(Base):
    """Copilot CLI 1.0.102 lets the server that a plugin bundles replace a project server of the same name, so the
    pinned server would silently become the unpinned one. The names that the locked plugins bundle are compared."""

    def setUp(self):
        super().setUp()
        self.small_project()
        self.assertEqual(0, self.cli("render", "--write-project")[0])
        self.path = self.root / "toolchain" / "toolchain.lock.json"

    def bundle(self, *names, plugin="core"):
        self.rewrite_lock(lambda l: l["skill_sources"]["src"]["plugins"][plugin].update(bundled_mcp=list(names)))

    def test_a_server_with_the_name_of_a_bundled_one_fails_for_every_profile_that_loads_it(self):
        self.bundle("npm-srv")
        code, out, _ = self.cli("verify")
        self.assertEqual(1, code)
        for profile in ("dev-a", "agent-ok"):
            self.assertIn("[FAIL] V12: profile %s: server npm-srv has the name of an MCP server that the plugin src/core bundles" % profile, out)
        self.assertIn("(rename it in toolchain.json)", out)
        self.assertNotIn("V12: profile agent-empty", out)

    def test_the_plugin_that_is_named_is_the_one_that_bundles_it(self):
        self.bundle("py-srv", plugin="extra")
        out = self.cli("verify")[1]
        self.assertIn("[FAIL] V12: profile dev-a: server py-srv has the name of an MCP server that the plugin src/extra bundles", out)

    def test_the_comparison_ignores_case(self):
        self.bundle("NPM-SRV")
        self.assertIn("[FAIL] V12: profile dev-a: server npm-srv ", self.cli("verify")[1])

    def test_a_server_id_with_capital_letters_is_compared_in_lower_case_too(self):
        self.rewrite_manifest(lambda m: [s.update(id="Docs") for s in m["mcp_servers"] if s["id"] == "docs"])
        self.rewrite_profiles(lambda p: [e.update(server="Docs") for e in p["profiles"]["dev-a"]["mcp"] if e["server"] == "docs"])
        self.bundle("docs")
        self.assertIn("[FAIL] V12: profile dev-a: server Docs has the name of an MCP server that the plugin src/core bundles", self.cli("verify")[1])

    def test_a_bundled_name_that_no_server_has_is_fine(self):
        self.bundle("FabricIQ", "other-name")
        code, out, _ = self.cli("verify")
        self.assertEqual(0, code, out)
        self.assertNotIn("V12", out)

    def test_only_the_servers_of_a_profile_are_compared(self):
        self.bundle("docs")
        out = self.cli("verify")[1]
        self.assertIn("[FAIL] V12: profile dev-a: server docs ", out)
        self.assertNotIn("V12: profile agent-ok", out)

    def test_a_plugin_that_lists_no_bundled_server_is_fine(self):
        self.rewrite_lock(lambda l: l["skill_sources"]["src"]["plugins"]["core"].pop("bundled_mcp"))
        code, out, _ = self.cli("verify")
        self.assertEqual(0, code, out)

    def test_an_update_that_introduces_a_clash_is_reported_and_is_not_written(self):
        up = Upstream(self.manifest, self.lock)
        up.plugins["plugins/core"]["bundled_mcp"] = ["hosted"]
        before = self.path.read_bytes()
        code, out, err = self.cli("update", "--write", deps=up.deps(self.home))
        self.assertEqual(1, code)
        self.assertIn("  profile dev-a (newly broken)", out.splitlines())
        self.assertIn("    server hosted has the name of an MCP server that the plugin src/core bundles", out)
        self.assertIn("not written: 1 profile(s) would not verify", err)
        self.assertEqual(before, self.path.read_bytes())

    def test_the_real_manifest_does_not_use_a_name_that_the_real_plugins_bundle(self):
        names = {"FabricIQ", "fabric-sqlendpoint", "powerbi-modeling-mcp", "azure", "azure-resource-manager-mcp"}
        manifest = toolchain.load_manifest(REAL / "toolchain.json")
        clash = sorted(s["id"] for s in manifest["mcp_servers"] if s["id"].lower() in {n.lower() for n in names})
        self.assertEqual([], clash)


class ReadOnlyToolsTests(Base):
    """A variant that promises read-only tools (its switch removes the writing ones) is held to it by the locked contract (V13)."""

    def setUp(self):
        super().setUp()
        manifest = small_manifest()
        manifest["mcp_servers"][0]["variants"]["offline"]["tools_read_only"] = True
        self.small_project(manifest=manifest)
        self.assertEqual(0, self.cli("render", "--write-project")[0])
        self.path = self.root / "toolchain" / "toolchain.lock.json"

    def spoil(self, tool="tool_b", key="offline"):
        self.rewrite_lock(lambda l: l["contracts"]["npm-srv/" + key]["tools"][tool].update(read_only=False))

    def test_a_contract_with_only_read_only_tools_passes(self):
        code, out, _ = self.cli("verify")
        self.assertEqual(0, code, out)
        self.assertNotIn("V13", out)

    def test_a_tool_that_is_not_read_only_fails_every_profile_that_loads_the_variant(self):
        self.spoil()
        code, out, _ = self.cli("verify")
        self.assertEqual(1, code)
        self.assertIn("[FAIL] V13: profile agent-ok: server npm-srv/offline is declared to list only read-only tools, "
                      "but its locked contract has 1 tool(s) that the server does not annotate read-only: tool_b", out)
        self.assertNotIn("V13: profile dev-a", out)

    def test_every_offending_tool_is_named_in_order(self):
        self.spoil("tool_b")
        self.spoil("tool_a")
        self.assertIn("has 2 tool(s) that the server does not annotate read-only: tool_a, tool_b", self.cli("verify")[1])

    def test_a_long_list_of_offenders_is_cut_after_eight(self):
        def many(lock):
            tools = lock["contracts"]["npm-srv/offline"]["tools"]
            for index in range(10):
                tools["writer_%02d" % index] = {"schema": "sha256:" + "%02d" % index * 32, "read_only": False, "destructive": True, "idempotent": False}
        self.rewrite_lock(many)
        out = self.cli("verify")[1]
        self.assertIn("has 10 tool(s) that the server does not annotate read-only: writer_00, writer_01, writer_02, writer_03, "
                      "writer_04, writer_05, writer_06, writer_07 (+2 more)", out)
        self.assertNotIn("writer_08", out)

    def test_a_variant_that_makes_no_promise_may_list_a_writing_tool(self):
        self.spoil(key="online")
        code, out, _ = self.cli("verify")
        self.assertEqual(0, code, out)
        self.assertNotIn("V13", out)

    def test_a_contract_that_was_not_captured_is_not_judged(self):
        self.rewrite_lock(lambda l: l["contracts"].__setitem__("npm-srv/offline", {"status": "unavailable", "reason": "exited", "detail": "code 1"}))
        code, out, _ = self.cli("verify")
        self.assertEqual(0, code, out)
        self.assertNotIn("V13", out)

    def test_an_update_that_brings_a_writing_tool_is_reported_and_is_not_written(self):
        up = Upstream(self.manifest, self.lock)
        up.tools["@acme/tool"]["tool_b"]["read_only"] = False
        before = self.path.read_bytes()
        code, out, err = self.cli("update", "--contracts", "--write", deps=up.deps(self.home, env={EULA_ENV: "true"}))
        self.assertEqual(1, code, out + err)
        self.assertIn("  profile agent-ok (newly broken)", out.splitlines())
        self.assertIn("server npm-srv/offline is declared to list only read-only tools", out)
        self.assertIn("not written: 1 profile(s) would not verify", err)
        self.assertEqual(before, self.path.read_bytes())


class ContractCheckTests(Base):
    def setUp(self):
        super().setUp()
        self.small_project()
        self.assertEqual(0, self.cli("render", "--write-project")[0])
        self.up = Upstream(self.manifest, self.lock)

    def verify(self, *args, env=None, upstream=None):
        deps = (upstream or self.up).deps(self.home, env=env)
        return self.cli("verify", "--contracts", "--profile", "dev-a", *args, deps=deps)

    def launched(self):
        return [call["argv"] for call in self.up.calls["probe_stdio"]]

    def test_matching_contracts_pass_and_every_stdio_variant_is_launched_with_the_locked_line(self):
        code, out, err = self.verify(env={EULA_ENV: "true"})
        self.assertEqual(0, code, out + err)
        self.assertEqual([["npx", "-y", NPM, "--online"], ["uvx", PY, "--all"], ["dnx", NUGET, "--yes"],
                          ["npx", "-y", LICENSED, "--start", "--readonly"]], self.launched())
        for key in ("npm-srv/online", "py-srv/default", "nuget-srv/default", "licensed/offline"):
            self.assertIn("[PASS] V10: contract %s matches the live server" % key, out)
        self.assertEqual([], self.up.calls["probe_http"])
        self.assertIn("[INFO] V10: contract hosted/default is needs-sign-in: a hosted server is not launched", out)

    def test_an_added_removed_or_changed_tool_is_a_failure(self):
        self.up.tools["@acme/tool"]["tool_c"] = {"schema": "sha256:" + "1" * 64, "read_only": True, "destructive": False, "idempotent": True}
        del self.up.tools["acme-py"]["tool_a"]
        self.up.tools["Acme.Nuget"]["tool_b"]["schema"] = "sha256:" + "2" * 64
        code, out, _ = self.verify(env={EULA_ENV: "true"})
        self.assertEqual(1, code)
        self.assertIn("[FAIL] V10: contract drift in npm-srv/online: tools added tool_c", out)
        self.assertIn("[FAIL] V10: contract drift in py-srv/default: tools removed tool_a", out)
        self.assertIn("[FAIL] V10: contract drift in nuget-srv/default: tools changed tool_b", out)

    def test_a_changed_annotation_is_drift_too(self):
        self.up.tools["@acme/tool"]["tool_a"]["read_only"] = False
        self.assertIn("tools changed tool_a", self.verify(env={EULA_ENV: "true"})[1])

    def test_a_server_whose_license_is_not_accepted_is_never_launched(self):
        for value in (None, "false", "1", "yes", " true", "", "tru", "accepted"):
            with self.subTest(value=value):
                self.up.calls["probe_stdio"].clear()
                code, out, _ = self.verify(env={} if value is None else {EULA_ENV: value})
                self.assertEqual(0, code, out)
                self.assertTrue(all(LICENSED not in " ".join(argv) for argv in self.launched()), self.launched())
                self.assertEqual(3, len(self.launched()))
                self.assertIn("[WARN] V10: contract licensed/offline was not checked: the license of licensed is not accepted (the operator sets %s)" % EULA_ENV, out)
        self.assertEqual(1, self.verify("--strict")[0])

    def test_a_server_whose_license_is_accepted_is_launched_whatever_the_case(self):
        for value in ("true", "TRUE", "True"):
            with self.subTest(value=value):
                self.up.calls["probe_stdio"].clear()
                self.assertEqual(0, self.verify(env={EULA_ENV: value})[0])
                self.assertEqual(4, len(self.launched()))
                licensed = [c for c in self.up.calls["probe_stdio"] if LICENSED in " ".join(c["argv"])][0]
                self.assertEqual(value, licensed["env"][EULA_ENV])

    def test_the_kit_never_sets_the_license_variable_or_passes_an_accept_flag(self):
        env = {EULA_ENV: "true"}
        self.verify(env=env)
        self.assertEqual({EULA_ENV: "true"}, env)
        others = [c for c in self.up.calls["probe_stdio"] if LICENSED not in " ".join(c["argv"])]
        self.assertTrue(others)
        for call in others:
            self.assertNotIn(EULA_ENV, call["env"])
        for argv in self.launched():
            self.assertFalse(any("accept" in a.lower() or "eula" in a.lower() for a in argv), argv)

    def test_the_probe_environment_holds_the_declared_defaults_and_the_operators_values(self):
        self.verify(env={"ACME_TARGET": "sandbox", "PATH": "/opt/fake/bin"})
        call = [c for c in self.up.calls["probe_stdio"] if NPM in " ".join(c["argv"])][0]
        self.assertEqual({"ACME_MODE": "safe", "ACME_TARGET": "sandbox", "PATH": "/opt/fake/bin"}, call["env"])

    def test_an_unavailable_or_skipped_contract_is_a_warning_and_is_not_launched(self):
        def change(lock):
            lock["contracts"]["py-srv/default"] = {"status": "unavailable", "reason": "install-blocked", "detail": ""}
            lock["contracts"]["nuget-srv/default"] = {"status": "skipped", "reason": "skipped", "detail": "contracts not captured"}
        self.rewrite_lock(change)
        code, out, _ = self.verify(env={EULA_ENV: "true"})
        self.assertEqual(0, code)
        self.assertIn("[WARN] V10: contract py-srv/default is unavailable (install-blocked)", out)
        self.assertIn("[WARN] V10: contract nuget-srv/default is skipped (contracts not captured)", out)
        self.assertEqual(2, len(self.launched()))

    def test_a_contract_captured_for_another_package_version_is_a_warning(self):
        self.rewrite_lock(lambda l: l["contracts"]["py-srv/default"].update(package_version="1.7.0"))
        code, out, _ = self.verify(env={EULA_ENV: "true"})
        self.assertEqual(0, code)
        self.assertIn("[WARN] V10: contract py-srv/default was captured for package version 1.7.0, not the locked one", out)
        self.assertTrue(all("acme-py" not in " ".join(a) for a in self.launched()))

    def test_a_probe_that_fails_is_a_failure_that_names_the_reason_only(self):
        feed = "pkgs." + "contoso." + "invalid"
        with mock.patch.object(self.up, "probe_stdio", side_effect=toolchain_mcp.McpProbeError("timeout: waited on " + feed)):
            code, out, _ = self.verify(env={EULA_ENV: "true"})
        self.assertEqual(1, code)
        self.assertIn("[FAIL] V10: contract npm-srv/online could not be checked: timeout", out)
        self.assertNotIn(feed, out)

    def test_without_the_flag_nothing_is_launched(self):
        deps = self.deps()
        self.assertEqual(0, self.cli("verify", deps=deps)[0])


class InstallTests(Base):
    def setUp(self):
        super().setUp()
        self.small_project()
        self.store = self.root / ".factory" / "pack"
        write_store(self.store, self.lock, ["alpha-core", "beta-core", "gamma"])
        self.runner = FakeRunner(found=["copilot", "code"])
        self.skills = self.root / ".github" / "skills"

    def install(self, *args, **deps_kw):
        deps_kw.setdefault("runner", self.runner)
        return self.cli("install", *args, deps=self.deps(**deps_kw))

    def marker(self, directory=None):
        return read_json((directory or self.skills) / toolchain.MARKER)

    @staticmethod
    def snapshot(root):
        return {p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns) for p in Path(root).rglob("*") if p.is_file()}

    def test_the_plan_prints_every_change_and_touches_nothing(self):
        before = self.snapshot(self.root)
        code, out, err = self.install()
        self.assertEqual((0, ""), (code, err))
        for line in ("+ skill alpha-core -> .github/skills/alpha-core", "+ skill gamma -> .github/skills/gamma", "+ skill router -> .github/skills/router",
                     "+ marker .github/skills/.toolchain-managed.json", "+ mcp copilot-cli .github/mcp.json", "+ mcp vscode .vscode/mcp.json",
                     "# skills folder .github/skills (copilot-cli, vscode)", "nothing was changed: add --apply to carry out the plan"):
            self.assertIn(line, out)
        self.assertNotIn("risky", out)
        self.assertEqual(before, self.snapshot(self.root))
        self.assertFalse((self.root / ".github").exists())

    def test_apply_copies_the_skills_and_writes_the_mcp_files_and_the_marker(self):
        code, out, err = self.install("--apply")
        self.assertEqual((0, ""), (code, err), out)
        for name in ("alpha-core", "beta-core", "gamma"):
            self.assertEqual(skill_files(name)["SKILL.md"], (self.skills / name / "SKILL.md").read_bytes())
            self.assertEqual(skill_files(name)["references/notes.md"], (self.skills / name / "references" / "notes.md").read_bytes())
        self.assertFalse((self.skills / "risky").exists())
        self.assertTrue((self.skills / "router" / "SKILL.md").is_file())
        lock_digest = "sha256:" + hashlib.sha256((self.root / "toolchain" / "toolchain.lock.json").read_bytes()).hexdigest()
        self.assertEqual({"profile": "dev-a", "lock": lock_digest,
                          "skills": {"alpha-core": skill_digest("alpha-core"), "beta-core": skill_digest("beta-core"), "gamma": skill_digest("gamma"),
                                     "router": tree_digest(self.root / "toolchain" / "skills" / "router")["digest"]}}, self.marker())
        self.assertEqual(toolchain.dump_json(golden("copilot-cli")), (self.root / ".github" / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(toolchain.dump_json(golden("vscode")), (self.root / ".vscode" / "mcp.json").read_text(encoding="utf-8"))
        self.assertFalse((self.root / ".mcp.json").exists())
        leftovers = [p.name for p in self.root.rglob("*") if p.name.startswith(".toolchain-new") or p.suffix == ".tmp"]
        self.assertEqual([], leftovers)
        self.assertFalse(any(p.is_symlink() for p in self.skills.rglob("*")))

    def test_a_second_apply_changes_nothing(self):
        self.assertEqual(0, self.install("--apply")[0])
        before = self.snapshot(self.root)
        code, out, _ = self.install("--apply")
        self.assertEqual(0, code)
        self.assertEqual(before, self.snapshot(self.root))
        self.assertNotRegex(out, r"(?m)^[+~!] ")
        self.assertIn("0 to add, 0 to change", out)
        self.assertIn("= skill alpha-core", out)

    def test_an_unmanaged_folder_is_a_conflict_that_is_not_overwritten_without_force(self):
        write(self.skills / "alpha-core" / "SKILL.md", "my own skill\n")
        code, out, _ = self.install("--apply")
        self.assertEqual(1, code)
        self.assertIn("! skill alpha-core: .github/skills/alpha-core exists and is not managed by the toolchain (use --force to replace it)", out)
        self.assertEqual(b"my own skill\n", (self.skills / "alpha-core" / "SKILL.md").read_bytes())
        self.assertTrue((self.skills / "beta-core" / "SKILL.md").is_file())
        self.assertNotIn("alpha-core", self.marker()["skills"])
        self.assertEqual(1, self.install("--apply")[0])
        code, out, _ = self.install("--apply", "--force")
        self.assertEqual(0, code, out)
        self.assertEqual(skill_files("alpha-core")["SKILL.md"], (self.skills / "alpha-core" / "SKILL.md").read_bytes())
        self.assertIn("alpha-core", self.marker()["skills"])

    def test_a_managed_skill_that_was_edited_is_repaired(self):
        self.install("--apply")
        (self.skills / "beta-core" / "SKILL.md").write_bytes(b"edited\n")
        code, out, _ = self.install()
        self.assertIn("~ skill beta-core: replace .github/skills/beta-core", out)
        self.install("--apply")
        self.assertEqual(skill_files("beta-core")["SKILL.md"], (self.skills / "beta-core" / "SKILL.md").read_bytes())

    def test_a_skill_that_left_the_profile_is_removed_but_foreign_folders_stay(self):
        self.install("--apply")
        write(self.skills / "mine" / "SKILL.md", "mine\n")
        code, out, _ = self.install("--apply", "--profile", "agent-ok")
        self.assertEqual(0, code, out)
        self.assertIn("~ skill beta-core: remove it, it left the profile", out)
        self.assertEqual(["alpha-core", "mine", "router"], sorted(p.name for p in self.skills.iterdir() if p.is_dir()))
        self.assertEqual({"alpha-core", "router"}, set(self.marker()["skills"]))
        self.assertEqual("agent-ok", self.marker()["profile"])
        self.assertEqual(toolchain.dump_json(toolchain.render("copilot-cli", self.resolved("agent-ok"))), (self.root / ".github" / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(0, self.install("--apply", "--profile", "agent-empty")[0])
        self.assertEqual(["mine"], sorted(p.name for p in self.skills.iterdir() if p.is_dir()))
        self.assertEqual({}, self.marker()["skills"])

    def test_an_mcp_file_that_is_not_a_rendering_is_a_conflict_with_a_diff(self):
        write(self.root / ".github" / "mcp.json", '{"mcpServers": {"mine": {"type": "local", "command": "x", "args": [], "tools": ["*"]}}}\n')
        code, out, _ = self.install("--apply", "--skip-skills")
        self.assertEqual(1, code)
        self.assertIn("! mcp copilot-cli .github/mcp.json differs from every rendering of the toolchain (use --force to replace it)", out)
        self.assertRegex(out, r"(?m)^    [-+].*\"mine\"")
        self.assertIn('"mine"', (self.root / ".github" / "mcp.json").read_text(encoding="utf-8"))
        self.assertTrue((self.root / ".vscode" / "mcp.json").is_file())
        self.assertEqual(0, self.install("--apply", "--skip-skills", "--force")[0])
        self.assertEqual(toolchain.dump_json(golden("copilot-cli")), (self.root / ".github" / "mcp.json").read_text(encoding="utf-8"))

    def test_an_mcp_file_that_equals_another_profiles_rendering_is_replaced_and_crlf_is_equal(self):
        other = toolchain.dump_json(toolchain.render("copilot-cli", self.resolved("agent-ok")))
        write(self.root / ".github" / "mcp.json", other.replace("\n", "\r\n"))
        code, out, _ = self.install("--skip-skills")
        self.assertIn("~ mcp copilot-cli .github/mcp.json: replace the rendering of another profile", out)
        same = toolchain.dump_json(golden("copilot-cli")).replace("\n", "\r\n")
        write(self.root / ".github" / "mcp.json", same)
        self.assertIn("= mcp copilot-cli .github/mcp.json", self.install("--skip-skills")[1])

    def test_the_user_scope_merges_into_the_users_mcp_file(self):
        target = self.home / ".copilot" / "mcp-config.json"
        wanted = golden("copilot-cli")["mcpServers"]
        existing = {"theme": "dark", "mcpServers": {"foreign": {"type": "local", "command": "x", "args": [], "tools": ["*"]},
                                                      "docs": {"type": "http", "url": "https://other.example.invalid/mcp", "tools": ["*"]},
                                                      "py-srv": wanted["py-srv"]}}
        write(target, toolchain.dump_json(existing))
        original = target.read_bytes()
        code, out, err = self.install("--apply", "--scope", "user", "--host", "copilot-cli", "--skip-skills")
        self.assertEqual((1, ""), (code, err), out)
        self.assertIn("! mcp-user copilot-cli $HOME/.copilot/mcp-config.json: server docs differs (use --force to replace it)", out)
        self.assertIn("= mcp-user copilot-cli $HOME/.copilot/mcp-config.json: server py-srv is unchanged", out)
        self.assertIn("+ mcp-user copilot-cli $HOME/.copilot/mcp-config.json: add server npm-srv", out)
        merged = read_json(target)
        self.assertEqual("dark", merged["theme"])
        self.assertEqual(existing["mcpServers"]["foreign"], merged["mcpServers"]["foreign"])
        self.assertEqual(existing["mcpServers"]["docs"], merged["mcpServers"]["docs"])
        for sid in ("npm-srv", "nuget-srv", "licensed", "hosted"):
            self.assertEqual(wanted[sid], merged["mcpServers"][sid])
        backup = target.with_name("mcp-config.json.bak-" + STAMP)
        self.assertEqual(original, backup.read_bytes())
        self.assertNotIn(b"\r", target.read_bytes())
        self.assertEqual(1, len(list(target.parent.glob("*.bak-*"))))
        before = self.snapshot(self.home)
        self.assertEqual(1, self.install("--apply", "--scope", "user", "--host", "copilot-cli", "--skip-skills")[0])
        self.assertEqual(before, self.snapshot(self.home))
        forced = target.read_bytes()
        code, out, _ = self.install("--apply", "--scope", "user", "--host", "copilot-cli", "--skip-skills", "--force")
        self.assertEqual(0, code, out)
        self.assertEqual(wanted["docs"], read_json(target)["mcpServers"]["docs"])
        self.assertEqual(wanted["docs"], read_json(target)["mcpServers"]["docs"])
        self.assertEqual(forced, target.with_name("mcp-config.json.bak-%s-1" % STAMP).read_bytes())
        self.assertEqual(0, self.install("--apply", "--scope", "user", "--host", "copilot-cli", "--skip-skills")[0])
        self.assertEqual(2, len(list(target.parent.glob("*.bak-*"))))

    def test_a_new_user_file_needs_no_backup_and_a_broken_one_is_left_alone(self):
        target = self.home / ".copilot" / "mcp-config.json"
        self.assertEqual(0, self.install("--apply", "--scope", "user", "--host", "copilot-cli", "--skip-skills")[0])
        self.assertEqual(golden("copilot-cli"), read_json(target))
        self.assertEqual([], list(target.parent.glob("*.bak-*")))
        target.write_text("{broken", encoding="utf-8")
        code, out, err = self.install("--apply", "--scope", "user", "--host", "copilot-cli", "--skip-skills")
        self.assertEqual(1, code)
        self.assertEqual("{broken", target.read_text(encoding="utf-8"))
        self.assertIn("not valid JSON", err)

    def test_the_user_scope_installs_skills_into_the_home_folder_and_vscode_has_no_user_mcp_file(self):
        code, out, _ = self.install("--apply", "--scope", "user", "--host", "copilot-cli", "vscode")
        self.assertEqual(0, code, out)
        self.assertTrue((self.home / ".copilot" / "skills" / "alpha-core" / "SKILL.md").is_file())
        self.assertEqual("dev-a", self.marker(self.home / ".copilot" / "skills")["profile"])
        self.assertFalse((self.root / ".github").exists())
        self.assertIn("# vscode has no user MCP file in this version; use --scope project", out)
        self.assertIn("$HOME/.copilot/skills", out)
        self.assertNotIn(str(self.home), out)

    def test_the_default_hosts_are_the_ones_on_path(self):
        code, out, _ = self.install("--skip-skills", runner=FakeRunner(found=["claude"]))
        self.assertIn("+ mcp claude-code .mcp.json", out)
        self.assertNotIn("copilot-cli", out)
        code, out, _ = self.install(runner=FakeRunner())
        self.assertEqual(2, code)
        self.assertIn("no host found", out)
        self.assertEqual(0, self.install("--host", "claude-code", runner=FakeRunner())[0])
        self.assertEqual(2, self.install("--host", "emacs", runner=FakeRunner())[0])

    def test_skip_flags(self):
        out = self.install("--skip-mcp")[1]
        self.assertNotIn("mcp", out.replace("--skip-mcp", ""))
        self.assertIn("skill alpha-core", out)
        out = self.install("--skip-skills")[1]
        self.assertNotIn("skill ", out)
        self.assertIn("mcp copilot-cli", out)

    def test_the_store_is_fetched_when_it_is_missing_or_stale_and_only_then(self):
        calls = []

        def vendor(lock, selection, store, runner, quarantine=()):
            calls.append((selection, quarantine))
            write_store(store, lock, [s[2] for s in selection])
            return {}
        shutil.rmtree(self.store)
        code, out, _ = self.install("--skip-mcp", vendor_skills=vendor)
        self.assertIn("+ store .factory/pack: fetch 3 skill(s) (the local pack has no MANIFEST.json)", out)
        self.assertEqual([], calls)
        self.assertEqual(0, self.install("--apply", "--skip-mcp", vendor_skills=vendor)[0])
        self.assertEqual([([("src", "core", "alpha-core"), ("src", "core", "beta-core"), ("src", "extra", "gamma")], ("risky",))], calls)
        self.assertIn("= store .factory/pack is current", self.install("--skip-mcp")[1])
        self.assertEqual(0, self.install("--apply", "--skip-mcp")[0])
        (self.store / "skills" / "gamma" / "SKILL.md").write_bytes(b"tampered\n")
        self.assertIn("+ store", self.install("--skip-mcp")[1])
        self.assertEqual(0, self.install("--apply", "--skip-mcp", vendor_skills=vendor)[0])
        self.assertEqual(2, len(calls))

    def test_a_fetch_that_leaves_the_store_unusable_stops_before_any_copy(self):
        shutil.rmtree(self.store)
        code, out, err = self.install("--apply", "--skip-mcp", vendor_skills=lambda *a, **k: {})
        self.assertEqual(1, code)
        self.assertIn("still not usable", err)
        self.assertFalse(self.skills.exists())

    def test_a_failed_vendor_reports_a_sanitised_reason(self):
        shutil.rmtree(self.store)
        feed = "pkgs." + "contoso." + "invalid"

        def vendor(*args, **kwargs):
            raise toolchain_sources.SourceError("network: could not reach https://%s/repo" % feed)
        code, out, err = self.install("--apply", "--skip-mcp", vendor_skills=vendor)
        self.assertEqual(1, code)
        self.assertNotIn(feed, err)
        self.assertIn("fetch failed", err)

    def test_a_copy_that_does_not_match_the_locked_digest_is_refused(self):
        def digest(path):
            if Path(path).name.startswith(".toolchain-new-"):
                return {"digest": "sha256:" + "0" * 64, "files": 1, "bytes": 1}
            return tree_digest(path)
        code, out, err = self.install("--apply", "--skip-mcp", digest_tree=digest)
        self.assertEqual(1, code)
        self.assertIn("the copy does not match its locked digest", err)
        self.assertEqual([], [p.name for p in self.skills.iterdir() if p.is_dir()])
        self.assertFalse((self.skills / toolchain.MARKER).exists())

    def test_a_symbolic_link_in_the_store_is_refused(self):
        folder = self.store / "skills" / "gamma"
        write(folder / "link.md", "stands in for a link\n")
        with mock.patch.object(Path, "is_symlink", lambda self: self.name == "link.md"):
            with self.assertRaises(toolchain.ToolchainError) as caught:
                toolchain.copy_tree(folder, self.tmp / "copy")
        self.assertIn("symbolic link", str(caught.exception))

    def test_an_unreadable_marker_makes_every_existing_folder_a_conflict(self):
        write(self.skills / toolchain.MARKER, "{broken")
        write(self.skills / "alpha-core" / "SKILL.md", "mine\n")
        code, out, _ = self.install("--skip-mcp")
        self.assertIn("! skill alpha-core", out)
        self.assertIn("~ marker", out)

    def test_a_stale_lock_is_refused(self):
        self.rewrite_manifest(lambda m: m["quarantine"].clear())
        code, out, err = self.install()
        self.assertEqual(1, code)
        self.assertIn("the lock is stale", err)

    def test_a_repo_owned_skill_may_not_shadow_a_locked_one(self):
        write(self.root / "toolchain" / "skills" / "alpha-core" / "SKILL.md", "shadow\n")
        code, out, err = self.install("--apply", "--skip-mcp")
        self.assertEqual(1, code)
        self.assertIn("same name as a locked skill", err)

    def test_an_empty_profile_installs_nothing_not_even_the_router(self):
        code, out, _ = self.install("--profile", "agent-empty", "--skip-mcp")
        self.assertEqual(0, code)
        self.assertNotIn("router", out)
        self.assertNotIn("marker", out)

    def test_live_verification_follows_the_installed_state(self):
        self.assertEqual(0, self.install("--apply", "--host", "copilot-cli", "vscode")[0])
        deps = self.deps(runner=self.runner)
        code, out, _ = self.cli("verify", "--live", "--host", "copilot-cli", "vscode", deps=deps)
        self.assertEqual(0, code, out)
        self.assertIn("[INFO] V9: live checks done for 2 host(s)", out)
        (self.skills / "gamma" / "SKILL.md").write_bytes(b"edited\n")
        code, out, _ = self.cli("verify", "--live", "--host", "copilot-cli", deps=deps)
        self.assertEqual(1, code)
        self.assertIn("[FAIL] V9: managed skill gamma in .github/skills differs from its recorded digest", out)
        self.install("--apply")
        shutil.rmtree(self.skills / "beta-core")
        self.assertIn("[FAIL] V9: managed skill beta-core is missing from .github/skills", self.cli("verify", "--live", "--host", "vscode", deps=deps)[1])
        self.install("--apply")
        marker = self.marker()
        marker["lock"] = "sha256:" + "0" * 64
        write(self.skills / toolchain.MARKER, toolchain.dump_json(marker))
        self.assertIn("[FAIL] V9: .github/skills was installed from another lock: the marker is stale", self.cli("verify", "--live", "--host", "copilot-cli", deps=deps)[1])
        self.install("--apply", "--force")
        mcp = read_json(self.root / ".github" / "mcp.json")
        del mcp["mcpServers"]["hosted"]
        mcp["mcpServers"]["docs"]["url"] = "https://changed.example.invalid/mcp"
        write(self.root / ".github" / "mcp.json", toolchain.dump_json(mcp))
        out = self.cli("verify", "--live", "--host", "copilot-cli", deps=deps)[1]
        self.assertIn("[FAIL] V9: .github/mcp.json lacks the server hosted", out)
        self.assertIn("[FAIL] V9: .github/mcp.json holds a different entry for the server docs", out)

    def test_live_verification_fails_when_nothing_is_installed(self):
        deps = self.deps(runner=self.runner)
        code, out, _ = self.cli("verify", "--live", "--host", "copilot-cli", deps=deps)
        self.assertEqual(1, code)
        self.assertIn("[FAIL] V9: .github/skills has no managed skills marker", out)
        self.assertIn("[FAIL] V9: .github/mcp.json is missing", out)

    def test_live_verification_checks_the_local_pack_and_the_user_files(self):
        self.install("--apply", "--host", "copilot-cli", "vscode")
        write(self.home / ".copilot" / "mcp-config.json", toolchain.dump_json({"mcpServers": {"py-srv": {"type": "local", "command": "other", "args": []}}}))
        deps = self.deps(runner=self.runner)
        out = self.cli("verify", "--live", "--host", "copilot-cli", deps=deps)[1]
        self.assertIn("[WARN] V9: $HOME/.copilot/mcp-config.json holds a different entry for the server py-srv", out)
        (self.store / "skills" / "gamma" / "SKILL.md").write_bytes(b"tampered\n")
        code, out, _ = self.cli("verify", "--live", "--host", "copilot-cli", deps=deps)
        self.assertEqual(1, code)
        self.assertIn("[FAIL] V9: profile dev-a: the local pack holds skill gamma with content that differs from the lock", out)


class DoctorTests(Base):
    ACCOUNT = "someone-account-name"

    def setUp(self):
        super().setUp()
        self.small_project()
        self.assertEqual(0, self.cli("render", "--write-project")[0])

    def machine(self, found=("git", "python", "gh", "az", "copilot"), answers=None):
        table = dict(GOOD_TOOLS)
        table.update(answers or {})
        return FakeRunner(found=found, answers=table)

    def doctor(self, *args, runner=None, **deps_kw):
        deps_kw.setdefault("runner", runner or self.machine())
        deps_kw.setdefault("probe_http", lambda url, headers=None, runner=None, timeout=15: {"status": "open", "http_status": 200})
        return self.cli("doctor", *args, deps=self.deps(**deps_kw))

    def test_a_healthy_machine_reports_each_check_and_exits_zero(self):
        code, out, err = self.doctor()
        self.assertEqual((0, ""), (code, err), out)
        for line in ("[PASS] tool git: version 2.43.0 (minimum 2.30)", "[PASS] tool python: version 3.11.9 (minimum 3.10)",
                     "[PASS] host copilot-cli: found on PATH", "[INFO] host vscode: not found on PATH (code)",
                     "[PASS] sign-in gh: signed in", "[PASS] sign-in az: signed in", "[PASS] lock: present, valid and fresh (generated 2026-10-01)",
                     "[PASS] host copilot-cli mcp: .github/mcp.json equals the rendering of profile dev-a"):
            self.assertIn(line, out)
        self.assertIn("[INFO] contracts: profile dev-a uses 6: 4 captured, 1 needs-sign-in, 1 open", out)

    def test_a_missing_required_tool_fails_and_a_missing_optional_tool_only_warns(self):
        code, out, _ = self.doctor(runner=self.machine(found=("python", "gh", "az")))
        self.assertEqual(1, code)
        self.assertIn("[FAIL] tool git: not found on PATH; needed for everything", out)
        code, out, _ = self.doctor(runner=self.machine(found=("git", "python", "gh")))
        self.assertEqual(0, code)
        self.assertIn("[WARN] tool az: not found on PATH; needed for sign-in", out)
        self.assertIn("[WARN] tool fab: not found on PATH; needed for the CLI", out)

    def test_a_version_below_the_minimum_fails_a_required_tool_and_warns_for_an_optional_one(self):
        code, out, _ = self.doctor(runner=self.machine(answers={("git", "--version"): (0, "git version 2.20.1\n", "")}))
        self.assertEqual(1, code)
        self.assertIn("[FAIL] tool git: version 2.20.1 is older than the minimum 2.30; needed for everything", out)
        code, out, _ = self.doctor(runner=self.machine(answers={("gh", "--version"): (0, "gh version 2.10.0\n", "")}))
        self.assertEqual(0, code)
        self.assertIn("[WARN] tool gh: version 2.10.0 is older than the minimum 2.40", out)
        code, out, _ = self.doctor(runner=self.machine(answers={("git", "--version"): (0, "garbled\n", "")}))
        self.assertEqual(0, code)
        self.assertIn("[WARN] tool git: found, but its version could not be read", out)
        code, out, _ = self.doctor(runner=self.machine(answers={("git", "--version"): (0, "git version 2.30\n", "")}))
        self.assertIn("[PASS] tool git: version 2.30", out)

    def test_an_alternative_command_counts(self):
        runner = FakeRunner(found=["git", "python3"], answers=dict(GOOD_TOOLS, **{}))
        runner.answers[("python3", "--version")] = (0, "Python 3.12.1\n", "")
        self.assertIn("[PASS] tool python: version 3.12.1", self.doctor(runner=runner)[1])

    def test_the_lock_must_be_present_valid_and_fresh(self):
        self.rewrite_manifest(lambda m: m["quarantine"].append({"source": "src", "skill": "more", "reason": "x"}))
        code, out, _ = self.doctor()
        self.assertEqual(1, code)
        self.assertIn("[FAIL] lock: stale: the manifest changed since it was resolved (run `python scripts/toolchain.py lock`)", out)
        (self.root / "toolchain" / "toolchain.lock.json").unlink()
        code, out, _ = self.doctor()
        self.assertEqual(1, code)
        self.assertIn("[FAIL] lock: missing: run `python scripts/toolchain.py lock`", out)
        write(self.root / "toolchain" / "toolchain.lock.json", '{"schema": 1}\n')
        code, out, _ = self.doctor()
        self.assertEqual(1, code)
        self.assertIn("[FAIL] lock: invalid", out)

    def test_sign_in_is_judged_by_the_exit_code_and_no_account_is_ever_printed(self):
        runner = self.machine(answers={("gh", "auth", "status"): (0, "Logged in to github.com account %s\n" % self.ACCOUNT, "token: gho_%s\n" % ("x" * 30)),
                                       ("az", "account", "show"): (1, '{"user": {"name": "%s"}}' % self.ACCOUNT, "tenant %s" % self.ACCOUNT)})
        code, out, err = self.doctor(runner=runner)
        self.assertEqual(0, code)
        self.assertIn("[PASS] sign-in gh: signed in", out)
        self.assertIn("[WARN] sign-in az: not signed in", out)
        self.assertNotIn(self.ACCOUNT, out + err)
        self.assertNotIn("gho_", out + err)
        self.assertIn(["/opt/fake/bin/gh", "auth", "status"], runner.calls)
        self.assertIn(["/opt/fake/bin/az", "account", "show"], runner.calls)
        code, out, _ = self.doctor(runner=self.machine(found=("git", "python", "copilot")))
        self.assertNotIn("[PASS] sign-in", out)
        self.assertNotIn("[WARN] sign-in", out)

    def test_the_output_names_no_absolute_path_and_no_user(self):
        code, out, err = self.doctor("--json")
        for text in (out, err):
            self.assertNotIn("/opt/fake", text)
            self.assertNotIn(str(self.tmp), text)
            self.assertNotIn(str(self.home), text)
        report = json.loads(out)
        self.assertTrue(report["ok"])
        self.assertTrue(all(set(f) == {"level", "check", "message"} for f in report["findings"]))

    def test_the_project_mcp_file_and_the_managed_skills_are_compared_with_the_profile(self):
        (self.root / ".github" / "mcp.json").unlink()
        out = self.doctor()[1]
        self.assertIn("[WARN] host copilot-cli mcp: .github/mcp.json is missing (run: python scripts/toolchain.py render --write-project)", out)
        self.assertIn("[WARN] host copilot-cli skills: no skills are installed in .github/skills (run: python scripts/toolchain.py install --apply)", out)
        write(self.root / ".github" / "mcp.json", "{}\n")
        self.assertIn("[WARN] host copilot-cli mcp: .github/mcp.json differs from the rendering of profile dev-a", self.doctor()[1])
        (self.root / ".github" / "mcp.json").unlink()
        write_store(self.root / ".factory" / "pack", self.lock, ["alpha-core", "beta-core", "gamma"])
        self.assertEqual(0, self.cli("install", "--apply", "--host", "copilot-cli", deps=self.deps(runner=self.machine(), vendor_skills=forbidden("vendor_skills")))[0], "install")
        out = self.doctor()[1]
        self.assertIn("[PASS] host copilot-cli skills: the managed skills in .github/skills match the lock", out)
        marker = read_json(self.root / ".github" / "skills" / toolchain.MARKER)
        marker["lock"] = "sha256:" + "0" * 64
        write(self.root / ".github" / "skills" / toolchain.MARKER, toolchain.dump_json(marker))
        self.assertIn("[WARN] host copilot-cli skills: the managed skills in .github/skills were installed from another lock", self.doctor()[1])

    def test_hosted_servers_are_probed_unless_offline(self):
        answers = {"https://mcp.example.invalid/v1/mcp": "needs-sign-in", "https://docs.example.invalid/mcp": "open"}
        seen = []

        def probe(url, headers=None, runner=None, timeout=15):
            seen.append((url, headers))
            return {"status": answers[url], "http_status": 200}
        out = self.doctor(probe_http=probe)[1]
        self.assertIn("[PASS] server hosted: reachable, needs a sign-in", out)
        self.assertIn("[PASS] server docs: reachable", out)
        self.assertIn(("https://mcp.example.invalid/v1/mcp", {"X-VARIANTS": "Acme.V1"}), seen)
        answers["https://docs.example.invalid/mcp"] = "error"
        self.assertIn("[WARN] server docs: not reachable", self.doctor(probe_http=probe)[1])
        seen.clear()
        code, out, _ = self.doctor("--offline")
        self.assertEqual((0, []), (code, seen))
        self.assertNotIn("server hosted", out)

    def test_a_server_with_a_license_is_reported_and_the_variable_is_never_set(self):
        env = {}
        out = self.doctor(env=env)[1]
        self.assertIn("[INFO] license licensed: the operator must accept the license (https://github.com/acme/licensed/blob/main/EULA.txt) by setting %s=true; the kit never sets it; currently not accepted" % EULA_ENV, out)
        self.assertEqual({}, env)
        env = {EULA_ENV: "true"}
        self.assertIn("currently accepted", self.doctor(env=env)[1])
        self.assertEqual({EULA_ENV: "true"}, env)

    def test_an_unresolved_package_is_a_warning_and_keeps_the_exit_code_zero(self):
        self.rewrite_lock(lambda l: l["packages"].__setitem__("pypi:acme-py", {"status": "unresolved", "reason": "network", "detail": ""}))
        code, out, _ = self.doctor()
        self.assertEqual(0, code)
        self.assertIn("[WARN] package pypi:acme-py: unresolved in the lock (server py-srv)", out)
        self.assertIn("[WARN] profile dev-a: cannot be resolved: package pypi:acme-py is unresolved in the lock", out)

    def test_the_hosts_can_be_chosen(self):
        out = self.doctor("--host", "claude-code")[1]
        self.assertIn("[WARN] host claude-code mcp: .mcp.json is missing", out)
        self.assertNotIn("host copilot-cli mcp", out)


class LockCommandTests(Base):
    def setUp(self):
        super().setUp()
        self.small_project(with_lock=False)
        self.truth = synthetic_lock(self.manifest, self.profiles)
        del self.lock  # the helper below is called lock(), like the command; the fixture's attribute would hide it
        self.up = Upstream(self.manifest, self.truth)
        self.path = self.root / "toolchain" / "toolchain.lock.json"

    def lock(self, *args, env=None, clock=None, **more):
        return self.cli("lock", *args, deps=self.up.deps(self.home, env=env, clock=clock, **more))

    def written(self):
        return read_json(self.path)

    def test_lock_resolves_the_manifest_and_matches_the_expected_lock(self):
        code, out, err = self.lock("--contracts", env={EULA_ENV: "true"})
        self.assertEqual((0, ""), (code, err), out)
        expected = {k: v for k, v in self.truth.items() if k != "generated"}
        actual = self.written()
        self.assertEqual("2026-10-30", actual.pop("generated"))
        self.assertEqual(expected, actual)
        self.assertEqual(["schema", "generated", "inputs_digest", "skill_sources", "packages", "contracts"], list(self.written()))
        self.assertIn("wrote toolchain/toolchain.lock.json: 1 skill source(s), 6 skill(s), 5 package(s) (0 unresolved), 7 contract(s) (5 captured)", out)
        raw = self.path.read_bytes()
        self.assertNotIn(b"\r", raw)
        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(toolchain.dump_json(self.written()).encode("utf-8"), raw)
        for mapping in (actual["skill_sources"], actual["packages"], actual["contracts"], actual["skill_sources"]["src"]["plugins"],
                        actual["skill_sources"]["src"]["plugins"]["core"]["skills"]):
            self.assertEqual(sorted(mapping), list(mapping))
        toolchain.load_lock(self.path)

    def test_the_resolved_lock_makes_a_verifiable_project(self):
        self.assertEqual(0, self.lock("--contracts", env={EULA_ENV: "true"})[0])
        self.assertEqual(0, self.cli("render", "--write-project")[0])
        self.assertEqual(0, self.cli("verify")[0])
        self.assertEqual(0, self.lock("--check", "--contracts", env={EULA_ENV: "true"})[0])

    def test_the_real_manifest_resolves_into_the_expected_lock(self):
        project = self.tmp / "real"
        project.mkdir()
        manifest, profiles, truth = copy_real_project(project, with_lock=False)
        up = Upstream(manifest, truth)
        deps = up.deps(self.home, env={"PBI_MODELING_MCP_ACCEPT_EULA": "true"})
        code, out, err = self.cli("lock", "--contracts", deps=deps, root=project)
        self.assertEqual(0, code, out + err)
        actual = read_json(project / "toolchain" / "toolchain.lock.json")
        actual.pop("generated")
        self.assertEqual({k: v for k, v in truth.items() if k != "generated"}, actual)

    def test_without_contracts_nothing_is_launched_and_each_contract_is_a_skipped_placeholder(self):
        code, out, _ = self.lock()
        self.assertEqual(0, code)
        self.assertEqual([], self.up.calls["probe_stdio"] + self.up.calls["probe_http"])
        placeholder = {"status": "skipped", "reason": "skipped", "detail": "contracts not captured"}
        self.assertEqual({k: placeholder for k in self.truth["contracts"]}, self.written()["contracts"])

    def test_the_output_is_deterministic_and_generated_changes_only_with_the_content(self):
        self.lock("--contracts", env={EULA_ENV: "true"})
        first = self.path.read_bytes()
        later = lambda: NOW + datetime.timedelta(days=6)
        self.lock("--contracts", env={EULA_ENV: "true"}, clock=later)
        self.assertEqual(first, self.path.read_bytes())
        self.up.packages["npm:@acme/tool"] = dict(self.up.packages["npm:@acme/tool"], version="1.7.0", integrity="sha512-" + "A" * 40)
        self.up.tools["@acme/tool"]["tool_a"]["read_only"] = False
        self.lock("--contracts", env={EULA_ENV: "true"}, clock=later)
        self.assertEqual("2026-11-05", self.written()["generated"])

    def test_a_captured_contract_survives_a_failed_capture_of_the_same_package_version(self):
        self.lock("--contracts", env={EULA_ENV: "true"})
        before = self.path.read_bytes()
        with mock.patch.object(self.up, "probe_stdio", side_effect=toolchain_mcp.McpProbeError("timeout: no answer")):
            code, out, _ = self.lock("--contracts", env={EULA_ENV: "true"})
        self.assertEqual(0, code)
        self.assertEqual(before, self.path.read_bytes())
        self.assertIn("note: kept the captured contract of npm-srv/online: the new capture is unavailable", out)

    def test_a_changed_package_version_replaces_the_contract_by_the_new_capture_or_by_unavailable(self):
        self.lock("--contracts", env={EULA_ENV: "true"})
        self.up.packages["pypi:acme-py"] = {"status": "resolved", "version": "1.9.0", "sha256": "ab" * 32, "via": "pypi"}
        self.up.tools["acme-py"] = {"tool_z": {"schema": "sha256:" + "3" * 64, "read_only": True, "destructive": False, "idempotent": True}}
        self.assertEqual(0, self.lock("--contracts", env={EULA_ENV: "true"})[0])
        contract = self.written()["contracts"]["py-srv/default"]
        self.assertEqual(("captured", "1.9.0", ["tool_z"]), (contract["status"], contract["package_version"], list(contract["tools"])))
        self.up.packages["pypi:acme-py"] = {"status": "resolved", "version": "2.0.0", "sha256": "cd" * 32, "via": "pypi"}
        original = self.up.probe_stdio

        def failing(argv, env=None, cwd=None, timeout=60):
            if "acme-py" in " ".join(argv):
                raise toolchain_mcp.McpProbeError("exited: gone")
            return original(argv, env=env, cwd=cwd, timeout=timeout)
        self.assertEqual(0, self.lock("--contracts", env={EULA_ENV: "true"}, probe_stdio=failing)[0])
        self.assertEqual({"status": "unavailable", "reason": "exited", "detail": "gone"}, self.written()["contracts"]["py-srv/default"])
        self.assertEqual("captured", self.written()["contracts"]["npm-srv/online"]["status"])

    def test_without_contracts_a_changed_package_version_marks_the_old_contract_skipped(self):
        self.lock("--contracts", env={EULA_ENV: "true"})
        self.up.packages["pypi:acme-py"] = {"status": "resolved", "version": "1.9.0", "sha256": "ab" * 32, "via": "pypi"}
        self.lock()
        self.assertEqual({"status": "skipped", "reason": "skipped", "detail": "package version changed"}, self.written()["contracts"]["py-srv/default"])
        self.assertEqual("captured", self.written()["contracts"]["npm-srv/online"]["status"])

    def test_a_resolved_package_is_never_replaced_by_a_failed_refresh(self):
        self.lock()
        before = self.written()["packages"]["npm:@acme/tool"]
        self.up.packages["npm:@acme/tool"] = {"status": "unresolved", "reason": "network", "detail": ""}
        code, out, _ = self.lock()
        self.assertEqual(0, code)
        self.assertEqual(before, self.written()["packages"]["npm:@acme/tool"])
        self.assertIn("note: kept the locked version of npm:@acme/tool: it could not be resolved now", out)
        self.path.unlink()
        code, out, _ = self.lock()
        self.assertEqual({"status": "unresolved", "reason": "network", "detail": ""}, self.written()["packages"]["npm:@acme/tool"])
        self.assertIn("WARN: package npm:@acme/tool is unresolved (network)", out)

    def test_nothing_that_could_leak_reaches_the_lock(self):
        feed = "pkgs." + "contoso." + "invalid"
        self.up.packages["npm:@acme/tool"] = {"status": "unresolved", "reason": "network",
                                               "detail": "GET https://%s/_packaging/x failed at %s E404 /home/%s/.npmrc ~/x" % (feed, feed, "someone")}
        self.up.packages["pypi:acme-py"] = {"status": "unresolved", "reason": "internal-feed-error", "detail": "x" * 200}
        self.up.packages["nuget:Acme.Nuget"] = {"status": "resolved", "version": "latest", "via": "nuget"}
        with mock.patch.object(self.up, "probe_stdio", side_effect=toolchain_mcp.McpProbeError("timeout: waited on https://%s/x for 60 s" % feed)):
            code, out, err = self.lock("--contracts", env={EULA_ENV: "true"})
        self.assertEqual(0, code, out + err)
        raw = json.dumps({"packages": self.written()["packages"], "contracts": self.written()["contracts"]})
        for leak in (feed, "https://", "/home/", "someone", ".npmrc", "~/"):
            self.assertNotIn(leak, raw)
        packages = self.written()["packages"]
        self.assertEqual({"status": "unresolved", "reason": "network", "detail": "GET failed at E404"}, packages["npm:@acme/tool"])
        self.assertEqual(("unresolved", "unresolved"), (packages["pypi:acme-py"]["status"], packages["pypi:acme-py"]["reason"]))
        self.assertLessEqual(len(packages["pypi:acme-py"]["detail"]), 80)
        self.assertEqual({"status": "unresolved", "reason": "unresolved", "detail": "unexpected version"}, packages["nuget:Acme.Nuget"])
        self.assertEqual({"status": "unavailable", "reason": "timeout", "detail": "waited on for 60 s"}, self.written()["contracts"]["licensed/offline"])
        self.assertEqual({"status": "unavailable", "reason": "unresolved", "detail": ""}, self.written()["contracts"]["npm-srv/online"])

    def test_a_pinned_package_that_resolves_to_another_version_is_unresolved(self):
        self.rewrite_manifest(lambda m: m["mcp_servers"][0]["package"].update(track="1.5.0"))
        self.lock()
        self.assertEqual("unresolved", self.written()["packages"]["npm:@acme/tool"]["status"])

    def test_a_skill_source_that_cannot_be_resolved_stops_the_lock_and_writes_nothing(self):
        self.lock()
        before = self.path.read_bytes()
        self.up.fail_refs.add("https://github.com/acme/skills.git")
        code, out, err = self.lock()
        self.assertEqual(1, code)
        self.assertIn("skill source src: network: fake failure", err)
        self.assertEqual(before, self.path.read_bytes())
        self.path.unlink()
        self.assertEqual(1, self.lock()[0])
        self.assertFalse(self.path.exists())

    def test_only_limits_the_resolution_to_the_named_source_or_package(self):
        self.lock("--contracts", env={EULA_ENV: "true"})
        self.up.refs["https://github.com/acme/skills.git"] = {"tag": "v0.2.0", "commit": "2" * 40}
        self.up.packages["npm:@acme/tool"] = dict(self.up.packages["npm:@acme/tool"], version="1.7.0")
        self.up.calls["resolve_package"].clear()
        self.assertEqual(0, self.lock("--only", "src")[0])
        self.assertEqual([], self.up.calls["resolve_package"])
        self.assertEqual(("v0.2.0", "1.6.0"), (self.written()["skill_sources"]["src"]["tag"], self.written()["packages"]["npm:@acme/tool"]["version"]))
        self.up.refs["https://github.com/acme/skills.git"] = {"tag": "v0.3.0", "commit": "3" * 40}
        for name in ("@acme/tool", "npm:@acme/tool"):
            self.up.calls["fetch_git"].clear()
            self.up.packages["npm:@acme/tool"]["version"] = "1.7.0"
            self.assertEqual(0, self.lock("--only", name)[0], name)
            self.assertEqual("1.7.0", self.written()["packages"]["npm:@acme/tool"]["version"])
            self.assertEqual(("v0.2.0", []), (self.written()["skill_sources"]["src"]["tag"], self.up.calls["fetch_git"]))
        self.assertEqual(2, self.lock("--only", "ghost")[0])
        self.path.unlink()
        self.assertEqual(2, self.lock("--only", "src")[0])

    def test_check_resolves_into_memory_and_fails_when_the_lock_differs(self):
        self.assertEqual(1, self.lock("--check")[0])
        self.lock()
        before = self.path.read_bytes()
        code, out, _ = self.lock("--check")
        self.assertEqual((0, True), (code, "the lock is current" in out))
        self.up.refs["https://github.com/acme/skills.git"] = {"tag": "v0.2.0", "commit": "2" * 40}
        code, out, _ = self.lock("--check")
        self.assertEqual(1, code)
        self.assertIn("src: tag v0.1.0 -> v0.2.0", out)
        self.assertEqual(before, self.path.read_bytes())

    def test_no_network_only_re_derives_the_inputs_digest(self):
        self.lock("--contracts", env={EULA_ENV: "true"})
        before = self.written()
        self.rewrite_manifest(lambda m: m["quarantine"].append({"source": "src", "skill": "more", "reason": "x"}))
        self.assertEqual(1, self.cli("verify")[0])
        code, out, err = self.cli("lock", "--no-network", deps=self.deps())
        self.assertEqual((0, ""), (code, err), out)
        after = self.written()
        self.assertEqual(toolchain.inputs_digest(self.manifest), after["inputs_digest"])
        self.assertEqual({k: v for k, v in before.items() if k not in ("inputs_digest", "generated")}, {k: v for k, v in after.items() if k not in ("inputs_digest", "generated")})
        self.assertEqual(0, self.cli("render", "--write-project")[0])
        code, out, _ = self.cli("verify")
        self.assertEqual(0, code, out)
        self.path.unlink()
        self.assertEqual(1, self.cli("lock", "--no-network", deps=self.deps())[0])

    def test_a_license_that_is_not_accepted_means_the_server_is_not_launched_and_the_contract_is_skipped(self):
        for env in ({}, {EULA_ENV: "false"}, {EULA_ENV: "1"}, {EULA_ENV: " true"}, {EULA_ENV: ""}):
            with self.subTest(env=env):
                self.up.calls["probe_stdio"].clear()
                self.assertEqual(0, self.lock("--contracts", env=env)[0])
                self.assertTrue(all(LICENSED not in " ".join(c["argv"]) for c in self.up.calls["probe_stdio"]))
                self.assertEqual(4, len(self.up.calls["probe_stdio"]))
                self.assertEqual({"status": "skipped", "reason": "skipped", "detail": "license not accepted"}, self.written()["contracts"]["licensed/offline"])

    def test_a_license_that_is_accepted_means_the_server_is_probed_and_the_value_is_never_stored(self):
        for value in ("true", "TRUE", "True"):
            with self.subTest(value=value):
                self.up.calls["probe_stdio"].clear()
                env = {EULA_ENV: value}
                self.assertEqual(0, self.lock("--contracts", env=env)[0])
                self.assertEqual({EULA_ENV: value}, env)
                self.assertEqual(5, len(self.up.calls["probe_stdio"]))
                self.assertEqual("captured", self.written()["contracts"]["licensed/offline"]["status"])
                raw = self.path.read_text(encoding="utf-8")
                self.assertNotIn(EULA_ENV, raw)
                self.assertNotIn("ACCEPT", raw)
                self.assertNotIn("TRUE", raw)
                self.assertNotIn("True", raw)

    def test_a_good_capture_is_kept_when_the_license_is_no_longer_accepted(self):
        self.lock("--contracts", env={EULA_ENV: "true"})
        before = self.path.read_bytes()
        self.assertEqual(0, self.lock("--contracts", env={})[0])
        self.assertEqual(before, self.path.read_bytes())

    def test_hosted_servers_are_probed_only_with_contracts(self):
        self.lock("--contracts", env={EULA_ENV: "true"})
        self.assertEqual({"status": "needs-sign-in"}, self.written()["contracts"]["hosted/default"])
        self.assertEqual({"status": "open"}, self.written()["contracts"]["docs/default"])
        self.assertEqual(["https://mcp.example.invalid/v1/mcp", "https://docs.example.invalid/mcp"], self.up.calls["probe_http"])
        self.up.http_status["https://docs.example.invalid/mcp"] = "error"
        self.lock("--contracts", env={EULA_ENV: "true"})
        self.assertEqual({"status": "open"}, self.written()["contracts"]["docs/default"])
        self.path.unlink()
        self.lock("--contracts", env={EULA_ENV: "true"})
        self.assertEqual({"status": "unavailable", "reason": "network", "detail": ""}, self.written()["contracts"]["docs/default"])

    def test_a_broken_manifest_or_an_invalid_existing_lock_stops_the_command(self):
        self.rewrite_manifest(lambda m: m.update(bogus=1))
        code, out, err = self.lock()
        self.assertEqual(1, code)
        self.assertIn("unknown key 'bogus'", err)
        self.rewrite_manifest(lambda m: m.pop("bogus"))
        write(self.path, '{"schema": 1}\n')
        code, out, err = self.lock()
        self.assertEqual(1, code)
        self.assertIn("toolchain.lock.json is invalid", err)

    def test_a_malformed_resolver_answer_cannot_corrupt_the_lock(self):
        self.up.plugins["plugins/core"]["skills"]["alpha-core"]["digest"] = "not-a-digest"
        code, out, err = self.lock()
        self.assertEqual(1, code)
        self.assertIn("the resolved lock is invalid", err)
        self.assertFalse(self.path.exists())


class UpdateTests(Base):
    def setUp(self):
        super().setUp()
        self.small_project()
        self.assertEqual(0, self.cli("render", "--write-project")[0])
        self.up = Upstream(self.manifest, self.lock)
        self.path = self.root / "toolchain" / "toolchain.lock.json"

    def update(self, *args, env=None):
        return self.cli("update", *args, deps=self.up.deps(self.home, env=env))

    def bump(self):
        """New upstream: a new tag, a version bump, one skill added, one renamed, one changed, one removed, and a package bump."""
        self.up.refs["https://github.com/acme/skills.git"] = {"tag": "v0.2.0", "commit": "2" * 40}
        core = self.up.plugins["plugins/core"]
        core["version"] = "0.2.0"
        core["skills"]["alpha-core-v2"] = core["skills"].pop("alpha-core")
        core["skills"]["delta"] = dict(core["skills"]["beta-core"], digest=skill_digest("delta"))
        core["skills"]["beta-core"] = dict(core["skills"]["beta-core"], digest="sha256:" + "9" * 64, description_chars=150)
        del self.up.plugins["plugins/extra"]["skills"]["gamma"]
        self.up.packages["npm:@acme/tool"] = {"status": "resolved", "version": "1.7.0", "integrity": "sha512-" + "B" * 40, "via": "npm-cli"}
        self.up.packages["pypi:acme-py"] = dict(self.up.packages["pypi:acme-py"], sha256="ef" * 32)

    def test_nothing_new_upstream_is_reported_as_such(self):
        code, out, err = self.update("--fail-on-update")
        self.assertEqual((0, ""), (code, err), out)
        self.assertIn("No upstream change.", out)
        self.assertIn("nothing: every profile still verifies", out)

    def test_the_gap_analysis_lists_every_kind_of_change(self):
        self.bump()
        code, out, err = self.update()
        self.assertEqual((0, ""), (code, err), out)
        for line in ("Skill sources", "  src: tag v0.1.0 -> v0.2.0, commit 111111111111 -> 222222222222",
                     "Plugins and skills", "  src/core: version 0.1.0 -> 0.2.0", "    skills added: delta", "    skills changed: beta-core",
                     "    skills renamed: alpha-core -> alpha-core-v2", "    description length changed: beta-core 120 -> 150",
                     "  src/extra", "    skills removed: gamma",
                     "Packages", "  npm:@acme/tool: 1.6.0 -> 1.7.0", "  pypi:acme-py: 1.8.0 -> 1.8.0 (same version, different hash)",
                     "What breaks"):
            self.assertIn(line, out.splitlines(), line)
        self.assertNotIn("skills removed: alpha-core", out)
        self.assertNotIn("skills added: alpha-core-v2", out)

    def test_what_breaks_names_every_profile_that_would_no_longer_verify_and_why(self):
        self.bump()
        out = self.update()[1]
        self.assertIn("  profile dev-a (newly broken)", out.splitlines())
        self.assertIn("    skill 'gamma' is not in the lock for src/extra", out)
        self.assertIn("  profile agent-ok (newly broken)", out.splitlines())
        self.assertIn("    skill 'alpha-core' is not in the lock for src/core", out)
        self.assertNotIn("profile agent-empty", out)

    def test_an_unresolved_package_breaks_an_agent_profile_in_the_analysis(self):
        self.up.packages["npm:@acme/tool"] = {"status": "unresolved", "reason": "network", "detail": ""}
        self.rewrite_lock(lambda l: l["packages"].pop("npm:@acme/tool"))
        out = self.update()[1]
        self.assertIn("  profile agent-ok", out)
        self.assertIn("package npm:@acme/tool is unresolved in the lock (network)", out)

    def test_the_exit_code_is_three_only_with_fail_on_update_and_a_change(self):
        self.bump()
        self.assertEqual(0, self.update()[0])
        self.assertEqual(0, self.update("--check")[0])
        self.assertEqual(3, self.update("--fail-on-update")[0])
        self.assertEqual(3, self.update("--check", "--fail-on-update")[0])

    def test_the_json_report(self):
        self.bump()
        code, out, _ = self.update("--json")
        report = json.loads(out)
        self.assertEqual(0, code)
        self.assertTrue(report["changed"])
        core = [p for p in report["plugins"] if p["plugin"] == "core"][0]
        self.assertEqual({"from": "alpha-core", "to": "alpha-core-v2"}, core["renamed"][0])
        self.assertEqual(["delta"], core["added"])
        self.assertEqual([{"skill": "beta-core", "chars": [120, 150]}], core["description"])
        self.assertEqual(["agent-ok", "dev-a"], sorted(b["profile"] for b in report["breaks"]))
        self.assertTrue(all(b["newly_broken"] for b in report["breaks"]))
        self.assertEqual(sorted(report["packages"][0]), ["key", "new", "note", "old"])

    def test_the_output_is_deterministic(self):
        self.bump()
        self.assertEqual(self.update(), self.update())
        self.assertEqual(self.update("--json"), self.update("--json"))

    def test_write_refuses_while_a_profile_would_not_verify_and_force_overrides(self):
        self.bump()
        before = self.path.read_bytes()
        code, out, err = self.update("--write")
        self.assertEqual(1, code)
        self.assertIn("not written: 2 profile(s) would not verify (use --force to write anyway)", err)
        self.assertEqual(before, self.path.read_bytes())
        code, out, _ = self.update("--write", "--force")
        self.assertEqual(0, code)
        self.assertIn("wrote toolchain/toolchain.lock.json", out)
        self.assertEqual("v0.2.0", read_json(self.path)["skill_sources"]["src"]["tag"])
        self.assertEqual("No upstream change.", [l for l in self.update()[1].splitlines() if l.startswith("No")][0])

    def test_write_updates_the_lock_when_every_profile_still_verifies(self):
        self.up.packages["npm:@acme/tool"] = {"status": "resolved", "version": "1.7.0", "integrity": "sha512-" + "B" * 40, "via": "npm-cli"}
        code, out, err = self.update("--write")
        self.assertEqual(0, code, out + err)
        self.assertEqual("1.7.0", read_json(self.path)["packages"]["npm:@acme/tool"]["version"])
        self.assertEqual(0, self.update("--check", "--fail-on-update")[0])
        self.assertEqual(1, self.cli("verify")[0])
        self.assertEqual(0, self.cli("render", "--write-project")[0])
        self.assertEqual(0, self.cli("verify")[0])

    def test_check_never_writes_the_lock(self):
        self.bump()
        before = self.path.read_bytes()
        self.update()
        self.update("--check", "--json")
        self.assertEqual(before, self.path.read_bytes())

    def test_the_summary_file_is_markdown(self):
        self.bump()
        summary = self.tmp / "summary.md"
        self.update("--summary-file", str(summary))
        text = summary.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Toolchain update check\n\n"))
        for fragment in ("## Skill sources", "- src: tag v0.1.0 -> v0.2.0", "## Plugins and skills", "  - skills renamed: alpha-core -> alpha-core-v2",
                         "## Packages", "## What breaks", "- profile agent-ok (newly broken)"):
            self.assertIn(fragment, text)
        self.assertNotIn(b"\r", summary.read_bytes())

    def test_contract_changes_are_listed_per_variant(self):
        self.up.tools["acme-py"]["tool_c"] = {"schema": "sha256:" + "4" * 64, "read_only": True, "destructive": False, "idempotent": True}
        del self.up.tools["acme-py"]["tool_a"]
        self.up.tools["acme-py"]["tool_b"]["destructive"] = True
        code, out, _ = self.update("--contracts", env={EULA_ENV: "true"})
        self.assertEqual(0, code)
        self.assertIn("  py-srv/default: captured -> captured; tools added tool_c; removed tool_a; changed tool_b", out.splitlines())
        self.assertEqual(3, self.update("--contracts", "--fail-on-update", env={EULA_ENV: "true"})[0])
        self.assertEqual(0, self.update("--fail-on-update", env={EULA_ENV: "true"})[0])

    def test_without_a_current_lock_everything_is_new(self):
        self.path.unlink()
        code, out, _ = self.update("--fail-on-update")
        self.assertEqual(3, code)
        self.assertIn("There is no current lock: everything below is new.", out)

    def test_a_license_that_is_not_accepted_keeps_the_server_unlaunched_in_update_too(self):
        calls = self.up.calls["probe_stdio"]
        self.assertEqual(0, self.update("--contracts", "--fail-on-update", env={})[0])
        self.assertTrue(calls)
        self.assertTrue(all(LICENSED not in " ".join(c["argv"]) for c in calls))
        self.rewrite_lock(lambda l: l["contracts"].pop("licensed/offline"))
        calls.clear()
        code, out, _ = self.update("--contracts", env={EULA_ENV: "no"})
        self.assertEqual(0, code)
        self.assertTrue(all(LICENSED not in " ".join(c["argv"]) for c in calls))
        self.assertIn("licensed/offline: none -> skipped", out)
        calls.clear()
        self.update("--contracts", env={EULA_ENV: "TRUE"})
        self.assertEqual(1, sum(LICENSED in " ".join(c["argv"]) for c in calls))

    def test_an_edited_manifest_is_a_change_even_when_upstream_is_unchanged(self):
        self.rewrite_manifest(lambda m: m["quarantine"].append({"source": "src", "skill": "more", "reason": "x"}))
        code, out, _ = self.update("--fail-on-update")
        self.assertEqual(3, code)
        self.assertIn("The lock inputs changed (the manifest was edited); nothing changed upstream.", out)

    def test_an_upstream_failure_stops_the_update(self):
        self.up.fail_refs.add("https://github.com/acme/skills.git")
        code, out, err = self.update()
        self.assertEqual(1, code)
        self.assertIn("skill source src: network: fake failure", err)


class ListTests(Base):
    def setUp(self):
        super().setUp()
        self.small_project()

    def test_the_profiles_table(self):
        code, out, _ = self.cli("list")
        self.assertEqual(0, code)
        self.assertRegex(out, r"(?m)^PROFILE\s+MODE\s+SKILLS\s+SERVERS\s+TITLE$")
        self.assertRegex(out, r"(?m)^dev-a\s+dev\s+3\s+6\s+Everything$")
        self.assertRegex(out, r"(?m)^agent-ok\s+agent\s+1\s+1\s*$")
        self.assertRegex(out, r"(?m)^agent-empty\s+agent\s+0\s+0\s*$")
        report = json.loads(self.cli("list", "--json")[1])
        self.assertEqual({"name": "dev-a", "mode": "dev", "skills": 3, "servers": 6, "title": "Everything"}, report["profiles"][0])

    def test_one_profile_shows_its_resolved_skills_and_servers_with_their_attributes(self):
        out = self.cli("list", "--profile", "dev-a")[1]
        self.assertIn("Profile dev-a (mode dev): Everything", out)
        self.assertIn("Skills: 3", out)
        self.assertIn("  src/core/alpha-core  " + skill_digest("alpha-core")[7:19], out)
        self.assertNotIn("risky", out)
        self.assertRegex(out, r"(?m)^  npm-srv\s+online\s+stdio\s+ga\s+microsoft-cloud\s+azure-identity\s+read\s+true\s+1\.6\.0$")
        self.assertRegex(out, r"(?m)^  hosted\s+default\s+http\s+preview\s+microsoft-cloud\s+entra-delegated\s+read-write\s+false\s+-$")
        report = json.loads(self.cli("list", "--profile", "agent-ok", "--json")[1])["profile"]
        self.assertEqual(["alpha-core"], [s["name"] for s in report["skills"]])

    def test_the_locked_skills_are_listed_with_the_quarantine_marked(self):
        out = self.cli("list", "--skills")[1]
        self.assertRegex(out, r"(?m)^src\s+core\s+risky\s+[0-9a-f]{12}\s+quarantined$")
        self.assertRegex(out, r"(?m)^src\s+core\s+alpha-core\s+[0-9a-f]{12}$")
        skills = json.loads(self.cli("list", "--skills", "--json")[1])["skills"]
        self.assertEqual([True], [s["quarantined"] for s in skills if s["name"] == "risky"])

    def test_the_servers_are_listed_with_variants_and_the_locked_package_version(self):
        out = self.cli("list", "--servers")[1]
        self.assertRegex(out, r"(?m)^npm-srv\s+offline\s+stdio\s+ga\s+none\s+none\s+read\s+true\s+1\.6\.0$")
        self.assertRegex(out, r"(?m)^npm-srv\s+manual\s+stdio\s+ga\s+none\s+none\s+read\s+false\s+1\.6\.0$")
        self.assertRegex(out, r"(?m)^npm-srv\s+unknown\s+stdio\s+ga\s+none\s+none\s+read\s+\"unverified\"\s+1\.6\.0$")
        self.assertRegex(out, r"(?m)^nuget-srv\s+default\s+stdio\s+unverified\s+internet\s+none\s+read\s+true\s+0\.5\.0$")

    def test_without_a_lock_the_listing_still_works_where_it_can(self):
        (self.root / "toolchain" / "toolchain.lock.json").unlink()
        out = self.cli("list")[1]
        self.assertRegex(out, r"(?m)^dev-a\s+dev\s+\?\s+6")
        self.assertRegex(out, r"(?m)^agent-ok\s+agent\s+1\s+1")
        self.assertIn("not locked", self.cli("list", "--servers")[1])
        code, out, err = self.cli("list", "--skills")
        self.assertEqual(1, code)
        self.assertIn("lock file missing", err)


class FetchTests(Base):
    def setUp(self):
        super().setUp()
        self.small_project()
        self.calls = []

    def vendor(self, lock, selection, store, runner, quarantine=()):
        self.calls.append({"selection": selection, "store": Path(store), "quarantine": quarantine})
        return {"schema": 1, "skills": {name: {"files": 2} for _s, _p, name in selection}}

    def test_fetch_vendors_the_union_of_the_profiles_skills_from_the_locked_commits(self):
        code, out, err = self.cli("fetch", deps=self.deps(vendor_skills=self.vendor))
        self.assertEqual((0, ""), (code, err), out)
        self.assertEqual([("src", "core", "alpha-core"), ("src", "core", "beta-core"), ("src", "extra", "gamma")], self.calls[0]["selection"])
        self.assertEqual(("risky",), self.calls[0]["quarantine"])
        self.assertEqual(self.root / ".factory" / "pack", self.calls[0]["store"])
        self.assertIn("fetched 3 skill(s), 6 file(s), into .factory/pack", out)

    def test_fetch_can_take_a_profile_and_a_store(self):
        elsewhere = self.tmp / "elsewhere"
        code, out, _ = self.cli("fetch", "--profile", "agent-ok", "--store", str(elsewhere), deps=self.deps(vendor_skills=self.vendor))
        self.assertEqual(0, code)
        self.assertEqual([("src", "core", "alpha-core")], self.calls[0]["selection"])
        self.assertEqual(elsewhere, self.calls[0]["store"])
        self.assertNotIn(str(self.tmp), out)

    def test_nothing_is_fetched_for_a_profile_without_skills(self):
        code, out, _ = self.cli("fetch", "--profile", "agent-empty", deps=self.deps(vendor_skills=self.vendor))
        self.assertEqual(0, code)
        self.assertEqual([], self.calls)
        self.assertIn("nothing to fetch", out)

    def test_a_failed_fetch_is_an_error_without_a_host_name(self):
        feed = "pkgs." + "contoso." + "invalid"

        def vendor(*args, **kwargs):
            raise toolchain_sources.SourceError("digest mismatch at https://%s/x" % feed)
        code, out, err = self.cli("fetch", deps=self.deps(vendor_skills=vendor))
        self.assertEqual(1, code)
        self.assertIn("fetch failed", err)
        self.assertNotIn(feed, err)

    def test_fetch_refuses_a_stale_lock_and_an_unknown_profile(self):
        self.assertEqual(2, self.cli("fetch", "--profile", "ghost", deps=self.deps(vendor_skills=self.vendor))[0])
        self.rewrite_manifest(lambda m: m["quarantine"].clear())
        self.assertEqual(1, self.cli("fetch", deps=self.deps(vendor_skills=self.vendor))[0])


class DepsTests(Base):
    def test_the_defaults_are_looked_up_on_the_modules_when_they_are_called(self):
        deps = toolchain.Deps()
        sentinel = object()
        with mock.patch.object(toolchain_sources, "resolve_package", return_value=sentinel):
            self.assertIs(sentinel, deps.resolve_package("npm", "x", "latest", None))
        with mock.patch.object(toolchain_mcp, "probe_http", return_value=sentinel):
            self.assertIs(sentinel, deps.probe_http("https://x.example.invalid"))
        with mock.patch.object(toolchain_mcp, "contract_diff", return_value=sentinel):
            self.assertIs(sentinel, deps.contract_diff({}, {}))
        for name in ("resolve_git_ref", "fetch_git", "read_plugin", "vendor_skills", "digest_tree"):
            self.assertIs(getattr(toolchain_sources, name), getattr(deps, name))
        for name in ("probe_stdio", "probe_http", "contract_diff"):
            self.assertIs(getattr(toolchain_mcp, name), getattr(deps, name))

    def test_an_override_wins_and_an_unknown_name_is_refused(self):
        marker = object()
        self.assertIs(marker, toolchain.Deps(resolve_package=marker).resolve_package)
        with self.assertRaises(TypeError):
            toolchain.Deps(resolve_packages=marker)
        with self.assertRaises(AttributeError):
            toolchain.Deps().no_such_function

    def test_the_runner_the_environment_and_the_home_folder_default_sensibly(self):
        deps = toolchain.Deps()
        self.assertIsInstance(deps.runner, toolchain.toolchain_io.SystemRunner)
        self.assertIs(deps.env, os.environ)
        self.assertEqual(self.home, deps.home)
        self.assertEqual(self.tmp / "h", toolchain.Deps(home=self.tmp / "h").home)
        self.assertRegex(toolchain.Deps(clock=lambda: NOW).today(), r"^2026-10-30$")
        self.assertEqual(STAMP, toolchain.Deps(clock=lambda: NOW).stamp())


class HelperTests(Base):
    def test_display_path_never_shows_a_user_name(self):
        root, home = self.tmp / "project", self.home
        self.assertEqual(".github/mcp.json", toolchain.display_path(root / ".github" / "mcp.json", root, home))
        self.assertEqual("$HOME/.copilot/mcp-config.json", toolchain.display_path(home / ".copilot" / "mcp-config.json", root, home))
        self.assertEqual("elsewhere.json", toolchain.display_path(self.tmp / "other" / "elsewhere.json", root, home))
        self.assertEqual(".", toolchain.display_path(root, root, home))
        self.assertEqual("$HOME", toolchain.display_path(home, root, home))

    def test_safe_detail_keeps_only_a_short_harmless_text(self):
        feed = "pkgs." + "contoso." + "invalid"
        cases = {None: "", "": "", "E404 not found": "E404 not found", "see https://%s/x now" % feed: "see now",
                 "host %s down" % feed: "host down", "at /home" + "/someone/x failed": "at failed", "C:\\" + "Users\\x\\y bad": "bad",
                 "a;b|c<d>": "a b c d", "x" * 200: "x" * 80, "version 1.6.0 missing": "version 1.6.0 missing", "~/x ok": "ok"}
        for text, expected in cases.items():
            self.assertEqual(expected, toolchain.safe_detail(text), text)
        self.assertEqual("boom", toolchain.safe_detail(ValueError("boom")))

    def test_a_license_is_accepted_only_by_the_exact_word_true(self):
        accepted = [{"V": "true"}, {"V": "TRUE"}, {"V": "True"}, {"V": "tRuE"}]
        refused = [{}, {"V": ""}, {"V": "false"}, {"V": "1"}, {"V": "yes"}, {"V": " true"}, {"V": "true "}, {"V": "truee"}]
        self.assertTrue(all(toolchain.license_accepted(env, "V") for env in accepted))
        self.assertFalse(any(toolchain.license_accepted(env, "V") for env in refused))

    def test_versions_are_parsed_and_compared_numerically(self):
        self.assertEqual((2, 43, 0), toolchain.parse_version("git version 2.43.0.windows.1"))
        self.assertEqual((22, 1, 0), toolchain.parse_version("v22.1.0"))
        self.assertEqual((10,), toolchain.parse_version("npm 10"))
        self.assertIsNone(toolchain.parse_version("nothing"))
        self.assertTrue(toolchain.at_least((2, 43, 0), "2.30"))
        self.assertTrue(toolchain.at_least((10,), "10"))
        self.assertTrue(toolchain.at_least((3, 10), "3.10.0"))
        self.assertFalse(toolchain.at_least((2, 9, 9), "2.30"))
        self.assertFalse(toolchain.at_least((9, 99), "10"))

    def test_home_is_expanded_only_at_the_start_of_a_path(self):
        self.assertEqual(str(self.home) + "/.copilot/x", toolchain.expand_home("$HOME/.copilot/x", self.home))
        self.assertEqual("/etc/$HOME/x", toolchain.expand_home("/etc/$HOME/x", self.home))

    def test_the_exact_version_rule(self):
        for eco, version, ok in (("npm", "1.2.3", True), ("npm", "1.2", False), ("npm", "1.2.3-rc.1", True), ("pypi", "1.2", True), ("pypi", "1.0rc1", True),
                                 ("nuget", "1.0.0" + ".1", True), ("nuget", "1", False), ("pypi", "latest", False), ("npm", "^1.2.3", False), ("npm", None, False),
                                 ("pypi", "1.*", False), ("npm", "1.2.3 ", False), ("npm", "1.2.3\n", False)):
            self.assertEqual(ok, toolchain.exact_version(eco, version), (eco, version))


class CliTests(Base):
    def setUp(self):
        super().setUp()
        self.small_project()

    def test_usage_errors_exit_with_two_and_help_exits_with_zero(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, toolchain.main([], self.deps()))
            self.assertEqual(2, toolchain.main(["--bogus"], self.deps()))
            self.assertEqual(2, toolchain.main(["frobnicate"], self.deps()))
            self.assertEqual(2, self.cli("verify", "--mode", "root")[0])
            self.assertEqual(2, self.cli("render", "--host", "emacs")[0])
            self.assertEqual(2, self.cli("update", "--check", "--write")[0])
            self.assertEqual(2, self.cli("install", "--scope", "galaxy")[0])
        for command in ("list", "verify", "render", "lock", "update", "fetch", "install", "doctor"):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, toolchain.main([command, "--help"], self.deps()), command)

    def test_an_unknown_profile_is_a_usage_error_everywhere(self):
        for command in (["list", "--profile", "ghost"], ["render", "--profile", "ghost", "--host", "vscode"], ["install", "--profile", "ghost"],
                        ["doctor", "--profile", "ghost"], ["verify", "--profile", "ghost"], ["fetch", "--profile", "ghost"]):
            self.assertEqual(2, self.cli(*command)[0], command)

    def test_a_project_that_does_not_exist_is_an_error_not_a_crash(self):
        nowhere = self.tmp / "nowhere"
        for command in (["list"], ["render", "--host", "vscode"], ["doctor"], ["install"], ["fetch"], ["lock"], ["update"]):
            code, out, err = self.cli(*command, root=nowhere)
            self.assertEqual(1, code, command)
            self.assertNotIn("Traceback", err)
            self.assertNotIn(str(self.tmp), err)
        code, out, err = self.cli("verify", root=nowhere)
        self.assertEqual(1, code)
        self.assertIn("[FAIL] V1: toolchain.json: cannot read the file (FileNotFoundError)", out)

    def test_the_default_root_is_the_parent_of_the_scripts_folder(self):
        self.assertEqual(HERE.parent, toolchain.DEFAULT_ROOT)

    def test_the_root_option_works_before_and_after_the_command(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(0, toolchain.main(["list", "--root", str(self.root)], self.deps()))
        self.assertIn("dev-a", out.getvalue())

    def test_the_command_line_never_touches_the_real_home_folder(self):
        sentinel = self.home / "sentinel"
        sentinel.write_text("x", encoding="utf-8")
        before = sorted(p.relative_to(self.home).as_posix() for p in self.home.rglob("*"))
        self.cli("verify")
        self.cli("doctor", "--offline")
        self.cli("install")
        self.assertEqual(before, sorted(p.relative_to(self.home).as_posix() for p in self.home.rglob("*")))


class EndToEndTests(Base):
    """The real manifest and profiles with a synthetic lock and store: install, verify live, switch profiles."""

    def test_install_the_default_profile_for_two_hosts_and_verify_it_live(self):
        self.real_project()
        self.assertEqual(0, self.cli("render", "--write-project")[0])
        resolved = toolchain.resolve_profile(self.manifest, self.profiles, self.lock, "dev-factory", self.root / "toolchain")
        names = sorted({s["name"] for s in resolved["skills"]})
        self.assertGreater(len(names), 10)
        write_store(self.root / ".factory" / "pack", self.lock, names)
        runner = FakeRunner(found=["copilot", "claude"])
        deps = self.deps(runner=runner)
        code, out, err = self.cli("install", "--apply", deps=deps)
        self.assertEqual((0, ""), (code, err), out)
        self.assertTrue((self.root / ".github" / "skills" / "factory-router" / "SKILL.md").is_file())
        self.assertTrue((self.root / ".claude" / "skills" / "factory-router" / "SKILL.md").is_file())
        self.assertFalse((self.root / ".github" / "skills" / "fabriciq-ontology-cli").exists())
        self.assertEqual(toolchain.dump_json(toolchain.render("claude-code", resolved)), (self.root / ".mcp.json").read_text(encoding="utf-8"))
        before = InstallTests.snapshot(self.root)
        self.assertEqual(0, self.cli("install", "--apply", deps=deps)[0])
        self.assertEqual(before, InstallTests.snapshot(self.root))
        code, out, _ = self.cli("verify", "--live", deps=deps)
        self.assertEqual(0, code, out)


if __name__ == "__main__":
    unittest.main()
