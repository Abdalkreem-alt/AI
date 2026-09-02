#!/usr/bin/env python3
"""End-to-end pipeline tests for the MultiHunter orchestrator.

Run with:  python -m unittest discover -s tests -v
No external dependencies (stdlib only).
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "orchestrator"))

import blackboard
import cli
import dedup
import promptlib
import reportgen


def _ns(**kw):
    return argparse.Namespace(**kw)


class TestBlackboard(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.e = blackboard.Engagement(base=self._tmp, target="acme.com")
        self.e.create("acme.com", "hackerone")

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_lifecycle_and_dedup(self):
        self.assertEqual(self.e.add_assets([
            {"host": "a.acme.com", "url": "https://a.acme.com/", "priority": "P1"},
            {"host": "a.acme.com", "url": "https://a.acme.com/", "priority": "P1"},
        ]), 1)
        self.assertEqual(self.e.add_endpoints([
            {"url": "https://a.acme.com/api/user/1", "method": "GET", "auth": "user"}
        ]), 1)
        self.e.set_phase("recon")
        self.e.complete_phase("recon", "one asset")
        s = self.e.summary()
        self.assertEqual(s["phase"], "map")
        self.assertEqual(s["stage_status"]["recon"], "complete")
        self.assertEqual(s["counts"]["assets"], 1)

    def test_resume(self):
        self.e.add_assets([{"host": "a.acme.com", "url": "https://a.acme.com/"}])
        e2 = blackboard.Engagement(base=self._tmp, target="acme.com")
        self.assertTrue(e2.exists())
        self.assertEqual(e2.artifacts("surface", "assets.json")[0]["host"], "a.acme.com")

    def test_findings_and_snapshot(self):
        fid = self.e.add_finding({"title": "IDOR", "vuln_class": "idor",
                                  "endpoint": "https://a.acme.com/api/user/1"})
        self.assertEqual(fid, "F-001")
        self.assertEqual(len(self.e.findings()), 1)
        snap = self.e.snapshot()
        self.assertIn("assets", snap)


class TestDedup(unittest.TestCase):
    def test_dedup(self):
        findings = [
            {"id": "F-001", "endpoint": "https://a.com/api/user/42", "method": "GET",
             "vuln_class": "IDOR", "param": "id", "title": "IDOR on user endpoint"},
            {"id": "F-002", "endpoint": "https://a.com/api/user/43", "method": "GET",
             "vuln_class": "IDOR", "param": "id", "title": "IDOR on user endpoint"},
        ]
        dups = dedup.find_duplicates(findings)
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0]["source"], "F-002")
        n = dedup.apply_duplicates(findings, dups)
        self.assertEqual(n, 1)
        self.assertEqual(findings[1]["status"], "duplicate")


class TestTriage(unittest.TestCase):
    def test_pass(self):
        t = cli.run_triage({"title": "IDOR leaks PII", "vuln_class": "IDOR",
                            "summary": "Any user can read another user's data with a real HTTP request",
                            "impact": "PII disclosure", "reproduction_steps": ["curl ..."],
                            "endpoint": "https://a.com/api/user/2", "asset": "a.com",
                            "dup_check": {"verdict": "clean", "evidence": "no public writeup found"}})
        self.assertEqual(t["verdict"], "PASS")

    def test_kill_never_submit(self):
        t = cli.run_triage({"title": "clickjacking on logout", "vuln_class": "clickjacking",
                            "summary": "logout CSRF via clickjacking", "impact": "logout",
                            "endpoint": "https://a.com/logout"})
        self.assertEqual(t["verdict"], "KILL")


class TestReportgen(unittest.TestCase):
    def test_report(self):
        with tempfile.TemporaryDirectory() as d:
            e = blackboard.Engagement(base=d, target="acme.com").create("acme.com")
            e.add_finding({"title": "IDOR on /api/user/{id}", "vuln_class": "IDOR",
                           "severity": "high", "endpoint": "https://a.acme.com/api/user/1",
                           "method": "GET", "summary": "read other users",
                           "reproduction_steps": ["1. login", "2. curl /api/user/2"],
                           "impact": "PII disclosure",
                           "remediation": "object-level authorization"})
            report = reportgen.build_report(e)
            self.assertIn("IDOR on /api/user/{id}", report)
            self.assertIn("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:L/A:L", report)
            self.assertIn("Pre-submission checklist", report)


class TestPromptlib(unittest.TestCase):
    def test_render(self):
        with tempfile.TemporaryDirectory() as d:
            e = blackboard.Engagement(base=d, target="acme.com").create("acme.com")
            e.add_assets([{"host": "a.acme.com", "url": "https://a.acme.com/"}])
            p = promptlib.render_agent_prompt("think", e)
            self.assertIn("Think", p)
            self.assertIn("Current blackboard context", p)
            self.assertIn("Handoff contract", p)
            self.assertIn("```json", p)

    def test_all_agents_render(self):
        agents_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents")
        names = [os.path.splitext(n)[0] for n in os.listdir(agents_dir) if n.endswith(".md")]
        with tempfile.TemporaryDirectory() as d:
            e = blackboard.Engagement(base=d, target="acme.com").create("acme.com")
            for name in names:
                with self.subTest(agent=name):
                    p = promptlib.render_agent_prompt(name, e)
                    self.assertIn("Handoff contract", p)
                    self.assertIn("```json", p)


class TestCLI(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.target = "cli-test.example"
        self.base = self._tmp

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_full_cli_flow(self):
        self.assertEqual(cli.cmd_new(_ns(base=self._tmp, target=self.target,
                                         program="hackerone", scope="")), 0)
        e = blackboard.Engagement(base=self._tmp, target=self.target)
        self.assertTrue(e.exists())

        # ingest
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, dir=self._tmp) as f:
            json.dump([{"host": "api.example", "url": "https://api.example/", "priority": "P1"},
                       {"host": "cdn.example", "url": "https://cdn.example/", "priority": "KILL"}], f)
            ingest_file = f.name
        self.assertEqual(cli.cmd_ingest(_ns(base=self._tmp, target=self.target,
                                           kind="assets", file=ingest_file)), 0)

        # add finding
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, dir=self._tmp) as f:
            json.dump({"title": "IDOR on API", "vuln_class": "IDOR", "severity": "high",
                       "endpoint": "https://api.example/api/user/1", "method": "GET",
                       "asset": "api.example",
                       "summary": "read other user data via id swap",
                       "reproduction_steps": ["curl https://api.example/api/user/2"],
                       "impact": "PII disclosure",
                       "dup_check": {"verdict": "clean"}}, f)
            finding_file = f.name
        self.assertEqual(cli.cmd_add_finding(_ns(base=self._tmp, target=self.target,
                                                 file=finding_file)), 0)

        # triage + dedup + report
        self.assertEqual(cli.cmd_triage(_ns(base=self._tmp, target=self.target, finding=None)), 0)
        self.assertEqual(cli.cmd_dedup(_ns(base=self._tmp, target=self.target, threshold=0.6)), 0)
        self.assertEqual(cli.cmd_status(_ns(base=self._tmp, target=self.target)), 0)
        out = os.path.join(self._tmp, "report.md")
        self.assertEqual(cli.cmd_report(_ns(base=self._tmp, target=self.target,
                                            platform="h1", out=out)), 0)
        self.assertTrue(os.path.isfile(out))
        with open(out, encoding="utf-8") as fh:
            self.assertIn("IDOR on API", fh.read())


if __name__ == "__main__":
    unittest.main(verbosity=2)