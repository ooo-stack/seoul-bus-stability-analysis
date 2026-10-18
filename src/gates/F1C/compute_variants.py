"""Specified F1C robustness, using frozen F1A Core and unchanged Main C2."""
from pathlib import Path
import json,math,numpy as np,pandas as pd

ROOT=Path(__file__).resolve().parent.parent
A=ROOT/'f1c_sources/F1A/f1a_results'
O=Path(__file__).resolve().parent
# Submission adapter: paths only; the original calculation statements follow.
from seoul_bus_paths import bind as _submission_bind
globals().update(_submission_bind('F1C'))
MONTHS=['202509','202510','202601','202602','202603','202604','202605','202606','202608']
REP=MONTHS[:-1]
K=['노선_ID','출발_정류장_ID','도착_정류장_ID','출발_정류장_순서','도착_정류장_순서']
DT={'month':str,'dong_code':str,'dong_code10':str,'candidate':'boolean'}
def read(p,**kw):return pd.read_csv(p,dtype=DT,float_precision='round_trip',**kw)
def save(d,n):d.to_csv(O/n,index=False,encoding='utf-8-sig',na_rep='',float_format='%.17g')
def rankcorr(x,y):
 q=pd.concat([x.rename('x'),y.rename('y')],axis=1).dropna().round(8)
 if len(q)<2 or q.x.nunique()<2 or q.y.nunique()<2:return np.nan,len(q)
 return q.x.rank(method='average').corr(q.y.rank(method='average')),len(q)
def flags(t,field='U_sec'):
 t=t.copy();t['U_percentile']=t[field].round(8).rank(method='average',pct=True)*100
 t['C2_percentile']=t.C2_count.round(8).rank(method='average',pct=True)*100
 t['U_percentile_denominator']=t[field].notna().sum();t['C2_percentile_denominator']=t.C2_count.notna().sum()
 both=t[field].notna()&t.C2_count.notna();t['candidate']=pd.Series(pd.NA,index=t.index,dtype='boolean')
 t.loc[both,'candidate']=(t.loc[both,'U_percentile']>=75)&(t.loc[both,'C2_percentile']>=75)
 return t
def supply(rs,a,hours):
 q=pd.DataFrame({'dong_code':rs.dong_code,'node_id':rs.node_id,'sum':pd.DataFrame(a[:,hours]).sum(axis=1,min_count=1)})
 st=q.groupby(['dong_code','node_id'])['sum'].sum(min_count=1)
 return st.groupby(level=0).median()
def stored_month(m):
 d=read(A/'monthly_dong_metrics.csv');main=d[d.month.eq(m)].set_index('dong_code')
 cfg=json.loads((A/'input_contract.json').read_text())['configs'][m]
 p=A/'core_checkpoints'/m
 keys=pd.read_csv(p/'segment_keys.csv.gz',dtype=str,keep_default_na=False)
 z=np.load(p/'segment_hour_core.npz')
 si=z['segment_index'];h=z['hour'];strict=z['strict']
 base=pd.DataFrame({'segment_index':si[strict],'hour':h[strict],'U':z['U'][strict],
                     'dep_node':keys['출발_정류장_ID'].iloc[si[strict]].to_numpy(),
                     'arr_node':keys['도착_정류장_ID'].iloc[si[strict]].to_numpy(),
                     'dong_code':keys.arr_dong_code.iloc[si[strict]].to_numpy()})
 recovered=base.groupby('dong_code').U.median().reindex(main.index)
 assert np.allclose(recovered,main.U_sec,equal_nan=True,atol=1e-11)
 rs=pd.read_csv(p/'supply_route_stop_keys.csv.gz',dtype=str,keep_default_na=False)
 supplyz=np.load(p/'supply_route_stop_hour.npz')['representative_count']
 assert np.allclose(supply(rs,supplyz,list(range(24))).reindex(main.index),main.C2_count,equal_nan=True,atol=1e-10)
 results=[];counts=[]
 def emit(name,groups,combos,policycount,status='calculated',reason='',C2=None):
  t=main[['dong_code10','dong_name','month','C2_count']].copy()
  t['variant']=name;t['status']=status;t['hold_reason']=reason
  if status!='calculated':
   t['U_sec']=np.nan;t['C2_count']=np.nan
  else:
   t['U_sec']=groups.reindex(t.index)
   if C2 is not None:t['C2_count']=C2.reindex(t.index)
  t=flags(t);results.append(t.reset_index())
  counts.append({'month':m,'variant':name,'status':status,'hold_reason':reason,'policy_Core_combinations':policycount,
                 'strict_Core_combinations':len(base) if name=='pair_dedup' else combos,
                 'aggregation_units':combos,'N_planned':cfg['N'],'common_days':len(cfg['days']),
                 'L_variant':max(16,math.ceil(18*cfg['N']/19)) if name=='strict_obs' else cfg['L']})
 emit('Main',recovered,len(base),len(si))
 # Stricter observation condition is a sub-sample of Main Core; C2 is Main-fixed.
 L=max(16,math.ceil(18*cfg['N']/19))
 if len(cfg['days'])<L:
  emit('strict_obs',pd.Series(dtype=float),np.nan,np.nan,'held_observation_days',f'common_days={len(cfg["days"])} < L_strict={L}')
 else:
  mask=z['positive_days']>=L;bs=base[mask[strict]]
  emit('strict_obs',bs.groupby('dong_code').U.median(),len(bs),int(mask.sum()))
 dedup=base.groupby(['dep_node','arr_node','hour','dong_code'],as_index=False).U.median()
 emit('pair_dedup',dedup.groupby('dong_code').U.median(),len(dedup),len(si))
 for name,hours in [('AM',[7,8,9]),('PM',[17,18,19])]:
  bh=base[base.hour.isin(hours)]
  emit(name,bh.groupby('dong_code').U.median(),len(bh),int(np.isin(h,hours).sum()),C2=supply(rs,supplyz,hours))
 iqrfile=O/'checkpoints'/m/'IQR_core.npz'
 if iqrfile.exists():
  iq=np.load(iqrfile)
  assert np.array_equal(iq['segment_index'],si) and np.array_equal(iq['hour'],h)
  iqframe=base[['dong_code']].copy();iqframe['IQR']=iq['IQR'][strict]
  emit('IQR',iqframe.groupby('dong_code').IQR.median(),len(base),len(si))
 weekfile=O/'checkpoints'/m/'fourweek_dong.csv'
 if weekfile.exists():
  w=read(weekfile);results.append(w)
  counts.append(json.loads((weekfile.parent/'fourweek_counts.json').read_text()))
 out=O/'checkpoints'/m;out.mkdir(parents=True,exist_ok=True)
 save(pd.concat(results,ignore_index=True),f'checkpoints/{m}/variants.csv')
 save(pd.DataFrame(counts),f'checkpoints/{m}/sample_counts.csv')
 print('VARIANTS_DONE',m,flush=True)
 return m

if __name__=='__main__':
 import sys
 for m in ([sys.argv[1]] if len(sys.argv)>1 else MONTHS):stored_month(m)
