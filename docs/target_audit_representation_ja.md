# Implicit conflict representation の追加一次資料監査

調査日・cutoff: 2026-09-05。Issue #4 の追加探索担当による限定的監査。
先に [#3 報告](../REPORT_policy_comparison_ja.md)、[next_stage.json](../next_stage.json)、
[EAS 設計](eas_design.md)、[理論](eas_theory.md) を読んだ。
#3 の「graph より速い」と「安価な policy より有利」は別の結果として扱う。
この文書だけで主要候補 Ding / Lantern / Fabric の総合 gate を決めない。

検索語・検索結果は [検索ログ](../experiments/target_selection/sources/representation_search_log.json)、
取得 URL・SHA256・失敗は [取得 manifest](../experiments/target_selection/sources/representation_download_manifest.json) に保存。
PDF、ページ区切り付き抽出本文、cutoff 前 GitHub commit/tree と該当 code を
`experiments/target_selection/sources/representation_*` に保存した。code は読取りのみで実行していない。
検索エンジンが示す crawl 相対日付は公開日の根拠にせず、論文と commit の日付を用いた。
網羅的な不存在証明・新規性認定ではない。

## 結論

**この追加探索から大規模統合へ Go とする候補はない。**
OptSmart は実際に明示 graph と動的 indegree 更新を払う公開 CPU 実装だが、
維持する意味論が STM の有向依存 replay であり EAS の対称 RMW 最大次数中止とは違う。
SEA 2026 は deterministic schedule の忠実再現候補だが、公開 artifact は
gas 時間を使う MATLAB simulation で、実システムの EVM 実行ではない。
既存 policy の優先順位を保持したまま表現だけを変える研究仮説は残るが、
EAS の現在の定理をそのまま適用できる証拠は得ていない。

「graph を明示化しない」「heavy/light に分ける」「小さい集合を扱う」
それぞれは既知の技法である。最も狭く残る候補命題は、完全 RMW・固定 arity での
**指定済み最大残存次数・ID 順・frozen top-k・全中止列を保存し、
構築を含む線形空間と劣二次の全削除時間を同時保証すること**である。
以下の論文がその命題全体を直接 subsume するとは確認できなかったが、
未発見を新規性の証明としない。

## 1. アルゴリズム先行研究と重複

|一次資料と本文 anchor|確認した既知結果|EAS との関係・取り違えない点|
|---|---|---|
|Kopelowitz–Pettie–Porat, **Dynamic Set Intersection**, WADS 2015。保存版は [arXiv v2, 2015-05-05](https://arxiv.org/pdf/1407.6755v2#page=1)、pp.1–3、§1。|動的集合族で emptiness / witness / reporting を扱い、word-RAM・線形空間・更新/照会の trade-off を示す。|EAS の隣接判定は既知の集合交差問題。ただし一組の intersection query と、全生存取引の重複を除いた隣接数を動的に最大化する操作は異なる。この資料だけから EAS の全 top-k 中止列の同じ上限を導かない。著者サイト PDF は TLS 検証失敗で、arXiv に切替えた。arXiv abstract と本文の更新時間表記にも差があるため、その数値を混ぜて優劣を主張しない。|
|Kara et al., **Maintaining Triangle Queries under Updates**, TODS 2020。[本文](https://arxiv.org/pdf/2004.03716v1#page=7)、§2.2 Definitions 7–8、§2.3、§3、§7。|頻度による heavy/light partition、部分ごとの補助 view、更新費用・空間・出力 delay の trade-off、再分類を明示する。|heavy/light で更新を分ける発想自体は新規でない。triangle join の乗法的 multiplicity と、EAS の inclusion–exclusion による distinct 隣人数・profile 共通加数・全体 argmax は別 query。固定削除列の EAS bound をこの論文の triangle bound と同一視しない。|
|Veldt, **Optimal LP Rounding and Linear-Time Approximation Algorithms for Clustering Edge-Colored Hypergraphs**, ICML 2023。[本文](https://proceedings.mlr.press/v202/veldt23a/veldt23a.pdf#page=7)、§5.1–5.2、Theorem 5.3、Appendix E。|hyperedge を conflict graph の頂点にする Vertex Cover 帰着を示し、その graph を形成せず既存 Vertex Cover 手法の variant を incidence 線形時間で実装する。|「衝突 graph を作らず既存アルゴリズムを速くする」広い主張を先取りする強い一次資料。PittColoring / MatchColoring は approximation と任意順・乱択を使い、EAS の最大 degree＋ID の全列を保存するものではない。implicit という名称だけを研究差にできない。|
|Assadi–Solomon, **Fully Dynamic Set Cover via Hypergraph Maximal Matching**, ESA 2021。[本文](https://drops.dagstuhl.de/storage/00lipics/lipics-vol204-esa2021/LIPIcs.ESA.2021.8/LIPIcs.ESA.2021.8.pdf#page=3)、pp.8:3–8:4、§2 Fact 1、§3。|rank-r hypergraph の maximal matching を hyperedge 挿入削除下で O(r²) expected amortized update time で保つ乱択手法を示す。|完全 RMW の disjoint commit set は hypergraph matching、2キーは multigraph matching として扱える。単に安全な極大集合が欲しい用途では強い代替 baseline。maximum cardinality、決定論的 exact EAS、frozen top-k の保存ではない。EAS の方が一般に高品質だと仮定しない。|

補助探索で [Blelloch–Brady 2025](https://arxiv.org/abs/2503.09908) の parallel
batch-dynamic maximal matching、[ALENEX 2026 の indexed-set intersection](https://epubs.siam.org/doi/10.1137/1.9781611978957)
も見つけた。今回は abstract screening に留め、定理本文・実装の検証済み主資料には数えない。
2025–2026 の matching/intersection 分野が止まっているとは扱わない。

## 2. OptSmart: graph を実際に払うが、EAS と異なる replay

一次資料: Anjana et al., **OptSmart: A Space Efficient Optimistic Concurrent Execution of
Smart Contracts**, 2021 preprint。[本文](https://arxiv.org/pdf/2102.04875#page=14) §4.1、
Algorithms 2–6 (pp.16–17)、§4.3–4.4。
[著者 repository](https://github.com/Parwatsingh/OptSmart/tree/0564abdd04e7bc37a3586982a1d7ca5a97be88d5)
の cutoff 前先頭 commit は `0564abdd04e7bc37a3586982a1d7ca5a97be88d5`
(2020-10-08)。論文版と code 版の厳密な一致は未検証。

|観点|コード・意味論の証拠と判定|
|---|---|
|実際の費用|[Graph.cpp L65](https://github.com/Parwatsingh/OptSmart/blob/0564abdd04e7bc37a3586982a1d7ca5a97be88d5/1.Coin/BTO-STM/Graph/Lockfree/Graph.cpp#L65) の add_edge が linked adjacency の重複検査、allocation、atomic in_count 増加を行う。[default-main.cpp L211](https://github.com/Parwatsingh/OptSmart/blob/0564abdd04e7bc37a3586982a1d7ca5a97be88d5/1.Coin/BTO-STM/default-main.cpp#L211) が conf_list の全相手から graph を作り、L333 以降で zero-indegree claim と successor count 減少を行う。graph 存在は確認、end-to-end 支配率は今回未測定。|
|Semantic fit|timestamp 順に方向を持つ STM 依存 graph を validator が replay する。安全な有向 replay と対称 complete-RMW 中止選択は一致しない。EAS の最大 degree / frozen k は呼ばれていない。|
|policy 保存の価値|miner's STM execution と整合する final state / conflict order を validator が再現する必要はある。しかし thread interleaving や「特定最大 degree 中止列」の保存要件ではない。|
|安い baseline|key 別 last-writer / readers、同等な順序制約の圧縮表現、元の zero-indegree scheduler を比較対象とすべき。accept_id で任意取引を捨てれば、block replay の task を変更してしまう。|
|小さい access set|Coin の [send_m L147–187](https://github.com/Parwatsingh/OptSmart/blob/0564abdd04e7bc37a3586982a1d7ca5a97be88d5/1.Coin/BTO-STM/Contract/Coin.cpp#L147) は sender/receiver を読み書きする2 account形状。get_bal は read-only、失敗/STM retry もあり、全 workload を同 snapshot R=W とみなせない。|
|密度|hot account で依存が増える可能性は自然だが、その同一入力の辺密度・費用分解を今回は測っていない。|
|artifact / 評価|C++ STM と Coin/Ballot/Auction/Mix の source を公開。特定 module だけを読んだ。全 build、安全性、依存・license 全体の確認は未実施。production Ethereum client と呼ばない。|
|新規性 / cost|依存 replay の compressed representation には別の証明・hook が必要。既存 EAS selector を差すだけでは済まない。|

Gate: Need の実在は満たす。Semantic fit は現状満たさず、Policy value は
state/order 保存についてのみある。**EAS 移植は No-Go**。
より弱い「同じ合法 replay の集合」を表現する問題へ pivot する余地はある。

## 3. SEA 2026: exact scheduler reproduction の候補、実 engine ではない

Karmegam–Kiffer–Fernández Anta, **Exploiting Multi-Core Parallelism in Blockchain Validation and
Construction**, SEA 2026。[本文 §2–§3](https://drops.dagstuhl.de/storage/00lipics/lipics-vol371-sea2026/html/LIPIcs.SEA.2026.23/LIPIcs.SEA.2026.23.html#S3)
および Appendix C Algorithms 4–7、§5–§7。
[公開 artifact](https://github.com/arivarasanka/blockchain_parallel_validation/tree/7c070ef20e9fdd1cfeeeac460cf81cfc8af6ada7)、
commit `7c070ef20e9fdd1cfeeeac460cf81cfc8af6ada7` (2025-10-28)。

|観点|本文と artifact の証拠と判定|
|---|---|
|実際の費用|論文 Algorithm 4 は pair 比較 O(n²)、DAG priority 計算 O(n+E)、完了時の successor indegree 更新。**公開 code は既に key posting を使う**。[Heuristics_P1_complex.m L100–159](https://github.com/arivarasanka/blockchain_parallel_validation/blob/7c070ef20e9fdd1cfeeeac460cf81cfc8af6ada7/simple%20and%20complex/Heuristics_P1_complex.m#L100) が writers/readers を索引化し WW/WR pair を列挙、unique で重複を除く。全 pair の素朴版だけを baseline にすると code の既存最適化を無視する。|
|Semantic fit|一般 R/W で ordered DAG を作り、priority は critical path、再帰 volume、fan-out、ID。動的 indegree は ready 判定であり最大次数中止ではない。code L203–221 の volume は merge を重複計数すると明記。exact reproduction ではその演算まで固定が必要。|
|policy 保存の価値|既定 order と等価な実行は blockchain correctness に必要。特定 heuristic priority の選択順保持は再現比較には有用だが、その priority 自体を protocol が要求する証拠はない。|
|安い baseline|論文の Solana-inspired declared-access baseline と reward-greedy を尊重。per-key frontier による precedence 圧縮も比較候補。ただし transitive edges を消すだけでは再帰 volume / fan-out が変わるので exact priority 保存とはならない。|
|access / 密度|論文 §2 は transfer の few keys と contract の many keys を区別。Ethereum trace があることだけでは fixed ell を保証しない。配布 trace がないので実 arity/density は今回独立に確認できない。|
|artifact / 評価|MATLAB R2025b、Optimization Toolbox / intlinprog。GPL-3.0。README は入力 Ethereum CSV を同梱しないと明記。code は gas_used を実行時間として event simulation するもので、EVM/client を実行しない。|
|実装 cost|directed reachability / critical path / weighted duplicate volume の表現を新たに扱う必要。EAS 定理の適用ではなく別のアルゴリズム研究。|

Gate: graph/degree 費用は code に存在するが、実 engine 上の支配費用は不明。
Semantic fit と practical policy value が不足。**EAS 統合は No-Go**。
追試するとしても paper/artifact-faithful scheduler simulation とラベルを固定する。

## 4. STM/runtime: conflict graph を使う理論と、物理的費用は分ける

Busch–Chlebus–Kowalski–Poudel, **Stable Scheduling in Transactional Memory**,
2022 preprint (CIAC 2023)。[本文](https://arxiv.org/pdf/2208.07359v1#page=9)
§4、Figure 1、Lemma 2。arrival 順に pending transaction を走査し、既に選んだ
Execute と交差しないものだけ採用する中央 scheduler を記載する。
生成順を ID とする固定 round では、accept_id / CFBS と同じ型の採用方式である。
queue の安定性を証明するための conflict graph と、その辺を実際に全保存する
実装は別である。この論文から production runtime の dynamic max-degree
費用は確認できず、max-degree を導入する理由にはならない。
安い既存 greedy policy に fairness / arrival-order の意味がある例として扱う。

## 5. Gate への引継ぎ

追加候補の順位は OptSmart（実コードの費用点あり）、SEA 2026（再現可能な
scheduler 算法あり）、Stable Scheduling（理論 baseline）とする。
いずれも Ding の complete-RMW 上の paper-faithful exact preservation より
Semantic fit が弱い。主要候補担当が Ding に限定した実証を選ぶ場合でも、
その結論を「implicit graph 全般の新規性」「別 system 全体の高速化」
「cheap policy に対する優位」へ拡大しない。

本監査で残す研究条件は、(1) 忠実な native representation baseline、
(2) 保存する observable decision の明文化、(3) 自然な small-access trace、
(4) graph/index 構築を含む費用計測、(5) 安い合法 policy との品質/実効率比較である。
これらを満たさない graph toy benchmark だけで次の systems target を採択しない。

