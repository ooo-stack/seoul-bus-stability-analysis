from common import *
from collections import defaultdict
import zipfile,time
contract=json.loads((A/'input_contract.json').read_text());sx=ROOT/'m2_sources/Gate2F1C_results/f1c_sources/F0SX/f0sx_results';b=units();primary=b[b.is_diagnostic43].copy();core_ak=set(primary[AK].itertuples(index=False,name=None))
manifest=pd.read_csv(sx/'csv_source_manifest.csv',dtype=str,keep_default_na=False);sources={r.source_id:dict(zip(manifest.columns,r)) for r in manifest.itertuples(index=False,name=None)} if False else manifest.set_index('source_id').to_dict('index')
dup=pd.read_csv(sx/'duplicate_raw_rows.csv',dtype=str,keep_default_na=False);groups=defaultdict(list)
for r in dup.itertuples():
 if r.kind!='time':continue
 raw=json.loads(r.raw_cells_json);groups[tuple(raw[k] for k in ['기준_날짜']+RAWK)].append((r.source_id,int(r.source_row),raw))
skip=defaultdict(dict)
for key,rows in groups.items():
 variants=defaultdict(list)
 for sid,row,raw in rows:variants[tuple(raw[c] for c in json.loads(sources[sid]['columns']))].append((sid,row))
 canonical=[]
 for values in variants.values():
  values.sort(key=lambda x:(sources[x[0]]['zip_sha256'],sources[x[0]]['member'],x[1]));canonical.append(values[0])
  for sid,row in values[1:]:skip[sid][row]='exact_duplicate'
 if len(canonical)>1:
  for sid,row in canonical:skip[sid][row]='conflict_pending'
# All raw archive hashes once, members validated once even if a month boundary uses them twice.
archives={}
for p in (ROOT/'m2_raw').rglob('*.zip'):archives[sha(p)]=p
cal=read(A/'reference/day_calendar.csv');cal['date']=cal.date.astype(str);csv_verified=set();hash_ledger=[];checkpoints=OUT/'daily_checkpoints';checkpoints.mkdir(exist_ok=True)
for month in MAIN:
 start=time.time();cfg=contract['configs'][month];days=cfg['days'];di={d:i for i,d in enumerate(days)};keys=pd.read_csv(A/'core_checkpoints'/month/'segment_keys.csv.gz',dtype=str,keep_default_na=False)
 with np.load(A/'core_checkpoints'/month/'segment_hour_core.npz') as compressed:
  z={name:compressed[name] for name in compressed.files}
 mapped=keys.rename(columns=dict(zip(RAWK,SK)))
 key_is_primary=np.fromiter((k in core_ak for k in mapped[['arr_dong_code']+SK[:3]].itertuples(index=False,name=None)),bool,len(mapped))
 indices=np.flatnonzero(z['strict'] & key_is_primary[z['segment_index']])
 seqids=np.unique(z['segment_index'][indices]);local={int(k):i for i,k in enumerate(seqids)};kframe=mapped.iloc[seqids].reset_index(drop=True);sindex={tuple(k):i for i,k in enumerate(kframe[SK].itertuples(index=False,name=None))}
 T=np.full((len(seqids),len(days),24),np.nan);present=np.zeros((len(seqids),len(days)),bool);conflict=np.zeros_like(present);sidarr=np.full(present.shape,'',dtype=object);rowarr=np.zeros(present.shape,np.int64);exact_removed=conflict_rows=0;seen_dates=set();failedjobs=[]
 for job in cfg['jobs']:
  if job['kind']!='time' or not set(job['dates'])&set(days):continue
  sid=job['source_id'];path=archives.get(job['zip_sha256'])
  if path is None:failedjobs.append({'source_id':sid,'reason':'archive_hash_missing'});continue
  ident=(job['zip_sha256'],job['member'])
  with zipfile.ZipFile(path) as f:
   if ident not in csv_verified:
    with f.open(job['member']) as q:digest=hashlib.file_digest(q,'sha256').hexdigest()
    ok=digest==job['csv_sha256'];hash_ledger.append({'archive':path.name,'zip_sha256':job['zip_sha256'],'source_id':sid,'member':job['member'],'csv_sha256':digest,'csv_hash_match':ok})
    if not ok:failedjobs.append({'source_id':sid,'reason':'csv_hash_mismatch'});continue
    csv_verified.add(ident)
   dtype={k:str for k in ['기준_날짜']+RAWK};dtype.update({v:np.float64 for v in VC})
   for q in pd.read_csv(f.open(job['member']),encoding='cp949',usecols=['기준_날짜']+RAWK+VC,dtype=dtype,keep_default_na=False,na_values={v:[''] for v in VC},chunksize=100000):
    q=q[q['기준_날짜'].isin(di)];seen_dates.update(q['기준_날짜']);q=q[q['노선_ID'].isin(set(primary.route_id))]
    if not len(q):continue
    ix=np.fromiter((sindex.get(k,-1) for k in q[RAWK].itertuples(index=False,name=None)),np.int32,len(q));match=ix>=0;q=q.loc[match];ix=ix[match]
    if not len(q):continue
    dx=q['기준_날짜'].map(di).to_numpy(np.int32);orig=(q.index+2).to_numpy(np.int64);reasons=np.array([skip[sid].get(int(i),'') for i in orig])
    held=reasons=='conflict_pending';conflict[ix[held],dx[held]]=True;conflict_rows+=int(held.sum());exact_removed+=int((reasons=='exact_duplicate').sum());keep=reasons=='';qq=q.loc[keep];ii=ix[keep];dd=dx[keep]
    assert not present[ii,dd].any() and len(np.unique(ii*len(days)+dd))==len(ii),'unresolved duplicate exact-key day'
    vals=qq[VC].to_numpy(np.float64);T[ii,dd,:]=vals;present[ii,dd]=True;sidarr[ii,dd]=sid;rowarr[ii,dd]=orig[keep]
 # Any unprocessed source prevents certification of this month's affected cells; full hold is conservative.
 source_ok=not failedjobs and seen_dates==set(days)
 qas=[];daily=[];expectedhours=0
 for zi in indices:
  li=local[int(z['segment_index'][zi])];hr=int(z['hour'][zi]);kr=kframe.iloc[li];x=T[li,:,hr].copy();x[(x<=0)|~np.isfinite(x)|conflict[li]]=np.nan;valid=np.isfinite(x);n=int(valid.sum());p50=float(np.nanquantile(x,.5,method='linear')) if n else np.nan;p90=float(np.nanquantile(x,.9,method='linear')) if n else np.nan;u=p90-p50
  weekly=[int(valid[[j for j,d in enumerate(days) if cfg['day_weeks'][d]==week]].sum()) for week in z['week_names']]
  counts_ok=n==int(z['positive_days'][zi]);week_ok=np.array_equal(weekly,z['weekly_positive_days'][zi]);f50=np.isclose(p50,z['P50'][zi],atol=1e-10,rtol=1e-12);f90=np.isclose(p90,z['P90'][zi],atol=1e-10,rtol=1e-12);fu=np.isclose(u,z['U'][zi],atol=1e-10,rtol=1e-12);ok=bool(source_ok and counts_ok and week_ok and f50 and f90 and fu)
  ar=primary[(primary.dong_code.eq(kr.arr_dong_code))&(primary.route_id.eq(kr.route_id))&(primary.departure_node.eq(kr.departure_node))&(primary.arrival_node.eq(kr.arrival_node))].iloc[0]
  qa={'month':month,**{k:ar[k] for k in LABELS},'departure_sequence':kr.departure_sequence,'arrival_sequence':kr.arrival_sequence,'hour':hr,'snapshot':cfg['snapshot'],'N_planned':cfg['N'],'common_days':len(days),'positive_days_restored':n,'positive_days_stored':int(z['positive_days'][zi]),'P50_restored_sec':p50,'P50_stored_sec':float(z['P50'][zi]),'P90_restored_sec':p90,'P90_stored_sec':float(z['P90'][zi]),'U_restored_QA_sec':u,'U_stored_sec':float(z['U'][zi]),'weekly_restored':json.dumps(weekly),'weekly_stored':json.dumps(z['weekly_positive_days'][zi].tolist()),'source_hash_and_dates_match':source_ok,'positive_days_match':counts_ok,'weekly_days_match':week_ok,'P50_match':bool(f50),'P90_match':bool(f90),'U_match':bool(fu),'QA_status':'pass' if ok else 'held_reconciliation','failed_jobs':json.dumps(failedjobs)};qas.append(qa)
  planned=cal[(cal.month.eq(month))&cal.planned_weekday]
  for day in planned.date:
   tix=di.get(day);weekday=pd.Timestamp(day).weekday();value=T[li,tix,hr] if tix is not None else np.nan
   if tix is None:reason='date_not_common_planned'
   elif conflict[li,tix]:reason='conflict_pending'
   elif not present[li,tix]:reason='key_absent'
   elif not np.isfinite(value):reason='value_missing'
   elif value==0:reason='time_zero'
   elif value<0:reason='time_negative'
   else:reason='valid_positive'
   good=reason=='valid_positive' and ok
   daily.append({'month':month,'date':day,'weekday':weekday,**{k:ar[k] for k in LABELS},'departure_sequence':kr.departure_sequence,'arrival_sequence':kr.arrival_sequence,'hour':hr,'T_sec':value,'P50_sec':float(z['P50'][zi]),'P90_sec':float(z['P90'][zi]),'U_stored_sec':float(z['U'][zi]),'E_sec':value-float(z['P50'][zi]) if good else np.nan,'P90_reached':float(value>=z['P90'][zi]) if good else np.nan,'valid':good,'status_reason':reason if ok else 'held_reconciliation:'+reason,'source_id':sidarr[li,tix] if tix is not None else '', 'source_row':rowarr[li,tix] if tix is not None and rowarr[li,tix]>0 else np.nan,'snapshot':cfg['snapshot'],'strict_core':True,'QA_status':'pass' if ok else 'held_reconciliation','common_planned':tix is not None})
 save(pd.DataFrame(qas),'daily_checkpoints/'+month+'_QA.csv');save(pd.DataFrame(daily),'daily_checkpoints/'+month+'_panel.csv.gz')
 dump({'month':month,'source_ok':source_ok,'exact_duplicate_rows_removed_for_diagnostic_keys':exact_removed,'conflict_rows_held_for_diagnostic_keys':conflict_rows,'native_Core_hour_cells':len(qas),'QA_pass':sum(r['QA_status']=='pass' for r in qas),'source_dates_seen':sorted(seen_dates),'failed_jobs':failedjobs},'daily_checkpoints/'+month+'_restoration.json')
 print('DAILY_RESTORED',month,'Core cells',len(qas),'QA pass',sum(r['QA_status']=='pass' for r in qas),'rows',len(daily),'sec',round(time.time()-start,1),flush=True)
q=pd.concat([read(checkpoints/(m+'_QA.csv')) for m in MAIN],ignore_index=True);save(q,'daily_panel_QA.csv')
save(pd.DataFrame(hash_ledger),'source_hash_checks.csv')
print('DAILY_ALL_READY',len(q),'QA cells',flush=True)
