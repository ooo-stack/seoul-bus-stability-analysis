"""Restore frozen pre-Core keys, IQR, and the prespecified 4-week sensitivity.

All 4-week planned weekdays are a subset of their frozen calendar month days.
Therefore the frozen pre-Core key frame supplies the same policy/master keys,
including keys that failed the calendar repetition filter. No Main-Core-only
restriction is imposed on the 4-week sensitivity.
"""
from pathlib import Path
import json,pickle,zipfile,hashlib,math,collections,warnings,time,os
import pandas as pd,numpy as np
from compute_variants import ROOT,A,O,MONTHS,K,read,flags,save,supply
W=ROOT/'f1c_work';SX=ROOT/'f1c_sources/F0SX/f0sx_results'
VC={'time':[f'운행시간_{h:02}시' for h in range(24)],'count':[f'버스운행횟수_{h:02}시' for h in range(24)]}
CK=['노선_ID','정류장_ID','정류장_순서']
def sha(p):
 with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(o,p):p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def atomic_npz(p,**arrays):
 tmp=p.with_suffix('.writing.npz')
 with open(tmp,'wb') as f:
  np.savez_compressed(f,**arrays);f.flush();os.fsync(f.fileno())
 with zipfile.ZipFile(tmp) as z:assert z.testzip() is None
 tmp.replace(p)
def linear(a,n,p):
 t=(n-1)*p;lo=np.floor(t).astype(int);hi=np.ceil(t).astype(int);f=t-lo;ix=np.arange(len(n));x=a[ix,lo];y=a[ix,hi];d=y-x;v=x+d*f;ii=f>=.5;v[ii]=y[ii]-d[ii]*(1-f[ii]);return v
def prepare():
 W.mkdir(parents=True,exist_ok=True)
 contract=json.loads((A/'input_contract.json').read_text());mf=pd.read_csv(SX/'csv_source_manifest.csv',dtype=str,keep_default_na=False)
 dates=pd.read_csv(SX/'file_schema_and_dates.csv',dtype={'source_id':str})
 mf=mf.merge(dates[['source_id','dates_json']],on='source_id',validate='one_to_one')
 sources={r.source_id:{'source_id':r.source_id,'kind':r.kind,'zip_sha256':r.zip_sha256,'member':r.member,
                      'csv_sha256':r.csv_sha256,'columns':json.loads(r.columns),'dates':json.loads(r.dates_json)} for r in mf.itertuples()}
 archives={}
 candidates=list((ROOT/'f1c_sources/raw').rglob('*.zip'))+list((ROOT/'upload').glob('*.zip'))+[ROOT/n for n in ['counts_week.zip','counts_w2.zip','counts_w3.zip','counts_w4.zip']]
 for p in candidates:
  if p.is_file():archives[sha(p)]=str(p.resolve())
 dup=pd.read_csv(SX/'duplicate_raw_rows.csv',dtype=str,keep_default_na=False);groups=collections.defaultdict(list)
 for row in dup.itertuples():
  raw=json.loads(row.raw_cells_json);key=['기준_날짜']+(K if row.kind=='time' else CK)
  groups[(row.kind,tuple(raw[k] for k in key))].append((row.source_id,int(row.source_row),raw))
 skip=collections.defaultdict(dict)
 for (kind,key),rows in groups.items():
  variants=collections.defaultdict(list)
  for sid,row,raw in rows:variants[tuple(raw[c] for c in sources[sid]['columns'])].append((sid,row))
  canonical=[]
  for values in variants.values():
   values.sort(key=lambda x:(sources[x[0]]['zip_sha256'],sources[x[0]]['member'],x[1]));canonical.append(values[0])
   for sid,row in values[1:]:skip[sid][row]='exact_duplicate'
  if len(canonical)>1:
   for sid,row in canonical:skip[sid][row]='conflict_pending'
 cal=pd.read_csv(A/'reference/day_calendar.csv',dtype={'month':str,'date':str})
 configs={};coverage=[];selected={}
 for m in MONTHS:
  cfg=contract['configs'][m];start=pd.Timestamp(m+'01');start+=pd.Timedelta(days=(7-start.weekday())%7);end=start+pd.Timedelta(days=27)
  window=cal[cal.date.between(start.strftime('%Y%m%d'),end.strftime('%Y%m%d'))];plan=window[window.planned_weekday];common=window[window.common_planned_day];N=len(plan);D=len(common);L=max(16,math.ceil(16*N/19));wk=plan.groupby('week_start').size();mins={k:min(3,int(v)) for k,v in wk.items()}
  missing=plan.loc[~plan.common_planned_day,'date'].tolist();weekpass=all(common.groupby('week_start').size().get(k,0)>=v for k,v in mins.items())
  ready=D>=math.ceil(.9*N) and D>=L and weekpass
  assert set(common.date).issubset(cfg['days']), '4-week dates outside frozen calendar-month pre-Core roster; rebuild from master required'
  w={'month':m,'start':start.strftime('%Y%m%d'),'end':end.strftime('%Y%m%d'),'N':N,'L':L,'days':common.date.tolist(),
     'week_min':mins,'day_weeks':dict(zip(window.date,window.week_start)),'eligible':ready,
     'reason':'' if ready else 'held_date: frozen coverage and/or weekly conditions not met'}
  configs[m]={'calendar':cfg,'fourweek':w}
  coverage.append({'month':m,'window_start':w['start'],'window_end':w['end'],'snapshot':cfg['snapshot'],'N_planned':N,
                   'time_planned_days':int(plan.time_present.sum()),'count_planned_days':int(plan.count_present.sum()),
                   'common_days':D,'coverage_minimum':math.ceil(.9*N),'L_main':L,'weekly_date_condition':weekpass,
                   'status':'calculated' if ready else 'held_date','missing_common_dates':','.join(missing),
                   'weekly_requirements_json':json.dumps(mins),'hold_reason':w['reason']})
  for job in cfg['jobs']:
   needed=cfg['days'] if job['kind']=='time' else (w['days'] if ready else [])
   if set(needed)&set(job['dates']):
    assert job['source_id'] in sources
    assert job['zip_sha256'] in archives,Path(job['path']).name
    assert job['csv_sha256']==sources[job['source_id']]['csv_sha256']
    selected[job['source_id']]={**sources[job['source_id']],'path':archives[job['zip_sha256']]}
 with open(W/'restoration_contract.pkl','wb') as f:pickle.dump({'configs':configs,'sources':selected,'skip':dict(skip)},f)
 save(pd.DataFrame(coverage),'fourweek_input_coverage.csv')
 dump({'configs':configs,'sources':list(selected.values()),'master_policy_space_source':'F1A frozen pre-Core segment keys; same snapshot and coordinates',
       'fourweek_dates_subset_of_calendar_dates_verified':True},O/'restoration_input_manifest.json')
 for r in [A,ROOT/'f1c_sources/F0SX/f0sx_results',ROOT/'f1c_sources/F0M/f0m_results']:
  manifest=json.loads((r/'deliverable_manifest.json').read_text())
  for p in r.rglob('*'):
   name=str(p.relative_to(r))
   if p.is_file() and name in manifest:assert sha(p)==manifest[name],name
 print('INPUT_VERIFIED',len(selected),'CSV members',len(set(j['zip_sha256'] for j in selected.values())),'ZIPs',flush=True)

def run(m):
 began=time.time()
 with open(W/'restoration_contract.pkl','rb') as f:cfgs=pickle.load(f)
 cfg=cfgs['configs'][m]['calendar'];wc=cfgs['configs'][m]['fourweek'];days=cfg['days'];di={d:i for i,d in enumerate(days)}
 sources=[j for j in cfgs['sources'].values() if j['source_id'] in {x['source_id'] for x in cfg['jobs']}]
 keys=pd.read_csv(A/'core_checkpoints'/m/'segment_keys.csv.gz',dtype=str,keep_default_na=False)
 z=np.load(A/'core_checkpoints'/m/'segment_hour_core.npz');index={tuple(k):i for i,k in enumerate(keys[K].itertuples(index=False,name=None))}
 panel=np.full((len(keys),len(days),24),np.nan);present=np.zeros((len(keys),len(days)),bool);seen_dates={'time':set(),'count':set()};ledgers=[]
 def batches(kind,needed):
  for job in sources:
   if job['kind']!=kind or not (set(needed)&set(job['dates'])):continue
   kk=K if kind=='time' else CK;cols=['기준_날짜']+kk+VC[kind];dt={k:str for k in ['기준_날짜']+kk};dt.update({k:np.float64 for k in VC[kind]})
   with zipfile.ZipFile(job['path']) as zipf:
    for q in pd.read_csv(zipf.open(job['member']),encoding='cp949',usecols=cols,dtype=dt,keep_default_na=False,
                         na_values={k:[''] for k in VC[kind]},chunksize=100000):
     q=q[q['기준_날짜'].isin(needed)].copy();seen_dates[kind].update(q['기준_날짜'])
     reason=pd.Series((q.index+2).map(cfgs['skip'].get(job['source_id'],{})),index=q.index)
     if reason.notna().any():ledgers.append({'month':m,'kind':kind,'source_id':job['source_id'],
            'exact_duplicate_removed':int(reason.eq('exact_duplicate').sum()),'conflict_rows_held':int(reason.eq('conflict_pending').sum())})
     q=q[reason.isna()]
     if len(q):yield q
 for q in batches('time',days):
  ix=np.fromiter((index.get(k,-1) for k in q[K].itertuples(index=False,name=None)),np.int32,len(q));match=ix>=0
  ix=ix[match];dx=q.loc[match,'기준_날짜'].map(di).to_numpy(np.int32);a=q.loc[match,VC['time']].to_numpy()
  assert len(np.unique(ix*len(days)+dx))==len(ix) and not present[ix,dx].any(),'Unresolved time duplicate'
  a[(a<=0)|~np.isfinite(a)]=np.nan;panel[ix,dx]=a;present[ix,dx]=True
 assert seen_dates['time']==set(days)
 si=z['segment_index'];h=z['hour'];X=panel.transpose(0,2,1)[si,h];n=np.isfinite(X).sum(axis=1);ordered=np.sort(np.where(np.isfinite(X),X,np.inf),axis=1)
 assert np.array_equal(n,z['positive_days'])
 assert np.allclose(linear(ordered,n,.5),z['P50'],atol=1e-10,rtol=1e-12)
 assert np.allclose(linear(ordered,n,.9),z['P90'],atol=1e-10,rtol=1e-12)
 iqr=linear(ordered,n,.75)-linear(ordered,n,.25)
 sample=np.linspace(0,len(X)-1,min(1000,len(X)),dtype=int)
 assert np.allclose(iqr[sample],np.nanquantile(X[sample],.75,axis=1,method='linear')-np.nanquantile(X[sample],.25,axis=1,method='linear'),atol=1e-10)
 out=O/'checkpoints'/m;out.mkdir(parents=True,exist_ok=True)
 atomic_npz(out/'IQR_core.npz',segment_index=si,hour=h,P25=linear(ordered,n,.25),P75=linear(ordered,n,.75),IQR=iqr)
 del X,ordered
 main=read(A/'monthly_dong_metrics.csv');main=main[main.month.eq(m)].set_index('dong_code')
 result=main[['dong_code10','dong_name','month']].copy();result['variant']='fourweek';result['status']='calculated' if wc['eligible'] else 'held_date';result['hold_reason']=wc['reason']
 count={'month':m,'variant':'fourweek','status':result.status.iloc[0],'hold_reason':wc['reason'],'N_planned':wc['N'],
        'common_days':len(wc['days']),'L_variant':wc['L'],'policy_Core_combinations':None,'strict_Core_combinations':None}
 if not wc['eligible']:
  result['U_sec']=np.nan;result['C2_count']=np.nan
 else:
  wi=[di[d] for d in wc['days']];p=panel[:,wi,:];valid=np.isfinite(p);nn=valid.sum(axis=1);core=nn>=wc['L']
  for week,minn in sorted(wc['week_min'].items()):
   ww=[i for i,d in enumerate(wc['days']) if wc['day_weeks'][d]==week];core&=valid[:,ww,:].sum(axis=1)>=minn
  si4,h4=np.where(core);X=p.transpose(0,2,1)[si4,h4];n4=nn[si4,h4];ss=np.sort(np.where(np.isfinite(X),X,np.inf),axis=1)
  u4=linear(ss,n4,.9)-linear(ss,n4,.5);strictkey=keys.dep_dong_code.ne('')&keys.arr_dong_code.ne('');st=strictkey.to_numpy()[si4]
  f=pd.DataFrame({'dong_code':keys.arr_dong_code.iloc[si4[st]].to_numpy(),'U':u4[st]})
  result['U_sec']=f.groupby('dong_code').U.median()
  atomic_npz(out/'fourweek_time_core.npz',segment_index=si4.astype(np.int32),hour=h4.astype(np.uint8),U=u4,
                      positive_days=n4.astype(np.uint8),strict=st)
  del X,ss,p,valid,panel
  ep=[]
  for node,seq,dong in [('출발_정류장_ID','출발_정류장_순서','dep_dong_code'),('도착_정류장_ID','도착_정류장_순서','arr_dong_code')]:
   a=keys.iloc[np.unique(si4)][['노선_ID',node,seq,dong]].copy();a.columns=['route_id','node_id','sequence','dong_code'];ep.append(a)
  roster=pd.concat(ep).drop_duplicates();roster=roster[roster.dong_code.ne('')].reset_index(drop=True)
  rind={k:i for i,k in enumerate(roster[['route_id','node_id','sequence']].itertuples(index=False,name=None))}
  wd={d:i for i,d in enumerate(wc['days'])};cp=np.full((len(roster),len(wd),24),np.nan);presentc=np.zeros((len(roster),len(wd)),bool)
  for q in batches('count',wc['days']):
   ix=np.fromiter((rind.get(k,-1) for k in q[CK].itertuples(index=False,name=None)),np.int32,len(q));match=ix>=0;ix=ix[match];dx=q.loc[match,'기준_날짜'].map(wd).to_numpy(np.int32);a=q.loc[match,VC['count']].to_numpy()
   assert len(np.unique(ix*len(wd)+dx))==len(ix) and not presentc[ix,dx].any(),'Unresolved count duplicate'
   finite=np.isfinite(a);assert not (a[finite]<0).any() and np.equal(a[finite],np.floor(a[finite])).all()
   cp[ix,dx]=a;presentc[ix,dx]=True
  assert seen_dates['count']==set(wc['days'])
  roster['rs_id']=pd.factorize(pd.MultiIndex.from_frame(roster[['route_id','node_id']]))[0]
  rs=roster.drop_duplicates('rs_id').sort_values('rs_id').reset_index(drop=True);vs=np.full((len(rs),len(wd),24),np.nan)
  for rid,ixs in roster.groupby('rs_id').indices.items():
   a=cp[ixs];v=np.nansum(a,axis=0);v[np.isfinite(a).sum(axis=0)==0]=np.nan;vs[rid]=v
  with warnings.catch_warnings():
   warnings.simplefilter('ignore',RuntimeWarning);representative=np.nanmedian(vs,axis=1)
  result['C2_count']=supply(rs,representative,list(range(24)))
  rs.to_csv(out/'fourweek_supply_keys.csv.gz',index=False,compression='gzip',encoding='utf-8-sig')
  atomic_npz(out/'fourweek_supply.npz',representative_count=representative,observed_days=np.isfinite(vs).sum(axis=1).astype(np.uint8))
  count['policy_Core_combinations']=len(si4);count['strict_Core_combinations']=int(st.sum());count['supply_target_route_stops']=len(rs)
 result=flags(result);save(result.reset_index(),f'checkpoints/{m}/fourweek_dong.csv');dump(count,out/'fourweek_counts.json')
 dump({'month':m,'Main_P50_P90_positive_days_reconciled':True,'Core_IQR_numpy_sample_checked':min(1000,len(iqr)),
       'all_calendar_common_dates_read':True,'fourweek_dates_subset_verified':True,'snapshot':cfg['snapshot'],
       'fourweek_status':result.status.iloc[0],'duplicates_and_conflicts':ledgers,'seconds':round(time.time()-began,1)},out/'restoration_verification.json')
 print('RESTORED',m,'IQR',len(iqr),'fourweek',result.status.iloc[0],'sec',round(time.time()-began,1),flush=True)
 return m

if __name__=='__main__':
 import sys
 if len(sys.argv)>1 and sys.argv[1]=='prepare':prepare()
 else:
  from concurrent.futures import ProcessPoolExecutor
  with ProcessPoolExecutor(max_workers=3) as ex:list(ex.map(run,sys.argv[1:] or MONTHS))
