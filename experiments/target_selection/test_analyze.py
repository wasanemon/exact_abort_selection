#!/usr/bin/env python3
"""Integrity and statistical regression tests for the target-selection archive."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("target_analyze", Path(__file__).with_name("analyze.py"))
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class AnalysisTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "raw").mkdir()
        (self.root / "traces").mkdir()
        empty = dict(arity=[], n=[], distribution=[], k=[])
        self.plan = dict(main=dict(arity=[1], n=[3], distribution=["uniform"], k=[1]),
                         scale=copy.deepcopy(empty), paper_k=copy.deepcopy(empty), dense=copy.deepcopy(empty),
                         seeds=[11, 29, 47, 71, 101], repetitions_per_seed=3, key_count=3, zipf=.99,
                         variants=["paper", "graph", "lazy", "profile", "adaptive", "accept_id", "accept_static_degree"])
        audit.save(self.root / "plan.json", self.plan)
        conditions = audit.expected_conditions(self.plan)
        self.jobs = list(audit.planned_jobs(self.plan, conditions).values())
        traces = {}
        for job in self.jobs:
            name = job["trace"]
            path = "traces/" + name
            data = (f"EAS_TRACE_V1 3 {job['seed']} {job['batch_id']}\n1\t0\n2\t0\n3\t0\n").encode()
            (self.root / path).write_bytes(data)
            traces[name] = dict(path=path, sha256=audit.digest(data), batch_id=job["batch_id"])
            job["trace_sha256"] = traces[name]["sha256"]
        audit.save(self.root / "trace_manifest.json", traces)
        self.manifest = dict(scope="full", expected_jobs=len(self.jobs), conditions=conditions, jobs=self.jobs,
                             saved_plan_sha256=audit.digest((self.root / "plan.json").read_bytes()))
        audit.save(self.root / "manifest.json", self.manifest)
        self.records = []
        for job in self.jobs:
            mode, rep = job["mode"], job["repetition"]
            times = {"paper": [1, 2, 100], "adaptive": [2, 100, 1]}.get(mode, [2, 2, 2])
            raw = dict(status="ok", verification="passed", n=3, mode=mode, k=1,
                       total_ms=times[rep - 1], commit_count=1, fvs_size=2, peak_rss_kib=1234,
                       stats=dict(build_ms=.1),
                       decisions=dict(abort_rounds=[[3], [2]] if mode in audit.EXACT else [], commit=[1, 0, 0],
                                      certificate=[1], consideration_order=[] if mode in audit.EXACT else [1, 2, 3],
                                      rejected_ids=[] if mode in audit.EXACT else [2, 3], initial_degrees=[]))
            path = "raw/" + job["id"] + ".json"
            audit.save(self.root / path, raw)
            self.records.append(dict(job, status="ok", raw_path=path,
                                     raw_sha256=audit.digest((self.root / path).read_bytes())))
        self.write_records()

    def write_records(self):
        (self.root / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in self.records))

    def run_audit(self):
        return audit.analyze(self.root, self.root / "summary", plots=False)

    def archive(self):
        with tarfile.open(self.root / "raw_data.tar.gz", "w:gz") as archive:
            for folder in ("raw", "traces"):
                for path in sorted((self.root / folder).iterdir()):
                    archive.add(path, arcname=str(path.relative_to(self.root)))
        for folder in ("raw", "traces"):
            for path in (self.root / folder).iterdir():
                path.unlink()

    def test_paired_ratios_are_computed_before_both_medians(self):
        result = self.run_audit()
        self.assertTrue(result["complete"], result["errors"])
        pair = next(r for r in result["paired_condition_metrics"] if r["numerator"] == "paper")
        # Per repetition [1/2, 2/100, 100/1], median .5. The quotient
        # of independent medians is 2/2 = 1 and would fail this assertion.
        self.assertEqual(pair["total_ms_ratio_median"], .5)
        self.assertEqual(pair["total_ms_ratio_count"], 5)
        self.assertEqual(result["direct_array_comparisons"], 90)

    def test_archive_only_is_identical_to_unpacked(self):
        unpacked = self.run_audit()
        self.archive()
        archived = self.run_audit()
        self.assertEqual(unpacked, archived)

    def test_logs_and_complete_archive_manifest_are_verified(self):
        (self.root / "logs").mkdir()
        (self.root / "logs/command.log").write_text("saved command\n")
        with tarfile.open(self.root / "raw_data.tar.gz", "w:gz") as archive:
            files = sorted(p for sub in ("raw", "traces", "logs") for p in (self.root / sub).iterdir())
            for path in files:
                archive.add(path, arcname=str(path.relative_to(self.root)))
        manifest = dict(archive="raw_data.tar.gz", sha256=audit.digest((self.root / "raw_data.tar.gz").read_bytes()),
                        members=[dict(path=str(p.relative_to(self.root)), bytes=p.stat().st_size,
                                      sha256=audit.digest(p.read_bytes())) for p in files])
        audit.save(self.root / "archive_manifest.json", manifest)
        result = self.run_audit()
        self.assertTrue(result["complete"], result["errors"])
        self.assertEqual(result["checked_archive_members"], 111)
        manifest["members"] = manifest["members"][:-1]
        audit.save(self.root / "archive_manifest.json", manifest)
        result = self.run_audit()
        self.assertFalse(result["complete"])
        self.assertTrue(any("membership mismatch" in error for error in result["errors"]))

    def test_raw_hash_corruption_is_rejected(self):
        path = self.root / self.records[0]["raw_path"]
        path.write_bytes(path.read_bytes() + b" ")
        result = self.run_audit()
        self.assertFalse(result["complete"])
        self.assertTrue(any("raw hash mismatch" in e for e in result["errors"]))

    def test_trace_corruption_is_rejected_in_archive(self):
        path = next((self.root / "traces").iterdir())
        path.write_bytes(path.read_bytes() + b"4\t0\n")
        self.archive()
        result = self.run_audit()
        self.assertFalse(result["complete"])
        self.assertTrue(any("trace hash mismatch" in e for e in result["errors"]))

    def test_same_commit_mask_different_abort_order_is_rejected(self):
        record = next(r for r in self.records if r["mode"] == "graph")
        path = self.root / record["raw_path"]
        raw = audit.load_json(path)
        raw["decisions"]["abort_rounds"] = [[2], [3]]
        audit.save(path, raw)
        record["raw_sha256"] = audit.digest(path.read_bytes())
        self.write_records()
        result = self.run_audit()
        self.assertFalse(result["complete"])
        self.assertTrue(any("full decision arrays disagree" in e for e in result["errors"]))

    def test_missing_job_and_timeout_are_retained(self):
        self.records.pop()
        self.records[0]["status"] = "timeout"
        self.write_records()
        result = self.run_audit()
        self.assertFalse(result["complete"])
        self.assertEqual(result["statuses"]["missing"], 1)
        self.assertEqual(result["statuses"]["timeout"], 1)
        self.assertEqual(result["observed_records"], 104)
        self.assertEqual(len((self.root / "summary/observations.csv").read_text().splitlines()), 106)

    def test_reducing_manifest_cannot_hide_missing_job(self):
        self.records.pop()
        self.manifest["jobs"] = self.manifest["jobs"][:-1]
        self.manifest["expected_jobs"] -= 1
        audit.save(self.root / "manifest.json", self.manifest)
        self.write_records()
        result = self.run_audit()
        self.assertFalse(result["complete"])
        self.assertTrue(any("complete plan grid" in e for e in result["errors"]))
        self.assertEqual(result["expected_jobs"], 105)

    def test_tar_paths_are_rejected_without_extraction(self):
        for name in ("../outside.json", "/tmp/outside.json"):
            with self.subTest(name=name):
                with tarfile.open(self.root / "raw_data.tar.gz", "w:gz") as archive:
                    member = tarfile.TarInfo(name)
                    member.size = 2
                    archive.addfile(member, io.BytesIO(b"{}"))
                with self.assertRaisesRegex(ValueError, "unsafe archive member"):
                    audit.Storage(self.root)


if __name__ == "__main__":
    unittest.main()
