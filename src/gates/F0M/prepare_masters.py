"""F0M input certification only. No travel-time or service-value analysis."""
from pathlib import Path as FP
import ast,struct,json,hashlib,pickle,zipfile,math
import pandas as pd,numpy as np
from matplotlib.path import Path
from vtkmodules.vtkGeovisCore import vtkGeoProjection,vtkGeoTransform
ROOT=FP(__file__).resolve().parent.parent;O=ROOT/'f0m_results';S=ROOT/'f0m_sources';W=ROOT/'f0m_work'
# Submission adapter: paths only; the original calculation statements follow.
from seoul_bus_paths import bind as _submission_bind
globals().update(_submission_bind('F0M'))
MAP={'202509':'20250901','202510':'20250901','202511':'20251002','202512':'20251103','202601':'20251209','202602':'20260108','202603':'20260226','202604':'20260305','202605':'20260402','202606':'20260506','202607':'20260701','202608':'20260701'}
MAIN={'간선','지선','순환','광역','마을'}
def sha(p):
 with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(d,n):pd.DataFrame(d).to_csv(O/n,index=False,encoding='utf-8-sig')
# Execute only the two unchanged geometry-reader and containment function definitions.
c1=(S/'c1/reproduce_gate2c1.py').read_text(); tree=ast.parse(c1); geom='\n\n'.join(ast.get_source_segment(c1,n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('read_shp','locate'));exec(geom)
(O/'inherited_geometry_functions.py').write_text('import struct\nimport numpy as np,pandas as pd\nfrom matplotlib.path import Path\n'+geom)
prior=json.loads((S/'c1/recovery_diagnostics.json').read_text())['hashes'];assets={}
for f in ['project_sources/02-_-_-.zip','project_sources/04-_-_-.zip']:
 h=sha(ROOT/f);assert h==prior[f];assets[f]=h
z=zipfile.ZipFile(ROOT/'project_sources/02-_-_-.zip');z.extractall(W/'boundary');B,polys=read_shp(W/'boundary/11000/TL_SCCO_GEMD');assert len(B)==427 and B.EMD_CD.is_unique
z=zipfile.ZipFile(ROOT/'project_sources/04-_-_-.zip');C=pd.read_csv(z.open('SEOUL_ADMI/ADMI_202608.csv'),dtype=str);C=C[C.SIDO_NM=='서울특별시'].copy();C['EMD_CD']=C.ADMI_CD+'00';cross=B.merge(C,on='EMD_CD',validate='one_to_one');assert len(cross)==427 and cross.EMD_KOR_NM.str.replace('제','').eq(cross.ADMI_NM.str.replace('제','')).all();save(cross,'boundary_code_crosswalk.csv')
proj=vtkGeoProjection();proj.SetPROJ4String('+proj=tmerc +lat_0=38 +lon_0=127.5 +k=0.9996 +x_0=1000000 +y_0=2000000 +ellps=GRS80 +units=m +no_defs');fw=vtkGeoTransform();fw.SetDestinationProjection(proj);assert np.allclose(fw.TransformPoint(127.5,38,0)[:2],[1e6,2e6])
(O/'spatial_asset_verification.json').write_text(json.dumps({'sha256':assets,'boundary_count':427,'code_count':427,'one_to_one_codes':True,'crs':'EPSG:5179','crs_basis':'Inherited validated Gate2C1 assignment; original ZIP has no PRJ','geometry_function_sha256':hashlib.sha256(geom.encode()).hexdigest(),'geometry_modified':False},ensure_ascii=False,indent=2))
def file(kind,d):return next(S.rglob(f'서울시버스{kind}({d}).xlsx'))
def hav(a,b):
 lon1,lat1,lon2,lat2=map(math.radians,[a[0],a[1],b[0],b[1]]);v=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2;return 6371008.8*2*math.asin(min(1,math.sqrt(v)))
def valid(p):return np.isfinite(p).all() and 120<=p[0]<=135 and 30<=p[1]<=45
masters={};assign=[];history=[];diag=[];coordinates=[];typecounts=[];moves=[];previous=None
for d in sorted(set(MAP.values())):
 fs={k:file(k,d) for k in ['노선기본정보','정류소위치정보','노선별정류소정보']};bs,loc,rs=[pd.read_excel(fs[k],dtype=str,keep_default_na=False) for k in fs]
 assert {'노선번호','유형'}<=set(bs) and {'ROUTE_ID','노선명','NODE_ID','순번'}<=set(rs)
 assert loc.NODE_ID.is_unique
 pairs=rs[['ROUTE_ID','노선명']].drop_duplicates();assert pairs.groupby('ROUTE_ID')['노선명'].nunique().max()==1 and pairs.groupby('노선명').ROUTE_ID.nunique().max()==1
 gt=bs.groupby('노선번호')['유형'].agg(lambda v: sorted(set(v)));assert gt.map(len).max()==1
 types={r.ROUTE_ID:(gt[r.노선명][0] if r.노선명 in gt else '') for r in pairs.itertuples()};allowed={r for r,t in types.items() if t in MAIN}
 for typ,n in bs['유형'].value_counts(dropna=False).items():typecounts.append({'snapshot':d,'official_type_label':typ,'basic_rows':int(n)})
 keys=['ROUTE_ID','NODE_ID','순번'];full=rs.drop_duplicates();conflict=full[full.duplicated(keys,keep=False)];conflictset=set(conflict[keys].itertuples(index=False,name=None));triples=set(rs[keys].itertuples(index=False,name=None))-conflictset
 lc={};rc={};held=set();origin={};spaceready=set();inside=set();coordrows=[]
 for r in loc.itertuples(index=False):
  try: p=(float(r.X좌표),float(r.Y좌표))
  except ValueError:p=(np.nan,np.nan)
  lc[r.NODE_ID]=p
 for nid,g in rs.groupby('NODE_ID',sort=False):
  uq=g[['X좌표','Y좌표']].drop_duplicates()
  if len(uq)==1:
   try:rc[nid]=(float(uq.iloc[0,0]),float(uq.iloc[0,1]))
   except ValueError:pass
 chosen={}
 for nid in sorted(set(lc)|set(rc)):
  l=lc.get(nid,(np.nan,np.nan));r=rc.get(nid,(np.nan,np.nan));dist=hav(l,r) if valid(l) and valid(r) else np.nan
  # Previously identified same-snapshot gross conflict: keep original coordinate, hold spatial assignment.
  gross=nid=='108900095' and np.isfinite(dist) and dist>50000
  p=l if valid(l) else r;src='stop_location' if valid(l) else 'same_snapshot_route_stop'
  if gross:held.add(nid)
  if valid(p):chosen[nid]=p;origin[nid]=src
  reason='known_gross_same_snapshot_coordinate_conflict' if gross else ('invalid_or_missing_coordinate' if not valid(p) else '')
  if reason:held.add(nid)
  coordrows.append({'snapshot':d,'node_id':nid,'longitude':p[0],'latitude':p[1],'coordinate_source':src,'same_snapshot_difference_m':dist,'held_coordinate_record':bool(reason),'hold_reason':reason})
 xy=np.array([fw.TransformPoint(*chosen[nid],0)[:2] if nid in chosen else [np.nan,np.nan] for nid in [r['node_id'] for r in coordrows]])
 codes,hits,edges=locate(xy,B.EMD_CD,polys)
 for row,code,hit,edge in zip(coordrows,codes,hits,edges):
  nid=row['node_id'];row.update({'administrative_code10':code,'inside_seoul':bool(code),'multiple_polygon_hits':int(hit),'on_boundary':bool(edge)})
  if hit>1 or edge:held.add(nid);row['held_coordinate_record']=True;row['hold_reason']='ambiguous_boundary_assignment'
  if nid in chosen and nid not in held:spaceready.add(nid)
  if code and nid not in held:inside.add(nid)
 coordinates.extend(coordrows)
 if previous:
  oldd,old=previous
  for nid in set(old)&set(lc):
   if valid(old[nid]) and valid(lc[nid]):
    dist=hav(old[nid],lc[nid])
    if dist>=100:moves.append({'from_snapshot':oldd,'to_snapshot':d,'node_id':nid,'movement_m':dist,'action':'retain_frozen_snapshot_coordinate; no automatic hold'})
 previous=(d,lc)
 masters[d]={'routes':set(types),'types':types,'allowed':allowed,'location_nodes':set(loc.NODE_ID),'route_stop_nodes':set(rs.NODE_ID),'triples':triples,'conflict_triples':conflictset,'coordinate_available':set(chosen),'coordinate_ready':spaceready,'inside_seoul':inside,'coordinate_held':held}
 diag.append({'snapshot':d,'route_ids':len(types),'main_route_ids':len(allowed),'unknown_type_route_ids':sum(not t for t in types.values()),'basic_has_route_id_column':False,'exact_label_bridge_one_to_one':True,'basic_type_conflicts':0,'location_nodes':len(loc),'route_stop_rows':len(rs),'route_stop_conflict_keys':len(conflictset),'coordinate_held_nodes':len(held),'inside_seoul_ready_nodes':len(inside)})
 for m,sd in MAP.items():
  if sd!=d:continue
  for k,f in fs.items():assign.append({'month':m,'snapshot':d,'master_kind':k,'filename':f.name,'sha256':sha(f),'snapshot_not_after_month_start':d<=m+'01','age_days':(pd.Timestamp(m+'01')-pd.Timestamp(d)).days,'available':True})
  for r in pairs.itertuples(index=False):history.append({'month':m,'snapshot':d,'route_id':r.ROUTE_ID,'route_name':r.노선명,'route_type':types[r.ROUTE_ID],'main_included':r.ROUTE_ID in allowed,'type_status':'verified_exact_label_bridge' if types[r.ROUTE_ID] else 'official_type_unavailable','type_source':fs['노선기본정보'].name,'id_bridge_source':fs['노선별정류소정보'].name,'exact_label_match':r.노선명 in gt})
 print(d,len(types),len(allowed),len(held),flush=True)
for m,d in MAP.items():
 q=next(x for x in diag if x['snapshot']==d);coordinates.append({'month':m,'snapshot':d,'node_id':'__MONTH_SUMMARY__','coordinate_held_nodes':q['coordinate_held_nodes'],'inside_seoul_ready_nodes':q['inside_seoul_ready_nodes'],'whole_month_coordinate_hold':False,'spatial_asset_ready':True})
save(assign,'monthly_master_assignment.csv');save(history,'route_type_history.csv');save(diag,'snapshot_master_diagnostics.csv');save(typecounts,'official_route_type_values.csv');save(coordinates,'coordinate_readiness.csv');save(moves,'coordinate_changes_over_100m.csv')
with open(W/'masters.pkl','wb') as f:pickle.dump({'mapping':MAP,'masters':masters},f)
print('MASTER_PREPARATION_COMPLETE',flush=True)
