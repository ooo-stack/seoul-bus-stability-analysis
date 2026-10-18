"""Assemble monthly-only outcomes and audit, without monthly recurrence."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,zipfile,shutil,html
from run_month import ALL,O,R
SX=R/'f1a_sources/unpacked/Gate2F0SX_results/f0sx_results';M=R/'f1a_sources/unpacked/Gate2F0M_results/f0m_results'
def save(d,n):d.to_csv(O/n,index=False,encoding='utf-8-sig',float_format='%.15g')
def md(d,decimals=3):
 def cell(v):
  if pd.isna(v):return 'NA'
  if isinstance(v,(float,np.floating)):return str(int(v)) if float(v).is_integer() else f'{v:.{decimals}f}'
  return str(v).replace('|','/').replace('\n',' ')
 rows=[list(d.columns),['---']*len(d.columns)]+list(d.itertuples(index=False,name=None));return '\n'.join('| '+' | '.join(cell(x) for x in r)+' |' for r in rows)
def dist(v,prefix):
 s=v.dropna();return {prefix+'_P25':s.quantile(.25),prefix+'_median':s.median(),prefix+'_P75':s.quantile(.75),prefix+'_P90':s.quantile(.9),prefix+'_min':s.min(),prefix+'_max':s.max()}
metrics=[];summ=[];samples=[];qas=[];tails=[];quintiles=[];equal=[];compositions=[];checks=[]
DUP=pd.read_csv(SX/'monthly_duplicate_audit.csv',dtype={'month':str});LED=pd.read_csv(O/'duplicate_application_ledger.csv',dtype={'month':str,'date':str});POP=pd.read_csv(O/'monthly_route_population.csv',dtype={'month':str});rawrecon=[]
for m in ALL['months']:
 p=O/'core_checkpoints'/m;d=pd.read_csv(p/'dong_metrics.csv',dtype={'month':str,'dong_code':str,'dong_code10':str,'snapshot':str,'candidate':'boolean'},float_precision='round_trip');assert len(d)==427 and d.dong_code.is_unique
 cfg=ALL['config'][m];a=np.load(p/'segment_hour_core.npz');k=pd.read_csv(p/'segment_keys.csv.gz',dtype=str,keep_default_na=False);roster=pd.read_csv(p/'supply_roster_positions.csv.gz',dtype=str);ma=ALL['masters'][cfg['snapshot']]
 assert (a['positive_days']>=cfg['L']).all() and (a['P90']>=a['P50']).all()
 for i,w in enumerate(a['week_names']):assert (a['weekly_positive_days'][:,i]>=cfg['week_min'][str(w)]).all()
 assert k['노선_ID'].isin(ma['allowed']).all() and not (k['출발_정류장_순서'].eq('2')&k['도착_정류장_순서'].eq('3')).any()
 strict=a['strict'];selected=k.iloc[a['segment_index']];assert selected.loc[strict,'dep_dong_code'].ne('').all() and selected.loc[strict,'arr_dong_code'].ne('').all();assert not selected.loc[strict,'spatial_coordinate_hold'].eq('True').any()
 assert roster.node_id.isin(ma['inside']).all()
 for field,label in [('C2_count','C2'),('U_sec','U')]:assert np.allclose(d[label+'_percentile'],d[field].round(8).rank(method='average',pct=True)*100,equal_nan=True)
 both=d.U_sec.notna()&d.C2_count.notna();assert d.loc[~both,'candidate'].isna().all();assert d.loc[both,'candidate'].equals(((d.loc[both,'C2_percentile']>=75)&(d.loc[both,'U_percentile']>=75)).astype('boolean'))
 q=d.loc[both];pearson=q.C2_count.corr(q.U_sec);spearman=q.C2_count.round(8).rank(method='average').corr(q.U_sec.round(8).rank(method='average'))
 s={'month':m,'role':d.month_role.iloc[0],'N_planned':cfg['N'],'common_days':len(cfg['days']),'L_main':cfg['L'],'valid_U_dongs':int(d.U_sec.notna().sum()),'valid_C2_dongs':int(d.C2_count.notna().sum()),'valid_both_dongs':int(both.sum()),'Pearson_C2_U':pearson,'Spearman_C2_U':spearman,'candidate_count':int(d.candidate.sum()),'candidate_NA_dongs':int(d.candidate.isna().sum()),**dist(d.U_sec,'U_sec'),**dist(d.C2_count,'C2_count')};summ.append(s);metrics.append(d)
 sample=json.loads((p/'sample_counts.json').read_text());sample['policy_Core_route_IDs']=selected['노선_ID'].nunique();sample['Strict_Core_route_IDs']=selected.loc[strict,'노선_ID'].nunique();sample.update({c:s[c] for c in ['valid_U_dongs','valid_C2_dongs','valid_both_dongs','candidate_count','candidate_NA_dongs']})
 for pop in POP[POP.month==m].itertuples():
  prefix=pop.data_kind+'_';sample.update({prefix+c:getattr(pop,c) for c in ['raw_all_distinct_route_ID_values','normal_9digit_route_IDs','observed_Main_route_IDs','unknown_type_normal_route_IDs','historical_type_blank_IDs','route_master_unmatched_IDs','unknown_type_raw_rows','unknown_type_raw_row_pct']});sample['both_data_raw_route_ID_union_count']=pop.both_data_raw_route_ID_union_count
  baseline=DUP[(DUP.month==m)&(DUP.kind==pop.data_kind)].raw_rows.iloc[0];assert baseline==pop.calendar_raw_rows;rawrecon.append({'month':m,'kind':pop.data_kind,'F0SX_calendar_rows':int(baseline),'F1A_calendar_rows':int(pop.calendar_raw_rows),'equal':True})
 samples.append(sample)
 for scope,flag in [('policy_Core',np.ones(len(selected),bool)),('Strict_Core',strict)]:
  rt=selected.loc[flag,'노선_ID'].map(ma['types']);counts=rt.value_counts()
  for t,n in counts.items():compositions.append({'month':m,'scope':scope,'route_type':t,'Core_combinations':int(n),'Core_share_pct':100*n/len(rt)})
 qa=pd.read_csv(p/'qa_chunks.csv');qa['month']=m;group=qa.groupby(['data_kind','scope','stage'],dropna=False).agg(rows=('rows','sum'),denominator_rows=('denominator_rows','sum'),cells=('cells','sum')).reset_index();group['month']=m;group['rate_pct']=100*group.rows/group.denominator_rows.replace(0,np.nan);group['note']=''
 zero=group.stage.eq('time_zero_cells_after_master');group.loc[zero,'rows']=np.nan;group.loc[zero,'rate_pct']=100*group.loc[zero,'cells']/(24*group.loc[zero,'denominator_rows']);group.loc[zero,'note']='value cells denominator = 24 * matched policy rows'
 for kind in ['time','count']:
  led=LED[(LED.month==m)&(LED.kind==kind)];commonled=led[led.date.isin(cfg['days'])];actual=float(group[(group.data_kind==kind)&(group.stage=='exact_duplicate_removed')].rows.sum());actualconf=float(group[(group.data_kind==kind)&(group.stage=='conflict_rows_after_dedup_held')].rows.sum());assert actual==commonled.exact_duplicate_extra_rows.sum();assert actualconf==commonled.conflict_rows_after_dedup.sum()
  cal=DUP[(DUP.month==m)&(DUP.kind==kind)].iloc[0]
  for stage,n in [('calendar_exact_duplicate_extra_rows',int(cal.complete_duplicate_extra_rows)),('calendar_conflict_keys_held',int(cal.conflict_keys)),('common_conflict_keys_held',int(commonled.conflict_key.sum()))]:
   group=pd.concat([group,pd.DataFrame([{'month':m,'data_kind':kind,'scope':'calendar_all' if stage.startswith('calendar') else 'common_planned','stage':stage,'rows':n,'denominator_rows':np.nan,'cells':np.nan,'rate_pct':np.nan,'note':'keys and rows distinguished; frozen full-field audit reapplied by exact source hash and CSV row number'}])],ignore_index=True)
 qas.append(group);ta=pd.read_csv(p/'tail.csv');ta['month']=m;tails.append(ta)
 bins,edges=pd.qcut(q.C2_count.round(8),5,duplicates='drop',retbins=True)
 for j,b in enumerate(bins.cat.categories):
  x=q[bins==b];quintiles.append({'month':m,'quintile':j+1,'actual_quintile_count':len(bins.cat.categories),'C2_lower_edge':edges[j],'C2_upper_edge':edges[j+1],'dong_count':len(x),'U_P25_sec':x.U_sec.quantile(.25),'U_median_sec':x.U_sec.median(),'U_P75_sec':x.U_sec.quantile(.75)})
 ties=q[q.C2_count.round(8).duplicated(keep=False)].copy();ties['C2_tie_value']=ties.C2_count.round(8);ties['tie_group_size']=ties.groupby('C2_tie_value').dong_code.transform('size');equal.append(ties[['month','dong_code','dong_name','C2_count','U_sec','C2_tie_value','tie_group_size']]);checks.append({'month':m,'Core_quantiles_verified_against_numpy':True,'weekly_and_minimum_days_verified':True,'coordinate_hold_preserved':True,'duplicate_and_conflict_application_verified':True,'427_code_frame_verified':True,'candidate_NA_preserved':True})
D=pd.concat(metrics,ignore_index=True);S=pd.DataFrame(summ);SC=pd.DataFrame(samples);QA=pd.concat(qas,ignore_index=True);T=pd.concat(tails,ignore_index=True)
assert len(D)==9*427 and len(S)==9 and D.candidate.isna().sum()==5
save(D,'monthly_dong_metrics.csv');save(S,'monthly_relationship_summary.csv');save(D[['month','month_role','dong_code','dong_code10','dong_name','C2_count','U_sec','C2_percentile','U_percentile','C2_percentile_denominator','U_percentile_denominator','candidate','U_missing_reason','C2_missing_reason']],'monthly_candidate_flags.csv');save(SC,'monthly_core_sample_counts.csv');save(QA,'monthly_QA_exclusions.csv');save(pd.DataFrame(quintiles),'monthly_supply_quintile_U.csv');save(pd.concat(equal,ignore_index=True),'monthly_equal_C2_groups.csv');save(pd.DataFrame(compositions),'monthly_core_route_type_composition.csv');save(pd.DataFrame(rawrecon),'raw_row_reconciliation.csv');save(pd.DataFrame(checks),'monthly_verification.csv')
held=ALL['eligibility'][ALL['eligibility'].final_status!='eligible'];save(held,'held_months_reference.csv')
for m in held.month: T=pd.concat([T,pd.DataFrame([{'month':m,'status':'held_date_not_analyzed','scope':'not_calculated'}])],ignore_index=True)
save(T,'monthly_tail_diagnostics.csv')
# Calendar-vs-legacy QA is descriptive, never selects which result is Main.
old=pd.read_csv(R/'f1a_sources/unpacked/Gate2C2_results/dong_supply_reliability_relationship.csv',dtype={'dong_code':str},float_precision='round_trip');new=D[D.month=='202608'];join=new.merge(old[['dong_code','C2_all','instability_all_sec','C2_high_supply_top25_high_instability_top25_flag']],on='dong_code',validate='one_to_one');na=set(new.loc[new.candidate.fillna(False),'dong_code']);oa=set(old.loc[old.C2_high_supply_top25_high_instability_top25_flag,'dong_code']);au=join.U_sec.round(8).rank().corr(join.instability_all_sec.round(8).rank());ac=join.C2_count.round(8).rank().corr(join.C2_all.round(8).rank());comparisons=[{'comparison_metric':key,'value':v,'unit':unit,'common_valid_dongs':427,'note':note} for key,v,unit,note in [('U_Spearman',au,'correlation','8-digit tied ranks'),('C2_Spearman',ac,'correlation','8-digit tied ranks'),('candidate_intersection',len(na&oa),'dongs','frozen 75-percentile rule'),('candidate_union',len(na|oa),'dongs','descriptive QA only'),('calendar_candidate_count',len(na),'dongs','calendar Main'),('legacy_candidate_count',len(oa),'dongs','legacy 2026-08-03 through 30'),('calendar_N_planned',20,'days','includes August 14 and 31; excludes August 17'),('legacy_analysis_days',19,'days','existing C1 code excludes August 14; includes August 17')]];save(pd.DataFrame(comparisons),'august_calendar_vs_legacy.csv')
join['U_delta_calendar_minus_legacy_sec']=join.U_sec-join.instability_all_sec;join['C2_delta_calendar_minus_legacy']=join.C2_count-join.C2_all;save(join,'august_dong_reconciliation.csv')
verification={'months_computed':ALL['months'],'all_9_months_success':True,'rows_9x427':len(D),'held_months_not_calculated':held.month.tolist(),'January_missing_dongs':D[(D.month=='202601')&D.U_sec.isna()].dong_name.tolist(),'candidate_missing_not_zero':True,'source_row_number_uses_CSV_index_plus_2':True,'all_calendar_row_totals_reconcile_with_F0SX':True,'June_conflict_keys_held':int(LED[(LED.month=='202606')&LED.conflict_key].shape[0]),'C2_no_new_observation_threshold':True,'monthly_recurrence_not_computed':True,'August_recomputed_calendar_month':True,'final_policy_candidates_not_selected':True};assert verification['June_conflict_keys_held']==51;(O/'verification_results.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2))
# Exact vector plots, Korean SVG text remains editable and uses viewer CJK fonts.
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="1230" viewBox="0 0 1440 1230">','<rect width="1440" height="1230" fill="white"/>','<g font-family="Malgun Gothic, Noto Sans CJK KR, Apple SD Gothic Neo, sans-serif" fill="#243340">','<text x="50" y="42" font-size="24">월별 관측 서비스량과 운행시간 불안정성</text>']
for i,m in enumerate(ALL['months']):
 q=D[(D.month==m)&D.C2_count.notna()&D.U_sec.notna()];s=S[S.month==m].iloc[0];x0=65+(i%3)*475;y0=105+(i//3)*355;w=370;h=250;xm=float(q.C2_count.max())*1.05;ym=float(q.U_sec.max())*1.05
 svg.append(f'<text x="{x0}" y="{y0-32}" font-size="19">{m[:4]}-{m[4:]} (유효 {len(q)}개 동)</text>');svg.append(f'<text x="{x0}" y="{y0-12}" font-size="13">Pearson {s.Pearson_C2_U:.3f}, Spearman {s.Spearman_C2_U:.3f}</text>');svg.append(f'<path d="M{x0},{y0} V{y0+h} H{x0+w}" fill="none" stroke="#71808e"/>')
 for v in np.linspace(0,xm,4):xx=x0+w*v/xm;svg.append(f'<text x="{xx}" y="{y0+h+20}" text-anchor="middle" font-size="12">{v:.0f}</text>')
 for v in np.linspace(0,ym,4):yy=y0+h-h*v/ym;svg.append(f'<text x="{x0-8}" y="{yy+4}" text-anchor="end" font-size="12">{v:.0f}</text>')
 for row in q.itertuples():
  color='#db7449' if bool(row.candidate) else '#688ea6';svg.append(f'<circle cx="{x0+w*row.C2_count/xm:.2f}" cy="{y0+h-h*row.U_sec/ym:.2f}" r="2.7" fill="{color}" opacity="0.68"/>')
 svg.append(f'<text x="{x0+w/2}" y="{y0+h+42}" text-anchor="middle" font-size="13">C2 (회, 전일 대표값의 관측 부분합)</text>');svg.append(f'<text transform="translate({x0-43},{y0+h/2}) rotate(-90)" text-anchor="middle" font-size="13">날짜별 구간 평균 운행시간 불안정성 (초)</text>')
svg+=['<text x="50" y="1170" font-size="16">주황색은 월별 탐색 후보입니다. 상위 25%는 탐색적 진단기준이며 각 패널의 축 범위는 다릅니다.</text>','<text x="50" y="1202" font-size="16">두 지표의 관계는 월별로 확인하며, 1월은 관측 및 표본구성 제약을 함께 해석해야 합니다.</text>','</g></svg>'];(O/'monthly_C2_U_scatter.svg').write_text('\n'.join(svg),encoding='utf-8')
# Report: results, concrete limitations, QA, provenance, and next-Gate readiness.
brief=S[['month','N_planned','common_days','L_main','valid_U_dongs','valid_C2_dongs','valid_both_dongs','Pearson_C2_U','Spearman_C2_U','candidate_count']].copy();brief.columns=['월','계획일 N','공통일','L','유효 U 동','유효 C2 동','공통 유효 동','Pearson','Spearman','탐색 후보 수']
corebrief=SC[['month','policy_time_Core_combinations','strict_Core_combinations','policy_Core_route_IDs','coordinate_held_policy_Core_segments','coordinate_held_supply_endpoint_stops','fixed_2_to_3_segments_excluded','supply_representative_hour_cells_observed_fewer_than_L']].copy();corebrief.columns=['월','정책 시간 Core 조합','Strict 조합','정책 Core 노선 ID','좌표보류 Core 구간','좌표보류 공급 정류장','2에서 3 제외 구간','관측일이 L 미만인 공급 대표 셀']
coretails=T[(T.status=='calculated')&(T.scope=='policy_time_Core')][['month','P50_sec','P90_sec','P99_sec','P99_9_sec','max_sec']].copy();coretails.columns=['월','P50 초','P90 초','P99 초','P99.9 초','최대 초']
coverage=D.groupby('month').strict_Core_combinations.agg(['min','median','max']).reset_index();coverage.columns=['월','동별 Strict 조합 최소','동별 Strict 조합 중앙값','동별 Strict 조합 최대']
missing=D[(D.month=='202601')&D.U_sec.isna()].dong_name.tolist();jan=SC[SC.month=='202601'].iloc[0];jcomp=pd.DataFrame(compositions);jshare=jcomp[(jcomp.month=='202601')&(jcomp.scope=='policy_Core')&(jcomp.route_type=='마을')].Core_share_pct.iloc[0]
text=f'''# Gate 2-F1A 월별 Core 및 핵심지표 보고서

검증일: 2026-10-08. F0D 동결 규칙과 F0S-X, F0M 인증에 따른 9개 적격월의 독립 계산 결과다.

## 1. 판정과 월별 결과

**9개 월 모두 계산에 성공했다.** 8개 월은 U와 C2가 모두 427개 동에서 유효하고, 2026-01은 두 지표 모두 422개 동에서 유효하다. 보류 2025-11, 2025-12, 2026-07은 계산하지 않았으며 후보 0으로 넣지 않았다. 427개 고정 코드 프레임은 모든 계산월에 유지했다. 관측이 있다는 사실만으로 충분한 대표성을 인증하지 않는다.

{md(brief)}

C2-U 상관은 1월을 제외한 8개 월에서 약한 양의 방향, 1월에서는 약한 음의 방향이다. 인과관계나 관계의 부재로 확대하지 않는다. 월별 후보는 해당 월 C2 및 U 각각의 평균 동률 백분위가 75 이상인 교집합이다. 공식 정책기준이나 최종 정책지역이 아니다.

2026-08은 탐색 및 설계 월이다. 2026-08-01부터 31까지 동결 달력으로 새로 계산했으며 기존 8월 결과를 재사용하지 않았다. 월 반복률이나 지속후보는 계산하지 않았다.

## 2. 고정 산식과 모집단

평상 평일과 공통 관측일 D는 동결 day_calendar.csv를 그대로 사용했다. N은 계획된 평상 평일 수, L=max(16,ceil(16N/19))이다. 각 달력주의 계획 평상 평일 수 p에 대해 min(3,p)일 이상의 양수 관측을 동시에 요구했다. 부분주와 자료 부재로 요구일 수를 낮추지 않았다.

노선, 출발 NODE_ID, 도착 NODE_ID, 출발 순서, 도착 순서, 시간대의 반복키를 월 내부에서 독립 구성했다. 양수 시간값만 사용하고 linear P50 및 P90에서 U=P90-P50을 계산했다. 0은 비유효이며 없는 날짜를 채우지 않았다. 인접 순서 차이 1만 사용하고 2에서 3 구간은 모든 월에서 제외했다. 새 양수 극단값 제거조건을 만들지 않았다.

역사 유형은 간선, 지선, 순환, 광역, 마을만 허용했다. 공항, 관광, 동행, 한강, 경기, 인천, 유형 미확인 및 기타 비허용형은 Main에 넣지 않았다. 노선 ID 미매칭은 유형을 추정하지 않고 별도 기록한다. 유형 빈칸과 서울 마스터 밖 ID 미매칭을 구분했고 특수 노선 ID 0은 정상 노선의 유형 미확인 수에 섞지 않았다. 전체 원자료 ID 값과 일반 9자리 ID 수도 구분했다.

정류장 양끝 정확한 노선, NODE_ID 및 순번 키를 선택 스냅샷에 결합했다. U는 양끝 모두 서울 내부이고 공간보류가 아닌 Strict 구간의 도착 동에 배정하며 구간 및 시간대 U의 중앙값이다. 날짜와 전체 시간을 먼저 합쳐 동별 P90-P50을 계산하지 않았다.

C2 공급 대상은 정책 시간 Core에 등장하는 구간의 양끝 중 서울 내부가 확인된 노선, 정류장 및 순번이다. 반대쪽 끝점의 서울 여부와 관계없이 해당 정류장은 공급 대상이 될 수 있다. 반복 순서는 같은 날짜와 시간대에서 관측 부분합으로 통합한 뒤, 노선 및 정류장 및 시간대의 날짜 중앙값을 구했다. 이 대표값을 정류장별로 합산하고 동 내부 정류장 중앙값을 취했다. **공급 셀에 새 L 또는 16일 반복필터를 적용하지 않았다.** 모든 값이 결측이면 NA이며 빈칸이나 키부재를 0회로 대체하지 않았다.

U 단위는 초다. C2 단위는 회이며 전일 24개 시간대 대표값의 관측 부분합에 대한 정류장 중앙값이다. 완전한 24시간 일일 총운행량, 고유 차량 수, 특정 실제 하루의 총계 또는 공급 적정성으로 해석하지 않는다.

## 3. 커버리지와 표본규모

{md(corebrief,0)}

{md(coverage,0)}

관측일이 L 미만인 공급 대표 셀도 원래 C2 산식대로 유지돼 새 공급 반복필터가 없음을 확인했다. 공급 관측일 최소 및 중앙값, 대상 및 관측 정류장 수, 대표 셀 존재율, 행부재와 빈칸 및 반복 순서 부분합은 monthly_dong_metrics.csv와 monthly_core_sample_counts.csv에 기록했다. 분포 P25, 중앙값, P75, P90, 최소, 최대는 monthly_relationship_summary.csv에 모두 저장했다.

### 1월 관측 제약

2026-01의 정책 시간 Core는 {int(jan.policy_time_Core_combinations):,}조합으로 다른 월보다 크게 작다. 마을 유형의 Core 비중은 {jshare:.2f}%다. 1월 13일과 14일의 간선 및 지선 양수 시간 관측이 급감했다. 같은 고정 필터를 적용한 원자료 시간 셀에서 간선 양수 비율은 각각 약 15.12%, 18.72%, 지선은 27.15%, 31.96%였다. 주변 일반 날짜에서는 간선 약 71%, 지선 약 79%였다. 이 날짜들은 원자료 전체 부재일이 아니고 새 휴일로 제외하지 않았다. 관측 감소의 실제 운영 원인은 이 자료만으로 확정하지 않는다.

N=21, D=19, L=18을 그대로 적용해 두 날짜에서 양수시간이 없는 많은 조합이 최소 관측조건을 통과하지 못했다. 임의로 L을 낮추거나 이 날짜를 복사 및 보간하지 않았다. 따라서 1월의 U, C2와 상관에는 바뀐 표본구성이 포함된다. 1월의 음의 상관을 단순한 지역 구조 반전으로 확정할 수 없다.

결측 동은 {', '.join(missing)}이다. 이 5개 동의 지표 및 후보는 NA이며 후보 False 또는 0으로 처리하지 않았다. 각 지표의 백분위 분모도 422개로 기록했다. 표본이 작다는 이유로 1월 전체를 새로 보류하거나 좋은 결과의 월만 선택하지 않았다.

## 4. 월별 제외 및 보류 QA

monthly_QA_exclusions.csv에서 전 달력월 감사 건수와 실제 공통 평일 적용 건수, 건의 종류 및 분모를 구분한다. 완전 중복 추가행과 충돌 키 수 및 완전 중복을 접은 뒤 보류한 충돌 행 수를 구분했다. 동일 키 값충돌은 전체 24시간 행을 보류했고 임의 평균 또는 값 선택을 하지 않았다.

2026-06-30의 51개 충돌 키를 해당 날짜 및 키에서만 보류했다. 6월 전체와 해당 날짜 전체는 제외하지 않았다. 특수 ID, 일반 ID 형식 미확인, 비정수 순서, 비양수 순서, 비인접 구간, 유형 미확인, 비허용 유형, 정확 마스터키 미매칭을 별도 기록했다. 유형 미확인 원자료 행 수 및 비율과 ID 수는 monthly_route_population.csv 및 monthly_core_sample_counts.csv에 자료 종류별로 있다. 역사 유형 빈칸과 마스터 미매칭 ID를 합쳐 서울 유형자료 전체 부재라고 해석하지 않는다.

F0M의 NODE_ID 108900095 과거 좌표 버전은 2025-09와 2025-10 공간배정에서 보류했다. 2025-11과 12는 원래 held_date다. 좌표 보류 NODE, 관련 Core 구간 및 공급 정류장 수를 기록했으며 최신 좌표로 대체하지 않았다. 다른 100m 이동은 F0M 규칙대로 동결 좌표를 유지했다. 고정 경계 및 코드 해시와 427개 대응은 F0M 검증 자산과 일치했다.

F0M CSV의 동 코드에 저장된 정수형 소수 표기 .0는 정확한 10자리 정수라는 조건과 검증된 427개 코드 대응 안에서만 무손실 제거했다. 행정동 공간배정이나 경계는 새로 만들지 않았다.

초기 8월 중복 적용 검사는 CSV 헤더 포함 행번호와 내부 0 기반 인덱스의 차이로 중단됐다. 인덱스+2로 수정 후 8월을 전부 다시 계산했다. 모든 월의 중복 및 충돌 실제 적용 건수는 동결 목록의 공통 평일 기대건수와 정확히 대조했고, 남은 동일 날짜 및 키 중복이 없음을 확인했다. 원자료를 수정하거나 충돌을 해결한 것이 아니다.

## 5. 원자료 꼬리 진단

다음은 정책 유형, 구조조건, 2에서 3 제외 및 정확 마스터 결합과 반복조건을 통과한 시간 Core의 양수 원자료 값이다. 불안정성 U의 분포가 아니다. 단위는 초다.

{md(coretails,1)}

8월의 최대값 축소는 고정된 Main 필터 후에도 남아 있다. 중앙값과 P90을 함께 제시해 상단 꼬리 변화와 중심 값 구조를 구분한다. 분포 변화만으로 초에서 분으로의 단위 변경이나 자료 정의 변경을 확정하지 않는다. 새로운 절단, 이상값 제거 또는 기간 변경을 적용하지 않았다. 월별 꼬리 진단에는 반복조건 전의 정책 및 마스터 유효 양수값도 별도 scope로 보존했다.

2026-07은 held_date이므로 이번 Gate에서 정책 Core 또는 필터 후 꼬리를 계산하지 않았다. 따라서 7월과 8월의 필터 후 단절 여부를 모두 인증했다고 쓰지 않는다. F0S-X의 7월 원자료 구조진단은 기존 참조 결과로만 승계했다.

## 6. 8월 달력월과 기존 결과 비교

{md(pd.DataFrame(comparisons)[['comparison_metric','value','unit']])}

동별 비교는 같은 427개 코드에서 수행했다. 새 후보 {len(na)}개와 기존 40개 중 교집합은 {len(na&oa)}개, 합집합은 {len(na|oa)}개다. 이 비교로 어느 기간을 Main으로 선택하지 않았고 달력월 Main을 유지했다.

기존 C1 코드의 분석일 집합은 8월 3일부터 30일까지 월요일부터 금요일 중 8월 14일을 뺀 19일이었다. 동결 달력월은 공식 평상 평일 기준으로 8월 14일과 31일을 포함하고 17일을 제외한 20일이다. 기존 집합에서 14일을 뺐다는 사실을 14일이 공식 휴일이었다는 주장으로 확대하지 않는다. 새 L=17, 마지막 부분주 31일의 조건, 역사 마스터 및 유형 조건도 함께 적용됐다. 따라서 이 QA 차이를 31일 하루 추가의 순수 효과로 분해해서 해석하지 않는다. 기존 결과는 보존하고 새 값으로 덮어쓰지 않았다.

## 7. 다음 Gate

**F1B 반복성 분석으로 진행 가능하다.** 1월의 5개 동 NA와 표본구성 제약, 보류 3개월, 8월의 설계 월 역할을 그대로 승계해야 한다. 같은 동의 평가 가능한 월을 분모로 구분하고 8월 포함과 제외의 역할은 F0D에 따른다. 이 Gate는 월 반복률, 몇 개월 이상 지속후보, 새 임계값, 외부수요 및 전용차로 결합이나 정책 우선순위를 만들지 않았다.

## 8. 파일 및 재현 근거

요청된 7개 CSV, 이 보고서와 재현 코드 및 검증 파일은 Gate2F1A_results.zip에 있다. 월별 Core 키 CSV와 P50, P90, U, 양수일 및 주별 관측일 배열, 공급 대표값 및 관측일 배열도 결과 ZIP의 core_checkpoints 폴더에 보존했다. 이 중간 산출물은 이미 계산된 결과이며 새 분석 없이 export_core_csv.py로 표를 복원할 수 있다.

원자료 및 선택 마스터 SHA256, 실제 CSV 날짜, 재업로드 대응, 달력과 공간 근거는 input_contract.json에 기록했다. F0S-X 원자료 전체 필드 비교의 중복 목록은 정확한 원본 해시가 일치하는 경우에만 재사용했다. 원자료 총행 수는 18개 월 및 자료종류 조합 모두 기존 F0S-X와 정확히 일치했다. 각 월 1,000개 조합의 linear 분위수를 NumPy와 대조했다. 백분위, 후보, 주별 관측조건, 좌표보류, Core 조합수 및 공급의 NA 유지도 검증했다.

P90은 짧은 월별 표본의 상단 몇 날짜와 선형보간에 민감하다. U는 날짜별 구간 평균 운행시간의 불안정성이며 개별 버스 지연이나 대기시간으로 바꾸어 해석하지 않는다. C2는 관측 부분합이다. 이번 결과는 시간적으로 독립된 외부검증이나 최종 정책효과를 의미하지 않는다.
'''
assert chr(183) not in text;(O/'Gate2F1A_monthly_core_report.md').write_text(text,encoding='utf-8')
ref=O/'reference';ref.mkdir(exist_ok=True)
for p in ['day_calendar.csv','monthly_date_coverage.csv','monthly_duplicate_audit.csv','duplicate_key_details.csv']:
 shutil.copyfile(SX/p,ref/p)
for p in ['final_month_eligibility.csv','monthly_master_assignment.csv','route_type_history.csv','coordinate_readiness.csv','spatial_asset_verification.json']:
 shutil.copyfile(M/p,ref/('F0M_'+p))
for p in (M/'reference').glob('*.md'):shutil.copyfile(p,ref/p.name)
shutil.copyfile(R/'f1a_sources/unpacked/Gate2C2_results/dong_supply_reliability_relationship.csv',ref/'legacy_August_dong_metrics.csv')
print(S[['month','valid_both_dongs','Pearson_C2_U','Spearman_C2_U','candidate_count']].to_string(index=False));print('ASSEMBLY_AND_QA_COMPLETE',flush=True)
