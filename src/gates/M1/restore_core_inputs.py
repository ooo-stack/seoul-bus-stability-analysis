"""Read existing F1A Core and frozen historical names; never process raw bus data."""
from pathlib import Path
import io,json,hashlib,zipfile,gzip,os
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parent; WORK=ROOT.parent/'m1_work'
# Submission adapter: paths only; the original calculation statements follow.
from seoul_bus_paths import bind as _submission_bind
globals().update(_submission_bind('M1'))
CORE=WORK/'f1a_results'; M=WORK/'f0m_results'; OUT=ROOT/'analysis_inputs';OUT.mkdir(exist_ok=True)
DONG={'11140520':'소공동','11140570':'필동','11620695':'신림동','11680510':'신사동(강남구)','11680610':'대치2동','11680660':'개포1동','11710650':'잠실본동','11710710':'잠실6동','11710720':'잠실7동'}
MONTHS=['202509','202510','202601','202602','202603','202604','202605','202606','202608']
C=json.loads((CORE/'input_contract.json').read_text());configs=C['configs']
history=pd.read_csv(M/'route_type_history.csv',dtype=str,keep_default_na=False)
package=next((ROOT.parent/'m1_inputs').rglob('서울시버스 정보.zip'))
assert hashlib.sha256(package.read_bytes()).hexdigest()==json.loads((M/'historical_master_package_provenance.json').read_text())['sha256']
z=zipfile.ZipFile(package)
masters={};meta=[]
def loadmaster(kind,snapshot):
 name=f'서울시버스{kind}({snapshot}).xlsx'
 if name in z.namelist():b=z.read(name)
 else:b=next((ROOT.parent/'m1_inputs').rglob(name)).read_bytes()
 expected={r['sha256'] for r in C['master_hashes'] if r['filename']==name};assert len(expected)==1
 digest=hashlib.sha256(b).hexdigest();assert digest in expected,(name,digest)
 meta.append({'filename':name,'sha256':digest})
 return pd.read_excel(io.BytesIO(b),dtype=str,keep_default_na=False)
for snapshot in sorted({configs[m]['snapshot'] for m in MONTHS}):
 loc=loadmaster('정류소위치정보',snapshot);rs=loadmaster('노선별정류소정보',snapshot)
 assert loc.NODE_ID.is_unique
 names=loc.set_index('NODE_ID')['정류소명'].to_dict()
 # Exact route/node/sequence fallback only, and only unambiguous same-snapshot names.
 fall={k:next(iter(set(g['정류소명']))) for k,g in rs.groupby(['ROUTE_ID','NODE_ID','순번'],sort=False) if len(set(g['정류소명']))==1}
 masters[snapshot]=(names,fall)
 print('Historical name snapshot verified',snapshot,flush=True)
allhour=[];refs=[];presence=[];qa=[];hashes={}
rename={'노선_ID':'route_id','출발_정류장_ID':'departure_node','도착_정류장_ID':'arrival_node','출발_정류장_순서':'departure_sequence','도착_정류장_순서':'arrival_sequence','arr_dong_code':'dong_code'}
for month in MONTHS:
 folder=CORE/'core_checkpoints'/month
 keys=pd.read_csv(folder/'segment_keys.csv.gz',dtype=str,keep_default_na=False).rename(columns=rename)
 a=np.load(folder/'segment_hour_core.npz');valid=a['strict'];u=a['U'][valid]
 assert np.isfinite(u).all() and (u>=0).all()
 sample=json.loads((folder/'sample_counts.json').read_text());assert int(valid.sum())==sample['strict_Core_combinations']
 x,c=np.unique(np.round(u,8),return_counts=True);less=np.cumsum(c)-c;pct=(less+(c+1)/2)/len(u)*100
 ref=pd.DataFrame({'month':month,'U_rounded':x,'frequency':c,'average_tie_percentile':pct,'reference_N':len(u)})
 refs.append(ref)
 strictkeys=keys.iloc[a['segment_index'][valid]].reset_index(drop=True)
 assert strictkeys.dep_dong_code.ne('').all() and strictkeys.dong_code.ne('').all()
 assert strictkeys.spatial_coordinate_hold.eq('False').all()
 assert (strictkeys.arrival_sequence.astype(int)-strictkeys.departure_sequence.astype(int)).eq(1).all()
 assert not (strictkeys.departure_sequence.eq('2') & strictkeys.arrival_sequence.eq('3')).any()
 presence.append(strictkeys[['route_id','departure_node','arrival_node','dong_code']].drop_duplicates().assign(month=month))
 selected=keys.dong_code.iloc[a['segment_index']].isin(DONG).to_numpy() & valid
 idx=np.where(selected)[0];out=keys.iloc[a['segment_index'][idx]].reset_index(drop=True)
 out=out[['route_id','departure_node','arrival_node','departure_sequence','arrival_sequence','dep_dong_code','dong_code']]
 out.insert(0,'month',month);out['snapshot']=configs[month]['snapshot'];out['dong_name']=out.dong_code.map(DONG)
 for field in ['hour','positive_days','P50','P90','U']:out[field if field in ['hour','positive_days'] else field+'_sec']=a[field][idx]
 out['U_hour_percentile']=np.interp(np.round(out.U_sec.to_numpy(),8),x,pct)
 out['high_instability_hour']=out.U_hour_percentile.ge(75)
 for j,w in enumerate(a['week_names']):out['positive_days_week_'+str(w)]=a['weekly_positive_days'][idx,j]
 out['strict_spatial_core']=True
 names,fall=masters[configs[month]['snapshot']]
 for side in ['departure','arrival']:
  ns=[];sources=[]
  for row in out.itertuples(index=False):
   node=getattr(row,side+'_node');key=(row.route_id,node,getattr(row,side+'_sequence'))
   value=names.get(node,'');source='same_snapshot_location' if value else ''
   if not value:value=fall.get(key,'');source='same_snapshot_route_node_sequence' if value else 'name_unavailable'
   ns.append(value);sources.append(source)
  out[side+'_name']=ns;out[side+'_name_source']=sources
 h=history[history.month.eq(month)][['route_id','route_name','route_type']]
 assert h.route_id.is_unique
 out=out.merge(h,on='route_id',how='left',validate='many_to_one');assert out.route_name.notna().all()
 out['segment_length_m']=np.nan;out['length_status']='verified_physical_segment_length_not_available_in_frozen_master'
 allhour.append(out)
 qa.append({'month':month,'snapshot':configs[month]['snapshot'],'all_seoul_strict_hour_rows':len(u),'target_hour_rows':len(out),'name_missing_departure':out.departure_name.eq('').sum(),'name_missing_arrival':out.arrival_name.eq('').sum()})
 for n in ['segment_keys.csv.gz','segment_hour_core.npz','sample_counts.json']:
  hashes[str(folder.relative_to(WORK)/n)]=hashlib.sha256((folder/n).read_bytes()).hexdigest()
 print('Stored Core restored',month,'target hour rows',len(out),'reference rows',len(u),flush=True)
def durable_gzip(df,name):
 data=df.to_csv(index=False).encode('utf-8-sig');blob=gzip.compress(data,mtime=0);target=OUT/name;temp=OUT/(name+'.tmp')
 with temp.open('wb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
 os.replace(temp,target);assert gzip.decompress(target.read_bytes())==data
durable_gzip(pd.concat(allhour,ignore_index=True),'target_hour_core.csv.gz')
durable_gzip(pd.concat(refs,ignore_index=True),'strict_U_reference.csv.gz')
durable_gzip(pd.concat(presence,ignore_index=True).drop_duplicates(),'strict_unit_presence.csv.gz')
pd.DataFrame(qa).to_csv(ROOT/'core_input_QA.csv',index=False,encoding='utf-8-sig')
(ROOT/'source_manifest.json').write_text(json.dumps({'Core_source':'Gate2F1A_results.zip','Core_files_sha256':hashes,'historical_name_master_sha256':meta,'raw_bus_files_read':False,'new_spatial_assignment':False},ensure_ascii=False,indent=2))
