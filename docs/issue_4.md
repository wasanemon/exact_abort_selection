# Issue #4 保存仕様

取得日: 2026-09-05
URL: https://github.com/wasanemon/exact_abort_selection/issues/4
開始点: `d150211968ef6d61efda82f9f44f63e3bac28b44`

## 開始条件

**Issue #3 の実装・実験・`REPORT_policy_comparison_ja.md`・`next_stage.json`が完成してから開始すること。** #3の結果を読まずに新しいDBMS/ブロックチェーンへ移植しない。#3が未完了なら、このIssueを実装完了扱いにしない。

このIssueの目的は、EASを「どこかへ無理に適用する」ことではない。**EASが解いている正確な中止選択、またはその中核となるimplicit conflict representationが、実際に価値を持つsystems researchの対象を再選定すること**である。適切な対象が見つからなければ、その負の結論を証拠付きで出すことを正しい完了とする。

## 1. 背景として固定する事実

前回のAria統合（Issue #1 / PR #2）では、同じEAS policyを明示bitset graphで計算する方式に対してimplicit/adaptive selectorが大幅に速くなる条件を確認した。一方、native Ariaは元々このgraph policyを使わずreservationで安く判定するため、EASは今回の統合条件でnative Ariaよりバッチ全体が遅かった。したがって「graph版に勝つこと」と「対象systemを高速化すること」を分離する。

#3ではさらに、安価な`accept_id`、`accept_static_degree`等とEASの品質・時間を同じ実行基盤で比較する。その結果を、本Issueのgo/no-go判定へ使う。

## 2. まず行う先行研究・実装監査

2026-09-05時点の最新情報まで検索し、論文本文・公開code/artifactを確認する。検索結果の要約だけでなく、主張する箇所の一次資料を保存/引用する。最低限、以下を確認する。

### A. Ding, Kot, Gehrke: Validator Batching / GreedySortGraph

- PVLDB 2018/2019 “Improving Optimistic Concurrency Control Through Transaction Batching and Operation Reordering”
- https://www.vldb.org/pvldb/vol12/p169-ding.pdf
- 同論文はIBVRでtransaction dependency graphを構築し、Algorithm 2 `GreedySortGraph(G,P,k)`を実行する。本文ではgraph構築を `O(|B|^2+|R|+|W|)` としている。
- prod-degree等、EASで固定したpolicyが本文のどの定義と一致し、どこを本Issue側で追加定義（tie-break等）しているか再確認する。
- 公開artifact/sourceが現在取得可能か検索する。見つからなければ「原著systemを高速化した」とは呼ばず、paper-faithful validator reproductionとする。

### B. Lantern（2026-09-03）

- arXiv:2609.03315 “Lantern: Finding Committable Transactions via Back-Propagation on DAGs”
- https://arxiv.org/abs/2609.03315
- 本文全体を読む。特にDAG構築、Back-Propagation、Section III-G CFBS、YCSB/SmallBank評価、ChainMaker統合を確認する。
- **重要：CFBSはpending transactionをindex昇順に走査し、既に選択したtransactionが占有するaccountと重ならないものだけをbatchへ入れる。アクセスaccountが事前に分かるRMWでは、#3の`accept_id`と非常に近い。** この近接を必ず比較し、`accept_id`を新規手法として扱わない。
- Lanternの公開実装/ChainMaker patch/artifactがあるか検索し、なければ論文の疑似コードを実装したものと明記する。
- Lanternは低indexへのRAWのみでDAGを作るため、今回の対称complete-RMW graphと同じ問題だと仮定しない。EASをそのまま当てはめる前に意味論を証明する。

### C. Fabric系transaction reordering

最低限、Fabric++、FabricSharp（SIGMOD 2020 “A Transactional Perspective on Execute-Order-Validate Blockchains”）、関連するexecute-order-validateのreordering/invalid-transaction削減手法を確認する。

- FabricSharp: https://github.com/ooibc88/FabricSharp
- 論文: https://arxiv.org/abs/2003.10064
- 実装可能性、依存（ForkBase等）、transaction RW-setが得られる時点、conflict graphを本当にmaterializeする箇所、既存schedulerの計算費用を確認する。
- セットアップが閉源依存等で重い場合、それ自体を候補の減点要因にする。無理に完全システムを動かさない。

### D. 追加の最新探索

2020–2026を中心に、次の語を組み合わせて調査する：

`transaction conflict graph`, `dependency graph`, `feedback vertex set`, `validator batching`, `transaction reordering`, `conflict-free batch selection`, `implicit graph`, `dynamic set intersection`, `read-write set batching`, `deterministic transaction execution`, `blockchain parallel execution`, `RMW`, `set packing`, `matching`。

database、blockchain、STM/runtimeを分野横断で見る。アルゴリズム論文についても、dynamic set intersection / set intersection graph / heavy-light等に今回の構造と同等またはより一般的な既知結果がないか確認する。

## 3. 候補評価表

`docs/target_selection_ja.md`を作り、候補ごとに少なくとも以下を埋める。

|観点|確認内容|
|---|---|
|実際のボトルネック|transaction-pair graph/edge列挙、degree更新、FVS/selection等を本当に行うか|
|意味論の一致|今回のEASの `R=W=S`、fixed arity、同snapshot、prod-degree、frozen top-kとどこまで一致するか|
|policy保存の価値|同じdecisionを保つ必要がある理由（品質、priority、tail latency、determinism等）があるか|
|安いbaseline|#3のaccept系、CFBS、static priority、matching/set-packing等で代替できないか|
|アクセス数|transactionあたりのpoint key/account数が小さいことが現実的か|
|graph密度|EASのimplicit representationが効きうる条件が自然に生じるか|
|artifact|公開source、build可能性、依存、ライセンス|
|評価可能性|YCSB/SmallBank/TPC-C等、既存baselineを公平に再現できるか|
|新規性リスク|既存手法にsubsumedされる可能性|
|実装コスト|最小hookで済むか、大規模portが必要か|

各項目はHigh/Medium/Lowだけで済ませず根拠を記載する。

## 4. Go / No-Go gate

候補を実装対象にしてよいのは、次を満たす場合のみ。

1. **Semantic fit**：今回の証明済み問題がそのsystemのsubproblemとして厳密に現れる、または必要な拡張を明確に定義・証明できる。一般R/Wへ暗黙に拡張しない。
2. **Need**：対象が実際にgraph materialization / dynamic selection等の高い費用を払っている。単に「graphという言葉が出てくる」だけでは不可。
3. **Policy value**：#3で安価なpolicyに対する明確な品質上の利点がある、または対象system側に「このpolicy/priorityを保存する」固有の要請がある。
4. **Baseline relevance**：Lantern CFBS等の最近の単純baselineを含めても研究上の差が残る。
5. **Evaluability**：公開artifactまたは忠実な最小再現で、主張を検査可能。

1と2は必須。3–5のうち重大な欠落がある場合は大規模統合をしない。

### #3の結果による分岐

- #3で`accept_static_degree`/`accept_id`がEASと同等以上のcommit品質かつ大幅に安い場合：**EAS policyそのものを売りにした別DBMS移植は原則No-Go**。ただしDing等で「既存policyをそのまま再現する高速化」が明確な対象なら、その限定的価値を検証してよい。
- #3でEASが特定の自然な条件で安価なpolicyより明確に多くcommitし、有効処理率の逆転が現実的なtransaction costで起こる場合：その条件が自然に存在する候補を優先する。
- どの候補もgateを通らない場合：無理にsystemを選ばず、`NO_GO.md`に根拠と、研究をどのproblemへpivotすべきかを書く。

## 5. 現時点での候補優先順位（固定結論ではない）

**第一候補：Ding et al.のvalidator batching / GreedySortGraph系。** 理由は、対象論文が実際にdependency graphを構築し、その上で今回の元になったgreedy selectionを走らせるため、Ariaと異なり「同じpolicyをgraphなしで再現する」こと自体に直接の意味がある。公開artifactの有無と、complete-RMWに限定したとき単純policyで十分でないかが最大のgate。

**第二候補：Lantern / ChainMaker。** 2026年の非常に近い最新研究なので、適用先候補であると同時に**新規性・baseline上の最大の脅威**として扱う。LanternのCFBSはRMW既知accountで単純なconflict-free selectionを既に提案しているため、まず重複を潰す。LanternのDAG構築やBack-Propagationをimplicit representationで高速化できる可能性は別仮説として評価するが、EASの定理をそのまま転用しない。

**第三候補：FabricSharp/Fabric++系。** conflict-aware reorderingとの問題相性はあるが、artifact依存や一般R/W semanticsの差が大きい可能性があるため、上2候補より先に大規模実装しない。

調査結果がこの順位を覆すなら、根拠を示して変更してよい。

## 6. 最有力候補で行う「最小実証」

Gateを通った**一候補だけ**で行う。最初から複数systemへportしない。

### 6.1 Ding系が選ばれた場合

原論文のAlgorithm 2 / prod-degreeを独立にpaper-faithful実装する。artifactがなければその事実を記載する。

- baseline A：明示dependency graph + paper-faithful GreedySortGraph。
- baseline B：同じpolicyを現在のEAS graph/lazy/profile/adaptiveで計算。ただし**意味論が一致するcomplete-RMW fixed-arity subsetに限定**。
- baseline C：#3で強かった安価な別policy（accept_static_degree等）。
- 小入力では全相手交差のoracleとdecisionを照合する。
- `k=1`を主、paperで推奨/評価されたkが確認できる場合だけ補助。
- point-RMW traceで1/2/3/4キー、batch sizeを振る。実際の論文workloadから意味のあるRMW形状を再現できるなら追加する。
- graph construction + selection全体、commit count/FVS size、peak memoryを測る。EASがgraph版より速くてもcheap policyに品質/有効率で負けるならそのまま報告する。
- 「原論文のDBMSを高速化した」と主張するには原artifact上のend-to-end測定が必要。paper-faithful standalone validatorだけならその範囲に限定する。

### 6.2 Lanternが選ばれた場合

まずpaperのRule/Algorithmを独立実装/既存artifactから確認する。CFBSと#3 `accept_id`の同等条件を形式的に書く。

EASをそのまま移植せず、対象subproblemを一つに固定する。例：fixed-small-RW-setでのDAG construction、zero-out-degree判定、Back-Propagationに必要な隣接情報のimplicit化等。**選んだsubproblemについて、明示graphと同一decisionを出すことをoracleで確認してから性能を測る。** 新しい理論が必要なら、証明なしに既存EAS定理の成果として扱わない。

### 6.3 Fabric系が選ばれた場合

公開artifactでscheduler/validationが再現できる場合だけ進む。closed dependencyのため実行不能なら、無理な環境再構築を研究成果にしない。実際にschedulerがmaterializeするgraphとtransaction RW semanticsを確認し、今回のcomplete-RMW subproblemが自然に存在する場合のみ最小hookを入れる。

## 7. 実験品質

- 同一traceを全比較方式に使用し、入力hashを保存。
- 計画、seed、反復、timeout/RSS予算を実行前に保存。
- 少なくとも5 input seed、性能は各seed複数反復。入力差と測定揺らぎを分離。
- compiler/flags/CPU/affinity/RAM/OS/commit SHA/完全コマンドを保存。
- build/setup/入力生成は測定時間から分離。graph構築、implicit index構築、selection、decision出力のどこを含むか明記。
- 大きな明示graphをimplicit側の検証のため測定区間内に作らない。
- timeout/OOM/unsupported/負けた条件を残す。
- ASan/UBSan、独立oracle、小入力の反例探索を実行。
- 性能比だけでなく、decision同一性、commit/FVS品質、メモリ、適用可能arityを出す。

## 8. 成果物

- `docs/target_selection_ja.md`：先行研究/候補比較表、最新Lanternを含む重複監査。
- `docs/prior_art_overlap.md`：今回のEAS、#3 cheap baselines、Ding、Lantern CFBS/Back-Propagation、Fabric系の「同じ部分/違う部分」を明示。
- `experiments/target_selection/`：最有力候補の最小実証（gate通過時のみ）、計画、生データ、script、集計、環境。
- `REPORT_target_selection_ja.md`：なぜその対象を選んだ/選ばなかったか、何が実証されたか、何はまだ主張できないか。
- gate不通過なら `NO_GO.md`：対象ごとの失敗理由と、次に研究すべきproblem候補。負の結果でも完了。
- clean checkoutから調査成果・prototypeを再検査する手順。

## 9. 最終判断に必ず答える質問

1. Ariaで負けた原因はtarget mismatchであり、別対象では消えるのか。それともEAS policy自体の費用対効果の問題か。
2. exact policy preservationに価値を置く実システムはどれか。
3. そのsystemの自然なworkloadでfixed-small-access-setという条件は成立するか。
4. #3のcheap baselines、特にLantern CFBS相当の方式を入れてもEASの利点は残るか。
5. 改善の本体は「EAS selector」なのか、「conflict graphをmaterializeしないrepresentation」なのか。
6. 今回の定理がそのまま適用できる範囲と、新しい理論が必要な範囲はどこか。
7. 現時点の証拠で、主要DB/systems国際会議へ向けて最も強い研究ストーリーは何か。弱ければ弱いと結論する。

実装や候補列挙だけで終了しない。逆に、gateを通らない対象へ大規模移植して時間を使わない。証拠が否定的ならNo-Goを最終成果としてよい。変更は別branch/PRにまとめ、自動mergeしない。
