# Standalone validator 集計

完全成功: True。予定 1050、観測 1050。

数値は反復→seed の二段階中央値。範囲は seed 間 min/max で信頼区間ではない。
validator rate は commit_count / validator 秒であり DBMS throughput ではない。RSS は process 高水位。
不完全 seed を条件推定に混ぜず、全観測・失敗は CSV に保持する。

|条件|方式|確定|FVS|全体 ms|RSS KiB|validator commits/s|完全 seed|
|---|---|---:|---:|---:|---:|---:|---:|
|main-l1-n40-uniform-k1|accept_id|40|0|0.038685|2000|1.034e+06|5/5|
|main-l1-n40-uniform-k1|accept_static_degree|40|0|0.038932|2020|1.0274e+06|5/5|
|main-l1-n40-uniform-k1|adaptive|40|0|0.038461|1996|1.04e+06|5/5|
|main-l1-n40-uniform-k1|graph|40|0|0.037837|2016|1.0572e+06|5/5|
|main-l1-n40-uniform-k1|lazy|40|0|0.037131|1992|1.0773e+06|5/5|
|main-l1-n40-uniform-k1|paper|40|0|0.028088|2004|1.4241e+06|5/5|
|main-l1-n40-uniform-k1|profile|40|0|0.0397|2016|1.0076e+06|5/5|
|main-l1-n40-zipf-k1|accept_id|32|8|0.04095|1996|7.5702e+05|5/5|
|main-l1-n40-zipf-k1|accept_static_degree|32|8|0.045579|2032|7.1192e+05|5/5|
|main-l1-n40-zipf-k1|adaptive|32|8|0.068737|2008|4.5099e+05|5/5|
|main-l1-n40-zipf-k1|graph|32|8|0.058899|2008|5.2632e+05|5/5|
|main-l1-n40-zipf-k1|lazy|32|8|0.052435|1996|5.852e+05|5/5|
|main-l1-n40-zipf-k1|paper|32|8|0.044713|2004|6.5394e+05|5/5|
|main-l1-n40-zipf-k1|profile|32|8|0.070373|1996|4.4051e+05|5/5|
|main-l2-n40-uniform-k1|accept_id|39|1|0.046227|2000|8.5587e+05|5/5|
|main-l2-n40-uniform-k1|accept_static_degree|39|1|0.052877|1992|7.3756e+05|5/5|
|main-l2-n40-uniform-k1|adaptive|39|1|0.053973|2004|7.2258e+05|5/5|
|main-l2-n40-uniform-k1|graph|39|1|0.056518|2004|6.9005e+05|5/5|
|main-l2-n40-uniform-k1|lazy|39|1|0.052208|1996|7.4701e+05|5/5|
|main-l2-n40-uniform-k1|paper|39|1|0.039339|2000|9.9138e+05|5/5|
|main-l2-n40-uniform-k1|profile|39|1|0.066655|1992|5.851e+05|5/5|
|main-l2-n40-zipf-k1|accept_id|24|16|0.044345|1996|5.2816e+05|5/5|
|main-l2-n40-zipf-k1|accept_static_degree|25|15|0.054502|2012|4.587e+05|5/5|
|main-l2-n40-zipf-k1|adaptive|25|15|0.088559|2016|2.694e+05|5/5|
|main-l2-n40-zipf-k1|graph|25|15|0.080937|2008|3.088e+05|5/5|
|main-l2-n40-zipf-k1|lazy|25|15|0.088082|1996|2.8383e+05|5/5|
|main-l2-n40-zipf-k1|paper|25|15|0.062651|1996|3.9904e+05|5/5|
|main-l2-n40-zipf-k1|profile|25|15|0.11539|2000|2.1666e+05|5/5|
|main-l3-n40-uniform-k1|accept_id|39|1|0.051908|2004|7.6001e+05|5/5|
|main-l3-n40-uniform-k1|accept_static_degree|39|1|0.13384|2016|2.8545e+05|5/5|
|main-l3-n40-uniform-k1|adaptive|39|1|0.066329|2000|5.8798e+05|5/5|
|main-l3-n40-uniform-k1|graph|39|1|0.063675|2000|6.1249e+05|5/5|
|main-l3-n40-uniform-k1|lazy|39|1|0.066543|2016|5.8609e+05|5/5|
|main-l3-n40-uniform-k1|paper|39|1|0.047453|2004|8.2187e+05|5/5|
|main-l3-n40-uniform-k1|profile|39|1|0.080302|2016|4.8567e+05|5/5|
|main-l3-n40-zipf-k1|accept_id|20|20|0.05105|2016|3.8037e+05|5/5|
|main-l3-n40-zipf-k1|accept_static_degree|20|20|0.13747|1996|1.438e+05|5/5|
|main-l3-n40-zipf-k1|adaptive|20|20|0.14927|3880|1.3399e+05|5/5|
|main-l3-n40-zipf-k1|graph|20|20|0.10649|2004|1.8781e+05|5/5|
|main-l3-n40-zipf-k1|lazy|20|20|0.14652|3876|1.3561e+05|5/5|
|main-l3-n40-zipf-k1|paper|20|20|0.084454|2020|2.3682e+05|5/5|
|main-l3-n40-zipf-k1|profile|20|20|0.18157|4084|1.1015e+05|5/5|
|main-l4-n40-uniform-k1|accept_id|39|1|0.060081|2016|6.4912e+05|5/5|
|main-l4-n40-uniform-k1|accept_static_degree|39|1|0.25263|2000|1.5422e+05|5/5|
|main-l4-n40-uniform-k1|adaptive|39|1|0.086141|2008|4.5275e+05|5/5|
|main-l4-n40-uniform-k1|graph|39|1|0.077027|2012|5.0632e+05|5/5|
|main-l4-n40-uniform-k1|lazy|39|1|0.085706|2016|4.5504e+05|5/5|
|main-l4-n40-uniform-k1|paper|39|1|0.058649|1996|6.6497e+05|5/5|
|main-l4-n40-uniform-k1|profile|39|1|0.10089|2036|3.8656e+05|5/5|
|main-l4-n40-zipf-k1|accept_id|15|25|0.07855|2004|1.8973e+05|5/5|
|main-l4-n40-zipf-k1|accept_static_degree|16|24|0.41009|2000|37670|5/5|
|main-l4-n40-zipf-k1|adaptive|16|24|0.27583|3908|58007|5/5|
|main-l4-n40-zipf-k1|graph|16|24|0.14917|1996|1.0055e+05|5/5|
|main-l4-n40-zipf-k1|lazy|16|24|0.34131|3908|46915|5/5|
|main-l4-n40-zipf-k1|paper|16|24|0.14081|1996|1.1363e+05|5/5|
|main-l4-n40-zipf-k1|profile|16|24|0.35233|3928|42574|5/5|
|paper_k-l2-n40-uniform-k2|accept_id|39|1|0.049297|2008|7.9112e+05|5/5|
|paper_k-l2-n40-uniform-k2|accept_static_degree|39|1|0.053802|1988|7.2488e+05|5/5|
|paper_k-l2-n40-uniform-k2|adaptive|38|2|0.05477|2016|6.9381e+05|5/5|
|paper_k-l2-n40-uniform-k2|graph|38|2|0.061217|2000|6.2074e+05|5/5|
|paper_k-l2-n40-uniform-k2|lazy|38|2|0.054786|2004|6.9361e+05|5/5|
|paper_k-l2-n40-uniform-k2|paper|38|2|0.039838|2004|9.5386e+05|5/5|
|paper_k-l2-n40-uniform-k2|profile|38|2|0.068898|2012|5.5154e+05|5/5|
|paper_k-l2-n40-zipf-k2|accept_id|24|16|0.044853|2016|5.3333e+05|5/5|
|paper_k-l2-n40-zipf-k2|accept_static_degree|25|15|0.053902|2008|4.6077e+05|5/5|
|paper_k-l2-n40-zipf-k2|adaptive|24|16|0.087513|1992|2.7378e+05|5/5|
|paper_k-l2-n40-zipf-k2|graph|24|16|0.07989|2032|3.0024e+05|5/5|
|paper_k-l2-n40-zipf-k2|lazy|24|16|0.087093|2012|2.7101e+05|5/5|
|paper_k-l2-n40-zipf-k2|paper|24|16|0.060875|2004|3.9425e+05|5/5|
|paper_k-l2-n40-zipf-k2|profile|24|16|0.11618|2004|1.9966e+05|5/5|

## 同一 trace・同一反復の paired 比較

時間比と rate 比は分子/分母、差は分子−分母。各比を反復内で計算してから中央値を取る。

|条件|分子/分母|時間比 [min,max]|確定差 [min,max]|rate 比 [min,max]|完全 seed|
|---|---|---:|---:|---:|---:|
|main-l1-n40-uniform-k1|adaptive/accept_id|1.022 [0.82765,1.0636]|0 [0,0]|0.97848 [0.94023,1.2082]|5/5|
|main-l1-n40-uniform-k1|adaptive/accept_static_degree|0.99856 [0.7598,1.0411]|0 [0,0]|1.0014 [0.96051,1.3161]|5/5|
|main-l1-n40-uniform-k1|graph/adaptive|0.98627 [0.96501,1.0449]|0 [0,0]|1.0139 [0.95701,1.0363]|5/5|
|main-l1-n40-uniform-k1|paper/adaptive|0.73273 [0.72882,0.96941]|0 [0,0]|1.3648 [1.0316,1.3721]|5/5|
|main-l1-n40-zipf-k1|adaptive/accept_id|1.7416 [1.2274,1.9413]|0 [0,0]|0.57418 [0.51511,0.8147]|5/5|
|main-l1-n40-zipf-k1|adaptive/accept_static_degree|1.6228 [1.0796,1.9143]|0 [0,0]|0.6162 [0.52239,0.9263]|5/5|
|main-l1-n40-zipf-k1|graph/adaptive|0.82649 [0.80573,0.86635]|0 [0,0]|1.2099 [1.1543,1.2411]|5/5|
|main-l1-n40-zipf-k1|paper/adaptive|0.61515 [0.59982,0.7446]|0 [0,0]|1.6256 [1.343,1.6672]|5/5|
|main-l2-n40-uniform-k1|adaptive/accept_id|1.1597 [1.0343,1.2255]|0 [0,0]|0.8623 [0.81602,0.96682]|5/5|
|main-l2-n40-uniform-k1|adaptive/accept_static_degree|0.97368 [0.92161,1.0424]|0 [0,0]|1.027 [0.95936,1.0851]|5/5|
|main-l2-n40-uniform-k1|graph/adaptive|1.0407 [0.97176,1.1143]|0 [0,0]|0.96092 [0.89744,1.0291]|5/5|
|main-l2-n40-uniform-k1|paper/adaptive|0.72501 [0.71238,0.7884]|0 [0,0]|1.3793 [1.2684,1.4037]|5/5|
|main-l2-n40-zipf-k1|adaptive/accept_id|1.9659 [1.8965,2.2182]|1 [0,1]|0.50866 [0.47228,0.54837]|5/5|
|main-l2-n40-zipf-k1|adaptive/accept_static_degree|1.5728 [1.558,1.8496]|0 [0,0]|0.6358 [0.54066,0.64184]|5/5|
|main-l2-n40-zipf-k1|graph/adaptive|0.89077 [0.86057,0.94765]|0 [0,0]|1.1226 [1.0552,1.162]|5/5|
|main-l2-n40-zipf-k1|paper/adaptive|0.68093 [0.63623,0.77811]|0 [0,0]|1.4686 [1.2852,1.5718]|5/5|
|main-l3-n40-uniform-k1|adaptive/accept_id|1.3144 [1.0534,1.4454]|0 [0,0]|0.7608 [0.69185,0.94928]|5/5|
|main-l3-n40-uniform-k1|adaptive/accept_static_degree|0.50837 [0.37716,0.58124]|0 [0,0]|1.9671 [1.7205,2.6514]|5/5|
|main-l3-n40-uniform-k1|graph/adaptive|0.95999 [0.89041,0.98794]|0 [0,0]|1.0417 [1.0122,1.1231]|5/5|
|main-l3-n40-uniform-k1|paper/adaptive|0.72458 [0.65725,0.88475]|0 [0,0]|1.3801 [1.1303,1.5215]|5/5|
|main-l3-n40-zipf-k1|adaptive/accept_id|2.907 [2.7696,3.0313]|1 [0,2]|0.36089 [0.34598,0.3687]|5/5|
|main-l3-n40-zipf-k1|adaptive/accept_static_degree|1.0783 [1.0661,1.1164]|0 [0,0]|0.92738 [0.89576,0.93796]|5/5|
|main-l3-n40-zipf-k1|graph/adaptive|0.70779 [0.69229,0.72921]|0 [0,0]|1.4129 [1.3713,1.4445]|5/5|
|main-l3-n40-zipf-k1|paper/adaptive|0.56338 [0.52859,0.56768]|0 [0,0]|1.775 [1.7616,1.8918]|5/5|
|main-l4-n40-uniform-k1|adaptive/accept_id|1.4509 [1.1088,1.9041]|0 [0,0]|0.68924 [0.52519,0.90191]|5/5|
|main-l4-n40-uniform-k1|adaptive/accept_static_degree|0.34327 [0.27321,0.47272]|0 [0,0]|2.9132 [2.1154,3.6602]|5/5|
|main-l4-n40-uniform-k1|graph/adaptive|0.86072 [0.66837,1.0667]|0 [0,0]|1.1618 [0.93745,1.4962]|5/5|
|main-l4-n40-uniform-k1|paper/adaptive|0.67213 [0.5334,0.8417]|0 [0,0]|1.4878 [1.1881,1.8748]|5/5|
|main-l4-n40-zipf-k1|adaptive/accept_id|4.4655 [4.2365,4.9129]|1 [1,1]|0.2382 [0.2192,0.24993]|5/5|
|main-l4-n40-zipf-k1|adaptive/accept_static_degree|0.85824 [0.65466,0.94489]|0 [0,0]|1.1652 [1.0583,1.5275]|5/5|
|main-l4-n40-zipf-k1|graph/adaptive|0.52206 [0.41108,0.54852]|0 [0,0]|1.9155 [1.8231,2.4326]|5/5|
|main-l4-n40-zipf-k1|paper/adaptive|0.41992 [0.40121,0.43723]|0 [0,0]|2.3814 [2.2871,2.4924]|5/5|
|paper_k-l2-n40-uniform-k2|adaptive/accept_id|1.2081 [0.95906,1.2491]|-1 [-1,0]|0.80655 [0.78008,1.0427]|5/5|
|paper_k-l2-n40-uniform-k2|adaptive/accept_static_degree|1.0061 [0.93755,1.2252]|-1 [-1,0]|0.96849 [0.79525,1.0666]|5/5|
|paper_k-l2-n40-uniform-k2|graph/adaptive|1.0602 [0.99846,1.1471]|0 [0,0]|0.94319 [0.87177,1.0015]|5/5|
|paper_k-l2-n40-uniform-k2|paper/adaptive|0.7292 [0.69208,0.88962]|0 [0,0]|1.3714 [1.1241,1.4449]|5/5|
|paper_k-l2-n40-zipf-k2|adaptive/accept_id|1.9481 [1.8749,2.1496]|-1 [-2,0]|0.49233 [0.44306,0.51333]|5/5|
|paper_k-l2-n40-zipf-k2|adaptive/accept_static_degree|1.6157 [1.5108,1.705]|-2 [-2,-1]|0.58606 [0.5332,0.61097]|5/5|
|paper_k-l2-n40-zipf-k2|graph/adaptive|0.92145 [0.87963,0.94202]|0 [0,0]|1.0853 [1.0616,1.1368]|5/5|
|paper_k-l2-n40-zipf-k2|paper/adaptive|0.69442 [0.656,0.71619]|0 [0,0]|1.44 [1.3963,1.5244]|5/5|
