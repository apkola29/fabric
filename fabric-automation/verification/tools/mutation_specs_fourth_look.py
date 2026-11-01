"""The 21 mutations that were applied to the fixes of the fourth look at the toolchain kit, as specifications for mutate.py.

usage: python mutation_specs_fourth_look.py [--project DIR] [--out DIR]

It writes three JSON files (mutations-fourth-look-a.json, -b.json and -c.json) and prints how to run them. Each mutation replaces one text of
the code by a broken one; mutate.py runs the tests that are meant to notice it, and a mutation that no test notices is reported as SURVIVED.
The texts are those of scripts/toolchain.py and scripts/toolchain_sources.py as published in commit 97a0d74a64 (and unchanged in later
commits that do not touch these lines): when the code moves, a mutation reports ERROR because its old text no longer occurs exactly once.
Each mutation is named after the finding that its safeguard answers (R-E1-1 to R-E1-5 of docs/reviews/toolchain-recheck-findings.md; the
ones named s1 belong to R-E2-1).
"""
import argparse
import json
import os
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLI_TESTS = ["scripts.test_toolchain.LinkTests", "scripts.test_toolchain.InstallSafetyTests",
             "scripts.test_toolchain.HostTests", "scripts.test_toolchain.InstalledStateTests"]


def mutation(mid, old, new, file="scripts/toolchain.py"):
    return {"id": mid, "file": file, "old": old, "new": new}


def specs():
    cli = [
        mutation("e1-unlink-link-old-fallback",
                 """        except OSError as refused:
            try:
                os.rmdir(path)  # Windows removes a junction like an empty folder
            except OSError:
                raise refused from None  # what the link itself said: a file link that is held for a moment is a PermissionError, which is waited for
""",
                 """        except OSError:
            os.rmdir(path)  # Windows removes a junction like an empty folder
"""),
        mutation("e1-unlink-link-raises-the-rmdir-error", "                raise refused from None", "                raise"),
        mutation("e2-repo-skills-no-inner-check", "            linked = link_inside(entry)\n", "            linked = entry if is_link(entry) else None\n"),
        mutation("e2-link-inside-no-self-test",
                 "    if is_link(folder):\n        return Path(folder)\n    for current, dirs, names in os.walk(folder):",
                 "    for current, dirs, names in os.walk(folder):"),
        mutation("e4-verify-reads-without-guard",
                 """        try:
            same = read_text_lf(path, rel) == dump_json(render(host, resolved))
        except ToolchainError:
            same = False  # a file that cannot be read as text is not the rendering
""",
                 """        same = read_text_lf(path, rel) == dump_json(render(host, resolved))
"""),
        mutation("e4-doctor-reads-without-guard",
                 """            try:
                same = read_text_lf(path, spec["mcp_project"]) == dump_json(render(host, resolved))
            except ToolchainError:
                same = False  # a file that cannot be read as text is not the rendering
""",
                 """            same = read_text_lf(path, spec["mcp_project"]) == dump_json(render(host, resolved))
"""),
        mutation("e1-user-mcp-file-checked-for-every-mode", '            if spec.get("mcp_user") and user_level:', '            if spec.get("mcp_user"):'),
        mutation("e1-user-skills-folder-checked-for-every-mode", '            if spec.get("skills_user") and user_level:', '            if spec.get("skills_user"):'),
        mutation("e1-user-level-for-agent-profiles-too", 'user_level = resolved["mode"] == "dev"', 'user_level = resolved["mode"] != "executor"'),
        mutation("e1-differing-entry-has-the-plain-hint", "(label, sid, replace_tail))", "(label, sid, tail))"),
        mutation("e1-replace-tail-is-the-plain-tail", 'replace_tail = " (%s)" % (replace_hint or hint) if (replace_hint or hint) else ""', "replace_tail = tail"),
        mutation("e1-replace-command-keeps-the-skills", '        command += " --skip-skills --force"', '        command += " --force"'),
        mutation("e1-replace-command-does-not-force", '        command += " --skip-skills --force"', '        command += " --skip-skills"'),
        mutation("e1-call-site-gives-no-replace-hint", '                                     replace_hint=install_command(name, default, [host], "user", replace_mcp=True))',
                 "                                     replace_hint=None)"),
        mutation("e5-doctor-skills-hint-without-the-host",
                 "    skills, shared = skills_dir_problems(project, deps, resolved, directory, rel, marker, hint)",
                 '    skills, shared = skills_dir_problems(project, deps, resolved, directory, rel, marker, INSTALL_HINT + " --profile " + resolved["name"])'),
        mutation("e5-store-problems-shared-entry-not-a-dict",
                 """        if not isinstance(entry, dict) or entry.get("digest") != item["digest"]:
            out.append(("WARN", "the local pack does not list shared folder""",
                 """        if entry is None or entry.get("digest") != item["digest"]:
            out.append(("WARN", "the local pack does not list shared folder"""),
    ]
    inside = [
        mutation("e2-link-inside-names-only", "        for entry in dirs + names:\n            if is_link(Path(current) / entry):\n",
                 "        for entry in names:\n            if is_link(Path(current) / entry):\n"),
        mutation("e2-link-inside-dirs-only", "        for entry in dirs + names:\n            if is_link(Path(current) / entry):\n",
                 "        for entry in dirs:\n            if is_link(Path(current) / entry):\n"),
    ]
    proxy = [
        mutation("s1-proxy-removed-from-network-calls",
                 '_GIT_NETWORK_DROPPED = ("GIT_ASKPASS", "GIT_SSH", "GIT_SSH_COMMAND", "SSH_ASKPASS", "NETRC",\n',
                 '_GIT_NETWORK_DROPPED = ("GIT_ASKPASS", "GIT_SSH", "GIT_SSH_COMMAND", "SSH_ASKPASS", "NETRC", "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY",\n',
                 "scripts/toolchain_sources.py"),
        mutation("s1-proxy-removed-from-every-call",
                 '    env = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}\n',
                 '    env = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0", "HTTPS_PROXY": None, "HTTP_PROXY": None}\n',
                 "scripts/toolchain_sources.py"),
        mutation("s1-proxy-auth-method-removed",
                 '        env["GIT_ALLOW_PROTOCOL"] = "https:file" if file_url else "https"\n',
                 '        env["GIT_ALLOW_PROTOCOL"] = "https:file" if file_url else "https"\n        env["GIT_HTTP_PROXY_AUTHMETHOD"] = None\n',
                 "scripts/toolchain_sources.py"),
    ]
    return {"a": (CLI_TESTS, cli), "b": (["scripts.test_toolchain.LinkTests"], inside),
            "c": (["scripts.test_toolchain_sources.GitIsolationTests"], proxy)}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--project", default=str(HERE.parents[1]), help="the project folder (default: the one this folder is in)")
    parser.add_argument("--out", default=tempfile.gettempdir(), help="where the JSON files go (default: the temporary folder)")
    args = parser.parse_args()
    total = 0
    for key, (tests, mutations) in specs().items():
        path = os.path.join(args.out, "mutations-fourth-look-%s.json" % key)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"project": os.path.abspath(args.project), "tests": tests, "timeout": 900, "mutations": mutations}, handle, indent=1)
        total += len(mutations)
        print('wrote %s (%d mutation(s)); run: python "%s" "%s"' % (path, len(mutations), HERE / "mutate.py", path))
    print("%d mutation(s) in all" % total)


if __name__ == "__main__":
    main()
