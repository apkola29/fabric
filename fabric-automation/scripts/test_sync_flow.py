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
if tool == "git":
    if args[:1] == ["-C"]:
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
        print("0")
    elif cmd == "rev-list":
        print("1" if args[-1].startswith("origin/") and state().get("committed") else "0")
    elif cmd == "log":
        print("fabric-automation/README.md")
    elif cmd == "diff" and "--name-status" in args:
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
    sys.exit(0)
joined = " ".join(args)
if "validate_docs.py" in joined:
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
            skipped = {n for n in names if n in ("__pycache__", "private", ".pytest_cache")}
            return skipped | {n for n in names if (Path(folder) / n).resolve() == local}
        # A mirror that is already in place keeps each script run short: robocopy then has nothing to copy.
        shutil.copytree(PROJECT, template / "fabric-automation", ignore=skip)
        (template / ".git").mkdir()

    @classmethod
    def tearDownClass(cls):
        cls.base.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.clone = root / "clone"
        shutil.copytree(Path(self.base.name) / "template", self.clone)
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

    def publish(self, *extra, **env):
        full = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"], **env)
        proc = subprocess.run([powershell(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
                               "-CloneDir", str(self.clone), "-DenyList", str(self.deny), "-Message", "test"] + list(extra),
                              capture_output=True, text=True, env=full)
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

    def test_excluded_leftovers_in_the_clone_are_removed_before_the_mirror_is_scanned(self):
        mirror = self.clone / "fabric-automation"
        (mirror / "scripts" / "__pycache__").mkdir(parents=True, exist_ok=True)
        (mirror / "scripts" / "__pycache__" / "x.pyc").write_bytes(b"\x00\x01")
        (mirror / "private").mkdir(exist_ok=True)
        (mirror / "private" / "leak.txt").write_text("private\n", encoding="utf-8")
        code, out, calls = self.publish("-NoPush")
        self.assertEqual(0, code, out)
        self.assertFalse((mirror / "scripts" / "__pycache__").exists())
        self.assertFalse((mirror / "private").exists())

    def test_a_junction_in_the_clone_stops_the_run_and_nothing_behind_it_is_deleted(self):
        # robocopy /MIR, even with /XJ, deletes what a destination junction points to. The script must refuse instead.
        outside = Path(self.tmp.name) / "outside"
        (outside / "__pycache__").mkdir(parents=True)
        (outside / "__pycache__" / "keep.pyc").write_bytes(b"\x00")
        (outside / "note.txt").write_text("keep me\n", encoding="utf-8")
        junction = self.clone / "fabric-automation" / "docs" / "junction"
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)], capture_output=True, text=True)
        if made.returncode != 0:
            self.skipTest("could not create a junction: " + made.stdout.strip()[:80])
        code, out, calls = self.publish("-NoPush")
        self.assertNotEqual(0, code, out)
        self.assertIn("holds a link", out)
        self.assertTrue((outside / "__pycache__" / "keep.pyc").exists(), "the script deleted through the junction")
        self.assertTrue((outside / "note.txt").exists(), "the script deleted through the junction")
        for pattern in (self.STAGE, self.COMMIT, self.PUSH):
            self.assert_never(calls, pattern)


if __name__ == "__main__":
    unittest.main()
