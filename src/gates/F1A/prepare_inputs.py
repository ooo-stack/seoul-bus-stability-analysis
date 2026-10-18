"""Lock previously certified files, master keys, calendar, duplicates and space."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,pickle,zipfile,collections
R=Path(__file__).resolve().parent.parent;O=R/'f1a_results';W=R/'f1a_work';S=R/'f1a_sources';SX=S/'unpacked/Gate2F0SX_results/f0sx_results';M=S/'unpacked/Gate2F0M_results/f0m_results'
# Submission adapter: paths only; the original calculation statements follow.
from seoul_bus_paths import bind as _submission_bind
globals().update(_submission_bind('F1A'))
MONTHS=['202509','202510','202601','202602','202603','202604','202605','202606','202608']
def sha(p):
 with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
E=pd.read_csv(M/'final_month_eligibility.csv',dtype={'month':str,'snapshot':str});assert E.loc[E.final_status=='eligible','month'].tolist()==MONTHS
A=pd.read_csv(M/'monthly_master_assignment.csv',dtype=str,keep_default_na=False)
for row in A.itertuples():
 if row.month in MONTHS:
  f=next(S.rglob(row.filename));assert sha(f)==row.sha256 and row.snapshot<=row.month+'01'
AS=json.loads((M/'spatial_asset_verification.json').read_text())
for p,h in AS['sha256'].items():assert sha(R/p)==h
B=pd.read_csv(M/'boundary_code_crosswalk.csv',dtype=str);assert len(B)==427 and B.ADMI_CD.is_unique
C=pd.read_csv(M/'coordinate_node_diagnostics.csv',dtype=str,keep_default_na=False)
def normalize_code(x):
 if not x:return ''
 if x.endswith('.0') and len(x[:-2])==10 and x[:-2].isdigit():x=x[:-2]
 assert x in set(B.EMD_CD),x
 return dict(zip(B.EMD_CD,B.ADMI_CD))[x]
C['dong_code']=C.administrative_code10.map(normalize_code)
H=pd.read_csv(M/'route_type_history.csv',dtype=str,keep_default_na=False)
masters={}
for snapshot in sorted(set(E.loc[E.month.isin(MONTHS),'snapshot'])):
 f=next(S.rglob(f'서울시버스노선별정류소정보({snapshot}).xlsx'));rs=pd.read_excel(f,dtype=str,keep_default_na=False);rs=rs.drop_duplicates();assert not rs.duplicated(['ROUTE_ID','NODE_ID','순번']).any()
 hist=H[H.snapshot==snapshot].drop_duplicates('route_id');types=dict(zip(hist.route_id,hist.route_type));allowed=set(hist.loc[hist.main_included=='True','route_id'])
 c=C[C.snapshot==snapshot].copy();assert c.node_id.is_unique
 held=set(c.loc[c.held_coordinate_record=='True','node_id']);inside=dict(zip(c.loc[(c.inside_seoul=='True')&~c.node_id.isin(held),'node_id'],c.loc[(c.inside_seoul=='True')&~c.node_id.isin(held),'dong_code']))
 masters[snapshot]={'types':types,'allowed':allowed,'triples':set(rs.ROUTE_ID+'|'+rs.NODE_ID+'|'+rs['순번']),'held_nodes':held,'inside':inside}
 print('MASTER',snapshot,len(allowed),flush=True)
MF=pd.read_csv(SX/'csv_source_manifest.csv',dtype=str,keep_default_na=False);FS=pd.read_csv(SX/'file_schema_and_dates.csv',dtype={'source_id':str});MF=MF.merge(FS[['source_id','dates_json']],on='source_id',validate='one_to_one')
archives={}
for p in list((S/'raw').rglob('*.zip'))+list((R/'upload').glob('*.zip'))+[R/n for n in ['counts_week.zip','counts_w2.zip','counts_w3.zip','counts_w4.zip']]:
 if p.is_file():archives[sha(p)]=str(p)
assert not set(MF.zip_sha256)-set(archives)
sources={r.source_id:{'source_id':r.source_id,'kind':r.kind,'path':archives[r.zip_sha256],'zip_sha256':r.zip_sha256,'csv_sha256':r.csv_sha256,'member':r.member,'dates':json.loads(r.dates_json),'columns':json.loads(r.columns)} for r in MF.itertuples()}
# Reuse F0S-X full-field duplicate comparison only after exact source hashes agree.
dup=pd.read_csv(SX/'duplicate_raw_rows.csv',dtype=str,keep_default_na=False);groups=collections.defaultdict(list)
KEYS={'time':['기준_날짜','노선_ID','출발_정류장_ID','도착_정류장_ID','출발_정류장_순서','도착_정류장_순서'],'count':['기준_날짜','노선_ID','정류장_ID','정류장_순서']}
for x in dup.itertuples():
 raw=json.loads(x.raw_cells_json);groups[(x.kind,tuple(raw[k] for k in KEYS[x.kind]))].append((x.source_id,int(x.source_row),raw))
skip=collections.defaultdict(dict);audit=[]
for (kind,key),rr in groups.items():
 variants=collections.defaultdict(list)
 for sid,row,raw in rr:variants[tuple(raw[c] for c in sources[sid]['columns'])].append((sid,row,raw))
 canonical=[]
 for vr in variants.values():
  vr.sort(key=lambda x:(sources[x[0]]['zip_sha256'],sources[x[0]]['member'],x[1]));canonical.append(vr[0])
  for sid,row,raw in vr[1:]:skip[sid][row]='exact_duplicate'
 if len(canonical)>1:
  for sid,row,raw in canonical:skip[sid][row]='conflict_pending'
 audit.append({'month':key[0][:6],'kind':kind,'date':key[0],'key_json':json.dumps(dict(zip(KEYS[kind],key)),ensure_ascii=False),'exact_duplicate_extra_rows':len(rr)-len(variants),'conflict_key':len(variants)>1,'conflict_rows_after_dedup':len(variants) if len(variants)>1 else 0})
pd.DataFrame(audit).to_csv(O/'duplicate_application_ledger.csv',index=False,encoding='utf-8-sig')
cal=pd.read_csv(SX/'day_calendar.csv',dtype={'date':str,'month':str});config={}
for m in MONTHS:
 e=E[E.month==m].iloc[0];c=cal[cal.month==m];planned=c[c.planned_weekday];days=c.loc[c.common_planned_day,'date'].tolist();weekplan=planned.groupby('week_start').size().to_dict()
 assert len(planned)==e.N_planned and len(days)==e.common_days and max(16,int(np.ceil(16*e.N_planned/19)))==e.L_main
 jobs=[j for j in sources.values() if any(d[:6]==m for d in j['dates'])];jobs.sort(key=lambda j:(j['zip_sha256'],j['member']))
 config[m]={'month':m,'snapshot':e.snapshot,'N':int(e.N_planned),'L':int(e.L_main),'days':days,'day_weeks':dict(zip(c.date,c.week_start)),'week_min':{w:min(3,n) for w,n in weekplan.items()},'jobs':jobs}
with open(W/'input_contract.pkl','wb') as f:pickle.dump({'months':MONTHS,'masters':masters,'config':config,'skip':dict(skip),'boundary':B,'eligibility':E},f)
(O/'input_contract.json').write_text(json.dumps({'months':MONTHS,'configs':config,'spatial_assets':AS,'master_hashes':A.to_dict('records'),'F0M_administrative_code_serialization':'Only a terminal .0 on exact 10-digit integer codes is losslessly removed; validated against 427-code crosswalk. No spatial reassignment.'},ensure_ascii=False,indent=2))
print('INPUT_PREPARATION_COMPLETE',flush=True)
