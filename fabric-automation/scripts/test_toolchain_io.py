#!/usr/bin/env python3
"""Tests for toolchain_io.py: the runner that every other toolchain module uses for child processes and HTTP.

They run real child processes (the interpreter that runs the tests) and a server on the loopback
address. Nothing leaves the machine and the real home folder is never read. Run from the project folder:

    python -m unittest scripts.test_toolchain_io -v
"""

import contextlib
import hashlib
import http.client
import http.server
import json
import ntpath
import os
import posixpath
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import toolchain_io  # noqa: E402
from toolchain_io import CommandResult, HttpResult, LaunchError, SystemRunner  # noqa: E402

PY = sys.executable
WINDOWS = os.name == "nt"

# Spawns a grandchild that sleeps, records both process ids, then sleeps itself.
TREE_SCRIPT = (
    "import os, subprocess, sys, time\n"
    "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
    "with open(sys.argv[1], 'w') as handle:\n"
    "    handle.write('%d %d' % (os.getpid(), child.pid))\n"
    "time.sleep(120)\n"
)


def pid_alive(pid):
    if WINDOWS:
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = kernel.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel.CloseHandle(handle)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_dead(pid, seconds=10.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if not pid_alive(pid):
            return True
        time.sleep(0.1)
    return not pid_alive(pid)


def read_pids(path, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            text = Path(path).read_text()
            if len(text.split()) == 2:
                return [int(part) for part in text.split()]
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    return []


class RunTests(unittest.TestCase):
    def setUp(self):
        self.runner = SystemRunner()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_captures_output_and_exit_code(self):
        result = self.runner.run([PY, "-c", "import sys; print('out'); sys.stderr.write('err'); sys.exit(3)"])
        self.assertIsInstance(result, CommandResult)
        self.assertEqual(3, result.returncode)
        self.assertEqual("out", result.stdout.strip())
        self.assertEqual("err", result.stderr.strip())

    def test_missing_executable_is_127_and_never_raises(self):
        self.assertEqual(CommandResult(127, "", "not found"), self.runner.run(["no-such-command-xyz-123"]))
        self.assertEqual(127, self.runner.run([]).returncode)
        self.assertEqual(127, self.runner.run([""]).returncode)

    def test_input_reaches_standard_input(self):
        script = "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read().decode('utf-8').upper().encode('utf-8'))"
        result = self.runner.run([PY, "-c", script], input="hello \u00e9")
        self.assertEqual("HELLO \u00c9", result.stdout)

    def test_environment_is_an_overlay_and_none_removes(self):
        probe = "import os; print(os.environ.get('TC_A'), os.environ.get('TC_B'), 'PATH' in os.environ or 'Path' in os.environ)"
        with mock.patch.dict(os.environ, {"TC_B": "inherited"}):
            result = self.runner.run([PY, "-c", probe], env={"TC_A": "given"})
            self.assertEqual("given inherited True", result.stdout.strip())
            result = self.runner.run([PY, "-c", probe], env={"TC_B": None})
            self.assertEqual("None None True", result.stdout.strip())

    def test_working_directory(self):
        result = self.runner.run([PY, "-c", "import os; print(os.getcwd())"], cwd=self.tmp.name)
        self.assertEqual(os.path.realpath(self.tmp.name).lower(), os.path.realpath(result.stdout.strip()).lower())

    def test_invalid_utf8_is_replaced(self):
        result = self.runner.run([PY, "-c", "import sys; sys.stdout.buffer.write(b'a\\xff\\xfeb')"])
        self.assertEqual("a\ufffd\ufffdb", result.stdout)

    def test_line_endings_are_not_translated(self):
        result = self.runner.run([PY, "-c", "import sys; sys.stdout.buffer.write(b'a\\r\\nb\\n')"])
        self.assertEqual("a\r\nb\n", result.stdout)

    def test_timeout_is_124_keeps_partial_output_and_kills_the_whole_tree(self):
        pidfile = Path(self.tmp.name) / "pids.txt"
        started = time.monotonic()
        result = self.runner.run([PY, "-c", TREE_SCRIPT, str(pidfile)], timeout=4)
        self.assertEqual(124, result.returncode)
        self.assertLess(time.monotonic() - started, 40)
        pids = read_pids(pidfile)
        self.assertEqual(2, len(pids), "the child never wrote its process ids")
        for pid in pids:
            self.assertTrue(wait_dead(pid), "process %d is still running after the timeout" % pid)

    def test_timeout_returns_the_output_written_so_far(self):
        script = "import sys, time; print('partial', flush=True); time.sleep(120)"
        result = self.runner.run([PY, "-c", script], timeout=3)
        self.assertEqual(124, result.returncode)
        self.assertIn("partial", result.stdout)

    def test_unusable_input_never_raises(self):
        self.assertEqual(126, self.runner.run([PY, "-c", "pass", "bad\x00arg"]).returncode)
        self.assertEqual(127, self.runner.run([PY], cwd=str(Path(self.tmp.name) / "missing")).returncode)

    def test_which_finds_a_path_and_rejects_the_rest(self):
        self.assertTrue(self.runner.which(PY))
        self.assertIsNone(self.runner.which("no-such-command-xyz-123"))
        self.assertIsNone(self.runner.which(""))
        self.assertIsNone(self.runner.which(None))


@unittest.skipUnless(WINDOWS, "command shims are a Windows matter")
class ShimTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.shim = self.dir / "tc-echo-shim.cmd"
        self.shim.write_bytes(b"@echo off\r\necho first=%1\r\necho second=%2\r\n")
        self.runner = SystemRunner()

    def test_a_cmd_shim_runs_with_its_arguments(self):
        result = self.runner.run([str(self.shim), "one", "two words"])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("first=one", result.stdout)
        self.assertIn('second="two words"', result.stdout)

    def test_a_shim_is_found_by_name_through_the_path(self):
        with mock.patch.dict(os.environ, {"PATH": str(self.dir) + os.pathsep + os.environ.get("PATH", "")}):
            found = self.runner.which("tc-echo-shim")
            self.assertTrue(found and found.lower().endswith(".cmd"))
            result = self.runner.run(["tc-echo-shim", "x"])
            self.assertIn("first=x", result.stdout)

    def test_shell_metacharacters_are_refused_before_a_shim_runs(self):
        marker = self.dir / "injected.txt"
        for argument in ("a&echo x>" + str(marker), "a|b", "a<b", 'a"b', "a^b", "%PATH%"):
            result = self.runner.run([str(self.shim), argument])
            self.assertEqual(126, result.returncode, argument)
            self.assertEqual("", result.stdout)
        self.assertFalse(marker.exists())

    def test_each_shell_metacharacter_is_refused_on_its_own_in_any_argument_position(self):
        characters = (("ampersand", "&"), ("pipe", "|"), ("less-than", "<"), ("greater-than", ">"), ("caret", "^"), ("double quote", '"'),
                      ("percent", "%"), ("carriage return", "\r"), ("line feed", "\n"))
        before = sorted(path.name for path in self.dir.iterdir())
        for name, char in characters:
            for argv in ([str(self.shim), "a" + char + "b"], [str(self.shim), "fine", "a" + char + "b"], [str(self.shim), "fine", "fine", char]):
                result = self.runner.run(argv, cwd=str(self.dir))
                self.assertEqual(126, result.returncode, "%s in %r" % (name, argv[1:]))
                self.assertEqual("", result.stdout, name)
        self.assertEqual(before, sorted(path.name for path in self.dir.iterdir()), "a redirect created a file")

    def test_the_refusal_covers_bat_files_and_any_letter_case_of_the_ending(self):
        bat = self.dir / "tc-echo-shim.bat"
        bat.write_bytes(b"@echo off\r\necho first=%1\r\n")
        upper = self.dir / "TC-UPPER-SHIM.CMD"
        upper.write_bytes(b"@echo off\r\necho first=%1\r\n")
        for path in (bat, upper):
            ok = self.runner.run([str(path), "plain"])
            self.assertEqual(0, ok.returncode, path.name)
            self.assertIn("first=plain", ok.stdout)
            for char in ("&", "|", "<", ">", "^", '"', "%", "\r", "\n"):
                self.assertEqual(126, self.runner.run([str(path), "a" + char + "b"], cwd=str(self.dir)).returncode, "%r in %s" % (char, path.name))

    def test_a_program_that_is_not_a_shim_gets_its_arguments_untouched(self):
        payload = 'a&b|c<d>e^f"g%h'
        result = self.runner.run([PY, "-c", "import sys; print(sys.argv[1])", payload], cwd=str(self.dir))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(payload, result.stdout.strip())


@contextlib.contextmanager
def in_folder(folder):
    """Make `folder` the current directory for the length of the block: on Windows the search for a command starts there."""
    previous = os.getcwd()
    os.chdir(str(folder))
    try:
        yield
    finally:
        os.chdir(previous)


def write_launcher(folder, name, *, prints="", marker=None):
    """A launcher that prints a word and may leave a marker file: `name.cmd` on Windows, an executable shell script elsewhere."""
    lines = []
    if marker is not None:
        lines.append('echo ran> "%s"' % marker if WINDOWS else "echo ran > '%s'" % marker)
    if prints:
        lines.append("echo " + prints)
    if WINDOWS:
        path = Path(folder) / (name + ".cmd")
        path.write_bytes(("@echo off\r\n" + "".join(line + "\r\n" for line in lines)).encode("utf-8"))
    else:
        path = Path(folder) / name
        path.write_bytes(("#!/bin/sh\n" + "".join(line + "\n" for line in lines)).encode("utf-8"))
        path.chmod(0o755)
    return path


class WhichTests(unittest.TestCase):
    """`which` never finds a launcher through the current folder. On Windows the search of the system starts there, and on POSIX an
    empty entry of PATH means it. These tests use the real file system of the machine that runs them."""

    NAME = "tc-which-tool"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(os.path.realpath(self.tmp.name))
        self.bin, self.decoys, self.other = self.dir / "bin", self.dir / "decoys", self.dir / "other"
        for folder in (self.bin, self.decoys, self.other):
            folder.mkdir()
        self.marker = self.dir / "decoy-ran.txt"
        self.real = write_launcher(self.bin, self.NAME, prints="real")
        self.decoy = write_launcher(self.decoys, self.NAME, prints="decoy", marker=self.marker)

    def assertSameLauncher(self, expected, found):
        self.assertIsNotNone(found)
        self.assertTrue(os.path.isabs(found), found)
        self.assertEqual(os.path.normcase(str(expected)), os.path.normcase(found))

    def search_path(self, *entries):
        return mock.patch.dict(os.environ, {"PATH": os.pathsep.join(str(entry) for entry in entries)})

    def test_a_launcher_in_an_absolute_folder_of_the_path_is_found_by_its_absolute_path(self):
        with self.search_path(self.bin):
            self.assertSameLauncher(self.real, toolchain_io.which(self.NAME))
            self.assertSameLauncher(self.real, SystemRunner().which(self.NAME))

    def test_the_launcher_of_the_current_folder_is_never_the_one_that_is_found_or_run(self):
        cases = (
            ("an empty entry first", self.decoys, ("", self.bin)),
            ("an empty entry between others", self.decoys, (self.other, "", self.bin)),
            ("a dot first", self.decoys, (".", self.bin)),
            ("a relative folder that holds the decoy", self.dir, ("decoys", self.bin)),
            ("a relative folder reached through ..", self.dir, (os.path.join("..", self.dir.name, "decoys"), self.bin)),
        )
        for label, cwd, entries in cases:
            with self.subTest(label), in_folder(cwd), self.search_path(*entries):
                self.assertSameLauncher(self.real, toolchain_io.which(self.NAME))
                result = SystemRunner().run([self.NAME])
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual("real", result.stdout.strip())
            self.assertFalse(self.marker.exists(), "the decoy of the current folder was run: " + label)

    def test_a_launcher_that_is_only_in_the_current_folder_is_not_found_and_not_run(self):
        cases = (
            ("no folder at all", self.decoys, ()),
            ("an empty entry", self.decoys, ("",)),
            ("a dot", self.decoys, (".",)),
            ("other folders and an empty entry", self.decoys, (self.other, "")),
            ("a relative name of the folder", self.dir, ("decoys",)),
        )
        for label, cwd, entries in cases:
            with self.subTest(label), in_folder(cwd), self.search_path(*entries):
                self.assertIsNone(toolchain_io.which(self.NAME))
                self.assertEqual(CommandResult(127, "", "not found"), SystemRunner().run([self.NAME]))
            self.assertFalse(self.marker.exists(), "the decoy of the current folder was run: " + label)

    def test_with_no_path_variable_at_all_nothing_comes_from_the_current_folder(self):
        with in_folder(self.decoys), mock.patch.dict(os.environ):
            os.environ.pop("PATH", None)
            self.assertIsNone(toolchain_io.which(self.NAME))
            self.assertEqual(127, SystemRunner().run([self.NAME]).returncode)
        self.assertFalse(self.marker.exists())

    def test_without_a_path_variable_the_default_path_of_the_system_is_searched(self):
        with mock.patch.dict(os.environ), mock.patch.object(toolchain_io.os, "defpath", os.pathsep.join(("", str(self.bin)))):
            os.environ.pop("PATH", None)
            self.assertSameLauncher(self.real, toolchain_io.which(self.NAME))

    def test_a_name_with_a_directory_part_is_never_looked_up_from_the_current_folder(self):
        relative = os.path.join(".", self.NAME + (".cmd" if WINDOWS else ""))
        with in_folder(self.decoys), self.search_path(self.bin):
            self.assertIsNone(toolchain_io.which(relative))
            self.assertEqual(127, SystemRunner().run([relative]).returncode)
            with self.assertRaises(LaunchError) as caught:
                toolchain_io.popen_tree([relative])
            self.assertEqual(127, caught.exception.returncode)
        self.assertFalse(self.marker.exists())

    def test_an_absolute_name_is_returned_as_it_is_when_it_is_a_launcher(self):
        self.assertEqual(str(self.real), toolchain_io.which(str(self.real)))
        self.assertIsNone(toolchain_io.which(str(self.bin / "no-such-launcher")))
        self.assertIsNone(toolchain_io.which(str(self.bin)), "a folder is not a launcher")

    def test_a_runner_whose_which_gives_a_bare_name_never_starts_it(self):
        class Sloppy(SystemRunner):
            def which(self, name):
                return name

        with in_folder(self.decoys), self.search_path("", self.other):
            result = Sloppy().run([self.NAME])
        self.assertEqual(CommandResult(127, "", "not found"), result)
        self.assertFalse(self.marker.exists(), "a bare name was started through the search of the system")

    @unittest.skipUnless(WINDOWS, "only on Windows does the search of the system for a command start in the current folder")
    def test_a_decoy_git_cmd_in_the_current_folder_is_neither_returned_nor_run(self):
        with in_folder(self.other):
            expected = shutil.which("git")  # nothing is in this empty folder, so this is the git of the search path
        if expected is None:
            self.skipTest("git is not installed")
        marker = self.decoys / "git-decoy-ran.txt"
        (self.decoys / "git.cmd").write_bytes(('@echo off\r\necho ran> "%s"\r\n' % marker).encode("utf-8"))
        with in_folder(self.decoys):
            found = toolchain_io.which("git")
            result = SystemRunner().run(["git", "--version"])
        self.assertSameLauncher(expected, found)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("git version", result.stdout)
        self.assertFalse(marker.exists(), "the decoy git.cmd was run")

    @unittest.skipIf(WINDOWS, "an empty entry of PATH that means the current folder is a POSIX rule")
    def test_a_decoy_git_in_the_current_folder_is_not_found_through_an_empty_entry_of_the_path(self):
        real = "/usr/bin/git"
        if not (os.path.isfile(real) and os.access(real, os.X_OK)):
            self.skipTest("git is not in /usr/bin")
        write_launcher(self.decoys, "git", marker=self.dir / "git-decoy-ran.txt")
        for path in (":/usr/bin", "/usr/bin::/bin", ".:/usr/bin"):
            with in_folder(self.decoys), mock.patch.dict(os.environ, {"PATH": path}):
                self.assertEqual(real, toolchain_io.which("git"), path)
                self.assertEqual(0, SystemRunner().run(["git", "--version"]).returncode)
        self.assertFalse((self.dir / "git-decoy-ran.txt").exists(), "the decoy git was run")


class FakeMachine:
    """A made-up file system and search path for `which`, in the style of one family (Windows or POSIX), whatever machine runs the test.

    Every path that `which` asks about is recorded in `checked`."""

    def __init__(self, windows, path, files=(), pathext=None, executable=None):
        self.windows, self.path, self.pathext = windows, path, pathext
        self.files = set(files)
        self.executable = set(self.files if executable is None else executable)
        self.checked = []

    def __enter__(self):
        self.stack = contextlib.ExitStack()
        self.stack.enter_context(mock.patch.object(toolchain_io, "WINDOWS", self.windows))
        self.stack.enter_context(mock.patch.dict(os.environ))
        os.environ.pop("PATHEXT", None)
        if self.path is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = self.path
        if self.pathext is not None:
            os.environ["PATHEXT"] = self.pathext
        self.stack.enter_context(mock.patch.object(toolchain_io.os.path, "isfile", side_effect=self.isfile))
        self.stack.enter_context(mock.patch.object(toolchain_io.os, "access", side_effect=lambda path, mode: path in self.executable))
        return self

    def __exit__(self, *exc):
        self.stack.close()
        return False

    def isfile(self, path):
        self.checked.append(path)
        return path in self.files

    def only_absolute_paths_were_asked_about(self):
        if self.windows:
            return all(ntpath.isabs(path) and ntpath.splitdrive(path)[0] for path in self.checked)
        return all(posixpath.isabs(path) for path in self.checked)


class WhichRuleTests(unittest.TestCase):
    """The rule of `which` for both families, written with a made-up file system so that every machine tests both."""

    WIN_RELATIVE_DECOYS = (r".\git.CMD", "git.CMD", r"tools\git.CMD", r"\rooted\git.CMD", r"C:rel\git.CMD", r"..\git.CMD", r"\git.CMD")

    def test_windows_entries_that_are_empty_or_relative_are_never_searched(self):
        files = set(self.WIN_RELATIVE_DECOYS) | {r"C:\bin\git.CMD", r"D:\more\git.CMD"}
        path = r";.;tools;\rooted;C:rel;..;C:\bin;D:\more"
        with FakeMachine(True, path, files, ".COM;.EXE;.BAT;.CMD") as machine:
            self.assertEqual(r"C:\bin\git.CMD", toolchain_io.which("git"))
        self.assertTrue(machine.only_absolute_paths_were_asked_about(), machine.checked)

    def test_windows_nothing_is_found_when_only_the_current_folder_and_relative_folders_hold_it(self):
        files = set(self.WIN_RELATIVE_DECOYS) | {r"C:\other\git.CMD"}
        for path in (r";;", ".", r"tools;\rooted;C:rel", r"C:\bin"):
            with self.subTest(path), FakeMachine(True, path, files, ".COM;.EXE;.BAT;.CMD") as machine:
                self.assertIsNone(toolchain_io.which("git"))
            self.assertTrue(machine.only_absolute_paths_were_asked_about(), machine.checked)

    def test_windows_a_unc_folder_is_an_absolute_folder(self):
        with FakeMachine(True, r"\\server\share\bin", {r"\\server\share\bin\git.EXE"}, ".EXE") as machine:
            self.assertEqual(r"\\server\share\bin\git.EXE", toolchain_io.which("git"))
        self.assertTrue(machine.only_absolute_paths_were_asked_about(), machine.checked)

    def test_windows_the_endings_of_pathext_are_tried_in_their_order(self):
        files = {r"C:\bin\git.BAT", r"C:\bin\git.CMD", r"C:\bin\git.EXE"}
        for pathext, expected in ((".COM;.EXE;.BAT;.CMD", r"C:\bin\git.EXE"), (".CMD;.BAT;.EXE", r"C:\bin\git.CMD"), (".BAT;.CMD", r"C:\bin\git.BAT")):
            with self.subTest(pathext), FakeMachine(True, r"C:\bin", files, pathext):
                self.assertEqual(expected, toolchain_io.which("git"))

    def test_windows_an_ending_that_only_pathext_lists_is_tried(self):
        with FakeMachine(True, r"C:\bin", {r"C:\bin\tool.XYZ"}, ".ABC;.XYZ"):
            self.assertEqual(r"C:\bin\tool.XYZ", toolchain_io.which("tool"))
        with FakeMachine(True, r"C:\bin", {r"C:\bin\tool.XYZ"}, ".ABC"):
            self.assertIsNone(toolchain_io.which("tool"))

    def test_windows_the_folder_order_comes_before_the_ending_order(self):
        files = {r"C:\a\git.CMD", r"C:\b\git.EXE"}
        with FakeMachine(True, r"C:\a;C:\b", files, ".EXE;.CMD"):
            self.assertEqual(r"C:\a\git.CMD", toolchain_io.which("git"))

    def test_windows_a_name_that_already_ends_with_a_listed_ending_is_tried_as_it_is(self):
        files = {r"C:\bin\git.exe.CMD", r"C:\bin\git.exe.COM", r"C:\bin\git.EXE"}
        with FakeMachine(True, r"C:\bin", files, ".COM;.EXE;.BAT;.CMD") as machine:
            self.assertIsNone(toolchain_io.which("git.exe"), "the made-up file system keeps letter case, so git.EXE is another name")
        self.assertEqual([r"C:\bin\git.exe"], machine.checked)
        with FakeMachine(True, r"C:\bin", {r"C:\bin\git.exe"}, ".COM;.EXE;.BAT;.CMD"):
            self.assertEqual(r"C:\bin\git.exe", toolchain_io.which("git.exe"))

    def test_windows_without_pathext_the_usual_list_is_used(self):
        for pathext in (None, ""):
            with self.subTest(repr(pathext)), FakeMachine(True, r"C:\bin", {r"C:\bin\git.BAT"}, pathext):
                self.assertEqual(r"C:\bin\git.BAT", toolchain_io.which("git"))

    def test_windows_exe_cmd_and_bat_are_tried_even_when_pathext_does_not_list_them(self):
        with FakeMachine(True, r"C:\a;C:\b", {r"C:\a\git.cmd", r"C:\b\git.exe", r"C:\b\git.bat"}, ".COM"):
            self.assertEqual(r"C:\b\git.exe", toolchain_io.which("git"), "exe before cmd before bat, whatever the folder order")
        with FakeMachine(True, r"C:\a;C:\b", {r"C:\a\git.bat", r"C:\b\git.cmd"}, ".COM"):
            self.assertEqual(r"C:\b\git.cmd", toolchain_io.which("git"))
        with FakeMachine(True, r"C:\a", {r"C:\a\git.bat"}, ".COM"):
            self.assertEqual(r"C:\a\git.bat", toolchain_io.which("git"))

    def test_windows_the_listed_endings_come_before_the_three_that_are_tried_by_hand(self):
        with FakeMachine(True, r"C:\a;C:\b", {r"C:\a\git.exe", r"C:\b\git.XYZ"}, ".XYZ"):
            self.assertEqual(r"C:\b\git.XYZ", toolchain_io.which("git"))

    def test_windows_the_three_endings_are_not_tried_for_a_name_that_has_an_ending(self):
        with FakeMachine(True, r"C:\bin", {r"C:\bin\tool.dat.exe", r"C:\bin\tool.dat.cmd"}, ".COM"):
            self.assertIsNone(toolchain_io.which("tool.dat"))

    def test_windows_a_name_that_ends_with_exe_cmd_or_bat_is_tried_as_it_is_even_when_pathext_does_not_list_it(self):
        for name in ("git.exe", "git.cmd", "git.bat", "git.EXE", "GIT.Cmd"):
            with self.subTest(name), FakeMachine(True, r"C:\bin", {r"C:\bin" + "\\" + name}, ".COM") as machine:
                self.assertEqual(r"C:\bin" + "\\" + name, toolchain_io.which(name))
            self.assertEqual([r"C:\bin" + "\\" + name], machine.checked)

    def test_windows_a_name_that_is_a_path_is_checked_as_a_file_and_returned_as_it_is_only_when_absolute(self):
        files = {r"C:\tools\git.exe", r"\\server\share\git.exe", r"tools\git.exe", r".\git.exe", r"..\git.exe", r"\git.exe", r"C:git.exe"}
        with FakeMachine(True, r"C:\bin", files, ".EXE") as machine:
            self.assertEqual(r"C:\tools\git.exe", toolchain_io.which(r"C:\tools\git.exe"))
            self.assertEqual(r"\\server\share\git.exe", toolchain_io.which(r"\\server\share\git.exe"))
            self.assertIsNone(toolchain_io.which(r"C:\tools\git"), "an absolute name gets no ending")
            checked = len(machine.checked)
            for name in (r"tools\git.exe", r".\git.exe", r"..\git.exe", r"\git.exe", r"C:git.exe", "tools/git.exe", "./git.exe"):
                self.assertIsNone(toolchain_io.which(name), name)
            self.assertEqual(checked, len(machine.checked), "a relative name with a directory part was looked up")

    def test_posix_empty_and_relative_entries_are_never_searched(self):
        files = {"/usr/bin/git", "/bin/git", "git", "./git", "bin/git", "relative/dir/git"}
        cases = ((":/usr/bin", "/usr/bin/git"), ("/usr/bin::/bin", "/usr/bin/git"), ("/usr/bin:", "/usr/bin/git"), (".:/usr/bin", "/usr/bin/git"),
                 ("bin:/usr/bin", "/usr/bin/git"), ("./bin:/bin", "/bin/git"), ("relative/dir:/bin", "/bin/git"),
                 (":", None), (".", None), ("", None), ("relative/dir", None), ("::.", None))
        for path, expected in cases:
            with self.subTest(path), FakeMachine(False, path, files) as machine:
                self.assertEqual(expected, toolchain_io.which("git"))
            self.assertTrue(machine.only_absolute_paths_were_asked_about(), machine.checked)

    def test_an_empty_entry_is_skipped_by_a_rule_of_its_own(self):
        # Even where every entry counted as absolute, an empty entry would stand for the current folder, so it is dropped first.
        with FakeMachine(False, "::", {"git", "./git"}) as machine, mock.patch.object(toolchain_io, "_is_absolute", return_value=True):
            self.assertIsNone(toolchain_io.which("git"))
        self.assertEqual([], machine.checked)
        with FakeMachine(True, ";;", {"git.CMD"}, ".CMD") as machine, mock.patch.object(toolchain_io, "_is_absolute", return_value=True):
            self.assertIsNone(toolchain_io.which("git"))
        self.assertEqual([], machine.checked)

    def test_posix_a_file_that_may_not_be_run_is_skipped_for_a_later_one(self):
        files = {"/a/git", "/b/git"}
        with FakeMachine(False, "/a:/b", files, executable={"/b/git"}):
            self.assertEqual("/b/git", toolchain_io.which("git"))
        with FakeMachine(False, "/a:/b", files, executable=()):
            self.assertIsNone(toolchain_io.which("git"))

    def test_posix_the_endings_of_windows_play_no_part(self):
        with FakeMachine(False, "/bin", {"/bin/git.CMD", "/bin/git.exe"}, ".CMD;.EXE"):
            self.assertIsNone(toolchain_io.which("git"))
        with FakeMachine(False, "/bin", {"/bin/git"}, ".CMD"):
            self.assertEqual("/bin/git", toolchain_io.which("git"))

    def test_posix_a_name_that_is_a_path_is_checked_as_a_file_and_returned_as_it_is_only_when_absolute(self):
        files = {"/usr/bin/git", "git", "./git", "bin/git", "../git", "/git"}
        with FakeMachine(False, "/usr/bin", files) as machine:
            self.assertEqual("/usr/bin/git", toolchain_io.which("/usr/bin/git"))
            self.assertIsNone(toolchain_io.which("/usr/bin/nothing"))
            checked = len(machine.checked)
            for name in ("./git", "bin/git", "../git", "bin/../git", "./bin/"):
                self.assertIsNone(toolchain_io.which(name), name)
            self.assertEqual(checked, len(machine.checked), "a relative name with a directory part was looked up")
        with FakeMachine(False, "/usr/bin", {"/usr/bin/git"}, executable=()):
            self.assertIsNone(toolchain_io.which("/usr/bin/git"), "a file that may not be run is not a launcher")

    def test_a_name_that_is_not_text_or_is_empty_is_not_found_and_nothing_is_looked_up(self):
        for windows, path in ((False, "/usr/bin"), (True, r"C:\bin")):
            with FakeMachine(windows, path, {"/usr/bin/git", r"C:\bin\git.EXE"}, ".EXE") as machine:
                for name in (None, "", 5, ["git"], b"git"):
                    self.assertIsNone(toolchain_io.which(name), repr(name))
            self.assertEqual([], machine.checked)


class ResolveCommandTests(unittest.TestCase):
    def test_a_finder_that_does_not_give_an_absolute_path_means_not_found(self):
        for answer in ("git", "./git", r".\git.cmd", "bin/git", "", None, "git.exe", r"C:git.exe", r"\git.exe", Path(PY), 5):
            with self.subTest(repr(answer)):
                with self.assertRaises(LaunchError) as caught:
                    toolchain_io.resolve_command(["git", "--version"], finder=lambda name, answer=answer: answer)
                self.assertEqual(127, caught.exception.returncode)
                self.assertEqual("not found", caught.exception.message)

    def test_an_absolute_path_from_the_finder_is_used_with_the_rest_of_the_arguments(self):
        self.assertEqual([PY, "-c", "pass"], toolchain_io.resolve_command(["whatever", "-c", "pass"], finder=lambda name: PY))
        asked = []
        toolchain_io.resolve_command(["whatever"], finder=lambda name: asked.append(name) or PY)
        self.assertEqual(["whatever"], asked)

    def test_a_command_that_cannot_be_named_is_not_found(self):
        for argv in ([], [""], [None], [5], ["git", 5]):
            with self.subTest(repr(argv)):
                with self.assertRaises(LaunchError) as caught:
                    toolchain_io.resolve_command(argv, finder=lambda name: PY)
                self.assertEqual(127, caught.exception.returncode)


PAYLOAD_BLOCK = bytes(range(256)) * 256  # 64 KiB


def payload(size):
    return (PAYLOAD_BLOCK * (size // len(PAYLOAD_BLOCK) + 1))[:size]


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def reply(self, status, body=b"", headers=()):
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_request(self):
        length = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(length) if length else b""
        port = self.server.server_address[1]
        path = self.path
        if path == "/ok":
            self.reply(200, b'{"a": 1}', [("Content-Type", "application/json"), ("X-Test", "Value")])
        elif path == "/echo":
            echo = {"method": self.command, "body": data.decode("utf-8"), "custom": self.headers.get("X-Custom"),
                    "agent": self.headers.get("User-Agent")}
            self.reply(200, json.dumps(echo).encode("utf-8"))
        elif path == "/missing":
            self.reply(404, b"nope")
        elif path == "/same":
            self.reply(302, b"", [("Location", "/ok")])
        elif path == "/other":
            self.reply(302, b"", [("Location", "http://localhost:%d/ok" % port)])
        elif path.startswith("/to-port/"):
            self.reply(302, b"", [("Location", "http://127.0.0.1:%s/ok" % path.rsplit("/", 1)[1])])
        elif path.startswith("/bytes/"):
            size = int(path.rsplit("/", 1)[1])
            self.send_response(200)
            self.send_header("Content-Length", str(size))
            self.end_headers()
            try:
                for start in range(0, size, len(PAYLOAD_BLOCK)):
                    self.wfile.write(PAYLOAD_BLOCK[:min(len(PAYLOAD_BLOCK), size - start)])
            except OSError:
                pass
        elif path == "/short":
            self.send_response(200)
            self.send_header("Content-Length", "100")
            self.end_headers()
            self.wfile.write(b"x" * 50)
            self.wfile.flush()
            self.close_connection = True
        elif path.startswith("/stream/"):
            size = int(path.rsplit("/", 1)[1])
            self.send_response(200)
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                for start in range(0, size, len(PAYLOAD_BLOCK)):
                    self.wfile.write(PAYLOAD_BLOCK[:min(len(PAYLOAD_BLOCK), size - start)])
            except OSError:
                pass
            self.close_connection = True
        elif path == "/dribble":
            self.send_response(200)
            self.send_header("Content-Length", "100")
            self.end_headers()
            try:
                for _ in range(100):
                    self.wfile.write(b"x")
                    self.wfile.flush()
                    time.sleep(0.1)
            except OSError:
                pass
        elif path.startswith("/to-bytes/"):
            self.reply(302, b"", [("Location", "/bytes/" + path.rsplit("/", 1)[1])])
        elif path == "/loop":
            self.reply(302, b"", [("Location", "/loop")])
        elif path == "/big":
            self.send_response(200)
            self.send_header("Content-Length", str(6 * 1024 * 1024))
            self.end_headers()
            try:
                for _ in range(6):
                    self.wfile.write(b"a" * 1024 * 1024)
            except OSError:
                pass
        elif path == "/slow":
            time.sleep(2.0)
            self.reply(200, b"late")
        elif path == "/auth":
            self.reply(401, b"", [("WWW-Authenticate", 'Bearer realm="x"'), ("Set-Cookie", "a=1"), ("Set-Cookie", "b=2")])
        else:
            self.reply(404, b"")

    do_GET = do_POST = do_HEAD = do_PUT = handle_request


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = _Server(("127.0.0.1", 0), _Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.runner = SystemRunner()

    def url(self, path):
        return "http://127.0.0.1:%d%s" % (self.port, path)

    def test_get_returns_status_lowercase_headers_and_body(self):
        result = self.runner.http("GET", self.url("/ok"))
        self.assertIsInstance(result, HttpResult)
        self.assertEqual(200, result.status)
        self.assertEqual("Value", result.headers["x-test"])
        self.assertEqual("application/json", result.headers["content-type"])
        self.assertEqual({"a": 1}, json.loads(result.body))
        self.assertIsNone(result.error)

    def test_post_sends_body_and_headers_and_a_default_user_agent(self):
        result = self.runner.http("POST", self.url("/echo"), headers={"X-Custom": "yes"}, body=b'{"k": "v"}')
        echo = json.loads(result.body)
        self.assertEqual({"method": "POST", "body": '{"k": "v"}', "custom": "yes", "agent": "fabric-automation-toolchain"}, echo)
        result = self.runner.http("GET", self.url("/echo"), headers={"user-agent": "mine"})
        self.assertEqual("mine", json.loads(result.body)["agent"])

    def test_an_http_error_status_is_a_result_not_an_exception(self):
        result = self.runner.http("GET", self.url("/missing"))
        self.assertEqual(404, result.status)
        self.assertEqual(b"nope", result.body)
        self.assertIsNone(result.error)

    def test_repeated_headers_are_joined(self):
        result = self.runner.http("GET", self.url("/auth"))
        self.assertEqual(401, result.status)
        self.assertIn("bearer", result.headers["www-authenticate"].lower())
        self.assertEqual("a=1, b=2", result.headers["set-cookie"])

    def test_redirect_to_the_same_host_is_followed(self):
        result = self.runner.http("GET", self.url("/same"))
        self.assertEqual(200, result.status)
        self.assertEqual({"a": 1}, json.loads(result.body))

    def test_redirect_to_another_host_is_not_followed(self):
        result = self.runner.http("GET", self.url("/other"))
        self.assertEqual(302, result.status)
        self.assertNotEqual(b'{"a": 1}', result.body)

    def test_a_redirect_loop_ends(self):
        result = self.runner.http("GET", self.url("/loop"), timeout=10)
        self.assertEqual(302, result.status)

    def test_redirect_rule(self):
        allowed = toolchain_io._redirect_allowed
        split = urllib.parse.urlsplit
        self.assertTrue(allowed(split("https://a.example/x"), split("https://a.example/y")))
        self.assertTrue(allowed(split("http://A.example/x"), split("https://a.example/y")))
        self.assertFalse(allowed(split("https://a.example/x"), split("http://a.example/y")))
        self.assertFalse(allowed(split("https://a.example/x"), split("https://b.example/y")))
        self.assertFalse(allowed(split("https://a.example/x"), split("ftp://a.example/y")))

    def test_a_redirect_keeps_the_port(self):
        allowed = toolchain_io._redirect_allowed
        split = urllib.parse.urlsplit
        for old, new in (("https://a.example/x", "https://a.example:443/y"), ("https://a.example:443/x", "https://a.example/y"),
                         ("http://a.example:80/x", "http://a.example/y"), ("https://a.example:8443/x", "https://a.example:8443/y"),
                         ("http://a.example/x", "https://a.example/y"), ("http://a.example:80/x", "https://a.example:443/y")):
            self.assertTrue(allowed(split(old), split(new)), (old, new))
        for old, new in (("https://a.example/x", "https://a.example:8443/y"), ("https://a.example:8443/x", "https://a.example/y"),
                         ("https://a.example:8443/x", "https://a.example:9443/y"), ("http://a.example:8080/x", "https://a.example/y"),
                         ("http://a.example/x", "http://a.example:8080/y"), ("https://a.example/x", "https://a.example:444/y"),
                         ("https://a.example/x", "https://a.example:0/y"), ("https://a.example/x", "https://a.example:99999/y"),
                         ("https://a.example/x", "https://a.example:port/y"), ("https://a.example:port/x", "https://a.example:port/y")):
            self.assertFalse(allowed(split(old), split(new)), (old, new))

    def test_a_redirect_to_another_port_of_the_same_host_is_not_followed(self):
        other = _Server(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=other.serve_forever, daemon=True)
        thread.start()

        def stop():
            other.shutdown()
            other.server_close()
        self.addCleanup(stop)
        result = self.runner.http("GET", self.url("/to-port/%d" % other.server_address[1]))
        self.assertEqual(302, result.status)
        self.assertNotEqual(b'{"a": 1}', result.body)
        result = self.runner.http("GET", self.url("/to-port/%d" % self.port))
        self.assertEqual(200, result.status)

    def test_http_hash_streams_a_body_that_is_larger_than_the_body_limit(self):
        size = toolchain_io.MAX_BODY + 2 * 1024 * 1024 + 123
        result = self.runner.http_hash(self.url("/bytes/%d" % size), timeout=20)
        self.assertIsInstance(result, toolchain_io.HashResult)
        self.assertEqual((200, hashlib.sha256(payload(size)).hexdigest(), size, None), tuple(result))

    def test_http_hash_gives_no_hash_for_a_body_over_the_limit(self):
        for path, read in (("/bytes/1001", 0), ("/bytes/6000000", 0), ("/stream/1001", 1001), ("/stream/6000000", 1001)):
            result = self.runner.http_hash(self.url(path), max_bytes=1000)
            self.assertEqual((200, None, "too-large"), (result.status, result.sha256, result.error), path)
            self.assertEqual(read, result.size, path)

    def test_http_hash_takes_a_body_of_exactly_the_limit(self):
        for path in ("/bytes/1000", "/stream/1000"):
            result = self.runner.http_hash(self.url(path), max_bytes=1000)
            self.assertEqual((200, hashlib.sha256(payload(1000)).hexdigest(), 1000, None), tuple(result), path)

    def test_http_hash_of_a_body_that_ends_early_is_incomplete_and_has_no_hash(self):
        result = self.runner.http_hash(self.url("/short"))
        self.assertEqual((200, None, "incomplete"), (result.status, result.sha256, result.error))

    def test_http_hash_of_an_error_status_has_no_hash_and_no_error(self):
        result = self.runner.http_hash(self.url("/missing"))
        self.assertEqual((404, None, 0, None), tuple(result))

    def test_http_hash_follows_a_redirect_to_the_same_host_only(self):
        result = self.runner.http_hash(self.url("/to-bytes/10"))
        self.assertEqual((200, hashlib.sha256(payload(10)).hexdigest(), 10, None), tuple(result))
        result = self.runner.http_hash(self.url("/other"))
        self.assertEqual((302, None, 0, None), tuple(result))

    def test_http_hash_never_raises_and_its_errors_are_short_words(self):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        for url in ("http://127.0.0.1:%d/secret-path" % port, "file:///etc/hosts", "not a url", "http://"):
            result = self.runner.http_hash(url, timeout=10)
            self.assertEqual(0, result.status, url)
            self.assertIsNone(result.sha256)
            self.assertTrue(result.error and result.error.replace("-", "").isalpha(), url)
            for forbidden in ("127.0.0.1", "secret-path", "://", "etc"):
                self.assertNotIn(forbidden, result.error)

    def test_http_hash_has_a_timeout_for_a_silent_server_and_a_total_time_for_a_slow_one(self):
        result = self.runner.http_hash(self.url("/slow"), timeout=0.4)
        self.assertEqual((0, None, "timeout"), (result.status, result.sha256, result.error))
        started = time.monotonic()
        result = self.runner.http_hash(self.url("/dribble"), timeout=5, total=0.6)
        self.assertEqual((200, None, "timeout"), (result.status, result.sha256, result.error))
        self.assertLess(time.monotonic() - started, 5)

    def test_a_body_that_trickles_in_is_cut_at_the_deadline(self):
        started = time.monotonic()
        result = self.runner.http("GET", self.url("/dribble"), timeout=0.6)
        self.assertEqual((200, "timeout"), (result.status, result.error))
        self.assertLess(len(result.body), 100)
        self.assertLess(time.monotonic() - started, 5)

    def test_a_body_over_the_limit_is_cut_and_reported(self):
        result = self.runner.http("GET", self.url("/big"), timeout=20)
        self.assertEqual(200, result.status)
        self.assertEqual("too-large", result.error)
        self.assertLessEqual(len(result.body), toolchain_io.MAX_BODY)

    def test_a_slow_server_is_a_timeout_with_status_zero(self):
        result = self.runner.http("GET", self.url("/slow"), timeout=0.4)
        self.assertEqual(0, result.status)
        self.assertEqual("timeout", result.error)

    def test_a_refused_connection_is_status_zero(self):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        result = self.runner.http("GET", "http://127.0.0.1:%d/x" % port, timeout=10)
        self.assertEqual(0, result.status)
        self.assertIn(result.error, ("refused", "connect", "timeout", "reset"))

    def test_errors_never_hold_a_url_or_a_host(self):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        for url in ("http://127.0.0.1:%d/secret-path" % port, "file:///etc/hosts", "ftp://127.0.0.1/x", "not a url", "http://"):
            result = self.runner.http("GET", url, timeout=10)
            self.assertEqual(0, result.status, url)
            self.assertTrue(result.error and result.error.replace("-", "").isalpha(), url)
            for forbidden in ("127.0.0.1", "secret-path", "://", "etc"):
                self.assertNotIn(forbidden, result.error)

    def test_other_schemes_are_refused_before_any_request(self):
        self.assertEqual(HttpResult(0, {}, b"", "unsupported-scheme"), self.runner.http("GET", "file:///does-not-matter"))

    def test_loopback_requests_never_use_a_proxy(self):
        with mock.patch.dict(os.environ, {"http_proxy": "http://127.0.0.1:9", "HTTP_PROXY": "http://127.0.0.1:9"}):
            result = self.runner.http("GET", self.url("/ok"))
        self.assertEqual(200, result.status)


class ClassifyTests(unittest.TestCase):
    def test_exceptions_map_to_a_short_vocabulary(self):
        cases = [
            (socket.timeout(), "timeout"),
            (TimeoutError(), "timeout"),
            (urllib.error.URLError(socket.gaierror(11001, "x")), "dns"),
            (urllib.error.URLError(ConnectionRefusedError()), "refused"),
            (urllib.error.URLError(ssl.SSLCertVerificationError("x")), "tls"),
            (ssl.SSLError("x"), "tls"),
            (ConnectionResetError(), "reset"),
            (http.client.BadStatusLine("x"), "protocol"),
            (urllib.error.URLError("anything"), "error"),
            (OSError("weird"), "connect"),
            (ValueError("x"), "error"),
        ]
        for exc, expected in cases:
            self.assertEqual(expected, toolchain_io.classify_exception(exc), repr(exc))


class SafeDetailTests(unittest.TestCase):
    HOST = "feed" + "." + "contoso" + "." + "example"
    FEED = "pkgs." + "visual" + "studio.com"
    ADDRESS = "10." + "1.2.3"

    def test_urls_hosts_and_addresses_are_removed(self):
        text = "GET https://%s/npm/registry/x failed at %s port 443 via %s (%s)" % (self.FEED, self.HOST, self.ADDRESS, self.FEED)
        detail = toolchain_io.safe_detail(text)
        for forbidden in (self.FEED, self.HOST, "://", self.ADDRESS, "visual", "https"):
            self.assertNotIn(forbidden, detail)
        self.assertIn("failed", detail)

    def test_paths_and_addresses_with_a_user_are_removed(self):
        windows = "C:" + "\\Us" + "ers\\someone\\project\\x.txt"
        posix = "/ho" + "me/someone/x"
        text = "cannot read %s and %s and ~/x and mailbox%shost.example" % (windows, posix, "@")
        detail = toolchain_io.safe_detail(text)
        for forbidden in ("someone", "Users", "project", "~", "host.example", "home", "mailbox"):
            self.assertNotIn(forbidden, detail)

    def test_only_safe_characters_survive_and_the_length_is_capped(self):
        detail = toolchain_io.safe_detail("a\tb\n<script>c</script> `d` $e %f \u00e9 {g} " + "z" * 500)
        self.assertRegex(detail, r"^[A-Za-z0-9 ._:=/-]*$")
        self.assertLessEqual(len(detail), 80)
        self.assertEqual(40, len(toolchain_io.safe_detail("a" * 100, limit=40)))
        self.assertEqual("", toolchain_io.safe_detail(None))
        self.assertEqual("E404 not found", toolchain_io.safe_detail("E404 not found"))

    def test_safe_detail_is_idempotent(self):
        once = toolchain_io.safe_detail("see https://%s/x for E404 and 1.6.0" % self.HOST)
        self.assertEqual(once, toolchain_io.safe_detail(once))
        self.assertIn("1.6.0", once)

    def test_a_word_with_a_backslash_is_removed_whole(self):
        for word in ("Us" + "ers\\alice\\secrets", "alice\\", "a\\b"):
            self.assertEqual("cannot open now", toolchain_io.safe_detail("cannot open %s now" % word), word)

    def test_a_word_with_a_slash_is_removed_whole(self):
        for word in ("src/Us" + "ers/alice/secrets", "and/or", "a/b", "</script>"):
            self.assertEqual("cannot open now", toolchain_io.safe_detail("cannot open %s now" % word), word)

    def test_a_word_with_a_colon_between_text_is_removed_whole(self):
        self.assertEqual("basic rejected", toolchain_io.safe_detail("basic alice:s3cret-token rejected"))
        self.assertEqual("basic rejected", toolchain_io.safe_detail("basic key=alice:s3cret rejected"))
        self.assertEqual("error: not found", toolchain_io.safe_detail("error: not found"))
        self.assertEqual("HTTP 404: Not Found", toolchain_io.safe_detail("HTTP 404: Not Found"))
        self.assertEqual("code: 5", toolchain_io.safe_detail("code: 5"))

    def test_a_word_with_an_at_sign_is_removed_whole(self):
        for word in ("@alice", "alice@", "alice" + "@" + "mail", "a@b.c"):
            self.assertEqual("invited now", toolchain_io.safe_detail("invited %s now" % word), word)

    def test_a_home_reference_is_removed(self):
        for word in ("~alice", "~", "~/x"):
            self.assertEqual("cannot read now", toolchain_io.safe_detail("cannot read %s now" % word), word)
        self.assertEqual("a b stays", toolchain_io.safe_detail("a~b stays"))

    def test_ipv6_addresses_are_removed(self):
        for address in ("2001:db8:85a3::8a2e:370:7334", "fe80::1", "::1", "[::1]:8080", "(2001:db8::1)", "fe80::1%eth0", "::ffff:" + "192.0.2." + "1"):
            self.assertEqual("connect to refused", toolchain_io.safe_detail("connect to %s refused" % address), address)

    def test_a_bare_ipv6_wildcard_is_removed(self):
        self.assertEqual("listening on now", toolchain_io.safe_detail("listening on :: now"))
        self.assertEqual("listening on now", toolchain_io.safe_detail("listening on <::> now"))
        self.assertEqual("listening on now", toolchain_io.safe_detail("listening on :ab: now"))
        self.assertEqual("listening on :xyz: now", toolchain_io.safe_detail("listening on :xyz: now"))

    def test_a_host_next_to_a_non_ascii_letter_or_an_underscore_is_removed_whole(self):
        for text in ("\u00e9" + self.HOST, self.HOST + "\u00e9", "_" + self.HOST, self.HOST + "_x", "x_" + self.HOST, "-" + self.HOST,
                     "feed.contoso.-" + "example", "\u00e9" + "example" + "." + "com"):
            self.assertEqual("failed at now", toolchain_io.safe_detail("failed at %s now" % text), text)

    def test_an_address_next_to_a_non_ascii_letter_or_an_underscore_is_removed_whole(self):
        for text, expected in (("\u00e9" + self.ADDRESS, "failed at now"), (self.ADDRESS + "\u00e9", "failed at now"),
                               ("_" + self.ADDRESS, "failed at _ now"), (self.ADDRESS + "_", "failed at _ now")):
            self.assertEqual(expected, toolchain_io.safe_detail("failed at %s now" % text), text)

    def test_a_long_run_of_name_characters_is_handled_in_linear_time(self):
        started = time.monotonic()
        for text in ("a." * 100000, "a-" * 100000, "1." * 100000, "ab-cd.ef-" * 50000):
            toolchain_io.safe_detail(text)
        self.assertLess(time.monotonic() - started, 10)

    def test_versions_and_error_codes_survive(self):
        for text in ("E404 not found for 1.6.0 and 1.16.10 and v2.0.0-rc.1", "12.34 after 3 tries code=ENOTFOUND e.g. now a.b"):
            self.assertEqual(text, toolchain_io.safe_detail(text))

    def test_a_token_shaped_word_is_removed(self):
        secret = "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4"
        for token in (secret, "AbCdEfGhIjKlMnOpQrStUv12", "AbCdEfGhIjKlMnOpQrStUvWx12==", "abc-def-ghi-jkl-mno-pqr-5", "a1" * 12):
            self.assertEqual("saw now", toolchain_io.safe_detail("saw %s now" % token), token)

    def test_a_long_word_that_is_not_token_shaped_stays(self):
        for token in ("AbCdEfGhIjKlMnOpQrStU12", "AbCdEfGhIjKlMnOpQrStUvWxYz", "1234567890" * 3, "----____====123456789012345678",
                      "AbCdEfGhIjKlMnOpQrStUvWx12.3"):
            self.assertEqual("saw %s now" % token, toolchain_io.safe_detail("saw %s now" % token), token)


class KillTreeTests(unittest.TestCase):
    def test_kill_tree_ends_a_child_and_its_grandchild(self):
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "pids.txt"
            proc = toolchain_io.popen_tree([PY, "-c", TREE_SCRIPT, str(pidfile)])
            try:
                pids = read_pids(pidfile)
                self.assertEqual(2, len(pids))
                toolchain_io.kill_tree(proc)
                for pid in pids:
                    self.assertTrue(wait_dead(pid), "process %d survived kill_tree" % pid)
            finally:
                toolchain_io.kill_tree(proc)

    def test_launch_errors_carry_a_posix_style_code(self):
        with self.assertRaises(toolchain_io.LaunchError) as caught:
            toolchain_io.popen_tree(["no-such-command-xyz-123"])
        self.assertEqual(127, caught.exception.returncode)

    def test_without_inheritance_the_given_environment_is_the_whole_environment(self):
        script = "import json, os, sys; json.dump(sorted(name.upper() for name in os.environ), sys.stdout)"
        given = {"TC_ONLY_GIVEN": "1", "TC_REMOVED": None}
        for name in ("SYSTEMROOT", "SYSTEMDRIVE", "PROGRAMDATA"):  # without these a Microsoft Store Python writes folders into its working directory
            given[name] = os.environ.get(name, "")
        with mock.patch.dict(os.environ, {"TC_ONLY_IN_PARENT": "secret"}), tempfile.TemporaryDirectory() as work:
            for inherit, expected_parent_visible in ((False, False), (True, True)):
                proc = toolchain_io.popen_tree([PY, "-c", script], cwd=work, env=given, stdout=subprocess.PIPE, inherit=inherit)
                out, _ = proc.communicate(timeout=60)
                names = json.loads(out.decode("utf-8"))
                self.assertIn("TC_ONLY_GIVEN", names)
                self.assertNotIn("TC_REMOVED", names)
                self.assertEqual(expected_parent_visible, "TC_ONLY_IN_PARENT" in names, "inherit=%s" % inherit)
            self.assertEqual([], os.listdir(work))


def real_taskkill(*pids):
    exe = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "taskkill.exe")
    for pid in pids:
        subprocess.run([exe, "/PID", str(pid), "/T", "/F"], capture_output=True, check=False, timeout=30)


@unittest.skipUnless(WINDOWS, "taskkill is a Windows matter")
class TaskkillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.marker = self.dir / "decoy-ran.txt"
        (self.dir / "taskkill.cmd").write_bytes(('@echo off\r\necho ran> "%s"\r\n' % self.marker).encode("utf-8"))

    def test_taskkill_is_run_by_absolute_path_and_never_found_through_the_path_or_the_current_folder(self):
        pidfile = self.dir / "pids.txt"
        proc = toolchain_io.popen_tree([PY, "-c", TREE_SCRIPT, str(pidfile)])
        pids = read_pids(pidfile)
        previous = os.getcwd()
        try:
            self.assertEqual(2, len(pids), "the child never wrote its process ids")
            os.chdir(self.dir)  # on Windows the search for a command starts in the current folder
            with mock.patch.dict(os.environ, {"PATH": str(self.dir) + os.pathsep + os.environ.get("PATH", "")}):
                toolchain_io.kill_tree(proc)
            for pid in pids:
                self.assertTrue(wait_dead(pid), "process %d survived kill_tree" % pid)
            self.assertFalse(self.marker.exists(), "a taskkill found on the search path or in the current folder was run")
        finally:
            os.chdir(previous)
            real_taskkill(proc.pid, *pids)
            toolchain_io.kill_tree(proc)

    def test_without_a_taskkill_the_child_itself_is_still_killed(self):
        proc = toolchain_io.popen_tree([PY, "-c", "import time; time.sleep(120)"])
        try:
            with mock.patch.object(toolchain_io, "_system_taskkill", return_value=None), mock.patch.object(toolchain_io.subprocess, "run") as run:
                toolchain_io.kill_tree(proc)
            run.assert_not_called()
            self.assertTrue(wait_dead(proc.pid), "the child survived kill_tree")
        finally:
            real_taskkill(proc.pid)
            toolchain_io.kill_tree(proc)

    def test_the_executable_comes_from_the_system_folder_and_must_exist(self):
        fake = self.dir / "FakeWindows"
        (fake / "System32").mkdir(parents=True)
        (fake / "System32" / "taskkill.exe").write_bytes(b"")
        real = os.environ.get("SystemRoot") or os.environ.get("windir")
        with mock.patch.dict(os.environ, {"SystemRoot": str(fake), "windir": str(self.dir / "nowhere")}):
            self.assertEqual(str(fake / "System32" / "taskkill.exe").lower(), toolchain_io._system_taskkill().lower())
        with mock.patch.dict(os.environ, {"SystemRoot": str(self.dir / "empty"), "windir": real}):
            found = toolchain_io._system_taskkill()
            self.assertTrue(found and os.path.isabs(found) and os.path.isfile(found), found)
            self.assertEqual("taskkill.exe", os.path.basename(found).lower())
            self.assertNotIn("empty", found)

    def test_a_relative_system_root_is_not_trusted(self):
        (self.dir / "System32").mkdir()
        (self.dir / "System32" / "taskkill.exe").write_bytes(b"")
        previous = os.getcwd()
        try:
            os.chdir(self.dir)
            with mock.patch.dict(os.environ, {"SystemRoot": ".", "windir": "."}), mock.patch.object(toolchain_io.os.path, "isfile", return_value=True):
                found = toolchain_io._system_taskkill()
        finally:
            os.chdir(previous)
        self.assertTrue(os.path.isabs(found), found)

    def test_the_usual_folder_is_the_last_resort_and_none_is_returned_when_nothing_exists(self):
        usual = os.path.join("C:\\Windows", "System32", "taskkill.exe").lower()
        with mock.patch.dict(os.environ):
            os.environ.pop("SystemRoot", None)
            os.environ.pop("windir", None)
            with mock.patch.object(toolchain_io.os.path, "isfile", side_effect=lambda path: str(path).lower() == usual):
                self.assertEqual(usual, toolchain_io._system_taskkill().lower())
            with mock.patch.object(toolchain_io.os.path, "isfile", return_value=False):
                self.assertIsNone(toolchain_io._system_taskkill())


class RetryTests(unittest.TestCase):
    """A refusal that Windows gives while something else has a file or folder open for a moment (a sync client such as OneDrive, a
    virus scanner, the indexer) is tried again after a short pause. Nothing else is."""

    @staticmethod
    def refusal(winerror=5):
        exc = PermissionError(13, "Access is denied")
        exc.winerror = winerror
        return exc

    def test_the_refusals_that_go_away_by_themselves_are_access_denied_sharing_and_lock_violations_on_windows_only(self):
        with mock.patch.object(toolchain_io, "WINDOWS", True):
            self.assertTrue(toolchain_io.transient_refusal(PermissionError(13, "denied")))
            for code in (5, 32, 33):
                self.assertTrue(toolchain_io.transient_refusal(self.refusal(code)), code)
            other = OSError(22, "invalid")
            other.winerror = 32
            self.assertTrue(toolchain_io.transient_refusal(other))
            for exc in (FileNotFoundError(2, "gone"), OSError(28, "no space"), FileExistsError(17, "there"), OSError(), ValueError("x"), KeyError("k")):
                self.assertFalse(toolchain_io.transient_refusal(exc), repr(exc))
            unrelated = OSError(22, "invalid")
            unrelated.winerror = 123
            self.assertFalse(toolchain_io.transient_refusal(unrelated))
        with mock.patch.object(toolchain_io, "WINDOWS", False):
            self.assertFalse(toolchain_io.transient_refusal(PermissionError(13, "denied")))
            self.assertFalse(toolchain_io.transient_refusal(self.refusal(32)))

    def test_the_pauses_grow_and_add_up_to_a_few_seconds(self):
        delays = toolchain_io.RETRY_DELAYS
        self.assertEqual(sorted(delays), list(delays))
        self.assertEqual(len(delays), len(set(delays)))
        self.assertTrue(3 <= sum(delays) <= 10, sum(delays))
        self.assertTrue(all(delay > 0 for delay in delays))

    def test_an_action_that_is_refused_for_a_moment_is_run_again_after_each_pause_and_its_result_is_returned(self):
        calls, pauses = [], []

        def flaky():
            calls.append(1)
            if len(calls) < 4:
                raise self.refusal()
            return "done"
        with mock.patch.object(toolchain_io, "WINDOWS", True):
            self.assertEqual("done", toolchain_io.retrying(flaky, sleep=pauses.append))
        self.assertEqual(4, len(calls))
        self.assertEqual(list(toolchain_io.RETRY_DELAYS[:3]), pauses)

    def test_an_action_that_is_always_refused_is_tried_once_more_than_there_are_pauses_and_the_last_refusal_is_raised(self):
        calls, pauses = [], []

        def refused():
            calls.append(1)
            raise self.refusal(32)
        with mock.patch.object(toolchain_io, "WINDOWS", True), self.assertRaises(PermissionError) as caught:
            toolchain_io.retrying(refused, sleep=pauses.append)
        self.assertEqual(32, caught.exception.winerror)
        self.assertEqual(len(toolchain_io.RETRY_DELAYS) + 1, len(calls))
        self.assertEqual(list(toolchain_io.RETRY_DELAYS), pauses)

    def test_any_other_failure_is_raised_at_once_without_a_pause(self):
        for exc in (FileNotFoundError(2, "gone"), OSError(28, "no space"), ValueError("x")):
            with self.subTest(exc=type(exc).__name__):
                calls, pauses = [], []

                def failing():
                    calls.append(1)
                    raise exc
                with mock.patch.object(toolchain_io, "WINDOWS", True), self.assertRaises(type(exc)):
                    toolchain_io.retrying(failing, sleep=pauses.append)
                self.assertEqual(([1], []), (calls, pauses))

    def test_where_the_system_is_not_windows_a_refusal_is_a_real_one_and_is_raised_at_once(self):
        calls, pauses = [], []

        def refused():
            calls.append(1)
            raise PermissionError(13, "denied")
        with mock.patch.object(toolchain_io, "WINDOWS", False), self.assertRaises(PermissionError):
            toolchain_io.retrying(refused, sleep=pauses.append)
        self.assertEqual(([1], []), (calls, pauses))

    def test_without_a_sleep_of_its_own_it_waits_with_time_sleep(self):
        state = {"n": 0}

        def flaky():
            state["n"] += 1
            if state["n"] == 1:
                raise self.refusal()
        with mock.patch.object(toolchain_io, "WINDOWS", True), mock.patch.object(toolchain_io.time, "sleep") as slept:
            toolchain_io.retrying(flaky)
        slept.assert_called_once_with(toolchain_io.RETRY_DELAYS[0])

    def test_a_replace_is_tried_again_while_it_is_refused_and_then_lands(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "source", Path(tmp) / "target"
            source.mkdir()
            (source / "file.txt").write_text("hello", encoding="utf-8")
            real, calls, pauses = os.replace, [], []

            def flaky(src, dst):
                calls.append((src, dst))
                if len(calls) < 3:
                    raise self.refusal()
                return real(src, dst)
            with mock.patch.object(toolchain_io, "WINDOWS", True), mock.patch.object(toolchain_io.os, "replace", side_effect=flaky):
                toolchain_io.replace_retrying(source, target, sleep=pauses.append)
            self.assertEqual("hello", (target / "file.txt").read_text(encoding="utf-8"))
            self.assertFalse(source.exists())
            self.assertEqual(3, len(calls))
            self.assertEqual(list(toolchain_io.RETRY_DELAYS[:2]), pauses)

    def test_a_replace_that_fails_for_another_reason_is_raised_at_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(toolchain_io, "WINDOWS", True), self.assertRaises(FileNotFoundError):
                toolchain_io.replace_retrying(Path(tmp) / "missing", Path(tmp) / "target", sleep=lambda _delay: self.fail("a pause for a missing file"))


class MakeWritableTests(unittest.TestCase):
    """Only Windows needs the read-only attribute cleared before a delete. Elsewhere the mode of a file is left alone, because a hard link
    shares it with every other name of the same file (found on the hosted Linux runner: a chmod before the delete made the other name
    of the file unreadable). On Windows the attribute is shared in the same way, so a file with a second name is left alone there too
    (found in round 9: clearing it through the name in a cache folder made a read-only file outside the folder writable)."""

    def two_names(self, tmp):
        """Two names of one file in `tmp`; skips the test where the file system has no hard links."""
        first, second = Path(tmp) / "first", Path(tmp) / "second"
        first.write_text("keep me", encoding="utf-8")
        try:
            os.link(str(first), str(second))
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("this file system has no hard links")
        return first, second

    def test_on_windows_the_read_only_attribute_is_cleared(self):
        with mock.patch.object(toolchain_io, "WINDOWS", True), mock.patch.object(toolchain_io.os, "chmod") as chmod:
            toolchain_io.make_writable("some-file")
        chmod.assert_called_once_with("some-file", stat.S_IWRITE)

    def test_anywhere_else_nothing_is_changed(self):
        with mock.patch.object(toolchain_io, "WINDOWS", False), mock.patch.object(toolchain_io.os, "chmod") as chmod:
            toolchain_io.make_writable("some-file")
        chmod.assert_not_called()

    def test_on_windows_a_file_with_one_name_is_made_writable(self):
        with mock.patch.object(toolchain_io, "WINDOWS", True), mock.patch.object(toolchain_io.os, "stat", return_value=mock.Mock(st_nlink=1)), \
                mock.patch.object(toolchain_io.os, "chmod") as chmod:
            toolchain_io.make_writable("some-file")
        chmod.assert_called_once_with("some-file", stat.S_IWRITE)

    def test_on_windows_a_file_with_more_than_one_name_is_left_alone(self):
        for names in (2, 3):
            with self.subTest(names=names), mock.patch.object(toolchain_io, "WINDOWS", True), \
                    mock.patch.object(toolchain_io.os, "stat", return_value=mock.Mock(st_nlink=names)), mock.patch.object(toolchain_io.os, "chmod") as chmod:
                toolchain_io.make_writable("some-file")
                chmod.assert_not_called()

    def test_on_windows_a_path_that_cannot_be_examined_is_handled_as_it_was_before(self):
        for failure in (FileNotFoundError(2, "gone"), PermissionError(13, "denied"), OSError(22, "invalid")):
            with self.subTest(failure=type(failure).__name__), mock.patch.object(toolchain_io, "WINDOWS", True), \
                    mock.patch.object(toolchain_io.os, "stat", side_effect=failure), mock.patch.object(toolchain_io.os, "chmod") as chmod:
                toolchain_io.make_writable("some-file")
                chmod.assert_called_once_with("some-file", stat.S_IWRITE)

    def test_the_number_of_names_is_read_from_the_file_system_where_the_rule_is_the_one_of_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = self.two_names(tmp)
            with mock.patch.object(toolchain_io, "WINDOWS", True), mock.patch.object(toolchain_io.os, "chmod") as chmod:
                toolchain_io.make_writable(second)
                chmod.assert_not_called()
                second.unlink()
                toolchain_io.make_writable(first)
                chmod.assert_called_once_with(first, stat.S_IWRITE)

    @unittest.skipUnless(WINDOWS, "the read-only attribute is a Windows matter")
    def test_the_other_name_of_a_read_only_file_stays_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside, inside = self.two_names(tmp)
            try:
                os.chmod(outside, stat.S_IREAD)
                toolchain_io.make_writable(inside)
                self.assertFalse(os.stat(outside).st_mode & stat.S_IWRITE, "the other name of the file became writable")
                self.assertEqual("keep me", outside.read_text(encoding="utf-8"))
                with self.assertRaises(PermissionError):
                    inside.unlink()  # the system still refuses the delete: it is the caller's error to report
            finally:
                os.chmod(outside, stat.S_IWRITE)

    @unittest.skipUnless(WINDOWS, "the read-only attribute is a Windows matter")
    def test_a_read_only_file_with_one_name_is_made_writable_and_can_be_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "object"
            path.write_text("x", encoding="utf-8")
            os.chmod(path, stat.S_IREAD)
            with self.assertRaises(PermissionError):
                path.unlink()
            toolchain_io.make_writable(path)
            path.unlink()
            self.assertFalse(path.exists())

    def test_the_mode_of_a_file_that_has_a_second_name_is_not_changed_when_the_system_is_not_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "first", Path(tmp) / "second"
            first.write_text("keep me", encoding="utf-8")
            try:
                os.link(str(first), str(second))
            except (OSError, NotImplementedError, AttributeError):
                self.skipTest("this file system has no hard links")
            before = os.stat(first).st_mode
            with mock.patch.object(toolchain_io, "WINDOWS", False):
                toolchain_io.make_writable(second)
            self.assertEqual(before, os.stat(first).st_mode)
            self.assertEqual("keep me", first.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
