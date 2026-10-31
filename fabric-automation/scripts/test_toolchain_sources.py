#!/usr/bin/env python3
"""Tests for toolchain_sources.py: directory and git digests, skill lint, git and package resolvers, and vendoring a pinned pack.

Git is real. A small repository is built once with `git fast-import` in a temp folder and used through file:// URLs, with the
user's and the system's git configuration switched off. The package resolvers run against a fake runner that answers from a
table, so no network and no npm are used. Run from the project folder:

    python -m unittest scripts.test_toolchain_sources -v
"""

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
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
        "plugins/zeta/skills/ts-skill/SKILL.md": b"---\nname: ts-skill\ndescription: Has scripts.\n---\n# Ts\n",
        "plugins/zeta/skills/ts-skill/scripts/run.ts": b"// npm install left-pad\n",
        "plugins/zeta/skills/ts-skill/Dockerfile": b"RUN pip install requests\n",
        "plugins/zeta/skills/ts-skill/references/big.txt": b"x" * 300,
        "plugins/zeta/skills/ts-skill/assets/blob.bin": b"\x00" + b"y" * 300,
        "plugins/alpha/common/shared.md": b"# Shared\nline two\n",
        "plugins/alpha/common/notebook-authoring/nb.md": b"# Notebook\n",
        "plugins/alpha/common/data.bin": b"\x00\x01\r\n\x02",
        "plugins/alpha/common/legacy.txt": b"caf\xe9\nsecond\n",
        "plugins/alpha/common/windows.txt": b"one\r\ntwo\r\n",
        "plugins/alpha/common-extra/other.md": b"# Not shared\n",
        "plugins/beta/common/shared.md": b"# Shared\nline two\n",
        "plugins/beta/common/notebook-authoring/nb.md": b"# Notebook\n",
        "plugins/beta/common/data.bin": b"\x00\x01\r\n\x02",
        "plugins/beta/common/legacy.txt": b"caf\xe9\nsecond\n",
        "plugins/beta/common/windows.txt": b"one\r\ntwo\r\n",
        "plugins/gamma/common/other.md": b"# Other\n",
        "plugins/theta/skills/t-skill/SKILL.md": b"---\nname: t-skill\ndescription: Has a shared folder with a link.\n---\n# T\n",
        "plugins/theta/common/real.md": b"real\n",
        "plugins/theta/common/pointer": ("120000", b"real.md"),
        "plugins/eta/common/ok.md": b"ok\n",
        "plugins/eta/common/vendor": ("160000", b"cd" * 20),
        "plugins/iota/common/a.md": b"a\n",
        "plugins/iota/common/b.md": b"b\n",
        "plugins/iota/common/c.md": b"c\n",
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


class FakeEntry:
    """A stand-in for os.DirEntry: a real one cannot be given the attributes of a Windows junction on any system."""

    def __init__(self, name, *, symlink=False, directory=False, attributes=0, tag=0, stat_error=False):
        self.name, self.path = name, "fake-folder/" + name
        self._symlink, self._directory, self._stat_error = symlink, directory, stat_error
        self._info = types.SimpleNamespace(st_file_attributes=attributes, st_reparse_tag=tag)

    def is_symlink(self):
        return self._symlink

    def is_dir(self, follow_symlinks=True):
        return self._directory

    def is_file(self, follow_symlinks=True):
        return not self._directory

    def stat(self, follow_symlinks=True):
        if self._stat_error:
            raise OSError("cannot stat")
        return self._info


class _FakeScan:
    def __init__(self, entries):
        self.entries = entries

    def __enter__(self):
        return iter(self.entries)

    def __exit__(self, *exc):
        return False


DIRECTORY_ATTRIBUTE, REPARSE_ATTRIBUTE, ARCHIVE_ATTRIBUTE = 0x10, 0x400, 0x20
MOUNT_POINT_TAG, SYMLINK_TAG, CLOUD_TAG = 0xA0000003, 0xA000000C, 0x9000701A


class WalkTests(unittest.TestCase):
    """What _walk reports as a link: it must never go into a folder that is only a pointer to another place."""

    def walk(self, entries, windows):
        calls = []

        def scandir(path):
            calls.append(path)
            return _FakeScan(entries if len(calls) == 1 else [])
        with mock.patch.object(ts.os, "scandir", side_effect=scandir), mock.patch.object(ts, "WINDOWS", windows):
            return list(ts._walk("fake-folder")), calls

    def test_a_symbolic_link_to_a_folder_is_a_link_entry_and_is_not_followed(self):
        for windows in (False, True):
            found, calls = self.walk([FakeEntry("pointer", symlink=True, directory=True)], windows)
            self.assertEqual([("pointer", "fake-folder/pointer", True)], found)
            self.assertEqual(["fake-folder"], calls, "the link was followed")

    def test_a_symbolic_link_to_a_file_is_a_link_entry(self):
        found, _ = self.walk([FakeEntry("pointer", symlink=True)], False)
        self.assertEqual([("pointer", "fake-folder/pointer", True)], found)

    def test_a_windows_junction_is_a_link_entry_and_is_not_followed(self):
        junction = FakeEntry("junction", directory=True, attributes=DIRECTORY_ATTRIBUTE | REPARSE_ATTRIBUTE, tag=MOUNT_POINT_TAG)
        found, calls = self.walk([junction], True)
        self.assertEqual([("junction", "fake-folder/junction", True)], found)
        self.assertEqual(["fake-folder"], calls, "the junction was followed")

    def test_a_reparse_point_of_another_kind_is_an_ordinary_entry(self):
        placeholder = FakeEntry("placeholder.md", attributes=ARCHIVE_ATTRIBUTE | REPARSE_ATTRIBUTE, tag=CLOUD_TAG)
        folder = FakeEntry("folder", directory=True, attributes=DIRECTORY_ATTRIBUTE | REPARSE_ATTRIBUTE, tag=CLOUD_TAG)
        found, calls = self.walk([placeholder, folder], True)
        self.assertEqual([("placeholder.md", "fake-folder/placeholder.md", False)], found)
        self.assertEqual(["fake-folder", "fake-folder/folder"], calls)

    def test_a_junction_tag_without_the_reparse_attribute_and_a_plain_folder_are_ordinary(self):
        odd = FakeEntry("odd", directory=True, attributes=DIRECTORY_ATTRIBUTE, tag=MOUNT_POINT_TAG)
        plain = FakeEntry("plain.md", attributes=ARCHIVE_ATTRIBUTE)
        found, calls = self.walk([odd, plain], True)
        self.assertEqual([("plain.md", "fake-folder/plain.md", False)], found)
        self.assertEqual(["fake-folder", "fake-folder/odd"], calls)

    def test_the_windows_attributes_are_ignored_on_other_systems(self):
        junction = FakeEntry("junction", directory=True, attributes=DIRECTORY_ATTRIBUTE | REPARSE_ATTRIBUTE, tag=MOUNT_POINT_TAG)
        found, calls = self.walk([junction], False)
        self.assertEqual([], found)
        self.assertEqual(["fake-folder", "fake-folder/junction"], calls)

    def test_an_entry_that_cannot_be_examined_is_a_source_error(self):
        with self.assertRaises(ts.SourceError) as caught:
            self.walk([FakeEntry("broken", attributes=ARCHIVE_ATTRIBUTE, stat_error=True)], True)
        self.assertEqual("unresolved", caught.exception.code)

    @unittest.skipUnless(WINDOWS, "junctions are a Windows matter")
    def test_a_real_junction_is_a_link_entry_and_what_it_points_to_does_not_change_the_digest(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root, outside = Path(tmp.name) / "skill", Path(tmp.name) / "outside"
        write_tree(root, {"SKILL.md": b"x\n"})
        write_tree(outside, {"secret.txt": b"one\n", "notes.md": b"pip install somepackage\n"})
        link = root / "shared"
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True, check=False)
        if made.returncode != 0 or not link.exists():
            self.skipTest("this account cannot create a junction")
        self.addCleanup(lambda: os.path.lexists(link) and os.rmdir(link))
        expected = spec_digest({"SKILL.md": b"x\n", "shared": os.readlink(link).encode("utf-8", "surrogateescape")})
        self.assertEqual(expected, ts.digest_tree(root))
        write_tree(outside, {"secret.txt": b"two\n", "more.txt": b"more\n"})
        self.assertEqual(expected, ts.digest_tree(root))
        self.assertEqual(0, ts.lint_skill(root)["install_hints"], "the junction was read by the lint")


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

    def test_install_hints_are_counted_once_each_in_every_text_file(self):
        text = "\n".join([
            "pip install a", "python -m pip install b", "uv pip install c", "npm install d", "npm i e", "npm exec f", "npx g", "dotnet tool install h",
            "winget install i", "brew install j", "apt install k", "apt-get install l", "choco install m", "Install-Module n", "az extension add o",
            "pip3 install p", "sudo apt-get install q", "PIP INSTALL r"])
        extra = {"references/a.md": text, "scripts/b.sh": "pip install x\n", "scripts/c.ps1": "Install-Module y\n", "data/d.json": '{"run": "npm install z"}',
                 "scripts/e.py": "# pip install w\n", "notes/f.txt": "brew install v\n", "ci/g.yml": "run: npx -y tool\n", "ci/h.yaml": "run: choco install u\n",
                 "assets/i.png": b"\x89PNG\x00 pip install hidden", "docs/j.rst": "pip install counted\n"}
        result = self.lint("---\nname: demo-skill\ndescription: d\n---\nbody\n", extra=extra)
        self.assertEqual(26, result["install_hints"])

    def test_an_install_command_in_any_kind_of_text_file_is_counted(self):
        names = ("scripts/run.ts", "scripts/run.js", "scripts/run.mjs", "scripts/run.cmd", "scripts/run.bat", "src/Program.cs", "infra/main.bicep",
                 "infra/main.tf", "Dockerfile", "docker/Dockerfile.dev", "scripts/noextension", "scripts/run.rb", "assets/page.html", "data/notes.csv",
                 "scripts/run.PS1", "scripts/RUN.TS", ".hidden/setup")
        for name in names:
            with self.subTest(name):
                result = self.lint("---\nname: demo-skill\ndescription: d\n---\nbody\n", extra={name: "RUN npm install left-pad\n"})
                self.assertEqual(1, result["install_hints"], name)
                self.assertEqual([], result["findings"], name)

    def test_a_file_with_a_nul_byte_is_binary_and_is_not_scanned_whatever_its_name(self):
        for name in ("scripts/run.ts", "Dockerfile", "references/a.md", "assets/blob.bin"):
            result = self.lint("---\nname: demo-skill\ndescription: d\n---\nbody\n", extra={name: b"pip install x\x00 pip install y\n"})
            self.assertEqual(0, result["install_hints"], name)
            self.assertEqual([], result["findings"], name)

    def test_a_text_file_over_the_limit_is_a_finding_and_is_not_counted(self):
        with mock.patch.object(ts, "MAX_LINT_FILE", 100):
            small = "pip install a\n" + "x" * 86
            self.assertEqual(100, len(small))
            extra = {"references/ok.txt": small, "references/big.txt": small + "y", "scripts/big.ts": "npm install z\n" + "x" * 200}
            result = self.lint("---\nname: demo-skill\ndescription: d\n---\nbody\n", extra=extra)
        self.assertEqual(1, result["install_hints"])
        self.assertEqual(["file too large to scan: references/big.txt", "file too large to scan: scripts/big.ts"], result["findings"])
        self.assertTrue(result["frontmatter_ok"])

    def test_a_large_binary_file_is_not_a_finding(self):
        with mock.patch.object(ts, "MAX_LINT_FILE", 100):
            result = self.lint("---\nname: demo-skill\ndescription: d\n---\nbody\n", extra={"assets/image.png": b"\x89PNG\r\n\x1a\n\x00" + b"z" * 500})
        self.assertEqual([], result["findings"])

    def test_only_the_beginning_of_a_large_file_decides_whether_it_is_text(self):
        late_nul = b"x" * 66000 + b"\x00" + b"x" * 4000
        early_nul = b"x" * 100 + b"\x00" + b"x" * 69000
        with mock.patch.object(ts, "MAX_LINT_FILE", 100):
            result = self.lint("---\nname: demo-skill\ndescription: d\n---\nbody\n", extra={"data/late.bin": late_nul, "data/early.bin": early_nul})
            in_memory = ts._lint_files({"SKILL.md": b"---\nname: demo-skill\ndescription: d\n---\nbody\n", "data/late.bin": late_nul, "data/early.bin": early_nul}, "demo-skill")
        self.assertEqual(["file too large to scan: data/late.bin"], result["findings"])
        self.assertEqual(result["findings"], in_memory["findings"], "git objects and a folder on disk are not linted by the same rule")

    def test_a_skill_md_over_the_limit_is_still_read_and_is_a_finding(self):
        with mock.patch.object(ts, "MAX_LINT_FILE", 100):
            result = self.lint("---\nname: demo-skill\ndescription: d\n---\n" + "npm install a\n" * 20)
        self.assertEqual("demo-skill", result["name"])
        self.assertTrue(result["frontmatter_ok"])
        self.assertEqual(0, result["install_hints"])
        self.assertEqual(["file too large to scan: SKILL.md"], result["findings"])

    def test_the_findings_about_size_come_after_the_others_and_name_the_path_safely(self):
        with mock.patch.object(ts, "MAX_LINT_FILE", 100):
            long_name = "references/" + "d" * 100 + ".txt"
            extra = {"references/caf\u00e9 name$.txt": "x" * 200, long_name: "x" * 200}
            result = self.lint("---\nname: other\ndescription: d\n---\n", extra=extra)
        self.assertEqual("name does not match folder", result["findings"][0])
        sizes = result["findings"][1:]
        self.assertEqual(2, len(sizes))
        for finding in sizes:
            self.assertRegex(finding, r"^file too large to scan: [A-Za-z0-9._ /?-]{1,80}$")
        self.assertIn("file too large to scan: references/caf? name?.txt", sizes)
        self.assertTrue(any(len(finding) == len("file too large to scan: ") + 80 for finding in sizes), sizes)

    def test_a_skill_with_too_many_files_or_bytes_is_a_finding_that_names_the_first_file_beyond_the_limit(self):
        files = {"SKILL.md": "---\nname: demo-skill\ndescription: d\n---\n", "a/one.txt": "pip install a\n", "b/two.txt": "pip install b\n",
                 "c/three.txt": "pip install c\n", "d/four.txt": "pip install d\n"}
        with mock.patch.object(ts, "MAX_TREE_FILES", 3):
            result = self.lint(files["SKILL.md"], extra={k: v for k, v in files.items() if k != "SKILL.md"})
        self.assertEqual(["skill too large to scan from: c/three.txt"], result["findings"])
        self.assertEqual(2, result["install_hints"])
        with mock.patch.object(ts, "MAX_TREE_FILES", 5):
            result = self.lint(files["SKILL.md"], extra={k: v for k, v in files.items() if k != "SKILL.md"})
        self.assertEqual([], result["findings"])
        self.assertEqual(4, result["install_hints"])
        total = sum(len(v) for v in files.values())
        with mock.patch.object(ts, "MAX_TREE_BYTES", total - 1):
            result = self.lint(files["SKILL.md"], extra={k: v for k, v in files.items() if k != "SKILL.md"})
        self.assertEqual(["skill too large to scan from: d/four.txt"], result["findings"])
        with mock.patch.object(ts, "MAX_TREE_BYTES", total):
            result = self.lint(files["SKILL.md"], extra={k: v for k, v in files.items() if k != "SKILL.md"})
        self.assertEqual([], result["findings"])

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

    def test_a_file_url_with_a_host_is_a_network_path_and_never_reaches_git(self):
        urls = ("file://server/share/r.git", "file://localhost/r.git", "file://C:/r.git", "file:////server/share/r.git",
                "file://///server/share/r.git", "file:relative/r.git", "file:///C:\\r.git", "file:///r.git?x=1", "file:///r.git#x")
        for url in urls:
            for call in (lambda fake: ts.resolve_git_ref(url, {"kind": "tag", "pattern": "v*"}, fake),
                         lambda fake: ts.fetch_git(url, "ab" * 20, Path(TMP.name) / "never-created", fake)):
                fake = FakeGit()
                with self.assertRaises(ts.SourceError, msg=url) as caught:
                    call(fake)
                self.assertEqual("unresolved", caught.exception.code, url)
                self.assertEqual([], fake.calls, url)
        self.assertTrue(self.resolve({"kind": "tag", "pattern": "v*"})["commit"])

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
    """A runner for git that answers from a script and records the argument lists and the environments."""

    def __init__(self, fetch_works=True):
        self.calls = []
        self.envs = []
        self.fetched = False
        self.fetch_works = fetch_works

    def which(self, name):
        return name

    def run(self, argv, *, cwd=None, env=None, timeout=60, input=None):
        self.calls.append(list(argv))
        self.envs.append(dict(env or {}))
        if "fetch" in argv:
            self.fetched = self.fetch_works
            return CommandResult(0 if self.fetch_works else 128, "", "" if self.fetch_works else "fatal: could not read from remote")
        if "cat-file" in argv:
            return CommandResult(0 if self.fetched else 128, "", "")
        if "ls-remote" in argv:
            return CommandResult(128, "", "fatal: unable to access")
        return CommandResult(0, "", "")


class NoGit:
    """A runner that must not be used: whatever is run through it is recorded and fails."""

    def __init__(self):
        self.calls = []

    def which(self, name):
        return name

    def run(self, argv, **kwargs):
        self.calls.append(list(argv))
        return CommandResult(128, "", "fatal: no git here")

    def run_bytes(self, argv, **kwargs):
        self.calls.append(list(argv))
        return toolchain_io.RawResult(128, b"", b"fatal: no git here")


class RecordingRunner(toolchain_io.SystemRunner):
    """The real runner with no isolation of its own: git gets exactly the environment that the module asks for."""

    def __init__(self):
        self.calls = []

    def run_bytes(self, argv, *, cwd=None, env=None, timeout=60, input=None):
        self.calls.append((list(argv), dict(env or {})))
        return super().run_bytes(argv, cwd=cwd, env=env, timeout=timeout, input=input)

    def with_word(self, word):
        return [call for call in self.calls if word in call[0]]


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


NETWORK_DROPPED = ("GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS", "GIT_ASKPASS", "GIT_SSH", "GIT_SSH_COMMAND", "SSH_ASKPASS")


@unittest.skipUnless(HAS_GIT, "git is not installed")
class PrivateGitSettingsTests(unittest.TestCase):
    """Every git call runs with a private configuration: what the settings are, call by call."""

    def setUp(self):
        self.runner = RecordingRunner()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dest = Path(self.tmp.name) / "cache"

    def check_private(self, env, label):
        self.assertEqual(os.devnull, env.get("GIT_CONFIG_GLOBAL"), label)
        self.assertEqual("1", env.get("GIT_CONFIG_NOSYSTEM"), label)
        self.assertEqual("0", env.get("GIT_TERMINAL_PROMPT"), label)
        for name in ("GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS"):
            self.assertIn(name, env, label)
            self.assertIsNone(env[name], "%s %s" % (label, name))

    def test_a_network_call_gets_the_private_configuration_and_only_the_allowed_protocols(self):
        ts.resolve_git_ref(FX.url, {"kind": "tag", "pattern": "v*"}, self.runner)
        ts.fetch_git(FX.url, FX.commits[3], self.dest, self.runner)
        network = self.runner.with_word("ls-remote") + self.runner.with_word("fetch")
        self.assertEqual(2, len(network))
        for argv, env in network:
            label = argv[argv.index("--git-dir") + 2] if "--git-dir" in argv else argv[argv.index("ls-remote")]
            self.check_private(env, label)
            self.assertEqual("https:file", env.get("GIT_ALLOW_PROTOCOL"), label)
            for name in NETWORK_DROPPED:
                self.assertIn(name, env, "%s %s" % (label, name))
                self.assertIsNone(env[name], "%s %s" % (label, name))
            subcommand = min(argv.index(word) for word in ("ls-remote", "--git-dir") if word in argv)
            options = argv[1:subcommand]
            self.assertIn("protocol.ext.allow=never", options, label)
            self.assertIn("credential.helper=", options, label)
            for setting in ("protocol.ext.allow=never", "credential.helper="):
                self.assertEqual("-c", options[options.index(setting) - 1], label)

    def test_a_network_call_for_an_https_address_allows_https_only(self):
        for call in (lambda fake: ts.resolve_git_ref("https://example.test/o/r.git", {"kind": "tag", "pattern": "v*"}, fake),
                     lambda fake: ts.fetch_git("https://example.test/o/r.git", "ab" * 20, self.dest, fake)):
            fake = FakeGit()
            try:
                call(fake)
            except ts.SourceError:
                pass
            env = [env for argv, env in zip(fake.calls, fake.envs) if "ls-remote" in argv or "fetch" in argv][0]
            self.assertEqual("https", env.get("GIT_ALLOW_PROTOCOL"))
            self.check_private(env, "https")

    def test_the_numbered_configuration_variables_that_are_set_are_removed(self):
        names = ("GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0", "GIT_CONFIG_KEY_12", "GIT_CONFIG_VALUE_12")
        others = ("GIT_CONFIG_KEYS", "GIT_CONFIG_KEY_", "GIT_CONFIG_KEY_X", "GIT_CONFIG_VALUE_1X")
        with mock.patch.dict(os.environ, {name: "x" for name in names + others}):
            fake = FakeGit()
            try:
                ts.resolve_git_ref("https://example.test/o/r.git", {"kind": "tag", "pattern": "v*"}, fake)
            except ts.SourceError:
                pass
            ts.fetch_git("https://example.test/o/r.git", "ab" * 20, self.dest, fake)
            env_by_call = list(zip(fake.calls, fake.envs))
        self.assertTrue(env_by_call)
        for argv, env in env_by_call:
            for name in names:
                self.assertIn(name, env, "%s in %s" % (name, argv[1:6]))
                self.assertIsNone(env[name], name)
            for name in others:
                self.assertNotIn(name, env, name)

    def test_a_local_call_gets_the_same_environment_without_the_network_keys(self):
        ts.fetch_git(FX.url, FX.commits[3], self.dest, self.runner)
        ts.digest_git_tree(self.dest, FX.commits[3], "plugins/alpha/skills/good-skill", self.runner)
        local = [(argv, env) for argv, env in self.runner.calls if "ls-remote" not in argv and "fetch" not in argv]
        words = {word for argv, _ in local for word in ("init", "cat-file", "ls-tree") if word in argv}
        self.assertEqual({"init", "cat-file", "ls-tree"}, words)
        for argv, env in local:
            self.check_private(env, argv[1:6])
            self.assertFalse(env.get("GIT_ALLOW_PROTOCOL"), argv[1:6])
            for name in ("GIT_ASKPASS", "GIT_SSH", "GIT_SSH_COMMAND", "SSH_ASKPASS"):
                self.assertNotIn(name, env, argv[1:6])

    def test_the_private_environment_is_built_for_each_call(self):
        first = ts._git_env(True, False)
        first["GIT_CONFIG_GLOBAL"] = "changed"
        self.assertEqual(os.devnull, ts._git_env(True, False)["GIT_CONFIG_GLOBAL"])
        self.assertEqual(os.devnull, ts._git_env()["GIT_CONFIG_GLOBAL"])


class _HostileConfigBase(unittest.TestCase):
    """The operator's own git configuration and environment are hostile: they rewrite the address of the repository. Real git."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        cls.decoy = cls.dir / "decoy.git"
        cls.git("init", "--bare", "--quiet", str(cls.decoy), use_dir=False)
        cls.git("-c", "protocol.file.allow=always", "fetch", "--quiet", FX.url, FX.commits[1], use_dir=True)
        cls.git("tag", "v9.9.9", FX.commits[1])
        cls.decoy_url = cls.decoy.as_uri()
        cls.rewrite = cls.dir / "rewrite.gitconfig"
        cls.rewrite.write_text('[url "%s"]\n\tinsteadOf = %s\n' % (cls.decoy_url, FX.url), encoding="utf-8")
        cls.home = cls.dir / "home"
        cls.home.mkdir()
        (cls.home / ".gitconfig").write_text(cls.rewrite.read_text(encoding="utf-8"), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def git(cls, *args, use_dir=True):
        argv = ["git"] + (["--git-dir", str(cls.decoy)] if use_dir else []) + list(args)
        raw = FX.runner.run_bytes(argv)
        if raw.returncode != 0:
            raise AssertionError("git %s failed: %s" % (args[0], raw.stderr.decode("utf-8", "replace")))

    def unprotected_view(self, env_extra, dropped=()):
        """What plain git, without the protection of the module, lists for the address of the fixture."""
        env = dict(os.environ)
        env.update(env_extra)
        for name in dropped:
            env.pop(name, None)
        done = subprocess.run(["git", "-c", "protocol.file.allow=always", "ls-remote", "--tags", FX.url], env=env, cwd=str(self.dir),
                              capture_output=True, text=True, timeout=60, check=False)
        return done.stdout

    def hostile_cases(self):
        count_key = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "url.%s.insteadOf" % self.decoy_url, "GIT_CONFIG_VALUE_0": FX.url}
        parameters = {"GIT_CONFIG_PARAMETERS": "'url.%s.insteadof'='%s'" % (self.decoy_url, FX.url)}
        return (("a global configuration file", {"GIT_CONFIG_GLOBAL": str(self.rewrite)}, ()),
                ("the home folder", {"HOME": str(self.home), "USERPROFILE": str(self.home)}, ("GIT_CONFIG_GLOBAL", "XDG_CONFIG_HOME")),
                ("a system configuration file", {"GIT_CONFIG_SYSTEM": str(self.rewrite)}, ()),
                ("numbered configuration variables", count_key, ()),
                ("configuration parameters", parameters, ()))


@unittest.skipUnless(HAS_GIT, "git is not installed")
class HostileGitConfigurationTests(_HostileConfigBase):
    def test_no_hostile_setting_can_send_the_call_to_another_repository(self):
        for number, (label, env_extra, dropped) in enumerate(self.hostile_cases()):
            with self.subTest(label):
                if "refs/tags/v9.9.9" not in self.unprotected_view(env_extra, dropped):
                    self.skipTest("this git does not take the address rewrite from %s" % label)
                dest = self.dir / ("cache-%d" % number)
                with mock.patch.dict(os.environ, env_extra):
                    for name in dropped:
                        os.environ.pop(name, None)
                    found = ts.resolve_git_ref(FX.url, {"kind": "tag", "pattern": "v*"}, RecordingRunner())
                    self.assertEqual("v1.10.0", found["tag"], "the address was rewritten by " + label)
                    ts.fetch_git(FX.url, FX.commits[3], dest, RecordingRunner())
                self.assertEqual(0, FX.runner.run(["git", "--git-dir", str(dest), "cat-file", "-e", FX.commits[3] + "^{commit}"]).returncode, label)


@unittest.skipUnless(HAS_GIT, "git is not installed")
class ExtHelperTests(_HostileConfigBase):
    """`protocol.ext.allow=always` and an address rewritten to ext:: would run a program: nothing of the kind may happen."""

    URL = "https://localhost:1/o/r.git"

    def setUp(self):
        self.marker = self.dir / "ext-ran.txt"
        if self.marker.exists():
            self.marker.unlink()
        helper = self.dir / "helper.py"
        helper.write_text("with open(%r, 'w') as handle:\n    handle.write('ran')\n" % self.marker.as_posix(), encoding="utf-8")

        def spaced(path):
            return path.replace("%", "%%").replace(" ", "% ")
        command = "ext::%s %s" % (spaced(Path(sys.executable).as_posix()), spaced(helper.as_posix()))
        self.config = self.dir / "ext.gitconfig"
        self.config.write_text('[protocol "ext"]\n\tallow = always\n[url "%s"]\n\tinsteadOf = %s\n' % (command, self.URL), encoding="utf-8")

    def test_an_address_rewritten_to_an_ext_helper_never_runs_it(self):
        env = dict(os.environ, GIT_CONFIG_GLOBAL=str(self.config), GIT_TERMINAL_PROMPT="0")
        subprocess.run(["git", "ls-remote", "--tags", self.URL], env=env, cwd=str(self.dir), capture_output=True, timeout=60, check=False)
        if not self.marker.exists():
            self.skipTest("this git did not run the ext helper even without protection")
        self.marker.unlink()
        with mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(self.config)}):
            with self.assertRaises(ts.SourceError):
                ts.resolve_git_ref(self.URL, {"kind": "tag", "pattern": "v*"}, RecordingRunner())
            with self.assertRaises(ts.SourceError):
                ts.fetch_git(self.URL, "ab" * 20, self.dir / "ext-cache", RecordingRunner())
        self.assertFalse(self.marker.exists(), "the ext helper was run")


SHARED_FILES = {"shared.md": b"# Shared\nline two\n", "notebook-authoring/nb.md": b"# Notebook\n", "data.bin": b"\x00\x01\r\n\x02", "legacy.txt": b"caf\xe9\nsecond\n",
                "windows.txt": b"one\r\ntwo\r\n"}


def content_digest(data):
    """The digest of one file by the rule of the specification: text with CRLF is hashed with LF, a file with a NUL byte as it is."""
    return "sha256:" + hashlib.sha256(data if b"\x00" in data else data.replace(b"\r\n", b"\n")).hexdigest()


@unittest.skipUnless(HAS_GIT, "git is not installed")
class ReadPluginTests(unittest.TestCase):
    def setUp(self):
        self.runner = IsolatedRunner()

    def read(self, plugin, commit=None):
        return ts.read_plugin(FX.git_dir, commit or FX.commits[3], "plugins/" + plugin, self.runner)

    def test_the_shape_of_the_answer(self):
        info = self.read("alpha")
        self.assertEqual({"version", "skills", "agents", "bundled_mcp", "shared"}, set(info))
        self.assertEqual("1.2.0", info["version"])
        self.assertEqual(["Helper.agent.md"], info["agents"])
        self.assertEqual(["Alpha-Server", "zeta-server"], info["bundled_mcp"])
        self.assertEqual({}, info["shared"])

    def test_only_folders_with_a_skill_md_are_skills(self):
        self.assertEqual(["bad-skill", "good-skill", "link-skill"], sorted(self.read("alpha")["skills"]))
        self.assertEqual(["good-skill", "other-skill"], sorted(self.read("beta")["skills"]))

    def test_a_plugin_without_skills_or_manifest(self):
        info = self.read("delta")
        self.assertEqual({"version": None, "skills": {}, "agents": [], "bundled_mcp": [], "shared": {}}, info)
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

    def test_every_text_file_is_linted_and_one_over_the_limit_is_a_finding(self):
        with mock.patch.object(ts, "MAX_LINT_FILE", 200):
            entry = self.read("zeta")["skills"]["ts-skill"]
        self.assertEqual(2, entry["install_hints"])
        self.assertEqual(["file too large to scan: references/big.txt"], entry["findings"])
        entry = self.read("zeta")["skills"]["ts-skill"]
        self.assertEqual(2, entry["install_hints"])
        self.assertEqual([], entry["findings"])

    def test_the_lint_of_git_objects_and_of_a_folder_on_disk_agree(self):
        prefix = "plugins/zeta/skills/ts-skill/"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ts-skill"
            write_tree(root, {key[len(prefix):]: value for key, value in final_files().items() if key.startswith(prefix)})
            for limit in (200, 2 * 1024 * 1024):
                with mock.patch.object(ts, "MAX_LINT_FILE", limit):
                    entry = self.read("zeta")["skills"]["ts-skill"]
                    disk = ts.lint_skill(root)
                self.assertEqual((disk["install_hints"], disk["findings"], disk["description_chars"]),
                                 (entry["install_hints"], entry["findings"], entry["description_chars"]), limit)

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

    def shared(self, plugin, *folders, commit=None, runner=None):
        return ts.read_plugin(FX.git_dir, commit or FX.commits[3], "plugins/" + plugin, runner or self.runner, shared=folders)

    def test_a_shared_folder_has_the_digest_of_a_skill_over_its_files_and_the_rest_of_the_answer_is_unchanged(self):
        info = self.shared("alpha", "common")
        self.assertEqual({"common": spec_digest(SHARED_FILES)}, info["shared"])
        self.assertEqual({"digest", "files", "bytes"}, set(info["shared"]["common"]))
        plain = self.read("alpha")
        for key in ("version", "skills", "agents", "bundled_mcp"):
            self.assertEqual(plain[key], info[key], key)

    def test_the_names_may_come_as_a_tuple_a_list_a_repeated_name_or_a_bare_string(self):
        expected = {"common": spec_digest(SHARED_FILES)}
        for names in (("common",), ["common"], ("common", "common"), "common"):
            self.assertEqual(expected, ts.read_plugin(FX.git_dir, FX.commits[3], "plugins/alpha", self.runner, shared=names)["shared"], names)

    def test_a_shared_folder_of_a_checkout_has_the_same_digest_with_either_line_ending(self):
        info = self.shared("alpha", "common")["shared"]["common"]
        for autocrlf in ("true", "false"):
            with tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "checkout"
                FX.clone(dest, autocrlf, FX.commits[3])
                self.assertEqual(info, ts.digest_tree(dest / "plugins" / "alpha" / "common"), "autocrlf=" + autocrlf)

    def test_identical_shared_folders_of_two_plugins_have_one_digest_and_a_different_one_another(self):
        self.assertEqual(self.shared("alpha", "common")["shared"], self.shared("beta", "common")["shared"])
        self.assertNotEqual(self.shared("alpha", "common")["shared"], self.shared("gamma", "common")["shared"])

    def test_read_shared_entries_gives_the_digest_of_the_content_of_every_file(self):
        entries = ts.read_shared_entries(FX.git_dir, FX.commits[3], "plugins/alpha", "common", self.runner)
        self.assertEqual({rel: content_digest(data) for rel, data in SHARED_FILES.items()}, entries)
        self.assertEqual({}, ts.read_shared_entries(FX.git_dir, FX.commits[3], "plugins/alpha", "nothing", self.runner))
        self.assertEqual({}, ts.read_shared_entries(FX.git_dir, FX.commits[1], "plugins/alpha", "common", self.runner))
        with self.assertRaises(ts.SourceError):
            ts.read_shared_entries(FX.git_dir, FX.commits[1], "plugins/beta", "common", self.runner)

    def test_a_missing_shared_folder_is_a_source_error(self):
        for plugin, folder, commit in (("alpha", "nothing", FX.commits[3]), ("alpha", "common", FX.commits[1]), ("delta", "common", FX.commits[3])):
            with self.assertRaises(ts.SourceError, msg=(plugin, folder)) as caught:
                self.shared(plugin, folder, commit=commit)
            self.assertEqual("unresolved", caught.exception.code)
            self.assertIn("shared folder not found", str(caught.exception))

    def test_bad_shared_names_are_refused_before_git_runs(self):
        for name in ("skills", "Common", ".hidden", "a/b", "a\\b", "..", "", "x" * 65, "con", "nul.txt", "common.", "com1", "common x", 5, None, "-"):
            nothing = NoGit()
            for call in (lambda: ts.read_plugin(FX.git_dir, FX.commits[3], "plugins/beta", nothing, shared=(name,)),
                         lambda: ts.read_shared_entries(FX.git_dir, FX.commits[3], "plugins/beta", name, nothing)):
                with self.assertRaises(ts.SourceError, msg=repr(name)) as caught:
                    call()
                self.assertEqual("unresolved", caught.exception.code, repr(name))
                self.assertIn("bad shared folder name", str(caught.exception), repr(name))
            self.assertEqual([], nothing.calls, repr(name))

    def test_a_link_or_a_submodule_inside_a_shared_folder_is_refused(self):
        with self.assertRaises(ts.SourceError) as caught:
            self.shared("theta", "common")
        self.assertIn("link", str(caught.exception))
        self.assertEqual(["t-skill"], list(self.read("theta")["skills"]), "a link in a folder that nobody shares is no problem")
        with self.assertRaises(ts.SourceError) as caught:
            ts.read_shared_entries(FX.git_dir, FX.commits[3], "plugins/theta", "common", self.runner)
        self.assertIn("link", str(caught.exception))
        for call in (lambda: self.shared("eta", "common"), lambda: ts.read_shared_entries(FX.git_dir, FX.commits[3], "plugins/eta", "common", self.runner)):
            with self.assertRaises(ts.SourceError) as caught:
                call()
            self.assertIn("submodule", str(caught.exception))

    def test_bundled_server_names_that_are_not_plain_labels_are_cleaned_or_unknown(self):
        servers = {"ok-name": {}, "Fine Name 2": {}, "ms/learn": {}, "a@b": {}, "x" * 80: {}, "Odd Name!": {}, "": {}, 5: {}}
        self.assertEqual(sorted(["Fine Name 2", "Odd Name", "ok-name", "unknown", "unknown", "unknown", "x" * 64]), ts._mcp_names(servers))
        self.assertEqual([], ts._mcp_names(None))
        self.assertEqual([], ts._mcp_names(["a"]))

    def test_the_limits_of_a_skill_apply_to_a_shared_folder(self):
        for name, limit, fails in (("MAX_TREE_FILES", 2, True), ("MAX_TREE_FILES", 3, False), ("MAX_TREE_BYTES", 5, True), ("MAX_TREE_BYTES", 6, False)):
            with mock.patch.object(ts, name, limit):
                for call in (lambda: self.shared("iota", "common"), lambda: ts.read_shared_entries(FX.git_dir, FX.commits[3], "plugins/iota", "common", self.runner)):
                    if fails:
                        with self.assertRaises(ts.SourceError, msg=(name, limit)) as caught:
                            call()
                        self.assertIn("too large", str(caught.exception))
                    else:
                        call()
        self.assertEqual({"digest", "files", "bytes"}, set(self.shared("iota", "common")["shared"]["common"]))
        self.assertEqual(3, self.shared("iota", "common")["shared"]["common"]["files"])
        self.assertEqual(6, self.shared("iota", "common")["shared"]["common"]["bytes"])


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
                            "bytes": self.lock["skill_sources"]["fx"]["plugins"]["beta"]["skills"]["other-skill"]["bytes"]}}, "shared": {}}, manifest)
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

    def test_nothing_selected_and_nothing_shared_changes_nothing(self):
        before = self.vendor([("fx", "alpha", "good-skill"), ("fx", "beta", "other-skill")])
        snapshot = {p.relative_to(self.store).as_posix(): p.read_bytes() for p in self.store.rglob("*") if p.is_file() and ".cache" not in p.parts}
        self.runner.calls.clear()
        self.assertEqual(before, self.vendor([]))
        self.assertEqual(before, self.vendor([], shared=[]))
        self.assertEqual([], self.runner.calls)
        self.assertEqual(snapshot, {p.relative_to(self.store).as_posix(): p.read_bytes() for p in self.store.rglob("*") if p.is_file() and ".cache" not in p.parts})
        self.assertEqual(["good-skill", "other-skill"], sorted(p.name for p in (self.store / "skills").iterdir()))

    def test_nothing_selected_in_a_store_without_a_manifest_creates_nothing(self):
        manifest = self.vendor([])
        self.assertEqual({"schema": 1, "lock_inputs_digest": self.lock["inputs_digest"], "skills": {}, "shared": {}}, manifest)
        self.assertFalse(self.store.exists())
        self.assertEqual([], self.runner.calls)

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

    # ---- shared folders of a plugin ----

    def add_shared(self, folder="common", plugin="alpha", source="fx"):
        info = ts.read_plugin(FX.git_dir, FX.commits[3], "plugins/" + plugin, self.runner, shared=(folder,))["shared"][folder]
        self.lock["skill_sources"][source].setdefault("shared", {})[folder] = dict(info, plugin=plugin)
        return info

    def snapshot(self):
        return {p.relative_to(self.store).as_posix(): p.read_bytes() for p in self.store.rglob("*") if p.is_file() and ".cache" not in p.parts}

    def leftovers(self):
        return [p.name for p in self.store.iterdir() if p.name.startswith((".staging", ".backup", "MANIFEST.json."))] if self.store.is_dir() else []

    def test_a_shared_folder_is_written_beside_the_skills_and_verified_against_the_lock(self):
        info = self.add_shared()
        manifest = self.vendor([("fx", "alpha", "good-skill")], shared=[("fx", "common")])
        self.assertEqual(info["digest"], ts.digest_tree(self.store / "common")["digest"])
        self.assertEqual({"common": {"source": "fx", "plugin": "alpha", "commit": FX.commits[3], "digest": info["digest"], "files": info["files"],
                                     "bytes": info["bytes"]}}, manifest["shared"])
        self.assertEqual(["good-skill"], list(manifest["skills"]))
        self.assertEqual(manifest, json.loads((self.store / "MANIFEST.json").read_text(encoding="utf-8")))
        self.assertEqual(["common", "skills"], sorted(p.name for p in self.store.iterdir() if p.is_dir() and not p.name.startswith(".")))
        self.assertFalse((self.store / "skills" / "common").exists())
        self.assertEqual([], self.leftovers())

    def test_a_shared_folder_keeps_its_subfolders_text_is_written_with_lf_and_binary_as_it_is(self):
        self.add_shared()
        self.vendor([("fx", "alpha", "good-skill")], shared=[("fx", "common")])
        for rel, data in SHARED_FILES.items():
            expected = data if b"\x00" in data else data.replace(b"\r\n", b"\n")
            self.assertEqual(expected, (self.store / "common" / rel).read_bytes(), rel)

    def test_the_manifest_has_a_shared_entry_even_when_nothing_is_shared(self):
        self.assertEqual({}, self.vendor([("fx", "alpha", "good-skill")])["shared"])

    def test_shared_folders_alone_can_be_vendored_and_skills_not_selected_then_are_removed(self):
        self.vendor([("fx", "alpha", "good-skill")])
        self.add_shared()
        manifest = self.vendor([], shared=[("fx", "common")])
        self.assertEqual({}, manifest["skills"])
        self.assertEqual(["common"], list(manifest["shared"]))
        self.assertEqual([], [p for p in (self.store / "skills").iterdir()])

    def test_the_digest_of_a_shared_folder_is_checked_before_anything_is_replaced(self):
        info = self.add_shared()
        self.vendor([("fx", "alpha", "good-skill")], shared=[("fx", "common")])
        (self.store / "common" / "shared.md").write_bytes(b"damaged\n")
        (self.store / "skills" / "good-skill" / "SKILL.md").write_bytes(b"damaged\n")
        before = self.snapshot()
        self.lock["skill_sources"]["fx"]["shared"]["common"]["digest"] = "sha256:" + "3" * 64
        with mock.patch.object(ts, "_move", side_effect=ts._move) as moved:
            with self.assertRaises(ts.SourceError) as caught:
                self.vendor([("fx", "alpha", "good-skill"), ("fx", "beta", "other-skill")], shared=[("fx", "common")])
            moved.assert_not_called()
        self.assertEqual("digest mismatch", caught.exception.code)
        self.assertEqual(before, self.snapshot(), "something was replaced although the check failed")
        self.assertEqual([], self.leftovers())
        self.lock["skill_sources"]["fx"]["shared"]["common"]["digest"] = info["digest"]
        self.lock["skill_sources"]["fx"]["plugins"]["beta"]["skills"]["other-skill"]["digest"] = "sha256:" + "4" * 64
        with mock.patch.object(ts, "_move", side_effect=ts._move) as moved:
            with self.assertRaises(ts.SourceError) as caught:
                self.vendor([("fx", "alpha", "good-skill"), ("fx", "beta", "other-skill")], shared=[("fx", "common")])
            moved.assert_not_called()
        self.assertEqual("digest mismatch", caught.exception.code)
        self.assertEqual(before, self.snapshot(), "a damaged shared folder was repaired although another check failed")

    def test_when_the_rollback_fails_too_the_old_folders_are_kept_in_a_backup_not_deleted(self):
        self.add_shared()
        self.vendor([("fx", "alpha", "good-skill")], shared=[("fx", "common")])
        (self.store / "common" / "shared.md").write_bytes(b"damaged\n")
        real = ts._move
        calls = []

        def breaking(source, target):
            calls.append(1)
            if len(calls) >= 2:
                raise OSError("injected failure")
            return real(source, target)
        with mock.patch.object(ts, "_move", side_effect=breaking):
            with self.assertRaises(ts.SourceError):
                self.vendor([("fx", "alpha", "good-skill")], shared=[("fx", "common")])
        saved = [path for path in self.store.rglob("shared.md") if path.read_bytes() == b"damaged\n"]
        self.assertTrue(saved, "the old folder is nowhere to be found after a failed rollback")

    def test_a_long_name_with_a_digit_is_shown_in_the_messages_and_other_text_is_cleaned(self):
        long_name = "e2e-fabric-cost-estimation"
        plugin = self.lock["skill_sources"]["fx"]["plugins"]["alpha"]
        plugin["skills"][long_name] = dict(plugin["skills"]["good-skill"], digest="sha256:" + "5" * 64)
        with self.assertRaises(ts.SourceError) as caught:
            self.vendor([("fx", "alpha", long_name)])
        self.assertEqual("digest mismatch: " + long_name, str(caught.exception))
        with self.assertRaises(ts.SourceError) as caught:
            self.vendor([("fx", "alpha", long_name)], quarantine=[long_name])
        self.assertEqual("quarantined: " + long_name, str(caught.exception))
        with self.assertRaises(ts.SourceError) as caught:
            self.vendor([("fx", "alpha", "e2e-fabric-cost-estimation-x")])
        self.assertEqual("unresolved: skill is not in the lock: e2e-fabric-cost-estimation-x", str(caught.exception))
        with self.assertRaises(ts.SourceError) as caught:
            self.vendor([("fx", "alpha", "x/y:z")])
        self.assertNotIn("/", str(caught.exception))
        self.assertNotIn("x/y", str(caught.exception))
        self.add_shared()
        self.lock["skill_sources"]["fx2"] = json.loads(json.dumps(self.lock["skill_sources"]["fx"]))
        with self.assertRaises(ts.SourceError) as caught:
            self.vendor([], shared=[("fx", "common"), ("fx2", "common")])
        self.assertEqual("conflict: shared folder named twice: common", str(caught.exception))

    def test_a_failure_while_replacing_puts_everything_back(self):
        self.add_shared()
        selection = [("fx", "alpha", "good-skill")]
        self.vendor(selection, shared=[("fx", "common")])
        (self.store / "common" / "shared.md").write_bytes(b"damaged\n")
        (self.store / "skills" / "good-skill" / "SKILL.md").write_bytes(b"damaged\n")
        (self.store / "skills" / "stale-skill").mkdir()
        (self.store / "skills" / "stale-skill" / "x.txt").write_bytes(b"stale\n")
        before = self.snapshot()
        wanted = selection + [("fx", "beta", "other-skill")]
        counted = []
        real = ts._move

        def counting(source, target):
            counted.append(1)
            return real(source, target)
        with mock.patch.object(ts, "_move", side_effect=counting):
            self.vendor(wanted, shared=[("fx", "common")])
        moves = len(counted)
        self.assertGreaterEqual(moves, 6)
        for failing in range(1, moves + 1):
            for path in self.store.iterdir():
                if path.name not in (".cache",):
                    (shutil.rmtree if path.is_dir() else os.remove)(path)
            write_tree(self.store, {rel: data for rel, data in before.items()})
            calls = []

            def flaky(source, target, failing=failing, calls=calls):
                calls.append(1)
                if len(calls) == failing:
                    raise OSError("injected failure")
                return real(source, target)
            with mock.patch.object(ts, "_move", side_effect=flaky):
                with self.assertRaises(ts.SourceError, msg="failure of move %d" % failing):
                    self.vendor(wanted, shared=[("fx", "common")])
            self.assertEqual(before, self.snapshot(), "the store is not as it was after a failure of move %d" % failing)
            self.assertEqual([], self.leftovers(), "leftovers after a failure of move %d" % failing)

    def test_a_failure_that_is_not_an_os_error_also_puts_everything_back_and_is_not_hidden(self):
        self.add_shared()
        self.vendor([("fx", "alpha", "good-skill")], shared=[("fx", "common")])
        (self.store / "common" / "shared.md").write_bytes(b"damaged\n")
        before = self.snapshot()
        real = ts._move
        calls = []

        def interrupted(source, target):
            calls.append(1)
            if len(calls) == 2:
                raise KeyboardInterrupt()
            return real(source, target)
        with mock.patch.object(ts, "_move", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.vendor([("fx", "alpha", "good-skill")], shared=[("fx", "common")])
        self.assertEqual(before, self.snapshot())
        self.assertEqual([], self.leftovers())

    def test_a_skill_and_a_shared_folder_may_have_the_same_name(self):
        info = self.add_shared()
        plugin = self.lock["skill_sources"]["fx"]["plugins"]["alpha"]
        plugin["skills"]["common"] = dict(plugin["skills"]["good-skill"])
        manifest = self.vendor([("fx", "alpha", "common")], shared=[("fx", "common")])
        self.assertEqual(plugin["skills"]["good-skill"]["digest"], ts.digest_tree(self.store / "skills" / "common")["digest"])
        self.assertEqual(info["digest"], ts.digest_tree(self.store / "common")["digest"])
        self.assertEqual(["common"], list(manifest["skills"]))
        self.assertEqual(["common"], list(manifest["shared"]))

    def test_a_shared_folder_that_left_the_selection_is_removed_and_only_what_the_manifest_lists(self):
        self.add_shared()
        self.vendor([("fx", "alpha", "good-skill")], shared=[("fx", "common")])
        (self.store / "hand-made").mkdir()
        (self.store / "hand-made" / "x.txt").write_text("x")
        manifest = self.vendor([("fx", "alpha", "good-skill")])
        self.assertEqual({}, manifest["shared"])
        self.assertFalse((self.store / "common").exists())
        self.assertTrue((self.store / "hand-made" / "x.txt").exists(), "a folder that no manifest lists was removed")
        self.assertEqual({}, json.loads((self.store / "MANIFEST.json").read_text(encoding="utf-8"))["shared"])

    def test_the_names_that_a_damaged_manifest_lists_are_not_trusted(self):
        self.vendor([("fx", "alpha", "good-skill")])
        (self.store.parent / "escape").mkdir()
        (self.store / "MANIFEST.json").write_text(json.dumps({"schema": 1, "skills": {}, "shared": {name: {} for name in (
            "../escape", "skills", "MANIFEST.json", ".cache", "a/b", "..", "", "Common")}}), encoding="utf-8")
        self.vendor([("fx", "alpha", "good-skill")])
        self.assertTrue((self.store.parent / "escape").is_dir())
        self.assertTrue((self.store / "skills" / "good-skill").is_dir())
        self.assertTrue((self.store / ".cache").is_dir())
        for raw in ("not json", "[]", '{"shared": []}', '{"shared": 5}'):
            (self.store / "MANIFEST.json").write_text(raw, encoding="utf-8")
            self.vendor([("fx", "alpha", "good-skill")])

    def test_a_second_run_with_shared_folders_changes_nothing_and_uses_no_git(self):
        self.add_shared()
        self.vendor([("fx", "alpha", "good-skill")], shared=[("fx", "common")])
        before = self.snapshot()
        self.runner.calls.clear()
        self.vendor([("fx", "alpha", "good-skill")], shared=[("fx", "common")])
        self.assertEqual([], self.runner.calls)
        self.assertEqual(before, self.snapshot())

    def test_a_damaged_shared_folder_is_rewritten_from_the_cache_without_a_new_fetch(self):
        info = self.add_shared()
        self.vendor([("fx", "alpha", "good-skill")], shared=[("fx", "common")])
        self.assertEqual(1, len(self.fetches()))
        (self.store / "common" / "shared.md").write_text("tampered\n")
        (self.store / "common" / "extra.md").write_text("added\n")
        self.runner.calls.clear()
        self.vendor([("fx", "alpha", "good-skill")], shared=[("fx", "common")])
        self.assertEqual([], self.fetches())
        self.assertEqual(info["digest"], ts.digest_tree(self.store / "common")["digest"])
        self.assertFalse((self.store / "common" / "extra.md").exists())

    def test_two_entries_with_one_folder_name_are_an_error_even_when_the_content_is_the_same(self):
        self.add_shared()
        self.lock["skill_sources"]["fx2"] = json.loads(json.dumps(self.lock["skill_sources"]["fx"]))
        with self.assertRaises(ts.SourceError) as caught:
            self.vendor([("fx", "alpha", "good-skill")], shared=[("fx", "common"), ("fx2", "common")])
        self.assertEqual("conflict", caught.exception.code)
        self.assertFalse(self.store.exists())

    def test_a_request_for_a_shared_folder_that_cannot_be_served_is_refused_and_writes_nothing(self):
        info = self.add_shared()
        source = self.lock["skill_sources"]["fx"]
        bad_names = ("skills", "MANIFEST.json", ".cache", "Common", "a/b", "", "con", "common.", "x" * 65)
        for name in bad_names:
            source["shared"][name] = dict(info, plugin="alpha")
        for label, shared in (("skills", [("fx", "skills")]), ("manifest", [("fx", "MANIFEST.json")]), ("dot", [("fx", ".cache")]), ("upper", [("fx", "Common")]),
                              ("slash", [("fx", "a/b")]), ("empty", [("fx", "")]), ("unknown source", [("nowhere", "common")]),
                              ("unknown folder", [("fx", "unlisted")]), ("not a pair", ["common"]), ("numbers", [(1, 2)]), ("not a list", 5),
                              ("reserved", [("fx", "con")]), ("trailing dot", [("fx", "common.")]), ("too long", [("fx", "x" * 65)])):
            with self.assertRaises(ts.SourceError, msg=label) as caught:
                self.vendor([("fx", "alpha", "good-skill")], shared=shared)
            self.assertEqual("unresolved", caught.exception.code, label)
        for name in bad_names:
            del source["shared"][name]
        for label, change in (("no plugin", lambda e: e.pop("plugin")), ("unknown plugin", lambda e: e.update(plugin="nowhere")),
                              ("no digest", lambda e: e.pop("digest")), ("bad digest", lambda e: e.update(digest="sha256:xyz")),
                              ("digest of a number", lambda e: e.update(digest=5)), ("entry is not an object", None)):
            source["shared"]["common"] = dict(info, plugin="alpha")
            if change is None:
                source["shared"]["common"] = "text"
            else:
                change(source["shared"]["common"])
            with self.assertRaises(ts.SourceError, msg=label) as caught:
                self.vendor([("fx", "alpha", "good-skill")], shared=[("fx", "common")])
            self.assertEqual("unresolved", caught.exception.code, label)
        source["shared"]["common"] = dict(info, plugin="alpha")
        plugin_path = source["plugins"]["alpha"]["path"]
        for bad in ("plugins/../../x", "/abs", "a\\b", ""):
            source["plugins"]["alpha"]["path"] = bad
            with self.assertRaises(ts.SourceError, msg=repr(bad)):
                self.vendor([("fx", "alpha", "good-skill")], shared=[("fx", "common")])
        source["plugins"]["alpha"]["path"] = plugin_path
        self.assertFalse(self.store.exists())
        self.assertFalse((Path(self.tmp.name) / "escape").exists())


class FakeRunner:
    """Answers `npm` calls and HTTP requests from tables and records what was asked."""

    def __init__(self, npm=None, http=None):
        self.npm = npm
        self.table = http or {}
        self.calls = []
        self.cwds = []
        self.listings = []

    def which(self, name):
        return name

    def run(self, argv, *, cwd=None, env=None, timeout=60, input=None):
        self.calls.append(("run", list(argv)))
        self.cwds.append(cwd)
        self.listings.append(sorted(os.listdir(cwd)) if cwd and os.path.isdir(cwd) else None)
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


class HashRunner(FakeRunner):
    """A runner that can also hash a large download, as the real one can; answers from a table of toolchain_io.HashResult."""

    def __init__(self, npm=None, http=None, hashes=None):
        super().__init__(npm, http)
        self.hashes = hashes or {}
        self.hash_calls = []

    def http_hash(self, url, *, headers=None, timeout=20, max_bytes=0, total=0):
        self.hash_calls.append((url, {"timeout": timeout, "max_bytes": max_bytes, "total": total}))
        answer = self.hashes.get(url, toolchain_io.HashResult(404, None, 0, None))
        if isinstance(answer, Exception):
            raise answer
        return answer


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
        self.assertEqual([("run", NPM_ARGV), ("http", NPM_URL)], runner.calls)

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
        runner = FakeRunner(npm=CommandResult(127, "", ""), http={NPM_URL: cut})
        result = self.resolve(runner)
        self.assertEqual({"status": "unresolved", "reason": "network", "detail": "npm missing - registry too-large"}, result)

    def test_the_cli_answers_with_a_bare_string_which_has_no_integrity(self):
        runner = FakeRunner(npm=npm_ok("1.6.0"))
        self.assertEqual({"status": "unresolved", "reason": "unresolved", "detail": "no integrity"}, self.resolve(runner))

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
            runner = FakeRunner(npm=CommandResult(127, "", ""), http={NPM_URL: json_answer(doc)})
            result = self.resolve(runner, track)
            self.assertEqual("unresolved", result["status"])
            assert_clean(self, result)

    def test_jsdelivr_is_not_asked_and_can_never_make_an_answer_resolved(self):
        doc = {"type": "npm", "name": "@microsoft/fabric-mcp", "tags": {"latest": "1.6.0"}, "versions": [{"version": "1.6.0"}, {"version": "1.5.0"}]}
        runner = FakeRunner(npm=CommandResult(127, "", ""), http={NPM_URL: failed("tls"), JSDELIVR_URL: json_answer(doc)})
        result = self.resolve(runner)
        self.assertEqual({"status": "unresolved", "reason": "network", "detail": "npm missing - registry tls"}, result)
        self.assertEqual([NPM_URL], runner.urls())

    def test_everything_blocked_is_a_network_reason_without_the_feed_address(self):
        runner = FakeRunner(npm=CommandResult(1, "", NPM_ERROR), http={NPM_URL: failed("tls")})
        result = self.resolve(runner)
        self.assertEqual("unresolved", result["status"])
        self.assertEqual("network", result["reason"])
        self.assertIn("tls", result["detail"])
        assert_clean(self, result)

    def test_an_error_text_with_a_host_and_a_url_never_reaches_the_result(self):
        for npm in (CommandResult(1, "", NPM_ERROR), CommandResult(1, NPM_ERROR, NPM_ERROR),
                    CommandResult(1, json.dumps({"error": {"code": "E404", "summary": NPM_ERROR, "detail": FEED_URL}}), "")):
            for table in ({NPM_URL: status_only(404)}, {NPM_URL: failed("dns")}, {}):
                result = self.resolve(FakeRunner(npm=npm, http=table))
                self.assertEqual("unresolved", result["status"])
                assert_clean(self, result)

    def test_not_found_everywhere_is_unresolved_not_network(self):
        runner = FakeRunner(npm=CommandResult(1, "", NPM_ERROR), http={NPM_URL: status_only(404)})
        result = self.resolve(runner)
        self.assertEqual("unresolved", result["reason"])
        self.assertIn("not found", result["detail"])

    def test_a_blocked_stage_makes_the_answer_a_network_problem_even_when_another_said_not_found(self):
        runner = FakeRunner(npm=CommandResult(1, "", NPM_ERROR), http={NPM_URL: failed("tls")})
        self.assertEqual("network", self.resolve(runner)["reason"])

    def test_values_that_are_not_a_version_or_an_integrity_are_not_trusted(self):
        for payload in ({"version": "1.6.0; echo x", "dist.integrity": INTEGRITY}, {"version": "latest", "dist.integrity": INTEGRITY},
                        {"version": "1.6.0", "dist.integrity": "md5-abc"}, {"version": "1.6.0", "dist.integrity": ["x"]}, {"version": 16}):
            runner = FakeRunner(npm=npm_ok(payload), http={NPM_URL: failed("tls")})
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
        for runner in (FakeRunner(npm=OSError("x"), http={}), FakeRunner(npm=CommandResult(127, "", ""), http={NPM_URL: OSError("x")})):
            result = self.resolve(runner)
            self.assertEqual("unresolved", result["status"])
            assert_clean(self, result)
        runner = FakeRunner(npm=npm_ok({"version": "1.6.0", "dist.integrity": INTEGRITY}), http={NPM_URL: OSError("x")})
        self.assertEqual("npm-cli", self.resolve(runner)["via"])

    def test_the_official_registry_must_agree_with_the_command_line(self):
        other = "sha512-" + "C" * 86 + "=="
        agree = {NPM_URL: json_answer(packument())}
        runner = FakeRunner(npm=npm_ok({"version": "1.6.0", "dist.integrity": INTEGRITY}), http=agree)
        self.assertEqual({"status": "resolved", "version": "1.6.0", "integrity": INTEGRITY, "via": "npm-cli"}, self.resolve(runner))
        mismatch = {"status": "unresolved", "reason": "unresolved", "detail": "mismatch"}
        cases = (("another integrity for the same version", npm_ok({"version": "1.6.0", "dist.integrity": other}), "latest", agree),
                 ("another latest version", npm_ok({"version": "1.5.0", "dist.integrity": "sha512-" + "B" * 86 + "=="}), "latest", agree),
                 ("the same integrity under another version", npm_ok({"version": "1.5.0", "dist.integrity": INTEGRITY}), "latest", agree),
                 ("a version that the official document does not list", npm_ok({"version": "9.9.9", "dist.integrity": other}), "9.9.9", agree),
                 ("a pinned version with another integrity", npm_ok({"version": "1.5.0", "dist.integrity": other}), "1.5.0", agree),
                 ("a newer latest than the document says", npm_ok({"version": "1.7.0", "dist.integrity": other}), "latest", agree))
        for label, npm, track, table in cases:
            result = self.resolve(FakeRunner(npm=npm, http=table), track)
            self.assertEqual(mismatch, result, label)

    def test_a_registry_that_cannot_be_asked_does_not_stop_the_command_line_answer(self):
        document_without_integrity = {"dist-tags": {"latest": "1.6.0"}, "versions": {"1.6.0": {"dist": {}}}}
        for label, answer in (("tls", failed("tls")), ("dns", failed("dns")), ("timeout", failed("timeout")), ("503", status_only(503)),
                              ("404", status_only(404)), ("not json", HttpResult(200, {}, b"not json", None)), ("a list", json_answer([])),
                              ("cut short", HttpResult(200, {}, b"{}", "too-large")), ("a document without the integrity", json_answer(document_without_integrity)),
                              ("a document without versions", json_answer({"dist-tags": {"latest": "1.6.0"}}))):
            runner = FakeRunner(npm=npm_ok({"version": "1.6.0", "dist.integrity": INTEGRITY}), http={NPM_URL: answer})
            self.assertEqual({"status": "resolved", "version": "1.6.0", "integrity": INTEGRITY, "via": "npm-cli"}, self.resolve(runner), label)

    def test_an_answer_without_an_integrity_is_never_accepted(self):
        no_integrity = {"dist-tags": {"latest": "1.6.0"}, "versions": {"1.6.0": {"dist": {"shasum": "abc"}}, "1.5.0": {"dist": {}}}}
        wanted = {"status": "unresolved", "reason": "unresolved", "detail": "no integrity"}
        for label, npm, table in (("a bare version", npm_ok("1.6.0"), {}), ("an object without the field", npm_ok({"version": "1.6.0"}), {}),
                                  ("an array without the field", npm_ok([{"version": "1.6.0"}]), {}),
                                  ("a registry document without it", CommandResult(127, "", ""), {NPM_URL: json_answer(no_integrity)}),
                                  ("both without it", npm_ok("1.6.0"), {NPM_URL: json_answer(no_integrity)}),
                                  ("the command line without it and the registry blocked", npm_ok("1.6.0"), {NPM_URL: failed("tls")})):
            self.assertEqual(wanted, self.resolve(FakeRunner(npm=npm, http=table)), label)
        self.assertEqual(wanted, self.resolve(FakeRunner(npm=CommandResult(127, "", ""), http={NPM_URL: json_answer(no_integrity)}), "1.5.0"))

    def test_the_stage_that_has_an_integrity_is_taken_when_the_other_has_none(self):
        runner = FakeRunner(npm=npm_ok("1.6.0"), http={NPM_URL: json_answer(packument())})
        self.assertEqual({"status": "resolved", "version": "1.6.0", "integrity": INTEGRITY, "via": "npm-registry"}, self.resolve(runner))

    def test_the_command_line_runs_in_a_fresh_empty_folder_that_is_removed_afterwards(self):
        seen = []
        for _ in range(2):
            runner = FakeRunner(npm=npm_ok({"version": "1.6.0", "dist.integrity": INTEGRITY}))
            self.resolve(runner)
            self.assertEqual(1, len(runner.cwds))
            cwd = runner.cwds[0]
            self.assertTrue(cwd and os.path.isabs(cwd), cwd)
            self.assertEqual([], runner.listings[0], "the folder was not empty or did not exist when npm ran")
            self.assertFalse(os.path.exists(cwd), "the folder was left behind")
            here = os.path.realpath(os.getcwd()).lower()
            self.assertFalse(os.path.realpath(cwd).lower().startswith(here + os.sep) or os.path.realpath(cwd).lower() == here)
            self.assertFalse(os.path.realpath(cwd).lower().startswith(os.path.realpath(str(HERE.parent)).lower() + os.sep))
            seen.append(cwd)
        self.assertNotEqual(seen[0], seen[1], "the folder is not fresh for each call")

    def test_the_folder_is_removed_when_the_command_line_fails_too(self):
        for npm in (CommandResult(1, "", NPM_ERROR), OSError("x"), CommandResult(124, "", "timed out")):
            runner = FakeRunner(npm=npm)
            self.resolve(runner)
            self.assertTrue(runner.cwds[0] and not os.path.exists(runner.cwds[0]), repr(npm))

    def test_a_temporary_folder_that_cannot_be_made_is_a_failure_of_the_stage_not_an_exception(self):
        runner = FakeRunner(npm=npm_ok({"version": "1.6.0", "dist.integrity": INTEGRITY}), http={NPM_URL: json_answer(packument())})
        with mock.patch.object(ts.tempfile, "mkdtemp", side_effect=OSError("no space")):
            result = self.resolve(runner)
        self.assertEqual({"status": "resolved", "version": "1.6.0", "integrity": INTEGRITY, "via": "npm-registry"}, result)
        self.assertEqual([], [call for call in runner.calls if call[0] == "run"])

    @unittest.skipUnless(WINDOWS or shutil.which("sh"), "needs a command shim or a shell")
    def test_a_hostile_npmrc_in_the_working_directory_is_never_read_by_the_command_line(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        bin_dir, project = Path(tmp.name) / "bin", Path(tmp.name) / "project"
        bin_dir.mkdir()
        project.mkdir()
        (project / ".npmrc").write_text("registry=https://hostile.example.test/\n", encoding="utf-8")
        answer = json.dumps({"version": "1.6.0", "dist.integrity": INTEGRITY})
        if WINDOWS:
            (bin_dir / "npm.cmd").write_bytes(("@echo off\r\nif exist .npmrc (\r\n  echo {\"error\":{\"code\":\"E500\"}}\r\n  exit /b 1\r\n)\r\necho %s\r\n" % answer).encode("utf-8"))
        else:
            script = bin_dir / "npm"
            script.write_text("#!/bin/sh\nif [ -e .npmrc ]; then echo '{\"error\":{\"code\":\"E500\"}}'; exit 1; fi\necho '%s'\n" % answer, encoding="utf-8")
            script.chmod(0o755)

        class NoNetwork(toolchain_io.SystemRunner):
            def http(self, method, url, **kwargs):
                return HttpResult(404, {}, b"", None)

        previous = os.getcwd()
        try:
            os.chdir(project)
            with mock.patch.dict(os.environ, {"PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", "")}):
                result = self.resolve(NoNetwork())
        finally:
            os.chdir(previous)
        self.assertEqual({"status": "resolved", "version": "1.6.0", "integrity": INTEGRITY, "via": "npm-cli"}, result)


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

    @staticmethod
    def nupkg_url(version):
        return "https://api.nuget.org/v3-flatcontainer/azure.bicep.mcpserver/%s/azure.bicep.mcpserver.%s.nupkg" % (version, version)

    @staticmethod
    def body_of(version):
        return b"package-bytes-" + version.encode("ascii")

    @staticmethod
    def integrity_of(body):
        return "sha256-" + base64.b64encode(hashlib.sha256(body).digest()).decode("ascii")

    def table(self, versions):
        table = {self.URL: json_answer({"versions": versions})}
        for version in versions:
            if isinstance(version, str):
                table[self.nupkg_url(version.lower())] = HttpResult(200, {}, self.body_of(version.lower()), None)
        return table

    def resolve(self, versions, track="latest", table=None):
        runner = FakeRunner(http=table if table is not None else self.table(versions))
        return ts.resolve_package("nuget", "Azure.Bicep.McpServer", track, runner), runner

    def test_the_highest_release_wins_and_the_id_is_lower_case(self):
        result, runner = self.resolve(["0.9.0", "1.10.0", "1.9.0", "2.0.0-beta.1"])
        self.assertEqual({"status": "resolved", "version": "1.10.0", "integrity": self.integrity_of(self.body_of("1.10.0")), "via": "nuget"}, result)
        self.assertEqual([self.URL, self.nupkg_url("1.10.0")], runner.urls())

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

    def test_a_pinned_version_must_match_exactly_after_case_folding(self):
        four_parts = ".".join(["1", "0", "0", "0"])
        for track in (four_parts, "1.0", "1.00.0", "1.0.0+build", "1.0.0-beta"):
            result, runner = self.resolve(["1.0.0", "1.1.0"], track)
            self.assertEqual({"status": "unresolved", "reason": "unresolved", "detail": "version not found"}, result, track)
            self.assertEqual([self.URL], runner.urls(), "a package was downloaded for " + track)
        result, runner = self.resolve(["1.0.0-beta.1"], "1.0.0-BETA.1")
        self.assertEqual({"status": "resolved", "version": "1.0.0-BETA.1", "integrity": self.integrity_of(self.body_of("1.0.0-beta.1")), "via": "nuget"}, result)
        self.assertEqual([self.URL, self.nupkg_url("1.0.0-beta.1")], runner.urls())

    def test_the_answer_carries_the_sha256_of_the_nupkg_in_the_form_npm_uses(self):
        result, _ = self.resolve(["1.0.0"])
        self.assertRegex(result["integrity"], r"^sha256-[A-Za-z0-9+/]{43}=$")
        self.assertEqual(self.integrity_of(self.body_of("1.0.0")), result["integrity"])
        self.assertNotEqual(self.integrity_of(self.body_of("1.0.0")), self.resolve(["1.0.1"])[0]["integrity"])

    def test_the_package_address_is_lower_case_even_when_the_list_is_not(self):
        result, runner = self.resolve(["1.0.0-Beta.1"])
        self.assertEqual({"status": "resolved", "version": "1.0.0-Beta.1", "integrity": self.integrity_of(self.body_of("1.0.0-beta.1")), "via": "nuget"}, result)
        self.assertEqual(self.nupkg_url("1.0.0-beta.1"), runner.urls()[-1])

    def test_a_nupkg_that_cannot_be_downloaded_is_a_network_problem(self):
        for answer in (failed("tls"), failed("timeout"), status_only(404), status_only(500), HttpResult(200, {}, None, None), HttpResult(200, {}, "text", None)):
            table = self.table(["1.0.0"])
            table[self.nupkg_url("1.0.0")] = answer
            result, _ = self.resolve(None, table=table)
            self.assertEqual("unresolved", result["status"], answer)
            self.assertEqual("network", result["reason"], answer)
            assert_clean(self, result)
        table = self.table(["1.0.0"])
        table[self.nupkg_url("1.0.0")] = OSError("boom")
        result, _ = self.resolve(None, table=table)
        self.assertEqual(("unresolved", "network"), (result["status"], result["reason"]))

    def test_a_nupkg_over_the_size_cap_is_unresolved_and_one_of_exactly_the_cap_is_taken(self):
        with mock.patch.object(ts, "MAX_NUPKG", 10):
            for size, resolved in ((10, True), (11, False)):
                table = self.table(["1.0.0"])
                table[self.nupkg_url("1.0.0")] = HttpResult(200, {}, b"x" * size, None)
                result, _ = self.resolve(None, table=table)
                self.assertEqual(resolved, result["status"] == "resolved", size)
                if resolved:
                    self.assertEqual(self.integrity_of(b"x" * 10), result["integrity"])
                else:
                    self.assertEqual({"status": "unresolved", "reason": "unresolved", "detail": "package too large"}, result)
        self.assertEqual(200 * 1024 * 1024, ts.MAX_NUPKG)

    def test_a_runner_that_can_hash_a_download_is_asked_to_stream_it_with_the_cap(self):
        digest = hashlib.sha256(b"streamed").hexdigest()
        url = self.nupkg_url("1.0.0")
        runner = HashRunner(http={self.URL: json_answer({"versions": ["1.0.0"]})}, hashes={url: toolchain_io.HashResult(200, digest, 8, None)})
        result = ts.resolve_package("nuget", "Azure.Bicep.McpServer", "latest", runner)
        self.assertEqual({"status": "resolved", "version": "1.0.0", "integrity": self.integrity_of(b"streamed"), "via": "nuget"}, result)
        self.assertEqual([self.URL], runner.urls(), "the package was fetched into memory")
        self.assertEqual(1, len(runner.hash_calls))
        called_url, options = runner.hash_calls[0]
        self.assertEqual(url, called_url)
        self.assertEqual(ts.MAX_NUPKG, options["max_bytes"])
        self.assertGreaterEqual(options["total"], 120)

    def test_the_streamed_hash_is_checked_and_its_failures_are_classified(self):
        url = self.nupkg_url("1.0.0")
        good = hashlib.sha256(b"x").hexdigest()
        cases = ((toolchain_io.HashResult(0, None, 0, "tls"), "network"), (toolchain_io.HashResult(200, None, 5, "timeout"), "network"),
                 (toolchain_io.HashResult(200, None, 5, "incomplete"), "network"), (toolchain_io.HashResult(404, None, 0, None), "network"),
                 (toolchain_io.HashResult(200, "not-hex", 5, None), "network"), (toolchain_io.HashResult(200, good.upper() + "0", 5, None), "network"),
                 (toolchain_io.HashResult(500, good, 5, None), "network"),
                 (toolchain_io.HashResult(200, None, 0, "too-large"), "unresolved"), (OSError("boom"), "network"))
        for answer, reason in cases:
            runner = HashRunner(http={self.URL: json_answer({"versions": ["1.0.0"]})}, hashes={url: answer})
            result = ts.resolve_package("nuget", "Azure.Bicep.McpServer", "latest", runner)
            self.assertEqual(("unresolved", reason), (result["status"], result["reason"]), repr(answer))
            assert_clean(self, result)

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
