from common import *
import zipfile
b=units();primary=b[b.is_diagnostic43];p=read(OUT/'segment_hour_monthly_panel.csv.gz');r=read(OUT/'segment_hour_recurrence.csv');assert len(r)==758*24 and len(p)==758*24*12
assert set(r.segment_id)==set(b.segment_id);assert r[r.is_diagnostic43].segment_id.nunique()==43
assert p[p.month.isin(HELD)].U_hour_sec.isna().all();assert r.loc[r.V_h.eq(0),'R_h'].isna().all();assert r.K_h.le(r.V_h).all();assert r.K_h_noJan.le(r.V_h_noJan).all()
# Independent aggregation of stored monthly records.
for ms,suf in [(MAIN,''),([m for m in MAIN if m!='202601'],'_noJan')]:
 v=p[p.month.isin(ms)&p.valid];vv=v.groupby(['segment_id','hour']).size();kk=v.groupby(['segment_id','hour']).high_instability_hour.sum();uu=v.groupby(['segment_id','hour']).U_hour_sec.median();ri=r.set_index(['segment_id','hour']);assert np.array_equal(ri['V_h'+suf].to_numpy(),vv.reindex(ri.index,fill_value=0).to_numpy());assert np.array_equal(ri['K_h'+suf].to_numpy(),kk.reindex(ri.index,fill_value=0).to_numpy());assert np.allclose(ri['U_median_h_sec'+suf],uu.reindex(ri.index),equal_nan=True,atol=1e-10)
orig=read(M/'route_segment_hour_folded.csv.gz').merge(b[['segment_id']+AK],on=AK,how='inner',validate='many_to_one');good=p[p.valid].merge(orig,on=['segment_id','month','hour'],validate='one_to_one',suffixes=('_export','_source'));assert len(good)==len(orig)
for c in ['U_hour_sec','U_hour_percentile']:assert np.allclose(good[c+'_export'],good[c+'_source'],atol=1e-10,rtol=1e-12)
qa=read(OUT/'daily_panel_QA.csv');assert not qa.duplicated(['month']+SK+['hour']).any()
checks={c:bool(qa[c].all()) for c in ['source_hash_and_dates_match','positive_days_match','weekly_days_match','P50_match','P90_match','U_match']};assert all(checks.values())
q=pd.concat([read(OUT/'daily_checkpoints'/(m+'_panel.csv.gz')) for m in MAIN],ignore_index=True);assert not q.duplicated(['month','date']+SK+['hour']).any();v=q[q.valid]
assert np.allclose(v.E_sec,v.T_sec-v.P50_sec,atol=1e-10,rtol=1e-12);assert np.array_equal(v.P90_reached.to_numpy(),v.T_sec.ge(v.P90_sec).astype(float).to_numpy());assert v.T_sec.gt(0).all();assert v.date.astype(str).str[:6].eq(v.month).all();assert v.weekday.between(0,4).all()
# Full native weekday reconstruction, independently from daily exports.
n=read(OUT/'weekday_available_native_cells.csv');key=['month','segment_id','departure_sequence','arrival_sequence','hour','weekday'];z=v.groupby(key).agg(n=('date','size'),E=('E_sec','median'),P=('P90_reached','mean')).reset_index();ch=n[n.n_positive.gt(0)].merge(z,on=key,validate='one_to_one');assert len(ch)==len(z);assert np.array_equal(ch.n_positive,ch.n);assert np.allclose(ch.e_median_sec,ch.E,atol=1e-10,rtol=1e-12);assert np.allclose(ch.p90_reach_rate,ch.P,atol=1e-12)
s=read(OUT/'diagnostic43_weekday_heatmap_data.csv');assert len(s)==43*24*5;assert s.assign(contributing_months=s.contributing_months.fillna('')).groupby(['segment_id','hour']).contributing_months.nunique().eq(1).all()
nm=read(OUT/'weekday_common_support_monthly.csv')
# Independently build equal-month final values for all Main cells.
for ms,suf in [(MAIN,''),([m for m in MAIN if m!='202601'],'_noJan')]:
 x=nm[nm.month.isin(ms)];e=x.groupby(['segment_id','hour','weekday']).E_median_seq_sec.median();pp=x.groupby(['segment_id','hour','weekday']).P90_mean_seq_rate.mean();nn=x.groupby(['segment_id','hour','weekday']).size();si=s.set_index(['segment_id','hour','weekday']);assert np.allclose(si['E_weekday_sec'+suf],e.reindex(si.index),equal_nan=True,atol=1e-10,rtol=1e-12);assert np.allclose(si['P90_reach_rate_equal_month'+suf],pp.reindex(si.index),equal_nan=True,atol=1e-12);assert np.array_equal(si['contributing_month_count'+suf],nn.reindex(si.index,fill_value=0))
# Native common support rules recomputed from observations, without group-level cutoff.
ns=n.groupby(['month','segment_id','departure_sequence','arrival_sequence','hour']).n_positive.min();assert np.array_equal(n.set_index(['month','segment_id','departure_sequence','arrival_sequence','hour']).all_five_weekdays_supported.to_numpy(),ns.gt(0).reindex(n.set_index(['month','segment_id','departure_sequence','arrival_sequence','hour']).index).to_numpy())
comp=read(OUT/'stop_pair_hourly_comparison.csv');assert np.allclose(comp.U_A_minus_B_sec,comp.U_hour_sec_A-comp.U_hour_sec_B,atol=1e-10,rtol=1e-12);assert np.array_equal(comp.flag_agrees,comp.high_instability_hour_A.eq(comp.high_instability_hour_B))
# Shared-pair folding uses every background route: independently recount medians and membership.
bh=read(OUT/'stop_pair_hour_monthly.csv.gz');z=orig.groupby(['month']+BK+['hour']).U_hour_sec.median().rename('check_U').reset_index();ch=bh.merge(z,on=['month']+BK+['hour'],validate='one_to_one');assert len(ch)==len(bh);assert np.allclose(ch.U_hour_sec,ch.check_U,atol=1e-10,rtol=1e-12)
for path in OUT.rglob('*.csv.gz'):gzip.decompress(path.read_bytes())
result={'status':'PASS','diagnostic_roster_43_unchanged':True,'background_758_unchanged':True,'M1_hour_values_and_flags_preserved':True,'held_months_NA':True,'Main_August_separate':True,'daily_QA_cells':len(qa),'daily_QA_checks':checks,'weekday_common_support_and_month_weighting_independently_verified':True,'A_B_all_background_routes_used':True,'new_cutoffs':False,'new_cause_or_policy_claims':False}
dump(result,'verification_results.json');print(json.dumps(result,ensure_ascii=False),flush=True)
