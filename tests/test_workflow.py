import tempfile
import unittest
from pathlib import Path
from patchroom.core import FIXTURE, case_path, initialize, load, propose, reproduce, run_contract


class EvidenceWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.case = initialize(self.work, "case-1", "Exactly $100 should have free shipping")

    def fixed_source(self):
        return (FIXTURE / "checkout.py").read_text().replace(
            'amount > Decimal("100.00")', 'amount >= Decimal("100.00")')

    def candidate(self, source):
        path = self.work / "proposed.py"
        path.write_text(source)
        return path

    def test_failing_baseline_then_passing_candidate_exports_evidence(self):
        baseline = reproduce(self.work, "case-1")
        self.assertFalse(baseline["passed"])
        self.assertIn("FAIL: test_exact_threshold", baseline["output"])
        candidate = propose(self.work, "case-1", self.candidate(self.fixed_source()))
        self.assertTrue(candidate["passed"])
        self.assertEqual(candidate["contract_sha256"], baseline["contract_sha256"])
        _, state = load(self.work, "case-1")
        self.assertEqual(state["status"], "awaiting_human_review")
        self.assertIn("+    return", (self.case / "candidate.patch").read_text())
        self.assertIn(candidate["source_sha256"], (self.case / "review.md").read_text())
        with self.assertRaisesRegex(ValueError, "verified candidate"):
            reproduce(self.work, "case-1")
        self.assertEqual(load(self.work, "case-1")[1]["status"], "awaiting_human_review")

    def test_cannot_propose_before_reproduction(self):
        with self.assertRaisesRegex(ValueError, "reproduce"):
            propose(self.work, "case-1", self.candidate(self.fixed_source()))

    def test_incorrect_patch_is_rejected(self):
        reproduce(self.work, "case-1")
        wrong = self.fixed_source().replace('Decimal("100.00")', 'Decimal("99.00")')
        result = propose(self.work, "case-1", self.candidate(wrong))
        self.assertFalse(result["passed"])
        self.assertFalse((self.case / "review.md").exists())

    def test_working_copy_cannot_replace_saved_contract(self):
        (self.case / "test_checkout.py").write_text("# accidentally deleted tests\n")
        reproduce(self.work, "case-1")
        source = (FIXTURE / "checkout.py").read_text() + "\n# unchanged logic\n"
        result = propose(self.work, "case-1", self.candidate(source))
        self.assertFalse(result["passed"])

    def test_exit_zero_without_running_tests_is_rejected(self):
        result = run_contract("import sys\nsys.exit(0)\n", (FIXTURE / "test_checkout.py").read_text())
        self.assertFalse(result["passed"])
        self.assertFalse(result["completed"])

    def test_case_ids_cannot_escape_work_directory(self):
        for value in ["../escape", "/tmp/escape", "a/b", "", "a;echo"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                case_path(self.work, value)

    def test_duplicate_case_preserves_original(self):
        with self.assertRaises(FileExistsError):
            initialize(self.work, "case-1", "replacement report")
        self.assertEqual(load(self.work, "case-1")[1]["report"],
                         "Exactly $100 should have free shipping")


if __name__ == "__main__":
    unittest.main()
