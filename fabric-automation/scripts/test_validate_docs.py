#!/usr/bin/env python3
"""Mutation tests for validate_docs.py.

Each test copies the project, injects one known defect and asserts that the
validator reports it. The unmodified copy must pass with no errors and no
warnings. Run from the project folder:

    python -m unittest discover -s scripts -p "test_*.py" -v
"""

import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(HERE))

import validate_docs  # noqa: E402

BRIEF = "docs/00-brief.md"
REQ = "docs/01-requirements.md"
DESIGN = "docs/04-design.md"
LOG = "docs/reviews/disposition-log.md"
CLOSURE = "docs/reviews/closure-gpt.md"


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        shutil.copytree(PROJECT, self.root, ignore=shutil.ignore_patterns("__pycache__", "private", ".pytest_cache"))

    def tearDown(self):
        self.tmp.cleanup()

    def edit(self, rel, change):
        path = self.root / rel
        raw = path.read_bytes().decode("utf-8")
        crlf = "\r\n" in raw
        original = raw.replace("\r\n", "\n")
        text = change(original)
        self.assertNotEqual(original, text, "the mutation changed nothing in %s, so this test would prove nothing" % rel)
        path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))

    def before_end(self, rel, line):
        self.edit(rel, lambda t: t.replace("<!-- END -->", line + "\n\n<!-- END -->", 1))

    def append(self, rel, text):
        self.edit(rel, lambda t: t + text)

    def validate(self, denylist=None):
        return validate_docs.run(self.root, denylist=denylist)

    def assert_flagged(self, report, check, level="ERROR"):
        found = sorted({(f[0], f[1]) for f in report.findings})
        self.assertTrue(report.has(level, check), "expected %s %s, got %s" % (level, check, found))

    def test_baseline_is_clean(self):
        report = self.validate()
        self.assertEqual([], report.findings, report.render(quiet=True))

    def test_table_row_with_extra_cell(self):
        self.edit(DESIGN, lambda t: re.sub(r"^(\| HR-1 \|)", r"\1 extra |", t, count=1, flags=re.M))
        self.assert_flagged(self.validate(), "table")

    def test_undefined_identifier(self):
        self.before_end(DESIGN, "A stray reference to FR-99.")
        self.assert_flagged(self.validate(), "id-undefined")

    def test_range_ending_at_undefined_identifier(self):
        self.before_end(DESIGN, "Covers FR-01 to FR-99.")
        self.assert_flagged(self.validate(), "id-range")

    def test_legacy_token_is_flagged_in_the_design(self):
        self.before_end(DESIGN, "The old ruleset RS-C is mentioned here.")
        self.assert_flagged(self.validate(), "id-undefined")

    def test_spike_count_claim(self):
        self.edit(DESIGN, lambda t: re.sub(r"Eleven(\s+(?:Phase 0\s+)?spikes)", r"Twelve\1", t))
        self.assert_flagged(self.validate(), "count-claim")

    def test_traceability_gap(self):
        self.edit(DESIGN, lambda t: re.sub(r"^\| FR-44 [^\n]*\n", "", t, flags=re.M))
        self.assert_flagged(self.validate(), "traceability")

    def test_decision_missing_from_design(self):
        self.edit(DESIGN, lambda t: re.sub(r"^\| D-32 [^\n]*\n", "", t, flags=re.M))
        self.assert_flagged(self.validate(), "decisions")

    def test_disposition_summary_mismatch(self):
        self.edit(LOG, lambda t: t.replace("| Gemini (F) | 20 |", "| Gemini (F) | 21 |", 1))
        self.assert_flagged(self.validate(), "disposition-summary")

    def test_closure_summary_mismatch(self):
        self.edit(LOG, lambda t: t.replace("| Gemini | 13 |", "| Gemini | 14 |", 1))
        self.assert_flagged(self.validate(), "closure-summary")

    def test_missing_disposition_row(self):
        self.edit(LOG, lambda t: re.sub(r"^\| O-12 [^\n]*\n", "", t, flags=re.M))
        self.assert_flagged(self.validate(), "disposition")

    def test_row_for_an_unknown_finding(self):
        self.edit(LOG, lambda t: re.sub(r"^(\| F-01 [^\n]*\n)", r"\1| F-99 | LOW | Accepted | none | 3.1 |\n", t, count=1, flags=re.M))
        self.assert_flagged(self.validate(), "disposition")

    def test_section_reference_to_missing_section(self):
        self.before_end(DESIGN, "See (9.9) for the detail.")
        self.assert_flagged(self.validate(), "section-ref")

    def test_version_mismatch(self):
        self.edit(DESIGN, lambda t: t.replace("requirements v0.3", "requirements v0.9", 1))
        self.assert_flagged(self.validate(), "version")

    def test_placeholder_marker(self):
        self.append(REQ, "\nTO" + "DO write this.\n")
        self.assert_flagged(self.validate(), "placeholder")

    def test_text_after_the_end_marker(self):
        self.append(DESIGN, "\nTrailing text after the end marker.\n")
        self.assert_flagged(self.validate(), "sentinel")

    def test_unclosed_code_fence(self):
        self.append(REQ, "\n```\n")
        self.assert_flagged(self.validate(), "fence")

    def test_mermaid_label_needs_quotes(self):
        self.edit(DESIGN, lambda t: t.replace('MP["Model proxy<br/>(holds the engine credential)"]', "MP[Model proxy<br/>(holds the engine credential)]", 1))
        self.assert_flagged(self.validate(), "mermaid")

    def test_mermaid_edge_to_undeclared_node(self):
        self.edit(DESIGN, lambda t: t.replace("  KP -.-> SBX\n", "  KP -.-> SBX\n  KP --> GHOST\n", 1))
        self.assert_flagged(self.validate(), "mermaid")

    def test_mermaid_state_diagram_garbage(self):
        self.edit(DESIGN, lambda t: t.replace("stateDiagram-v2\n", "stateDiagram-v2\n  this is not a transition\n", 1))
        self.assert_flagged(self.validate(), "mermaid")

    def test_broken_file_reference(self):
        self.before_end(DESIGN, "See `reviews/does-not-exist.md`.")
        self.assert_flagged(self.validate(), "path-ref")

    def test_reference_to_local_only_material(self):
        self.before_end(DESIGN, "See `research/local/survey.md`.")
        self.assert_flagged(self.validate(), "path-ref")

    def test_user_path_leak(self):
        value = "C:" + "\\" + "Users" + "\\" + "someone" + "\\" + "file.txt"
        self.append("README.md", value + "\n")
        self.assert_flagged(self.validate(), "leak")

    def test_email_leak(self):
        self.append("README.md", "someone" + "@" + "example.org\n")
        self.assert_flagged(self.validate(), "leak")

    def test_internal_host_leak(self):
        self.append("README.md", "https://team." + "share" + "point.com/site\n")
        self.assert_flagged(self.validate(), "leak")

    def test_guid_leak(self):
        self.append("README.md", "-".join(["12345678", "1234", "1234", "1234", "123456789abc"]) + "\n")
        self.assert_flagged(self.validate(), "leak")

    def test_token_leak(self):
        self.append("README.md", "gh" + "p_" + "a" * 36 + "\n")
        self.assert_flagged(self.validate(), "leak")

    def test_secret_assignment_leak(self):
        self.append("README.md", "client" + "_secret = " + "x" * 20 + "\n")
        self.assert_flagged(self.validate(), "leak")

    def test_private_denylist_term(self):
        deny = Path(self.tmp.name) / "deny.txt"
        deny.write_text("# private\nHard rules\n", encoding="utf-8")
        self.assert_flagged(self.validate(denylist=deny), "leak-denylist")

    def test_local_tool_path_leak(self):
        self.append("README.md", "~" + "/." + "copilot" + "/installed-" + "plugins/x\n")
        self.assert_flagged(self.validate(), "leak")

    def test_the_other_local_tool_path_is_flagged_too(self):
        self.append("README.md", "~" + "/." + "claude" + "/skills/x\n")
        self.assert_flagged(self.validate(), "leak")

    def test_the_ssh_user_of_a_git_remote_is_not_an_address_leak(self):
        self.append("README.md", "git" + "@github.com:owner/repo.git\n")
        self.assertEqual([], self.validate().findings)

    def test_only_that_exact_address_is_allowed_not_a_look_alike(self):
        for value in ("digit" + "@github.com", "git" + "@gitlab.com", "git" + "@github.com.evil.example"):
            with self.subTest(value=value):
                self.assertEqual(1, sum(1 for f in self._leaks_of(value) if f[1] == "leak"))

    def _leaks_of(self, text):
        self.append("README.md", "see %s here\n" % text)
        findings = self.validate().findings
        self.edit("README.md", lambda t: t.replace("see %s here\n" % text, ""))
        return findings

    def test_a_capitalised_user_name_in_a_unix_path(self):
        self.append("README.md", "/" + "Users" + "/Alice/notes.md\n")
        self.assert_flagged(self.validate(), "leak")

    def test_an_unreadable_denylist_is_an_error_not_a_crash(self):
        missing = Path(self.tmp.name) / "no-such-denylist.txt"
        self.assert_flagged(validate_docs.run(self.root, denylist=missing), "leak-denylist")

    TERM = "zzz-private" + "-term-zzz"

    def write_list(self, name, data):
        path = Path(self.tmp.name) / name
        path.write_bytes(data)
        return path

    def test_a_byte_order_mark_does_not_hide_the_first_private_term(self):
        self.append("README.md", "This line holds %s.\n" % self.TERM)
        deny = self.write_list("bom.txt", b"\xef\xbb\xbf" + self.TERM.encode("utf-8") + b"\r\n")
        report = self.validate(denylist=deny)
        self.assertTrue(any(f[1] == "leak-denylist" and "term appears" in f[4] for f in report.findings), report.render(quiet=True))

    def test_a_list_of_only_comments_behind_a_byte_order_mark_holds_no_terms(self):
        deny = self.write_list("bom-comment.txt", b"\xef\xbb\xbf# only a comment\n")
        report = validate_docs.run(self.root, denylist=deny, require_denylist=True)
        self.assert_flagged(report, "leak-denylist")

    def test_a_utf16_list_is_read(self):
        self.append("README.md", "This line holds %s.\n" % self.TERM)
        deny = self.write_list("utf16.txt", ("# private\n" + self.TERM + "\n").encode("utf-16"))
        report = self.validate(denylist=deny)
        self.assertTrue(any(f[1] == "leak-denylist" and "term appears" in f[4] for f in report.findings), report.render(quiet=True))

    def test_a_utf16_list_without_a_mark_is_refused_not_ignored(self):
        deny = self.write_list("utf16-nomark.txt", (self.TERM + "\n").encode("utf-16-le"))
        report = validate_docs.run(self.root, denylist=deny, require_denylist=True)
        self.assertTrue(any(f[1] == "leak-denylist" and "cannot read" in f[4] for f in report.findings), report.render(quiet=True))

    def test_read_denylist_drops_comments_blank_lines_and_marks(self):
        deny = self.write_list("mixed.txt", b"\xef\xbb\xbf# c\r\n\r\n  first  \r\n#x\r\nsecond\r\n")
        self.assertEqual(["first", "second"], validate_docs.read_denylist(deny))

    def test_a_file_type_the_leak_scan_does_not_read_blocks_publishing(self):
        (self.root / "docs" / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        self.assert_flagged(self.validate(), "unscanned-file")

    def test_a_file_without_an_extension_is_not_read_either(self):
        (self.root / "NOTICE").write_text("text\n", encoding="utf-8")
        self.assert_flagged(self.validate(), "unscanned-file")

    def test_files_that_are_never_published_are_not_flagged(self):
        for rel in ("private/notes.bin", "docs/research/local/survey.bin", "scripts/__pycache__/x.pyc", "docs/secret.env",
                    "tmp-scratch/data.bin", "docs/scratch.tmp"):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\x00\x01")
        self.assertEqual([], self.validate().findings)

    def test_publishable_files_follow_the_ignore_rules(self):
        (self.root / "tmp-scratch").mkdir()
        (self.root / "tmp-scratch" / "a.md").write_text("x\n", encoding="utf-8")
        listed = validate_docs.publishable_files(self.root)
        self.assertIn("README.md", listed)
        self.assertNotIn("tmp-scratch/a.md", listed)

    def test_a_control_character_in_a_text_file_is_flagged(self):
        self.append("README.md", "a line with a stray " + "\x01" + " control character\n")
        self.assert_flagged(self.validate(), "hygiene")

    def test_tab_form_feed_backspace_and_escape_are_not_control_characters_here(self):
        self.append("README.md", "tab\there, a form feed\x0c, a backspace\x08 and an escape\x1b[0m\n")
        self.assertFalse(self.validate().has("ERROR", "hygiene"))

    def make_link(self, link, target, directory=False):
        try:
            os.symlink(target, link, target_is_directory=directory)
        except (OSError, NotImplementedError):
            self.skipTest("this account cannot create symbolic links")

    def test_a_symbolic_link_to_a_file_is_flagged(self):
        self.make_link(self.root / "docs" / "link.md", self.root / "README.md")
        self.assert_flagged(self.validate(), "link")

    def test_a_symbolic_link_to_a_folder_is_flagged(self):
        self.make_link(self.root / "docs" / "linked-scripts", self.root / "scripts", directory=True)
        self.assert_flagged(self.validate(), "link")

    @unittest.skipUnless(sys.platform == "win32", "junctions exist only on Windows")
    def test_a_junction_is_flagged(self):
        link = self.root / "docs" / "junction"
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.root / "scripts")], capture_output=True, text=True)
        if made.returncode != 0:
            self.skipTest("could not create a junction: " + made.stdout.strip()[:80])
        self.assert_flagged(self.validate(), "link")

    def test_a_folder_without_links_reports_none(self):
        self.assertFalse(self.validate().has("ERROR", "link"))

    def run_main(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return validate_docs.main(["--root", str(self.root), "--quiet"])

    def test_a_private_list_in_the_project_is_used_without_being_asked(self):
        (self.root / "private").mkdir()
        (self.root / "private" / "denylist.txt").write_text("# private\nHard rules\n", encoding="utf-8")
        self.assertEqual(1, self.run_main())

    def test_a_project_without_a_private_list_is_not_checked_against_one(self):
        self.assertEqual(0, self.run_main())

    def test_publishing_requires_a_denylist(self):
        report = validate_docs.run(self.root, require_denylist=True)
        self.assert_flagged(report, "leak-denylist")

    def test_publishing_with_a_denylist_is_clean(self):
        deny = Path(self.tmp.name) / "deny.txt"
        deny.write_text("# private\n" + "zzz-no-such" + "-term-zzz\n", encoding="utf-8")
        report = validate_docs.run(self.root, denylist=deny, require_denylist=True)
        self.assertEqual([], report.findings, report.render(quiet=True))

    def test_scan_file_finds_a_leak_outside_the_project(self):
        outside = Path(self.tmp.name) / "outside.md"
        outside.write_text("contact " + "someone" + "@" + "example.org\n", encoding="utf-8")
        self.assert_flagged(validate_docs.run(self.root, extra_files=[outside]), "leak")

    def test_scan_file_accepts_a_clean_file(self):
        outside = Path(self.tmp.name) / "outside.md"
        outside.write_text("A clean line.\n", encoding="utf-8")
        report = validate_docs.run(self.root, extra_files=[outside])
        self.assertEqual([], report.findings, report.render(quiet=True))

    def test_scan_file_that_cannot_be_read(self):
        missing = Path(self.tmp.name) / "missing.md"
        self.assert_flagged(validate_docs.run(self.root, extra_files=[missing]), "leak")

    def test_missing_final_newline(self):
        self.edit(BRIEF, lambda t: t.rstrip("\n"))
        self.assert_flagged(self.validate(), "hygiene")

    def test_mixed_line_endings(self):
        path = self.root / BRIEF
        data = path.read_bytes().replace(b"\r\n", b"\n")
        path.write_bytes(data.replace(b"\n", b"\r\n", 1))
        self.assert_flagged(self.validate(), "hygiene")

    def test_garbled_text(self):
        self.append("README.md", "caf\u00c3\u00a9\n")
        self.assert_flagged(self.validate(), "mojibake")

    def test_required_file_missing(self):
        os.remove(self.root / "README.md")
        self.assert_flagged(self.validate(), "required-file")

    LOCAL_PATHS = [
        ("lower-case users folder", "C:" + "\\" + "users" + "\\" + "someone" + "\\" + "secret.txt"),
        ("forward slashes and lower case", "C:" + "/users/someone/other.txt"),
        ("mixed slashes", "C:" + "\\" + "Users/someone/x"),
        ("upper case", "D:" + "\\" + "USERS" + "\\" + "someone" + "\\" + "x"),
        ("lower-case app data folder", "in " + "\\" + "appdata" + "\\" + "local" + "\\" + "temp"),
        ("app data folder with forward slashes", "in /" + "AppData" + "/Roaming/x"),
        ("lower-case OneDrive tenant folder", "the folder onedrive" + " - contoso"),
    ]

    def test_a_local_path_is_found_in_any_case_and_with_either_slash(self):
        for label, value in self.LOCAL_PATHS:
            with self.subTest(label):
                self.assertEqual(1, sum(1 for f in self._leaks_of(value) if f[1] == "leak"), value)

    def test_an_api_url_with_a_users_segment_is_not_a_local_path(self):
        self.assertEqual([], [f for f in self._leaks_of("https://api.github.com/users/octocat/repos") if f[1] == "leak"])

    HIDDEN = [
        ("a zero-width space", "se\u200bcret"),
        ("a soft hyphen", "se\u00adcret"),
        ("a right-to-left override", "\u202etext"),
        ("a C1 control character", "next\u0085line"),
        ("a Cyrillic letter inside a Latin word", "Us\u0435rs"),
        ("a Greek letter", "\u03b1lpha"),
        ("a full-width Latin letter", "\uff21BC"),
    ]

    def test_characters_that_hide_text_from_the_scan_are_refused(self):
        for label, value in self.HIDDEN:
            with self.subTest(label):
                self.assertTrue(any(f[1] == "hygiene" for f in self._leaks_of(value)), label)

    def test_typographic_punctuation_and_accented_latin_letters_are_fine(self):
        self.assertEqual([], [f for f in self._leaks_of("an em dash \u2014, an arrow \u2192, a middle dot \u00b7, a caf\u00e8 and a check \u2714\ufe0f") if f[1] == "hygiene"])

    def test_a_nul_byte_in_a_text_file_is_flagged(self):
        path = self.root / "README.md"
        path.write_bytes(path.read_bytes() + b"a line with a NUL \x00 byte\r\n")
        self.assertTrue(any(f[1] == "hygiene" and "NUL" in f[4] for f in self.validate().findings))

    def extra(self, name, data):
        path = Path(self.tmp.name) / name
        path.write_bytes(data)
        return path

    def test_scan_file_refuses_what_the_leak_scan_cannot_read(self):
        cases = {
            "utf16.md": "a private term\n".encode("utf-16"),
            "nul.md": b"a line\x00with a NUL\n",
            "invalid.md": b"invalid \xc3\x28 bytes\n",
            "control.md": b"a stray \x01 control character\n",
            "hidden.md": "se\u200bcret\n".encode("utf-8"),
        }
        for name, data in cases.items():
            with self.subTest(name):
                report = validate_docs.run(self.root, extra_files=[self.extra(name, data)])
                self.assertTrue(report.has("ERROR", "hygiene"), report.render(quiet=True))

    def test_scan_file_still_finds_a_private_term_in_a_utf8_file(self):
        deny = self.write_list("deny.txt", (self.TERM + "\n").encode("utf-8"))
        report = validate_docs.run(self.root, denylist=deny, extra_files=[self.extra("term.md", ("a line with " + self.TERM + "\n").encode("utf-8"))])
        self.assert_flagged(report, "leak-denylist")

    def test_scan_file_refuses_a_symbolic_link(self):
        real = self.extra("real.md", b"A clean line.\n")
        link = Path(self.tmp.name) / "link.md"
        self.make_link(link, real)
        self.assert_flagged(validate_docs.run(self.root, extra_files=[link]), "link")

    def test_scan_file_refuses_a_link_even_where_links_cannot_be_made(self):
        outside = self.extra("real.md", b"A clean line.\n")
        with mock.patch.object(validate_docs, "is_link", lambda path: Path(path) == outside):
            self.assert_flagged(validate_docs.run(self.root, extra_files=[outside]), "link")

    def test_a_project_folder_that_is_a_symbolic_link_is_refused(self):
        link = Path(self.tmp.name) / "symlink-root"
        self.make_link(link, self.root, directory=True)
        self.assert_flagged(validate_docs.run(link), "link")

    @unittest.skipUnless(sys.platform == "win32", "junctions exist only on Windows")
    def test_a_project_folder_that_is_a_junction_is_refused(self):
        link = Path(self.tmp.name) / "junction-root"
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.root)], capture_output=True, text=True)
        if made.returncode != 0:
            self.skipTest("could not create a junction: " + made.stdout.strip()[:80])
        self.assert_flagged(validate_docs.run(link), "link")

    def test_a_nested_ignore_file_is_refused_because_it_is_not_modelled(self):
        (self.root / "docs" / ".gitignore").write_text("*.md\n", encoding="utf-8")
        self.assert_flagged(self.validate(), "gitignore")

    def test_ignore_syntax_that_is_not_modelled_is_refused(self):
        for rule in ("[ab]*.md", "docs/**/x.md", "\\#literal", "**/x.md"):
            with self.subTest(rule):
                self.append(".gitignore", rule + "\n")
                self.assert_flagged(self.validate(), "gitignore")
                self.edit(".gitignore", lambda t: t.replace(rule + "\n", ""))


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class IgnoreRuleTests(unittest.TestCase):
    """The rule engine against Git itself: what Git would add must be what publishable_files lists."""

    FILES = ["a.md", "b.tmp", "tmp1/x.md", "tmpdir/y.md", "docs/a.md", "docs/b.tmp", "docs/keep.bin", "docs/sub/c.md", "docs/sub/d.tmp",
             "a/b", "axb", "a/c/b", ".env", "docs/.env", "src/x.pyc", "build/out/z.bin", "foo.txt", "dir/foo.txt", "dir/deep/foo.txt",
             "nested/private/secret.md", "private/secret.md", "docs/q?.md", "docs/qa.md"]
    RULESETS = [
        ["*.tmp"], ["tmp*/"], ["/b.tmp"], ["docs/*.tmp"], ["a*b"], ["*.tmp", "!docs/b.tmp"], ["private/"], ["docs/", "!docs/keep.bin"],
        [".env", "*.pyc"], ["build"], ["/build/"], ["docs/sub"], ["docs/q?.md"], ["foo.txt", "!dir/foo.txt"], ["dir/", "!dir/foo.txt", "*.md"],
        ["# a comment", "", "  *.tmp  "], ["a/"], ["/a"], ["*", "!*.md"], ["docs/*"], ["/docs/sub/"],
    ]

    def git(self, root, *args):
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=env)

    def test_every_rule_set_selects_the_files_that_git_would_add(self):
        for rules in self.RULESETS:
            with self.subTest(rules=rules), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.assertEqual(0, self.git(root, "init", "-q").returncode)
                (root / ".gitignore").write_text("\n".join(rules) + "\n", encoding="utf-8")
                for rel in self.FILES:
                    if "?" in rel and sys.platform == "win32":
                        continue
                    path = root / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("x\n", encoding="utf-8")
                listed = self.git(root, "ls-files", "--others", "--exclude-standard", "-z")
                self.assertEqual(0, listed.returncode, listed.stderr)
                by_git = {p for p in listed.stdout.split("\0") if p and p != ".gitignore"}
                parsed = validate_docs.ignore_rules(root)
                mine = {rel for rel in self.FILES if (root / rel).exists() and not validate_docs.is_ignored(rel, parsed)}
                self.assertEqual(sorted(by_git), sorted(mine), "rules %r" % (rules,))


if __name__ == "__main__":
    unittest.main()
