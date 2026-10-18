"""External-exposure audit only. Never opens a bus outcome table."""
from pathlib import Path
import pandas as pd,numpy as np,json,csv,zipfile,io,hashlib,struct,sys,math,datetime
from vtkmodules.vtkGeovisCore import vtkGeoProjection,vtkGeoTransform

BASE=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd().resolve()
META=BASE/'c2a_metadata';OUT=BASE/'Gate4C2A';STAGE=OUT/'staging'
for p in [OUT,STAGE]:p.mkdir(exist_ok=True)
MONTHS=['202509','202510','202601','202602','202603','202604','202605','202606']
CASES={'11140520':'소공동','11140570':'필동','11620695':'신림동','11680510':'신사동(강남구)','11680610':'대치2동','11680660':'개포1동','11710650':'잠실본동','11710710':'잠실6동','11710720':'잠실7동'}
SETS=['LOCAL_PEOPLE_DONG','LONG_FOREIGNER_DONG','TEMP_FOREIGNER_DONG']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x): (OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def save(n,df):df.to_csv(STAGE/n,index=False,encoding='utf-8-sig',na_rep='')
def numeric(s):return pd.to_numeric(s,errors='coerce')

# Freeze before detailed exposure QC or candidate selection. These are data-quality rules.
RULES={'version':'C2A-1.0','created_at_kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'months':MONTHS,'cases':CASES,'bus_outcome_access':False,'living_parse':'UTF8 BOM CSV; preserve header fields; discard only verified all-empty final surplus field','living_duplicate_rule':'exact duplicate one observation; conflicting full record for same date/hour/code held; no averaging','living_non_numeric':'blank/suppressed/non-numeric/negative total -> NA with distinct status; zero preserved','living_baseline':'same component/code/month/weekday/hour, planned ordinary weekdays only, exposure-observed dates regardless of bus-day presence; all-calendar baseline auxiliary','baseline_self_inclusion':'includes current eligible date; n disclosed; no new sample cutoff','relative':'deviation/baseline only if baseline>0 and finite; else NA','living_components':'separate; no total until independent explicit official aggregation authorization','station_candidate_rule':'nearest of uploaded Seoul AWS current official coordinates to fixed polygon interior point; distance order fixed; missing-data rule independent of outcomes','station_coverage_rule':'temperature AND rainfall each >=90% valid hours in every Main calendar month to qualify one fixed station across Main; quality threshold only','station_history_rule':'historical location validity must be verified before Main station certification; current coordinates are provisional','fallback':'fixed next-nearest qualifying station for whole period if coverage failure; do not fill individual missing hours; missing historical metadata is not a reason to declare location valid','time':'KST retain native timestamps; rainfall prior-hour interval candidate, temperature instant; no bus join before bus hour boundary and source field equivalence confirmed','rain':'positive ->1; observed zero->0; missing/conflict/invalid->NA','temperature':'continuous; no hot/cold threshold','jan':'include Main, exclude whole January only for future QA, no date-specific deletion'}
dump('exposure_rule_freeze.json',RULES)

# Metadata calendar only: explicitly deny bus availability/value fields.
cal=pd.read_csv(BASE/'c2a_inputs/day_calendar.csv',dtype=str,usecols=['month','date','weekday','holiday_name','planned_weekday'],keep_default_na=False)
cal=cal[cal['month'].isin(MONTHS)].copy()
cal['planned_weekday']=cal['planned_weekday'].eq('True')
cal['timestamp']=pd.to_datetime(cal['date'],format='%Y%m%d');cal['weekday_num']=cal.timestamp.dt.dayofweek+1
assert cal.date.is_unique
dates=cal[['date','month','weekday_num','holiday_name','planned_weekday']]
grid=pd.MultiIndex.from_product([list(CASES),cal.date.tolist(),range(24)],names=['dong_code','date','hour']).to_frame(index=False)
grid=grid.merge(dates,on='date',validate='many_to_one');grid['dong_name']=grid.dong_code.map(CASES)
grid['timestamp_kst']=pd.to_datetime(grid.date,format='%Y%m%d')+pd.to_timedelta(grid.hour,unit='h')
grid['timestamp_kst']=grid.timestamp_kst.dt.strftime('%Y-%m-%dT%H:00:00+09:00')
grid['hour']=grid.hour.astype(int)

audits=[];panels=[];codes_by_source={};headers_ref={};monthly_selected=[];duplicate_details=[]
for component in SETS:
 for month in MONTHS:
  p=META/f'{component}_{month}.zip'
  assert p.exists() and zipfile.is_zipfile(p),str(p)
  with zipfile.ZipFile(p) as z:
   names=[n for n in z.namelist() if n.lower().endswith('.csv')]
   assert len(names)==1,(p,names)
   try: z.open(names[0]).read(4096).decode('utf-8-sig');encoding='utf-8-sig'
   except UnicodeDecodeError:encoding='cp949'
   header=next(csv.reader(io.TextIOWrapper(z.open(names[0]),encoding=encoding)))
   # Detect the surplus field from a data record, not inferred DataFrame indexing.
   rr=csv.reader(io.TextIOWrapper(z.open(names[0]),encoding=encoding));next(rr);sample=next(rr)
   assert len(sample) in (len(header),len(header)+1)
   extra=len(sample)-len(header);names_read=header+(['__surplus_empty'] if extra else [])
   a={'component':component,'month':month,'source_file':p.name,'source_sha256':sha(p),'zip_member':names[0],'encoding':encoding,'column_count':len(header),'columns_json':json.dumps(header,ensure_ascii=False),'schema_changed':component in headers_ref and header!=headers_ref[component],'data_surplus_empty_column':extra,'rows':0,'empty_surplus_field_rows':0,'nonempty_surplus_field_rows':0,'missing_key_rows':0,'invalid_date_rows':0,'invalid_hour_rows':0,'invalid_code_rows':0,'blank_numeric_cells':0,'suppressed_numeric_cells':0,'other_non_numeric_cells':0,'negative_total_rows':0,'total_blank_rows':0,'total_suppressed_rows':0,'total_other_non_numeric_rows':0,'selected_rows':0,'selected_total_suppressed':0,'selected_total_blank':0,'selected_total_other_non_numeric':0,'name_field_present':False,'name_source':'official code archive; raw name field absent'}
   headers_ref.setdefault(component,header)
   unique_dates=set();unique_hours=set();unique_codes=set();keys=[];selected=[];all_numerics=header[3:];missing_by_col={c:0 for c in header};supp_by_col={c:0 for c in all_numerics};bad_by_col={c:0 for c in all_numerics}
   for d in pd.read_csv(z.open(names[0]),names=names_read,skiprows=1,dtype=str,keep_default_na=False,encoding=encoding,chunksize=50000,index_col=False):
    a['rows']+=len(d)
    if extra:
     a['empty_surplus_field_rows']+=int(d['__surplus_empty'].eq('').sum());a['nonempty_surplus_field_rows']+=int(d['__surplus_empty'].ne('').sum());assert d['__surplus_empty'].eq('').all()
    validdate=pd.to_datetime(d[header[0]],format='%Y%m%d',errors='coerce').notna()
    validhour=d[header[1]].str.fullmatch(r'\d{2}') & numeric(d[header[1]]).between(0,23)
    validcode=d[header[2]].str.fullmatch(r'\d{8}')
    a['invalid_date_rows']+=int((~validdate).sum());a['invalid_hour_rows']+=int((~validhour).sum());a['invalid_code_rows']+=int((~validcode).sum());a['missing_key_rows']+=int(d[header[:3]].eq('').any(axis=1).sum())
    assert validdate.all() and validhour.all() and validcode.all()
    k=d[header[0]].astype('int64')*10000000000+d[header[2]].astype('int64')*100+d[header[1]].astype('int64');keys.append(k.to_numpy())
    unique_dates.update(d[header[0]]);unique_hours.update(d[header[1]]);unique_codes.update(d[header[2]])
    for c in header: missing_by_col[c]+=int(d[c].eq('').sum())
    for c in all_numerics:
     blank=d[c].eq('');supp=d[c].eq('*');num=numeric(d[c]);bad=num.isna()&~blank&~supp
     a['blank_numeric_cells']+=int(blank.sum());a['suppressed_numeric_cells']+=int(supp.sum());a['other_non_numeric_cells']+=int(bad.sum());supp_by_col[c]+=int(supp.sum());bad_by_col[c]+=int(bad.sum())
    raw=d[header[3]];nv=numeric(raw)
    a['total_blank_rows']+=int(raw.eq('').sum());a['total_suppressed_rows']+=int(raw.eq('*').sum());a['total_other_non_numeric_rows']+=int((nv.isna()&~raw.isin(['','*'])).sum());a['negative_total_rows']+=int(nv.lt(0).sum())
    s=d[d[header[2]].isin(CASES)].copy();a['selected_rows']+=len(s)
    sv=numeric(s[header[3]]);a['selected_total_suppressed']+=int(s[header[3]].eq('*').sum());a['selected_total_blank']+=int(s[header[3]].eq('').sum());a['selected_total_other_non_numeric']+=int((sv.isna()&~s[header[3]].isin(['','*'])).sum())
    selected.append(s[header])
   keyarr=np.concatenate(keys);uni,cnt=np.unique(keyarr,return_counts=True);dupkeys=set(uni[cnt>1].tolist())
   a['duplicate_key_groups']=len(dupkeys);a['duplicate_key_extra_rows']=int((cnt[cnt>1]-1).sum());a['exact_duplicate_extra_rows']=0;a['conflicting_key_groups']=0
   conflict=set()
   if dupkeys:
    dup=[]
    for d in pd.read_csv(z.open(names[0]),names=names_read,skiprows=1,dtype=str,keep_default_na=False,encoding=encoding,chunksize=50000,index_col=False):
     k=d[header[0]].astype('int64')*10000000000+d[header[2]].astype('int64')*100+d[header[1]].astype('int64')
     dup.append(d.loc[k.isin(dupkeys),header])
    du=pd.concat(dup,ignore_index=True);a['exact_duplicate_extra_rows']=int(du.duplicated().sum());dd=du.drop_duplicates();g=dd.groupby(header[:3],dropna=False).size();bad=g[g>1]
    a['conflicting_key_groups']=len(bad)
    for key,n in bad.items():
     conflict.add(tuple(key));duplicate_details.append({'component':component,'month':month,'date':key[0],'hour':key[1],'dong_code':key[2],'distinct_full_rows':int(n),'handling':'held_conflict'})
   s=pd.concat(selected,ignore_index=True).drop_duplicates()
   if conflict:
    conflict_mask=s[header[:3]].apply(tuple,axis=1).isin(conflict)
   else:conflict_mask=pd.Series(False,index=s.index)
   s=s.drop_duplicates(header[:3],keep='first').copy()
   # Conflicts stay in the audit but no arbitrary full-row value is used.
   conflicted=s[header[:3]].apply(tuple,axis=1).isin(conflict) if conflict else pd.Series(False,index=s.index)
   raw=s[header[3]];v=numeric(raw)
   status=np.select([conflicted,raw.eq(''),raw.eq('*'),v.isna(),v.lt(0)],['held_conflict','missing','suppressed','non_numeric','invalid_negative'],default='observed')
   s2=pd.DataFrame({'date':s[header[0]],'hour':s[header[1]].astype(int),'dong_code':s[header[2]],'component_raw':raw,'living_population':v.mask(status!='observed'),'value_status':status})
   pane=grid.merge(s2,on=['date','hour','dong_code'],how='left',validate='one_to_one');pane['component']=component;pane['source_file']=p.name
   pane=pane[pane.month.eq(month)].copy();pane['value_status']=pane.value_status.fillna('row_absent');pane['component_raw']=pane.component_raw.fillna('')
   # Main baseline excludes holidays and weekends, but never consults bus presence.
   groups=['dong_code','month','weekday_num','hour']
   valid=pane[pane.planned_weekday & pane.value_status.eq('observed')]
   baseline=valid.groupby(groups).living_population.agg(baseline_living_population_median='median',baseline_valid_dates='count').reset_index()
   pane=pane.merge(baseline,on=groups,how='left',validate='many_to_one')
   aux=pane[pane.value_status.eq('observed')].groupby(groups).living_population.agg(all_calendar_baseline_aux='median',all_calendar_baseline_n_aux='count').reset_index()
   pane=pane.merge(aux,on=groups,how='left',validate='many_to_one')
   eligible=pane.planned_weekday & pane.value_status.eq('observed')
   pane['daily_activity_deviation']=(pane.living_population-pane.baseline_living_population_median).where(eligible)
   pane['relative_activity_deviation']=(pane.daily_activity_deviation/pane.baseline_living_population_median).where(eligible & pane.baseline_living_population_median.gt(0))
   pane['baseline_reference']='planned_ordinary_weekdays;component/dong/month/weekday/hour;self_included'
   pane['living_name_source']='official supplied ADMI monthly code table; raw has no name'
   pane['code_match_status']='exact_code_present;2016_boundary_equivalence_unverified'
   pane['exposure_readiness']='CONDITIONAL';pane['approved_for_bus_join']=False
   panels.append(pane)
   a.update(min_date=min(unique_dates),max_date=max(unique_dates),unique_dates=len(unique_dates),hour_min=min(unique_hours),hour_max=max(unique_hours),unique_hours=len(unique_hours),unique_codes=len(unique_codes),codes_json=json.dumps(sorted(unique_codes)),missing_by_column_json=json.dumps(missing_by_col,ensure_ascii=False),suppressed_by_column_json=json.dumps(supp_by_col,ensure_ascii=False),nonnumeric_by_column_json=json.dumps(bad_by_col,ensure_ascii=False),case_rows=len(pane),case_observed_rows=int(pane.value_status.eq('observed').sum()),case_absent_rows=int(pane.value_status.eq('row_absent').sum()))
   audits.append(a);codes_by_source[(component,month)]=unique_codes
   print('living audited',component,month,a['rows'],'selected observed',a['case_observed_rows'],'duplicates',a['duplicate_key_groups'],flush=True)
living=pd.concat(panels,ignore_index=True).sort_values(['dong_code','date','hour','component'])
save('living_population_exposure_panel.csv',living);save('living_population_schema_audit.csv',pd.DataFrame(audits))
save('living_population_duplicate_details.csv',pd.DataFrame(duplicate_details,columns=['component','month','date','hour','dong_code','distinct_full_rows','handling']))

# Crosswalk: prove exact code and official supplied table; do not invent 2016 boundary equivalence.
code_archive=BASE/'project_sources/04-_-_-.zip'
assert sha(code_archive)==sha(META/'living_code_official.download')
cross=[]
with zipfile.ZipFile(code_archive) as z:
 for m in MONTHS:
  tab=pd.read_csv(z.open(f'SEOUL_ADMI/ADMI_{m}.csv'),dtype=str,keep_default_na=False);tab=tab[tab.SIDO_NM.eq('서울특별시')]
  for c,n in CASES.items():
   rows=tab[tab.ADMI_CD.eq(c)];assert len(rows)==1
   r=rows.iloc[0]
   cross.append({'month':m,'research_dong_code':c,'research_dong_name':n,'living_population_code':c,'living_population_name':r.ADMI_NM,'living_population_district':r.SGG_NM,'name_provenance':f'official supplied ADMI_{m}.csv; raw population has no name column','mapping_type':'exact_code_match_no_reallocation','official_code_archive_identical':True,'code_present_all_three_components':all(c in codes_by_source[(s,m)] for s in SETS),'current_code_table_seoul_rows':len(tab),'living_raw_code_count':len(codes_by_source[(SETS[0],m)]),'boundary_2016_to_2026_equivalence_verified':False,'readiness':'CONDITIONAL','hold_reason':'same code does not prove unchanged boundary; need official 2016 correspondence/boundary-change confirmation'})
save('living_population_dong_crosswalk.csv',pd.DataFrame(cross))

# Fixed geometry only; no stop/segment outcome data is read.
geo_meta=json.loads((BASE/'c2a_inputs/spatial_asset_verification.json').read_text())
for fn,expected in geo_meta['sha256'].items():assert sha(BASE/fn)==expected
sys.path.insert(0,str(BASE/'c2a_inputs'))
from inherited_geometry_functions import read_shp,locate
with zipfile.ZipFile(BASE/'project_sources/02-_-_-.zip') as z:
 for ext in ['shp','dbf','shx']:
  p=BASE/'c2a_inputs'/f'TL_SCCO_GEMD.{ext}';p.write_bytes(z.read(f'11000/TL_SCCO_GEMD.{ext}'))
B,polys=read_shp(BASE/'c2a_inputs/TL_SCCO_GEMD');assert len(B)==427
proj=vtkGeoProjection();proj.SetPROJ4String('+proj=tmerc +lat_0=38 +lon_0=127.5 +k=0.9996 +x_0=1000000 +y_0=2000000 +ellps=GRS80 +units=m +no_defs')
fw=vtkGeoTransform();fw.SetDestinationProjection(proj);inv=vtkGeoTransform();inv.SetSourceProjection(proj)
assert np.allclose(fw.TransformPoint(127.5,38,0)[:2],[1000000,2000000])
def internal_point(rings):
 pts=np.vstack(rings);ys=np.unique(pts[:,1]);mid=(ys[0]+ys[-1])/2
 ys_mid=(ys[:-1]+ys[1:])/2;y=ys_mid[np.argmin(np.abs(ys_mid-mid))]
 xs=[]
 for ring in rings:
  for a,b in zip(ring,np.roll(ring,-1,axis=0)):
   if (a[1]>y)!=(b[1]>y):xs.append(a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1]))
 xs=sorted(xs);assert len(xs)%2==0
 ints=[(xs[i+1]-xs[i],xs[i],xs[i+1]) for i in range(0,len(xs),2)];_,l,r=max(ints,key=lambda x:(x[0],-x[1]))
 return np.array([(l+r)/2,y])
points={}
for code in CASES:
 i=B.index[B.EMD_CD.eq(code+'00')][0];xy=internal_point(polys[i]);hit,n,edge=locate(xy[None,:],B.EMD_CD.to_numpy(),polys);assert hit[0]==code+'00' and n[0]==1 and not edge[0]
 lon,lat,_=inv.TransformPoint(float(xy[0]),float(xy[1]),0);assert np.linalg.norm(np.array(fw.TransformPoint(lon,lat,0)[:2])-xy)<0.01
 points[code]={'x_5179':float(xy[0]),'y_5179':float(xy[1]),'longitude':lon,'latitude':lat,'method':'scanline nearest bbox middle between distinct vertex y levels; midpoint of longest even-odd interior interval','inside_verified':True}
dump('representative_point_QA.json',{'boundary_sha256':sha(BASE/'project_sources/02-_-_-.zip'),'CRS':'EPSG:5179 inherited from F0M; no PRJ in original','method':'deterministic internal scanline point, not centroid','points':points})

# Native meteorological panel: keys aligned by station/time only.
weather_specs=[('temperature_c','OBS_AWS_TIM_20261017002148.xls','기온(°C)'),('precipitation_mm','OBS_AWS_TIM_20261017002756.xls','강수량(mm)'),('wind_speed_m_s','OBS_AWS_TIM_20261017002354.xls','풍속(m/s)'),('wind_direction_deg','OBS_AWS_TIM_20261017002354.xls','풍향(deg)'),('relative_humidity_pct','OBS_AWS_TIM_20261017002854.xls','습도(%)')]
loaded={};station_blocks=[];raw_audits=[];station_meta=json.loads((META/'seoul_station_current_metadata.json').read_text());metadata={r['awsId']:r for r in station_meta}
for var,filename,col in weather_specs:
 if filename not in loaded:loaded[filename]=pd.read_csv(BASE/'upload'/filename,sep='\t',encoding='cp949',dtype=str,keep_default_na=False)
 d=loaded[filename].copy();assert not d.duplicated(['지점','일시']).any()
 d['timestamp']=pd.to_datetime(d['일시'],format='%Y-%m-%d %H:%M',errors='coerce');assert d.timestamp.notna().all()
 d['month']=d.timestamp.dt.strftime('%Y%m');d['date']=d.timestamp.dt.strftime('%Y%m%d');d['hour']=d.timestamp.dt.hour
 raw=d[col];num=numeric(raw);sentinel=num.isin([-99,-99.9,-999,-9999]);invalid=sentinel | (num.lt(0) if var!='temperature_c' else False)
 st=np.select([raw.eq(''),num.isna(),invalid],['missing_cell','non_numeric','invalid_or_sentinel'],default='observed')
 d[var]=num.mask(st!='observed');d[var+'_status']=st
 for (sid,m),g in d[d.month.isin(MONTHS)].groupby(['지점','month']):
  expected=pd.Period(m,freq='M').days_in_month*24
  row={'network':'AWS','station_id':sid,'station_name':g['지점명'].iloc[0],'month':m,'variable':var,'source_file':filename,'source_sha256':sha(BASE/'upload'/filename),'source_rows':len(d),'station_month_rows':len(g),'expected_hours':expected,'observed_valid_hours':int(g[var].notna().sum()),'missing_row_hours':expected-len(g),'blank_cells':int(g[col].eq('').sum()),'non_numeric_cells':int((numeric(g[col]).isna()&g[col].ne('')).sum()),'invalid_or_sentinel_cells':int(g[var+'_status'].eq('invalid_or_sentinel').sum()),'coverage':g[var].notna().sum()/expected,'duplicate_keys':0,'field_present':True,'QC_flag_present':False,'latitude_field_present_in_upload':False,'longitude_field_present_in_upload':False,'station_current_latitude':metadata.get(sid,{}).get('lat',''),'station_current_longitude':metadata.get(sid,{}).get('lon',''),'coordinates_source':'official weather.go.kr current metadata, historical validity not certified','historical_location_verified':False,'readiness':'CONDITIONAL'}
  raw_audits.append(row)
 station_blocks.append(d[['지점','지점명','timestamp',var,var+'_status']])
aws=None
for d in station_blocks:
 cols=['지점','timestamp']+[c for c in d.columns if c not in ['지점','지점명','timestamp']]
 aws=d[cols] if aws is None else aws.merge(d[cols],on=['지점','timestamp'],how='outer',validate='one_to_one')
aws['month']=aws.timestamp.dt.strftime('%Y%m');aws=aws[aws.month.isin(MONTHS)]
all_stations=sorted(aws['지점'].unique(),key=int)
qa=pd.DataFrame(raw_audits)
coverage=qa[qa.variable.isin(['temperature_c','precipitation_mm'])].groupby('station_id').coverage.agg(['min','count'])
eligible={sid:bool(r['min']>=0.90 and r['count']==len(MONTHS)*2) for sid,r in coverage.iterrows()}
aws['date']=aws.timestamp.dt.strftime('%Y%m%d');aws['hour']=aws.timestamp.dt.hour
crossw=[];distances=[];weather=[]
asos=pd.read_csv(BASE/'upload/OBS_ASOS_TIM_20261016132020.xls',sep='\t',encoding='cp949',dtype=str,keep_default_na=False)
assert not asos.duplicated(['지점','일시']).any();asos['date']=pd.to_datetime(asos['일시']).dt.strftime('%Y%m%d');asos['hour']=pd.to_datetime(asos['일시']).dt.hour;asos['month']=pd.to_datetime(asos['일시']).dt.strftime('%Y%m')
snow=numeric(asos['적설(cm)']);asos['asos_snow_depth_cm_raw_observed']=snow;asos['asos_snow_raw_status']=np.where(asos['적설(cm)'].eq(''),'missing_or_no_report_not_zero','observed')
asos['asos_phenomenon_code_raw']=asos['현상번호(국내식)'];asos['asos_phenomenon_status']=np.where(asos['현상번호(국내식)'].eq(''),'no_report_definition_unconfirmed','reported')
asos=asos[asos.month.isin(MONTHS)]
for code,name in CASES.items():
 pt=points[code];cand=[]
 for sid in all_stations:
  assert sid in metadata,sid
  r=metadata[sid];x,y,_=fw.TransformPoint(float(r['lon']),float(r['lat']),0)
  dist=math.hypot(x-pt['x_5179'],y-pt['y_5179']);cand.append((dist,int(sid),sid))
 cand.sort();nearest=cand[0][2];selected=next((sid for dist,n,sid in cand if eligible.get(sid,False)),None)
 for rank,(dist,n,sid) in enumerate(cand,1):distances.append({'dong_code':code,'dong_name':name,'station_id':sid,'station_name':metadata[sid]['nameKo'],'distance_m':dist,'distance_rank':rank,'coverage_eligible':eligible.get(sid,False),'historical_location_verified':False})
 dist=next(d for d,n,s in cand if s==selected) if selected else None
 crossw.append({'dong_code':code,'dong_name':name,**pt,'CRS':'EPSG:5179','nearest_aws_id':nearest,'nearest_aws_name':metadata[nearest]['nameKo'],'nearest_distance_m':cand[0][0],'candidate_main_aws_id':selected,'candidate_main_aws_name':metadata[selected]['nameKo'] if selected else '', 'candidate_distance_m':dist,'coverage_fallback_used':selected!=nearest,'candidate_min_monthly_temp_rain_coverage':coverage.loc[selected,'min'] if selected else None,'main_period_operation_observed':bool(selected and coverage.loc[selected,'count']==16),'official_operating_start_end_verified':False,'historical_location_verified':False,'station_assignment_status':'CONDITIONAL','hold_reason':'current official coordinates only; historical station location/operating metadata and bus time boundary need confirmation','approved_for_bus_join':False})
 w=grid[grid.dong_code.eq(code)].copy()
 if selected:
  sd=aws[aws['지점'].eq(selected)].drop(columns=['month','timestamp','지점'])
  w=w.merge(sd,on=['date','hour'],how='left',validate='one_to_one')
  for var,filename,col in weather_specs:w[var+'_status']=w[var+'_status'].fillna('row_absent')
 else:
  for var,filename,col in weather_specs:w[var]=np.nan;w[var+'_status']='no_coverage_eligible_station'
 w['aws_station_id']=selected;w['aws_station_distance_m']=dist;w['rain_flag']=np.where(w.precipitation_mm.gt(0),1,np.where(w.precipitation_mm.eq(0),0,np.nan))
 w['precip_interval_candidate_start_kst']=(pd.to_datetime(w.timestamp_kst)-pd.Timedelta(hours=1)).dt.strftime('%Y-%m-%dT%H:00:00+09:00')
 w['precip_interval_candidate_end_kst']=w.timestamp_kst
 w=w.merge(asos[['date','hour','asos_snow_depth_cm_raw_observed','asos_snow_raw_status','asos_phenomenon_code_raw','asos_phenomenon_status']],on=['date','hour'],how='left',validate='one_to_one')
 w['asos_station_id']='108';w['station_assignment_status']='CONDITIONAL';w['time_join_status']='CONDITIONAL_bus_hour_boundary_and_export_rain_field_definition';w['exposure_readiness']='CONDITIONAL';w['approved_for_bus_join']=False
 weather.append(w)
save('weather_exposure_panel.csv',pd.concat(weather,ignore_index=True).sort_values(['dong_code','date','hour']))
save('dong_weather_station_crosswalk.csv',pd.DataFrame(crossw));save('dong_aws_distance_candidates.csv',pd.DataFrame(distances))
# Field inventory is explicit; absent variables are not synthesized.
for var,col in [('temperature_c','기온(°C)'),('precipitation_mm','강수량(mm)'),('wind_speed_m_s','풍속(m/s)'),('relative_humidity_pct','습도(%)'),('snow_depth_cm','적설(cm)'),('phenomenon_code','현상번호(국내식)')]:
 for m,g in asos.groupby('month'):
  nv=numeric(g[col]) if var!='phenomenon_code' else None
  raw_audits.append({'network':'ASOS','station_id':'108','station_name':'서울','month':m,'variable':var,'source_file':'OBS_ASOS_TIM_20261016132020.xls','source_sha256':sha(BASE/'upload/OBS_ASOS_TIM_20261016132020.xls'),'source_rows':7272,'station_month_rows':len(g),'expected_hours':pd.Period(m,freq='M').days_in_month*24,'observed_valid_hours':int(g[col].ne('').sum()),'missing_row_hours':0,'blank_cells':int(g[col].eq('').sum()),'non_numeric_cells':int((nv.isna()&g[col].ne('')).sum()) if nv is not None else 0,'invalid_or_sentinel_cells':0,'coverage':g[col].ne('').mean(),'duplicate_keys':0,'field_present':True,'QC_flag_present':col.replace('(°C)','').replace('(mm)','').replace('(m/s)','').replace('(%)','')+' QC플래그' in g.columns,'latitude_field_present_in_upload':False,'longitude_field_present_in_upload':False,'station_current_latitude':metadata.get('108',{}).get('lat',''),'station_current_longitude':metadata.get('108',{}).get('lon',''),'coordinates_source':'current official station metadata; ASOS city context only','historical_location_verified':False,'readiness':'CONDITIONAL'})
for v in ['latitude','longitude','QC_flag','snow_depth_cm','phenomenon_code']:
 raw_audits.append({'network':'AWS','station_id':'ALL','variable':v,'field_present':False,'readiness':'NOT_USABLE','notes':'not in uploaded AWS file schema; coordinates separately sourced, absent observation fields not imputed'})
save('weather_station_audit.csv',pd.DataFrame(raw_audits))
save('weather_native_station_hour_panel.csv',aws.sort_values(['지점','date','hour']))
save('asos_supplemental_hour_panel.csv',asos[['date','hour','month','asos_snow_depth_cm_raw_observed','asos_snow_raw_status','asos_phenomenon_code_raw','asos_phenomenon_status']])

dump('external_QA_summary.json',{'main_months':MONTHS,'living_source_files':len(audits),'living_raw_rows':sum(a['rows'] for a in audits),'living_case_grid_rows':len(living),'living_observed_rows':int(living.value_status.eq('observed').sum()),'living_status_counts':living.value_status.value_counts().to_dict(),'living_raw_code_counts':{f'{s}:{m}':len(v) for (s,m),v in codes_by_source.items()},'living_duplicates':sum(a['duplicate_key_groups'] for a in audits),'living_conflicts':sum(a['conflicting_key_groups'] for a in audits),'living_suppression_all_numeric_cells':sum(a['suppressed_numeric_cells'] for a in audits),'living_nonnumeric_all_numeric_cells':sum(a['other_non_numeric_cells'] for a in audits),'living_schema_changed_files':[a['source_file'] for a in audits if a['schema_changed']],'living_baseline_n_counts':living[living.planned_weekday].baseline_valid_dates.value_counts(dropna=False).to_dict(),'weather_case_grid_rows':len(grid),'weather_station_candidate_assignments':crossw,'aws_coverage_eligible_station_ids':[s for s,v in eligible.items() if v],'aws_coverage_ineligible_station_ids':[s for s,v in eligible.items() if not v],'new_bus_results_computed':False,'bus_outcome_files_read':[],'living_sum_created':False})
print('External panels built; no bus outcome data read.',flush=True)
