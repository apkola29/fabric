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
import time
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

        def skip(folder, names):
            # What the toolchain generates for a machine (all ignored by Git) is not part of the project that these tests copy.
            skipped = {n for n in names if n in ("__pycache__", "private", ".pytest_cache", ".factory", ".claude", ".mcp.json")}
            if Path(folder) == PROJECT / ".github":
                skipped.add("skills")
            return skipped
        shutil.copytree(PROJECT, self.root, ignore=skip)

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

    def test_a_package_name_with_a_version_is_not_an_email(self):
        values = ["name" + "@" + "1.6.0", "@scope/name" + "@" + "1.6.10", "Package.Id" + "@" + "3.0.0-beta.3",
                  "tool" + "@" + "0.24.0-beta", "pkg" + "@" + "2.0.0-rc.12", "pkg" + "@" + "1.0", "pkg" + "@" + "1.0.0.rc1",
                  "pkg" + "@" + "2.1.a"]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual([], [f for f in self._leaks_of(value) if f[1] == "leak"])

    def test_real_addresses_are_still_emails(self):
        values = ["someone" + "@" + "example.org", "first.last+tag" + "@" + "sub.example.co.uk", "a" + "@" + "b.cc",
                  "x" + "@" + "example.xn--p1ai", "me" + "@" + "1.example.org"]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(1, sum(1 for f in self._leaks_of(value) if f[1] == "leak"))

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

    def test_a_private_term_in_the_name_of_a_project_file_is_a_leak(self):
        name = "docs/" + self.TERM.upper() + "-notes.md"
        (self.root / name).write_bytes(b"A clean line.\n")
        deny = self.write_list("deny.txt", (self.TERM + "\n").encode("utf-8"))
        found = [f for f in self.validate(denylist=deny).findings if f[2] == name]
        self.assertEqual([("ERROR", "leak-denylist")], [(f[0], f[1]) for f in found])
        self.assertIn("file name", found[0][4])

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

    def test_a_tab_is_not_a_control_character_here(self):
        self.append("README.md", "a tab\there\n")
        self.assertFalse(self.validate().has("ERROR", "hygiene"))

    def test_every_control_character_except_tab_line_feed_and_carriage_return_is_refused(self):
        for code in list(range(0x20)) + [0x7F]:
            with self.subTest("U+%04X" % code):
                self.assertEqual(code not in (0x09, 0x0A, 0x0D), bool(validate_docs.CONTROL_CHARS.search(chr(code))))

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
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.root / "scripts")], capture_output=True, encoding="utf-8", errors="replace")
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

    def leaks_by_line(self, values):
        """{value: pattern names of the leak findings on its line}. The values go into README.md, one per line, and are judged in one run."""
        self.append("README.md", "".join("see %s here\n" % value for value in values))
        lines = (self.root / "README.md").read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")
        findings = self.validate().findings
        return {value: [f[4].split()[0] for f in findings if f[1] == "leak" and f[3] == lines.index("see %s here" % value) + 1]
                for value in values}

    FOREIGN_PATHS = [
        ("escaped backslashes as in JSON or Python source", "C:" + "\\" * 2 + "Users" + "\\" * 2 + "someone" + "\\" * 2 + "x", "user-path"),
        ("repeated forward slashes", "C:" + "//" + "Users" + "//" + "someone" + "//" + "x", "user-path"),
        ("a WSL mount", "/mnt/c/" + "users" + "/someone/x", "user-path"),
        ("a WSL mount with a capital letter", "/mnt/c/" + "Users" + "/someone/x", "user-path"),
        ("a Git Bash drive", "/c/" + "users" + "/someone/x", "user-path"),
        ("a Git Bash drive after an equals sign", "cd=/c/" + "users" + "/someone/x", "user-path"),
        ("a UNC administrative share", "\\" * 2 + "localhost" + "\\" + "c$" + "\\" + "Users" + "\\" + "someone" + "\\" + "x", "user-path"),
        ("a macOS home folder without a trailing slash", "/" + "Users" + "/someone", "user-path"),
        ("a Linux home folder", "/" + "home" + "/someone/x", "user-path"),
        ("a Linux home folder without a trailing slash", "/" + "home" + "/someone", "user-path"),
        ("a local tool folder with escaped backslashes", "~" + "\\" * 2 + "." + "copilot" + "\\" * 2 + "x", "local-tool-path"),
        ("a local tool folder with repeated forward slashes", "~" + "//" + "." + "claude" + "//" + "x", "local-tool-path"),
    ]

    def test_path_forms_that_escaping_and_other_systems_produce_are_found(self):
        found = self.leaks_by_line([value for _, value, _ in self.FOREIGN_PATHS])
        for label, value, name in self.FOREIGN_PATHS:
            with self.subTest(label):
                self.assertEqual([name], found[value])

    def test_web_addresses_that_resemble_paths_are_not_local_paths(self):
        values = ["https://api.github.com/users/octocat/repos",
                  "https://example.com/c/" + "users" + "/42",
                  "https://www.businesswire.com/news/home/20260513083026/en/"]
        values += [before + "/c/" + "users" + "/someone" for before in ("a", "9", "_", ".", "-")]
        found = self.leaks_by_line(values)
        for value in values:
            with self.subTest(value):
                self.assertEqual([], found[value])

    REFUSED = [
        ("a zero-width space", "\u200b"),
        ("a soft hyphen", "\u00ad"),
        ("a right-to-left override", "\u202e"),
        ("a C1 control character", "\u0085"),
        ("a Cyrillic letter", "\u0435"),
        ("a Greek letter", "\u03b1"),
        ("a full-width Latin letter", "\uff21"),
        ("a combining grapheme joiner", "\u034f"),
        ("a variation selector", "\ufe00"),
        ("the emoji variation selector", "\ufe0f"),
        ("a variation selector outside the first plane", "\U000e0100"),
        ("a combining accent", "\u0301"),
        ("a Roman numeral that looks like a letter", "\u216d"),
        ("a Latin letter that is not ASCII", "\u0261"),
        ("a small capital letter", "\ua731"),
        ("a private use character", "\ue000"),
        ("a line separator", "\u2028"),
        ("a paragraph separator", "\u2029"),
        ("a no-break space", "\u00a0"),
        ("a backspace", "\x08"),
        ("a form feed", "\x0c"),
        ("an escape", "\x1b"),
    ]

    def probe(self, name, text):
        """A new text file in docs/, so that one run can judge many files; returns its relative path."""
        (self.root / "docs" / name).write_bytes(text.encode("utf-8"))
        return "docs/" + name

    def test_characters_that_hide_text_from_the_scan_are_refused(self):
        probes = {label: self.probe("probe-%02d.md" % number, "a line with se%scret inside\n" % ch)
                  for number, (label, ch) in enumerate(self.REFUSED)}
        findings = self.validate().findings
        for label, ch in self.REFUSED:
            with self.subTest(label):
                self.assertTrue(validate_docs.hidden_character(ch), "hidden_character accepts it")
                found = [f for f in findings if f[0] == "ERROR" and f[1] == "hygiene" and f[2] == probes[label]]
                self.assertTrue(found, "a project file holding it is accepted")
                if ord(ch) > 0x7F:
                    self.assertIn("U+%04X" % ord(ch), found[0][4])

    def test_a_file_holding_every_allowed_character_is_clean(self):
        path = self.probe("allowed.md", "".join(chr(code) for code in sorted(CharacterTests.allowed())) + "\n")
        self.assertEqual([], [f for f in self.validate().findings if f[2] == path])

    def test_typographic_punctuation_and_accented_latin_letters_are_fine(self):
        self.assertEqual([], [f for f in self._leaks_of("an em dash \u2014, an arrow \u2192, a middle dot \u00b7, a caf\u00e8 and a check \u2714") if f[1] == "hygiene"])

    def test_a_nul_byte_in_a_text_file_is_flagged(self):
        path = self.root / "README.md"
        path.write_bytes(path.read_bytes() + b"a line with a NUL \x00 byte\r\n")
        self.assertTrue(any(f[1] == "hygiene" and "NUL" in f[4] for f in self.validate().findings))

    def extra(self, name, data):
        path = Path(self.tmp.name) / name
        path.write_bytes(data)
        return path

    def test_scan_file_refuses_what_the_leak_scan_cannot_read(self):
        # Each case names the message of the check that is meant to stop it: a second check (the control characters, the
        # characters that are not allowed) would stop several of them anyway, and the one meant for it could be lost unseen.
        cases = {
            "utf16.md": ("a private term\n".encode("utf-16"), "NUL bytes"),
            "nul.md": (b"a line\x00with a NUL\n", "NUL bytes"),
            "invalid.md": (b"invalid \xc3\x28 bytes\n", "not valid UTF-8"),
            "control.md": (b"a stray \x01 control character\n", "control character"),
            "hidden.md": ("se\u200bcret\n".encode("utf-8"), "U+200B"),
        }
        for name, (data, message) in cases.items():
            with self.subTest(name):
                report = validate_docs.run(self.root, extra_files=[self.extra(name, data)])
                messages = [f[4] for f in report.findings if f[0] == "ERROR" and f[1] == "hygiene"]
                self.assertTrue(any(message in m for m in messages), report.render(quiet=True))

    def test_scan_file_still_finds_a_private_term_in_a_utf8_file(self):
        deny = self.write_list("deny.txt", (self.TERM + "\n").encode("utf-8"))
        report = validate_docs.run(self.root, denylist=deny, extra_files=[self.extra("term.md", ("a line with " + self.TERM + "\n").encode("utf-8"))])
        self.assert_flagged(report, "leak-denylist")

    SPLITTERS = [
        ("a vertical tab", "\x0b"),
        ("a form feed", "\x0c"),
        ("a file separator", "\x1c"),
        ("a group separator", "\x1d"),
        ("a record separator", "\x1e"),
        ("a next-line control character", "\x85"),
        ("a line separator", "\u2028"),
        ("a paragraph separator", "\u2029"),
        ("a lone carriage return", "\r"),
    ]

    def extra_findings(self, files, denylist=None):
        """Run with these files ({name: bytes}), kept outside the project; returns {name: the findings that name the file}."""
        paths = [self.extra(name, data) for name, data in files.items()]
        report = validate_docs.run(self.root, denylist=denylist, extra_files=paths)
        return {name: [f for f in report.findings if f[2].startswith(name + " ")] for name in files}

    def test_scan_file_is_not_fooled_by_a_character_that_splits_lines_in_python(self):
        deny = self.write_list("deny.txt", b"supersecret\n")
        files = {"split-%d.md" % number: ("a line with super" + ch + "secret in it\n").encode("utf-8")
                 for number, (_, ch) in enumerate(self.SPLITTERS)}
        found = self.extra_findings(files, deny)
        for number, (label, _) in enumerate(self.SPLITTERS):
            with self.subTest(label):
                self.assertTrue([f for f in found["split-%d.md" % number] if f[0] == "ERROR"], "the file is accepted")

    def test_scan_file_reports_what_a_project_file_reports(self):
        found = self.extra_findings({
            "lone-cr.md": b"one\rtwo\n",
            "mixed.md": b"one\r\ntwo\nthree\n",
            "garbled.md": "caf\u00c3\u00a9\n".encode("utf-8"),
            "crlf.md": b"one\r\ntwo\r\n",
        })
        for name, check, text in (("lone-cr.md", "hygiene", "lone carriage return"), ("mixed.md", "hygiene", "mixed line endings"),
                                  ("garbled.md", "mojibake", "garbled")):
            with self.subTest(name):
                self.assertTrue([f for f in found[name] if f[0] == "ERROR" and f[1] == check and text in f[4]], found[name])
        with self.subTest("a file with CRLF endings only"):
            self.assertEqual([], found["crlf.md"])

    def test_scan_file_warns_about_a_byte_order_mark_without_refusing_the_file(self):
        found = self.extra_findings({"bom.md": b"\xef\xbb\xbfA clean line.\n"})
        self.assertEqual([("WARN", "hygiene")], [(f[0], f[1]) for f in found["bom.md"]])

    def test_a_byte_order_mark_in_a_project_file_is_only_a_warning(self):
        path = self.root / "README.md"
        path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
        self.assertEqual([("WARN", "hygiene")], [(f[0], f[1]) for f in self.validate().findings if f[2] == "README.md"])

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
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.root)], capture_output=True, encoding="utf-8", errors="replace")
        if made.returncode != 0:
            self.skipTest("could not create a junction: " + made.stdout.strip()[:80])
        self.assert_flagged(validate_docs.run(link), "link")

    @unittest.skipUnless(sys.platform == "win32", "junctions exist only on Windows")
    def test_the_default_project_folder_is_not_resolved_through_a_junction(self):
        link = Path(self.tmp.name) / "junction-root"
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.root)], capture_output=True, encoding="utf-8", errors="replace")
        if made.returncode != 0:
            self.skipTest("could not create a junction: " + made.stdout.strip()[:80])
        ran = subprocess.run([sys.executable, str(link / "scripts" / "validate_docs.py"), "--quiet"], capture_output=True, encoding="utf-8", errors="replace")
        self.assertEqual(1, ran.returncode, ran.stdout + ran.stderr)
        self.assertIn("the project folder itself is a symbolic link or junction", ran.stdout)

    def test_a_nested_ignore_file_is_refused_because_it_is_not_modelled(self):
        (self.root / "docs" / ".gitignore").write_text("*.md\n", encoding="utf-8")
        self.assert_flagged(self.validate(), "gitignore")

    def test_ignore_syntax_that_is_not_modelled_is_refused(self):
        path = self.root / ".gitignore"
        original = path.read_bytes()
        for rule in ("[ab]*.md", "docs/**/x.md", "\\#literal", "**/x.md", "/", "!", "!/", "//secret.bin"):
            with self.subTest(rule):
                path.write_bytes(original)
                self.append(".gitignore", rule + "\n")
                self.assert_flagged(self.validate(), "gitignore")

    def test_a_file_that_depends_on_git_folding_case_is_reported(self):
        self.append(".gitignore", "!Important.tmp\n")
        (self.root / "docs" / "important.tmp").write_bytes(b"x\n")
        report = self.validate()
        self.assertTrue(any(f[0] == "ERROR" and f[1] == "gitignore" and "core.ignorecase" in f[4] for f in report.findings), report.render(quiet=True))

    def test_an_ignore_file_inside_local_only_material_is_not_a_problem(self):
        nested = self.root / "docs" / "research" / "local" / "clone"
        nested.mkdir(parents=True)
        (nested / ".gitignore").write_bytes(b"[ab]*\n")
        self.assertFalse(self.validate().has("ERROR", "gitignore"))


class CharacterTests(unittest.TestCase):
    """Which characters a document may hold, judged on the functions themselves."""

    POINTS = (0xA7, 0xA9, 0xAB, 0xAE, 0xB0, 0xB1, 0xB5, 0xB6, 0xB7, 0xBB, 0xD7, 0xF7,
              0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2020, 0x2022, 0x2026, 0x2032, 0x2033, 0x2122,
              0x21D2, 0x21D4, 0x2212, 0x2248, 0x2260, 0x2264, 0x2265, 0x2713, 0x2714)
    RANGES = ((0xC0, 0xD6), (0xD8, 0xF6), (0xF8, 0xFF), (0x2190, 0x2195), (0x2500, 0x257F))
    USED_BY_THE_PROJECT = (0x2014, 0x2192, 0x2248, 0x2013, 0xB7, 0x2264, 0x2194, 0xD7, 0x2265, 0x2260, 0x2212, 0xA7, 0x2026, 0xA9, 0xE8, 0x2714)

    @classmethod
    def allowed(cls):
        """The non-ASCII code points that may appear. The decided list is repeated here so that a change to it has to be deliberate."""
        return set(cls.POINTS).union(*(range(first, last + 1) for first, last in cls.RANGES))

    def test_exactly_the_decided_non_ascii_characters_are_allowed(self):
        allowed = self.allowed()
        tested = list(range(0x80, 0x10000)) + list(range(0x10000, 0x110000, 7)) + list(range(0xE0000, 0xE0200))
        wrong = [code for code in tested if (validate_docs.hidden_character(chr(code)) is None) != (code in allowed)]
        self.assertEqual([], ["U+%04X" % code for code in wrong[:20]])

    def test_the_characters_the_project_uses_are_allowed(self):
        for code in self.USED_BY_THE_PROJECT:
            with self.subTest("U+%04X" % code):
                self.assertIsNone(validate_docs.hidden_character(chr(code)))

    def test_printable_ascii_tab_line_feed_and_carriage_return_are_allowed_and_other_controls_are_not(self):
        wrong = [code for code in range(0x80)
                 if (validate_docs.hidden_character(chr(code)) is None) != (code in (0x09, 0x0A, 0x0D) or 0x20 <= code < 0x7F)]
        self.assertEqual([], ["U+%04X" % code for code in wrong])

    def test_a_refused_character_is_named_with_its_code_point_and_the_remedy(self):
        number, message = validate_docs.hidden_in(["a clean line", "a line with \u034f inside"])
        self.assertEqual(2, number)
        for part in ("U+034F", "plain ASCII", "allowlist", "validate_docs.py"):
            self.assertIn(part, message)

    def test_a_byte_order_mark_is_skipped_only_at_the_very_start_of_a_file(self):
        self.assertIsNone(validate_docs.hidden_in(["\ufeffa clean line", "another"]))
        self.assertEqual(2, validate_docs.hidden_in(["a clean line", "\ufeffnot at the start"])[0])
        self.assertEqual(1, validate_docs.hidden_in(["x\ufeffy"])[0])


class PatternTests(unittest.TestCase):
    """The leak patterns on their own."""

    def test_a_line_of_slashes_is_scanned_in_linear_time(self):
        started = time.perf_counter()
        for text in ("/" * 20000 + "x", "\\" * 20000 + "x", "\\/" * 10000 + " x", "//" * 10000 + "x", "~" + "/" * 20000, "/c" + "/" * 20000):
            for _, pattern in validate_docs.LEAK_PATTERNS:
                pattern.search(text)
        self.assertLess(time.perf_counter() - started, 5.0)


class IgnoreFileTests(unittest.TestCase):
    """How the ignore file is read and what is refused, on small folders and without Git."""

    CONTROLS = ["\x0c", "\x0b", "\r", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029", "\x00", "\x08", "\x1b", "\x7f", "\x9f"]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.count = 0

    def tearDown(self):
        self.tmp.cleanup()

    def project(self, rules, files=()):
        """A new folder with this ignore file (bytes) and these small files."""
        self.count += 1
        folder = self.root / ("project-%d" % self.count)
        folder.mkdir()
        (folder / ".gitignore").write_bytes(rules)
        for rel in files:
            (folder / rel).parent.mkdir(parents=True, exist_ok=True)
            (folder / rel).write_bytes(b"x\n")
        return folder

    def refusal(self, rules):
        with self.assertRaises(validate_docs.UnsupportedIgnore) as raised:
            validate_docs.ignore_rules(self.project(rules))
        return str(raised.exception)

    def test_a_doubled_slash_or_a_lone_slash_is_refused_because_git_keeps_it_in_the_pattern(self):
        for rule in ("//secret.bin", "docs//", "/docs//", "!//secret.bin", "docs//x.md", "/", "!", "!/"):
            with self.subTest(rule):
                self.assertIn("not modelled", self.refusal(rule.encode("utf-8") + b"\n"))

    def test_a_line_with_a_control_or_separator_character_is_refused_with_a_message_that_is_safe_to_print(self):
        for ch in self.CONTROLS:
            with self.subTest("U+%04X" % ord(ch)):
                message = self.refusal(("dummy" + ch + "*.bin\n").encode("utf-8"))
                self.assertIn("not modelled", message)
                self.assertNotIn(ch, message)
                self.assertTrue(message.isprintable(), ascii(message))

    def test_a_comment_line_is_checked_for_these_characters_too(self):
        self.assertIn("not modelled", self.refusal(b"# note\x0c*.bin\n"))

    def test_one_carriage_return_before_the_line_feed_is_dropped_like_git_and_a_second_one_is_refused(self):
        rules = validate_docs.ignore_rules(self.project(b"*.tmp\r\n*.bin\r\n"))
        self.assertTrue(validate_docs.is_ignored("a.tmp", rules))
        self.assertTrue(validate_docs.is_ignored("a.bin", rules))
        self.assertIn("not modelled", self.refusal(b"*.tmp\r\r\n"))

    def test_one_leading_byte_order_mark_is_skipped_like_git_and_a_second_one_is_not(self):
        once = validate_docs.ignore_rules(self.project(b"\xef\xbb\xbf*.tmp\n"))
        self.assertTrue(validate_docs.is_ignored("a.tmp", once))
        twice = validate_docs.ignore_rules(self.project(b"\xef\xbb\xbf\xef\xbb\xbf*.tmp\n"))
        self.assertFalse(validate_docs.is_ignored("a.tmp", twice))

    def test_an_ignore_file_that_is_not_utf8_is_refused_and_does_not_crash(self):
        message = self.refusal(b"caf\xe9\n")
        self.assertIn("UTF-8", message)
        self.assertIn("not modelled", message)

    def test_a_tab_inside_a_rule_is_allowed(self):
        rules = validate_docs.ignore_rules(self.project(b"*.t\tmp\n"))
        self.assertTrue(validate_docs.is_ignored("a.t\tmp", rules))

    def test_a_nested_ignore_file_in_local_only_material_is_not_a_problem(self):
        folder = self.project(b"", ["docs/research/local/.gitignore", "docs/research/local/clone/.gitignore"])
        self.assertEqual([], validate_docs.ignore_rules(folder))

    def test_a_nested_ignore_file_in_a_skipped_folder_is_not_a_problem(self):
        folder = self.project(b"", ["private/clone/.gitignore", "scripts/__pycache__/.gitignore"])
        self.assertEqual([], validate_docs.ignore_rules(folder))

    def test_a_nested_ignore_file_elsewhere_is_still_refused(self):
        for rel in ("docs/.gitignore", "docs/research/other/.gitignore", "docs/research/local-notes/.gitignore"):
            with self.subTest(rel), self.assertRaises(validate_docs.UnsupportedIgnore):
                validate_docs.ignore_rules(self.project(b"", [rel]))

    def test_case_is_folded_only_when_asked(self):
        rules = validate_docs.ignore_rules(self.project(b"*.TMP\n!Important.tmp\nDOCS/\n"))
        self.assertFalse(validate_docs.is_ignored("a.tmp", rules))
        self.assertTrue(validate_docs.is_ignored("a.tmp", rules, fold=True))
        self.assertFalse(validate_docs.is_ignored("docs/a.md", rules))
        self.assertTrue(validate_docs.is_ignored("docs/a.md", rules, fold=True))
        self.assertTrue(validate_docs.is_ignored("c.TMP", rules))
        self.assertFalse(validate_docs.is_ignored("important.tmp", rules, fold=True))

    def test_a_file_that_is_ignored_or_kept_depending_on_git_folding_case_is_refused(self):
        cases = [
            (b"*.tmp\n!Important.tmp\n", "important.tmp"),
            (b"*.TMP\n", "a.tmp"),
            (b"DOCS/\n", "docs/a.md"),
            (b"readme.MD\n", "README.md"),
            (b"/SRC/main.py\n", "src/main.py"),
        ]
        for rules, rel in cases:
            with self.subTest(rules=rules):
                with self.assertRaises(validate_docs.UnsupportedIgnore) as raised:
                    validate_docs.publishable_files(self.project(rules, [rel]))
                self.assertIn("core.ignorecase", str(raised.exception))
                self.assertIn(rel, str(raised.exception))

    def test_a_rule_in_another_case_than_every_file_is_not_a_problem(self):
        folder = self.project(b"*.TMP\n!Important.tmp\nDOCS/\n", ["a.md", "docs2/b.md", "keep.TXT", "c.TMP"])
        self.assertEqual(sorted([".gitignore", "a.md", "docs2/b.md", "keep.TXT"]), sorted(validate_docs.publishable_files(folder)))

    def test_a_refusal_that_names_a_file_is_safe_to_print(self):
        name = "dir\u2028"
        try:
            ambiguous = self.project(b"*.tmp\n!Important.tmp\n", [name + "/important.tmp"])
            nested = self.project(b"", [name + "/.gitignore"])
        except OSError:
            self.skipTest("this file system does not allow the folder name")
        with self.assertRaises(validate_docs.UnsupportedIgnore) as by_case:
            validate_docs.publishable_files(ambiguous)
        with self.assertRaises(validate_docs.UnsupportedIgnore) as by_nesting:
            validate_docs.ignore_rules(nested)
        for raised in (by_case, by_nesting):
            self.assertTrue(str(raised.exception).isprintable(), ascii(str(raised.exception)))


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class IgnoreRuleTests(unittest.TestCase):
    """The rule engine against Git itself: what Git would add must be what publishable_files lists."""

    FILES = ["a.md", "b.tmp", "tmp1/x.md", "tmpdir/y.md", "docs/a.md", "docs/b.tmp", "docs/keep.bin", "docs/sub/c.md", "docs/sub/d.tmp",
             "a/b", "axb", "a/c/b", ".env", "docs/.env", "src/x.pyc", "build/out/z.bin", "foo.txt", "dir/foo.txt", "dir/deep/foo.txt",
             "nested/private/secret.md", "private/secret.md", "docs/q?.md", "docs/qa.md", "x/docs/b.tmp", "docs/q/.md"]
    RULESETS = [
        ["*.tmp"], ["tmp*/"], ["/b.tmp"], ["docs/*.tmp"], ["a*b"], ["*.tmp", "!docs/b.tmp"], ["private/"], ["docs/", "!docs/keep.bin"],
        [".env", "*.pyc"], ["build"], ["/build/"], ["docs/sub"], ["docs/q?.md"], ["foo.txt", "!dir/foo.txt"], ["dir/", "!dir/foo.txt", "*.md"],
        ["# a comment", "", "  *.tmp  "], ["a/"], ["/a"], ["*", "!*.md"], ["docs/*"], ["/docs/sub/"],
    ]

    SAMPLE = [["*.tmp"], ["docs/", "!docs/keep.bin"], ["# a comment", "", "  *.tmp  "], ["*.tmp", "!docs/b.tmp"]]
    CASE_FILES = ["a.tmp", "B.TMP", "important.tmp", "Docs/a.md", "docs2/b.md", "README.md", "src/Main.py"]
    CASE_RULESETS = [["*.TMP"], ["*.tmp", "!Important.tmp"], ["DOCS/"], ["docs/"], ["readme.MD"], ["SRC/main.PY"], ["*", "!*.MD"]]

    def git(self, root, *args):
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, encoding="utf-8", errors="replace", env=env)

    def compare(self, content, files, fold=False):
        """Put this ignore file (bytes) and these files in a new repository and compare the list of Git with ours. Git's case setting is chosen, not left to the platform."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(0, self.git(root, "init", "-q").returncode)
            self.assertEqual(0, self.git(root, "config", "core.ignorecase", "true" if fold else "false").returncode)
            (root / ".gitignore").write_bytes(content)
            for rel in files:
                if "?" in rel and sys.platform == "win32":
                    continue
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x\n", encoding="utf-8")
            listed = self.git(root, "ls-files", "--others", "--exclude-standard", "-z")
            self.assertEqual(0, listed.returncode, listed.stderr)
            by_git = {p for p in listed.stdout.split("\0") if p and p != ".gitignore"}
            parsed = validate_docs.ignore_rules(root)
            mine = {rel for rel in files if (root / rel).exists() and not validate_docs.is_ignored(rel, parsed, fold=fold)}
            self.assertEqual(sorted(by_git), sorted(mine), "ignore file %r" % (content,))

    def test_every_rule_set_selects_the_files_that_git_would_add(self):
        for rules in self.RULESETS:
            with self.subTest(rules=rules):
                self.compare(("\n".join(rules) + "\n").encode("utf-8"), self.FILES)

    def test_the_line_endings_and_a_byte_order_mark_of_the_ignore_file_do_not_change_the_result(self):
        layouts = [
            ("CRLF", lambda text: text.replace("\n", "\r\n").encode("utf-8")),
            ("a byte-order mark", lambda text: b"\xef\xbb\xbf" + text.encode("utf-8")),
            ("a byte-order mark and CRLF", lambda text: b"\xef\xbb\xbf" + text.replace("\n", "\r\n").encode("utf-8")),
            ("no final newline", lambda text: text.rstrip("\n").encode("utf-8")),
        ]
        for name, layout in layouts:
            for rules in self.SAMPLE:
                with self.subTest(layout=name, rules=rules):
                    self.compare(layout("\n".join(rules) + "\n"), self.FILES)

    def test_git_skips_one_byte_order_mark_only(self):
        self.compare(b"\xef\xbb\xbf\xef\xbb\xbf*.tmp\n", self.FILES)

    def test_case_folding_follows_the_setting_of_git(self):
        for rules in self.CASE_RULESETS:
            for fold in (False, True):
                with self.subTest(rules=rules, fold=fold):
                    self.compare(("\n".join(rules) + "\n").encode("utf-8"), self.CASE_FILES, fold=fold)


if __name__ == "__main__":
    unittest.main()
