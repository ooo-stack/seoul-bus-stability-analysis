from common import *
p=units();p=p[p.is_diagnostic43].sort_values('diagnostic_no');roads=pd.read_csv(OUT/'speed_service_link_registry.csv',dtype={'service_link':str});mapping=pd.read_csv(OUT/'service_standard_link_crosswalk.csv',dtype={'service_link':str,'standard_link':str});rs=pd.read_csv(OUT/'june_route_stop_master.csv.gz',dtype=str,keep_default_na=False)
order_missing_services=set(mapping.loc[mapping.standard_link_order.isna(),'service_link']);nonnull=mapping[mapping.standard_link_order.notna()];order_duplicate_services=set(nonnull.loc[nonnull.duplicated(['service_link','standard_link_order'],keep=False),'service_link']);order_ambiguous_services=order_missing_services|order_duplicate_services
nameby={}
for nid,g in rs.groupby('NODE_ID'):nameby[nid]=sorted(set(g['정류소명'].str.strip()))
mapby={k:g.sort_values('standard_link_order').standard_link.tolist() for k,g in mapping.groupby('service_link')};roadby=roads.set_index('service_link').to_dict('index');candidates={};criteria={}
for x in p.itertuples():
 deps=set(nameby.get(x.departure_node,[]));arrs=set(nameby.get(x.arrival_node,[]));cand=[]
 for r in roads.itertuples(index=False,name=None):
  d=dict(zip(roads.columns,r));lid=d['service_link'];starts=set(json.loads(d['시점명_values_json']));ends=set(json.loads(d['종점명_values_json']));tests=[]
  if deps&starts:tests.append('exact_departure_stop_label_to_service_start_label')
  if arrs&ends:tests.append('exact_arrival_stop_label_to_service_end_label')
  if deps&ends:tests.append('exact_departure_stop_label_to_service_end_label')
  if arrs&starts:tests.append('exact_arrival_stop_label_to_service_start_label')
  if tests:
   if deps&starts and arrs&ends:tests.append('both_endpoint_labels_same_direction')
   if deps&ends and arrs&starts:tests.append('both_endpoint_labels_reverse_direction')
   cand.append(lid);criteria[(x.segment_id,lid)]=tests
 candidates[x.segment_id]=cand
owners={lid:set(sid for sid,c in candidates.items() if lid in c) for c in candidates.values() for lid in c}
rows=[]
for x in p.itertuples():
 cand=candidates[x.segment_id]
 for lid in cand or ['']:
  rr=roadby.get(lid,{});owner=len(owners.get(lid,set()));n=len(cand)
  card='unmatched' if n==0 else 'one_to_one_candidate' if n==1 and owner==1 else 'one_to_many_candidate' if n>1 and owner==1 else 'many_to_one_candidate' if n==1 and owner>1 else 'many_to_many_candidate'
  rows.append({'segment_id':x.segment_id,'diagnostic_no':x.diagnostic_no,'dong_name':x.dong_name,'route_id':x.route_id,'departure_node':x.departure_node,'arrival_node':x.arrival_node,'month':'202606','snapshot':'20260506','departure_master_labels_json':json.dumps(nameby.get(x.departure_node,[]),ensure_ascii=False),'arrival_master_labels_json':json.dumps(nameby.get(x.arrival_node,[]),ensure_ascii=False),'candidate_service_link':lid,'name_candidate_count':n,'candidate_owner_bus_segments':owner,'candidate_cardinality':card,'candidate_name_criteria':';'.join(criteria.get((x.segment_id,lid),[])),'road_names_json':rr.get('도로명_values_json',''),'service_start_names_json':rr.get('시점명_values_json',''),'service_end_names_json':rr.get('종점명_values_json',''),'direction_values_json':rr.get('방향_values_json',''),'standard_links_in_mapping_order_json':json.dumps(mapby.get(lid,[])),'n_mapped_standard_links':len(set(mapby.get(lid,[]))),'source_mapping_order_ambiguous':lid in order_ambiguous_services,'source_mapping_order_missing':lid in order_missing_services,'source_mapping_nonnull_order_duplicate':lid in order_duplicate_services,'bus_to_speed_exact_key_available':False,'verified_bus_link_match':False,'verified_bus_link_cardinality':'unmatched_missing_bus_road_crosswalk','candidate_match_category':'ambiguous_name_candidate' if n else 'unmatched','road_speed_match_status':'held_geometry','candidate_use':'manual-review lead only; no nearest-road assignment, exposure or cause inference'})
out=pd.DataFrame(rows);save(out,'road_speed_match_candidates.csv');unit=out.drop_duplicates('segment_id');dump({'Primary_segments':len(unit),'verified_bus_road_link_matches':0,'segments_with_exact_name_candidates':int(unit.name_candidate_count.gt(0).sum()),'segments_without_exact_name_candidates':int(unit.name_candidate_count.eq(0).sum()),'candidate_rows':int(out.candidate_service_link.ne('').sum()),'candidate_cardinality_counts':out.candidate_cardinality.value_counts().to_dict(),'all_verified_categories':'unmatched_missing_bus_road_crosswalk','name_candidates_are_not_verified_spatial_matches':True},'road_candidate_summary.json');print('ROAD_CANDIDATES_READY',len(out),'rows',flush=True)
