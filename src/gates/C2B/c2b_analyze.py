from pathlib import Path
import zipfile,io,json,hashlib,shutil
import numpy as np,pandas as pd
from fractions import Fraction

from seoul_bus_paths import workdir
ROOT=workdir();OUT=ROOT/'Gate4C2B';OUT.mkdir(exist_ok=True)
ST=OUT/'staging';ST.mkdir(exist_ok=True)
MONTHS=['202509','202510','202601','202602','202603','202604','202605','202606']
APPROVED={'11140520','11140570','11620695','11710650','11710710','11710720'}
COMPS=['LOCAL_PEOPLE_DONG','LONG_FOREIGNER_DONG','TEMP_FOREIGNER_DONG']
TARGETS=['daily_dong_E','daily_dong_I_rate']
IDT={k:str for k in ['month','date','dong_code','route_id','departure_node','arrival_node','departure_sequence','arrival_sequence','segment_id']}
def rd(p,**kw):return pd.read_csv(p,dtype=IDT,float_precision="round_trip",**kw)
def save(d,n):d.to_csv(ST/n,index=False,encoding='utf-8-sig',float_format='%.17g')
def dump(o,n):(OUT/n).write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def corr(g,x,y):
 v=g[[x,y]].dropna();n=len(v)
 status='ok' if n>=2 and v[x].nunique()>1 and v[y].nunique()>1 else 'insufficient_pairs' if n<2 else 'constant_variable'
 return {'n_pairs':n,'n_unique_dates':g.loc[v.index,'date'].nunique(),'x_unique':v[x].nunique(),'y_unique':v[y].nunique(),'spearman':v[x].rank(method='average').corr(v[y].rank(method='average')) if status=='ok' else np.nan,'status':status}
def periods(g):
 for m in MONTHS: yield 'Main',m,g[g.month.eq(m)]
 yield 'Main','pooled',g
 yield 'noJan','pooled',g[~g.month.eq('202601')]
def dirsummary(values):
 v=values.dropna();return {'valid_months':len(v),'positive_months':int(v.gt(0).sum()),'zero_months':int(v.eq(0).sum()),'negative_months':int(v.lt(0).sum()),'NA_months':len(values)-len(v),'monthly_median':v.median(),'monthly_min':v.min(),'monthly_max':v.max()}

z=zipfile.ZipFile(ROOT/'c2b_inputs/Gate3M2_results.zip')
roster=rd(io.BytesIO(z.read('fixed_segment_roster.csv')));roster=roster[roster.is_diagnostic43].copy()
assert len(roster)==43 and roster.segment_id.nunique()==43 and roster.dong_code.nunique()==9
save(roster,'fixed_diagnostic43_roster.csv')
cal=rd(ROOT/'Gate4C2A/analysis_calendar_metadata_only.csv');cal=cal[cal.month.isin(MONTHS)&cal.planned_weekday].copy();assert len(cal)==160
save(cal,'analysis_calendar.csv')
q=pd.concat([rd(io.BytesIO(z.read(f'daily_checkpoints/{m}_panel.csv.gz')),compression='gzip') for m in MONTHS],ignore_index=True)
assert set(q.segment_id)==set(roster.segment_id)
NK=['month','date','segment_id','departure_sequence','arrival_sequence','hour']
assert not q.duplicated(NK).any()
assert q.month.isin(MONTHS).all()
valid=q.valid & q.QA_status.eq('pass') & q.strict_core & q.common_planned
v=q[valid].copy();assert v.T_sec.gt(0).all()
assert np.allclose(v.E_sec,v.T_sec-v.P50_sec,rtol=0,atol=1e-10)
assert np.array_equal(v.P90_reached.to_numpy(),v.T_sec.ge(v.P90_sec).astype(int).to_numpy())
# Preserve M2 sequence folding before the user-specified two-level equal weighting.
h=v.groupby(['month','date','dong_code','segment_id','hour'],sort=False).agg(E_hour=('E_sec','median'),I_hour=('P90_reached','mean'),native_observations=('E_sec','size'),reach_count=('P90_reached','sum')).reset_index()
h['I_fraction']=[Fraction(int(i),int(n)) for i,n in zip(h.reach_count,h.native_observations)]
s=h.groupby(['month','date','dong_code','segment_id'],sort=False).agg(daily_segment_E=('E_hour','median'),daily_segment_I_rate=('I_hour','mean'),valid_hour_cells=('hour','size'),native_positive_observations=('native_observations','sum'),I_fraction=('I_fraction',lambda x:sum(x,Fraction(0))/len(x))).reset_index()
s['daily_segment_I_rate']=s.I_fraction.map(float)
sg=roster[['dong_code','segment_id','diagnostic_no']].merge(cal[['month','date']],how='cross').merge(s,on=['month','date','dong_code','segment_id'],how='left',validate='one_to_one')
sg[['valid_hour_cells','native_positive_observations']]=sg[['valid_hour_cells','native_positive_observations']].fillna(0).astype(int)
save(sg.drop(columns='I_fraction'),'daily_segment_case_panel.csv')
dg=s.groupby(['month','date','dong_code'],sort=False).agg(daily_dong_E=('daily_segment_E','median'),daily_dong_I_rate=('daily_segment_I_rate','mean'),valid_segments=('segment_id','nunique'),valid_hour_cells=('valid_hour_cells','sum'),native_positive_observations=('native_positive_observations','sum'),I_fraction=('I_fraction',lambda x:sum(x,Fraction(0))/len(x))).reset_index()
dg['daily_dong_I_rate']=dg.I_fraction.map(float)
dg=dg.drop(columns='I_fraction')
cases=roster[['dong_code','dong_name']].drop_duplicates();fixed=roster.groupby('dong_code').size().rename('fixed_diagnostic_segments')
grid=cases.merge(cal,how='cross').merge(dg,on=['month','date','dong_code'],how='left',validate='one_to_one').merge(fixed,on='dong_code',validate='many_to_one')
for col in ['valid_segments','valid_hour_cells','native_positive_observations']:grid[col]=grid[col].fillna(0).astype(int)
grid['bus_status']=np.where(grid.valid_segments.gt(0),'observed_fixed_diagnostic_segments','NA_no_valid_fixed_diagnostic_segments')
grid['living_population_main_approved']=grid.dong_code.isin(APPROVED)
assert len(grid)==1440 and not grid.duplicated(['dong_code','date']).any()

# Exposure-only daily transformation, no hourwise bus join.
lp=rd(ROOT/'Gate4C2A/living_population_exposure_panel.csv');lp=lp[lp.month.isin(MONTHS)&lp.planned_weekday &lp.dong_code.isin(APPROVED)].copy()
assert set(lp.component)==set(COMPS)
a=lp.groupby(['dong_code','date','month','component'],sort=False).agg(daily_activity_deviation_ratio=('relative_activity_deviation','median'),valid_activity_hours=('relative_activity_deviation','count'),expected_hour_labels=('hour','nunique')).reset_index()
assert a.expected_hour_labels.eq(24).all();assert not a.duplicated(['dong_code','date','component']).any()
save(a,'daily_activity_exposure.csv')
for comp in COMPS:
 aa=a[a.component.eq(comp)].drop(columns=['component','month','expected_hour_labels']).rename(columns={'daily_activity_deviation_ratio':comp+'_daily_activity_deviation_ratio','valid_activity_hours':comp+'_valid_hours'})
 grid=grid.merge(aa,on=['dong_code','date'],how='left',validate='one_to_one')
activity=[]
for (code,comp),g in a.groupby(['dong_code','component'],sort=False):
 g=g.merge(grid[['dong_code','date']+TARGETS],on=['dong_code','date'],validate='one_to_one');name=cases.set_index('dong_code').loc[code,'dong_name']
 for variant,period,gg in periods(g):
  for y in TARGETS:
   activity.append({'dong_code':code,'dong_name':name,'component':comp,'variant':variant,'period':period,'outcome':y,'planned_dates':len(gg),'valid_activity_dates':int(gg.daily_activity_deviation_ratio.notna().sum()),'activity_hours_min':gg.valid_activity_hours.min(),'activity_hours_max':gg.valid_activity_hours.max(),**corr(gg,'daily_activity_deviation_ratio',y),'interpretation_unit':'행정동 × 날짜','exposure_unit':'비율(1=100%)','outcome_unit':'초' if y=='daily_dong_E' else '비율(0~1)'})
ar=pd.DataFrame(activity);save(ar,'daily_activity_case_results.csv')

w=rd(ROOT/'c2b_inputs/official_daily_weather/official_asos108_daily.csv')
assert w.station_id.astype(str).eq('108').all() and not w.date.duplicated().any()
assert w.month.isin(MONTHS).all() and len(w)==242
assert w.daily_precipitation_mm.dropna().ge(0).all()
w['rain_day_status']=np.select([w.daily_precipitation_mm.eq(0),w.daily_precipitation_mm.gt(0)],['dry_day','rain_day'],default='NA_no_official_numeric_daily_precipitation')
save(w,'official_asos108_daily.csv')
grid=grid.merge(w.drop(columns=['month']),on='date',how='left',validate='many_to_one')
grid['weather_scope']='서울 공통 기상조건(ASOS 108)'
save(grid.sort_values(['dong_code','date']),'daily_bus_case_panel.csv')
weather=[]
for code,g in grid.groupby('dong_code',sort=False):
 name=g.dong_name.iloc[0]
 for variant,period,gg in periods(g):
  for y in TARGETS:
   base={'dong_code':code,'dong_name':name,'variant':variant,'period':period,'outcome':y,'planned_dates':len(gg),'bus_valid_dates':int(gg[y].notna().sum()),'outcome_unit':'초' if y=='daily_dong_E' else '비율(0~1)'}
   weather.append({**base,'analysis':'temperature_spearman','exposure':'ASOS108_official_daily_mean_temperature_c',**corr(gg,'daily_mean_temperature_c',y),'exposure_unit':'섭씨도','coverage_caveat':'한 지점의 서울 공통 조건. 월별 방향을 함께 해석하며 pooled를 계절통제 결과로 해석하지 않음.'})
   eligible=gg.dropna(subset=[y]);r=eligible[eligible.rain_day_status.eq('rain_day')][y];d=eligible[eligible.rain_day_status.eq('dry_day')][y]
   nmiss=int(eligible.rain_day_status.str.startswith('NA_').sum());ok=len(r)>0 and len(d)>0
   weather.append({**base,'analysis':'rain_minus_dry','exposure':'ASOS108_official_numeric_daily_precipitation','n_rain_dates':len(r),'n_dry_dates':len(d),'n_precipitation_NA_dates_with_bus':nmiss,'rain_all_planned_dates':int(gg.rain_day_status.eq('rain_day').sum()),'dry_all_planned_dates':int(gg.rain_day_status.eq('dry_day').sum()),'precipitation_NA_all_planned_dates':int(gg.rain_day_status.str.startswith('NA_').sum()),'rain_outcome_mean':r.mean(),'rain_outcome_median':r.median(),'dry_outcome_mean':d.mean(),'dry_outcome_median':d.median(),'mean_difference_rain_minus_dry':r.mean()-d.mean() if ok else np.nan,'median_difference_rain_minus_dry':r.median()-d.median() if ok else np.nan,'mean_difference_percentage_points':(r.mean()-d.mean())*100 if ok and y=='daily_dong_I_rate' else np.nan,'median_difference_percentage_points':(r.median()-d.median())*100 if ok and y=='daily_dong_I_rate' else np.nan,'n_pairs':len(r)+len(d),'status':'conditional_numeric_zero_comparison' if ok else 'held_no_rain_or_explicit_zero_group','exposure_unit':'mm/day','coverage_caveat':'수치 0인 날만 dry_day. 원문 - 표기는 NA. 일반적인 모든 무강수일과의 비교로 일반화 금지.'})
wr=pd.DataFrame(weather);save(wr,'daily_weather_case_results.csv')

direction=[]
for (code,comp,y),g in ar[ar.period.isin(MONTHS)].groupby(['dong_code','component','outcome'],sort=False):
 for variant,sel in [('Main',MONTHS),('noJan',[m for m in MONTHS if m!='202601'])]:
  gg=g[g.period.isin(sel)];direction.append({'domain':'activity','dong_code':code,'component':comp,'outcome':y,'variant':variant,'statistic':'spearman',**dirsummary(gg.spearman)})
for (code,analysis,y),g in wr[wr.period.isin(MONTHS)].groupby(['dong_code','analysis','outcome'],sort=False):
 for variant,sel in [('Main',MONTHS),('noJan',[m for m in MONTHS if m!='202601'])]:
  gg=g[g.period.isin(sel)]
  for metric in ['spearman'] if analysis=='temperature_spearman' else ['mean_difference_rain_minus_dry','median_difference_rain_minus_dry']:
   direction.append({'domain':analysis,'dong_code':code,'component':'','outcome':y,'variant':variant,'statistic':metric,**dirsummary(gg[metric])})
dr=pd.DataFrame(direction);save(dr,'monthly_direction_summary.csv')
summary=[]
for _,case in cases.iterrows():
 code=case.dong_code;g=grid[grid.dong_code.eq(code)];row=case.to_dict();row.update({'fixed_diagnostic_segments':int(g.fixed_diagnostic_segments.iloc[0]),'planned_dates':len(g),'bus_valid_dates':int(g.daily_dong_E.notna().sum()),'living_population_main_approved':code in APPROVED,'activity_status':'6case_approved' if code in APPROVED else 'NA_C2AR_space_not_verified','weather_status':'official_temperature_available_rain_comparison_conditional_missing_daily_values','interpretation':'현재 자료로 원인 미확정'})
 row['interpretation']='현재 자료로 원인 미확정. 실제 계수와 월별 방향을 함께 참조.'
 for comp in COMPS:
  for y,short in [('daily_dong_E','E'),('daily_dong_I_rate','I')]:
   gg=ar[(ar.dong_code.eq(code))&ar.component.eq(comp)&ar.outcome.eq(y)&ar.period.eq('pooled')]
   for variant in ['Main','noJan']:
    vrow=gg[gg.variant.eq(variant)]
    row[f'{comp}_{short}_rho_{variant}']=vrow.spearman.iloc[0] if len(vrow) else np.nan
    dd=dr[(dr.domain.eq('activity'))&dr.dong_code.eq(code)&dr.component.eq(comp)&dr.outcome.eq(y)&dr.variant.eq(variant)]
    row[f'{comp}_{short}_monthly_direction_{variant}']=json.dumps(dd[['positive_months','zero_months','negative_months','NA_months']].iloc[0].to_dict(),ensure_ascii=False) if len(dd) else ''
 for y,short in [('daily_dong_E','E'),('daily_dong_I_rate','I')]:
  for variant in ['Main','noJan']:
   gg=wr[(wr.dong_code.eq(code))&wr.outcome.eq(y)&wr.variant.eq(variant)&wr.period.eq('pooled')]
   temp=gg[gg.analysis.eq('temperature_spearman')].iloc[0];rain=gg[gg.analysis.eq('rain_minus_dry')].iloc[0]
   row[f'temperature_{short}_rho_{variant}']=temp.spearman
   row[f'rain_{short}_mean_diff_{variant}']=rain.mean_difference_rain_minus_dry
   row[f'rain_{short}_median_diff_{variant}']=rain.median_difference_rain_minus_dry
   for c in ['n_rain_dates','n_dry_dates','n_precipitation_NA_dates_with_bus']:row[f'{c}_{variant}']=rain[c]
 summary.append(row)
sm=pd.DataFrame(summary);save(sm,'case_evidence_summary.csv')
quality=grid.groupby(['month','dong_code','dong_name'],sort=False).agg(planned_dates=('date','size'),bus_valid_dates=('daily_dong_E','count'),min_valid_segments=('valid_segments','min'),max_valid_segments=('valid_segments','max'),temperature_dates=('daily_mean_temperature_c','count'),official_numeric_precip_dates=('daily_precipitation_mm','count')).reset_index();save(quality,'monthly_case_QA.csv')
qa={'M2_native_rows':len(q),'M2_valid_native_rows':len(v),'M2_status_counts':q.status_reason.value_counts().to_dict(),'folded_valid_hour_cells':len(h),'valid_segment_days':len(s),'planned_dong_days':len(grid),'valid_dong_days':int(grid.daily_dong_E.notna().sum()),'absent_dong_days':int(grid.daily_dong_E.isna().sum()),'planned_dates':160,'Main_months':MONTHS,'diagnostic_segments':43,'case_dongs':9,'activity_approved_dongs':6,'activity_daily_rows':len(a),'activity_daily_valid_rows':int(a.daily_activity_deviation_ratio.notna().sum()),'activity_hour_coverage_distribution':{str(k):int(v) for k,v in a.valid_activity_hours.value_counts().sort_index().items()},'official_weather_calendar_days':len(w),'official_weather_planned_days':int(w.date.isin(cal.date).sum()),'rain_status_on_planned_dates':w[w.date.isin(cal.date)].rain_day_status.value_counts().to_dict(),'temperature_valid_planned_dates':int(w[w.date.isin(cal.date)].daily_mean_temperature_c.notna().sum()),'activity_result_rows':len(ar),'weather_result_rows':len(wr),'no_hourwise_external_bus_join':True,'no_new_cutoff_or_score':True,'p_values_computed':False,'official_daily_precipitation_not_reconstructed_from_hourly':True}
dump(qa,'analysis_QA.json')
manifest={'M2_zip':{'path':'c2b_inputs/Gate3M2_results.zip','sha256':sha(ROOT/'c2b_inputs/Gate3M2_results.zip')},'living_population_panel':{'path':'Gate4C2A/living_population_exposure_panel.csv','sha256':sha(ROOT/'Gate4C2A/living_population_exposure_panel.csv')},'execution_spec':{'path':'execution_spec_frozen.md','sha256':sha(OUT/'execution_spec_frozen.md')},'M2_daily_member_sha256':{m:hashlib.sha256(z.read(f'daily_checkpoints/{m}_panel.csv.gz')).hexdigest() for m in MONTHS},'weather_metadata_manifest':json.loads((ROOT/'c2b_inputs/official_daily_weather/source_manifest.json').read_text())}
dump(manifest,'source_manifest.json')
print(json.dumps(qa,ensure_ascii=False,indent=2))
print('ACTIVITY POOLED E');print(ar[(ar.period.eq('pooled'))&ar.variant.eq('Main')&ar.outcome.eq('daily_dong_E')][['dong_name','component','spearman','n_pairs']].to_string(index=False))
print('WEATHER POOLED');print(wr[(wr.period.eq('pooled'))&wr.variant.eq('Main')][['dong_name','analysis','outcome','spearman','mean_difference_rain_minus_dry','median_difference_rain_minus_dry','n_rain_dates','n_dry_dates','n_precipitation_NA_dates_with_bus']].to_string(index=False))
