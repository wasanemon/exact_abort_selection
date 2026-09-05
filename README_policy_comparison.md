# Issue #3: Aria上のpolicy比較の再現

範囲は単一ノード、CPU、インメモリ、point access、完全RMWです。
[事前計画](experiments/policy_comparison/plan.json)と
[日本語報告](REPORT_policy_comparison_ja.md)を参照してください。Issue #4 は未着手です。
PR #2 の EAS HEAD `d1de8c4fe3285cc5ed338b760a13be8890007a29` から分岐し、
既存policy、元Aria、以前の生データ/報告を保持しています。

## clean checkoutから実行

Linux、C++14、CMake、make、jemalloc、Boost headers、glog、gflags、Python3が必要です。
図の再生成にだけmatplotlibを使います（既存の依存関係は README_eas.md を参照）。

```bash
git clone --branch codex/issue-3-policy-comparison https://github.com/wasanemon/exact_abort_selection.git
cd exact_abort_selection
set -euo pipefail
cmake -S . -B build -DARIA_BUILD_EAS=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build --target bench_eas eas_selector_test eas_integration_test policy_comparison_test -j 2
ctest --test-dir build --verbose --output-on-failure
python3 experiments/policy_comparison/test_tools.py
python3 experiments/eas/test_tools.py
python3 tests/test_audit_results.py
mkdir -p experiments/policy_comparison/reproduced/quality
python3 tests/test_hsc.py --output experiments/policy_comparison/reproduced/hsc.json --log experiments/policy_comparison/reproduced/hsc.log
timeout 1800 build/policy_comparison_test --quality-dir experiments/policy_comparison/reproduced/quality
python3 experiments/policy_comparison/run.py --smoke --output experiments/policy_comparison/reproduced/smoke --cpus 0,2,4,6,8
python3 experiments/policy_comparison/analyze.py experiments/policy_comparison/reproduced/smoke
python3 experiments/policy_comparison/run.py --full --output experiments/policy_comparison/reproduced/full --cpus 0,2,4,6,8
python3 experiments/policy_comparison/analyze.py experiments/policy_comparison/reproduced/full
```

CPU番号は利用可能なaffinityの部分集合に置き換えられます。
確認は `python3 -c 'import os; print(sorted(os.sched_getaffinity(0)))'`。
同じCPU集合を全方式で共有し、管理threadとworkerそれぞれの固定割当や排他的占有はしません。
全計測に同じRelease binaryを使用します。sanitizerは性能計測と分離します。

```bash
cmake -S . -B build-asan -DARIA_BUILD_EAS=ON -DCMAKE_BUILD_TYPE=RelWithDebInfo -DEAS_SANITIZER=address,undefined
cmake --build build-asan --target eas_selector_test eas_integration_test policy_comparison_test -j 2
ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir build-asan --verbose --output-on-failure
```

前回環境のptrace/LeakSanitizer制約に合わせleak検査のみ無効です。ASan/UBSanの通過から
leak検査の通過は主張しません。CTestはfrozen top-k、k=2ゼロcommit、k=1対照、
実DBのsnapshot/private writes/全最終状態、worker=1/2/4・3連続batchを含みます。

## 計画・時間・容量

主10条件＋補助arity6条件＋worker2/4の2条件＋全員同一2キー4096の対照1条件です。
2キー8192のEAS k=1対照はmainと同じ観測を再利用します。性能1,500実行、warmup100実行。
各条件は5入力seed、それぞれ3回の新プロセス計測です。smokeは7条件・544実行です。
方式順はseed付きで入れ替え、高負荷方式を同時実行しません。
seed=7の別プロセスwarmupは次プロセスのheap/cacheを暖める保証がありません。

全方式は同じ32byte値、同じ取引本体、同じreservationを実行します。nativeは既存の
SI=false/reordering=trueの判定を使います。nativeはselectorを呼ばず、実入力抽出・
正規化は測定外の検査にだけ使用します。新方式とEASのselector時間は実R/W抽出・正規化、
入力安全性検査、必要な構築・ソート・選択、mask/証明書と公開コピー、scratch解放を含みます。
batch時間はsnapshot公開直前から全確定書込みと完了handshakeまでです。
trace生成・DB初期化・検査用開始状態コピー・oracle・検査・JSON出力は測定外です。

`accept_id` はID順を確認し、必要時だけソートします。採用済みキーのbyte配列だけを使い、
不採用のキーを予約しません。subset incidenceは0で、`max_incidence=0`でも実行できます。
selector APIでは明示した `max_arity` により8を超える集合も扱います。実Aria実験は全方式4キー以下です。
staticは1/2キー用singleton/pair計数、3/4キー用immutable包除計数を一度構築し、
全初期次数と順位を固定します。`count_ms`は計数構造の構築・次数評価・解放、
`sort_ms`は順位整列、`select_ms`は採用検査です。採用後の次数更新はありません。
EASの既存 `build_ms` は構築・初期順位、`select_ms` は選択と削除更新、
`trim_ms` はtrimとその更新、`switch_ms` は旧索引解放とprofile再構築です。
内訳に含まれる区間を親時間へ再加算しません。更新仕事量や再質問数もCSVに保存します。
`initial_core_size` は新採用方式では未計数（0）です。

プロセスごと120秒、RLIMIT_AS 2048MiB、計測ループ全体14,400秒の固定予算です。
subsetを使う方式のincidence上限は8,000,000、graph payloadは512MiBです。
RSSはDB・検査・出力も含む各プロセス全体の高水位で、selector単独の確保量ではありません。
timeout/OOM/unsupported等は失敗statusで保存し、有限時間に置換しません。
中断後は同じコマンドへ `--resume` を追加します。計画、binary、runner、CPU、raw/trace hashが
一致する場合のみ再開し、保存済みの失敗も再測定しません。新しい試行は別出力先を使います。

## 保存データから監査・再集計

`results/full` と `results/smoke` がclean checkoutからの正式測定です。
`results/development-smoke` は実装時の検査、`baseline_smoke` は変更前EASの確認であり、
性能比には混ぜません。全て原本を無損失archiveに保存しています。

```bash
tar -xzf experiments/policy_comparison/results/full/raw_data.tar.gz -C experiments/policy_comparison/results/full
tar -xzf experiments/policy_comparison/results/smoke/raw_data.tar.gz -C experiments/policy_comparison/results/smoke
tar -xzf experiments/policy_comparison/quality/raw_data.tar.gz -C experiments/policy_comparison/quality
python3 experiments/policy_comparison/analyze.py experiments/policy_comparison/results/full --output /tmp/policy-summary-full
python3 experiments/policy_comparison/analyze.py experiments/policy_comparison/results/smoke --output /tmp/policy-summary-smoke
```

`analyze.py`はraw/trace hash・予定全件・全配列のpolicy/k別一致・確定集合の非交差・
新方式の極大性/採用順再実行・native最小writer規則を検査します。対応する旧k=2保存結果とも
全decision配列だけを照合し、旧時間を使いません。CSVを作るだけなら `--no-plots` で実行可能です。

- `plan.json`, `manifest.json`, `environment.json`, `commands.json`: 計画、測定commit/binary/flags/affinity、全コマンド。
- `trace_manifest.json`: 元archive member、再生成bytes一致、trace SHA256。入力を全方式・全反復で共有。
- `runs.jsonl`, `records/`, `raw/`, `logs/`: 全反復status、完全decision配列、内訳時間・仕事量、stdout/stderr/RSS。
- `summary/seed_metrics.csv`: 各seed内3反復の中央値/min/max/IQR。
- `summary/metrics.csv`: seed内中央値を5seedで集計した中央値/min/max/IQR。
- `summary/paired_observations.csv`, `paired_seed.csv`, `paired.csv`: 同一trace・同一反復の差/比→seed内→seed間集計。
- `summary/sensitivity_roots.csv`, `sensitivity_grid.csv`: 各paired観測の仮定本体費用逆転点と感度曲線。
- `quality/quality.jsonl`: 最大確定件数と5policy件数の全保存入力。順序はnative/accept_id/static/EAS k1/k2。
- `quality/witness_search.jsonl`, `witnesses.json`, `*.tsv`: 有限探索20,000入力、縮小前後、採用順と中止round。
- `archive_manifest.json`: archive全memberのSHA256。`pack.py`が無損失性を検査して生成。
- `next_stage.json`: 測定に基づく後続への材料。自動採択/新規性認定ではありません。

有効処理率は `commit_count / batch_seconds` という一バッチの量で、retryを含む
定常throughput・公平性の証明ではありません。commit=0なら有効処理率0、成功1件あたり費用は
未定義（JSON/CSVはnull/空欄）です。感度分析の追加本体費用cは仮定で、重い取引の実測ではありません。
最大確定件数は計画したn<=18の取引部分集合全探索に限り、大入力の最適値は測定していません。
