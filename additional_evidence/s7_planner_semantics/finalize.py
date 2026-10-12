#!/usr/bin/env python3
"""Freeze the diagnosis after a genuine A3 smoke failure; do not run more cases."""
import copy
import csv
import datetime
import json
import pathlib
import statistics
import subprocess

from s7_audit import OUT, RELEASE, ORIGINAL, OBSERVER, SOURCE, ROOT, audit, make_plan, sha, dist

now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
plan = make_plan()
raw = [json.loads(line) for line in (OUT / 's7_observations.jsonl').read_text(encoding='utf-8').splitlines() if line]
actual = {(r['field_id'], r['angle_deg']): r for r in raw}
assert len(actual) == len(raw) == 6
assert all(r['status'] == 'SUCCESS' and r.get('baseline', {}).get('match') for r in raw)
assert all(r['observation']['status'] == 'VALID_FINITE' for r in raw)

def rc(cmd):
    p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.stdout.strip()

f2c_head = rc(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'])
f2c_dirty = rc(['git', '-C', str(SOURCE), 'status', '--porcelain'])
release_dirty = rc(['git', '-C', str(RELEASE), 'status', '--porcelain'])
lib = pathlib.Path('<ORIGINAL_CACHE>/Fields2Cover-build/fields2cover/libFields2Cover.so')
adapter = ROOT / 'runner/src/agri_f2c_runner.cpp'
source_hashes = {str(p): sha(p) for p in [adapter, ORIGINAL, lib, OBSERVER,
                                         OUT/'s7_observer.cpp', OUT/'s7_audit.py', OUT/'finalize.py']}

def negative_selftest():
    base = next(r['observation'] for r in raw if len(r['observation']['generated']) > 1)
    x = copy.deepcopy(base)
    x['generated'].pop()
    a1 = audit(x)['A1_status'] == 'FAIL'
    x = copy.deepcopy(base)
    sw = [i for i,s in enumerate(x['states']) if s['type'] == 1]
    # One millimetre spatial gap in a copy of the observation only.
    turn = next(i for i,s in enumerate(x['states']) if s['type'] != 1 and i > 0)
    x['states'][turn]['point'][0] += .001
    a3 = audit(x)['A3_status'] == 'FAIL' and audit(x)['max_gap_m'] > .0009
    x = copy.deepcopy(base)
    x['states'][sw[0]]['len'] += .001
    a4 = audit(x)['A4_status'] == 'FAIL'
    return {'dropped_generated_swath_detected': a1, 'inserted_1mm_gap_detected': a3,
            'inflated_state_length_detected': a4,
            'status':'PASS' if a1 and a3 and a4 else 'FAIL',
            'disclaimer':'Artificial mutations of copied observations, never planner measurements.'}

selftest = negative_selftest()
rows = []
failures = []
case_audits = []
for p in plan:
    key = (p['field_id'], p['angle_deg'])
    record = actual.get(key)
    if record:
        a = audit(record['observation'])
        case_audits.append({'field_id':key[0], 'angle_deg':key[1], 'audit':a})
        states = record['observation']['states']
        gaps = [dist(states[i]['end'],states[i+1]['point']) for i in range(len(states)-1)]
        row = {**p, 'run_status':record['status'], 'elapsed_s':record['elapsed_s'],
               'baseline_match':record['baseline']['match'],
               'A1_status':a['A1_status'], 'A2_status':a['A2_status'],
               'A3_status':a['A3_status'], 'A4_status':a['A4_status'],
               'generated_count':a['generated_count'], 'route_count':a['route_count'],
               'state_count':a['state_count'], 'max_swath_error_m':a['max_swath_error_m'],
               'missing_connections':a['missing_connections'],
               'zero_length_connections':a['zero_length_connections'],
               'max_gap_m':a['max_gap_m'], 'gap_count_1e_6':a['gap_count'],
               'gap_count_1e_5':sum(g > 1e-5 for g in gaps),
               'gap_count_1e_4':sum(g > 1e-4 for g in gaps),
               'length_residual_m':a['length_residual_m'],
               'work_residual_m':a['work_residual_m'],
               'connector_length_m':a['connector_length_m'],
               'nonwork_length_m':a['nonwork_length_m'],
               'extra_nonwork_length_m':a['extra_nonwork_length_m'],
               'connector_overlap_count':a['connector_overlap_count'],
               'observation_file':str(OUT/'s7_observations.jsonl'),
               'finished_utc':record['finished_utc']}
        if any(a['A'+str(i)+'_status'] != 'PASS' for i in range(1,5)):
            first = next((d for d in a['details'] if d['kind']=='spatial_gap'), a['details'][0])
            failures.append({**{k:row[k] for k in ['field_id','angle_deg','source_wkt_sha256','source_ref',
                                                   'A1_status','A2_status','A3_status','A4_status']},
                             'swath_id':None, 'route_group_id':None,
                             'state_index':first.get('state_index'),
                             'expected':first.get('expected'), 'observed':first.get('observed'),
                             'delta':first.get('delta_m'), 'tolerance':1e-6,
                             'notes': 'Real PathState spatial seam; full trace in observation_file.',
                             'observation_file':str(OUT/'s7_observations.jsonl'),
                             'finished_utc':record['finished_utc']})
    else:
        row = {**p, 'run_status':'UNRESOLVED_NOT_RUN_AFTER_A3_FAILURE',
               'A1_status':'NOT_APPLICABLE', 'A2_status':'NOT_APPLICABLE',
               'A3_status':'NOT_APPLICABLE', 'A4_status':'NOT_APPLICABLE',
               'observation_file':'', 'finished_utc':''}
        failures.append({'field_id':key[0], 'angle_deg':key[1],
                         'source_wkt_sha256':p['source_wkt_sha256'], 'source_ref':p['source_ref'],
                         'status':row['run_status'], 'swath_id':None, 'route_group_id':None,
                         'state_index':None, 'expected':None, 'observed':None,
                         'delta':None, 'tolerance':1e-6,
                         'notes':'Predeclared case not executed after genuine A3 failure in smoke set.',
                         'observation_file':None, 'time':now})
    rows.append(row)

with (OUT/'s7_case_results.csv').open('w', newline='', encoding='utf-8') as f:
    keys = list(dict.fromkeys(k for row in rows for k in row))
    writer = csv.DictWriter(f, fieldnames=keys)
    writer.writeheader(); writer.writerows(rows)
with (OUT/'s7_failures.jsonl').open('w', encoding='utf-8') as f:
    for x in failures:
        f.write(json.dumps(x, ensure_ascii=False, separators=(',',':'))+'\n')
with (OUT/'s7_case_audits.jsonl').open('w', encoding='utf-8') as f:
    for x in case_audits:
        f.write(json.dumps(x, ensure_ascii=False, separators=(',',':'))+'\n')
with (OUT/'negative_selftest.json').open('w', encoding='utf-8') as f:
    json.dump(selftest, f, indent=2)

valid = [r for r in rows if r['run_status']=='SUCCESS']
failed = [r for r in valid if r['A3_status']=='FAIL']
max_gap = max(r['max_gap_m'] for r in valid)
max_resid = max(abs(r['length_residual_m']) for r in valid)
report = f'''# S7 pinned planner runtime semantics audit

Run time (Asia/Shanghai): {now}. **S7_GATE=FAIL.** A3 fails in 3 of 6 preselected smoke cases at the declared 1e-6 m spatial threshold. The run stopped before the remaining {len(plan)-6} cases, as requested for a genuine failure. This is an empirical finding for executed inputs, not a formal guarantee for all inputs.

## Text and execution identity

`PAPER_TEXT_NOT_AVAILABLE`: no latest JESTECH Section 2.2, Proposition 1, Table 1 or S7 file was found locally. The accessible `submission/CLBOS_BE_FINAL_SUBMISSION_MANUSCRIPT.docx` contains related A1–A4 wording and Proposition 1, but is a Biosystems Engineering file and is not represented here as JESTECH text. The audit uses the four operational definitions in the supplied task document.

Fields2Cover HEAD `{f2c_head}`; source worktree clean={not bool(f2c_dirty)}. Production adapter SHA-256 `{sha(adapter)}`, identical to the release adapter. Original binary SHA-256 `{sha(ORIGINAL)}`; linked `libFields2Cover.so` SHA-256 `{sha(lib)}`. New observer binary SHA-256 `{sha(OBSERVER)}`. Original binary's CMake cache binds `F2C_SOURCE_DIR={SOURCE}` and `CMAKE_HOME_DIRECTORY=<ORIGINAL_WORKSPACE>/runner`; `ldd` resolves the pinned library in the old build directory. The observer only adds JSON serialization to a copy of the original runner and links that same library. Six baseline replays matched swath count, swath length, and complete path length.

The adapter fixes a 6 m total headland through 3 m + TrapezoidalDecomp + 3 m, uses the same narrow splitByLine fallback, BruteForce swaths, RoutePlannerBase::genRoute, PathPlanning::planPath with DubinsCurves, and PathLength::computeCost. Inputs are metric selected WKT files; source WKT SHA-256 is checked against the frozen selection table. Each metric WKT hash is in `s7_predeclared_cases.json`.

## Source semantics and runtime tests

Source line numbers below refer to `{SOURCE}` at the pinned HEAD.

- `route_planning/route_planner_base.cpp:21-34` constructs shortest/coverage graphs and transforms solver IDs; `:193-227` matches route node endpoints to swaths and appends swaths. This does not independently prove a one-to-one geometry multiset or complete path traversal.
- `path_planning/path_planning.cpp:12-25` concatenates connections and swath groups; `:28-43` appends swaths and same-group turns; `:46-89` builds cross-group endpoint connections. These calls do not check the resulting PathState seams.
- `types/Path.cpp:98-103` appends state vectors without continuity validation; `:205-222` sums absolute state lengths and appends each swath edge; `types/PathState.cpp:11-13` reconstructs a state endpoint from point, angle, signed direction and len; `objectives/pp_obj/pp_objective.cpp:11-13` returns `path.length()`.
- `types/Path.cpp:346-394,434-440` discretizes turns by spline positions, angles and fixed step length, then reduces states. This is a plausible source of the approximately 25 micrometre PathState endpoint mismatch. It is an inference from source and observed data, not a proven unique cause.

The four checks use 1e-6 m absolute spatial tolerance and 1e-6 m + 1e-10 relative length tolerance, declared before execution. A1 matches generated-to-route polylines as a multiset (including reversal), then matches every route swath edge to ordered final SWATH states. A2 assigns a unique nonwork state range to every adjacent swath pair and checks its endpoints or legal zero-length adjacency. A3 compares every `state.atEnd()` with the following `state.point`. A4 reconciles every absolute state length with PathLength, generated work length and disjoint connector ranges; extra nonwork is separately classified. The independent negative self-test mutated copied observations only: {selftest['status']}.

## Smoke results and diagnosis

All 6 planned smoke cases returned valid finite paths and matched the original runner. A1, A2 and A4 pass in all 6; A3 passes in 3 and fails in 3. A3 failures are:

| Field | Angle | Maximum gap (m) | Gaps > 1e-6 | Gaps > 1e-5 | Gaps > 1e-4 |
|---|---:|---:|---:|---:|---:|
''' + ''.join(f"| {r['field_id']} | {r['angle_deg']} | {r['max_gap_m']:.12g} | {r['gap_count_1e_6']} | {r['gap_count_1e_5']} | {r['gap_count_1e_4']} |\n" for r in failed) + f'''
The largest observed gap is {max_gap:.12g} m. All three failures persist at 1e-5 m and pass at 1e-4 m; this sensitivity does not change the primary verdict. Their length residuals are at most {max_resid:.3g} m, demonstrating that length agreement alone misses the discontinuities. The recorded first-gap coordinates, state IDs and types are in `s7_failures.jsonl`; all states and route geometry are in `s7_observations.jsonl`. The initial embedded audit fields in that raw JSONL coupled A2/A4 to A3; the corrected independent adjudication is `s7_case_audits.jsonl` and `s7_case_results.csv`.

The predeclared P0 list contains {len(plan)} unique field-angle cases: 90 exhaustive 1° oracle angles, 25 differing upstream SwathLength angles and 18 deterministic additional E3/M2 candidate angles. Six were executed and {len(plan)-6} were intentionally left unresolved after the real A3 finding. The 3 passing cases do not establish universal planner semantics. The release repository contains pre-existing dirty tracked files (`{release_dirty.replace(chr(10), '; ')}`) discovered during this audit; the audit did not edit them. The original source, runner, library and source WKT checks remain unchanged by this audit.
'''
(OUT/'S7_PINNED_PLANNER_AUDIT.md').write_text(report, encoding='utf-8')

files = ['s7_observer.cpp','s7_observer','s7_audit.py','finalize.py','s7_predeclared_cases.json',
         's7_observations.jsonl','s7_case_audits.jsonl','s7_case_results.csv',
         's7_failures.jsonl','negative_selftest.json','S7_PINNED_PLANNER_AUDIT.md','stderr.log']
manifest = {'created_asia_shanghai':now, 'gate':'FAIL', 'reason':'Three real A3 spatial seam failures at 1e-6 m',
            'paper_text_status':'PAPER_TEXT_NOT_AVAILABLE',
            'f2c_head':f2c_head, 'f2c_source_dirty':f2c_dirty,
            'release_repo_dirty_at_review':release_dirty,
            'adapter_sha256':sha(adapter), 'original_binary_sha256':sha(ORIGINAL),
            'linked_library_sha256':sha(lib), 'observer_binary_sha256':sha(OBSERVER),
            'predeclared_cases':len(plan), 'valid_finite_cases':len(valid),
            'not_run_after_failure':len(plan)-len(valid),
            'tolerances':{'spatial_absolute_m':1e-6,'length_absolute_m':1e-6,
                          'length_relative':1e-10,'spatial_sensitivity_m':[1e-5,1e-4]},
            'commands':['g++ -std=c++17 -O2 -I<F2C>/include -I/usr/include/gdal s7_observer.cpp -L<old_build>/fields2cover -lFields2Cover -lgdal -lgeos_c -Wl,-rpath,<old_build>/fields2cover -o s7_observer',
                        'python3 s7_audit.py --smoke --timeout 120',
                        'python3 finalize.py'],
            'planned_case_file':'s7_predeclared_cases.json',
            'source_hashes':source_hashes,
            'file_sha256':{name:sha(OUT/name) for name in files if (OUT/name).exists()},
            'negative_selftest':selftest}
(OUT/'s7_evidence_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'gate':'FAIL','planned':len(plan),'valid':len(valid),'A3_failed':len(failed),
                  'max_gap_m':max_gap,'selftest':selftest['status']}))
