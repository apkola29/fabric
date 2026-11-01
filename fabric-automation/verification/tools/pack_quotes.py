"""Checks the evidence quotes of a verification report of the reference pack against the extracted source pages.

usage: python pack_quotes.py PACKDIR SOURCEDIR REPORT [REPORT ...]

A report has one row per check or note: `id | verdict | quote | reason`, where the quote (at most 12 words, fragments joined by ...) was copied from the cited
section of the cited page. The notes are called note-wa-1 and so on (wa, sec, del and arc for the four files, numbered in file order). For each row the quote has
to be found, after normalization, in the cited section of the cited page. The program prints the rows whose quote is not found there (found on the cited page but
in another section, found on another page, or not found at all), the verdict counts, and the ids that the report did not cover. A row whose quote is not on the
page shows that the line was not read against the page. It does not say whether the verdict is right.
"""
import re
import sys
from pathlib import Path

PACK, SOURCES = Path(sys.argv[1]), Path(sys.argv[2])
REPORTS = [Path(arg) for arg in sys.argv[3:]]
CITE = re.compile(r'(?:^|; )([^,";]+), "([^"]+)"')
LINE = re.compile(r"^- `(std-[a-z]+-\d+)` (.+)$")
NOTE = re.compile(r"^Note: (.+?) Source: (.+)\.$")
BODY = re.compile(r"(?P<check>.+?) Applies to: (?P<applies>.+?)\. Source: (?P<cites>.+)\.")
ROW = re.compile(r"^\s*\|?\s*`?(std-[a-z]+-\d+|note-[a-z]+-\d)`?\s*\|\s*([SPUMTCX])\b[^|]*\|\s*(.*)$")
NOTE_FILES = {"wa": "well-architected.md", "sec": "security-and-governance.md", "del": "delivery-and-lifecycle.md", "arc": "architecture-patterns.md"}


def norm(text):
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return " " + re.sub(r"[^a-z0-9]+", " ", text.lower()).strip() + " "


def source_file(url):
    slug = re.sub(r"[^A-Za-z0-9]+", "-", url.split("learn.microsoft.com/", 1)[1]).strip("-")
    path = SOURCES / (slug + ".md")
    return path if path.is_file() else None


def section(text, heading):
    out, level = [], None
    for line in text.splitlines():
        m = re.match(r"^(#{1,6}) (.+)$", line)
        if m:
            if level is not None and len(m.group(1)) <= level:
                break
            if level is None and re.sub(r"[^a-z0-9]+", " ", m.group(2).lower()).strip() == re.sub(r"[^a-z0-9]+", " ", heading.lower()).strip():
                level = len(m.group(1))
                continue
        if level is not None:
            out.append(line)
    return "\n".join(out)


pages_all = {path.name: norm(path.read_text(encoding="utf-8")) for path in SOURCES.glob("*.md")}
entries = {}
for path in sorted(PACK.glob("*.md")):
    if path.name == "DRAFTING-BRIEF.md":
        continue
    lines = path.read_text(encoding="utf-8").splitlines()
    sources, in_sources = {}, False
    for line in lines:
        if line.startswith("## "):
            in_sources = line.strip() == "## Sources"
        elif in_sources and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == 4 and cells[0] != "Label" and not set(cells[0]) <= set("-: "):
                sources[cells[0]] = cells[1]
    notes = 0
    for line in lines:
        check, note = LINE.match(line), NOTE.match(line)
        if check:
            parts = BODY.fullmatch(check.group(2))
            who, cites = check.group(1), parts.group("cites")
        elif note:
            notes += 1
            key = [k for k, v in NOTE_FILES.items() if v == path.name][0]
            who, cites = "note-%s-%d" % (key, notes), note.group(2)
        else:
            continue
        found = []
        for label, heading in CITE.findall(cites):
            file = source_file(sources[label])
            text = file.read_text(encoding="utf-8")
            found.append((file.name, norm(section(text, heading)), heading))
        entries[who] = found

for report in REPORTS:
    rows = {}
    for line in report.read_text(encoding="utf-8", errors="replace").splitlines():
        m = ROW.match(line)
        if m:
            rows.setdefault(m.group(1), (m.group(2), m.group(3)))
    print("=" * 80)
    print("%s: %d rows" % (report.name, len(rows)))
    counts = {}
    for who, (verdict, rest) in rows.items():
        counts[verdict] = counts.get(verdict, 0) + 1
    print("verdicts:", ", ".join("%s=%d" % item for item in sorted(counts.items())))
    print("not covered:", ", ".join(sorted(set(entries) - set(rows))) or "none")
    print("not in the pack:", ", ".join(sorted(set(rows) - set(entries))) or "none")
    bad = 0
    for who in sorted(rows):
        if who not in entries:
            continue
        verdict, rest = rows[who]
        quote = rest.split("|")[0].strip().strip("`\"' ")
        fragments = [f for f in re.split(r"\.\.\.|\u2026", quote) if norm(f).strip()]
        if not fragments:
            print("  %s %s: no quote" % (who, verdict)); bad += 1
            continue
        where = "section"
        for fragment in fragments:
            needle = norm(fragment)
            if any(needle in text for _, text, _ in entries[who]):
                continue
            if any(needle in pages_all[name] for name, _, _ in entries[who]):
                where = "cited page, not the cited section" if where == "section" else where
                continue
            if any(needle in text for text in pages_all.values()):
                where = "another page"
                continue
            where = "not found"
            break
        if where != "section":
            bad += 1
            print("  %s %s: quote %s -- %r" % (who, verdict, where, quote[:90]))
    print("rows whose quote is not in the cited section: %d" % bad)
