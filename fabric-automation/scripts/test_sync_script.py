#!/usr/bin/env python3
"""Tests for the parts of sync_to_github.ps1 that can run without GitHub.

The publish script is the last gate before anything reaches a public repository,
so its address check is tested against look-alike hosts, other repositories and
addresses with credentials in them, using the function exactly as shipped (it is
extracted from the script with PowerShell's own parser). The tests skip when
PowerShell is not installed. Run from the project folder:

    python -m unittest discover -s scripts -p "test_*.py" -v
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(os.environ.get("SYNC_SCRIPT_UNDER_TEST") or Path(__file__).resolve().parent / "sync_to_github.ps1")
REPO = "apkola29/fabric"

ACCEPTED = [
    "https://github.com/apkola29/fabric.git",
    "https://github.com/apkola29/fabric",
    "https://github.com/apkola29/fabric/",
    "https://github.com/Apkola29/Fabric.git",
    "git@github.com:apkola29/fabric.git",
    "git@github.com:apkola29/fabric",
    "ssh://git@github.com/apkola29/fabric.git",
]
REFUSED = [
    "https://evil.example/apkola29/fabric.git",
    "https://github.com.evil.example/apkola29/fabric",
    "https://evil.example/github.com/apkola29/fabric",
    "https://github.com/other/fabric.git",
    "https://github.com/apkola29/fabric-other.git",
    "https://github.com/apkola29/fabric.git.evil",
    "https://user:secret" + "@github.com/apkola29/fabric.git",
    "https://token" + "@github.com/apkola29/fabric.git",
    "git" + "@gitlab.com:apkola29/fabric.git",
    "C:/work/apkola29/fabric",
    "/srv/git/apkola29/fabric.git",
    "file:///C:/x/apkola29/fabric.git",
]

LOAD = r"""
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($env:SYNC_SCRIPT, [ref]$tokens, [ref]$errors)
if ($errors.Count -gt 0) { $errors | ForEach-Object { 'PARSE ERROR: ' + $_.Message }; exit 3 }
$fn = $ast.Find({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-GitHubRemote' }, $true)
if (-not $fn) { 'function Test-GitHubRemote not found'; exit 4 }
Invoke-Expression $fn.Extent.Text
"""

ASK = LOAD + r"""
Get-Content -LiteralPath $env:SYNC_ADDRESSES | ForEach-Object { '{0}|{1}' -f (Test-GitHubRemote $_ $env:SYNC_REPO), $_ }
"""


def powershell():
    return shutil.which("pwsh") or shutil.which("powershell")


@unittest.skipUnless(powershell(), "PowerShell is not installed")
class SyncScriptTests(unittest.TestCase):
    def run_ps(self, code, **env):
        full = dict(os.environ, SYNC_SCRIPT=str(SCRIPT), SYNC_REPO=REPO)
        full.update(env)
        proc = subprocess.run([powershell(), "-NoProfile", "-NonInteractive", "-Command", code],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", env=full)
        return proc

    def answers(self, addresses, repo=REPO):
        with tempfile.TemporaryDirectory() as tmp:
            listing = Path(tmp) / "addresses.txt"
            listing.write_text("\n".join(addresses) + "\n", encoding="utf-8")
            proc = self.run_ps(ASK, SYNC_ADDRESSES=str(listing), SYNC_REPO=repo)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return dict(line.split("|", 1)[::-1] for line in proc.stdout.splitlines() if "|" in line)

    def test_the_script_parses_and_holds_the_address_check(self):
        proc = self.run_ps(LOAD)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_only_the_canonical_addresses_of_the_repository_are_accepted(self):
        answers = self.answers(ACCEPTED + REFUSED)
        for address in ACCEPTED:
            self.assertEqual("True", answers.get(address), "should accept %s" % address)
        for address in REFUSED:
            self.assertEqual("False", answers.get(address), "should refuse %s" % address)

    def test_a_dot_in_the_repository_name_is_not_a_wildcard_in_the_address_check(self):
        accepted = ["https://github.com/ow.ner/re.po.git", "git@github.com:ow.ner/re.po", "ssh://git@github.com/ow.ner/re.po"]
        refused = ["https://github.com/owXner/re.po.git", "https://github.com/ow.ner/reXpo", "git@github.com:owXner/reXpo.git",
                   "https://github.com/ow.ner/re.po.gitX"]
        answers = self.answers(accepted + refused, repo="ow.ner/re.po")
        for address in accepted:
            self.assertEqual("True", answers.get(address), "should accept %s" % address)
        for address in refused:
            self.assertEqual("False", answers.get(address), "should refuse %s" % address)


class SyncScriptOrderTests(unittest.TestCase):
    """The order of the gates is part of their meaning, so it is pinned."""

    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def position(self, needle):
        found = self.text.find(needle)
        self.assertGreaterEqual(found, 0, "%r is missing from the publish script" % needle)
        return found

    def test_the_tree_of_the_commit_is_checked_before_it_is_pushed(self):
        self.assertLess(self.position("'--clone'"), self.position("'push', 'origin'"))

    def test_the_commit_is_made_before_its_tree_is_checked(self):
        self.assertLess(self.position("'commit', '-F'"), self.position("'--clone'"))

    def test_both_the_fetch_and_the_push_address_are_checked(self):
        self.assertIn("'--push'", self.text)
        self.assertLess(self.position("Test-GitHubRemote $address"), self.position("Step 'Validating the documents"))

    def test_the_validation_comes_before_anything_is_staged(self):
        self.assertLess(self.position("Step 'Validating the documents"), self.position("Step 'Staging only this project'"))


if __name__ == "__main__":
    unittest.main()
