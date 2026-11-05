"""Mechanical checks of the reference pack against the extracted source pages.

usage: python pack_mechanics.py PACKDIR SOURCEDIR

PACKDIR holds the reference files (toolchain/skills/factory-standards/references: the four of the first pack, the five of the workload pack, or the ones that are being checked) and SOURCEDIR the pages
reduced to text, one file per page, named by the address of the page with every run of other characters replaced by a hyphen, and starting with a line `SOURCE: <address>`.

For every check and every note of every reference file it verifies that: each cited label is in the sources table; each cited section heading is a heading of the
extracted page of that label; every number in the check text occurs in the text of the cited pages; no run of more than 12 words is copied from a cited page. The
model that reads the pack still has to decide whether a point is supported. This only removes the errors that a program can find.
"""
import re
import sys
from pathlib import Path

PACK, SOURCES = Path(sys.argv[1]), Path(sys.argv[2])
CITE = re.compile(r'(?:^|; )([^,";]+), "([^"]+)"')
LINE = re.compile(r"^- `(std-[a-z]+-\d+)` (.+)$")
NOTE = re.compile(r"^Note: (.+?) Source: (.+)\.$")
BODY = re.compile(r"(?P<check>.+?) Applies to: (?P<applies>.+?)\. Source: (?P<cites>.+)\.")
NUMBER = re.compile(r"\d[\d,.]*\d|\d")


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def words(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def source_file(url):
    slug = re.sub(r"[^A-Za-z0-9]+", "-", url.split("learn.microsoft.com/", 1)[1]).strip("-")
    path = SOURCES / (slug + ".md")
    return path if path.is_file() else None


def longest_shared(sentence, page_words, limit=12):
    """The longest run of words of `sentence` that occurs in the page, searched only for runs longer than `limit`."""
    page_text = " " + " ".join(page_words) + " "
    best = 0
    for start in range(len(sentence)):
        length = best + 1
        while start + length <= len(sentence) and (" " + " ".join(sentence[start:start + length]) + " ") in page_text:
            best = length
            length += 1
    return best


problems = 0
for path in sorted(PACK.glob("*.md")):
    if path.name == "DRAFT-NOTES.md":
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
    pages = {}
    for label, url in sources.items():
        file = source_file(url)
        text = file.read_text(encoding="utf-8") if file else ""
        headings = {norm(m.group(1)) for m in re.finditer(r"^#{1,6} (.+)$", text, re.M)}
        pages[label] = (text, headings, words(text))
        if not file:
            print("%s: no extracted page for %s" % (path.name, label)); problems += 1
    count = 0
    for line in lines:
        check = LINE.match(line)
        note = NOTE.match(line)
        if not check and not note:
            continue
        count += 1
        who = check.group(1) if check else "note"
        if check:
            parts = BODY.fullmatch(check.group(2))
            if not parts:
                print("%s %s: does not parse" % (path.name, who)); problems += 1
                continue
            sentence, cites = parts.group("check"), parts.group("cites")
        else:
            sentence, cites = note.group(1), note.group(2)
        found = CITE.findall(cites)
        if not found:
            print("%s %s: no citation" % (path.name, who)); problems += 1
        cited_text = ""
        for label, heading in found:
            if label not in pages:
                print("%s %s: label %r not in the sources table" % (path.name, who, label)); problems += 1
                continue
            text, headings, _ = pages[label]
            cited_text += " " + text
            if norm(heading) not in headings:
                print("%s %s: heading %r is not a heading of %s" % (path.name, who, heading, label)); problems += 1
        for number in NUMBER.findall(re.sub(r"\[[a-z]+\]", "", sentence)):
            if number not in cited_text:
                print("%s %s: the number %s is not in the cited pages" % (path.name, who, number)); problems += 1
        sentence_words = words(re.sub(r"\[[a-z]+\]", "", sentence))
        for label, heading in found:
            if label in pages:
                shared = longest_shared(sentence_words, pages[label][2])
                if shared > 12:
                    print("%s %s: %d words in a row are copied from %s" % (path.name, who, shared, label)); problems += 1
    print("%s: %d checks and notes read" % (path.name, count))
print("%d problem(s)" % problems)
sys.exit(1 if problems else 0)
