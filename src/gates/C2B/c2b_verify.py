from pathlib import Path
from collections import defaultdict
from statistics import median,mean
import csv,io,zipfile,json,hashlib,math
import numpy as np,pandas as pd
from fractions import Fraction
R=Path(__file__).resolve().parent;O=R/'Gate4C2B';S=O/'staging';checks={}
# Submission adapter: paths only; the original calculation statements follow.
from seoul_bus_paths import bind as _submission_bind
globals().update(_submission_bind('C2B'))
def check(k,v):
 assert bool(v),k
 checks[k]=True
def read(n):return pd.read_csv(S/n,float_precision='round_trip',dtype={'dong_code':str,'date':str,'month':str,'period':str})
b=read('daily_bus_case_panel.csv');ar=read('daily_activity_case_results.csv');wr=read('daily_weather_case_results.csv');dr=read('monthly_direction_summary.csv');lp=read('daily_activity_exposure.csv')
check('9_cases_160_planned_days_1440_unique_rows',len(b)==1440 and b.dong_code.nunique()==9 and b.date.nunique()==160 and not b.duplicated(['dong_code','date']).any())
M={'202509','202510','202601','202602','202603','202604','202605','202606'}
check('only_Main_months',set(b.month)==M)
approved={'11140520','11140570','11620695','11710650','11710710','11710720'}
check('living_population_only_approved_6',set(lp.dong_code)==approved)
for c in [x for x in b if 'daily_activity_deviation_ratio' in x]:check('unapproved_3_NA_'+c,b.loc[~b.dong_code.isin(approved),c].isna().all())
check('missing_bus_74_preserved',b.daily_dong_E.isna().sum()==74 and b.loc[b.valid_segments.eq(0),'daily_dong_E'].isna().all() and b.loc[b.valid_segments.eq(0),'daily_dong_I_rate'].isna().all())
check('January_Jamsilbon_NA',b.loc[b.dong_code.eq('11710650')&b.month.eq('202601'),'daily_dong_E'].isna().all())
z=zipfile.ZipFile(R/'c2b_inputs/Gate3M2_results.zip');hour=defaultdict(lambda:[[],[]]);native=0
for m in sorted(M):
 p=pd.read_csv(io.BytesIO(z.read(f'daily_checkpoints/{m}_panel.csv.gz')),compression='gzip',float_precision='round_trip',dtype={'date':str,'dong_code':str,'segment_id':str})
 for r in p.itertuples(index=False):
  if r.valid and r.QA_status=='pass' and r.strict_core and r.common_planned:
   key=(r.dong_code,r.date,r.segment_id,r.hour);hour[key][0].append(r.E_sec);hour[key][1].append(r.P90_reached);native+=1
seg=defaultdict(lambda:[[],[],0])
for (dong,date,sid,h),(ee,ii) in hour.items():
 g=seg[(dong,date,sid)];g[0].append(median(ee));g[1].append(sum((Fraction(int(x)) for x in ii),Fraction(0))/len(ii));g[2]+=len(ee)
dong=defaultdict(lambda:[[],[],0,0])
for (code,date,sid),(ee,ii,raw) in seg.items():
 g=dong[(code,date)];g[0].append(median(ee));g[1].append(sum(ii,Fraction(0))/len(ii));g[2]+=len(ee);g[3]+=raw
for r in b.itertuples(index=False):
 if (r.dong_code,r.date) not in dong:continue
 e,i,h,n=dong[(r.dong_code,r.date)]
 assert abs(r.daily_dong_E-median(e))<1e-10
 assert abs(r.daily_dong_I_rate-float(sum(i,Fraction(0))/len(i)))<1e-12
 assert r.valid_segments==len(e) and r.valid_hour_cells==h and r.native_positive_observations==n
check('all_daily_two_stage_equal_weight_aggregates_independent',True)
check('all_native_120659_and_folded_116475_counts',native==120659 and len(hour)==116475)
# Independent tie ranks, not scipy hypothesis testing.
def rank(v):
 ix=np.argsort(v,kind='stable');rr=np.empty(len(v),dtype=float);i=0
 while i<len(v):
  j=i+1
  while j<len(v) and v[ix[j]]==v[ix[i]]:j+=1
  rr[ix[i:j]]=(i+1+j)/2;i=j
 return rr
def rho(v,x,y):
 vv=v[[x,y]].dropna()
 if len(vv)<2 or vv[x].nunique()<2 or vv[y].nunique()<2:return np.nan,len(vv)
 return np.corrcoef(rank(vv[x].to_numpy()),rank(vv[y].to_numpy()))[0,1],len(vv)
def close(x,y):return pd.isna(x) and pd.isna(y) or (not pd.isna(x) and not pd.isna(y) and abs(x-y)<1e-11)
for r in ar.itertuples(index=False):
 g=lp[(lp.dong_code==r.dong_code)&(lp.component==r.component)].merge(b[['dong_code','date',r.outcome]],on=['dong_code','date'],validate='one_to_one')
 if r.period!='pooled':g=g[g.month.eq(r.period)]
 if r.variant=='noJan':g=g[g.month.ne('202601')]
 rr,n=rho(g,'daily_activity_deviation_ratio',r.outcome);assert close(rr,r.spearman) and n==r.n_pairs
check('all_360_activity_correlations_independent',len(ar)==360)
original_lp=pd.read_csv(R/'Gate4C2A/living_population_exposure_panel.csv',float_precision='round_trip',dtype={'dong_code':str,'date':str,'month':str})
original_lp=original_lp[original_lp.dong_code.isin(approved)&original_lp.month.isin(M)&original_lp.planned_weekday]
manual={k:(median(g.relative_activity_deviation.dropna().tolist()),int(g.relative_activity_deviation.notna().sum())) for k,g in original_lp.groupby(['dong_code','date','component'])}
for r in lp.itertuples(index=False):
 x,n=manual[(r.dong_code,r.date,r.component)];assert close(x,r.daily_activity_deviation_ratio) and n==r.valid_activity_hours
check('all_2880_activity_daily_medians_from_original_hourly_panel',len(manual)==2880)
cal=pd.read_csv(io.BytesIO(z.read('inputs/F1A/reference/day_calendar.csv')),dtype=str)
cal=cal[cal.month.isin(M)&cal.planned_weekday.eq('True')]
check('frozen_M2_planned_calendar_exact_dates',set(cal.date)==set(b.date))
m2qa=pd.read_csv(io.BytesIO(z.read('daily_panel_QA.csv')))
check('M2_all_6288_native_cells_inherited_QA_pass',len(m2qa)==6288 and m2qa.QA_status.eq('pass').all() and m2qa.source_hash_and_dates_match.all())

for r in wr.itertuples(index=False):
 g=b[b.dong_code==r.dong_code]
 if r.period!='pooled':g=g[g.month.eq(r.period)]
 if r.variant=='noJan':g=g[g.month.ne('202601')]
 if r.analysis=='temperature_spearman':
  rr,n=rho(g,'daily_mean_temperature_c',r.outcome);assert close(rr,r.spearman) and n==r.n_pairs
 else:
  g=g.dropna(subset=[r.outcome]);rain=g[g.daily_precipitation_mm.gt(0)][r.outcome];dry=g[g.daily_precipitation_mm.eq(0)][r.outcome]
  assert len(rain)==r.n_rain_dates and len(dry)==r.n_dry_dates and g.daily_precipitation_mm.isna().sum()==r.n_precipitation_NA_dates_with_bus
  for label,xx,fun in [('rain_outcome_mean',rain,'mean'),('dry_outcome_mean',dry,'mean'),('rain_outcome_median',rain,'median'),('dry_outcome_median',dry,'median')]:assert close(getattr(r,label),getattr(xx,fun)())
  de=rain.mean()-dry.mean() if len(rain) and len(dry) else np.nan;dm=rain.median()-dry.median() if len(rain) and len(dry) else np.nan
  assert close(de,r.mean_difference_rain_minus_dry) and close(dm,r.median_difference_rain_minus_dry)
check('all_360_weather_results_independent',len(wr)==360)
check('no_precip_missing_to_dry',b.loc[b.daily_precipitation_mm.isna(),'rain_day_status'].str.startswith('NA_').all())
check('I_rate_range',b.daily_dong_I_rate.dropna().between(0,1).all())
check('negative_and_zero_E_preserved',b.daily_dong_E.lt(0).any() and b.daily_dong_E.eq(0).any())
check('no_new_outcome_type_cutoff_score',not any('score' in c or 'priority' in c for c in b.columns))
check('all_monthly_and_pooled_variants_preserved',set(ar.period)==M|{'pooled'} and set(wr.period)==M|{'pooled'} and len(ar[ar.variant=='noJan'])==36 and len(wr[wr.variant=='noJan'])==36)
check('report_exists',(O/'Gate4C2B_daily_case_report.md').exists())
for p in [O/'Gate4C2B_daily_case_report.md',O/'execution_spec_frozen.md',O/'units_and_fields.md']:
 check('no_middle_dot_'+p.name,'\u00b7' not in p.read_text())
manifest=json.loads((O/'source_manifest.json').read_text())
check('frozen_spec_hash_unchanged',hashlib.sha256((O/'execution_spec_frozen.md').read_bytes()).hexdigest()==manifest['execution_spec']['sha256'])
result={'status':'PASS','checks':checks,'independent_all_cell_aggregation':True,'all_720_association_or_difference_rows_reconciled':True,'hypothesis_testing_performed':False,'material_limitations':['공식 일강수 수치 부재 100/160 계획 평일은 NA. 일반적인 모든 건조일 비교는 보류.','강남구 3개 생활인구 공간 미승인.','1월 잠실본동 버스 NA.','기술적 동반관계이며 인과효과와 설명력 증가 미입증.']}
(O/'verification_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASS','checks':len(checks),'daily_aggregates':len(dong),'result_rows':len(ar)+len(wr)},ensure_ascii=False))
