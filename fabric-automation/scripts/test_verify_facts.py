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
            "regex": "the_flag", "expect": "absent", "control": "marker", "claim": "c", "cited_in": "d"}
    fact.update(extra)
    return fact


def page_fact(**extra):
    fact = {"id": "p", "kind": "page", "url": PAGE, "all": [r"alpha\s+beta"], "claim": "c", "cited_in": "d"}
    fact.update(extra)
    return fact


class GithubFileTests(unittest.TestCase):
    def test_absent_at_the_latest_release_passes(self):
        routes = {LATEST: (200, json.dumps({"tag_name": "v2.0.0"})), RAW + "v2.0.0/f.py": (200, "marker nothing here")}
        self.assertEqual(verify_facts.PASS, status_of(file_fact(), routes))

    def test_an_absence_is_not_believed_when_the_file_lacks_its_control_text(self):
        for body in ("<html>Please sign in</html>", "nothing here", "Access denied by the proxy"):
            with self.subTest(body=body):
                routes = {LATEST: (200, json.dumps({"tag_name": "v2.0.0"})), RAW + "v2.0.0/f.py": (200, body)}
                self.assertEqual(verify_facts.UNREACHABLE, status_of(file_fact(), routes))

    def test_an_absence_claim_without_a_control_pattern_is_an_invalid_entry(self):
        fact = file_fact()
        del fact["control"]
        self.assertEqual(verify_facts.FAIL, status_of(fact, {}))

    def test_a_presence_claim_needs_no_control(self):
        fact = file_fact(ref="main", expect="present")
        del fact["control"]
        self.assertEqual(verify_facts.PASS, status_of(fact, {RAW: (200, "has the_flag")}))

    def test_the_latest_release_is_looked_up_not_assumed(self):
        seen = []
        routes = {LATEST: (200, json.dumps({"tag_name": "v7.1.0"})), RAW: (200, "marker nothing here")}
        status_of(file_fact(), routes, seen)
        self.assertTrue(any("/v7.1.0/" in url for url in seen), seen)

    def test_a_flag_that_appears_is_drift_when_unstable(self):
        routes = {LATEST: (200, json.dumps({"tag_name": "v3.0.0"})), RAW: (200, "marker has the_flag now")}
        self.assertEqual(verify_facts.DRIFT, status_of(file_fact(stable=False), routes))

    def test_a_flag_that_appears_fails_when_stable(self):
        routes = {LATEST: (200, json.dumps({"tag_name": "v3.0.0"})), RAW: (200, "marker has the_flag now")}
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

    def test_a_missing_page_fails(self):
        for code in (404, 410):
            with self.subTest(code=code):
                self.assertEqual(verify_facts.FAIL, status_of(page_fact(stable=False), {PAGE: (code, "")}))

    def test_any_other_error_status_says_nothing_about_the_claim(self):
        for code in (401, 403, 500):
            with self.subTest(code=code):
                self.assertEqual(verify_facts.UNREACHABLE, status_of(page_fact(stable=False), {PAGE: (code, "")}))

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


class FakeResponse:
    def __init__(self, status, body, url):
        self.status = status
        self._body = body
        self._url = url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body.encode("utf-8")

    def geturl(self):
        return self._url


def serving(status, body, final_url=None):
    """A stand-in for urlopen. The answer comes from the requested address unless a final address after a redirect is given."""
    return lambda req, timeout=40: FakeResponse(status, body, final_url or req.full_url)


class HttpGetTests(unittest.TestCase):
    @staticmethod
    def raising(code, headers=None):
        def urlopen(req, timeout=40):
            raise verify_facts.urlerror.HTTPError(req.full_url, code, "x", headers or {}, None)
        return urlopen

    def test_an_empty_answer_is_unreachable(self):
        for body in ("", "  \n"):
            with self.subTest(body=body):
                with mock.patch.object(verify_facts.urlrequest, "urlopen", serving(200, body)):
                    with self.assertRaises(verify_facts.Unreachable):
                        verify_facts.http_get("https://example.test/x")

    def test_a_real_answer_is_returned(self):
        with mock.patch.object(verify_facts.urlrequest, "urlopen", serving(200, "text")):
            self.assertEqual((200, "text"), verify_facts.http_get("https://example.test/x"))

    def test_an_answer_from_another_host_after_a_redirect_is_unreachable(self):
        for final in ("https://elsewhere.test/login", "https://example.test.evil.test/x", "http://other.example.test/x"):
            with self.subTest(final=final):
                with mock.patch.object(verify_facts.urlrequest, "urlopen", serving(200, "Please sign in", final)):
                    with self.assertRaises(verify_facts.Unreachable):
                        verify_facts.http_get("https://example.test/x")

    def test_a_redirect_within_the_same_host_is_followed(self):
        with mock.patch.object(verify_facts.urlrequest, "urlopen", serving(200, "text", "https://EXAMPLE.test/moved/y")):
            self.assertEqual((200, "text"), verify_facts.http_get("https://example.test/x"))

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
        self.assertEqual(verify_facts.PASS, status_of(fact, {self.API + "contents/p": (200, json.dumps({"path": "p", "type": "file"}))}))
        self.assertEqual(verify_facts.PASS, status_of(fact, {self.API + "contents/p": (200, json.dumps([{"path": "p/a"}]))}))
        self.assertEqual(verify_facts.FAIL, status_of(fact, {self.API + "contents/p": (404, "")}))

    def test_a_live_repository_passes_and_an_archived_one_fails(self):
        fact = self.fact("github-repo")
        live = json.dumps({"full_name": "o/r", "archived": False, "pushed_at": "2026-10-01T00:00:00Z"})
        archived = json.dumps({"full_name": "o/r", "archived": True, "pushed_at": "2026-10-01T00:00:00Z"})
        self.assertEqual(verify_facts.PASS, status_of(fact, {self.API[:-1]: (200, live)}))
        self.assertEqual(verify_facts.FAIL, status_of(fact, {self.API[:-1]: (200, archived)}))

    def test_a_renamed_repository_fails_or_drifts(self):
        moved = json.dumps({"full_name": "new/name", "archived": False, "pushed_at": "2026-10-01T00:00:00Z"})
        self.assertEqual(verify_facts.FAIL, status_of(self.fact("github-repo"), {self.API[:-1]: (200, moved)}))
        self.assertEqual(verify_facts.DRIFT, status_of(self.fact("github-repo", stable=False), {self.API[:-1]: (200, moved)}))

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
        body = json.dumps({"ghsa_id": "GHSA-x", "cve_id": "CVE-1", "summary": "a bad tj-actions release"})
        self.assertEqual(verify_facts.PASS, status_of(self.advisory(), {self.ADVISORY: (200, body)}))
        self.assertEqual(verify_facts.FAIL, status_of(self.advisory("CVE-2"), {self.ADVISORY: (200, body)}))

    def test_a_paper_with_the_expected_title_passes_and_another_fails(self):
        fact = {"id": "x", "kind": "arxiv", "id_list": "1234", "title_contains": "Comment and Control", "claim": "c", "cited_in": "d"}
        good = "<feed><entry><title>Comment and Control: a study</title></entry></feed>"
        other = "<feed><entry><title>Something else</title></entry></feed>"
        self.assertEqual(verify_facts.PASS, status_of(fact, {self.ARXIV: (200, good)}))
        self.assertEqual(verify_facts.FAIL, status_of(fact, {self.ARXIV: (200, other)}))


class UnusableAnswerTests(unittest.TestCase):
    """A source that answers with nothing, or with something that is not what the check reads, says nothing about the claim."""
    API = "https://api.github.com/repos/o/r/"

    def cases(self):
        make = GithubKindsTests.fact
        return {
            "pypi": (RegistryTests.pypi_fact(), "https://pypi.org/"),
            "npm": ({"id": "n", "kind": "npm", "package": "p", "claim": "c", "cited_in": "d"}, "https://registry.npmjs.org/"),
            "github-tree": (make("github-tree", present=[], absent=[]), self.API + "git/trees/"),
            "github-path": (make("github-path", path="p"), self.API + "contents/"),
            "github-repo": (make("github-repo"), self.API[:-1]),
            "github-tag": (make("github-tag", tag="v1", sha="abc"), self.API + "git/ref/tags/"),
            "advisory": (AdvisoryAndPaperTests.advisory(), "https://api.github.com/advisories/"),
            "latest release": (file_fact(), LATEST),
        }

    def test_malformed_json_is_unreachable_not_a_failed_claim(self):
        for name, (fact, prefix) in self.cases().items():
            for body in ('{"truncated": ', "<html>captcha</html>", "[]"):
                with self.subTest(kind=name, body=body):
                    self.assertEqual(verify_facts.UNREACHABLE, status_of(fact, {prefix: (200, body)}))

    def test_an_empty_object_is_unreachable(self):
        for name, (fact, prefix) in self.cases().items():
            with self.subTest(kind=name):
                self.assertEqual(verify_facts.UNREACHABLE, status_of(fact, {prefix: (200, "{}")}))

    def test_an_empty_file_does_not_prove_a_pattern_absent(self):
        with mock.patch.object(verify_facts.urlrequest, "urlopen", serving(200, "")):
            results = verify_facts.run([file_fact(ref="main"), page_fact()], pause=0)
        self.assertEqual([verify_facts.UNREACHABLE, verify_facts.UNREACHABLE], [r[0] for r in results])

    def test_registry_answers_without_a_latest_version_are_unreachable(self):
        npm = {"id": "n", "kind": "npm", "package": "p", "claim": "c", "cited_in": "d"}
        empty_tags = json.dumps({"dist-tags": {}, "versions": {}})
        self.assertEqual(verify_facts.UNREACHABLE, status_of(npm, {"https://registry.npmjs.org/": (200, empty_tags)}))
        no_version = json.dumps({"info": {}, "releases": {}})
        self.assertEqual(verify_facts.UNREACHABLE, status_of(RegistryTests.pypi_fact(), {"https://pypi.org/": (200, no_version)}))

    def test_a_tree_entry_without_a_path_is_unreachable(self):
        fact = GithubKindsTests.fact("github-tree", present=[], absent=[])
        self.assertEqual(verify_facts.UNREACHABLE, status_of(fact, {self.API + "git/trees/": (200, json.dumps({"tree": [{}]}))}))

    def test_an_annotated_tag_that_cannot_be_followed_is_unreachable(self):
        fact = GithubKindsTests.fact("github-tag", tag="v1", sha="abc")
        routes = {self.API + "git/ref/tags/v1": (200, json.dumps({"object": {"sha": "t1", "type": "tag"}})),
                  self.API + "git/tags/t1": (403, "")}
        self.assertEqual(verify_facts.UNREACHABLE, status_of(fact, routes))

    def test_an_answer_about_another_advisory_is_unreachable(self):
        body = json.dumps({"ghsa_id": "GHSA-other", "cve_id": "CVE-1", "summary": "a bad tj-actions release"})
        self.assertEqual(verify_facts.UNREACHABLE, status_of(AdvisoryAndPaperTests.advisory(), {AdvisoryAndPaperTests.ADVISORY: (200, body)}))

    def test_a_paper_feed_without_an_entry_is_unreachable(self):
        fact = {"id": "x", "kind": "arxiv", "id_list": "1234", "title_contains": "T", "claim": "c", "cited_in": "d"}
        arxiv = AdvisoryAndPaperTests.ARXIV
        self.assertEqual(verify_facts.UNREACHABLE, status_of(fact, {arxiv: (200, "<feed></feed>")}))
        self.assertEqual(verify_facts.UNREACHABLE, status_of(fact, {arxiv: (403, "")}))

    def test_an_answer_with_fields_of_the_wrong_type_is_unreachable_not_a_verdict(self):
        make = GithubKindsTests.fact
        cases = {
            "a folder listing of nulls": (make("github-path", path="p"), self.API + "contents/", "[null]"),
            "a file without a path": (make("github-path", path="p"), self.API + "contents/", json.dumps({"path": None})),
            "a folder entry without a path": (make("github-path", path="p"), self.API + "contents/", json.dumps([{"name": "x"}])),
            "a tree entry whose path is null": (make("github-tree", present=[], absent=["x/"]), self.API + "git/trees/",
                                                json.dumps({"tree": [{"path": None}]})),
            "a repository name that is a number": (make("github-repo"), self.API[:-1], json.dumps({"full_name": 5})),
            "a tag object whose sha is a list": (make("github-tag", tag="v1", sha="abc"), self.API + "git/ref/tags/",
                                                 json.dumps({"object": {"sha": ["a"], "type": "commit"}})),
            "an advisory id that is a number": (AdvisoryAndPaperTests.advisory(), "https://api.github.com/advisories/",
                                                json.dumps({"ghsa_id": 7})),
            "a PyPI version that is a number": (RegistryTests.pypi_fact(), "https://pypi.org/",
                                                json.dumps({"info": {"version": 2}, "releases": {}})),
            "an npm latest tag that is a list": ({"id": "n", "kind": "npm", "package": "p", "claim": "c", "cited_in": "d"},
                                                 "https://registry.npmjs.org/", json.dumps({"dist-tags": {"latest": ["1"]}, "versions": {}})),
        }
        for name, (fact, prefix, body) in cases.items():
            with self.subTest(name):
                self.assertEqual(verify_facts.UNREACHABLE, status_of(fact, {prefix: (200, body)}))

    def test_an_archived_flag_that_is_not_a_boolean_does_not_fail_a_live_repository(self):
        body = json.dumps({"full_name": "o/r", "archived": "no", "pushed_at": "2026-10-01T00:00:00Z"})
        self.assertEqual(verify_facts.PASS, status_of(GithubKindsTests.fact("github-repo"), {self.API[:-1]: (200, body)}))

    def test_the_other_error_statuses_of_the_api_checks_are_unreachable_and_not_found_is_a_failure(self):
        for name, (fact, prefix) in self.cases().items():
            if name == "latest release":
                continue
            with self.subTest(kind=name):
                self.assertEqual(verify_facts.UNREACHABLE, status_of(fact, {prefix: (403, "")}))
                self.assertEqual(verify_facts.FAIL, status_of(fact, {prefix: (404, "")}))


class DefinitionTests(unittest.TestCase):
    def test_a_fact_that_lacks_a_key_fails_before_any_network_call(self):
        seen = []
        fact = file_fact()
        del fact["regex"]
        self.assertEqual(verify_facts.FAIL, status_of(fact, {}, seen))
        self.assertEqual([], seen)

    def test_an_unknown_kind_and_a_pattern_that_does_not_compile_fail(self):
        self.assertEqual(verify_facts.FAIL, status_of(dict(page_fact(), kind="no-such-kind"), {}))
        self.assertEqual(verify_facts.FAIL, status_of(page_fact(all=["("]), {PAGE: (200, "text")}))

    def test_the_evidence_names_the_broken_entry_as_a_definition_problem(self):
        fact = page_fact()
        del fact["url"]
        with mock.patch.object(verify_facts, "http_get", fake_web({})):
            _status, _fact, evidence = verify_facts.run([fact], pause=0)[0]
        self.assertIn("invalid fact definition", evidence)

    def test_a_checker_defect_is_a_failure_that_says_so(self):
        with mock.patch.dict(verify_facts.CHECKS, {"page": lambda fact: 1 / 0}):
            status, _fact, evidence = verify_facts.run([page_fact()], pause=0)[0]
        self.assertEqual(verify_facts.FAIL, status)
        self.assertIn("checker crashed", evidence)

    def test_a_broken_entry_does_not_stop_the_rest_of_the_run_or_the_report(self):
        broken = {"kind": "page"}
        results = None
        with mock.patch.object(verify_facts, "http_get", fake_web({PAGE: (200, "alpha beta")})):
            results = verify_facts.run([broken, page_fact()], pause=0)
        self.assertEqual([verify_facts.FAIL, verify_facts.PASS], [r[0] for r in results])
        self.assertIn("invalid fact definition", verify_facts.render_markdown(results))

    def test_a_string_where_a_list_belongs_is_a_broken_entry_not_a_pass(self):
        # Read one character at a time, "alpha" would pass against a page that only says "aplha".
        fact = page_fact(all="alpha")
        with mock.patch.object(verify_facts, "http_get", fake_web({PAGE: (200, "<p>aplha</p>")})):
            status, _fact, evidence = verify_facts.run([fact], pause=0)[0]
        self.assertEqual(verify_facts.FAIL, status)
        self.assertIn("invalid fact definition", evidence)

    def test_wrongly_typed_entries_are_broken_entries(self):
        broken = {
            "stable written as text": page_fact(stable="false"),
            "raw written as text": page_fact(raw="yes"),
            "an unknown expect value": file_fact(expect="absnet"),
            "a regex that is a list": file_fact(regex=["x"]),
            "an empty claim": page_fact(claim=""),
            "a segment without an end": page_fact(segment={"start": "a"}),
            "a segment list that is a string": page_fact(segment={"start": "a", "end": "b", "present": "x"}),
            "a tree list that is a string": {"id": "t", "kind": "github-tree", "repo": "o/r", "ref": "main", "present": "a.md",
                                             "claim": "c", "cited_in": "d"},
            "an entry that is not an object": "just text",
        }
        for name, fact in broken.items():
            with self.subTest(name):
                with mock.patch.object(verify_facts, "http_get", fake_web({})):
                    status, _fact, evidence = verify_facts.run([fact], pause=0)[0]
                self.assertEqual(verify_facts.FAIL, status, evidence)
                self.assertIn("invalid fact definition", evidence)

    def test_a_well_formed_entry_with_every_optional_key_is_accepted(self):
        fact = page_fact(stable=False, raw=True, segment={"start": "a", "end": "b", "present": ["x"], "absent": ["y"]})
        verify_facts.validate_definition(fact)
        verify_facts.validate_definition(file_fact(expect="present", show="(x)", stable=True))


class FactsFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = json.loads((HERE / "facts.json").read_text(encoding="utf-8"))["facts"]

    def test_ids_are_unique(self):
        ids = [fact["id"] for fact in self.facts]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_fact_has_a_known_kind_and_its_keys(self):
        for fact in self.facts:
            try:
                verify_facts.validate_definition(fact)
            except verify_facts.InvalidFact as exc:
                self.fail("%s: %s" % (fact.get("id", "?"), exc))

    def test_every_kind_has_its_required_keys_listed(self):
        self.assertEqual(set(verify_facts.CHECKS), set(verify_facts.REQUIRED_KEYS))

    def test_a_page_fact_checks_something(self):
        for fact in self.facts:
            if fact["kind"] == "page":
                self.assertTrue(fact.get("all") or fact.get("segment"), fact["id"])

    def test_regular_expressions_compile(self):
        for fact in self.facts:
            patterns = list(fact.get("all", [])) + [p for p in [fact.get("regex"), fact.get("show"), fact.get("control")] if p]
            for pattern in patterns:
                re.compile(pattern)

    def test_cited_files_exist(self):
        for fact in self.facts:
            for name in re.findall(r"(?:docs|ci)/[\w./-]+\.(?:md|yml)", fact["cited_in"]):
                self.assertTrue((PROJECT / name).exists(), "%s cites %s, which does not exist" % (fact["id"], name))

    def test_a_claim_says_what_its_check_proves_and_gives_no_reason(self):
        reasoning = re.compile(r"\b(so|therefore|hence|thus|which means|which does not|which is why)\b", re.IGNORECASE)
        for fact in self.facts:
            self.assertIsNone(reasoning.search(fact["claim"]), "%s: the claim gives a reason, and no check can prove a reason" % fact["id"])


def real_fact(fact_id):
    facts = json.loads((HERE / "facts.json").read_text(encoding="utf-8"))["facts"]
    return next(fact for fact in facts if fact["id"] == fact_id)


def routes_for(fact, body):
    if fact["kind"] == "page":
        return {fact["url"]: (200, body)}
    return {"https://raw.githubusercontent.com/%s/%s/%s" % (fact["repo"], fact["ref"], fact["path"]): (200, body)}


class ClaimPrecisionTests(unittest.TestCase):
    """Each test removes the one text that a real entry stands for and expects the check to stop passing.

    Every case below is a check that stayed green after that text was removed.
    """

    def assert_needs(self, fact_id, good, removed, replacement=""):
        fact = real_fact(fact_id)
        self.assertEqual(verify_facts.PASS, status_of(fact, routes_for(fact, good)), "the sample must pass before it is changed")
        mutated = good.replace(removed, replacement)
        self.assertNotEqual(good, mutated, "the mutation changed nothing")
        self.assertNotEqual(verify_facts.PASS, status_of(fact, routes_for(fact, mutated)))

    PERMISSION = 'To subscribe to this event, a GitHub App must have at least read-level access for the "Members" organization permission. '

    def test_the_membership_permission_needs_its_own_sentence_not_the_word_members(self):
        good = ("Action type : added An organization member was added to a team. This event occurs when there is activity relating to team membership. "
                'For more information about the APIs to manage team memberships, see "Team members" in the REST API documentation. '
                + self.PERMISSION + "Availability for membership")
        self.assert_needs("page-webhook-membership", good, self.PERMISSION)

    def test_the_team_permission_needs_its_own_sentence(self):
        good = ('A team was granted access to a repository. This event occurs when there is activity relating to teams in an organization. '
                'For more information, see "About teams." ' + self.PERMISSION + "Availability for team")
        self.assert_needs("page-webhook-team", good, self.PERMISSION)

    GIT_ITEMS = ("Data Agents Data Factory items: Copy Job Ontology (preview) Plan (preview) "
                 "Report (except reports connected to semantic models hosted in Azure Analysis Services , SQL Server Analysis Services , "
                 "or reports exported by Power BI Desktop that depend on semantic models hosted in MyWorkspace ) (preview) "
                 "Semantic model (except push datasets, live connections to Analysis Services, model v1) (preview) Database items: SQL database")

    def test_the_semantic_model_bullet_needs_its_own_preview_tag(self):
        self.assert_needs("page-git-supported-items", self.GIT_ITEMS, "model v1) (preview)", "model v1)")

    def test_the_report_bullet_needs_its_own_preview_tag(self):
        self.assert_needs("page-git-supported-items", self.GIT_ITEMS, "MyWorkspace ) (preview)", "MyWorkspace )")

    def test_a_data_agent_with_a_preview_tag_is_not_what_the_page_claims(self):
        self.assert_needs("page-git-supported-items", self.GIT_ITEMS, "Data Agents Data", "Data Agents (preview) Data")

    def test_the_entra_page_check_does_not_read_the_wildcard_negation_as_support(self):
        good = ("A maximum of 20 federated identity credentials can be added to an application or user-assigned managed identity. "
                "The subject setting values must exactly match the configuration on the GitHub workflow configuration. "
                "Wildcard characters aren't supported in any federated identity credential property value.")
        self.assert_needs("page-entra-federated-credential-limits", good, "aren't supported", "are supported")

    def test_the_bot_signature_check_needs_the_conditions_not_only_the_heading(self):
        good = ("Signature verification for bots will only work if the request is verified and authenticated as the GitHub App or bot "
                "and contains no custom author information, custom committer information, and no custom signature information.")
        self.assert_needs("page-github-bot-signatures", good,
                          " and contains no custom author information, custom committer information, and no custom signature information")

    def test_only_the_admin_column_may_permanently_delete_a_recoverable_item(self):
        good = ("You can change the retention period (from 7 to 90 days) by using the Define workspace retention period setting in OneLake catalog. "
                "Action Workspace Viewer Workspace Contributor Workspace Member Workspace Admin Recover a deleted item No Yes Yes Yes "
                "Permanently delete a recoverable item No No No Yes Note")
        self.assert_needs("page-retention-recovery", good, "recoverable item No No No Yes", "recoverable item No No Yes Yes")

    def test_the_organization_budget_alert_sentence_must_sit_in_the_organization_paragraph(self):
        good = ('Organization budget An organization\'s metered charges From first metered use Per organization Only if "Stop usage when budget limit is reached" is enabled '
                "The user-level budget (ULB) caps how many AI credits a single user can consume in a billing cycle, whether usage is metered or drawn from an included pool. ULBs always enforce a hard stop. "
                "Organization budget An organization budget limits metered charges for users whose Copilot seats are billed to that organization. "
                "If Stop usage when budget limit is reached is not enabled, the budget only sends alerts and app spending continues after the limit is reached. "
                "For information about managing app access, see the page.")
        self.assert_needs("page-copilot-budget-stop-setting", good, "the budget only sends alerts", "the budget enforces a limit")

    def test_every_webhook_action_must_be_in_the_openapi_description(self):
        operations = ("membership/added", "membership/removed", "team/edited", "team/added-to-repository", "team/removed-from-repository")
        good = "".join('"operationId": "%s", ' % name for name in operations)
        for name in operations:
            self.assert_needs("webhook-actions-in-github-openapi", good, '"operationId": "%s", ' % name)

    MATRIX = ("Item type Workspace private links Customer managed keys Outbound access protection Data Engineering "
              "Lakehouse \u2713 \u2713 \u2713 Lakehouse SQL analytics endpoint \u2713 \u2713 \u2713 Notebook \u2713 \u2713 \u2713 Spark Job Definition \u2713 \u2713 \u2713 "
              "Data Factory Default Semantic Model \u2713 - \u2713 Pipeline \u2713 \u2713 \u2713 Dataflow Gen1 - - - "
              "Data Science Experiment \u2713 \u2713 \u2713 Data Agent \u2713 - Preview Power BI Power BI Report - - Preview Dashboard - - - "
              "Semantic Model - - Preview Streaming dataflow - - - Fabric IQ Graph model - - \u2713 Ontology - - - Operations agent")

    def test_the_matrix_cells_must_keep_their_marks(self):
        for removed, replacement in (("Notebook \u2713 \u2713 \u2713", "Notebook \u2713 \u2713 Preview"), ("Pipeline \u2713 \u2713 \u2713", "Pipeline \u2713 \u2713 -"),
                                     ("Report - - Preview", "Report - - \u2713"), ("Ontology - - -", "Ontology - - Preview")):
            self.assert_needs("page-oap-availability-matrix", self.MATRIX, removed, replacement)

    ENCLAVE = ("invocations.set(claims.invocationId, state);\n    }\n"
               "    if (state.maxRequests !== null && state.requests >= state.maxRequests) {\n"
               "      return { allowed: false, reason: 'request_limit' };\n    }\n"
               "    if (state.maxTokens !== null) {\n"
               "      if (state.exhausted || state.tokens >= state.maxTokens) {\n"
               "        return { allowed: false, reason: 'token_limit', tokenFailure: 'budget_exhausted' };\n      }\n")

    def test_the_request_ceiling_must_refuse_the_request(self):
        self.assert_needs("awf-enclave-budget-refusals", self.ENCLAVE, "reason: 'request_limit'", "reason: 'ok'")

    def test_the_token_ceiling_must_refuse_the_request(self):
        self.assert_needs("awf-enclave-budget-refusals", self.ENCLAVE, "reason: 'token_limit'", "reason: 'ok'")

    BLOCK_STATE = ("function getAiCreditsBlockState() {\n  const config = getAiCreditsConfig();\n"
                   "  const roundedTotalAiCredits = roundCredits(aiCreditsState.totalAiCredits);\n\n"
                   "  // Hard cap always applies, regardless of config\n"
                   "  if (roundedTotalAiCredits >= HARD_CAP_AI_CREDITS) {\n    return {\n      maxAiCredits: HARD_CAP_AI_CREDITS,\n"
                   "      totalAiCredits: roundedTotalAiCredits,\n      maxExceeded: true,\n      hardCap: true,\n    };\n  }\n\n"
                   "  if (!config.max) return null;\n  return {\n    maxAiCredits: config.max,\n"
                   "    totalAiCredits: roundedTotalAiCredits,\n    maxExceeded: roundedTotalAiCredits >= config.max,\n  };\n}\n")

    def test_the_hard_cap_branch_must_be_in_the_block_state(self):
        branch = ("  if (roundedTotalAiCredits >= HARD_CAP_AI_CREDITS) {\n    return {\n      maxAiCredits: HARD_CAP_AI_CREDITS,\n"
                  "      totalAiCredits: roundedTotalAiCredits,\n      maxExceeded: true,\n      hardCap: true,\n    };\n  }\n")
        self.assert_needs("awf-ai-credits-block-state", self.BLOCK_STATE, branch)

    def test_the_configured_maximum_must_decide_the_block_state(self):
        self.assert_needs("awf-ai-credits-block-state", self.BLOCK_STATE, "roundedTotalAiCredits >= config.max", "false")

    REFUSAL = ("      block: getAiCreditsBlockState(),\n      isBlocked: block => block && block.maxExceeded,\n"
               "      // Terminal hard cap, non-retryable.\n      statusCode: 403,\n      eventName: 'ai_credits_limit_exceeded',\n"
               "      buildError: buildAiCreditsLimitError,\n")

    def test_a_request_must_be_refused_when_the_cap_is_exceeded(self):
        self.assert_needs("awf-ai-credits-refusal", self.REFUSAL, "block && block.maxExceeded", "false")


if __name__ == "__main__":
    unittest.main()
