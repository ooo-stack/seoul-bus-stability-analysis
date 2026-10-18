"""QA only: identify date/type observation scarcity under unchanged filters."""
from run_month import ALL,VC,K,O
import pandas as pd,numpy as np,zipfile,collections
cfg=ALL['config']['202601'];ma=ALL['masters'][cfg['snapshot']];days=set(cfg['days']);acc=collections.defaultdict(collections.Counter)
for job in cfg['jobs']:
 if job['kind']!='time':continue
 cols=['기준_날짜']+K['time']+VC['time'];dtype={c:str for c in ['기준_날짜']+K['time']};dtype.update({c:np.float64 for c in VC['time']});z=zipfile.ZipFile(job['path'])
 for q in pd.read_csv(z.open(job['member']),encoding='cp949',usecols=cols,dtype=dtype,keep_default_na=False,na_values={c:[''] for c in VC['time']},chunksize=100000):
  q=q[q['기준_날짜'].isin(days)].copy();drop=ALL['skip'].get(job['source_id'],{});q=q[~(q.index+2).isin(drop)].copy();q=q[q['노선_ID'].isin(ma['allowed'])].copy()
  q=q[(q['도착_정류장_순서'].astype(int)-q['출발_정류장_순서'].astype(int)==1)&q['출발_정류장_순서'].astype(int).gt(0)&~(q['출발_정류장_순서'].eq('2')&q['도착_정류장_순서'].eq('3'))].copy()
  match=(q['노선_ID']+'|'+q['출발_정류장_ID']+'|'+q['출발_정류장_순서']).isin(ma['triples'])&(q['노선_ID']+'|'+q['도착_정류장_ID']+'|'+q['도착_정류장_순서']).isin(ma['triples']);q=q[match].copy();q['type']=q['노선_ID'].map(ma['types'])
  for key,a in q.groupby(['기준_날짜','type']):
   v=a[VC['time']].to_numpy();c=acc[key];c['rows']+=len(a);c['hour_cells']+=v.size;c['positive_cells']+=int((v>0).sum());c['zero_cells']+=int((v==0).sum());c['positive_at_least_one_hour_rows']+=int((v>0).any(axis=1).sum())
rows=[{'month':'202601','date':d,'route_type':t,**c,'positive_cell_pct':100*c['positive_cells']/c['hour_cells']} for (d,t),c in sorted(acc.items())];pd.DataFrame(rows).to_csv(O/'january_date_type_observation_QA.csv',index=False,encoding='utf-8-sig');print(pd.DataFrame(rows).pivot(index='date',columns='route_type',values='positive_cell_pct').round(2).to_string())
