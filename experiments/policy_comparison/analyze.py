#!/usr/bin/env python3
"""Audit raw records, then summarize repeat noise within seeds and paired policy comparisons."""
import argparse
import collections
import csv
import json
import math
from pathlib import Path
import statistics as st
import tarfile
import run

LABELS=['native','accept_id','accept_static_degree','eas_k1_adaptive','eas_k2_adaptive']
KEYS=['condition','suite','arity','n','distribution','workers','variant','policy','policy_k','implementation']
METRICS=['commit_count','abort_count','batch_ms','selector_ms','effective_commits_per_second','ms_per_commit',
         'peak_rss_kib','runner_peak_rss_kib','read_wall_ms','commit_wall_ms','extract_ms',
         'read_worker_ms','commit_worker_ms','reservation_worker_ms','dependency_worker_ms','apply_worker_ms','sync_wait_ms']


def stats(values):
    values=sorted(v for v in values if v is not None and math.isfinite(v))
    if not values:return dict(count=0,median=None,minimum=None,maximum=None,q1=None,q3=None,iqr=None)
    def quantile(q):
        i=(len(values)-1)*q;lo=int(i);hi=min(lo+1,len(values)-1)
        return values[lo]+(values[hi]-values[lo])*(i-lo)
    return dict(count=len(values),median=st.median(values),minimum=values[0],maximum=values[-1],q1=quantile(.25),q3=quantile(.75),iqr=quantile(.75)-quantile(.25))


def csv_write(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def read_trace(path):
    lines=path.read_text().splitlines();header=lines[0].split()
    items=[]
    for line in lines[1:]:
        tid,keys=line.split('\t');items.append((int(tid),set(map(int,keys.split(','))) if keys else set()))
    return header,items


def audit(output,records):
    errors=[];trace_cache={};seen={};legacy_count=0
    expected=run.jobs_for(json.loads((output/'plan.json').read_text()),json.loads((output/'manifest.json').read_text())['conditions'])
    if [r['id'] for r in records] != [j['id'] for j in expected]:errors.append('schedule/order/coverage mismatch')
    trace_meta=json.loads((output/'trace_manifest.json').read_text())['traces']
    previous=run.ROOT/'experiments/eas/results/full/raw_data.tar.gz'
    with tarfile.open(previous,'r:gz') as archive:
        names=set(archive.getnames())
        for r in records:
            if r['status']!='ok':continue
            path=run.local_raw(output,r)
            if run.sha256(path)!=r['raw_sha256']:errors.append(r['id']+': raw hash')
            raw=json.loads(path.read_text())
            for k in ('mode','policy','policy_k','implementation','workers','seed','batch_id','n'):
                if raw[k]!=r[k]:errors.append(r['id']+': metadata '+k)
            trace=output/'traces'/Path(r['trace_path']).name
            if trace.name not in trace_cache:
                if run.sha256(trace)!=r['trace_sha256']:errors.append(trace.name+': trace hash')
                header,items=read_trace(trace)
                if [i for i,_ in items]!=list(range(1,r['n']+1)):errors.append(trace.name+': ID order')
                if any(len(s)!=r['arity'] for _,s in items):errors.append(trace.name+': distinct arity')
                trace_cache[trace.name]=items
            items=trace_cache[trace.name];d=raw['decisions'];mask=d['commit']
            if len(mask)!=len(items) or any(c not in (0,1) for c in mask):raise ValueError('invalid mask')
            cert=[tid for (tid,_),c in zip(items,mask) if c]
            if cert!=d['certificate'] or len(cert)!=raw['commit_count'] or raw['abort_count']!=len(items)-len(cert):errors.append(r['id']+': counts/certificate')
            used=set()
            for (_,s),c in zip(items,mask):
                if c:
                    if used&s:errors.append(r['id']+': intersecting commits')
                    used|=s
            if r['policy'].startswith('accept_'):
                if d['abort_rounds']:errors.append(r['id']+': fabricated rounds')
                if sorted(d['consideration_order'])!=[tid for tid,_ in items]:errors.append(r['id']+': consideration order partition')
                if set(d['rejected_ids'])!={tid for (tid,_),c in zip(items,mask) if not c}:errors.append(r['id']+': rejection partition')
                if any(not c and not s&used for (_,s),c in zip(items,mask)):errors.append(r['id']+': not maximal')
                # Replay saved order independently. This checks reservation semantics on every large trace.
                order=d['consideration_order'];by_id=dict(items);accepted=set();actual=[];rejected=[]
                for tid in order:
                    if accepted&by_id[tid]:rejected.append(tid)
                    else:accepted|=by_id[tid];actual.append(tid)
                if sorted(actual)!=cert or rejected!=d['rejected_ids']:errors.append(r['id']+': greedy replay')
                if r['policy']=='accept_id' and (order!=sorted(order) or any(raw['selector'][k] for k in ('subsets','incidences','degree_queries','initial_degree_evaluations','graph_bytes'))):errors.append(r['id']+': accept_id unnecessary structure')
                if r['policy']=='accept_static_degree':
                    if len(d['initial_degrees'])!=len(items):errors.append(r['id']+': degree length')
                    expected_order=sorted(range(len(items)),key=lambda t:(d['initial_degrees'][t],items[t][0]))
                    if order!=[items[t][0] for t in expected_order]:errors.append(r['id']+': static frozen order')
            elif r['policy']=='native':
                first={}
                for tid,s in items:
                    for k in s:first.setdefault(k,tid)
                expected_cert=[tid for tid,s in items if all(first[k]==tid for k in s)]
                if cert!=expected_cert:errors.append(r['id']+': native minimum writers')
            else:
                aborted=[tid for rr in d['abort_rounds'] for tid in rr]
                if sorted(aborted+cert)!=[tid for tid,_ in items]:errors.append(r['id']+': EAS complete partition')
                # Compare against old saved full arrays, never old timings.
                meta=trace_meta[trace.name];member=meta.get('member')
                key=(r['trace_sha256'],r['policy_k'],r['implementation'])
                if r['policy_k']==2 and member and key not in seen:
                    stem=Path(member).stem
                    old_member=f"raw/{stem}-{'warmup' if r['seed']==7 else 'measure'}-{r['implementation']}.json"
                    if old_member in names:
                        before=json.load(archive.extractfile(old_member))['decisions']
                        if before!=d:errors.append(r['id']+': existing EAS decisions changed')
                        legacy_count+=1;seen[key]=True
            if raw['verification']!='passed':errors.append(r['id']+': engine state verification')
    checks=run.check_decisions(output,records)
    if any(c['status']!='passed' for c in checks):errors.append('incomplete or failed policy comparisons')
    report=dict(status='passed' if not errors and all(r['status']=='ok' for r in records) else 'incomplete_or_failed',
                records=len(records),expected_records=len(expected),unique_traces=len(trace_cache),
                saved_legacy_decision_comparisons=legacy_count,errors=errors,
                failures=dict(collections.Counter(r['status'] for r in records if r['status']!='ok')))
    run.save_json(output/'audit.json',report)
    if errors:raise ValueError(str(errors[:10]))
    return report


def observations(output,records):
    rows=[]
    for r in records:
        if r['phase']!='measure':continue
        row={k:r[k] for k in KEYS};row.update(seed=r['seed'],repetition=r['repetition'],status=r['status'],trace_sha256=r['trace_sha256'],id=r['id'])
        if r['status']=='ok':
            raw=json.loads(run.local_raw(output,r).read_text())
            row.update({k:raw.get(k) for k in METRICS});row['runner_peak_rss_kib']=r.get('runner_peak_rss_kib')
            row.update({'selector_'+k:v for k,v in raw['selector'].items()})
            row['selector_degree_requeries']=max(0,raw['selector']['degree_queries']-raw['selector']['initial_core_size']) if r['mode'] in ('lazy','adaptive') and r['arity']>1 else 0
        rows.append(row)
    return rows


def summarize(rows):
    groups=collections.defaultdict(list)
    for r in rows:groups[(r['condition'],r['variant'],r['seed'])].append(r)
    seed_rows=[]
    for _,rs in groups.items():
        first=rs[0];metrics=METRICS+sorted(k for k in first if k.startswith('selector_') and k not in METRICS)
        for m in metrics:
            values=[r.get(m) for r in rs if r['status']=='ok']
            seed_rows.append(dict({k:first[k] for k in KEYS},seed=first['seed'],metric=m,expected_repeats=3,**stats(values)))
    groups=collections.defaultdict(list)
    for r in seed_rows:groups[(r['condition'],r['variant'],r['metric'])].append(r)
    aggregate=[]
    for _,rs in groups.items():
        aggregate.append(dict({k:rs[0][k] for k in KEYS},metric=rs[0]['metric'],expected_seeds=5,**stats([r['median'] for r in rs])))
    return seed_rows,aggregate


def paired(rows):
    lookup={(r['condition'],r['seed'],r['repetition'],r['variant']):r for r in rows}
    result=[]
    for r in rows:
        for base in ('native','accept_id','accept_static_degree','eas_k1_graph'):
            if base==r['variant']:continue
            if base=='eas_k1_graph' and (r['policy']!='eas' or r['policy_k']!=1):continue
            b=lookup.get((r['condition'],r['seed'],r['repetition'],base))
            if b is None:continue
            rec=dict({k:r[k] for k in KEYS},seed=r['seed'],repetition=r['repetition'],baseline=base,status='unavailable')
            if r['status']=='ok' and b['status']=='ok' and r['trace_sha256']==b['trace_sha256']:
                dr=r['commit_count']-b['commit_count'];dt=r['batch_ms']-b['batch_ms']
                rec.update(status='ok',commit_delta=dr,batch_delta_ms=dt,selector_delta_ms=r['selector_ms']-b['selector_ms'],
                           batch_speedup=b['batch_ms']/r['batch_ms'],selector_speedup=b['selector_ms']/r['selector_ms'] if r['selector_ms'] else None,
                           rate_ratio=r['effective_commits_per_second']/b['effective_commits_per_second'] if b['commit_count'] else None,
                           baseline_commits=b['commit_count'],commits=r['commit_count'],baseline_batch_ms=b['batch_ms'],batch_ms=r['batch_ms'],
                           quality_cost='baseline_dominates' if dr<=0 and dt>0 else 'extra_commits_extra_time' if dr>0 and dt>0 else 'variant_dominates' if dr>=0 and dt<0 else 'tradeoff_or_tie')
            result.append(rec)
    metric_names=['commit_delta','batch_delta_ms','selector_delta_ms','batch_speedup','selector_speedup','rate_ratio']
    groups=collections.defaultdict(list)
    for r in result:groups[(r['condition'],r['variant'],r['baseline'],r['seed'])].append(r)
    per_seed=[]
    for _,rs in groups.items():
        for m in metric_names:
            per_seed.append(dict({k:rs[0][k] for k in KEYS},baseline=rs[0]['baseline'],seed=rs[0]['seed'],metric=m,**stats([r.get(m) for r in rs if r['status']=='ok'])))
    groups=collections.defaultdict(list)
    for r in per_seed:groups[(r['condition'],r['variant'],r['baseline'],r['metric'])].append(r)
    aggregate=[]
    for _,rs in groups.items():
        aggregate.append(dict({k:rs[0][k] for k in KEYS},baseline=rs[0]['baseline'],metric=rs[0]['metric'],**stats([r['median'] for r in rs])))
    return result,per_seed,aggregate


def crossover(ce,cs,te,ts,n):
    # Times in milliseconds; root output in microseconds of cost per attempted txn.
    gain=ce-cs;rhs=cs*te-ce*ts
    if gain==0:return dict(wins_for='all_c' if rhs<0 else 'no_c' if rhs>0 else 'tie_all_c',crossover_us=None)
    root=1000*rhs/(n*gain)
    if root<0:return dict(wins_for='all_c' if gain>0 else 'no_c',crossover_us=None)
    return dict(wins_for='c_above' if gain>0 else 'c_below',crossover_us=root)


def sensitivity(pairs,grid):
    roots=[];points=[]
    for r in pairs:
        if r['status']!='ok' or r['workers']!=1 or r['variant'] not in ('eas_k1_adaptive','eas_k2_adaptive') or r['baseline'] not in ('accept_id','accept_static_degree'):continue
        ce,cs,te,ts,n=r['commits'],r['baseline_commits'],r['batch_ms'],r['baseline_batch_ms'],r['n']
        record={k:r[k] for k in KEYS+['baseline','seed','repetition','commit_delta','batch_delta_ms']}
        roots.append(dict(record,**crossover(ce,cs,te,ts,n)))
        for c in grid:
            erate=1000*ce/(te+n*c/1000);srate=1000*cs/(ts+n*c/1000)
            points.append(dict(record,extra_cost_us=c,eas_rate=erate,baseline_rate=srate,rate_ratio=erate/srate if srate else None))
    return roots,points


def tables(out,metrics,pairs):
    def value(c,v,m):
        row=next(r for r in metrics if r['condition']==c and r['variant']==v and r['metric']==m)
        return row['median']
    lines=['# 同一seed内3反復の中央値 → 5seedの中央値','',
           '時間は ms。有効処理率は確定件数/秒。native selector=0 は既存の依存判定を batch に含める扱い。', '',
           '|系列|arity|n|分布|worker|方式|commit|selector ms|batch ms|有効処理率|RSS KiB|',
           '|---|---:|---:|---|---:|---|---:|---:|---:|---:|---:|']
    seen=set()
    for r in metrics:
        c,v=r['condition'],r['variant']
        if (c,v) in seen:continue
        seen.add((c,v))
        vals=[value(c,v,m) for m in ('commit_count','selector_ms','batch_ms','effective_commits_per_second','runner_peak_rss_kib')]
        lines.append(f"|{r['suite']}|{r['arity']}|{r['n']}|{r['distribution']}|{r['workers']}|{v}|"+'|'.join(f'{x:.5g}' if x is not None else '未定義' for x in vals)+'|')
    lines+=['','## EAS k=1 と static の paired 差','',
            '|arity|n|分布|worker|件数差 median [min,max]|追加batch ms median [min,max]|有効処理率比 median [min,max]|',
            '|---:|---:|---|---:|---|---|---|']
    seen=set()
    for r in pairs:
        if r['variant']!='eas_k1_adaptive' or r['baseline']!='accept_static_degree' or r['condition'] in seen:continue
        seen.add(r['condition']);columns=[]
        for m in ('commit_delta','batch_delta_ms','rate_ratio'):
            q=next(p for p in pairs if p['condition']==r['condition'] and p['variant']==r['variant'] and p['baseline']==r['baseline'] and p['metric']==m)
            columns.append(f"{q['median']:.5g} [{q['minimum']:.5g},{q['maximum']:.5g}]" if q['median'] is not None else '未定義')
        lines.append(f"|{r['arity']}|{r['n']}|{r['distribution']}|{r['workers']}|"+'|'.join(columns)+'|')
    (out/'tables_ja.md').write_text('\n'.join(lines)+'\n')


def plots(out,metrics,pair_metrics,points):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    lookup={(r['condition'],r['variant'],r['metric']):r for r in metrics}
    colors=['#697586','#1e9187','#2262b5','#cd5937','#b39440']
    fig,axes=plt.subplots(2,3,figsize=(14,8),constrained_layout=True)
    for row,dist in enumerate(('uniform','zipf')):
        for col,metric in enumerate(('commit_count','batch_ms','effective_commits_per_second')):
            ax=axes[row,col]
            for v,color in zip(LABELS,colors):
                ns=[128,512,2048,8192,32768];rs=[lookup[(f'l2-n{n}-{dist}-w1',v,metric)] for n in ns]
                ax.plot(ns,[r['median'] for r in rs],label=v,color=color,marker='o',ms=3)
                ax.fill_between(ns,[r['minimum'] for r in rs],[r['maximum'] for r in rs],alpha=.10,color=color)
            ax.set_xscale('log',base=2);ax.set_yscale('log');ax.set_title(f'{dist}: {metric}');ax.set_xlabel('attempted transactions n');ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=8)
    for ext in ('svg','png'):fig.savefig(out/f'main.{ext}',dpi=160)
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4),constrained_layout=True)
    for ax,base in zip(axes,('accept_id','accept_static_degree')):
        for n,color in ((8192,'#1e9187'),(32768,'#cd5937')):
            chosen=[r for r in points if r['condition']==f'l2-n{n}-zipf-w1' and r['variant']=='eas_k1_adaptive' and r['baseline']==base]
            grid=sorted({r['extra_cost_us'] for r in chosen});med=[];lo=[];hi=[]
            for c in grid:
                seed=[st.median(r['rate_ratio'] for r in chosen if r['seed']==s and r['extra_cost_us']==c) for s in (11,29,47,71,101)]
                med.append(st.median(seed));lo.append(min(seed));hi.append(max(seed))
            ax.plot(grid,med,label=f'n={n}',marker='o',color=color);ax.fill_between(grid,lo,hi,alpha=.15,color=color)
        ax.axhline(1,color='black',lw=1);ax.set_xscale('symlog',linthresh=.1);ax.set_title(f'EAS k=1 / {base} effective rate');ax.set_xlabel('hypothetical extra body cost per attempt (us)');ax.legend();ax.grid(alpha=.2)
    for ext in ('svg','png'):fig.savefig(out/f'sensitivity.{ext}',dpi=160)
    plt.close(fig)


def main():
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--output',type=Path);p.add_argument('--no-plots',action='store_true');args=p.parse_args()
    source=args.input.resolve();out=args.output or source/'summary';out.mkdir(parents=True,exist_ok=True)
    records=[json.loads(s) for s in (source/'runs.jsonl').read_text().splitlines()]
    checked=audit(source,records);rows=observations(source,records);seeds,metrics=summarize(rows);pairs,pair_seeds,pair_metrics=paired(rows)
    roots,points=sensitivity(pairs,json.loads((source/'plan.json').read_text())['sensitivity']['extra_body_cost_us'])
    for name,data in [('runs',rows),('seed_metrics',seeds),('metrics',metrics),('paired_observations',pairs),('paired_seed',pair_seeds),('paired',pair_metrics),('sensitivity_roots',roots),('sensitivity_grid',points)]:csv_write(out/(name+'.csv'),data)
    tables(out,metrics,pair_metrics)
    if not args.no_plots and any(r['n']==32768 for r in rows):plots(out,metrics,pair_metrics,points)
    facts=dict(audit=checked,measurements=len(rows),successful=sum(r['status']=='ok' for r in rows),
               eas_k1_vs_static=[r for r in pair_metrics if r['variant']=='eas_k1_adaptive' and r['baseline']=='accept_static_degree'],
               zero_commit_runs=sum(r.get('commit_count')==0 for r in rows),
               adaptive_switches=sum(r.get('selector_switches',0) for r in rows if r['implementation']=='adaptive'))
    run.save_json(out/'facts.json',facts);print(json.dumps(checked))
    return 0 if checked['status']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
