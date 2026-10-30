#!/usr/bin/env python3
"""Mutation tests for validate_docs.py.

Each test copies the project, injects one known defect and asserts that the
validator reports it. The unmodified copy must pass with no errors and no
warnings. Run from the project folder:

    python -m unittest discover -s scripts -p "test_*.py" -v
"""

import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

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
        text = change(raw.replace("\r\n", "\n"))
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
        self.edit(DESIGN, lambda t: t.replace('ISS["Issue form (intake)"]', "ISS[Issue form (intake)]", 1))
        self.assert_flagged(self.validate(), "mermaid")

    def test_mermaid_edge_to_undeclared_node(self):
        self.edit(DESIGN, lambda t: t.replace("SM --> VERIF\n", "SM --> VERIF\n  SM --> GHOST\n", 1))
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


if __name__ == "__main__":
    unittest.main()
