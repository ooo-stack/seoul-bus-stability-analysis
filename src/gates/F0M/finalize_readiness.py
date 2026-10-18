"""Finalize F0M statuses from certified input evidence, never research outcomes."""
from pathlib import Path
import json,hashlib,zipfile,shutil
import pandas as pd,numpy as np
R=Path(__file__).resolve().parent.parent;O=R/'f0m_results';SX=R/'f0m_sources/sx/f0sx_results'
# Submission adapter: paths only; the original calculation statements follow.
from seoul_bus_paths import bind as _submission_bind
globals().update(_submission_bind('F0M'))
def csv(n,**kw):return pd.read_csv(O/n,**kw)
def save(d,n):d.to_csv(O/n,index=False,encoding='utf-8-sig')
def table(d):
 rows=[list(d.columns),['---']*len(d.columns)]+d.astype(str).values.tolist();return '\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)
D=pd.read_csv(SX/'monthly_date_coverage.csv',dtype={'month':str});A=csv('monthly_master_assignment.csv',dtype=str);H=csv('route_type_history.csv',dtype={'month':str,'snapshot':str,'route_id':str});G=csv('snapshot_master_diagnostics.csv',dtype={'snapshot':str});V=csv('master_match_rates.csv',dtype={'month':str,'snapshot':str});Q=csv('coordinate_readiness.csv',dtype={'month':str,'snapshot':str,'node_id':str});F=pd.read_csv(SX/'monthly_duplicate_audit.csv',dtype={'month':str});AS=json.loads((O/'spatial_asset_verification.json').read_text())
# Separate node diagnostics from the monthly coordinate readiness output.
summary=Q[Q.node_id=='__MONTH_SUMMARY__'].copy();nodes=Q[Q.node_id!='__MONTH_SUMMARY__'].drop(columns=['month'],errors='ignore').copy();save(nodes,'coordinate_node_diagnostics.csv')
coordinate=[];rows=[]
for d in D.itertuples(index=False):
 m=d.month;s=A.loc[A.month==m,'snapshot'].iloc[0];g=G[G.snapshot==s].iloc[0];a=A[A.month==m];h=H[H.month==m];v=V[(V.month==m)&(V.denominator_scope=='common_planned_policy_ID_raw_rows')];n=nodes[nodes.snapshot==s]
 masterready=len(a)==3 and (a.snapshot_not_after_month_start=='True').all() and g.main_route_ids>0 and g.exact_label_bridge_one_to_one and g.basic_type_conflicts==0 and g.route_stop_conflict_keys==0
 coordsready=AS['boundary_count']==427 and AS['one_to_one_codes'] and g.inside_seoul_ready_nodes>0 and n.coordinate_source.notna().any()
 reasons=[]
 if not d.date_condition_pass:reasons.append('held_date')
 if not masterready:reasons.append('held_master')
 if not coordsready:reasons.append('held_coordinate')
 if not d.input_structure_pass or len(v)!=2 or v.raw_rows.eq(0).any():reasons.append('held_other')
 conflict=int(F[F.month==m].conflict_keys.sum());heldids=n.loc[n.held_coordinate_record.eq(True),'node_id'].tolist()
 coordinate.append({'month':m,'snapshot':s,'coordinate_master_nodes':len(n),'available_coordinate_nodes':int(n.longitude.notna().sum()),'missing_or_invalid_coordinate_nodes':int(n.longitude.isna().sum()),'spatial_hold_NODE_IDs_json':json.dumps(heldids),'spatial_hold_node_count':len(heldids),'inside_seoul_ready_nodes':int(g.inside_seoul_ready_nodes),'whole_month_coordinate_hold':not coordsready,'fixed_boundary_count':427,'CRS':'EPSG:5179','spatial_execution_ready':coordsready})
 rows.append({'month':m,'snapshot':s,'final_status':reasons[0] if reasons else 'eligible','all_hold_reasons_json':json.dumps(reasons),'held_date':'held_date' in reasons,'held_master':'held_master' in reasons,'held_coordinate':'held_coordinate' in reasons,'held_other':'held_other' in reasons,'N_planned':d.N_planned,'common_days':d.common_days,'coverage_minimum':d.coverage_minimum,'L_main':d.L_main,'monthly_count_condition_pass':d.monthly_count_condition_pass,'weekly_condition_pass':d.weekly_condition_pass,'date_condition_pass':d.date_condition_pass,'verified_main_route_ids':int(g.main_route_ids),'unknown_type_route_ids_excluded':int(g.unknown_type_route_ids),'coordinate_record_hold_count':len(heldids),'coordinate_record_hold_NODE_IDs_json':json.dumps(heldids),'raw_conflict_keys_held':conflict,'conflict_scope':'individual_date_key_only' if conflict else '', 'F1_execution_ready':not reasons,'august_role':'design_month' if m=='202608' else 'temporal_reproducibility_month'})
E=pd.DataFrame(rows);save(E,'final_month_eligibility.csv');save(pd.DataFrame(coordinate),'coordinate_readiness.csv')
# Reconciliation against previously certified calendar raw row counts.
raw=V[V.denominator_scope=='calendar_all_raw_rows'].merge(F[['month','kind','raw_rows']],on=['month','kind'],suffixes=('_current','_F0SX'),validate='one_to_one');assert len(raw)==24 and raw.raw_rows_current.eq(raw.raw_rows_F0SX).all()
assert set(E.loc[E.held_date,'month'])=={'202511','202512','202607'} and E[E.month=='202606'].final_status.iloc[0]=='eligible' and E[E.month=='202606'].raw_conflict_keys_held.iloc[0]==51
assert len(E)==12 and len(A)==36 and len(V)==72 and not E.held_master.any() and E.F1_execution_ready.sum()==9
assert AS['boundary_count']==427 and AS['code_count']==427 and not AS['geometry_modified']
checks={'monthly_rows':12,'master_assignments':36,'master_match_rows':72,'raw_rows_reconcile_with_F0SX':True,'eligible_months':9,'held_date_months':3,'held_master_months':0,'held_coordinate_whole_months':0,'june_conflicts_only_51_date_keys':True,'fixed_boundary_427_verified':True,'research_outcomes_calculated':False}
(O/'verification_results.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
brief=E[['month','snapshot','final_status','N_planned','common_days','verified_main_route_ids','unknown_type_route_ids_excluded','coordinate_record_hold_count','raw_conflict_keys_held']].copy();brief.columns=['분석월','고정 스냅샷','최종 상태','계획 평상 평일','공통 실제 평일','확인된 Main 노선 ID','유형 미확인 제외 ID','공간보류 NODE','보류 충돌 키']
vr=V[V.denominator_scope=='common_planned_policy_ID_raw_rows'];rt=vr[['month','kind','raw_rows','route_match_pct','departure_location_match_pct','arrival_location_match_pct','stop_location_match_pct','departure_route_stop_sequence_match_pct','arrival_route_stop_sequence_match_pct','stop_route_stop_sequence_match_pct','departure_coordinate_missing_pct','arrival_coordinate_missing_pct','stop_coordinate_missing_pct']].copy();rt=rt.round(3).fillna('해당 없음')
eligible=E.loc[E.final_status=='eligible','month'].tolist()
held=n=nodes[nodes.held_coordinate_record.eq(True)]
text=f'''# Gate 2-F0M 역사 마스터 및 최종 실행월 인증

검증일: 2026-10-08. 연구결과를 산출하지 않은 입력 인증이다.

## 1. 판정

12개월 모두 공식 역사 노선유형 자료와 같은 시점 정류소 및 경로 마스터를 이용할 수 있어 전체 월의 held_master를 해제한다. F0S-X 날짜조건을 충족한 **9개월만 F1에 진입 가능**하다. 2025-11, 2025-12, 2026-07은 held_date를 유지한다. 일부 노선 유형 미확인과 개별 좌표보류는 기록 단위로 처리하며, 완전 매칭이나 모든 좌표의 정확성을 인증한다는 뜻은 아니다.

{table(brief)}

F1 진입월: {', '.join(eligible)}. 2026-08은 기존 탐색 및 설계 월이며 나머지 월은 시간적 재현성 검증 월이다. 실제 Core의 양수 관측 및 반복조건 충족은 F1에서 적용할 조건이며 이 Gate에서 계산하지 않았다.

## 2. 역사적 노선유형과 ID 연결

사용자 제공 서울시버스 정보.zip의 노선기본정보는 노선번호와 명시적 유형을 포함하지만 노선 ID 열은 없다. 같은 스냅샷 공식 노선별 정류소정보의 ROUTE_ID와 노선명으로 ID 연결표를 만들었다. 모든 선택 스냅샷에서 ID에서 노선명, 노선명에서 ID가 각각 일대일이며 같은 노선번호의 기본정보 여러 행도 유형이 일치함을 확인했다. **기본정보 노선번호와 경로정보 노선명을 원문 문자열로 정확히 결합**했으며 숫자 패턴, 유사 이름, 미래 유형으로 분류하지 않았다. 같은 이름이라는 이유만으로 서로 다른 시점의 유형을 소급하지 않는다.

간선, 지선, 순환, 광역, 마을만 Main에 포함한다. 공항, 관광, 동행, 한강 등 비허용 유형과 유형 빈칸 또는 기본정보 미매칭 ID는 제외 사유를 남긴다. 경기와 인천 등 공식 서울 역사 마스터에 연결되지 않는 원자료 ID도 Main에서 제외한다. 유형자료 전체 부재와 일부 ID의 유형 미확인은 다르다. 후자는 F0D의 기존 규칙에 따라 개별 노선 제외와 미매칭률 공개로 처리했다. 월별 확인 및 제외 ID는 route_type_history.csv에 모두 기록했다. 노선기본정보 전체 유형값과 행 수는 official_route_type_values.csv에 저장했다.

2026-01-08 이후 일부 기본정보에 유형 빈칸이 있으므로 모든 ID의 유형이 확보됐다고 주장하지 않는다. 2026-06-02 및 2026-08-04 기본정보는 확보됐지만 월초 이후 자료이므로 Main에 쓰지 않는다.

## 3. 시점별 마스터와 결합률

사용자 지정 12개월 스냅샷 매핑을 그대로 적용했다. 분석월 1일 이하의 선택 스냅샷을 월 전체에 고정하며 미래 스냅샷으로 미매칭을 보충하지 않았다. monthly_master_assignment.csv에 자료 종류, 날짜, 파일명, 해시, 월초 대비 경과일과 선택 적격성을 기록했다. 마스터 내용 충돌은 허용하지 않았고 노선유형 정확 결합의 일대일 여부를 확인했다.

master_match_rates.csv는 세 분모를 구분한다.

1. calendar_all_raw_rows: 해당 달력월의 모든 원자료 행.
2. common_planned_all_raw_rows: 운행시간과 운행횟수가 함께 있는 계획 평상 평일의 모든 원자료 행.
3. common_planned_policy_ID_raw_rows: 두 번째 분모 중 역사 유형으로 허용된 Main 노선 ID의 원자료 행.

운행시간 양수 여부, 시간대 유효성, 반복관측, 2에서 3 구간 제외를 적용하지 않은 **원자료 ID 결합 감사 분모**다. 완전 중복 및 값충돌 행도 이 분모에는 남아 있다. F1의 유효 표본 수나 최종 정책 Core 보존율로 해석하지 않는다. 전체 106개 논리 CSV의 식별 열만 재조회했으며 시간 및 횟수 값 열을 분석하지 않았다. 달력월 원자료 행 수가 F0S-X의 24개 월 및 자료종류 집계와 정확히 일치함을 검증했다.

노선 ID, 정류소 위치정보의 NODE_ID 단독, 경로정보의 NODE_ID 단독, 노선과 NODE_ID와 순번 정확키를 각각 구분했다. 서울 이외 정류장이 포함될 수 있어 위치정보 미매칭을 오류나 서울 밖으로 단정하지 않는다. 좌표 결측률은 같은 스냅샷 위치 우선 및 유일한 경로 좌표 보완 후의 값이며, 좌표가 있지만 공간배정이 보류된 비율은 별도 열이다.

다음은 공통 평상 평일의 Main 노선 ID 원자료 분모에 대한 결합률이다. 단위는 %, 행 수는 건이다.

{table(rt)}

## 4. 좌표 준비상태와 사용자 지시 적용

F0D 문서에는 100m 이상 이동 버전의 확인 전 보류 규칙이 있으나 이번 F0M의 명시적 사용자 지시는 **선택 스냅샷 좌표를 유지하고 명백한 공간상 문제만 개별 held_coordinate로 기록**하도록 했다. 이 최신 지시를 적용하며 원래 F0D 파일은 수정하지 않았다. 100m 이동 진단값은 coordinate_changes_over_100m.csv에 보존한다. 이동 크기만으로 오류 확정, 최신 좌표 대체 또는 좌표 보정을 하지 않았다.

NODE_ID 108900095, 8번지입구는 2025-09-01, 2025-10-02, 2025-11-03 위치정보와 같은 날짜 경로정보 사이 약 54.7km 차이가 있다. 위치정보 좌표는 서울 경계 밖, 같은 시점 경로 좌표는 서울 내부로 배정돼 공간배정이 크게 충돌한다. 어느 좌표를 임의로 채택하지 않고 해당 버전의 NODE 공간배정을 보류한다. 이 버전이 사용되는 2025-09, 2025-10, 2025-11, 2025-12에만 해당하며 **9월과 10월 전체를 제외하지 않는다**. 이 NODE 연결 시간 구간의 Strict 공간배정과 공급 정류장 동 배정은 F1에서 보류하도록 전달한다. 2025-12-09 이후 선택 버전의 동시점 좌표는 다시 검사하며 과거로 소급하지 않는다.

NODE_ID 104000136, 건대입구역사거리의 두 공식 출처 사이 약 2.17km 차이도 진단에 남긴다. 양쪽 모두 유효한 서울 좌표이며 이 Gate에서 공식 이전 또는 오류 근거를 새로 확보하지 않았으므로 사용자 F0M 지시대로 동결 위치정보 좌표를 유지한다. 정확한 실제 위치까지 인증했다는 뜻은 아니다. 같은 시점에서 유일한 경로 좌표는 위치정보가 없을 때만 보완에 사용했다.

coordinate_readiness.csv는 12개월 실행준비 요약이며 coordinate_node_diagnostics.csv는 선택 스냅샷별 NODE 좌표, 출처, 출처 간 거리, 동 코드 및 개별 보류사유를 담는다. 좌표 보류는 월 전체 보류와 분리했다. 필요한 공간 프레임과 유효 좌표 입력은 확보돼 개별 보류 처리 후 공간집계를 실행할 수 있다.

## 5. 공통 427개 공간기준

기존 C1 검증 자산과 SHA256가 정확히 일치한다. 경계 427개 고유 10자리 코드와 2026-08 코드자료의 서울 427개 고유 8자리 코드에 00을 붙인 대응이 일대일이며 명칭의 기존 제 표기 차이도 일치한다. 기존 폴리곤을 수정하지 않았고 기존 C1의 SHP 읽기 및 point-in-polygon 함수만 재사용했다.

경계 ZIP SHA256: {AS['sha256']['project_sources/02-_-_-.zip']}

코드 ZIP SHA256: {AS['sha256']['project_sources/04-_-_-.zip']}

CRS는 기존 검증된 EPSG:5179를 승계했다. 원본 ZIP에 PRJ가 없으므로 파일 메타데이터가 CRS를 증명한다고 표현하지 않는다. 기존 투영의 기준점 변환을 확인했다. SGIS 2025 경계를 Main으로 대체하지 않았다. 시간 불안정성은 기존 Strict 양끝 서울 내부 및 도착 동 배정, 공급은 정책 시간 Core 양끝 중 서울 내부 정류장 동 배정의 정의를 그대로 전달한다. 이번 Gate에서는 지표를 계산하지 않았다.

## 6. 날짜 및 값충돌 승계

2025-11과 2025-12는 날짜 및 주별 조건 미충족이다. 2026-07은 월 총 자료일 수 기준은 통과하지만 첫 부분주의 반복가능 날짜조건을 충족하지 않아 held_date다. 없는 날의 0 대체, 복사, 보간을 하지 않는다. 날짜 적격성은 F0S-X의 동결 공휴일 및 실제 날짜 근거를 재사용했으며 새 달력이나 기준을 만들지 않았다.

2026-06-30 운행시간 51개 값충돌 키는 해당 날짜와 전체 반복키의 관측을 보류한다. 평균, 최대, 최소, 임의 행 선택을 하지 않는다. 월 전체 제외 사유가 아니므로 6월은 eligible다. 보류할 정확 키는 승계한 reference/duplicate_key_details.csv에 기록한다. 완전 동일 중복은 F0D대로 한 관측으로 처리하며 원자료 감사 분모와 구분한다.

## 7. 다음 Gate 및 필수 추가자료

F1은 인증된 9개월에서만 실행 가능하다. 유형 미확인 ID 제외, 개별 좌표보류, 정확 경로키 미매칭 및 June 51키 관측 보류를 먼저 적용한다. 실제 최소 양수 관측일 및 주별 반복조건을 충족하지 못한 구간은 F1에서 기존 규칙대로 다룬다. 입력 인증은 Core 유효 표본이 모든 동에서 확보된다는 보장이 아니다.

현재 인증된 9개월의 F1 진입을 위해 추가로 꼭 필요한 파일은 없다. 날짜 보류 3개월을 해제하려면 실제 누락된 날짜의 공식 원자료와 주별 조건이 충족되는지 재인증이 필요하지만, 12개월로 수를 맞추기 위해 이를 추정하거나 규칙을 바꾸지 않는다.

P90-P50, C2, 상관계수, 후보지역 및 월 반복률은 계산하지 않았다. 추가 원자료 수집, 정책해석, 회귀나 학습모형은 수행하지 않았다.
'''
assert '\u00b7' not in text
(O/'Gate2F0M_master_readiness_report.md').write_text(text,encoding='utf-8')
ref=O/'reference';ref.mkdir(exist_ok=True)
for p in ['monthly_date_coverage.csv','monthly_duplicate_audit.csv','duplicate_key_details.csv','day_calendar.csv','weekly_date_feasibility.csv']:
 shutil.copyfile(SX/p,ref/p)
for p in ['master_snapshot_rule.md','Gate2F0D_design_freeze.md','duplicate_handling_rule.md','eligible_day_rule.md','month_definition.md','multi_month_analysis_spec.md']:
 shutil.copyfile(SX/'reference'/p,ref/p)
manifest={str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest() for p in O.rglob('*') if p.is_file() and '__pycache__' not in p.parts};(O/'deliverable_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
with zipfile.ZipFile(R/'Gate2F0M_results.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in O.rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:z.write(p,'f0m_results/'+str(p.relative_to(O)))
print(E[['month','final_status','F1_execution_ready']].to_string(index=False));print('VERIFIED AND PACKAGED',flush=True)
