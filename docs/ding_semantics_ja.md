# Ding Algorithm 2 と EAS の対応範囲

開始点は `d150211968ef6d61efda82f9f44f63e3bac28b44`。以下の対応証明は本追試の導出である。
原論文: [Ding, Kot, Gehrke, PVLDB 12(2), pp.169–182](https://www.vldb.org/pvldb/vol12/p169-ding.pdf)。
§3.2、§4、Algorithm 2、§4.2、§5–5.6 を全文と照合した。

## 証明する限定

入力は既に実行を終えた viable な取引の一バッチ。全取引は同じ snapshot を読み、
local point key の有限集合について `R_i=W_i=S_i`、`|S_i|≤a`、a は小さい定数とする。
取引 ID は一意。異なる取引の同一キー集合は統合しない。自己辺を作らず、同じ相手と
複数キーで交差しても一辺とする。range、remote、version mismatch、一般 R/W はこの証明の外。

1. 原論文の辺 `i→j ⇔ i≠j ∧ R_i∩W_j≠∅` は、この限定では
   `S_i∩S_j≠∅` と等価であり、必ず逆辺もある。
2. 任意の残存集合 A で入次数と出次数はともに異なる競合相手数 `d_A(i)`。
   prod-degree は `d_A(i)^2`。非負整数上で二乗は厳密単調なので、最大 prod-degree の
   順位と最大 d の順位が一致する。sum-degree/max-degree も、この限定内だけなら同順位。
3. 対称 graph の零入次数/零出次数 trim は孤立点除去と等価。孤立点を除去しても
   他の次数は変わらず、その取引を commit 側へ退避できる。
4. tie-break を両実装で **ID 降順** と固定すれば、初期 trim 後の順位が一致する。
   Algorithm 2 の一回の選択時点の上位 k を凍結し、全候補削除後に trim する。
   `|A|<k` なら以後 k=1 とする。帰納法で、各 round の中止 ID 順、round 境界、
   残存集合、最終 commit mask が EAS と一致する。
5. 最終残存 graph が非巡回であることと辺を一つも持たないことは等価。
   辺があれば長さ2の有向閉路があるためである。従って commit 集合は pairwise disjoint。
   ID 昇順は合法な serialization certificate になる。

ID 降順の tie-break、round 内の出力順、最終 certificate の ID 昇順は本実装の追加規約。
原論文は同点候補の一意な選択を要求していない。原著の未知の実行列そのものを保存したとは言わない。
Algorithm 2 の疑似コードは `G.size < k`、説明文は no more than k と記す不整合がある。
本追試は疑似コードの厳密不等号を採用する。k=2・同一1キーの2取引では2件とも中止となる。
`≤` へ読み替える版や逐次再順位付け版と同一とは主張しない。

## 原論文の実システムとの距離

§4 は writer hash table を read set で probe して辺を明示化し、構築費用を
`O(|B|²+|R|+|W|)` と記す。§4.3/§5.4 は reordering が重い component と報告する。
§5 の既定は prod-degree、k=2。従って k=1 を主比較、k=2 を論文設定の補助比較にする。
§5 の microbenchmark は5 read/5 writeで、一つのreadとwriteを同じobjectにする。§5.5 Cicada は16 accessで
read と RMW の混在であり、complete-RMW 1–4キーの実測と同一 workload ではない。
§5.6 DBMS-X は中間層で同snapshotを保守的に仮定するが、実行済み一snapshotの証拠ではない。

SmallBank の deposit/transfer は少数の残高キーに対する RMW を動機付ける。
ただし account lookup、read-only balance、分岐、全transaction mixを省いたキー形状を
SmallBank 再現または原著 workload と呼ばない。本実証は合成 point-RMW trace と明記する。

tail latency の rct/rdeg、monetary priority、Cicada の thread-aware policy は
prod-degree＋ID の別名ではない。現行 EAS がそれらを保存するとの主張には別の順位証明、
入力 contract、実装、oracle、再試行を含む評価が必要。決定性だけでは cheap policy も
決定的なので EAS を必要にする理由にならない。

## 実装対象への限定 Go

Issue #4 が認める「既存 policy の忠実再現」の機構検査だけを Go とする。
原論文にある高い処理費用と上の限定的意味論対応は確認できた。
原著 artifact の取得、自然な対象 workload での必要性、cheap policyを超える実用価値は
未確認であり、原 DBMS の高速化、大規模 port、tail latency 改善を承認する gate ではない。
実証では独立の明示 directed graph＋Algorithm 2、既存 EAS 4実装、accept_id、
accept_static_degree を同一 raw trace で比較する。Lantern CFBS の同等条件下では
accept_id がその baseline を兼ねるため、別名で独立観測を水増ししない。
