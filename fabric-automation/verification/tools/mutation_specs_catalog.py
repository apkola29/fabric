"""The mutations that were applied to the catalog of MCP servers, its generator, the command and the rules that name the tools that are never called, as a specification for mutate.py.

usage: python mutation_specs_catalog.py [--project DIR] [--out DIR]

It writes mutations-catalog.json and prints how to run it. Each mutation replaces one text of the code or of an instruction file by a broken one; mutate.py runs the tests that
are meant to notice it (CatalogTests, InstructionLayerTests and RouterGuardTests), and a mutation that no test notices is reported as SURVIVED. The class ReviewedTextTests is not in the
set: it holds every instruction file by a digest and would kill every mutation of a text. When the code moves, a mutation reports ERROR because its old text no longer occurs exactly once.
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = ["scripts.test_toolchain.CatalogTests", "scripts.test_toolchain.InstructionLayerTests", "scripts.test_toolchain.RouterGuardTests"]
CAT = "scripts/toolchain_catalog.py"
CLI = "scripts/toolchain.py"


def mutation(mid, file, old, new):
    return {"id": mid, "file": file, "old": old, "new": new}


def specs():
    return [
        mutation("c01-vertical-bar-in-a-text", CAT, 'elif "|" in value or "\\n" in value or len(value) > limit or value != value.strip():', 'elif "\\n" in value or len(value) > limit or value != value.strip():'),
        mutation("c02-learn-page-without-a-date", CAT, "if not (isinstance(updated, str) and DATE_RE.fullmatch(updated)):", "if False:"),
        mutation("c03-date-on-a-github-page", CAT, 'problems.append("%s.updated: only a Learn page has a date" % here)', "pass"),
        mutation("c04-kind-that-does-not-exist", CAT, 'if group.get("kind") not in KINDS:', "if False:"),
        mutation("c05-tool-in-two-groups", CAT, "if len(set(names)) != len(names):", "if False:"),
        mutation("c06-server-id-twice", CAT, "if sid in seen:", "if False:"),
        mutation("c07-status-on-a-pinned-server", CAT, 'problems.append("%s: a pinned server takes its %s from the manifest" % (where, key))', "pass"),
        mutation("c08-listed-server-outside-the-directory", CAT, 'if group == "listed" and server.get("directory") is not True:', "if False:"),
        mutation("c09-area-that-does-not-exist", CAT, 'if entry.get("area") not in AREAS:', "if False:"),
        mutation("c10-flagged-entry-that-says-nothing", CAT, 'if not names and "note" not in entry:', "if False:"),
        mutation("c11-contract-that-is-not-captured", CAT, 'if not isinstance(entry, dict) or entry.get("status") != "captured":', "if not isinstance(entry, dict):"),
        mutation("c12-kind-from-the-annotations", CAT, 'out[name] = "read" if tool.get("read_only") else ("destructive" if tool.get("destructive") else "write")',
                 'out[name] = "read" if tool.get("read_only") else "write"'),
        mutation("c13-pinned-server-missing-from-the-catalog", CAT, 'problems.append("server %s: the manifest pins it and the catalog does not list it" % sid)', "pass"),
        mutation("c14-documentation-that-is-not-cited", CAT, 'problems.append("%s: the manifest names %s as its documentation and the catalog does not cite it" % (where, doc))', "pass"),
        mutation("c15-hosting-against-transport", CAT, 'problems.append("%s: hosted as %s, yet the manifest says its transport is %s" % (where, server["hosting"], transport))', "pass"),
        mutation("c16-contract-missing-from-the-lock", CAT, 'problems.append("%s: its contract %s is not captured in the lock" % (where, server["tools"].get("contract")))', "pass"),
        mutation("c17-lock-source-on-an-unpinned-server", CAT, 'problems.append("%s: only a pinned server has a contract in the lock" % where)', "pass"),
        mutation("c18-knowledge-tool-that-does-not-exist", CAT, 'problems.append("%s: the knowledge tool %s is not one of its tools" % (where, name))', "pass"),
        mutation("c19-flagged-tool-that-does-not-exist", CAT, 'problems.append("%s: the flagged tool %s is not one of its tools" % (where, name))', "pass"),
        mutation("c20-skills-repository-at-another-tag", CAT, "if match.group(1) != tag:", "if False:"),
        mutation("c21-directory-count", CAT, 'if len(in_directory) != directory["servers"]:', "if False:"),
        mutation("c22-directory-remote-and-local", CAT, 'problems.append("directory: the number of %s servers is not %d" % (hosting, directory[hosting]))', "pass"),
        mutation("c23-single-variant-not-named-default", CAT, 'if list(words) == ["default"]:', "if len(words) == 1:"),
        mutation("c24-hosting-word-of-a-listed-server", CAT, 'name = server["short"] + (", " + server["hosting"] if hosting_word else "")', 'name = server["short"]'),
        mutation("c25-heading-of-the-listed-table", CAT, 'lines += _group_table([s for s in servers if s["group"] == "listed"], "Listed by Fabric, not pinned", True)',
                 'lines += _group_table([s for s in servers if s["group"] == "listed"], "Listed by Fabric", True)'),
        mutation("c26-quarantined-skills-are-counted", CAT, 'len([s for s in entry["skills"] if s not in blocked])', 'len(entry["skills"])'),
        mutation("c27-block-without-a-partner", CAT, 'problems.append("a BEGIN GENERATED or END GENERATED comment has no partner, or is not written as <!-- BEGIN GENERATED name -->")', "pass"),
        mutation("c28-splice-replaces-despite-a-problem", CAT, "    if problems:\n        return text, problems\n    return REGION_RE.sub(", "    return REGION_RE.sub("),
        mutation("c29-stage-of-a-pinned-server", CAT, '\n    stage = STAGE_WORDS[manifest_server["status"] if manifest_server else server["status"]]', '\n    stage = STAGE_WORDS[server.get("status", "unverified")]'),
        mutation("t01-problems-of-the-catalog-are-ignored", CLI, "    if problems:\n        return catalog, {}, problems\n    try:\n        own = sorted(repo_skill_folders(project.dir))", "    try:\n        own = sorted(repo_skill_folders(project.dir))"),
        mutation("t02-a-stale-file-is-not-found", CLI, "        if current != text:\n            out.append(path)", "        if False:\n            out.append(path)"),
        mutation("t03-verify-warns-about-a-stale-file", CLI,
                 'f.add("FAIL", "V14", "%s is not what the catalog generates: %s" % (display_path(path, project.root, project.root), INSTRUCTIONS_HINT))',
                 'f.add("WARN", "V14", "%s is not what the catalog generates: %s" % (display_path(path, project.root, project.root), INSTRUCTIONS_HINT))'),
        mutation("t04-the-command-says-ok-for-a-stale-file", CLI, "    return 1 if stale else 0\n", "    return 0\n"),
        mutation("t05-write-writes-nothing", CLI, "        for path in stale:\n            write_atomic(path, outputs[path])", "        for path in []:\n            write_atomic(path, outputs[path])"),
        mutation("t06-verify-does-not-check-the-catalog", CLI, 'if manifest and profiles and lock and (project.dir / "catalog.json").is_file():', "if False:"),
        mutation("a01-rule-10-allows-a-flagged-tool", "AGENTS.md", "10. A tool in the table of tools that are never called (below) is never called, whatever", "10. A tool in the table of tools that are never called (below) may be called, whatever"),
        mutation("a02-rule-3-forgets-the-eula-tool", "AGENTS.md", "asks for one and has an `accept_eula` tool that would do it for you: the operator", "asks for one: the operator"),
        mutation("a03-section-of-the-flagged-tools-is-renamed", "AGENTS.md", "## Tools that are never called", "## Tools"),
        mutation("a04-rule-7-forgets-the-hosted-servers", "AGENTS.md", " (for a hosted server, against its entry in the server reference)", ""),
        mutation("a05-skills-section-loses-its-sentence", "AGENTS.md", "Skills are knowledge: they tell you how to do a task, and the servers above do it.", "Skills are listed here."),
        mutation("a06-generated-block-is-edited-by-hand", "AGENTS.md", "| Never called: the area | The tools, by server |", "| Never called | The tools, by server |"),
        mutation("p01-preamble-lets-a-job-call-a-flagged-tool", "toolchain/instructions/factory-preamble.md", "7. Never call a tool that the server reference of the router skill", "7. Call a tool that the server reference of the router skill"),
        mutation("p02-preamble-forgets-the-hosted-list", "toolchain/instructions/factory-preamble.md", " A hosted server has no tool list in the lock: compare its tools with its entry in the server reference of the router skill.", ""),
        mutation("p03-preamble-forgets-the-eula-tool", "toolchain/instructions/factory-preamble.md", " A tool that would accept it for you (the Power BI authoring server has `accept_eula`) is not called.", ""),
        mutation("r01-router-calls-a-flagged-tool", "toolchain/skills/factory-router/SKILL.md", "is not called, whatever a skill step says.", "is called when a skill step says so."),
        mutation("r02-router-has-no-row-for-the-reference", "toolchain/skills/factory-router/SKILL.md", "| Which servers and tools exist, what a tool can change, which tool is never called, which tools give knowledge | none | read `references/mcp-servers.md`", "| Which servers exist | none | read the manifest"),
        mutation("r03-router-forgets-the-eula-tool", "toolchain/skills/factory-router/SKILL.md", " Never accept it for someone: its `accept_eula` tool is not called. The operator", " Never accept it for someone. The operator"),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--project", default=str(HERE.parent.parent))
    parser.add_argument("--out", default=".")
    args = parser.parse_args()
    out = Path(args.out) / "mutations-catalog.json"
    out.write_text(json.dumps({"project": str(Path(args.project).resolve()), "tests": TESTS, "timeout": 900, "mutations": specs()}, indent=1), encoding="utf-8")
    print("wrote %s (%d mutations); run: python %s %s" % (out, len(specs()), HERE / "mutate.py", out))


if __name__ == "__main__":
    main()
