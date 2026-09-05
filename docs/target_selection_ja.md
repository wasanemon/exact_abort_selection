# Issue #4 適用先再選定

調査 cutoff: **2026-09-05**。開始点: `codex/issue-3-policy-comparison`
(`d150211968ef6d61efda82f9f44f63e3bac28b44`)。
[保存仕様](issue_4.md)、[#3 報告](../REPORT_policy_comparison_ja.md)、
[機械可読引継ぎ](../next_stage.json)を読んでから gate を適用した。

**Ding Algorithm 2 の complete-RMW standalone 再現だけを限定 Go とする。実システムへの
EAS 移植は全候補 No-Go。** 前者は「指定した既存 heuristic を保存する実装比較」を
可能にする判定であり、実用価値が確認されたという採用判定ではない。
[事前 gate](../experiments/target_selection/gate.json)と
[実験計画](../experiments/target_selection/plan.json)を実装・測定前に保存した。

## #3 を gate へ反映する

#3 の主10条件では EAS k=1 の paired 有効処理率中央値は accept_id/native より低かった。
static に対する小さい同数の時間差と一部 seed の件数利得はあるが、自然な workload の
実測重い本体・retry 下での逆転は未確認。従って別 DBMS に EAS の品質優位を売る分岐は閉じる。
graph/adaptive の同一判断の速度比は representation の機構証拠として引き継ぐ。
原 policy の実費と保存要求がない対象に graph を追加して、その graph を消す高速化は採択しない。

## 主候補の10観点

各 cell の根拠を詳細監査へリンクする。High/Medium/Low の点数だけで順位を作らない。

|観点|Ding validator / Algorithm 2|Lantern / ChainMaker|Fabric++ / FabricSharp|
|---|---|---|---|
|実際のボトルネック|§4 の writer index→依存辺構築、§4.3/5.4 の reordering 費用。原著実行の再測定はない。|Rule 1 の DAG と Rule 3 の隣接伝播は存在する。実装固有の費用・支配率は未確認。|公開 code が辺を作る。++ は全cycle参加数、Sharp はreachabilityやcycle回避、focc-latestは動的degreeを使う。|
|意味論の一致|viable・同snapshot・R=W=Sなら対称辺、prod-degree=d²。ID降順の追加tieを共通化したAlgorithm 2とEASは一致する。|低indexへのRAW DAGで対称graphではない。BP最終maskとEASの違いは3取引反例で分かる。|一般R/W、version、複数snapshot。++のcycle-countとdegreeは異なる。focc-latestもtieが異なる。|
|policy保存の価値|既存heuristicの忠実再現は比較上有用。原著rct/rdegのtail priorityを現EASが保存するとは言えず、prod-degree固定の外部要請は未確認。|replica間の決定性は必要だが、旧policy固定の外部要請は未確認。RMWではaccepted-key走査と同じ。|有効なversion/commit順を保存する必要はある。特定のEAS中止列を使う理由は確認できない。|
|安いbaseline|accept_static_degree、accept_id/CFBSを同時評価。2キーの最大matchingは最適品質上限の別問題。|CFBSは既知account・同じ候補列/順序でaccept_id相当。一般point R/W BPにはaccepted-write unionという別の単純baselineがある。|native schedulerを基準にすべき。EASへ任意に置換するとorder/version規則が変わる。|
|アクセス数|SmallBankのdeposit/transferは動機になるが、原著microbenchmarkとCicadaは一般R/W。1–4キー合成traceを原workloadと呼ばない。|account粒度とlogical key粒度の一致が必要。YCSBとSmallBankを同一の完全RMWにしない。|公開SmallBank codeには1/2account RMWがある。一方sigmod20主workloadは4read/4writeで全batch R=Wの証拠ではない。|
|graph密度|共有hot keyでdenseになる。原著の既定batch40も含め、巨大同一集合はstressとして分離する。|共通keyならRule 1辺数はn(n−1)/2。ただしCFBS有効時には後段のdense conflictを事前に除く。|hot keyで辺/cycle費用が増えうるが、現EASへ対応する自然なbatchの密度は未測定。|
|artifact / build / license|原著Java validator/Cicada patch/DBMS-X artifactは限定探索で未特定。独立C++再現を作る。第三者focc-latestは原著artifactではない。|公式paper取得済み。Lantern固有source/patch未特定。ChainMaker本体sourceと取り違えない。|++公開source、Sharpはbranch差あり。masterのForkBase閉源依存をsigmod20へ一般化しない。Apache-2.0 codeと依存は別監査。|
|評価可能性|同一raw trace、独立directed graph、oracle、EAS4方式とcheap2方式で限定比較可能。DBMS全体評価ではない。|最終maskは疑似コードから再現可能だが今回は実装しない。ChainMaker本体性能の追試は不可。|source-level監査可能。全system setupの成功は未確認。巨大な環境再構築を成果に代用しない。|
|新規性リスク|prod-degree/FVS heuristicは既知。implicit化一般も既知。残るのは狭いexact列と資源上限の組合せ。|CFBS/accept_idを新規手法にできない。BPも単純なindex順漸化式で同じ最終maskを得られる。|既存conflict-aware reorderingとの重複が強い。新representationにもversionと一般R/Wの証明が必要。|
|実装コスト|standalone一候補の小実装で限定仮説を検査できる。原systemへのportは行わない。|VM・private writes・retry hookが不明。EAS定理のそのまま転用は不可。|schedulerごとの意味論が違い最小hookの範囲を越える。今段階で大規模portしない。|

Ding の一次資料・検索記録: [原論文](https://www.vldb.org/pvldb/vol12/p169-ding.pdf)、
[保存監査](../experiments/target_selection/sources/ding_audit.json)、[対応証明](ding_semantics_ja.md)。
Lantern: [v1 全文](https://arxiv.org/html/2609.03315v1)、[全文・artifact監査](target_audit_lantern_ja.md)。
Fabric: [公開repository](https://github.com/ooibc88/FabricSharp)、[本文・commit固定code監査](target_audit_fabric_ja.md)。

## 2020–2026 の追加候補とアルゴリズム監査

追加の詳細10観点に相当する根拠は[representation監査](target_audit_representation_ja.md)に保存した。

|候補|実費・保存対象|semantic / baseline / artifact / cost|gate|
|---|---|---|---|
|OptSmart (2021)|公開C++が明示依存辺とindegree更新を払う。minerとvalidatorのstate/order対応に価値がある。|Coinは2account形状を含むがSTMの有向replay、retry、混在read-only。per-key precedence圧縮が適切な比較。artifactの一部をcommit固定監査、全build未実行。|Needあり、現EASとのSemantic fit不足。No-Go。|
|SEA 2026 blockchain validation/construction|DAGとcritical path/volume/fan-out優先度。元の実装は既にkey postingを使い、素朴全pair比較だけをbaselineにできない。|一般R/W、Ethereum入力は固定arity保証なし。MATLAB/gas時間simulation、CSV未同梱、GPL-3.0。priority保存には別証明が必要。|exact scheduler再現の仮説はあるがengine費用/現EAS適合不足。No-Go。|
|Stable Scheduling in Transactional Memory (2022/2023)|arrival順の採用集合走査と安定性理論。graphの理論上の利用と物理materializationを分ける。|固定roundではaccept_id/CFBS型。理論のgraphを実装が全保存すると推測しない。到着順のfairnessはEAS最大次数と別。|実systemのNeed不足。No-Go。|
|Fabric-X (2026)|fixed-order validationの依存graphを持つ公開committer。|既定order/validity保存は具体的だがEAS中止選択とは別。一般R/Wと依存schedulingの証明が必要。|現EASのSemantic fit不足。No-Go。|

Dynamic Set Intersection、heavy/light IVM、Veldt の implicit conflict-graph Vertex Cover、
dynamic hypergraph matching の本文を確認した。既知の構造を列挙するだけで新規性を認定しない。
今回の exact 最大残存次数・ID・frozen top-k の全列と資源上限の命題全体が直接 subsume
される資料はこの探索では未確認だが、それは不存在の証明ではない。
[各定理・section・取得物の索引](target_audit_representation_ja.md)。

## Gate と選定理由

1. **Semantic fit**: Ding の限定問題だけは現 EAS と一致する証明がある。他候補の
   一般R/W・有向DAG・cycle数・version規則へ暗黙に広げない。
2. **Need**: Ding は原論文が構築とreordering費用を実際に報告する。
   ただし取得していない原artifactの現在の費用を推測しない。
3. **Policy value**: #3から品質優位は採択できない。Issue #4のDing例外に従い、
   published policy reproductionとして限定評価する。運用上このheuristicを固定すべき理由は未確定。
4. **Baseline relevance**: CFBS相当accept_idと強いstaticを含めて差を検査する。
5. **Evaluability**: 原著systemを名乗らず、独立paper-faithful standaloneで検査する。

このため順位は **Ding限定再現 → Lanternの別問題仮説 → Fabric系**。
追加候補はこの限定再現を置き換えるだけの適合証拠を得ていない。
実験の結果で採用価値が否定的でも、policyを変えたりtargetを追加して勝ちを探さない。
測定結果・最終7問への回答は[最終報告](../REPORT_target_selection_ja.md)、
次の研究へ進む条件は[NO_GO](../NO_GO.md)にまとめる。
