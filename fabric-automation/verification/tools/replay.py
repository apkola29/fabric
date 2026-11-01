"""Replay the reviewers' reproductions against a project tree.

usage: python replay.py PROJECT_DIR [--only ID,ID] [--pack STORE_DIR] [--reference-lock LOCK] [--keep]

Each scenario copies the toolchain files of PROJECT_DIR into a scratch folder, applies the change
that a reviewer described, runs the command line, and says whether the behaviour the reviewer
reported (the bad one) still happens. REPRODUCED means the defect is present.
Nothing outside the scratch folder is touched; HOME and USERPROFILE point into it.
"""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

HELPERS = ("toolchain.py", "toolchain_io.py", "toolchain_mcp.py", "toolchain_sources.py")
ZERO = "sha256:" + "0" * 64
HERE = os.path.dirname(os.path.abspath(__file__))
# The lock that gives a captured contract to a tree that holds none (an old commit): the lock of the project that this folder is in.
REFERENCE_LOCK = os.path.normpath(os.path.join(HERE, "..", "..", "toolchain", "toolchain.lock.json"))


def rmtree(path):
    def onerror(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass
    if os.path.lexists(path):
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path, onerror=onerror)
        else:
            os.unlink(path)


class Work:
    def __init__(self, tree, pack=None):
        self.tree = tree
        self.pack = pack
        self.base = tempfile.mkdtemp(prefix="fa-replay-")
        self.project = os.path.join(self.base, "project")
        self.home = os.path.join(self.base, "home")
        self.bin = os.path.join(self.base, "bin")
        os.makedirs(self.home)
        os.makedirs(self.bin)
        os.makedirs(os.path.join(self.project, "scripts"))
        for name in HELPERS:
            shutil.copy2(os.path.join(tree, "scripts", name), os.path.join(self.project, "scripts", name))
        shutil.copytree(os.path.join(tree, "toolchain"), os.path.join(self.project, "toolchain"))
        for rel in (".github/mcp.json", ".vscode/mcp.json", "AGENTS.md"):
            src = os.path.join(tree, *rel.split("/"))
            if os.path.isfile(src):
                dst = os.path.join(self.project, *rel.split("/"))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
        if pack and os.path.isdir(pack):
            shutil.copytree(pack, os.path.join(self.project, ".factory", "pack"))

    def p(self, *parts):
        return os.path.join(self.project, *parts)

    def env(self, path_first=None):
        env = dict(os.environ)
        env["HOME"] = env["USERPROFILE"] = self.home
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if path_first:
            env["PATH"] = path_first + os.pathsep + env["PATH"]
        return env

    def run(self, *args, path_first=None, timeout=600):
        cmd = [sys.executable, "-B", self.p("scripts", "toolchain.py")] + list(args)
        done = subprocess.run(cmd, cwd=self.project, env=self.env(path_first), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
        return done.returncode, (done.stdout or "") + (done.stderr or "")

    def py(self, code, path_first=None, timeout=600, cwd=None):
        done = subprocess.run([sys.executable, "-B", "-c", code], cwd=cwd or self.project, env=self.env(path_first),
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return done.returncode, (done.stdout or "") + (done.stderr or "")

    def jload(self, *parts):
        with open(self.p(*parts), "r", encoding="utf-8") as handle:
            return json.load(handle)

    def jsave(self, data, *parts):
        path = self.p(*parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

    def write(self, text, *parts):
        path = self.p(*parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def shim(self, name, log):
        if os.name == "nt":
            body = "@echo off\r\necho %* >> \"" + log + "\"\r\nexit /b 0\r\n"
            with open(os.path.join(self.bin, name + ".cmd"), "w", newline="") as handle:
                handle.write(body)
        else:
            path = os.path.join(self.bin, name)
            with open(path, "w", newline="\n") as handle:
                handle.write("#!/bin/sh\necho \"$@\" >> \"" + log + "\"\nexit 0\n")
            os.chmod(path, 0o755)

    def close(self):
        rmtree(self.base)


def lock_digest(w):
    rc, out = w.py("import sys; sys.path.insert(0, 'scripts'); import toolchain as t; "
                   "p = t.Project('.').load(); print(t.lock_digest(p.lock))")
    return out.strip().splitlines()[-1] if rc == 0 else None


def server(manifest, sid):
    return next(s for s in manifest["mcp_servers"] if s["id"] == sid)


def short(text, n=160):
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n] + "..."


# ---------------------------------------------------------------- scenarios: each returns (reproduced, evidence)

def a1a(w):
    rc1, o1 = w.run("install", "--profile", "dev-factory", "--host", "copilot-cli", "--scope", "user", "--skip-skills", "--apply")
    rc2, o2 = w.run("install", "--profile", "agent-intake", "--host", "copilot-cli", "--scope", "user", "--skip-skills", "--apply")
    rc3, o3 = w.run("verify", "--profile", "agent-intake", "--live", "--host", "copilot-cli")
    return (rc2 == 0 and rc3 == 0), "dev user install rc=%d; agent user install rc=%d; live verify rc=%d; %s" % (rc1, rc2, rc3, short(o2))


def a1b(w):
    rc0, _ = w.run("render", "--profile", "dev-factory", "--host", "claude-code", "--output", ".mcp.json")
    rc1, o1 = w.run("install", "--profile", "agent-intake", "--host", "copilot-cli", "--skip-skills", "--apply")
    rc2, o2 = w.run("verify", "--profile", "agent-intake", "--live", "--host", "copilot-cli")
    return (rc2 == 0), "render rc=%d; install rc=%d; live verify rc=%d; %s" % (rc0, rc1, rc2, short(o2))


def _skip_contract(w, key):
    lock = w.jload("toolchain", "toolchain.lock.json")
    lock["contracts"][key] = {"status": "skipped", "reason": "skipped", "detail": "license not accepted"}
    w.jsave(lock, "toolchain", "toolchain.lock.json")


def _findings(out):
    return {line for line in out.splitlines() if line.startswith("[WARN]") or line.startswith("[FAIL]")}


def _borrow_contract(w, key):
    """Make sure the lock holds a captured contract for key (the published lock held none): copy the reference one."""
    lock = w.jload("toolchain", "toolchain.lock.json")
    if lock["contracts"].get(key, {}).get("status") != "captured":
        with open(REFERENCE_LOCK, "r", encoding="utf-8") as handle:
            ref = json.load(handle)
        contract = ref["contracts"][key]
        server_id = key.split("/")[0]
        version = None
        for pkey, entry in lock["packages"].items():
            if pkey.endswith(":@microsoft/fabric-mcp") and server_id == "fabric-local":
                version = entry.get("version")
        contract["package_version"] = version or contract.get("package_version")
        lock["contracts"][key] = contract
        w.jsave(lock, "toolchain", "toolchain.lock.json")


def a2a(w):
    _borrow_contract(w, "fabric-local/docs")
    rc0, out0 = w.run("verify", "--profile", "agent-planner", "--strict")
    _skip_contract(w, "fabric-local/docs")
    rc1, out1 = w.run("verify", "--profile", "agent-planner", "--strict")
    new = sorted(_findings(out1) - _findings(out0))
    return (not new), "before the skip rc=%d; after rc=%d; new findings: %s" % (rc0, rc1, [short(n, 90) for n in new])


def a2b(w):
    _skip_contract(w, "fabric-local/docs")
    rc, out = w.run("render", "--profile", "agent-planner", "--host", "load-plan")
    return rc == 0, "load plan rc=%d; %s" % (rc, short(out, 100))


def a3(w):
    rc, out = w.run("render", "--profile", "agent-planner", "--host", "load-plan")
    if rc != 0:
        return False, "load plan refused rc=%d; %s" % (rc, short(out))
    plan = json.loads(out)
    bad = [m for m in plan["mcp"] if m["command"] in ("npx", "uvx", "dnx") and "--offline" not in m["args"]]
    return bool(bad), "%d launch(es) without an offline form: %s" % (len(bad), [m["command"] + " " + " ".join(m["args"][:3]) for m in bad])


def a4(w):
    rc, out = w.run("render", "--profile", "agent-planner", "--host", "load-plan")
    if rc != 0:
        return False, "load plan refused rc=%d" % rc
    plan = json.loads(out)
    names = [s["name"] for s in plan["skills"]] + [s["name"] for s in plan.get("repo_skills", [])]
    return "factory-router" not in names, "skills and repo skills in plan: %s" % names


def a5a(w):
    m = w.jload("toolchain", "toolchain.json")
    server(m, "fabric-local")["launch"]["command"] = "arbitrary-command"
    w.jsave(m, "toolchain", "toolchain.json")
    rc, out = w.run("verify", "--profile", "agent-planner")
    return rc == 0, "verify rc=%d; %s" % (rc, short(out))


def a5b(w):
    m = w.jload("toolchain", "toolchain.json")
    m["modes"]["agent"]["allow"] = dict(m["modes"]["dev"]["allow"])
    w.jsave(m, "toolchain", "toolchain.json")
    pr = w.jload("toolchain", "profiles.json")
    pr["profiles"]["agent-intake"]["mcp"] = [{"server": "fabric-core", "variant": "default"}]
    w.jsave(pr, "toolchain", "profiles.json")
    w.run("lock", "--no-network")
    rc, out = w.run("verify", "--profile", "agent-intake")
    return rc == 0, "verify rc=%d; %s" % (rc, short(out))


def a6(w):
    m = w.jload("toolchain", "toolchain.json")
    m["skill_sources"][0]["repo"] = "https://github.com/acme/other-skills.git"
    w.jsave(m, "toolchain", "toolchain.json")
    rc1, o1 = w.run("verify", "--profile", "agent-planner")
    rc2, o2 = w.run("lock", "--no-network")
    rc3, o3 = w.run("verify", "--profile", "agent-planner")
    return (rc1 != 0 and rc2 == 0 and rc3 == 0), "verify=%d, lock --no-network=%d, verify=%d; %s" % (rc1, rc2, rc3, short(o2))


def a7a(w):
    lock = w.jload("toolchain", "toolchain.lock.json")
    plugin = lock["skill_sources"]["skills-for-fabric"]["plugins"]["powerbi-authoring"]
    bundled = plugin.get("bundled_mcp", [])
    if bundled and isinstance(bundled[0], dict):
        bundled.append(dict(bundled[0], name="fabric-local"))
    else:
        bundled.append("fabric-local")
    plugin["bundled_mcp"] = bundled
    w.jsave(lock, "toolchain", "toolchain.lock.json")
    rc1, o1 = w.run("verify", "--profile", "agent-planner")
    rc2, o2 = w.run("render", "--profile", "agent-planner", "--host", "load-plan")
    return (rc1 != 0 and rc2 == 0), "verify=%d (%s); render load plan rc=%d" % (rc1, short(o1, 70), rc2)


def a7b(w):
    _borrow_contract(w, "fabric-local/docs")
    lock = w.jload("toolchain", "toolchain.lock.json")
    tools = lock["contracts"]["fabric-local/docs"]["tools"]
    first = next(iter(tools)) if isinstance(tools, dict) else 0
    tools[first]["read_only"] = False
    w.jsave(lock, "toolchain", "toolchain.lock.json")
    rc1, o1 = w.run("verify", "--profile", "agent-planner")
    rc2, o2 = w.run("render", "--profile", "agent-planner", "--host", "load-plan")
    return (rc1 != 0 and rc2 == 0), "verify=%d (%s); render load plan rc=%d" % (rc1, short(o1, 70), rc2)


def a8(w):
    m = w.jload("toolchain", "toolchain.json")
    srv = server(m, "powerbi-authoring-local")
    srv["variants"]["offline-readonly"]["env"] = {
        "PBI_MODELING_MCP_ACCEPT_EULA": {"from_env": "REVIEW_LICENSE", "default": "true"}}
    w.jsave(m, "toolchain", "toolchain.json")
    w.run("lock", "--no-network")
    rc, out = w.run("verify", "--profile", "agent-implementer")
    return rc == 0, "verify rc=%d; %s" % (rc, short(out))


def a9(w):
    w.write("---\nname: my-notes\ndescription: personal notes\n---\nmine\n", ".github", "skills", "my-notes", "SKILL.md")
    w.jsave({"profile": "agent-intake", "lock": ZERO, "skills": {"my-notes": ZERO}}, ".github", "skills", ".toolchain-managed.json")
    rc, out = w.run("install", "--profile", "agent-intake", "--host", "copilot-cli", "--skip-mcp", "--apply")
    gone = not os.path.exists(w.p(".github", "skills", "my-notes", "SKILL.md"))
    return gone, "install rc=%d; personal skill %s; %s" % (rc, "DELETED" if gone else "kept", short(out))


def a10(w):
    sentinel = w.p(".github", "skills", ".toolchain-new-factory-router", "sentinel.txt")
    w.write("user data\n", ".github", "skills", ".toolchain-new-factory-router", "sentinel.txt")
    rc, out = w.run("install", "--profile", "dev-docs", "--host", "copilot-cli", "--skip-mcp", "--apply")
    gone = not os.path.exists(sentinel)
    return gone, "install rc=%d; sentinel %s" % (rc, "DELETED" if gone else "kept")


def a11(w):
    if os.name != "nt":
        return False, "skipped: needs a Windows junction"
    outside = os.path.join(w.base, "outside")
    os.makedirs(outside)
    os.makedirs(w.p(".github"), exist_ok=True)
    made = subprocess.run(["cmd", "/c", "mklink", "/J", w.p(".github", "skills"), outside], capture_output=True, text=True)
    if made.returncode != 0:
        return False, "skipped: mklink failed: " + short(made.stdout + made.stderr)
    rc, out = w.run("install", "--profile", "dev-docs", "--host", "copilot-cli", "--skip-mcp", "--apply")
    written = os.path.exists(os.path.join(outside, "factory-router", "SKILL.md"))
    return written, "install rc=%d; wrote through the junction: %s" % (rc, written)


def a12(w):
    rc0, o0 = w.run("install", "--profile", "dev-docs", "--host", "copilot-cli", "--skip-mcp", "--apply")
    router = w.p("toolchain", "skills", "factory-router", "SKILL.md")
    with open(router, "a", encoding="utf-8", newline="\n") as handle:
        handle.write("\nA line that changes the digest.\n")
    code = (
        "import os, sys\n"
        "sys.path.insert(0, 'scripts')\n"
        "import toolchain as t\n"
        "real_replace, real_rename = os.replace, os.rename\n"
        "state = {'failed': False}\n"
        "def guard(real):\n"
        "    def inner(src, dst, *a, **k):\n"
        "        if (not state['failed'] and os.path.basename(str(dst)) == 'factory-router'\n"
        "                and os.path.basename(str(src)).startswith('.')):\n"
        "            state['failed'] = True\n"
        "            raise OSError('rename fault')\n"
        "        return real(src, dst, *a, **k)\n"
        "    return inner\n"
        "os.replace, os.rename = guard(real_replace), guard(real_rename)\n"
        "sys.exit(t.main(['install', '--profile', 'dev-docs', '--host', 'copilot-cli', '--skip-mcp', '--apply']))\n")
    rc, out = w.py(code)
    kept = os.path.isfile(w.p(".github", "skills", "factory-router", "SKILL.md"))
    return (not kept), "first install rc=%d; faulted install rc=%d; installed router %s; %s" % (
        rc0, rc, "kept" if kept else "GONE", short(out, 90))


def a13(w):
    w.run("render", "--profile", "agent-planner", "--write-project")
    digest = lock_digest(w)
    if not digest:
        return False, "could not compute the lock digest"
    w.jsave({"profile": "agent-planner", "lock": digest, "skills": {}}, ".github", "skills", ".toolchain-managed.json")
    rc, out = w.run("verify", "--profile", "agent-planner", "--live", "--host", "copilot-cli")
    return rc == 0, "live verify with an empty marker rc=%d; %s" % (rc, short(out))


def a14(w):
    log = os.path.join(w.base, "calls.log")
    for name in ("gh", "az"):
        w.shim(name, log)
    rc, out = w.run("doctor", "--offline", path_first=w.bin)
    calls = open(log, encoding="utf-8").read() if os.path.exists(log) else ""
    hit = [line for line in calls.splitlines() if "auth" in line or "account" in line]
    return bool(hit), "doctor --offline rc=%d; account calls: %s" % (rc, hit[:3])


def c4(w):
    lock = w.jload("toolchain", "toolchain.lock.json")
    lock["packages"]["nuget:Azure.Bicep.McpServer"] = {"status": "unresolved", "reason": "network", "detail": "tls"}
    w.jsave(lock, "toolchain", "toolchain.lock.json")
    rc1, o1 = w.run("render", "--profile", "dev-azure", "--host", "copilot-cli")
    rc2, o2 = w.run("verify", "--profile", "dev-azure", "--live", "--host", "copilot-cli")
    return rc1 != 0, "render dev-azure rc=%d (%s); live verify rc=%d" % (rc1, short(o1, 90), rc2)


def c6(w):
    log = os.path.join(w.base, "hosts.log")
    for name in ("copilot", "code", "claude"):
        w.shim(name, log)
    rc, out = w.run("install", "--skip-skills", "--apply", path_first=w.bin)
    wrote = os.path.exists(w.p(".mcp.json"))
    return wrote, "install rc=%d; .mcp.json %s" % (rc, "WRITTEN" if wrote else "not written")


def c7(w):
    log = os.path.join(w.base, "hosts.log")
    w.shim("claude", log)
    rc, out = w.run("doctor", "--offline", "--host", "claude-code", path_first=w.bin)
    line = next((l for l in out.splitlines() if "claude-code" in l and ".mcp.json" in l), "")
    return "render --write-project" in line, "doctor line: %s" % short(line, 140)


def c8(w):
    rc0, o0 = w.run("install", "--profile", "dev-docs", "--host", "copilot-cli", "--skip-mcp", "--apply")
    rc, out = w.run("verify", "--profile", "dev-factory", "--live", "--host", "copilot-cli")
    return rc == 0, "dev-docs install rc=%d; live verify of dev-factory rc=%d; %s" % (rc0, rc, short(out))


def c9(w):
    rc, out = w.run("list", "--profile", "dev-factory", "--skills")
    rc2, out2 = w.run("render", "--profile", "dev-factory", "--host", "load-plan")
    in_list = "factory-router" in out
    in_plan = rc2 == 0 and "factory-router" in out2
    return not (in_list and in_plan), "listed=%s, in load plan=%s" % (in_list, in_plan)


def n1_1(w):
    m = w.jload("toolchain", "toolchain.json")
    s = server(m, "fabric-local")
    s["variants"]["docs"]["args"] = [a for a in s["variants"]["docs"]["args"] if a not in ("--namespace", "docs")]
    w.jsave(m, "toolchain", "toolchain.json")
    rc0, _ = w.run("verify", "--profile", "agent-planner")
    rc1, _ = w.run("lock", "--no-network")
    rc2, _ = w.run("verify", "--profile", "agent-planner")
    rc3, out = w.run("render", "--profile", "agent-planner", "--host", "load-plan")
    return rc3 == 0, "verify after the edit=%d; lock --no-network=%d; verify=%d; load plan=%d" % (rc0, rc1, rc2, rc3)


def n1_2(w):
    m = w.jload("toolchain", "toolchain.json")
    server(m, "fabric-local")["launch"]["command"] = "npx.cmd"
    w.jsave(m, "toolchain", "toolchain.json")
    w.run("lock", "--no-network")
    rc_v, _ = w.run("verify", "--profile", "agent-planner")
    rc, out = w.run("render", "--profile", "agent-planner", "--host", "load-plan")
    if rc != 0:
        return False, "verify=%d; load plan refused rc=%d" % (rc_v, rc)
    mcp = json.loads(out)["mcp"][0]
    return "--offline" not in mcp["args"], "verify=%d; command=%s args=%s provisioning=%s" % (rc_v, mcp["command"], mcp["args"][:3], mcp.get("provisioning"))


def n1_3(w):
    path = w.p("toolchain", "skills", "factory-router", "SKILL.md")
    text = open(path, encoding="utf-8", newline="").read()
    padded = text.replace("description: ", "description: " + "padding " * 140, 1)
    open(path, "w", encoding="utf-8", newline="").write(padded)
    rc_v, _ = w.run("verify", "--profile", "agent-planner")
    rc_r, _ = w.run("render", "--profile", "agent-planner", "--host", "load-plan")
    lint_split = (rc_v != 0 and rc_r == 0)
    open(path, "w", encoding="utf-8", newline="").write(text)
    lock = w.jload("toolchain", "toolchain.lock.json")
    lock["contracts"]["fabric-local/docs"]["tools"] = {}
    w.jsave(lock, "toolchain", "toolchain.lock.json")
    rc_v2, _ = w.run("verify", "--profile", "agent-planner")
    rc_r2, _ = w.run("render", "--profile", "agent-planner", "--host", "load-plan")
    empty_split = (rc_v2 != 0 and rc_r2 == 0)
    return lint_split or empty_split, "router lint: verify=%d plan=%d; empty tools: verify=%d plan=%d" % (rc_v, rc_r, rc_v2, rc_r2)


def n1_4(w):
    w.write(json.dumps({"mcpServers": {"fabric-local": {"type": "stdio", "command": "evil", "args": ["x"]}}}), ".mcp.json")
    rc_d, out_d = w.run("doctor", "--offline", "--host", "copilot-cli")
    rc_v, out_v = w.run("verify", "--live", "--host", "copilot-cli")
    seen = ".mcp.json takes precedence" in out_d
    return (not seen) and rc_v != 0, "doctor rc=%d (names the shadowing file: %s); verify --live rc=%d" % (rc_d, seen, rc_v)


def n1_5(w):
    if os.name != "nt":
        return False, "skipped: needs a Windows junction"
    outside = os.path.join(w.base, "outside")
    os.makedirs(outside)
    rmtree(w.p(".factory"))
    made = subprocess.run(["cmd", "/c", "mklink", "/J", w.p(".factory"), outside], capture_output=True, text=True)
    if made.returncode != 0:
        return False, "skipped: mklink failed: " + short(made.stdout + made.stderr)
    rc, out = w.run("fetch", "--profile", "agent-planner")
    written = sum(len(files) for _d, _s, files in os.walk(outside))
    return written > 0, "fetch rc=%d; files written through the junction: %d; %s" % (rc, written, short(out, 80))


def n1_7(w):
    rc0, o0 = w.run("install", "--profile", "dev-docs", "--host", "copilot-cli", "--skip-mcp", "--apply")
    router = w.p("toolchain", "skills", "factory-router", "SKILL.md")
    with open(router, "a", encoding="utf-8", newline="\n") as handle:
        handle.write("\nA line that changes the digest.\n")
    code = (
        "import os, sys\n"
        "sys.path.insert(0, 'scripts')\n"
        "import toolchain as t\n"
        "real = os.replace\n"
        "state = {'failed': False}\n"
        "def inner(src, dst, *a, **k):\n"
        "    if not state['failed'] and os.path.basename(str(dst)) == 'factory-router' and os.path.basename(str(src)).startswith('.'):\n"
        "        state['failed'] = True\n"
        "        raise OSError('rename fault')\n"
        "    return real(src, dst, *a, **k)\n"
        "os.replace = inner\n"
        "sys.exit(t.main(['install', '--profile', 'dev-docs', '--host', 'copilot-cli', '--skip-mcp', '--apply']))\n")
    rc, out = w.py(code)
    traceback = "Traceback" in out
    claimed = "applied:" in out
    return traceback or claimed, "first install rc=%d; faulted install rc=%d; says applied: %s; traceback: %s" % (rc0, rc, claimed, traceback)


STANDIN = os.path.join(HERE, "standin_server.py")


def _stand_in(w, mode):
    code = (
        "import json, sys\n"
        "sys.path.insert(0, %r)\n"
        "import toolchain_mcp as m\n"
        "try:\n"
        "    r = m.probe_stdio([sys.executable, %r, %r], timeout=60)\n"
        "    print('RESULT ' + json.dumps({'era': r['era'], 'protocol': r['protocol'], 'server': r['server']}))\n"
        "except m.McpProbeError as e:\n"
        "    print('REFUSED ' + str(e))\n") % (w.p("scripts"), STANDIN, mode)
    return w.py(code)[1]


def n1_6(w):
    code = (
        "import json, sys\n"
        "sys.path.insert(0, 'scripts')\n"
        "import toolchain as t\n"
        "m = json.load(open('toolchain/toolchain.json', encoding='utf-8'))\n"
        "lock = json.load(open('toolchain/toolchain.lock.json', encoding='utf-8'))\n"
        "server = next(s for s in m['mcp_servers'] if s['id'] == 'fabric-local')\n"
        "def fake(argv, **k):\n"
        "    return {'era': 'modern', 'protocol': 'C:/' + 'Users/secret/token',\n"
        "            'server': {'name': 'C:/' + 'Users/secret/box', 'version': 'build.private.example'},\n"
        "            'tools': {'C:/' + 'Users/secret/tool': {'schema': 'sha256:' + '0' * 64, 'read_only': True, 'destructive': False, 'idempotent': True}}}\n"
        "c = t.capture_contract(m, lock['packages'], server, 'docs', t.Deps(probe_stdio=fake, env={}))\n"
        "print('CONTRACT ' + json.dumps(c))\n")
    rc, out = w.py(code)
    line = next((l for l in out.splitlines() if l.startswith("CONTRACT ")), "")
    if not line:
        return None, short(out, 200)
    c = json.loads(line[len("CONTRACT "):])
    leaked = c.get("status") == "captured" and (
        "/" in str(c.get("protocol")) or any("/" in n for n in c.get("tools", {})) or c.get("server", {}).get("version") == "build.private.example")
    return leaked, "status=%s protocol=%s version=%s tools=%s" % (
        c.get("status"), c.get("protocol"), (c.get("server") or {}).get("version"), list(c.get("tools", {}))[:2])


def n2_1(w):
    work = os.path.join(w.base, "n21")
    repo = os.path.join(work, "repo")
    os.makedirs(work)
    subprocess.run(["git", "init", "--quiet", repo], check=True)
    code = (
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "import toolchain_sources as ts\n"
        "try:\n"
        "    r = ts.resolve_git_ref('https://github.com/microsoft/skills-for-fabric.git', {'kind': 'tag', 'pattern': 'v0.3.*'})\n"
        "    print('RESOLVED ' + str(r.get('tag') if isinstance(r, dict) else getattr(r, 'tag', r)))\n"
        "except ts.SourceError as e:\n"
        "    print('SOURCE-ERROR ' + str(e))\n") % w.p("scripts")
    _rc0, out0 = w.py(code, cwd=work)
    subprocess.run(["git", "-C", repo, "config", "url.https://rewritten.invalid/.insteadOf", "https://github.com/"], check=True)
    _rc1, out1 = w.py(code, cwd=repo)
    if "RESOLVED" not in out0:
        return None, "inconclusive, the control did not resolve: " + short(out0, 100)
    return "RESOLVED" not in out1, "outside a repository: %s | inside a repository that rewrites the URL: %s" % (short(out0, 60), short(out1, 90))


def n2_2(w):
    if os.name != "nt":
        return False, "skipped: Windows only"
    work = os.path.join(w.base, "n22")
    os.makedirs(work)
    marker = os.path.join(work, "ran.txt")
    with open(os.path.join(work, "git.cmd"), "w", newline="") as handle:
        handle.write('@echo off\r\necho ran> "%s"\r\n' % marker)
    code = (
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "import toolchain_io as tio\n"
        "r = tio.SystemRunner().run(['git', '--version'], timeout=30)\n"
        "print('RC', r.returncode)\n") % w.p("scripts")
    _rc, out = w.py(code, cwd=work)
    ran = os.path.exists(marker)
    return ran, "a git.cmd in the current directory was executed: %s; %s" % (ran, short(out, 60))


def n2_4(w):
    code = (
        "import json, sys\n"
        "sys.path.insert(0, %r)\n"
        "import toolchain_io as tio, toolchain_sources as ts\n"
        "class R:\n"
        "    def run(self, argv, **k):\n"
        "        return tio.CommandResult(0, json.dumps({'version': '9.9.9', 'dist.integrity': 'sha512-' + 'A' * 86 + '=='}), '')\n"
        "    def http(self, method, url, **k):\n"
        "        return tio.HttpResult(404, {}, b'', None)\n"
        "print('OUT ' + json.dumps(ts.resolve_package('npm', '@microsoft/fabric-mcp', 'latest', R()), default=str))\n") % w.p("scripts")
    _rc, out = w.py(code)
    return '"status": "resolved"' in out, short(out, 200)


def n2_5(w):
    out = _stand_in(w, "future")
    return '"era": "modern"' in out, short(out, 160)


def n2_6(w):
    out = _stand_in(w, "boolproto")
    return out.startswith("RESULT") and '"protocol": "True"' in out, short(out, 160)


def n2_7(w):
    out = _stand_in(w, "leak")
    return out.startswith("RESULT") and ("ghp_" in out or "internal.contoso.corp" in out), short(out, 200)


def n2_3(w):
    if os.name != "nt":
        return False, "skipped: needs a Windows junction"
    shutil.copy2(os.path.join(w.tree, "scripts", "test_toolchain_sources.py"), w.p("scripts", "test_toolchain_sources.py"))
    work = os.path.join(w.base, "n23")
    out = os.path.join(work, "outside")
    os.makedirs(os.path.join(out, "victim"))
    with open(os.path.join(out, "victim", "f.txt"), "w") as handle:
        handle.write("keep")
    store = os.path.join(work, "pack")
    os.makedirs(store)
    made = subprocess.run(["cmd", "/c", "mklink", "/J", os.path.join(store, "skills"), out], capture_output=True, text=True)
    if made.returncode != 0:
        return False, "skipped: mklink failed: " + short(made.stdout + made.stderr)
    code = (
        "import sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, 'scripts')\n"
        "import toolchain_sources as ts, test_toolchain_sources as tts\n"
        "fx = tts.Fixture(Path(%r))\n"
        "r = tts.IsolatedRunner()\n"
        "lock = tts.lock_for(fx, r)\n"
        "try:\n"
        "    ts.vendor_skills(lock, [('fx', 'alpha', 'good-skill')], Path(%r), r)\n"
        "    print('VENDORED')\n"
        "except ts.SourceError as e:\n"
        "    print('SOURCE-ERROR ' + str(e))\n") % (os.path.join(work, "fx"), store)
    _rc, text = w.py(code)
    wrote = os.path.exists(os.path.join(out, "good-skill", "SKILL.md"))
    deleted = not os.path.exists(os.path.join(out, "victim"))
    return wrote or deleted, "wrote through the junction: %s; deleted a folder behind it: %s; %s" % (wrote, deleted, short(text, 120))


def n3_3(w):
    if os.name != "nt":
        return False, "skipped: Windows only"
    for name in ("fab", "powerbi-report-author"):
        with open(os.path.join(w.bin, name + ".cmd"), "w", newline="") as handle:
            handle.write("@echo off\r\necho 99.0.0\r\n")
    rc, out = w.run("doctor", "--offline", path_first=w.bin)
    lines = [l for l in out.splitlines() if "fab" in l.lower() or "powerbi-report-author" in l]
    passed = [l for l in lines if l.startswith("[PASS]") and "99.0.0" in l]
    return len(passed) == 2, "doctor rc=%d; lines for the two CLIs that pass at 99.0.0: %d of %d; %s" % (rc, len(passed), len(lines), short(" || ".join(lines), 220))


"""The scenarios of the third review (the delta review of the toolchain kit)."""


# ---------------------------------------------------------------- the delta review (R-D1-*, R-D2-*)

def d1_1(w):
    lock = w.jload("toolchain", "toolchain.lock.json")
    skill = lock["skill_sources"]["skills-for-fabric"]["plugins"]["powerbi-authoring"]["skills"]["semantic-model-authoring"]
    skill["findings"] = ["description longer than 1024 characters"]
    w.jsave(lock, "toolchain", "toolchain.lock.json")
    rc_v, _ = w.run("verify", "--profile", "agent-planner")
    code = (
        "import argparse, sys\n"
        "sys.path.insert(0, 'scripts')\n"
        "import toolchain as t\n"
        "called = []\n"
        "def vendor(*a, **k):\n"
        "    called.append(1)\n"
        "    return {'skills': {}}\n"
        "d = t.Deps(vendor_skills=vendor)\n"
        "try:\n"
        "    rc = t.cmd_fetch(argparse.Namespace(profile=['agent-planner'], store=None), d, '.')\n"
        "    print('FETCHED rc=%s vendor-called=%d' % (rc, len(called)))\n"
        "except t.ToolchainError as e:\n"
        "    print('REFUSED vendor-called=%d %s' % (len(called), str(e)[:60]))\n")
    _rc, out = w.py(code)
    return "FETCHED" in out and "vendor-called=1" in out, "verify rc=%d (V8); fetch: %s" % (rc_v, short(out, 100))


def d1_2(w):
    _rc, out = w.py("import sys; sys.path.insert(0, 'scripts'); import toolchain as t; "
                    "print(t.at_pin('fab 1.8.0rc1', '1.8.0'), t.at_pin('fab 1.8.0a1', '1.8.0rc1'))")
    return out.strip().endswith("True True"), "at_pin(1.8.0rc1, 1.8.0) and at_pin(1.8.0a1, 1.8.0rc1): " + short(out, 60)


def d1_3(w):
    if os.name != "nt":
        return False, "skipped: needs a Windows junction"
    work = os.path.join(w.base, "d13")
    outside = os.path.join(work, "outside")
    source = os.path.join(work, "source")
    os.makedirs(outside)
    os.makedirs(source)
    with open(os.path.join(outside, "secret.txt"), "w") as handle:
        handle.write("outside")
    with open(os.path.join(source, "SKILL.md"), "w") as handle:
        handle.write("x")
    made = subprocess.run(["cmd", "/c", "mklink", "/J", os.path.join(source, "linked"), outside], capture_output=True, text=True)
    if made.returncode != 0:
        return False, "skipped: mklink failed: " + short(made.stdout + made.stderr)
    code = (
        "import sys\n"
        "sys.path.insert(0, 'scripts')\n"
        "import toolchain as t\n"
        "try:\n"
        "    t.copy_tree(%r, %r)\n"
        "    print('COPIED')\n"
        "except t.ToolchainError as e:\n"
        "    print('REFUSED ' + str(e)[:80])\n") % (source, os.path.join(work, "target"))
    _rc, out = w.py(code)
    leaked = os.path.exists(os.path.join(work, "target", "linked", "secret.txt"))
    return leaked, "copy of a folder with a junction inside: %s; the file behind the junction was copied: %s" % (short(out, 60), leaked)


def d1_4(w):
    _borrow_contract(w, "fabric-local/docs")
    code = (
        "import json, sys\n"
        "sys.path.insert(0, 'scripts')\n"
        "import toolchain as t\n"
        "m = json.load(open('toolchain/toolchain.json', encoding='utf-8'))\n"
        "lock = json.load(open('toolchain/toolchain.lock.json', encoding='utf-8'))\n"
        "contract = lock['contracts']['fabric-local/docs']\n"
        "server = next(s for s in m['mcp_servers'] if s['id'] == 'fabric-local')\n"
        "server['variants']['docs']['args'] = ['server', 'start', '--mode', 'all']\n"
        "lock['inputs_digest'] = t.inputs_digest(m)\n"
        "json.dump(m, open('toolchain/toolchain.json', 'w', encoding='utf-8'), indent=2)\n"
        "json.dump(lock, open('toolchain/toolchain.lock.json', 'w', encoding='utf-8'), indent=2)\n"
        "calls = []\n"
        "def fake(argv, **k):\n"
        "    calls.append(list(argv))\n"
        "    return {'era': contract['era'], 'protocol': contract['protocol'], 'server': contract['server'], 'tools': contract['tools']}\n"
        "rc = t.main(['verify', '--contracts', '--profile', 'agent-planner'], deps=t.Deps(probe_stdio=fake, env={}))\n"
        "print('LAUNCHED %d time(s) rc=%s %s' % (len(calls), rc, calls[0][-4:] if calls else ''))\n")
    _rc, out = w.py(code)
    line = next((l for l in out.splitlines() if l.startswith("LAUNCHED")), "")
    return bool(line) and not line.startswith("LAUNCHED 0"), short(line or out, 160)


def d1_5(w):
    m = w.jload("toolchain", "toolchain.json")
    server(m, "fabric-local")["package"]["track"] = "1.7.0"
    w.jsave(m, "toolchain", "toolchain.json")
    rc, out = w.run("lock", "--no-network")
    rc_v, out_v = w.run("verify")
    return rc == 0, "lock --no-network rc=%d, then verify rc=%d (%s)" % (rc, rc_v, short(out_v.splitlines()[-1] if out_v.splitlines() else "", 60))


def d1_6(w):
    rc0, o0 = w.run("install", "--profile", "dev-docs", "--host", "copilot-cli", "--skip-mcp", "--apply")
    folder = w.p(".github", "skills", "factory-router")
    rmtree(folder)
    with open(folder, "w") as handle:
        handle.write("not a folder")
    rc1, o1 = w.run("install", "--profile", "dev-docs", "--host", "copilot-cli", "--skip-mcp", "--apply", "--force")
    rc2, o2 = w.run("verify", "--live", "--profile", "dev-docs", "--host", "copilot-cli")
    crashed = "Traceback" in o1 or "Traceback" in o2
    return crashed, "first install rc=%d; forced install over a file: rc=%d traceback=%s; verify --live traceback=%s" % (
        rc0, rc1, "Traceback" in o1, "Traceback" in o2)


def d1_7(w):
    rc0, _ = w.run("install", "--profile", "dev-docs", "--host", "claude-code", "--skip-mcp", "--apply")
    rc1, out = w.run("doctor", "--offline", "--host", "claude-code", "--profile", "agent-planner")
    hint = next((l for l in out.splitlines() if "was installed for profile" in l), "")
    return bool(hint) and "--host claude-code" not in hint, "install rc=%d; hint: %s" % (rc0, short(hint, 170))


def d1_9(w):
    _rc, out = w.py("import sys; sys.path.insert(0, 'scripts'); import toolchain as t; "
                    "print(t.probe_environment({'ACME_MODE': {'from_env': 'ACME_MODE', 'default': 'safe'}, "
                    "'ACME_TARGET': {'from_env': 'ACME_TARGET'}}, {'ACME_MODE': '', 'ACME_TARGET': ''}, None, ()))")
    return "'ACME_MODE': ''" in out, "an empty operator value in the probe environment: " + short(out, 80)


def _git_fixture(w, name):
    """Source for the scenarios that run real git: the Fixture of the helper tests, a throw-away folder."""
    shutil.copy2(os.path.join(w.tree, "scripts", "test_toolchain_sources.py"), w.p("scripts", "test_toolchain_sources.py"))
    return os.path.join(w.base, name)


def d2_1(w):
    work = _git_fixture(w, "d21")
    code = (
        "import subprocess, sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, 'scripts')\n"
        "import toolchain_sources as ts, test_toolchain_sources as tts\n"
        "base = Path(%r)\n"
        "fx = tts.Fixture(base / 'fx')\n"
        "common = base / 'common.git'\n"
        "subprocess.run(['git', 'init', '--bare', '--quiet', str(common)], check=True)\n"
        "marker = base / 'ran.txt'\n"
        "script = base / 'u.sh'\n"
        "script.write_text(\"echo ran > '%%s'\\nexit 1\\n\" %% marker.as_posix(), newline='\\n')\n"
        "with open(common / 'config', 'a', encoding='utf-8', newline='\\n') as h:\n"
        "    h.write('[remote \"%%s\"]\\n\\tuploadpack = sh \\'%%s\\'\\n' %% (fx.url, script.as_posix()))\n"
        "cache = base / 'cache.git'\n"
        "subprocess.run(['git', 'init', '--bare', '--quiet', str(cache)], check=True)\n"
        "(cache / 'commondir').write_text(str(common) + '\\n')\n"
        "try:\n"
        "    ts.fetch_git(fx.url, fx.commits[3], cache, tts.RecordingRunner())\n"
        "    print('FETCHED')\n"
        "except ts.SourceError as e:\n"
        "    print('SOURCE-ERROR ' + str(e))\n"
        "print('MARKER', marker.exists(), 'COMMONDIR-LEFT', (cache / 'commondir').exists())\n") % work
    _rc, out = w.py(code)
    ran = "MARKER True" in out
    return ran, "a commondir file in the cache points at a repository whose configuration names a program: " + short(out, 150)


def d2_3(w):
    if os.name != "nt":
        return False, "skipped: needs a Windows junction"
    work = _git_fixture(w, "d23")
    outside = os.path.join(w.base, "d23-outside")
    os.makedirs(outside)
    code = (
        "import os, shutil, stat, subprocess, sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, 'scripts')\n"
        "import toolchain_sources as ts, test_toolchain_sources as tts\n"
        "base = Path(%r)\n"
        "fx = tts.Fixture(base / 'fx')\n"
        "cache = base / 'cache.git'\n"
        "ts.fetch_git(fx.url, fx.commits[3], cache, tts.RecordingRunner())\n"
        "def unlock(function, path, _info):\n"
        "    os.chmod(path, stat.S_IWRITE)\n"
        "    function(path)\n"
        "shutil.rmtree(cache / 'objects', onerror=unlock)\n"
        "made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(cache / 'objects'), %r], capture_output=True, text=True)\n"
        "print('MKLINK', made.returncode)\n"
        "try:\n"
        "    ts.fetch_git(fx.url, fx.commits[3], cache, tts.RecordingRunner())\n"
        "    print('FETCHED')\n"
        "except ts.SourceError as e:\n"
        "    print('SOURCE-ERROR ' + str(e))\n") % (work, outside)
    _rc, out = w.py(code)
    written = sum(len(files) for _d, _s, files in os.walk(outside))
    return written > 0, "files written behind the junction inside the cache: %d; %s" % (written, short(out, 100))


def d2_4(w):
    code = (
        "import json, sys\n"
        "sys.path.insert(0, %r)\n"
        "import toolchain_io as tio, toolchain_sources as ts\n"
        "class R:\n"
        "    def run(self, argv, **k):\n"
        "        return tio.CommandResult(0, json.dumps({'version': '9.9.9', 'dist.integrity': 'sha512-' + 'A' * 86 + '=='}), '')\n"
        "    def http(self, method, url, **k):\n"
        "        return tio.HttpResult(404, {}, b'', 'too-large')\n"
        "print('OUT ' + json.dumps(ts.resolve_package('npm', '@microsoft/fabric-mcp', 'latest', R()), default=str))\n") % w.p("scripts")
    _rc, out = w.py(code)
    return '"status": "resolved"' in out, short(out, 200)


def d2_5(w):
    out = _stand_in(w, "futureok")
    return out.startswith("RESULT") and "2027-01-01" in out, "initialize answered with a revision that the probe does not speak: " + short(out, 120)


def d2_6(w):
    if os.name != "nt":
        return False, "skipped: Windows only"
    work = os.path.join(w.base, "d26")
    os.makedirs(work)
    first, second = os.path.join(work, "first.txt"), os.path.join(work, "second.txt")
    with open(first, "w") as handle:
        handle.write("keep")
    os.chmod(first, stat.S_IREAD)
    try:
        os.link(first, second)
    except OSError as exc:
        return False, "skipped: no hard link: %r" % (exc,)
    code = (
        "import sys\n"
        "sys.path.insert(0, 'scripts')\n"
        "import toolchain_io as tio\n"
        "tio.make_writable(%r)\n") % second
    w.py(code)
    writable = bool(os.stat(first).st_mode & stat.S_IWRITE)
    return writable, "the other name of a read-only file is writable afterwards: %s" % writable


SCENARIOS = [
    ("A-1a", "an agent profile installed at user scope keeps the dev servers, and live verify passes", a1a),
    ("A-1b", ".mcp.json shadows the rendered project file, and live verify passes", a1b),
    ("A-2a", "a skipped contract passes verify --strict for an agent profile", a2a),
    ("A-2b", "a skipped contract does not stop the load plan", a2b),
    ("A-3", "the agent load plan launches with a run-time installer form", a3),
    ("A-4", "the load plan omits factory-router", a4),
    ("A-5a", "an edited launch command keeps the lock fresh", a5a),
    ("A-5b", "a hosted server in an agent profile once the mode list is edited", a5b),
    ("A-6", "lock --no-network launders a changed source repository", a6),
    ("A-7a", "a bundled-name collision passes the load plan", a7a),
    ("A-7b", "a write tool in a read-only contract passes the load plan", a7b),
    ("A-8", "a variant defaults the license to true", a8),
    ("A-9", "a marker with zero digests authorises deleting a personal skill", a9),
    ("A-10", "a staging-shaped folder of the user is deleted", a10),
    ("A-11", "install writes through a junction", a11),
    ("A-12", "a failed replace leaves no installed skill", a12),
    ("A-13", "an empty marker passes live verify", a13),
    ("A-14", "doctor --offline calls the account checks", a14),
    ("C-4", "one unresolved package stops render for a profile", c4),
    ("C-6", "install writes .mcp.json when Claude Code is on the PATH", c6),
    ("C-7", "the doctor hint for .mcp.json names render --write-project", c7),
    ("C-8", "live verify passes with only the router installed", c8),
    ("C-9", "the router is missing from list or from the load plan", c9),
    ("N1-1", "a changed launch keeps the old captured contract and the load plan passes", n1_1),
    ("N1-2", "a renamed launcher drops --offline but the plan says preinstalled", n1_2),
    ("N1-3", "render passes where verify fails (router lint, empty contract)", n1_3),
    ("N1-4", "doctor misses a shadowing .mcp.json", n1_4),
    ("N1-5", "fetch writes the pack through a junction", n1_5),
    ("N1-7", "install says applied before it applies and a failed rename is a traceback", n1_7),
    ("N1-6", "probe text (protocol, tool names, a host-shaped version) reaches the contract", n1_6),
    ("N2-1", "git reads the config of the repository in the current directory", n2_1),
    ("N2-2", "a launcher in the current directory is executed instead of the one on PATH", n2_2),
    ("N2-3", "vendor_skills writes and deletes through a junction used as the skills folder of the pack", n2_3),
    ("N2-4", "npm CLI answer accepted when the registry says 404", n2_4),
    ("N2-5", "initialize that names only a future revision is taken as the modern one", n2_5),
    ("N2-6", "a boolean protocolVersion is accepted", n2_6),
    ("N2-7", "a token-shaped name and a host-shaped version reach the contract", n2_7),
    ("N3-3", "doctor passes CLIs at a version that is not the pinned one", n3_3),
    ("D1-1", "fetch vendors a profile that verify refuses (a lint finding of a locked skill in agent mode)", d1_1),
    ("D1-2", "a pre-release passes for the pinned release", d1_2),
    ("D1-3", "copy_tree follows a junction inside a skill folder", d1_3),
    ("D1-4", "verify --contracts launches a server whose launch changed", d1_4),
    ("D1-5", "lock --no-network accepts a changed package pin", d1_5),
    ("D1-6", "a managed skill folder replaced by a file crashes install and verify --live", d1_6),
    ("D1-7", "the doctor hint for a Claude Code skills folder omits the host", d1_7),
    ("D1-9", "an empty operator variable is handed to a server instead of its default", d1_9),
    ("D2-1", "a commondir file in the cache makes git run a program of another repository", d2_1),
    ("D2-3", "a junction inside the cache receives what git writes", d2_3),
    ("D2-4", "a body error erases an authoritative 404 so that the npm CLI stands alone", d2_4),
    ("D2-5", "a successful initialize that names an unsupported revision is accepted", d2_5),
    ("D2-6", "clearing the read-only attribute changes the other name of a hard-linked file", d2_6),
]


def main(argv):
    global REFERENCE_LOCK
    if not argv:
        print(__doc__)
        return 2
    tree = os.path.abspath(argv[0])
    only = None
    pack = None
    keep = "--keep" in argv
    if "--only" in argv:
        only = set(argv[argv.index("--only") + 1].split(","))
    if "--pack" in argv:
        pack = argv[argv.index("--pack") + 1]
    if "--reference-lock" in argv:
        REFERENCE_LOCK = os.path.abspath(argv[argv.index("--reference-lock") + 1])
    reproduced = 0
    shown = 0
    for sid, what, fn in SCENARIOS:
        if only and sid not in only:
            continue
        shown += 1
        started = time.time()
        w = Work(tree, pack)
        try:
            hit, evidence = fn(w)
        except Exception as exc:  # a broken scenario must not hide the others
            hit, evidence = None, "scenario error: %r" % (exc,)
        finally:
            if keep:
                print("   kept: " + w.base)
            else:
                w.close()
        flag = "REPRODUCED" if hit else ("error" if hit is None else "not reproduced")
        reproduced += 1 if hit else 0
        print("%-5s %-14s %s\n        %s  [%.0fs]" % (sid, flag, what, evidence, time.time() - started))
        sys.stdout.flush()
    print("\n%d scenario(s), %d reproduced" % (shown, reproduced))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
