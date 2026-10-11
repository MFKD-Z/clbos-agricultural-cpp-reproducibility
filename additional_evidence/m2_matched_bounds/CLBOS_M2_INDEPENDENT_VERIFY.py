#!/usr/bin/env python3
"""Independently verify archived M2 paired experiment from row-level CSV.

Inputs in the same directory: formal_runs.csv, formal_environment.json,
m2_formal_analysis.json, m2_formal_field_summary.csv,
CLBOS_M2_PAIRED_TIMING.py. No network or Fields2Cover calls.
The bootstrap explicitly mirrors the original pre-registered M2 analysis.
"""
from __future__ import annotations
import collections
import csv
import hashlib
import json
import math
import random
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METHODS = ('LB0_CERTIFIED','LB1_MST_CERTIFIED')

def read_csv(name):
    with (ROOT/name).open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def read_json(name):
    return json.loads((ROOT/name).read_text(encoding='utf-8'))

def digest(name):
    return hashlib.sha256((ROOT/name).read_bytes()).hexdigest()

def require(cond, message):
    if not cond:
        raise AssertionError(message)

def percentile(xs,q):
    xs=sorted(xs)
    k=(len(xs)-1)*q
    low=math.floor(k); high=math.ceil(k)
    return xs[low]*(1-(k-low))+xs[high]*(k-low)

def main():
    records=read_csv('formal_runs.csv')
    expected=read_json('m2_formal_analysis.json')
    summary=read_csv('m2_formal_field_summary.csv')
    manifest=read_json('formal_environment.json')
    require(len(records)==180,'Must have 180 formal records')
    require(manifest['mode']=='FORMAL_18x5','Wrong provenance mode')
    require(manifest['repeats']==5 and manifest['angle_count']==180,'Wrong protocol')
    require(manifest['experiment_script_sha256']==digest('CLBOS_M2_PAIRED_TIMING.py'),'Script SHA-256 mismatch')
    require(len(set(manifest['fields']))==18,'Invalid selection count')
    keys=set()
    grouped=collections.defaultdict(lambda:collections.defaultdict(list))
    for r in records:
        key=(r['field_id'],int(r['repeat']),r['method'])
        require(key not in keys,'Duplicate experimental key')
        keys.add(key)
        require(r['field_id'] in manifest['fields'],'Unselected field present')
        require(r['method'] in METHODS and 1<=int(r['repeat'])<=5,'Bad method/repeat')
        require(r['status']=='SUCCESS' and r['exact_to_authority']=='true','Unsuccessful/inexact record')
        require(not r['error'] and int(r['unresolved_count'])==0,'Unresolved execution')
        require(abs(float(r['objective_m'])-float(r['authority_j_m']))<=1e-6,'Oracle mismatch')
        for name in ('wall_seconds','bound_wall_seconds','selected_full_wall_seconds'):
            require(math.isfinite(float(r[name])) and float(r[name])>=0,'Invalid time')
        require(abs(float(r['wall_seconds'])-float(r['bound_wall_seconds'])-float(r['selected_full_wall_seconds']))<0.03,'Timing component mismatch')
        grouped[r['field_id']][r['method']].append(r)
    require(set(grouped)==set(manifest['fields']),'Selected field coverage mismatch')
    calc=[]
    for fid in sorted(grouped):
        d={'field_id':fid}
        for method in METHODS:
            rows=grouped[fid][method]
            require(len(rows)==5 and sorted(int(x['repeat']) for x in rows)==[1,2,3,4,5],'Repetition completeness failure')
            calls={int(x['full_calls']) for x in rows}
            require(len(calls)==1,'Unstable complete evaluation count')
            d['median_'+method+'_s']=statistics.median(float(x['wall_seconds']) for x in rows)
            d['median_'+method+'_bound_s']=statistics.median(float(x['bound_wall_seconds']) for x in rows)
            d['median_'+method+'_full_s']=statistics.median(float(x['selected_full_wall_seconds']) for x in rows)
            d['calls_'+method]=next(iter(calls))
        d['ratio']=d['median_LB1_MST_CERTIFIED_s']/d['median_LB0_CERTIFIED_s']
        calc.append(d)
    a=sum(x['median_LB0_CERTIFIED_s'] for x in calc)
    b=sum(x['median_LB1_MST_CERTIFIED_s'] for x in calc)
    rng=random.Random(20261011)
    boot=[]
    for _ in range(10000):
        chosen=[calc[rng.randrange(18)] for _ in range(18)]
        boot.append(sum(x['median_LB1_MST_CERTIFIED_s'] for x in chosen)/sum(x['median_LB0_CERTIFIED_s'] for x in chosen))
    ci=[percentile(boot,.025),percentile(boot,.975)]
    independent={
        'run_type':'FORMAL','n_fields':18,'repeats_per_method_field':5,
        'aggregate_sum_field_medians_lb0_s':a,
        'aggregate_sum_field_medians_lb1_s':b,
        'lb1_over_lb0_ratio':b/a,
        'lb1_relative_change_percent':100*(b/a-1),
        'field_cluster_bootstrap_95pct_ci_lb1_over_lb0':ci,
        'median_fieldwise_lb1_over_lb0':statistics.median(x['ratio'] for x in calc),
        'lb1_faster_field_count':sum(x['ratio']<1 for x in calc),
        'total_full_calls_lb0':sum(x['calls_LB0_CERTIFIED'] for x in calc),
        'total_full_calls_lb1':sum(x['calls_LB1_MST_CERTIFIED'] for x in calc),
    }
    for key,value in independent.items():
        ref=expected[key]
        if isinstance(value,list):
            require(len(ref)==len(value) and all(abs(x-y)<1e-10 for x,y in zip(value,ref)),f'Published summary mismatch: {key}')
        elif isinstance(value,float):
            require(abs(value-ref)<1e-10,f'Published summary mismatch: {key}')
        else:
            require(value==ref,f'Published summary mismatch: {key}')
    require(len(summary)==18,'Field-level summary rowcount')
    for row in summary:
        d=next(x for x in calc if x['field_id']==row['field_id'])
        for m in METHODS:
            require(abs(float(row['median_'+m+'_s'])-d['median_'+m+'_s'])<1e-10,'Field median mismatch')
            require(abs(float(row['median_'+m+'_bound_s'])-d['median_'+m+'_bound_s'])<1e-10,'Field bound median mismatch')
            require(int(row['calls_'+m])==d['calls_'+m],'Field call mismatch')
        require(abs(float(row['lb1_over_lb0'])-d['ratio'])<1e-10,'Field ratio mismatch')
        require(abs(float(row['paired_seconds_diff_lb1_minus_lb0'])-(d['median_LB1_MST_CERTIFIED_s']-d['median_LB0_CERTIFIED_s']))<1e-10,'Field difference mismatch')
    independent.update({
        'row_level_consistency':'PASS',
        'matching_summary_json':'PASS',
        'matching_field_csv':'PASS',
        'script_sha256_match':'PASS',
        'raw_csv_sha256':digest('formal_runs.csv'),
        'm2_speedup_claim':'NOT_ESTABLISHED_CI_SPANS_ONE',
        'call_reduction_percent':100*(1-independent['total_full_calls_lb1']/independent['total_full_calls_lb0']),
        'sum_median_lb0_bound_seconds':sum(x['median_LB0_CERTIFIED_bound_s'] for x in calc),
        'sum_median_lb1_bound_seconds':sum(x['median_LB1_MST_CERTIFIED_bound_s'] for x in calc),
        'sum_median_lb0_selected_full_seconds':sum(x['median_LB0_CERTIFIED_full_s'] for x in calc),
        'sum_median_lb1_selected_full_seconds':sum(x['median_LB1_MST_CERTIFIED_full_s'] for x in calc),
    })
    target=ROOT/'CLBOS_M2_INDEPENDENT_RECOMPUTED.json'
    target.write_text(json.dumps(independent,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('PASS: 180/180, 18/18 fields, original analysis and field summary exactly reproduced')
    print(json.dumps(independent,indent=2))

if __name__=='__main__':
    main()
