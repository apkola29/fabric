#!/usr/bin/env python3
"""Tests for toolchain_sources.py: directory and git digests, skill lint, git and package resolvers, and vendoring a pinned pack.

Git is real. A small repository is built once with `git fast-import` in a temp folder and used through file:// URLs, with the
user's and the system's git configuration switched off. The package resolvers run against a fake runner that answers from a
table, so no network and no npm are used. Run from the project folder:

    python -m unittest scripts.test_toolchain_sources -v
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import toolchain_io  # noqa: E402
import toolchain_sources as ts  # noqa: E402
from toolchain_io import CommandResult, HttpResult  # noqa: E402

WINDOWS = os.name == "nt"
ADDRESS = "tester" + "@" + "example.test"
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}
HAS_GIT = shutil.which("git") is not None


class IsolatedRunner(toolchain_io.SystemRunner):
    """The real runner, with git cut off from the user's configuration. It records every call."""

    def __init__(self):
        self.calls = []

    def run_bytes(self, argv, *, cwd=None, env=None, timeout=60, input=None):
        self.calls.append((list(argv), dict(env or {})))
        merged = dict(GIT_ENV)
        merged.update(env or {})
        return super().run_bytes(argv, cwd=cwd, env=merged, timeout=timeout, input=input)

    def argvs(self):
        return [call[0] for call in self.calls]


def spec_digest(files):
    """The digest of a tree, written from the specification and independent of the module: {relative path: bytes}."""
    outer = hashlib.sha256()
    total = 0
    for rel in sorted(files, key=lambda name: name.encode("utf-8")):
        data = files[rel]
        if b"\x00" not in data:
            data = data.replace(b"\r\n", b"\n")
        outer.update(rel.encode("utf-8") + b"\x00" + hashlib.sha256(data).digest())
        total += len(data)
    return {"digest": "sha256:" + outer.hexdigest(), "files": len(files), "bytes": total}


def write_tree(root, files):
    for rel, data in files.items():
        path = Path(root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))


SKILL_GOOD = (
    "---\n"
    "name: good-skill\n"
    "description: >\n"
    "  Does a good thing.\n"
    "  Use it when testing.\n"
    "metadata:\n"
    "  author: tester\n"
    "  version: \"1.0\"\n"
    "---\n"
    "# Good skill\n"
    "Run `pip install demo-package` first.\n"
)
GOOD_DESCRIPTION = "Does a good thing. Use it when testing."
GOOD_FILES = {
    "SKILL.md": SKILL_GOOD.encode("utf-8"),
    "references/guide.md": b"Use `brew install thing` when needed.\n",
    "references/crlf.txt": b"one\r\ntwo\r\n",
    "references/legacy.txt": b"caf\xe9\nsecond line\n",
    "scripts/run.sh": b"#!/bin/sh\nnpx -y some-tool\n",
    "assets/blob.bin": b"\x00\x01\r\n\x02\xff\r\n",
}
LINK_SKILL_MD = b"---\nname: link-skill\ndescription: Has a link.\n---\n# Link\n"
BAD_SKILL_MD = ("---\nname: other-name\ndescription: " + "x" * 1025 + "\n---\n# Bad\n").encode("utf-8")
GAMMA_SKILL_MD = b"---\nname: good-skill\ndescription: A different one.\n---\n# Gamma\n"


def alpha_files(version):
    files = {"plugins/alpha/.claude-plugin/plugin.json": ('{"name": "alpha", "version": "%s"}\n' % version).encode("utf-8")}
    for rel, data in GOOD_FILES.items():
        files["plugins/alpha/skills/good-skill/" + rel] = data
    return files


def beta_files():
    files = {"plugins/beta/skills/other-skill/SKILL.md": b"---\nname: other-skill\ndescription: Another.\n---\n# Other\n"}
    for rel, data in GOOD_FILES.items():
        files["plugins/beta/skills/good-skill/" + rel] = data
    return files


def final_files():
    files = alpha_files("1.2.0")
    files.update(beta_files())
    files.update({
        "plugins/alpha/.mcp.json": b'{"mcpServers": {"zeta-server": {"command": "z"}, "Alpha-Server": {"command": "a"}}}\n',
        "plugins/alpha/agents/Helper.agent.md": b"# Helper\n",
        "plugins/alpha/agents/notes.txt": b"not an agent\n",
        "plugins/alpha/skills/link-skill/SKILL.md": LINK_SKILL_MD,
        "plugins/alpha/skills/link-skill/current": ("120000", b"SKILL.md"),
        "plugins/alpha/skills/bad-skill/SKILL.md": BAD_SKILL_MD,
        "plugins/alpha/skills/no-skill-md/readme.txt": b"no skill here\n",
        "plugins/gamma/skills/good-skill/SKILL.md": GAMMA_SKILL_MD,
        "plugins/delta/README.md": b"# no skills\n",
        "plugins/epsilon/skills/with-module/SKILL.md": b"---\nname: with-module\ndescription: Has a submodule.\n---\n# Module\n",
        "plugins/epsilon/skills/with-module/vendor": ("160000", b"ab" * 20),
        "plugins/beta/skills/good-skill/scripts/run.sh": ("100755", GOOD_FILES["scripts/run.sh"]),
    })
    files["plugins/alpha/skills/good-skill/scripts/run.sh"] = ("100755", GOOD_FILES["scripts/run.sh"])
    return files


def _data(content):
    return b"data %d\n%s\n" % (len(content), content)


def _commit(mark, parent, files, message):
    out = [b"commit refs/heads/main\nmark :%d\n" % mark,
           b"author Tester <%s> 1700000000 +0000\ncommitter Tester <%s> 1700000000 +0000\n" % (ADDRESS.encode(), ADDRESS.encode()),
           _data(message.encode("utf-8"))]
    if parent:
        out.append(b"from :%d\n" % parent)
    out.append(b"deleteall\n")
    for path, value in sorted(files.items()):
        mode, content = value if isinstance(value, tuple) else ("100644", value)
        if mode == "160000":
            out.append(b"M 160000 %s %s\n" % (content, path.encode("utf-8")))
            continue
        out.append(b"M %s inline %s\n" % (mode.encode(), path.encode("utf-8")))
        out.append(_data(content))
    return b"".join(out)


def _tag(name, mark, annotated):
    if not annotated:
        return b"reset refs/tags/%s\nfrom :%d\n\n" % (name.encode(), mark)
    return (b"tag %s\nfrom :%d\ntagger Tester <%s> 1700000100 +0000\n" % (name.encode(), mark, ADDRESS.encode())) + _data(b"release " + name.encode())


class Fixture:
    """A bare repository with three commits, tags of every kind and two branches."""

    def __init__(self, base):
        self.base = Path(base)
        self.git_dir = self.base / "fixture.git"
        self.url = self.git_dir.as_uri()
        self.runner = IsolatedRunner()
        self.git("init", "--bare", "--quiet", str(self.git_dir), use_dir=False)
        self.git("config", "uploadpack.allowAnySHA1InWant", "true")
        c1 = dict(alpha_files("1.0.0"))
        c1["plugins/alpha/skills/good-skill/SKILL.md"] = SKILL_GOOD.replace("Does a good thing.", "Did a good thing.").encode("utf-8")
        c2 = dict(c1)
        c2.update(beta_files())
        stream = [_commit(1, None, c1, "first"), _commit(2, 1, c2, "second"), _commit(3, 2, final_files(), "third")]
        stream += [b"reset refs/heads/dev\nfrom :2\n\n", _tag("v1.0.0", 1, False), _tag("v1.2.0", 2, True), _tag("v1.9.0", 2, False),
                   _tag("v1.10.0", 3, True), _tag("v2.0.0-rc1", 3, False), _tag("latest", 1, False), _tag("release-2", 1, False)]
        marks = self.base / "marks.txt"
        self.git("fast-import", "--quiet", "--export-marks=" + str(marks), input=b"".join(stream))
        self.git("symbolic-ref", "HEAD", "refs/heads/main")
        self.commits = {int(line.split()[0][1:]): line.split()[1] for line in marks.read_text().splitlines()}

    def git(self, *args, input=None, use_dir=True, cwd=None):
        argv = ["git"] + (["--git-dir", str(self.git_dir)] if use_dir else []) + list(args)
        raw = self.runner.run_bytes(argv, input=input, cwd=cwd)
        if raw.returncode != 0:
            raise AssertionError("git %s failed: %s" % (args[0], raw.stderr.decode("utf-8", "replace")))
        return raw.stdout.decode("utf-8", "replace").strip()

    def clone(self, dest, autocrlf, commit=None):
        argv = ["git", "-c", "core.autocrlf=" + autocrlf, "-c", "protocol.file.allow=always", "clone", "--quiet", self.url, str(dest)]
        raw = self.runner.run_bytes(argv)
        if raw.returncode != 0:
            raise AssertionError("clone failed: " + raw.stderr.decode("utf-8", "replace"))
        if commit:
            checkout = self.runner.run_bytes(["git", "-c", "core.autocrlf=" + autocrlf, "checkout", "--quiet", commit], cwd=str(dest))
            if checkout.returncode != 0:
                raise AssertionError("checkout failed")


FX = None
TMP = None


def setUpModule():
    global FX, TMP
    if HAS_GIT:
        TMP = tempfile.TemporaryDirectory()
        FX = Fixture(TMP.name)


def tearDownModule():
    if TMP is not None:
        TMP.cleanup()


def lock_for(fx, runner, plugins=("alpha", "beta", "gamma", "delta"), tag="v1.10.0"):
    commit = fx.commits[3]
    built = {}
    for name in plugins:
        path = "plugins/" + name
        built[name] = dict(ts.read_plugin(fx.git_dir, commit, path, runner), path=path)
    return {"schema": 1, "inputs_digest": "sha256:" + "a" * 64,
            "skill_sources": {"fx": {"repo": fx.url, "tag": tag, "commit": commit, "plugins": built}}}


class DigestTreeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "skill"

    def test_matches_the_formula_of_the_specification(self):
        files = {"SKILL.md": b"# x\nline\n", "b/z.txt": b"z\n", "a.txt": b"a\n", "assets/blob.bin": b"\x00\x01\r\n"}
        write_tree(self.root, files)
        result = ts.digest_tree(self.root)
        self.assertEqual(spec_digest(files), result)
        self.assertEqual(set(result), {"digest", "files", "bytes"})
        self.assertRegex(result["digest"], r"^sha256:[0-9a-f]{64}$")

    def test_crlf_and_lf_text_give_the_same_digest(self):
        write_tree(self.root, {"SKILL.md": b"a\nb\n", "x/y.txt": b"1\n2\n"})
        lf = ts.digest_tree(self.root)
        write_tree(self.root, {"SKILL.md": b"a\r\nb\r\n", "x/y.txt": b"1\r\n2\r\n"})
        crlf = ts.digest_tree(self.root)
        self.assertEqual(lf, crlf)

    def test_text_that_is_not_utf8_is_still_text(self):
        write_tree(self.root, {"legacy.txt": b"caf\xe9\nline\n"})
        lf = ts.digest_tree(self.root)
        write_tree(self.root, {"legacy.txt": b"caf\xe9\r\nline\r\n"})
        self.assertEqual(lf, ts.digest_tree(self.root))

    def test_binary_content_is_hashed_as_it_is(self):
        write_tree(self.root, {"blob.bin": b"\x00\r\n\x01"})
        first = ts.digest_tree(self.root)
        write_tree(self.root, {"blob.bin": b"\x00\n\x01"})
        self.assertNotEqual(first["digest"], ts.digest_tree(self.root)["digest"])
        self.assertEqual(4, first["bytes"])

    def test_a_lone_carriage_return_is_kept(self):
        write_tree(self.root, {"a.txt": b"a\rb\n"})
        first = ts.digest_tree(self.root)
        write_tree(self.root, {"a.txt": b"a\nb\n"})
        self.assertNotEqual(first["digest"], ts.digest_tree(self.root)["digest"])

    def test_the_path_and_the_content_both_count(self):
        write_tree(self.root, {"a.txt": b"same\n"})
        one = ts.digest_tree(self.root)["digest"]
        shutil.rmtree(self.root)
        write_tree(self.root, {"b.txt": b"same\n"})
        two = ts.digest_tree(self.root)["digest"]
        shutil.rmtree(self.root)
        write_tree(self.root, {"a.txt": b"other\n"})
        three = ts.digest_tree(self.root)["digest"]
        self.assertEqual(3, len({one, two, three}))

    def test_a_split_between_path_and_content_cannot_be_forged(self):
        write_tree(self.root, {"a": b"b\x00c"})
        one = ts.digest_tree(self.root)["digest"]
        shutil.rmtree(self.root)
        write_tree(self.root, {"ab": b"\x00c"})
        self.assertNotEqual(one, ts.digest_tree(self.root)["digest"])

    def test_the_order_of_creation_does_not_matter(self):
        files = {"z.txt": b"z", "a/b.txt": b"b", "a.txt": b"a", "\u00e9.txt": b"e"}
        write_tree(self.root, dict(reversed(list(files.items()))))
        self.assertEqual(spec_digest(files), ts.digest_tree(self.root))

    def test_a_top_level_git_folder_is_skipped_but_a_nested_one_is_not(self):
        write_tree(self.root, {"SKILL.md": b"x\n"})
        plain = ts.digest_tree(self.root)
        write_tree(self.root, {".git/config": b"[core]\n", ".git/HEAD": b"ref\n"})
        self.assertEqual(plain, ts.digest_tree(self.root))
        write_tree(self.root, {"sub/.git/config": b"[core]\n"})
        self.assertEqual(2, ts.digest_tree(self.root)["files"])

    def test_empty_folders_do_not_count(self):
        write_tree(self.root, {"SKILL.md": b"x\n"})
        plain = ts.digest_tree(self.root)
        (self.root / "empty" / "deeper").mkdir(parents=True)
        self.assertEqual(plain, ts.digest_tree(self.root))

    def test_file_modes_are_ignored(self):
        write_tree(self.root, {"run.sh": b"#!/bin/sh\n"})
        before = ts.digest_tree(self.root)
        os.chmod(self.root / "run.sh", 0o755)
        self.assertEqual(before, ts.digest_tree(self.root))

    def test_a_symbolic_link_counts_as_a_file_holding_its_target(self):
        write_tree(self.root, {"SKILL.md": b"x\n"})
        try:
            os.symlink("SKILL.md", self.root / "current")
        except (OSError, NotImplementedError):
            self.skipTest("this account cannot create symbolic links")
        self.assertEqual(spec_digest({"SKILL.md": b"x\n", "current": b"SKILL.md"}), ts.digest_tree(self.root))

    def test_a_missing_folder_is_a_source_error(self):
        with self.assertRaises(ts.SourceError) as caught:
            ts.digest_tree(Path(self.tmp.name) / "missing")
        self.assertEqual("unresolved", caught.exception.code)

    def test_a_link_entry_is_hashed_as_its_target_even_without_the_privilege_to_make_links(self):
        write_tree(self.root, {"SKILL.md": b"x\n"})
        entries = [("SKILL.md", str(self.root / "SKILL.md"), False), ("current", str(self.root / "SKILL.md"), True)]
        with mock.patch.object(ts, "_walk", return_value=iter(entries)), mock.patch.object(os, "readlink", return_value="SKILL.md"):
            result = ts.digest_tree(self.root)
        self.assertEqual(spec_digest({"SKILL.md": b"x\n", "current": b"SKILL.md"}), result)

    def test_the_paths_a_skill_may_be_written_to(self):
        for good in ("SKILL.md", "references/guide.md", ".gitignore", "a/b/c.txt", "scripts/run.sh"):
            self.assertEqual(good.split("/"), ts._file_parts(good))
        for bad in ("../x", "a/../b", "a//b", ".git/config", "a/.GIT/x", "a:b", "a\\b", "CON.txt", "a/nul", "x.", "x /y", "a/b*", "", "a/\x01"):
            with self.assertRaises(ts.SourceError, msg=repr(bad)):
                ts._file_parts(bad)


@unittest.skipUnless(HAS_GIT, "git is not installed")
class GitDigestTests(unittest.TestCase):
    SKILL = "plugins/alpha/skills/good-skill"

    def setUp(self):
        self.runner = IsolatedRunner()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def git_digest(self, subpath=None, commit=None):
        return ts.digest_git_tree(FX.git_dir, commit or FX.commits[3], subpath or self.SKILL, self.runner)

    def test_matches_the_formula_of_the_specification(self):
        self.assertEqual(spec_digest(GOOD_FILES), self.git_digest())

    def test_equals_the_digest_of_a_checkout_with_lf_and_with_crlf(self):
        results = {}
        for mode in ("false", "true"):
            dest = Path(self.tmp.name) / ("checkout-" + mode)
            FX.clone(dest, mode)
            skill = dest / self.SKILL
            results[mode] = ts.digest_tree(skill)
            raw = (skill / "SKILL.md").read_bytes()
            self.assertEqual(mode == "true", b"\r\n" in raw, "the checkout did not have the expected line endings")
            self.assertEqual(b"\x00\x01\r\n\x02\xff\r\n", (skill / "assets" / "blob.bin").read_bytes())
        git = self.git_digest()
        self.assertEqual(git, results["false"])
        self.assertEqual(git, results["true"])

    def test_a_blob_that_stores_crlf_gives_the_same_digest_as_a_checkout(self):
        dest = Path(self.tmp.name) / "crlf-blob"
        FX.clone(dest, "false")
        self.assertEqual(b"one\r\ntwo\r\n", (dest / self.SKILL / "references" / "crlf.txt").read_bytes())
        self.assertEqual(ts.digest_tree(dest / self.SKILL), self.git_digest())

    def test_a_link_in_git_equals_the_file_that_a_checkout_without_links_leaves(self):
        link = "plugins/alpha/skills/link-skill"
        expected = spec_digest({"SKILL.md": LINK_SKILL_MD, "current": b"SKILL.md"})
        self.assertEqual(expected, self.git_digest(link))
        dest = Path(self.tmp.name) / "plain"
        write_tree(dest, {"SKILL.md": LINK_SKILL_MD, "current": b"SKILL.md"})
        self.assertEqual(expected, ts.digest_tree(dest))

    def test_the_digest_follows_the_commit(self):
        old = self.git_digest(commit=FX.commits[1])
        self.assertNotEqual(old["digest"], self.git_digest()["digest"])

    def test_an_unknown_path_or_a_file_instead_of_a_folder_is_a_source_error(self):
        for subpath in ("plugins/alpha/skills/nothing", self.SKILL + "/SKILL.md"):
            with self.assertRaises(ts.SourceError) as caught:
                self.git_digest(subpath)
            self.assertEqual("unresolved", caught.exception.code)

    def test_bad_commit_and_path_values_are_refused_before_git_runs(self):
        for commit in ("main", "--output=x", "abc123", "g" * 40, ""):
            with self.assertRaises(ts.SourceError):
                ts.digest_git_tree(FX.git_dir, commit, self.SKILL, self.runner)
        for subpath in ("../x", "a/../b", "/abs", "a\\b"):
            with self.assertRaises(ts.SourceError):
                ts.digest_git_tree(FX.git_dir, FX.commits[3], subpath, self.runner)
        self.assertEqual([], self.runner.calls)

    def test_a_tree_that_is_too_large_is_refused(self):
        old = ts.MAX_TREE_BYTES
        ts.MAX_TREE_BYTES = 10
        try:
            with self.assertRaises(ts.SourceError) as caught:
                self.git_digest()
        finally:
            ts.MAX_TREE_BYTES = old
        self.assertEqual("unresolved", caught.exception.code)

    def test_a_submodule_inside_a_skill_is_refused_rather_than_left_out(self):
        with self.assertRaises(ts.SourceError) as caught:
            self.git_digest("plugins/epsilon/skills/with-module")
        self.assertEqual("unresolved", caught.exception.code)
        self.assertIn("submodule", str(caught.exception))


class LintTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def lint(self, skill_md, name="demo-skill", extra=None):
        root = Path(self.tmp.name) / name
        shutil.rmtree(root, ignore_errors=True)
        files = dict(extra or {})
        if skill_md is not None:
            files["SKILL.md"] = skill_md
        write_tree(root, files if files else {"keep.txt": b"x"})
        return ts.lint_skill(root)

    def check_description(self, front, expected, name="demo-skill"):
        result = self.lint("---\nname: %s\n%s---\nbody\n" % (name, front))
        self.assertTrue(result["frontmatter_ok"], result)
        self.assertEqual([], result["findings"])
        self.assertEqual(len(expected), result["description_chars"], result)

    def test_a_good_skill(self):
        result = self.lint(SKILL_GOOD, name="good-skill")
        self.assertEqual({"name", "name_ok", "description_chars", "frontmatter_ok", "install_hints", "findings"}, set(result))
        self.assertEqual("good-skill", result["name"])
        self.assertTrue(result["name_ok"])
        self.assertTrue(result["frontmatter_ok"])
        self.assertEqual(len(GOOD_DESCRIPTION), result["description_chars"])
        self.assertEqual(1, result["install_hints"])
        self.assertEqual([], result["findings"])

    def test_plain_scalars(self):
        self.check_description("description: Plain text with a colon:inside and a hash#inside\n", "Plain text with a colon:inside and a hash#inside")
        self.check_description("description: first part: second part\n", "first part: second part")
        self.check_description("description: Text # a trailing comment\n", "Text")

    def test_double_quoted_scalars_and_their_escapes(self):
        self.check_description('description: "Say \\"hi\\" \\\\ \\u00e9 \\x41 \\t end"\n', 'Say "hi" \\ \u00e9 A \t end')
        self.check_description('description: "kept # not a comment"\n', "kept # not a comment")
        self.check_description('description: "tail"  # comment\n', "tail")

    def test_single_quoted_scalars(self):
        self.check_description("description: 'It''s fine: really'\n", "It's fine: really")

    def test_folded_and_literal_blocks(self):
        self.check_description("description: >\n  one\n  two\n\n  three\n", "one two\nthree")
        self.check_description("description: >-\n  one\n  two\n", "one two")
        self.check_description("description: |\n  one\n  two\n", "one\ntwo")
        self.check_description("description: |-\n    indented\n    more\n", "indented\nmore")
        self.check_description("description: >2\n  keep\n  this\n", "keep this")

    def test_multi_line_plain_and_quoted_scalars_are_folded(self):
        self.check_description("description: first line\n  second line\n", "first line second line")
        self.check_description("description:\n  on the next line\n", "on the next line")
        self.check_description('description: "first\n  second"\n', "first second")

    def test_nested_keys_never_stand_in_for_the_top_level_ones(self):
        front = "metadata:\n  description: not this one\n  name: nor this\ndescription: the real one\n"
        self.check_description(front, "the real one")
        self.check_description("allowed-tools:\n  - a\n  - b\ntags:\n- x\ndescription: after lists\n", "after lists")
        self.check_description("metadata: {author: x, version: 1}\ndescription: after a flow map\n", "after a flow map")

    def test_the_key_order_does_not_matter(self):
        result = self.lint("---\ndescription: first\nname: demo-skill\n---\n")
        self.assertTrue(result["name_ok"])
        self.assertEqual(5, result["description_chars"])

    def test_crlf_files_and_a_byte_order_mark(self):
        text = "---\r\nname: demo-skill\r\ndescription: >\r\n  one\r\n  two\r\n---\r\nbody\r\n"
        result = self.lint(text.encode("utf-8"))
        self.assertEqual([], result["findings"])
        self.assertEqual(len("one two"), result["description_chars"])
        result = self.lint(b"\xef\xbb\xbf" + text.encode("utf-8"))
        self.assertEqual([], result["findings"])

    def test_the_limit_of_1024_characters(self):
        ok = self.lint("---\nname: demo-skill\ndescription: %s\n---\n" % ("x" * 1024))
        self.assertEqual([], ok["findings"])
        self.assertEqual(1024, ok["description_chars"])
        long = self.lint("---\nname: demo-skill\ndescription: %s\n---\n" % ("x" * 1025))
        self.assertEqual(["description longer than 1024 characters"], long["findings"])
        self.assertEqual(1025, long["description_chars"])

    def test_a_name_that_does_not_match_the_folder(self):
        result = self.lint("---\nname: other-name\ndescription: d\n---\n")
        self.assertFalse(result["name_ok"])
        self.assertEqual("other-name", result["name"])
        self.assertEqual(["name does not match folder"], result["findings"])

    def test_name_rules(self):
        cases = {"Upper-Case": "name must use lower-case letters, digits and hyphens", "with_underscore": "name must use lower-case letters, digits and hyphens",
                 "-leading": "name must use lower-case letters, digits and hyphens", "double--hyphen": "name must use lower-case letters, digits and hyphens",
                 "a" * 65: "name longer than 64 characters"}
        for name, finding in cases.items():
            result = self.lint("---\nname: %s\ndescription: d\n---\n" % name, name=name[:60] if len(name) > 64 else name)
            self.assertFalse(result["name_ok"], name)
            self.assertIn(finding, result["findings"], name)
        result = self.lint("---\nname: " + "a" * 64 + "\ndescription: d\n---\n", name="a" * 64)
        self.assertTrue(result["name_ok"])

    def test_a_missing_or_empty_name_or_description(self):
        result = self.lint("---\ndescription: d\n---\n")
        self.assertIsNone(result["name"])
        self.assertFalse(result["name_ok"])
        self.assertEqual(["missing name"], result["findings"])
        result = self.lint("---\nname: demo-skill\n---\n")
        self.assertEqual(0, result["description_chars"])
        self.assertEqual(["missing description"], result["findings"])
        result = self.lint("---\nname: demo-skill\ndescription: ''\n---\n")
        self.assertEqual(["missing description"], result["findings"])

    def test_no_skill_md(self):
        result = self.lint(None)
        self.assertEqual({"name": None, "name_ok": False, "description_chars": 0, "frontmatter_ok": False, "install_hints": 0,
                          "findings": ["no SKILL.md"]}, result)

    def test_missing_or_broken_frontmatter(self):
        self.assertEqual(["no frontmatter"], self.lint("# just a heading\n")["findings"])
        result = self.lint("---\nname: demo-skill\ndescription: d\nbody without the closing line\n")
        self.assertFalse(result["frontmatter_ok"])
        self.assertIn("frontmatter is not closed", result["findings"])
        result = self.lint("---\nname: demo-skill\nthis line is no key\ndescription: d\n---\n")
        self.assertFalse(result["frontmatter_ok"])
        self.assertTrue(any(f.startswith("frontmatter line 3") for f in result["findings"]), result["findings"])
        result = self.lint('---\nname: demo-skill\ndescription: "never closed\n---\n')
        self.assertFalse(result["frontmatter_ok"])

    def test_a_skill_md_that_is_not_utf8_is_reported_not_fatal(self):
        result = self.lint(b"---\nname: demo-skill\ndescription: caf\xe9\n---\n")
        self.assertIn("SKILL.md is not valid UTF-8", result["findings"])

    def test_install_hints_are_counted_once_each_in_the_listed_file_types(self):
        text = "\n".join([
            "pip install a", "python -m pip install b", "uv pip install c", "npm install d", "npm i e", "npm exec f", "npx g", "dotnet tool install h",
            "winget install i", "brew install j", "apt install k", "apt-get install l", "choco install m", "Install-Module n", "az extension add o",
            "pip3 install p", "sudo apt-get install q", "PIP INSTALL r"])
        extra = {"references/a.md": text, "scripts/b.sh": "pip install x\n", "scripts/c.ps1": "Install-Module y\n", "data/d.json": '{"run": "npm install z"}',
                 "scripts/e.py": "# pip install w\n", "notes/f.txt": "brew install v\n", "ci/g.yml": "run: npx -y tool\n", "ci/h.yaml": "run: choco install u\n",
                 "assets/i.png": b"\x89PNG pip install hidden", "docs/j.rst": "pip install ignored\n"}
        result = self.lint("---\nname: demo-skill\ndescription: d\n---\nbody\n", extra=extra)
        self.assertEqual(25, result["install_hints"])

    def test_words_that_only_look_like_install_commands_are_not_counted(self):
        extra = {"a.md": "the npm package\na pipeline\nnpx\nuse pip to install later\ninstall the thing\nreinstall pip\nnpm installed\nbrew installation\n"
                         "choco installer\nsnip install\npip installation\nxpip install\n"}
        result = self.lint("---\nname: demo-skill\ndescription: d\n---\n", extra=extra)
        self.assertEqual(0, result["install_hints"])

    def test_a_key_that_is_given_twice_is_a_problem(self):
        result = self.lint("---\nname: demo-skill\ndescription: one\ndescription: two\n---\n")
        self.assertFalse(result["frontmatter_ok"])
        self.assertIn("frontmatter line 4: duplicate key", result["findings"])


@unittest.skipUnless(HAS_GIT, "git is not installed")
class ResolveGitRefTests(unittest.TestCase):
    def setUp(self):
        self.runner = IsolatedRunner()

    def resolve(self, track, url=None):
        return ts.resolve_git_ref(url or FX.url, track, self.runner)

    def test_the_highest_semantic_version_wins_over_the_highest_text(self):
        result = self.resolve({"kind": "tag", "pattern": "v*"})
        self.assertEqual({"ref": "refs/tags/v1.10.0", "tag": "v1.10.0", "commit": FX.commits[3]}, result)

    def test_an_annotated_tag_gives_the_commit_not_the_tag_object(self):
        tag_object = FX.git("rev-parse", "refs/tags/v1.10.0")
        self.assertNotEqual(tag_object, FX.commits[3])
        self.assertEqual(FX.commits[3], self.resolve({"kind": "tag", "pattern": "v1.10*"})["commit"])

    def test_the_glob_narrows_the_tags(self):
        self.assertEqual("v1.9.0", self.resolve({"kind": "tag", "pattern": "v1.9*"})["tag"])
        result = self.resolve({"kind": "tag", "pattern": "v1.[0-2].*"})
        self.assertEqual("v1.2.0", result["tag"])
        self.assertEqual(FX.commits[2], result["commit"])
        self.assertEqual("v1.0.0", self.resolve({"kind": "tag", "pattern": "v1.0*"})["tag"])

    def test_a_pre_release_loses_to_a_release_but_wins_when_it_is_the_only_match(self):
        self.assertEqual("v1.10.0", self.resolve({"kind": "tag", "pattern": "v*"})["tag"])
        self.assertEqual("v2.0.0-rc1", self.resolve({"kind": "tag", "pattern": "v2*"})["tag"])

    def test_tags_that_are_not_versions_are_ignored(self):
        with self.assertRaises(ts.SourceError) as caught:
            self.resolve({"kind": "tag", "pattern": "release-*"})
        self.assertEqual("unresolved", caught.exception.code)
        with self.assertRaises(ts.SourceError):
            self.resolve({"kind": "tag", "pattern": "no-such-*"})

    def test_a_branch_head(self):
        self.assertEqual({"ref": "refs/heads/main", "tag": None, "commit": FX.commits[3]}, self.resolve({"kind": "branch", "name": "main"}))
        self.assertEqual(FX.commits[2], self.resolve({"kind": "branch", "name": "dev"})["commit"])
        with self.assertRaises(ts.SourceError) as caught:
            self.resolve({"kind": "branch", "name": "missing"})
        self.assertEqual("unresolved", caught.exception.code)

    def test_a_commit_is_taken_as_given_without_a_call(self):
        sha = "ab" * 20
        result = self.resolve({"kind": "commit", "sha": sha.upper()})
        self.assertEqual(sha, result["commit"])
        self.assertIsNone(result["tag"])
        self.assertEqual([], self.runner.calls)
        for bad in ("abc", "g" * 40, "ab" * 21, ""):
            with self.assertRaises(ts.SourceError):
                self.resolve({"kind": "commit", "sha": bad})

    def test_bad_tracks_are_refused(self):
        for track in ({"kind": "weird"}, {"kind": "tag"}, {"kind": "tag", "pattern": ""}, {"kind": "branch"}, {"kind": "commit"}, {}, None, "v*"):
            with self.assertRaises(ts.SourceError):
                self.resolve(track)

    def test_bad_branch_names_and_tag_patterns_are_refused_before_git_runs(self):
        for name in ("a b", "-x", "/x", "a..b", "x:y", "a~1", "a^", "a?", "a*", "a[b", "a\\b", "x@{1}", "a\x01b"):
            fake = FakeGit()
            with self.assertRaises(ts.SourceError, msg=repr(name)):
                ts.resolve_git_ref("https://example.test/o/r.git", {"kind": "branch", "name": name}, fake)
            self.assertEqual([], fake.calls, repr(name))
        for pattern in ("v* x", "v*\n", "\tv*"):
            fake = FakeGit()
            with self.assertRaises(ts.SourceError, msg=repr(pattern)):
                ts.resolve_git_ref("https://example.test/o/r.git", {"kind": "tag", "pattern": pattern}, fake)
            self.assertEqual([], fake.calls, repr(pattern))

    def test_git_runs_anonymously_without_a_prompt(self):
        self.resolve({"kind": "tag", "pattern": "v*"})
        argv, env = self.runner.calls[0]
        self.assertEqual("git", argv[0])
        self.assertLess(argv.index("credential.helper="), argv.index("ls-remote"))
        self.assertEqual("-c", argv[argv.index("credential.helper=") - 1])
        self.assertEqual("0", env["GIT_TERMINAL_PROMPT"])

    def test_the_file_protocol_is_allowed_only_for_file_urls(self):
        self.resolve({"kind": "tag", "pattern": "v*"})
        self.assertIn("protocol.file.allow=always", self.runner.argvs()[0])
        fake = FakeGit()
        with self.assertRaises(ts.SourceError):
            ts.resolve_git_ref("https://example.test/o/r.git", {"kind": "tag", "pattern": "v*"}, fake)
        self.assertTrue(fake.calls)
        for argv in fake.calls:
            self.assertNotIn("protocol.file.allow=always", argv)

    def test_other_url_schemes_never_reach_git(self):
        for url in ("ext::sh -c touch-x", "git://example.test/r.git", "ssh://example.test/r.git", "-oops", "", "/local/path", "http-not-a-url"):
            fake = FakeGit()
            with self.assertRaises(ts.SourceError) as caught:
                ts.resolve_git_ref(url, {"kind": "tag", "pattern": "v*"}, fake)
            self.assertEqual("unresolved", caught.exception.code, url)
            self.assertEqual([], fake.calls, url)

    def test_an_unreachable_repository_is_a_source_error_without_the_address(self):
        missing = (Path(TMP.name) / "no-such-repo.git").as_uri()
        with self.assertRaises(ts.SourceError) as caught:
            self.resolve({"kind": "tag", "pattern": "v*"}, url=missing)
        message = str(caught.exception)
        self.assertIn(caught.exception.code, ("network", "unresolved"))
        for forbidden in ("no-such-repo", "file:", TMP.name, "://"):
            self.assertNotIn(forbidden, message)
        self.assertRegex(message, r"^[a-z-]+: [A-Za-z0-9 ._:=/-]{0,80}$")


class GitFailureTests(unittest.TestCase):
    HOST = "git" + "." + "contoso" + "." + "example"

    def failure(self, returncode, stderr):
        return ts._git_failure(CommandResult(returncode, "", stderr))

    def test_known_failures_become_a_fixed_code_and_detail(self):
        host, quoted = self.HOST, "'https://%s/x.git/'" % self.HOST
        cases = [
            ("fatal: unable to access %s: Could not resolve host: %s" % (quoted, host), "network: dns"),
            ("fatal: unable to access %s: SSL certificate problem: unable to get local issuer certificate" % quoted, "network: tls"),
            ("fatal: unable to access %s: Failed to connect to %s port 443 after 21050 ms" % (quoted, host), "network: connect"),
            ("fatal: unable to access %s: Connection timed out after 21000 milliseconds" % quoted, "network: timeout"),
            ("fatal: could not read Username for %s: terminal prompts disabled" % quoted, "network: authentication required"),
            ("remote: Resource protected by organization SAML enforcement\nfatal: unable to access %s" % quoted, "network: authentication required"),
            ("remote: Repository not found.\nfatal: repository %s not found" % quoted, "unresolved: repository not found"),
            ("fatal: '/some/where' does not appear to be a git repository", "unresolved: repository not found"),
            ("fatal: remote error: upload-pack: not our ref " + "ab" * 20, "unresolved: commit not found"),
            ("something unexpected happened at %s" % host, "network: git exit 1"),
        ]
        for stderr, expected in cases:
            self.assertEqual(expected, str(self.failure(1, stderr)), stderr)

    def test_a_missing_git_and_a_timeout(self):
        self.assertEqual("not-installed: git", str(self.failure(127, "not found")))
        self.assertEqual("network: timeout", str(self.failure(124, "timed out")))

    def test_words_that_merely_contain_a_keyword_do_not_change_the_class(self):
        self.assertEqual("network: git exit 1", str(self.failure(1, "an assorted tlsomething classlist")))


class FakeGit:
    """A runner for git that answers from a script and records the argument lists."""

    def __init__(self, fetch_works=True):
        self.calls = []
        self.fetched = False
        self.fetch_works = fetch_works

    def which(self, name):
        return name

    def run(self, argv, *, cwd=None, env=None, timeout=60, input=None):
        self.calls.append(list(argv))
        if "fetch" in argv:
            self.fetched = self.fetch_works
            return CommandResult(0 if self.fetch_works else 128, "", "" if self.fetch_works else "fatal: could not read from remote")
        if "cat-file" in argv:
            return CommandResult(0 if self.fetched else 128, "", "")
        if "ls-remote" in argv:
            return CommandResult(128, "", "fatal: unable to access")
        return CommandResult(0, "", "")


@unittest.skipUnless(HAS_GIT, "git is not installed")
class FetchGitTests(unittest.TestCase):
    def setUp(self):
        self.runner = IsolatedRunner()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dest = Path(self.tmp.name) / "cache"

    def has(self, git_dir, commit):
        return self.runner.run(["git", "--git-dir", str(git_dir), "cat-file", "-e", commit + "^{commit}"]).returncode == 0

    def test_fetches_exactly_that_commit_into_a_bare_repository(self):
        commit = FX.commits[2]
        result = ts.fetch_git(FX.url, commit, self.dest, self.runner)
        self.assertEqual(self.dest, result)
        self.assertTrue(self.has(self.dest, commit))
        self.assertFalse(self.has(self.dest, FX.commits[3]), "a commit that was not asked for came along")
        self.assertTrue((self.dest / "HEAD").exists())
        self.assertFalse((self.dest / ".git").exists())
        self.assertTrue((self.dest / "shallow").exists(), "the fetch was not shallow")

    def test_the_fetched_tree_can_be_read(self):
        ts.fetch_git(FX.url, FX.commits[3], self.dest, self.runner)
        self.assertEqual(spec_digest(GOOD_FILES), ts.digest_git_tree(self.dest, FX.commits[3], "plugins/alpha/skills/good-skill", self.runner))

    def test_a_second_call_for_the_same_commit_does_not_fetch_again(self):
        ts.fetch_git(FX.url, FX.commits[3], self.dest, self.runner)
        self.runner.calls.clear()
        ts.fetch_git(FX.url, FX.commits[3], self.dest, self.runner)
        self.assertFalse(any("fetch" in argv for argv in self.runner.argvs()))

    def test_another_commit_can_join_an_existing_cache(self):
        ts.fetch_git(FX.url, FX.commits[2], self.dest, self.runner)
        ts.fetch_git(FX.url, FX.commits[3], self.dest, self.runner)
        self.assertTrue(self.has(self.dest, FX.commits[2]))
        self.assertTrue(self.has(self.dest, FX.commits[3]))

    def test_git_runs_anonymously_and_the_file_protocol_only_for_file_urls(self):
        ts.fetch_git(FX.url, FX.commits[3], self.dest, self.runner)
        fetches = [(argv, env) for argv, env in self.runner.calls if "fetch" in argv]
        self.assertEqual(1, len(fetches))
        argv, env = fetches[0]
        self.assertIn("credential.helper=", argv)
        self.assertIn("protocol.file.allow=always", argv)
        self.assertIn("--depth", argv)
        self.assertEqual("0", env["GIT_TERMINAL_PROMPT"])
        fake = FakeGit()
        ts.fetch_git("https://example.test/o/r.git", "ab" * 20, self.dest / "other", fake)
        fetch = [argv for argv in fake.calls if "fetch" in argv][0]
        self.assertNotIn("protocol.file.allow=always", fetch)
        self.assertIn("credential.helper=", fetch)

    def test_a_commit_that_is_not_there_is_a_source_error(self):
        with self.assertRaises(ts.SourceError) as caught:
            ts.fetch_git(FX.url, "cd" * 20, self.dest, self.runner)
        self.assertIn(caught.exception.code, ("unresolved", "network"))
        self.assertNotIn(FX.url, str(caught.exception))

    def test_a_fetch_that_reports_success_without_the_commit_is_still_an_error(self):
        fake = FakeGit()
        fake.fetched = False

        class Liar(FakeGit):
            def run(self, argv, **kwargs):
                self.calls.append(list(argv))
                return CommandResult(1 if "cat-file" in argv else 0, "", "")

        with self.assertRaises(ts.SourceError):
            ts.fetch_git("https://example.test/o/r.git", "ab" * 20, self.dest, Liar())

    def test_bad_arguments_never_reach_git(self):
        for url, commit in ((FX.url, "main"), (FX.url, "--upload-pack=x"), ("ext::sh -c x", "ab" * 20), ("-oops", "ab" * 20), ("", "ab" * 20)):
            fake = FakeGit()
            with self.assertRaises(ts.SourceError):
                ts.fetch_git(url, commit, self.dest, fake)
            self.assertEqual([], fake.calls)


@unittest.skipUnless(HAS_GIT, "git is not installed")
class ReadPluginTests(unittest.TestCase):
    def setUp(self):
        self.runner = IsolatedRunner()

    def read(self, plugin, commit=None):
        return ts.read_plugin(FX.git_dir, commit or FX.commits[3], "plugins/" + plugin, self.runner)

    def test_the_shape_of_the_answer(self):
        info = self.read("alpha")
        self.assertEqual({"version", "skills", "agents", "bundled_mcp"}, set(info))
        self.assertEqual("1.2.0", info["version"])
        self.assertEqual(["Helper.agent.md"], info["agents"])
        self.assertEqual(["Alpha-Server", "zeta-server"], info["bundled_mcp"])

    def test_only_folders_with_a_skill_md_are_skills(self):
        self.assertEqual(["bad-skill", "good-skill", "link-skill"], sorted(self.read("alpha")["skills"]))
        self.assertEqual(["good-skill", "other-skill"], sorted(self.read("beta")["skills"]))

    def test_a_plugin_without_skills_or_manifest(self):
        info = self.read("delta")
        self.assertEqual({"version": None, "skills": {}, "agents": [], "bundled_mcp": []}, info)
        self.assertIsNone(self.read("beta")["version"])

    def test_a_skill_entry_has_the_fields_of_the_lock(self):
        entry = self.read("alpha")["skills"]["good-skill"]
        self.assertEqual({"path", "digest", "files", "bytes", "description_chars", "install_hints", "findings"}, set(entry))
        self.assertEqual("plugins/alpha/skills/good-skill", entry["path"])
        expected = spec_digest(GOOD_FILES)
        self.assertEqual(expected["digest"], entry["digest"])
        self.assertEqual(expected["files"], entry["files"])
        self.assertEqual(expected["bytes"], entry["bytes"])
        self.assertEqual(len(GOOD_DESCRIPTION), entry["description_chars"])
        self.assertEqual(3, entry["install_hints"])
        self.assertEqual([], entry["findings"])

    def test_findings_of_a_bad_skill(self):
        entry = self.read("alpha")["skills"]["bad-skill"]
        self.assertEqual(1025, entry["description_chars"])
        self.assertEqual(["name does not match folder", "description longer than 1024 characters"], entry["findings"])

    def test_the_same_skill_in_two_plugins_has_the_same_digest(self):
        self.assertEqual(self.read("alpha")["skills"]["good-skill"]["digest"], self.read("beta")["skills"]["good-skill"]["digest"])
        self.assertNotEqual(self.read("alpha")["skills"]["good-skill"]["digest"], self.read("gamma")["skills"]["good-skill"]["digest"])

    def test_the_commit_decides(self):
        self.assertEqual("1.0.0", self.read("alpha", FX.commits[1])["version"])
        self.assertEqual({"good-skill"}, set(self.read("alpha", FX.commits[1])["skills"]))
        with self.assertRaises(ts.SourceError):
            self.read("beta", FX.commits[1])

    def test_a_missing_plugin_or_a_bad_path_is_a_source_error(self):
        with self.assertRaises(ts.SourceError) as caught:
            self.read("nothing")
        self.assertEqual("unresolved", caught.exception.code)
        for path in ("../x", "plugins/../x", "/abs", "a\\b", ""):
            with self.assertRaises(ts.SourceError):
                ts.read_plugin(FX.git_dir, FX.commits[3], path, self.runner)

    def test_a_plugin_with_a_submodule_in_a_skill_is_refused(self):
        with self.assertRaises(ts.SourceError) as caught:
            self.read("epsilon")
        self.assertIn("submodule", str(caught.exception))


@unittest.skipUnless(HAS_GIT, "git is not installed")
class VendorTests(unittest.TestCase):
    def setUp(self):
        self.runner = IsolatedRunner()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Path(self.tmp.name) / "pack"
        self.lock = lock_for(FX, self.runner)
        self.runner.calls.clear()

    def vendor(self, selection, **kwargs):
        return ts.vendor_skills(self.lock, selection, self.store, self.runner, **kwargs)

    def digest_of(self, plugin, skill):
        return self.lock["skill_sources"]["fx"]["plugins"][plugin]["skills"][skill]["digest"]

    def fetches(self):
        return [argv for argv in self.runner.argvs() if "fetch" in argv]

    def test_writes_the_selected_skills_verified_against_the_lock(self):
        manifest = self.vendor([("fx", "alpha", "good-skill"), ("fx", "beta", "other-skill")])
        self.assertEqual(["good-skill", "other-skill"], sorted(p.name for p in (self.store / "skills").iterdir()))
        self.assertEqual(self.digest_of("alpha", "good-skill"), ts.digest_tree(self.store / "skills" / "good-skill")["digest"])
        entry = self.lock["skill_sources"]["fx"]["plugins"]["alpha"]["skills"]["good-skill"]
        self.assertEqual({"schema": 1, "lock_inputs_digest": self.lock["inputs_digest"], "skills": {
            "good-skill": {"source": "fx", "plugin": "alpha", "commit": FX.commits[3], "digest": entry["digest"], "files": entry["files"], "bytes": entry["bytes"]},
            "other-skill": {"source": "fx", "plugin": "beta", "commit": FX.commits[3],
                            "digest": self.digest_of("beta", "other-skill"),
                            "files": self.lock["skill_sources"]["fx"]["plugins"]["beta"]["skills"]["other-skill"]["files"],
                            "bytes": self.lock["skill_sources"]["fx"]["plugins"]["beta"]["skills"]["other-skill"]["bytes"]}}}, manifest)
        self.assertEqual(manifest, json.loads((self.store / "MANIFEST.json").read_text(encoding="utf-8")))

    def test_the_manifest_file_is_deterministic_json_with_lf(self):
        self.vendor([("fx", "beta", "other-skill"), ("fx", "alpha", "good-skill")])
        raw = (self.store / "MANIFEST.json").read_bytes()
        self.assertNotIn(b"\r", raw)
        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(json.dumps(json.loads(raw), indent=2, ensure_ascii=False) + "\n", raw.decode("utf-8"))
        self.assertEqual(["good-skill", "other-skill"], list(json.loads(raw)["skills"]))

    def test_text_is_written_with_lf_and_binary_as_it_is(self):
        self.vendor([("fx", "alpha", "good-skill")])
        skill = self.store / "skills" / "good-skill"
        self.assertEqual(b"one\ntwo\n", (skill / "references" / "crlf.txt").read_bytes())
        self.assertEqual(b"caf\xe9\nsecond line\n", (skill / "references" / "legacy.txt").read_bytes())
        self.assertEqual(b"\x00\x01\r\n\x02\xff\r\n", (skill / "assets" / "blob.bin").read_bytes())
        self.assertEqual(GOOD_FILES["scripts/run.sh"], (skill / "scripts" / "run.sh").read_bytes())

    def test_a_link_is_written_as_a_file_holding_its_target(self):
        self.vendor([("fx", "alpha", "link-skill")])
        link = self.store / "skills" / "link-skill" / "current"
        self.assertFalse(link.is_symlink())
        self.assertEqual(b"SKILL.md", link.read_bytes())

    def test_a_digest_that_does_not_match_stops_everything_and_writes_nothing(self):
        entry = self.lock["skill_sources"]["fx"]["plugins"]["beta"]["skills"]["other-skill"]
        entry["digest"] = "sha256:" + "0" * 64
        with self.assertRaises(ts.SourceError) as caught:
            self.vendor([("fx", "alpha", "good-skill"), ("fx", "beta", "other-skill")])
        self.assertTrue(str(caught.exception).startswith("digest mismatch"), str(caught.exception))
        self.assertEqual("digest mismatch", caught.exception.code)
        self.assertFalse((self.store / "skills").exists() and any((self.store / "skills").iterdir()))
        self.assertFalse((self.store / "MANIFEST.json").exists())

    def test_a_failed_run_leaves_the_earlier_store_alone(self):
        self.vendor([("fx", "alpha", "good-skill")])
        before = (self.store / "MANIFEST.json").read_bytes()
        self.lock["skill_sources"]["fx"]["plugins"]["beta"]["skills"]["other-skill"]["digest"] = "sha256:" + "1" * 64
        with self.assertRaises(ts.SourceError):
            self.vendor([("fx", "beta", "other-skill")])
        self.assertEqual(before, (self.store / "MANIFEST.json").read_bytes())
        self.assertTrue((self.store / "skills" / "good-skill" / "SKILL.md").exists())
        self.assertFalse((self.store / "skills" / "other-skill").exists())
        self.assertEqual([], [p.name for p in self.store.iterdir() if p.name.startswith(".staging")])

    def test_a_tampered_cache_cannot_pass_as_the_locked_content(self):
        self.vendor([("fx", "alpha", "good-skill")])
        shutil.rmtree(self.store / "skills")
        self.lock["skill_sources"]["fx"]["plugins"]["alpha"]["skills"]["good-skill"]["digest"] = "sha256:" + "2" * 64
        with self.assertRaises(ts.SourceError):
            self.vendor([("fx", "alpha", "good-skill")])

    def test_a_quarantined_skill_is_never_written(self):
        for quarantine in ([{"source": "fx", "skill": "bad-skill"}], ["bad-skill"], [("fx", "bad-skill")], [{"skill": "bad-skill"}]):
            with self.assertRaises(ts.SourceError) as caught:
                self.vendor([("fx", "alpha", "good-skill"), ("fx", "alpha", "bad-skill")], quarantine=quarantine)
            self.assertEqual("quarantined", caught.exception.code)
            self.assertFalse((self.store / "skills" / "bad-skill").exists())
            self.assertFalse((self.store / "skills" / "good-skill").exists())

    def test_a_quarantine_for_another_source_or_skill_does_not_matter(self):
        self.vendor([("fx", "alpha", "good-skill")], quarantine=[{"source": "elsewhere", "skill": "good-skill"}, "bad-skill"])
        self.assertTrue((self.store / "skills" / "good-skill").exists())

    def test_the_same_skill_from_two_plugins_with_one_digest_is_written_once(self):
        manifest = self.vendor([("fx", "alpha", "good-skill"), ("fx", "beta", "good-skill")])
        self.assertEqual(["good-skill"], list(manifest["skills"]))
        self.assertEqual("alpha", manifest["skills"]["good-skill"]["plugin"])
        self.assertEqual(self.digest_of("alpha", "good-skill"), ts.digest_tree(self.store / "skills" / "good-skill")["digest"])

    def test_the_same_name_with_different_content_is_a_conflict(self):
        with self.assertRaises(ts.SourceError) as caught:
            self.vendor([("fx", "alpha", "good-skill"), ("fx", "gamma", "good-skill")])
        self.assertEqual("conflict", caught.exception.code)
        self.assertFalse((self.store / "skills" / "good-skill").exists())

    def test_skills_that_left_the_selection_are_removed(self):
        self.vendor([("fx", "alpha", "good-skill"), ("fx", "beta", "other-skill")])
        (self.store / "skills" / "hand-made").mkdir()
        (self.store / "skills" / "hand-made" / "x.txt").write_text("x")
        manifest = self.vendor([("fx", "alpha", "good-skill")])
        self.assertEqual(["good-skill"], sorted(p.name for p in (self.store / "skills").iterdir() if p.is_dir()))
        self.assertEqual(["good-skill"], list(manifest["skills"]))
        manifest = self.vendor([])
        self.assertEqual({"schema": 1, "lock_inputs_digest": self.lock["inputs_digest"], "skills": {}}, manifest)
        self.assertEqual([], [p for p in (self.store / "skills").iterdir() if p.is_dir()])

    def test_a_second_run_changes_nothing_and_uses_no_git(self):
        selection = [("fx", "alpha", "good-skill"), ("fx", "beta", "other-skill")]
        self.vendor(selection)
        before = {p.relative_to(self.store).as_posix(): p.read_bytes() for p in self.store.rglob("*") if p.is_file() and ".cache" not in p.parts}
        self.runner.calls.clear()
        self.vendor(selection)
        self.assertEqual([], self.runner.calls)
        after = {p.relative_to(self.store).as_posix(): p.read_bytes() for p in self.store.rglob("*") if p.is_file() and ".cache" not in p.parts}
        self.assertEqual(before, after)

    def test_a_damaged_skill_is_rewritten_from_the_cache_without_a_new_fetch(self):
        self.vendor([("fx", "alpha", "good-skill")])
        self.assertEqual(1, len(self.fetches()))
        (self.store / "skills" / "good-skill" / "SKILL.md").write_text("tampered\n")
        self.runner.calls.clear()
        self.vendor([("fx", "alpha", "good-skill")])
        self.assertEqual([], self.fetches())
        self.assertEqual(self.digest_of("alpha", "good-skill"), ts.digest_tree(self.store / "skills" / "good-skill")["digest"])

    def test_the_locked_commit_is_fetched_into_a_cache_named_after_it(self):
        self.vendor([("fx", "alpha", "good-skill")])
        cache = self.store / ".cache" / FX.commits[3][:12]
        self.assertTrue((cache / "HEAD").exists())
        fetch = self.fetches()[0]
        self.assertEqual(FX.commits[3], fetch[-1])
        self.assertEqual(FX.url, fetch[-2])

    def test_a_selection_that_is_not_in_the_lock_is_a_source_error(self):
        for selection in ([("nowhere", "alpha", "good-skill")], [("fx", "nowhere", "good-skill")], [("fx", "alpha", "nowhere")]):
            with self.assertRaises(ts.SourceError) as caught:
                self.vendor(selection)
            self.assertEqual("unresolved", caught.exception.code)

    def test_unsafe_names_and_paths_in_the_lock_are_refused(self):
        plugin = self.lock["skill_sources"]["fx"]["plugins"]["alpha"]
        good = plugin["skills"]["good-skill"]
        plugin["skills"]["../escape"] = dict(good)
        plugin["skills"]["nested/name"] = dict(good)
        plugin["skills"][".git"] = dict(good)
        for name in ("../escape", "nested/name", ".git"):
            with self.assertRaises(ts.SourceError):
                self.vendor([("fx", "alpha", name)])
        plugin["skills"]["ok-name"] = dict(good, path="plugins/alpha/skills/../../../x")
        with self.assertRaises(ts.SourceError):
            self.vendor([("fx", "alpha", "ok-name")])
        self.assertFalse((Path(self.tmp.name) / "escape").exists())
        self.assertFalse((self.store.parent / "escape").exists())


class FakeRunner:
    """Answers `npm` calls and HTTP requests from tables and records what was asked."""

    def __init__(self, npm=None, http=None):
        self.npm = npm
        self.table = http or {}
        self.calls = []

    def which(self, name):
        return name

    def run(self, argv, *, cwd=None, env=None, timeout=60, input=None):
        self.calls.append(("run", list(argv)))
        if isinstance(self.npm, Exception):
            raise self.npm
        return self.npm(argv) if callable(self.npm) else (self.npm or CommandResult(127, "", "not found"))

    def http(self, method, url, *, headers=None, body=None, timeout=20):
        self.calls.append(("http", url))
        answer = self.table.get(url, HttpResult(404, {}, b"", None))
        if isinstance(answer, Exception):
            raise answer
        return answer

    def urls(self):
        return [value for kind, value in self.calls if kind == "http"]


def json_answer(obj, status=200):
    return HttpResult(status, {}, json.dumps(obj).encode("utf-8"), None)


def failed(error):
    return HttpResult(0, {}, b"", error)


def status_only(code):
    return HttpResult(code, {}, b"", None)


NPM_URL = "https://registry.npmjs.org/@microsoft%2Ffabric-mcp"
JSDELIVR_URL = "https://data.jsdelivr.com/v1/packages/npm/@microsoft/fabric-mcp"
INTEGRITY = "sha512-" + "A" * 86 + "=="
INTERNAL_HOST = "pkgs." + "visual" + "studio.com"
FEED_URL = "https://" + INTERNAL_HOST + "/org/_packaging/feed/npm/registry/@microsoft%2ffabric-mcp"
NPM_ERROR = "npm error code E404\nnpm error 404 Not Found - GET " + FEED_URL + " - Not found\nnpm error 404\nnpm error host " + INTERNAL_HOST + "\n"
NPM_ARGV = ["npm", "view", "@microsoft/fabric-mcp", "version", "dist.integrity", "--json"]


def npm_ok(payload):
    return CommandResult(0, json.dumps(payload), "")


def packument(latest="1.6.0", versions=("1.5.0", "1.6.0"), tags=None):
    return {"dist-tags": tags or {"latest": latest}, "versions": {v: {"dist": {"integrity": INTEGRITY if v == "1.6.0" else "sha512-" + "B" * 86 + "=="}} for v in versions}}


def assert_clean(test, result):
    text = json.dumps(result)
    for forbidden in (INTERNAL_HOST, "visual", "://", "_packaging", "npm error", "fabric-mcp"):
        test.assertNotIn(forbidden, text)
    if result.get("status") == "unresolved":
        test.assertEqual({"status", "reason", "detail"}, set(result))
        test.assertRegex(result["detail"], r"^[A-Za-z0-9 ._:=/-]{0,80}$")


class NpmTests(unittest.TestCase):
    def resolve(self, runner, track="latest"):
        return ts.resolve_package("npm", "@microsoft/fabric-mcp", track, runner)

    def test_the_cli_answers_with_an_object(self):
        runner = FakeRunner(npm=npm_ok({"version": "1.6.0", "dist.integrity": INTEGRITY}))
        self.assertEqual({"status": "resolved", "version": "1.6.0", "integrity": INTEGRITY, "via": "npm-cli"}, self.resolve(runner))
        self.assertEqual([("run", NPM_ARGV)], runner.calls)

    def test_the_cli_answers_with_an_array_as_it_does_on_the_maintainers_machine(self):
        runner = FakeRunner(npm=npm_ok([{"version": "1.6.0", "dist.integrity": INTEGRITY}]))
        self.assertEqual({"status": "resolved", "version": "1.6.0", "integrity": INTEGRITY, "via": "npm-cli"}, self.resolve(runner))

    def test_an_array_of_several_versions_gives_the_highest(self):
        runner = FakeRunner(npm=npm_ok([{"version": "1.9.0", "dist.integrity": INTEGRITY}, {"version": "1.10.0", "dist.integrity": INTEGRITY}]))
        self.assertEqual("1.10.0", self.resolve(runner)["version"])

    def test_a_release_wins_over_a_higher_pre_release_in_an_array(self):
        runner = FakeRunner(npm=npm_ok([{"version": "1.9.0", "dist.integrity": INTEGRITY}, {"version": "2.0.0-beta.1", "dist.integrity": INTEGRITY}]))
        self.assertEqual("1.9.0", self.resolve(runner)["version"])

    def test_an_answer_that_was_cut_short_is_a_failure_of_that_stage(self):
        cut = HttpResult(200, {}, json.dumps(packument()).encode("utf-8"), "too-large")
        runner = FakeRunner(npm=CommandResult(127, "", ""), http={NPM_URL: cut, JSDELIVR_URL: failed("tls")})
        result = self.resolve(runner)
        self.assertEqual({"status": "unresolved", "reason": "network", "detail": "npm missing - registry too-large - jsdelivr tls"}, result)

    def test_the_cli_answers_with_a_bare_string(self):
        runner = FakeRunner(npm=npm_ok("1.6.0"))
        self.assertEqual({"status": "resolved", "version": "1.6.0", "integrity": None, "via": "npm-cli"}, self.resolve(runner))

    def test_an_object_that_holds_a_nested_integrity_is_read_too(self):
        runner = FakeRunner(npm=npm_ok({"version": "1.6.0", "dist": {"integrity": INTEGRITY}}))
        self.assertEqual(INTEGRITY, self.resolve(runner)["integrity"])

    def test_an_exact_version_is_asked_for_by_name_and_version(self):
        runner = FakeRunner(npm=npm_ok({"version": "1.5.0", "dist.integrity": INTEGRITY}))
        result = self.resolve(runner, "1.5.0")
        self.assertEqual("1.5.0", result["version"])
        self.assertEqual("@microsoft/fabric-mcp" + "@" + "1.5.0", runner.calls[0][1][2])

    def test_an_exact_version_must_come_back_as_asked(self):
        runner = FakeRunner(npm=npm_ok({"version": "1.6.0", "dist.integrity": INTEGRITY}), http={NPM_URL: json_answer(packument())})
        result = self.resolve(runner, "1.5.0")
        self.assertEqual("npm-registry", result["via"])
        self.assertEqual("1.5.0", result["version"])

    def test_a_failing_cli_falls_back_to_the_registry(self):
        for npm in (CommandResult(1, "", NPM_ERROR), CommandResult(127, "", "not found"), CommandResult(124, "", "timed out"), CommandResult(0, "not json", ""),
                    CommandResult(0, "", ""), CommandResult(0, "{}", "")):
            runner = FakeRunner(npm=npm, http={NPM_URL: json_answer(packument())})
            result = self.resolve(runner)
            self.assertEqual({"status": "resolved", "version": "1.6.0", "integrity": INTEGRITY, "via": "npm-registry"}, result)
            self.assertEqual([NPM_URL], runner.urls())

    def test_the_registry_with_an_exact_version(self):
        runner = FakeRunner(npm=CommandResult(127, "", "not found"), http={NPM_URL: json_answer(packument())})
        result = self.resolve(runner, "1.5.0")
        self.assertEqual({"status": "resolved", "version": "1.5.0", "integrity": "sha512-" + "B" * 86 + "==", "via": "npm-registry"}, result)

    def test_the_registry_without_a_latest_tag_or_with_a_missing_version_is_unresolved(self):
        for track, doc in (("latest", packument(tags={"next": "2.0.0"})), ("9.9.9", packument())):
            runner = FakeRunner(npm=CommandResult(127, "", ""), http={NPM_URL: json_answer(doc), JSDELIVR_URL: failed("tls")})
            result = self.resolve(runner, track)
            self.assertEqual("unresolved", result["status"])
            assert_clean(self, result)

    def test_jsdelivr_gives_the_version_only(self):
        doc = {"type": "npm", "name": "@microsoft/fabric-mcp", "tags": {"latest": "1.6.0"}, "versions": [{"version": "1.6.0"}, {"version": "1.5.0"}]}
        runner = FakeRunner(npm=CommandResult(127, "", ""), http={NPM_URL: failed("tls"), JSDELIVR_URL: json_answer(doc)})
        self.assertEqual({"status": "resolved", "version": "1.6.0", "integrity": None, "via": "jsdelivr"}, self.resolve(runner))
        self.assertEqual([NPM_URL, JSDELIVR_URL], runner.urls())

    def test_jsdelivr_with_a_plain_list_of_versions(self):
        doc = {"type": "npm", "versions": ["1.2.0", "1.10.0", "1.9.0", "2.0.0-beta.1"]}
        runner = FakeRunner(npm=CommandResult(127, "", ""), http={JSDELIVR_URL: json_answer(doc)})
        self.assertEqual("1.10.0", self.resolve(runner)["version"])
        runner = FakeRunner(npm=CommandResult(127, "", ""), http={JSDELIVR_URL: json_answer(doc)})
        self.assertEqual("1.9.0", self.resolve(runner, "1.9.0")["version"])
        runner = FakeRunner(npm=CommandResult(127, "", ""), http={JSDELIVR_URL: json_answer(doc)})
        self.assertEqual("unresolved", self.resolve(runner, "7.7.7")["status"])

    def test_everything_blocked_is_a_network_reason_without_the_feed_address(self):
        runner = FakeRunner(npm=CommandResult(1, "", NPM_ERROR), http={NPM_URL: failed("tls"), JSDELIVR_URL: failed("tls")})
        result = self.resolve(runner)
        self.assertEqual("unresolved", result["status"])
        self.assertEqual("network", result["reason"])
        self.assertIn("tls", result["detail"])
        assert_clean(self, result)

    def test_an_error_text_with_a_host_and_a_url_never_reaches_the_result(self):
        for npm in (CommandResult(1, "", NPM_ERROR), CommandResult(1, NPM_ERROR, NPM_ERROR),
                    CommandResult(1, json.dumps({"error": {"code": "E404", "summary": NPM_ERROR, "detail": FEED_URL}}), "")):
            for table in ({NPM_URL: status_only(404), JSDELIVR_URL: status_only(404)}, {NPM_URL: failed("dns"), JSDELIVR_URL: failed("timeout")}, {}):
                result = self.resolve(FakeRunner(npm=npm, http=table))
                self.assertEqual("unresolved", result["status"])
                assert_clean(self, result)

    def test_not_found_everywhere_is_unresolved_not_network(self):
        runner = FakeRunner(npm=CommandResult(1, "", NPM_ERROR), http={NPM_URL: status_only(404), JSDELIVR_URL: status_only(404)})
        result = self.resolve(runner)
        self.assertEqual("unresolved", result["reason"])
        self.assertIn("not found", result["detail"])

    def test_a_blocked_stage_makes_the_answer_a_network_problem_even_when_another_said_not_found(self):
        runner = FakeRunner(npm=CommandResult(1, "", NPM_ERROR), http={NPM_URL: failed("tls"), JSDELIVR_URL: status_only(404)})
        self.assertEqual("network", self.resolve(runner)["reason"])

    def test_values_that_are_not_a_version_or_an_integrity_are_not_trusted(self):
        for payload in ({"version": "1.6.0; echo x", "dist.integrity": INTEGRITY}, {"version": "latest", "dist.integrity": INTEGRITY},
                        {"version": "1.6.0", "dist.integrity": "md5-abc"}, {"version": "1.6.0", "dist.integrity": ["x"]}, {"version": 16}):
            runner = FakeRunner(npm=npm_ok(payload), http={NPM_URL: failed("tls"), JSDELIVR_URL: failed("tls")})
            result = self.resolve(runner)
            self.assertEqual("unresolved", result["status"], payload)
            assert_clean(self, result)

    def test_names_and_tracks_that_could_be_options_or_ranges_are_refused_before_any_call(self):
        for name in ("--registry=x", "-x", "a b", "", "a;b", "@scope", "@/x", "../x", "a$(x)"):
            runner = FakeRunner()
            result = ts.resolve_package("npm", name, "latest", runner)
            self.assertEqual("unresolved", result["status"], name)
            self.assertEqual([], runner.calls)
        for track in ("^1.0.0", "~1", ">=1", "next", "", "1.0.0 || 2", "-1", "1.0.0;x", None, 5):
            runner = FakeRunner()
            result = ts.resolve_package("npm", "@microsoft/fabric-mcp", track, runner)
            self.assertEqual("unresolved", result["status"], track)
            self.assertEqual([], runner.calls)

    def test_a_runner_that_raises_never_makes_the_resolver_raise(self):
        for runner in (FakeRunner(npm=OSError("x"), http={}), FakeRunner(npm=CommandResult(127, "", ""), http={NPM_URL: OSError("x"), JSDELIVR_URL: RuntimeError("y")})):
            result = self.resolve(runner)
            self.assertEqual("unresolved", result["status"])
            assert_clean(self, result)


class PypiTests(unittest.TestCase):
    URL = "https://pypi.org/pypi/ms-fabric-cli/json"
    PINNED = "https://pypi.org/pypi/ms-fabric-cli/1.7.0/json"

    def doc(self, version="1.8.0", files=None):
        if files is None:
            files = [{"packagetype": "bdist_wheel", "digests": {"sha256": "ab" * 32}, "filename": "x-py3-none-any.whl"},
                     {"packagetype": "sdist", "digests": {"sha256": "cd" * 32}, "filename": "x.tar.gz"}]
        return {"info": {"version": version}, "urls": files}

    def resolve(self, table, track="latest"):
        runner = FakeRunner(http=table)
        return ts.resolve_package("pypi", "ms-fabric-cli", track, runner), runner

    def test_latest_takes_the_first_sdist_or_wheel_by_file_name(self):
        result, runner = self.resolve({self.URL: json_answer(self.doc())})
        self.assertEqual({"status": "resolved", "version": "1.8.0", "sha256": "ab" * 32, "via": "pypi"}, result)
        self.assertEqual([self.URL], runner.urls())

    def test_the_choice_does_not_depend_on_the_order_of_the_answer(self):
        files = [{"packagetype": "sdist", "digests": {"sha256": "cd" * 32}, "filename": "x.tar.gz"},
                 {"packagetype": "bdist_wheel", "digests": {"sha256": "ab" * 32}, "filename": "x-py3-none-win_amd64.whl"},
                 {"packagetype": "bdist_wheel", "digests": {"sha256": "ef" * 32}, "filename": "x-py3-none-any.whl"}]
        for order in (files, files[::-1], files[1:] + files[:1]):
            result, _ = self.resolve({self.URL: json_answer(self.doc(files=list(order)))})
            self.assertEqual("ef" * 32, result["sha256"])

    def test_a_file_without_a_hash_is_passed_over_for_the_next_one_by_name(self):
        files = [{"packagetype": "bdist_wheel", "digests": {}, "filename": "x-py3-none-any.whl"},
                 {"packagetype": "sdist", "digests": {"sha256": "cd" * 32}, "filename": "x.tar.gz"}]
        result, _ = self.resolve({self.URL: json_answer(self.doc(files=files))})
        self.assertEqual("cd" * 32, result["sha256"])

    def test_other_kinds_of_files_are_skipped(self):
        files = [{"packagetype": "bdist_egg", "digests": {"sha256": "11" * 32}}, {"packagetype": "sdist", "digests": {"sha256": "22" * 32}}]
        result, _ = self.resolve({self.URL: json_answer(self.doc(files=files))})
        self.assertEqual("22" * 32, result["sha256"])

    def test_a_release_without_usable_files_resolves_without_a_hash(self):
        for files in ([], [{"packagetype": "bdist_egg", "digests": {"sha256": "11" * 32}}], [{"packagetype": "sdist", "digests": {}}],
                      [{"packagetype": "sdist", "digests": {"sha256": "not-hex"}}]):
            result, _ = self.resolve({self.URL: json_answer(self.doc(files=files))})
            self.assertEqual({"status": "resolved", "version": "1.8.0", "sha256": None, "via": "pypi"}, result)

    def test_a_pinned_version_uses_its_own_page(self):
        result, runner = self.resolve({self.PINNED: json_answer(self.doc("1.7.0"))}, "1.7.0")
        self.assertEqual("1.7.0", result["version"])
        self.assertEqual([self.PINNED], runner.urls())

    def test_a_page_for_another_version_than_pinned_is_refused(self):
        result, _ = self.resolve({self.PINNED: json_answer(self.doc("1.8.0"))}, "1.7.0")
        self.assertEqual("unresolved", result["status"])

    def test_failures_are_classified(self):
        result, _ = self.resolve({self.URL: status_only(404)})
        self.assertEqual(("unresolved", "not found"), (result["reason"], result["detail"]))
        for table in ({self.URL: failed("tls")}, {self.URL: failed("timeout")}, {self.URL: status_only(503)}):
            result, _ = self.resolve(table)
            self.assertEqual("network", result["reason"])
            assert_clean(self, result)
        for answer in (HttpResult(200, {}, b"not json", None), json_answer([]), json_answer({"info": {}}), json_answer({"info": {"version": "1; x"}})):
            result, _ = self.resolve({self.URL: answer})
            self.assertEqual("unresolved", result["status"])
            assert_clean(self, result)

    def test_bad_names_are_refused_before_any_call(self):
        for name in ("-x", "a b", "", "a/b", "a;b", "..", "a?x=1"):
            runner = FakeRunner()
            self.assertEqual("unresolved", ts.resolve_package("pypi", name, "latest", runner)["status"], name)
            self.assertEqual([], runner.calls)

    def test_a_runner_that_raises_gives_an_unresolved_answer(self):
        result, _ = self.resolve({self.URL: OSError("boom")})
        self.assertEqual("unresolved", result["status"])


class NugetTests(unittest.TestCase):
    URL = "https://api.nuget.org/v3-flatcontainer/azure.bicep.mcpserver/index.json"

    def resolve(self, versions, track="latest", table=None):
        runner = FakeRunner(http=table if table is not None else {self.URL: json_answer({"versions": versions})})
        return ts.resolve_package("nuget", "Azure.Bicep.McpServer", track, runner), runner

    def test_the_highest_release_wins_and_the_id_is_lower_case(self):
        result, runner = self.resolve(["0.9.0", "1.10.0", "1.9.0", "2.0.0-beta.1"])
        self.assertEqual({"status": "resolved", "version": "1.10.0", "integrity": None, "via": "nuget"}, result)
        self.assertEqual([self.URL], runner.urls())

    def test_only_pre_releases_gives_the_highest_pre_release(self):
        result, _ = self.resolve(["1.0.0-alpha", "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "0.9.0-z"])
        self.assertEqual("1.0.0-rc.1", result["version"])
        result, _ = self.resolve(["1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-beta.3"])
        self.assertEqual("1.0.0-beta.11", result["version"])

    def test_a_release_is_higher_than_its_own_pre_releases_and_four_parts_count(self):
        result, _ = self.resolve(["1.0.0-rc.1", "1.0.0", "1.0.0-zzz"])
        self.assertEqual("1.0.0", result["version"])
        four = ".".join(["1", "2", "3", "4"])
        result, _ = self.resolve(["1.2.3", four, "1.2.2"])
        self.assertEqual(four, result["version"])

    def test_the_order_does_not_depend_on_the_order_of_the_list(self):
        result, _ = self.resolve(["2.0.0", "1.0.0", "10.0.0", "9.0.0"])
        self.assertEqual("10.0.0", result["version"])

    def test_a_pinned_version_must_be_in_the_list(self):
        result, _ = self.resolve(["1.0.0", "1.1.0"], "1.0.0")
        self.assertEqual("1.0.0", result["version"])
        result, _ = self.resolve(["1.0.0", "1.1.0"], "2.0.0")
        self.assertEqual("unresolved", result["status"])
        self.assertIn("not found", result["detail"])
        result, _ = self.resolve(["1.0.0", "1.1.0-beta"], "1.1.0-beta")
        self.assertEqual("1.1.0-beta", result["version"])

    def test_the_list_may_contain_nothing_usable(self):
        for versions in ([], ["not-a-version"], [5, None]):
            result, _ = self.resolve(versions)
            self.assertEqual("unresolved", result["status"])
        result, _ = self.resolve(None, table={self.URL: HttpResult(200, {}, b"[]", None)})
        self.assertEqual("unresolved", result["status"])

    def test_failures_are_classified_and_clean(self):
        result, _ = self.resolve(None, table={self.URL: status_only(404)})
        self.assertEqual("unresolved", result["reason"])
        for answer in (failed("tls"), failed("dns"), status_only(500)):
            result, _ = self.resolve(None, table={self.URL: answer})
            self.assertEqual("network", result["reason"])
            assert_clean(self, result)

    def test_bad_ids_are_refused_before_any_call(self):
        for name in ("-x", "a b", "", "a/b", "a;b", "a?x"):
            runner = FakeRunner()
            self.assertEqual("unresolved", ts.resolve_package("nuget", name, "latest", runner)["status"], name)
            self.assertEqual([], runner.calls)


class ResolvePackageGeneralTests(unittest.TestCase):
    def test_an_unknown_ecosystem_is_unresolved(self):
        runner = FakeRunner()
        result = ts.resolve_package("cargo", "x", "latest", runner)
        self.assertEqual({"status": "unresolved", "reason": "unresolved", "detail": "unknown ecosystem"}, result)
        self.assertEqual([], runner.calls)

    def test_the_default_runner_is_the_real_one(self):
        self.assertTrue(callable(ts.resolve_package))
        self.assertEqual("unresolved", ts.resolve_package("cargo", "x", "latest", None)["status"])


class ErrorTests(unittest.TestCase):
    def test_the_code_is_the_text_before_the_first_colon(self):
        self.assertEqual("network", ts.SourceError("network: timeout").code)
        self.assertEqual("digest mismatch", ts.SourceError("digest mismatch: good-skill").code)
        self.assertEqual("conflict", ts.SourceError("conflict").code)
        self.assertIsInstance(ts.SourceError("x"), Exception)


if __name__ == "__main__":
    unittest.main()
