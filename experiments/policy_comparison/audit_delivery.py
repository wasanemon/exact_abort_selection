#!/usr/bin/env python3
"""Verify every archived byte and worker-invariant policy outputs in the delivered data."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import tarfile
import run

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=run.HERE);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
root=args.root.resolve();archives=[];groups={};parallel=set();count=0
for relative in ('results/full','results/smoke','results/development-smoke','baseline_smoke','quality'):
    directory=root/relative;manifest=json.loads((directory/'archive_manifest.json').read_text());path=directory/'raw_data.tar.gz'
    assert run.sha256(path)==manifest['archive_sha256'],relative
    with tarfile.open(path,'r:gz') as tar:
        actual={}
        for m in tar:
            if not m.isfile():continue
            contents=tar.extractfile(m).read();actual[m.name]=hashlib.sha256(contents).hexdigest()
            if relative=='results/full' and m.name.startswith('raw/'):
                raw=json.loads(contents)
                assert raw['verification']=='passed'
        assert actual==manifest['files'],relative
    archives.append(dict(path=str(path.relative_to(root)),files=len(actual),sha256=manifest['archive_sha256']))
# Read the portable archived records directly, without trusting any saved absolute path.
full=root/'results/full';records=[json.loads(s) for s in (full/'runs.jsonl').read_text().splitlines()]
with tarfile.open(full/'raw_data.tar.gz','r:gz') as tar:
    record_by_raw={'raw/'+Path(r['raw_path']).name:r for r in records if r['phase']=='measure'}
    workers=collections.defaultdict(set)
    for member in tar:
        if member.name not in record_by_raw:continue
        r=record_by_raw[member.name];raw=json.load(tar.extractfile(member));key=(r['trace_sha256'],r['policy'],r['policy_k'])
        if key in groups:assert groups[key]==raw['decisions'],key
        else:groups[key]=raw['decisions']
        workers[key].add(r['workers']);count+=1
    parallel={key for key,ws in workers.items() if ws=={1,2,4}}
assert count==1500 and len(parallel)==25
stage=json.loads((root.parent.parent/'next_stage.json').read_text())
assert stage['issue_4_status']=='not_started' and not stage['completion']['unexecuted_issue_3_items']
for key,path in stage['data_paths'].items():assert (root.parent.parent/path).exists(),key
result=dict(status='passed',archives=archives,full_measurements=count,
            exact_policy_groups_across_workers=len(groups),worker_1_2_4_groups=len(parallel),
            machine_summary_paths_exist=True)
run.save_json(args.output,result);print(json.dumps(result))
