"""Mutation harness: python mutate.py SPEC.json

SPEC: {"project": DIR, "tests": ["scripts.test_x.Class", ...],
       "mutations": [{"id": "m1", "file": "scripts/toolchain.py", "old": "text", "new": "text"}, ...]}

The project's scripts, toolchain and .github folders are copied once. Each mutation replaces the text `old`
(which must occur exactly once; "\n" in the spec is written as CRLF when the file uses CRLF) with `new`, runs the tests,
and puts the file back. KILLED = some test failed or errored; SURVIVED = all passed.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


def run_tests(cwd, tests, timeout):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    done = subprocess.run([sys.executable, "-B", "-m", "unittest", *tests], cwd=cwd, env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)
    text = (done.stderr or "") + (done.stdout or "")
    failed = re.findall(r"^(?:FAIL|ERROR): (\S+)", text, re.MULTILINE)
    ran = re.search(r"^Ran (\d+) tests?", text, re.MULTILINE)
    return done.returncode, failed, int(ran.group(1)) if ran else 0, text


def main(argv):
    spec = json.load(open(argv[0], encoding="utf-8"))
    timeout = int(spec.get("timeout", 900))
    scratch = tempfile.mkdtemp(prefix="fa-mut-")
    try:
        work = os.path.join(scratch, "project")
        os.makedirs(work)
        for folder in ("scripts", "toolchain", ".github", ".vscode", "verification"):
            src = os.path.join(spec["project"], folder)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(work, folder), ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
            if os.path.isfile(os.path.join(spec["project"], name)):
                shutil.copy2(os.path.join(spec["project"], name), work)
        code, failed, ran, text = run_tests(work, spec["tests"], timeout)
        print("baseline: %d test(s), %s" % (ran, "OK" if code == 0 else "FAILED " + ", ".join(failed[:5])))
        if code != 0:
            print(text[-1500:])
            return 2
        killed = 0
        for mutation in spec["mutations"]:
            path = os.path.join(work, *mutation["file"].split("/"))
            raw = open(path, "rb").read()
            text_in = raw.decode("utf-8")
            crlf = "\r\n" in text_in
            old, new = mutation["old"], mutation["new"]
            if crlf:
                old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
            count = text_in.count(old)
            if count != 1:
                print("%-8s ERROR   the old text occurs %d times" % (mutation["id"], count))
                continue
            open(path, "wb").write(text_in.replace(old, new).encode("utf-8"))
            try:
                code, failed, ran, text = run_tests(work, spec["tests"], timeout)
            finally:
                open(path, "wb").write(raw)
            if code != 0:
                killed += 1
                shown = ", ".join(name.split(".")[-1] for name in failed[:2]) or "(error)"
                print("%-8s KILLED  by %s%s" % (mutation["id"], shown, " (+%d)" % (len(failed) - 2) if len(failed) > 2 else ""))
            else:
                print("%-8s SURVIVED  all %d test(s) passed" % (mutation["id"], ran))
            sys.stdout.flush()
        print("%d of %d mutation(s) killed" % (killed, len(spec["mutations"])))
        return 0 if killed == len(spec["mutations"]) else 1
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
