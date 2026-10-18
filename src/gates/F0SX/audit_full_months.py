"""Gate 2-F0S-X: raw structure audit only, frozen F0D-1.0. No research metrics.
Run: python audit_full_months.py inventory|scan|duplicates|assemble
Paths are rooted at parent of this output folder. Raw files remain unchanged.
Quantiles reuse F0S quantile(hist,q), copied unchanged into baseline_quantile.py.
"""
from pathlib import Path
import pandas as pd, numpy as np
import csv,json,zipfile,hashlib,collections,re,pickle,sys,time,datetime,calendar,math
from concurrent.futures import ProcessPoolExecutor
BASE=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent; WORK=BASE/'f0sx_work';SOURCES=BASE/'f0sx_sources'
# Submission adapter: paths only; the original calculation statements follow.
from seoul_bus_paths import bind as _submission_bind
globals().update(_submission_bind('F0SX'))
MONTHS=[f'{y}{m:02d}' for y,m in [(2025,m) for m in range(9,13)]+[(2026,m) for m in range(1,9)]]
KEYS={'time':['기준_날짜','노선_ID','출발_정류장_ID','도착_정류장_ID','출발_정류장_순서','도착_정류장_순서'],'count':['기준_날짜','노선_ID','정류장_ID','정류장_순서']}
PREFIX={'time':'운행시간','count':'버스운행횟수'}
EXPECTED={k:KEYS[k][:4 if k=='time' else 3]+[v]+[f'{v}_{h:02d}시' for h in range(24)]+KEYS[k][-2 if k=='time' else -1:] for k,v in PREFIX.items()}
def write(rows,name):pd.DataFrame(rows).to_csv(OUT/name,index=False,encoding='utf-8-sig')
def dump(x,path):Path(path).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda x:int(x) if isinstance(x,np.integer) else float(x)),encoding='utf-8')
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def inventory():
 files=sorted(SOURCES.rglob('tpss*.zip'))+sorted((BASE/'upload').glob('*speedh*.zip'))+[BASE/n for n in ['counts_week.zip','counts_w2.zip','counts_w3.zip','counts_w4.zip']]
 assert all(p.exists() for p in files)
 aliases=[];logical={}
 for p in files:
  kind='time' if 'speedh' in p.name else 'count';h=sha(p);aliases.append({'path':str(p.relative_to(BASE)),'kind':kind,'zip_sha256':h,'bytes':p.stat().st_size})
  logical.setdefault(h,{'path':str(p),'kind':kind,'zip_sha256':h})
 write(aliases,'zip_source_manifest.csv')
 members=[];seen={};sid=0
 for h,zp in sorted(logical.items()):
  with zipfile.ZipFile(zp['path']) as z:
   for zi in z.infolist():
    if not zi.filename.lower().endswith('.csv'):continue
    dig=hashlib.sha256()
    with z.open(zi) as f:
     for b in iter(lambda:f.read(8*1024*1024),b''):dig.update(b)
    ch=dig.hexdigest();sig=(zp['kind'],ch)
    if sig not in seen:seen[sig]=sid;sid+=1
    with z.open(zi) as f:header=next(csv.reader([f.readline().decode('cp949').strip()]))
    members.append({**zp,'member':zi.filename,'csv_sha256':ch,'source_id':seen[sig],'csv_bytes':zi.file_size,'columns':header,'schema_ok':header==EXPECTED[zp['kind']]})
 jobs=[];done=set()
 for r in members:
  if r['source_id'] not in done:jobs.append(r);done.add(r['source_id'])
 dump(jobs,WORK/'jobs.json');dump(members,OUT/'csv_source_manifest.json')
 write([{**r,'columns':json.dumps(r['columns'],ensure_ascii=False)} for r in members],'csv_source_manifest.csv')
 print('INVENTORY',len(files),'zip aliases',len(logical),'unique zips',len(members),'CSV entries',len(jobs),'unique CSV',flush=True)

def newstats(cols):return {'rows':0,'cnt':np.zeros((len(cols),6),dtype=np.int64),'hist':[collections.Counter() for c in cols],'lex':{c:collections.Counter() for c in cols},'idlex':{},'dates':collections.Counter(),'normal_dates':collections.Counter(),'anom':collections.Counter(),'delta':collections.Counter()}
def lexical(counts):
 c=collections.Counter()
 for v,n in counts.items():
  c['blank' if v=='' else 'integer_lexeme' if re.fullmatch(r'[+-]?\d+',v) else 'decimal_lexeme' if re.fullmatch(r'[+-]?\d+\.\d+',v) else 'other_lexeme']+=int(n)
  if v:c['length_'+str(len(v))]+=int(n);c['leading_zero']+=int(n)*(len(v)>1 and v.startswith('0'))
 return c

def scan_file(job):
 sid=job['source_id'];cp=WORK/f'scan_{sid:03d}.pkl'
 if cp.exists():
  try:
   with open(cp,'rb') as f:pickle.load(f)
   return f'REUSED {sid}'
  except (EOFError,pickle.UnpicklingError):cp.rename(cp.with_suffix('.incomplete'))
 t=time.time();kind=job['kind'];key=KEYS[kind];cols=job['columns'];vcols=[c for c in cols if c.startswith(PREFIX[kind])];res={'job':job,'months':{},'all_dates':collections.Counter(),'schema':cols,'errors':[]};hashes=collections.defaultdict(list);offset=0
 if not job['schema_ok']:
  res['errors'].append('schema_not_F0S');pickle.dump(res,open(cp,'wb'));return f'HELD_SCHEMA {sid}'
 with zipfile.ZipFile(job['path']) as z,z.open(job['member']) as f:
  for d in pd.read_csv(f,encoding='cp949',dtype=str,keep_default_na=False,na_filter=False,chunksize=100000):
   d['_source_row']=np.arange(offset+2,offset+2+len(d),dtype=np.uint32);offset+=len(d)
   res['all_dates'].update(d['기준_날짜'].value_counts().to_dict())
   for date in d['기준_날짜'].unique():
    try:assert re.fullmatch(r'\d{8}',date);datetime.datetime.strptime(date,'%Y%m%d')
    except Exception:res['errors'].append('invalid_date:'+date)
   for mo,dd in d.groupby(d['기준_날짜'].str[:6],sort=False):
    if mo not in MONTHS:continue
    a=res['months'].setdefault(mo,newstats(vcols));a['rows']+=len(dd);a['dates'].update(dd['기준_날짜'].value_counts().to_dict())
    # Hashes only locate possible duplicate keys; all selected raw fields are reread and compared exactly.
    kh=pd.util.hash_pandas_object(dd[key],index=False).to_numpy(dtype=np.uint64)
    hashes[mo].append(np.rec.fromarrays([kh,dd['_source_row'].to_numpy(np.uint32)],names='key_hash,source_row'))
    for c in key:
     a['idlex'].setdefault(c,collections.Counter()).update(lexical(dd[c].value_counts().to_dict()))
    nine=lambda s:s.str.fullmatch(r'\d{9}')
    seqcols=key[-2:] if kind=='time' else key[-1:]
    seq=[pd.to_numeric(dd[c],errors='coerce').to_numpy(float) for c in seqcols]
    ids=key[1:4] if kind=='time' else key[1:3]
    normal=np.logical_and.reduce([nine(dd[c]).to_numpy() for c in ids]+[(np.isfinite(s)&(s>0)&(s==np.floor(s))) for s in seq])
    for c in ids:a['anom'][c+'_missing']+=int(dd[c].eq('').sum())
    a['anom']['zero_or_negative_sequence']+=int(np.logical_or.reduce([s<=0 for s in seq]).sum())
    a['anom']['noninteger_or_missing_sequence']+=int(np.logical_or.reduce([~np.isfinite(s)|(s!=np.floor(s)) for s in seq]).sum())
    special=np.zeros(len(dd),dtype=bool)
    if kind=='time':
     delta=seq[1]-seq[0];a['delta'].update(dict(zip(*np.unique(delta[np.isfinite(delta)],return_counts=True))))
     a['anom']['reversed_sequence']+=int((delta<0).sum());a['anom']['nonadjacent_sequence']+=int((delta!=1).sum());a['anom']['segment_2_to_3_rows']+=int(((seq[0]==2)&(seq[1]==3)).sum());normal&=(delta==1)
    else:
     special=(dd['노선_ID'].eq('0')&dd['정류장_ID'].str.fullmatch(r'\d{4}')&dd['정류장_순서'].eq('999')).to_numpy()
     a['anom']['special_id_rows']+=int(special.sum());a['anom']['special_all_values_blank']+=int((special&dd[vcols].eq('').all(axis=1).to_numpy()).sum())
    a['anom']['normal_id_sequence_rows']+=int(normal.sum());a['anom']['unknown_id_or_sequence_rows']+=int((~normal&~special).sum());a['normal_dates'].update(dd.loc[normal,'기준_날짜'].value_counts().to_dict())
    for i,c in enumerate(vcols):
     raw=dd[c];counts=raw.value_counts().to_dict();a['lex'][c].update(lexical(counts));v=pd.to_numeric(raw,errors='coerce').to_numpy(float);finite=np.isfinite(v);blank=raw.eq('').to_numpy();pos=(v>0)&finite
     a['cnt'][i]+=np.array([blank.sum(),((v==0)&finite).sum(),pos.sum(),((v<0)&finite).sum(),(~blank&~finite).sum(),(pos&(v!=np.floor(v))).sum()],dtype=np.int64)
     vals,ns=np.unique(v[pos],return_counts=True);a['hist'][i].update(dict(zip(vals,ns)))
 for mo,arr in hashes.items():np.save(WORK/f'keys_{sid:03d}_{mo}.npy',np.concatenate(arr))
 res['rows']=offset;res['seconds']=time.time()-t
 tmp=cp.with_suffix('.tmp')
 with open(tmp,'wb') as f:pickle.dump(res,f)
 tmp.replace(cp)
 return f'DONE {sid:03d} {kind} {job["member"]} rows={offset:,} seconds={res["seconds"]:.1f}'
def scan():
 jobs=json.loads((WORK/'jobs.json').read_text())
 with ProcessPoolExecutor(max_workers=2) as pool:
  for s in pool.map(scan_file,jobs):print(s,flush=True)

def duplicates():
 jobs=json.loads((WORK/'jobs.json').read_text());selected=collections.defaultdict(list)
 for kind in ['time','count']:
  for mo in MONTHS:
   arr=[]
   for job in jobs:
    sid=job['source_id'];p=WORK/f'keys_{sid:03d}_{mo}.npy'
    if job['kind']!=kind or not p.exists():continue
    a=np.load(p);arr.append(np.rec.fromarrays([a['key_hash'],a['source_row'],np.full(len(a),sid,np.uint16)],names='key_hash,source_row,source_id'))
   a=np.concatenate(arr);ix=pd.Series(a['key_hash']).duplicated(keep=False).to_numpy()
   for sid in np.unique(a['source_id'][ix]):selected[int(sid)].extend(a['source_row'][ix&(a['source_id']==sid)].tolist())
   print('DUP_CANDIDATES',kind,mo,int(ix.sum()),flush=True)
 dump(selected,WORK/'duplicate_candidate_rows.json');rows=[]
 for sid,rownums in selected.items():
  j=next(j for j in jobs if j['source_id']==sid);offset=0;wanted=set(rownums)
  with zipfile.ZipFile(j['path']) as z,z.open(j['member']) as f:
   for d in pd.read_csv(f,encoding='cp949',dtype=str,keep_default_na=False,na_filter=False,chunksize=100000):
    rn=np.arange(offset+2,offset+2+len(d));offset+=len(d);ix=pd.Series(rn).isin(wanted).to_numpy()
    for idx in np.flatnonzero(ix):rows.append({'source_id':sid,'source_row':int(rn[idx]),'kind':j['kind'],'raw':d.iloc[idx].to_dict()})
 groups=collections.defaultdict(list)
 for r in rows:groups[(r['kind'],tuple(r['raw'][c] for c in KEYS[r['kind']]))].append(r)
 details=[];rawrows=[]
 for (kind,key),rr in groups.items():
  if len(rr)<2:continue # hash collision would be excluded by exact key comparison
  cols=EXPECTED[kind];variants=collections.Counter(tuple(r['raw'][c] for c in cols) for r in rr);nv=len(variants);ex=len(rr)-nv
  numeric_equal=False
  if nv>1:
   vcols=[c for c in cols if c.startswith(PREFIX[kind])]
   def numeric_tuple(r):
    return tuple(None if r['raw'][c]=='' else float(r['raw'][c]) for c in vcols)
   try:numeric_equal=len(set(numeric_tuple(r) for r in rr))==1
   except ValueError:pass
  status='exact_duplicate' if nv==1 else 'format_only_conflict' if numeric_equal else 'value_conflict'
  group={'month':key[0][:6],'kind':kind,'date':key[0],'raw_key':json.dumps(dict(zip(KEYS[kind],key)),ensure_ascii=False),'problem':status,'rows':len(rr),'distinct_raw_rows':nv,'complete_duplicate_extra_rows':ex,'key_duplicate_extra_rows':len(rr)-1,'held_raw_rows':len(rr) if nv>1 else 0,'held_distinct_rows':nv if nv>1 else 0,'sources':json.dumps([{'source_id':r['source_id'],'source_row':r['source_row']} for r in rr]),'hold_scope':'date_key_24h_row' if nv>1 else 'one_observation_after_exact_dedup'}
  details.append(group)
  for r in rr:rawrows.append({'month':key[0][:6],'kind':kind,'problem':status,'source_id':r['source_id'],'source_row':r['source_row'],'raw_cells_json':json.dumps(r['raw'],ensure_ascii=False)})
 write(details,'duplicate_key_details.csv');write(rawrows,'duplicate_raw_rows.csv');dump(details,WORK/'duplicate_details.json')
 print('EXACT_DUPLICATE_VERIFICATION',len(details),'groups',sum(r['problem']!='exact_duplicate' for r in details),'conflicts',flush=True)
if __name__=='__main__':globals()[sys.argv[1]]()
