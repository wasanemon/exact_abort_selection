# Exact Abort Selection 実験の再現手順

[Issue #1 の保存仕様](docs/issue_1.md)に基づき、元の Aria に単一ノード・完全 RMW
専用の中止選択 policy を追加した実験です。結果と限界は [日本語報告](REPORT_ja.md)、
phase・検査・時間区間は [設計](docs/eas_design.md)、固定 arity の上限と HSC 帰着は
[理論](docs/eas_theory.md)を参照してください。

元の Aria のベースは `d0508c393ec084582c12e6f3abadab63501eaedd`。
実装ブランチは `codex/issue-1-exact-abort-selection` です。
既存 YCSB の10キー設定や既存 protocol の既定動作は保持しています。
耐久性・複製・分散処理・再試行の新設計は含みません。

## 1. clean checkout と依存関係

以下は Linux、Bash、Python 3 の手順です。C++14 compiler、CMake、make、
jemalloc、Boost headers、glog、gflags が必要です。図の再生成だけに matplotlib を使い、
入力生成・実行・CSV集計・HSC検査には Python 標準ライブラリを使います。

```bash
sudo apt-get update
sudo apt-get install -y git make cmake g++ libjemalloc-dev libboost-dev libgoogle-glog-dev libgflags-dev python3 python3-matplotlib
git clone --branch codex/issue-1-exact-abort-selection https://github.com/wasanemon/exact_abort_selection.git
cd exact_abort_selection
set -euo pipefail
```

すでに checkout がある場合はそのリポジトリ直下から実行します。公開された実装 commit
を直接 checkout しても構いません。今回の測定時点の commit、dirty 状態、binary SHA256、
compiler flags は各結果ディレクトリの `environment.json` / `manifest.json` にあります。

## 2. build と正しさの検査

EAS は opt-in で、`ARIA_BUILD_EAS` の既定値は `OFF` です。既存 target だけを build
する場合は次のとおりです。

```bash
cmake -S . -B build-default -DCMAKE_BUILD_TYPE=Release
cmake --build build-default --target bench_ycsb bench_tpcc -j 2
```

実験用 target とテストを追加します。

```bash
cmake -S . -B build -DARIA_BUILD_EAS=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build --target bench_eas eas_selector_test eas_integration_test -j 2
mkdir -p experiments/eas/validation/reproduced
ctest --test-dir build --verbose --output-on-failure > experiments/eas/validation/reproduced/ctest.log 2>&1
python3 tests/test_hsc.py --output experiments/eas/validation/reproduced/hsc.json --log experiments/eas/validation/reproduced/hsc.log
python3 experiments/eas/test_tools.py > experiments/eas/validation/reproduced/tools.log 2>&1
```

CTest の `eas_selector` は独立 oracle との全中止round・commit mask・証明書比較、
次数の独立再計算、profile の B=1/2/既定値、adaptive の予算0/1/既定値、容量拒否などを
検査します。失敗時には `experiments/eas/validation/selector_failure.json` に反例を保存します。
`eas_integration` は native を含む実 Aria の読取り・private writes・最終DB全状態を
直接比較し、複数worker・同じ phase 遷移での3バッチ実行・必須の policy 反例も検査します。
HSC の有限検査は selector の実装を共有せず、空集合・重複集合を含む全列挙で帰着を点検します。
有限検査の成功を計算量下限の証明とは扱いません。

今回保存した検査結果は [validation](experiments/eas/validation/) にあります。
新しい検査ログを `reproduced/` に分けるため、保存済みの結果を置き換えません。

## 3. smoke と full

全方式の入力をファイルで固定し、同じ条件の5seed `[11,29,47,71,101]` を5反復として
比較します。各条件・各方式で seed=7 の別プロセスを一度実行して warmup とし、その後に
5回の測定を行います。方式順は `order_seed=20260905` で入れ替え、同時に実行する
benchmark は一つです。各プロセスで一バッチを一回だけ試行し、abort を再試行しません。

保存された [事前計画](experiments/eas/plan.json)の系列は次のとおりです。

|系列|条件|
|---|---|
|main|arity=2、n=128/512/2048/8192/32768、一様/Zipf 0.99、worker=1、k=2|
|arity|arity=1/3/4、n=512/8192、一様/Zipf 0.99、worker=1、k=2|
|worst|全員同じ2または4キー、n=256/1024/4096/16384、worker=1、k=1|
|constant|selector単体、arity=1/2/3/4/6/8、n=2048、一様、k=2、EAS4方式|
|scale|arity=2、n=8192、Zipf 0.99、worker=2/4、k=2。worker=1はmainと共通trace|
|zero_commit|同じ1キーの2取引、worker=1、k=2|

キー領域は10,000です。full は39条件、warmup189回、測定945回と、incidence予算を1に
した4方式の明示拒否検査を合わせて1138プロセスです。smoke は main の n=128 の2分布、
worst の arity=2/n=256、zero_commit の4条件を使う120プロセスです。

リポジトリには今回の `results/full` / `results/smoke` が含まれます。clean checkout
から再実行するときは、次のように新しい出力先を指定してください。

```bash
python3 experiments/eas/run.py --smoke --output experiments/eas/results/reproduce-smoke --timeout 120 --memory-mib 2048 --total-seconds 14400
python3 experiments/eas/summarize.py experiments/eas/results/reproduce-smoke
python3 experiments/eas/run.py --full --output experiments/eas/results/reproduce-full --timeout 120 --memory-mib 2048 --total-seconds 14400
python3 experiments/eas/summarize.py experiments/eas/results/reproduce-full
```

上記は実行環境で許可された全CPUを affinity の範囲に使います。今回の採用CLIは、
出力先を `experiments/eas/results/smoke` と `experiments/eas/results/full` とし、いずれも
次のCPU指定を追加したものです。

```bash
python3 experiments/eas/run.py --smoke --output experiments/eas/results/smoke --cpus 0,2,4,6,8 --timeout 120 --memory-mib 2048 --total-seconds 14400
python3 experiments/eas/run.py --full --output experiments/eas/results/full --cpus 0,2,4,6,8 --timeout 120 --memory-mib 2048 --total-seconds 14400
```

別環境では利用可能なCPU番号に置き換えます。`--cpus` は現在の affinity の部分集合のみ
許可し、要求worker数が使用可能CPU数を超える条件は `unsupported` にします。
使用可能な番号は `python3 -c 'import os; print(sorted(os.sched_getaffinity(0)))'` で確認できます。
各 worker を個別のCPUへ固定する指定ではなく、benchmark プロセスとそのthreadが動ける
CPU集合の指定です。

## 4. 予算、途中再開、結果の読み方

|オプション|既定値と意味|
|---|---|
|`--timeout`|120秒、各benchmarkプロセスの上限|
|`--memory-mib`|2048 MiB、子プロセスの `RLIMIT_AS`（仮想アドレス空間）上限。RSS制限ではない|
|`--total-seconds`|14400秒、runner全体の実行予算。再開時にも使用済み予算を引き継ぐ|
|`--max-incidence`|8,000,000、非空subset incidenceの上限|
|`--max-graph-bytes`|536,870,912、明示bitsetグラフpayloadの上限|
|`--binary`|`build/bench_eas`。性能測定には通常buildを使用|
|`--suite`|main/arity/worst/constant/scale/zero_commit。複数指定可能|
|`--seeds`|固定seedの部分集合などを指定する調査用。主評価は既定の5seed|

実エンジンは最大4キー、selector単体は最大8キーです。予算超過や対象外入力は
`unsupported` として記録し、入力の切捨てや別policyへの fallback は行いません。

途中から続ける場合は、元のコマンドに `--resume` を追加します。成功・失敗・timeoutを
含む保存済みの測定は再実行しません。binary、runner、計画のhashや予算・seed・CPU設定
が変わった場合は再開を拒否するので、新しい出力先を使います。出力先の既存manifestを
無条件に上書きする動作はありません。SIGINT/SIGTERMでは実行中の子process groupを停止し、
保存できた `interrupted` を残します。

`--dry-run` は新しい出力先にmanifestと環境情報を保存する計画確認用です。
実測は別の新しい出力先で開始してください。全体予算を使い切って実行できなかった予定は
`budget_exhausted`、途中終了した集計で保存レコードのない予定は `not_run` として表示します。
`timeout`、`oom`、`unsupported`、その他の失敗を有限の性能時間に置き換えません。
SIGKILLだけでOOMと断定せず、原因不明のkillは `killed_unknown` です。

各結果ディレクトリの主なファイルは次のとおりです。

|場所|内容|
|---|---|
|`plan.json`, `manifest.json`, `environment.json`|保存計画、使用した予算・hash・条件、OS/CPU/affinity/メモリ/compiler/flags/git状態|
|`commands.json`|実行順と各benchmarkの完全なargv・shell表現|
|`traces/*.tsv`|warmupと各固定seedの有限入力。全方式で共有|
|`raw/*.json`|benchmarkの生出力。全中止round・commit mask・証明書・時間・仕事量を含む|
|`records/*.json`, `runs.jsonl`|各プロセスのstatus、trace hash、コマンド、timeout、RSS、ログへの対応|
|`logs/`|各プロセスの標準出力・標準エラー・`/usr/bin/time`のRSS|
|`decision_checks.json`, `run_summary.json`|EAS同士の全配列直接比較、方式不足や失敗、実行件数|
|`summary/metrics.csv`, `summary/status_counts.csv`|成功観測の中央値・min/max・四分位範囲と、失敗を含む件数|
|`summary/paired_graph.csv`, `summary/paired_native.csv`|同policyのgraph比較と、異policyのnative比較|
|`summary/paired_observations.csv`, `summary/paired_ratios.csv`|seedごとの比とその集計。欠測したpairも保持|
|`summary/facts.json`, `summary/figures/`|報告用の事実一覧、再生成可能なPNG/SVG|

`peak_rss_kib` はDB・入力・検証を含むプロセス全体の高水位です。方式ごとの新しい
プロセスで測り、以前の方式の高水位を持ち越しません。`runner_peak_rss_kib` は
`/usr/bin/time`による別の記録です。`index_payload_bytes` は一部データ構造のpayload推定で、
selector全体の確保量ではありません。

速度比は各seedの `baseline_ms / mode_ms` を先に計算し、その比の中央値・IQR・min/maxを
取ります。独立に集計した中央値どうしの比ではありません。1より大きい値は分母の方式が
速いことを表します。`graph` 対 EAS は中止policyが同じ比較で、native 対 EAS は
policyが異なるバッチ全体の比較です。後者にcommit集合の一致は要求しません。

selector時間は抽出・正規化から構築・選択・証明書取得までを含みます。統合の
`batch_ms` はsnapshotの開始から書込み適用と完了handshakeまでです。入力生成、DB初期化、
検証は測定外です。worker累積時間とwall時間、親区間と内訳を足し合わせないでください。
正確な包含関係は [設計の計測区間表](docs/eas_design.md#検証と計測区間)にあります。

## 5. trace と個別実行

UTF-8 TSVで、先頭行は `EAS_TRACE_V1 key_count seed batch_id`、以後は
`ID<TAB>comma-separated-key-IDs` です。空の集合はIDとTABだけの行で表します。
実エンジンはIDを1からnの連番とし、`n < 2^20`、論理キーは `0..key_count-1` です。

generatorは `(seed,batch_id,transaction_id)` ごとのPython `random.Random`を使います。
一様分布またはZipf 0.99から重複キーを再抽選して指定arityを保ち、キーを昇順で保存します。
同一署名の異なる取引は残します。`identical` は全員が `0..arity-1` を触ります。
batch IDはworkload条件から決め、worker数・方式・実行順では変更しません。
値はキーから初期化する32 byteで、writeは読んだ値と固定IDに依存する共通の非自明な変換です。

保存traceを一方式だけ再実行する例です。

```bash
build/bench_eas --mode adaptive --trace experiments/eas/results/full/traces/main-l2-n8192-zipf-w1-k2-s11.tsv --k 2 --workers 1 --max-incidence 8000000 --max-graph-bytes 536870912 --output /tmp/eas-one-batch.json
```

modeは `native` / `graph` / `lazy` / `profile` / `adaptive` です。
`--selector-only` はDBを使わないEAS単体の実行です。`--trace`を複数回指定すると同じ
manager/workerで複数batchを実行できます。`--profile-B` と `--adaptive-budget` は
特殊値の検証用であり、主実験runnerは変更しません。

保存済み生データから集計だけを再生成できます。

```bash
python3 experiments/eas/summarize.py experiments/eas/results/full --output /tmp/eas-regenerated-summary
```

matplotlibなしでCSVだけを作る場合は `--no-plots` を追加します。生データディレクトリを
別のcheckoutへコピーした場合も、集計はその中の `raw/` を優先して読みます。

## 6. ASan/UBSan と TSan

sanitizer結果は性能データに混ぜません。追加コードと統合をASan/UBSanで検査します。

```bash
cmake -S . -B build-asan -DARIA_BUILD_EAS=ON -DCMAKE_BUILD_TYPE=RelWithDebInfo -DEAS_SANITIZER=address,undefined
cmake --build build-asan --target eas_selector_test eas_integration_test -j 2
ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir build-asan --verbose --output-on-failure > experiments/eas/validation/reproduced/asan_ubsan.log 2>&1
```

今回の環境ではLeakSanitizerの試行が `LeakSanitizer does not work under ptrace` と失敗したため、
上記ではleak検査だけを無効にしています。実際のエラーは
[selector_lsan_attempt.stderr](experiments/eas/validation/selector_lsan_attempt.stderr)に保存しました。
ASan/UBSanの成功を、未実行のleak検査まで通過した結果とは扱いません。

複数workerを含む統合テストをTSanでも実行します。

```bash
cmake -S . -B build-tsan -DARIA_BUILD_EAS=ON -DCMAKE_BUILD_TYPE=RelWithDebInfo -DEAS_SANITIZER=thread
cmake --build build-tsan --target eas_integration_test -j 2
TSAN_OPTIONS=halt_on_error=1 build-tsan/eas_integration_test > experiments/eas/validation/reproduced/integration_tsan.json 2> experiments/eas/validation/reproduced/integration_tsan.stderr
```

今回のTSan試行は161回のエンジン呼出し、181要求batch、246 assertionで通過し、stderrは空でした。
この有限試験を、すべての並行実行に対する証明とは扱いません。最終版の結果・実測値・
改善した条件と損になった条件は [REPORT_ja.md](REPORT_ja.md)を参照してください。
