"""Independent statistical checks on exported F1C files. SciPy is QA-only."""
from pathlib import Path
import json,zipfile,numpy as np,pandas as pd
from scipy.stats import spearmanr
from compute_variants import O,ROOT,MONTHS

d=pd.read_csv(O/'robustness_dong_month_metrics.csv',dtype={'month':str,'dong_code':str,'candidate':'boolean'},float_precision='round_trip')
s=pd.read_csv(O/'robustness_monthly_summary.csv',dtype={'month':str},float_precision='round_trip');n=0
for (m,v),q in d.groupby(['month','variant']):
 both=q.U_sec.notna()&q.C2_count.notna();assert q.candidate.isna().equals(~both)
 expected=((q.U_sec.round(8).rank(method='average',pct=True)*100>=75)&(q.C2_count.round(8).rank(method='average',pct=True)*100>=75)).astype('boolean').mask(~both,pd.NA)
 assert q.candidate.equals(expected),(m,v)
 t=q[both];row=s[(s.month==m)&(s.variant==v)].iloc[0]
 if len(t)>1:
  value=spearmanr(t.U_sec.round(8),t.C2_count.round(8)).statistic
  assert np.isclose(value,row.C2_U_Spearman,atol=1e-12),(m,v)
  assert len(t)==row.valid_both_dongs and int(t.candidate.sum())==row.candidate_count;n+=1
 else:assert pd.isna(row.C2_U_Spearman) and pd.isna(row.candidate_count)
for m in MONTHS:
 main=d[(d.month==m)&(d.variant=='Main')].set_index('dong_code').C2_count
 for v in ['IQR','strict_obs','pair_dedup']:
  q=d[(d.month==m)&(d.variant==v)].set_index('dong_code')
  if q.status.iloc[0]=='calculated':assert np.allclose(q.C2_count,main,equal_nan=True)
npz_count=0
for p in (O/'checkpoints').glob('*/*.npz'):
 with zipfile.ZipFile(p) as z:assert z.testzip() is None,p
 npz_count+=1
f1b=pd.read_csv(ROOT/'f1c_sources/F1B/dong_replication_metrics.csv',dtype={'dong_code':str},float_precision='round_trip').set_index('dong_code')
rep=pd.read_csv(O/'robustness_dong_replication_metrics.csv',dtype={'dong_code':str},float_precision='round_trip')
for scope,suffix in [('main_replication_8','rep'),('january_excluded_7_QA','rep_noJan'),('all_eligible_9_auxiliary','all')]:
 t=rep[(rep.variant=='Main')&(rep.scope==scope)].set_index('dong_code').reindex(f1b.index)
 for col in ['K','V','R']:assert np.allclose(t[col],f1b[col+'_'+suffix],equal_nan=True)
evidence={'status':'PASS','independent_scipy_monthly_Spearman_count':n,'all_exported_candidates_and_NA_verified':True,
          'C2_fixed_where_specified':True,'derived_NPZ_CRC_checked':npz_count,'F1B_Main_noJan_all_period_K_V_R_preserved':True}
(O/'additional_verification.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
print('ADDITIONAL_VERIFICATION_PASS',n,npz_count)
