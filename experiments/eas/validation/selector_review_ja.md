# Selector の独立検証と実装監査

`tests/eas_selector_test.cpp` は `eas/Oracle.cpp` の素朴な集合交差・毎 round 全再計算を基準とし、graph/lazy/profile/adaptive の round 境界付き中止列、commit mask、昇順証明書を比較する。oracle は dense-key 正規化、subset index、trim queue、候補順位構造を共有しない。元の論理キーを用いた独立の証明書検査で、確定取引のキーが互いに素であり、各 ID がちょうど一度 commit/abort に分類されることも確認する。

## 検査範囲

- 全列挙: キー宇宙 3・バッチ長 0～4 の全 ordered batches と、キー宇宙 4・バッチ長 0～3 の全 ordered batches。空集合・同一署名を含め、9,050 batches。
- ランダム: 4 固定 seed × ell=1～4 × 64 batches、計 1,024 batches。n=1～48、可変 arity、重複操作、ID 順と物理配置順の相違を含む。
- 個別例: wedge、frozen top-2、zero commit、64-bit 最大値と table/partition の区別、ell=1/2/3/4/6/8 の同一署名・非競合・複数成分・重複競合、default adaptive の実切替え。29 batches。
- 各入力で k=1/2/3/n+1、profile B=1/2/default、adaptive budget=0/1/default。テスト用 B の結果に既定 B の漸近保証を適用しない。
- 毎 round、全生存相手との直接交差から求めた degree と scheduler の degree を比較。profile ではさらに `local+common-1` と subset-count degree の一致を確認。
- 不正設定・非 RMW・remote/range・重複 ID・arity/incidence/graph/transaction/key 容量・不正な正規化 metadata を明示拒否。最終版は 35 rejection checks。

全 10,103 batches から、oracle 40,412 回、selector 323,296 回、round degree audit 696,640 回、adaptive の切替え観測 26,879 回となった。JSON の件数は実際に実行したループから集計し、固定値の期待結果を表示していない。`selector_release.jsonl` と `selector_asan_ubsan.jsonl` に結果を保存する。

## 発見した入力検証の不備と修正

以前の `select(Batch, Options)` は、手作り Batch に実際には存在しないキー数を宣言しても受理した。最小例は `ids=[]、keys=[]、key_count=1、accesses=0` であり、同じ形で `key_count` を容量上限まで増やすと空入力に対して大きな State 配列を確保できた。正規化済み入力の `O(A+n)` 空間前提を API 境界で保証できていなかった。

`selector_metadata_before.jsonl` は修正前の validation guard を復元した一時ソースを使った反例の実行結果、`selector_metadata_after.jsonl` は修正後の実ソースによる明示拒否である。反例の全入力を両ファイルに含めた。修正は、独立に再計算した総アクセス数に対して `key_count<=accesses` を検査し、その後に used 配列を確保して全 dense ID の使用を確認するもの。末尾の未使用 ID と途中の穴も拒否する。この追加走査と配列は `O(A+n)` である。

有効入力について、最適化 selector と oracle の不一致は発見しなかった。

## 全走査・記憶量の監査

`State` は各キーの count/XOR と取引の support を使い、各キーの 2→1 遷移でのみ孤立候補を追加する。テストは `trim_key_visits == 3*A` を毎回検査する。構築時 2 回・実削除時 1 回であり、全 round の全取引再走査を trim に含めていない。

`Index` は実在取引の非空 subset のみ、`Profile` は実在 profile とその subset のみを作る。subset/profile の索引は `std::map`、正規化済み Batch の ID 重複検査は `std::set` とし、構築を決定的な `O_ell(n log n)` に収めた。raw 論理キーと raw ID の正規化だけは hash の期待時間を仮定する。この構造選択は性能測定開始前に理論との対応のため決定した。light は初期 posting、heavy は事前構築した subset→profile 接続のみを更新する。`Profile` 内の集合と代表集合は ordered set。全キー組合せ・全 profile を削除ごとに走査する経路はない。

`Lazy` は取引ごとに heap entry を一つだけ保持し、各 generation 中に同じ取引の degree を繰り返し再計算しない。選択済み候補を heap/set から外しても、全 top-k の選択完了まで subset counts と alive は保持する。したがって切替え予算を跨ぐ一 round の追加 degree 質問は O(n0)。ただし、lazy 単独の全期間には二次回数があり得る。

adaptive は round 終了・全実削除・trim 完了後に一度だけ再構築し、旧 scheduler を先に解放する。初期構築と一回の再構築の全取引走査は O(n)。証明書の最終走査と sort は O(n log n)。`audit_degrees=true` の全相手走査はテスト専用であり、既定値 false の性能実験には入らない。

`index_payload_bytes` は index の要素 payload の概算で、map の tree node、allocator の管理情報、State、Batch、全 ordered-set 要素を網羅する heap 実測値ではない。プロセス全体の RSS と同一視しない。

## 再現コマンド

リポジトリ root で実行する。C++14 compiler 以外の外部依存はない。

```sh
mkdir -p experiments/eas/validation
g++ -std=c++14 -O2 -g -Wall -Wextra -Wpedantic -I. eas/Selector.cpp eas/Oracle.cpp tests/eas_selector_test.cpp -o /tmp/eas_selector_test
/tmp/eas_selector_test > experiments/eas/validation/selector_release.jsonl
g++ -std=c++14 -O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined -I. eas/Selector.cpp eas/Oracle.cpp tests/eas_selector_test.cpp -o /tmp/eas_selector_test_asan
ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 /tmp/eas_selector_test_asan > experiments/eas/validation/selector_asan_ubsan.jsonl 2> experiments/eas/validation/selector_asan_ubsan.stderr
```

最初は `detect_leaks=1` でも試行したが、環境の ptrace 制約により LeakSanitizer が終了時に fatal error となった。`selector_lsan_attempt.stderr` に実エラーを保存した。そのため ASan/UBSan は leak detection を無効化して全件実行する。これは address/undefined 検査を無効化するものではない。リーク検査の成功は主張しない。sanitizer 実行は性能測定に含めない。
