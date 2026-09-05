#!/usr/bin/env python3
"""Generate Japanese report tables solely from summarize.py's saved CSV tables."""
import argparse
import csv
from pathlib import Path

MODES = ("native", "graph", "lazy", "profile", "adaptive")
EAS_MODES = MODES[1:]


def read_csv(path, required=True):
    if not path.exists() and not required:
        return []
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def number(value, integer=False, scale=1):
    parsed = float(value) / scale
    if integer and parsed.is_integer():
        return f"{int(parsed):,}"
    if parsed == 0:
        return "0"
    if abs(parsed) < .001:
        return f"{parsed:.3g}"
    return f"{parsed:,.3f}"


class Tables:
    def __init__(self, directory):
        self.metrics = read_csv(directory / "metrics.csv")
        self.ratios = read_csv(directory / "paired_ratios.csv")
        self.statuses = read_csv(directory / "status_counts.csv", required=False)
        self.by_metric = {(row["condition"], row["mode"], row["metric"]): row for row in self.metrics}
        self.by_ratio = {(row["condition"], row["baseline"], row["mode"], row["metric"]): row for row in self.ratios}
        self.conditions = {}
        for row in self.metrics + self.statuses + self.ratios:
            self.conditions[row["condition"]] = row
        self.lines = []

    def text(self, value=""):
        self.lines.append(value)

    def table(self, headers, rows):
        self.text("|" + "|".join(headers) + "|")
        self.text("|" + "|".join("---" for _ in headers) + "|")
        for row in rows:
            self.text("|" + "|".join(map(str, row)) + "|")
        self.text()

    def conditions_for(self, suite):
        return sorted((row for row in self.conditions.values() if row["suite"] == suite),
                      key=lambda row: (row["distribution"] != "uniform", row["distribution"],
                                       int(row["arity"]), int(row["n"]), int(row["workers"])))

    def missing(self, condition, mode):
        failed = [(row["status"], row["count"]) for row in self.statuses
                  if row["condition"] == condition and row["mode"] == mode and row["status"] != "ok"]
        return "—" if not failed else "— (" + ", ".join(f"{status}×{count}" for status, count in failed) + ")"

    def cell(self, condition, mode, metric, interval=True, integer=False, scale=1, baseline=None):
        record = (self.by_metric.get((condition, mode, metric)) if baseline is None else
                  self.by_ratio.get((condition, baseline, mode, metric)))
        if not record or not record.get("median") or int(record["count"]) == 0:
            if baseline is not None:
                return "— (有効pairなし)"
            return self.missing(condition, mode)
        result = number(record["median"], integer, scale)
        if interval:
            result += " [" + number(record["q1"], integer, scale) + "–" + number(record["q3"], integer, scale) + "]"
        expected = record.get("expected_pairs" if baseline is not None else "expected_repetitions", record["count"])
        if int(record["count"]) < int(expected):
            result += f" (n={record['count']}/{expected})"
        return result

    def metric(self, row, mode, metric, **kwargs):
        return self.cell(row["condition"], mode, metric, **kwargs)

    def render(self):
        self.text("# 日本語報告用の再生成表")
        self.text()
        self.text("`metrics.csv`・`paired_ratios.csv`・`status_counts.csv`から生成。時間はms。"
                  "原則として値は中央値 [第1四分位点–第3四分位点]、IQRはこの区間の幅です。"
                  "commit数・仕事量・切替え位置は中央値のみを示します。")
        self.text()
        self.text("5固定seedによる5反復の成功観測だけを集計し、少ない場合は `(n=有効数/予定数)` と表示します。"
                  "失敗・欠測に有限時間を代入しません。倍率は各seedで baseline時間 / mode時間を計算してから集計し、"
                  "1より大きければmodeが速いことを表します。graph比較は同policy、native比較は異なるpolicyです。"
                  "独立した中央値どうしの比・commit差ではありません。")
        self.text()
        main = self.conditions_for("main")
        if main:
            self.text("## 主系列（arity=2、worker=1、k=2）")
            self.text()
            self.text("selector時間（抽出・正規化・構築から証明書取得まで）。")
            self.text()
            self.table(["分布", "n"] + list(EAS_MODES), [
                [row["distribution"], row["n"]] + [self.metric(row, mode, "selector_ms") for mode in EAS_MODES]
                for row in main])
            self.text("統合バッチ時間、commit数、およびpaired比。EASのcommit欄はadaptiveの値を示し、"
                      "EAS4方式の判断一致は別途 `decision_checks.json` で検査します。")
            self.text()
            self.table(["分布", "n", "native batch", "adaptive batch", "native commit", "EAS commit",
                        "graph/adaptive selector比", "native/adaptive batch比"], [
                [row["distribution"], row["n"], self.metric(row, "native", "batch_ms"),
                 self.metric(row, "adaptive", "batch_ms"),
                 self.metric(row, "native", "commit_count", interval=False, integer=True),
                 self.metric(row, "adaptive", "commit_count", interval=False, integer=True),
                 self.metric(row, "adaptive", "selector_ms", baseline="graph"),
                 self.metric(row, "adaptive", "batch_ms", baseline="native")]
                for row in main])
        worst = self.conditions_for("worst")
        if worst:
            self.text("## 同一署名の最悪挙動系列（k=1）")
            self.text()
            self.table(["arity", "n"] + list(EAS_MODES), [
                [row["arity"], row["n"]] + [self.metric(row, mode, "selector_ms") for mode in EAS_MODES]
                for row in worst])
            self.table(["arity", "n", "lazy次数質問", "adaptive次数質問", "adaptive切替え回数", "切替えround", "切替え時残存数"], [
                [row["arity"], row["n"]] + [self.metric(row, mode, metric, interval=False, integer=True)
                  for mode, metric in (("lazy", "selector.degree_queries"), ("adaptive", "selector.degree_queries"),
                                       ("adaptive", "selector.switches"), ("adaptive", "selector.switch_round"),
                                       ("adaptive", "selector.switch_remaining"))]
                for row in worst])
        constant = self.conditions_for("constant")
        if constant:
            self.text("## arityの定数費用（selector単体、n=2048）")
            self.text()
            self.text("RSSは全プロセスの高水位（MiB）で、selectorだけの確保量ではありません。"
                      "各方式を新しいプロセスで測定し、`runner_peak_rss_kib` を優先、"
                      "存在しない場合に `peak_rss_kib` を使用します。subset/incidence数は実際に構築した"
                      "subset indexの要素数であり、graphの0はsubset indexを構築しないことを表します。")
            self.text()
            values = []
            for row in constant:
                for mode in EAS_MODES:
                    rss = "runner_peak_rss_kib" if (row["condition"], mode, "runner_peak_rss_kib") in self.by_metric else "peak_rss_kib"
                    values.append([row["arity"], mode,
                                   self.metric(row, mode, "selector.subsets", interval=False, integer=True),
                                   self.metric(row, mode, "selector.incidences", interval=False, integer=True),
                                   self.metric(row, mode, "selector_ms"), self.metric(row, mode, rss, scale=1024),
                                   "runner" if rss.startswith("runner") else "benchmark"])
            self.table(["arity", "mode", "subset数", "incidence数", "selector ms", "全プロセスRSS MiB", "RSS出典"], values)
        arity = self.conditions_for("arity")
        if arity:
            self.text("## arity=1/3/4の統合バッチ時間")
            self.text()
            self.table(["分布", "arity", "n"] + list(MODES), [
                [row["distribution"], row["arity"], row["n"]] + [self.metric(row, mode, "batch_ms") for mode in MODES]
                for row in arity])
        scale = self.conditions_for("scale") + [row for row in main if row["n"] == "8192" and row["distribution"] == "zipf"]
        scale.sort(key=lambda row: int(row["workers"]))
        if scale:
            self.text("## worker数の確認（arity=2、n=8192、Zipf 0.99）")
            self.text()
            self.text("worker=1は主系列から取得します。最初の表は統合バッチwall時間、次の表は"
                      "同期残差の推定wall時間です。最後のreservation欄だけは全workerの累積処理時間で、"
                      "wall時間やその内訳へ重ねて加算できません。")
            self.text()
            self.table(["worker"] + list(MODES), [
                [row["workers"]] + [self.metric(row, mode, "batch_ms") for mode in MODES]
                for row in scale])
            self.table(["worker"] + [mode + " sync" for mode in MODES] + ["adaptive selector", "adaptive reservation累積"], [
                [row["workers"]] + [self.metric(row, mode, "sync_wait_ms") for mode in MODES] +
                [self.metric(row, "adaptive", "selector_ms"), self.metric(row, "adaptive", "reservation_worker_ms")]
                for row in scale])
        self.text("丸め前の数値・min/max・有効反復数・全statusは元CSVに残しています。"
                  "表の丸めにより短い時間の四分位区間が同じ値に見える場合があります。"
                  "通常入力でadaptiveが切り替えたかは `metrics.csv` の `selector.switches` と"
                  " `facts.json` を併せて確認してください。")
        return "\n".join(self.lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="full results directory or its summary/ directory")
    parser.add_argument("--output", type=Path, help="default: summary/tables_ja.md")
    args = parser.parse_args(argv)
    source = args.directory.resolve()
    if not (source / "metrics.csv").exists():
        source = source / "summary"
    if not (source / "metrics.csv").exists() or not (source / "paired_ratios.csv").exists():
        parser.error("metrics.csv and paired_ratios.csv are required; run summarize.py first")
    destination = (args.output or source / "tables_ja.md").resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(Tables(source).render())
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
