from pathlib import Path
import json,gzip,hashlib
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parent;C=ROOT.parent/'m1_work/f1a_results/core_checkpoints'
# Submission adapter: paths only; the original calculation statements follow.
from seoul_bus_paths import bind as _submission_bind
globals().update(_submission_bind('M1'))
MAIN=['202509','202510','202601','202602','202603','202604','202605','202606']
AK=['dong_code','route_id','departure_node','arrival_node'];BK=['dong_code','departure_node','arrival_node']
hour=pd.read_csv(ROOT/'analysis_inputs/target_hour_core.csv.gz',dtype={c:str for c in ['month','dong_code','route_id','departure_node','arrival_node','departure_sequence','arrival_sequence']},low_memory=False)
ref=pd.read_csv(ROOT/'analysis_inputs/strict_U_reference.csv.gz',dtype={'month':str})
samples=[]
for m,g in hour.groupby('month',sort=True):
 keys=pd.read_csv(C/m/'segment_keys.csv.gz',dtype=str,keep_default_na=False)
 a=np.load(C/m/'segment_hour_core.npz');v=a['strict'];targets=keys.arr_dong_code.iloc[a['segment_index']].isin(set(hour.dong_code)).to_numpy()&v
 assert len(g)==int(targets.sum())
 for col,array in [('U_sec','U'),('P50_sec','P50'),('P90_sec','P90'),('positive_days','positive_days')]:assert np.allclose(g[col],a[array][targets],rtol=0,atol=1e-10)
 u=np.round(a['U'][v],8);r=ref[ref.month.eq(m)];x,c=np.unique(u,return_counts=True)
 assert np.array_equal(x,r.U_rounded) and np.array_equal(c,r.frequency)
 assert int(r.frequency.sum())==int(v.sum())
 # Independent full-reference mean tie ranks, then compare sampled original hour rows.
 rank=pd.Series(u).rank(method='average',pct=True).to_numpy()*100
 inds=np.flatnonzero(targets[v]);n=min(1000,len(inds));idx=np.linspace(0,len(inds)-1,n,dtype=int)
 assert np.allclose(g.U_hour_percentile.iloc[idx],rank[inds[idx]],rtol=0,atol=1e-10)
 samples.append({'month':m,'hour_rows_U_P50_P90_reconciled':len(g),'independent_rank_samples':n})
for monthly,rec,keys in [('route_segment_monthly_instability.csv','route_segment_recurrence.csv',AK),('stop_pair_monthly_instability.csv','stop_pair_recurrence.csv',BK)]:
 p=pd.read_csv(ROOT/monthly,dtype={c:str for c in keys+['month']});rr=pd.read_csv(ROOT/rec,dtype={c:str for c in keys})
 assert not p.duplicated(keys+['month']).any()
 assert p.loc[p.month.isin(['202511','202512','202607']),['U_sec','U_percentile','high_instability_month']].isna().all().all()
 lookup={key:g for key,g in p.groupby(keys,sort=False)}
 for row in rr.itertuples(index=False):
  g=lookup[tuple(getattr(row,k) for k in keys)]
  for months,suf in [(MAIN,''),([m for m in MAIN if m!='202601'],'_noJan')]:
   q=g[g.month.isin(months)];V=int(q.U_sec.notna().sum());K=int(q.loc[q.U_sec.notna(),'high_instability_month'].eq(True).sum())
   assert V==getattr(row,'V'+suf) and K==getattr(row,'K'+suf)
   R=getattr(row,'R'+suf);assert pd.isna(R) if V==0 else abs(R-K/V)<1e-9
  valid=g[g.U_sec.notna()]
  assert valid.high_instability_month.eq(valid.U_percentile.ge(75)).all()
  for m,v in valid.groupby('month'):
   r=ref[ref.month.eq(m)];assert v.U_sec.min()>=r.U_rounded.min()-1e-7 and v.U_sec.max()<=r.U_rounded.max()+1e-7
con=pd.read_csv(ROOT/'dong_segment_concentration.csv');a=pd.read_csv(ROOT/'route_segment_recurrence.csv',dtype={'dong_code':str});kdist=pd.read_csv(ROOT/'segment_K_distribution.csv',dtype={'dong_code':str})
for row in con.itertuples(index=False):
 code=str(row.dong_code);g=a[a.dong_code.eq(code)&a.V.gt(0)]
 assert len(g)==row.analyzable_route_segments and int(g.K.gt(0).sum())==row.ever_high_route_segments
 assert int(kdist[kdist.dong_code.eq(code)&kdist.unit_type.eq('route_segment')].units.sum())==len(g)
for p in ROOT.rglob('*.gz'):
 with gzip.open(p,'rb') as f:
  while f.read(1024*1024):pass
assert len(con)==9 and set(con.dong_name)=={'소공동','필동','신림동','신사동(강남구)','대치2동','개포1동','잠실본동','잠실6동','잠실7동'}
out={'status':'PASS','Core_values_and_global_reference_reconciled':samples,'all_recurrences_independently_counted':True,'held_NA_preserved':True,'9_target_dongs_unchanged':True,'compressed_files_integrity':'PASS','value_conflicts_not_resolved_again':True}
(ROOT/'verification_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False))
