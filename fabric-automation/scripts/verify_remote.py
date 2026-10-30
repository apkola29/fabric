#!/usr/bin/env python3
"""Check that a folder of the repository matches the local folder, on GitHub or in a commit that is not pushed yet.

Compares the Git blob hash of every file that would be published (line endings
normalised to LF, as Git stores them) with the blob hash held at the same path,
and reports missing, extra and different files. By default the other side is
the repository on GitHub, which needs the GitHub CLI (gh) signed in to an
account that can read it. With --clone and --commit the other side is that
commit in a local clone, so the publish script can prove that a commit holds
exactly the validated files before it pushes anything. Standard library only.

Exit status is 1 when anything differs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_docs import publishable_files  # noqa: E402


def gh_json(*args):
    proc = subprocess.run(["gh", "api", *args], capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise SystemExit("gh api %s failed: %s" % (" ".join(args), proc.stderr.strip()[:300]))
    return json.loads(proc.stdout)


def blob_sha(data):
    if b"\x00" not in data:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()


def local_files(folder):
    """{path: blob hash} of every file the validator has to read and the publish script would copy."""
    folder = Path(folder)
    return {rel: blob_sha((folder / rel).read_bytes()) for rel in publishable_files(folder)}


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


def git_run(clone, *args, check=True):
    proc = subprocess.run(["git", "-C", str(clone), *args], capture_output=True)
    if check and proc.returncode != 0:
        raise SystemExit("git %s failed: %s" % (args[0], proc.stderr.decode("utf-8", "replace").strip()[:300]))
    return proc


def commit_tree(clone, commit, remote_path):
    """{path under remote_path: blob hash} for a commit in a local clone, or None when the folder is not in it."""
    if git_run(clone, "cat-file", "-e", "%s:%s" % (commit, remote_path), check=False).returncode != 0:
        return None
    listing = git_run(clone, "ls-tree", "-r", "-z", "%s:%s" % (commit, remote_path)).stdout.decode("utf-8")
    tree = {}
    for entry in listing.split("\0"):
        if entry:
            meta, _, path = entry.partition("\t")
            _mode, kind, sha = meta.split()
            if kind == "blob":
                tree[path] = sha
    return tree


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default="apkola29/fabric")
    parser.add_argument("--ref", default="master")
    parser.add_argument("--remote-path", default="fabric-automation")
    parser.add_argument("--local", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--extra", action="append", default=[],
                        help="REMOTE=LOCAL pair for a file kept outside the folder, for example "
                             ".github/workflows/x.yml=ci/x.yml (LOCAL is relative to --local)")
    parser.add_argument("--clone", type=Path,
                        help="compare with a commit in this local clone instead of GitHub, before anything is pushed (needs --commit)")
    parser.add_argument("--commit", help="the commit to check. On GitHub it must be the head of the ref")
    args = parser.parse_args(argv)

    problems = 0
    if args.clone:
        if not args.commit:
            parser.error("--clone needs --commit")
        commit = git_run(args.clone, "rev-parse", "--verify", args.commit + "^{commit}").stdout.decode("utf-8").strip()
        print("checking commit %s in the local clone, which is not pushed yet" % commit[:10])
        remote = commit_tree(args.clone, commit, args.remote_path)
        where = "the commit"

        def blob_of(path):
            proc = git_run(args.clone, "rev-parse", "--verify", "--quiet", "%s:%s" % (commit, path), check=False)
            return proc.stdout.decode("utf-8").strip() if proc.returncode == 0 else ""
    else:
        head = gh_json("repos/%s/commits/%s" % (args.repo, args.ref))
        commit = head["sha"]
        print("head of %s on %s: %s %s" % (args.ref, args.repo, commit[:10], head["commit"]["message"].splitlines()[0][:70]))
        if args.commit and not commit.startswith(args.commit):
            print("MISMATCH head is %s, expected %s" % (commit[:10], args.commit[:10]))
            problems += 1
        remote = remote_tree(args.repo, commit, args.remote_path)
        where = args.ref

        def blob_of(path):
            proc = subprocess.run(["gh", "api", "repos/%s/contents/%s?ref=%s" % (args.repo, path, commit), "--jq", ".sha"],
                                  capture_output=True, text=True, encoding="utf-8")
            return proc.stdout.strip() if proc.returncode == 0 else ""

    if remote is None:
        print("MISSING the folder %s does not exist on %s" % (args.remote_path, where))
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
        remote_sha = blob_of(remote_rel)
        if not remote_sha:
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
