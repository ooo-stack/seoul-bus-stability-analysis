from common import *
primary=units().query('is_diagnostic43').sort_values('diagnostic_no');q=pd.concat([read(OUT/'daily_checkpoints'/(m+'_panel.csv.gz')) for m in MAIN],ignore_index=True)
assert set(q.segment_id)==set(primary.segment_id);q['date']=q.date.astype(str)
q['native_id']=q.segment_id+'|'+q.departure_sequence+'|'+q.arrival_sequence
NG=['month','segment_id','native_id','departure_sequence','arrival_sequence','hour'];native=[]
for key,g in q.groupby(NG+['weekday'],sort=False):
 v=g[g.valid];row=dict(zip(NG+['weekday'],key));n=len(v)
 row.update({'n_planned_weekday':len(g),'n_common_weekday':int(g.common_planned.sum()),'n_positive':n,'n_unique_positive_dates':v.date.nunique(),'n_date_not_common':int(g.status_reason.eq('date_not_common_planned').sum()),'n_missing_key':int(g.status_reason.eq('key_absent').sum()),'n_zero':int(g.status_reason.eq('time_zero').sum()),'n_missing_value':int(g.status_reason.eq('value_missing').sum()),'n_conflict':int(g.status_reason.eq('conflict_pending').sum()),'n_held_QA':int(g.QA_status.ne('pass').sum()),'e_median_sec':v.E_sec.median(),'p90_reach_n':int(v.P90_reached.sum()),'p90_reach_rate':v.P90_reached.mean(),'P50_eq_P90':bool(g.P50_sec.iloc[0]==g.P90_sec.iloc[0]),'P50_sec':g.P50_sec.iloc[0],'P90_sec':g.P90_sec.iloc[0],'U_stored_sec':g.U_stored_sec.iloc[0]});native.append(row)
n=pd.DataFrame(native);support=n.groupby(NG,sort=False).agg(n_weekdays=('weekday','nunique'),min_positive_days=('n_positive','min')).reset_index();support['all_five_weekdays_supported']=support.n_weekdays.eq(5)&support.min_positive_days.gt(0)
n=n.merge(support[NG+['all_five_weekdays_supported']],on=NG,validate='many_to_one');save(n.merge(primary[LABELS],on='segment_id',validate='many_to_one'),'weekday_available_native_cells.csv')
# All-available A cells kept as auxiliary, no pooling across months.
av=n[n.n_positive.gt(0)].groupby(['month','segment_id','hour','weekday']).agg(E_available_seq_median_sec=('e_median_sec','median'),P90_available_seq_mean=('p90_reach_rate','mean'),n_sequences=('native_id','nunique'),n_positive_observations=('n_positive','sum')).reset_index();save(av.merge(primary[LABELS],on='segment_id',validate='many_to_one'),'weekday_available_A_month_cells.csv')
ns=n[n.all_five_weekdays_supported].copy();nm=ns.groupby(['month','segment_id','hour','weekday'],sort=False).agg(E_median_seq_sec=('e_median_sec','median'),P90_mean_seq_rate=('p90_reach_rate','mean'),n_sequences=('native_id','nunique'),n_positive_observations=('n_positive','sum'),n_p90_reach_observations=('p90_reach_n','sum'),P50_eq_P90_sequences=('P50_eq_P90','sum')).reset_index()
goodseq=support[support.all_five_weekdays_supported][NG];d=q.merge(goodseq,on=NG,how='inner',validate='many_to_one');d=d[d.valid]
dates=d.groupby(['month','segment_id','hour','weekday']).date.nunique().rename('n_unique_positive_dates').reset_index();nm=nm.merge(dates,on=['month','segment_id','hour','weekday'],validate='one_to_one')
assert nm.groupby(['month','segment_id','hour']).weekday.nunique().eq(5).all();save(nm.merge(primary[LABELS],on='segment_id',validate='many_to_one'),'weekday_common_support_monthly.csv')
ix=pd.MultiIndex.from_product([primary.segment_id,range(24),range(5)],names=['segment_id','hour','weekday']);rows=[]
for key in ix:
 sid,h,w=key;g=nm[(nm.segment_id.eq(sid))&nm.hour.eq(h)&nm.weekday.eq(w)];r={'segment_id':sid,'hour':h,'weekday':w,'weekday_name':['월','화','수','목','금'][w]}
 for ms,suf in [(MAIN,''),([m for m in MAIN if m!='202601'],'_noJan')]:
  v=g[g.month.isin(ms)].sort_values('month');count=len(v);r['E_weekday_sec'+suf]=v.E_median_seq_sec.median();r['P90_reach_rate_equal_month'+suf]=v.P90_mean_seq_rate.mean();r['contributing_month_count'+suf]=count;r['contributing_months'+suf]=','.join(v.month);r['n_unique_positive_dates'+suf]=int(v.n_unique_positive_dates.sum());r['n_positive_observations'+suf]=int(v.n_positive_observations.sum());r['date_count_by_month'+suf]=json.dumps(dict(zip(v.month,v.n_unique_positive_dates)));r['sequence_count_by_month'+suf]=json.dumps(dict(zip(v.month,v.n_sequences)));r['support_status'+suf]='no_common_support' if count==0 else 'single_month_descriptive' if count==1 else 'multiple_month_descriptive'
 rows.append(r)
s=pd.DataFrame(rows).merge(primary[LABELS],on='segment_id',validate='many_to_one')
assert s.groupby(['segment_id','hour']).contributing_month_count.nunique().eq(1).all();assert s.groupby(['segment_id','hour']).contributing_months.nunique().eq(1).all()
base=['segment_id','hour','weekday','weekday_name']+[c for c in LABELS if c!='segment_id'];meta=[c for c in s.columns if any(c.startswith(x) for x in ['contributing_','n_unique_','n_positive_','date_count_','sequence_count_','support_status'])]
save(s[base+['E_weekday_sec','E_weekday_sec_noJan']+meta],'segment_weekday_excess.csv');save(s[base+['P90_reach_rate_equal_month','P90_reach_rate_equal_month_noJan']+meta],'segment_weekday_p90reach.csv');save(s,'diagnostic43_weekday_heatmap_data.csv')
# Compare weekday pair patterns only within each common month/hour.
wp=[]
for (sid,h),g in nm.groupby(['segment_id','hour'],sort=False):
 for wa in range(5):
  for wb in range(wa+1,5):
   a=g[g.weekday.eq(wa)].set_index('month');bb=g[g.weekday.eq(wb)].set_index('month');idx=a.index.intersection(bb.index);de=a.loc[idx,'E_median_seq_sec']-bb.loc[idx,'E_median_seq_sec'];dp=a.loc[idx,'P90_mean_seq_rate']-bb.loc[idx,'P90_mean_seq_rate'];wp.append({'segment_id':sid,'hour':h,'weekday_A':wa,'weekday_B':wb,'common_months':','.join(idx),'common_month_count':len(idx),'monthly_E_A_minus_B_median_sec':de.median(),'monthly_E_A_above_B_months':int(de.gt(0).sum()),'monthly_E_A_equal_B_months':int(de.eq(0).sum()),'monthly_E_A_below_B_months':int(de.lt(0).sum()),'monthly_P90_A_minus_B_mean':dp.mean(),'monthly_P90_A_above_B_months':int(dp.gt(0).sum()),'monthly_P90_A_equal_B_months':int(dp.eq(0).sum()),'monthly_P90_A_below_B_months':int(dp.lt(0).sum())})
save(pd.DataFrame(wp),'weekday_pair_month_direction_counts.csv')
hour=read(OUT/'hour_january_sensitivity.csv');s['level']='weekday';s['E_change_noJan_minus_Main_sec']=s.E_weekday_sec_noJan-s.E_weekday_sec;s['P90_rate_change_noJan_minus_Main']=s.P90_reach_rate_equal_month_noJan-s.P90_reach_rate_equal_month;save(pd.concat([hour,s],ignore_index=True),'january_temporal_sensitivity.csv')
# Planning/status and support tables make every denominator visible.
sc=[]
for month in MAIN:
 nn=n[n.month.eq(month)];cell=nn.drop_duplicates(NG);main=cell[cell.all_five_weekdays_supported]
 sc.append({'month':month,'native_Core_hour_cells':len(cell),'native_all_five_supported_cells':len(main),'native_all_five_unsupported_cells':len(cell)-len(main),'A_hour_common_support_cells':main[['segment_id','hour']].drop_duplicates().shape[0],'segments_with_common_support':main.segment_id.nunique(),'positive_daily_hour_observations':int(nn.n_positive.sum()),'common_support_positive_observations':int(nn.loc[nn.all_five_weekdays_supported,'n_positive'].sum())})
save(pd.DataFrame(sc),'weekday_support_summary.csv')
print('WEEKDAYS_READY native',len(n),'common A month/hour/weekday',len(nm),'final weekday cells',len(s),flush=True)
