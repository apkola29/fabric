#!/usr/bin/env python3
"""Tests for verify_remote.py: its --clone mode, which checks a commit before it is pushed, and its GitHub mode.

The clone tests build a small project and a throwaway clone, commit a mirror of the
project, change one thing and assert what the check reports. The GitHub tests replace
`gh` with a stand-in that answers from a table. GitHub is never contacted. Run from
the project folder:

    python -m unittest discover -s scripts -p "test_*.py" -v
"""

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        proc = subprocess.run(GIT + list(args), cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
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
        blob = subprocess.run(GIT + ["hash-object", "-w", "--stdin"], cwd=self.clone, input=content, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
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

    def test_an_extra_file_that_is_missing_locally_is_a_problem(self):
        code, out = self.check(more=["x.md=docs/no-such-file.md"])
        self.assertEqual(1, code, out)
        self.assertIn("MISSING-LOCAL  docs/no-such-file.md", out)
        self.assertIn("1 problem(s)", out)

    def test_an_extra_file_that_is_missing_from_the_commit_is_a_problem(self):
        code, out = self.check(more=["docs/not-in-the-commit.md=docs/a.md"])
        self.assertEqual(1, code, out)
        self.assertIn("MISSING-REMOTE docs/not-in-the-commit.md", out)
        self.assertIn("1 problem(s)", out)

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

    def readme_pair(self):
        return "README.md=%s" % (self.clone / "README.md")

    def commit_readme(self, data):
        write(self.clone / "README.md", data)
        self.git(self.clone, "add", "README.md")
        self.git(self.clone, "commit", "-q", "-m", "readme")

    def test_an_extra_file_with_windows_line_endings_matches_the_bytes_that_were_committed(self):
        self.commit_readme(b"# readme\r\nline\r\n")
        code, out = self.check(more=[self.readme_pair()])
        self.assertEqual(0, code, out)

    def test_an_extra_file_matches_when_git_stored_it_with_unix_line_endings(self):
        self.commit_readme(b"# readme\nline\n")
        write(self.clone / "README.md", b"# readme\r\nline\r\n")
        code, out = self.check(more=[self.readme_pair()])
        self.assertEqual(0, code, out)

    def test_an_extra_file_with_other_text_is_different_whatever_its_line_endings(self):
        self.commit_readme(b"# readme\nline\n")
        write(self.clone / "README.md", b"# readme\r\nanother line\r\n")
        code, out = self.check(more=[self.readme_pair()])
        self.assertEqual(1, code, out)
        self.assertIn("DIFFERENT      README.md", out)

    def test_ignore_rules_that_are_not_modelled_stop_the_check(self):
        write(self.project / ".gitignore", "private/\n[ab]*.md\n")
        with self.assertRaises(SystemExit) as stopped:
            self.check()
        self.assertIn("not modelled", str(stopped.exception))


class GithubListingTests(unittest.TestCase):
    """What the check does with the answers of the GitHub API: anything it cannot read stops it, and nothing is skipped."""
    ROOT = {"tree": [{"path": "fabric-automation", "mode": "040000", "type": "tree", "sha": "1" * 40}]}
    BLOB = {"path": "a.md", "mode": "100644", "type": "blob", "sha": "2" * 40}

    def read(self, full):
        def fake(*args):
            return full if args[0].endswith("?recursive=1") else self.ROOT
        with mock.patch.object(verify_remote, "gh_json", fake):
            return verify_remote.remote_tree("o/r", "c" * 40, "fabric-automation")

    def test_a_complete_listing_is_read(self):
        self.assertEqual({"a.md": ("100644", "2" * 40)}, self.read({"truncated": False, "tree": [self.BLOB]}))

    def test_a_truncated_listing_stops_the_check(self):
        with self.assertRaises(SystemExit):
            self.read({"truncated": True, "tree": [self.BLOB]})

    def test_a_listing_that_does_not_say_whether_it_is_complete_stops_the_check(self):
        for full in ({"tree": [self.BLOB]}, {"truncated": None, "tree": [self.BLOB]}, {"truncated": "false", "tree": [self.BLOB]}):
            with self.subTest(full=full):
                with self.assertRaises(SystemExit):
                    self.read(full)

    def test_an_entry_that_cannot_be_judged_stops_the_check_instead_of_being_skipped(self):
        broken = [{"mode": "100644", "type": "blob", "sha": "2" * 40}, {"path": "a.md", "mode": "100644", "sha": "2" * 40},
                  {"path": "a.md", "mode": "100644", "type": "blob"}, {"path": "a.md", "type": "blob", "sha": None}, "a.md", None]
        for entry in broken:
            with self.subTest(entry=entry):
                with self.assertRaises(SystemExit):
                    self.read({"truncated": False, "tree": [self.BLOB, entry]})

    def test_an_entry_of_a_type_that_is_not_known_stops_the_check(self):
        with self.assertRaises(SystemExit):
            self.read({"truncated": False, "tree": [dict(self.BLOB, type="weird")]})

    def test_a_listing_without_a_list_of_entries_stops_the_check(self):
        answers = {"an object": {"truncated": False, "tree": {}}, "null": {"truncated": False, "tree": None},
                   "text": {"truncated": False, "tree": ""}, "a number": {"truncated": False, "tree": 5}, "no entries key": {"truncated": False}}
        for name, full in answers.items():
            with self.subTest(name):
                with self.assertRaises(SystemExit) as stopped:
                    self.read(full)
                self.assertIn("without a tree listing", str(stopped.exception))


class GithubModeTests(unittest.TestCase):
    """main() against GitHub, with `gh` replaced by a stand-in that answers from a table, so that GitHub is never contacted."""
    HEAD = "c" * 40
    FOLDER = "d" * 40
    CONTENTS = "repos/o/r/contents/%s?ref=%s" % (WORKFLOW, HEAD)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name) / "project"
        write(self.project / ".gitignore", "private/\n__pycache__/\n*.pyc\n")
        write(self.project / "README.md", "# title\n")
        write(self.project / "docs" / "a.md", "text\n")
        write(self.project / "ci" / "w.yml", "name: w\n")
        files = [{"path": rel, "mode": "100644", "type": "blob", "sha": verify_remote.blob_sha((self.project / rel).read_bytes())}
                 for rel in verify_remote.publishable_files(self.project)]
        self.answers = {
            "repos/o/r/commits/master": {"sha": self.HEAD, "commit": {"message": "the head\n\nits body"}},
            "repos/o/r/git/trees/" + self.HEAD: {"tree": [{"path": "fabric-automation", "mode": "040000", "type": "tree", "sha": self.FOLDER}]},
            "repos/o/r/git/trees/%s?recursive=1" % self.FOLDER: {"truncated": False, "tree": files},
        }
        self.workflow_sha = verify_remote.blob_sha((self.project / "ci" / "w.yml").read_bytes())

    def gh(self, command, **kwargs):
        """Stands in for subprocess.run(["gh", "api", PATH, ...]): the text or JSON in the table, or a failure for a path that is not in it."""
        self.assertEqual(["gh", "api"], command[:2])
        answer = self.answers.get(command[2])
        if answer is None:
            return subprocess.CompletedProcess(command, 1, "", "gh: Not Found (HTTP 404)")
        return subprocess.CompletedProcess(command, 0, answer if isinstance(answer, str) else json.dumps(answer), "")

    def check(self, commit=None, extra=None):
        argv = ["--repo", "o/r", "--ref", "master", "--local", str(self.project)]
        if commit:
            argv += ["--commit", commit]
        if extra:
            argv += ["--extra", extra]
        out = io.StringIO()
        with mock.patch.object(verify_remote.subprocess, "run", self.gh), contextlib.redirect_stdout(out):
            code = verify_remote.main(argv)
        return code, out.getvalue()

    def test_a_remote_folder_that_holds_the_local_files_passes(self):
        code, out = self.check()
        self.assertEqual(0, code, out)
        self.assertIn("4 file(s) identical in fabric-automation", out)
        self.assertIn("0 problem(s)", out)

    def test_a_head_that_is_not_the_expected_commit_is_a_problem(self):
        code, out = self.check(commit="deadbeef00")
        self.assertEqual(1, code, out)
        self.assertIn("MISMATCH head is cccccccccc, expected deadbeef00", out)
        self.assertIn("1 problem(s)", out)

    def test_a_head_that_matches_the_expected_commit_is_not_a_problem(self):
        for expected in (self.HEAD, self.HEAD[:7]):
            with self.subTest(expected=expected):
                code, out = self.check(commit=expected)
                self.assertEqual(0, code, out)
                self.assertNotIn("MISMATCH", out)

    def test_a_regular_file_on_github_is_compared_by_its_hash(self):
        extra = "%s=ci/w.yml" % WORKFLOW
        self.answers[self.CONTENTS] = "file\t%s\n" % self.workflow_sha
        code, out = self.check(extra=extra)
        self.assertEqual(0, code, out)
        self.assertIn("1 managed file(s) identical", out)
        self.answers[self.CONTENTS] = "file\t%s\n" % ("0" * 40)
        code, out = self.check(extra=extra)
        self.assertEqual(1, code, out)
        self.assertIn("DIFFERENT      %s" % WORKFLOW, out)

    def test_a_symbolic_link_or_a_submodule_on_github_is_not_a_regular_file(self):
        # Each entry has the hash of the local file, so only the type that GitHub reports tells it from the file.
        for kind, mode in (("symlink", "120000"), ("submodule", "160000"), ("weird", "weird")):
            with self.subTest(kind):
                self.answers[self.CONTENTS] = "%s\t%s\n" % (kind, self.workflow_sha)
                code, out = self.check(extra="%s=ci/w.yml" % WORKFLOW)
                self.assertEqual(1, code, out)
                self.assertIn("UNEXPECTED-MODE %s %s" % (WORKFLOW, mode), out)

    def test_a_file_that_gh_cannot_find_on_github_is_missing(self):
        code, out = self.check(extra="%s=ci/w.yml" % WORKFLOW)
        self.assertEqual(1, code, out)
        self.assertIn("MISSING-REMOTE %s" % WORKFLOW, out)


if __name__ == "__main__":
    unittest.main()
