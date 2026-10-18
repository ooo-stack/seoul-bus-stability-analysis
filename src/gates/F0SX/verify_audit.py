"""Audit consistency and comparison to existing F0S; no outcome calculation."""
from audit_full_months import *
from baseline_quantile import quantile

def main():
 baseline=OUT/'reference';checks=[];comparisons=[]
 def check(name,ok,detail=''):checks.append({'check':name,'pass':bool(ok),'detail':detail})
 s=pd.read_csv(OUT/'monthly_schema_audit.csv',dtype={'month':str});v=pd.read_csv(OUT/'monthly_value_structure.csv',dtype={'month':str});d=pd.read_csv(OUT/'monthly_duplicate_audit.csv',dtype={'month':str});c=pd.read_csv(OUT/'monthly_date_coverage.csv',dtype={'month':str});daily=pd.read_csv(OUT/'daily_file_coverage.csv',dtype={'date':str});ids=pd.read_csv(OUT/'monthly_id_structure.csv',dtype={'month':str});days=pd.read_csv(OUT/'day_calendar.csv',dtype={'date':str,'month':str});details=json.loads((WORK/'duplicate_details.json').read_text())
 check('24_month_kind_rows',len(s)==24 and len(d)==24 and len(ids)==24 and len(c)==12)
 check('all_106_csv_completed',len(list(WORK.glob('scan_*.pkl')))==106)
 check('no_parse_errors',json.loads((OUT/'parse_errors.json').read_text())==[])
 check('cell_partition_exact',((v[['blank_cells','zero_cells','positive_cells','negative_cells','invalid_cells']].sum(axis=1))==v.cells).all())
 check('24hour_denominator',((v.loc[v.scope=='hourly_00_23_pooled','cells'])==(v.loc[v.scope=='hourly_00_23_pooled','raw_rows']*24)).all())
 check('quantile_order',((v.positive_median<=v.positive_p90)&(v.positive_p90<=v.positive_p99)&(v.positive_p99<=v.positive_max)).all())
 check('F0D_N_unchanged',c.N_planned.tolist()==[22,18,20,22,21,17,21,22,18,21,22,20])
 check('F0D_monthly_requirements',((c.common_days>=c.coverage_minimum)&(c.common_days>=c.L_main)).equals(c.monthly_count_condition_pass))
 check('F0D_weekly_and_monthly',((c.monthly_count_condition_pass)&c.weekly_condition_pass).equals(c.date_condition_pass))
 for _,r in s.iterrows():
  n=int(daily[(daily.kind==r.kind)&daily.date.str.startswith(r.month)].rows.sum());check(f'row_reconciliation_{r.month}_{r.kind}',n==r.raw_rows)
 for _,r in d.iterrows():
  group=[x for x in details if x['month']==r.month and x['kind']==r.kind];extra=sum(x['distinct_raw_rows']-1 for x in group)
  check(f'duplicate_reconciliation_{r.month}_{r.kind}',r.key_duplicate_extra_rows==r.complete_duplicate_extra_rows+extra)
 # Existing 4-month baselines must match; any mismatch is reported, not silently amended.
 oldv=pd.read_csv(baseline/'F0S_value_structure_diagnostics.csv',dtype={'source_or_period':str});oldr=pd.read_csv(baseline/'F0S_repeated_key_diagnostics.csv',dtype={'source_or_period':str});oldc=pd.read_csv(baseline/'F0S_date_coverage.csv',dtype={'source':str})
 for mo in ['202509','202601','202607','202608']:
  for kind in ['time','count']:
   ov=oldv[(oldv.scope=='calendar_month')&(oldv.source_or_period==mo)&(oldv.kind==kind)]
   if ov.empty:ov=oldv[(oldv.source_or_period==mo)&(oldv.kind==kind)]
   nv=v[(v.month==mo)&(v.kind==kind)]
   for _,a in ov.iterrows():
    col='hourly_00_23_pooled' if '24' in a['column'] or a['column']=='ALL_HOURS' else a['column']
    b=nv[nv.scope==col]
    if len(b)!=1:continue
    for metric in ['cells','blank_cells','zero_cells','positive_cells','positive_median','positive_p90','positive_p99','positive_max']:
     x=a[metric];y=b.iloc[0][metric];comparisons.append({'month':mo,'kind':kind,'scope':col,'metric':metric,'F0S':x,'F0SX':y,'equal':bool(x==y or (pd.isna(x) and pd.isna(y)))})
   rr=oldr[(oldr.source_or_period==mo)&(oldr.kind==kind)]
   for _,a in rr.iterrows():
    b=d[(d.month==mo)&(d.kind==kind)].iloc[0]
    for om,nm in [('rows','raw_rows'),('complete_duplicate_extra_rows','complete_duplicate_extra_rows'),('key_duplicate_extra_rows','key_duplicate_extra_rows')]:comparisons.append({'month':mo,'kind':kind,'scope':'calendar_month','metric':om,'F0S':a[om],'F0SX':b[nm],'equal':a[om]==b[nm]})
   cc=oldc[(oldc.source==mo)&(oldc.kind==kind)]
   for _,a in cc.iterrows():
    n=c[c.month==mo].iloc[0][kind+'_calendar_days'];comparisons.append({'month':mo,'kind':kind,'scope':'calendar_month','metric':'actual_dates','F0S':a.unique_dates,'F0SX':n,'equal':a.unique_dates==n})
 write(comparisons,'baseline_F0S_reconciliation.csv');check('baseline_comparison_nonempty',len(comparisons)>=200);check('baseline_values_unchanged',all(r['equal'] for r in comparisons))
 june=[x for x in details if x['date']=='20260630' and x['kind']=='time' and x['problem']!='exact_duplicate'];check('known_June30_51_keys',len(june)==51)
 if (OUT/'id_sequence_hold_keys.csv').exists():
  held=pd.read_csv(OUT/'id_sequence_hold_keys.csv',dtype=str)
  check('all_unknown_sequence_keys_preserved',len(held)==int(ids.unknown_id_or_sequence_rows.sum()))
 check('frozen_uploaded_document_equals_package',(SOURCES/'Ai 교통 공모전/Gate2F0D_design_freeze.md').read_bytes()==(OUT/'reference/Gate2F0D_design_freeze.md').read_bytes())
 write(checks,'verification_results.csv');dump({'pass':all(x['pass'] for x in checks),'checks':checks},OUT/'verification_results.json')
 print('VERIFICATION',len(checks),'checks',sum(x['pass'] for x in checks),'passed');print([x for x in checks if not x['pass']]);print('baseline comparisons',len(comparisons))
if __name__=='__main__':main()
