#!/usr/bin/env python3
"""Deterministic report tables/facts derived from the audited full data (not a recommendation engine)."""
import argparse
import collections
import csv
import json
from pathlib import Path
import statistics as st
import run

p=argparse.ArgumentParser();p.add_argument('directory',type=Path);args=p.parse_args();root=args.directory;out=root/'summary'
def read(name):
    rows=list(csv.DictReader((out/name).open()))
    for r in rows:
        for k in ('seed','repetition','n','arity','workers','median','minimum','maximum','commit_delta','batch_delta_ms','commits','baseline_commits','crossover_us','rate_ratio','batch_ms','baseline_batch_ms'):
            if k in r:r[k]=float(r[k]) if r[k] else None
    return rows
metrics=read('metrics.csv');pairs=read('paired.csv');rawpairs=read('paired_observations.csv');roots=read('sensitivity_roots.csv')
def m(c,v,metric):return next(r['median'] for r in metrics if r['condition']==c and r['variant']==v and r['metric']==metric)
def paired(c,v,b,metric):return next(r for r in pairs if r['condition']==c and r['variant']==v and r['baseline']==b and r['metric']==metric)
variants=['native','accept_id','accept_static_degree','eas_k1_adaptive','eas_k2_adaptive']
lines=['|分布|n|方式|確定件数|selector ms|batch ms|有効処理率 /秒|','|---|---:|---|---:|---:|---:|---:|']
for dist in ('uniform','zipf'):
    for n in (128,512,2048,8192,32768):
        c=f'l2-n{n}-{dist}-w1'
        for v in variants:
            vals=[m(c,v,q) for q in ('commit_count','selector_ms','batch_ms','effective_commits_per_second')]
            lines.append(f'|{dist}|{n}|{v}|{vals[0]:.0f}|{vals[1]:.5f}|{vals[2]:.5f}|{vals[3]:.1f}|')
(out/'main_table_ja.md').write_text('\n'.join(lines)+'\n')
lines=['|n|batch_id|native|accept_id|static|EAS k=2|EAS k=1|','|---:|---:|---:|---:|---:|---:|---:|'];repro=[]
for n,batch,expected in ((8192,1208417051,[538,936,1042,1038,1041]),(32768,566257870,[711,1829,2125,2116,2119])):
    c=f'l2-n{n}-zipf-w1';actual=[m(c,v,'commit_count') for v in ('native','accept_id','accept_static_degree','eas_k2_adaptive','eas_k1_adaptive')]
    repro.append(dict(n=n,batch_id=batch,previous_python_medians=expected,cpp_medians=actual,equal=expected==actual))
    lines.append(f'|{n}|{batch}|'+'|'.join(f'{v:.0f}' for v in actual)+'|')
(out/'count_reproduction_ja.md').write_text('\n'.join(lines)+'\n')
conditions=[]
for c in dict.fromkeys(r['condition'] for r in metrics if r['variant']=='eas_k1_adaptive' and r['suite']!='control'):
    meta=next(r for r in metrics if r['condition']==c)
    row={k:meta[k] for k in ('condition','suite','n','arity','distribution','workers')}
    for b in ('accept_id','accept_static_degree','native'):
        chosen=[r for r in rawpairs if r['condition']==c and r['variant']=='eas_k1_adaptive' and r['baseline']==b]
        rs=[r for r in roots if r['condition']==c and r['variant']=='eas_k1_adaptive' and r['baseline']==b]
        seed_roots=[st.median(r['crossover_us'] for r in rs if r['seed']==s and r['wins_for']=='c_above') for s in sorted({r['seed'] for r in rs if r['wins_for']=='c_above'})]
        row[b]={q:{k:paired(c,'eas_k1_adaptive',b,q)[k] for k in ('median','minimum','maximum')} for q in ('commit_delta','batch_delta_ms','rate_ratio')}
        row[b].update(measured_pairs=len(chosen),quality_cost_counts=dict(collections.Counter(r['quality_cost'] for r in chosen)),
                       rate_wins=sum(r['rate_ratio']>1 for r in chosen),root_cases=dict(collections.Counter(r['wins_for'] for r in rs)),
                       positive_root_seed_count=len(seed_roots),crossover_us_seed_median=st.median(seed_roots) if seed_roots else None,
                       crossover_us_seed_range=[min(seed_roots),max(seed_roots)] if seed_roots else None)
    conditions.append(row)
controls=[]
for c in ('l2-n8192-uniform-w1','l2-n8192-zipf-w1','l2-n4096-identical-w1'):
    q=paired(c,'eas_k1_adaptive','eas_k1_graph','selector_speedup')
    controls.append(dict(condition=c,graph_over_adaptive_selector={k:q[k] for k in ('median','minimum','maximum')},
                         modes={v:{metric:m(c,v,metric) for metric in ('commit_count','batch_ms','selector_ms','selector_degree_queries','selector_degree_requeries','selector_switches','selector_switch_round','selector_build_ms','selector_select_ms','selector_switch_ms')} for v in ('eas_k1_graph','eas_k1_lazy','eas_k1_profile','eas_k1_adaptive')}))
run.save_json(out/'report_facts.json',dict(count_reproduction=repro,conditions=conditions,controls=controls))
print(json.dumps(dict(count_reproduction=repro,conditions=conditions,controls=controls)))
