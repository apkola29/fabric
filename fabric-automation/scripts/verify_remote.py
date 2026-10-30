#!/usr/bin/env python3
"""Check that a folder of the repository on GitHub matches the local folder.

Compares the Git blob hash of every local file (line endings normalised to LF,
as Git stores them) with the blob hash GitHub holds at the same path, and
reports missing, extra and different files. Needs the GitHub CLI (gh), signed
in to an account that can read the repository. Standard library only.

Exit status is 1 when anything differs.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {"private", "__pycache__", ".pytest_cache", ".git"}
SKIP_PATHS = ("docs/research/local",)


def gh_json(*args):
    proc = subprocess.run(["gh", "api", *args], capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise SystemExit("gh api %s failed: %s" % (" ".join(args), proc.stderr.strip()[:300]))
    return json.loads(proc.stdout)


def blob_sha(data):
    if b"\x00" not in data:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()


def ignore_rules(folder):
    rules = []
    path = folder / ".gitignore"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("!"):
                rules.append(line)
    return rules


def is_ignored(rel, rules):
    parts = rel.split("/")
    for rule in rules:
        if rule.endswith("/"):
            name = rule.rstrip("/")
            if "/" in name:
                if rel == name or rel.startswith(name + "/"):
                    return True
            elif name in parts[:-1]:
                return True
        elif fnmatch.fnmatch(parts[-1], rule) or fnmatch.fnmatch(rel, rule):
            return True
    return False


def local_files(folder):
    rules = ignore_rules(folder)
    out = {}
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(folder).as_posix()
        if any(part in SKIP_DIRS for part in rel.split("/")[:-1]):
            continue
        if any(rel == p or rel.startswith(p + "/") for p in SKIP_PATHS):
            continue
        if path.suffix == ".pyc" or is_ignored(rel, rules):
            continue
        out[rel] = blob_sha(path.read_bytes())
    return out


def remote_tree(repo, commit, remote_path):
    sha = commit
    for segment in [s for s in remote_path.split("/") if s]:
        listing = gh_json("repos/%s/git/trees/%s" % (repo, sha))
        match = next((e for e in listing["tree"] if e["path"] == segment and e["type"] == "tree"), None)
        if match is None:
            return None
        sha = match["sha"]
    full = gh_json("repos/%s/git/trees/%s?recursive=1" % (repo, sha))
    if full.get("truncated"):
        raise SystemExit("GitHub truncated the tree listing; cannot verify")
    return {e["path"]: e["sha"] for e in full["tree"] if e["type"] == "blob"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default="apkola29/fabric")
    parser.add_argument("--ref", default="master")
    parser.add_argument("--remote-path", default="fabric-automation")
    parser.add_argument("--local", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--extra", action="append", default=[],
                        help="REMOTE=LOCAL pair for a file kept outside the folder, for example "
                             ".github/workflows/x.yml=ci/x.yml (LOCAL is relative to --local)")
    parser.add_argument("--commit", help="expect this commit to be the head of the ref")
    args = parser.parse_args(argv)

    head = gh_json("repos/%s/commits/%s" % (args.repo, args.ref))
    commit = head["sha"]
    print("head of %s on %s: %s %s" % (args.ref, args.repo, commit[:10], head["commit"]["message"].splitlines()[0][:70]))
    problems = 0
    if args.commit and not commit.startswith(args.commit):
        print("MISMATCH head is %s, expected %s" % (commit[:10], args.commit[:10]))
        problems += 1

    remote = remote_tree(args.repo, commit, args.remote_path)
    if remote is None:
        print("MISSING the folder %s does not exist on %s" % (args.remote_path, args.ref))
        return 1
    local = local_files(args.local)
    same = 0
    for rel in sorted(set(local) | set(remote)):
        if rel not in remote:
            print("MISSING-REMOTE %s" % rel)
            problems += 1
        elif rel not in local:
            print("EXTRA-REMOTE   %s" % rel)
            problems += 1
        elif local[rel] != remote[rel]:
            print("DIFFERENT      %s local %s remote %s" % (rel, local[rel][:10], remote[rel][:10]))
            problems += 1
        else:
            same += 1
    extras = 0
    for pair in args.extra:
        remote_rel, _, local_rel = pair.partition("=")
        local_file = args.local / local_rel
        if not local_file.exists():
            print("MISSING-LOCAL  %s" % local_rel)
            problems += 1
            continue
        proc = subprocess.run(["gh", "api", "repos/%s/contents/%s?ref=%s" % (args.repo, remote_rel, commit), "--jq", ".sha"],
                              capture_output=True, text=True, encoding="utf-8")
        remote_sha = proc.stdout.strip()
        if proc.returncode != 0 or not remote_sha:
            print("MISSING-REMOTE %s" % remote_rel)
            problems += 1
        elif remote_sha != blob_sha(local_file.read_bytes()):
            print("DIFFERENT      %s" % remote_rel)
            problems += 1
        else:
            extras += 1
    print("%d file(s) identical in %s, %d managed file(s) identical, %d problem(s)" % (same, args.remote_path, extras, problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
