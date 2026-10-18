"""Summarize frozen variants with nullable candidates and scope-specific denominators."""
from pathlib import Path
from itertools import combinations
import json,numpy as np,pandas as pd
from compute_variants import ROOT,A,O,MONTHS,REP,read,save,rankcorr

VARS=['Main','IQR','strict_obs','pair_dedup','AM','PM','fourweek']
HELD=['202511','202512','202607']
def jaccard(a,b):
 av=a.notna();bv=b.notna();both=av&bv
 sa=set(a.index[a.eq(True).fillna(False)]);sb=set(b.index[b.eq(True).fillna(False)])
 union=sa|sb;intersection=sa&sb;valid=set(both.index[both]);ca=sa&valid;cb=sb&valid;cu=ca|cb
 return {'candidate_count_a':len(sa),'candidate_count_b':len(sb),'intersection':len(intersection),'union':len(union),
         'Jaccard':len(intersection)/len(union) if union else np.nan,'common_evaluable_dongs':int(both.sum()),
         'intersection_common_valid':len(ca&cb),'union_common_valid':len(cu),
         'Jaccard_common_valid':len(ca&cb)/len(cu) if cu else np.nan,
         'candidate_union_not_common_evaluable':len(union-valid)}
def empty_jaccard():return {k:np.nan for k in jaccard(pd.Series([],dtype='boolean'),pd.Series([],dtype='boolean'))}
def recurrent(panel,months):
 t=panel[months];v=t.notna().sum(axis=1);k=t.eq(True).sum(axis=1,min_count=1).fillna(0).astype(int);r=k.div(v.where(v>0))
 assert (k<=v).all();return v,k,r

def run():
 daily=pd.concat([read(O/'checkpoints'/m/'variants.csv') for m in MONTHS],ignore_index=True)
 counts=pd.concat([read(O/'checkpoints'/m/'sample_counts.csv') for m in MONTHS],ignore_index=True)
 assert set(daily.variant)==set(VARS) and len(daily)==9*7*427
 assert not daily.duplicated(['variant','month','dong_code']).any()
 main=read(A/'monthly_dong_metrics.csv');ids=main[['dong_code','dong_code10','dong_name']].drop_duplicates().set_index('dong_code').sort_index()
 f1b=read(ROOT/'f1c_sources/F1B/dong_replication_metrics.csv').set_index('dong_code').reindex(ids.index)
 allpanels={v:daily[daily.variant.eq(v)].pivot(index='dong_code',columns='month',values='candidate').reindex(ids.index) for v in VARS}
 vmain,kmain,rmain=recurrent(allpanels['Main'],REP)
 assert np.array_equal(vmain,f1b.V_rep) and np.array_equal(kmain,f1b.K_rep)
 assert np.allclose(rmain,f1b.R_rep,equal_nan=True)
 high=ids.loc[kmain.eq(8)].copy();assert len(high)==9
 monthly=[];overlaps=[];four=[]
 for m in MONTHS:
  benchmark=daily[(daily.variant=='Main')&(daily.month==m)].set_index('dong_code').reindex(ids.index)
  mainrho,_=rankcorr(benchmark.C2_count,benchmark.U_sec)
  for v in VARS:
   t=daily[(daily.variant==v)&(daily.month==m)].set_index('dong_code').reindex(ids.index)
   c=counts[(counts.variant==v)&(counts.month==m)].iloc[0].to_dict()
   status=t.status.iloc[0];valid=t.U_sec.notna()&t.C2_count.notna()
   rho,n=rankcorr(t.C2_count,t.U_sec);ucorr,un=rankcorr(benchmark.U_sec,t.U_sec);ccorr,cn=rankcorr(benchmark.C2_count,t.C2_count)
   calculated=status=='calculated'
   jc=jaccard(benchmark.candidate,t.candidate) if calculated else empty_jaccard()
   samedir=np.nan if pd.isna(rho) or pd.isna(mainrho) else bool(np.sign(rho)==np.sign(mainrho))
   row={**c,'role':'design_month_auxiliary' if m=='202608' else 'main_replication',
        'valid_U_dongs':int(t.U_sec.notna().sum()) if calculated else np.nan,
        'valid_C2_dongs':int(t.C2_count.notna().sum()) if calculated else np.nan,
        'valid_both_dongs':int(valid.sum()) if calculated else np.nan,
        'candidate_NA_dongs':int(t.candidate.isna().sum()),'candidate_count':int(t.candidate.sum()) if calculated else np.nan,
        'C2_U_Spearman':rho,'C2_U_common_dongs':n if calculated else np.nan,'Main_C2_U_Spearman':mainrho,
        'same_C2_U_direction_as_Main':samedir,'Main_U_Spearman':ucorr,'Main_U_common_dongs':un if calculated else np.nan,
        'Main_C2_Spearman':ccorr,'Main_C2_common_dongs':cn if calculated else np.nan,
        'Main_candidate_Jaccard':jc['Jaccard'],'Main_candidate_Jaccard_common_valid':jc['Jaccard_common_valid']}
   monthly.append(row)
   overlaps.append({'comparison':'Main_vs_variant_same_month','variant':v,'scope':'monthly','month_a':m,'month_b':m,'status':status,**jc})
   if v=='fourweek':
    four.append({**row,'C2_U_Spearman_difference_fourweek_minus_calendar':rho-mainrho if calculated else np.nan})
 for m in HELD:
  for v in VARS:
   monthly.append({'month':m,'variant':v,'status':'held_date_Main','hold_reason':'Calendar Main held_date; no replacement with a robustness result',
                   'role':'held_NA','candidate_NA_dongs':427})
   h=ids.reset_index();h['month']=m;h['variant']=v;h['status']='held_date_Main';h['hold_reason']='held_date';
   for c in ['U_sec','C2_count','U_percentile','C2_percentile']:h[c]=np.nan
   h['candidate']=pd.Series(pd.NA,index=h.index,dtype='boolean');daily=pd.concat([daily,h],ignore_index=True)
  four.append({'month':m,'variant':'fourweek','status':'held_date_Main','hold_reason':'Calendar Main unavailable; robustness not used to replace Main','role':'held_NA'})
 monthly=pd.DataFrame(monthly).sort_values(['month','variant'])
 save(monthly,'robustness_monthly_summary.csv');save(daily.sort_values(['variant','dong_code','month']),'robustness_dong_month_metrics.csv')
 temporal=[];regions=[];distributions=[]
 scopes={'main_replication_8':REP,'january_excluded_7_QA':[m for m in REP if m!='202601'],'all_eligible_9_auxiliary':MONTHS}
 for v in VARS:
  full=allpanels[v]
  for scope,months in scopes.items():
   sub=monthly[(monthly.variant==v)&monthly.month.isin(months)]
   available=sub.loc[sub.status=='calculated','month'].tolist()
   pv,pk,pr=recurrent(full,months);mv,mk,mr=recurrent(allpanels['Main'],months)
   vm,km,rm=recurrent(allpanels['Main'],available) if available else (mv*0,mk*0,mr*np.nan)
   common=(pr.notna()&mr.notna());rfull,nfull=rankcorr(pr,mr);rmatched,nmatched=rankcorr(pr,rm)
   pairs=[];pairscommon=[]
   for a,b in combinations(available,2):
    jc=jaccard(full[a],full[b]);pairs.append(jc['Jaccard']);pairscommon.append(jc['Jaccard_common_valid'])
    overlaps.append({'comparison':'within_variant_month_pair','variant':v,'scope':scope,'month_a':a,'month_b':b,'status':'calculated',**jc})
   rhos=sub.loc[sub.status=='calculated','C2_U_Spearman'].dropna()
   table={'variant':v,'scope':scope,'scheduled_months':len(months),'calculated_months':len(available),'calculated_month_list':','.join(available),
          'C2_U_Spearman_median':rhos.median(),'C2_U_Spearman_min':rhos.min(),'C2_U_Spearman_max':rhos.max(),
          'positive_months':int((rhos>0).sum()),'negative_months':int((rhos<0).sum()),'zero_months':int((rhos==0).sum()),
          'candidate_month_pair_count':len(pairs),'candidate_pair_Jaccard_median':pd.Series(pairs,dtype=float).median(),
          'candidate_pair_Jaccard_min':pd.Series(pairs,dtype=float).min(),'candidate_pair_Jaccard_max':pd.Series(pairs,dtype=float).max(),
          'candidate_pair_Jaccard_common_valid_median':pd.Series(pairscommon,dtype=float).median(),
          'R_Spearman_vs_Main_full_scope':rfull,'R_comparison_valid_dongs':nfull,
          'R_Spearman_vs_Main_matched_calculated_months':rmatched,'R_matched_comparison_valid_dongs':nmatched,
          'Main_U_Spearman_monthly_median':sub.Main_U_Spearman.median(),'Main_U_Spearman_monthly_min':sub.Main_U_Spearman.min(),
          'Main_candidate_Jaccard_monthly_median':sub.Main_candidate_Jaccard.median(),
          'R_P25':pr.quantile(.25),'R_median':pr.median(),'R_P75':pr.quantile(.75),'R_P90':pr.quantile(.9),'R_max':pr.max(),
          'no_evaluable_dongs':int(pv.eq(0).sum()),'V_min':int(pv.min()),'V_max':int(pv.max())}
   temporal.append(table)
   reg=ids.copy();reg['variant']=v;reg['scope']=scope;reg['V']=pv;reg['K']=pk;reg['R']=pr
   reg['Main_V_full_scope']=mv;reg['Main_K_full_scope']=mk;reg['Main_R_full_scope']=mr
   reg['Main_V_matched_months']=vm;reg['Main_K_matched_months']=km;reg['Main_R_matched_months']=rm
   regions.append(reg.reset_index())
   for vn in sorted(set(pv)):
    for kn in range(vn+1):
     distributions.append({'variant':v,'scope':scope,'calculated_months':len(available),'V':vn,
                           'K':kn if vn else np.nan,'dong_count':int((pv.eq(vn)&pk.eq(kn)).sum()),'interpretation':'not_evaluable' if vn==0 else 'evaluated'})
   if scope=='main_replication_8':
    high[v+'_K']=pk;high[v+'_V']=pv;high[v+'_R']=pr
    high[v+'_candidate_months']=[','.join(m for m in months if pd.notna(full.at[c,m]) and bool(full.at[c,m])) for c in high.index]
 temporal=pd.DataFrame(temporal);save(temporal,'robustness_temporal_summary.csv')
 save(pd.DataFrame(overlaps),'robustness_candidate_overlap.csv')
 save(pd.concat(regions,ignore_index=True),'robustness_dong_replication_metrics.csv')
 save(pd.DataFrame(distributions),'robustness_recurrence_distribution.csv')
 save(high.reset_index(),'robustness_high_recurrence_regions.csv')
 coverage=read(O/'fourweek_input_coverage.csv')
 fc=pd.DataFrame(four).merge(coverage,on='month',how='left',suffixes=('','_coverage'),validate='one_to_one')
 save(fc.sort_values('month'),'robustness_4week_comparison.csv')
 # Check identities and absent-variant denominators without deriving any new cutoff.
 assert len(daily)==12*7*427
 assert daily[daily.month.isin(HELD)][['U_sec','C2_count','candidate']].isna().all().all()
 for variant in VARS:
  t=temporal[(temporal.variant==variant)&(temporal.scope=='main_replication_8')].iloc[0]
  rr=pd.concat(regions,ignore_index=True);rr=rr[(rr.variant==variant)&(rr.scope=='main_replication_8')]
  assert len(rr)==427 and (rr.K<=rr.V).all()
  if variant=='strict_obs':assert t.calculated_months==4
  elif variant=='fourweek':assert t.calculated_months==6
  else:assert t.calculated_months==8
 for m in MONTHS:
  restored=json.loads((O/'checkpoints'/m/'restoration_verification.json').read_text())
  assert restored['Main_P50_P90_positive_days_reconciled']
 assert main.set_index(['month','dong_code']).candidate.sort_index().equals(
  daily[(daily.variant=='Main')&~daily.month.isin(HELD)].set_index(['month','dong_code']).candidate.sort_index())
 qa={'status':'PASS','Main_unchanged':True,'F1B_Main_K_V_R_reconciled':True,'calendar_Core_P50_P90_positive_days_reconciled_all_9':True,
     'IQR_numpy_sample_checks_each_month':1000,'Main_dong_frame':427,'held_months_NA_preserved':True,
     'strict_obs_calculated_replication_months':4,'fourweek_calculated_replication_months':6,
     'new_candidate_cutoff':False,'January_13_14_removed':False,'external_data_joined':False,
     'frozen_policy_master_spatial_preCore_keys_reused':True,'fourweek_not_restricted_to_calendar_Main_Core':True,
     'versions':{'numpy':np.__version__,'pandas':pd.__version__}}
 (O/'verification_results.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n')
 print(temporal[temporal.scope=='main_replication_8'].to_string(index=False))
 print('HIGH_RECURRENCE\n',high[[x for x in high if x.endswith('_K') or x.endswith('_V')]+['dong_name']].to_string(index=False))
 print('ASSEMBLY_QA_PASS')

if __name__=='__main__':run()
