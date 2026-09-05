# Exact Abort Selection の意味論・上限・条件付き限界

この文書の対象は、同じ snapshot から実行済みの完全 RMW 取引
`R_t = W_t = S_t` に対する、Issue #1 で固定された中止選択 policy である。
正確さはその policy の全中止列との一致を意味する。最大の確定集合を求めること、
native Aria と同じ集合を返すこと、耐久性・分散 commit・再試行の進行性を意味しない。

実装は [Selector.cpp](../eas/Selector.cpp)、公開型・予算は
[Selector.h](../eas/Selector.h) にある。以下の関数名は実際のループと対応する。
独立 oracle と実エンジン検査の結果は実験報告を参照し、本書の HSC 検査は
そのいずれの selector も使用しない。

## 1. 固定した policy と一次資料

[Ding–Kot–Gehrke, PVLDB 2018](https://www.vldb.org/pvldb/vol12/p169-ding.pdf)
の Algorithm 2（PDF 4 ページ、誌面 172）を確認した。候補列 `Q` を選んでから
その全候補を削除し、trim する構造である。§4.2 の prod-degree は入次数と
出次数の積で順位を付ける。ID 同点順序と、出力の round 内順序は本 Issue が
具体化した仕様である。

原論文には境界表現の不一致がある。Algorithm 2 の条件は `G.size < k` だが、
説明文は k 以下と読める。本実装は Issue と擬似コードの厳密な `< k` に従う。
従って残存数がちょうど k なら全件中止できる。原論文の別の記述を理由に
「最低一件確定」の補正を追加しない。

異なる取引 `t,u` の間の辺は `R_t ∩ W_u ≠ ∅` で定まる。
完全 RMW では対称であり、自己辺を除く異なる競合相手数を `d(t)` とすれば
入次数も出次数も `d(t)`、積は `d(t)^2` である。非負整数の二乗は順位を保つので、
実装は `(d(t), ID(t))` の辞書順最大を使用する。複数キーの共有は一辺と数え、
同一キー集合を持つ別取引は別頂点と数える。

各 round は次の順で進む。

1. 次数 0 の取引をすべて確定側へ取り除く。対称グラフの source/sink は孤立点に一致する。
2. 非空なら、残存数が k 未満の場合は以後 `k=1` とする。`k=0` は入力エラー。
3. **同じ削除前グラフ**の `(degree 降順, ID 降順)` 上位 k 件を列挙する。
4. k 件すべてを中止・実削除してから次の trim に進む。

`select_impl()` の候補選択ループは `eligible` のみを落とし、別の削除ループが
`Scheduler::erase()` と `State::erase()` を呼ぶ。`alive` と subset/key の計数は
全候補を決めるまで変えない。profile の `exclude()` は local 順位集合からの
候補除外だけである。候補に選ばれた取引も round の次数の分母・競合相手に残る。

例えば ID 1～4 が `{a}`、ID 5～7 が `{b}` なら、最初の frozen top-2 は
`[4,3]` となる。top-1 を実削除しながら二度選ぶ `[4,7]` は別の policy である。
同じキーを更新する二取引では k=1 は一件確定、k=2 は両方中止となる。
`{a,b}`, `{a,c}`, `{b,d}` の ID 1,2,3 では k=1 は ID 1 を中止して 2,3 を確定する。
native Aria がこの ID 順で 1 のみを確定することは、EAS の計算誤りを意味しない。

孤立取引は、その除去時点で残るすべての取引とキーが互いに素である。
除去済みの確定取引についてもこの関係が成り立つので、最後の確定集合全体が
pairwise disjoint となる。共通 snapshot の値を読んで private writes を計算した
確定取引は、任意の順で同じ read と write を再現できる。これが ID 昇順の証明書と、
確定取引の既存 worker による並列書込み適用の根拠である。

## 2. 計算モデルと入力索引化

`n` はバッチ全体の取引数、`ell=max_t |S_t|`、`A=Σ_t |S_t|` とする。
完全 RMW の read と write を別々に数えるアクセス総数は `2A` である。
`Batch::accesses` は片側の `A` を記録する。空バッチと空集合取引は最初の trim で
直接処理され、式中の対数は必要に応じ `log(n+1)` と読む。

上限は word-RAM と通常の ordered set の一操作 `O(log(n+1))` を前提とする。
添字と ID は一 word、ell は固定定数である。実装の ell 上限は **8** であり、
数学的な任意固定 ell の式を、そのまま任意 ell の実装済み性能保証とは呼ばない。

`normalize()` は `(table, partition, logical value)` を比較し、R/W 内部の重複を
除いた後に `R=W` を確認する。ポインタ値で同一性を決めない。raw key の各成分は
64 bit のまま比較され、dense ID と subset key は 32 bit で保持される。
hash 値が衝突しても等値比較で区別するので、hash 衝突をキー同一性に利用しない。

索引化の費用には二つの留保がある。

- raw read/write 長を `r_t,w_t`、`A_raw=Σ(r_t+w_t)` とすると、現在の実装は
  `sort+unique` を使うため、正規化の費用は
  `O(Σ r_t log(r_t+1) + Σ w_t log(w_t+1))` に hash 索引化の平均的な
  `O(A_raw+n)` を加えたものになる。重複が任意多数ある raw 入力の全費用を
  正規化後の `A` の線形時間とは主張しない。raw の一時コピーも `O(A_raw)` である。
  主性能実験は重複キーを再抽選して raw 長を ell 以下にするので、この区別は
  固定 ell の主系列の漸近上限を変えない。
- raw key/ID の `normalize()` は `unordered_map` / `unordered_set` を使う。
  この raw 索引化の「期待時間」は通常の平均 O(1) hash 仮定を指し、本コードの
  固定 mix 関数が悪意ある入力に乱択ハッシュの保証を与えるという意味ではない。
  一方、正規化後の `Index::ids` と profile の `group_ids` は subset を比較する
  `std::map`、`check_batch()` の ID 重複検査も `std::set` である。
  構築時の辞書操作一回は決定的 `O_ell(log(n+1))`、追加の
  `O_ell(n log(n+1))` は以下の主上限に吸収される。**indexed Batch 以降は構築を含めて
  決定的な時間上限**であり、raw key 索引化についてだけ平均 hash 仮定を別記する。
  性能実験を始める前の理論監査で、この区別を実装にも対応させた。

空間 `O_ell(A+n)` は canonical な dense Batch、すなわちキー配列の長さ `K` が
実際の使用キー数で `K≤A` となる入力について述べる。`State` は長さ K の配列を使う。
`normalize()` はこの条件を満たす Batch を生成する。公開 `select()` の
`check_batch()` も A を独立に再計算し、配列確保前に `K≤A` を確認したうえで
すべての dense ID が実際に使われることを検査する。手作り Batch に未使用の
巨大なキー空間を宣言して、この空間上限を壊す入力は拒否される。

## 3. 正確な次数と lazy の限界

非空 `Q⊆S_t` に対し、生存取引のうち Q を含む個数を `C(Q)` とする。
集合和の包除原理から、生存 t について

```text
d(t) = Σ[∅≠Q⊆S_t] (-1)^(|Q|+1) C(Q) - 1.
```

和は少なくとも一つのキーを共有する取引を重複なく数える。t 自身も一回数えられるため
最後に 1 を引く。空集合取引はこの式の対象に入れず、事前に孤立確定する。
`Index` は各取引について `2^|S_t|-1` 個の incidence を構築し、`Index::degree()`
がその符号付き和を計算する。実削除は各 incidence の count を一度ずつ減らす。

過去に計算した degree は現在の degree の上界である。lazy heap の entry は
`(degree, ID, generation)` を持ち、先頭候補をその round で未再計算なら再計算する。
再計算後の `(degree,ID)` が次候補の上界以上なら確定できる。それ以外は heap に
戻して先頭を調べ直す。ID も比較する必要がある。古い degree が同じで ID が大きい
候補を無視すると全中止列が一致しなくなる。

`generation` は round の全削除後に一度だけ進む。同じ frozen round 中は degree が
変化せず、各候補を高々一度しか再計算しない。heap には候補ごとに高々一 entry があり、
trim された古い entry の回収も全期間で高々 n 回である。

それでも、全取引が同じ非空キー集合を持つ n 頂点 clique、k=1 では、
各 round で残り全員の古い上界が一段高く、ほぼ全員を再評価する。
初期 degree 計算を含む質問数は n≥2 で
`n+(n-1)+...+2 = n(n+1)/2-1` となる。lazy 単独には全中止列の
真の劣二次時間保証がない。`Stats::degree_queries` は初期計算を含み、audit 用の
独立質問は性能カウンタに加えない。

## 4. trim は全期間 O(A+n)

`State` の `count[key]` と `xors[key]` は、生存件数と生存**取引添字**の XOR を持つ。
`support[t]` は t のキーのうち、生存件数が 2 以上のものの個数である。
生存 t の degree が 0 であることと support が 0 であることは同値である。

構築時にキー incidence を二度走査し、support=0 を queue に入れる。
各 `State::erase(t)` は t のキーを一度走査する。件数が 2→1 になったキーでは
XOR から唯一の生存取引を得て、その support を一つ減らす。件数は減少しかしないため、
各キーの 2→1 は一度限りである。添字 0 も XOR で正しく復元できる。
queue は初期孤立取引または support が 0 になった取引に限られ、取引ごと高々一回である。

frozen 候補が一時的に唯一の生存取引となる場合も計数から外さない。その候補が
同じ round で中止・削除された後に queue から出た場合は `alive` を確認して飛ばす。
trim は全候補の実削除後にだけ実行するので、選択済み中止候補を確定へ変更しない。

したがって State のキー訪問は全取引を最後まで処理すると初期 `2A` と削除 `A` の
計 `3A`、そのほかは `O(K+n)` である。trim **検出機構**の総費用は `O(A+n)`。
trim が呼ぶ selector の削除更新は次節の全削除費用に含む。
round ごとの全取引・全キー走査はない。検査用 `audit_degrees=true` だけは
独立全相手検査を行うため、性能上限と性能測定の対象から外す。

## 5. heavy singleton profile による全削除の上限

一回の profile 構築時に残る取引数を `N` とする。最初から profile なら
初期 trim 後の `n0`、adaptive の切替えならその時点の残存数である。
ell は入力バッチ全体の最大 arity を保守的に使う。`N=0` では構築しない。

既定値は `B=ceil(N^((ell-1)/ell))`（最小 1）。構築時 count が B 以上の Q を
heavy、未満を light と分類し、その後の削除では分類を固定する。
`H` を heavy singleton の数とすれば

```text
H B ≤ Σ_key C0({key}) ≤ ell N,     H ≤ ell N/B.
```

heavy Q の各要素は必ず heavy singleton である。各取引を
`P_t=S_t∩K_H` で group 化する。すると t の heavy subset は、ちょうど
P_t に含まれる heavy subset なので

```text
common(P) = Σ[heavy Q⊆P] sign(Q) C(Q)
local(t)  = Σ[light Q⊆S_t] sign(Q) C(Q)
d(t)      = common(P_t) + local(t) - 1.
```

`Profile::groups[p].local` は `(local,ID)` の `std::set`、
`representatives` は各非空 group の代表 `(degree,ID)` の `std::set` である。
common は同一 group 内の全員への同じ加数であるため、代表だけ見れば
全候補の真の最大を得られる。削除途中は light 偶数サイズ subset の寄与が増える等、
部分和が増減するので local/common/count は `int64_t` で保持する。
途中で top 候補を質問せず、すべての subset 更新が済んでから次 round に進む。
検査用 `Profile::degree()` は subset 和だけでなく `local+common-1` も照合し、
二つの表現が同じバグで見逃されないよう独立の交差 degree と比較する。

### 5.1 構築と空間

`Index::Index()` は生存取引の各非空 subset を生成する。
subset 生成には mask ごとに ell 個のキー検査があり、費用は
`O(ell·2^ell·N)`、固定 ell では `O_ell(N)` である。
生成した subset の比較木による索引化まで含めると `O_ell(N log(n+1))` となる。
`nodes`、`incidence[t]`、`Node::posting` に保存する incidence の総数は
`M=Σ_t(2^|S_t|-1)≤(2^ell-1)N`。一つの subset が多数取引に現れても、
一取引内では一回しか posting に登録しない。

group は**実在する** P_t だけを作るので高々 N 個。
heavy subset→profile の接続 `Node::profiles` は、各実在 profile の subset を
一度列挙して構築する。全キーの組合せや全 profile 対を列挙しない。
接続総数 `L≤(2^ell-1)·#profiles≤(2^ell-1)N` である。
local 順位集合の全要素は高々 N 個、代表は group ごと一つ。
一時 `group_ids`、profile 署名、vector の capacity と各辞書・順位集合の木 node の
定数倍費用も固定 ell の線形範囲に入る。

State・Batch・commit mask・全中止列・証明書を含め、canonical な入力で
空間は `O_ell(A+n)`。巨大な暗黙グラフを別に保存する必要はない。
`index_payload_bytes` は payload の部分推定であり、辞書・順位集合の木 node、allocator、
State/Batch の全費用を網羅する peak memory ではない。実測の peak RSS は
DB・プロセス全体を含む別の値として読む。

### 5.2 light 更新

light Q の初期 posting 長は `C0(Q)<B` である。
`Profile::erase()` は Q の count を一つ減らすたびにその初期 posting を走査し、
現在 eligible な相手だけの local と代表を更新する。削除済み・候補除外済みの entry は
飛ばすが、走査自体も `light_scans` に計上する。posting を圧縮し直す必要はない。

一つの Q は高々 C0(Q) 回減らされるため、総走査回数は

```text
Σ_light Q C0(Q)^2 < B Σ_Q C0(Q) = B M = O_ell(N B).
```

各 eligible 相手の処理は定数回の local/representative 木操作なので、
light 全更新は `O_ell(N B log(n+1))` である。

### 5.3 heavy 更新

heavy なサイズ q の Q が含まれる profile P は、Q に残り H-q 個の heavy key を
高々 ell-q 個追加したものに限られる。従って接続先数は

```text
L_Q ≤ Σ[j=0..ell-q] binom(H-q,j) = O_ell(max(1,H)^(ell-q)).
```

実装は保存済み `q.profiles` だけを走査し、各接続先の common と代表を更新する。
空になった group の接続も走査回数へ含め、`heavy_updates` を増やす。
q≥1 と総 count 減少 M から、全 heavy 更新の粗い上界は

```text
O_ell(M · max(1,H)^(ell-1) · log(n+1))
  = O_ell(N · (1+(N/B)^(ell-1)) · log(n+1)).
```

light/heavy の両上界に `B=ceil(N^((ell-1)/ell))` を入れると、支配項は
`N^(2-1/ell) log(n+1)` となる。candidate の除外・trim での local からの削除は
全期間で高々 N 回。最後の証明書の ID sort は `O(n log(n+1))`。
初期検査・全削除・trim 検出・証明書・解放を合わせ、固定 ell で

```text
時間: O_ell(A + n^(2-1/ell) log(n+1))
空間: O_ell(A + n)
```

となる。この上限は indexed Batch 以降について構築も含む決定的なものである。
raw 入力から始める場合の正規化費用と平均 hash 仮定は第 2 節の通り。
繰返し全走査はテスト audit 以外にない。構築や切替えの最中には元バッチ長 n の
配列を走査するが、構築は高々二回であり合計 `O_ell(n)` に収まる。

ell=1 では B=1。全生存 singleton が heavy、各 transaction は一つの group に属し、
heavy singleton はその一 group しか更新しない。空集合は先に処理される。
従って `O(A+n log(n+1))`、ell=2 は `O(A+n^(3/2) log(n+1))` となる。
定数には subset の `2^ell` とその生成・比較費用等が含まれ、ell=6/8 の実測定数費用を
小さいものとは仮定しない。

テスト用 `profile_B=1/2` 等でも意味論は同じだが、この選び方には既定値の時間保証を
そのまま適用できない。例えば ell≥2 で B=1 にすると H の上界が線形になり、
上の heavy 粗い上界が大きくなる。特殊 B は正しさの検査で使用し、主実験では
`profile_B=0` の既定値を使う。

## 6. adaptive の切替えと round 内の超過

ell≥2 の既定予算は、初期 trim 後の `n0` を固定して
`D=n0·ceil(sqrt(n0))` 回の正確な degree 質問とする。
初期 heap 構築の n0 回も含む。ell=1 は最初から profile を使う。

一 round 中は graph の count が不変であり、lazy の generation も不変である。
再挿入された entry は同じ generation を保持するため、同じ eligible 取引を
二度再計算しない。従って round 全体の質問数は高々その round の残存数、つまり
高々 n0。k が入力に依存して大きくても `O(k n0)` に増えない。

予算到達の検査は、候補全削除、generation 更新、孤立 trim の**後**にある。
その直前の round 境界で D 未満なら、次の境界での超過は高々 n0。
初期 n0 回も D 以下なので、切替え前または終了までの質問数は
`D+O(n0)=O(n0^(3/2))`。一質問は `O_ell(1)` の subset 和と `O(log(n+1))` の
heap 操作、実削除の subset count 減少と heap の残骸回収は合計 `O_ell(A+n)` である。

切替え時は `scheduler.reset()` で旧 heap・subset 索引・posting を先に解放し、
残存状態から Profile を新たに構築する。解放と再構築は `switch_ms` に含み、
`switches`、`switch_round`、`switch_remaining`、`switch_queries` を記録する。
フラグにより切替えは高々一回。切替えなく終了した場合も、それまでの費用は同じ予算内。
全件消えた境界では無駄な profile 構築をしない。

ell≥2 では `3/2≤2-1/ell` なので、lazy 前半と profile 後半を合計しても
第 5 節の時間上限内である。二構造を同時に保持せず、空間も同じ線形上限内に収まる。
強制予算 0/1 は round 境界で切替えることを検査するための設定であり、
主実験の既定予算を結果に応じて変更するものではない。
通常入力で一度も切替えなければ、その測定値の改善は lazy 経路によると解釈する。

## 7. graph baseline と容量

`Graph` は初期 trim 後の N 頂点に bitset 行を持つ。
キー posting の bitset を各取引の行へ OR することで重複辺を除き、自分の bit を消す。
次数を初期化し、順位を木で維持する。実削除後は `live_bits` と隣接行の AND により
生存隣接頂点だけの degree を減らす。全取引対の再計算を毎 round 行う oracle を
性能 baseline に流用していない。

bitset 本体は `8·N·ceil(N/64)` bytes。構築は固定 arity で概ね
`O(A·ceil(N/64)+N·ceil(N/64)+n log(n+1))`、全削除は行 word 走査と各辺の
更新に応じた費用を持つ。profile の線形空間保証はこの明示グラフ方式には適用しない。
bitset 確保、構築、degree 初期化、更新、trim は測定内である。
この一実装を最速の既知グラフ方式とは主張しない。

既定で最大 arity 8、subset incidence 合計 8,000,000、取引数 1,048,576、
dense key 数 8,388,608、graph 本体 512 MiB の上限を検査する。
arity を検査してから subset mask を shift し、合計 incidence の加算前に残予算を確認し、
bitset の積による確保は除算した予算と比較する。上限超過・不正入力は
`Unsupported` で拒否する。容量制約を満たす実行についての計数上限であって、
任意規模の入力を無条件に処理できるという約束ではない。

## 8. HSC からの帰着

HSC は証明済みの定理ではなく仮定である。
[On Complexity of 1-Center in Various Metrics, Definition 7](https://drops.dagstuhl.de/storage/00lipics/lipics-vol275-approx-random2023/LIPIcs.APPROX-RANDOM.2023.1/LIPIcs.APPROX-RANDOM.2023.1.pdf)
（PDF 6 ページ）を一次資料として確認した。任意の `epsilon>0` に対しある `c>1` が
存在し、宇宙 `[c log m]` 上の m 集合ずつの族 A/B について、B の全集合と交わる
集合が A にあるかを `O(m^(2-epsilon))` 時間では一般に決定できない、という量化である。
SETH そのものと同一視しない。以下の取引 gadget は Issue の構成を本書で検証したもので、
この引用論文に記載された EAS の定理ではない。

### 8.1 前処理と構成

m≥1 とする。まず A の union を作り、その union と交わらない B_j があれば NO と返す。
この場合どの A_i も B_j に当たらないので、正しい即時 NO である。
indexed な宇宙での前処理は入力 incidence に線形で、`O(m log m)` 時間・空間内。
残りについて入力宇宙と異なる五つのキー `x,y,h,l0,l1` を用意し、全取引を R=W=S とする。

| 族 | 個数 | S |
| --- | ---: | --- |
| X_i | m | A_i ∪ {x} |
| Y_j | 各 j 二取引、計 2m | B_j ∪ {y} |
| D0,D1 | 2 | {x,l0}, {x,l1} |
| C0,C1 | 2 | {h,l0}, {h,l1} |
| その他 C | 3m−2 | {h} |

Y の二コピーは同じ署名でも異なる ID を持つ別頂点である。C も同様。
頂点総数 `n=6m+2`、片側のキー incidence は
`Σ|A_i|+2Σ|B_j|+6m+6`。read/write を両方数えた総アクセスは

```text
2Σ|A_i| + 4Σ|B_j| + 12m + 12 = O(m log m).
```

最大 arity は高々 `max(c log m+1,2)=O(log n)` である。
入力コピーと固定 gadget の生成も `O(m log m)` なので、帰着で二次時間の
明示グラフを構築する必要はない。以下のグラフ構築は証明と小入力検査でのみ行う。

### 8.2 全辺・連結性・次数

X 族は x、Y 族は y、C 族は h を共有し、それぞれ clique。
X_i と Y_j の各コピーは元集合が交わるときだけ結ばれる。
両 D は全 X と互いに結ばれ、D0–C0 と D1–C1 のみが l の橋となる。
それ以外の族間辺と自己辺はない。

X・D・C はこの橋で連結であり、前処理を通ったすべての B_j は少なくとも一つの
A_i と交わるので、Y 全体も X に接続する。従って全体が連結であり、辺が双方向なので
一つの SCC である。孤立点の初期 trim で gadget が消えることはない。

`h_i=|{j:A_i∩B_j≠∅}|` とすると、集合交差で定めた全辺から

```text
d(X_i)       = (m−1)+2+2h_i = m+1+2h_i
d(Y_j copy)  = (2m−1)+|{i:A_i∩B_j≠∅}| ≤ 3m−1
d(D0)=d(D1)  = m+1+1 = m+2 ≤ 3m
d(C0)=d(C1)  = (3m−1)+1 = 3m
d(other C)   = 3m−1.
```

YES なら少なくとも一つの X_i が degree `3m+1` を持ち、非 X はすべて `3m` 以下。
従って最初の最大候補は必ず X。NO ならすべての h_i≤m−1 なので X は
`3m−1` 以下、C0/C1 は `3m`。従って最初の最大候補は必ず非 X。
さらに C0/C1 が二つあるため、NO の frozen top-2 に X は入らず、YES では
少なくとも最初の一件が X。どちらも同点の ID 選びに依存しない。
m=1 の端点でも式は成立し、前処理を通る m=1 入力は YES である。

### 8.3 何が条件付きで排除されるか

仮に、対数 arity を許すこの完全 RMW 入力族で最初の正確な top-1 または frozen top-2 を
一般に `O(n^(2-epsilon))` で返すアルゴリズムがあれば、前処理と構成を含めて
Hitting Set を `O(m log m + m^(2-epsilon))` で判定できる。
必要なら epsilon を小さく固定し直せば、これは真の劣二次時間となり HSC に反する。
全中止列を返すアルゴリズムも、その出力から最初の候補を得られるので同じ制限を受ける。

これは HSC が正しければ、ある対数 arity の族に一般的な真の劣二次解法がないという
条件付き限界である。固定 ell の `2−1/ell` という指数の最適性は証明していない。
中間の全 arity を分類したわけでもない。`O_ell` の定数には指数的な ell 依存があり、
固定 ell の式へ `ell=log n` を代入して劣二次保証を導くことはできない。
現在の実装の ell≤8 という有限検査から、この漸近下限を実証したともいえない。

## 9. 独立した HSC 有限検査と再現

[tests/test_hsc.py](../tests/test_hsc.py) は Python 標準ライブラリだけを使い、
selector・subset index・degree 計算を import しない。以下を**順序付き族**として
全列挙する。同一集合の繰返し、空集合、A/B 間の重複を除外しない。

| 宇宙サイズ | m | 入力件数 |
| --- | --- | ---: |
| 0 | 1,2,3 | 3 |
| 1 | 1,2,3 | 84 |
| 2 | 1,2,3 | 4,368 |
| 3 | 1,2 | 4,160 |
| 合計 | | **8,615** |

元 Hitting Set の YES/NO は素朴な `any(all(A_i∩B_j))` で判定する。
前処理を通る入力は実際の R/W 集合を作り、全順序付き頂点対の交差から全辺を作る。
その graph を、別途予測した gadget の辺関係、上の次数式、アクセス総数と比較する。
正向き・逆向き双方の到達可能性を調べて一 SCC も検査する。
top-1 と frozen top-2 は graph の degree から計算し、degree の同点で許される
**すべての選択肢**を列挙する。ID の昇順付与・逆順付与の二通りでも確認する。

保存済み [hsc.json](../experiments/eas/validation/hsc.json) と
[hsc.log](../experiments/eas/validation/hsc.log) の実行結果は次の通り。

- 8,615 入力を生成・検査。空集合を含む 5,343 入力、同じ族内に重複を含む 4,670 入力。
- 前処理 NO は 4,581。残る 4,034 構成は YES 3,790 / NO 244。
- 全順序付き頂点対 1,078,892、自己辺なし・対称性・全辺関係を照合。
- 64,858 頂点の全次数を照合。read/write の総アクセス計 247,752 を式と照合。
- 4,034 構成の連結性・SCC・アクセス総数をそれぞれ検査。
- top-1 の同点選択肢 6,029、frozen top-2 の同点選択肢 8,766 をすべて検査。
- ID 付与二通りの確認 8,068 件。すべて PASS、反例なし。

再現コマンド（repository root、Python 3、追加 package 不要）:

```sh
python3 tests/test_hsc.py
```

既存の記録を保持して再実行する場合:

```sh
python3 tests/test_hsc.py --output /tmp/eas-hsc-repeat.json --log /tmp/eas-hsc-repeat.log
```

JSON は列挙条件、期待件数と実件数、実行コマンド、Python version、script SHA-256、
実測時間を含む。失敗すれば該当する具体的 A/B とエラーを JSON に保存する。
この全列挙は有限範囲で構成の間違いを探す検査であり、HSC の証明でも、
漸近下限の実験による証明でもない。帰着の全入力に対する根拠は第 8 節の議論である。
