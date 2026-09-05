#!/usr/bin/env python3
"""Summarize the prespecified finite optimum/search raw inputs, without extrapolation."""
import argparse
import collections
import json
from pathlib import Path
import statistics
import run
import analyze

p=argparse.ArgumentParser();p.add_argument('directory',type=Path);args=p.parse_args();root=args.directory
policies=['native','accept_id','accept_static_degree','eas_k1','eas_k2']
groups=collections.defaultdict(list)
for line in (root/'quality.jsonl').read_text().splitlines():
    row=json.loads(line)
    assert len(row['input'])<=18 and all(c<=row['maximum'] for c in row['commits'])
    groups[row['suite']].append(row)
rows=[]
for suite,records in groups.items():
    for i,policy in enumerate(policies):
        gaps=[r['maximum']-r['commits'][i] for r in records]
        rows.append(dict(suite=suite,policy=policy,inputs=len(gaps),n_min=min(len(r['input']) for r in records),
                         n_max=max(len(r['input']) for r in records),optimum_hits=gaps.count(0),
                         mean_gap=statistics.mean(gaps),max_gap=max(gaps),gap_histogram=json.dumps(dict(sorted(collections.Counter(gaps).items())))))
analyze.csv_write(root/'optimal_gaps.csv',rows)
witness=json.loads((root/'witnesses.json').read_text());counts=collections.Counter()
for line in (root/'witness_search.jsonl').read_text().splitlines():
    r=json.loads(line);counts['eas_wins' if r['eas_k1']>r['static'] else 'static_wins' if r['eas_k1']<r['static'] else 'ties']+=1
assert sum(counts.values())==20000
assert all(witness[k]==v for k,v in counts.items())
result=dict(status='passed',quality_inputs=sum(map(len,groups.values())),optimum_scope='prespecified n<=18 only; exhaustive transaction subsets',
            optimum_subset_count=sum(2**len(r['input']) for rs in groups.values() for r in rs),
            quality_rows=rows,witness_search=dict(counts),witness_cases=sum(counts.values()),
            raw_hashes={f:run.sha256(root/f) for f in ('quality.jsonl','witness_search.jsonl','witnesses.json')})
run.save_json(root/'summary.json',result)
print(json.dumps(result))
