#!/usr/bin/env python3
"""Small synthetic artifact fixtures; no engine/performance trials are run."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("audit_results", ROOT / "experiments/eas/audit_results.py")
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")


def fixture(directory, smoke=False):
    """Metadata exercises the required scale group; arrays stay intentionally tiny.

    These are parser/comparison fixtures, not purported 8192-transaction runs or
    a substitute for the engine's checks of transaction/state validity.
    """
    conditions = []
    for workers in ([1] if smoke else [1, 2, 4]):
        suite = "main" if workers == 1 else "scale"
        conditions.append(dict(condition=f"{suite}-l2-n8192-zipf-w{workers}-k2", suite=suite,
                               arity=2, n=8192, distribution="zipf", workers=workers,
                               policy_k=2, key_count=2, zipf=0.99, selector_only=False, batch_id=123))
    save(directory / "manifest.json", {"identity": {"seeds": [11], "smoke": smoke},
                                        "conditions": conditions, "warmup": "seed=7; separate process"})
    modes = ["native", "graph", "lazy", "profile", "adaptive"]
    save(directory / "plan.json", {"modes": modes})
    for condition in conditions:
        for phase, seed in (("warmup", 7), ("measure", 11)):
            trace_name = f"{condition['condition']}-s{seed}.tsv"
            trace = directory / "traces" / trace_name
            trace.parent.mkdir(parents=True, exist_ok=True)
            trace.write_text(f"fixture-seed={seed}\n1\t0,1\n2\t0,1\n")
            for mode in modes:
                record = dict(condition, phase=phase, seed=seed, mode=mode, status="ok")
                name = audit_module.stem(record)
                raw = dict(record, verification="passed",
                           decisions={"abort_rounds": [[2]], "commit": [1, 0], "certificate": [1]})
                if mode == "native":
                    raw["decisions"] = {"abort_rounds": [], "commit": [0, 1], "certificate": [2]}
                raw_path = directory / "raw" / (name + ".json")
                save(raw_path, raw)
                record.update(trace_path="/old/relocated/experiment/traces/" + trace_name,
                              raw_path="/old/relocated/experiment/raw/" + name + ".json",
                              trace_sha256=audit_module.sha256(trace), raw_sha256=audit_module.sha256(raw_path))
                save(directory / "records" / (name + ".json"), record)


class AuditFixtureTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="eas-audit-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.full, self.smoke = self.base / "full", self.base / "smoke"
        fixture(self.full)
        fixture(self.smoke, smoke=True)

    def test_success_relocation_and_native_exclusion(self):
        result = audit_module.audit(self.full, self.smoke)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["violation_count"], 0)
        self.assertEqual(result["datasets"]["full"]["expected_records"], 30)
        self.assertEqual(result["datasets"]["full"]["file_integrity"], {"matched": 60})
        self.assertEqual(result["checks"]["same_policy_full"]["decision_comparisons"], 18)
        self.assertEqual(result["checks"]["workers_full"]["decision_comparisons"], 20)
        self.assertEqual(result["checks"]["full_smoke_overlap"]["decision_comparisons"], 10)

    def test_missing_and_timeout_are_unavailable(self):
        prefix = "main-l2-n8192-zipf-w1-k2-s11-measure-"
        (self.full / "records" / (prefix + "profile.json")).unlink()
        (self.full / "raw" / (prefix + "lazy.json")).unlink()
        graph = self.full / "records" / (prefix + "graph.json")
        data = json.loads(graph.read_text()); data["status"] = "timeout"; save(graph, data)
        result = audit_module.audit(self.full)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["violation_count"], 0)
        self.assertEqual(len(result["datasets"]["full"]["missing_records"]), 1)
        group = next(g for g in result["checks"]["same_policy_full"]["groups"]
                     if "/main-" in g["group"] and "/measure/" in g["group"])
        self.assertEqual(group["unavailable"], {"graph": "record_status:timeout",
                                               "lazy": "missing_raw_file", "profile": "missing_record"})

    def test_hash_corruption_sets_nonzero_exit(self):
        trace = self.full / "traces/main-l2-n8192-zipf-w1-k2-s11.tsv"
        trace.write_text(trace.read_text() + "corruption\n")
        output = self.base / "audit.json"
        with contextlib.redirect_stdout(io.StringIO()):
            code = audit_module.main([str(self.full), "--output", str(output)])
        result = json.loads(output.read_text())
        self.assertEqual(code, 1)
        self.assertIn("sha256_mismatch", {v["kind"] for v in result["violations"]})

    def test_arrays_detect_changed_decisions_even_with_updated_hash(self):
        name = "scale-l2-n8192-zipf-w2-k2-s11-measure-adaptive.json"
        raw_path = self.full / "raw" / name
        data = json.loads(raw_path.read_text())
        data["decisions"]["abort_rounds"] = [[1]]
        save(raw_path, data)
        record_path = self.full / "records" / name
        record = json.loads(record_path.read_text())
        record["raw_sha256"] = audit_module.sha256(raw_path); save(record_path, record)
        result = audit_module.audit(self.full)
        kinds = {v["kind"] for v in result["violations"]}
        self.assertIn("decision_mismatch", kinds)
        self.assertNotIn("sha256_mismatch", kinds)
        self.assertTrue(any(v.get("differing_arrays") == ["abort_rounds"] for v in result["violations"]))

    def test_trace_bytes_detect_difference_even_with_updated_hashes(self):
        prefix = "scale-l2-n8192-zipf-w2-k2-s11"
        trace = self.full / "traces" / (prefix + ".tsv")
        trace.write_text(trace.read_text() + "different paired input\n")
        for path in (self.full / "records").glob(prefix + "-*.json"):
            record = json.loads(path.read_text())
            record["trace_sha256"] = audit_module.sha256(trace); save(path, record)
        result = audit_module.audit(self.full)
        kinds = {v["kind"] for v in result["violations"]}
        self.assertIn("trace_bytes_mismatch", kinds)
        self.assertNotIn("sha256_mismatch", kinds)

    def test_smoke_native_is_compared_only_with_same_mode(self):
        name = "main-l2-n8192-zipf-w1-k2-s11-measure-native.json"
        path = self.smoke / "raw" / name
        data = json.loads(path.read_text()); data["decisions"]["certificate"] = [1]; save(path, data)
        path = self.smoke / "records" / name
        record = json.loads(path.read_text())
        record["raw_sha256"] = audit_module.sha256(self.smoke / "raw" / name); save(path, record)
        result = audit_module.audit(self.full, self.smoke)
        different = [v for v in result["violations"] if v["kind"] == "decision_mismatch"]
        self.assertEqual(len(different), 1)
        self.assertTrue(different[0]["group"].startswith("full-smoke/"))
        self.assertTrue(different[0]["group"].endswith("mode=native"))

    def test_worker_absent_from_manifest_is_explicit(self):
        path = self.full / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["conditions"] = [c for c in manifest["conditions"] if c["workers"] != 4]
        save(path, manifest)
        for path in (self.full / "records").glob("*-w4-*.json"):
            path.unlink()
        result = audit_module.audit(self.full)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["violation_count"], 0)
        self.assertTrue(all(g["unavailable"]["4"] == "not_in_manifest"
                            for g in result["checks"]["workers_full"]["groups"]))

    def test_missing_manifest_is_not_reported_as_success(self):
        (self.full / "manifest.json").unlink()
        result = audit_module.audit(self.full)
        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["datasets"]["full"]["expected_records"])
        self.assertEqual(result["datasets"]["full"]["status"], "unavailable")
        self.assertEqual(result["violation_count"], 0)


if __name__ == "__main__":
    unittest.main()
