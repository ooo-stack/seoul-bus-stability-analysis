"""Read-only submission QA. It does not rebuild raw observations or change results."""
from pathlib import Path
import ast,csv,json,hashlib,re,sys
import numpy as np,pandas as pd
from seoul_bus_paths import REPOSITORY as R

def read(p):return pd.read_csv(R/p,dtype={'month':str,'dong_code':str,'route_id':str,'departure_node':str,'arrival_node':str},float_precision='round_trip')
def main():
 checks={}
 def check(label,value):
  assert bool(value),label
  checks[label]=True
 main_months=['202509','202510','202601','202602','202603','202604','202605','202606']
 eligibility=read('outputs/F0M/final_month_eligibility.csv')
 check('eligible_8_plus_August_design_month',eligibility.loc[eligibility.final_status.eq('eligible'),'month'].tolist()==main_months+['202608'])
 check('held_months_unchanged',eligibility.loc[eligibility.final_status.eq('held_date'),'month'].tolist()==['202511','202512','202607'])
 d=read('outputs/F1A/monthly_dong_metrics.csv');s=read('outputs/F1A/monthly_relationship_summary.csv')
 check('427_dongs_each_of_9_eligible_months',len(d)==9*427 and d.groupby('month').dong_code.nunique().eq(427).all())
 expected={'202509':.194,'202510':.195,'202601':-.185,'202602':.198,'202603':.203,'202604':.212,'202605':.198,'202606':.207,'202608':.179}
 for m,r in expected.items():
  row=s[s.month.eq(m)].iloc[0];q=d[d.month.eq(m)];valid=q.C2_count.notna()&q.U_sec.notna()
  rr=q.loc[valid,'C2_count'].round(8).rank().corr(q.loc[valid,'U_sec'].round(8).rank())
  check('C2_U_saved_correlation_'+m,abs(rr-row.Spearman_C2_U)<1e-12 and round(float(row.Spearman_C2_U),3)==r)
 rec=read('outputs/F1B/dong_replication_metrics.csv');nine=rec[rec.K_rep.eq(8)]
 expected9={'11140520','11140570','11620695','11680510','11680610','11680660','11710650','11710710','11710720'}
 check('nine_exact_codes_8_of_8',len(nine)==9 and set(nine.dong_code)==expected9 and nine.V_rep.eq(8).all())
 check('all_K_recurrence_counts_unchanged',rec.K_rep.value_counts().sort_index().to_dict()=={0:363,1:21,2:1,3:2,4:2,5:5,6:3,7:21,8:9})
 primary=read('outputs/M1/dong_max_recurrence_route_segments.csv');con=read('outputs/M1/dong_segment_concentration.csv')
 keys=['dong_code','route_id','departure_node','arrival_node']
 check('43_distinct_fixed_segments',len(primary)==43 and not primary.duplicated(keys).any() and set(primary.dong_code)==expected9)
 check('regional_maximum_K_definition',primary.merge(con[['dong_code','K_max']],on='dong_code',validate='many_to_one').eval('K == K_max').all() and primary.groupby('dong_code').size().to_dict()==con.set_index('dong_code').K_max_group_count.to_dict())
 h=read('outputs/M2/diagnostic43_pattern_summary.csv');heat=read('outputs/M2/diagnostic43_hourly_heatmap.csv')
 check('43_hourly_pattern_keys_unchanged',set(map(tuple,h[keys].to_numpy()))==set(map(tuple,primary[keys].to_numpy())))
 check('hourly_coverage_min_median_max_17_19_20',h.evaluated_hours.min()==17 and h.evaluated_hours.median()==19 and h.evaluated_hours.max()==20)
 check('highest_hour_count_2_to_19',h.hour_R_max_hours.map(lambda x:len(str(x).split(','))).min()==2 and h.hour_R_max_hours.map(lambda x:len(str(x).split(','))).max()==19)
 # Code hashes plus normalized original AST signatures protect calculation logic.
 provenance=json.loads((R/'docs/code_provenance.json').read_text());asts=json.loads((R/'qa/original_ast_signatures.json').read_text())
 for p in provenance:
  file=R/p['repository_path'];text=file.read_text();check('code_sha_'+p['repository_path'],hashlib.sha256(file.read_bytes()).hexdigest()==p['submission_sha256'])
  t=ast.parse(text)
  t.body=[n for n in t.body if not (isinstance(n,ast.ImportFrom) and n.module=='seoul_bus_paths') and not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and ast.unparse(n.value.func)=='globals().update' and '_submission_bind' in ast.unparse(n))]
  if p['source_gate']=='C2B' and file.name=='c2b_analyze.py':
   for n in t.body:
    if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='ROOT' for x in n.targets):n.value=ast.Constant('PATH_ONLY')
  for n in ast.walk(t):
   if isinstance(n,ast.Constant) and isinstance(n.value,str):n.value=re.sub(r'libfile_[0-9a-f]+','private-reference-redacted',n.value)
  check('original_AST_'+p['repository_path'],hashlib.sha256(ast.dump(t,include_attributes=False).encode()).hexdigest()==asts[p['repository_path']])
 for p in json.loads((R/'docs/result_provenance.json').read_text()):
  if 'sha256' in p:check('saved_result_sha_'+p['path'],hashlib.sha256((R/p['path']).read_bytes()).hexdigest()==p['sha256'])
 for f in (R/'src').rglob('*.py'):compile(f.read_text(),str(f.relative_to(R)),'exec')
 result={'status':'PASS','checks_passed':len(checks),'checks':checks,'Main_replication_months':main_months,'source_code_files':len(provenance),'new_research_analysis_performed':False,'full_raw_pipeline_reexecuted':False,'scope':'published saved-result consistency and source integrity only; actual saved-state replay recorded separately in qa/reproduction_QA.md'}
 print(json.dumps(result,ensure_ascii=False,indent=2))
 return result
if __name__=='__main__':main()
