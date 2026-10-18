from common import *
from inherited_tm_projection import forward_tm,inverse_tm
from scipy.spatial import cKDTree
b=units();p=b[b.is_diagnostic43].sort_values('diagnostic_no');assignment=pd.read_csv(F0/'monthly_master_assignment.csv',dtype={'month':str,'snapshot':str});snap=assignment.groupby('month').snapshot.first().to_dict();coords=pd.read_csv(F0/'coordinate_node_diagnostics.csv',dtype={'snapshot':str,'node_id':str,'administrative_code10':str},keep_default_na=False);coords=coords[coords.node_id.str.fullmatch(r'\d{9}')].copy();assert not coords.duplicated(['snapshot','node_id']).any();coords['longitude']=pd.to_numeric(coords.longitude);coords['latitude']=pd.to_numeric(coords.latitude)
cols=coords[['longitude','latitude']].to_numpy();xy=forward_tm(cols[:,0],cols[:,1],127.,1.,200000.,600000.);coords['x5186']=xy[:,0];coords['y5186']=xy[:,1];back=inverse_tm(xy,127.,1.,200000.,600000.);xy2=forward_tm(back[:,0],back[:,1],127.,1.,200000.,600000.);err=float(np.linalg.norm(xy2-xy,axis=1).max());assert err<.001;assert np.allclose(forward_tm(np.array([127.]),np.array([38.]),127.,1.,200000.,600000.),[[200000.,600000.]])
inter,ig,imeta=read_shape(INTERSECTION);lane,lg,lmeta=read_shape(LANE);assert imeta['shape_type']==1 and lmeta['shape_type']==3
for meta in [imeta,lmeta]:assert all(q in meta['prj'] for q in ['GRS_1980','600000.0','200000.0','127.0','38.0'])
validpoint=np.array([len(g)==1 and len(g[0])==1 and np.isfinite(g[0]).all() for g in ig])&~inter.dbf_deleted.to_numpy();xyi=np.array([g[0][0] if len(g) else [np.nan,np.nan] for g in ig]);idx=np.flatnonzero(validpoint);tree=cKDTree(xyi[idx]);imeta['valid_points_for_distance']=len(idx);imeta['CSS_NUM_unique']=inter.CSS_NUM.nunique();imeta['CSS_NUM_duplicate_extra']=int(inter.CSS_NUM.duplicated().sum());imeta['crs_identified']='EPSG:5186';imeta['kind_code_counts']=inter.A008_KND_C.value_counts().to_dict();imeta['code_dictionary_present']=False
lmeta['crs_identified']='EPSG:5186';lmeta['kind_code_counts']=lane.A058_KND_C.value_counts().to_dict();lmeta['subkind_code_counts']=lane.A058_KND2_.value_counts().to_dict();lmeta['code_dictionary_present']=False
# Coordinate attributes are retained separately from official point geometry.
attrx=pd.to_numeric(inter.XCE,errors='coerce');attry=pd.to_numeric(inter.YCE,errors='coerce');attrvalid=np.isfinite(np.c_[attrx,attry]).all(axis=1);imeta['XY_attribute_missing_or_nonnumeric_rows']=int((~attrvalid).sum());imeta['XY_attribute_vs_SHP_max_distance_m']=float(np.linalg.norm(np.c_[attrx,attry][attrvalid]-xyi[attrvalid],axis=1).max()) if attrvalid.any() else None;imeta['geometry_coordinate_used']='SHP point; XCE/YCE are audited attributes, not substituted'
save(inter.assign(x5186=xyi[:,0],y5186=xyi[:,1]),'intersection_source_attributes.csv');save(lane,'bus_lane_source_attributes.csv')
monthunits=read(M1/'route_segment_monthly_instability.csv');monthunits=monthunits[monthunits.month.isin(MONTHS)].merge(b[['segment_id','diagnostic_no','is_diagnostic43']+AK],on=AK,how='inner',validate='many_to_one');monthunits['core_evaluable']=monthunits.U_sec.notna()
# Retain endpoints for the background as well, without any new administrative assignment.
geometry=[]
for m in MONTHS:
 c=coords[coords.snapshot.eq(snap[m])].set_index('node_id')
 for u in b.itertuples():
  row={k:getattr(u,k) for k in AK+['segment_id','diagnostic_no','is_diagnostic43','dong_name','route_name']};row.update({'month':m,'snapshot':snap[m],'actual_path_geometry_available':False,'bus_lane_match_status':'held_geometry'})
  for role,nid in [('departure',u.departure_node),('arrival',u.arrival_node)]:
   if nid in c.index:
    x=c.loc[nid];row[role+'_longitude']=float(x.longitude);row[role+'_latitude']=float(x.latitude);row[role+'_x5186']=float(x.x5186);row[role+'_y5186']=float(x.y5186);row[role+'_coordinate_source']=x.coordinate_source;row[role+'_coordinate_held']=str(x.held_coordinate_record).lower()=='true';row[role+'_inside_seoul']=str(x.inside_seoul).lower()=='true'
   else:row[role+'_coordinate_held']=True;row[role+'_inside_seoul']=False
  row['coordinate_ready']=all(not row[role+'_coordinate_held'] and row[role+'_inside_seoul'] for role in ['departure','arrival']);geometry.append(row)
g=pd.DataFrame(geometry).merge(monthunits[['month','segment_id','core_evaluable']],on=['month','segment_id'],validate='one_to_one');save(g,'historical_segment_endpoint_registry.csv.gz')
# Distances to the chord are explicitly proxies. Actual path-distance is never filled.
dist=[]
for u in g[g.is_diagnostic43].itertuples():
 row={k:getattr(u,k) for k in AK+['month','snapshot','segment_id','diagnostic_no','dong_name','route_name','core_evaluable','coordinate_ready']};row['segment_actual_path_nearest_intersection_m']=np.nan;row['actual_path_status']='held_geometry';row['intersection_exposure_flag']=np.nan;row['distance_unit']='m';row['distance_reference']='all valid nondeleted A008_P source points; no type-code interpretation or distance cutoff'
 if u.coordinate_ready and u.core_evaluable:
  a=np.array([u.departure_x5186,u.departure_y5186]);bb=np.array([u.arrival_x5186,u.arrival_y5186]);dep_d,dep_i=tree.query(a);arr_d,arr_i=tree.query(bb);v=bb-a;den=v@v;t=np.clip((xyi[idx]-a)@v/den,0,1) if den>0 else np.zeros(len(idx));dd=np.linalg.norm(xyi[idx]-a-t[:,None]*v,axis=1);ii=int(np.argmin(dd));row.update({'departure_nearest_intersection_m':float(dep_d),'arrival_nearest_intersection_m':float(arr_d),'nearest_of_endpoints_m':float(min(dep_d,arr_d)),'proxy_stop_chord_nearest_point_m':float(dd[ii]),'proxy_stop_chord_length_m':float(np.linalg.norm(v)),'departure_nearest_feature_row':int(inter.feature_row.iloc[idx[dep_i]]),'departure_nearest_CSS_NUM':inter.CSS_NUM.iloc[idx[dep_i]],'departure_nearest_name':inter.CSS_NAM.iloc[idx[dep_i]],'arrival_nearest_feature_row':int(inter.feature_row.iloc[idx[arr_i]]),'arrival_nearest_CSS_NUM':inter.CSS_NUM.iloc[idx[arr_i]],'arrival_nearest_name':inter.CSS_NAM.iloc[idx[arr_i]],'proxy_nearest_feature_row':int(inter.feature_row.iloc[idx[ii]]),'proxy_nearest_CSS_NUM':inter.CSS_NUM.iloc[idx[ii]],'proxy_nearest_name':inter.CSS_NAM.iloc[idx[ii]],'distance_status':'ready_point_and_explicit_chord_proxy_only'})
 else:row['distance_status']='no_Core_month' if not u.core_evaluable else 'held_coordinate'
 dist.append(row)
dist=pd.DataFrame(dist);save(dist,'intersection_distance_audit.csv')
# Historical master sample: official same-month frozen path and basic table, no new download.
with zipfile.ZipFile(MASTER) as z:
 name='서울시버스노선별정류소정보(20260506).xlsx';payload=z.read(name);expected=assignment[(assignment.month.eq('202606'))&assignment.master_kind.eq('노선별정류소정보')].sha256.iloc[0];assert hashlib.sha256(payload).hexdigest()==expected
 import io
 rs=pd.read_excel(io.BytesIO(payload),dtype=str,keep_default_na=False);bs=pd.read_excel(z.open('서울시버스노선기본정보(20260506).xlsx'),dtype=str,keep_default_na=False)
 rcolumns=rs.columns.tolist();rsfull=rs.drop_duplicates();bad=rsfull[rsfull.duplicated(['ROUTE_ID','NODE_ID','순번'],keep=False)];badkeys=set(bad[['ROUTE_ID','NODE_ID','순번']].itertuples(index=False,name=None));rs=rsfull[~rsfull[['ROUTE_ID','NODE_ID','순번']].apply(tuple,axis=1).isin(badkeys)].copy();rs['seq']=pd.to_numeric(rs['순번'],errors='coerce');types=read(F0/'route_type_history.csv');allowed=set(types[(types.month.eq('202606'))&types.main_included].route_id)
rows=[]
for rid,q in rs.groupby('ROUTE_ID',sort=False):
 q=q[q.seq.gt(0)].sort_values('seq');qq=q[['seq','NODE_ID']].merge(q[['seq','NODE_ID']].assign(seq=lambda x:x.seq-1),on='seq',suffixes=('_departure','_arrival'))
 for x in qq.itertuples():
  if x.seq==2:continue
  rows.append({'route_id':rid,'departure_node':x.NODE_ID_departure,'arrival_node':x.NODE_ID_arrival,'main_allowed':rid in allowed})
masterpairs=pd.DataFrame(rows).drop_duplicates();save(masterpairs,'june_master_directed_adjacent_pairs.csv');mastercounts=masterpairs[masterpairs.main_allowed].groupby(['departure_node','arrival_node']).route_id.agg(lambda a:sorted(set(a))).to_dict()
cc=[]
for (m,dong,dep,arr),q in monthunits[monthunits.core_evaluable].groupby(['month']+BK,sort=False):
 routes=sorted(set(q.route_id));masterroute=mastercounts.get((dep,arr),[]) if m=='202606' else None;members=q.segment_id.tolist()
 for x in q.itertuples():cc.append({'month':m,'snapshot':snap[m],'dong_code':dong,'segment_id':x.segment_id,'is_diagnostic43':x.is_diagnostic43,'route_id':x.route_id,'departure_node':dep,'arrival_node':arr,'background_core_shared_unique_routes':len(routes),'background_route_ids':json.dumps(routes),'master_adjacent_Main_route_count_June':len(masterroute) if masterroute is not None else np.nan,'master_route_ids_June':json.dumps(masterroute) if masterroute is not None else '', 'master_count_status':'ready_frozen_20260506' if masterroute is not None else 'background_Core_count_ready; master_count_not_recomputed_outside_June_sample','readiness':'READY','meaning':'ordered stop-pair sharing within observed Core; no physical-road pass-through or vehicle count'})
con=pd.DataFrame(cc);save(con,'route_concentration_readiness.csv')
save(rs,'june_route_stop_master.csv.gz');save(types[types.month.eq('202606')],'june_route_id_name_bridge.csv')
summary={'intersection_metadata':imeta,'lane_metadata':lmeta,'projection':'Inherited Gate2E1 forward/inverse GRS80 TM functions unchanged; EPSG:5186 parameters read from PRJ','projection_roundtrip_max_error_m':err,'frozen_coordinate_source':'F0M coordinate_node_diagnostics.csv; no re-assignment','primary_coordinate_ready_month_rows':int(g[g.is_diagnostic43].coordinate_ready.sum()),'primary_month_rows':int(g.is_diagnostic43.sum()),'primary_Core_evaluable_month_rows':int(g[g.is_diagnostic43].core_evaluable.sum()),'June_primary_coordinate_ready':int(g[g.is_diagnostic43 & g.month.eq('202606')].coordinate_ready.sum()),'verified_path_geometry_segments':0,'geometry_in_master_columns':False,'route_stop_master_columns':rcolumns,'actual_path_lane_overlap_assigned':0,'June_primary_background_shared_routes_min':int(con[con.month.eq('202606')&con.is_diagnostic43].background_core_shared_unique_routes.min()),'June_primary_background_shared_routes_max':int(con[con.month.eq('202606')&con.is_diagnostic43].background_core_shared_unique_routes.max()),'master_exact_key_conflicts_June':len(badkeys)}
dump(summary,'geometry_route_summary.json');print('GEOMETRY_ROUTE_READY',len(dist),'primary-month distance audit rows;',len(con),'observed background segment-month route-count rows',flush=True)
