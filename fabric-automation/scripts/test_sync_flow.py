#!/usr/bin/env python3
"""Behavioural tests of sync_to_github.ps1: what the script does, not what its text says.

The real script is run with stand-in `git`, `gh` and `python` programs first on the path. They answer from
canned data, record every call, and fail on request, so each test can make one step go wrong and assert what
the script then does: above all, that nothing is pushed unless every check before the push passed.

The script mirrors with robocopy, so these tests run on Windows, which is where the maintainer runs it and
where it runs this suite before every publication. Run from the project folder:

    python -m unittest discover -s scripts -p "test_*.py" -v
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
SCRIPT = Path(os.environ.get("SYNC_SCRIPT_UNDER_TEST") or HERE / "sync_to_github.ps1")
CANONICAL = "https://github.com/apkola29/fabric.git"
HEAD = "0123456789abcdef0123456789abcdef01234567"

SHIM = r'''
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
tool, args = sys.argv[1], sys.argv[2:]
with open(os.path.join(here, "calls.log"), "a", encoding="utf-8") as log:
    log.write(tool + " " + " ".join(args) + "\n")
state_file = os.path.join(here, "state.json")
def state():
    try:
        return json.load(open(state_file))
    except Exception:
        return {}
env = os.environ
if env.get("SYNC_STDERR_NOISE"):
    sys.stderr.write("warning: noise on stderr that is not an answer\n")
if tool == "git":
    if args[:1] == ["-C"]:
        args = args[2:]
    while args[:1] == ["-c"]:
        args = args[2:]
    cmd = args[0] if args else ""
    if cmd == "remote" and args[1] == "get-url":
        urls = env.get("SYNC_PUSH_URLS" if "--push" in args else "SYNC_FETCH_URLS", "%(canonical)s").split(";")
        print("\n".join(urls if "--all" in args else urls[:1]))
    elif cmd == "rev-parse" and "--abbrev-ref" in args:
        print("master")
    elif cmd == "rev-parse":
        print("%(head)s")
    elif cmd == "rev-list" and "--merges" in args:
        print(env.get("SYNC_MERGES", "0"))
    elif cmd == "rev-list":
        print("1" if args[-1].startswith("origin/") and (state().get("committed") or env.get("SYNC_AHEAD")) else "0")
    elif cmd == "log":
        print(env.get("SYNC_LOG_PATHS", "fabric-automation/README.md").replace(";", "\n"))
    elif cmd == "diff" and "--name-status" in args:
        if not env.get("SYNC_NOTHING_STAGED"):
            print("M\tfabric-automation/README.md")
    elif cmd == "diff" and "--shortstat" in args:
        print(" 1 file changed")
    elif cmd == "commit":
        json.dump({"committed": True}, open(state_file, "w"))
    sys.exit(0)
if tool == "gh":
    if args[:2] == ["api", "user"]:
        print(env.get("SYNC_GH_LOGIN", "apkola29"))
    elif args[:1] == ["api"]:
        print("[the project](fabric-automation/)")
    elif args[:2] == ["run", "list"]:
        # A run of another commit comes first, so that only a match on the commit finds the right run.
        runs = [{"databaseId": 1111, "headSha": "f" * 40}]
        if env.get("SYNC_CI_RUNS") != "other":
            runs.append({"databaseId": 4242, "headSha": "%(head)s"})
        print(json.dumps(runs))
    elif args[:2] == ["run", "watch"]:
        print("the run is being watched")
        sys.exit(int(env.get("SYNC_CI_EXIT", "0")))
    sys.exit(0)
joined = " ".join(args)
if "validate_docs.py" in joined:
    if "--root" in args:
        # The real validator skips these, so only a stand-in that looks at the disk can tell when they were removed.
        root = args[args.index("--root") + 1]
        found = []
        for folder, names, files in os.walk(root):
            found += [os.path.join(folder, n) for n in names if n in ("private", "__pycache__", ".pytest_cache")]
            found += [os.path.join(folder, n) for n in files if n.endswith(".pyc")]
        if os.path.exists(os.path.join(root, "docs", "research", "local")):
            found.append(os.path.join(root, "docs", "research", "local"))
        if found:
            print("leftovers were still there when the mirror was scanned: " + found[0])
            sys.exit(1)
        # What a file given with --scan-file held when it was scanned, kept for the tests.
        count = 0
        for position, value in enumerate(args):
            if value == "--scan-file":
                count += 1
                try:
                    data = open(args[position + 1], "rb").read()
                except OSError:
                    data = b"unreadable"
                open(os.path.join(here, "scanned-" + str(count) + ".bin"), "wb").write(data)
        edit = env.get("SYNC_EDIT_README_AFTER_SCAN")
        if edit:
            with open(edit, "ab") as handle:
                handle.write(b"added after the scan\n")
    sys.exit(int(env.get("SYNC_MIRROR_SCAN_EXIT" if "--root" in args else "SYNC_SOURCE_SCAN_EXIT", "0")))
if "unittest" in joined:
    sys.exit(int(env.get("SYNC_TESTS_EXIT", "0")))
if "verify_remote.py" in joined:
    sys.exit(int(env.get("SYNC_TREE_EXIT" if "--clone" in args else "SYNC_REMOTE_EXIT", "0")))
sys.exit(0)
''' % {"canonical": CANONICAL, "head": HEAD}


def powershell():
    return shutil.which("powershell") or shutil.which("pwsh")


@unittest.skipUnless(sys.platform == "win32" and shutil.which("robocopy") and powershell(),
                     "the publish script needs Windows, robocopy and PowerShell")
class SyncFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.TemporaryDirectory()
        template = Path(cls.base.name) / "template"
        local = (PROJECT / "docs" / "research" / "local").resolve()

        def skip(folder, names):
            skipped = {n for n in names if n in ("__pycache__", "private", ".pytest_cache", ".factory", ".claude", ".mcp.json")}
            if Path(folder) == PROJECT / ".github":
                skipped.add("skills")
            return skipped | {n for n in names if (Path(folder) / n).resolve() == local}
        # A mirror that is already in place keeps each script run short: robocopy then has nothing to copy.
        shutil.copytree(PROJECT, template / "fabric-automation", ignore=skip)
        (template / ".git").mkdir()
        (template / "README.md").write_text("# the repository readme\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.base.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.clone = root / "clone"
        shutil.copytree(Path(self.base.name) / "template", self.clone)
        # The script publishes a copy of the project, so a test can change the source and a mutated copy of the
        # script (SYNC_SCRIPT_UNDER_TEST) can live anywhere.
        self.project = root / "project"
        shutil.copytree(Path(self.base.name) / "template" / "fabric-automation", self.project)
        self.bin = root / "bin"
        self.bin.mkdir()
        (self.bin / "shim.py").write_text(SHIM, encoding="utf-8")
        for tool in ("git", "gh", "python"):
            (self.bin / (tool + ".cmd")).write_text('@"%s" "%%~dp0shim.py" %s %%*\r\n@exit /b %%errorlevel%%\r\n' % (sys.executable, tool),
                                                    encoding="utf-8")
        self.deny = root / "deny.txt"
        self.deny.write_text("zzz-private-term-zzz\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def publish(self, *extra, deny=True, clone=None, cwd=None, **env):
        full = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"], **env)
        full.pop("FABRIC_AUTOMATION_DENYLIST", None)
        for name in ("calls.log", "state.json"):
            (self.bin / name).unlink(missing_ok=True)
        for kept in self.bin.glob("scanned-*.bin"):
            kept.unlink()
        command = [powershell(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
                   "-CloneDir", clone or str(self.clone), "-ProjectDir", str(self.project), "-Message", "test"]
        if deny:
            command += ["-DenyList", str(self.deny)]
        proc = subprocess.run(command + list(extra), capture_output=True, text=True, encoding="utf-8", errors="replace", env=full, cwd=cwd)
        log = self.bin / "calls.log"
        calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        return proc.returncode, proc.stdout + proc.stderr, calls

    @staticmethod
    def find(calls, pattern):
        return [i for i, line in enumerate(calls) if re.search(pattern, line)]

    def assert_never(self, calls, pattern):
        self.assertEqual([], self.find(calls, pattern), "%s was called: %s" % (pattern, [calls[i] for i in self.find(calls, pattern)]))

    PUSH = r"^git .*\bpush origin"
    STAGE = r"^git .*\badd -A\b"
    COMMIT = r"^git .*\bcommit -F\b"
    SOURCE_SCAN = r"^python .*validate_docs\.py (?!.*--root)"
    MIRROR_SCAN = r"^python .*validate_docs\.py .*--root"
    TREE_CHECK = r"^python .*verify_remote\.py .*--clone"
    REMOTE_CHECK = r"^python .*verify_remote\.py (?!.*--clone)"

    def test_a_clean_run_runs_every_check_in_order_and_pushes_the_checked_commit_once(self):
        code, out, calls = self.publish()
        self.assertEqual(0, code, out)
        order = [self.find(calls, p) for p in (self.SOURCE_SCAN, self.MIRROR_SCAN, self.STAGE, self.COMMIT, self.TREE_CHECK, self.PUSH, self.REMOTE_CHECK)]
        for steps in order:
            self.assertEqual(1, len(steps), calls)
        firsts = [steps[0] for steps in order]
        self.assertEqual(sorted(firsts), firsts, "the steps ran out of order: %s" % calls)
        self.assertIn("%s:refs/heads/master" % HEAD, calls[order[5][0]])

    def test_a_failed_tree_check_means_nothing_is_pushed(self):
        code, out, calls = self.publish(SYNC_TREE_EXIT="1")
        self.assertNotEqual(0, code, out)
        self.assertIn("nothing was pushed", out)
        self.assert_never(calls, self.PUSH)
        self.assert_never(calls, self.REMOTE_CHECK)

    def test_a_failed_scan_of_the_mirrored_copy_means_nothing_is_staged_or_pushed(self):
        code, out, calls = self.publish(SYNC_MIRROR_SCAN_EXIT="1")
        self.assertNotEqual(0, code, out)
        self.assertIn("nothing was committed", out)
        for pattern in (self.STAGE, self.COMMIT, self.PUSH):
            self.assert_never(calls, pattern)

    def test_a_failed_first_validation_stops_before_the_mirror_is_touched(self):
        code, out, calls = self.publish(SYNC_SOURCE_SCAN_EXIT="1")
        self.assertNotEqual(0, code, out)
        for pattern in (self.MIRROR_SCAN, self.STAGE, self.COMMIT, self.PUSH, r"^git .*\bfetch\b"):
            self.assert_never(calls, pattern)

    def test_failing_tests_stop_the_run_before_anything_is_written(self):
        code, out, calls = self.publish(SYNC_TESTS_EXIT="1")
        self.assertNotEqual(0, code, out)
        for pattern in (self.MIRROR_SCAN, self.STAGE, self.COMMIT, self.PUSH):
            self.assert_never(calls, pattern)

    def test_every_fetch_and_every_push_address_is_asked_for(self):
        code, out, calls = self.publish()
        self.assertEqual(0, code, out)
        self.assertTrue(self.find(calls, r"^git .*remote get-url --all origin"), calls)
        self.assertTrue(self.find(calls, r"^git .*remote get-url --push --all origin"), calls)

    def test_a_second_push_address_that_is_not_the_repository_stops_the_run_first(self):
        code, out, calls = self.publish(SYNC_PUSH_URLS=CANONICAL + ";https://elsewhere.invalid/public.git")
        self.assertNotEqual(0, code, out)
        self.assertIn("elsewhere.invalid", out)
        for pattern in (r"^git .*\bfetch\b", self.STAGE, self.COMMIT, self.PUSH):
            self.assert_never(calls, pattern)

    def test_a_fetch_address_that_is_not_the_repository_stops_the_run(self):
        code, out, calls = self.publish(SYNC_FETCH_URLS="https://elsewhere.invalid/apkola29/fabric.git")
        self.assertNotEqual(0, code, out)
        for pattern in (self.COMMIT, self.PUSH):
            self.assert_never(calls, pattern)

    def test_an_address_with_a_credential_is_refused_and_the_credential_is_not_printed(self):
        secret = "ghp_" + "x" * 8
        code, out, calls = self.publish(SYNC_PUSH_URLS="https://" + secret + "@github.com/apkola29/fabric.git")
        self.assertNotEqual(0, code, out)
        self.assertNotIn(secret, out)
        self.assert_never(calls, self.PUSH)

    def test_no_push_runs_every_check_and_pushes_nothing(self):
        code, out, calls = self.publish("-NoPush")
        self.assertEqual(0, code, out)
        self.assertTrue(self.find(calls, self.TREE_CHECK), calls)
        self.assert_never(calls, self.PUSH)
        self.assert_never(calls, self.REMOTE_CHECK)

    def test_being_signed_in_as_someone_else_stops_the_run(self):
        code, out, calls = self.publish(SYNC_GH_LOGIN="someone-else")
        self.assertNotEqual(0, code, out)
        for pattern in (self.STAGE, self.COMMIT, self.PUSH):
            self.assert_never(calls, pattern)

    def test_the_repository_readme_is_scanned_and_compared_when_it_is_published(self):
        code, out, calls = self.publish("-IncludeReadme")
        self.assertEqual(0, code, out)
        for pattern in (self.SOURCE_SCAN, self.MIRROR_SCAN):
            self.assertTrue(any("--scan-file" in calls[i] and "README.md" in calls[i] for i in self.find(calls, pattern)), calls)
        for pattern in (self.TREE_CHECK, self.REMOTE_CHECK):
            self.assertTrue(any("--extra README.md=" in calls[i] for i in self.find(calls, pattern)), calls)

    def test_the_mirror_scan_reads_a_private_copy_of_the_readme_and_the_commit_is_compared_with_that_copy(self):
        live = self.clone / "README.md"
        text = b"# the repository readme\n\nwhat was scanned\n"
        live.write_bytes(text)
        code, out, calls = self.publish("-IncludeReadme")
        self.assertEqual(0, code, out)
        self.assertNotIn(str(live), calls[self.find(calls, self.MIRROR_SCAN)[0]], "the scan read the live file, which can change afterwards")
        self.assertEqual(text, (self.bin / "scanned-1.bin").read_bytes())
        for pattern in (self.TREE_CHECK, self.REMOTE_CHECK):
            call = calls[self.find(calls, pattern)[0]]
            self.assertIn("--extra README.md=", call)
            self.assertNotIn("--extra README.md=" + str(live), call, "the commit was compared with the live file, not with what was scanned")

    def test_a_change_to_the_readme_after_it_was_scanned_stops_the_run_before_anything_is_committed(self):
        code, out, calls = self.publish("-IncludeReadme", SYNC_EDIT_README_AFTER_SCAN=str(self.clone / "README.md"))
        self.assertNotEqual(0, code, out)
        self.assertIn("changed after it was scanned", out)
        for pattern in (self.STAGE, self.COMMIT, self.PUSH):
            self.assert_never(calls, pattern)

    def test_the_private_copy_of_the_readme_is_removed_when_the_run_succeeds_and_when_it_fails(self):
        for label, env in (("succeeds", {}), ("fails at the tree check", {"SYNC_TREE_EXIT": "1"}),
                           ("fails after the push", {"SYNC_REMOTE_EXIT": "1"})):
            with self.subTest(label):
                scratch = Path(tempfile.mkdtemp(dir=self.tmp.name))
                args = ("-IncludeReadme", "-NoPush") if label == "succeeds" else ("-IncludeReadme",)
                self.publish(*args, TMP=str(scratch), TEMP=str(scratch), **env)
                self.assertEqual([], [p.name for p in scratch.iterdir() if p.name.lower().startswith("fabric-automation")],
                                 "a copy of the README was left in the temporary folder")

    def test_every_kind_of_leftover_is_gone_before_the_mirror_is_scanned(self):
        mirror = self.clone / "fabric-automation"
        leftovers = [mirror / "private" / "leak.txt", mirror / "docs" / "research" / "local" / "survey.md",
                     mirror / "scripts" / "__pycache__" / "x.pyc", mirror / ".pytest_cache" / "v" / "cache.txt",
                     mirror / "scripts" / "stray.pyc", mirror / "docs" / "private" / "nested.md"]
        for path in leftovers:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"x\n")
        code, out, calls = self.publish("-NoPush")
        self.assertEqual(0, code, out)
        for path in leftovers:
            self.assertFalse(path.exists(), path)

    def test_a_private_folder_at_any_depth_of_the_project_is_not_mirrored(self):
        nested = self.project / "docs" / "private"
        nested.mkdir()
        (nested / "note.txt").write_text("never published\n", encoding="utf-8")
        code, out, calls = self.publish("-NoPush")
        self.assertEqual(0, code, out)
        self.assertFalse((self.clone / "fabric-automation" / "docs" / "private").exists())

    GENERATED = (".factory/pack/.cache/abc/objects/pack/x.idx", ".github/skills/a-skill/SKILL.md", ".claude/skills/a-skill/SKILL.md", ".mcp.json")

    def test_what_the_toolchain_generates_for_a_machine_is_not_mirrored_but_its_committed_mcp_files_are(self):
        for rel in self.GENERATED:
            path = self.project / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"x\n")
        (self.project / ".github" / "mcp.json").write_text("{}\n", encoding="utf-8")
        code, out, calls = self.publish("-NoPush")
        self.assertEqual(0, code, out)
        mirror = self.clone / "fabric-automation"
        for rel in self.GENERATED:
            self.assertFalse((mirror / rel).exists(), rel)
        self.assertFalse((mirror / ".factory").exists())
        self.assertEqual("{}\n", (mirror / ".github" / "mcp.json").read_text(encoding="utf-8"))

    def test_a_junction_in_the_clone_stops_the_run_and_nothing_behind_it_is_deleted(self):
        # robocopy /MIR, even with /XJ, deletes what a destination junction points to. The script must refuse instead.
        outside = Path(self.tmp.name) / "outside"
        (outside / "__pycache__").mkdir(parents=True)
        (outside / "__pycache__" / "keep.pyc").write_bytes(b"\x00")
        (outside / "note.txt").write_text("keep me\n", encoding="utf-8")
        junction = self.clone / "fabric-automation" / "docs" / "junction"
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if made.returncode != 0:
            self.skipTest("could not create a junction: " + made.stdout.strip()[:80])
        code, out, calls = self.publish("-NoPush")
        self.assertNotEqual(0, code, out)
        self.assertIn("holds a link", out)
        self.assertTrue((outside / "__pycache__" / "keep.pyc").exists(), "the script deleted through the junction")
        self.assertTrue((outside / "note.txt").exists(), "the script deleted through the junction")
        for pattern in (self.STAGE, self.COMMIT, self.PUSH):
            self.assert_never(calls, pattern)

    def junction(self, link, target):
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if made.returncode != 0:
            self.skipTest("could not create a junction: " + made.stdout.strip()[:80])

    def outside_folder(self):
        outside = Path(self.tmp.name) / "outside"
        (outside / "__pycache__").mkdir(parents=True)
        (outside / "__pycache__" / "keep.pyc").write_bytes(b"\x00")
        (outside / "precious.txt").write_text("keep me\n", encoding="utf-8")
        return outside

    def assert_untouched(self, outside):
        self.assertEqual("keep me\n", (outside / "precious.txt").read_text(encoding="utf-8"), "the script changed what a link points to")
        self.assertTrue((outside / "__pycache__" / "keep.pyc").exists(), "the script deleted through a link")
        self.assertEqual([], sorted(p.name for p in outside.rglob("*.yml")), "the script wrote through a link")

    def assert_a_link_stops_the_run(self, link, outside):
        code, out, calls = self.publish("-NoPush")
        self.assertNotEqual(0, code, out)
        self.assertIn("is a link", out)
        self.assert_untouched(outside)
        for pattern in (self.STAGE, self.COMMIT, self.PUSH):
            self.assert_never(calls, pattern)

    def test_the_mirror_folder_itself_being_a_junction_stops_the_run_and_nothing_behind_it_is_deleted(self):
        outside = self.outside_folder()
        shutil.rmtree(self.clone / "fabric-automation")
        self.junction(self.clone / "fabric-automation", outside)
        self.assert_a_link_stops_the_run(self.clone / "fabric-automation", outside)

    def test_the_github_folder_being_a_junction_stops_the_run_before_anything_is_written(self):
        outside = self.outside_folder()
        self.junction(self.clone / ".github", outside)
        self.assert_a_link_stops_the_run(self.clone / ".github", outside)

    def test_the_workflow_folder_being_a_junction_stops_the_run_before_anything_is_written(self):
        outside = self.outside_folder()
        (self.clone / ".github").mkdir()
        self.junction(self.clone / ".github" / "workflows", outside)
        self.assert_a_link_stops_the_run(self.clone / ".github" / "workflows", outside)

    def test_a_workflow_file_that_is_a_symbolic_link_stops_the_run(self):
        workflows = self.clone / ".github" / "workflows"
        workflows.mkdir(parents=True)
        target = Path(self.tmp.name) / "elsewhere.yml"
        target.write_text("keep me\n", encoding="utf-8")
        try:
            os.symlink(target, workflows / "fabric-automation-validate.yml")
        except (OSError, NotImplementedError):
            self.skipTest("this account cannot create symbolic links")
        code, out, calls = self.publish("-NoPush")
        self.assertNotEqual(0, code, out)
        self.assertIn("is a link", out)
        self.assertEqual("keep me\n", target.read_text(encoding="utf-8"))

    def hard_link(self, link):
        # A hard link is a second name for the same file, so a write under one name changes the other. It needs no
        # privilege and Windows PowerShell reports it as LinkType HardLink.
        target = Path(self.tmp.name) / "other-name.txt"
        target.write_text("keep me\n", encoding="utf-8")
        link.parent.mkdir(parents=True, exist_ok=True)
        link.unlink(missing_ok=True)
        try:
            os.link(target, link)
        except OSError as exc:
            self.skipTest("this volume cannot make hard links: %s" % exc)
        return target

    def test_a_hard_linked_workflow_file_stops_the_run_and_its_other_name_is_untouched(self):
        target = self.hard_link(self.clone / ".github" / "workflows" / "fabric-automation-validate.yml")
        code, out, calls = self.publish("-NoPush")
        self.assertNotEqual(0, code, out)
        self.assertIn("is a link", out)
        self.assertEqual("keep me\n", target.read_text(encoding="utf-8"), "the script wrote through a hard link")
        for pattern in (self.STAGE, self.COMMIT, self.PUSH):
            self.assert_never(calls, pattern)

    def test_a_hard_linked_file_in_the_mirror_stops_the_run_before_robocopy_can_overwrite_it(self):
        target = self.hard_link(self.clone / "fabric-automation" / "README.md")
        self.assertNotEqual(target.read_text(encoding="utf-8"), (self.project / "README.md").read_text(encoding="utf-8"))
        code, out, calls = self.publish("-NoPush")
        self.assertNotEqual(0, code, out)
        self.assertIn("holds a link", out)
        self.assertEqual("keep me\n", target.read_text(encoding="utf-8"), "robocopy wrote through a hard link")
        for pattern in (self.STAGE, self.COMMIT, self.PUSH):
            self.assert_never(calls, pattern)

    def test_a_hard_linked_readme_stops_the_run_when_the_readme_is_published(self):
        target = self.hard_link(self.clone / "README.md")
        code, out, calls = self.publish("-IncludeReadme", "-NoPush")
        self.assertNotEqual(0, code, out)
        self.assertIn("is a link", out)
        self.assertEqual("keep me\n", target.read_text(encoding="utf-8"))

    def test_a_readme_that_is_a_symbolic_link_stops_the_run_when_the_readme_is_published(self):
        target = Path(self.tmp.name) / "elsewhere.md"
        target.write_text("keep me\n", encoding="utf-8")
        (self.clone / "README.md").unlink()
        try:
            os.symlink(target, self.clone / "README.md")
        except (OSError, NotImplementedError):
            self.skipTest("this account cannot create symbolic links")
        code, out, calls = self.publish("-IncludeReadme", "-NoPush")
        self.assertNotEqual(0, code, out)
        self.assertIn("is a link", out)
        self.assertEqual("keep me\n", target.read_text(encoding="utf-8"))

    def test_a_path_that_differs_only_in_case_is_not_hidden_by_a_correctly_written_one(self):
        for paths in ("fabric-automation/README.md;Fabric-Automation/README.md", "Fabric-Automation/README.md;fabric-automation/README.md"):
            with self.subTest(paths=paths):
                code, out, calls = self.publish(SYNC_LOG_PATHS=paths)
                self.assertNotEqual(0, code, out)
                self.assertIn("outside the managed set", out)
                self.assert_never(calls, self.PUSH)

    def test_a_leading_space_in_a_path_is_kept_so_that_the_path_is_not_taken_for_a_managed_one(self):
        code, out, calls = self.publish(SYNC_LOG_PATHS=" fabric-automation/README.md")
        self.assertNotEqual(0, code, out)
        self.assertIn("outside the managed set", out)
        self.assert_never(calls, self.PUSH)

    def test_a_relative_clone_path_is_made_absolute_before_it_is_used(self):
        code, out, calls = self.publish("-IncludeReadme", "-NoPush", clone="clone", cwd=self.clone.parent)
        self.assertEqual(0, code, out)
        tree = calls[self.find(calls, self.TREE_CHECK)[0]]
        clone = re.search(r"--clone (.+?) --commit", tree).group(1)
        self.assertTrue(os.path.isabs(clone), tree)
        self.assertTrue(os.path.isabs(re.search(r"--extra README\.md=(.+)$", tree).group(1)), tree)

    def test_the_private_list_is_required_and_given_to_both_scans(self):
        code, out, calls = self.publish()
        self.assertEqual(0, code, out)
        for pattern in (self.SOURCE_SCAN, self.MIRROR_SCAN):
            scan = calls[self.find(calls, pattern)[0]]
            self.assertIn("--denylist %s --require-denylist" % self.deny, scan)

    def test_both_scans_treat_warnings_as_errors(self):
        code, out, calls = self.publish()
        self.assertEqual(0, code, out)
        for pattern in (self.SOURCE_SCAN, self.MIRROR_SCAN):
            self.assertIn(" --strict ", calls[self.find(calls, pattern)[0]] + " ")

    WORKFLOW_EXTRAS = (".github/workflows/fabric-automation-validate.yml=ci/fabric-automation-validate.yml",
                       ".github/workflows/fabric-automation-facts.yml=ci/fabric-automation-facts.yml")

    def test_both_verifiers_compare_each_workflow_file_with_its_copy_in_the_project(self):
        code, out, calls = self.publish()
        self.assertEqual(0, code, out)
        for pattern in (self.TREE_CHECK, self.REMOTE_CHECK):
            call = calls[self.find(calls, pattern)[0]]
            for extra in self.WORKFLOW_EXTRAS:
                self.assertIn("--extra " + extra, call)

    def test_waiting_for_ci_watches_the_run_of_the_pushed_commit_and_reports_success(self):
        code, out, calls = self.publish("-WaitCi")
        self.assertEqual(0, code, out)
        self.assertIn("CI run 4242 passed", out)
        watch = self.find(calls, r"^gh run watch 4242 --repo apkola29/fabric --exit-status")
        self.assertEqual(1, len(watch), calls)
        self.assertGreater(watch[0], self.find(calls, self.REMOTE_CHECK)[0])

    def test_a_failed_ci_run_is_a_failed_publication(self):
        code, out, calls = self.publish("-WaitCi", SYNC_CI_EXIT="1")
        self.assertNotEqual(0, code, out)
        self.assertIn("the CI run 4242 failed", out)
        self.assertNotIn("Done.", out)

    def test_a_ci_run_that_never_appears_for_the_pushed_commit_is_an_error(self):
        code, out, calls = self.publish("-WaitCi", "-CiWaitMinutes", "0", SYNC_CI_RUNS="other")
        self.assertNotEqual(0, code, out)
        self.assertIn("no CI run appeared for commit", out)
        self.assert_never(calls, r"^gh run watch")

    def test_without_the_wait_option_the_run_does_not_wait_for_ci(self):
        code, out, calls = self.publish()
        self.assertEqual(0, code, out)
        self.assert_never(calls, r"^gh run ")

    def test_nothing_is_awaited_when_nothing_was_pushed(self):
        code, out, calls = self.publish("-WaitCi", SYNC_NOTHING_STAGED="1")
        self.assertEqual(0, code, out)
        self.assertIn("nothing to push", out)
        self.assert_never(calls, self.PUSH)
        self.assert_never(calls, r"^gh run ")

    def test_without_a_private_list_the_run_stops_before_it_touches_anything(self):
        code, out, calls = self.publish(deny=False)
        self.assertNotEqual(0, code, out)
        self.assertIn("no private denylist found", out)
        for pattern in (r"^git .*\bfetch\b", self.SOURCE_SCAN, self.MIRROR_SCAN, self.STAGE, self.COMMIT, self.PUSH):
            self.assert_never(calls, pattern)

    def test_a_run_skips_the_private_list_only_when_asked_and_says_so(self):
        code, out, calls = self.publish("-NoDenylist", deny=False)
        self.assertEqual(0, code, out)
        self.assertIn("without the private term check", out)
        self.assertNotIn("--denylist", calls[self.find(calls, self.SOURCE_SCAN)[0]])

    MANAGED = (r"-- fabric-automation \.github/workflows/fabric-automation-validate\.yml "
               r"\.github/workflows/fabric-automation-facts\.yml")

    def test_only_the_managed_paths_are_staged_and_committed(self):
        code, out, calls = self.publish()
        self.assertEqual(0, code, out)
        self.assertRegex(calls[self.find(calls, self.STAGE)[0]], self.MANAGED + "$")
        self.assertRegex(calls[self.find(calls, self.COMMIT)[0]], self.MANAGED + "$")

    def test_the_repository_readme_joins_the_managed_paths_only_when_asked(self):
        code, out, calls = self.publish("-IncludeReadme")
        self.assertEqual(0, code, out)
        self.assertRegex(calls[self.find(calls, self.STAGE)[0]], self.MANAGED + r" README\.md$")
        self.assertRegex(calls[self.find(calls, self.COMMIT)[0]], self.MANAGED + r" README\.md$")

    def test_a_commit_that_touches_a_path_outside_the_managed_set_is_never_pushed(self):
        for paths in ("somewhere/else.txt", "fabric-automation/README.md;other/file.md", "Fabric-Automation/secret.txt",
                      ".GITHUB/workflows/fabric-automation-validate.yml", "fabric-automationx/file.md"):
            with self.subTest(paths=paths):
                code, out, calls = self.publish(SYNC_LOG_PATHS=paths)
                self.assertNotEqual(0, code, out)
                self.assertIn("outside the managed set", out)
                self.assert_never(calls, self.PUSH)

    def test_the_readme_is_managed_only_with_its_exact_name(self):
        code, out, calls = self.publish("-IncludeReadme", SYNC_LOG_PATHS="readme.md")
        self.assertNotEqual(0, code, out)
        self.assertIn("outside the managed set", out)
        self.assert_never(calls, self.PUSH)

    def test_a_merge_commit_is_never_pushed(self):
        code, out, calls = self.publish(SYNC_MERGES="1")
        self.assertNotEqual(0, code, out)
        self.assertIn("merge commit", out)
        self.assert_never(calls, self.PUSH)

    def test_the_commit_log_is_read_with_settings_that_keep_path_parsing_stable(self):
        code, out, calls = self.publish()
        self.assertEqual(0, code, out)
        log = calls[self.find(calls, r"^git .* log ")[0]]
        self.assertIn("core.quotePath=false", log)
        self.assertIn("--no-show-signature", log)

    def test_every_commit_that_would_be_pushed_is_checked_and_not_only_the_new_one(self):
        code, out, calls = self.publish(SYNC_AHEAD="1")
        self.assertEqual(0, code, out)
        logs = [calls[i] for i in self.find(calls, r"^git .* log ")]
        self.assertEqual(2, len(logs), "the earlier commits are checked before the fold and what will be pushed after the commit: %s" % logs)
        for line in logs:
            self.assertTrue(line.endswith(" origin/master..HEAD"), line)
        merges = [calls[i] for i in self.find(calls, r"^git .* rev-list --merges")]
        self.assertTrue(merges and all(line.endswith(" origin/master..HEAD") for line in merges), merges)

    def test_a_failed_check_of_what_github_holds_is_a_failed_run(self):
        code, out, calls = self.publish(SYNC_REMOTE_EXIT="1")
        self.assertNotEqual(0, code, out)
        self.assertIn("GitHub does not match", out)
        self.assertNotIn("Done.", out)

    def test_the_workflow_files_are_copied_from_the_mirror_with_unix_line_endings(self):
        code, out, calls = self.publish("-NoPush")
        self.assertEqual(0, code, out)
        for name in ("fabric-automation-validate.yml", "fabric-automation-facts.yml"):
            copy = (self.clone / ".github" / "workflows" / name).read_bytes()
            self.assertEqual((self.project / "ci" / name).read_bytes().replace(b"\r\n", b"\n"), copy)
            self.assertNotIn(b"\r", copy)

    def test_earlier_local_commits_are_folded_after_the_mirror_scan_and_only_the_managed_paths_leave_the_index(self):
        code, out, calls = self.publish(SYNC_AHEAD="1")
        self.assertEqual(0, code, out)
        reset = self.find(calls, r"^git .*\breset\b")
        self.assertEqual(2, len(reset), calls)
        self.assertIn("reset --soft origin/master", calls[reset[0]])
        self.assertRegex(calls[reset[1]], r"reset -q " + self.MANAGED + "$")
        self.assertGreater(reset[0], self.find(calls, self.MIRROR_SCAN)[0], "the fold came before the mirror scan")
        self.assertLess(reset[1], self.find(calls, self.STAGE)[0], "the fold came after staging")
        self.assert_never(calls, r"^git .*\breset --mixed\b")

    def test_a_failed_scan_leaves_earlier_local_commits_where_they_are(self):
        code, out, calls = self.publish(SYNC_AHEAD="1", SYNC_MIRROR_SCAN_EXIT="1")
        self.assertNotEqual(0, code, out)
        self.assert_never(calls, r"^git .*\breset\b")

    def test_noise_on_stderr_of_a_successful_command_is_not_taken_for_its_answer(self):
        code, out, calls = self.publish(SYNC_STDERR_NOISE="1")
        self.assertEqual(0, code, out)
        self.assertIn("%s:refs/heads/master" % HEAD, calls[self.find(calls, self.PUSH)[0]])


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class FoldSemanticsTests(unittest.TestCase):
    """Why the script folds earlier local commits with a soft reset and then a reset of the managed paths.

    A soft reset alone keeps the index of those commits, including a file that was force-added although .gitignore keeps
    it out, so the next run would commit it again and the pre-push check would refuse it on every run. A mixed reset drops
    that file, but it also unstages work that someone staged in the clone for another purpose. A soft reset followed by a
    reset of only the managed paths does neither.
    """
    GIT = ["git", "-c", "core.autocrlf=false", "-c", "user.email=test" + "@example.invalid", "-c", "user.name=test", "-c", "commit.gpgsign=false"]
    MANAGED = ["fabric-automation", ".github/workflows/fabric-automation-validate.yml", ".github/workflows/fabric-automation-facts.yml", "README.md"]

    def git(self, cwd, *args):
        proc = subprocess.run(self.GIT + list(args), cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout

    def staged_after_fold(self, *resets):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.git(repo, "init", "-q")
            (repo / "fabric-automation").mkdir()
            (repo / "fabric-automation" / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
            (repo / "fabric-automation" / "a.md").write_text("a\n", encoding="utf-8")
            self.git(repo, "add", "-A")
            self.git(repo, "commit", "-q", "-m", "origin")
            self.git(repo, "branch", "origin-master")
            (repo / "fabric-automation" / "scratch.tmp").write_text("x\n", encoding="utf-8")
            self.git(repo, "add", "-f", "fabric-automation/scratch.tmp")
            self.git(repo, "commit", "-q", "-m", "earlier local commit")
            (repo / "notes.txt").write_text("work that someone staged for another purpose\n", encoding="utf-8")
            self.git(repo, "add", "notes.txt")
            for reset in resets:
                self.git(repo, "reset", *reset)
            self.git(repo, "add", "-A", "--", "fabric-automation")
            return sorted(self.git(repo, "diff", "--cached", "--name-only").split())

    def test_a_soft_reset_keeps_a_force_added_ignored_file_in_the_next_commit(self):
        self.assertEqual(["fabric-automation/scratch.tmp", "notes.txt"], self.staged_after_fold(["--soft", "origin-master"]))

    def test_a_mixed_reset_lets_the_ignore_rules_decide_again_but_unstages_other_work(self):
        self.assertEqual([], self.staged_after_fold(["--mixed", "origin-master"]))

    def test_a_soft_reset_followed_by_a_reset_of_the_managed_paths_does_both_jobs(self):
        # Some of the managed paths exist nowhere yet; git must accept that.
        self.assertEqual(["notes.txt"], self.staged_after_fold(["--soft", "origin-master"], ["-q", "--"] + self.MANAGED))


if __name__ == "__main__":
    unittest.main()
