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
