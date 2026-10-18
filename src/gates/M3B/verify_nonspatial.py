"""Independent output-level checks, using counters/dicts and original preserved cells."""
from pathlib import Path
from collections import defaultdict
import json,hashlib
import pandas as pd
from build_nonspatial import ROOT, INP, AK, MONTHS, MAIN, HELD, SNAP, EVENTS, atomic

def r(p): return pd.read_csv(p,dtype=str,keep_default_na=False)
checks={}
roster=r(INP/'M2/fixed_segment_roster.csv')
detail=r(INP/'M1/segment_hour_detail.csv.gz')
lookup={tuple(getattr(x,k) for k in AK):x.segment_id for x in roster.itertuples()}
primary=set(roster.loc[roster.is_diagnostic43.eq('True'),'segment_id'])
independent=defaultdict(set); valid=set();native=set()
for row in detail.itertuples():
    sid=lookup[tuple(getattr(row,k) for k in AK)]
    independent[(row.month,row.departure_node,row.arrival_node)].add(row.route_id)
    valid.add((row.month,sid))
    native.add((row.month,sid,row.departure_sequence,row.arrival_sequence))
c=r(ROOT/'monthly_route_concentration.csv')
assert len(c)==len(MONTHS)*758 and not c.duplicated(['month','segment_id']).any()
for row in c.itertuples():
    assert row.frozen_master_snapshot==SNAP[row.month]
    assert row.frozen_master_snapshot<=row.month+'01'
    if (row.month,row.segment_id) in valid:
        routes=independent[(row.month,row.departure_node,row.arrival_node)]
        assert int(row.shared_route_count)==len(routes)
        assert json.loads(row.shared_route_ids)==sorted(routes)
        assert row.core_evaluable=='True' and row.count_status=='READY'
    else:
        assert row.shared_route_count=='' and row.shared_route_ids==''
        assert row.core_evaluable=='False'
    if row.month in HELD:
        assert row.count_status=='held_date'
checks['monthly_counts_all9096_rows_and_nulls']='PASS'
checks['held_months_not_zero_and_no_future_master']='PASS'

g=r(ROOT/'frozen_ridership_quality_groups.csv')
expectedB={'A0202','A0203','A0204','A0581'};expectedC={'A0073','A0074','A0626','A0693'}
assert set(g[g.ridership_quality_group.eq('B_repeated_stop')].segment_id)==expectedB
assert set(g[g.ridership_quality_group.eq('C_sequence_token_mismatch')].segment_id)==expectedC
assert len(g)==43 and set(g.segment_id)==primary
clean=r(ROOT/'ridership_clean35_hourly.csv')
raw=r(INP/'M3A/ridership_source_rows_for_primary.csv').set_index('source_row',verify_integrity=True)
assert len(clean)==840 and clean.segment_id.nunique()==35
source_cells=0
for row in clean.itertuples():
    assert row.segment_id not in expectedB|expectedC
    h='00' if row.hour=='0' else row.hour
    for endpoint in ['departure','arrival']:
        src=raw.loc[getattr(row,endpoint+'_candidate_source_row')]
        assert src['표준버스정류장ID']==getattr(row,endpoint+'_node')
        assert src.embedded_sequence_normalized==getattr(row,endpoint+'_sequence')
        for action,kr in [('boarding','승차'),('alighting','하차')]:
            assert float(getattr(row,endpoint+'_'+action+'_events'))==float(src[h+'시'+kr+'총승객수'])
            source_cells+=1
assert source_cells==3360
checks['fixed_35_4_4_groups']='PASS'
checks['all3360_clean_values_equal_original_cells']='PASS'

cond=r(ROOT/'ridership_conditional8_audit.csv')
assert set(cond.segment_id)==expectedB|expectedC
assert len(cond)==696 and cond.candidate_selected_for_Main.eq('False').all()
for row in cond.itertuples():
    src=raw.loc[row.candidate_source_row]
    assert src['역명']==row.source_station_label
    assert src.embedded_sequence_token==row.source_sequence_token_raw
    assert src['표준버스정류장ID']==row.source_NODE_ID==row.expected_node
    assert src[row.source_boarding_column]==row.raw_boarding_events
    assert src[row.source_alighting_column]==row.raw_alighting_events
# Every original candidate ID is retained for each native combination, endpoint and hour.
old=r(INP/'M3A/ridership_match_audit.csv')
for x in old[old.segment_id.isin(expectedB|expectedC)].itertuples():
    for ep in ['departure','arrival']:
        q=cond[cond.segment_id.eq(x.segment_id)&cond.departure_sequence.eq(x.departure_sequence)&cond.arrival_sequence.eq(x.arrival_sequence)&cond.hour.eq(x.hour)&cond.endpoint_role.eq(ep)]
        assert set(q.candidate_source_row)==set(map(str,json.loads(getattr(x,ep+'_source_rows_json'))))
checks['all_conditional_source_candidates_and_tokens_preserved']='PASS'

ctx=r(ROOT/'diagnostic43_june_context.csv')
hp=r(INP/'M2/segment_hour_monthly_panel.csv.gz')
hp=hp[hp.month.eq('202606')&hp.segment_id.isin(primary)]
comp=ctx.merge(hp,on=['month','segment_id','hour'],suffixes=('_out','_old'),validate='one_to_one')
for a,b in [('M2_June_U_sec','U_hour_sec'),('M2_June_U_percentile','U_hour_percentile'),('M2_June_high_instability_flag','high_instability_hour'),('M2_hour_valid','valid')]:
    assert comp[a].eq(comp[b]).all()
assert len(ctx)==1032 and ctx.M2_hour_valid.eq('True').sum()==815
assert ctx[ctx.segment_id.isin(expectedB|expectedC)][EVENTS].eq('').all().all()
assert ctx[EVENTS].ne('').all(axis=1).sum()==840
assert (ctx.main_ridership_cell_allowed.eq('True')&ctx.M2_hour_valid.eq('True')).sum()==664
cl=clean.set_index(['segment_id','hour'])
for row in ctx[ctx.main_ridership_cell_allowed.eq('True')].itertuples():
    src=cl.loc[(row.segment_id,row.hour)]
    for e in EVENTS: assert float(getattr(row,e))==float(src[e])
assert ctx.causal_variable_certified.eq('False').all()
checks['all_M2_values_flags_and_missing_hours_unchanged']='PASS'
checks['no_B_C_values_in_Main_context']='PASS'

path=r(ROOT/'route_path_join_keys.csv')
assert len(path)==9111 and not path.route_path_join_key.duplicated().any()
assert set(path[path.departure_sequence.ne('')][['month','segment_id','departure_sequence','arrival_sequence']].itertuples(index=False,name=None))==native
assert path.path_match_status.eq('held_geometry').all()
assert path.automatic_historical_backcast_allowed.eq('False').all()
for col in ['path_route_id','departure_anchor_point_order','arrival_anchor_point_order','departure_anchor_offset_m','arrival_anchor_offset_m']:
    assert path[col].eq('').all()
assert path[path.month.isin(HELD)].departure_sequence.eq('').all()
jm=r(INP/'M3A/june_route_stop_master.csv.gz')
masterset=set(jm[['ROUTE_ID','NODE_ID','순번']].itertuples(index=False,name=None))
june=path[path.month.eq('202606')&path.departure_sequence.ne('')]
for row in june.itertuples():
    assert (row.route_id,row.departure_node,row.departure_sequence) in masterset
    assert (row.route_id,row.arrival_node,row.arrival_sequence) in masterset
assert len(june)==679 and june.is_diagnostic43.eq('True').sum()==44
checks['path_keys_all5691_native_keys_and_June_master']='PASS'
checks['geometry_not_fabricated_or_backcast']='PASS'

manifest=json.loads((ROOT/'source_manifest.json').read_text())
for source in manifest['sources']:
    assert hashlib.sha256((ROOT/source['path']).read_bytes()).hexdigest()==source['sha256']
for name,digest in manifest['outputs'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
checks['all_input_and_output_hashes']='PASS'
for p in ROOT.iterdir():
    if p.suffix in ['.md','.py']:
        assert chr(183) not in p.read_text(encoding='utf-8'),p.name
out={'overall':'PASS','checks':checks,'verified_original_ridership_cells':source_cells,'Main_ridership_and_M2_joint_valid_hours':664,'limitations':['monthly_all_daytypes_vs_ordinary_weekdays','hour_interval_definition_unconfirmed','8_conditional_segments_held','all_spatial_paths_held']}
atomic(ROOT/'independent_verification.json',(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps(out,ensure_ascii=False,indent=2))
