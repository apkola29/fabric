#!/usr/bin/env python3
"""Check the concrete claims in scripts/facts.json against public sources.

Statuses: PASS (the claim holds now), DRIFT (it held when written and a newer
value exists, or a page that a claim quotes has since changed), FAIL (the claim
is wrong, or its entry in facts.json is itself broken), UNREACHABLE (the source
could not be fetched, answered with an error other than "not found", or answered
with something unusable such as an empty body or malformed JSON, so it says
nothing about the claim). Standard library only.

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
    """The source gave no usable answer, so the claim is neither confirmed nor refuted."""


class InvalidFact(Exception):
    """An entry of facts.json is broken. That is a defect in this repository, not in a source."""


def http_get(url, timeout=40):
    req = urlrequest.Request(url, headers={"User-Agent": "fabric-automation-verify-facts", "Accept": "*/*"})
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            if resp.status == 200 and not body.strip():
                # An empty answer would make every "pattern absent" claim pass.
                raise Unreachable("empty answer from %s" % url[:70])
            return resp.status, body
    except Unreachable:
        raise
    except urlerror.HTTPError as exc:
        if exc.code == 403 and exc.headers.get("X-RateLimit-Remaining") == "0":
            raise Unreachable("GitHub API rate limit reached")
        if exc.code == 429 or exc.code >= 500:
            raise Unreachable("HTTP %s from %s" % (exc.code, url[:70]))
        return exc.code, ""
    except Exception as exc:
        raise Unreachable(str(exc)[:120])


def require_ok(status, what):
    """A page that did not answer 200 says nothing about the claim, so it is never read as evidence."""
    if status != 200:
        raise Unreachable("%s answered HTTP %s" % (what, status))


def gone(status):
    """Only these two statuses say that the thing a claim points at no longer exists."""
    return status in (404, 410)


def json_object(body, what, *keys):
    """Parse a JSON object and require the keys a check reads. Anything else is an unusable answer."""
    try:
        data = json.loads(body)
    except ValueError:
        raise Unreachable("%s answered with text that is not JSON" % what)
    if not isinstance(data, dict) or any(key not in data for key in keys):
        raise Unreachable("%s answered with JSON that lacks %s" % (what, ", ".join(keys) if keys else "an object"))
    return data


def nested(value, what, *keys):
    """Require a JSON object with these keys inside a response."""
    if not isinstance(value, dict) or any(key not in value for key in keys):
        raise Unreachable("%s answered with an unexpected structure" % what)
    return value


def plain_text(raw):
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw))


def check_pypi(fact):
    status, body = http_get("https://pypi.org/pypi/%s/json" % fact["package"])
    if gone(status):
        return FAIL, "package not found on PyPI"
    require_ok(status, "PyPI")
    data = json_object(body, "PyPI", "info", "releases")
    info = nested(data["info"], "PyPI", "version")
    releases = data["releases"]
    if not info["version"] or not isinstance(releases, dict):
        raise Unreachable("PyPI answered with an unexpected structure")
    version, latest = fact["version"], info["version"]
    if not releases.get(version):
        return FAIL, "version %s was never published (latest is %s)" % (version, latest)
    if latest == version:
        return PASS, "%s is the latest release" % version
    return DRIFT, "%s exists, the latest release is now %s" % (version, latest)


def check_npm(fact):
    status, body = http_get("https://registry.npmjs.org/" + fact["package"].replace("/", "%2f"))
    if gone(status):
        return FAIL, "package not found on npm"
    require_ok(status, "the npm registry")
    data = json_object(body, "the npm registry", "dist-tags", "versions")
    tags, versions = data["dist-tags"], data["versions"]
    latest = tags.get("latest") if isinstance(tags, dict) else None
    if not latest or not isinstance(versions, dict):
        raise Unreachable("the npm registry answered with an unexpected structure")
    if fact.get("version") and fact["version"] not in versions:
        return FAIL, "version %s was never published (latest is %s)" % (fact["version"], latest)
    return PASS, "published, latest %s" % latest


def resolve_ref(fact):
    if fact["ref"] != "@latest-release":
        return fact["ref"]
    status, body = http_get("https://api.github.com/repos/%s/releases/latest" % fact["repo"])
    require_ok(status, "the latest release lookup")
    tag = json_object(body, "the latest release lookup", "tag_name")["tag_name"]
    if not isinstance(tag, str) or not tag:
        raise Unreachable("the latest release lookup answered without a tag name")
    return tag


def check_github_file(fact):
    ref = resolve_ref(fact)
    url = "https://raw.githubusercontent.com/%s/%s/%s" % (fact["repo"], ref, fact["path"])
    status, body = http_get(url)
    if gone(status):
        return FAIL, "file not found at %s" % ref
    require_ok(status, "raw.githubusercontent.com")
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
    if gone(status):
        return FAIL, "tree not found (the repository or ref is gone)"
    require_ok(status, "the tree listing")
    data = json_object(body, "the tree listing", "tree")
    if not isinstance(data["tree"], list):
        raise Unreachable("the tree listing answered with an unexpected structure")
    if data.get("truncated"):
        return UNREACHABLE, "GitHub truncated the tree listing"
    paths = [nested(entry, "the tree listing", "path")["path"] for entry in data["tree"]]
    missing = [p for p in fact.get("present", []) if p not in paths]
    found = [p for p in fact.get("absent", []) if any(x == p or x.startswith(p if p.endswith("/") else p + "/") for x in paths)]
    if missing or found:
        return FAIL, "missing: %s; present but expected absent: %s" % (missing or "none", found or "none")
    return PASS, "%d paths listed; expected files present, none of %s present" % (len(paths), fact.get("absent", []))


def check_github_path(fact):
    status, body = http_get("https://api.github.com/repos/%s/contents/%s?ref=%s" % (fact["repo"], fact["path"], fact["ref"]))
    if gone(status):
        return FAIL, "path not found"
    require_ok(status, "the contents lookup")
    try:
        data = json.loads(body)
    except ValueError:
        raise Unreachable("the contents lookup answered with text that is not JSON")
    is_file = isinstance(data, dict) and bool(data.get("path"))
    is_folder = isinstance(data, list) and bool(data)
    if not (is_file or is_folder):
        raise Unreachable("the contents lookup answered with an unexpected structure")
    return PASS, "path exists"


def check_github_repo(fact):
    status, body = http_get("https://api.github.com/repos/" + fact["repo"])
    if gone(status):
        return FAIL, "repository not found"
    require_ok(status, "the repository lookup")
    data = json_object(body, "the repository lookup", "full_name")
    if str(data["full_name"]).lower() != fact["repo"].lower():
        return (FAIL if fact.get("stable", True) else DRIFT), "the repository is now called %s" % data["full_name"]
    if data.get("archived"):
        return FAIL, "repository is archived"
    return PASS, "live, last pushed %s" % str(data.get("pushed_at", "?"))[:10]


def check_github_tag(fact):
    base = "https://api.github.com/repos/%s/git/" % fact["repo"]
    status, body = http_get(base + "ref/tags/" + fact["tag"])
    if gone(status):
        return FAIL, "tag not found"
    require_ok(status, "the tag lookup")
    obj = nested(json_object(body, "the tag lookup", "object")["object"], "the tag lookup", "sha", "type")
    sha = obj["sha"]
    if obj["type"] == "tag":
        status, body = http_get(base + "tags/" + sha)
        require_ok(status, "the annotated tag lookup")
        sha = nested(json_object(body, "the annotated tag lookup", "object")["object"], "the annotated tag lookup", "sha")["sha"]
    if sha == fact["sha"]:
        return PASS, "%s resolves to %s" % (fact["tag"], sha[:12])
    return FAIL, "%s resolves to %s, not %s" % (fact["tag"], sha[:12], fact["sha"][:12])


def check_advisory(fact):
    status, body = http_get("https://api.github.com/advisories/" + fact["ghsa"])
    if gone(status):
        return FAIL, "advisory not found"
    require_ok(status, "the advisory lookup")
    data = json_object(body, "the advisory lookup", "ghsa_id")
    if str(data["ghsa_id"]).lower() != fact["ghsa"].lower():
        raise Unreachable("the advisory lookup answered about another advisory")
    summary = data.get("summary") or ""
    if data.get("cve_id") != fact["cve"] or fact["contains"].lower() not in summary.lower():
        return FAIL, "advisory says %s: %s" % (data.get("cve_id"), data.get("summary"))
    return PASS, "%s: %s" % (data["cve_id"], summary[:80])


def check_arxiv(fact):
    status, body = http_get("https://export.arxiv.org/api/query?id_list=" + fact["id_list"])
    require_ok(status, "arXiv")
    match = re.search(r"<entry>.*?<title>(.*?)</title>", body, re.S)
    if not match:
        raise Unreachable("arXiv answered without an entry")
    title = re.sub(r"\s+", " ", match.group(1)).strip()
    if fact["title_contains"].lower() in title.lower():
        return PASS, title[:90]
    return FAIL, "title is '%s'" % title[:90]


def check_page(fact):
    status, body = http_get(fact["url"])
    if gone(status):
        return FAIL, "HTTP %s" % status
    require_ok(status, "the page")
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

COMMON_KEYS = ("id", "claim", "cited_in")
REQUIRED_KEYS = {
    "pypi": ("package", "version"), "npm": ("package",), "github-file": ("repo", "ref", "path", "regex"),
    "github-tree": ("repo", "ref"), "github-path": ("repo", "ref", "path"), "github-repo": ("repo",),
    "github-tag": ("repo", "tag", "sha"), "advisory": ("ghsa", "cve", "contains"),
    "arxiv": ("id_list", "title_contains"), "page": ("url",),
}


def validate_definition(fact):
    """Raise InvalidFact when an entry of facts.json cannot be run, before any network call is made."""
    kind = fact.get("kind")
    if kind not in CHECKS:
        raise InvalidFact("unknown kind %r" % (kind,))
    missing = [key for key in COMMON_KEYS + REQUIRED_KEYS[kind] if key not in fact]
    if missing:
        raise InvalidFact("%s lacks %s" % (kind, ", ".join(missing)))
    if kind == "page" and not (fact.get("all") or fact.get("segment")):
        raise InvalidFact("a page fact checks nothing without 'all' or 'segment'")
    patterns = list(fact.get("all", [])) + [p for p in (fact.get("regex"), fact.get("show")) if p]
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise InvalidFact("a pattern does not compile (%s)" % exc)


def run(facts, pause=0.3):
    results = []
    for fact in facts:
        try:
            validate_definition(fact)
            status, evidence = CHECKS[fact["kind"]](fact)
        except Unreachable as exc:
            status, evidence = UNREACHABLE, str(exc)
        except InvalidFact as exc:
            status, evidence = FAIL, "invalid fact definition: %s" % exc
        except Exception as exc:
            # Answers from sources are validated where they are read, so reaching this means a defect in the checker.
            status, evidence = FAIL, "the checker crashed (%s: %s)" % (type(exc).__name__, str(exc)[:80])
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
        cells = [status, "`%s`" % fact.get("id", "?"), fact.get("claim", "?"), fact.get("cited_in", "?"), evidence]
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
        facts = [f for f in facts if f.get("id") in wanted]
    results = run(facts)
    for status, fact, evidence in results:
        print("%-12s %-40s %s" % (status, fact.get("id", "?"), evidence))
    counts = {s: sum(1 for r in results if r[0] == s) for s in (PASS, DRIFT, FAIL, UNREACHABLE)}
    print("\n%d PASS, %d DRIFT, %d FAIL, %d UNREACHABLE" % (counts[PASS], counts[DRIFT], counts[FAIL], counts[UNREACHABLE]))
    if args.write:
        args.write.write_text(render_markdown(results), encoding="utf-8")
        print("wrote %s" % args.write)
    bad = counts[FAIL] + (counts[DRIFT] + counts[UNREACHABLE] if args.strict else 0)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
