# Issue #4 の再検査と再測定

開始点: `d150211968ef6d61efda82f9f44f63e3bac28b44`。
[候補選定](docs/target_selection_ja.md)、[意味論の対応証明](docs/ding_semantics_ja.md)、
[事前gate](experiments/target_selection/gate.json)、[事前plan](experiments/target_selection/plan.json)、
[最終報告](REPORT_target_selection_ja.md)を先に読む。

実証は **Ding Algorithm 2 / prod-degree の独立 C++ standalone 再現**。
原著 artifact、Aria engine、Cicada、ChainMaker、Fabric network はこの実証では実行しない。
既存 `eas/Selector.cpp` / `eas/Oracle.cpp` は #3 のまま使う。
DBMS transaction body、storage、durability、network、retry、steady-state throughput の評価ではない。

## Clean checkout と build

配布branchの commit を固定して clone する。既存の作業ディレクトリや結果を上書きしない。
以下の `<issue-4-commit>` は調べたい Issue #4 の commit SHA に置き換える。

```bash
git clone https://github.com/wasanemon/exact_abort_selection.git /tmp/eas-issue4-reproduce
git -C /tmp/eas-issue4-reproduce checkout <issue-4-commit>
cd /tmp/eas-issue4-reproduce
python3 experiments/target_selection/verify_sources.py
python3 experiments/target_selection/build.py --output /tmp/issue4-release/validator
/tmp/issue4-release/validator --self-test
python3 experiments/target_selection/check_witnesses.py --binary /tmp/issue4-release/validator --output /tmp/issue4-fixed-witnesses.json
python3 experiments/target_selection/build.py --sanitize --output /tmp/issue4-sanitize/validator
ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 /tmp/issue4-sanitize/validator --self-test
python3 experiments/target_selection/test_analyze.py
```

必要なのは C++14対応g++ と Python 3.9以上、Linux の affinity/resource API。
図の再生成は matplotlib を使う。標準C++と既存selectorだけを直接linkするので、DBMSの
glog/gflags/jemallocなどの依存は不要。`build.py` は完全compile command、flags、compiler、
source SHA256、git commit/status、binary SHA256を `.build.json` に保存する。
runnerは成功build・binary/source hash一致・build時のclean statusを確認する。
SanitizerはASan+UBSanを同時有効化する。LSanのみ既存環境制約に合わせ無効化し、
sanitizerの時間をRelease性能比に混ぜない。
matplotlibの設定directoryが書込み不可なら、再集計コマンドの前に
`MPLCONFIGDIR=/tmp/issue4-matplotlib` を指定する。

## 保存データの独立再集計

```bash
python3 experiments/target_selection/verify_provenance.py --input experiments/target_selection/results/full
python3 experiments/target_selection/verify_provenance.py --input experiments/target_selection/results/smoke
python3 experiments/target_selection/analyze.py --input experiments/target_selection/results/full
python3 experiments/target_selection/analyze.py --input experiments/target_selection/results/smoke
```

`verify_provenance.py` はbuild・environment・manifest間のcommit/source/binary hashとclean statusを照合し、
測定commitのGit objectでsource/runner/plan/gateを検証する。後続の報告commitのHEADとは比較しない。
測定commitのGit objectがないshallow cloneでは失敗するため、そのcommitを含む履歴を取得する。
測定時のbinaryも手元にある場合は `--binary /tmp/issue4-release/validator` を追加して実bytesを照合できる。
`analyze.py` はjob metadataとraw/trace SHA256、予定jobの完備性、同一policyの全decision配列を照合する。
`raw_data.tar.gz` は `raw/`, `traces/`, `logs/` を含む。analyzerはarchiveを展開せず読める。
missing/error/timeoutを成功観測として補完せず、集計から黙って消さない。
再集計は保存済み `summary/` を生成し直すので、元を保持する場合はdatasetを別directoryへcopyする。
計時結果のbit一致は要求しないが、保存データから得る数値集計は一致する必要がある。

## 新しい測定

```bash
python3 experiments/target_selection/run.py --binary /tmp/issue4-release/validator --output /tmp/issue4-new-smoke --smoke
python3 experiments/target_selection/analyze.py --input /tmp/issue4-new-smoke
python3 experiments/target_selection/run.py --binary /tmp/issue4-release/validator --output /tmp/issue4-new-full
python3 experiments/target_selection/analyze.py --input /tmp/issue4-new-full
python3 experiments/target_selection/pack.py /tmp/issue4-new-full
```

fullは42条件×5seed×3反復×7方式＝4,410プロセス、smokeは10条件の1,050プロセス。
各方式は新プロセス、seed/反復ごとに事前seedで方式順をshuffleし、性能測定同士は並列にしない。
warmupは置かず、fresh processのallocator/cache条件を含む測定。入力生成とbuildは測定外。
既定affinityは実行環境で許可された最小CPU一つ。変更するなら `--cpus 0` などと指定し、
保存環境の `affinity_used` と照合する。排他的なCPU予約ではない。

各process timeout60秒、address space上限2GiB、全体予算3,600秒。
address-space上限とRSSを混同しない。SIGKILLの原因不明をOOMと断定しない。
budget未実行/unsupported/memory_limit/timeout/errorも `runs.jsonl` に残る。

traceは既存generatorの `EAS_TRACE_V1` bytesを使う。同一arity/n/distribution/seedは
全方式・k間で同じtraceを共有する。n=40は原論文の既定batch sizeだけを参照し、
5read/5write workloadの再現とはしない。identical系列は5seedでも同じ競合構造であり、
5種類の独立workloadとは数えない。cheap方式はkに依存しないので補助k=2での再測定を
独立した品質利得の証拠として合算しない。

## 測定区間と公平性

|項目|含むもの / 注意|
|---|---|
|`total_ms`|raw logical R/Wから、正規化・安全性/容量検査・全index/graph構築・trim・順位計算/更新・選択・round/mask/certificate構築・scratch解放までのAPI wall time。戻り値の永続decision bufferは残る。|
|paper `normalize_ms`|独自のlogical key sort/dedupとID/入力検査。EAS正規化を呼ばない。|
|paper `build_ms`|writer hash posting、read probe、相手重複/自己辺除外、前後adjacencyと次数配列の構築。素朴全pair graphだけをbaselineにしない。|
|paper `select_ms`|初期/各round trim、全順位走査、nth_element、凍結k件の出力と全削除・次数更新。paper `trim_ms=0`は個別計時しないという意味で、trimが無料ではない。|
|paper `certificate_ms`|commit ID収集と昇順sort。|
|既存EAS/cheap内訳|既存のstatsをそのまま出す。staticのcount/sort、implicit構築、adaptive switchも実費。内訳の分類はpaperと完全同一ではないので全API時間を主比較にする。|
|JSON serialization|timing後の検証とstdout JSON変換/IOは除外。配列出力そのものの構築はtotal内。|
|`peak_rss_kib`|入力parseを含むprocess高水位を、検証用set構築前に採取。selector専用allocationではない。外側`runner_peak_rss_kib`は検証・JSONまで含む別の値。|
|`graph_bytes`|paperは前後adjacency容量と主要graph配列の見積り。hash/normalization/allocator費用を全て表す値ではなく、RSSの代用ではない。EAS bitsetのpayloadとは同じ物差しでない。|
|memory budget|paper/EAS graphの既定512MiB容量上限と、process全体2GiB上限は別。大graphをimplicit側のtiming中にoracle用に作らない。|

paperのgeneric directed codeは独立oracleを検査するためにも使うが、CLIは完全RMWだけを渡す。
ID昇順certificateはこの完全RMWで合法。一般directed graphでID順が常にtopologicalだとは主張しない。
大入力ではtiming後にdisjointnessとmask/certificate整合を直接検査し、方式間の全配列比較はanalyzerで行う。

qualityは `commit_count` と `fvs_size=n-commit_count`。
`commit_count/(total_ms/1000)` は **validator処理時間あたりの残存件数**であり、
DBMS有効throughput、transaction latency、retry含む公平性ではない。
最適FVSを求めていない。exactとは指定heuristicと同じ判断を出す意味である。

各対比は同一trace・同一反復の比/差を計算し、seed内3反復中央値→5seed中央値とmin/maxを出す。
別々の中央値の商をpaired値に代用せず、15回を15独立入力と数えない。
caseごとの負け、時間揺らぎ、arity制限、zero commitもそのまま残す。
