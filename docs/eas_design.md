# Aria に対する Exact Abort Selection の最小統合

ベースは `d0508c393ec084582c12e6f3abadab63501eaedd`。開始時の HEAD はこの SHA、
master の作業差分は空だった。実装ブランチは `codex/issue-1-exact-abort-selection`。
仕様の取得時点の写しは [issue_1.md](issue_1.md)。

## 範囲と構成

`ARIA_BUILD_EAS=ON` で専用 `bench_eas` とテストを追加する。既定値は OFF。
元の YCSB はコンパイル時 10 キーのままであり、既存 workload の CLI を変えて
少数キー実験とは呼ばない。実験は専用 `Workload` / `Transaction` を用いる。
DB の保存・検索・更新には元の `aria::Table<9973,uint64_t,Value>`、実行には元の
`AriaManager<Workload>` / `AriaExecutor<Workload>`、書込みには元の `Aria::commit()` を使う。
自作の別 DB 上だけのシミュレーションではない。

対象は coordinator=1、Aria、hash partitioner の replica=1、table=0、partition=0、
ローカル point key、全取引 `R=W=S` のインメモリ実験。実エンジンの最大 arity は4、
selector 単体は8。混在 arity と空集合にも対応する。CLI は分散・耐久性・SQL・range
等の設定を受け付けない。一般 R/W、remote/range フラグ、実セット内の非local
partition/table、local-index access、未完了応答、abort_no_retry、範囲外のキーは明示拒否する。
自動 fallback、容量の切捨て、native WAW による EAS 入力の事前棄却はない。

主な追加ファイルと変更点:

|場所|役割|
|---|---|
|`eas/Selector.h/.cpp`|小さな共通 API、正規化、graph/lazy/profile/adaptive、容量検査|
|`eas/Oracle.cpp`|小入力の独立全対交差・全round再計算 oracle|
|`eas/Engine.h/.cpp`|有限 trace 専用 workload、既存 Table の初期化、manager hook、独立状態検証|
|`core/AriaExperiment.h`|任意接続の phase observer・decision/commit byte 配列・worker 計測|
|`core/Context.h`|既定 nullptr の `aria_experiment` のみ追加|
|`protocol/Aria/AriaManager.h`|READ前、READ完了後COMMIT前、COMMIT完了後のcallback|
|`protocol/Aria/AriaExecutor.h`|任意計測、decision適用経路、元commit呼出の記録|
|`bench_eas.cpp`|trace / mode / worker / 予算 CLI と機械可読 JSON|

`Aria.h`、`AriaTransaction.h`、reservation/dependency 判定の本体、YCSB、他 protocol は
変更していない。既定 nullptr の場合、元の分岐と `protocol.commit()` を使う。
小さな hook の nullptr 検査自体はソースに残る。

## phase、公開、バッファの寿命

```text
manager: epoch++ / cleanup_batch
         before_read: traceをstorageへ設定、検査用DB全状態コピー、計時開始
         Aria_READを公開
workers: 実read_snapshot() → 第一executeで読取り、第二executeでprivate writes生成
         元のread/write reservationを実行 → READ完了 / STOP handshake
manager: 全worker完了・ack後、実transactionのreadSet/writeSetを抽出
         EASの選択を一回だけ実行 → decision配列を完成
         Aria_COMMITを公開
workers: nativeなら元のanalyze_dependencyと判定、EASならdecisionを適用
         確定取引は元のAria::commit() → COMMIT完了 / STOP handshake
manager: 全書込み完了後に計時終了、測定外の独立検証
         次epoch、または EXIT
```

元の atomic worker status / completed count の barrier をそのまま使い、READ 完了前に
selector を始めず、全書込み完了前に次 snapshot を読まない。manager が作る decision
配列は COMMIT status の公開前に完成する。byte vector は `vector<bool>` ではない。
各 worker は固有 transaction 添字の committed byte と固有 WorkerTimes 要素だけを書き、
manager は完了の atomic handshake 後に読む。新たな scheduler/通信経路は作らない。

レコードの同一性は `(table ID, partition ID, uint64_t論理キー)` で決める。
read key と write key は別 vector に置き、同じ論理値でもアドレスが異なる。
private read/write の値も別 vector である。vector は READ 前にサイズを確定し、
COMMIT と検査が終わるまでリサイズしない。実行済み R/W set のポインタを辿って論理値を
コピーし、各集合内を dedup する。同じ署名の別 transaction は ID が異なる別頂点として残す。

EAS の確定集合はキーが互いに素である。この証明と直接検査によって、元 worker による
並列書込み適用が可能になる。中止の private writes をテーブルへ公開しない。
EAS の選択時に容量エラーが起きた場合は全件を確定不可にして二つの phase を終了させ、
worker を join した後に明示エラーを返す。部分的な成功結果へ置換しない。

## native と EAS の比較

[Aria 原論文 §4–5](https://pages.cs.wisc.edu/~yxy/pubs/aria.pdf) と、このベースの
`reserve_transaction()` / `analyze_dependency()` はキー別 reservation と
RAW/WAR/WAW による判定を行う。元 Aria が明示衝突グラフ上の GreedySort を
実行しているわけではない。EAS は別の中止 policy の実験である。

`native` は `aria_snapshot_isolation=false`、既定の
`aria_reordering_optmization=true`、`aria_read_only_optmization=true` を使う。
元の validation 分岐を実行し、observer は実際の commit を記録する。
EAS 4方式には native validation を重ねない。READ の reservation は全方式に残し、
その不要な費用も `reservation_worker_ms` で測る。

ID1=`{a,b}`, ID2=`{a,c}`, ID3=`{b,d}` の k=1 は、実 Aria で native が `[1]`、
EAS が `[2,3]` を確定する。k=2 で同じキーの2取引は EAS ではゼロ commit、native は1件。
これらを統合テストで期待結果として固定している。

## trace と取引本体

保存形式は UTF-8 TSV。先頭行は `EAS_TRACE_V1 key_count seed batch_id`、
以後 `ID<TAB>key,key,...`。実エンジンは元の20bit ID予約に合わせて `1..n` の連番を要求し、
`n<2^20`。selector API は異なる任意64bit IDを扱う。worker 数や実行順を乱数源にしない。
Python generator は `(seed,batch ID,logical ID)` ごとの固定乱数でキーを作り、
重複を再抽選して指定 arity を保ち、数値順に保存する。一様分布または正規化した有限
Zipf(0.99) CDF の逆変換、最悪入力は全員同じ集合である。trace と SHA256 を保存する。

値は4つのuint64、計32 byte。初期値はキーとlaneで決まる。全読取り値の重み付き和を
checksum とし、各 write は対応する read 値の定数乗算と、checksum・固定transaction ID・
key・laneを含む値との XOR で計算する。uint64 の剰余演算は意図的な仕様。
全モードで同一の計算であり、単なる共通定数の書込みではない。

主評価は一バッチの一回試行、新しいプロセスと同じ開始 DB 状態である。abort を retry して
成功数に足さない。元の `cleanup_batch()` が `abort_lock` を参照し、`Aria::abort()` が
no-op な点も変更していない。別途、同じ manager と worker を保った3 epochの smokeで
DB状態を引き継ぎ、ID・mask・値・epochの漏れがないことを検査する。
再試行の公平性・停止性・進行性は主張しない。

## 検証と計測区間

小入力は集合交差だけで作った oracle と、中止round全列・commit mask・ID昇順証明書を
直接比較する。最適化版の計数・候補選択を oracle に共有しない。degree audit は小テスト
で毎roundの全対交差と比較し、profileのlocal+common分解も検査する。

実エンジンの各実行では測定終了後に次を直接比較する:

- 実 R/W set と保存trace。全 transaction の read 値とバッチ開始時の実 DB 値。
- 独立のscalar再計算結果と全 private write 値。実R/W pointerの別アドレス。
- 確定集合をID順で逐次再実行した際の読取り、キー非交差、結果。
- キー領域全体・全4laneの DB 最終状態。hash一致だけで済ませない。

worker=1/4、および3batch連続実行も同じ配列・全状態で比較する。大入力の implicit modeの
計測裏側に巨大グラフは作らない。性能runnerはEAS全方式の保存した完全decision配列を比較する。
selector単体の大入力検査は独立した証明書・分割検査であり、exact policy の一致は
方式間比較と小入力 oracle による。

時間は steady_clock の wall time。単位は ms。

|JSON欄|意味・包含関係|
|---|---|
|`batch_ms`|READ公開直前からCOMMIT終了handshakeまで。snapshot、予約、selector、書込み、barrierを含む|
|`read_wall_ms`|READの公開と完了handshakeを含む。snapshot実行・本体・transaction確保・reservationを含む|
|`read_worker_ms`|各workerのread_snapshotの累積。wallとは異なる|
|`reservation_worker_ms`|read_worker_msの内数、各reserve_transaction前後の累積|
|`extract_ms`|EASの実R/W抽出と正規化。nativeは0（検証用抽出は測定外）|
|`selector_ms`|実R/W抽出開始からselector kernel・decision配列へのコピー・抽出buffer解放まで。単体では入力正規化から証明書取得と入力buffer解放まで|
|`selector.build_ms`|subset/bitset、degree初期化、順位構造の構築|
|`selector.trim_ms`|singleton state初期化とtrim queue処理（その際のselector更新を含む）|
|`selector.select_ms`|frozen選択と中止取引の実削除・更新。trim・switchを除く|
|`selector.switch_ms`|旧heap/index解放と残存profile再構築。build_msには重ねない|
|`selector.certificate_ms`|証明書生成・整列と最終selector解放|
|`selector.kernel_ms`|正規化済み入力の検査、全構築・選択・trim・switch・証明書まで。内訳の親区間|
|`commit_wall_ms`|COMMIT公開前から完了handshakeまで。validation/適用を含む|
|`commit_worker_ms`|各workerのcommit_transactions累積|
|`dependency_worker_ms`, `apply_worker_ms`|commit_worker_msの内数、各依存判定とAria::commitの累積|
|`sync_wait_ms`|read/commitそれぞれのwallから最長worker処理を引いた非負残差の和。開始ずれ/handshake等の推定、各worker待機の総和ではない|

計時処理の呼出費用は全方式に含む。readのうちreservationを除いたworker累積がsnapshot/
transaction本体の時間であり、独立したwall区間として二重加算しない。
内訳を足して親区間に再加算しない。timer・callback・小さな管理処理の残差がある。
`selector.certificate_ms` は解放も含むため純粋な整列時間とは呼ばない。
生成・trace読込・DB初期化・worker起動・検査用開始状態コピー・全oracle/直接検査・JSON出力は
`batch_ms` から除外する。selector単体は `batch_ms=null` とする。

`peak_rss_kib` はJSON生成開始時点までのプロセス全体（DB・入力・検査を含む）の高水位で、selectorだけの使用量ではない。
`runner_peak_rss_kib` は外部の `/usr/bin/time` による終了時までの高水位で、JSON出力の確保も含む。日本語表では後者を優先する。
各反復を別プロセスにして他方式の高水位を持ち越さない。`graph_bytes` はbitsetのpayload、
`index_payload_bytes` は明記したsubset/posting等の部分的なpayload推定で、allocator・木node・
hash bucket・全補助配列を含む完全な確保量ではない。要素数も併記し、RSSと混同しない。
