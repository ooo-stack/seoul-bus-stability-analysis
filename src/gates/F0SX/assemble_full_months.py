"""Aggregate structural audit checkpoints and apply frozen input eligibility only."""
from audit_full_months import *
from baseline_quantile import quantile
HOLIDAY_NAMES={'20251003':'개천절','20251005':'추석 연휴','20251006':'추석','20251007':'추석 연휴','20251008':'추석 대체공휴일','20251009':'한글날','20251225':'기독탄신일','20260101':'1월 1일','20260216':'설 연휴','20260217':'설날','20260218':'설 연휴','20260301':'삼일절','20260302':'삼일절 대체공휴일','20260501':'노동절','20260505':'어린이날','20260524':'부처님오신날','20260525':'부처님오신날 대체공휴일','20260603':'전국동시지방선거','20260606':'현충일','20260717':'제헌절','20260815':'광복절','20260817':'광복절 대체공휴일'}
def jstr(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,default=lambda x:int(x) if isinstance(x,np.integer) else float(x))
def merge(a,b):
 a['rows']+=b['rows'];a['cnt']+=b['cnt']
 for i,h in enumerate(b['hist']):a['hist'][i].update(h)
 for c,h in b['lex'].items():a['lex'][c].update(h)
 for c,h in b['idlex'].items():a['idlex'].setdefault(c,collections.Counter()).update(h)
 for c in ['dates','normal_dates','anom','delta']:a[c].update(b[c])
def main():
 jobs=json.loads((WORK/'jobs.json').read_text());agg={};src={};daily=[];schema_files=[];errors=[]
 for job in jobs:
  r=pickle.load(open(WORK/f'scan_{job["source_id"]:03d}.pkl','rb'));kind=job['kind'];vcols=[c for c in job['columns'] if c.startswith(PREFIX[kind])]
  schema_files.append({'source_id':job['source_id'],'kind':kind,'column_count':len(job['columns']),'columns_json':jstr(job['columns']),'schema_equal_F0S':job['schema_ok'],'rows':r.get('rows',0),'min_actual_date':min(r['all_dates']) if r['all_dates'] else '', 'max_actual_date':max(r['all_dates']) if r['all_dates'] else '', 'distinct_dates':len(r['all_dates']),'dates_json':jstr(sorted(r['all_dates']))})
  for date,n in r['all_dates'].items():daily.append({'source_id':job['source_id'],'kind':kind,'date':date,'rows':n,'in_study':date[:6] in MONTHS})
  for e in r['errors']:errors.append({'source_id':job['source_id'],'error':e})
  for mo,b in r['months'].items():
   a=agg.setdefault((mo,kind),newstats(vcols));merge(a,b);src.setdefault((mo,kind),[]).append(job['source_id'])
 assert len(agg)==24,'Some months not covered by source rows'
 write(schema_files,'file_schema_and_dates.csv');write(daily,'daily_file_coverage.csv');dump(errors,OUT/'parse_errors.json')
 details=json.loads((WORK/'duplicate_details.json').read_text());schemas=[];ids=[];values=[];dups=[];date_rows=[];calendar_rows=[];week_rows=[];problems=[]
 datesets={};normalsets={}
 for (mo,kind),a in sorted(agg.items()):
  datesets[(mo,kind)]=set(a['dates']);normalsets[(mo,kind)]=set(a['normal_dates']);cols=EXPECTED[kind];vcols=[c for c in cols if c.startswith(PREFIX[kind])]
  schemas.append({'month':mo,'kind':kind,'raw_rows':a['rows'],'csv_count':len(src[(mo,kind)]),'column_count':len(cols),'columns_in_order_json':jstr(cols),'hours_present':'00-23','hour_column_count':24,'same_as_F0S':all(jobs[s]['schema_ok'] for s in src[(mo,kind)]),'added_columns_json':'[]','removed_columns_json':'[]','column_order_changed':False,'key_columns_json':jstr(KEYS[kind]),'date_format':'YYYYMMDD','storage_type':'CSV text preserved as strings','value_lexical_types_json':jstr({c:dict(x) for c,x in a['lex'].items()}),'source_ids_json':jstr(src[(mo,kind)])})
  ids.append({'month':mo,'kind':kind,'raw_rows':a['rows'],'key_columns_json':jstr(KEYS[kind]),'key_lexical_diagnostics_json':jstr(a['idlex']),'sequence_delta_distribution_json':jstr({str(k):int(v) for k,v in a['delta'].items()}),**{c:int(a['anom'][c]) for c in ['normal_id_sequence_rows','special_id_rows','special_all_values_blank','unknown_id_or_sequence_rows','zero_or_negative_sequence','noninteger_or_missing_sequence','reversed_sequence','nonadjacent_sequence','segment_2_to_3_rows']},'missing_ids_json':jstr({k:v for k,v in a['anom'].items() if k.endswith('_missing')})})
  entries=[(c,a['cnt'][i],a['hist'][i],a['rows']) for i,c in enumerate(vcols)]
  h=collections.Counter()
  for hh in a['hist'][1:]:h.update(hh)
  entries.append(('hourly_00_23_pooled',a['cnt'][1:].sum(axis=0),h,a['rows']*24))
  for scope,cnt,h,n in entries:
   values.append({'month':mo,'kind':kind,'scope':scope,'unit':'초' if kind=='time' else '회','raw_rows':a['rows'],'cells':n,**{k:int(v) for k,v in zip(['blank_cells','zero_cells','positive_cells','negative_cells','invalid_cells','positive_noninteger_cells'],cnt)},'blank_pct':100*cnt[0]/n,'zero_pct':100*cnt[1]/n,'positive_pct':100*cnt[2]/n,'positive_median':quantile(h,.5),'positive_p90':quantile(h,.9),'positive_p99':quantile(h,.99),'positive_max':max(h) if h else None,'population':'unfiltered_raw_calendar_month; exact duplicate rows included; identical ZIP/CSV reuploads excluded'})
  dd=[r for r in details if r['month']==mo and r['kind']==kind];cc=[r for r in dd if r['problem']!='exact_duplicate']
  dups.append({'month':mo,'kind':kind,'raw_rows':a['rows'],'complete_duplicate_extra_rows':sum(r['complete_duplicate_extra_rows'] for r in dd),'key_duplicate_extra_rows':sum(r['key_duplicate_extra_rows'] for r in dd),'duplicate_key_groups':len(dd),'duplicate_involved_rows':sum(r['rows'] for r in dd),'conflict_keys':len(cc),'format_only_conflict_keys':sum(r['problem']=='format_only_conflict' for r in cc),'conflict_raw_rows':sum(r['held_raw_rows'] for r in cc),'conflict_distinct_rows':sum(r['held_distinct_rows'] for r in cc),'conflict_dates_json':jstr(sorted({r['date'] for r in cc})),'exactly_compared_all_raw_fields':True,'cross_file_scan':True})
 # F0D planned weekday table is applied to source date availability, never to outcomes.
 for mo in MONTHS:
  y,m=int(mo[:4]),int(mo[4:]);days=[datetime.date(y,m,d) for d in range(1,calendar.monthrange(y,m)[1]+1)];cal={d.strftime('%Y%m%d') for d in days};P={d.strftime('%Y%m%d') for d in days if d.weekday()<5 and d.strftime('%Y%m%d') not in HOLIDAY_NAMES};N=len(P);L=max(16,math.ceil(N*16/19));lo=math.ceil(N*.9)
  time_dates=datesets[(mo,'time')];count_dates=datesets[(mo,'count')];T=P&normalsets[(mo,'time')];F=P&normalsets[(mo,'count')];D=T&F
  weekly=collections.defaultdict(list)
  for d in days:
   ds=d.strftime('%Y%m%d');wk=(d-datetime.timedelta(days=d.weekday())).isoformat();tp=ds in time_dates;fp=ds in count_dates;planned=ds in P
   calendar_rows.append({'month':mo,'date':ds,'weekday':d.weekday()+1,'holiday_name':HOLIDAY_NAMES.get(ds,''),'holiday_frozen_source':'F0D-1.0 eligible_day_rule.md' if ds in HOLIDAY_NAMES else '', 'planned_weekday':planned,'time_present':tp,'count_present':fp,'time_normal_rows':agg[(mo,'time')]['normal_dates'].get(ds,0),'count_normal_rows':agg[(mo,'count')]['normal_dates'].get(ds,0),'common_planned_day':ds in D,'week_start':wk})
   if planned:weekly[wk].append(ds)
   if not tp or not fp:problems.append({'month':mo,'date':ds,'kind':'both' if not tp and not fp else 'time' if not tp else 'count','problem':'raw_date_absent','planned_weekday':planned,'holiday_name':HOLIDAY_NAMES.get(ds,''),'hold_scope':'month_if_F0D_date_requirements_fail','reason':'원자료 날짜 부재. 0 대체 및 보간 없음'})
  failedweeks=[]
  for wk,p in weekly.items():
   nw=len(set(p)&D);need=min(3,len(p));ok=nw>=need
   week_rows.append({'month':mo,'week_start':wk,'planned_weekdays':len(p),'common_weekdays':nw,'minimum_required':need,'week_pass':ok,'missing_common_planned_dates_json':jstr(sorted(set(p)-D))})
   if not ok:failedweeks.append(wk)
  conf=[r for r in details if r['month']==mo and r['problem']!='exact_duplicate'];commonconf=[r for r in conf if r['date'] in D]
  for a in ids:
   if a['month']==mo and a['unknown_id_or_sequence_rows']:problems.append({'month':mo,'kind':a['kind'],'problem':'id_sequence_hold','rows':a['unknown_id_or_sequence_rows'],'hold_scope':'row_key','reason':'F0D 양수 정수 순서 또는 정상 ID 검증 미통과. 전체 키는 id_sequence_hold_keys.csv 참조'})
  for r in details:
   if r['month']==mo:problems.append({**r,'planned_weekday':r['date'] in P,'common_planned_day':r['date'] in D})
  structural_bad=any(not r['same_as_F0S'] for r in schemas if r['month']==mo) or any(r['negative_cells'] or r['invalid_cells'] or (r['kind']=='count' and (r['positive_noninteger_cells'] or r['zero_cells'])) for r in values if r['month']==mo)
  month_counts_pass=len(D)>=lo and len(D)>=L;dateok=month_counts_pass and not failedweeks
  # Master adequacy is independent; no dated official route type evidence in audited F0D inventory or new supplied inputs.
  masterheld=True;rawstatus='held_schema' if structural_bad else 'held_date' if not dateok else 'held_conflict' if conf else 'eligible_input'
  status='held_schema' if structural_bad else 'held_date' if not dateok else 'held_conflict' if conf else 'held_master' if masterheld else 'eligible_input'
  source_snapshot='20250901' if mo<='202601' else '20260108' if mo<='202606' else '20260701'
  grade='C' if structural_bad else 'B' if (len(time_dates)<len(cal) or len(count_dates)<len(cal) or any(r['unknown_id_or_sequence_rows'] for r in ids if r['month']==mo) or any(r['complete_duplicate_extra_rows'] or r['conflict_keys'] for r in dups if r['month']==mo)) else 'A'
  date_rows.append({'month':mo,'calendar_days':len(cal),'time_calendar_days':len(time_dates),'count_calendar_days':len(count_dates),'common_calendar_days':len(time_dates&count_dates),'N_planned':N,'time_planned_days':len(T),'count_planned_days':len(F),'common_days':len(D),'coverage_minimum':lo,'L_main':L,'L_strict':max(16,math.ceil(N*18/19)),'monthly_count_condition_pass':month_counts_pass,'weekly_condition_pass':not failedweeks,'failed_week_starts_json':jstr(failedweeks),'date_condition_pass':dateok,'missing_time_calendar_dates_json':jstr(sorted(cal-time_dates)),'missing_count_calendar_dates_json':jstr(sorted(cal-count_dates)),'missing_common_planned_dates_json':jstr(sorted(P-D)),'input_structure_pass':not structural_bad,'raw_input_status':rawstatus,'month_status':status,'held_date':not dateok,'held_schema':structural_bad,'held_conflict':bool(commonconf),'has_conflict_any_calendar_day':bool(conf),'conflict_keys_all_calendar':len(conf),'conflict_keys_common_planned':len(commonconf),'held_master':masterheld,'master_status':'held_master','master_reason':'시점이 확인된 공식 노선유형 근거 미확보. F0D D19 실행조건 미충족','snapshot_by_F0D_known_inventory':source_snapshot,'compatibility_grade':grade,'F1_result_execution_ready':False})
  problems.append({'month':mo,'problem':'held_master','hold_scope':'policy_Core_month','reason':'F0D D19: 해당 월초에 적용 가능한 공식 노선유형 이력 미확보; 구조 실패가 아님'})
  if not dateok:problems.append({'month':mo,'problem':'held_date','hold_scope':'month','reason':f'common={len(D)}, required90={lo}, L={L}, failed_weeks={failedweeks}'})
  for r in dups:
   if r['month']==mo:r['conflict_keys_common_planned']=sum(x['kind']==r['kind'] for x in commonconf)
 write(schemas,'monthly_schema_audit.csv');write(ids,'monthly_id_structure.csv');write(values,'monthly_value_structure.csv');write(dups,'monthly_duplicate_audit.csv');write(date_rows,'monthly_date_coverage.csv');write(calendar_rows,'day_calendar.csv');write(week_rows,'weekly_date_feasibility.csv');write(problems,'problem_months_and_keys.csv')
 dump({'freeze_version':'F0D-1.0','months':date_rows,'totals':{'input_structure_pass_months':sum(r['input_structure_pass'] for r in date_rows),'date_held_months':sum(r['held_date'] for r in date_rows),'conflict_held_months_common_planned':sum(r['held_conflict'] for r in date_rows),'conflict_months_all_calendar':sum(r['has_conflict_any_calendar_day'] for r in date_rows),'master_held_months':sum(r['held_master'] for r in date_rows)},'raw_rows':sum(a['rows'] for a in agg.values()),'source_rows_including_out_of_period':sum(r['rows'] for r in schema_files),'csv_files':len(jobs),'schema_error_records':errors,'data_definition_note':'Unit evidence is structural, not a new supplier definition confirmation; zero and blanks remain distinct.'},OUT/'audit_summary.json')
 print(pd.DataFrame(date_rows)[['month','common_days','N_planned','weekly_condition_pass','raw_input_status','held_master','compatibility_grade']].to_string(index=False),flush=True)
if __name__=='__main__':main()
