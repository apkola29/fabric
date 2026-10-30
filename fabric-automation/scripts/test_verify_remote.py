#!/usr/bin/env python3
"""Tests for verify_remote.py in its --clone mode, which checks a commit before it is pushed.

Each test builds a small project and a throwaway clone, commits a mirror of the
project, changes one thing and asserts what the check reports. GitHub is never
contacted. Run from the project folder:

    python -m unittest discover -s scripts -p "test_*.py" -v
"""

import contextlib
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import verify_remote  # noqa: E402

GIT = ["git", "-c", "core.autocrlf=false", "-c", "user.email=test" + "@example.invalid", "-c", "user.name=test",
       "-c", "commit.gpgsign=false"]
WORKFLOW = ".github/workflows/w.yml"


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class CloneModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.project = base / "project"
        self.clone = base / "clone"
        write(self.project / ".gitignore", "private/\n__pycache__/\n*.pyc\n")
        write(self.project / "README.md", "# title\nline\n")
        write(self.project / "docs" / "a.md", "text\n")
        write(self.project / "ci" / "w.yml", "name: w\n")
        write(self.project / "private" / "note.txt", "never published\n")
        write(self.project / "scripts" / "__pycache__" / "x.pyc", b"\x00\x01")
        self.git(base, "init", "-q", str(self.clone))
        self.mirror()
        self.commit("first")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, cwd, *args):
        proc = subprocess.run(GIT + list(args), cwd=cwd, capture_output=True, text=True)
        self.assertEqual(0, proc.returncode, proc.stderr)
        return proc.stdout.strip()

    def mirror(self):
        """What the publish script does: copy the publishable files, plus the workflow outside the folder."""
        target = self.clone / "fabric-automation"
        shutil.rmtree(target, ignore_errors=True)
        for rel in verify_remote.publishable_files(self.project):
            write(target / rel, (self.project / rel).read_bytes().replace(b"\r\n", b"\n"))
        write(self.clone / WORKFLOW, (self.project / "ci" / "w.yml").read_bytes())

    def commit(self, message):
        self.git(self.clone, "add", "-A")
        self.git(self.clone, "commit", "-q", "-m", message)
        return self.git(self.clone, "rev-parse", "HEAD")

    def check(self, commit="HEAD", extra=True, more=()):
        argv = ["--clone", str(self.clone), "--commit", commit, "--local", str(self.project)]
        if extra:
            argv += ["--extra", "%s=ci/w.yml" % WORKFLOW]
        for pair in more:
            argv += ["--extra", pair]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = verify_remote.main(argv)
        return code, out.getvalue()

    def stage_entry(self, mode, content, path):
        """Put an entry with the given mode into the index without creating a file, then commit."""
        blob = subprocess.run(GIT + ["hash-object", "-w", "--stdin"], cwd=self.clone, input=content, capture_output=True, text=True)
        self.assertEqual(0, blob.returncode, blob.stderr)
        self.git(self.clone, "update-index", "--add", "--cacheinfo", "%s,%s,%s" % (mode, blob.stdout.strip(), path))
        self.git(self.clone, "commit", "-q", "-m", "special entry")

    def test_a_commit_that_holds_exactly_the_project_passes(self):
        code, out = self.check()
        self.assertEqual(0, code, out)
        self.assertIn("0 problem(s)", out)

    def test_files_that_are_never_published_are_not_expected(self):
        code, out = self.check()
        self.assertNotIn("private", out)
        self.assertNotIn("pycache", out)
        self.assertEqual(0, code, out)

    def test_a_private_file_that_was_committed_is_an_extra_file(self):
        write(self.clone / "fabric-automation" / "private" / "denylist.txt", "secret\n")
        self.git(self.clone, "add", "-f", "fabric-automation/private/denylist.txt")
        self.commit("oops")
        code, out = self.check()
        self.assertEqual(1, code, out)
        self.assertIn("EXTRA-REMOTE   private/denylist.txt", out)

    def test_committed_bytecode_is_an_extra_file(self):
        write(self.clone / "fabric-automation" / "scripts" / "__pycache__" / "x.pyc", b"\x00\x01")
        self.git(self.clone, "add", "-f", "fabric-automation/scripts/__pycache__/x.pyc")
        self.commit("oops")
        code, out = self.check()
        self.assertEqual(1, code, out)
        self.assertIn("EXTRA-REMOTE   scripts/__pycache__/x.pyc", out)

    def test_a_file_that_differs_is_reported(self):
        write(self.clone / "fabric-automation" / "docs" / "a.md", "changed\n")
        self.commit("edit")
        code, out = self.check()
        self.assertEqual(1, code, out)
        self.assertIn("DIFFERENT      docs/a.md", out)

    def test_a_file_missing_from_the_commit_is_reported(self):
        write(self.project / "docs" / "new.md", "new\n")
        code, out = self.check()
        self.assertEqual(1, code, out)
        self.assertIn("MISSING-REMOTE docs/new.md", out)

    def test_windows_line_endings_in_the_project_are_not_a_difference(self):
        write(self.project / "docs" / "a.md", b"text\r\n")
        code, out = self.check()
        self.assertEqual(0, code, out)

    def test_a_workflow_copy_that_differs_is_reported(self):
        write(self.project / "ci" / "w.yml", "name: changed\n")
        code, out = self.check()
        self.assertEqual(1, code, out)
        self.assertIn("DIFFERENT      %s" % WORKFLOW, out)

    def test_the_earlier_commit_is_judged_not_the_head(self):
        first = self.git(self.clone, "rev-parse", "HEAD")
        write(self.clone / "fabric-automation" / "docs" / "a.md", "changed\n")
        self.commit("edit")
        self.assertEqual(0, self.check(commit=first)[0])
        self.assertEqual(1, self.check(commit="HEAD")[0])

    def test_a_commit_without_the_folder_is_reported(self):
        shutil.rmtree(self.clone / "fabric-automation")
        self.commit("remove")
        code, out = self.check()
        self.assertEqual(1, code, out)
        self.assertIn("MISSING the folder", out)

    def test_clone_mode_needs_a_commit(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            verify_remote.main(["--clone", str(self.clone), "--local", str(self.project)])
        self.assertEqual(2, raised.exception.code)

    def test_a_gitlink_in_the_commit_is_reported(self):
        self.stage_entry("160000", "", "fabric-automation/docs/sub")
        code, out = self.check()
        self.assertEqual(1, code, out)
        self.assertIn("docs/sub", out)

    def test_a_symbolic_link_is_reported_even_when_its_text_equals_a_local_file(self):
        write(self.project / "docs" / "link.md", b"target")
        self.stage_entry("120000", "target", "fabric-automation/docs/link.md")
        code, out = self.check()
        self.assertEqual(1, code, out)
        self.assertIn("UNEXPECTED-MODE docs/link.md 120000", out)

    def test_an_executable_regular_file_is_accepted(self):
        self.git(self.clone, "update-index", "--chmod=+x", "fabric-automation/docs/a.md")
        self.git(self.clone, "commit", "-q", "-m", "mode")
        code, out = self.check()
        self.assertEqual(0, code, out)

    def test_a_workflow_copy_that_is_a_symbolic_link_is_reported(self):
        self.stage_entry("120000", "name: w\n", WORKFLOW)
        code, out = self.check()
        self.assertEqual(1, code, out)
        self.assertIn("UNEXPECTED-MODE %s 120000" % WORKFLOW, out)

    def test_a_file_outside_the_project_can_be_compared_by_its_absolute_path(self):
        write(self.clone / "README.md", "# the repository readme\n")
        self.git(self.clone, "add", "README.md")
        self.git(self.clone, "commit", "-q", "-m", "readme")
        pair = "README.md=%s" % (self.clone / "README.md")
        self.assertEqual(0, self.check(more=[pair])[0])
        write(self.clone / "README.md", "# changed after the scan\n")
        code, out = self.check(more=[pair])
        self.assertEqual(1, code, out)
        self.assertIn("DIFFERENT      README.md", out)

    def test_a_readme_that_is_a_symbolic_link_in_the_commit_is_reported(self):
        write(self.clone / "README.md", b"clean\n")
        self.stage_entry("120000", "docs/a.md", "README.md")
        pair = "README.md=%s" % (self.clone / "README.md")
        code, out = self.check(more=[pair])
        self.assertEqual(1, code, out)
        self.assertIn("UNEXPECTED-MODE README.md 120000", out)

    def test_the_github_listing_keeps_files_and_gitlinks_with_their_modes(self):
        listing = [{"path": "a.md", "mode": "100644", "type": "blob", "sha": "1" * 40},
                   {"path": "docs", "mode": "040000", "type": "tree", "sha": "2" * 40},
                   {"path": "docs/sub", "mode": "160000", "type": "commit", "sha": "3" * 40},
                   {"path": "docs/link", "mode": "120000", "type": "blob", "sha": "4" * 40}]
        self.assertEqual({"a.md": ("100644", "1" * 40), "docs/sub": ("160000", "3" * 40), "docs/link": ("120000", "4" * 40)},
                         verify_remote.normalize_tree(listing))


if __name__ == "__main__":
    unittest.main()
