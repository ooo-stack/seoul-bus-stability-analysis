from common import *
r=read(OUT/'segment_hour_recurrence.csv');r=r[r.is_diagnostic43];s=read(OUT/'segment_hour_summary.csv');s=s[s.is_diagnostic43];b=units().query('is_diagnostic43').sort_values('diagnostic_no');w=read(OUT/'diagnostic43_weekday_heatmap_data.csv');n=read(OUT/'weekday_available_native_cells.csv');support=read(OUT/'weekday_support_summary.csv');qa=read(OUT/'daily_panel_QA.csv');comp=read(OUT/'stop_pair_hourly_comparison.csv');comp=comp[comp.is_diagnostic43 & comp.month.isin(MAIN)]
def basic(x):
 y=x.dropna();return {'n':len(y),'min':float(y.min()) if len(y) else None,'median':float(y.median()) if len(y) else None,'max':float(y.max()) if len(y) else None}
rows=[]
for br in b.itertuples():
 h=r[r.segment_id.eq(br.segment_id)];ww=w[w.segment_id.eq(br.segment_id)];valid=ww[ww.contributing_month_count.gt(0)];row={k:getattr(br,k) for k in LABELS};row.update({'evaluated_hours':int(h.V_h.gt(0).sum()),'hour_R_max':float(h.R_h.max()),'hour_R_max_hours':','.join('%02d'%int(hr) for hr in h.loc[h.R_h.eq(h.R_h.max()),'hour']),'weekday_supported_hours':int(valid.hour.nunique()),'weekday_months_min':int(valid.contributing_month_count.min()) if len(valid) else 0,'weekday_months_median':float(valid.contributing_month_count.median()) if len(valid) else None,'weekday_months_max':int(valid.contributing_month_count.max()) if len(valid) else 0,'weekday_positive_dates_min':int(valid.n_unique_positive_dates.min()) if len(valid) else 0,'weekday_positive_dates_median':float(valid.n_unique_positive_dates.median()) if len(valid) else None,'weekday_positive_dates_max':int(valid.n_unique_positive_dates.max()) if len(valid) else 0})
 for metric,tag in [('E_weekday_sec','E'),('P90_reach_rate_equal_month','P90')]:
  maxima={day:0 for day in range(5)};tot=0
  for hr,g in valid.groupby('hour'):
   peaks=g[g[metric].eq(g[metric].max())]
   for day in peaks.weekday:maxima[int(day)]+=1
   tot+=len(peaks)
  row[tag+'_max_weekday_hour_counts']=json.dumps({['월','화','수','목','금'][k]:v for k,v in maxima.items()},ensure_ascii=False);row[tag+'_max_ties_total']=tot
 rows.append(row)
save(pd.DataFrame(rows),'diagnostic43_pattern_summary.csv')
c=read(OUT/'hour_pair_common_month_comparison.csv');ap=c[c.hour_A.isin([7,8,9])&c.hour_B.isin([17,18,19])&c.common_month_count.gt(0)].copy();ap['PM_R_minus_AM_R']=ap.R_B_common-ap.R_A_common;ap['PM_U_minus_AM_U_sec']=ap.U_B_common_median_sec-ap.U_A_common_median_sec;save(ap,'AM_PM_common_month_comparison.csv')
hours=[]
for hr,g in r.groupby('hour'):
 v=g[g.V_h.gt(0)];hours.append({'hour':int(hr),'evaluated_segments':len(v),'R_median':float(v.R_h.median()) if len(v) else None,'R1_segments':int(v.R_h.eq(1).sum()),'Rmax_tie_segments':int(s.R_h_max_hours.fillna('').str.split(',').apply(lambda a:'%02d'%hr in a).sum()),'U_median_across_segments_sec':float(v.U_median_h_sec.median()) if len(v) else None})
wg=w[w.contributing_month_count.gt(0)];hc=wg[wg.weekday.eq(0)];native=n.drop_duplicates(['month','segment_id','departure_sequence','arrival_sequence','hour']);nm=read(OUT/'weekday_common_support_monthly.csv')
weekday_summary=[]
for metric in ['E_weekday_sec','P90_reach_rate_equal_month']:
 maxcounts=[0]*5;mincounts=[0]*5;varying=equal=0
 for key,g in wg.groupby(['segment_id','hour']):
  mx=g[g[metric].eq(g[metric].max())];mn=g[g[metric].eq(g[metric].min())]
  for day in mx.weekday:maxcounts[int(day)]+=1
  for day in mn.weekday:mincounts[int(day)]+=1
  if g[metric].max()==g[metric].min():equal+=1
  else:varying+=1
 weekday_summary.append({'metric':metric,'supported_segment_hour_cells':hc.shape[0],'all_five_equal_cells':equal,'weekday_values_differ_cells':varying,'max_weekday_ties_counts':maxcounts,'min_weekday_ties_counts':mincounts})
noJan=w[w.contributing_month_count.gt(0)&w.contributing_month_count_noJan.gt(0)]
peak_qa=[]
for metric in ['E_weekday_sec','P90_reach_rate_equal_month']:
 same=changed=0;js=[]
 for key,g in noJan.groupby(['segment_id','hour']):
  aa=set(g.loc[g[metric].eq(g[metric].max()),'weekday']);bb=set(g.loc[g[metric+'_noJan'].eq(g[metric+'_noJan'].max()),'weekday']);same+=aa==bb;changed+=aa!=bb;js.append(len(aa&bb)/len(aa|bb))
 peak_qa.append({'metric':metric,'same_max_weekday_set_cells':same,'changed_max_weekday_set_cells':changed,'max_weekday_set_Jaccard_median':float(np.median(js))})
rr=r[r.V_h.gt(0)&r.V_h_noJan.gt(0)];same_r=np.isclose(rr.R_h,rr.R_h_noJan,atol=1e-12);shared=comp[comp.n_routes.gt(1)]
wp=read(OUT/'weekday_pair_month_direction_counts.csv');sample=wp[(wp.segment_id.eq(b.segment_id.iloc[0]))&wp.hour.isin([8,18])&wp.weekday_A.eq(0)&wp.weekday_B.eq(4)]
result={'hour_evaluated_count':basic(s.evaluated_hours),'hour_peak_ties_count':basic(s.R_h_max_hour_count),'hour_V_distribution':{str(k):int(v) for k,v in r.V_h.value_counts().sort_index().items()},'hours':hours,'AM_PM_common_comparisons':len(ap),'AM_PM_R_PM_above':int(ap.PM_R_minus_AM_R.gt(0).sum()),'AM_PM_R_equal':int(ap.PM_R_minus_AM_R.eq(0).sum()),'AM_PM_R_AM_above':int(ap.PM_R_minus_AM_R.lt(0).sum()),'AM_PM_U_PM_above':int(ap.PM_U_minus_AM_U_sec.gt(0).sum()),'AM_PM_U_equal':int(ap.PM_U_minus_AM_U_sec.eq(0).sum()),'AM_PM_U_AM_above':int(ap.PM_U_minus_AM_U_sec.lt(0).sum()),'QA_cells':len(qa),'QA_pass_cells':int(qa.QA_status.eq('pass').sum()),'weekday_support_by_month':support.to_dict('records'),'native_common_support_cells':int(native.all_five_weekdays_supported.sum()),'native_cells_total':len(native),'weekday_supported_A_hour_cells':len(hc),'weekday_unsupported_A_hour_cells':43*24-len(hc),'weekday_supported_segments':hc.segment_id.nunique(),'weekday_month_count_distribution':{str(k):int(v) for k,v in hc.contributing_month_count.value_counts().sort_index().items()},'weekday_positive_unique_dates_per_hour_weekday':basic(wg.n_unique_positive_dates),'weekday_positive_days_per_native_month_weekday':basic(n[n.n_positive.gt(0)].n_positive),'weekday_native_P50_eq_P90_cells':int(native.P50_eq_P90.sum()),'weekday_peak_summaries':weekday_summary,'January_hour_common_cells':len(rr),'January_R_exactly_same_cells':int(same_r.sum()),'January_R_abs_change':basic((rr.R_h-rr.R_h_noJan).abs()),'January_U_abs_change_sec':basic((rr.U_median_h_sec-rr.U_median_h_sec_noJan).abs()),'January_weekday_common_cells':len(noJan),'January_E_abs_change_sec':basic((noJan.E_weekday_sec-noJan.E_weekday_sec_noJan).abs()),'January_P90_rate_abs_change':basic((noJan.P90_reach_rate_equal_month-noJan.P90_reach_rate_equal_month_noJan).abs()),'January_weekday_peak_QA':peak_qa,'pair_hour_main_comparisons':len(comp),'pair_hour_main_agreement_count':int(comp.flag_agrees.sum()),'pair_hour_main_agreement':float(comp.flag_agrees.mean()),'shared_pair_hour_main_comparisons':len(shared),'shared_pair_hour_main_agreement_count':int(shared.flag_agrees.sum()),'shared_pair_hour_main_agreement':float(shared.flag_agrees.mean()),'shared_pair_cases':shared.flag_case.value_counts().to_dict(),'all_pair_cases':comp.flag_case.value_counts().to_dict(),'fixed_first_segment_mon_vs_fri_examples':sample.to_dict('records')}
dump(result,'temporal_summary.json');print(json.dumps(result,ensure_ascii=False,indent=2))
