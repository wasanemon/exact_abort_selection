# EAS と prior art の同じ部分・違う部分

Cutoff 2026-09-05。#3 の測定結果を読んだ上での重複監査。
「新規性未確認」と「既知手法による直接包含」を区別する。

|対象|同じ部分|違う部分 / 今回主張しないこと|
|---|---|---|
|Ding Algorithm 2 / prod-degree|complete-RMWではdegree²の順位がdegree順位と同じ。frozen k候補→削除→trimという制御。|一般有向R/WのFVS、rct/rdeg、thread-aware assignmentは現EASの範囲外。ID降順tieと出力列は今回の追加規約。|
|EAS graph/lazy/profile/adaptive|既存4実装は同じabort round列・mask・certificateを保存する。|graphより速いことはnative/cheap policyより価値があることを意味しない。|
|#3 accept_id / Lantern CFBS|既知完全RMW、同じ候補列・順序・交差粒度なら採用済み集合との非交差走査が同値。|CFBSは実行前pending全列、#3は実行後batch。実行費用・batch充填・retryは同じでない。新policyと呼べない。|
|#3 accept_static_degree|初期distinct degreeを一度計算して固定順位のdisjoint acceptance。|残存次数の動的再評価・frozen top-k中止はしない。#3で強かったcheap baselineとして必須。|
|Lantern Back-Propagation|RMWに限る最終red集合はaccept_idと同じ。|一般point R/Wでは低index writerへの有向RAW。最終maskのaccepted-write union漸化式は別の導出であり、EAS定理でも伝播層保存でもない。|
|Fabric++|R/W交差からgraph、invalid取引を減らす目的。|cycle列挙とcycle参加数による削除。degree heuristicsと等価ではない。|
|FabricSharp|reorderingと依存を実codeで扱う。第三者focc-latestのsum-degreeは対称RMW上でprod-degreeと同順位。|Sharp本体はmulti-version/reachability。focc-latestの同点は先着側で現EASと逆。原著Ding artifactではない。|
|OptSmart / Fabric-X|実依存辺を避けるrepresentation変更に工学上の動機がある。|commit済みSTM replayまたはfixed-order validityという別contract。任意取引をEASで中止すると問題を変える。|
|SEA 2026|DAGとdegree関連のpriority、ready集合を扱う。|artifactは既にpostingで辺を生成する。critical-path/再帰volume/IDを保存するには別証明。gas simulationをengine速度としない。|
|Dynamic Set Intersection / heavy-light IVM|交差照会、頻度分割、更新と空間のtrade-offは既知。|distinct残存neighbor数の全体argmax、profile共有加数、全frozen列の同一性は別のquery contract。直接包含は今回未確認。|
|Veldt 2023|hypergraph incidenceからconflict graphを形成せず既存Vertex Cover系を実装する先例。|近似解・任意/乱択順であり指定最大degree列の保存ではない。implicit化一般という広い新規性を否定する。|
|Hypergraph maximal matching / set packing|disjoint採用集合の問題そのもの。2キーはキー頂点・取引辺のmatching。|maximumとmaximal、品質最適化と特定heuristicの再現は異なる。EASがmatchingより高品質とは言えない。|

根拠: [Ding対応証明と原論文位置](ding_semantics_ja.md)、
[Lantern全文監査・CFBS/BPの独立導出](target_audit_lantern_ja.md)、
[Fabric本文とcommit固定source](target_audit_fabric_ja.md)、
[アルゴリズムと追加systems一次資料](target_audit_representation_ja.md)。
source URL、取得失敗、検索query、hashは `experiments/target_selection/sources/` に保存している。

残る最小命題は、**complete point-RMW・固定小arityで、指定したdegree/ID/frozen-kの
全判断を保つimplicit実装の資源上限**。これは品質の新policy提案ではない。
その厳密な列を維持する実用要求と自然なworkloadでの費用削減がなければ、
この命題だけで主要systems会議への強い実証になったとは結論しない。
