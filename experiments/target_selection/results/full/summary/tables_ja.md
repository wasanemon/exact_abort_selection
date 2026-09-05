# Standalone validator 集計

完全成功: True。予定 4410、観測 4410。

数値は反復→seed の二段階中央値。範囲は seed 間 min/max で信頼区間ではない。
validator rate は commit_count / validator 秒であり DBMS throughput ではない。RSS は process 高水位。
不完全 seed を条件推定に混ぜず、全観測・失敗は CSV に保持する。

|条件|方式|確定|FVS|全体 ms|RSS KiB|validator commits/s|完全 seed|
|---|---|---:|---:|---:|---:|---:|---:|
|dense-l2-n1024-identical-k1|accept_id|1|1023|0.45216|3876|2211.6|5/5|
|dense-l2-n1024-identical-k1|accept_static_degree|1|1023|0.48589|3808|2058.1|5/5|
|dense-l2-n1024-identical-k1|adaptive|1|1023|4.3897|4236|227.81|5/5|
|dense-l2-n1024-identical-k1|graph|1|1023|73.507|4224|13.604|5/5|
|dense-l2-n1024-identical-k1|lazy|1|1023|48.68|4180|20.542|5/5|
|dense-l2-n1024-identical-k1|paper|1|1023|41.329|12596|24.196|5/5|
|dense-l2-n1024-identical-k1|profile|1|1023|1.3074|4192|764.88|5/5|
|dense-l2-n4096-identical-k1|accept_id|1|4095|1.816|4996|550.65|5/5|
|dense-l2-n4096-identical-k1|accept_static_degree|1|4095|1.9643|4996|509.08|5/5|
|dense-l2-n4096-identical-k1|adaptive|1|4095|29.743|5744|33.622|5/5|
|dense-l2-n4096-identical-k1|graph|1|4095|1378.9|7352|0.72522|5/5|
|dense-l2-n4096-identical-k1|lazy|1|4095|831.58|5512|1.2025|5/5|
|dense-l2-n4096-identical-k1|paper|1|4095|657|1.3748e+05|1.5221|5/5|
|dense-l2-n4096-identical-k1|profile|1|4095|5.3314|5676|187.57|5/5|
|main-l1-n128-uniform-k1|accept_id|127|1|0.08719|2004|1.4524e+06|5/5|
|main-l1-n128-uniform-k1|accept_static_degree|127|1|0.093195|2016|1.3627e+06|5/5|
|main-l1-n128-uniform-k1|adaptive|127|1|0.10407|1996|1.2203e+06|5/5|
|main-l1-n128-uniform-k1|graph|127|1|0.094532|2016|1.3435e+06|5/5|
|main-l1-n128-uniform-k1|lazy|127|1|0.093767|1992|1.345e+06|5/5|
|main-l1-n128-uniform-k1|paper|127|1|0.073773|1996|1.7237e+06|5/5|
|main-l1-n128-uniform-k1|profile|127|1|0.10386|1996|1.2228e+06|5/5|
|main-l1-n128-zipf-k1|accept_id|93|35|0.088217|1996|1.0412e+06|5/5|
|main-l1-n128-zipf-k1|accept_static_degree|93|35|0.099199|2000|9.1666e+05|5/5|
|main-l1-n128-zipf-k1|adaptive|93|35|0.15782|2016|5.8929e+05|5/5|
|main-l1-n128-zipf-k1|graph|93|35|0.15754|2000|5.8803e+05|5/5|
|main-l1-n128-zipf-k1|lazy|93|35|0.13812|2016|6.4197e+05|5/5|
|main-l1-n128-zipf-k1|paper|93|35|0.13643|2012|6.8168e+05|5/5|
|main-l1-n128-zipf-k1|profile|93|35|0.15744|2016|5.9135e+05|5/5|
|main-l1-n2048-uniform-k1|accept_id|1808|240|1.151|4460|1.5615e+06|5/5|
|main-l1-n2048-uniform-k1|accept_static_degree|1808|240|1.3045|4448|1.3829e+06|5/5|
|main-l1-n2048-uniform-k1|adaptive|1808|240|1.8458|4444|9.7788e+05|5/5|
|main-l1-n2048-uniform-k1|graph|1808|240|1.5999|4440|1.1284e+06|5/5|
|main-l1-n2048-uniform-k1|lazy|1808|240|1.5248|4460|1.1831e+06|5/5|
|main-l1-n2048-uniform-k1|paper|1808|240|2.0881|4684|8.6393e+05|5/5|
|main-l1-n2048-uniform-k1|profile|1808|240|1.8587|4444|9.7271e+05|5/5|
|main-l1-n2048-zipf-k1|accept_id|903|1145|1.1013|4188|8.245e+05|5/5|
|main-l1-n2048-zipf-k1|accept_static_degree|903|1145|1.313|4168|6.856e+05|5/5|
|main-l1-n2048-zipf-k1|adaptive|903|1145|2.8128|4440|3.2101e+05|5/5|
|main-l1-n2048-zipf-k1|graph|903|1145|8.666|4700|1.0278e+05|5/5|
|main-l1-n2048-zipf-k1|lazy|903|1145|6.0043|4420|1.4789e+05|5/5|
|main-l1-n2048-zipf-k1|paper|903|1145|19.676|5196|45081|5/5|
|main-l1-n2048-zipf-k1|profile|903|1145|2.8243|4440|3.1877e+05|5/5|
|main-l1-n40-uniform-k1|accept_id|40|0|0.035532|2016|1.1257e+06|5/5|
|main-l1-n40-uniform-k1|accept_static_degree|40|0|0.037088|2012|1.0785e+06|5/5|
|main-l1-n40-uniform-k1|adaptive|40|0|0.036988|2016|1.0814e+06|5/5|
|main-l1-n40-uniform-k1|graph|40|0|0.037194|1996|1.0754e+06|5/5|
|main-l1-n40-uniform-k1|lazy|40|0|0.036944|2020|1.0827e+06|5/5|
|main-l1-n40-uniform-k1|paper|40|0|0.02628|2016|1.5221e+06|5/5|
|main-l1-n40-uniform-k1|profile|40|0|0.037048|2004|1.0797e+06|5/5|
|main-l1-n40-zipf-k1|accept_id|32|8|0.035218|2020|9.1517e+05|5/5|
|main-l1-n40-zipf-k1|accept_static_degree|32|8|0.039034|2004|8.198e+05|5/5|
|main-l1-n40-zipf-k1|adaptive|32|8|0.064441|2004|4.9658e+05|5/5|
|main-l1-n40-zipf-k1|graph|32|8|0.052048|2016|6.1482e+05|5/5|
|main-l1-n40-zipf-k1|lazy|32|8|0.049031|1996|6.5265e+05|5/5|
|main-l1-n40-zipf-k1|paper|32|8|0.037123|2000|8.6202e+05|5/5|
|main-l1-n40-zipf-k1|profile|32|8|0.063796|1984|5.016e+05|5/5|
|main-l1-n512-uniform-k1|accept_id|495|17|0.26611|3904|1.8502e+06|5/5|
|main-l1-n512-uniform-k1|accept_static_degree|495|17|0.29025|3904|1.7054e+06|5/5|
|main-l1-n512-uniform-k1|adaptive|495|17|0.3421|3916|1.4469e+06|5/5|
|main-l1-n512-uniform-k1|graph|495|17|0.30986|3920|1.6007e+06|5/5|
|main-l1-n512-uniform-k1|lazy|495|17|0.30607|3924|1.6205e+06|5/5|
|main-l1-n512-uniform-k1|paper|495|17|0.25404|3872|1.9367e+06|5/5|
|main-l1-n512-uniform-k1|profile|495|17|0.33799|3920|1.4645e+06|5/5|
|main-l1-n512-zipf-k1|accept_id|290|222|0.2696|3932|1.0727e+06|5/5|
|main-l1-n512-zipf-k1|accept_static_degree|290|222|0.31248|3928|9.2352e+05|5/5|
|main-l1-n512-zipf-k1|adaptive|290|222|0.58309|3904|4.9938e+05|5/5|
|main-l1-n512-zipf-k1|graph|290|222|0.87198|3916|3.3831e+05|5/5|
|main-l1-n512-zipf-k1|lazy|290|222|0.67736|3932|4.3514e+05|5/5|
|main-l1-n512-zipf-k1|paper|290|222|1.2402|3948|2.3222e+05|5/5|
|main-l1-n512-zipf-k1|profile|290|222|0.58129|3928|5.0252e+05|5/5|
|main-l2-n128-uniform-k1|accept_id|126|2|0.12796|1996|9.7478e+05|5/5|
|main-l2-n128-uniform-k1|accept_static_degree|126|2|0.15435|2004|8.1632e+05|5/5|
|main-l2-n128-uniform-k1|adaptive|126|2|0.14843|2000|8.4888e+05|5/5|
|main-l2-n128-uniform-k1|graph|126|2|0.1475|2004|8.5424e+05|5/5|
|main-l2-n128-uniform-k1|lazy|126|2|0.14565|2012|8.585e+05|5/5|
|main-l2-n128-uniform-k1|paper|126|2|0.12195|2012|1.0332e+06|5/5|
|main-l2-n128-uniform-k1|profile|126|2|0.16654|2016|7.5658e+05|5/5|
|main-l2-n128-zipf-k1|accept_id|61|67|0.12386|1992|4.9497e+05|5/5|
|main-l2-n128-zipf-k1|accept_static_degree|63|65|0.15759|2036|4.0434e+05|5/5|
|main-l2-n128-zipf-k1|adaptive|63|65|0.28841|1984|2.1844e+05|5/5|
|main-l2-n128-zipf-k1|graph|63|65|0.32661|2020|1.9289e+05|5/5|
|main-l2-n128-zipf-k1|lazy|63|65|0.29403|2072|2.1427e+05|5/5|
|main-l2-n128-zipf-k1|paper|63|65|0.30071|2004|2.0285e+05|5/5|
|main-l2-n128-zipf-k1|profile|63|65|0.36938|3960|1.8073e+05|5/5|
|main-l2-n2048-uniform-k1|accept_id|1357|691|1.4131|4456|9.5705e+05|5/5|
|main-l2-n2048-uniform-k1|accept_static_degree|1407|641|1.859|4660|7.5385e+05|5/5|
|main-l2-n2048-uniform-k1|adaptive|1402|646|3.2178|5232|4.3464e+05|5/5|
|main-l2-n2048-uniform-k1|graph|1402|646|2.8393|5032|4.9344e+05|5/5|
|main-l2-n2048-uniform-k1|lazy|1402|646|3.2169|5248|4.3551e+05|5/5|
|main-l2-n2048-uniform-k1|paper|1402|646|7.257|5252|1.9333e+05|5/5|
|main-l2-n2048-uniform-k1|profile|1402|646|3.8374|5520|3.6509e+05|5/5|
|main-l2-n2048-zipf-k1|accept_id|408|1640|1.2179|4576|3.3499e+05|5/5|
|main-l2-n2048-zipf-k1|accept_static_degree|433|1615|1.7051|4604|2.5469e+05|5/5|
|main-l2-n2048-zipf-k1|adaptive|433|1615|8.6647|5220|49817|5/5|
|main-l2-n2048-zipf-k1|graph|433|1615|36.492|5080|12085|5/5|
|main-l2-n2048-zipf-k1|lazy|433|1615|8.6634|5212|49979|5/5|
|main-l2-n2048-zipf-k1|paper|433|1615|40.522|7604|10883|5/5|
|main-l2-n2048-zipf-k1|profile|433|1615|8.4728|5360|50534|5/5|
|main-l2-n40-uniform-k1|accept_id|39|1|0.052991|2004|7.5485e+05|5/5|
|main-l2-n40-uniform-k1|accept_static_degree|39|1|0.058963|1984|6.7839e+05|5/5|
|main-l2-n40-uniform-k1|adaptive|39|1|0.061639|1996|6.3272e+05|5/5|
|main-l2-n40-uniform-k1|graph|39|1|0.063564|2000|6.1355e+05|5/5|
|main-l2-n40-uniform-k1|lazy|39|1|0.060202|1984|6.4782e+05|5/5|
|main-l2-n40-uniform-k1|paper|39|1|0.044752|2008|8.7147e+05|5/5|
|main-l2-n40-uniform-k1|profile|39|1|0.076303|2016|5.1112e+05|5/5|
|main-l2-n40-zipf-k1|accept_id|24|16|0.051284|2004|4.6617e+05|5/5|
|main-l2-n40-zipf-k1|accept_static_degree|25|15|0.061805|1984|3.876e+05|5/5|
|main-l2-n40-zipf-k1|adaptive|25|15|0.10234|2000|2.4586e+05|5/5|
|main-l2-n40-zipf-k1|graph|25|15|0.091795|2012|2.7235e+05|5/5|
|main-l2-n40-zipf-k1|lazy|25|15|0.10099|1980|2.4352e+05|5/5|
|main-l2-n40-zipf-k1|paper|25|15|0.071157|2004|3.5134e+05|5/5|
|main-l2-n40-zipf-k1|profile|25|15|0.13004|1996|1.8341e+05|5/5|
|main-l2-n512-uniform-k1|accept_id|448|64|0.41529|3956|1.0844e+06|5/5|
|main-l2-n512-uniform-k1|accept_static_degree|453|59|0.51436|3932|8.8185e+05|5/5|
|main-l2-n512-uniform-k1|adaptive|453|59|0.621|4144|7.2947e+05|5/5|
|main-l2-n512-uniform-k1|graph|453|59|0.54024|3916|8.3852e+05|5/5|
|main-l2-n512-uniform-k1|lazy|453|59|0.62716|4144|7.223e+05|5/5|
|main-l2-n512-uniform-k1|paper|453|59|0.49533|3908|9.1455e+05|5/5|
|main-l2-n512-uniform-k1|profile|453|59|0.70078|4348|6.4642e+05|5/5|
|main-l2-n512-zipf-k1|accept_id|149|363|0.38139|3920|3.9181e+05|5/5|
|main-l2-n512-zipf-k1|accept_static_degree|153|359|0.50741|3916|2.9697e+05|5/5|
|main-l2-n512-zipf-k1|adaptive|153|359|1.4323|4244|1.0909e+05|5/5|
|main-l2-n512-zipf-k1|graph|153|359|2.8066|3908|54515|5/5|
|main-l2-n512-zipf-k1|lazy|153|359|1.4572|4184|1.0886e+05|5/5|
|main-l2-n512-zipf-k1|paper|153|359|2.9569|4136|50303|5/5|
|main-l2-n512-zipf-k1|profile|153|359|1.7251|4180|86952|5/5|
|main-l3-n128-uniform-k1|accept_id|119|9|0.13934|2016|8.6811e+05|5/5|
|main-l3-n128-uniform-k1|accept_static_degree|119|9|0.40229|3932|2.9395e+05|5/5|
|main-l3-n128-uniform-k1|adaptive|119|9|0.19875|1988|5.9875e+05|5/5|
|main-l3-n128-uniform-k1|graph|119|9|0.17027|2012|6.9889e+05|5/5|
|main-l3-n128-uniform-k1|lazy|119|9|0.19822|2004|6.0034e+05|5/5|
|main-l3-n128-uniform-k1|paper|119|9|0.13453|3888|8.8939e+05|5/5|
|main-l3-n128-uniform-k1|profile|119|9|0.22|3980|5.4091e+05|5/5|
|main-l3-n128-zipf-k1|accept_id|40|88|0.12696|2008|3.1911e+05|5/5|
|main-l3-n128-zipf-k1|accept_static_degree|42|86|0.41528|3916|1.0159e+05|5/5|
|main-l3-n128-zipf-k1|adaptive|42|86|0.47449|4072|90624|5/5|
|main-l3-n128-zipf-k1|graph|42|86|0.46358|1980|95782|5/5|
|main-l3-n128-zipf-k1|lazy|42|86|0.4785|4044|89856|5/5|
|main-l3-n128-zipf-k1|paper|42|86|0.42259|3876|1.0138e+05|5/5|
|main-l3-n128-zipf-k1|profile|42|86|0.60915|4264|70590|5/5|
|main-l3-n2048-uniform-k1|accept_id|1021|1027|1.7285|4756|5.8995e+05|5/5|
|main-l3-n2048-uniform-k1|accept_static_degree|1109|939|7.0276|5488|1.5828e+05|5/5|
|main-l3-n2048-uniform-k1|adaptive|1095|953|7.5646|7328|1.4475e+05|5/5|
|main-l3-n2048-uniform-k1|graph|1095|953|4.466|5476|2.4445e+05|5/5|
|main-l3-n2048-uniform-k1|lazy|1095|953|7.548|7328|1.4535e+05|5/5|
|main-l3-n2048-uniform-k1|paper|1095|953|16.789|5504|63077|5/5|
|main-l3-n2048-uniform-k1|profile|1095|953|8.8349|7568|1.2394e+05|5/5|
|main-l3-n2048-zipf-k1|accept_id|205|1843|1.4422|4704|1.4214e+05|5/5|
|main-l3-n2048-zipf-k1|accept_static_degree|233|1815|6.865|5224|33940|5/5|
|main-l3-n2048-zipf-k1|adaptive|234|1814|12.066|7392|19314|5/5|
|main-l3-n2048-zipf-k1|graph|234|1814|85.257|5252|2744.6|5/5|
|main-l3-n2048-zipf-k1|lazy|234|1814|12.081|7404|19317|5/5|
|main-l3-n2048-zipf-k1|paper|234|1814|58.176|12116|4142.6|5/5|
|main-l3-n2048-zipf-k1|profile|234|1814|31.358|7404|7685.4|5/5|
|main-l3-n40-uniform-k1|accept_id|39|1|0.051506|2016|7.6934e+05|5/5|
|main-l3-n40-uniform-k1|accept_static_degree|39|1|0.13424|2016|2.9293e+05|5/5|
|main-l3-n40-uniform-k1|adaptive|39|1|0.068094|2000|5.7274e+05|5/5|
|main-l3-n40-uniform-k1|graph|39|1|0.064936|1988|6.0059e+05|5/5|
|main-l3-n40-uniform-k1|lazy|39|1|0.0682|2020|5.7185e+05|5/5|
|main-l3-n40-uniform-k1|paper|39|1|0.046203|2000|8.276e+05|5/5|
|main-l3-n40-uniform-k1|profile|39|1|0.07836|2016|4.977e+05|5/5|
|main-l3-n40-zipf-k1|accept_id|20|20|0.051529|2000|3.8363e+05|5/5|
|main-l3-n40-zipf-k1|accept_static_degree|20|20|0.13619|2020|1.457e+05|5/5|
|main-l3-n40-zipf-k1|adaptive|20|20|0.14942|3896|1.3385e+05|5/5|
|main-l3-n40-zipf-k1|graph|20|20|0.10663|2008|1.8756e+05|5/5|
|main-l3-n40-zipf-k1|lazy|20|20|0.14502|3904|1.3792e+05|5/5|
|main-l3-n40-zipf-k1|paper|20|20|0.081045|2016|2.4678e+05|5/5|
|main-l3-n40-zipf-k1|profile|20|20|0.18225|4096|1.1181e+05|5/5|
|main-l3-n512-uniform-k1|accept_id|408|104|0.46931|3832|8.6214e+05|5/5|
|main-l3-n512-uniform-k1|accept_static_degree|412|100|1.559|4184|2.6464e+05|5/5|
|main-l3-n512-uniform-k1|adaptive|411|101|1.0295|4332|3.9921e+05|5/5|
|main-l3-n512-uniform-k1|graph|411|101|0.69666|4176|5.9186e+05|5/5|
|main-l3-n512-uniform-k1|lazy|411|101|1.0165|4396|4.049e+05|5/5|
|main-l3-n512-uniform-k1|paper|411|101|0.6478|4120|6.3446e+05|5/5|
|main-l3-n512-uniform-k1|profile|411|101|1.1341|4572|3.6329e+05|5/5|
|main-l3-n512-zipf-k1|accept_id|100|412|0.40395|3824|2.4669e+05|5/5|
|main-l3-n512-zipf-k1|accept_static_degree|106|406|1.6227|4240|65322|5/5|
|main-l3-n512-zipf-k1|adaptive|107|405|2.2072|4656|47835|5/5|
|main-l3-n512-zipf-k1|graph|107|405|4.9764|3904|19618|5/5|
|main-l3-n512-zipf-k1|lazy|107|405|2.2034|4584|47885|5/5|
|main-l3-n512-zipf-k1|paper|107|405|4.1292|4396|25819|5/5|
|main-l3-n512-zipf-k1|profile|107|405|3.5155|4672|30413|5/5|
|main-l4-n128-uniform-k1|accept_id|112|16|0.15317|2004|7.2998e+05|5/5|
|main-l4-n128-uniform-k1|accept_static_degree|114|14|0.74667|3908|1.5402e+05|5/5|
|main-l4-n128-uniform-k1|adaptive|114|14|0.31484|4000|3.636e+05|5/5|
|main-l4-n128-uniform-k1|graph|114|14|0.19977|2056|5.7567e+05|5/5|
|main-l4-n128-uniform-k1|lazy|114|14|0.31785|4008|3.618e+05|5/5|
|main-l4-n128-uniform-k1|paper|114|14|0.16619|3888|6.9126e+05|5/5|
|main-l4-n128-uniform-k1|profile|114|14|0.34824|4188|3.2736e+05|5/5|
|main-l4-n128-zipf-k1|accept_id|29|99|0.14453|2008|1.9897e+05|5/5|
|main-l4-n128-zipf-k1|accept_static_degree|32|96|0.84011|3920|38198|5/5|
|main-l4-n128-zipf-k1|adaptive|32|96|0.8212|4172|38967|5/5|
|main-l4-n128-zipf-k1|graph|32|96|0.65521|2020|47313|5/5|
|main-l4-n128-zipf-k1|lazy|32|96|0.82895|4184|38603|5/5|
|main-l4-n128-zipf-k1|paper|32|96|0.50127|3840|61843|5/5|
|main-l4-n128-zipf-k1|profile|32|96|1.1341|4320|27334|5/5|
|main-l4-n2048-uniform-k1|accept_id|756|1292|2.0898|4972|3.6177e+05|5/5|
|main-l4-n2048-uniform-k1|accept_static_degree|850|1198|15.821|7136|53710|5/5|
|main-l4-n2048-uniform-k1|adaptive|845|1203|17.15|11176|48838|5/5|
|main-l4-n2048-uniform-k1|graph|845|1203|6.168|5504|1.3727e+05|5/5|
|main-l4-n2048-uniform-k1|lazy|845|1203|17.32|11188|48677|5/5|
|main-l4-n2048-uniform-k1|paper|845|1203|28.052|5948|30123|5/5|
|main-l4-n2048-uniform-k1|profile|845|1203|19.278|11328|43694|5/5|
|main-l4-n2048-zipf-k1|accept_id|120|1928|1.6578|4712|73266|5/5|
|main-l4-n2048-zipf-k1|accept_static_degree|143|1905|15.789|6684|9096|5/5|
|main-l4-n2048-zipf-k1|adaptive|144|1904|20.82|10140|7012.4|5/5|
|main-l4-n2048-zipf-k1|graph|144|1904|142.54|5492|1029.4|5/5|
|main-l4-n2048-zipf-k1|lazy|144|1904|20.712|10172|6957.3|5/5|
|main-l4-n2048-zipf-k1|paper|144|1904|73.538|15484|1950.1|5/5|
|main-l4-n2048-zipf-k1|profile|144|1904|75.474|10356|1928.7|5/5|
|main-l4-n40-uniform-k1|accept_id|39|1|0.060113|2016|6.4878e+05|5/5|
|main-l4-n40-uniform-k1|accept_static_degree|39|1|0.24217|2004|1.6104e+05|5/5|
|main-l4-n40-uniform-k1|adaptive|39|1|0.086636|2020|4.5016e+05|5/5|
|main-l4-n40-uniform-k1|graph|39|1|0.075253|2016|5.1825e+05|5/5|
|main-l4-n40-uniform-k1|lazy|39|1|0.084281|2012|4.6274e+05|5/5|
|main-l4-n40-uniform-k1|paper|39|1|0.057485|2012|6.7844e+05|5/5|
|main-l4-n40-uniform-k1|profile|39|1|0.1002|2036|3.8924e+05|5/5|
|main-l4-n40-zipf-k1|accept_id|15|25|0.056576|2000|2.6544e+05|5/5|
|main-l4-n40-zipf-k1|accept_static_degree|16|24|0.26736|2016|59844|5/5|
|main-l4-n40-zipf-k1|adaptive|16|24|0.24875|3936|64322|5/5|
|main-l4-n40-zipf-k1|graph|16|24|0.13421|1996|1.2183e+05|5/5|
|main-l4-n40-zipf-k1|lazy|16|24|0.24875|3904|64033|5/5|
|main-l4-n40-zipf-k1|paper|16|24|0.1059|2012|1.5108e+05|5/5|
|main-l4-n40-zipf-k1|profile|16|24|0.31582|3912|50232|5/5|
|main-l4-n512-uniform-k1|accept_id|349|163|0.53577|3816|6.4979e+05|5/5|
|main-l4-n512-uniform-k1|accept_static_degree|360|152|3.1375|4444|1.1474e+05|5/5|
|main-l4-n512-uniform-k1|adaptive|359|153|2.2999|5316|1.56e+05|5/5|
|main-l4-n512-uniform-k1|graph|359|153|0.8861|4244|4.0514e+05|5/5|
|main-l4-n512-uniform-k1|lazy|359|153|2.3023|5312|1.5549e+05|5/5|
|main-l4-n512-uniform-k1|paper|359|153|1.0245|4100|3.514e+05|5/5|
|main-l4-n512-uniform-k1|profile|359|153|2.5082|5328|1.4273e+05|5/5|
|main-l4-n512-zipf-k1|accept_id|57|455|0.44568|3784|1.2633e+05|5/5|
|main-l4-n512-zipf-k1|accept_static_degree|68|444|3.4893|4448|19488|5/5|
|main-l4-n512-zipf-k1|adaptive|68|444|3.8761|5304|17213|5/5|
|main-l4-n512-zipf-k1|graph|68|444|8.2267|3880|8265.8|5/5|
|main-l4-n512-zipf-k1|lazy|68|444|3.8925|5368|17225|5/5|
|main-l4-n512-zipf-k1|paper|68|444|5.4156|4704|12695|5/5|
|main-l4-n512-zipf-k1|profile|68|444|8.3075|5680|8445.9|5/5|
|paper_k-l2-n2048-uniform-k2|accept_id|1357|691|1.4117|4508|9.6112e+05|5/5|
|paper_k-l2-n2048-uniform-k2|accept_static_degree|1407|641|1.8589|4708|7.5796e+05|5/5|
|paper_k-l2-n2048-uniform-k2|adaptive|1400|648|3.1862|5256|4.4003e+05|5/5|
|paper_k-l2-n2048-uniform-k2|graph|1400|648|2.8234|5032|4.9558e+05|5/5|
|paper_k-l2-n2048-uniform-k2|lazy|1400|648|3.1723|5240|4.4069e+05|5/5|
|paper_k-l2-n2048-uniform-k2|paper|1400|648|4.7999|5208|2.9209e+05|5/5|
|paper_k-l2-n2048-uniform-k2|profile|1400|648|3.8088|5540|3.6757e+05|5/5|
|paper_k-l2-n2048-zipf-k2|accept_id|408|1640|1.2194|4556|3.3288e+05|5/5|
|paper_k-l2-n2048-zipf-k2|accept_static_degree|433|1615|1.7108|4588|2.5409e+05|5/5|
|paper_k-l2-n2048-zipf-k2|adaptive|430|1618|7.4719|5220|57936|5/5|
|paper_k-l2-n2048-zipf-k2|graph|430|1618|35.967|5076|12178|5/5|
|paper_k-l2-n2048-zipf-k2|lazy|430|1618|7.4328|5220|57640|5/5|
|paper_k-l2-n2048-zipf-k2|paper|430|1618|28.238|7588|15511|5/5|
|paper_k-l2-n2048-zipf-k2|profile|430|1618|8.3402|5336|51155|5/5|
|paper_k-l2-n40-uniform-k2|accept_id|39|1|0.052574|1996|7.4181e+05|5/5|
|paper_k-l2-n40-uniform-k2|accept_static_degree|39|1|0.060371|2016|6.4601e+05|5/5|
|paper_k-l2-n40-uniform-k2|adaptive|38|2|0.059265|2008|6.4119e+05|5/5|
|paper_k-l2-n40-uniform-k2|graph|38|2|0.063099|2004|6.0223e+05|5/5|
|paper_k-l2-n40-uniform-k2|lazy|38|2|0.060875|2008|6.2423e+05|5/5|
|paper_k-l2-n40-uniform-k2|paper|38|2|0.044576|2012|8.5248e+05|5/5|
|paper_k-l2-n40-uniform-k2|profile|38|2|0.077688|2008|4.8914e+05|5/5|
|paper_k-l2-n40-zipf-k2|accept_id|24|16|0.051837|1992|4.5929e+05|5/5|
|paper_k-l2-n40-zipf-k2|accept_static_degree|25|15|0.062652|2012|3.8991e+05|5/5|
|paper_k-l2-n40-zipf-k2|adaptive|24|16|0.10081|2016|2.365e+05|5/5|
|paper_k-l2-n40-zipf-k2|graph|24|16|0.087944|2004|2.729e+05|5/5|
|paper_k-l2-n40-zipf-k2|lazy|24|16|0.10079|2000|2.377e+05|5/5|
|paper_k-l2-n40-zipf-k2|paper|24|16|0.068202|2016|3.519e+05|5/5|
|paper_k-l2-n40-zipf-k2|profile|24|16|0.13208|2012|1.7612e+05|5/5|
|paper_k-l2-n512-uniform-k2|accept_id|448|64|0.41016|3840|1.083e+06|5/5|
|paper_k-l2-n512-uniform-k2|accept_static_degree|453|59|0.51126|3880|8.9592e+05|5/5|
|paper_k-l2-n512-uniform-k2|adaptive|450|62|0.63292|4116|7.1099e+05|5/5|
|paper_k-l2-n512-uniform-k2|graph|450|62|0.54254|3916|8.2943e+05|5/5|
|paper_k-l2-n512-uniform-k2|lazy|450|62|0.61715|4132|7.2916e+05|5/5|
|paper_k-l2-n512-uniform-k2|paper|450|62|0.47562|3900|9.3352e+05|5/5|
|paper_k-l2-n512-uniform-k2|profile|450|62|0.70048|4376|6.4242e+05|5/5|
|paper_k-l2-n512-zipf-k2|accept_id|149|363|0.37259|3956|4.3203e+05|5/5|
|paper_k-l2-n512-zipf-k2|accept_static_degree|153|359|0.50035|3884|3.3889e+05|5/5|
|paper_k-l2-n512-zipf-k2|adaptive|150|362|1.2537|4280|1.302e+05|5/5|
|paper_k-l2-n512-zipf-k2|graph|150|362|2.5006|3924|59985|5/5|
|paper_k-l2-n512-zipf-k2|lazy|150|362|1.2501|4200|1.2994e+05|5/5|
|paper_k-l2-n512-zipf-k2|paper|150|362|2.0947|4176|71631|5/5|
|paper_k-l2-n512-zipf-k2|profile|150|362|1.6133|4196|99733|5/5|
|scale-l2-n8192-uniform-k1|accept_id|2751|5441|5.2184|6704|5.2443e+05|5/5|
|scale-l2-n8192-uniform-k1|accept_static_degree|3137|5055|7.2749|6684|4.3126e+05|5/5|
|scale-l2-n8192-uniform-k1|adaptive|2993|5199|20.038|10292|1.4897e+05|5/5|
|scale-l2-n8192-uniform-k1|graph|2993|5199|33.6|15392|89077|5/5|
|scale-l2-n8192-uniform-k1|lazy|2993|5199|20.126|10336|1.4888e+05|5/5|
|scale-l2-n8192-uniform-k1|paper|2993|5199|454.69|9288|6617.7|5/5|
|scale-l2-n8192-uniform-k1|profile|2993|5199|28.447|11060|1.0578e+05|5/5|
|scale-l2-n8192-zipf-k1|accept_id|859|7333|4.6692|6440|1.836e+05|5/5|
|scale-l2-n8192-zipf-k1|accept_static_degree|943|7249|6.7229|6704|1.4099e+05|5/5|
|scale-l2-n8192-zipf-k1|adaptive|946|7246|67.357|9400|13896|5/5|
|scale-l2-n8192-zipf-k1|graph|946|7246|687.7|15440|1358.2|5/5|
|scale-l2-n8192-zipf-k1|lazy|946|7246|67.432|9428|13881|5/5|
|scale-l2-n8192-zipf-k1|paper|946|7246|795.74|52912|1190.3|5/5|
|scale-l2-n8192-zipf-k1|profile|946|7246|61.151|9856|15438|5/5|

## 同一 trace・同一反復の paired 比較

時間比と rate 比は分子/分母、差は分子−分母。各比を反復内で計算してから中央値を取る。

|条件|分子/分母|時間比 [min,max]|確定差 [min,max]|rate 比 [min,max]|完全 seed|
|---|---|---:|---:|---:|---:|
|dense-l2-n1024-identical-k1|adaptive/accept_id|9.6974 [9.648,9.8046]|0 [0,0]|0.10312 [0.10199,0.10365]|5/5|
|dense-l2-n1024-identical-k1|adaptive/accept_static_degree|9.04 [8.9356,9.0733]|0 [0,0]|0.11062 [0.11021,0.11191]|5/5|
|dense-l2-n1024-identical-k1|graph/adaptive|16.73 [16.651,16.885]|0 [0,0]|0.059771 [0.059223,0.060058]|5/5|
|dense-l2-n1024-identical-k1|paper/adaptive|9.4486 [9.3237,9.4943]|0 [0,0]|0.10584 [0.10533,0.10725]|5/5|
|dense-l2-n4096-identical-k1|adaptive/accept_id|16.417 [16.3,16.635]|0 [0,0]|0.060914 [0.060113,0.06135]|5/5|
|dense-l2-n4096-identical-k1|adaptive/accept_static_degree|15.26 [15.01,15.609]|0 [0,0]|0.06553 [0.064065,0.066622]|5/5|
|dense-l2-n4096-identical-k1|graph/adaptive|46.376 [45.832,46.682]|0 [0,0]|0.021563 [0.021422,0.021819]|5/5|
|dense-l2-n4096-identical-k1|paper/adaptive|22.062 [21.852,22.234]|0 [0,0]|0.045326 [0.044976,0.045762]|5/5|
|main-l1-n128-uniform-k1|adaptive/accept_id|1.2104 [1.0479,1.2213]|0 [0,0]|0.8262 [0.81883,0.95426]|5/5|
|main-l1-n128-uniform-k1|adaptive/accept_static_degree|1.1007 [1.0156,1.1384]|0 [0,0]|0.90851 [0.87844,0.98464]|5/5|
|main-l1-n128-uniform-k1|graph/adaptive|0.91828 [0.90228,0.99025]|0 [0,0]|1.089 [1.0098,1.1083]|5/5|
|main-l1-n128-uniform-k1|paper/adaptive|0.70377 [0.69627,0.80191]|0 [0,0]|1.4209 [1.247,1.4362]|5/5|
|main-l1-n128-zipf-k1|adaptive/accept_id|1.7511 [1.721,1.9345]|0 [0,0]|0.57108 [0.51692,0.58107]|5/5|
|main-l1-n128-zipf-k1|adaptive/accept_static_degree|1.5801 [1.5523,1.7179]|0 [0,0]|0.63288 [0.58211,0.64422]|5/5|
|main-l1-n128-zipf-k1|graph/adaptive|0.95019 [0.93437,1.0142]|0 [0,0]|1.0524 [0.98602,1.0702]|5/5|
|main-l1-n128-zipf-k1|paper/adaptive|0.84351 [0.79994,0.87917]|0 [0,0]|1.1855 [1.1374,1.2501]|5/5|
|main-l1-n2048-uniform-k1|adaptive/accept_id|1.5839 [1.5764,1.632]|0 [0,0]|0.63134 [0.61274,0.63437]|5/5|
|main-l1-n2048-uniform-k1|adaptive/accept_static_degree|1.3953 [1.3875,1.4211]|0 [0,0]|0.71668 [0.70369,0.72073]|5/5|
|main-l1-n2048-uniform-k1|graph/adaptive|0.86663 [0.85114,0.88075]|0 [0,0]|1.1539 [1.1354,1.1749]|5/5|
|main-l1-n2048-uniform-k1|paper/adaptive|1.1345 [1.0875,1.1571]|0 [0,0]|0.88147 [0.86421,0.91956]|5/5|
|main-l1-n2048-zipf-k1|adaptive/accept_id|2.56 [2.4969,2.5921]|0 [0,0]|0.39063 [0.38578,0.40049]|5/5|
|main-l1-n2048-zipf-k1|adaptive/accept_static_degree|2.1501 [2.1115,2.157]|0 [0,0]|0.46509 [0.4636,0.47361]|5/5|
|main-l1-n2048-zipf-k1|graph/adaptive|3.0637 [3.0437,3.2916]|0 [0,0]|0.3264 [0.3038,0.32855]|5/5|
|main-l1-n2048-zipf-k1|paper/adaptive|6.9362 [5.9622,7.5727]|0 [0,0]|0.14417 [0.13205,0.16772]|5/5|
|main-l1-n40-uniform-k1|adaptive/accept_id|1.0418 [1.019,1.1075]|0 [0,0]|0.9599 [0.90297,0.98131]|5/5|
|main-l1-n40-uniform-k1|adaptive/accept_static_degree|1.0138 [0.9442,1.0639]|0 [0,0]|0.98642 [0.93998,1.0591]|5/5|
|main-l1-n40-uniform-k1|graph/adaptive|0.98798 [0.92815,1.0497]|0 [0,0]|1.0122 [0.9527,1.0774]|5/5|
|main-l1-n40-uniform-k1|paper/adaptive|0.71379 [0.67377,0.73928]|0 [0,0]|1.401 [1.3527,1.4842]|5/5|
|main-l1-n40-zipf-k1|adaptive/accept_id|1.843 [1.5565,1.9535]|0 [0,0]|0.5426 [0.51191,0.64245]|5/5|
|main-l1-n40-zipf-k1|adaptive/accept_static_degree|1.6509 [1.4279,1.7181]|0 [0,0]|0.60573 [0.58204,0.70031]|5/5|
|main-l1-n40-zipf-k1|graph/adaptive|0.8161 [0.80676,0.84016]|0 [0,0]|1.2253 [1.1903,1.2395]|5/5|
|main-l1-n40-zipf-k1|paper/adaptive|0.59992 [0.53307,0.62768]|0 [0,0]|1.6669 [1.5932,1.8759]|5/5|
|main-l1-n512-uniform-k1|adaptive/accept_id|1.2727 [1.2171,1.2905]|0 [0,0]|0.78573 [0.77492,0.8216]|5/5|
|main-l1-n512-uniform-k1|adaptive/accept_static_degree|1.1615 [1.1166,1.1787]|0 [0,0]|0.86093 [0.84843,0.8956]|5/5|
|main-l1-n512-uniform-k1|graph/adaptive|0.92077 [0.90744,0.93444]|0 [0,0]|1.086 [1.0702,1.102]|5/5|
|main-l1-n512-uniform-k1|paper/adaptive|0.75938 [0.73833,0.81042]|0 [0,0]|1.3169 [1.2339,1.3544]|5/5|
|main-l1-n512-zipf-k1|adaptive/accept_id|2.1591 [2.0868,2.1974]|0 [0,0]|0.46316 [0.45508,0.47919]|5/5|
|main-l1-n512-zipf-k1|adaptive/accept_static_degree|1.8577 [1.8036,1.8804]|0 [0,0]|0.53831 [0.53181,0.55444]|5/5|
|main-l1-n512-zipf-k1|graph/adaptive|1.5031 [1.4376,1.5509]|0 [0,0]|0.66529 [0.64479,0.69562]|5/5|
|main-l1-n512-zipf-k1|paper/adaptive|2.1236 [1.8739,2.2183]|0 [0,0]|0.47091 [0.45079,0.53365]|5/5|
|main-l2-n128-uniform-k1|adaptive/accept_id|1.1431 [1.081,1.2299]|0 [0,0]|0.87484 [0.81306,0.92508]|5/5|
|main-l2-n128-uniform-k1|adaptive/accept_static_degree|0.95361 [0.94693,1.0069]|0 [0,0]|1.0486 [0.99312,1.056]|5/5|
|main-l2-n128-uniform-k1|graph/adaptive|0.99068 [0.9539,1.0016]|0 [0,0]|1.0094 [0.99843,1.0483]|5/5|
|main-l2-n128-uniform-k1|paper/adaptive|0.8249 [0.78649,0.84222]|0 [0,0]|1.2123 [1.1873,1.2715]|5/5|
|main-l2-n128-zipf-k1|adaptive/accept_id|2.3601 [2.2427,2.4383]|2 [0,3]|0.4376 [0.41696,0.45732]|5/5|
|main-l2-n128-zipf-k1|adaptive/accept_static_degree|1.8451 [1.6977,1.9738]|0 [0,0]|0.54198 [0.50665,0.58902]|5/5|
|main-l2-n128-zipf-k1|graph/adaptive|1.0909 [1.0313,1.1545]|0 [0,0]|0.91666 [0.86615,0.96964]|5/5|
|main-l2-n128-zipf-k1|paper/adaptive|1.0102 [0.96592,1.1043]|0 [0,0]|0.98991 [0.90555,1.0353]|5/5|
|main-l2-n2048-uniform-k1|adaptive/accept_id|2.2776 [2.2546,2.2839]|43 [38,46]|0.45363 [0.45052,0.45858]|5/5|
|main-l2-n2048-uniform-k1|adaptive/accept_static_degree|1.7338 [1.727,1.7391]|-6 [-8,-3]|0.57448 [0.57217,0.57656]|5/5|
|main-l2-n2048-uniform-k1|graph/adaptive|0.88601 [0.87822,0.93207]|0 [0,0]|1.1287 [1.0729,1.1387]|5/5|
|main-l2-n2048-uniform-k1|paper/adaptive|2.2465 [2.0254,2.348]|0 [0,0]|0.44513 [0.4259,0.49372]|5/5|
|main-l2-n2048-zipf-k1|adaptive/accept_id|7.1143 [6.779,7.4991]|30 [23,32]|0.14849 [0.14356,0.15894]|5/5|
|main-l2-n2048-zipf-k1|adaptive/accept_static_degree|5.1022 [4.8587,5.3589]|-1 [-2,0]|0.19599 [0.18616,0.2049]|5/5|
|main-l2-n2048-zipf-k1|graph/adaptive|4.2486 [4.054,4.4714]|0 [0,0]|0.23537 [0.22364,0.24667]|5/5|
|main-l2-n2048-zipf-k1|paper/adaptive|4.5775 [4.2206,4.8763]|0 [0,0]|0.21846 [0.20507,0.23694]|5/5|
|main-l2-n40-uniform-k1|adaptive/accept_id|1.1738 [1.0072,1.2187]|0 [0,0]|0.85196 [0.82057,0.99284]|5/5|
|main-l2-n40-uniform-k1|adaptive/accept_static_degree|1.0328 [0.9035,1.0932]|0 [0,0]|0.96822 [0.91471,1.1068]|5/5|
|main-l2-n40-uniform-k1|graph/adaptive|1.0281 [0.95126,1.039]|0 [0,0]|0.97267 [0.96244,1.0512]|5/5|
|main-l2-n40-uniform-k1|paper/adaptive|0.72869 [0.69865,0.81477]|0 [0,0]|1.3723 [1.2273,1.4313]|5/5|
|main-l2-n40-zipf-k1|adaptive/accept_id|1.9873 [1.8509,2.2095]|1 [0,1]|0.52415 [0.47415,0.55608]|5/5|
|main-l2-n40-zipf-k1|adaptive/accept_static_degree|1.5751 [1.5524,1.8419]|0 [0,0]|0.63487 [0.54293,0.64418]|5/5|
|main-l2-n40-zipf-k1|graph/adaptive|0.88536 [0.85723,0.96725]|0 [0,0]|1.1295 [1.0339,1.1665]|5/5|
|main-l2-n40-zipf-k1|paper/adaptive|0.71292 [0.64053,0.72542]|0 [0,0]|1.4027 [1.3785,1.5612]|5/5|
|main-l2-n512-uniform-k1|adaptive/accept_id|1.5032 [1.4493,1.5585]|3 [1,5]|0.67268 [0.64309,0.69754]|5/5|
|main-l2-n512-uniform-k1|adaptive/accept_static_degree|1.2206 [1.1752,1.2594]|0 [0,0]|0.81927 [0.79404,0.85094]|5/5|
|main-l2-n512-uniform-k1|graph/adaptive|0.87638 [0.86917,0.89632]|0 [0,0]|1.1411 [1.1157,1.1505]|5/5|
|main-l2-n512-uniform-k1|paper/adaptive|0.80129 [0.78667,0.82032]|0 [0,0]|1.248 [1.219,1.2712]|5/5|
|main-l2-n512-zipf-k1|adaptive/accept_id|3.7058 [3.5499,4.002]|6 [4,13]|0.27709 [0.2605,0.3039]|5/5|
|main-l2-n512-zipf-k1|adaptive/accept_static_degree|2.725 [2.6614,2.9907]|0 [0,0]|0.36697 [0.33437,0.37574]|5/5|
|main-l2-n512-zipf-k1|graph/adaptive|1.9043 [1.7374,2.0013]|0 [0,0]|0.52514 [0.49968,0.57559]|5/5|
|main-l2-n512-zipf-k1|paper/adaptive|2.0117 [1.9613,2.1687]|0 [0,0]|0.4971 [0.46111,0.50987]|5/5|
|main-l3-n128-uniform-k1|adaptive/accept_id|1.4287 [1.3273,1.5358]|0 [0,0]|0.69993 [0.65112,0.75339]|5/5|
|main-l3-n128-uniform-k1|adaptive/accept_static_degree|0.48777 [0.46287,0.51806]|0 [0,0]|2.0502 [1.9303,2.1604]|5/5|
|main-l3-n128-uniform-k1|graph/adaptive|0.85524 [0.81651,0.8938]|0 [0,0]|1.1693 [1.1188,1.2247]|5/5|
|main-l3-n128-uniform-k1|paper/adaptive|0.67321 [0.64188,0.71819]|0 [0,0]|1.4854 [1.3924,1.5579]|5/5|
|main-l3-n128-zipf-k1|adaptive/accept_id|3.7537 [3.6633,3.8688]|3 [1,3]|0.28639 [0.26792,0.29397]|5/5|
|main-l3-n128-zipf-k1|adaptive/accept_static_degree|1.1374 [1.1156,1.1716]|0 [-1,0]|0.87601 [0.85353,0.88307]|5/5|
|main-l3-n128-zipf-k1|graph/adaptive|0.98023 [0.91321,1.1253]|0 [0,0]|1.0202 [0.88868,1.095]|5/5|
|main-l3-n128-zipf-k1|paper/adaptive|0.89292 [0.83318,0.91429]|0 [0,0]|1.1199 [1.0937,1.2002]|5/5|
|main-l3-n2048-uniform-k1|adaptive/accept_id|4.3796 [4.3207,4.4565]|73 [59,75]|0.24454 [0.24042,0.24791]|5/5|
|main-l3-n2048-uniform-k1|adaptive/accept_static_degree|1.0778 [1.0645,1.0901]|-14 [-21,-14]|0.9145 [0.89984,0.92762]|5/5|
|main-l3-n2048-uniform-k1|graph/adaptive|0.58968 [0.58227,0.5952]|0 [0,0]|1.6958 [1.6801,1.7174]|5/5|
|main-l3-n2048-uniform-k1|paper/adaptive|2.2154 [1.9096,2.512]|0 [0,0]|0.45139 [0.39808,0.52368]|5/5|
|main-l3-n2048-zipf-k1|adaptive/accept_id|8.3813 [8.2078,8.707]|28 [23,30]|0.13469 [0.13233,0.13748]|5/5|
|main-l3-n2048-zipf-k1|adaptive/accept_static_degree|1.7607 [1.733,1.8246]|0 [-2,1]|0.56943 [0.54296,0.57704]|5/5|
|main-l3-n2048-zipf-k1|graph/adaptive|7.0368 [6.4641,7.2451]|0 [0,0]|0.14211 [0.13802,0.1547]|5/5|
|main-l3-n2048-zipf-k1|paper/adaptive|4.8259 [4.1232,5.0208]|0 [0,0]|0.20722 [0.19917,0.24253]|5/5|
|main-l3-n40-uniform-k1|adaptive/accept_id|1.3355 [1.0389,1.45]|0 [0,0]|0.74881 [0.68963,0.96256]|5/5|
|main-l3-n40-uniform-k1|adaptive/accept_static_degree|0.51871 [0.39387,0.57327]|0 [0,0]|1.9279 [1.7444,2.5389]|5/5|
|main-l3-n40-uniform-k1|graph/adaptive|0.95362 [0.91895,1.0038]|0 [0,0]|1.0486 [0.99625,1.0882]|5/5|
|main-l3-n40-uniform-k1|paper/adaptive|0.69204 [0.61826,0.84206]|0 [0,0]|1.445 [1.1876,1.6174]|5/5|
|main-l3-n40-zipf-k1|adaptive/accept_id|2.9311 [2.7309,3.0763]|1 [0,2]|0.34889 [0.34117,0.3821]|5/5|
|main-l3-n40-zipf-k1|adaptive/accept_static_degree|1.0849 [1.0317,1.1393]|0 [0,0]|0.92176 [0.87772,0.96923]|5/5|
|main-l3-n40-zipf-k1|graph/adaptive|0.72913 [0.64122,0.7349]|0 [0,0]|1.3715 [1.3607,1.5595]|5/5|
|main-l3-n40-zipf-k1|paper/adaptive|0.54109 [0.51678,0.57465]|0 [0,0]|1.8481 [1.7402,1.9351]|5/5|
|main-l3-n512-uniform-k1|adaptive/accept_id|2.199 [2.1221,2.2299]|5 [3,8]|0.4581 [0.45524,0.47694]|5/5|
|main-l3-n512-uniform-k1|adaptive/accept_static_degree|0.66009 [0.65197,0.66804]|-1 [-2,0]|1.5113 [1.4969,1.527]|5/5|
|main-l3-n512-uniform-k1|graph/adaptive|0.67813 [0.6648,0.6822]|0 [0,0]|1.4746 [1.4658,1.5042]|5/5|
|main-l3-n512-uniform-k1|paper/adaptive|0.6375 [0.61617,0.65878]|0 [0,0]|1.5686 [1.518,1.6229]|5/5|
|main-l3-n512-zipf-k1|adaptive/accept_id|5.4642 [5.1704,5.6115]|9 [7,14]|0.20429 [0.19144,0.21996]|5/5|
|main-l3-n512-zipf-k1|adaptive/accept_static_degree|1.3465 [1.3004,1.4086]|0 [-1,1]|0.74268 [0.70291,0.77568]|5/5|
|main-l3-n512-zipf-k1|graph/adaptive|2.3149 [2.1743,2.4383]|0 [0,0]|0.43199 [0.41013,0.45993]|5/5|
|main-l3-n512-zipf-k1|paper/adaptive|1.8489 [1.7961,1.9436]|0 [0,0]|0.54085 [0.5145,0.55676]|5/5|
|main-l4-n128-uniform-k1|adaptive/accept_id|2.027 [1.9962,2.4361]|0 [0,3]|0.49641 [0.42189,0.50655]|5/5|
|main-l4-n128-uniform-k1|adaptive/accept_static_degree|0.42663 [0.40945,0.49323]|0 [0,0]|2.3439 [2.0275,2.4423]|5/5|
|main-l4-n128-uniform-k1|graph/adaptive|0.6273 [0.54745,0.65391]|0 [0,0]|1.5941 [1.5293,1.8266]|5/5|
|main-l4-n128-uniform-k1|paper/adaptive|0.52334 [0.45542,0.54412]|0 [0,0]|1.9108 [1.8378,2.1958]|5/5|
|main-l4-n128-zipf-k1|adaptive/accept_id|5.6846 [5.3601,5.9124]|3 [3,6]|0.19411 [0.18865,0.22094]|5/5|
|main-l4-n128-zipf-k1|adaptive/accept_static_degree|0.97656 [0.93267,1.008]|0 [0,1]|1.024 [0.9921,1.1037]|5/5|
|main-l4-n128-zipf-k1|graph/adaptive|0.78921 [0.74421,0.82645]|0 [0,0]|1.2671 [1.21,1.3437]|5/5|
|main-l4-n128-zipf-k1|paper/adaptive|0.60671 [0.58316,0.63107]|0 [0,0]|1.6482 [1.5846,1.7148]|5/5|
|main-l4-n2048-uniform-k1|adaptive/accept_id|8.2107 [8.1673,8.2913]|85 [76,97]|0.13537 [0.13375,0.13829]|5/5|
|main-l4-n2048-uniform-k1|adaptive/accept_static_degree|1.0827 [1.0779,1.101]|-8 [-20,-4]|0.91183 [0.9029,0.91674]|5/5|
|main-l4-n2048-uniform-k1|graph/adaptive|0.35937 [0.35444,0.36097]|0 [0,0]|2.7826 [2.7703,2.8214]|5/5|
|main-l4-n2048-uniform-k1|paper/adaptive|1.6264 [1.4114,1.8377]|0 [0,0]|0.61485 [0.54416,0.70849]|5/5|
|main-l4-n2048-zipf-k1|adaptive/accept_id|12.556 [12.498,12.667]|24 [21,29]|0.094735 [0.093579,0.099167]|5/5|
|main-l4-n2048-zipf-k1|adaptive/accept_static_degree|1.3095 [1.305,1.323]|0 [-1,1]|0.76628 [0.75075,0.76897]|5/5|
|main-l4-n2048-zipf-k1|graph/adaptive|6.8432 [6.6698,6.932]|0 [0,0]|0.14613 [0.14426,0.14993]|5/5|
|main-l4-n2048-zipf-k1|paper/adaptive|3.4982 [3.4304,3.6014]|0 [0,0]|0.28586 [0.27767,0.29151]|5/5|
|main-l4-n40-uniform-k1|adaptive/accept_id|1.4665 [1.127,1.8804]|0 [0,0]|0.68189 [0.53179,0.8873]|5/5|
|main-l4-n40-uniform-k1|adaptive/accept_static_degree|0.35858 [0.28368,0.46116]|0 [0,0]|2.7888 [2.1684,3.5251]|5/5|
|main-l4-n40-uniform-k1|graph/adaptive|0.86404 [0.66664,1.0003]|0 [0,0]|1.1574 [0.99974,1.5001]|5/5|
|main-l4-n40-uniform-k1|paper/adaptive|0.66107 [0.53857,0.8389]|0 [0,0]|1.5127 [1.192,1.8568]|5/5|
|main-l4-n40-zipf-k1|adaptive/accept_id|4.3927 [3.9949,4.4843]|1 [1,1]|0.24446 [0.23787,0.26505]|5/5|
|main-l4-n40-zipf-k1|adaptive/accept_static_degree|0.9401 [0.83189,0.94821]|0 [0,0]|1.0637 [1.0546,1.2021]|5/5|
|main-l4-n40-zipf-k1|graph/adaptive|0.54209 [0.52796,0.55706]|0 [0,0]|1.8447 [1.7951,1.8941]|5/5|
|main-l4-n40-zipf-k1|paper/adaptive|0.42881 [0.4139,0.44383]|0 [0,0]|2.3321 [2.2531,2.416]|5/5|
|main-l4-n512-uniform-k1|adaptive/accept_id|4.2907 [4.2053,4.4915]|13 [9,17]|0.23999 [0.23411,0.24854]|5/5|
|main-l4-n512-uniform-k1|adaptive/accept_static_degree|0.73009 [0.71884,0.76803]|-1 [-2,0]|1.3621 [1.302,1.3874]|5/5|
|main-l4-n512-uniform-k1|graph/adaptive|0.38362 [0.37743,0.38762]|0 [0,0]|2.6068 [2.5799,2.6495]|5/5|
|main-l4-n512-uniform-k1|paper/adaptive|0.43974 [0.43419,0.44549]|0 [0,0]|2.2741 [2.2447,2.3031]|5/5|
|main-l4-n512-zipf-k1|adaptive/accept_id|8.7276 [8.5661,8.9026]|7 [7,11]|0.12951 [0.12774,0.1362]|5/5|
|main-l4-n512-zipf-k1|adaptive/accept_static_degree|1.1088 [1.0821,1.1314]|0 [-1,1]|0.90187 [0.86889,0.92415]|5/5|
|main-l4-n512-zipf-k1|graph/adaptive|2.1086 [2.0785,2.3305]|0 [0,0]|0.47424 [0.42909,0.48111]|5/5|
|main-l4-n512-zipf-k1|paper/adaptive|1.3989 [1.3145,1.4912]|0 [0,0]|0.71486 [0.67061,0.76074]|5/5|
|paper_k-l2-n2048-uniform-k2|adaptive/accept_id|2.2432 [2.2232,2.2826]|42 [36,45]|0.45956 [0.44965,0.46471]|5/5|
|paper_k-l2-n2048-uniform-k2|adaptive/accept_static_degree|1.7098 [1.6951,1.7436]|-8 [-9,-4]|0.58277 [0.56985,0.58617]|5/5|
|paper_k-l2-n2048-uniform-k2|graph/adaptive|0.88768 [0.86513,0.8939]|0 [0,0]|1.1265 [1.1187,1.1559]|5/5|
|paper_k-l2-n2048-uniform-k2|paper/adaptive|1.4993 [1.3701,1.5641]|0 [0,0]|0.667 [0.63936,0.72985]|5/5|
|paper_k-l2-n2048-zipf-k2|adaptive/accept_id|6.1198 [5.8182,6.3224]|26 [20,29]|0.17141 [0.16866,0.18311]|5/5|
|paper_k-l2-n2048-zipf-k2|adaptive/accept_static_degree|4.3676 [4.1964,4.5483]|-4 [-7,-3]|0.22737 [0.21726,0.23457]|5/5|
|paper_k-l2-n2048-zipf-k2|graph/adaptive|4.8953 [4.6677,5.1753]|0 [0,0]|0.20428 [0.19323,0.21424]|5/5|
|paper_k-l2-n2048-zipf-k2|paper/adaptive|3.7462 [3.4705,3.8882]|0 [0,0]|0.26694 [0.25719,0.28814]|5/5|
|paper_k-l2-n40-uniform-k2|adaptive/accept_id|1.1128 [1.0288,1.1565]|-1 [-1,0]|0.87557 [0.84249,0.97204]|5/5|
|paper_k-l2-n40-uniform-k2|adaptive/accept_static_degree|0.98078 [0.90739,1.0229]|-1 [-1,0]|0.99345 [0.95258,1.1021]|5/5|
|paper_k-l2-n40-uniform-k2|graph/adaptive|1.0291 [0.97846,1.1079]|0 [0,0]|0.97174 [0.90259,1.022]|5/5|
|paper_k-l2-n40-uniform-k2|paper/adaptive|0.77091 [0.73199,0.82921]|0 [0,0]|1.2972 [1.206,1.3661]|5/5|
|paper_k-l2-n40-zipf-k2|adaptive/accept_id|1.9293 [1.8182,2.1023]|-1 [-2,0]|0.50228 [0.45302,0.52799]|5/5|
|paper_k-l2-n40-zipf-k2|adaptive/accept_static_degree|1.5911 [1.5553,1.7439]|-2 [-2,-1]|0.59325 [0.52129,0.60336]|5/5|
|paper_k-l2-n40-zipf-k2|graph/adaptive|0.8986 [0.85488,0.91409]|0 [0,0]|1.1128 [1.094,1.1698]|5/5|
|paper_k-l2-n40-zipf-k2|paper/adaptive|0.67264 [0.66297,0.70268]|0 [0,0]|1.4867 [1.4231,1.5084]|5/5|
|paper_k-l2-n512-uniform-k2|adaptive/accept_id|1.53 [1.4639,1.5858]|1 [0,3]|0.6565 [0.63061,0.68759]|5/5|
|paper_k-l2-n512-uniform-k2|adaptive/accept_static_degree|1.2443 [1.184,1.2573]|-2 [-3,-1]|0.80188 [0.79358,0.84091]|5/5|
|paper_k-l2-n512-uniform-k2|graph/adaptive|0.87174 [0.86037,0.88308]|0 [0,0]|1.1471 [1.1324,1.1623]|5/5|
|paper_k-l2-n512-uniform-k2|paper/adaptive|0.75083 [0.74047,1.0565]|0 [0,0]|1.3319 [0.94651,1.3505]|5/5|
|paper_k-l2-n512-zipf-k2|adaptive/accept_id|3.4579 [3.3137,3.6742]|5 [1,13]|0.29114 [0.28182,0.32555]|5/5|
|paper_k-l2-n512-zipf-k2|adaptive/accept_static_degree|2.5391 [2.3391,2.7316]|-2 [-5,0]|0.38387 [0.3636,0.42182]|5/5|
|paper_k-l2-n512-zipf-k2|graph/adaptive|2.0895 [1.8418,2.1754]|0 [0,0]|0.47858 [0.45968,0.54296]|5/5|
|paper_k-l2-n512-zipf-k2|paper/adaptive|1.7338 [1.6714,1.8305]|0 [0,0]|0.57677 [0.5463,0.59832]|5/5|
|scale-l2-n8192-uniform-k1|adaptive/accept_id|3.8646 [3.7931,3.8978]|253 [231,267]|0.28377 [0.2781,0.28783]|5/5|
|scale-l2-n8192-uniform-k1|adaptive/accept_static_degree|2.7495 [2.7356,2.7925]|-144 [-162,-124]|0.34709 [0.33965,0.35109]|5/5|
|scale-l2-n8192-uniform-k1|graph/adaptive|1.6747 [1.6585,1.6783]|0 [0,0]|0.59713 [0.59586,0.60294]|5/5|
|scale-l2-n8192-uniform-k1|paper/adaptive|22.732 [20.975,24.428]|0 [0,0]|0.043991 [0.040936,0.047677]|5/5|
|scale-l2-n8192-zipf-k1|adaptive/accept_id|14.054 [13.507,15.02]|91 [87,93]|0.078412 [0.073321,0.081968]|5/5|
|scale-l2-n8192-zipf-k1|adaptive/accept_static_degree|9.8542 [9.5673,10.476]|-2 [-3,3]|0.10127 [0.095762,0.10419]|5/5|
|scale-l2-n8192-zipf-k1|graph/adaptive|10.271 [10.057,10.818]|0 [0,0]|0.09736 [0.092439,0.099432]|5/5|
|scale-l2-n8192-zipf-k1|paper/adaptive|11.67 [10.711,13.044]|0 [0,0]|0.085691 [0.076661,0.093361]|5/5|
