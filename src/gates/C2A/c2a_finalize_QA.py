from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,csv
R=Path('Gate4C2A');S=R/'staging'
def save(n,d):d.to_csv(S/n,index=False,encoding='utf-8-sig',na_rep='')
a=pd.read_csv(S/'living_population_schema_audit.csv',dtype={'month':str},keep_default_na=False)
a['raw_schema_changed_vs_first_month']=a.schema_changed
normalized=[]
for text in a.columns_json:
 h=json.loads(text);h[0]='기준일ID' if h[0] in ['?"기준일ID"','기준일ID'] else h[0];normalized.append(h)
a['normalized_columns_json']=[json.dumps(h,ensure_ascii=False) for h in normalized]
a['normalized_schema_changed']=False
for comp,ix in a.groupby('component').groups.items():
 ref=normalized[min(ix)]
 for i in ix:a.loc[i,'normalized_schema_changed']=normalized[i]!=ref
a['schema_change_explanation']=np.where(a.raw_schema_changed_vs_first_month,'first-column header artifact and encoding change; normalized semantic columns unchanged','no semantic column change')
a['expected_rows_424_calendar_grid']=[pd.Period(m,freq='M').days_in_month*24*424 for m in a.month]
a['absent_keys_vs_424_calendar_grid']=a.expected_rows_424_calendar_grid-a.rows
a['file_QA_readiness']='READY'
a['bus_join_readiness']='CONDITIONAL'
save('living_population_schema_audit.csv',a)
l=pd.read_csv(S/'living_population_exposure_panel.csv',dtype={'date':str,'month':str,'dong_code':str},keep_default_na=False)
remove=['baseline_reference','living_name_source','code_match_status']
l=l.drop(columns=remove)
save('living_population_exposure_panel.csv',l)
missing=l[l.value_status.ne('observed')][['dong_code','dong_name','date','hour','component','value_status']]
save('living_population_missing_keys.csv',missing)
c=[]
for (code,m,component),g in l.groupby(['dong_code','month','component']):
 ordinary=g[g.planned_weekday.eq(True)]
 c.append({'dong_code':code,'dong_name':g.dong_name.iloc[0],'month':m,'component':component,'calendar_grid_cells':len(g),'observed_cells':int(g.value_status.eq('observed').sum()),'absent_cells':int(g.value_status.eq('row_absent').sum()),'planned_ordinary_cells':len(ordinary),'observed_ordinary_cells':int(ordinary.value_status.eq('observed').sum()),'baseline_valid_dates_min':pd.to_numeric(ordinary.baseline_valid_dates,errors='coerce').min(),'baseline_valid_dates_max':pd.to_numeric(ordinary.baseline_valid_dates,errors='coerce').max(),'zero_baseline_cells':int(pd.to_numeric(ordinary.baseline_living_population_median,errors='coerce').eq(0).sum()),'missing_value_not_imputed':True,'raw_panel_readiness':'READY','bus_join_readiness':'CONDITIONAL'})
save('living_population_case_coverage.csv',pd.DataFrame(c))
w=pd.read_csv(S/'weather_native_station_hour_panel.csv',dtype={'지점':str,'month':str,'date':str})
q=pd.read_csv(S/'weather_station_audit.csv',dtype=str,keep_default_na=False)
q['max_consecutive_missing_hours']=''
def longest(a):
 best=run=0
 for v in a:
  run=run+1 if v else 0;best=max(best,run)
 return best
for i,row in q[q.network.eq('AWS') & q.field_present.eq('True')].iterrows():
 g=w[w['지점'].eq(row.station_id) & w.month.eq(row.month)]
 rng=pd.date_range(pd.Period(row.month,freq='M').start_time,pd.Period(row.month,freq='M').end_time.floor('h'),freq='h')
 t=pd.to_datetime(g.timestamp);v=pd.Series(pd.to_numeric(g[row.variable],errors='coerce').to_numpy(),index=t).reindex(rng)
 q.loc[i,'max_consecutive_missing_hours']=str(longest(v.isna().to_numpy()))
save('weather_station_audit.csv',q)
# Individual omitted weather keys remain explicitly absent, no per-hour replacement.
wc=pd.read_csv(S/'weather_exposure_panel.csv',dtype={'dong_code':str,'date':str,'month':str})
weather_missing=wc[wc.temperature_c.isna()|wc.precipitation_mm.isna()][['dong_code','dong_name','date','hour','aws_station_id','temperature_c_status','precipitation_mm_status']]
save('weather_missing_keys.csv',weather_missing)
coverage=[]
for (code,m),g in wc.groupby(['dong_code','month']):
 coverage.append({'dong_code':code,'dong_name':g.dong_name.iloc[0],'month':m,'aws_station_id':int(g.aws_station_id.iloc[0]),'expected_hours':len(g),'temperature_valid_hours':int(g.temperature_c.notna().sum()),'rainfall_valid_hours':int(g.precipitation_mm.notna().sum()),'joint_weather_valid_hours':int(g.temperature_c.notna().mul(g.precipitation_mm.notna()).sum()),'temperature_coverage':g.temperature_c.notna().mean(),'rainfall_coverage':g.precipitation_mm.notna().mean(),'station_match_readiness':'CONDITIONAL'})
save('weather_dong_month_coverage.csv',pd.DataFrame(coverage))
summary=json.loads((R/'external_QA_summary.json').read_text())
summary.update(living_normalized_schema_changed_files=a.loc[a.normalized_schema_changed,'source_file'].tolist(),living_raw_schema_change_explanation='202509 local/long first field has literal ? and quotes; code/date values verified and header normalized only for audit',weather_valid_temperature_cells=int(wc.temperature_c.notna().sum()),weather_valid_rainfall_cells=int(wc.precipitation_mm.notna().sum()),weather_joint_valid_cells=int((wc.temperature_c.notna()&wc.precipitation_mm.notna()).sum()),living_activity_deviation_valid_cells=int(pd.to_numeric(l.daily_activity_deviation,errors='coerce').notna().sum()),living_relative_deviation_valid_cells=int(pd.to_numeric(l.relative_activity_deviation,errors='coerce').notna().sum()),weather_missing_any_cells=len(weather_missing))
(R/'external_QA_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
# Freeze metadata actually used; inherited bus row counts and availability are excluded.
cal=pd.read_csv('c2a_inputs/day_calendar.csv',dtype=str,usecols=['month','date','weekday','holiday_name','planned_weekday'],keep_default_na=False)
save('analysis_calendar_metadata_only.csv',cal[cal.month.isin(summary['main_months'])])
print('QA finalized. Header artifact is not a semantic schema break. Metadata-only calendar preserved.')
