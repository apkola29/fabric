"""Reduces pages of Microsoft Learn to plain text with the headings, lists, tables and code kept, and the date that Microsoft gives for each page.

usage: python learn_extract.py OUTDIR URL [URL ...]
       python learn_extract.py OUTDIR --list FILE         FILE has one address on each line (blank lines and lines that start with # are skipped)

For each address it writes OUTDIR/<name>.md and OUTDIR/<name>.links.txt. The name is the address after "learn.microsoft.com/" with every run of other characters
replaced by a hyphen (the same rule that pack_mechanics.py, pack_quotes.py and pack_hedges.py use to find a page). The text file starts with these lines:

    SOURCE: <the address that was asked for>
    UPDATED_AT: <the updated_at meta of the page: set when the page is published, and the date that the reference pack records>
    MS_DATE: <the ms.date meta of the page: set by the author of the page>
    TITLE: <the title>

and then the main text of the page. The links file has one line for each link in the main text: the text, a tab and the address.

A page is read once, with no sign-in. The conversion is deliberately plain: a heading is a line of '#', a list item starts with '- ' or '1. ', a table is a table of '|', a code block is fenced. What is not
text of the article (the navigation, the feedback buttons, the table of contents of the page and the footer) is left out. A change of the markup of Microsoft Learn can change what is left out, so read
a result before you rely on it. It needs the network.
"""
import html.parser
import re
import sys
import urllib.request
from pathlib import Path

SKIP_TAGS = {"script", "style", "nav", "aside", "footer", "header", "form", "button", "svg", "noscript", "template", "select", "option", "iframe"}
SKIP_CLASSES = {"anchor-link", "feedback-section", "like-dislike-button", "visually-hidden", "is-hidden", "display-none", "contributors-text", "page-action-holder", "action-buttons",
                "binary-feedback", "article-metadata", "article-header-metadata-container", "metadata", "hidden-text", "text-body-medium-bold-hide"}
BLOCK_TAGS = {"p", "div", "section", "article", "blockquote", "dl", "dt", "dd", "figure", "figcaption", "details", "summary", "main", "tr"}
VOID_TAGS = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}


def slug(url):
    tail = url.split("learn.microsoft.com/", 1)[1] if "learn.microsoft.com/" in url else re.sub(r"^https?://", "", url)
    return re.sub(r"[^A-Za-z0-9]+", "-", tail).strip("-")


class Reader(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.title, self.in_title = {}, "", False
        self.stack = []          # the open tags of the main text, each as (tag, skipped)
        self.in_main = False
        self.skip_depth = 0
        self.out = []            # finished lines
        self.line = []           # pieces of the line that is open
        self.list_stack = []     # ['ul'] or ['ol', count]
        self.pre = False
        self.table = None        # the rows of the table that is open
        self.row = None
        self.cell = None
        self.links = []
        self.link_text, self.link_href = None, None
        self.code_lang = ""

    # ---------------------------------------------------------------- helpers
    def flush(self, blank=False):
        text = "".join(self.line)
        self.line = []
        if not self.pre:
            text = re.sub(r"[ \t\u00a0]+", " ", text).strip()
        if text.strip() or self.pre:
            self.out.append(text)
        if blank and self.out and self.out[-1] != "":
            self.out.append("")

    def put(self, text):
        if self.cell is not None:
            self.cell.append(text)
        else:
            self.line.append(text)

    # ---------------------------------------------------------------- parser callbacks
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("name") in ("updated_at", "ms.date"):
            self.meta[attrs["name"]] = attrs.get("content", "")
        if tag == "title":
            self.in_title = True
        if tag == "main" and attrs.get("id") == "main":
            self.in_main = True
        if not self.in_main:
            return
        classes = set((attrs.get("class") or "").split())
        skipped = tag in SKIP_TAGS or bool(classes & SKIP_CLASSES) or attrs.get("hidden") is not None or attrs.get("aria-hidden") == "true"
        if tag in VOID_TAGS:
            if not self.skip_depth:
                if tag == "br":
                    self.put("\n" if self.cell is None and not self.pre else " ")
                    if self.cell is None and not self.pre:
                        self.flush()
                elif tag == "hr":
                    self.flush(True)
            return
        self.stack.append((tag, skipped))
        if skipped or self.skip_depth:
            self.skip_depth += 1
            return
        if re.fullmatch(r"h[1-6]", tag):
            self.flush(True)
            self.put("#" * int(tag[1]) + " ")
        elif tag in ("ul", "ol"):
            self.flush()
            self.list_stack.append([tag, 0])
        elif tag == "li":
            self.flush()
            if self.list_stack:
                top = self.list_stack[-1]
                top[1] += 1
                self.put("  " * (len(self.list_stack) - 1) + ("- " if top[0] == "ul" else "%d. " % top[1]))
        elif tag == "pre":
            self.flush(True)
            self.pre = True
            self.code_lang = ""
            self.out.append("```")
        elif tag == "code" and self.pre:
            match = re.search(r"(?:lang|language)-([A-Za-z0-9+#-]+)", attrs.get("class") or "")
            if match and self.out and self.out[-1] == "```":
                self.out[-1] = "```" + match.group(1)
        elif tag == "code":
            self.put("`")
        elif tag == "table":
            self.flush(True)
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.table is not None:
            self.cell = []
        elif tag == "a" and attrs.get("href") and not attrs["href"].startswith("#") and not attrs["href"].startswith("javascript"):
            self.link_href, self.link_text = attrs["href"], []
        elif tag in BLOCK_TAGS and self.table is None and tag != "tr":
            self.flush()

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if not self.in_main:
            return
        if tag == "main" and not self.stack:
            self.in_main = False
            return
        if tag in VOID_TAGS or not self.stack:
            return
        # close up to the matching open tag, tolerating the unbalanced markup that pages have
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                closed = self.stack[index:]
                del self.stack[index:]
                break
        else:
            return
        for name, skipped in reversed(closed):
            if skipped or self.skip_depth:
                self.skip_depth -= 1
                if skipped or self.skip_depth:
                    continue
            self.close(name)
        if tag == "main" and not self.stack:
            self.in_main = False

    def close(self, tag):
        if re.fullmatch(r"h[1-6]", tag):
            self.flush(True)
        elif tag in ("ul", "ol"):
            self.flush()
            if self.list_stack:
                self.list_stack.pop()
            if not self.list_stack:
                self.flush(True)
        elif tag == "li":
            self.flush()
        elif tag == "pre":
            self.pre = False
            self.flush()
            self.out.append("```")
            self.out.append("")
        elif tag == "code" and not self.pre:
            self.put("`")
        elif tag in ("td", "th") and self.cell is not None:
            text = re.sub(r"\s+", " ", "".join(self.cell)).strip().replace("|", "\\|")
            self.row.append(text)
            self.cell = None
        elif tag == "tr" and self.row is not None and self.table is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            rows = [r for r in self.table if any(c for c in r)]
            if rows:
                width = max(len(r) for r in rows)
                for number, row in enumerate(rows):
                    row = row + [""] * (width - len(row))
                    self.out.append("| " + " | ".join(row) + " |")
                    if number == 0:
                        self.out.append("|" + "|".join(["---"] * width) + "|")
                self.out.append("")
            self.table = None
        elif tag == "a" and self.link_href is not None:
            text = re.sub(r"\s+", " ", "".join(self.link_text)).strip()
            if text:
                self.links.append((text, self.link_href))
            self.link_href, self.link_text = None, None
        elif tag in BLOCK_TAGS and self.table is None:
            self.flush()

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if not self.in_main or self.skip_depth:
            return
        if self.link_text is not None:
            self.link_text.append(data)
        if self.pre:
            self.line.append(data)
            if "\n" in data:
                joined = "".join(self.line)
                parts = joined.split("\n")
                self.out.extend(parts[:-1])
                self.line = [parts[-1]]
            return
        self.put(data)


def extract(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (learn-extract)"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        final = response.geturl()
        text = response.read().decode("utf-8", "replace")
    reader = Reader()
    reader.feed(text)
    reader.flush()
    lines = reader.out
    while lines and lines[-1] == "":
        lines.pop()
    body = []
    for line in lines:
        if line == "" and body and body[-1] == "":
            continue
        body.append(line)
    first = next((i for i, line in enumerate(body) if line.startswith("# ")), 0)
    body = body[first:]
    while body and (body[-1] in ("", "##", "## ", "Additional resources")):
        body.pop()
    return {"final": final, "updated_at": reader.meta.get("updated_at", ""), "ms_date": reader.meta.get("ms.date", ""),
            "title": re.sub(r"\s+", " ", reader.title).strip(), "body": body, "links": reader.links}


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    out = Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    if argv[2] == "--list":
        urls = [line.strip() for line in Path(argv[3]).read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    else:
        urls = argv[2:]
    for url in urls:
        page = extract(url)
        name = slug(url)
        head = ["SOURCE: " + url, "UPDATED_AT: " + page["updated_at"], "MS_DATE: " + page["ms_date"], "TITLE: " + page["title"]]
        if page["final"] != url:
            head.append("FINAL_URL: " + page["final"])
        (out / (name + ".md")).write_text("\n".join(head) + "\n\n" + "\n".join(page["body"]) + "\n", encoding="utf-8", newline="\n")
        (out / (name + ".links.txt")).write_text("".join("%s\t%s\n" % link for link in page["links"]), encoding="utf-8", newline="\n")
        print("%-100s %6d lines, updated_at %s" % (name[:100], len(page["body"]), page["updated_at"][:10] or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
