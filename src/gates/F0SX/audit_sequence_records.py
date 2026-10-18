"""Supplement: preserve all nonpositive/malformed-sequence or unknown-ID raw keys.
This implements the existing F0D validation, without choosing replacement values.
Only key columns are read; raw values are not altered or used for policy analysis.
"""
from audit_full_months import *
def one(j):
 sid=j['source_id'];path=WORK/f'idhold_{sid:03d}.csv'
 if path.exists():return str(path)
 rows=[];key=KEYS[j['kind']];offset=0
 with zipfile.ZipFile(j['path']) as z,z.open(j['member']) as f:
  for d in pd.read_csv(f,encoding='cp949',dtype=str,keep_default_na=False,na_filter=False,usecols=key,chunksize=150000):
   rn=np.arange(offset+2,offset+2+len(d));offset+=len(d);ids=key[1:4] if j['kind']=='time' else key[1:3];sc=key[-2:] if j['kind']=='time' else key[-1:]
   idok=np.logical_and.reduce([d[c].str.fullmatch(r'\d{9}').to_numpy() for c in ids]);sq=[pd.to_numeric(d[c],errors='coerce').to_numpy(float) for c in sc];seqok=np.logical_and.reduce([np.isfinite(s)&(s>0)&(s==np.floor(s)) for s in sq]);adj=np.ones(len(d),bool) if j['kind']=='count' else sq[1]-sq[0]==1
   special=np.zeros(len(d),bool) if j['kind']=='time' else (d['노선_ID'].eq('0')&d['정류장_ID'].str.fullmatch(r'\d{4}')&d['정류장_순서'].eq('999')).to_numpy()
   bad=(~(idok&seqok&adj))&~special&d['기준_날짜'].str[:6].isin(MONTHS).to_numpy()
   for i in np.flatnonzero(bad):
    r=d.iloc[i].to_dict();rows.append({'month':r['기준_날짜'][:6],'kind':j['kind'],'source_id':sid,'source_row':int(rn[i]),'date':r['기준_날짜'],'reason':'unknown_id' if not idok[i] else 'nonpositive_or_malformed_sequence' if not seqok[i] else 'nonadjacent_sequence','raw_key':json.dumps({c:r[c] for c in key},ensure_ascii=False)})
 pd.DataFrame(rows,columns=['month','kind','source_id','source_row','date','reason','raw_key']).to_csv(path,index=False,encoding='utf-8-sig');return str(path)
def main():
 jobs=json.loads((WORK/'jobs.json').read_text());selected=[]
 for j in jobs:
  r=pickle.load(open(WORK/f'scan_{j["source_id"]:03d}.pkl','rb'))
  if any(a['anom']['unknown_id_or_sequence_rows'] for a in r['months'].values()):selected.append(j)
 with ProcessPoolExecutor(max_workers=2) as pool:
  for p in pool.map(one,selected):print('ID_HOLD_KEYS',Path(p).name,flush=True)
 dfs=[pd.read_csv(WORK/f'idhold_{j["source_id"]:03d}.csv',dtype=str,keep_default_na=False) for j in selected]
 allrows=pd.concat(dfs,ignore_index=True) if dfs else pd.DataFrame(columns=['month','kind','source_id','source_row','date','reason','raw_key'])
 allrows.to_csv(OUT/'id_sequence_hold_keys.csv',index=False,encoding='utf-8-sig')
 print('ID_HOLD_ROWS',len(allrows),flush=True)
if __name__=='__main__':main()
