#!/usr/bin/env python3
"""Validate the Fabric Automation documentation set (standard library only).

Checks file hygiene, Markdown tables and fences, section numbering, the
definition and use of every identifier (FR-nn, D-nn, HR-n, S-n and so on),
requirement and decision coverage, the review disposition log and its counts,
links and paths, Mermaid diagrams, repeated numbers, and leaks of local paths,
addresses and secrets.

Exit status is 1 when an ERROR is found (or a WARN with --strict).
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

SKIP_DIRS = {"private", "__pycache__", ".pytest_cache", ".git"}
SKIP_PATHS = ("docs/research/local",)
TEXT_SUFFIXES = {".md", ".py", ".ps1", ".yml", ".yaml", ".json", ".txt"}
TEXT_NAMES = {".gitignore", ".gitattributes"}

BRIEF = "docs/00-brief.md"
REQ = "docs/01-requirements.md"
REG = "docs/02-decision-register.md"
DIG = "docs/03-landscape-research.md"
DES = "docs/04-design.md"
LOG = "docs/reviews/disposition-log.md"
REVIEWS = {
    "F": "docs/reviews/review-gemini.md",
    "AF": "docs/reviews/review-gpt.md",
    "X": "docs/reviews/review-grok.md",
    "O": "docs/reviews/review-orchestrator.md",
}
REQUIRED = [BRIEF, REQ, REG, DIG, DES, LOG, "README.md"] + list(REVIEWS.values())

# Documents whose identifiers are checked against the definitions.
REFERENCE_SCOPE = (REQ, REG, DES, LOG)
REFERENCE_GLOBS = ("docs/reviews/closure-*.md", "docs/reviews/review-*.md")

FAMILIES = {
    "FR": re.compile(r"\bFR-(\d{2})\b"),
    "NFR": re.compile(r"\bNFR-(\d{2})\b"),
    "PS": re.compile(r"\bPS-(\d)\b"),
    "HR": re.compile(r"\bHR-(\d{1,2})\b"),
    "D": re.compile(r"\bD-(\d{2})\b"),
    "RS": re.compile(r"\bRS-([A-C]\d?)\b"),
    "I": re.compile(r"\bI-(\d)\b"),
    "K": re.compile(r"\bK(\d{1,2})\b"),
    "C": re.compile(r"\bC(\d{1,2})\b"),
    "G": re.compile(r"\bG(\d{1,2})\b"),
    "S": re.compile(r"\bS(\d{1,2})\b"),
    "N": re.compile(r"\bN(\d{1,2})\b"),
    "R": re.compile(r"\bR(\d{1,2})\b"),
    "B": re.compile(r"\bB(\d)\b"),
    "A": re.compile(r"\bA(\d{1,2})\b"),
    "F": re.compile(r"\bF-(\d{2})\b"),
    "AF": re.compile(r"\bA-(\d{2})\b"),
    "X": re.compile(r"\bX-(\d{2})\b"),
    "O": re.compile(r"\bO-(\d{2})\b"),
}
PREFIX = {"FR": "FR-", "NFR": "NFR-", "PS": "PS-", "HR": "HR-", "D": "D-", "RS": "RS-",
          "I": "I-", "F": "F-", "AF": "A-", "X": "X-", "O": "O-"}
FINDING_FAMILIES = ("F", "AF", "X", "O")

DEFINITIONS = [
    ("FR", REQ, re.compile(r"^FR-(\d{2})$")),
    ("NFR", REQ, re.compile(r"^NFR-(\d{2})$")),
    ("PS", REQ, re.compile(r"^PS-(\d)$")),
    ("A", REQ, re.compile(r"^A(\d{1,2})$")),
    ("D", REG, re.compile(r"^D-(\d{2})$")),
    ("HR", DES, re.compile(r"^HR-(\d{1,2})$")),
    ("K", DES, re.compile(r"^K(\d{1,2})\b")),
    ("I", DES, re.compile(r"^I-(\d)$")),
    ("N", DES, re.compile(r"^N(\d{1,2})$")),
    ("B", DES, re.compile(r"^B(\d)$")),
    ("S", DES, re.compile(r"^S(\d{1,2})\b")),
    ("R", DES, re.compile(r"^R(\d{1,2})$")),
    ("RS", DES, re.compile(r"^RS-([A-C]\d?)\b")),
    ("G", DIG, re.compile(r"^G(\d{1,2})$")),
    ("F", REVIEWS["F"], re.compile(r"^F-(\d{2})$")),
    ("AF", REVIEWS["AF"], re.compile(r"^A-(\d{2})$")),
    ("X", REVIEWS["X"], re.compile(r"^X-(\d{2})$")),
    ("O", REVIEWS["O"], re.compile(r"^O-(\d{2})$")),
]

# Families that are reported when defined but never used; the others are listed in tables and need no cross-reference.
ORPHAN_WARN = ("HR", "S", "RS", "PS")

# Historical wording kept in the review and closure files, where the reviewers saw the earlier name.
LEGACY_TOKENS = {"RS": {"RS-C"}}

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
         "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20}

EMAIL_ALLOW = ("@users.noreply.github.com", "cursoragent@cursor.com")
# Patterns are assembled from pieces so that this file does not match its own scan.
LEAK_PATTERNS = [
    ("user-path", re.compile(
        r"(?:[A-Za-z]:" + r"\\" + r"Users" + r"\\[^\\\s]+|/Users/[a-z][^/\s]*/|/home/[a-z][^/\s]*/|"
        + r"\\" + r"AppData" + r"\\|" + "OneDrive" + r" - )")),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")),
    ("guid", re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")),
    ("jwt", re.compile(r"\bey" + r"J[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AK" + r"IA[0-9A-Z]{16})\b")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*(?:PRIVATE KEY|CERTIFICATE)")),
    ("secret-assignment", re.compile(
        r"(?i)\b(?:client_?secret|password|passwd|pwd|api_?key|access_?key|account_?key|sharedaccesskey|sas_?token)"
        r"\b\s*[:=]\s*[\"']?[A-Za-z0-9/+_~.-]{12,}")),
    ("internal-host", re.compile(
        r"(?i)(?:pkgs\.visual" + r"studio\.com|\.share" + r"point\.com|onmicro" + r"soft\.com|corp\.micro" + r"soft\.com|\.msft\.net|\beng\.ms\b)")),
    ("ipv4", re.compile(r"\b(?!127\.0\.0\.1\b|0\.0\.0\.0\b)(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")),
    ("local-tool-path", re.compile(r"~[\\/]\." + r"copilot[\\/]")),
]
MOJIBAKE = re.compile("\u00e2\u20ac|\u00c3[\u0080-\u00bf]|\u00c2[\u0080-\u00bf]|\ufffd")
PLACEHOLDER = re.compile(r"\b(?:TODO|TBD|FIXME|XXX)\b|<<<<<<<|>>>>>>>")


class Report:
    def __init__(self):
        self.findings = []
        self.ran = []

    def add(self, level, check, rel, line, message):
        self.findings.append((level, check, rel, line, message))

    def error(self, check, rel, line, message):
        self.add("ERROR", check, rel, line, message)

    def warn(self, check, rel, line, message):
        self.add("WARN", check, rel, line, message)

    def note(self, check, detail):
        self.ran.append((check, detail))

    def count(self, level):
        return sum(1 for f in self.findings if f[0] == level)

    def has(self, level, check):
        return any(f[0] == level and f[1] == check for f in self.findings)

    def render(self, quiet=False):
        out = []
        for level, check, rel, line, message in self.findings:
            where = rel + (":%d" % line if line else "")
            out.append("[%s] %s %s: %s" % (level, check, where, message))
        if not quiet:
            out.append("")
            out.append("Checks run:")
            for check, detail in self.ran:
                out.append("  - %s: %s" % (check, detail))
        out.append("")
        out.append("Result: %d error(s), %d warning(s)" % (self.count("ERROR"), self.count("WARN")))
        return "\n".join(out)


def fence_mask(lines):
    mask, inside, marker = [], False, ""
    for line in lines:
        m = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if m:
            fence = m.group(1)
            if not inside:
                inside, marker = True, fence[0] * 3
                mask.append(True)
                continue
            if fence.startswith(marker):
                mask.append(True)
                inside = False
                continue
        mask.append(inside)
    return mask, inside


class Doc:
    def __init__(self, root, path):
        self.path = path
        self.rel = path.relative_to(root).as_posix()
        self.raw = path.read_bytes()
        text = self.raw.decode("utf-8", errors="replace")
        self.crlf = text.count("\r\n")
        self.lone_cr = text.count("\r") - self.crlf
        self.lf = text.count("\n") - self.crlf
        self.text = text.replace("\r\n", "\n")
        self.lines = self.text.split("\n")
        if self.lines and self.lines[-1] == "":
            self.lines.pop()
        self.is_markdown = path.suffix == ".md"
        if self.is_markdown:
            self.mask, self.unclosed = fence_mask(self.lines)
        else:
            self.mask, self.unclosed = [False] * len(self.lines), False
        self._tables = None

    @property
    def tables(self):
        if self._tables is None:
            self._tables = find_tables(self)
        return self._tables

    def prose(self):
        for i, line in enumerate(self.lines):
            if not self.mask[i]:
                yield i + 1, line


DELIM_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


def split_cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", s)]


class Table:
    def __init__(self, start, header, delim, rows):
        self.start = start
        self.header = header
        self.delim = delim
        self.rows = rows


def find_tables(doc):
    tables, i, n = [], 0, len(doc.lines)
    while i < n:
        line = doc.lines[i]
        if (not doc.mask[i] and line.lstrip().startswith("|") and i + 1 < n
                and not doc.mask[i + 1] and DELIM_RE.match(doc.lines[i + 1])):
            header = split_cells(line)
            delim = split_cells(doc.lines[i + 1])
            rows, j = [], i + 2
            while j < n and not doc.mask[j] and doc.lines[j].lstrip().startswith("|"):
                rows.append((j + 1, split_cells(doc.lines[j])))
                j += 1
            tables.append(Table(i + 1, header, delim, rows))
            i = j
        else:
            i += 1
    return tables


def plain(cell):
    return re.sub(r"[`*]", "", cell).strip()


def headings(doc):
    out = []
    for i, line in enumerate(doc.lines):
        if doc.mask[i]:
            continue
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if m:
            out.append((len(m.group(1)), m.group(2), i + 1))
    return out


def slug(text):
    t = re.sub(r"[`*~]", "", text.strip().lower())
    t = re.sub(r"[^\w\- ]", "", t)
    return t.replace(" ", "-")


def anchors(doc):
    seen, out = {}, set()
    for _level, text, _line in headings(doc):
        s = slug(text)
        count = seen.get(s, 0)
        out.add(s if count == 0 else "%s-%d" % (s, count))
        seen[s] = count + 1
    return out


class Context:
    def __init__(self, root, report, denylist=None):
        self.root = root
        self.report = report
        self.denylist = denylist or []
        self.docs = {}
        self.sections = set()
        self.defs = {fam: set() for fam in FAMILIES}
        self.defs["NP"] = set()
        self.defs["GN"] = set()
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            rel = relative.as_posix()
            if any(part in SKIP_DIRS for part in relative.parts[:-1]):
                continue
            if any(rel == p or rel.startswith(p + "/") for p in SKIP_PATHS):
                continue
            if path.suffix in TEXT_SUFFIXES or path.name in TEXT_NAMES:
                self.docs[rel] = Doc(root, path)

    def get(self, rel):
        return self.docs.get(rel)

    def markdown(self):
        return [d for d in self.docs.values() if d.is_markdown]

    def matching(self, pattern):
        return [d for rel, d in sorted(self.docs.items()) if Path(rel).match(pattern)]

    def findings_defined(self):
        out = set()
        for fam in FINDING_FAMILIES:
            out |= self.defs[fam]
        return out


def token(fam, group):
    return PREFIX.get(fam, fam) + group


def sort_key(tok):
    m = re.search(r"(\d+)", tok)
    return (re.sub(r"\d+", "", tok), int(m.group(1)) if m else 0)


def check_required(ctx):
    missing = [rel for rel in REQUIRED if rel not in ctx.docs]
    for rel in missing:
        ctx.report.error("required-file", rel, 0, "file is missing")
    ctx.report.note("required-file", "%d required files, %d missing" % (len(REQUIRED), len(missing)))


def check_hygiene(ctx):
    crlf_only = 0
    for doc in ctx.docs.values():
        if doc.raw.startswith(b"\xef\xbb\xbf"):
            ctx.report.warn("hygiene", doc.rel, 1, "file starts with a byte-order mark")
        if b"\x00" in doc.raw:
            ctx.report.error("hygiene", doc.rel, 0, "file contains NUL bytes")
        if doc.lone_cr:
            ctx.report.error("hygiene", doc.rel, 0, "file contains lone carriage returns")
        if doc.crlf and doc.lf:
            ctx.report.error("hygiene", doc.rel, 0, "mixed line endings (%d CRLF, %d LF)" % (doc.crlf, doc.lf))
        elif doc.crlf:
            crlf_only += 1
        if doc.raw and not doc.raw.endswith(b"\n"):
            ctx.report.error("hygiene", doc.rel, len(doc.lines), "file does not end with a newline")
        if len(doc.raw) > 500 * 1024 and doc.is_markdown:
            ctx.report.warn("hygiene", doc.rel, 0, "file is over 500 KB, GitHub may not render it")
        for i, line in enumerate(doc.lines, 1):
            if MOJIBAKE.search(line):
                ctx.report.error("mojibake", doc.rel, i, "garbled text (encoding damage)")
    ctx.report.note("hygiene", "%d text files, %d with CRLF endings (git stores them as LF)" % (len(ctx.docs), crlf_only))


def check_markdown(ctx):
    tables = rows = fences = 0
    for doc in ctx.markdown():
        if doc.unclosed:
            ctx.report.error("fence", doc.rel, len(doc.lines), "code fence is never closed")
        fences += sum(1 for i, line in enumerate(doc.lines)
                      if doc.mask[i] and re.match(r"^\s{0,3}(`{3,}|~{3,})", line))
        for table in doc.tables:
            tables += 1
            width = len(table.header)
            if len(table.delim) != width:
                ctx.report.error("table", doc.rel, table.start + 1,
                                 "delimiter row has %d cells, header has %d" % (len(table.delim), width))
            for line, cells in table.rows:
                rows += 1
                if len(cells) != width:
                    ctx.report.error("table", doc.rel, line,
                                     "row has %d cells, header has %d (an unescaped | inside a cell?)" % (len(cells), width))
    for rel in (BRIEF, REQ, REG, DES, LOG):
        doc = ctx.get(rel)
        if not doc:
            continue
        for line, text in doc.prose():
            found = PLACEHOLDER.search(text)
            if found:
                ctx.report.error("placeholder", rel, line, "unfinished marker: " + found.group(0))
    des = ctx.get(DES)
    if des and (not des.lines or des.lines[-1].strip() != "<!-- END -->"):
        ctx.report.error("sentinel", DES, len(des.lines), "design must end with the <!-- END --> marker")
    ctx.report.note("markdown", "%d tables, %d rows, %d fence lines" % (tables, rows, fences))


def check_headings(ctx):
    des = ctx.get(DES)
    if not des:
        return
    tops, subs = [], {}
    for level, text, line in headings(des):
        m = re.match(r"^(\d+)\.\s", text)
        if level == 2 and m:
            tops.append((int(m.group(1)), line))
            continue
        m = re.match(r"^(\d+)\.(\d+)\s", text)
        if level == 3 and m:
            subs.setdefault(int(m.group(1)), []).append((int(m.group(2)), line))
    nums = [n for n, _ in tops]
    if nums != list(range(1, len(nums) + 1)):
        ctx.report.error("headings", DES, 0, "top-level sections are not numbered 1..n in order: %s" % nums)
    for top, items in subs.items():
        got = [n for n, _ in items]
        if got != list(range(1, len(got) + 1)):
            ctx.report.error("headings", DES, items[0][1], "subsections of %d are not contiguous: %s" % (top, got))
    ctx.sections = {str(n) for n in nums} | {"%d.%d" % (t, n) for t, items in subs.items() for n, _ in items}
    ctx.report.note("headings", "%d sections, %d subsections" % (len(nums), sum(len(v) for v in subs.values())))


def check_versions(ctx):
    version = {}
    for rel in (REQ, REG, DES, DIG, BRIEF):
        doc = ctx.get(rel)
        if not doc:
            continue
        found = None
        for line in doc.lines[:6]:
            found = re.match(r"^Version (\d+\.\d+)\b", line)
            if found:
                break
        if found:
            version[rel] = found.group(1)
        else:
            ctx.report.error("version", rel, 3, "no 'Version x.y' header line in the first lines")
    pairs = [(DES, r"requirements v(\d+\.\d+)", REQ), (DES, r"decision register v(\d+\.\d+)", REG),
             (REG, r"design v(\d+\.\d+)", DES)]
    for rel, pattern, target in pairs:
        doc = ctx.get(rel)
        if not doc or target not in version:
            continue
        m = re.search(pattern, "\n".join(doc.lines[:12]))
        if not m:
            ctx.report.warn("version", rel, 3, "header does not state the version of %s" % target)
        elif m.group(1) != version[target]:
            ctx.report.error("version", rel, 3, "header cites %s v%s but that file is v%s" % (target, m.group(1), version[target]))
    ctx.report.note("version", ", ".join("%s v%s" % (Path(k).name, v) for k, v in version.items()))


def build_definitions(ctx):
    for fam, rel, pattern in DEFINITIONS:
        doc = ctx.get(rel)
        if not doc:
            continue
        for table in doc.tables:
            for _line, cells in table.rows:
                m = pattern.match(plain(cells[0])) if cells else None
                if m:
                    ctx.defs[fam].add(token(fam, m.group(1)))
    dig = ctx.get(DIG)
    if dig:
        for _line, text in dig.prose():
            m = re.match(r"^- \*\*C(\d{1,2})\*\*", text)
            if m:
                ctx.defs["C"].add("C" + m.group(1))
    for rel, fam in (("docs/reviews/closure-gemini.md", "NP"), ("docs/reviews/closure-gpt.md", "GN")):
        doc = ctx.get(rel)
        if doc:
            for table in doc.tables:
                for _line, cells in table.rows:
                    if cells and re.match(r"^%s-\d$" % fam, plain(cells[0])):
                        ctx.defs[fam].add(plain(cells[0]))
    ctx.report.note("definitions", ", ".join("%s=%d" % (f, len(s)) for f, s in ctx.defs.items() if s))


def reference_docs(ctx):
    docs = [ctx.get(rel) for rel in REFERENCE_SCOPE if ctx.get(rel)]
    for pattern in REFERENCE_GLOBS:
        docs.extend(ctx.matching(pattern))
    seen, out = set(), []
    for d in docs:
        if d.rel not in seen:
            seen.add(d.rel)
            out.append(d)
    return out


def check_references(ctx):
    occurrences = Counter()
    undefined = 0
    docs = reference_docs(ctx)
    for doc in docs:
        for line, text in doc.prose():
            for fam, pattern in FAMILIES.items():
                for m in pattern.finditer(text):
                    tok = token(fam, m.group(1))
                    occurrences[tok] += 1
                    if ctx.defs[fam] and tok not in ctx.defs[fam]:
                        if doc.rel.startswith("docs/reviews/") and tok in LEGACY_TOKENS.get(fam, ()):
                            continue
                        undefined += 1
                        ctx.report.error("id-undefined", doc.rel, line, "%s is not defined" % tok)
    dig = ctx.get(DIG)
    if dig:
        for line, text in dig.prose():
            for fam in ("C", "G"):
                for m in FAMILIES[fam].finditer(text):
                    tok = token(fam, m.group(1))
                    if ctx.defs[fam] and tok not in ctx.defs[fam]:
                        undefined += 1
                        ctx.report.error("id-undefined", DIG, line, "%s is not defined" % tok)
    for fam in ORPHAN_WARN:
        for tok in sorted(ctx.defs[fam], key=sort_key):
            if occurrences[tok] <= 1:
                ctx.report.warn("id-orphan", REQ if fam in ("PS", "A") else DES, 0, "%s is defined but never referenced" % tok)
    range_re = re.compile(r"\b(FR-|NFR-|HR-|PS-|D-|I-|[KCGSNRBA])(\d+)\s+to\s+\1(\d+)\b")
    prefix_family = {"FR-": "FR", "NFR-": "NFR", "HR-": "HR", "PS-": "PS", "D-": "D", "I-": "I"}
    for doc in docs + ([dig] if dig else []):
        for line, text in doc.prose():
            for m in range_re.finditer(text):
                fam = prefix_family.get(m.group(1), m.group(1))
                if fam not in ctx.defs or not ctx.defs[fam]:
                    continue
                width = 2 if fam in ("FR", "NFR", "D") else 0
                lo, hi = int(m.group(2)), int(m.group(3))
                for n in (lo, hi):
                    tok = token(fam, str(n).zfill(width) if width else str(n))
                    if tok not in ctx.defs[fam]:
                        ctx.report.error("id-range", doc.rel, line, "range '%s' ends at %s, which is not defined" % (m.group(0), tok))
                if lo > hi:
                    ctx.report.error("id-range", doc.rel, line, "range '%s' runs backwards" % m.group(0))
    ctx.report.note("references", "%d reference(s) to an undefined identifier" % undefined)


def table_after_heading(doc, start_pattern, end_pattern=None):
    start = end = None
    for _level, text, line in headings(doc):
        if start is None:
            if re.match(start_pattern, text):
                start = line
        elif end is None and (end_pattern is None or re.match(end_pattern, text)):
            end = line
    if start is None:
        return None
    for table in doc.tables:
        if table.start > start and (end is None or table.start < end):
            return table
    return None


def expand_requirement_ids(text):
    out = set()
    for m in re.finditer(r"\b(NFR|FR)-(\d+)\s+to\s+\1-(\d+)\b", text):
        for n in range(int(m.group(2)), int(m.group(3)) + 1):
            out.add("%s-%02d" % (m.group(1), n))
    for m in re.finditer(r"\b(NFR|FR)-(\d+)\b", text):
        out.add("%s-%02d" % (m.group(1), int(m.group(2))))
    return out


def check_coverage(ctx):
    des = ctx.get(DES)
    if not des:
        return
    requirements = ctx.defs["FR"] | ctx.defs["NFR"]
    trace = table_after_heading(des, r"8\.\s", r"9\.\s")
    covered = set()
    if trace is None:
        ctx.report.error("traceability", DES, 0, "section 8 table not found")
    else:
        for _line, cells in trace.rows:
            covered |= expand_requirement_ids(cells[0])
        for tok in sorted(requirements - covered, key=sort_key):
            ctx.report.error("traceability", DES, trace.start, "%s is not covered by the section 8 traceability table" % tok)
        for tok in sorted(covered - requirements, key=sort_key):
            ctx.report.error("traceability", DES, trace.start, "%s is traced but not defined in the requirements" % tok)
    ctx.report.note("traceability", "%d of %d requirements covered" % (len(covered & requirements), len(requirements)))
    status = table_after_heading(des, r"6\.\s", r"7\.\s")
    in_design = set()
    if status is None:
        ctx.report.error("decisions", DES, 0, "section 6 table not found")
    else:
        for _line, cells in status.rows:
            m = re.match(r"^D-(\d{2})$", plain(cells[0]))
            if m:
                in_design.add("D-" + m.group(1))
        for tok in sorted(ctx.defs["D"] - in_design, key=sort_key):
            ctx.report.error("decisions", DES, status.start, "%s is in the register but not in design section 6" % tok)
        for tok in sorted(in_design - ctx.defs["D"], key=sort_key):
            ctx.report.error("decisions", DES, status.start, "%s is in design section 6 but not in the register" % tok)
    numbers = sorted(int(t[2:]) for t in ctx.defs["D"])
    if numbers and numbers != list(range(1, numbers[-1] + 1)):
        ctx.report.error("decisions", REG, 0, "decision numbers are not contiguous from D-01")
    for rel in (REG, DES):
        doc = ctx.get(rel)
        if not doc:
            continue
        for table in doc.tables:
            col = next((i for i, h in enumerate(table.header) if h.lower().startswith("closed by")), None)
            if col is None:
                continue
            for line, cells in table.rows:
                for m in re.finditer(r"\bS(\d{1,2})\b", cells[col] if col < len(cells) else ""):
                    if "S" + m.group(1) not in ctx.defs["S"]:
                        ctx.report.error("decisions", rel, line, "'Closed by' cites S%s, which is not a defined spike" % m.group(1))
    ctx.report.note("decisions", "%d in register, %d in design" % (len(ctx.defs["D"]), len(in_design)))


def categorize(decision):
    d = decision.lower()
    if d.startswith("merged"):
        return "merged"
    if "modified" in d:
        return "modified"
    if "phased" in d:
        return "phased"
    return "accepted"


def lead_int(cell):
    m = re.match(r"^\**(\d+)", plain(cell))
    return int(m.group(1)) if m else None


CATEGORIES = ("accepted", "modified", "phased", "merged")


def read_decisions(ctx, log):
    findings = ctx.findings_defined()
    decisions = {}
    for table in log.tables:
        header = [h.lower() for h in table.header]
        if header[:3] != ["id", "sev", "decision"]:
            continue
        last = len(header) - 1
        for line, cells in table.rows:
            fid = plain(cells[0])
            if not re.match(r"^[FAXO]-\d{2}$", fid):
                continue
            if fid in decisions:
                ctx.report.error("disposition", LOG, line, "%s has more than one row" % fid)
            decisions[fid] = categorize(cells[2])
            if cells[2].lower().startswith("merged"):
                for m in re.finditer(r"\b[FAXO]-\d{2}\b", cells[2]):
                    if m.group(0) not in findings:
                        ctx.report.error("disposition", LOG, line, "%s merges with %s, which is not a finding" % (fid, m.group(0)))
            if ctx.sections and last < len(cells):
                for part in re.sub(r"\([^)]*\)", "", cells[last]).split(","):
                    part = part.strip()
                    if re.fullmatch(r"\d+(?:\.\d+)?", part) and part not in ctx.sections:
                        ctx.report.error("section-ref", LOG, line, "%s cites design section %s, which does not exist" % (fid, part))
    return decisions


def read_closure(ctx):
    closure = {}
    for rel, name in (("docs/reviews/closure-gemini.md", "Gemini"), ("docs/reviews/closure-gpt.md", "GPT"),
                      ("docs/reviews/closure-grok.md", "Grok")):
        doc = ctx.get(rel)
        if not doc:
            continue
        own = closed = partly = opened = new = 0
        for table in doc.tables:
            header = [h.lower() for h in table.header]
            if "verdict" in header:
                col = header.index("verdict")
                for _line, cells in table.rows:
                    verdict = plain(cells[col]).upper()
                    if re.match(r"^(CLOSED|PARTLY|OPEN)\b", verdict):
                        own += 1
                        closed += 1 if verdict.startswith("CLOSED") else 0
                        partly += 1 if verdict.startswith("PARTLY") else 0
                        opened += 1 if verdict.startswith("OPEN") else 0
            if "problem" in header and "disposition" in header:
                new = len(table.rows)
        closure[name] = [own, closed, partly, opened, new]
    return closure


def check_disposition(ctx):
    log = ctx.get(LOG)
    if not log:
        return
    decisions = read_decisions(ctx, log)
    findings = ctx.findings_defined()
    for fid in sorted(findings - set(decisions), key=sort_key):
        ctx.report.error("disposition", LOG, 0, "%s has no disposition row" % fid)
    for fid in sorted(set(decisions) - findings, key=sort_key):
        ctx.report.error("disposition", LOG, 0, "%s has a row but no review finding defines it" % fid)
    per_source = {"F": Counter(), "A": Counter(), "X": Counter(), "O": Counter()}
    total = Counter()
    for fid, cat in decisions.items():
        per_source[fid[0]][cat] += 1
        total[cat] += 1
    summary = next((t for t in log.tables if [h.lower() for h in t.header[:2]] == ["source", "findings"]), None)
    if summary is None:
        ctx.report.error("disposition", LOG, 0, "summary table not found")
    else:
        for line, cells in summary.rows:
            name = plain(cells[0])
            m = re.search(r"\((F|A|X|O)\)", name)
            counts = total if name.lower() == "total" else (per_source.get(m.group(1)) if m else None)
            if counts is None:
                continue
            stated = [lead_int(c) for c in cells[1:6]]
            actual = [sum(counts.values())] + [counts[c] for c in CATEGORIES]
            if stated != actual:
                ctx.report.error("disposition-summary", LOG, line,
                                 "%s row states %s but the rows add up to %s (findings, accepted, modified, phased, merged)" % (name, stated, actual))
    brief = ctx.get(BRIEF)
    if brief:
        for line, text in brief.prose():
            m = re.search(r"\((\d+) accepted, (\d+) modified, (\d+) phased, (\d+) merged, (\d+) rejected\)", text)
            if m:
                stated = [int(g) for g in m.groups()]
                actual = [total[c] for c in CATEGORIES] + [0]
                if stated != actual:
                    ctx.report.error("disposition-summary", BRIEF, line, "brief states %s but the log adds up to %s" % (stated, actual))
    closure = read_closure(ctx)
    for table in log.tables:
        if table.header and table.header[0].lower() == "reviewer":
            for line, cells in table.rows:
                name = plain(cells[0])
                if name in closure:
                    stated = [lead_int(c) for c in cells[1:6]]
                    if stated != closure[name]:
                        ctx.report.error("closure-summary", LOG, line,
                                         "%s row states %s but the closure file counts %s (own, closed, partly, open, new)" % (name, stated, closure[name]))
    ctx.report.note("disposition", "%d findings, %s" % (len(decisions), ", ".join("%s=%d" % (c, total[c]) for c in CATEGORIES)))


def check_counts(ctx):
    des = ctx.get(DES)
    if not des:
        return
    problems = 0
    spikes = len(ctx.defs["S"])
    for line, text in des.prose():
        for m in re.finditer(r"\b([A-Za-z]+)\s+(?:Phase 0\s+)?spikes\b", text):
            word = m.group(1).lower()
            if word in WORDS and WORDS[word] != spikes:
                problems += 1
                ctx.report.error("count-claim", DES, line, "text says %s spikes but %d are defined" % (word, spikes))
    scenarios = table_after_heading(des, r"9\.\s", r"10\.\s")
    for _level, text, line in headings(des):
        m = re.search(r"the (\w+) scenarios", text)
        if m and scenarios is not None and m.group(1).lower() in WORDS and WORDS[m.group(1).lower()] != len(scenarios.rows):
            problems += 1
            ctx.report.error("count-claim", DES, line, "heading says %s scenarios but the table has %d" % (m.group(1), len(scenarios.rows)))
    for rel in (DES, REG):
        doc = ctx.get(rel)
        if not doc:
            continue
        for line, text in doc.prose():
            for m in re.finditer(r"\b(\w+)\s+rulesets\b", text):
                word = m.group(1).lower()
                if word in WORDS and WORDS[word] != len(ctx.defs["RS"]):
                    problems += 1
                    ctx.report.error("count-claim", rel, line, "text says %s rulesets but %d are defined" % (word, len(ctx.defs["RS"])))
    total = len(ctx.findings_defined())
    for rel in (DES, REQ, BRIEF):
        doc = ctx.get(rel)
        if not doc:
            continue
        for line, text in doc.prose():
            for m in re.finditer(r"\b(\d+) findings\b", text):
                if int(m.group(1)) != total:
                    problems += 1
                    ctx.report.error("count-claim", rel, line, "text says %s findings but %d are defined" % (m.group(1), total))
    brief = ctx.get(BRIEF)
    if brief:
        current = re.search(r"decision register v(\d+\.\d+)", "\n".join(ctx.get(DES).lines[:12]) if ctx.get(DES) else "")
        for line, text in brief.prose():
            for m in re.finditer(r"decision register v(\d+\.\d+) \((\d+) decisions\)", text, re.IGNORECASE):
                if current and m.group(1) == current.group(1) and int(m.group(2)) != len(ctx.defs["D"]):
                    problems += 1
                    ctx.report.error("count-claim", BRIEF, line, "brief says %s decisions for v%s but %d are defined" % (m.group(2), m.group(1), len(ctx.defs["D"])))
    ctx.report.note("count-claims", "%d mismatch(es) (spikes %d, findings %d)" % (problems, spikes, total))


def check_section_refs(ctx):
    checked = 0
    if not ctx.sections:
        return
    for rel in (REQ, REG, DES, LOG):
        doc = ctx.get(rel)
        if not doc:
            continue
        for line, text in doc.prose():
            for m in re.finditer(r"\(((?:\d{1,2}\.\d{1,2})(?:\s*(?:,|and|to)\s*\d{1,2}\.\d{1,2})*)\)", text):
                for sec in re.findall(r"\d{1,2}\.\d{1,2}", m.group(1)):
                    checked += 1
                    if sec not in ctx.sections:
                        ctx.report.error("section-ref", rel, line, "cites section %s, which does not exist in the design" % sec)
    des = ctx.get(DES)
    trace = table_after_heading(des, r"8\.\s", r"9\.\s") if des else None
    if trace is not None:
        for line, cells in trace.rows:
            if len(cells) > 1:
                for part in re.sub(r"\([^)]*\)", "", cells[1]).split(","):
                    part = part.strip()
                    if re.fullmatch(r"\d+(?:\.\d+)?", part):
                        checked += 1
                        if part not in ctx.sections:
                            ctx.report.error("section-ref", DES, line, "traceability cites section %s, which does not exist" % part)
    ctx.report.note("section-refs", "%d parenthetical or table reference(s)" % checked)


LINK_RE = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
PATH_TOKEN_RE = re.compile(
    r"`((?:docs/)?(?:reviews|archive|research|scripts|ci)/[^`\s<>*{}]+|\d\d-[a-z-]+\.md|(?:closure|review|disposition|xv)-[a-z-]+\.md)`")


def resolve(ctx, doc, target):
    for base in (doc.path.parent, ctx.root / "docs", ctx.root):
        candidate = (base / target).resolve()
        if candidate.exists():
            return candidate
    return None


def check_links(ctx):
    links = paths = 0
    root = ctx.root.resolve()
    for doc in ctx.markdown():
        own_anchors = None
        for line, text in doc.prose():
            for m in LINK_RE.finditer(text):
                target = m.group(1)
                if re.match(r"^(https?:|mailto:)", target):
                    continue
                links += 1
                file_part, _, frag = target.partition("#")
                if not file_part:
                    own_anchors = own_anchors or anchors(doc)
                    if frag and frag not in own_anchors:
                        ctx.report.error("link", doc.rel, line, "anchor #%s does not exist in this file" % frag)
                    continue
                found = (doc.path.parent / file_part).resolve()
                if not found.exists():
                    ctx.report.error("link", doc.rel, line, "link target %s does not exist" % file_part)
                elif frag and found.suffix == ".md" and found.is_file():
                    try:
                        other = ctx.docs.get(found.relative_to(root).as_posix())
                    except ValueError:
                        other = None
                    if other is not None and frag not in anchors(other):
                        ctx.report.error("link", doc.rel, line, "anchor #%s does not exist in %s" % (frag, file_part))
            for m in PATH_TOKEN_RE.finditer(text):
                paths += 1
                rel = m.group(1)
                if "research/local" in rel:
                    ctx.report.error("path-ref", doc.rel, line, "`%s` points at unpublished local-only material" % rel)
                elif resolve(ctx, doc, rel) is None:
                    ctx.report.error("path-ref", doc.rel, line, "`%s` does not exist" % rel)
    ctx.report.note("links", "%d link(s), %d file reference(s)" % (links, paths))


def mermaid_body(body):
    for idx, (_line, text) in enumerate(body):
        if text.strip():
            return body[idx + 1:]
    return []


def lint_flowchart(ctx, doc, body):
    declared, subgraphs, refs, stack = set(), set(), [], []
    arrow = re.compile(r"\s*(?:<-->|-->|---|-\.->|-\.-|==>)\s*(?:\|[^|]*\|\s*)?")
    for lineno, raw in mermaid_body(body):
        line = raw.strip()
        if not line or line.startswith("%%"):
            continue
        if line.count('"') % 2:
            ctx.report.error("mermaid", doc.rel, lineno, "unbalanced double quote")
        m = re.match(r"^subgraph\s+([A-Za-z_]\w*)", line)
        if m:
            subgraphs.add(m.group(1))
            stack.append(lineno)
            continue
        if line == "end":
            if not stack:
                ctx.report.error("mermaid", doc.rel, lineno, "'end' without a subgraph")
            else:
                stack.pop()
            continue
        if re.match(r"^(classDef|class|style|linkStyle|click|direction)\b", line):
            continue
        for m in re.finditer(r"\b([A-Za-z_]\w*)\[([^\]]*)\]", line):
            declared.add(m.group(1))
            label = m.group(2)
            quoted = len(label) >= 2 and label.startswith('"') and label.endswith('"')
            if not quoted and re.search(r"[()\[\]{}\"]", label):
                ctx.report.error("mermaid", doc.rel, lineno, "label of %s needs quotes because it contains brackets or quotes" % m.group(1))
        if arrow.search(line):
            for part in (p.strip() for p in arrow.split(line)):
                m = re.match(r"^([A-Za-z_]\w*)(\[.*\])?$", part)
                if not m:
                    ctx.report.error("mermaid", doc.rel, lineno, "cannot read edge endpoint '%s'" % part)
                else:
                    refs.append((m.group(1), lineno))
        elif not re.match(r"^[A-Za-z_]\w*\s*\[", line):
            ctx.report.error("mermaid", doc.rel, lineno, "unrecognised flowchart line")
    for ident, lineno in refs:
        if ident not in declared and ident not in subgraphs:
            ctx.report.error("mermaid", doc.rel, lineno, "edge uses %s, which is never declared" % ident)
    for lineno in stack:
        ctx.report.error("mermaid", doc.rel, lineno, "subgraph is never closed with 'end'")


def lint_state(ctx, doc, start, body):
    transition = re.compile(r"^(\[\*\]|[A-Za-z_]\w*)\s*-->\s*(\[\*\]|[A-Za-z_]\w*)\s*(?::\s*(.*))?$")
    has_start = False
    for lineno, raw in mermaid_body(body):
        line = raw.strip()
        if not line or line.startswith("%%"):
            continue
        m = transition.match(line)
        if not m:
            if not re.match(r"^(state|note|direction|\}|\{)\b", line):
                ctx.report.error("mermaid", doc.rel, lineno, "unrecognised state diagram line: %s" % line[:60])
            continue
        has_start = has_start or m.group(1) == "[*]"
        if m.group(3) and ";" in m.group(3):
            ctx.report.warn("mermaid", doc.rel, lineno, "a semicolon in a transition label can break the parser")
    if not has_start:
        ctx.report.error("mermaid", doc.rel, start, "state diagram has no [*] start transition")


def check_mermaid(ctx):
    blocks = 0
    opening = re.compile(r"^\s{0,3}`{3,}\s*mermaid\b")
    closing = re.compile(r"^\s{0,3}`{3,}\s*$")
    for doc in ctx.markdown():
        i = 0
        while i < len(doc.lines):
            if opening.match(doc.lines[i]):
                body, j = [], i + 1
                while j < len(doc.lines) and not closing.match(doc.lines[j]):
                    body.append((j + 1, doc.lines[j]))
                    j += 1
                if j >= len(doc.lines):
                    ctx.report.error("mermaid", doc.rel, i + 1, "mermaid block is never closed")
                first = next((b[1].strip() for b in body if b[1].strip()), "")
                blocks += 1
                if first.startswith(("flowchart", "graph")):
                    lint_flowchart(ctx, doc, body)
                elif first.startswith("stateDiagram"):
                    lint_state(ctx, doc, i + 1, body)
                else:
                    ctx.report.warn("mermaid", doc.rel, i + 1, "diagram type is not linted: %s" % first[:30])
                i = j
            i += 1
    ctx.report.note("mermaid", "%d diagram(s)" % blocks)


def scan_lines(ctx, rel, lines, deny):
    hits = 0
    for i, line in enumerate(lines, 1):
        for name, pattern in LEAK_PATTERNS:
            for m in pattern.finditer(line):
                value = m.group(0)
                if name == "email" and any(value.endswith(a) for a in EMAIL_ALLOW):
                    continue
                hits += 1
                ctx.report.error("leak", rel, i, "%s pattern found (%d characters)" % (name, len(value)))
        low = line.lower()
        for term in deny:
            if term.lower() in low:
                hits += 1
                ctx.report.error("leak-denylist", rel, i, "a private denylist term appears here")
    return hits


def check_leaks(ctx, extra_files=()):
    hits = 0
    deny = [t for t in ctx.denylist if t]
    for doc in ctx.docs.values():
        hits += scan_lines(ctx, doc.rel, doc.lines, deny)
        for term in deny:
            if term.lower() in doc.rel.lower():
                ctx.report.error("leak-denylist", doc.rel, 0, "a private denylist term appears in the file name")
    for path in extra_files:
        label = "%s (outside the project)" % Path(path).name
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            ctx.report.error("leak", label, 0, "cannot read the file (%s)" % type(exc).__name__)
            continue
        hits += scan_lines(ctx, label, text.splitlines(), deny)
    ctx.report.note("leaks", "%d hit(s), %d private term(s) checked, %d extra file(s)" % (hits, len(deny), len(list(extra_files))))


URL_RE = re.compile(r"https?://[^\s<>()\[\]`\"']+")


def check_urls(ctx, include_raw=False):
    urls = {}
    for doc in ctx.markdown():
        if "/research/raw/" in "/" + doc.rel and not include_raw:
            continue
        for i, line in enumerate(doc.lines, 1):
            for m in URL_RE.finditer(line):
                urls.setdefault(m.group(0).rstrip(".,;:!?*"), (doc.rel, i))
    bad = blocked = 0
    for url, (rel, line) in sorted(urls.items()):
        status = None
        for method in ("HEAD", "GET"):
            try:
                req = urlrequest.Request(url, method=method, headers={"User-Agent": "fabric-automation-validator"})
                with urlrequest.urlopen(req, timeout=20) as resp:
                    status = resp.status
                break
            except urlerror.HTTPError as exc:
                status = exc.code
                if exc.code not in (400, 403, 405, 429):
                    break
            except Exception as exc:  # network failure
                status = str(exc)[:60]
        time.sleep(0.2)
        if isinstance(status, int) and 200 <= status < 400:
            continue
        if status in (403, 429, 999):
            blocked += 1
            ctx.report.warn("url", rel, line, "%s answered %s (blocks automated requests)" % (url, status))
        else:
            bad += 1
            ctx.report.error("url", rel, line, "%s answered %s" % (url, status))
    ctx.report.note("urls", "%d fetched, %d broken, %d blocked" % (len(urls), bad, blocked))


def run(root, denylist=None, check_urls_flag=False, include_raw=False, require_denylist=False, extra_files=()):
    root = Path(root).resolve()
    report = Report()
    terms = []
    if denylist:
        for line in Path(denylist).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                terms.append(line)
    if require_denylist and not terms:
        report.error("leak-denylist", "(denylist)", 0, "a private denylist is required here, but none was given or it holds no terms")
    ctx = Context(root, report, terms)
    check_required(ctx)
    check_hygiene(ctx)
    check_markdown(ctx)
    check_headings(ctx)
    check_versions(ctx)
    build_definitions(ctx)
    check_references(ctx)
    check_coverage(ctx)
    check_section_refs(ctx)
    check_disposition(ctx)
    check_counts(ctx)
    check_links(ctx)
    check_mermaid(ctx)
    check_leaks(ctx, extra_files)
    if check_urls_flag:
        check_urls(ctx, include_raw)
    return report


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent, help="project folder")
    parser.add_argument("--denylist", type=Path, help="file of private terms, one per line (never published)")
    parser.add_argument("--require-denylist", action="store_true", help="fail when no denylist is given or it holds no terms (use when publishing)")
    parser.add_argument("--scan-file", type=Path, action="append", default=[], help="also scan this file, which may be outside the project (repeatable)")
    parser.add_argument("--check-urls", action="store_true", help="also fetch every URL in the main documents (network)")
    parser.add_argument("--include-raw", action="store_true", help="with --check-urls, include the raw research reports")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    parser.add_argument("--quiet", action="store_true", help="print findings only")
    args = parser.parse_args(argv)
    report = run(args.root, args.denylist, args.check_urls, args.include_raw, args.require_denylist, args.scan_file)
    print(report.render(args.quiet))
    failed = report.count("ERROR") > 0 or (args.strict and report.count("WARN") > 0)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
