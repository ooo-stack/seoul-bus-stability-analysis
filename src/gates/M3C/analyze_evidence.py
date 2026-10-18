"""Gate3M3C, frozen-output descriptive diagnostics only. No raw Core rebuild."""
from pathlib import Path
from fractions import Fraction
import json,hashlib,os
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
# Submission adapter: paths only; the original calculation statements follow.
from seoul_bus_paths import bind as _submission_bind
globals().update(_submission_bind('M3C'))
INP=ROOT/'inputs'
MAIN=['202509','202510','202601','202602','202603','202604','202605','202606']
AK=['dong_code','route_id','departure_node','arrival_node']
BK=['month','dong_code','departure_node','arrival_node','hour']
EVENTS=['departure_boarding_events','departure_alighting_events','arrival_boarding_events','arrival_alighting_events']

def atomic(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name('.'+path.name+'.tmp')
    with tmp.open('wb') as f: f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
def save(x,name): atomic(ROOT/name,x.to_csv(index=False,na_rep='',lineterminator='\n').encode('utf-8-sig'))
def dump(x,name): atomic(ROOT/name,(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def read(g,n): return pd.read_csv(INP/g/n,dtype=str,keep_default_na=False)
def number(s): return pd.to_numeric(s,errors='coerce')
def rho(x,y): return float(x.rank(method='average').corr(y.rank(method='average')))
def sorted_display(x): return x.sort_values('diagnostic_no',key=number)

def build():
    r=read('M2','fixed_segment_roster.csv');p=r[r.is_diagnostic43.eq('True')].copy()
    assert len(r)==758 and len(p)==43 and not r.duplicated(AK).any()
    old43=read('M1','dong_max_recurrence_route_segments.csv')
    assert set(map(tuple,old43[AK].to_numpy()))==set(map(tuple,p[AK].to_numpy()))
    counts=read('M3B','monthly_route_concentration.csv')
    monthly=read('M1','route_segment_monthly_instability.csv')
    monthly=monthly.merge(r[['segment_id']+AK],on=AK,validate='many_to_one')
    q=monthly[monthly.month.isin(MAIN)].merge(counts[['month','segment_id','shared_route_count','shared_route_ids','count_status']],on=['month','segment_id'],validate='one_to_one')
    q['U_sec']=number(q.U_sec);q['shared_route_count']=number(q.shared_route_count)
    assert q.U_sec.notna().eq(q.shared_route_count.notna()).all()
    q=q[q.U_sec.notna()&q.shared_route_count.notna()].copy()
    q['shared_route_count']=q.shared_route_count.astype(int)
    assert len(q)==4999 and q.count_status.eq('READY').all()
    assert q.high_instability_month.isin(['True','False']).all()
    save(q,'analysis_input_monthly.csv')
    assoc=[]
    for m,g in q.groupby('month',sort=True):
        assoc.append({'month':m,'scope':'Main_fixed758_evaluated_route_segment_month','n_observations':len(g),'n_unique_directed_stop_pairs':g[['departure_node','arrival_node']].drop_duplicates().shape[0],'shared_route_count_min':int(g.shared_route_count.min()),'shared_route_count_max':int(g.shared_route_count.max()),'spearman_shared_routes_U':rho(g.shared_route_count,g.U_sec),'U_unit':'초','shared_routes_unit':'개 노선','january_QA_month':m=='202601','independent_observations_assumed':False,'interpretation':'descriptive association, not a traffic or causal effect'})
    assoc=pd.DataFrame(assoc);save(assoc,'monthly_route_concentration_association.csv')
    levels=[]
    for scope,m,g0 in [('monthly',m,g) for m,g in q.groupby('month',sort=True)]+[('all_Main_pooled','all_Main',q)]:
        for k,g in g0.groupby('shared_route_count',sort=True):
            flags=g.high_instability_month.isin(['True','False'])
            levels.append({'scope':scope,'month':m,'shared_route_count':int(k),'n_observations':len(g),'n_unique_route_segments':g.segment_id.nunique(),'n_contributing_months':g.month.nunique(),'U_median_sec':float(g.U_sec.median()),'U_P25_sec':float(g.U_sec.quantile(.25,interpolation='linear')),'U_P75_sec':float(g.U_sec.quantile(.75,interpolation='linear')),'high_flag_valid_n':int(flags.sum()),'high_flag_n':int(g.high_instability_month.eq('True').sum()),'high_flag_proportion':float(g.loc[flags,'high_instability_month'].eq('True').mean()),'flag_source':'existing_M1_monthly_high_instability_flag','weighting':'one stored route-segment-month per observation; pooled row is not equal-month weighting','small_n_merged':False})
    save(pd.DataFrame(levels),'route_count_level_summary.csv')

    # Existing all-background A/B comparisons, including A in B. No new B or flags.
    cmp=read('M2','stop_pair_hourly_comparison.csv')
    cmp=cmp[cmp.month.isin(MAIN)&cmp.comparison_scope.eq('Main')].copy()
    assert not cmp.duplicated(['month','segment_id','hour']).any()
    assert cmp.valid.eq('True').all()
    assert cmp.high_instability_hour_A.isin(['True','False']).all()
    assert cmp.high_instability_hour_B.isin(['True','False']).all()
    group=cmp.groupby(BK,sort=False).agg(actual_route_n=('route_id','nunique'),actual_high_n=('high_instability_hour_A',lambda s:int(s.eq('True').sum()))).reset_index()
    cmp=cmp.merge(group,on=BK,validate='many_to_one')
    assert np.array_equal(number(cmp.n_routes).to_numpy(),cmp.actual_route_n.to_numpy())
    cmp['A_high']=cmp.high_instability_hour_A.eq('True')
    cmp['B_high']=cmp.high_instability_hour_B.eq('True')
    cmp['other_valid_route_n']=cmp.actual_route_n-1
    cmp['other_high_route_n']=cmp.actual_high_n-cmp.A_high.astype(int)
    cmp['multi_route_same_month_hour']=cmp.actual_route_n.ge(2)
    cc=cmp[cmp.segment_id.isin(p.segment_id)].copy()
    assert len(cc)==6069
    cc['support_comparison_eligible']=cc.multi_route_same_month_hour
    cc['both_high']=cc.A_high&cc.B_high
    cc['A_only_high']=cc.A_high&~cc.B_high
    cc['any_other_route_high']=cc.other_high_route_n.gt(0)
    cc['B_includes_focal_A']=True
    save(cc,'pair_support_comparison_cells.csv')
    support=[]
    for x in p.itertuples():
        a=cc[cc.segment_id.eq(x.segment_id)];g=a[a.support_comparison_eligible]
        ah=g[g.A_high];both=int(ah.B_high.sum());only=len(ah)-both
        support.append({'segment_id':x.segment_id,'diagnostic_no':x.diagnostic_no,'dong_code':x.dong_code,'dong_name':x.dong_name,'route_id':x.route_id,'route_name':x.route_name,'departure_node':x.departure_node,'arrival_node':x.arrival_node,'departure_name':x.departure_name,'arrival_name':x.arrival_name,'all_valid_A_B_comparisons':len(a),'single_route_comparisons_excluded':int((~a.multi_route_same_month_hour).sum()),'multi_route_comparisons':len(g),'multi_route_comparison_months':g.month.nunique(),'has_multi_route_comparison':len(g)>0,'A_high_valid_multi_comparisons':len(ah),'both_high':both,'A_only_high':only,'pair_support_rate':both/len(ah) if len(ah) else np.nan,'B_only_high':int((~g.A_high&g.B_high).sum()),'neither_high':int((~g.A_high&~g.B_high).sum()),'A_high_with_other_route_high':int(ah.any_other_route_high.sum()),'A_high_without_other_route_high':int((~ah.any_other_route_high).sum()),'both_high_without_other_route_high':int((ah.B_high&~ah.any_other_route_high).sum()),'A_only_high_without_other_route_high':int((~ah.B_high&~ah.any_other_route_high).sum()),'A_only_high_with_other_route_high':int((~ah.B_high&ah.any_other_route_high).sum()),'pair_support_status':'evaluated_multi_route_A_high' if len(ah) else 'NA_no_A_high_multi_route_comparison' if len(g) else 'NA_no_multi_route_comparison','B_includes_focal_A':True,'evidence_caveat':'B contains A; inspect other-route flag counts; no independent or physical-road causal interpretation'})
    support=pd.DataFrame(support);save(sorted_display(support),'diagnostic43_pair_support.csv')
    assert support.both_high.sum()==2084 and support.A_only_high.sum()==304
    assert support.multi_route_comparisons.sum()==3177 and support.single_route_comparisons_excluded.sum()==2892

    # A35 ridership: four separate totals, sum only with all 24 labels present.
    clean=read('M3B','ridership_clean35_hourly.csv')
    quality=read('M3B','frozen_ridership_quality_groups.csv')
    assert len(clean)==840 and clean.segment_id.nunique()==35
    rid=[]
    for sid,g in clean.groupby('segment_id',sort=True):
        assert len(g)==24 and set(number(g.hour))==set(range(24))
        row={'segment_id':sid,'month':'202606','context_name':'2026년 6월 승하차 이벤트 맥락','ridership_quality_group':'A_single_row_token_agrees','n_hour_labels':24,'value_unit':'월 승차 또는 하차 이벤트(건)','date_scope':'calendar_month_all_daytypes','hour_definition_status':'official_hour_boundaries_unconfirmed; no hourly U association','aggregation':'sum each of four endpoint/action series separately over all24 labels','unique_passenger_count':False}
        for e in EVENTS:
            v=number(g[e]);assert v.notna().all() and np.equal(v,np.floor(v)).all()
            row[e+'_monthly_total']=int(v.sum())
        rid.append(row)
    rid=pd.DataFrame(rid).merge(p[['segment_id','diagnostic_no']+AK+['dong_name','route_name','departure_name','arrival_name']],on='segment_id',validate='one_to_one')
    save(sorted_display(rid),'june_ridership_context35.csv')

    # One evidence row per fixed43; original M2 technical summaries retained.
    evidence=p.copy().rename(columns={'V':'Main_V','K':'Main_K','R':'Main_R'})
    stats=q[q.segment_id.isin(p.segment_id)].groupby('segment_id').agg(shared_route_count_valid_months=('month','nunique'),shared_route_count_Main_median=('shared_route_count','median'),shared_route_count_Main_min=('shared_route_count','min'),shared_route_count_Main_max=('shared_route_count','max')).reset_index()
    evidence=evidence.merge(stats,on='segment_id',validate='one_to_one')
    evidence['has_multi_route_any_Main_month']=evidence.shared_route_count_Main_max.ge(2)
    count_by_month={sid:json.dumps(dict(zip(g.month,g.shared_route_count.astype(int))),ensure_ascii=False) for sid,g in q[q.segment_id.isin(p.segment_id)].groupby('segment_id')}
    evidence['shared_route_count_by_Main_month']=evidence.segment_id.map(count_by_month)
    pscols=[c for c in support if c not in set(AK+['diagnostic_no','dong_name','route_name','departure_name','arrival_name'])]
    evidence=evidence.merge(support[pscols],on='segment_id',validate='one_to_one')
    patt=read('M2','diagnostic43_pattern_summary.csv')
    pats=[c for c in patt if c not in set(AK+['diagnostic_no','is_diagnostic43','dong_name','route_name','departure_name','arrival_name'])]
    evidence=evidence.merge(patt[pats],on='segment_id',validate='one_to_one')
    hs=read('M2','segment_hour_summary.csv')
    evidence=evidence.merge(hs[['segment_id','R_h_max_hour_count','R_h_max_K_V','hourly_K_V_all','max_hours_noJan']],on='segment_id',validate='one_to_one')
    hr=read('M2','segment_hour_recurrence.csv');hr['R_h']=number(hr.R_h)
    hmedian=hr.groupby('segment_id').R_h.median()
    evidence['hour_R_median']=evidence.segment_id.map(hmedian)
    ampm=read('M2','AM_PM_common_month_comparison.csv')
    amrows=[]
    for sid,g in ampm.groupby('segment_id'):
        dr=number(g.PM_R_minus_AM_R);du=number(g.PM_U_minus_AM_U_sec)
        amrows.append({'segment_id':sid,'AM_PM_common_timepair_n':len(g),'AM_PM_common_month_min':int(number(g.common_month_count).min()),'AM_PM_common_month_max':int(number(g.common_month_count).max()),'PM_R_higher_timepairs':int((dr>0).sum()),'AM_R_higher_timepairs':int((dr<0).sum()),'AM_PM_R_equal_timepairs':int((dr==0).sum()),'PM_U_higher_timepairs':int((du>0).sum()),'AM_U_higher_timepairs':int((du<0).sum()),'AM_PM_U_equal_timepairs':int((du==0).sum()),'AM_PM_comparison_scope':'same-segment 3AM x3PM hour pairs on common months; not independent segments'})
    evidence=evidence.merge(pd.DataFrame(amrows),on='segment_id',validate='one_to_one')
    evidence=evidence.merge(quality[['segment_id','ridership_quality_group']],on='segment_id',validate='one_to_one')
    ridcols=['segment_id','context_name','n_hour_labels']+[e+'_monthly_total' for e in EVENTS]
    evidence=evidence.merge(rid[ridcols],on='segment_id',how='left',validate='one_to_one')
    evidence['ridership_context_name']='2026년 6월 승하차 이벤트 맥락'
    evidence['ridership_Main_status']=np.where(evidence.ridership_quality_group.eq('A_single_row_token_agrees'),'A35_monthly_context_available','held_B_C; four_totals_NA')
    for c in [e+'_monthly_total' for e in EVENTS]: evidence[c]=evidence[c].astype('Int64')
    for c in ['geometry_status','road_speed_status','intersection_status','bus_lane_status']:evidence[c]='held_geometry'
    evidence['cause_type_assigned']=False
    evidence['policy_priority_assigned']=False
    evidence['technical_evidence_note']=[f"복수노선 A 고불안정 비교 {int(x.A_high_valid_multi_comparisons)}건, B 동시 {int(x.both_high)}건, A만/B미만 {int(x.A_only_high)}건. 실제 다른 노선 flag 동시 {int(x.A_high_with_other_route_high)}건, 동시 없음 {int(x.A_high_without_other_route_high)}건. B는 A를 포함하며 원인유형은 미확정." if x.A_high_valid_multi_comparisons else f"복수노선 유효 비교 {int(x.multi_route_comparisons)}건, A 고불안정 분모 0으로 pair_support NA. 단일노선 일치는 공통환경 증거에 넣지 않음." for x in evidence.itertuples()]
    evidence=sorted_display(evidence)
    assert len(evidence)==43 and not evidence.segment_id.duplicated().any()
    save(evidence,'diagnostic43_evidence_matrix.csv')

    # Six transparent extreme criteria, all ties, exact rational comparison for support.
    criteria=[]
    for key,label,col,func in [('shared_routes_max','Main 공유노선 수 중앙값 최대','shared_route_count_Main_median','max'),('shared_routes_min','Main 공유노선 수 중앙값 최소','shared_route_count_Main_median','min'),('max_R_hours_widest','최고 R 동률 시간대 개수 최대','R_h_max_hour_count','max'),('max_R_hours_narrowest','최고 R 동률 시간대 개수 최소','R_h_max_hour_count','min')]:
        vals=number(evidence[col]);v=getattr(vals,func)()
        for sid in evidence.loc[vals.eq(v),'segment_id']:criteria.append({'segment_id':sid,'criterion':key,'criterion_label':label,'criterion_field':col,'criterion_value':float(v)})
    elig=evidence[evidence.A_high_valid_multi_comparisons.gt(0)]
    fractions={x.segment_id:Fraction(int(x.both_high),int(x.A_high_valid_multi_comparisons)) for x in elig.itertuples()}
    for key,label,fn in [('pair_support_max','복수노선 pair_support_rate 최대',max),('pair_support_min','복수노선 pair_support_rate 최소',min)]:
        v=fn(fractions.values())
        for sid,f in fractions.items():
            if f==v:criteria.append({'segment_id':sid,'criterion':key,'criterion_label':label,'criterion_field':'pair_support_rate','criterion_value':float(v)})
    membership=pd.DataFrame(criteria).merge(evidence,on='segment_id',validate='many_to_one')
    save(sorted_display(membership),'case_validation_criterion_membership.csv')
    reasons=pd.DataFrame([{'segment_id':sid,'selection_criterion_count':len(g),'selection_criteria':';'.join(g.criterion),'selection_reasons':';'.join(g.criterion_label),'selection_values_json':json.dumps(dict(zip(g.criterion,g.criterion_value)),ensure_ascii=False)} for sid,g in pd.DataFrame(criteria).groupby('segment_id')])
    shortlist=evidence.merge(reasons,on='segment_id',how='inner',validate='one_to_one')
    shortlist['list_name']='사례검토 후보';shortlist['policy_priority']=False
    save(sorted_display(shortlist),'case_validation_shortlist.csv')
    summary={'Main_months':MAIN,'association':{'median':float(assoc.spearman_shared_routes_U.median()),'min':float(assoc.spearman_shared_routes_U.min()),'max':float(assoc.spearman_shared_routes_U.max()),'positive_months':int(assoc.spearman_shared_routes_U.gt(0).sum()),'negative_months':int(assoc.spearman_shared_routes_U.lt(0).sum()),'evaluated_segment_months':len(q)},'pair_support':{'all_valid_comparisons':len(cc),'multi_comparisons':int(support.multi_route_comparisons.sum()),'single_excluded':int(support.single_route_comparisons_excluded.sum()),'A_high_multi':int(support.A_high_valid_multi_comparisons.sum()),'both_high':int(support.both_high.sum()),'A_only_high':int(support.A_only_high.sum()),'pooled_rate':float(support.both_high.sum()/support.A_high_valid_multi_comparisons.sum()),'eligible_segments':len(elig),'no_multi_comparison_segments':int(support.multi_route_comparisons.eq(0).sum()),'segment_rate_median':float(support.pair_support_rate.median()),'segment_rate_min':float(support.pair_support_rate.min()),'segment_rate_max':float(support.pair_support_rate.max()),'A_high_with_other_high':int(support.A_high_with_other_route_high.sum()),'A_high_without_other_high':int(support.A_high_without_other_route_high.sum()),'both_high_without_other_high':int(support.both_high_without_other_route_high.sum()),'A_only_without_other_high':int(support.A_only_high_without_other_route_high.sum())},'case_selection':{'criterion_memberships':len(membership),'unique_segments':len(shortlist),'criterion_counts':membership.criterion.value_counts().to_dict()},'fixed43':43,'background758':758,'ridership_clean35':35,'ridership_held8':8,'geometry_all_held':True,'new_cutoffs_or_cause_types':False}
    dump(summary,'analysis_summary.json')
    sources=[{'path':f.relative_to(ROOT).as_posix(),'size_bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(INP.rglob('*')) if f.is_file()]
    dump({'gate':'3-M3C','current_reports':{'M3B':'private-reference-redacted','path_QA':'private-reference-redacted','M2':'private-reference-redacted'},'sources':sources,'rule_record_sha256':hashlib.sha256((ROOT/'Gate3M3C_rule_record.md').read_bytes()).hexdigest(),'new_external_data_used':False,'raw_Core_rebuilt':False},'source_manifest.json')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print(assoc.to_string(index=False))
    print(shortlist[['segment_id','dong_name','route_name','shared_route_count_Main_median','pair_support_rate','both_high','A_only_high','R_h_max_hour_count','selection_criteria']].to_string(index=False))

if __name__=='__main__':build()
