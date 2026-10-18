"""Independent CSV-level checks against immutable M1/M2/M3B source outputs."""
from collections import defaultdict
from fractions import Fraction
import hashlib,json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from analyze_evidence import ROOT,INP,MAIN,AK,EVENTS,atomic

def r(p):return pd.read_csv(p,dtype=str,keep_default_na=False)
checks={}
roster=r(INP/'M2/fixed_segment_roster.csv');primary=roster[roster.is_diagnostic43.eq('True')]
q=r(ROOT/'analysis_input_monthly.csv');q['u']=pd.to_numeric(q.U_sec);q['count']=pd.to_numeric(q.shared_route_count)
assert len(q)==4999 and set(q.month)==set(MAIN)
assert len(roster)==758 and len(primary)==43
assert hashlib.sha256((INP/'M1/dong_max_recurrence_route_segments.csv').read_bytes()).hexdigest()=='ba14af3923db5afcba165e873b3a7ae3c7c627950007b5ed483d98e4c860264f'
old=r(INP/'M1/route_segment_monthly_instability.csv').merge(roster[['segment_id']+AK],on=AK,validate='many_to_one')
count=r(INP/'M3B/monthly_route_concentration.csv')
old=old[old.month.isin(MAIN)&old.U_sec.ne('')].merge(count[['month','segment_id','shared_route_count']],on=['month','segment_id'],validate='one_to_one')
assert len(old)==len(q)
for x in q.merge(old[['month','segment_id','U_sec','shared_route_count','high_instability_month']],on=['month','segment_id'],suffixes=('_new','_old'),validate='one_to_one').itertuples():
    assert float(x.U_sec_new)==float(x.U_sec_old)
    assert int(x.shared_route_count_new)==int(x.shared_route_count_old)
    assert x.high_instability_month_new==x.high_instability_month_old
assoc=r(ROOT/'monthly_route_concentration_association.csv')
for x in assoc.itertuples():
    g=q[q.month.eq(x.month)]
    result=spearmanr(g['count'],g.u).statistic # p-value deliberately unused.
    assert np.isclose(float(x.spearman_shared_routes_U),result,atol=1e-14)
    assert int(x.n_observations)==len(g)
checks['Main4999_source_U_count_flags_unchanged_and_rho_independent']='PASS'

levels=r(ROOT/'route_count_level_summary.csv')
for x in levels.itertuples():
    gg=q[q.month.eq(x.month)] if x.scope=='monthly' else q
    g=gg[gg['count'].eq(int(x.shared_route_count))]
    assert len(g)==int(x.n_observations)
    values=np.asarray(sorted(g.u),dtype=float)
    for val,z in [('U_P25_sec',.25),('U_median_sec',.50),('U_P75_sec',.75)]:
        assert np.isclose(float(getattr(x,val)),np.quantile(values,z,method='linear'))
    assert int(x.high_flag_n)==g.high_instability_month.eq('True').sum()
    assert float(x.high_flag_proportion)==int(x.high_flag_n)/len(g)
assert levels[levels.scope.eq('all_Main_pooled')].n_observations.astype(int).sum()==4999
checks['exact_integer_levels_n_quantiles_and_flag_denominators']='PASS'

allcmp=r(INP/'M2/stop_pair_hourly_comparison.csv')
allcmp=allcmp[allcmp.month.isin(MAIN)&allcmp.comparison_scope.eq('Main')]
bykey=defaultdict(dict)
for x in allcmp.itertuples():
    key=(x.month,x.dong_code,x.departure_node,x.arrival_node,x.hour)
    assert x.route_id not in bykey[key]
    bykey[key][x.route_id]=x.high_instability_hour_A=='True'
expected=defaultdict(lambda:defaultdict(int))
for x in allcmp[allcmp.segment_id.isin(primary.segment_id)].itertuples():
    z=expected[x.segment_id];z['all_valid_A_B_comparisons']+=1
    key=(x.month,x.dong_code,x.departure_node,x.arrival_node,x.hour)
    routes=bykey[key];ah=x.high_instability_hour_A=='True';bh=x.high_instability_hour_B=='True'
    assert len(routes)==int(x.n_routes)
    if len(routes)==1:
        z['single_route_comparisons_excluded']+=1;continue
    z['multi_route_comparisons']+=1
    z['A_high_valid_multi_comparisons']+=ah
    z['both_high']+=ah and bh
    z['A_only_high']+=ah and not bh
    z['B_only_high']+=not ah and bh
    z['neither_high']+=not ah and not bh
    other=any(v for k,v in routes.items() if k!=x.route_id)
    z['A_high_with_other_route_high']+=ah and other
    z['A_high_without_other_route_high']+=ah and not other
    z['both_high_without_other_route_high']+=ah and bh and not other
    z['A_only_high_without_other_route_high']+=ah and not bh and not other
    z['A_only_high_with_other_route_high']+=ah and not bh and other
sup=r(ROOT/'diagnostic43_pair_support.csv')
assert len(sup)==43 and set(sup.segment_id)==set(primary.segment_id)
for x in sup.itertuples():
    z=expected[x.segment_id]
    for col,v in z.items():assert int(getattr(x,col))==v,(x.segment_id,col,v)
    assert int(x.both_high)+int(x.A_only_high)==int(x.A_high_valid_multi_comparisons)
    if int(x.A_high_valid_multi_comparisons):assert float(x.pair_support_rate)==int(x.both_high)/int(x.A_high_valid_multi_comparisons)
    else:assert x.pair_support_rate==''
assert sum(x['both_high'] for x in expected.values())==2084
assert sum(x['A_only_high'] for x in expected.values())==304
assert sum(x['single_route_comparisons_excluded'] for x in expected.values())==2892
checks['all43_support_counts_hour_specific_multi_and_B_self_inclusion']='PASS'

matrix=r(ROOT/'diagnostic43_evidence_matrix.csv');short=r(ROOT/'case_validation_shortlist.csv')
assert len(matrix)==43 and not matrix.segment_id.duplicated().any()
assert set(map(tuple,matrix[AK].to_numpy()))==set(map(tuple,primary[AK].to_numpy()))
pattern=r(INP/'M2/diagnostic43_pattern_summary.csv')
cols=['evaluated_hours','hour_R_max','hour_R_max_hours','E_max_weekday_hour_counts','P90_max_weekday_hour_counts','weekday_months_min','weekday_months_max','weekday_positive_dates_min','weekday_positive_dates_max']
ch=matrix.merge(pattern[['segment_id']+cols],on='segment_id',suffixes=('_new','_old'),validate='one_to_one')
for c in cols:assert ch[c+'_new'].eq(ch[c+'_old']).all()
assert matrix.geometry_status.eq('held_geometry').all()
for c in ['road_speed_status','intersection_status','bus_lane_status']:assert matrix[c].eq('held_geometry').all()
assert matrix.cause_type_assigned.eq('False').all() and matrix.policy_priority_assigned.eq('False').all()
clean=r(INP/'M3B/ridership_clean35_hourly.csv')
rid=r(ROOT/'june_ridership_context35.csv')
assert len(rid)==35 and rid.context_name.eq('2026년 6월 승하차 이벤트 맥락').all()
for x in rid.itertuples():
    h=clean[clean.segment_id.eq(x.segment_id)]
    assert len(h)==24 and set(h.hour)==set(map(str,range(24)))
    for c in EVENTS:
        total=sum(int(v) for v in h[c])
        assert int(getattr(x,c+'_monthly_total'))==total
        assert int(matrix.set_index('segment_id').loc[x.segment_id,c+'_monthly_total'])==total
held=matrix[~matrix.ridership_quality_group.eq('A_single_row_token_agrees')]
assert len(held)==8 and held[[c+'_monthly_total' for c in EVENTS]].eq('').all().all()
checks['matrix_original43_M2_pattern_and_four35_ridership_totals']='PASS'
checks['conditional8_totals_NA_and_all_geometry_held']='PASS'

mem=r(ROOT/'case_validation_criterion_membership.csv')
expected_reasons=defaultdict(set)
for crit,col,func in [('shared_routes_max','shared_route_count_Main_median',max),('shared_routes_min','shared_route_count_Main_median',min),('max_R_hours_widest','R_h_max_hour_count',max),('max_R_hours_narrowest','R_h_max_hour_count',min)]:
    vals={x.segment_id:float(getattr(x,col)) for x in matrix.itertuples()};v=func(vals.values())
    ids={sid for sid,val in vals.items() if val==v}
    assert ids==set(mem[mem.criterion.eq(crit)].segment_id)
    for sid in ids:expected_reasons[sid].add(crit)
fractions={x.segment_id:Fraction(int(x.both_high),int(x.A_high_valid_multi_comparisons)) for x in matrix.itertuples() if int(x.A_high_valid_multi_comparisons)>0}
for crit,func in [('pair_support_max',max),('pair_support_min',min)]:
    v=func(fractions.values());ids={sid for sid,f in fractions.items() if f==v}
    assert ids==set(mem[mem.criterion.eq(crit)].segment_id)
    for sid in ids:expected_reasons[sid].add(crit)
assert set(short.segment_id)==set(expected_reasons) and len(short)==27
for x in short.itertuples():
    assert set(x.selection_criteria.split(';'))==expected_reasons[x.segment_id]
    assert int(x.selection_criterion_count)==len(expected_reasons[x.segment_id])
checks['six_extremes_all_ties_and_duplicate_reasons_preserved']='PASS'
manifest=json.loads((ROOT/'source_manifest.json').read_text())
for item in manifest['sources']:
    assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256']
assert hashlib.sha256((ROOT/'Gate3M3C_rule_record.md').read_bytes()).hexdigest()==manifest['rule_record_sha256']
checks['input_hashes_and_precalculation_rule_record']='PASS'
for f in ROOT.iterdir():
    if f.suffix in ['.md','.py']:assert chr(183) not in f.read_text(),f.name
result={'overall':'PASS','checks':checks,'scope':'frozen 8 Main months; fixed43 and fixed758','causal_claims_supported':False,'new_cutoffs_created':False}
atomic(ROOT/'verification_results.json',(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps(result,ensure_ascii=False,indent=2))
