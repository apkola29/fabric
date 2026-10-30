#!/usr/bin/env python3
"""Check the concrete claims in scripts/facts.json against public sources.

Statuses: PASS (the claim holds now), DRIFT (it held when written and a newer
value exists, or a page that a claim quotes has since changed), FAIL (the claim
is wrong), UNREACHABLE (the source could not be fetched, for example a network
that blocks it). Standard library only.

Exit status is 1 when any claim FAILS (or with --strict, when any is not PASS).
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import platform
import re
import sys
import time
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

PASS, DRIFT, FAIL, UNREACHABLE = "PASS", "DRIFT", "FAIL", "UNREACHABLE"


class Unreachable(Exception):
    pass


def http_get(url, timeout=40):
    req = urlrequest.Request(url, headers={"User-Agent": "fabric-automation-verify-facts", "Accept": "*/*"})
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urlerror.HTTPError as exc:
        if exc.code == 403 and exc.headers.get("X-RateLimit-Remaining") == "0":
            raise Unreachable("GitHub API rate limit reached")
        return exc.code, ""
    except Exception as exc:
        raise Unreachable(str(exc)[:120])


def plain_text(raw):
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw))


def check_pypi(fact):
    status, body = http_get("https://pypi.org/pypi/%s/json" % fact["package"])
    if status == 404:
        return FAIL, "package not found on PyPI"
    data = json.loads(body)
    version, latest = fact["version"], data["info"]["version"]
    if not data["releases"].get(version):
        return FAIL, "version %s was never published (latest is %s)" % (version, latest)
    if latest == version:
        return PASS, "%s is the latest release" % version
    return DRIFT, "%s exists, the latest release is now %s" % (version, latest)


def check_npm(fact):
    status, body = http_get("https://registry.npmjs.org/" + fact["package"].replace("/", "%2f"))
    if status == 404:
        return FAIL, "package not found on npm"
    data = json.loads(body)
    latest = data.get("dist-tags", {}).get("latest")
    if fact.get("version") and fact["version"] not in data.get("versions", {}):
        return FAIL, "version %s was never published (latest is %s)" % (fact["version"], latest)
    return PASS, "published, latest %s" % latest


def resolve_ref(fact):
    if fact["ref"] != "@latest-release":
        return fact["ref"]
    status, body = http_get("https://api.github.com/repos/%s/releases/latest" % fact["repo"])
    if status != 200:
        raise Unreachable("latest release not readable (HTTP %s)" % status)
    return json.loads(body)["tag_name"]


def check_github_file(fact):
    ref = resolve_ref(fact)
    url = "https://raw.githubusercontent.com/%s/%s/%s" % (fact["repo"], ref, fact["path"])
    status, body = http_get(url)
    if status == 404:
        return FAIL, "file not found at %s" % ref
    found = bool(re.search(fact["regex"], body))
    changed = FAIL if fact.get("stable", True) else DRIFT
    if fact.get("expect") == "absent":
        if not found:
            return PASS, "pattern absent at %s" % ref
        return changed, "pattern is now present at %s" % ref
    if found:
        return PASS, "pattern found at %s" % ref
    shown = re.search(fact["show"], body) if fact.get("show") else None
    detail = "pattern not found" + (" (the file says %s)" % shown.group(1) if shown else "")
    return changed, detail


def check_github_tree(fact):
    status, body = http_get("https://api.github.com/repos/%s/git/trees/%s?recursive=1" % (fact["repo"], fact["ref"]))
    if status != 200:
        return FAIL, "tree not readable (HTTP %s)" % status
    data = json.loads(body)
    paths = [e["path"] for e in data["tree"]]
    missing = [p for p in fact.get("present", []) if p not in paths]
    found = [p for p in fact.get("absent", []) if any(x == p or x.startswith(p if p.endswith("/") else p + "/") for x in paths)]
    if data.get("truncated"):
        return UNREACHABLE, "GitHub truncated the tree listing"
    if missing or found:
        return FAIL, "missing: %s; present but expected absent: %s" % (missing or "none", found or "none")
    return PASS, "%d paths listed; expected files present, none of %s present" % (len(paths), fact.get("absent", []))


def check_github_path(fact):
    status, _ = http_get("https://api.github.com/repos/%s/contents/%s?ref=%s" % (fact["repo"], fact["path"], fact["ref"]))
    return (PASS, "path exists") if status == 200 else (FAIL, "HTTP %s" % status)


def check_github_repo(fact):
    status, body = http_get("https://api.github.com/repos/" + fact["repo"])
    if status != 200:
        return FAIL, "HTTP %s" % status
    data = json.loads(body)
    if data.get("archived"):
        return FAIL, "repository is archived"
    return PASS, "live, last pushed %s" % data.get("pushed_at", "?")[:10]


def check_github_tag(fact):
    base = "https://api.github.com/repos/%s/git/" % fact["repo"]
    status, body = http_get(base + "ref/tags/" + fact["tag"])
    if status != 200:
        return FAIL, "tag not found (HTTP %s)" % status
    obj = json.loads(body)["object"]
    sha = obj["sha"]
    if obj["type"] == "tag":
        status, body = http_get(base + "tags/" + sha)
        sha = json.loads(body)["object"]["sha"] if status == 200 else sha
    if sha == fact["sha"]:
        return PASS, "%s resolves to %s" % (fact["tag"], sha[:12])
    return FAIL, "%s resolves to %s, not %s" % (fact["tag"], sha[:12], fact["sha"][:12])


def check_advisory(fact):
    status, body = http_get("https://api.github.com/advisories/" + fact["ghsa"])
    if status != 200:
        return FAIL, "HTTP %s" % status
    data = json.loads(body)
    if data.get("cve_id") != fact["cve"] or fact["contains"].lower() not in (data.get("summary") or "").lower():
        return FAIL, "advisory says %s: %s" % (data.get("cve_id"), data.get("summary"))
    return PASS, "%s: %s" % (data["cve_id"], data["summary"][:80])


def check_arxiv(fact):
    status, body = http_get("https://export.arxiv.org/api/query?id_list=" + fact["id_list"])
    match = re.search(r"<entry>.*?<title>(.*?)</title>", body, re.S)
    title = re.sub(r"\s+", " ", match.group(1)).strip() if match else ""
    if status == 200 and fact["title_contains"].lower() in title.lower():
        return PASS, title[:90]
    return FAIL, "title is '%s'" % title[:90]


def check_page(fact):
    status, body = http_get(fact["url"])
    if status != 200:
        return FAIL, "HTTP %s" % status
    text = body if fact.get("raw") else plain_text(body)
    missing = [p for p in fact.get("all", []) if not re.search(p, text, re.IGNORECASE)]
    segment = fact.get("segment")
    notes = []
    if segment:
        match = re.search(re.escape(segment["start"]) + "(.*?)" + re.escape(segment["end"]), text, re.S)
        if not match:
            return FAIL, "could not find the section between '%s' and '%s'" % (segment["start"], segment["end"])
        part = match.group(1)
        missing += [p for p in segment.get("present", []) if not re.search(re.escape(p), part, re.IGNORECASE)]
        leaked = [p for p in segment.get("absent", []) if re.search(r"\b" + re.escape(p) + r"\b", part, re.IGNORECASE)]
        if leaked:
            notes.append("section now mentions: %s" % ", ".join(leaked))
    if missing or notes:
        detail = "; ".join(filter(None, ["missing: %s" % ", ".join(missing) if missing else "", *notes]))
        return (FAIL if fact.get("stable", True) else DRIFT), detail
    return PASS, "all expected text found"


CHECKS = {
    "pypi": check_pypi, "npm": check_npm, "github-file": check_github_file, "github-tree": check_github_tree,
    "github-path": check_github_path, "github-repo": check_github_repo, "github-tag": check_github_tag,
    "advisory": check_advisory, "arxiv": check_arxiv, "page": check_page,
}


def run(facts, pause=0.3):
    results = []
    for fact in facts:
        try:
            status, evidence = CHECKS[fact["kind"]](fact)
        except Unreachable as exc:
            status, evidence = UNREACHABLE, str(exc)
        except Exception as exc:  # a malformed response must not stop the run
            status, evidence = FAIL, "check crashed: %s" % str(exc)[:100]
        results.append((status, fact, evidence))
        time.sleep(pause)
    return results


def render_markdown(results):
    counts = {s: sum(1 for r in results if r[0] == s) for s in (PASS, DRIFT, FAIL, UNREACHABLE)}
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Fact check results",
        "",
        "Generated by `scripts/verify_facts.py` on %s (%s). Each row checks one concrete claim from the documents against its public source." % (now, platform.platform()),
        "",
        "Summary: %d PASS, %d DRIFT (true when written, a newer value exists), %d FAIL, %d UNREACHABLE (source not fetchable from the machine that ran this)." % (
            counts[PASS], counts[DRIFT], counts[FAIL], counts[UNREACHABLE]),
        "",
        "| Status | Fact | Claim | Cited in | Evidence |",
        "|---|---|---|---|---|",
    ]
    for status, fact, evidence in results:
        cells = [status, "`%s`" % fact["id"], fact["claim"], fact["cited_in"], evidence]
        lines.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--facts", type=Path, default=Path(__file__).resolve().parent / "facts.json")
    parser.add_argument("--write", type=Path, help="write the results as a Markdown table to this file")
    parser.add_argument("--only", help="comma-separated fact ids to run")
    parser.add_argument("--strict", action="store_true", help="exit 1 unless every claim is PASS")
    args = parser.parse_args(argv)
    facts = json.loads(args.facts.read_text(encoding="utf-8"))["facts"]
    if args.only:
        wanted = set(args.only.split(","))
        facts = [f for f in facts if f["id"] in wanted]
    results = run(facts)
    for status, fact, evidence in results:
        print("%-12s %-40s %s" % (status, fact["id"], evidence))
    counts = {s: sum(1 for r in results if r[0] == s) for s in (PASS, DRIFT, FAIL, UNREACHABLE)}
    print("\n%d PASS, %d DRIFT, %d FAIL, %d UNREACHABLE" % (counts[PASS], counts[DRIFT], counts[FAIL], counts[UNREACHABLE]))
    if args.write:
        args.write.write_text(render_markdown(results), encoding="utf-8")
        print("wrote %s" % args.write)
    bad = counts[FAIL] + (counts[DRIFT] + counts[UNREACHABLE] if args.strict else 0)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
