"""Hedge audit of the reference pack against the extracted source pages.

usage: python pack_hedges.py PACKDIR SOURCEDIR [ID ...]

For every check (or only the given ids) it prints the check and, for each sentence of the cited sections that shares content words with it, the hedge and
condition words of that sentence which the check does not carry. A program cannot decide whether a check is supported; this shows where a reader has to look
at a lost "can", "may", "such as", "if", "usually" or a changed "or". Round 2 of the verification of the pack read it for every check and found one lost word
and nothing else, and round 3 questioned 26 checks: the output is a prompt for a reader, not a substitute for one.
"""
import re
import sys
from pathlib import Path

PACK, SOURCES = Path(sys.argv[1]), Path(sys.argv[2])
ONLY = set(sys.argv[3:])
CITE = re.compile(r'(?:^|; )([^,";]+), "([^"]+)"')
LINE = re.compile(r"^- `(std-[a-z]+-\d+)` (.+)$")
BODY = re.compile(r"(?P<check>.+?) Applies to: (?P<applies>.+?)\. Source: (?P<cites>.+)\.")
HEDGES = ["can", "may", "might", "could", "should", "usually", "typically", "normally", "generally", "often", "commonly", "such as", "for example",
          "for instance", "whenever possible", "when possible", "if", "when", "unless", "only", "except", "as long as", "consider", "ideally", "preferably",
          "at least", "avoid", "never", "always", "must", "not", "or", "both", "all", "every", "any", "each", "currently", "preview", "recommend", "best",
          "instead", "rather than", "periodically", "regularly", "where", "because", "so that", "larger", "smaller", "at any time", "some", "most", "many",
          "few", "less", "more", "between", "than"]
STOP = set("a an the of to in on for and or is are be it its this that these those with by as at from not no do does if so than then also can may you your we our "
           "has have had was were will would should could must which who whom what when where while into over under per via about up out use used using".split())


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def stem(word):
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[:-len(suffix)]
    return word


def content(text):
    return {stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 2}


def source_file(url):
    slug = re.sub(r"[^A-Za-z0-9]+", "-", url.split("learn.microsoft.com/", 1)[1]).strip("-")
    path = SOURCES / (slug + ".md")
    return path if path.is_file() else None


def section(text, heading):
    lines, out, level = text.splitlines(), [], None
    for line in lines:
        m = re.match(r"^(#{1,6}) (.+)$", line)
        if m:
            if level is not None and len(m.group(1)) <= level:
                break
            if level is None and norm(m.group(2)) == norm(heading):
                level = len(m.group(1))
                continue
        if level is not None:
            out.append(line)
    return "\n".join(out)


def sentences(block):
    found = []
    for line in block.splitlines():
        line = line.strip().lstrip("|-* ").strip()
        if not line:
            continue
        found.extend(s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", line) if s.strip())
    return found


def hedges_in(sentence):
    low = " " + " ".join(re.findall(r"[a-z0-9']+", sentence.lower().replace("don't", "do not").replace("doesn't", "does not"))) + " "
    return {h for h in HEDGES if " " + h + " " in low}


for path in sorted(PACK.glob("*.md")):
    lines = path.read_text(encoding="utf-8").splitlines()
    sources, in_sources = {}, False
    for line in lines:
        if line.startswith("## "):
            in_sources = line.strip() == "## Sources"
        elif in_sources and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == 4 and cells[0] != "Label" and not set(cells[0]) <= set("-: "):
                sources[cells[0]] = cells[1]
    for line in lines:
        check = LINE.match(line)
        if not check:
            continue
        who = check.group(1)
        if ONLY and who not in ONLY:
            continue
        parts = BODY.fullmatch(check.group(2))
        if not parts:
            continue
        sentence = re.sub(r"\[[a-z]+\]", "", parts.group("check"))
        mine = content(sentence)
        my_hedges = hedges_in(sentence)
        print("=" * 100)
        print("%s  %s" % (who, parts.group("check")))
        print("   applies to: %s" % parts.group("applies"))
        for label, heading in CITE.findall(parts.group("cites")):
            file = source_file(sources.get(label, "https://learn.microsoft.com/x/y"))
            text = file.read_text(encoding="utf-8") if file else ""
            block = section(text, heading)
            if not block:
                print("   !! no section %r in %s" % (heading, label))
                continue
            ranked = []
            for s in sentences(block):
                shared = mine & content(s)
                if len(shared) >= 3 and len(shared) / max(1, len(content(s))) >= 0.2:
                    ranked.append((len(shared), s))
            ranked.sort(key=lambda item: -item[0])
            print("   -- %s, %r" % (label, heading))
            for count, s in ranked[:4]:
                missing = sorted(hedges_in(s) - my_hedges - {"not", "all", "any", "each", "more", "less", "than", "between"})
                print("      [%d] %s" % (count, s[:420]))
                if missing:
                    print("          lost: %s" % ", ".join(missing))
