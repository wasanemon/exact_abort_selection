#!/usr/bin/env python3
"""Small checks of experiment bookkeeping; temporary fake observations are not results."""
import json
from pathlib import Path
import tempfile
import unittest
import os

import run
import summarize


class ExperimentToolsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="eas-tools-test-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.plan = json.loads((run.HERE / "plan.json").read_text())

    def test_prespecified_jobs_and_worker_invariant_input(self):
        conditions = run.configurations(self.plan)
        self.assertEqual(len(conditions), 39)
        invocations = sum((4 if c["selector_only"] else 5) * 6 for c in conditions)
        self.assertEqual(invocations + 4, 1138)
        first = next(c for c in conditions if c["suite"] == "main" and c["n"] == 8192 and c["distribution"] == "zipf")
        second = next(c for c in conditions if c["suite"] == "scale" and c["workers"] == 4)
        self.assertEqual(first["batch_id"], second["batch_id"])
        self.assertEqual(len(run.configurations(self.plan, smoke=True)), 4)

    def test_trace_reproducible_and_fixed_arity(self):
        condition = run.configurations(self.plan, smoke=True)[0]
        for distribution in ("uniform", "zipf", "identical"):
            condition = dict(condition, distribution=distribution, arity=4, n=16)
            first, second = self.path / "first.tsv", self.path / "second.tsv"
            run.generate_trace(first, condition, 11)
            run.generate_trace(second, condition, 11)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            for transaction_id, line in enumerate(first.read_text().splitlines()[1:], 1):
                identifier, key_text = line.split("\t")
                self.assertEqual(int(identifier), transaction_id)
                keys = list(map(int, key_text.split(",")))
                self.assertEqual(len(set(keys)), 4)
                self.assertEqual(keys, sorted(keys))
                self.assertTrue(all(0 <= key < condition["key_count"] for key in keys))

    def test_timeout_stays_timeout_even_with_json(self):
        path = self.path / "raw.json"
        run.save_json(path, {"status": "ok", "verification": "passed", "batch_ms": 1})
        record = {"status": "timeout", "returncode": -9}
        run.inspect_benchmark(record, path)
        self.assertEqual(record["status"], "timeout")

    def test_exact_pair_comparison_detects_round_boundary(self):
        records = []
        for mode, rounds in (("graph", [[2, 3]]), ("lazy", [[2], [3]])):
            path = self.path / f"{mode}.json"
            run.save_json(path, {"decisions": {"abort_rounds": rounds, "commit": [1, 0, 0], "certificate": [1]}})
            records.append(dict(phase="measure", condition="fixture", seed=11, mode=mode,
                                status="ok", raw_path=str(path)))
        checks = run.check_pairs(records, self.path / "checks.json")
        self.assertEqual(checks[0]["status"], "failed")

    def test_paired_ratio_and_failed_timings_excluded(self):
        condition = run.configurations(self.plan, smoke=True)[0]
        rows = []
        for seed, graph_time, lazy_time in ((11, 1, 4), (29, 10, 5), (47, 100, 10)):
            for mode, duration in (("graph", graph_time), ("lazy", lazy_time)):
                rows.append(dict(condition, phase="measure", seed=seed, mode=mode, status="ok",
                                 batch_ms=duration, selector_ms=duration, trace_sha256="same", decision_sha256="same"))
        rows.append(dict(rows[-1], seed=71, status="timeout", batch_ms=999, selector_ms=999))
        rows.append(dict(rows[-2], mode="graph", seed=71, status="ok", batch_ms=999, selector_ms=999))
        observations, ratios = summarize.paired_ratios(rows)
        selected = next(row for row in ratios if row["metric"] == "batch_ms" and row["baseline"] == "graph" and row["mode"] == "lazy")
        self.assertEqual(selected["count"], 3)
        self.assertEqual(selected["expected_pairs"], 4)
        self.assertEqual(selected["median"], 2)
        self.assertTrue(any(row["status"] == "unavailable" for row in observations))
        missing = next(row for row in ratios if row["metric"] == "batch_ms" and row["mode"] == "adaptive")
        self.assertEqual(missing["count"], 0)
        statistics, _ = summarize.summarize(rows)
        selected = next(row for row in statistics if row["mode"] == "lazy" and row["metric"] == "batch_ms")
        self.assertEqual(selected["median"], 5)
        self.assertEqual(selected["maximum"], 10)

    def test_fresh_process_and_timeout(self):
        cpus = sorted(os.sched_getaffinity(0))
        first = run.execute(["/bin/true"], self.path / "first", 2, 512, cpus)
        second = run.execute(["/bin/true"], self.path / "second", 2, 512, cpus)
        self.assertEqual(first["status"], "ok")
        self.assertNotEqual(first["wrapper_pid"], second["wrapper_pid"])
        timed = run.execute(["/bin/sleep", "10"], self.path / "timeout", .03, 512, cpus)
        self.assertEqual(timed["status"], "timeout")
        self.assertLess(timed["process_wall_seconds"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
