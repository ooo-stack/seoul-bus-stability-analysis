from common import *
from inherited_tm_projection import forward_tm
from vtkmodules.vtkGeovisCore import vtkGeoProjection,vtkGeoTransform
b=units();p=b[b.is_diagnostic43];s=read(OUT/'segment_environment_match_status.csv');assert len(s)==43 and set(s.segment_id)==set(p.segment_id);assert s.bus_lane_match_status.eq('held_geometry').all();assert s.bus_lane_overlap_m.isna().all();assert s.actual_path_nearest_intersection_m.isna().all();assert s.road_speed_verified_link_count.eq(0).all()
assert sha(M1/'dong_max_recurrence_route_segments.csv')=='ba14af3923db5afcba165e873b3a7ae3c7c627950007b5ed483d98e4c860264f';assert sha(M1/'route_segment_recurrence.csv')=='cbdfb27c42162358e0d086abc965d440765cdd3407fb14a6a1b81e7db9e9f65c'
# Independent nearest-point and point-to-chord calculations, no distance cutoff.
d=read(OUT/'intersection_distance_audit.csv');points=pd.read_csv(OUT/'intersection_source_attributes.csv');xy=points[['x5186','y5186']].to_numpy();g=read(OUT/'historical_segment_endpoint_registry.csv.gz').set_index(['month','segment_id']);valid=d[d.core_evaluable&d.coordinate_ready]
for x in valid.itertuples():
 z=g.loc[(x.month,x.segment_id)];aa=np.array([z.departure_x5186,z.departure_y5186]);bb=np.array([z.arrival_x5186,z.arrival_y5186]);da=np.linalg.norm(xy-aa,axis=1);db=np.linalg.norm(xy-bb,axis=1);assert np.isclose(da.min(),x.departure_nearest_intersection_m,atol=1e-8);assert np.isclose(db.min(),x.arrival_nearest_intersection_m,atol=1e-8)
 vec=bb-aa;length=np.linalg.norm(vec);dot=(xy-aa)@vec;cross=(xy[:,0]-aa[0])*vec[1]-(xy[:,1]-aa[1])*vec[0];chord=np.where(dot<0,da,np.where(dot>length*length,db,np.abs(cross)/length));assert np.isclose(chord.min(),x.proxy_stop_chord_nearest_point_m,atol=1e-8)
assert d.segment_actual_path_nearest_intersection_m.isna().all() and d.intersection_exposure_flag.isna().all();assert d[~d.core_evaluable].departure_nearest_intersection_m.isna().all()
# Projection cross-check using independently implemented installed PROJ through VTK.
proj=vtkGeoProjection();proj.SetPROJ4String('+proj=tmerc +lat_0=38 +lon_0=127 +k=1 +x_0=200000 +y_0=600000 +ellps=GRS80 +units=m +no_defs');tr=vtkGeoTransform();tr.SetDestinationProjection(proj);june=g.loc['202606'];ll=june[june.is_diagnostic43][['departure_longitude','departure_latitude']].to_numpy();calc=forward_tm(ll[:,0],ll[:,1],127.,1.,200000.,600000.);ref=np.array([tr.TransformPoint(float(x),float(y),0)[:2] for x,y in ll]);projerr=float(np.linalg.norm(calc-ref,axis=1).max());assert projerr<.001
# Every ridership number is one source cell, never averaged or summed over duplicate occurrences.
r=pd.read_csv(RIDER,encoding='cp949',dtype=str,keep_default_na=False);r['source_row']=np.arange(len(r))+2;r['token']=r.역명.str.extract(r'\((\d+)\)$',expand=False).map(lambda t:str(int(t)) if isinstance(t,str) else '')
a=read(OUT/'ridership_match_audit.csv');bridge=read(OUT/'june_route_id_name_bridge.csv').set_index('route_id').route_name.to_dict()
for x in a.itertuples():
 for role,node in [('departure',x.departure_node),('arrival',x.arrival_node)]:
  q=r[(r.노선번호.eq(bridge[x.route_id]))&r.표준버스정류장ID.eq(node)];assert len(q)==getattr(x,role+'_raw_records');board=('00' if x.hour==0 else str(x.hour))+'시승차총승객수';alight=('00' if x.hour==0 else str(x.hour))+'시하차총승객수'
  if len(q)==1:assert getattr(x,role+'_boarding_events')==float(q[board].iloc[0]) and getattr(x,role+'_alighting_events')==float(q[alight].iloc[0])
  else:assert np.isnan(getattr(x,role+'_boarding_events')) and np.isnan(getattr(x,role+'_alighting_events'))
  sr=getattr(x,role+'_candidate_source_row')
  if not np.isnan(sr):
   qq=r[r.source_row.eq(int(sr))].iloc[0];assert qq.token==str(int(getattr(x,role+'_sequence')));assert getattr(x,role+'_boarding_events_sequence_candidate')==float(qq[board]);assert getattr(x,role+'_alighting_events_sequence_candidate')==float(qq[alight])
# Count unique routes from the separately stored M2 hourly B contributors.
con=read(OUT/'route_concentration_readiness.csv');hour=read(M2/'stop_pair_hour_monthly.csv.gz');sets={}
for key,q in hour.groupby(['month']+BK):sets[key]=set(v for x in q.contributing_route_ids for v in str(x).split(',') if v)
for x in con.itertuples():assert x.background_core_shared_unique_routes==len(sets[(x.month,x.dong_code,x.departure_node,x.arrival_node)])
assert con.segment_id.nunique()==758
j=con[con.month.eq('202606')&con.is_diagnostic43];assert j.background_core_shared_unique_routes.le(j.master_adjacent_Main_route_count_June).all()
road=read(OUT/'road_speed_match_candidates.csv');assert not road.verified_bus_link_match.any();assert road.segment_id.nunique()==43
rawmap=pd.read_excel(MAPPING,dtype=str,keep_default_na=False);registry=pd.read_csv(OUT/'speed_service_link_registry.csv',dtype={'service_link':str});exact=len(set(registry.service_link)&set(rawmap['서비스링크']));assert exact==5052
for zpath in [MASTER,INTERSECTION,LANE]:
 with zipfile.ZipFile(zpath) as z:assert z.testzip() is None
for f in OUT.rglob('*.csv.gz'):gzip.decompress(f.read_bytes())
result={'status':'PASS','fixed_Primary_43_unchanged':True,'background_758_retained':True,'frozen_coordinate_master_inherited':True,'nearest_distances_independently_checked_rows':len(valid),'projection_independent_max_difference_m':projerr,'actual_path_distances_and_lane_overlap_remain_NA':True,'no_road_candidate_accepted_as_verified_link':True,'ridership_all_selected_values_equal_single_source_cells':True,'ambiguous_ridership_rows_not_aggregated':True,'background_route_counts_checked_against_M2_hourly_B':True,'external_environment_correlations_or_effects_calculated':False,'new_cutoffs_or_cohort_selection':False}
dump(result,'verification_results.json');print(json.dumps(result,ensure_ascii=False),flush=True)
