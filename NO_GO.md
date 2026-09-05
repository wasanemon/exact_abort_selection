# 実システムへの EAS 採用は現時点で No-Go

対象: [Issue #4](docs/issue_4.md)。調査 cutoff は2026-09-05。
これは研究を必ず継続すべきという提案ではなく、現証拠で実システム移植を進めない判断である。
**Ding の忠実な standalone 機構検査だけは限定 Go** とした。
その計測結果が良くても、以下の運用上の欠落を埋めたことにはならない。
[候補表](docs/target_selection_ja.md)、[事前gate](experiments/target_selection/gate.json)、
[実証結果](REPORT_target_selection_ja.md)を参照。

|対象|進めない理由|再開に必要な証拠|
|---|---|---|
|Ariaから別DBMSへのEAS policy移植|#3でcheap policyへの実用的優位が弱い。nativeは元々EAS graphを払わない。|自然な入力でstatic/accept_idを超える品質と本体/retry込み有効率、または既存policyを保持する明示要請。|
|Ding原著system|Algorithm 2の限定subsetは合うが、原著artifact未特定。一般R/Wとrct/rdeg/Cicada thread policyを現EASは保存しない。|原artifactまたは実運用hook、同snapshot complete-RMW割合、graph/selection内訳とend-to-end、外部priority契約。|
|Lantern|完全RMWはCFBS/accept_idと重複。BPは有向RAWの別policy。固有artifact未特定。|まず一般point R/Wの最終mask保存という別問題に固定し、native BP実装と安価なaccepted-write unionを比較。CFBS後も費用が残る証拠。|
|Fabric++ / Sharp|graphは実在するが、cycle参加数・multi-version reachability・到着時判定の意味論が違う。|保存する実decisionを固定し、その表現変更の独立証明とoracle。branch固有依存を分けた最小hook。|
|Focc-latest|近い第三者実装だがsum-degree/先着tie。自然RMW部分はあっても全batchの適合・必要性は未確認。|policy/tieを含む完全対応、実際のsubset比率、cheap policyを加えたscheduler全費用。|
|OptSmart / Fabric-X|実replay/fixed-order validationに保存価値があるが、最大次数中止とは違う。|point-keyの前後依存表現が同じ合法順序/validity/stateを保存する別証明と実機内訳。|
|SEA 2026|公開codeは既にposting索引を持つ。simulationであり実engineではない。priorityも別。|同じnative codeを基準にしたpriority保存、配布可能trace、実engineでrepresentationが支配する証拠。|
|STM理論scheduler|到着順のcheap acceptanceが既にあり、graph materializationの実費を確認できない。|実runtimeの実装とprofile。理論上のconflict graphの存在だけでは足りない。|

ForkBaseの閉源依存はFabricSharp **master** の減点であり、公開sigmod20 branchまで
一律実行不能とした理由ではない。artifact未発見も不存在の証明ではない。
個々の一次資料・commit・取得失敗は[監査資料](docs/target_selection_ja.md)に残した。

## Pivot を検討するなら

1. **既存の directed point-R/W validator の最終判断を保存する表現。**
   Lantern BPの最終red集合は、低indexの採用済みwriteのunionとのread交差という
   漸化式に帰着するという[独立導出](docs/target_audit_lantern_ja.md)がある。
   まずこれを最小baselineにする。BP層の保存、range、dynamic access discovery、retryを
   暗黙に含めない。単純走査で十分なら、その負の新規性結論を受け入れる。
2. **実在する priority / precedence contract を保つ representation。**
   OptSmart/Fabric-Xのstate/order保存、Ding rdegの重み付き順位などのどれか一つを
   固定する。現在のEASに似ているというだけで選ばず、費用の計測と要請確認を先に置く。
   graphをtransitive reductionするとfan-out/volume等が変わり得るため、保存対象を明文化する。
3. **品質最適化が本当に目的なら matching / set packing と比較する。**
   2キーでは最大matching、一般固定rankではhypergraph packingが自然な問題。
   greedy中止policyの再現と最適品質は別である。#3の人工反例だけでEASの実用優位を主張しない。
4. **理論の限定命題として整理する。**
   fixed-small-arity、exact degree/ID/frozen-k列、線形空間、全削除時間という
   組合せを既知dynamic intersection/heavy-light/implicit Vertex Coverと厳密に比較する。
   未発見を新規性認定にせず、実systemの裏付けが弱いままsystems成果へ拡大しない。

現時点の最も強い筋は、特定の既存decisionを明示した上でのrepresentation研究である。
**主要DB/systems国際会議向けに、EASが実システムを有意に改善するという主張はまだ弱い。**
無理な別system移植を追加してその不足を隠さない。
