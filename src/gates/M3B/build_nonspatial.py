"""Gate 3-M3B: deterministic joins of frozen Core outputs and audited source cells.
Run with the bundled Python: python build_nonspatial.py
No raw travel-time rebuilding, ranking, correlation or causal estimation.
"""
from pathlib import Path
import hashlib, io, json, os, gzip, zipfile
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
# Submission adapter: paths only; the original calculation statements follow.
from seoul_bus_paths import bind as _submission_bind
globals().update(_submission_bind('M3B'))
INP = ROOT / 'inputs'
AK = ['dong_code','route_id','departure_node','arrival_node']
PAIR = ['month','departure_node','arrival_node']
MAIN = ['202509','202510','202601','202602','202603','202604','202605','202606']
MONTHS = ['202509','202510','202511','202512','202601','202602','202603','202604','202605','202606','202607','202608']
HELD = ['202511','202512','202607']
SNAP = dict(zip(MONTHS,['20250901','20250901','20251002','20251103','20251209','20260108','20260226','20260305','20260402','20260506','20260701','20260701']))
EVENTS = ['departure_boarding_events','departure_alighting_events','arrival_boarding_events','arrival_alighting_events']

def atomic(path, payload):
    path = Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp = path.with_name('.'+path.name+'.tmp')
    with tmp.open('wb') as f:
        f.write(payload); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,path)

def read(gate,name):
    return pd.read_csv(INP/gate/name,dtype=str,keep_default_na=False)

def save(df,name):
    atomic(ROOT/name,df.to_csv(index=False,lineterminator='\n',na_rep='').encode('utf-8-sig'))

def dump(x,name):
    atomic(ROOT/name,(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def b(x): return x.eq('True')
def role(m): return 'Main_replication' if m in MAIN else 'auxiliary_design_month' if m=='202608' else 'held_date'

def build():
    roster=read('M2','fixed_segment_roster.csv')
    assert len(roster)==758 and not roster.segment_id.duplicated().any() and not roster.duplicated(AK).any()
    primary=roster[b(roster.is_diagnostic43)].copy()
    assert len(primary)==43
    status=read('M3A','segment_environment_match_status.csv')
    assert set(status.segment_id)==set(primary.segment_id) and not status.segment_id.duplicated().any()
    qa={}
    oldmanifest=json.loads((INP/'M3A/source_manifest.json').read_text())
    source_hashes=[]
    for p in sorted(INP.rglob('*')):
        if p.is_file():
            source_hashes.append({'path':p.relative_to(ROOT).as_posix(),'size_bytes':p.stat().st_size,'sha256':sha(p)})
            if p.parent.name=='M3A' and p.name in oldmanifest['outputs']:
                assert sha(p)==oldmanifest['outputs'][p.name],p.name
    assert sha(INP/'M1/dong_max_recurrence_route_segments.csv')=='ba14af3923db5afcba165e873b3a7ae3c7c627950007b5ed483d98e4c860264f'
    assert sha(INP/'M2/fixed_segment_roster.csv')=='ee907ec0bd93a572226b621fa139cd38a9043cf54d95ef355e83245a8c8b64eb'
    qa['source_hashes_and_fixed_rosters']='PASS'

    # Frozen quality assignment depends only on M3A structural status.
    repeated=(pd.to_numeric(status.ridership_departure_records)>1)|(pd.to_numeric(status.ridership_arrival_records)>1)
    agreeing=b(status.ridership_all_native_tokens_agree)
    status['ridership_quality_group']=np.where(repeated,'B_repeated_stop',np.where(agreeing,'A_single_row_token_agrees','C_sequence_token_mismatch'))
    assert status.ridership_quality_group.value_counts().to_dict()=={'A_single_row_token_agrees':35,'B_repeated_stop':4,'C_sequence_token_mismatch':4}
    groups=status[['segment_id','diagnostic_no']+AK+['dong_name','route_name','departure_name','arrival_name','ridership_quality_group','ridership_departure_records','ridership_arrival_records','ridership_all_native_tokens_agree','ridership_native_sequence_status']].copy()
    groups['main_ridership_cell_allowed']=groups.ridership_quality_group.eq('A_single_row_token_agrees')
    groups['assignment_source']='M3A fixed structural audit; no event values used'
    groups=groups.sort_values('diagnostic_no',key=lambda s:pd.to_numeric(s))
    save(groups,'frozen_ridership_quality_groups.csv')

    # Rebuild sharing counts from valid stored A-month keys, never from 43 alone.
    detail=read('M1','segment_hour_detail.csv.gz').merge(roster[['segment_id']+AK],on=AK,how='inner',validate='many_to_one')
    assert len(detail)==104353 and detail.strict_spatial_core.eq('True').all()
    units=detail[['month','segment_id']+AK].drop_duplicates()
    pairrows=[]
    for key,q in units.groupby(PAIR,sort=True):
        routes=sorted(q.route_id.unique().tolist())
        pairrows.append(dict(zip(PAIR,key),shared_route_count=len(routes),shared_route_ids=json.dumps(routes)))
    pairs=pd.DataFrame(pairrows)
    assert not pairs.duplicated(PAIR).any()
    # Independent stored B contributor union must agree with every count and ID list.
    bp=read('M2','stop_pair_hour_monthly.csv.gz')
    for key,q in bp.groupby(PAIR,sort=False):
        routes=set()
        for s in q.contributing_route_ids: routes.update(s.split('|') if '|' in s else s.split(','))
        routes.discard('')
        found=pairs.set_index(PAIR).loc[key]
        assert sorted(routes)==json.loads(found.shared_route_ids),(key,routes,found.shared_route_ids)
    assert len(bp.groupby(PAIR))==len(pairs)
    grid=pd.DataFrame({'month':MONTHS}).merge(roster,how='cross')
    grid['month_role']=grid.month.map(role)
    grid['frozen_master_snapshot']=grid.month.map(SNAP)
    grid=grid.merge(units[['month','segment_id']].assign(core_evaluable=True),on=['month','segment_id'],how='left',validate='one_to_one')
    grid['core_evaluable']=grid.core_evaluable.eq(True)
    # A count is published only for an evaluated unit-month, matching M3A's scope.
    valid=units.merge(pairs,on=PAIR,validate='many_to_one')
    grid=grid.merge(valid[['month','segment_id','shared_route_count','shared_route_ids']],on=['month','segment_id'],how='left',validate='one_to_one')
    grid['shared_route_count']=grid.shared_route_count.astype('Int64')
    grid['count_status']=np.where(grid.month.isin(HELD),'held_date',np.where(grid.core_evaluable,'READY','NA_no_stored_Strict_Core_unit_month'))
    grid['count_label']='정류장쌍 공유노선 수'
    grid['count_unit']='개 노선'
    grid['count_population']='fixed758; valid stored Strict Core; unique ROUTE_ID per directed NODE pair and month; union across valid hours'
    old=read('M3A','route_concentration_readiness.csv')
    chk=grid[grid.core_evaluable].merge(old[['month','segment_id','background_core_shared_unique_routes','background_route_ids','master_adjacent_Main_route_count_June','master_route_ids_June']],on=['month','segment_id'],validate='one_to_one')
    assert len(chk)==5676
    assert np.array_equal(chk.shared_route_count.to_numpy(dtype=int),pd.to_numeric(chk.background_core_shared_unique_routes).to_numpy(dtype=int))
    assert all(json.loads(a)==json.loads(c) for a,c in zip(chk.shared_route_ids,chk.background_route_ids))
    grid=grid.merge(old[['month','segment_id','master_adjacent_Main_route_count_June','master_route_ids_June']],on=['month','segment_id'],how='left',validate='one_to_one')
    grid['master_adjacent_Main_route_count_June']=pd.to_numeric(grid.master_adjacent_Main_route_count_June,errors='coerce').astype('Int64')
    grid['master_count_scope']='202606 only: inherited frozen20260506 Main adjacent-pair count; other months NA, not recomputed'
    assert len(grid)==9096 and grid[grid.month.isin(HELD)].shared_route_count.isna().all()
    save(grid.sort_values(['month','segment_id']),'monthly_route_concentration.csv')
    qa['route_counts_match_M3A_and_independent_M2_B']='PASS'

    # Exact source-cell reuse. No ridership row aggregation or choice in B/C.
    audit=read('M3A','ridership_match_audit.csv')
    raw=read('M3A','ridership_source_rows_for_primary.csv')
    rawidx=raw.set_index('source_row',verify_integrity=True)
    audit=audit.merge(groups[['segment_id','ridership_quality_group']],on='segment_id',validate='many_to_one')
    clean=audit[audit.ridership_quality_group.eq('A_single_row_token_agrees')].copy()
    assert len(clean)==840 and clean.segment_id.nunique()==35
    assert not clean.duplicated(['segment_id','hour']).any()
    for row in clean.itertuples():
        h=int(row.hour)
        for endpoint in ['departure','arrival']:
            assert getattr(row,endpoint+'_raw_records')=='1'
            assert getattr(row,endpoint+'_sequence_candidates')=='1'
            src=rawidx.loc[getattr(row,endpoint+'_candidate_source_row')]
            assert src.route_id==row.route_id and src['노선번호']==row.frozen_route_number
            assert src['표준버스정류장ID']==getattr(row,endpoint+'_node')
            assert src.embedded_sequence_normalized==getattr(row,endpoint+'_sequence')
            for action,kr in [('boarding','승차'),('alighting','하차')]:
                col=('00' if h==0 else str(h))+'시'+kr+'총승객수'
                field=endpoint+'_'+action+'_events'
                assert float(getattr(row,field))==float(src[col])==float(getattr(row,field+'_sequence_candidate'))
    clean['ridership_clock_label']=clean.hour.map(lambda h:f'{int(h):02d}시')
    clean['hour_join_status']='assumed_numeric_clock_label_correspondence; official_interval_and_service_day_definition_unconfirmed'
    clean['temporal_scope_status']='monthly_all_daytypes_events; M2_U_uses_ordinary_weekdays; context_only'
    clean['causal_variable_certified']=False
    clean['ridership_source_file']='2026년_버스노선별_정류장별_시간대별_승하차_인원_정보(06월).csv'
    save(clean.sort_values(['diagnostic_no','hour'],key=lambda s:pd.to_numeric(s)),'ridership_clean35_hourly.csv')

    condrows=[]; usedids=set()
    conditional=audit[~audit.ridership_quality_group.eq('A_single_row_token_agrees')]
    for row in conditional.itertuples():
        h=int(row.hour)
        for endpoint in ['departure','arrival']:
            ids=json.loads(getattr(row,endpoint+'_source_rows_json'))
            for srcid in ids:
                src=rawidx.loc[str(srcid)];usedids.add(str(srcid))
                boardcol=('00' if h==0 else str(h))+'시승차총승객수'
                alightcol=('00' if h==0 else str(h))+'시하차총승객수'
                condrows.append({'month':row.month,'frozen_master_snapshot':row.snapshot,'segment_id':row.segment_id,'diagnostic_no':row.diagnostic_no,'dong_name':row.dong_name,'route_id':row.route_id,'frozen_route_number':row.frozen_route_number,'departure_node':row.departure_node,'arrival_node':row.arrival_node,'departure_sequence':row.departure_sequence,'arrival_sequence':row.arrival_sequence,'hour':h,'ridership_quality_group':row.ridership_quality_group,'endpoint_role':endpoint,'expected_node':getattr(row,endpoint+'_node'),'expected_sequence':getattr(row,endpoint+'_sequence'),'endpoint_raw_records':getattr(row,endpoint+'_raw_records'),'candidate_source_row':str(srcid),'source_route_number':src['노선번호'],'source_NODE_ID':src['표준버스정류장ID'],'source_ARS_ID':src['버스정류장ARS번호'],'source_station_label':src['역명'],'source_sequence_token_raw':src.embedded_sequence_token,'source_sequence_token_normalized':src.embedded_sequence_normalized,'token_equals_frozen_sequence':src.embedded_sequence_normalized==getattr(row,endpoint+'_sequence'),'source_boarding_column':boardcol,'source_alighting_column':alightcol,'raw_boarding_events':src[boardcol],'raw_alighting_events':src[alightcol],'source_registration_date':src['등록일자'],'candidate_selected_for_Main':False,'hold_reason':'repeated_stop_occurrence_and_unconfirmed_token_definition' if row.ridership_quality_group=='B_repeated_stop' else 'single_row_token_differs_from_frozen_Core_sequence','use_status':'held_ridership; preserve all rows without aggregation'})
    cond=pd.DataFrame(condrows)
    assert cond.segment_id.nunique()==8 and (~cond.candidate_selected_for_Main).all()
    save(cond.sort_values(['diagnostic_no','departure_sequence','hour','endpoint_role','candidate_source_row']),'ridership_conditional8_audit.csv')
    save(raw[raw.source_row.isin(usedids)],'ridership_conditional8_source_rows.csv')
    qa['clean35_all_four_values_equal_original_single_cells']='PASS'
    qa['conditional8_all_endpoint_candidates_preserved_unselected']='PASS'

    # Retain the exact stored M2 U, percentile and nullable flag, including absent cells.
    hp=read('M2','segment_hour_monthly_panel.csv.gz')
    june=hp[(hp.month=='202606')&b(hp.is_diagnostic43)].copy()
    assert len(june)==1032 and b(june.valid).sum()==815
    june=june.rename(columns={'U_hour_sec':'M2_June_U_sec','U_hour_percentile':'M2_June_U_percentile','high_instability_hour':'M2_June_high_instability_flag','valid':'M2_hour_valid'})
    june=june.merge(groups[['segment_id','ridership_quality_group','main_ridership_cell_allowed']],on='segment_id',validate='many_to_one')
    cc=grid[grid.month=='202606'][['segment_id','frozen_master_snapshot','shared_route_count','shared_route_ids','master_adjacent_Main_route_count_June','master_route_ids_June']]
    june=june.merge(cc,on='segment_id',validate='many_to_one')
    valuecols=EVENTS+['departure_sequence','arrival_sequence','departure_candidate_source_row','arrival_candidate_source_row','departure_raw_sequence_tokens_json','arrival_raw_sequence_tokens_json','hour_join_status','temporal_scope_status']
    june=june.merge(clean[['segment_id','hour']+valuecols],on=['segment_id','hour'],how='left',validate='one_to_one')
    for col in EVENTS: june[col]=pd.to_numeric(june[col],errors='coerce').astype('Int64')
    june['ridership_value_unit']='2026년6월 월 총 시간대별 승차 또는 하차 이벤트(건)'
    june['sharing_value_unit']='개 노선; 해당 월 유효 Core 시간대 합집합'
    june['ridership_join_status']=np.where(june.main_ridership_cell_allowed,'linked_A35_monthly_context_only','held_B_or_C; see conditional8 audit')
    june['hour_label_alignment']='assumed_numeric_00_to_23; official_interval_unconfirmed'
    june['causal_variable_certified']=False
    assert june.loc[~june.main_ridership_cell_allowed,EVENTS].isna().all().all()
    assert june.loc[b(june.M2_hour_valid),'M2_June_high_instability_flag'].isin(['True','False']).all()
    assert june.loc[~b(june.M2_hour_valid),'M2_June_high_instability_flag'].eq('').all()
    assert june[EVENTS].notna().all(axis=1).sum()==840
    save(june.sort_values(['diagnostic_no','hour'],key=lambda s:pd.to_numeric(s)),'diagnostic43_june_context.csv')
    qa['June_panel_exact_M2_values_and_NA_preserved']='PASS'

    # Native sequence keys are retained per month, not borrowed across months.
    nk=['month','segment_id','route_id','departure_node','arrival_node','departure_sequence','arrival_sequence','snapshot','route_name','departure_name','arrival_name','route_type']
    native=detail[nk].drop_duplicates()
    assert len(native)==5691 and not native.duplicated(['month','segment_id','departure_sequence','arrival_sequence']).any()
    native=native.rename(columns={'snapshot':'Core_snapshot','route_name':'frozen_route_number','departure_name':'frozen_departure_name','arrival_name':'frozen_arrival_name','route_type':'frozen_route_type'})
    keys=grid.drop(columns=['shared_route_ids','master_route_ids_June','count_population','master_count_scope']).merge(native.drop(columns=['route_id','departure_node','arrival_node']),on=['month','segment_id'],how='left',validate='one_to_many')
    assert keys.loc[keys.Core_snapshot.notna(),'Core_snapshot'].eq(keys.loc[keys.Core_snapshot.notna(),'frozen_master_snapshot']).all()
    coords=read('M3A','historical_segment_endpoint_registry.csv.gz')
    coordcols=['month','segment_id','coordinate_ready']+[c for c in coords if c.startswith(('departure_','arrival_')) and c not in ['departure_node','arrival_node']]
    keys=keys.merge(coords[coordcols],on=['month','segment_id'],how='left',validate='many_to_one')
    keys['native_key_status']=np.where(keys.month.isin(HELD),'held_date_no_sequence_borrowing',np.where(keys.departure_sequence.notna(),'stored_Core_native_key','NA_no_stored_Core_native_sequence'))
    keys['route_path_join_key']=keys.month+':'+keys.segment_id+':'+keys.departure_sequence.fillna('NA')+':'+keys.arrival_sequence.fillna('NA')
    assert not keys.route_path_join_key.duplicated().any()
    master=read('M3A','june_route_stop_master.csv.gz')
    mi=set(master[['ROUTE_ID','NODE_ID','순번']].itertuples(index=False,name=None))
    keys['historical_master_exact_key_QA']='inherited_Core_rule; not_reaudited_in_M3B'
    keys.loc[keys.month.isin(HELD),'historical_master_exact_key_QA']='held_date'
    keys.loc[keys.departure_sequence.isna()&~keys.month.isin(HELD),'historical_master_exact_key_QA']='NA_no_native_key'
    june_keys=keys[(keys.month=='202606')&keys.departure_sequence.notna()]
    for row in june_keys.itertuples():
        assert (row.route_id,row.departure_node,row.departure_sequence) in mi
        assert (row.route_id,row.arrival_node,row.arrival_sequence) in mi
    keys.loc[june_keys.index,'historical_master_exact_key_QA']='PASS_both_ROUTE_NODE_sequence_in_frozen20260506'
    for col in ['path_source_id','path_file_sha256','path_reference_date','path_valid_from','path_valid_to','path_CRS','path_route_id','departure_anchor_point_order','arrival_anchor_point_order','departure_anchor_along_path','arrival_anchor_along_path','departure_anchor_offset_m','arrival_anchor_offset_m','path_direction_QA','stop_order_QA','temporal_applicability_QA','anchor_occurrence_QA','geometry_review_evidence','geometry_reviewer']:
        keys[col]=''
    keys['path_match_status']='held_geometry'
    keys['path_status_reason']='official versioned route-path and verified stop-occurrence anchors not supplied'
    keys['automatic_historical_backcast_allowed']=False
    keys['coordinate_reference']='inherited F0M selected coordinates; x5186/y5186 EPSG:5186; no new spatial assignment'
    save(keys.sort_values(['month','segment_id','departure_sequence']),'route_path_join_keys.csv')
    qa['path_native_sequence_keys_and_June679_exact_master_matches']='PASS'
    qa['all_geometry_still_held_no_fabricated_path_or_anchor']='PASS'

    summary=[]
    for m in MONTHS:
        g=grid[grid.month.eq(m)];p=g[b(g.is_diagnostic43)];j=june if m=='202606' else None
        summary.append({'month':m,'role':role(m),'snapshot':SNAP[m],'background_roster':758,'background_evaluated':int(g.core_evaluable.sum()),'diagnostic_roster':43,'diagnostic_evaluated':int(p.core_evaluable.sum()),'count_nonmissing':int(g.shared_route_count.notna().sum()),'count_status':'held_date' if m in HELD else 'READY_for_evaluated_Core_units'})
    monthly=pd.DataFrame(summary);save(monthly,'monthly_build_coverage.csv')
    results={'gate':'3-M3B','status':'PASS_nonspatial_build; spatial_path_held','fixed_background':758,'fixed_diagnostic':43,'quality_groups':{'A':35,'B':4,'C':4},'monthly_grid_rows':len(grid),'evaluated_unit_month_rows':len(chk),'monthly_directed_pairs':len(pairs),'clean35_hour_rows':len(clean),'clean35_nonmissing_four_value_rows':int(june[EVENTS].notna().all(axis=1).sum()),'clean35_joint_M2_valid_hours':int((june.main_ridership_cell_allowed&b(june.M2_hour_valid)).sum()),'diagnostic_June_hour_rows':len(june),'diagnostic_June_valid_U_hours':int(b(june.M2_hour_valid).sum()),'conditional8_native_sequence_combinations':len(conditional[['segment_id','departure_sequence','arrival_sequence']].drop_duplicates()),'conditional8_candidate_endpoint_hour_rows':len(cond),'conditional8_preserved_original_rows':len(usedids),'path_join_rows':len(keys),'observed_native_keys':len(native),'June_native_keys_exact_master_checked':len(june_keys),'verified_geometry_rows':0,'new_U_C2_or_rank_computation':False,'correlation_or_causal_estimation':False,'checks':qa}
    dump(results,'verification_results.json')
    dump({'gate':'3-M3B','source_reports_current_ids':['private-reference-redacted','private-reference-redacted'],'package_library_ids':{'M3A':'private-reference-redacted','M2':'private-reference-redacted','M1':'private-reference-redacted'},'sources':source_hashes,'raw_ridership_original_sha256':'0adb483b12cd31351e386625b88a2dba1485dd8d6e4b64b27289b4c03f1fe0d2','definitions':{'sharing_count':'count distinct route_id within fixed758 valid stored month Core, per ordered NODE pair, all valid hours union','Main_months':MAIN,'auxiliary_months':['202608'],'held_months':HELD,'frozen_snapshots':SNAP,'ridership_clock_mapping':'assumed label match; interval unconfirmed','no_new_external_data':True},'outputs':{p.name:sha(p) for p in ROOT.glob('*.csv')}},'source_manifest.json')
    print(json.dumps(results,ensure_ascii=False,indent=2))
    print(monthly.to_string(index=False))

if __name__=='__main__': build()
