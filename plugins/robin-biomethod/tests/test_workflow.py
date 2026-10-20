"""Offline integration checks; deterministic runners are NOT model capability evidence."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest
import subprocess
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "vendor")]
from robinharness.runtime import Budget, BudgetExceeded, CodexRunner, POLICY, dump, fingerprint, safe_relative, redact
from robinharness.engine import FileTaskAdapter, CodexProposer, evaluate, run_task, validate_config
from robinharness.adoption import adopt, rollback
from robinharness.cli import optimize, config_diff, unknown_costs, read_report, snapshot_task
from harness2.core.tree import read_tree


class ScriptedRunner:
    model = "offline-test-only"

    def __init__(self, fixture):
        self.fixture = fixture
        self.calls = []
        self.contexts = []

    def run(self, ws, mission, label, timeout=None):
        self.calls.append(label)
        self.contexts.append([str(p.relative_to(ws)) for p in ws.rglob("*") if p.is_file()])
        assert not any(p.name == "expected.json" for p in ws.rglob("*"))
        if label.startswith("execute:"):
            # Expected data are held in this test stub, not in the model workspace.
            expected = json.loads((self.fixture / "expected.json").read_text())
            lines = {}
            for p in (ws / "source").glob("*.txt"):
                for line in p.read_text().splitlines():
                    loc, text = line[1:].split("] ", 1)
                    lines[loc] = (p.name, text)
            rows = []
            for cid, rule in expected.items():
                rows.append(dict(id=cid, claim="fixture claim", status=rule["status"], uncertainty="",
                    citations=[dict(source=lines[loc][0], locator=loc, quote=lines[loc][1])
                               for loc in rule["locators"]]))
            dump(ws / "output/evidence.json", dict(claims=rows))
            text = "File delivered."
        elif label.startswith("experience."):
            text = "<edits>component: AGENTS.md\nverdict: no observed effect</edits>\nNO_ENTRY"
        elif label.startswith("select."):
            text = "<why>Equivalent fixture outputs.</why>\n" + chr(96)*3 + "choice\nA\n" + chr(96)*3
        else:
            text = "<notes>KEEP_BASE: no evidence supports a modification.</notes>"
        return dict(text=text, trajectory="[ACTION] offline stub\n[OBSERVATION] file created", usage={})


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixture = self.root / "task"
        shutil.copytree(ROOT / "examples/evidence/tasks/adapt-1", self.fixture)
        self.runner = ScriptedRunner(self.fixture)
        self.adapter = FileTaskAdapter(self.fixture / "task.json", self.root / "experiment", self.runner)

    def tearDown(self):
        self.temp.cleanup()

    def test_real_upstream_k1_plumbing(self):
        prop = CodexProposer(self.runner, self.root / "edits")
        result = run_task(self.adapter, prop)
        self.assertEqual(result.status, "ok")
        self.assertEqual(len([x for x in self.runner.calls if x.startswith("execute:")]), 4)
        self.assertEqual(len(self.runner.calls), 8)
        self.assertTrue(result.selections["agg"]["trivial"])
        self.assertFalse(result.selections["agg"]["experience"])
        self.assertFalse(any("expected.json" in p for paths in self.runner.contexts for p in paths))

    def test_real_upstream_k2_selection_plumbing(self):
        result = run_task(self.adapter, CodexProposer(self.runner, self.root / "edits"), k=2)
        self.assertEqual(result.status, "ok")
        self.assertEqual(len([x for x in self.runner.calls if x.startswith("execute:")]), 8)
        self.assertFalse(result.selections["agg"]["trivial"])
        self.assertTrue(any(x.startswith("select.") for x in self.runner.calls))

    def test_evaluator_and_mutated_quote(self):
        rd = self.adapter.execute("adapt-1", None, "check")
        self.assertTrue(evaluate(self.adapter, rd)["valid"])
        p = rd / "output/evidence.json"
        d = json.loads(p.read_text())
        d["claims"][0]["citations"][0]["quote"] = "fabricated"
        dump(p, d)
        self.assertFalse(evaluate(self.adapter, rd)["valid"])

    def test_missing_and_duplicate_claims(self):
        rd = self.adapter.execute("adapt-1", None, "check")
        p = rd / "output/evidence.json"
        d = json.loads(p.read_text())
        d["claims"] = [d["claims"][0], d["claims"][0]]
        dump(p, d)
        self.assertTrue(evaluate(self.adapter, rd)["critical"])

    def test_missing_output(self):
        self.assertFalse(evaluate(self.adapter, self.root)["valid"])

    def test_answer_leak_rejected(self):
        (self.fixture / "source/expected.json").write_text("{}")
        with self.assertRaises(ValueError):
            FileTaskAdapter(self.fixture / "task.json", self.root / "x", self.runner)

    def test_changed_source_cannot_enter_a_comparison(self):
        (self.fixture / "source/main.txt").write_text("changed after task loading")
        with self.assertRaises(ValueError):
            self.adapter.execute("adapt-1", None, "drift")
        self.assertEqual(self.runner.calls, [])

    def test_snapshot_freezes_prompt_and_hidden_expectations(self):
        dest = snapshot_task(self.adapter, self.root / "snapshot")
        prompt = (dest.parent / "prompt.txt").read_text()
        (self.fixture / "prompt.txt").write_text("later edit")
        self.assertEqual((dest.parent / "prompt.txt").read_text(), prompt)
        self.assertTrue((dest.parent / "expected.json").is_file())
        self.assertFalse((dest.parent / "source/expected.json").exists())

    def test_budget_persisted_and_exhausted(self):
        b = Budget(self.root / "budget.json", 1, 1)
        i, _ = b.reserve("one")
        b.finish(i, state="ok")
        with self.assertRaises(BudgetExceeded):
            Budget(self.root / "budget.json", 100, 100).reserve("two")

    def test_elapsed_budget(self):
        b = Budget(self.root / "budget.json")
        b.data["deadline"] = 0
        with self.assertRaises(BudgetExceeded):
            b.reserve("late")

    def test_path_and_symlink_guard(self):
        for value in ("../secret", "/etc/passwd", ""):
            with self.assertRaises(ValueError):
                safe_relative(value)
        (self.root / "link").symlink_to(self.fixture / "task.json")
        with self.assertRaises(ValueError):
            fingerprint(self.root)

    def test_hooks_rejected(self):
        config = read_tree(self.adapter.substrate.surface(), self.adapter.base)
        config[".codex/hooks.json"] = "{}"
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_adoption_and_safe_rollback(self):
        target = self.root / "target"
        candidate = self.root / "candidate"
        shutil.copytree(self.adapter.base, target)
        shutil.copytree(target, candidate)
        before = fingerprint(target)
        (candidate / "AGENTS.md").write_text((candidate / "AGENTS.md").read_text() + "\nVerify citations.\n")
        self.assertTrue(config_diff(target, candidate))
        txn = adopt(candidate, target, self.root / "state", before)
        self.assertEqual(fingerprint(target), fingerprint(candidate))
        rollback(txn)
        self.assertEqual(fingerprint(target), before)

    def test_adoption_source_drift(self):
        candidate = self.root / "candidate"
        shutil.copytree(self.adapter.base, candidate)
        with self.assertRaises(ValueError):
            adopt(candidate, self.adapter.base, self.root / "state", "outdated")

    def test_rollback_refuses_newer_work(self):
        candidate = self.root / "candidate"
        shutil.copytree(self.adapter.base, candidate)
        txn = adopt(candidate, self.adapter.base, self.root / "state", fingerprint(self.adapter.base))
        (self.adapter.base / "AGENTS.md").write_text("new user edit")
        with self.assertRaises(ValueError):
            rollback(txn)

    def test_credential_redaction(self):
        s = redact("Authorization: Bearer private-value sk-abcdefghijklmnopqrst")
        self.assertNotIn("private-value", s)
        self.assertNotIn("sk-abcdefghijklmnopqrst", s)

    def test_package_manifest_and_provenance(self):
        root = json.loads((ROOT / "plugin.json").read_text())
        compat = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(root["name"], compat["name"])
        self.assertEqual(root["version"], compat["version"])
        self.assertTrue((ROOT / "vendor/LICENSE.harness2").exists())
        for p in (ROOT / "skills").glob("*/SKILL.md"):
            self.assertIn("description: Load when", p.read_text())

    def test_outer_report_keeps_perfect_baseline(self):
        args = SimpleNamespace(task=str(self.fixture / "task.json"), run_dir=str(self.root / "outer"),
             k=1, mode="parallel", session_limit=24, minutes=60, model=None,
             holdout=[str(self.fixture / "task.json")], learning_task=None)
        with patch("robinharness.cli.CodexRunner", return_value=self.runner):
            # Reusing the adaptation input as holdout is rejected separately below.
            args.holdout = []
            result, _ = optimize(args)
        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["recommended"])
        self.assertTrue(result["original_unchanged"])

    def test_missing_required_structure_is_not_valid(self):
        rd = self.adapter.execute("adapt-1", None, "check")
        p = rd / "output/evidence.json"
        d = json.loads(p.read_text())
        del d["claims"][0]["uncertainty"]
        dump(p, d)
        self.assertFalse(evaluate(self.adapter, rd)["valid"])

    def test_identical_holdout_rejected_before_model_use(self):
        args = SimpleNamespace(task=str(self.fixture / "task.json"), run_dir=str(self.root / "outer"),
             k=1, mode="parallel", session_limit=24, minutes=60, model=None,
             holdout=[str(self.fixture / "task.json")], learning_task=None)
        with patch("robinharness.cli.CodexRunner", return_value=self.runner):
            with self.assertRaises(ValueError):
                optimize(args)
        self.assertEqual(self.runner.calls, [])

    def test_codex_identity_and_default_model_contract(self):
        auth_home = self.root / "auth"
        auth_home.mkdir()
        (auth_home / "auth.json").write_text("{}")
        ws = self.root / "workspace"
        ws.mkdir()
        (ws / "AGENTS.md").write_text(POLICY)
        budget = Budget(self.root / "budget.json")
        events = json.dumps({"type":"item.completed","item":{"type":"agent_message","text":"OK"}})
        with patch("robinharness.runtime.shutil.which", return_value="/fake/codex"):
            runner = CodexRunner(budget, self.root / "audit", "codex-default")
        runner.auth_home = auth_home
        with patch("robinharness.runtime.subprocess.Popen") as popen:
            popen.return_value.communicate.return_value = (events, "")
            popen.return_value.returncode = 0
            result = runner.run(ws, "No tools.", "unit")
            argv = popen.call_args.args[0]
            env = popen.call_args.kwargs["env"]
            self.assertNotIn("--model", argv)
            self.assertIn("--ignore-user-config", argv)
            self.assertNotIn("OPENAI_API_KEY", env)
            self.assertNotEqual(env["CODEX_HOME"], str(auth_home))
            self.assertEqual(result["text"], "OK")
        self.assertEqual(budget.data["sessions"][0]["state"], "ok")

    def test_unknown_cost_is_not_zero(self):
        self.assertEqual(unknown_costs({"usd":0.0,"score":0,"nested":[{"cost_usd":0}]}),
                         {"usd":None,"score":0,"nested":[{"cost_usd":None}]})

    def test_upstream_package_fingerprints(self):
        import hashlib
        data = json.loads((ROOT / "vendor/UPSTREAM.json").read_text())
        for rel, digest in data["files"].items():
            self.assertEqual(hashlib.sha256((ROOT / "vendor" / rel).read_bytes()).hexdigest(), digest)

    def test_progress_does_not_claim_completion(self):
        Budget(self.root / "budget.json")
        result = read_report(self.root)
        self.assertEqual(result["status"], "not_finalized")
        self.assertFalse(result["report_available"])

    def test_timeout_counts_and_terminates_session(self):
        auth = self.root / "auth"
        auth.mkdir()
        (auth / "auth.json").write_text("{}")
        ws = self.root / "worker"
        ws.mkdir()
        (ws / "AGENTS.md").write_text(POLICY)
        (ws / "output").mkdir()
        dump(ws / "output/method.json", dict(status="draft_missing_evidence"))
        b = Budget(self.root / "budget.json", 1, 1)
        with patch("robinharness.runtime.shutil.which", return_value="/fake/codex"):
            runner = CodexRunner(b, self.root / "audit", "codex-default")
        runner.auth_home = auth
        with patch("robinharness.runtime.subprocess.Popen") as popen, patch("robinharness.runtime.os.killpg") as kill:
            popen.return_value.communicate.side_effect = [subprocess.TimeoutExpired("codex", 1), ("", "")]
            with self.assertRaises(TimeoutError):
                runner.run(ws, "test", "timeout")
            kill.assert_called_once()
        self.assertEqual(b.data["sessions"][0]["state"], "timeout")
        partial = self.root / "audit" / b.data["sessions"][0]["partial_output"]
        self.assertTrue((partial / "method.json").exists())
        self.assertFalse(json.loads((partial.parent / "receipt.json").read_text())["transport_completed"])
        with self.assertRaises(BudgetExceeded):
            b.reserve("retry")

    def test_invalid_edit_retries_then_keeps_base(self):
        original = self.runner.run
        def invalid(ws, mission, label, timeout=None):
            result = original(ws, mission, label, timeout)
            if not label.startswith(("execute:", "experience.", "select.")):
                (ws / "context/harness/.codex").mkdir(exist_ok=True)
                (ws / "context/harness/.codex/hooks.json").write_text("{}")
            return result
        self.runner.run = invalid
        result = run_task(self.adapter, CodexProposer(self.runner, self.root / "edits"))
        self.assertEqual(result.status, "ok")
        self.assertTrue(result.modes["agg"]["fell_back"])
        self.assertTrue(any(x.endswith(".a2") for x in self.runner.calls))

    def test_experience_is_passed_to_next_task(self):
        original = self.runner.run
        def with_experience(ws, mission, label, timeout=None):
            result = original(ws, mission, label, timeout)
            if label.startswith("experience."):
                result["text"] = ("<experience>\ncue: supplied documents conflict\n"
                    "lesson: check AGENTS.md source reconciliation instruction\n"
                    "evidence: offline fixture only, not model evidence\nconfidence: low\n</experience>")
            return result
        self.runner.run = with_experience
        lib = self.root / "library"
        prop = CodexProposer(self.runner, self.root / "edits")
        first = run_task(self.adapter, prop, library_root=lib)
        first_harvests = [r.workspace for r in prop._calls if r.workspace]
        self.assertTrue(list(lib.rglob("EXPERIENCE.md")))
        later_dir = self.root / "later-fixture"
        shutil.copytree(ROOT / "examples/evidence/tasks/adapt-2", later_dir)
        self.runner.fixture = later_dir
        later = FileTaskAdapter(later_dir / "task.json", self.root / "later", self.runner)
        second = run_task(later, prop, library_root=lib)
        self.assertEqual(second.status, "ok")
        self.assertTrue(any("/library/" in p for paths in self.runner.contexts for p in paths))
        self.assertTrue(all(p.is_dir() for p in first_harvests))
        all_harvests = [r.workspace for r in prop._calls if r.workspace]
        self.assertEqual(len(all_harvests), len(set(all_harvests)))

    def test_explicit_seed_library_is_copied_and_current_task_excluded(self):
        from harness2.core.library import Library
        source = self.root / "previous-library"
        lib = Library(source, "scientific-evidence", self.adapter.substrate.surface())
        config = read_tree(self.adapter.substrate.surface(), self.adapter.base)
        exp = dict(cue="conflicting sources", lesson="reconcile source statements", evidence="offline fixture")
        lib.add("historical", config, experience=exp)
        lib.add("adapt-1", config, experience=exp)
        before = fingerprint(source)
        args = SimpleNamespace(task=str(self.fixture / "task.json"), run_dir=str(self.root / "outer"),
             k=1, mode="parallel", session_limit=24, minutes=60, model=None, holdout=[],
             learning_task=None, library_dir=str(source))
        with patch("robinharness.cli.CodexRunner", return_value=self.runner):
            result, run = optimize(args)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(fingerprint(source), before)
        copied = Library(run / "library", "scientific-evidence", self.adapter.substrate.surface())
        self.assertIn("historical", copied.entries())
        self.assertNotIn("adapt-1", copied.entries())


if __name__ == "__main__":
    unittest.main()
