# 同一seed内3反復の中央値 → 5seedの中央値

時間は ms。有効処理率は確定件数/秒。native selector=0 は既存の依存判定を batch に含める扱い。

|系列|arity|n|分布|worker|方式|commit|selector ms|batch ms|有効処理率|RSS KiB|
|---|---:|---:|---|---:|---|---:|---:|---:|---:|---:|
|main|2|128|uniform|1|native|126|0|0.17241|7.2784e+05|8248|
|main|2|128|uniform|1|eas_k1_adaptive|126|0.1538|0.319|3.9499e+05|8048|
|main|2|128|uniform|1|accept_id|126|0.13431|0.29927|4.18e+05|8180|
|main|2|128|uniform|1|eas_k2_adaptive|124|0.15187|0.31899|3.915e+05|8064|
|main|2|128|uniform|1|accept_static_degree|126|0.15768|0.325|3.8769e+05|8080|
|main|2|128|zipf|1|eas_k1_adaptive|69|0.28325|0.42292|1.6315e+05|8216|
|main|2|128|zipf|1|native|62|0|0.14737|4.1622e+05|8236|
|main|2|128|zipf|1|accept_id|67|0.13492|0.27648|2.3922e+05|8132|
|main|2|128|zipf|1|eas_k2_adaptive|66|0.26923|0.41349|1.6068e+05|8136|
|main|2|128|zipf|1|accept_static_degree|69|0.16219|0.305|2.2491e+05|8176|
|smoke_parallel|2|32|zipf|1|accept_id|20|0.041875|0.086386|2.3636e+05|7980|
|smoke_parallel|2|32|zipf|1|native|20|0|0.044709|4.5288e+05|7984|
|smoke_parallel|2|32|zipf|1|eas_k1_adaptive|20|0.077856|0.12221|1.631e+05|7916|
|smoke_parallel|2|32|zipf|1|eas_k2_adaptive|18|0.077021|0.12111|1.4863e+05|8056|
|smoke_parallel|2|32|zipf|1|accept_static_degree|20|0.049156|0.093426|2.1666e+05|7924|
|smoke_parallel|2|32|zipf|2|accept_static_degree|20|0.047418|0.096457|2.0226e+05|7976|
|smoke_parallel|2|32|zipf|2|native|20|0|0.045281|4.6652e+05|8116|
|smoke_parallel|2|32|zipf|2|eas_k1_adaptive|20|0.075777|0.13992|1.5496e+05|7972|
|smoke_parallel|2|32|zipf|2|accept_id|20|0.039328|0.098674|1.9255e+05|8104|
|smoke_parallel|2|32|zipf|2|eas_k2_adaptive|18|0.097797|0.15083|1.1934e+05|8000|
|smoke_parallel|2|32|zipf|4|accept_id|20|0.043449|58.144|330.04|8084|
|smoke_parallel|2|32|zipf|4|eas_k2_adaptive|18|0.081474|53.303|343.44|8212|
|smoke_parallel|2|32|zipf|4|accept_static_degree|20|0.055078|55.518|368.5|8080|
|smoke_parallel|2|32|zipf|4|native|20|0|53.295|405|8164|
|smoke_parallel|2|32|zipf|4|eas_k1_adaptive|20|0.082143|59.241|358.98|8148|
|zero_commit|1|2|identical|1|native|1|0|0.009044|1.1057e+05|8004|
|zero_commit|1|2|identical|1|accept_id|1|0.008338|0.01785|56022|7952|
|zero_commit|1|2|identical|1|eas_k1_adaptive|1|0.020985|0.029986|33349|8080|
|zero_commit|1|2|identical|1|eas_k2_adaptive|0|0.020271|0.028664|0|7996|
|zero_commit|1|2|identical|1|accept_static_degree|1|0.009216|0.018304|54633|8000|
|control|2|32|identical|1|eas_k1_graph|1|0.11537|0.142|7042.4|7912|
|control|2|32|identical|1|eas_k1_lazy|1|0.092595|0.11939|8375.6|8052|
|control|2|32|identical|1|eas_k1_adaptive|1|0.10114|0.12744|7847.1|8236|
|control|2|32|identical|1|eas_k1_profile|1|0.081965|0.10959|9124.5|8204|

## EAS k=1 と static の paired 差

|arity|n|分布|worker|件数差 median [min,max]|追加batch ms median [min,max]|有効処理率比 median [min,max]|
|---:|---:|---|---:|---|---|---|
|2|128|uniform|1|0 [0,0]|-0.01124 [-0.012651,0.001299]|1.0358 [0.99603,1.0406]|
|2|128|zipf|1|0 [0,0]|0.11613 [0.11253,0.13366]|0.72541 [0.69503,0.73214]|
|2|32|zipf|1|0 [0,0]|0.028872 [0.019373,0.030217]|0.7655 [0.75352,0.83378]|
|2|32|zipf|2|0 [0,0]|0.030354 [-57.266,48.35]|0.78305 [0.0020027,398.25]|
|2|32|zipf|4|0 [0,0]|4.7903 [-12.868,9.7788]|0.91707 [0.85827,1.2568]|
|1|2|identical|1|0 [0,0]|0.011131 [0.010872,0.012832]|0.62036 [0.56677,0.63567]|
