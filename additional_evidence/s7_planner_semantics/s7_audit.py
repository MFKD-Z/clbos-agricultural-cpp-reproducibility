#!/usr/bin/env python3
"""Read-only replay and semantic checks of the pinned CLBOS planner."""
import argparse
import csv
import hashlib
import json
import math
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path('<ORIGINAL_WORKSPACE>/ 's7_pinned_planner_semantics_audit'
RELEASE = ROOT / 'release/CLBOS_BiosystemsEngineering_Reproducibility'
ORIGINAL = pathlib.Path('<ORIGINAL_CACHE>/Fields2Cover-build/agri_f2c_runner')
OBSERVER = OUT / 's7_observer'
SOURCE = pathlib.Path('<ORIGINAL_CACHE>/Fields2Cover')
WKT_ROOT = pathlib.Path('<ORIGINAL_CACHE>/selected_wkts')
SOURCE_WKT_ROOT = ROOT / 'tmp/b1_a1_fields2benchmark_14524735'
SPACE_TOL = 1e-6
ABS_TOL = 1e-6
REL_TOL = 1e-10

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def csv_rows(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def make_plan():
    selected = {r['field_id']: r for r in csv_rows(RELEASE / 'data/heldout/selected_heldout_fields.csv')}
    full = csv_rows(RELEASE / 'data/derived/cross_stage/field_results.csv')
    e3 = {r['field_id'] for r in csv_rows(ROOT / 'E3_REPRESENTATIVE_RUNTIME/01_E3_SELECTION_FREEZE.csv')}
    plan = {}
    for row in full:
        fid = row['field_id']
        if row['status'] != 'COMPLETE' or fid not in selected:
            raise RuntimeError('missing authoritative result or selection: ' + fid)
        angles = [(int(row['oracle_best_angle_deg']), 'oracle_1deg')]
        if row['bf_sl_angle_deg'] != row['oracle_best_angle_deg']:
            angles.append((int(row['bf_sl_angle_deg']), 'upstream_mismatch'))
        if fid in e3:
            # Deterministic extra candidate, frozen before any runtime observation.
            extra = next(a for a in range(180) if a not in {v for v, _ in angles})
            angles.append((extra, 'e3_m2_representative'))
        for angle, source in angles:
            key = (fid, angle)
            if key in plan:
                raise RuntimeError('duplicate key')
            sel = selected[fid]
            wkt = WKT_ROOT / (sel['source_wkt_sha256'] + '.wkt')
            plan[key] = dict(field_id=fid, family=row['family'], angle_deg=angle,
                             sample_role=source, source_ref=sel['source_path'],
                             source_wkt_sha256=sel['source_wkt_sha256'], wkt_path=str(wkt),
                             source_wkt_path=str(SOURCE_WKT_ROOT / sel['source_path']),
                             authority_j_m=row['oracle_j_star_m'] if source == 'oracle_1deg' else '')
    rows = [plan[k] for k in sorted(plan)]
    for r in rows:
        p = pathlib.Path(r['wkt_path'])
        source = pathlib.Path(r['source_wkt_path'])
        r['wkt_available'] = p.is_file()
        r['metric_wkt_sha256'] = sha(p) if p.is_file() else None
        r['wkt_hash_verified'] = p.is_file() and source.is_file() and sha(source) == r['source_wkt_sha256']
    return rows

def close(a, b, abs_tol=ABS_TOL):
    return math.isfinite(a) and math.isfinite(b) and abs(a-b) <= abs_tol + REL_TOL*max(abs(a), abs(b))

def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def same_poly(a, b):
    ap, bp = a['points'], b['points']
    if len(ap) != len(bp):
        return False, math.inf, False
    fwd = max(dist(x, y) for x, y in zip(ap, bp))
    rev = max(dist(x, y) for x, y in zip(ap, reversed(bp)))
    error = min(fwd, rev)
    return error <= SPACE_TOL and close(a['length'], b['length']), error, rev < fwd

def audit(obs):
    generated = obs['generated']
    route = [(g, s) for g, group in enumerate(obs['route_groups']) for s in group]
    states = obs['states']
    result = dict(generated_count=len(generated), route_count=len(route), state_count=len(states),
                  A1_status='INCONCLUSIVE', A2_status='INCONCLUSIVE',
                  A3_status='INCONCLUSIVE', A4_status='INCONCLUSIVE',
                  missing_swaths=0, extra_swaths=0, repeated_swaths=0,
                  missing_connections=0, zero_length_connections=0,
                  connector_overlap_count=0, max_swath_error_m=0.0,
                  max_gap_m=0.0, max_length_residual_m=0.0,
                  details=[])
    if not generated or not route or not states:
        result['details'].append({'kind':'empty_generated_route_or_path'})
        return result
    nums = [obs['complete_path_length_m'], obs['path_length_m'], obs['swath_total_length_m']]
    for sw in generated + [x[1] for x in route]:
        nums.extend([sw['length']] + [v for p in sw['points'] for v in p])
    for s in states:
        nums.extend([s['angle'], s['len']] + s['point'] + s['end'])
    if not all(map(math.isfinite, nums)):
        result['details'].append({'kind':'nonfinite_observation'})
        return result

    # A1: one-to-one generated/route matching, then exact ordered segments in final SWATH states.
    used = set()
    matches = []
    ambiguous = False
    for j, (_, sw) in enumerate(route):
        options = [(i, same_poly(src, sw)) for i, src in enumerate(generated) if i not in used]
        options = [(i, data) for i, data in options if data[0]]
        if len(options) != 1:
            if len(options) > 1:
                ambiguous = True
            result['extra_swaths'] += 1
            result['details'].append({'kind':'route_match', 'route_swath_index':j,
                                      'candidate_generated_indices':[i for i, _ in options]})
            matches.append(None)
        else:
            i, (_, err, reversed_dir) = options[0]
            used.add(i)
            result['max_swath_error_m'] = max(result['max_swath_error_m'], err)
            matches.append(dict(generated_index=i, reversed=reversed_dir, geometry_error_m=err,
                                length_delta_m=sw['length']-generated[i]['length']))
    result['missing_swaths'] = len(generated) - len(used)
    result['repeated_swaths'] = max(0, len(route)-len(generated))
    for i in range(len(generated)):
        if i not in used:
            result['details'].append({'kind':'missing_generated_swath', 'generated_index':i,
                                      'cell_id':generated[i]['cell_id'],
                                      'local_id':generated[i]['local_id']})
    result['swath_matches'] = matches
    swath_state_indices = [i for i, s in enumerate(states) if s['type'] == 1]
    expected_segments = sum(max(0, len(sw['points'])-1) for _, sw in route)
    path_match = len(swath_state_indices) == expected_segments
    spans = []
    cursor = 0
    if path_match:
        for j, (g, sw) in enumerate(route):
            n = len(sw['points'])-1
            idxs = swath_state_indices[cursor:cursor+n]
            cursor += n
            spans.append((idxs[0], idxs[-1]) if idxs else None)
            for k, idx in enumerate(idxs):
                s = states[idx]
                error = max(dist(s['point'], sw['points'][k]), dist(s['end'], sw['points'][k+1]))
                result['max_swath_error_m'] = max(result['max_swath_error_m'], error)
                if error > SPACE_TOL or not close(abs(s['len']), dist(sw['points'][k],sw['points'][k+1])):
                    path_match = False
                    result['details'].append({'kind':'path_swath_segment', 'route_swath_index':j,
                                              'state_index':idx, 'delta_m':error,
                                              'expected':sw['points'][k:k+2],
                                              'observed':[s['point'],s['end']]})
    else:
        result['details'].append({'kind':'swath_segment_count', 'expected':expected_segments,
                                  'observed':len(swath_state_indices)})
    result['A1_status'] = 'INCONCLUSIVE' if ambiguous else ('PASS' if not result['missing_swaths'] and not result['extra_swaths'] and path_match else 'FAIL')

    # A3: all state joins, including joins across appended route groups.
    gaps = [dist(states[i]['end'], states[i+1]['point']) for i in range(len(states)-1)]
    result['max_gap_m'] = max(gaps, default=0.0)
    bad_gaps = [i for i, gap in enumerate(gaps) if gap > SPACE_TOL]
    result['gap_count'] = len(bad_gaps)
    result['gap_p50_m'] = sorted(gaps)[len(gaps)//2] if gaps else 0.0
    result['gap_p99_m'] = sorted(gaps)[min(len(gaps)-1, int(.99*len(gaps)))] if gaps else 0.0
    for i in bad_gaps[:30]:
        result['details'].append({'kind':'spatial_gap', 'state_index':i, 'next_state_index':i+1,
                                  'expected':states[i]['end'], 'observed':states[i+1]['point'],
                                  'delta_m':gaps[i], 'types':[states[i]['type'],states[i+1]['type']]})
    result['A3_status'] = 'PASS' if not bad_gaps else 'FAIL'

    # A2: each adjacent pair owns its intervening nonwork state range.
    assigned = set()
    transitions = []
    if len(spans) == len(route) and all(spans):
        for j in range(len(route)-1):
            a, b = spans[j], spans[j+1]
            idxs = list(range(a[1]+1, b[0]))
            prev_end = route[j][1]['points'][-1]
            next_start = route[j+1][1]['points'][0]
            start_error = dist(states[a[1]]['end'], prev_end)
            end_error = dist(states[b[0]]['point'], next_start)
            valid = start_error <= SPACE_TOL and end_error <= SPACE_TOL
            if idxs:
                valid &= all(states[i]['type'] != 1 for i in idxs)
                valid &= dist(states[idxs[0]]['point'], prev_end) <= SPACE_TOL
                valid &= dist(states[idxs[-1]]['end'], next_start) <= SPACE_TOL
            else:
                valid &= dist(prev_end, next_start) <= SPACE_TOL
                if valid:
                    result['zero_length_connections'] += 1
            if any(i in assigned for i in idxs):
                result['connector_overlap_count'] += 1
                valid = False
            assigned.update(idxs)
            transition = dict(id=j, route_swath_from=j, route_swath_to=j+1,
                              from_group=route[j][0], to_group=route[j+1][0],
                              state_indices=idxs, start_expected=prev_end, end_expected=next_start,
                              length_m=sum(abs(states[i]['len']) for i in idxs),
                              status='PASS' if valid else 'FAIL')
            transitions.append(transition)
            if not valid:
                result['missing_connections'] += 1
                result['details'].append({'kind':'transition', **transition,
                                          'start_error_m':start_error, 'end_error_m':end_error})
        result['A2_status'] = 'PASS' if not result['missing_connections'] else 'FAIL'
    result['transitions'] = transitions

    # A4: exact state ledger, unique transition assignment and explicit head/tail.
    work = sum(abs(s['len']) for s in states if s['type'] == 1)
    nonwork = sum(abs(s['len']) for s in states if s['type'] != 1)
    total = work + nonwork
    extra_nonwork = [i for i,s in enumerate(states) if s['type'] != 1 and i not in assigned]
    result['work_length_m'] = work
    result['nonwork_length_m'] = nonwork
    result['connector_length_m'] = sum(x['length_m'] for x in transitions)
    result['extra_nonwork_state_indices'] = extra_nonwork
    result['extra_nonwork_length_m'] = sum(abs(states[i]['len']) for i in extra_nonwork)
    result['length_residual_m'] = total - obs['complete_path_length_m']
    result['work_residual_m'] = work - sum(s['length'] for s in generated)
    result['max_length_residual_m'] = max(abs(result['length_residual_m']), abs(result['work_residual_m']),
                                        abs(total-obs['path_length_m']))
    ledger_ok = (result['A1_status'] == 'PASS' and result['A2_status'] == 'PASS'
                 and close(total, obs['path_length_m'])
                 and close(total, obs['complete_path_length_m'])
                 and close(work, sum(s['length'] for s in generated))
                 and result['connector_overlap_count'] == 0
                 and close(result['connector_length_m'] + result['extra_nonwork_length_m'], nonwork))
    result['A4_status'] = 'PASS' if ledger_ok else ('INCONCLUSIVE' if result['A1_status'] == 'INCONCLUSIVE' or result['A2_status'] == 'INCONCLUSIVE' else 'FAIL')
    if not ledger_ok:
        result['details'].append({'kind':'length_ledger', 'expected':obs['complete_path_length_m'],
                                  'observed':total, 'delta_m':result['length_residual_m'],
                                  'work_delta_m':result['work_residual_m']})
    return result

def run_one(row, exe, timeout):
    cmd = [str(exe), '--wkt-file', row['wkt_path'], '--angle-deg', str(row['angle_deg'])]
    begin = time.time()
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, timeout=timeout)
        status = 'SUCCESS' if p.returncode == 0 else 'ERROR'
        return dict(status=status, exit_code=p.returncode, stdout=p.stdout,
                    stderr=p.stderr, elapsed_s=time.time()-begin, command=cmd)
    except subprocess.TimeoutExpired as e:
        return dict(status='TIMEOUT', exit_code=None, stdout=(e.stdout or b'').decode(errors='replace'),
                    stderr=(e.stderr or b'').decode(errors='replace'), elapsed_s=time.time()-begin,
                    command=cmd)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--timeout', type=int, default=120)
    args = ap.parse_args()
    plan = make_plan()
    (OUT / 's7_predeclared_cases.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    if not args.smoke and not args.all:
        print('planned', len(plan)); return
    done = {}
    evidence = OUT / 's7_observations.jsonl'
    if evidence.exists():
        for line in evidence.read_text(encoding='utf-8').splitlines():
            if line:
                x = json.loads(line)
                if x['status'] != 'BLOCKED_WKT_HASH':
                    done[(x['field_id'], x['angle_deg'])] = x
    smoke = []
    for family in sorted({r['family'] for r in plan}):
        smoke.extend([r for r in plan if r['family'] == family and r['sample_role'] == 'oracle_1deg'][:2])
    selected = smoke if args.smoke else plan
    for row in selected:
        key = (row['field_id'], row['angle_deg'])
        if key in done:
            continue
        record = dict(row)
        record['started_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        if not row['wkt_hash_verified']:
            record.update(status='BLOCKED_WKT_HASH', stderr='missing or hash mismatch')
        else:
            run = run_one(row, OBSERVER, args.timeout)
            (OUT / 'stderr.log').open('a', encoding='utf-8').write(f"{key}: {run['stderr']}\n")
            record.update(status=run['status'], exit_code=run['exit_code'],
                          elapsed_s=run['elapsed_s'], stderr=run['stderr'], command=run['command'])
            if run['status'] == 'SUCCESS':
                try:
                    obs = json.loads(run['stdout'])
                    record['observation'] = obs
                    record['audit'] = audit(obs)
                except (ValueError, KeyError, TypeError) as ex:
                    record['status'] = 'MALFORMED_OBSERVATION'
                    record['stderr'] += repr(ex)
            if args.smoke and record['status'] == 'SUCCESS':
                baseline = run_one(row, ORIGINAL, args.timeout)
                record['baseline'] = dict(status=baseline['status'], stderr=baseline['stderr'],
                                          elapsed_s=baseline['elapsed_s'])
                if baseline['status'] == 'SUCCESS':
                    b = json.loads(baseline['stdout'])
                    record['baseline']['values'] = b
                    o = record['observation']
                    record['baseline']['match'] = (b['swath_count'] == len(o['generated'])
                        and close(b['swath_total_length_m'], o['swath_total_length_m'])
                        and close(b['complete_path_length_m'], o['complete_path_length_m']))
        record['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        with evidence.open('a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False, separators=(',',':'), allow_nan=False)+'\n')
            f.flush(); os.fsync(f.fileno())
        print(row['field_id'], row['angle_deg'], record['status'],
              [record.get('audit',{}).get('A'+str(i)+'_status') for i in range(1,5)], flush=True)

if __name__ == '__main__':
    main()
