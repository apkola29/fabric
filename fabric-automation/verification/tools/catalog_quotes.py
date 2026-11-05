"""Fetches the pages that toolchain/catalog.json cites, lists what a reviewer has to verify against them, and checks the quotes of a verification report.

usage: python catalog_quotes.py fetch PROJECT SOURCES
       python catalog_quotes.py checklist PROJECT [--servers ID,ID,...]
       python catalog_quotes.py check PROJECT SOURCES REPORT [REPORT ...]
       python catalog_quotes.py lists PROJECT SOURCES

PROJECT is the folder of the project (the one with toolchain/ and scripts/). SOURCES is a folder for the pages: `fetch` writes each page of Microsoft Learn with
learn_extract.py (<slug>.md) and each page of GitHub as its raw text (gh-<slug>.md, with a SOURCE: line first). It needs the network.

`lists` compares, for the servers whose pages list their tools in a table or a list that a program can read, the tool names of the page with those of the catalog in both
directions (a name on the page that the catalog lacks, a name in the catalog that the page lacks) and prints DIFF for each server that differs. It reads the pages in SOURCES.

`checklist` prints one row for each statement of the catalog, with the id that a report has to use:

    <server>:use        what the server is for           <server>:where     where it runs, how it is reached, how it signs in
    <server>:stage      its release stage                <server>#N         the Nth sentence of what it needs and its limits
    <server>:tools      its tool lists and their kinds   <server>:flagged   the tools that no agent calls, and their areas
    <server>:knowledge  the tools that give knowledge    directory, skills#N  the facts about the directory and about the skills

A report has one row per id: `id | verdict | quote | reason`, the verdict one letter (S supported, P partly, U unsupported, M misleading, T wrong kind or a flag that is
missing or not due, C conflict, X other), and the quote at most 12 words copied from one of the pages that the row's server cites (fragments are joined by ...).
`check` prints the rows whose quote is not on any of those pages, the verdict counts, and the ids that the report did not cover. A quote that is not on the page
shows that the statement was not read against it. It does not say whether the verdict is right.
"""
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROW = re.compile(r"^\s*\|?\s*`?([a-z][a-z0-9-]*(?:[:#][a-z0-9]+)?)`?\s*\|\s*([SPUMTCX])\b[^|]*\|\s*(.*)$")
STAGE = {"ga": "generally available", "public-preview": "public preview", "preview": "preview", "beta": "beta", "unverified": "not stated on the pages that were read"}


def project_modules(project):
    sys.path.insert(0, str(Path(project) / "scripts"))
    import toolchain_catalog
    return toolchain_catalog


def load(project):
    tc = project_modules(project)
    root = Path(project) / "toolchain"
    read = lambda name: __import__("json").loads((root / name).read_text(encoding="utf-8"))
    return tc, tc.load((root / "catalog.json").read_text(encoding="utf-8")), read("toolchain.json"), read("toolchain.lock.json")


def learn_slug(url):
    """The file name that learn_extract.py gives a page of Learn (the same rule, so that this file also runs where learn_extract.py is not beside it)."""
    return re.sub(r"[^A-Za-z0-9]+", "-", url.split("learn.microsoft.com/", 1)[1]).strip("-")


def local_name(url):
    if url.startswith("https://learn.microsoft.com/"):
        try:
            import learn_extract
            return learn_extract.slug(url) + ".md"
        except ImportError:
            return learn_slug(url) + ".md"
    return "gh-" + re.sub(r"[^A-Za-z0-9]+", "-", url.split("github.com/", 1)[1]).strip("-") + ".md"


def raw_address(url):
    owner, repo, *rest = url.split("github.com/", 1)[1].split("/")
    if not rest:
        return "https://raw.githubusercontent.com/%s/%s/HEAD/README.md" % (owner, repo)
    kind, ref, *path = rest
    return "https://raw.githubusercontent.com/%s/%s/%s/%s" % (owner, repo, ref, "/".join(path) + ("/README.md" if kind == "tree" else ""))


def all_pages(catalog):
    pages = {}
    for page in catalog["directory"]["pages"] + catalog["skills"]["pages"]:
        pages[page["url"]] = None
    for server in catalog["servers"]:
        for page in server["pages"]:
            pages[page["url"]] = server["id"]
    return list(pages)


def fetch(project, sources):
    import learn_extract
    tc, catalog, _manifest, _lock = load(project)
    Path(sources).mkdir(parents=True, exist_ok=True)
    for url in all_pages(catalog):
        target = Path(sources) / local_name(url)
        if url.startswith("https://learn.microsoft.com/"):
            learn_extract.main(["learn_extract.py", str(sources), url])
        else:
            request = urllib.request.Request(raw_address(url), headers={"User-Agent": "fabric-automation-verification"})
            with urllib.request.urlopen(request, timeout=60) as response:
                text = response.read().decode("utf-8", "replace").replace("\r\n", "\n")
            target.write_text("SOURCE: %s\n\n%s" % (url, text), encoding="utf-8", newline="\n")
        print("fetched", target.name)


def stage_of(server, manifest_server):
    return STAGE[manifest_server["status"] if manifest_server else server["status"]]


def rows(project):
    """[(id, text, [page urls])] for every statement of the catalog."""
    tc, catalog, manifest, lock = load(project)
    by_id = {s["id"]: s for s in manifest["mcp_servers"]}
    out = [("directory", "Fabric's directory lists %(servers)d servers: %(remote)d remote and %(local)d local; the servers marked `directory` in the catalog are those it lists. Pages: %%s"
            % catalog["directory"] % ", ".join(p["url"] for p in catalog["directory"]["pages"]), [p["url"] for p in catalog["directory"]["pages"]])]
    for n, fact in enumerate(catalog["skills"]["facts"], 1):
        out.append(("skills#%d" % n, fact, [p["url"] for p in catalog["skills"]["pages"]]))
    for server in catalog["servers"]:
        sid, pages, mine = server["id"], [p["url"] for p in server["pages"]], by_id.get(server["id"])
        out.append((sid + ":use", server["use"], pages))
        sign_in = tc.sign_in_cell(mine) if mine else "(not pinned: see the page)"
        out.append((sid + ":where", "%s, endpoint: %s; group %s%s; sign-in: %s" % (server["hosting"], server["endpoint"], server["group"], ", listed in the directory" if server.get("directory") else "", sign_in), pages))
        out.append((sid + ":stage", stage_of(server, mine), pages))
        for n, sentence in enumerate(server["needs"], 1):
            out.append(("%s#%d" % (sid, n), sentence, pages))
        groups = tc.server_tools(server, lock)
        tools = server["tools"]
        if tools["from"] == "none":
            text = "no list of tools: " + tools["note"]
        elif tools["from"] == "lock":
            text = "from the lock, contract %s (verify only that the page does not contradict it): %s" % (tools["contract"], "; ".join("%s%s (%d): %s" % (k or "all", " [%s]" % s if s else "", len(n_), ", ".join(n_)) for s, k, n_ in groups))
        else:
            text = "; ".join("%s%s (%d): %s" % (k, " [%s]" % s if s else "", len(n_), ", ".join(n_)) for s, k, n_ in groups)
        out.append((sid + ":tools", text, pages))
        out.append((sid + ":flagged", "; ".join("%s: %s%s%s" % (e["area"], ("never called: " + ", ".join(e["tools"])) if e["tools"] else "no tool named",
                                                                  " (%s)" % e["note"] if "note" in e else "",
                                                                  "; never made through any tool: " + " / ".join(e["changes"]) if e.get("changes") else "")
                                                for e in server["flagged"]) or "nothing is flagged", pages))
        if server["knowledge"]:
            out.append((sid + ":knowledge", "; ".join("%s: %s" % (", ".join(e["tools"]), e["what"]) for e in server["knowledge"]), pages))
    return out


def norm(text):
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return " " + re.sub(r"[^a-z0-9]+", " ", text.lower()).strip() + " "


def checklist(project, only):
    for ident, text, pages in rows(project):
        if only and ident.split(":")[0].split("#")[0] not in only and not (ident.startswith(("directory", "skills")) and "directory" in only):
            continue
        print("%s | %s" % (ident, text))
        print("    pages: " + "; ".join(pages))


def check(project, sources, reports):
    pages = {}
    expected = {}
    for ident, _text, urls in rows(project):
        expected[ident] = urls
        for url in urls:
            if url not in pages:
                path = Path(sources) / local_name(url)
                pages[url] = norm(path.read_text(encoding="utf-8")) if path.is_file() else None
    everything = [text for text in pages.values() if text]
    for report in reports:
        found = {}
        for line in Path(report).read_text(encoding="utf-8", errors="replace").splitlines():
            m = ROW.match(line)
            if m:
                found.setdefault(m.group(1), (m.group(2), m.group(3)))
        print("=" * 80)
        print("%s: %d rows" % (Path(report).name, len(found)))
        counts = {}
        for verdict, _rest in found.values():
            counts[verdict] = counts.get(verdict, 0) + 1
        print("verdicts:", ", ".join("%s=%d" % item for item in sorted(counts.items())))
        print("not covered:", ", ".join(sorted(set(expected) - set(found))) or "none")
        print("not in the catalog:", ", ".join(sorted(set(found) - set(expected))) or "none")
        bad = long = split = 0
        for ident in sorted(found):
            if ident not in expected:
                continue
            verdict, rest = found[ident]
            quote = rest.split("|")[0].strip().strip("`\"' ")
            fragments = [f for f in re.split(r"\.\.\.|\u2026", quote) if norm(f).strip()]
            if not fragments:
                print("  %s %s: no quote" % (ident, verdict))
                bad += 1
                continue
            words = sum(len(f.split()) for f in fragments)
            if words > 12:
                long += 1
                print("  %s %s: the quote has %d words, the limit is 12 -- %r" % (ident, verdict, words, quote[:60]))
            own = [pages[u] for u in expected[ident] if pages.get(u)]
            needles = [norm(fragment) for fragment in fragments]
            if any(all(needle in text for needle in needles) for text in own):
                continue
            if all(any(needle in text for text in own) for needle in needles):
                split += 1
                print("  %s %s: the fragments of the quote are on different cited pages -- %r" % (ident, verdict, quote[:90]))
                continue
            where = "not found"
            for needle in needles:
                if not any(needle in text for text in own):
                    where = "another page" if any(needle in text for text in everything) else "not found"
                    break
            bad += 1
            print("  %s %s: quote on %s -- %r" % (ident, verdict, where, quote[:90]))
        print("rows whose quote is not on a page that the row's server cites: %d; quotes of more than 12 words: %d; quotes whose fragments are on different pages: %d" % (bad, long, split))


LEARN = "https://learn.microsoft.com/en-us/"
# server, set of its tools (None: the unnamed set), page, the text where its list starts and the text where it ends (None: the whole page, or to the end of the section), how to read the names
LISTS = [
    ("fabric-core", None, LEARN + "rest/api/fabric/articles/mcp-servers/core-remote/tools-core-mcp-server", None, None, "table"),
    ("fabric-iq", None, LEARN + "fabric/iq/connectors/fabric-iq-mcp", "## Available tools", "## Tool contract", "table"),
    ("fabric-sql", None, LEARN + "fabric/data-warehouse/data-warehouse-mcp-server", "## Available tools", "\n## ", "table"),
    ("powerbi-consumption-remote", None, LEARN + "power-bi/developer/mcp/remote-mcp-server-get-started", "## Available Power BI MCP server tools", None, "tool headings"),
    ("microsoft-learn", None, "https://github.com/MicrosoftDocs/mcp", "| Tool", "\n\n", "table"),
    ("activator-remote", None, LEARN + "fabric/real-time-intelligence/mcp-remote-activator", "## Rule management", "\n## ", "table"),
    ("operations-agent-remote", None, LEARN + "fabric/real-time-intelligence/mcp-remote-operations-agent", "Configure server", "\n## ", "table"),
    ("onelake-hosted", None, LEARN + "fabric/onelake/onelake-hosted-mcp", "## Browse and read data", "## Read tool results", "table"),
    ("sql-mcp-server", None, LEARN + "azure/data-api-builder/mcp/data-manipulation-language-tools", "## What are DML tools?", "## The tools", "table"),
    ("azure-arm-cost", None, "https://github.com/Azure/Azure-Resource-Manager-MCP", "| Tool", "\n\n", "table"),
    ("azure-arm-cost", "optional Cost Management toolset", "https://github.com/Azure/Azure-Resource-Manager-MCP/blob/main/docs/CostManagementAndPricingTools.md", "## Cost Management tools", "## Example", "table"),
    ("powerbi-authoring-local", None, "https://github.com/microsoft/powerbi-modeling-mcp", None, None, "operations"),
    ("datafactory-local", None, "https://github.com/microsoft/DataFactory.MCP", "## Available Tools", "## Available Resources", "inline"),
    ("graph-enterprise", None, LEARN + "graph/mcp-server/overview", "## Tools", "\n## ", "bullets"),
    ("graphql-sample", None, LEARN + "fabric/data-engineering/api-graphql-local-model-context-protocol", "### Available MCP tools", "\n## ", "headings"),
    ("foundry-mcp", None, LEARN + "azure/ai-foundry/mcp/available-tools", None, None, "table"),
]
NOT_ON_THE_PAGE = {"powerbi-authoring-local": {"accept_eula"},  # named in the text about the license
                   "datafactory-local": {"create_connection_ui"}}  # named in the guide to connection management, not in the list of the README
ACCESS = {"foundry-mcp": LEARN + "azure/ai-foundry/mcp/available-tools"}  # a page whose table says, for each tool, read or write: the destructive tools of the catalog are among its write tools


def names_on(text, how):
    if how == "table":
        return re.findall(r"^\|\s*`([A-Za-z0-9_\-]+)`", text, re.MULTILINE)
    if how == "operations":
        return re.findall(r"^\|\s*\*\*([a-z_]+_operations)\*\*", text, re.MULTILINE)
    if how == "bullets":
        return re.findall(r"^- ([a-z_]+):", text, re.MULTILINE)
    if how == "headings":
        return re.findall(r"^#{3,5} `([A-Za-z0-9_\-]+)`", text, re.MULTILINE)
    if how == "tool headings":
        return re.findall(r"^## ([A-Z][A-Za-z ]+?) tool$", text, re.MULTILINE)
    return re.findall(r"`([a-z_]+)`", text)


def access_differences(sid, url, catalog_server, sources):
    """The tools whose access (read or write) on the page differs from the catalog's kinds: write on the page is write or destructive in the catalog."""
    text = (Path(sources) / local_name(url)).read_text(encoding="utf-8")
    page = {m.group(1): m.group(2) for m in re.finditer(r"^\|\s*`([A-Za-z0-9_\-]+)`\s*\|\s*(read|write)\s*\|", text, re.MULTILINE)}
    mine = {n: ("read" if g["kind"] == "read" else "write") for g in catalog_server["tools"]["groups"] for n in g["names"]}
    return sorted(n for n in set(page) & set(mine) if page[n] != mine[n]), len(page)


def lists(project, sources):
    tc, catalog, _manifest, _lock = load(project)
    by_id = {s["id"]: s for s in catalog["servers"]}
    status = 0
    union = {}
    for sid, tool_set, url, start, end, how in LISTS:
        text = (Path(sources) / local_name(url)).read_text(encoding="utf-8")
        if start:
            first = text.index(start)
            text = text[first:text.index(end, first + 1)] if end else text[first:]
        found = names_on(text, how)
        union.setdefault((sid, tool_set), []).extend(found)
    for (sid, tool_set), found in union.items():
        groups = by_id[sid]["tools"].get("groups", [])
        mine = [n for g in groups if g.get("set") == tool_set for n in g["names"]]
        if tool_set is None and not mine:
            mine = [n for g in groups for n in g["names"]]  # a server whose groups are all in named sets (the two URLs of an operations agent)
        if tool_set == "optional Cost Management toolset":
            found = [n for n in found if n not in union[(sid, None)]]
        absent = sorted(n for n in NOT_ON_THE_PAGE.get(sid, set()) if n in found or n not in mine)  # a tool that this table sets aside has to be in the catalog and not in the list of the page
        mine = [n for n in mine if n not in NOT_ON_THE_PAGE.get(sid, set())]
        missing, extra = sorted(set(found) - set(mine)), sorted(set(mine) - set(found))
        duplicated = sorted({n for n in found if found.count(n) > 1})
        state = "DIFF" if missing or extra or duplicated or absent else "OK"
        status |= state == "DIFF"
        print("%-26s %-34s %-4s page %d, catalog %d; on the page only: %s; in the catalog only: %s; twice on the page: %s%s"
              % (sid, tool_set or "", state, len(set(found)), len(set(mine)), missing, extra, duplicated, "; set aside and not as expected: %s" % absent if absent else ""))
    unread = sorted(s["id"] for s in catalog["servers"] if s["tools"]["from"] == "page" and s["id"] not in {sid for sid, _set in union})
    if unread:
        status = 1
        print("DIFF the catalog lists the tools of these servers from a page, and LISTS has no entry that reads it: %s" % ", ".join(unread))
    for sid, url in ACCESS.items():
        different, count = access_differences(sid, url, by_id[sid], sources)
        status |= bool(different) or count == 0
        print("%-26s %-34s %-4s access of %d tools on the page; kinds that differ: %s" % (sid, "access", "DIFF" if different or count == 0 else "OK", count, different))
    return status


def main(argv):
    if len(argv) >= 3 and argv[0] == "fetch":
        fetch(argv[1], argv[2])
    elif len(argv) == 3 and argv[0] == "lists":
        return lists(argv[1], argv[2])
    elif len(argv) >= 2 and argv[0] == "checklist":
        only = set(argv[3].split(",")) if len(argv) > 3 and argv[2] == "--servers" else set()
        checklist(argv[1], only)
    elif len(argv) >= 4 and argv[0] == "check":
        check(argv[1], argv[2], argv[3:])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
