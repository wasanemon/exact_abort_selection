# 【Codex】AriaにExact Abort Selectionを最小統合し、固定キー数の理論・実測効果・限界を検証する

Source: https://github.com/wasanemon/exact_abort_selection/issues/1
Retrieved: 2026-09-05; base: d0508c393ec084582c12e6f3abadab63501eaedd

## 目的と終了条件

Ariaの実際のsnapshot実行・private write set・書込み適用を利用し、Exact Abort Selection（以下EAS）を**単一ノードの実験用validatorとして最小統合**する。実装案だけで止まらず、実装、独立oracleとの照合、実験の実行、生データ、集計、再現手順、結論まで完成させる。

検証するのは、固定された中止規則の計算を軽くできるか、その理論上の適用条件と実用上の限界は何かである。Ariaより速い・中止率が低いという結論を先に決めない。負の結果や反例も正規の成果であり、過去のプロトタイプの倍率を再現目標にしない。

このIssueは過去チャットやsandbox内のファイルを読めなくても実行できる仕様とする。以下の研究上の主張は未査読の検証対象であり、Codex自身も証明・前提・実装との対応を点検すること。

## 1. ベースと変更範囲

確認したベースは `master` の `d0508c393ec084582c12e6f3abadab63501eaedd`。作業開始時にHEADと差分を確認し、既存作業を消さず、実装用ブランチで作業する。履歴の書換えや自動mergeは不要。

主な確認箇所：

| ファイル | 用途・注意点 |
|---|---|
| `protocol/Aria/AriaManager.h` | 全workerのREAD終了からCOMMIT開始までのbarrier、共有`transactions`、`cleanup_batch()`。 |
| `protocol/Aria/AriaExecutor.h` | `read_snapshot()`、二段階の`execute()`、`reserve_transaction()`、`analyze_dependency()`、`commit_transactions()`。 |
| `protocol/Aria/AriaTransaction.h` | 実行で収集された`readSet`/`writeSet`、`reset()`、epoch/ID、バッファの寿命。 |
| `protocol/Aria/Aria.h` | `commit()`による実テーブル更新。`abort()`は現在no-op。 |
| `benchmark/ycsb/Transaction.h` | 現在の`keys_num`はコンパイル時に10固定。CLIの値だけを変えて2キー実験と呼ばない。 |
| `core/Context.h`、`CMakeLists.txt` | opt-in設定と実験targetの追加。既存はC++14。 |

**対象：** coordinator 1台、protocolはAria（AriaFBではない）、全対象キーがlocal、複製なし、インメモリのpoint-keyアクセス。主対象は全取引が `R_t = W_t = S_t` を満たす完全RMWで、主評価の最大キー数は1～4、中心は2キー。追加のarity定数費用はselector単体で6/8キーまで調べる。異なる個数のキーを持つRMW取引が混ざってもよい。

**対象外：** WAL、fsync、クラッシュ回復、レプリケーション、分散commit、範囲検索・phantom、SQL、TPC-Cへの全面対応、Silo対応、汎用の並列selector、再試行/公平性の新設計。1R1W専用アルゴリズムと一般の非対称R/Wへの拡張も今回は不要。一般固定arityの上限と条件付き下限を同じ完全RMWモデルで検証することを優先する。

対象外のR/W形状、remote access、不正な設定、容量上限超過は明示的に拒否する。入力を黙って切り詰める、別規則へ黙ってfallbackする、一般OLTPを扱えたことにする、という対応は禁止。

既存のAria、YCSB、他protocolの標準動作とデフォルトは保持する。専用の小さなworkload/benchmark targetと、Ariaへのopt-in hookを追加する方針を優先し、無関係なリファクタリングや依存関係の大型更新は行わない。

## 2. 比較の意味を混同しない

**元のAriaは全取引間の衝突グラフを構築してGreedySortを実行する方式ではない。** このベースの実装はキーごとのreservationとRAW/WAR/WAW判定を使う。従ってEASは、Ariaの既存中止判断をそのまま高速化するdrop-in置換ではなく、Ariaの実行基盤に別の中止選択policyを載せる実験である。

比較を必ず分ける：

1. **同じpolicyの計算方法の比較：** 明示グラフEAS vs lazy EAS vs profile EAS vs adaptive EAS。中止列・確定集合が完全一致することが前提。これが高速化の主比較。
2. **元のAriaとの比較：** native Aria vs Aria+EAS。policyが違うため、確定集合の一致は要求しない。バッチ全体の時間、commit/abort数、追加の直列処理費を測る。グラフ版に対する高速化を「Ariaに対する高速化」と記載しない。

nativeは既存validationをそのまま利用し、`aria_snapshot_isolation=false`、reorderingは既定の有効設定を記録する。Rule 1/2の全比較を増やす必要はない。EAS側でnativeのWAW棄却を事前適用すると別の入力問題になるため、共通snapshotを実行できた全対象取引から選択する。

## 3. EASの厳密な仕様

`n`は一つのバッチ中の取引数であり、worker数を掛けた値ではない。各取引に固定した相異なるIDを持たせる。アクセス集合内は重複を除くが、同じキー集合を持つ別取引を一つの取引として数えてはいけない。

一般的な定義は `t -> u iff t != u && R_t intersects W_u`。今回の完全RMWでは「キーを一つでも共有する異なる取引」の間に双方向の辺がある。複数キーでぶつかっても相手一人は一人、自己辺はゼロ。異なる競合相手数を`d(t)`とすると、入次数×出次数は`d(t)^2`なので、非負の`d(t)`で順位を比較してよい。

policyはDing et al.のGreedySortGraph/Algorithm 2を基に、以下で完全に固定する：

- source/sinkを取り除き、取り除いた取引は確定側に入れる。完全RMWではこれは次数0の孤立取引の除去に一致する。
- 残存グラフが空でなければ、`(degree降順, transaction ID降順)`の上位`k`件を、**削除前の同じグラフ**から選ぶ。
- 上位`k`件の選択が終わってから全件を中止・削除し、再び孤立取引を取り除く。
- 残存数が`k`未満なら以後`k=1`で処理する。`k=0`は不正入力。
- `selected_this_round`と`alive_in_graph`は別状態。選択済み候補を優先度構造から除いても、全員を選び終えるまで次数計数器は変更しない。

出力は、round境界を含む中止ID列、commit mask、確定取引の直列化証明書。完全RMWの確定集合はキーが互いに素なので、証明書は確定ID昇順へ正規化して比較できる。

### 必須の意味論テスト

- `T1={a,b}, T2={a,c}, T3={b,d}`：`k=1`のEASはT1を中止しT2/T3を確定する。native AriaはこのID順ではT1のみを確定する。**EAS同士は一致し、nativeとは異なり得る**ことを実エンジンでも確認する。
- ID1～4が`{a}`、ID5～7が`{b}`：最初のfrozen top-2は`[4,3]`。逐次top-1の繰返しだと`[4,7]`となり、同じ規則ではない。
- 同じキーを更新する2取引：`k=1`なら一件確定、上の厳密な`k=2`なら二件とも中止する。**このpolicy自体には常に一件以上確定する保証がない。** 勝手な「最低一件commit」救済を入れず、限界として残す。

## 4. 実装するselectorと理論

外部ライブラリの大規模導入は不要。selectorをAriaの通信・永続化から分離し、同一の正規化済みバッチ入力を受け取る小さなAPIにする。次の5モードを用意する（名称は例、最終名をREADMEに記載）：

| モード | 内容 |
|---|---|
| `native` | 既存Ariaのpolicy。 |
| `graph` | 明示bitsetグラフを使う同一policyの性能比較対象。 |
| `lazy` | 部分集合計数による正確な次数 + lazy最大heap。 |
| `profile` | heavy singleton profile構造を最初から使う。 |
| `adaptive` | lazyから始め、規定の作業量を超えたらprofileへ一度だけ切り替える。 |

これとは別に、小入力専用の単純なoracleを置く。oracleは全相手との集合交差と各roundの全再計算で実装し、最適化selectorの計数器や候補選択を共有しない。

### 4.1 `graph`を不当に弱くしない

bitsetで重複辺と自己辺を正しく処理する。次数は削除された頂点の生存隣接頂点について増分更新し、順位はheap/ordered set等で維持する。各中止のたびに全取引対を再計算するoracleを性能baselineにしない。初期の孤立取引を先に除いてから残存グラフを構築する軽量前処理を許し、その時間も含める。

グラフ構築、bitset確保、次数初期化、更新、trimを全て測る。CSRの追加は任意であり、一方式しか測らない場合は「最速の既知実装」と呼ばない。

### 4.2 `lazy`：正確な計数と、その限界

各非空キー部分集合`Q`について、グラフ中で生存し`Q`を含む取引数を`C(Q)`とする。

```text
d(t) = sum(nonempty Q subset of S_t, (-1)^(|Q|+1) * C(Q)) - 1
例：d({a,b}) = C({a}) + C({b}) - C({a,b}) - 1
```

全てのsubset incidenceを構築し、取引の実削除時にその取引の各subsetの計数を減らす。削除だけの過程なので、過去に計算した次数は現在値の上界。最大heapの先頭を正確に再計算し、更新済み候補が他候補の上界以上であるときだけ選ぶ。IDの同点処理も比較に含める。

この方式だけでは、再計算回数が最悪二次になり得る。**lazyだけを実装して劣二次時間の定理を実装済みとしてはいけない。**

### 4.3 `profile`：固定arityでの全中止列の上限

以下を実装し、実際のループ・確保量との対応を`docs/eas_theory.md`に書く。最大arityを`ell`、構築時の残存取引数を`n0`とする。空集合入力は直接処理する。

1. `B = ceil(n0^((ell-1)/ell))`（定数倍内の丸め可）。初期計数`C0(Q) >= B`をheavy、それ以外をlightとし、削除途中に分類し直さない。
2. heavyなsingletonキー集合を`K_H`とする。heavy subsetの全要素はheavy singletonなので、取引を`P_t = S_t intersect K_H`というキー集合でgroup化できる。実在するprofileだけを作る。
3. `sign(Q)=(-1)^(|Q|+1)`として、
   `common(P)=sum(heavy Q subset of P, sign(Q)*C(Q))`、
   `local(t)=sum(light Q subset of S_t, sign(Q)*C(Q))`。
   よって`d(t)=common(P_t)+local(t)-1`。
4. 各profile内に`(local, ID)`のordered set、全体に各profile代表の`(degree, ID)`のordered setを持つ。共通項は加数なのでprofile内の順位を変えない。
5. `C(Q)`を一つ減らすとき、lightなら初期posting list上の選択可能な取引のlocalを`-sign(Q)`だけ更新する。heavyなら`Q subset of P`となる実在profileのcommonと代表だけを更新する。heavy subset -> profileの接続を構築しておく。全キー組合せや全profileを毎回走査しない。
6. frozen-kの候補除外はlocal setからの除外だけであり、実削除とは分ける。複数subsetの更新途中はlocal/commonが増減し得るので、符号付き整数を使い、更新途中に候補を質問しない。

**trimを隠れた二次処理にしない。** 完全RMWでは、各キーの生存件数と唯一の生存IDを復元するXOR等、各取引の「他者も触るキー数」を持てる。キー件数が2→1になったとき、その唯一の生存取引の支持数を減らし、0なら孤立queueへ入れる。各キーのしきい値通過は一度であり、全期間のtrimを`O(A+n)`にできる。候補に選択済みだがまだ生存する取引も計数に含める。全roundごとの全取引走査を入れない。

`H=|K_H| <= ell*n0/B`。light更新は一subset当たり`B`未満のposting、heavyなサイズqのsubsetが触るprofile数は`sum(j=0..ell-q, binom(H-q,j))`以下。各取引には高々`2^ell-1`個の非空subsetがある。従って、固定ellで

```text
時間：O_ell(A + n^(2-1/ell) log n)
空間：O_ell(A + n)
```

を目標にする。初期索引構築・trim・全削除・証明書生成を含める。`ell=1`は`O(A+n log n)`、2は`O(A+n^(3/2) log n)`。定数には`2^ell`等が含まれる。ハッシュによるraw keyの索引化の期待時間と、索引化後の計算量を区別する。

### 4.4 `adaptive`

ell>=2ではlazyの正確な次数質問が`n0*ceil(sqrt(n0))`に達した後の**round終了・全削除・trim完了後**に、残存状態からprofileを構築する。切替えは一回のみ。古いheap等を不要になり次第解放し、その解放・再構築も時間とメモリに含める。ell=1は最初からprofileでよい。

一つのfrozen round中の超過は`O(n0)`質問で抑えられ、切替え前の仕事は上記上限以内、切替え後はprofileの上限に従う、という証明を確認する。切替え回数と時点を必ず記録する。強制切替えのテスト用予算も用意するが、主実験の既定値を結果を見て変更しない。

一般部分集合indexは少なくともell=8まで安全予算内で実装・検査できるものにし、arity上限と総subset incidence上限を明示する。指数的な確保の前にオーバーフローと予算をチェックする。16bit packing等を使う場合は範囲外の衝突・切捨てを許さない。未実装の任意ellまで性能評価済みとは書かない。

## 5. Ariaへの最小統合

最短の実装方針は以下。命名や小さな構成変更は任せるが、同じ意味論を保つこと。

1. 新しい実験用workload/targetで、同じキーを読み書きする1～4キー取引を既存Aria executorに実行させる。DB/テーブル、snapshot read、private write buffer、commit時のtable updateは元実装を再利用する。**別の自作DBだけで動かしたものをAria統合としない。**
2. ManagerでREAD phaseの全worker完了を待ち、COMMITを開始する直前に、共有`transactions`から**実際に収集された**R/W setを読み出す。予定されたqueryのキーだけを代用しない。選択はバッチにつき一回、単一threadで行い、全workerへ完了済みdecision配列を公開する。専用の複雑なschedulerは不要。
3. record同一性は`(table ID, partition ID, keyの論理値)`で定義する。`get_key()`が返すポインタ値をキーそのものにしてはいけない。バッファの寿命、同値キーの異なるアドレス、重複操作の正規化を検査する。
4. EASモードのCOMMITはdecision配列を使い、確定取引には既存`Aria::commit()`で書込みを適用する。nativeのRAW/WAR/WAWによる棄却を再度かけない。完全RMWの生存集合は互いにキーが素なので既存workerによる並列適用が可能。この根拠を説明・検査する。
5. 最初の最小版はREAD側の既存reservationを残してよい。その未使用費用を計測・明記し、全EAS方式で条件を揃える。除去を行うなら全EAS方式に同じ変更を入れ、効果をselector高速化と混同しない。native経路は維持する。
6. 全選択・全書込みの完了より前に次バッチを読ませない。epoch、ID、mask、計数器をバッチごとにresetする。abortされた取引の値を公開しない。耐久性を省くことと、メモリ上の正しさを省くことを混同しない。

### 再試行は主評価から外す

主評価は同一の有限traceと開始DB状態を使った**一バッチの一回試行**で行う。abortを勝手に再実行してから成功件数に加えない。nativeとEASの選択差により次バッチの入力が変わる閉ループ比較は不要。

このベースでは`cleanup_batch()`が`abort_lock`を参照する一方、`Aria::abort()`はno-opなので、再試行が期待通り実装されていると仮定しない。主評価に不要な既存再試行機構の全面修正へ脱線しない。EASのfrozen-kにはゼロcommit例もあるため、再試行の進行性まで保証したと記載しない。

別途、3バッチ以上を実際のphase遷移で動かすsmoke testを作り、状態が漏れないことは検査する。

## 6. workloadと正しさの検証

入力は`(seed, batch ID, logical transaction ID)`で決定的に生成し、traceを保存する。現在のExecutorには`this`のアドレス由来の乱数seedがあるので、「同じCLI seedなら同じ入力」と思い込まず、全モードで完全に同じtransaction ID・キー集合・初期値を使う。worker数や実行順で入力を変えない。

write値は読んだ値と固定IDから決まる非自明な変換にする。全取引が同じ定数を書くだけのworkloadではread依存の検査にならない。変換・値サイズ・取引本体の仕事量はnativeを含む全方式で共通。重複keyを再抽選して固定個数にするかdedupで可変個数にするかを定義し、実測arityを記録する。

必須検査：

- 小さなキー宇宙・短いバッチの全列挙と、固定seedのランダム入力。ell=1～4、空バッチ、n=1、同一署名多数、全員同一キー、全員非競合、複数成分、同点、キー重複、自己RMWを含める。生成件数と検査件数を実測で報告する。
- oracle vs graph/lazy/profile/adaptiveで、各roundの中止列、commit mask、正規化した証明書を比較する。k=1/2/3とk>nを含め、各roundでsubset次数を独立の集合交差と照合する小テストを置く。
- profileのB=1/2/既定値、adaptiveの切替え予算0/1/既定値等を検査し、切替え前後で選択が一致することを確認する。テスト用の特殊Bに主実験の計算量保証を誤適用しない。
- 上限・不正入力・キーIDの大きな値・同値キーの別アドレスを検査する。一般R/W、範囲操作、remote等は明示エラー。
- 実Ariaで確定取引を独立に逐次再実行し、読み取った値、計算結果/private writes、DBの最終全状態を直接比較する。hash一致だけに依存しない。検査は時間測定外で行う。nativeはnative自身の確定集合、EASはEASの集合で検査する。
- worker=1と複数workerで、固定traceから同じEAS判断・DB状態が得られることを確認する。ASan/UBSanを追加コードと統合smokeにかける。可能なら小さな並列テストをTSanでも調べる。sanitizerを性能測定と混ぜない。

oracleを最適化実装と同じバグで一致させない。問題が出たら最小反例を保存し、仕様・証明・実装のどこが誤っていたかを説明してから修正する。

## 7. 必要最小限の性能実験

`--smoke`と`--full`に相当する再現スクリプトを用意する。以下を基準に実行計画を先に保存し、無意味な全パラメータ直積は作らない。実行時間・メモリの予算はCLIで変更可能にし、使用した実値を残す。

| 系列 | 条件・目的 |
|---|---|
| 主系列 | ell=2、n=128/512/2048/8192/32768、キー領域10,000、一様とZipf 0.99、worker=1、k=2。nativeと4種類のEASを比較。 |
| arity確認 | ell=1/3/4、n=512/8192、同じキー領域、一様とZipf 0.99。少数キーでも定数費用・交差点が違うかを確認。 |
| 最悪挙動・切替え | 全取引が同じ2または4キーを触る入力、n=256/1024/4096/16384、k=1。lazyの再評価回数増加とadaptiveの実切替えを確認。k=2のゼロcommit例も別途記録。 |
| arityの定数費用 | selector単体、n=2048、ell=1/2/3/4/6/8。subset数・時間・メモリ・明示的な予算超過を記録。HSC下限の実証とは呼ばない。 |
| 最小の統合スケール確認 | ell=2、n=8192、Zipf 0.99、worker=1/2/4（利用可能なCPU範囲）。直列selectorとbarrier費用を含むバッチ全体を比較。 |

主表は最低5反復、複数の固定入力seedを含む同一条件のpaired測定とする。ウォームアップと測定を分離し、方式の実行順をseed付きで入れ替える。高負荷な方式を同時実行しない。マシン、CPU割当/affinity、メモリ、OS、compiler、最適化flags、commit SHA、実行コマンドを保存する。

一つの測定は少なくとも次を持つ：

- `mode, policy_k, seed, n, actual_arity, key_count, workers, initial_core_size, status`。
- snapshot実行、reservation、R/W抽出・正規化、index/graph構築、trim、選択/更新、切替え、書込み適用、同期待ち、バッチ全体のwall time。包含関係を明記し、内訳を二重加算しない。並列workerの累積時間とwall timeも区別する。
- commit数、abort数、round数、実行した次数再評価数、subset数/incidence数、light posting走査数、heavy profile更新数、tree更新数、切替え回数と時点。
- peak RSS（プロセス全体であることを明記）と、可能ならselectorの要素数/確保byte。別プロセス測定等で前の方式の高水位を持ち越さない。

**時間区間を二つに分ける。** selector単体は抽出/正規化・構築から確定集合と証明書を得るまでを含む区間と、その内訳を示す。統合時間は既存Ariaでsnapshot実行を開始してから全書込みを適用するまで。入力生成・DB初期化・oracle検査を除外した場合は明記する。normalized入力を共有する純粋なkernel時間も別欄に出せるが、抽出や構築を無料にした数字を総時間と呼ばない。

implicit側で測定用に巨大な明示グラフを裏で作らない。正確な辺数が必要な場合は小入力または計測外の独立処理に限定する。

中央値とばらつき、pairedな速度比を集計する。負けた条件、ゼロcommit、OOM/timeout/unsupportedも生データに残し、timeoutを有限の実測時間に置換しない。対象の全反復を完了できない設定はstatusと予算を報告する。

特に、通常入力でadaptiveが一度も切り替わらなければ「その高速化はlazy側による」と書く。profileを最初から使うablation、lazy単独、実際に切替える入力を比較し、最悪計算量を保証する構造と通常時に速い構造を混同しない。

## 8. 理論上の限界：HSC帰着の検査

ベンチマークから計算量下限は証明できない。下限は以下の帰着を文書で再検証し、小入力の全列挙で構成と次数を点検する。

HSCは「任意のepsilon>0に対しあるcがあり、宇宙サイズc log m上のm集合ずつの二族A/Bについて、Bの全集合と交わる集合がAにあるかを、O(m^(2-epsilon))時間では一般に決定できない」という仮定。SETHそのものでも証明済みの事実でもない。

入力を`A_1..A_m`, `B_1..B_m`、m>=1とする。まず`B_j intersect union(A_i)`が空となるjがあればNOと判定する。残りについて、入力宇宙とは異なる5キー`x,y,h,l0,l1`を追加し、すべて`R=W=S`で次を作る。

| 族 | 個数 | S |
|---|---:|---|
| X_i | m | A_i union {x} |
| Y_j | 各jにつき2取引、計2m | B_j union {y} |
| D0, D1 | 2 | {x,l0}, {x,l1} |
| C0, C1 | 2 | {h,l0}, {h,l1} |
| 残りのC | 3m-2 | {h} |

合計`n=6m+2`、総アクセス数は`2*sum|A_i| + 4*sum|B_j| + 12m + 12 = O(m log m)`。自己辺はなく、同一署名の別取引は別頂点。全体が連結な対称グラフ、従って一つのSCCになる。

`h_i = |{j: A_i intersects B_j}|`とすると、

```text
d(X_i) = m+1+2*h_i
d(Y_jの各コピー) = 2m-1 + |{i: A_i intersects B_j}| <= 3m-1
d(D0)=d(D1)=m+2 <= 3m
d(C0)=d(C1)=3m
その他のCのdegree = 3m-1
```

YESなら最大次数は`3m+1`で最大候補はX族。NOならXの最大は`3m-1`以下で最大候補は非X族。非Xの競争相手C0/C1が二つあるので、frozen top-2にXが含まれるかでも判定できる。tie-breakには依存しない。前処理と構成の時間を含めて帰着を説明する。

小さいm/宇宙の全列挙に空集合・重複集合を含め、集合の素朴な交差から全辺と次数を構築し、前処理、連結性、全次数、最大候補、top-2、元Hitting SetのYES/NOを独立に確認する。構成で作ったdegree式を正解oracleとして使い回さない。テスト件数・生成条件を保存する。

結論の量化を正しく書く：固定ellの完全RMWでは上記の全選択上限がある。一方、対数arityまで許す入力族では、HSCの下で最初の正確な候補選択にも一般的な真の劣二次時間アルゴリズムはない。**中間の全arityを分類したわけでも、固定ellの指数が最適と示したわけでもない。** ell依存の定数を無視してell=log nを上限式へ代入しない。

## 9. 成果物・受入基準

ファイル名は多少変更可だが、少なくとも以下をリポジトリに残す。

- opt-inのAria統合、共通selector API、graph/lazy/profile/adaptive、独立oracleとunit/integration tests。
- `docs/eas_design.md`：実装箇所、対応するAria phase、モデル制約、nativeとの差、同期・キー/バッファの扱い。
- `docs/eas_theory.md`：policy、上限の計数、コードとの対応、HSC帰着と限定。訂正があれば根拠を含む。
- `experiments/eas/`等：生成/実行/集計スクリプト、事前設定、機械可読の生データ、環境情報、実行/検査ログ、図表。
- `REPORT_ja.md`と再現README：実測した事実、証明上の主張、未確認点を分離し、勝った条件・負けた条件・適用不能条件を併記する。過去のチャット上の数値を今回の測定として転載しない。

完了チェック：

- [ ] 既存のデフォルト経路を保持し、変更箇所とベースSHAを記録した。
- [ ] nativeを含む全モードが実際のAria実行基盤で動き、EASモード間の全選択列が一致した。
- [ ] 独立oracle、snapshot/最終状態の検査、強制切替え、複数worker、複数バッチ、ASan/UBSanを実行し、結果と失敗時の対処を保存した。
- [ ] lazyだけでなくprofileとadaptiveを実装し、仕事量と記憶量の上限を壊す隠れた全走査がないかを点検した。
- [ ] HSC帰着の文書と独立した有限検査を用意した。有限検査を下限の証明とは呼んでいない。
- [ ] 主比較、native比較、arity費用、通常時と最悪時、実切替え、ゼロcommit例を実行し、生データから図表を再生成できる。
- [ ] clean checkoutからのbuild/test/smoke/full/集計コマンドを記載し、少なくとも記載したsmokeの再実行を確認した。必要な依存関係も明記した。
- [ ] 最終報告は「どのpolicyに対して何が同一で、何が改善し、どこでは損で、何は主張できないか」に答えている。

「Ariaより必ず速い」「最適なcommit集合を求める」「一般OLTPで少数キーなら同じ定理が使える」「グラフ版に対する倍率がAriaへの倍率」「ベンチマークでHSCを証明した」は不可。完全RMWの確定集合選択はset packingと関係し、2キーでは最大matchingを使う別policyも考えられるが、その実装・新policy探索は今回の完了条件に含めない。

ビルドだけ、unit testだけ、実験計画だけで完了にしない。理論に不備が見つかった場合は反例と訂正を、環境上実行不能な項目があれば実際のエラーと未完了範囲を明記する。勝つまで恣意的に条件変更するのではなく、合意した範囲で検証を完結させる。最終出力には変更要約、実行コマンド、結果の要点、成果物の場所を記載し、利用可能な通常のworkflowでcommit/PRにまとめる。自動mergeはしない。

## 参考資料

- Aria原論文： https://pages.cs.wisc.edu/~yxy/pubs/aria.pdf （§4–5。reservationによるnative判定と区別する。）
- Ding–Kot–Gehrke, PVLDB 2018： https://www.vldb.org/pvldb/vol12/p169-ding.pdf （Algorithm 2とprod-degree。ID同点処理は本Issueで具体化。）
- HSCの定義： https://drops.dagstuhl.de/storage/00lipics/lipics-vol275-approx-random2023/LIPIcs.APPROX-RANDOM.2023.1/LIPIcs.APPROX-RANDOM.2023.1.pdf （Definition 7。上記の取引への帰着自体を述べる論文ではない。）
- ベース実装： https://github.com/wasanemon/exact_abort_selection/tree/d0508c393ec084582c12e6f3abadab63501eaedd
