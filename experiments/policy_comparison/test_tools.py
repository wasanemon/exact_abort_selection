#!/usr/bin/env python3
import json
from pathlib import Path
import tempfile
import unittest
import run
import analyze

class Bookkeeping(unittest.TestCase):
    def test_plan_coverage_and_pairing(self):
        plan=json.loads((run.HERE/'plan.json').read_text())
        cs=run.configurations(plan);jobs=run.jobs_for(plan,cs)
        self.assertEqual(len(cs),19)
        self.assertEqual(len(jobs),1600)
        self.assertEqual(sum(j['phase']=='measure' for j in jobs),1500)
        self.assertEqual(len({j['id'] for j in jobs}),1600)
        self.assertEqual(run.jobs_for(plan,cs),jobs)
        zipf=[c for c in cs if c['n']==8192 and c['arity']==2 and c['distribution']=='zipf']
        self.assertEqual({c['workers'] for c in zipf},{1,2,4})
        self.assertEqual(len({c['batch_id'] for c in zipf}),1)
        self.assertEqual(zipf[0]['batch_id'],1208417051)
        self.assertEqual(len(zipf[0]['variants']),8)

    def test_group_by_policy_and_k_then_detect_repeat_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'raw').mkdir();records=[]
            for index,(v,mask) in enumerate([('native',[1,0]),('accept_id',[1,0]),('accept_static_degree',[0,1]),
                                           ('eas_k1_graph',[1,0]),('eas_k1_adaptive',[1,0]),('eas_k2_adaptive',[0,0])]):
                file=root/'raw'/f'{index}.json'
                run.save_json(file,{'decisions':{'commit':mask,'abort_rounds':[[2]] if sum(mask) else [[2,1]],'certificate':[i+1 for i,c in enumerate(mask) if c]}})
                records.append(dict(run.variant_fields(v),id=str(index),phase='measure',trace_sha256='same',workers=1,status='ok',raw_path=str(file)))
            checks=run.check_decisions(root,records)
            self.assertEqual(len(checks),5)
            self.assertTrue(all(c['status']=='passed' for c in checks))
            run.save_json(root/'raw/4.json',{'decisions':{'commit':[1,0],'abort_rounds':[[1]],'certificate':[1]}})
            self.assertEqual(sum(c['status']=='failed' for c in run.check_decisions(root,records)),1)

    def test_failures_remain_missing(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            r=dict(run.variant_fields('eas_k1_adaptive'),id='bad',phase='measure',trace_sha256='t',workers=1,status='timeout')
            self.assertEqual(run.check_decisions(root,[r])[0]['status'],'incomplete')

    def test_paired_seed_summary_not_ratio_of_marginal_medians(self):
        rows=[]
        for seed,bt,et in ((11,1,4),(29,10,5),(47,100,10)):
            for rep in (1,2,3):
                for variant,duration in (('native',bt),('eas_k1_adaptive',et)):
                    rows.append(dict(run.variant_fields(variant),condition='fixture',suite='main',arity=2,n=10,
                                     distribution='uniform',workers=1,seed=seed,repetition=rep,status='ok',
                                     trace_sha256='same',commit_count=3,batch_ms=duration,selector_ms=duration,
                                     effective_commits_per_second=3000/duration))
        obs,seeds,summary=analyze.paired(rows)
        result=next(r for r in summary if r['variant']=='eas_k1_adaptive' and r['metric']=='batch_speedup')
        self.assertEqual(result['count'],3)
        self.assertEqual(result['median'],2)
        rows[-1]['status']='timeout'
        self.assertEqual(sum(r['status']=='unavailable' for r in analyze.paired(rows)[0]),1)

    def test_sensitivity_algebra_and_undefined_statistics(self):
        # 2/(4+2c) = 1/(1+2c) at c=1ms, with times in ms.
        self.assertEqual(analyze.crossover(2,1,4,1,2),dict(wins_for='c_above',crossover_us=1000))
        self.assertEqual(analyze.crossover(1,1,4,1,2)['wins_for'],'no_c')
        self.assertEqual(analyze.crossover(1,2,4,1,2)['wins_for'],'no_c')
        self.assertIsNone(analyze.stats([None])['median'])

if __name__=='__main__':unittest.main(verbosity=2)
