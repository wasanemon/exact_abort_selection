# Fabric系候補の一次資料・公開実装監査

監査日: 2026-09-05。Issue #3開始点 `d150211968ef6d61efda82f9f44f63e3bac28b44` の
`REPORT_policy_comparison_ja.md` と `next_stage.json` を先に読んだ。
本監査は公開資料の取得・コード読解まで。build、Docker起動、scheduler改変、移植、性能測定は行っていない。

## 判断

**Fabric++とFabricSharp本来のschedulerへの現EAS直接移植はNo-Go。**
両者とも実際にgraphを構築するのでNeedはある。一方、Fabric++はcycle参加数を使い、
FabricSharpは到着時cycle拒否・複数snapshot・過去blockへの到達可能性を扱う。
現EASの最大残存degree/frozen top-k中止を代入して既存decision保存とは呼べない。
同じ入力に対してorderer間で同じ結果を出す要請は実在するが、EASのpolicyを選ぶ固有の理由ではない。
#3の安いpolicyへの不利を、このtarget変更だけでは解消しない。

**ただし、FabricSharpに同梱されたFocc-latestはDing系の実在する第三者実装であり、
限定したpolicy保存の需要を裏付ける資料になる。** 同schedulerはsum-degreeを使い、
同点では到着順の先頭を中止する。complete-RMWならproductとの順位差は消えるが、
現EASの大ID中止との同点差は残る。Ding原著artifactとは呼ばず、独立した適合証明と
priority対応が必要である。[Focc-latest実装][FL]

## 論文・artifactの同定

|対象|確認した一次資料・commit|注意点|
|---|---|---|
|Fabric++|Sharma, Schuhknecht, Agrawal, Dittrich, **Blurring the Lines between Blockchains and Database Systems: the Case of Hyperledger Fabric**, SIGMOD 2019, DOI `10.1145/3299869.3319883`。[著者版18頁PDF][FP19]。公開source `shankur/fabric` master `bef689d1cf3daadccbe573f5d4ea860934e22d5c`（2019-05-28）|arXiv `1810.13177v1` は旧題 **How to Databasify a Blockchain: the Case of Hyperledger Fabric**、2018-10-31、28頁。最終版とは節番号・評価が異なる。最終版§5.1/Algorithm 1に対応する旧版は§4.1/Figure 5。`sh-ankur/fabric` は現在 `shankur/fabric` へredirectする。|
|FabricSharp論文|Ruan, Loghin, Ta, Zhang, Chen, Ooi, **A Transactional Perspective on Execute-order-validate Blockchains**, SIGMOD 2020。[arXiv `2003.10064v1`][FS20]、19頁|このarXiv番号はFabric++の論文ではない。|
|FabricSharp論文専用branch|`ooibc88/FabricSharp` sigmod20 `fc639da4cd36aa85f3cb8cd9924e24d061ff2146`（2021-03-02）|[README][FSR]が論文・Sharp/Focc-standard/Focc-latest・Fabric++原著repoを直接対応付ける。Makefile L47 はFabric 1.3.1。|
|FabricSharp master|`b6011f90c41b79d670fc52d6ee6f92f8046c6674`|Fabric 2.2、provenance/ForkBase等を統合した別系統。[README][FSM] L20–21のclosed-source/Docker制約をsigmod20へ一律に移してはいけない。|

保存資料のURL・SHA256・bytesは
[`fabric_sources_manifest.json`](../experiments/target_selection/sources/fabric_sources_manifest.json)。
PDF本文は原bytesと`pypdf`抽出textを保存した。抽出text中の`=== PDF PAGE N ===`が1始まりのPDF頁番号。
最終Fabric++ PDFには埋込みfont由来の抽出警告・欠字があり、式の読解はPDFまたは公開コードを優先する。

## 本当に払っているgraph費用とRW-set取得時点

|対象|実際の経路・保存箇所|policyと費用の範囲|
|---|---|---|
|Fabric++|`blockcutter.ProcessTransaction` L133–154がendorsement結果のEnvelopeから`TxRwSet`を抽出し、L143–144/178–179/216–217でR/W bitsetを作る。`ProcessBlock` L346–367がn×nを走査し、各pairのwrite/read bitset交差で`graph`/`invgraph`へ辺をappendする。[code][FPBC]|各隣接sliceのcapacityをnにするL349–350により、辺が疎でも前後graphのcapacityは二次規模。`resolver.GetSchedule` L39–45がJohnson cycle breakerを実際に呼ぶ。[resolver][FPR]。graph構築だけをなくしてもcycle列挙が残る。|
|Fabric++ cycle breaker|`johnsonce.FindCycles` L77–117はcycle listとcycle×vertex membershipを保存し、`BreakCycles` L176–203が残存cycle参加数最大を選び、そのcycle分を全頂点から引く。[code][FPJ]|最終論文§5.1/Algorithm 1にもTarjan SCC→Johnson全cycle→cycle参加数最大中止→topological orderを記述。残存相手数・prod-degree・frozen top-kとは異なる。|
|FabricSharp Sharp|`blockcutter.scheduleMsg` L84–112はsimulation結果のRW-setとsnapshotをordererの`ProcessTxn`へ渡す。`Cut` L171–179が`ProcessBlk`のschedule順にEnvelopeを並べる。[blockcutter][FSBC]|全取引のRW-setが実行前に既知という前提ではない。simulation/endorsement後、ordering中には実際のpoint read/write listがある。コードはfirst namespaceだけを取るL98、txn IDは8文字prefix L81。汎用multi-namespace APIとして無条件に再利用しない。|
|FabricSharp Sharp graph|`sharpscheduler.ProcessTxn` L106–139がLevelDB過去取引・pending per-key indexから依存を求め、L157–162がpred×succのreachabilityで到着取引を拒否する。L174–206はsuccessor listを更新しBFS、L214–240はpending全頂点を走査しreachability edgeを`Graph.AddEdge`へ保存する。[Sharp][FSS]|`common.Graph` L195–204は`outputs map[string]map[string]int`と入力次数、L241–256が実際の辺map挿入。[構造][FSD]。論文§4.4のdirect successors＋Bloom reachabilityに加え、実装ではpending schedule用graphもmaterializeされる。単純な全相手交差graphだけではない。|
|Focc-latest|`latestscheduler.computeDep` L60–90がキーごとのread×writeを列挙しpred/succのTxnSetへ重複を除いた辺を追加。L108で`ProcessBlk`が呼ぶ。[code][FL]|L113–143で繰り返しsourceをscheduleし、L145–175で全未処理取引の残存in+out degreeを隣接setから数え直す。構築＋選択の費用がsource上で直接確認できる。主Sharpがこのpolicyを使用するわけではない。|

以上のNeedは実行経路の構造の確認であり、本環境でのbottleneck比率の実測ではない。
FabricSharp論文§5.3/Figure 11はFocc-lのreordering費用が大きく、Sharpは到着時処理へ費用を移すと説明する。
新しい測定でなく原論文の観測であり、block formation時間だけを比較すれば費用を取り落とす。[論文][FS20]

## Semantic fitとexact policy preservation

1. **Fabric++**: 一般R/Wでは向き付きedgeがあり、reorderingにより両方commitできるpairがある。
   同snapshotのcomplete-RMWに制限すればedgeの有無は`S_i∩S_j≠∅`で対称になり、
   cycle-freeな残存集合は独立集合になる。しかし長いcycleも存在し、cycle参加数は次数ではない。
   最大次数中止への変更は既存policy保存の証明にならない。
2. **Sharp**: 論文Algorithm 1は取引ごとのsnapshotを固定するが、batch全体が同snapshotとはしない。
   Algorithm 2は既にcommitした取引とpending取引をまたぐcycleを扱い、pending c-wwを一旦除外し、
   Algorithm 3/5でcommit順に戻す。§4.4とcode L67–70/L214–224はBloom false positive由来の
   追加abortも扱う。既存EASはmulti-version reachabilityやこのfalse-positive behaviorを保存しない。[論文][FS20] [code][FSS]
3. **Focc-latestの限定一致**: complete-RMWなら各残存頂点で`d_in=d_out=d`。
   `d_in+d_out=2d`と`d_in*d_out=d²`の順位は非負整数上で一致する。
   source pruningは`d=0`を消すだけで残存の次数を変えないため、k=1の非zero頂点除去policyは、
   **同点規則まで一致させた場合に限り**同じ判断へ還元できる。
   ところがcode L148のpending到着順走査とL168のstrict `<`は最大値が同点なら最初の取引を中止する。
   例えば到着順`[1,2]`, `S_1=S_2={a}`ならFocc-latestは1を中止し2を残す。
   現EAS（大IDを中止）は2を中止し1を残す。公開codeが存在することだけで既存EASとのexact一致とは言わない。[code][FL]

Sharp論文§3.5は、consensus後の同じ取引streamからhonest ordererが同じledgerを得る要請を説明する。
コード`common.Graph.ToposortWithLimit` L288–291もdeterministic順のためのsortを明記する。
これはrepresentation変更で同decisionを保つ価値の根拠だが、Focc-lのsum-degreeやEAS自体を永続的に
維持しなければならない運用・priority契約の確認ではない。[論文][FS20] [code][FSD]

## fixed-small-accessと自然な密度

sigmod20の[`custom.go`][FSC] L63–74には1key `GetState→PutState`があるが、書込みは固定`empty`で、
本体がread値に依存する重いbanking transactionの実測ではない。
READMEはこれをFigure 1用とし、残りの主図には`ReadWrite`を使うと明記する。
`ReadWrite` L78–120はread listとwrite listを別に受け取り、R=Wを要求しない。
論文§5.2は1万account中各4read/4write、hot account 1%を使う。
従ってsmall-access・hotspotは自然な候補条件だが、その主系列全体をarity4 complete-RMWとして再現してはならない。
§5.5の元Smallbank混合もread-onlyを50%含み、batch全体がcomplete-RMWではない。[論文][FS20] [README][FSR]

一方、masterの[`benchmark/smallbank/smallbank.go`][FSB]にはより直接的な形状がある。
`loadAccount` L228–239はaccount IDをkeyにしてGetState、`saveAccount` L242–248は
同じ保存IDでPutStateする。正常な初期化済みaccountについて、DepositChecking L88–103、
WriteCheck L106–121、TransactSavings L124–140は1accountの値に依存するRMW。
SendPayment L143–166とAmalgamate L169–191は両端accountのloadとsaveで、異なる両端なら2key RMW。
同一両端は正規化後1keyになるため固定arity2測定では区別する。
Query L194–201はread-only、CreateAccount L60–85はwrite-onlyなので混ぜない。
README L62はこのcodeをSIGMOD 2021のoriginal Fabric 2.2比較用と位置付ける。
これは**自然な1/2key shapeの証拠**であり、sigmod20主図のtraceを取得・再現した証拠ではない。[README][FSM]

hot accountの再利用は密な交差graphを生み得る。ただしSharpは到着時にcycleを拒否するため、
accepted pendingのgraph密度と、abort前の全要求graph密度は別物である。
自然workloadで現EASの費用を回収できるほどのcommit利得が残るかは未測定。
#3のstatic/accept_idとの不利を、小さいアクセス数や密度だけから覆さない。

## Artifact・依存・評価費用

|対象|公開性・build証拠|本Issueでの評価|
|---|---|---|
|Fabric++|原著repo取得成功、root LICENSEはApache-2.0、対象Go sourceにもSPDX。READMEはHyperledger codeをApache-2.0と記し、冒頭にSaarlandのAll rights reservedも残す。旧FabricのMakefile/Gopkg/vendorあり。|本監査でbuild未実行。公開scheduler単体を読む/再現することは可能。旧Fabricネットワーク再構築を先行させない。|
|Sharp master|root README L20–21がForkBase closed-sourceとDocker内build/runを明記。L41–46はstateDB/scheduler互換性とMV_STORE_PATHを記述。|closed dependencyは主にこのbranchの減点。closedだからrepository全体実行不能とは断定しない。|
|Sharp sigmod20|README L8–18が通常の`make peer`/`make orderer`とDocker双方を案内。`common/mv_store.go` L7–24は公開goleveldbを利用。参照したMakefile/images/statedbでForkBase依存は見つからなかった。|masterの閉源依存をNo-Goの唯一の理由にしない。旧環境のbuild成功は未確認。scheduler内部ログ・analysis scriptsがあるため測定設計は可能。|
|Focc-latest|上記sigmod20に公開。`ProcessTxn`/`ProcessBlk` API、構築・prune/filterの内部時刻ログがある。|standalone reproductionが可能でも原著Ding DBMS end-to-end改善にはならない。既存policy保存の限定仮説はDing候補側で別評価できる。|

Sharp constructorは保存pathを削除する（`sharpscheduler` L41–46）、READMEも同動作を明記する。
本監査はconstructorを起動していない。実験する場合は実験専用pathを使い、その初期化費用を区別する。
これは既存codeの再現上の注意であり、ユーザーに未要求の大規模環境構築を求める理由にはしない。

## 2024–2026追加探索で残った関連候補

探索日は2026-09-05。語句・検索範囲・取得失敗は
[`fabric_recent_search.json`](../experiments/target_selection/sources/fabric_recent_search.json)へ記録。
完全な文献網羅性や新規性の認定は行わない。

|資料|確認範囲と本研究への含意|
|---|---|
|**FabricMan**, *Optimization of High-Concurrency Conflict Issues in Execute-Order-Validate Blockchain*, ZTE Communications 2024, DOI `10.12142/ZTECOM.202402004`|[出版社abstract][FM]はblock内reorder/parallel validation、transfer merge、block間version-cacheの組合せ。公開full paper/codeは今回の取得では未確認。mergeは本体意味論を変えて利用する別方向であり、graphの語だけでEAS適合とはしない。|
|**RapidSnail**, IEEE TC 75(1), 261–274, 2026（early online 2025-10-28）, DOI `10.1109/TC.2025.3625641`|[共著者所属大学の書誌・abstract][RS]は未commit値で実行し、new RW-set representation / effect-based graphを使う。単一snapshotのcomplete-RMWとは前提が異なる。本文・artifact未確認なのでsubsumptionや性能を判断しない。|
|**Fabric-X**, SIGMOD 2026 Industry *Scaling Hyperledger Fabric for Asset Exchange*|[公式conference accepted list][FXCONF]で2026 paperを確認。公開[`fabric-x` README][FX]はdependency graphを使う並列validationとdeterministic outcomeを説明。[`fabric-x-committer` README][FXC]はordererの順に既使用tokenを判定する。優先順位保存の実需要はあるが、この確認範囲ではFVS/最大degree中止を必要としない。small UTXO/RMWを同一扱いせず、初期screeningに留める。READMEはcommit固定して保存、paper PDFは403で未取得。|
|**FlexTender**, *Back to the Future: Rethinking Endorsement in Order-Execute Blockchains*, 2026-04-30|[arXiv一次abstract][FT]はChainMaker/Tendermintのorder-executeにendorsementを組み込む。EOV simulationとの比較であり、一般EOV改善やEASの優位の証拠として転用しない。abstract HTMLを保存、本文/code詳細監査は未実施。|

## Gate結果

|Gate|Fabric++|Sharp本来のscheduler|Focc-latest限定subset|
|---|---|---|---|
|1 Semantic fit（必須）|complete-RMWでもcycle-count policyが違う。現EAS直接置換不合格。|一般RW・複数snapshot・Bloom reachability・到着時判断の拡張が未証明。不合格。|同snapshot/complete-RMW/k=1でsum/product順位は一致。先着同点を対応させる証明・oracleが条件。|
|2 Need（必須）|pair graph＋cycle membershipをsourceで確認。|pending reachability graph＋BFS/LevelDB依存をsourceで確認。|明示pred/succ構築＋反復次数scanをsourceで確認。|
|3 Policy value|既存ledger決定の再現価値はあるが最大degreeは既存policyではない。|replica determinismはあるがEASは別decision。|既存比較baselineの同decision保存には限定価値。現EAS選択の品質優位は未確認。|
|4 Baseline relevance|accept系/CFBS・static・matchingとの有効比較が必要。|同じ意味論で比較しないとcheap baselineが過剰abortし得る。|#3のcheap系を含めてpolicy品質が劣る条件も示す必要。|
|5 Evaluability|原著sourceあり、build未確認。|sigmod20 sourceあり、master依存と区別。|忠実standalone可能。ただし本監査では実装しない。|
|実装判断|現EAS移植No-Go|現EAS移植No-Go|Ding系の限定検証を支える資料。Fabric全system統合のGoではない。|

研究の強い候補は「実在するselector/validator decisionを固定したrepresentation変更」であり、
Fabricの一般reordering問題を既存EASの対称次数問題に読み替えることではない。
自然な1/2key RMWは確認できたが、same-snapshot subsetの出現割合、既存schedulerへの寄与、
cheap policyを入れた有効処理率は未確認である。

## 再確認コマンド

読み取りcloneは`/tmp`で実施。network sandboxのDNS制約後、公開source取得を認可された
`require_escalated`で再実行した。外部への書込みはない。

```bash
git ls-remote https://github.com/ooibc88/FabricSharp.git refs/heads/master refs/heads/sigmod20
git clone --depth 1 --branch sigmod20 https://github.com/ooibc88/FabricSharp.git /tmp/issue4-fabricsharp-sigmod20
git clone --depth 1 https://github.com/sh-ankur/fabric.git /tmp/issue4-fabricpp
git -C /tmp/issue4-fabricsharp-sigmod20 log -1 --format='%H %aI %cI %s'
git -C /tmp/issue4-fabricpp log -1 --format='%H %aI %cI %s'
rg -n 'graph|cycle|degree|Greedy' /tmp/issue4-fabricsharp-sigmod20/orderer/common/blockcutter/scheduler
rg -n 'graph|cycle|degree' /tmp/issue4-fabricpp/orderer/common/blockcutter /tmp/issue4-fabricpp/orderer/common/johnsonce
```

保存sourceは各URLのcommitを固定しているため、再clone時のbranch先端が変化していれば
保存manifestのcommitをcheckoutする。SHA256照合はnetworkなしで可能。

```bash
python3 - <<'PY'
import hashlib, json
from pathlib import Path
m=json.loads(Path('experiments/target_selection/sources/fabric_sources_manifest.json').read_text())
for x in m['sources']:
    p=Path(x['path'])
    assert p.stat().st_size == x['bytes']
    assert hashlib.sha256(p.read_bytes()).hexdigest() == x['sha256'], p
print('Fabric source hashes OK:', len(m['sources']))
PY
```

[FP19]: https://bigdata.uni-saarland.de/publications/mod485-sharma.pdf
[FS20]: https://arxiv.org/pdf/2003.10064v1
[FPBC]: https://github.com/shankur/fabric/blob/bef689d1cf3daadccbe573f5d4ea860934e22d5c/orderer/common/blockcutter/blockcutter.go#L133
[FPR]: https://github.com/shankur/fabric/blob/bef689d1cf3daadccbe573f5d4ea860934e22d5c/orderer/common/resolver/resolver.go#L39
[FPJ]: https://github.com/shankur/fabric/blob/bef689d1cf3daadccbe573f5d4ea860934e22d5c/orderer/common/johnsonce/johnsonce.go#L176
[FSR]: https://github.com/ooibc88/FabricSharp/blob/fc639da4cd36aa85f3cb8cd9924e24d061ff2146/README.md
[FSM]: https://github.com/ooibc88/FabricSharp/blob/b6011f90c41b79d670fc52d6ee6f92f8046c6674/README.md
[FL]: https://github.com/ooibc88/FabricSharp/blob/fc639da4cd36aa85f3cb8cd9924e24d061ff2146/orderer/common/blockcutter/scheduler/latestscheduler/scheduler.go#L60
[FSS]: https://github.com/ooibc88/FabricSharp/blob/fc639da4cd36aa85f3cb8cd9924e24d061ff2146/orderer/common/blockcutter/scheduler/sharpscheduler/scheduler.go#L76
[FSBC]: https://github.com/ooibc88/FabricSharp/blob/fc639da4cd36aa85f3cb8cd9924e24d061ff2146/orderer/common/blockcutter/blockcutter.go#L84
[FSD]: https://github.com/ooibc88/FabricSharp/blob/fc639da4cd36aa85f3cb8cd9924e24d061ff2146/orderer/common/blockcutter/scheduler/common/ds.go#L195
[FSC]: https://github.com/ooibc88/FabricSharp/blob/fc639da4cd36aa85f3cb8cd9924e24d061ff2146/supplementary/contract/custom.go#L63
[FSB]: https://github.com/ooibc88/FabricSharp/blob/b6011f90c41b79d670fc52d6ee6f92f8046c6674/benchmark/smallbank/smallbank.go#L88
[FM]: https://www.zte.com.cn/global/about/magazine/zte-communications/2024/en202402/special-topic/en20240204.html
[RS]: https://scholars.hkbu.edu.hk/en/publications/rapidsnail-improve-scalability-of-blockchain-under-high-contentio/
[FXCONF]: https://2026.sigmod.org/sigmod_industry_papers.shtml
[FX]: https://github.com/hyperledger/fabric-x/blob/658ace9f69c6b682422294a17979d0930c3e20a1/README.md
[FXC]: https://github.com/hyperledger/fabric-x-committer/blob/7ca0d43148e90df697b8b3a2cd0b1cd4db6d25a0/README.md
[FT]: https://arxiv.org/abs/2604.27659
