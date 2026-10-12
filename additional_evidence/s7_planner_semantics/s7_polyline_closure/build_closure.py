#!/usr/bin/env python3
"""Read-only implementation audit for the pinned CLBOS/F2C execution path."""
import csv
import datetime
import hashlib
import json
import math
import pathlib
import statistics
import subprocess

ROOT = pathlib.Path('<ORIGINAL_WORKSPACE>/ 's7_pinned_planner_semantics_audit'
A3 = P / 's7_a3_root_cause_audit'
OUT = P / 's7_polyline_closure'
F2C = pathlib.Path('<ORIGINAL_CACHE>/Fields2Cover')
REL = ROOT / 'release/CLBOS_BiosystemsEngineering_Reproducibility'
BIN = pathlib.Path('<ORIGINAL_CACHE>/Fields2Cover-build/agri_f2c_runner')
LIB = pathlib.Path('<ORIGINAL_CACHE>/Fields2Cover-build/fields2cover/libFields2Cover.so')
SPACE_TOL = 1e-6
LENGTH_ABS_TOL = 1e-6
LENGTH_REL_TOL = 1e-10

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def rows(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def emit_csv(path, records, columns):
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        w.writeheader(); w.writerows(records)

def xy(p,q):
    return math.hypot(p[0]-q[0],p[1]-q[1])

def near(a,b):
    return math.isfinite(a) and math.isfinite(b) and abs(a-b) <= LENGTH_ABS_TOL + LENGTH_REL_TOL*max(abs(a),abs(b))

def mst(swaths):
    if len(swaths)<=1:return 0.0
    used={0}; total=0.0
    while len(used)<len(swaths):
        options=[]
        for i in used:
            for j in range(len(swaths)):
                if j in used: continue
                w=min(xy(swaths[i]['points'][a],swaths[j]['points'][b])
                      for a in (0,-1) for b in (0,-1))
                options.append((w,j))
        w,j=min(options)
        total+=w; used.add(j)
    return total

def source_row(n,file,func,lines,caller,inputs,outputs,branch,length,risk):
    return dict(step=n,source_file=str(file),function=func,line_range=lines,
                caller=caller,input_objects=inputs,output_objects=outputs,
                branch_condition=branch,length_geometry=length,unverified_risk=risk)

def make_callchain():
    R=ROOT/'runner/src/agri_f2c_runner.cpp'
    M=ROOT/'runner/src/agri_f2c_mst_probe.cpp'
    S=F2C/'src/fields2cover'
    H=F2C/'include/fields2cover'
    return [
      source_row(1,R,'main: input/headland/decomposition','105-145','CLI','metric WKT, angle, robot 2m/2m/radius2m','mid_headland, working_cells','stock decompose; narrow MultiPolygon fallback','UTM metres; 3m+3m headland','fallback changes geometry only for known numerical exception'),
      source_row(2,S/'swath_generator/swath_generator_base.cpp','SwathGeneratorBase::generateSwaths','33-61','runner:147','angle, width, working_cells','SwathsByCells','each cell generates clipped parallel lines','swath geometry polyline','individual degenerate swath not rejected'),
      source_row(3,R,'swath_length','23-33,149-151','runner main','SwathsByCells','count, LB0','reject count<=0 or total<=0 at 151','SwathLength over each Swath','sum does not prove downstream preservation'),
      source_row(4,S/'objectives/sg_obj/swath_length.cpp','SwathLength::computeCost','11-13','swath_length','Swath','double','none','Swath::length -> LineString OGR get_Length','nonnegative under finite polyline geometry'),
      source_row(5,S/'route_planning/route_planner_base.cpp','RoutePlannerBase::genRoute','21-34','runner:161','mid_headland, SwathsByCells','F2CRoute','default redirect_swaths=true, d_tol=1e-4','graph uses integer-scaled costs','no per-swath coverage invariant checked'),
      source_row(6,S/'route_planning/route_planner_base.cpp','computeBestRoute','149-190','genRoute','coverage graph','route node IDs','solver solution dereferenced at 184 without null guard','route-graph cost; not final J','solver failure may crash; ID sequence alone does not prove coverage'),
      source_row(7,S/'route_planning/route_planner_base.cpp','transformSolutionToRoute','193-227','genRoute','route IDs, swaths, graphs','route groups/connections','endpoint-coordinate match then first matching swath; optional depot branch','no final length','ambiguous/duplicate endpoints can select wrong swath; no matched-count assertion'),
      source_row(8,S/'types/Route.cpp','Route::addSwath/ addConnection','43-89','transformSolutionToRoute','swath, shortest graph','new group and connection','nonempty route adds connection before each next swath','no length charge here','empty shortestPath still creates connection object'),
      source_row(9,S/'path_planning/path_planning.cpp','PathPlanning::planPath(route)','12-25','runner:164','robot, route, Dubins','F2CPath','each group and optional terminal connection','concatenates charged state vectors','no completeness/seam assertion'),
      source_row(10,S/'path_planning/path_planning.cpp','planPath(swaths)','28-43','planPath(route)','one route group','group path','if size>1 turn_path.discretize(0.1)','swath/turn states','same-group branch source-excluded for fixed genRoute path'),
      source_row(11,S/'path_planning/path_planning.cpp','planPathForConnection','46-89,104-157','planPath(route)','previous/next swaths and route multipoint','zero or more turn paths','empty endpoint branch returns {}; simplify may reduce waypoints','createTurn state lengths','empty turn can leave needed transition uncharged'),
      source_row(12,S/'path_planning/turning_base.cpp','TurningBase::createTurn/correctPath','30-78','planPathForConnection','endpoint poses, cache, Dubins','TURN Path','size<=1 returns empty; correctPath shifts endpoints if <0.05m','may move sampled point without recomputing len','polyline charge equality not invariant'),
      source_row(13,S/'path_planning/dubins_curves.cpp','DubinsCurves::createSimpleTurn','13-35','TurningBase::createTurn','robot max curvature, 0.01 discretization','steering states -> Path','forward Dubins library path','sampled curve','external steering failures not validated by adapter'),
      source_row(14,H/'path_planning/steer_to_path.hpp','steerStatesToPath','21-39','DubinsCurves','sampled pose states','TURN PathStates','last state len=0','len=distance to next sample; heading stored separately','correctPath may later break chord/len equality'),
      source_row(15,S/'types/Path.cpp','Path::appendSwath','210-223','planPath(swaths)','route swath vertices','SWATH PathStates','each consecutive vertex pair','len=vertex chord; dir=FORWARD','no validation of degenerate/missing vertices'),
      source_row(16,S/'types/Path.cpp','Path::operator+=','99-103','planPath and planPathForConnection','Path states','concatenated Path','unconditional append','preserves each state len; no overlap accounting','no seam/duplicate check'),
      source_row(17,S/'types/Path.cpp','Path::populate/reduce/discretize','346-440','same-group turn only in fixed planPath','turn Path','resampled/reduced Path','requires group size>1; source-excluded here','spline position/angle; merged len','if reached elsewhere chord/charge relation requires separate audit'),
      source_row(18,S/'types/Path.cpp','Path::length','205-208','PPObjective','all PathStates','double J','none','sum fabs(state.len)','finite sum cannot certify geometry completeness'),
      source_row(19,H/'objectives/pp_obj/path_length.h','PathLength::computeCost inherited','15-19','runner:166','F2CPath','double','inherits PPObjective','Path::length','no independent accounting check'),
      source_row(20,S/'objectives/pp_obj/pp_objective.cpp','PPObjective::computeCost','11-13','PathLength','F2CPath','double','none','returns Path::length','does not inspect chord or route'),
      source_row(21,R,'main: complete result','160-180','CLI','F2CRoute, F2CPath','JSON complete_path_length_m','reject only nonfinite/nonpositive complete','PathLength cost; turns=max(0,J-Lsw)','positive finite J can still hide omitted swath/connector'),
      source_row(22,M,'mst_endpoint_distance/mst_connection_bound','102-148,218-226','MST sidecar','same generated SwathsByCells','LB1=LB0+MST','complete graph; min of four endpoints; Prim; n<=1 ->0','Euclidean endpoint relaxation in metric CRS','requires route-to-work identity and charged connector premises')
    ]

def main():
    OUT.mkdir(exist_ok=True)
    m=json.loads((P/'s7_evidence_manifest.json').read_text(encoding='utf-8'))
    a3m=json.loads((A3/'s7_a3_integrity.json').read_text(encoding='utf-8'))
    assert m['gate']=='FAIL' and a3m['first_s7_gate_unchanged']=='FAIL'
    head=subprocess.check_output(['git','-C',str(F2C),'rev-parse','HEAD'],text=True).strip()
    assert head==m['f2c_head']=='92b9f2fcf72d26c44202f9d2ab54fbf25ed87426'
    assert not subprocess.check_output(['git','-C',str(F2C),'status','--porcelain'],text=True).strip()
    assert sha(ROOT/'runner/src/agri_f2c_runner.cpp')==m['adapter_sha256']
    assert sha(BIN)==m['original_binary_sha256'] and sha(LIB)==m['linked_library_sha256']
    previous={}
    for n in ['S7_PINNED_PLANNER_AUDIT.md','s7_case_results.csv','s7_case_audits.jsonl',
              's7_observations.jsonl','s7_failures.jsonl','s7_evidence_manifest.json']:
        previous[str(P/n)]=sha(P/n)
        if n in m['file_sha256']: assert previous[str(P/n)]==m['file_sha256'][n]
    for n, expected in m['file_sha256'].items():
        path=P/n
        assert sha(path)==expected
        previous[str(path)]=expected
    for name, expected in m['source_hashes'].items():
        path=pathlib.Path(name)
        assert sha(path)==expected
        previous[str(path)]=expected
    for n in ['S7_A3_ROOT_CAUSE_AUDIT.md','s7_a3_gap_by_type.csv',
              's7_a3_connector_error_budget.csv','s7_a3_lower_bound_impact.csv','s7_a3_integrity.json']:
        previous[str(A3/n)]=sha(A3/n)
        if n in a3m['new_file_sha256']: assert previous[str(A3/n)]==a3m['new_file_sha256'][n]
    for n, expected in a3m['new_file_sha256'].items():
        path=A3/n
        assert sha(path)==expected
        previous[str(path)]=expected
    bounds=REL/'data/derived/cross_stage/bound_1deg.csv'
    full=REL/'data/derived/cross_stage/full_evaluations.csv'
    previous[str(bounds)]=sha(bounds); previous[str(full)]=sha(full)
    old_cases={(r['field_id'],int(r['angle_deg'])):r for r in rows(P/'s7_case_results.csv')}
    bound={(r['field_id'],int(r['angle_deg'])):r for r in rows(bounds)}
    final={(r['field_id'],int(r['angle_deg'])):r for r in rows(full)}
    obs={(r['field_id'],r['angle_deg']):r for r in
         (json.loads(x) for x in (P/'s7_observations.jsonl').open(encoding='utf-8'))}
    aud={(r['field_id'],r['angle_deg']):r['audit'] for r in
         (json.loads(x) for x in (P/'s7_case_audits.jsonl').open(encoding='utf-8'))}
    assert len(obs)==len(aud)==6
    source=make_callchain()
    emit_csv(OUT/'s7_source_callchain.csv',source,list(source[0]))

    checks=[]; sample_counts={'connectors':0,'nonwork_states':0,'zero_states':0,'reverse_swaths':0,
                              'backward_states':0,'polyline_pass':0,'single_swath_cases':0}
    case_summary=[]
    for key in sorted(obs):
        record=obs[key]; o=record['observation']; aa=aud[key]
        assert record['status']=='SUCCESS' and record['baseline']['match']
        states=o['states']; generated=o['generated']; route=[s for group in o['route_groups'] for s in group]
        assert aa['A1_status']==aa['A2_status']==aa['A4_status']=='PASS'
        assert len(route)==len(generated) and all(len(group)==1 for group in o['route_groups'])
        assert all(math.isfinite(v) for s in states for v in
                   [s['len'],s['angle'],*s['point'],*s['end']])
        nrev=sum(x['reversed'] for x in aa['swath_matches'])
        sample_counts['reverse_swaths']+=nrev
        mst_recomputed=mst(generated)
        b=bound[key]; f=final[key]
        assert b['status']==f['status']=='SUCCESS'
        lb0=float(b['swath_total_length_m']); lb1=float(b['mst_total_lb_m'])
        assert near(lb0,o['swath_total_length_m'])
        assert near(lb0+mst_recomputed,lb1)
        assert near(float(f['complete_path_length_m']),o['complete_path_length_m'])
        assert near(sum(abs(s['len']) for s in states),o['path_length_m'])
        assert near(o['path_length_m'],o['complete_path_length_m'])
        all_nonwork={i for i,s in enumerate(states) if s['type']!=1}
        assigned=[]
        for t in aa['transitions']: assigned+=t['state_indices']
        assert len(assigned)==len(set(assigned)) and set(assigned)==all_nonwork
        sample_counts['backward_states']+=sum(s['dir']==-1 for s in states)
        if len(generated)==1:
            sample_counts['single_swath_cases']+=1
            assert not aa['transitions'] and not all_nonwork
        for t in aa['transitions']:
            ids=t['state_indices']; assert ids and all(states[i]['type']!=1 for i in ids)
            j=t['id']
            prev=route[j]['points'][-1]; nxt=route[j+1]['points'][0]
            start_err=xy(states[ids[0]]['point'],prev)
            end_err=xy(states[ids[-1]]['end'],nxt)
            charged=math.fsum(abs(states[i]['len']) for i in ids)
            chords=[]; residuals=[]; zeros=0; unbilled=0; backward=0; illegal_dir=0
            for i in ids:
                s=states[i]; assert i+1<len(states)
                chord=xy(s['point'],states[i+1]['point']); chords.append(chord)
                residuals.append(chord-abs(s['len']))
                if abs(s['len'])<1e-12:
                    zeros+=1
                    if chord>SPACE_TOL:unbilled+=1
                if s['dir']==-1:backward+=1
                if s['dir'] not in (1,-1):illegal_dir+=1
            polyline=math.fsum(chords)
            direct=xy(prev,nxt)
            per_state_ok=all(near(chords[k],abs(states[i]['len'])) for k,i in enumerate(ids))
            total_ok=near(polyline,charged)
            endpoint_ok=start_err<=SPACE_TOL and end_err<=SPACE_TOL
            no_unbilled=unbilled==0 and illegal_dir==0
            pass_here=per_state_ok and total_ok and endpoint_ok and no_unbilled and charged+LENGTH_ABS_TOL>=direct
            sample_counts['connectors']+=1
            sample_counts['nonwork_states']+=len(ids)
            sample_counts['zero_states']+=zeros
            sample_counts['polyline_pass']+=bool(pass_here)
            checks.append(dict(row_type='CONNECTOR',field_id=key[0],angle_deg=key[1],
                connector_id=j,generated_swath_count=len(generated),route_group_count=len(o['route_groups']),
                route_swath_reversal_count=nrev,first_nonwork_state=ids[0],last_nonwork_state=ids[-1],
                nonwork_state_count=len(ids),zero_len_state_count=zeros,backward_state_count=backward,
                invalid_direction_count=illegal_dir,unbilled_nonzero_step_count=unbilled,
                endpoint_start_error_m=start_err,endpoint_end_error_m=end_err,
                max_abs_state_charge_chord_residual_m=max(map(abs,residuals)),
                sum_state_charge_chord_residual_m=math.fsum(residuals),
                charged_state_length_m=charged,sampled_polyline_length_m=polyline,
                polyline_minus_charged_m=polyline-charged,
                euclidean_endpoint_distance_m=direct,charged_minus_direct_m=charged-direct,
                per_state_match=per_state_ok,whole_connector_match=total_ok,
                endpoints_match=endpoint_ok,polyline_status='PASS' if pass_here else 'FAIL',
                strict_a3_status='FAIL' if aa['A3_status']=='FAIL' else 'PASS',
                observation_source=str(P/'s7_observations.jsonl')))
        case_summary.append(dict(field_id=key[0],angle_deg=key[1],swaths=len(generated),
                                 connectors=len(aa['transitions']),reversed_swaths=nrev,
                                 lb0=lb0,lb1=lb1,recomputed_mst=mst_recomputed,
                                 J=o['complete_path_length_m'],strict_a3=aa['A3_status']))
    assert sample_counts['connectors']==44 and sample_counts['polyline_pass']==44
    assert sample_counts['single_swath_cases']==3 and sample_counts['backward_states']==0
    case_checks=[dict(row_type='CASE',field_id=x['field_id'],angle_deg=x['angle_deg'],
                      generated_swath_count=x['swaths'],route_group_count=x['swaths'],
                      route_swath_reversal_count=x['reversed_swaths'],
                      connector_count=x['connectors'],lb0_m=x['lb0'],lb1_m=x['lb1'],
                      recomputed_mst_m=x['recomputed_mst'],complete_J_m=x['J'],
                      J_minus_lb1_m=x['J']-x['lb1'],
                      lower_bounds_status='PASS' if x['lb0']<=x['lb1']<=x['J'] else 'FAIL',
                      strict_a3_status=x['strict_a3'],
                      polyline_status='PASS' if all(c['polyline_status']=='PASS' for c in checks
                                  if c['field_id']==x['field_id'] and c['angle_deg']==x['angle_deg']) else 'FAIL',
                      observation_source=str(P/'s7_observations.jsonl'))
                 for x in case_summary]
    check_columns=list(dict.fromkeys(k for item in checks+case_checks for k in item))
    emit_csv(OUT/'s7_polyline_case_checks.csv',checks+case_checks,check_columns)

    # Source, runtime and mathematical evidence are kept separate.
    proof=[
      dict(obligation='A1 mandatory work exactly once',condition='Generated swath multiset equals ordered charged SWATH-state polylines',
           source='runner:147-151; route_planner_base.cpp:193-222; Path.cpp:210-223',
           runtime=f"PASS 6/6; including 3 multi-swath cases and {sample_counts['reverse_swaths']} reversed route swaths",
           implementation_status='INCONCLUSIVE',gap='Coordinate-based first match and no unique-ID/count invariant for arbitrary inputs'),
      dict(obligation='A2 all required connectors',condition='Every consecutive swath pair owns a distinct nonwork state interval with legal endpoints',
           source='Route.cpp:56-79; path_planning.cpp:12-25,46-89; turning_base.cpp:30-78',
           runtime='PASS 44/44 observed inter-swath connectors; 3 singleton cases vacuous',
           implementation_status='INCONCLUSIVE',gap='createTurn may return empty; correctPath does not force an endpoint beyond its 0.05m window'),
      dict(obligation='A3-STRICT',condition='Each atEnd equals next state point within 1e-6m',
           source='PathState.cpp:11-13; steer_to_path.hpp:24-35',
           runtime='FAIL in all 3 multi-swath cases; 48085 TURN→TURN gaps >1e-6m',
           implementation_status='FAIL',gap='Chord-length versus tangent-heading representation'),
      dict(obligation='A3-POLYLINE',condition='Each charged nonwork len equals next-sample chord; ordered samples meet swath endpoints; no unpaid jump',
           source='steer_to_path.hpp:24-39; Path.cpp:99-103,205-208; turning_base.cpp:65-78',
           runtime=f"PASS {sample_counts['polyline_pass']}/{sample_counts['connectors']} observed connectors, {sample_counts['nonwork_states']} nonwork states; no unpaid zero-length step",
           implementation_status='PASS_OBSERVED_ONLY',gap='correctPath can shift samples without recomputing len; exceptional/empty turn paths unverified'),
      dict(obligation='A4 complete nonnegative ledger',condition='J includes every mandatory work edge and distinct connector state exactly once plus nonnegative extras',
           source='Path.cpp:99-103,205-223; path_length.h:15-19; pp_objective.cpp:11-13',
           runtime='PASS 6/6 ledger; all observed nonwork indices assigned exactly once',
           implementation_status='INCONCLUSIVE',gap='No global guard against missing work or connectors before positive finite J return'),
      dict(obligation='LB0',condition='Generated mandatory swath length <= complete charged J',
           source='runner:23-33,147-174; SwathLength.cpp:11-13',
           runtime='Frozen LB0 equals observed generated length; LB0<=J in 6/6',
           implementation_status='CONDITIONAL',gap='Requires A1/A4 on each finite plan'),
      dict(obligation='LB1 endpoint MST relaxation',condition='Complete graph on generated swaths; each edge min over four endpoint distances; MST <= connected charged connector sum',
           source='agri_f2c_mst_probe.cpp:102-148,218-226',
           runtime='Independent Prim reconstruction matches frozen LB1 in 6/6; LB1<=J in 6/6',
           implementation_status='PASS_CONDITIONAL_MAPPING',gap='Requires A1, A2 and A3-POLYLINE charged-connector premises on all candidate plans'),
      dict(obligation='Proposition 1 finite-angle stopping',condition='For every finite candidate LB<=J and all unresolved candidates handled correctly; then ordered lower-bound stop is admissible',
           source='runner/clbos01_run_heldout_topk.py:220-275; bound sidecar',
           runtime='Numerical bound relation in 6/6 only; 127 S7 cases unrun',
           implementation_status='CONDITIONAL_ONLY',gap='Current JESTECH text unavailable; path invariants not proven for every candidate'),
    ]
    emit_csv(OUT/'s7_proof_obligation_matrix.csv',proof,list(proof[0]))
    branches=[
      dict(branch='Same-group multi-swath and turn_path.discretize(0.1)',reachability='SOURCE_PROVEN_EXCLUDED',evidence='transformSolutionToRoute calls only Route::addSwath(s,g); nonempty route first adds connection, then addSwath opens a new group. Adapter never mutates route.',case_count='0',residual='Not excluded for arbitrary caller-supplied Route; outside fixed adapter.'),
      dict(branch='Route swath reversal',reachability='RUNTIME_VERIFIED',evidence='transformSolutionToRoute reverses matched swath; A1 geometry comparison permits reversal.',case_count=str(sample_counts['reverse_swaths']),residual='Vehicle backward direction is distinct and unobserved.'),
      dict(branch='Backward PathDirection on TURN states',reachability='UNRESOLVED',evidence='PathState enum allows -1; observed states are all +1; fixed Dubins library path not independently proven forward for every degenerate input.',case_count='0',residual='Polyine point-chord check is direction-neutral, but heading reconstruction/feasibility is not globally verified.'),
      dict(branch='Ordinary inter-swath multipoint connections',reachability='RUNTIME_VERIFIED',evidence='44 distinct connector state intervals; all charged sample chords and endpoints checked.',case_count='44',residual='Finite evidence only.'),
      dict(branch='Multiple consecutive Dubins subturns and zero terminal states',reachability='RUNTIME_VERIFIED',evidence='Each observed connector has >=3 zero-length TURN states; all zero states lead to zero next-sample displacement.',case_count=str(sample_counts['zero_states']),residual='No guarantee for unseen waypoint topology.'),
      dict(branch='One generated swath',reachability='RUNTIME_VERIFIED',evidence='Three observed singleton plans contain one charged SWATH state and no mandatory connector.',case_count='3',residual='Does not exercise transition safety.'),
      dict(branch='Depot start/end extra connections',reachability='SOURCE_PROVEN_EXCLUDED',evidence='RoutePlannerBase::r_start_end defaults empty; fixed production adapter never calls setStartAndEndPoint.',case_count='0',residual='Other callers can enable this branch.'),
      dict(branch='Empty route MultiPoint between distinct swaths',reachability='SOURCE_SUPPORTED',evidence='Route::addConnection(empty) creates a connection group; planPathForConnection still constructs p1,p2 from adjacent swaths.',case_count='not isolated',residual='createTurn can still return empty; missing charged motion not globally excluded.'),
      dict(branch='Geometrically coincident swath endpoints / legal zero travel',reachability='UNRESOLVED',evidence='No observed zero-length required connector; source may generate empty turn for coincident poses.',case_count='0',residual='Need prove endpoint coincidence and no missing nonzero movement.'),
      dict(branch='createTurn returns <=1 state / failed steering path',reachability='SOURCE_SUPPORTED',evidence='turning_base.cpp:49 explicitly returns empty Path; adapter checks only finite positive total J.',case_count='0',residual='For separated swaths this could violate A2; reachability under frozen inputs not established.'),
      dict(branch='correctPath point adjustment without len update',reachability='SOURCE_SUPPORTED',evidence='turning_base.cpp:65-77 may shift first or last sample up to 0.05m; steer_to_path.hpp computes len before this.',case_count='observed chord residual <=1.35e-9m',residual='Potential under/overcharge for other inputs; no global tolerance proof.'),
      dict(branch='Ambiguous duplicate endpoint geometry in transformSolutionToRoute',reachability='SOURCE_SUPPORTED',evidence='route_planner_base.cpp:203-220 selects first endpoint-equal swath and breaks, with no stable ID or matched-count check.',case_count='0 observed ambiguous',residual='Could duplicate/omit a distinct mandatory swath.'),
      dict(branch='Route solver null or uncovered route IDs',reachability='UNRESOLVED',evidence='route_planner_base.cpp:178-189 dereferences solution and transform lacks coverage count assertion.',case_count='0 observed failures',residual='Crash/unresolved is separate from valid finite; a positive incomplete path remains possible.'),
      dict(branch='Nonfinite state coordinate but finite len sum',reachability='UNRESOLVED',evidence='runner:167 rejects nonfinite total only; Path::length sums len, not coordinates.',case_count='0 observed',residual='No source-wide coordinate finiteness guard on positive finite return.'),
      dict(branch='Repeated geometry points and degenerate swath',reachability='UNRESOLVED',evidence='Path::appendSwath iterates numPoints()-1; generation/runner reject only total count/length.',case_count='0 observed',residual='Degenerate individual swaths and zero edges need separate validity criterion.'),
    ]
    emit_csv(OUT/'s7_branch_coverage.csv',branches,list(branches[0]))

    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    multi=[x for x in case_summary if x['swaths']>1]
    min_margin=min(x['J']-x['lb1'] for x in multi)
    max_res=max(float(x['max_abs_state_charge_chord_residual_m']) for x in checks)
    max_connector_total=max(abs(float(x['polyline_minus_charged_m'])) for x in checks)
    max_endpoint=max(max(float(x['endpoint_start_error_m']),float(x['endpoint_end_error_m'])) for x in checks)
    max_mst_res=max(abs(x['lb0']+x['recomputed_mst']-x['lb1']) for x in case_summary)
    statuses='''TASK_STATUS=PARTIAL
A1_IMPLEMENTATION=INCONCLUSIVE
A2_IMPLEMENTATION=INCONCLUSIVE
A3_STRICT_CONTINUITY=FAIL
A3_POLYLINE_SEMANTICS=PASS
A4_IMPLEMENTATION=INCONCLUSIVE
SAME_GROUP_MULTISWATH_BRANCH=EXCLUDED
SPECIAL_CONNECTION_BRANCHES=INCONCLUSIVE
MST_RELAXATION_MAPPING=PASS
PROPOSITION1_IMPLEMENTATION_SCOPE=CONDITIONAL_ONLY
S7_ORIGINAL_GATE=FAIL
S7_REFINED_POLYLINE_GATE=INCONCLUSIVE
SOURCE_LEVEL_PROOF_COMPLETE=FALSE
RUNTIME_EVIDENCE_COMPLETE=FALSE
SCIENTIFIC_METHOD_CHANGED=FALSE'''
    report=f'''# S7 pinned-planner polyline semantics and Proposition 1 implementation closure

Created {now} (Asia/Shanghai). This is an independent, read-only analysis of the pinned production source and six existing observations. No planner case was rerun. Original strict S7 `FAIL` and A3 root-cause files remain unchanged.

## Decision

```text
{statuses}
```

The charged sampled-polyline interpretation passes in the **44 observed required inter-swath connectors**, while the `PathState::atEnd()` interpretation fails in all three multi-swath cases. This distinction explains the earlier 25 µm A3 result; it does not close the implementation-wide proof. A1, A2 and A4 are supported by these six observations but are not source-enforced for every input. The refined gate is therefore INCONCLUSIVE, and the original gate stays FAIL.

## Frozen identity and text scope

Fields2Cover HEAD `{head}`, clean source worktree. Production adapter SHA-256 `{m['adapter_sha256']}`; original execution binary `{m['original_binary_sha256']}`; linked Fields2Cover library `{m['linked_library_sha256']}`. Original audit and A3 follow-up hashes agree with their manifests. The latest JESTECH Section 2.2, Proposition 1, Table 1 and S7 text are still unavailable locally: **JESTECH_TEXT_ALIGNMENT=UNVERIFIED**. The accessible Biosystems Engineering manuscript is related material, not an authenticated substitute. This report diagnoses the frozen operational definitions only.

## Complete fixed-path call chain

`s7_source_callchain.csv` gives absolute paths, functions, line ranges, calls, branch conditions, object flow, length geometry and unverified risks. In brief: the production adapter reads metric WKT, makes 3m + 3m headlands, generates fixed-angle BruteForce swaths and obtains `SwathLength`; `genRoute` builds coverage/shortest graphs and transforms solver node IDs to Route groups; `Route::addSwath(s,g)` makes a new connection before each later swath; `planPath` appends each connection and each swath; `DubinsCurves::createSimpleTurn` produces steering samples; `steerStatesToPath` uses successive-sample chord lengths; `Path::appendSwath` uses successive swath-vertex distances; `Path::operator+=` appends without geometric checks; `PathLength::computeCost` inherits `PPObjective::computeCost`, which returns the sum of `fabs(PathState.len)`. The adapter returns that positive finite total as `complete_path_length_m`.

The `PathPlanning::planPath(swaths)` branch that calls `turn_path.discretize(0.1)` requires a group with more than one swath. It is **source-proven excluded for this exact adapter path**: `transformSolutionToRoute` only calls `Route::addSwath(swath, shortest_graph)`; on a nonempty route this calls `addConnection`, and `Route::addSwath(swath)` then opens a new group because the connection count exceeds the old group count. The adapter never calls another Route mutator. The six observations independently have one swath per group. Thus `Path::populate/reduce`, reached through same-group `discretize`, do not explain these observations. They remain relevant to other callers that construct a Route differently.

## A3-STRICT versus charged sampled polyline

The 48,085 previously recorded 1e-6m strict gaps are all TURN→TURN. In the fixed source, `steerStatesToPath` stores each steering sample's position and tangent heading but sets `len` to the distance to the next sample; `PathState::atEnd()` moves along the heading by `len`. The reconstructed endpoint can therefore miss the next point on a curve. The original strict A3 result remains FAIL.

For the charged-polyline audit, a nonworking state represents the ordered edge from its `point` to the **next final PathState's `point`**, including zero-length terminal states at subturn boundaries. Every one of the {sample_counts['nonwork_states']:,} observed nonworking states belongs to exactly one of {sample_counts['connectors']} required connector ranges. Every connector starts and ends at the neighbouring swath endpoints within {SPACE_TOL:g}m (maximum observed endpoint error {max_endpoint:.3g}m). For every state, `fabs(len)` matches that next-sample chord within the original S7 numeric comparison tolerance (absolute {LENGTH_ABS_TOL:g}m plus relative {LENGTH_REL_TOL:g}); maximum individual residual {max_res:.3g}m, maximum connector total residual {max_connector_total:.3g}m. All {sample_counts['zero_states']} zero-length nonworking states have zero next-sample displacement. No observed nonworking segment is unpaid or assigned to two connectors. All observed PathDirection values are +1; {sample_counts['reverse_swaths']} route swaths reverse their **geometric vertex order**, which `appendSwath` still charges forward. Vehicle backward motion remains unobserved.

The interpretation is conditional: the source computes turn `len` before `TurningBase::correctPath` may move the first or last sample by up to 0.05m without recomputing `len`; and `createTurn` can return an empty Path when it has at most one state. Neither can be dismissed by calling `Path::length`. These branches are listed in `s7_branch_coverage.csv` with their actual source reachability and runtime evidence.

## Why the endpoint MST is a relaxation

The sidecar `agri_f2c_mst_probe.cpp:102-148` flattens **all generated swaths**, creates a complete graph with one vertex per swath, and assigns edge weight `w(i,j)` as the minimum of the four Euclidean endpoint-pair distances. Prim's algorithm adds the least reachable edge until all vertices are used; for `n≤1` its connection bound is zero. It adds this MST to the same generated swath length used by LB0. Independent reconstruction from the six serialized generated-swath lists matches the frozen LB1 within {max_mst_res:.3g}m.

Suppose each mandatory swath occurs in the charged path and the distinct required connections form a connected swath-visitation walk. For a connection from endpoint `p` of swath `i` to endpoint `q` of `j`, `w(i,j)≤||p−q||`. If its charged sampled-polyline length is the sum of all consecutive sample chords and samples start at `p` and end at `q`, the triangle inequality gives `||p−q||≤charged_length`. A connected walk contains a spanning tree, so `MST≤sum(required connector charges)`. The complete graph and minimum over all endpoint pairs impose **weaker**, not stronger, constraints than the realised route; depot or extra nonworking costs are not needed in the MST and can only add to J when nonnegative. With A1, A2 and A4, `LB0≤LB1≤J`. This mathematical mapping is valid for the stated predicates, independent of route optimality. It is not a source proof that every returned finite plan satisfies those predicates.

In the three observed multi-swath cases, each connector's charged state length exceeds its endpoint straight-line distance; the smallest connector surplus is 2.995825883m. All six frozen LB0/LB1 values agree with the independently reconstructed generated swaths and satisfy `LB0≤LB1≤J`; the smallest multi-swath `J−LB1` is {min_margin:.9f}m. The finite orientation domain permits an admissible bound-based stop **only if each unevaluated candidate's bound is valid and execution failures remain unresolved as specified**. Numerical success on these six does not prove that premise for the other 127 S7 keys or for all possible inputs.

## Proof obligations and branches

`s7_proof_obligation_matrix.csv` separates mathematical predicates, source support, runtime evidence and the remaining gap. `s7_branch_coverage.csv` uses `SOURCE_PROVEN_EXCLUDED`, `SOURCE_SUPPORTED`, `RUNTIME_VERIFIED` and `UNRESOLVED`. The important unresolved conditions are: the route conversion matches swaths by endpoint coordinates and takes the first match without asserting a one-to-one generated-swath mapping; `TurningBase::createTurn` may return empty; endpoint correction may alter charged chords; positive finite J is checked without a full coordinate, coverage or connection audit. Those are **source-level proof gaps**, not observed planner failures. No new candidate was selected to force a PASS; no planner was rerun.

## Scientific closure and minimal text changes

**A sentence-only replacement of A3 does not close Proposition 1 for the pinned implementation.** The mathematical proposition can be stated with a charged-polyline A3 condition, but the implementation-wide claim still needs a checked one-to-one swath mapping, a charged connector for every required adjacency, endpoint and per-edge charge validation after `correctPath`, and complete handling of empty/nonfinite paths. The 127 unrun S7 cases and latest JESTECH text also remain open. Without those checks or a source proof, the correct manuscript scope is conditional, not an unconditional guarantee about this implementation.

Suggested sentence-level wording for later author review (no Word file edited):

1. Replace the strict A3 sentence with: “For each valid finite plan to which the bound is applied, every generated working swath is included in one connected ordered traversal, and each required inter-swath connection is represented by an ordered sequence of sampled points whose first and last points coincide with the corresponding swath endpoints; the charged nonworking length of that connection is no less than the sum of Euclidean distances between consecutive samples.”
2. Add immediately after it: “The fixed implementation's `PathState::atEnd()` need not equal the next state's stored point at every Dubins sample; any implementation claim based on sampled-point connectivity requires explicit verification of swath inclusion, connector endpoints, charged chord lengths and absence of uncharged jumps for the evaluated candidate.”
3. Qualify the Proposition 1 implementation sentence as: “Under A1, A2, the charged-sampled-polyline form of A3, and A4 for every candidate on the predefined finite orientation domain, the endpoint-minimum complete-graph MST is an admissible connection lower bound; candidates with unresolved planning outcomes are not certified by this statement.”

These are **proposed conditions**, not claims already verified for all runs. They do not change the scientific method or retroactively pass the original strict A3 audit.
'''
    (OUT/'S7_POLYLINE_IMPLEMENTATION_CLOSURE.md').write_text(report,encoding='utf-8')
    unresolved='''# S7 unresolved implementation obligations

1. **A1 global identity:** `transformSolutionToRoute` matches the first swath with a matching endpoint pair and has no unique generated-swath ID or multiset assertion. Prove one-to-one correspondence for all frozen candidate inputs, or instrument every bound-eligible full evaluation.
2. **A2 connector existence:** `createTurn` can return an empty Path. Demonstrate that this occurs only for coincident endpoints with no required travel, or reject those candidate plans.
3. **A3 charged polyline after correction:** `correctPath` may move sampled endpoints by up to 0.05m without recomputing adjacent `len`. Prove the resulting charged length still bounds the sampled connector geometry, or check each returned connector edge at runtime and apply an explicit safe policy for any residual.
4. **A4 complete ledger:** Positive finite total length does not assert that all swaths and required connectors were included exactly once. Establish a per-state disjoint ledger for every candidate used in a certificate.
5. **Exceptional states and directions:** Verify or safely reject empty/nonfinite paths, degenerate swaths, duplicate endpoints, illegal direction values and any backward vehicle motion. The observed zero-length terminal states were safe; they do not close all such branches.
6. **Candidate coverage:** Only six of 133 predeclared keys ran in S7, and only three had multiple swaths. The remaining 127 cannot be labelled passing from source plausibility or these six results.
7. **Paper alignment:** Latest JESTECH Proposition 1, Table 1 and S7 are unavailable locally. Compare exact wording against the conditional predicates before publication.
8. **Certificate failure policy:** Confirm that unresolved planner outcomes are never treated as model infeasibility or silently pruned under a bound that has not been validated for that candidate.

The complete-graph endpoint MST relaxation itself matches the six frozen bound records and is mathematically optimistic under the predicates above. The missing step is an implementation-wide proof or runtime certificate of those predicates.
'''
    (OUT/'s7_unresolved_obligations.md').write_text(unresolved,encoding='utf-8')

    after={path:sha(pathlib.Path(path)) for path in previous}
    assert previous==after
    assert sha(ROOT/'runner/src/agri_f2c_runner.cpp')==m['adapter_sha256']
    assert sha(BIN)==m['original_binary_sha256'] and sha(LIB)==m['linked_library_sha256']
    assert subprocess.check_output(['git','-C',str(F2C),'rev-parse','HEAD'],text=True).strip()==head
    produced=['S7_POLYLINE_IMPLEMENTATION_CLOSURE.md','s7_source_callchain.csv',
              's7_proof_obligation_matrix.csv','s7_branch_coverage.csv',
              's7_polyline_case_checks.csv','s7_unresolved_obligations.md','build_closure.py']
    manifest=dict(created_asia_shanghai=now,f2c_head=head,
                  adapter_sha256=m['adapter_sha256'],binary_sha256=m['original_binary_sha256'],
                  linked_library_sha256=m['linked_library_sha256'],
                  first_s7_gate='FAIL',strict_a3='FAIL',polyline_observed='PASS_44_OF_44',
                  refined_gate='INCONCLUSIVE',planner_replays=0,
                  all_frozen_files_unchanged=previous==after,
                  frozen_hashes_before=previous,frozen_hashes_after=after,
                  tolerance=dict(spatial_absolute_m=SPACE_TOL,length_absolute_m=LENGTH_ABS_TOL,
                                 length_relative=LENGTH_REL_TOL),
                  observed=dict(cases=len(obs),multiswath_cases=len(multi),**sample_counts),
                  output_sha256={n:sha(OUT/n) for n in produced})
    (OUT/'s7_polyline_evidence_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'cases':len(obs),'connectors':sample_counts['connectors'],
                      'polyline_pass':sample_counts['polyline_pass'],
                      'same_group':'EXCLUDED','MST_mapping':'PASS',
                      'refined_gate':'INCONCLUSIVE','frozen_unchanged':True}))

if __name__=='__main__':
    main()
