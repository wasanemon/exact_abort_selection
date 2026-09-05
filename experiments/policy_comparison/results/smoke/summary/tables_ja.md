# 同一seed内3反復の中央値 → 5seedの中央値

時間は ms。有効処理率は確定件数/秒。native selector=0 は既存の依存判定を batch に含める扱い。

|系列|arity|n|分布|worker|方式|commit|selector ms|batch ms|有効処理率|RSS KiB|
|---|---:|---:|---|---:|---|---:|---:|---:|---:|---:|
|main|2|128|uniform|1|native|126|0|0.16187|7.7843e+05|8172|
|main|2|128|uniform|1|eas_k1_adaptive|126|0.15078|0.30571|4.1216e+05|8064|
|main|2|128|uniform|1|accept_id|126|0.13502|0.29196|4.3076e+05|8076|
|main|2|128|uniform|1|eas_k2_adaptive|124|0.15047|0.30683|4.0513e+05|8124|
|main|2|128|uniform|1|accept_static_degree|126|0.1568|0.31241|4.0332e+05|8124|
|main|2|128|zipf|1|eas_k1_adaptive|69|0.28222|0.41646|1.6568e+05|8216|
|main|2|128|zipf|1|native|62|0|0.13638|4.5462e+05|8180|
|main|2|128|zipf|1|accept_id|67|0.13331|0.27027|2.4727e+05|8096|
|main|2|128|zipf|1|eas_k2_adaptive|66|0.2738|0.40699|1.6281e+05|8216|
|main|2|128|zipf|1|accept_static_degree|69|0.16137|0.29544|2.2921e+05|8068|
|smoke_parallel|2|32|zipf|1|accept_id|20|0.043321|0.086816|2.2861e+05|7940|
|smoke_parallel|2|32|zipf|1|native|20|0|0.042312|4.656e+05|8060|
|smoke_parallel|2|32|zipf|1|eas_k1_adaptive|20|0.07773|0.12094|1.6351e+05|7924|
|smoke_parallel|2|32|zipf|1|eas_k2_adaptive|18|0.078221|0.12104|1.4871e+05|7988|
|smoke_parallel|2|32|zipf|1|accept_static_degree|20|0.050441|0.092927|2.1522e+05|8048|
|smoke_parallel|2|32|zipf|2|accept_static_degree|20|0.045423|0.085146|2.2512e+05|7996|
|smoke_parallel|2|32|zipf|2|native|20|0|0.041409|4.6821e+05|8028|
|smoke_parallel|2|32|zipf|2|eas_k1_adaptive|20|0.074944|0.11411|1.7272e+05|8104|
|smoke_parallel|2|32|zipf|2|accept_id|20|0.038519|0.078277|2.5307e+05|8040|
|smoke_parallel|2|32|zipf|2|eas_k2_adaptive|18|0.073372|0.11056|1.628e+05|8100|
|smoke_parallel|2|32|zipf|4|accept_id|20|0.046791|53.336|375.65|8144|
|smoke_parallel|2|32|zipf|4|eas_k2_adaptive|18|0.083756|56.572|372.08|8116|
|smoke_parallel|2|32|zipf|4|accept_static_degree|20|0.055827|56.425|355.92|8148|
|smoke_parallel|2|32|zipf|4|native|20|0|55.976|347.51|8276|
|smoke_parallel|2|32|zipf|4|eas_k1_adaptive|20|0.082086|56.585|388.77|8076|
|zero_commit|1|2|identical|1|native|1|0|0.009563|1.0457e+05|7904|
|zero_commit|1|2|identical|1|accept_id|1|0.008864|0.017836|56066|7848|
|zero_commit|1|2|identical|1|eas_k1_adaptive|1|0.023678|0.032679|30601|8080|
|zero_commit|1|2|identical|1|eas_k2_adaptive|0|0.023921|0.032672|0|7996|
|zero_commit|1|2|identical|1|accept_static_degree|1|0.00985|0.019029|52551|7876|
|control|2|32|identical|1|eas_k1_graph|1|0.11638|0.14274|7005.8|7988|
|control|2|32|identical|1|eas_k1_lazy|1|0.091204|0.11721|8532|8048|
|control|2|32|identical|1|eas_k1_adaptive|1|0.10063|0.12669|7893.5|8256|
|control|2|32|identical|1|eas_k1_profile|1|0.084931|0.11117|8995.5|8204|

## EAS k=1 と static の paired 差

|arity|n|分布|worker|件数差 median [min,max]|追加batch ms median [min,max]|有効処理率比 median [min,max]|
|---:|---:|---|---:|---|---|---|
|2|128|uniform|1|0 [0,0]|-0.006316 [-0.014391,0.000849]|1.0207 [0.99737,1.0489]|
|2|128|zipf|1|0 [0,0]|0.11862 [0.10308,0.1367]|0.71517 [0.67804,0.7479]|
|2|32|zipf|1|0 [0,0]|0.027073 [0.023461,0.034195]|0.76903 [0.72395,0.79608]|
|2|32|zipf|2|0 [0,0]|0.027226 [0.022018,0.031885]|0.76721 [0.72704,0.80364]|
|2|32|zipf|4|0 [0,0]|-0.075807 [-5.3203,9.5442]|1.0013 [0.8492,1.0986]|
|1|2|identical|1|0 [0,0]|0.013692 [0.011823,0.014033]|0.58102 [0.57572,0.6226]|
