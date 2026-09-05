#!/usr/bin/env python3
"""Rebuild CSV tables and static figures from saved EAS benchmark observations."""
import argparse
import csv
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run import save_json  # Standard-library helper only; main is not executed.

MODES = ("native", "graph", "lazy", "profile", "adaptive")
CONDITION_FIELDS = ("condition", "suite", "arity", "n", "distribution", "workers", "policy_k", "key_count", "selector_only")
META_NUMBERS = {"seed", "batch_id", "n", "workers", "policy_k", "key_count", "arity_min", "arity_max", "actual_arity"}
COLORS = {"native": "#555555", "graph": "#cc6677", "lazy": "#4477aa", "profile": "#228833", "adaptive": "#aa3377"}


def percentile(values, fraction):
    """Linear interpolation between sorted observations (Hyndman-Fan type 7)."""
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    low = int(index)
    return ordered[low] + (ordered[min(low + 1, len(ordered) - 1)] - ordered[low]) * (index - low)


def describe(values):
    if not values:
        return dict(count=0, median=None, minimum=None, maximum=None, q1=None, q3=None, iqr=None)
    first, third = percentile(values, .25), percentile(values, .75)
    return dict(count=len(values), median=statistics.median(values), minimum=min(values),
                maximum=max(values), q1=first, q3=third, iqr=third - first)


def write_csv(path, rows, preferred=()):
    fields = list(preferred) + sorted({key for row in rows for key in row} - set(preferred))
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def flatten_raw(raw):
    result = {}
    for key, value in raw.items():
        if key == "decisions":
            continue
        if key == "selector" and isinstance(value, dict):
            for stat, number in value.items():
                result[f"selector.{stat}"] = number
        elif not isinstance(value, (dict, list)):
            result[key] = value
    return result


def load_records(directory):
    # Individual atomic records remain usable if the runner was interrupted before runs.jsonl.
    records = [json.loads(path.read_text()) for path in sorted((directory / "records").glob("*.json"))]
    if not records and (directory / "runs.jsonl").exists():
        records = [json.loads(line) for line in (directory / "runs.jsonl").read_text().splitlines() if line]
    result = []
    for record in records:
        row = {key: value for key, value in record.items() if not isinstance(value, (dict, list))}
        raw_path = Path(record["raw_path"])
        # Data directories can be copied to a new checkout without editing saved absolute paths.
        local_raw = directory / "raw" / raw_path.name
        if local_raw.exists():
            raw_path = local_raw
        if raw_path.exists():
            try:
                data = flatten_raw(json.loads(raw_path.read_text()))
            except ValueError:
                data = {}
            # Preserve orchestration failures such as timeout even if a partial JSON says ok.
            data.pop("status", None)
            data.pop("mode", None)
            row.update(data)
        result.append(row)
    manifest_path = directory / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        present = {(row["condition"], row["seed"], row["mode"]) for row in result if row["phase"] == "measure"}
        for condition in manifest["conditions"]:
            for seed in manifest["identity"]["seeds"]:
                for mode in MODES:
                    if mode == "native" and condition["selector_only"]:
                        continue
                    if (condition["condition"], seed, mode) not in present:
                        result.append(dict(condition, seed=seed, mode=mode, phase="measure", status="not_run",
                                           reason="planned measurement has no saved record (interrupted run)"))
    return result


def summarize(rows):
    groups = {}
    for row in rows:
        if row["phase"] == "measure":
            groups.setdefault((row["condition"], row["mode"]), []).append(row)
    summary, statuses = [], []
    for key, group in sorted(groups.items()):
        base = {name: group[0][name] for name in CONDITION_FIELDS}
        base.update(mode=key[1], expected_repetitions=len(group))
        successful = [row for row in group if row["status"] == "ok"]
        counts = {status: sum(row["status"] == status for row in group) for status in sorted({r["status"] for r in group})}
        statuses.extend(dict(base, status=status, count=count) for status, count in counts.items())
        metrics = sorted({name for row in successful for name, value in row.items()
                          if (isinstance(value, (int, float)) and not isinstance(value, bool)
                              and (name.startswith("selector.") or name.endswith("_ms") or
                                   name in ("commit_count", "abort_count", "round_count", "peak_rss_kib",
                                            "runner_peak_rss_kib", "actual_arity", "arity_min", "arity_max",
                                            "initial_core_size", "value_bytes")))})
        for metric in metrics:
            values = [row[metric] for row in successful if isinstance(row.get(metric), (int, float))]
            summary.append(dict(base, metric=metric, **describe(values)))
    return summary, statuses


def paired_ratios(rows):
    groups = {}
    for row in rows:
        if row["phase"] == "measure":
            groups.setdefault((row["condition"], row["seed"]), {})[row["mode"]] = row
    observations = []
    for (condition, seed), by_mode in sorted(groups.items()):
        representative = next(iter(by_mode.values()))
        for baseline in ("graph", "native"):
            if baseline == "native" and representative["selector_only"]:
                continue
            for mode in ("lazy", "profile", "adaptive") if baseline == "graph" else ("graph", "lazy", "profile", "adaptive"):
                for metric in (("selector_ms", "batch_ms") if baseline == "graph" else ("batch_ms",)):
                    left = by_mode.get(baseline, dict(representative, mode=baseline, status="not_run"))
                    right = by_mode.get(mode, dict(representative, mode=mode, status="not_run"))
                    if metric == "batch_ms" and right["selector_only"]:
                        continue
                    result = {name: right[name] for name in CONDITION_FIELDS}
                    result.update(seed=seed, baseline=baseline, mode=mode, metric=metric,
                                  ratio=None, baseline_status=left["status"], mode_status=right["status"])
                    if left["status"] != "ok" or right["status"] != "ok":
                        result["status"] = "unavailable"
                    elif not isinstance(left.get(metric), (int, float)) or not isinstance(right.get(metric), (int, float)):
                        result["status"] = "missing_metric"
                    elif left[metric] <= 0 or right[metric] <= 0:
                        result["status"] = "nonpositive_interval"
                    elif left.get("trace_sha256") != right.get("trace_sha256"):
                        result["status"] = "trace_mismatch"
                    elif baseline == "graph" and left.get("decision_sha256") != right.get("decision_sha256"):
                        result["status"] = "decision_mismatch"
                    else:
                        result.update(status="ok", ratio=left[metric] / right[metric],
                                      baseline_ms=left[metric], mode_ms=right[metric])
                    observations.append(result)
    summaries = []
    groupings = {}
    for observation in observations:
        key = tuple(observation[name] for name in ("condition", "baseline", "mode", "metric"))
        groupings.setdefault(key, []).append(observation)
    for key, group in sorted(groupings.items()):
        base = {name: group[0][name] for name in CONDITION_FIELDS}
        base.update(baseline=key[1], mode=key[2], metric=key[3], expected_pairs=len(group))
        values = [row["ratio"] for row in group if row["status"] == "ok"]
        summaries.append(dict(base, **describe(values)))
    return observations, summaries


def make_figures(directory, summary, ratios):
    # Sandboxed checkouts need no access to the user's ~/.config/matplotlib.
    cache = tempfile.TemporaryDirectory(prefix="eas-matplotlib-")
    os.environ.setdefault("MPLCONFIGDIR", cache.name)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as error:
        return {"status": "unavailable", "error": str(error), "remedy": "install matplotlib; all CSV tables were generated"}
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                         "savefig.dpi": 160, "svg.fonttype": "none"})
    figure_dir = directory / "figures"
    figure_dir.mkdir(exist_ok=True)
    written = []

    def save(figure, name):
        figure.tight_layout()
        for suffix in ("png", "svg"):
            path = figure_dir / f"{name}.{suffix}"
            figure.savefig(path, bbox_inches="tight")
            written.append(str(path))
        plt.close(figure)

    def plot_lines(axis, data, x="n", reference=False):
        for mode in MODES:
            group = sorted((row for row in data if row["mode"] == mode and row["count"]), key=lambda row: row[x])
            if not group:
                continue
            axis.plot([r[x] for r in group], [r["median"] for r in group], marker="o", markersize=3,
                      label=mode, color=COLORS[mode])
            axis.fill_between([r[x] for r in group], [r["q1"] for r in group], [r["q3"] for r in group],
                              color=COLORS[mode], alpha=.13)
        if reference:
            axis.axhline(1, color="#777777", linestyle="--", linewidth=.8)
        axis.grid(alpha=.2)

    main = [row for row in summary if row["suite"] == "main"]
    if main:
        fig, axes = plt.subplots(2, 2, figsize=(10, 7))
        for column, distribution in enumerate(("uniform", "zipf")):
            for row_index, metric in enumerate(("selector_ms", "batch_ms")):
                values = [row for row in main if row["distribution"] == distribution and row["metric"] == metric
                          and (metric != "selector_ms" or row["mode"] != "native")]
                plot_lines(axes[row_index, column], values)
                axes[row_index, column].set(xscale="log", yscale="log", xlabel="Transactions per batch (n)",
                                            ylabel="Milliseconds, median and IQR", title=f"{distribution}: {metric}")
                axes[row_index, column].legend(fontsize=8)
        save(fig, "main_timing")
        fig, axes = plt.subplots(2, 2, figsize=(10, 7))
        for column, distribution in enumerate(("uniform", "zipf")):
            for row_index, (baseline, metric) in enumerate((("graph", "selector_ms"), ("native", "batch_ms"))):
                values = [row for row in ratios if row["suite"] == "main" and row["distribution"] == distribution
                          and row["baseline"] == baseline and row["metric"] == metric]
                plot_lines(axes[row_index, column], values, reference=True)
                axes[row_index, column].set(xscale="log", yscale="log", xlabel="Transactions per batch (n)",
                                            ylabel="Paired time ratio, median and IQR",
                                            title=f"{distribution}: {baseline} / mode ({metric})")
                axes[row_index, column].legend(fontsize=8)
        save(fig, "main_paired_ratios")
    worst = [row for row in summary if row["suite"] == "worst"]
    if worst:
        fig, axes = plt.subplots(2, 3, figsize=(13, 7))
        for row_index, arity in enumerate((2, 4)):
            for column, metric in enumerate(("selector_ms", "selector.degree_queries", "selector.switches")):
                values = [row for row in worst if row["arity"] == arity and row["metric"] == metric and row["mode"] != "native"]
                plot_lines(axes[row_index, column], values)
                axes[row_index, column].set(xscale="log", xlabel="Transactions per batch (n)",
                                            ylabel="Median and IQR", title=f"Identical {arity}-key transactions: {metric}")
                if metric != "selector.switches":
                    axes[row_index, column].set_yscale("symlog", linthresh=.01 if metric.endswith("_ms") else 1)
                axes[row_index, column].legend(fontsize=8)
        save(fig, "worst_and_switch")
    constant = [row for row in summary if row["suite"] == "constant"]
    if constant:
        fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
        for axis, metric in zip(axes, ("selector_ms", "selector.incidences", "peak_rss_kib")):
            plot_lines(axis, [row for row in constant if row["metric"] == metric], "arity")
            axis.set(yscale="log", xlabel="Keys per transaction", ylabel="Median and IQR", title=metric)
            axis.legend(fontsize=8)
        save(fig, "arity_constant_cost")
    arity_data = [row for row in summary if row["suite"] == "arity"]
    if arity_data:
        fig, axes = plt.subplots(2, 2, figsize=(10, 7))
        for i, n in enumerate((512, 8192)):
            for j, distribution in enumerate(("uniform", "zipf")):
                values = [row for row in arity_data if row["n"] == n and row["distribution"] == distribution
                          and row["metric"] == "batch_ms"]
                plot_lines(axes[i, j], values, "arity")
                axes[i, j].set(yscale="log", xlabel="Keys per transaction", ylabel="Batch ms, median and IQR",
                               title=f"n={n}, {distribution}")
                axes[i, j].legend(fontsize=8)
        save(fig, "arity_integrated")
    scale = [row for row in summary if row["suite"] == "scale" or
             (row["suite"] == "main" and row["n"] == 8192 and row["distribution"] == "zipf")]
    if scale:
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
        for axis, metric in zip(axes, ("batch_ms", "sync_wait_ms")):
            plot_lines(axis, [row for row in scale if row["metric"] == metric], "workers")
            axis.set(xlabel="Workers", ylabel="Milliseconds, median and IQR", title=f"8192 transactions, Zipf: {metric}")
            axis.legend(fontsize=8)
        save(fig, "worker_scaling")
    return {"status": "ok", "matplotlib_version": matplotlib.__version__, "files": written,
            "shading": "Interquartile range across five paired input seeds (or successful subset, see CSV count)",
            "missing": "No finite benchmark timings substituted for timeout/OOM/unsupported observations",
            "ratio_direction": "greater than one means denominator mode is faster; graph compares same policy; native compares different policies"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    args.directory = args.directory.resolve()
    destination = (args.output or args.directory / "summary").resolve()
    destination.mkdir(parents=True, exist_ok=True)
    rows = load_records(args.directory)
    if not rows:
        parser.error("no saved run records")
    summaries, statuses = summarize(rows)
    paired, ratios = paired_ratios(rows)
    write_csv(destination / "runs.csv", rows, ("phase", "condition", "mode", "seed", "status"))
    write_csv(destination / "status_counts.csv", statuses, CONDITION_FIELDS + ("mode", "status", "count"))
    write_csv(destination / "metrics.csv", summaries, CONDITION_FIELDS + ("mode", "metric", "count", "median", "minimum", "maximum", "q1", "q3", "iqr"))
    write_csv(destination / "paired_observations.csv", paired, CONDITION_FIELDS + ("baseline", "mode", "seed", "metric", "status", "ratio"))
    write_csv(destination / "paired_ratios.csv", ratios, CONDITION_FIELDS + ("baseline", "mode", "metric", "count", "median", "minimum", "maximum", "q1", "q3", "iqr"))
    for baseline in ("graph", "native"):
        write_csv(destination / f"paired_{baseline}.csv", [row for row in ratios if row["baseline"] == baseline],
                  CONDITION_FIELDS + ("baseline", "mode", "metric", "count", "median", "minimum", "maximum", "q1", "q3", "iqr"))
    measured = [row for row in rows if row["phase"] == "measure"]
    facts = {"measurement_count": len(measured), "successful_count": sum(r["status"] == "ok" for r in measured),
             "warmup_count": sum(r["phase"] == "warmup" for r in rows),
             "capacity_probes": [{key: row.get(key) for key in ("mode", "status", "control_passed", "max_incidence", "error")}
                                 for row in rows if row["phase"] == "capacity_probe"],
             "zero_commit": [{key: row.get(key) for key in ("condition", "seed", "mode", "commit_count", "abort_count", "status")}
                             for row in measured if row["suite"] == "zero_commit"],
             "adaptive_switches": [{key: row.get(key) for key in ("condition", "suite", "seed", "status", "selector.switches",
                                      "selector.switch_round", "selector.switch_remaining", "selector.switch_queries", "selector.degree_queries")}
                                   for row in measured if row["mode"] == "adaptive"],
             "statistics": "median, min/max, interpolated quartiles (Hyndman-Fan type 7); successful observations only",
             "paired_ratio": "per-seed baseline duration / mode duration, then summarize the ratios; never ratio of independent medians",
             "timing_intervals": "selector_ms includes extraction/normalization and kernel. selector.total_ms is the same interval; kernel_ms excludes normalize. batch_ms includes read, reservation, selection, commit and waits. Worker cumulative fields are not wall-time components. See engine/design docs for nested fields; do not sum overlapping fields.",
             "rss": "peak_rss_kib is whole benchmark process high-water mark; runner_peak_rss_kib independently obtained via /usr/bin/time; every run a fresh process",
             "source": str(args.directory)}
    save_json(destination / "facts.json", facts)
    plots = {"status": "disabled"} if args.no_plots else make_figures(destination, summaries, ratios)
    save_json(destination / "figures.json", plots)
    print(json.dumps({"output": str(destination), "measurements": len(measured), "metrics": len(summaries),
                      "paired_ratios": len(ratios), "figures": plots["status"]}, sort_keys=True))
    return 1 if any(row["status"] in ("trace_mismatch", "decision_mismatch") for row in paired) else 0


if __name__ == "__main__":
    sys.exit(main())
