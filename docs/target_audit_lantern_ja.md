# Lantern / ChainMaker 候補監査

監査日: 2026-09-05。開始前に `REPORT_policy_comparison_ja.md` と `next_stage.json` を読んだ。
#3 の軽い完全 RMW では安価な policy に対する EAS の実用上の優位は支持されない。
したがって、以下では EAS の移植を推奨せず、同一の判断を保持する表現変更の可能性を分ける。

**判定: EAS の直接移植は No-Go。Lantern の本格統合も現時点では No-Go。**
任意の point R/W に対する Back-Propagation の最終採用集合を graph なしで得る仮説は
形式的に定義できるが、実システム上の費用削減は未測定である。
本監査では Lantern の prototype / oracle / benchmark を実装・実行していない。

## 一次資料と読了範囲

[arXiv の書誌ページ](https://arxiv.org/abs/2609.03315v1)で、題名、著者
Denglong Li / Gerui Wang / Tian Guan / Mingchao Wan、v1 の提出日時
2026-09-03 03:10:10 UTC を確認した。指定番号と論文は一致する。
日付を Issue 本文から転記しただけではない。

[v1 全文](https://arxiv.org/html/2609.03315v1)の I–V、全 Algorithm、証明、評価、参考文献を読んだ。
以下は再確認箇所の索引であり、論文全体の翻訳ではない。

|論点|一次資料の位置|確認すべき契約|
|---|---|---|
|snapshot と再試行|III-A, III-B, III-D|batch 内の書込み隔離、未確定取引の再投入順|
|有向依存|III-C, Rule 1, Algorithm 1|低 index writer への RAW のみ|
|commit|III-D, Rule 2, Algorithm 2|index 順の書込み、後続 writer の上書き|
|最終採用と伝播層|III-E, Rule 3, Algorithm 3|red/gray の交互伝播、同一層の遅延反映|
|停止性|III-F, Lemma 1/2, Theorem 1|DAG 上の未標識頂点の減少|
|CFBS|III-G, Algorithm 4|payload の account、採用済み account との交差、全 pending 列|
|等価逐次実行|III-H, Theorem 2/3|batch 内の index 順を batch 順に連結|
|実装と workload|IV-A|ChainMaker v2.3.8、Go / Rust / Wasmer、YCSB / SmallBank|
|正確性|IV-B|決定性と逐次再実行による検査|
|ablation|IV-C, IV-D, Fig. 8–11|YCSB では CFBS 無効、SmallBank では有効/無効の対照|
|費用と batch|IV-E, IV-F, Fig. 12–14|phase 内訳、SmallBank batch-size 評価では CFBS 無効|

本文の短い事実要約: YCSB は 5 read / 5 write で完全 RMW を要求せず、SmallBank は
account 単位の RMW を含む。SmallBank の CFBS あり/なしの差と、一般 R/W の BP の差は別の結果である。
論文のシステム高速化を EAS の効果に帰属できない。
[根拠: IV-A–IV-F](https://arxiv.org/html/2609.03315v1#S4)。

公式 HTML / PDF / 書誌 HTML の取得物と SHA-256 は
[`lantern_downloads.json`](../experiments/target_selection/sources/lantern_downloads.json)に保存した。
HTML から標準ライブラリで抽出したテキストも保存した。抽出テキストには数式の
MathML/TeX 表記が重複するため、数式判定には元の HTML を用いた。
`pdftotext` はこの環境に存在せず、読了には公式 HTML を使った。PDF は保存した一次資料である。

## CFBS と accept_id の同値条件 — 本監査の導出

取引の全順序を `1,...,n`、完全 RMW の論理キー集合を `S_i = R_i = W_i`、
CFBS が抽出する account 集合を `A_i` とする。比較には次の条件が必要である。

1. 同一の候補列を同一の全順序で走査する。固定長 prefix と pending 全体を比較しない。
2. account とキーの交差関係が一致する。十分条件は同一 namespace への正規化後 `A_i = S_i`。
   より一般には全取引対について `A_i ∩ A_j = ∅ ⇔ S_i ∩ S_j = ∅` でよい。
3. 走査中に集合は変わらず、不採用取引の集合は occupied に追加しない。
4. 空集合も通常の非交差判定で採用し、各取引は別 ID を持つ。

採用済み集合を `C_{i-1}` とすると、両方式の判定は同じ式になる。

```text
accept(i) ⇔ S_i ∩ (⋃[j ∈ C_{i-1}] S_j) = ∅
C_i = C_{i-1} ∪ {i}  (accept の場合)
C_i = C_{i-1}        (それ以外)
```

証明: 初期 occupied は双方空。i より前の採用が一致すると occupied の交差判定も一致し、
i の採用と更新が一致する。i に関する帰納法で、採用 ID 列・不採用 ID 列・mask が一致する。
従って既知 account の完全 RMW に対する CFBS を EAS の新しい発見として提示できない。
これは [Algorithm 4](https://arxiv.org/html/2609.03315v1#S3.SS7) と #3 の実装定義からの本監査の証明である。

同値の限界: account が複数 table のキーをまとめると、同じ account だが互いに異なるキーへの
アクセスを CFBS が保守的に延期する場合がある。payload が完全なアクセス集合を与えない場合も
上の仮定は成立しない。さらに CFBS は実行前の選択であり、#3 の accept_id は実行後の選択である。
集合の一致は実行済み仕事量、再試行、batch サイズ、定常 throughput の一致を意味しない。
Algorithm 4 には固定件数で走査を打ち切る条件がないため、比較する実装に独自の cap を加えるなら別仕様である。

## Back-Propagation の最終判断を保存する別問題 — 本監査の導出

まず任意の point R/W に対して、公開 Rule 1 のグラフを次で表す。

```text
E = {(i,j) | j < i, R_i ∩ W_j ≠ ∅}
```

これは EAS が完全 RMW で扱う無向交差グラフと同じデータ構造・同じ policy ではない。
ただし Rule 3 が終了した時の最終 red/gray に限れば、`c_i = 1` を red として次の一意な漸化式がある。

```text
c_i = 1 ⇔ ∀j < i: ((i,j) ∈ E ⇒ c_j = 0)
        ⇔ R_i ∩ (⋃[j < i, c_j = 1] W_j) = ∅
```

証明: red への遷移時に出辺先は全て gray である。gray は red への出辺を持つ場合にのみ生じる。
一度確定した色は変わらず、停止時には全頂点に色がある。従って最終 red は red の出辺先を持たず、
最終 gray は少なくとも一つ red の出辺先を持つ。全ての出辺先は自分より小さい index なので、
小さい index からの帰納法で漸化式の解は一意である。
これは [Rule 1 と Rule 3](https://arxiv.org/html/2609.03315v1#S3.SS5)からの新たな導出であり、既存 EAS の定理の転用ではない。

従って候補となる別実装は、index 順に read key を採用済み write key の集合と照合し、
採用した場合に限り自分の write key を追加する。キー操作数に線形な hash 集合走査は期待計算量であり、
敵対的 hash の最悪保証ではない。DAG を明示しなくても最終 mask と ID 順の commit 列を得られる。
一般 R/W では blind write 同士を両方採用できるため、無向の全アクセスキー交差を使う実装とは違う。

保存対象は慎重に限定する必要がある。

- 上の単純走査は最終 red/gray と ID 順 commit を保存するが、BP の内部色伝播層の順序や境界は出力しない。
- 元の batch 選択、snapshot、private write の適用順、未確定列を全て保持すれば、次の状態と pending 列も
  一致し、batch に関する帰納法で後続の結果も一致する。この条件の実装検査は本監査では未実施である。
- 完全 RMW に制限すると上の式は accept_id と一致する。従ってその制限内での BP の graph 除去だけでは、
  CFBS / accept_id を超える選択 policy の新規性はない。
- 利益が残るなら、実行前 account 情報を必要としない一般 point R/W の既存 BP policy 保存、
  または内部伝播証跡まで保持する必要がある用途である。後者の実際の要求は未確認である。

意味論確認用の小さな反例を示す。`S_1={a,b}, S_2={a,c}, S_3={b,d}` では、
CFBS / accept_id / BP は `{1}` を採用する。EAS k=1 は最大次数の 1 を中止し `{2,3}` を残す。
どちらも同じ snapshot で安全な採用集合だが、同一 policy ではない。
この手計算反例により、EAS をそのまま Lantern に入れると exact preservation が壊れることを示せる。

また全取引が一つの同じキーを RMW する場合、Rule 1 をそのまま適用した辺数は `n(n-1)/2` である。
III-G の star-like という形容から疎な star の辺数を仮定してはいけない。採用は先頭一件だが、
採用集合の小ささと明示 graph の小ささは別である。
逆に CFBS がその衝突を実行前に除くなら、後段に密な DAG が発生するという仮説自体を再確認する必要がある。

## 公開 artifact の確認範囲

全文内の外部リンクを抽出したが、Lantern 固有の repository / patch / commit / artifact は見つからなかった。
実装関連の参照は [ChainMaker v2.3.8](https://git.chainmaker.org.cn/chainmaker/chainmaker-go/-/tree/v2.3.8) と
[Go SDK](https://git.chainmaker.org.cn/chainmaker/sdk-go)であり、これだけでは Lantern の公開実装を特定できない。

2026-09-05 の追加探索結果:

- GitHub repository API の `lantern chainmaker` と論文題名の検索は、どちらも `total_count=0`、
  `incomplete_results=false`。これは repository metadata 検索の結果であり、全 GitHub code の不存在証明ではない。
- ChainMaker の公開 GitLab project 検索 API は HTTP 403、論文の v2.3.8 tree URL の直接取得は HTTP 404。
  API の拒否や URL の取得失敗を、閉源の証拠とは扱わない。
- Web 検索では論文・mirror と無関係な同名結果を除き、Lantern 固有の source を特定できなかった。
  mirror の内容は根拠に採用していない。著者への問い合わせ・メッセージ送信は行っていない。

[`lantern_artifact_probes.json`](../experiments/target_selection/sources/lantern_artifact_probes.json)と
[`lantern_search_log.json`](../experiments/target_selection/sources/lantern_search_log.json)に URL・query・結果を保存した。
公開実装が存在しない、または build 不能だとは結論しない。
**この監査で実装を特定できず、Lantern 本体の build / license / 実行費用を検証できていない**という制約である。

## 10 観点と gate

|観点|判断と限界|
|---|---|
|実際のボトルネック|Algorithm 1 は取引対と先行 write を走査し、Algorithm 3 は隣接を使う。実行可能な形で materialization は記載される。しかし公開実装の allocation と内訳を追試しておらず、selection が支配的とは断定しない。|
|意味論の一致|EAS への直接一致は反例で否定。最終 BP mask の graph-free 漸化式は上に導出した。一般 R/W は別定理・別実装として扱う。|
|policy 保存の価値|同一 replica 間の決定性は同一 policy 実装を必要とするが、全 replica 同時変更で旧 policy の結果を必ず維持すべき外部契約は論文から確認できない。既存結果・証跡の維持という工学上の価値は仮説。|
|安い baseline|既知完全 RMW では CFBS/accept_id が同値。一般 R/W なら accepted-write union を必須 baseline にする。EAS/static は異 policy の品質比較として分離する。|
|アクセス数|account から DB キーへの写像を要検証。YCSB の read/write 個数と complete-RMW arity を混同しない。SmallBank の各取引の実キー集合は artifact なしでは未確認。|
|graph 密度|共通 RMW キーで二次数の辺となることは Rule 1 から導出可能。しかし CFBS 有効時はその衝突を事前回避するので、実 workload に残る密度を別途測る必要がある。|
|artifact|論文全文と疑似コードは入手済み。Lantern 固有 source / patch は未特定。依存・license・build は未検証。|
|評価可能性|paper-based 最小再現は可能。公開実装がない状態で再現物を Lantern/ChainMaker 実測と表示してはいけない。本監査では数値追試なし。|
|新規性リスク|RMW の単純 conflict-free 選択は CFBS と重複。BP の最終判断も上の安価な漸化式が比較対象であり、重い EAS index の必要性は自明でない。|
|実装コスト|独立 point-R/W oracle は小さくできる。VM・snapshot・block・retry を含む実統合の hook は、固有 artifact がないため未確定。|

|Go/No-Go 条件|判定|
|---|---|
|1 Semantic fit|EAS 直接移植は不合格。別問題としての BP 最終判断保存は上の定義・証明の範囲で適合可能。|
|2 Need|明示 graph 処理が paper に存在することは確認。実システムで最適化に値する高費用を払うかは未追試で、必須条件の実証には不足。|
|3 Policy value|EAS の優位を #3 から仮定できない。Lantern 旧 decision を保存する固有外部要請も未確認。|
|4 Baseline relevance|RMW では CFBS/accept_id に帰着し、新 policy の差は残らない。一般 R/W の表現変更は別仮説として残る。|
|5 Evaluability|忠実な最小再現は可能。実システム追試は固有 artifact の未特定で未達。|

従って Lantern は今段階の大規模移植先に選ばない。将来再開するなら、まず一般 point R/W の
BP 最終 mask 保存に対象を固定し、独立 explicit-DAG oracle と accepted-write union を比較する。
最終集合だけを測るのか、色伝播層も保存するのかを事前に定める。後者の要請も、実際の費用もないなら
EAS の構造を持ち込む理由はない。この結論は Lantern の論文性能や正確性を否定するものではない。
