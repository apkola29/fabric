#!/usr/bin/env python3
"""Offline tests for verify_facts.py.

The checks talk to the network, so these tests replace the HTTP call with a
fake and show that each kind of check reports PASS, DRIFT, FAIL or UNREACHABLE
for the right reason. They also check that facts.json is well formed. Run from
the project folder:

    python -m unittest discover -s scripts -p "test_*.py" -v
"""

import json
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(HERE))

import verify_facts  # noqa: E402

RAW = "https://raw.githubusercontent.com/o/r/"
LATEST = "https://api.github.com/repos/o/r/releases/latest"
PAGE = "https://example.test/page"


def fake_web(routes, seen=None):
    """Answer from a dict of URL prefix to (status, body), and record every URL asked for."""
    def get(url, timeout=40):
        if seen is not None:
            seen.append(url)
        for prefix, answer in routes.items():
            if url.startswith(prefix):
                return answer
        return 404, ""
    return get


def status_of(fact, routes, seen=None):
    with mock.patch.object(verify_facts, "http_get", fake_web(routes, seen)):
        return verify_facts.run([fact], pause=0)[0][0]


def file_fact(**extra):
    fact = {"id": "f", "kind": "github-file", "repo": "o/r", "ref": "@latest-release", "path": "f.py",
            "regex": "the_flag", "expect": "absent", "claim": "c", "cited_in": "d"}
    fact.update(extra)
    return fact


def page_fact(**extra):
    fact = {"id": "p", "kind": "page", "url": PAGE, "all": [r"alpha\s+beta"], "claim": "c", "cited_in": "d"}
    fact.update(extra)
    return fact


class GithubFileTests(unittest.TestCase):
    def test_absent_at_the_latest_release_passes(self):
        routes = {LATEST: (200, json.dumps({"tag_name": "v2.0.0"})), RAW + "v2.0.0/f.py": (200, "nothing here")}
        self.assertEqual(verify_facts.PASS, status_of(file_fact(), routes))

    def test_the_latest_release_is_looked_up_not_assumed(self):
        seen = []
        routes = {LATEST: (200, json.dumps({"tag_name": "v7.1.0"})), RAW: (200, "nothing here")}
        status_of(file_fact(), routes, seen)
        self.assertTrue(any("/v7.1.0/" in url for url in seen), seen)

    def test_a_flag_that_appears_is_drift_when_unstable(self):
        routes = {LATEST: (200, json.dumps({"tag_name": "v3.0.0"})), RAW: (200, "has the_flag now")}
        self.assertEqual(verify_facts.DRIFT, status_of(file_fact(stable=False), routes))

    def test_a_flag_that_appears_fails_when_stable(self):
        routes = {LATEST: (200, json.dumps({"tag_name": "v3.0.0"})), RAW: (200, "has the_flag now")}
        self.assertEqual(verify_facts.FAIL, status_of(file_fact(stable=True), routes))

    def test_a_pinned_ref_is_not_replaced_by_the_latest_release(self):
        seen = []
        routes = {RAW: (200, "has the_flag")}
        status = status_of(file_fact(ref="main", expect="present"), routes, seen)
        self.assertEqual(verify_facts.PASS, status)
        self.assertFalse(any("releases/latest" in url for url in seen), seen)

    def test_a_missing_pattern_is_drift_when_unstable(self):
        routes = {RAW: (200, "nothing here")}
        fact = file_fact(ref="main", expect="present", stable=False)
        self.assertEqual(verify_facts.DRIFT, status_of(fact, routes))

    def test_a_missing_file_fails(self):
        routes = {LATEST: (200, json.dumps({"tag_name": "v1.0.0"}))}
        self.assertEqual(verify_facts.FAIL, status_of(file_fact(), routes))

    def test_an_unreadable_latest_release_is_unreachable(self):
        routes = {LATEST: (500, "")}
        self.assertEqual(verify_facts.UNREACHABLE, status_of(file_fact(), routes))


class PageTests(unittest.TestCase):
    def test_expected_text_passes(self):
        self.assertEqual(verify_facts.PASS, status_of(page_fact(), {PAGE: (200, "<p>Alpha   <b>beta</b></p>")}))

    def test_missing_text_fails_when_stable(self):
        self.assertEqual(verify_facts.FAIL, status_of(page_fact(), {PAGE: (200, "<p>gamma</p>")}))

    def test_missing_text_is_drift_when_unstable(self):
        self.assertEqual(verify_facts.DRIFT, status_of(page_fact(stable=False), {PAGE: (200, "<p>gamma</p>")}))

    def test_an_http_error_fails(self):
        self.assertEqual(verify_facts.FAIL, status_of(page_fact(stable=False), {PAGE: (500, "")}))

    def test_a_network_error_is_unreachable(self):
        def broken(url, timeout=40):
            raise verify_facts.Unreachable("no network")
        with mock.patch.object(verify_facts, "http_get", broken):
            self.assertEqual(verify_facts.UNREACHABLE, verify_facts.run([page_fact()], pause=0)[0][0])


class ErrorStatusTests(unittest.TestCase):
    def test_an_error_page_is_never_read_as_evidence_that_a_pattern_is_absent(self):
        for code in (401, 403, 429, 500, 502):
            with self.subTest(code=code):
                fact = file_fact(ref="main")
                self.assertEqual(verify_facts.UNREACHABLE, status_of(fact, {RAW: (code, "")}))

    def test_a_registry_error_is_unreachable_not_a_crash(self):
        pypi = {"id": "p", "kind": "pypi", "package": "p", "version": "1", "claim": "c", "cited_in": "d"}
        npm = {"id": "n", "kind": "npm", "package": "p", "claim": "c", "cited_in": "d"}
        self.assertEqual(verify_facts.UNREACHABLE, status_of(pypi, {"https://pypi.org/": (500, "")}))
        self.assertEqual(verify_facts.UNREACHABLE, status_of(npm, {"https://registry.npmjs.org/": (500, "")}))


class HttpGetTests(unittest.TestCase):
    @staticmethod
    def raising(code, headers=None):
        def urlopen(req, timeout=40):
            raise verify_facts.urlerror.HTTPError(req.full_url, code, "x", headers or {}, None)
        return urlopen

    def test_server_errors_and_throttling_are_unreachable(self):
        for code in (429, 500, 502, 503):
            with self.subTest(code=code):
                with mock.patch.object(verify_facts.urlrequest, "urlopen", self.raising(code)):
                    with self.assertRaises(verify_facts.Unreachable):
                        verify_facts.http_get("https://example.test/x")

    def test_a_github_rate_limit_is_unreachable(self):
        with mock.patch.object(verify_facts.urlrequest, "urlopen", self.raising(403, {"X-RateLimit-Remaining": "0"})):
            with self.assertRaises(verify_facts.Unreachable):
                verify_facts.http_get("https://api.github.com/x")

    def test_a_missing_page_is_a_404_answer(self):
        with mock.patch.object(verify_facts.urlrequest, "urlopen", self.raising(404)):
            self.assertEqual((404, ""), verify_facts.http_get("https://example.test/x"))


class RegistryTests(unittest.TestCase):
    PYPI = "https://pypi.org/pypi/p/json"
    NPM = "https://registry.npmjs.org/p"

    @staticmethod
    def pypi_fact(version="1.0"):
        return {"id": "p", "kind": "pypi", "package": "p", "version": version, "claim": "c", "cited_in": "d"}

    def pypi_body(self, latest, published):
        return json.dumps({"info": {"version": latest}, "releases": {v: [{"f": 1}] for v in published}})

    def test_the_latest_release_passes(self):
        routes = {self.PYPI: (200, self.pypi_body("1.0", ["1.0"]))}
        self.assertEqual(verify_facts.PASS, status_of(self.pypi_fact(), routes))

    def test_a_newer_release_is_drift(self):
        routes = {self.PYPI: (200, self.pypi_body("2.0", ["1.0", "2.0"]))}
        self.assertEqual(verify_facts.DRIFT, status_of(self.pypi_fact(), routes))

    def test_a_version_that_was_never_published_fails(self):
        routes = {self.PYPI: (200, self.pypi_body("2.0", ["2.0"]))}
        self.assertEqual(verify_facts.FAIL, status_of(self.pypi_fact(), routes))

    def test_an_unknown_pypi_package_fails(self):
        self.assertEqual(verify_facts.FAIL, status_of(self.pypi_fact(), {self.PYPI: (404, "")}))

    def test_a_published_npm_package_passes(self):
        body = json.dumps({"dist-tags": {"latest": "1.2.3"}, "versions": {"1.2.3": {}}})
        fact = {"id": "n", "kind": "npm", "package": "p", "claim": "c", "cited_in": "d"}
        self.assertEqual(verify_facts.PASS, status_of(fact, {self.NPM: (200, body)}))

    def test_an_npm_version_that_was_never_published_fails(self):
        body = json.dumps({"dist-tags": {"latest": "1.2.3"}, "versions": {"1.2.3": {}}})
        fact = {"id": "n", "kind": "npm", "package": "p", "version": "9.9.9", "claim": "c", "cited_in": "d"}
        self.assertEqual(verify_facts.FAIL, status_of(fact, {self.NPM: (200, body)}))

    def test_an_unknown_npm_package_fails(self):
        fact = {"id": "n", "kind": "npm", "package": "p", "claim": "c", "cited_in": "d"}
        self.assertEqual(verify_facts.FAIL, status_of(fact, {self.NPM: (404, "")}))


class GithubKindsTests(unittest.TestCase):
    API = "https://api.github.com/repos/o/r/"

    @staticmethod
    def fact(kind, **extra):
        fact = {"id": "g", "kind": kind, "repo": "o/r", "ref": "main", "claim": "c", "cited_in": "d"}
        fact.update(extra)
        return fact

    def tree(self, paths, truncated=False):
        return json.dumps({"tree": [{"path": p} for p in paths], "truncated": truncated})

    def test_a_tree_with_the_expected_files_and_none_of_the_forbidden_ones_passes(self):
        fact = self.fact("github-tree", present=["c.yml"], absent=["tests/"])
        self.assertEqual(verify_facts.PASS, status_of(fact, {self.API + "git/trees/main": (200, self.tree(["a/b.md", "c.yml"]))}))

    def test_a_forbidden_path_that_is_present_fails(self):
        fact = self.fact("github-tree", present=["c.yml"], absent=["tests/"])
        self.assertEqual(verify_facts.FAIL, status_of(fact, {self.API + "git/trees/main": (200, self.tree(["c.yml", "tests/x.py"]))}))

    def test_a_missing_expected_file_fails(self):
        fact = self.fact("github-tree", present=["c.yml"], absent=[])
        self.assertEqual(verify_facts.FAIL, status_of(fact, {self.API + "git/trees/main": (200, self.tree(["a.md"]))}))

    def test_a_truncated_listing_is_unreachable(self):
        fact = self.fact("github-tree", present=[], absent=["tests/"])
        self.assertEqual(verify_facts.UNREACHABLE, status_of(fact, {self.API + "git/trees/main": (200, self.tree(["a.md"], True))}))

    def test_a_path_that_exists_passes_and_one_that_does_not_fails(self):
        fact = self.fact("github-path", path="p")
        self.assertEqual(verify_facts.PASS, status_of(fact, {self.API + "contents/p": (200, "{}")}))
        self.assertEqual(verify_facts.FAIL, status_of(fact, {self.API + "contents/p": (404, "")}))

    def test_a_live_repository_passes_and_an_archived_one_fails(self):
        fact = self.fact("github-repo")
        live = json.dumps({"archived": False, "pushed_at": "2026-10-01T00:00:00Z"})
        archived = json.dumps({"archived": True, "pushed_at": "2026-10-01T00:00:00Z"})
        self.assertEqual(verify_facts.PASS, status_of(fact, {self.API[:-1]: (200, live)}))
        self.assertEqual(verify_facts.FAIL, status_of(fact, {self.API[:-1]: (200, archived)}))

    def test_a_tag_that_resolves_to_the_pinned_commit_passes(self):
        fact = self.fact("github-tag", tag="v1", sha="abc")
        body = json.dumps({"object": {"sha": "abc", "type": "commit"}})
        self.assertEqual(verify_facts.PASS, status_of(fact, {self.API + "git/ref/tags/v1": (200, body)}))

    def test_a_tag_that_moved_fails(self):
        fact = self.fact("github-tag", tag="v1", sha="abc")
        body = json.dumps({"object": {"sha": "def", "type": "commit"}})
        self.assertEqual(verify_facts.FAIL, status_of(fact, {self.API + "git/ref/tags/v1": (200, body)}))

    def test_an_annotated_tag_is_followed_to_its_commit(self):
        fact = self.fact("github-tag", tag="v1", sha="abc")
        routes = {self.API + "git/ref/tags/v1": (200, json.dumps({"object": {"sha": "t1", "type": "tag"}})),
                  self.API + "git/tags/t1": (200, json.dumps({"object": {"sha": "abc"}}))}
        self.assertEqual(verify_facts.PASS, status_of(fact, routes))


class AdvisoryAndPaperTests(unittest.TestCase):
    ADVISORY = "https://api.github.com/advisories/GHSA-x"
    ARXIV = "https://export.arxiv.org/api/query?id_list=1234"

    @staticmethod
    def advisory(cve="CVE-1"):
        return {"id": "a", "kind": "advisory", "ghsa": "GHSA-x", "cve": cve, "contains": "tj-actions", "claim": "c", "cited_in": "d"}

    def test_a_matching_advisory_passes_and_another_cve_fails(self):
        body = json.dumps({"cve_id": "CVE-1", "summary": "a bad tj-actions release"})
        self.assertEqual(verify_facts.PASS, status_of(self.advisory(), {self.ADVISORY: (200, body)}))
        self.assertEqual(verify_facts.FAIL, status_of(self.advisory("CVE-2"), {self.ADVISORY: (200, body)}))

    def test_a_paper_with_the_expected_title_passes_and_another_fails(self):
        fact = {"id": "x", "kind": "arxiv", "id_list": "1234", "title_contains": "Comment and Control", "claim": "c", "cited_in": "d"}
        good = "<feed><entry><title>Comment and Control: a study</title></entry></feed>"
        other = "<feed><entry><title>Something else</title></entry></feed>"
        self.assertEqual(verify_facts.PASS, status_of(fact, {self.ARXIV: (200, good)}))
        self.assertEqual(verify_facts.FAIL, status_of(fact, {self.ARXIV: (200, other)}))


class FactsFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = json.loads((HERE / "facts.json").read_text(encoding="utf-8"))["facts"]

    def test_ids_are_unique(self):
        ids = [fact["id"] for fact in self.facts]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_fact_has_a_known_kind_and_its_keys(self):
        needs = {"pypi": ["package", "version"], "npm": ["package"], "github-file": ["repo", "ref", "path", "regex"],
                 "github-tree": ["repo", "ref"], "github-path": ["repo", "ref", "path"], "github-repo": ["repo"],
                 "github-tag": ["repo", "tag", "sha"], "advisory": ["ghsa", "cve", "contains"],
                 "arxiv": ["id_list", "title_contains"], "page": ["url"]}
        for fact in self.facts:
            self.assertIn(fact["kind"], verify_facts.CHECKS, fact["id"])
            for key in needs[fact["kind"]] + ["claim", "cited_in"]:
                self.assertIn(key, fact, "%s lacks %s" % (fact["id"], key))

    def test_a_page_fact_checks_something(self):
        for fact in self.facts:
            if fact["kind"] == "page":
                self.assertTrue(fact.get("all") or fact.get("segment"), fact["id"])

    def test_regular_expressions_compile(self):
        for fact in self.facts:
            patterns = list(fact.get("all", [])) + [p for p in [fact.get("regex"), fact.get("show")] if p]
            for pattern in patterns:
                re.compile(pattern)

    def test_cited_files_exist(self):
        for fact in self.facts:
            for name in re.findall(r"(?:docs|ci)/[\w./-]+\.(?:md|yml)", fact["cited_in"]):
                self.assertTrue((PROJECT / name).exists(), "%s cites %s, which does not exist" % (fact["id"], name))


if __name__ == "__main__":
    unittest.main()
