"""Read raw identification columns only; certify master join readiness."""
import json,pickle,hashlib,zipfile,collections,concurrent.futures
from pathlib import Path
import pandas as pd,numpy as np
R=Path(__file__).resolve().parent.parent;O=R/'f0m_results';W=R/'f0m_work';SX=R/'f0m_sources/sx/f0sx_results'
# Submission adapter: paths only; the original calculation statements follow.
from seoul_bus_paths import bind as _submission_bind
globals().update(_submission_bind('F0M'))
with open(W/'masters.pkl','rb') as f:PAY=pickle.load(f)
MAP=PAY['mapping'];MA=PAY['masters']
for d,a in MA.items():a['string_triples']={'|'.join(t) for t in a['triples']}
CAL=pd.read_csv(SX/'day_calendar.csv',dtype={'date':str,'month':str});DAYS=set(CAL.loc[CAL.common_planned_day,'date'])
MF=pd.read_csv(SX/'csv_source_manifest.csv',dtype=str,keep_default_na=False)
archive={}
for p in list((R/'f0m_sources/raw').rglob('*.zip'))+list((R/'upload').glob('*.zip'))+[R/n for n in ['counts_week.zip','counts_w2.zip','counts_w3.zip','counts_w4.zip']]:
 if p.exists():
  with open(p,'rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
  archive[h]=p
missing=set(MF.zip_sha256)-set(archive);assert not missing,missing
joblist=[{'source_id':r.source_id,'kind':r.kind,'path':str(archive[r.zip_sha256]),'member':r.member} for r in MF.itertuples()]
(O/'raw_identification_source_manifest.json').write_text(json.dumps(joblist,ensure_ascii=False,indent=2))
def job(j):
 roles=['출발','도착'] if j['kind']=='time' else ['']
 # count column names recovered from the audited CSV header, never value columns.
 z=zipfile.ZipFile(j['path']);header=pd.read_csv(z.open(j['member']),encoding='cp949',nrows=0).columns.tolist()
 date='기준_날짜';rid='노선_ID'
 if j['kind']=='time':spec=[('departure','출발_정류장_ID','출발_정류장_순서'),('arrival','도착_정류장_ID','도착_정류장_순서')]
 else:
  node=next(c for c in header if c in ('정류장_ID','정류소_ID'));seq=next(c for c in header if c in ('정류장_순서','정류소_순서'));spec=[('stop',node,seq)]
 cols=[date,rid]+[c for _,n,s in spec for c in (n,s)];acc=collections.defaultdict(collections.Counter)
 for df in pd.read_csv(z.open(j['member']),encoding='cp949',usecols=cols,dtype=str,keep_default_na=False,chunksize=150000):
  for month,q in df.groupby(df[date].str[:6],sort=False):
   if month not in MAP:continue
   a=MA[MAP[month]];common=q[date].isin(DAYS).to_numpy();pol=q[rid].isin(a['allowed']).to_numpy();known=q[rid].isin({r for r,t in a['types'].items() if t}).to_numpy()
   masks={'calendar_all_raw_rows':np.ones(len(q),bool),'common_planned_all_raw_rows':common,'common_planned_policy_ID_raw_rows':common&pol}
   checks={'route_match':q[rid].isin(a['routes']).to_numpy(),'route_type_verified':known,'policy_ID':pol}
   for role,n,s in spec:
    checks.update({role+'_location_match':q[n].isin(a['location_nodes']).to_numpy(),role+'_route_stop_NODE_match':q[n].isin(a['route_stop_nodes']).to_numpy(),role+'_route_stop_sequence_match':(q[rid]+'|'+q[n]+'|'+q[s]).isin(a['string_triples']).to_numpy(),role+'_coordinate_available':q[n].isin(a['coordinate_available']).to_numpy(),role+'_coordinate_ready':q[n].isin(a['coordinate_ready']).to_numpy(),role+'_coordinate_held':q[n].isin(a['coordinate_held']).to_numpy(),role+'_inside_seoul':q[n].isin(a['inside_seoul']).to_numpy()})
   for scope,mask in masks.items():
    c=acc[(month,j['kind'],scope)];c['raw_rows']+=int(mask.sum())
    for name,flag in checks.items():c[name]+=int((mask&flag).sum())
 rows=[dict(month=m,kind=k,denominator_scope=s,**c) for (m,k,s),c in acc.items()]
 (W/f"match_{int(j['source_id']):03}.json").write_text(json.dumps(rows));return j['source_id']
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  for i,s in enumerate(pool.map(job,joblist),1):
   if i%10==0:print('completed',i,'/',len(joblist),flush=True)
 total=collections.defaultdict(collections.Counter)
 for j in joblist:
  for row in json.loads((W/f"match_{int(j['source_id']):03}.json").read_text()):
   key=tuple(row.pop(c) for c in ('month','kind','denominator_scope'));total[key].update(row)
 records=[]
 for (m,k,s),c in sorted(total.items()):
  row=dict(month=m,snapshot=MAP[m],kind=k,denominator_scope=s,**c)
  for n,v in c.items():
   if n!='raw_rows':row[n+'_pct']=100*v/c['raw_rows'] if c['raw_rows'] else np.nan
  for role in (['departure','arrival'] if k=='time' else ['stop']):row[role+'_coordinate_missing_pct']=100-row[role+'_coordinate_available_pct']
  records.append(row)
 pd.DataFrame(records).to_csv(O/'master_match_rates.csv',index=False,encoding='utf-8-sig')
 assert len(records)==72
 print('MATCH_RATE_COMPLETE',flush=True)
