from pathlib import Path
import pandas as pd,numpy as np,json,shutil
ROOT=Path(__file__).resolve().parent;O=ROOT/'Gate4C2B';S=O/'staging'
# Submission adapter: paths only; the original calculation statements follow.
from seoul_bus_paths import bind as _submission_bind
globals().update(_submission_bind('C2B'))
def read(n):return pd.read_csv(S/n,float_precision='round_trip',dtype={'dong_code':str,'period':str,'month':str,'date':str})
a=read('daily_activity_case_results.csv');w=read('daily_weather_case_results.csv');d=read('monthly_direction_summary.csv');b=read('daily_bus_case_panel.csv');s=read('case_evidence_summary.csv');qa=json.loads((O/'analysis_QA.json').read_text());names=b[['dong_code','dong_name']].drop_duplicates();order=names.dong_code.tolist()
C={'LOCAL_PEOPLE_DONG':'내국인','LONG_FOREIGNER_DONG':'장기체류 외국인','TEMP_FOREIGNER_DONG':'단기체류 외국인'}
def f(x,n=3):return 'NA' if pd.isna(x) else f'{float(x):.{n}f}'
def row(g):assert len(g)==1;return g.iloc[0]
def ap(code,comp,y,var='Main'):return row(a[(a.dong_code==code)&(a.component==comp)&(a.outcome==y)&(a.variant==var)&(a.period=='pooled')])
def wp(code,analysis,y,var='Main'):return row(w[(w.dong_code==code)&(w.analysis==analysis)&(w.outcome==y)&(w.variant==var)&(w.period=='pooled')])
def ds(code,domain,y,comp=None,var='Main',stat='spearman'):
 g=d[(d.dong_code==code)&(d.domain==domain)&(d.outcome==y)&(d.variant==var)&(d.statistic==stat)]
 if comp is not None:g=g[g.component==comp]
 return row(g)
def signs(g):return f'{int(g.positive_months)}/{int(g.zero_months)}/{int(g.negative_months)}/{int(g.NA_months)}'
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])

answers={}
for code in order:
 name=names.set_index('dong_code').loc[code,'dong_name'];er=wp(code,'rain_minus_dry','daily_dong_E');ir=wp(code,'rain_minus_dry','daily_dong_I_rate');te=ds(code,'temperature_spearman','daily_dong_E');ti=ds(code,'temperature_spearman','daily_dong_I_rate')
 if code in set(a.dong_code):
  aa=[]
  for comp,cn in C.items():
   ae=ap(code,comp,'daily_dong_E');ai=ap(code,comp,'daily_dong_I_rate');dd=ds(code,'activity','daily_dong_E',comp)
   aa.append(f'{cn}: E ρ={f(ae.spearman)}, I ρ={f(ai.spearman)}, E 월별 방향(양/0/음/NA)={signs(dd)}')
  act='; '.join(aa)+'. 성분에 따라 다르며 도시활동의 원인효과를 의미하지 않는다.'
 else:act='생활인구 공간대응 미승인으로 Main NA. 외부조건으로 설명되지 않았다는 결과와 구별한다.'
 rain=f'제한된 수치표본에서 강수−명시적 0의 E 평균차 {f(er.mean_difference_rain_minus_dry)}초, 중앙값차 {f(er.median_difference_rain_minus_dry)}초, I 평균차 {f(ir.mean_difference_percentage_points)}%p. 강수 {int(er.n_rain_dates)}일, 명시적 0 {int(er.n_dry_dates)}일, 버스 유효일 중 강수 수치 부재 {int(er.n_precipitation_NA_dates_with_bus)}일. 일반적인 건조일 대비 결론은 보류.'
 temp=f'E 월별 방향(양/0/음/NA)={signs(te)}, I={signs(ti)}. E 월별 ρ 범위 {f(te.monthly_min)}~{f(te.monthly_max)}. 양방향 또는 0이 섞이며 공통 기온 메커니즘을 확정하지 않는다.'
 overall='생활인구의 동반관계는 일부 성분과 월에 한정되고, 기온 및 조건부 강수 비교만으로 반복 불안정이 설명됐다고 볼 수 없다. 현재 자료로 설명 미확정.'
 answers[code]={'activity_case_answer':act,'rain_case_answer':rain,'temperature_case_answer':temp,'unexplained_case_answer':overall}
 for k,v in answers[code].items():s.loc[s.dong_code.eq(code),k]=v
s.to_csv(S/'case_evidence_summary.csv',index=False,encoding='utf-8-sig',float_format='%.17g')

text=['# Gate 4-C2B 일 단위 외부조건 사례분석',
'**생활인구와 공식 일평균기온의 일 단위 사례분석 완료. 강수는 공식 일별 표의 수치 가용성이 제한되어 조건부 참고 분석으로 보존한다. 기존 9개 동과 43개 진단구간을 변경하지 않았으며, 원인 또는 정책효과를 추정하지 않았다.**',
'## 1. 사령탑 답변',
'1. 생활인구와 버스 이상의 양의 동반관계는 6개 지역 전체와 모든 성분에서 일관되게 반복되지 않는다. 내국인 성분의 E pooled ρ는 0.066~0.373이다. 잠실6동은 E ρ=0.373, 월별 7양/1음이며, 잠실본동은 ρ=0.214, 평가가능 7개월 모두 양수다. 잠실본동의 1월은 기존 버스 Core 부재로 NA다. 단기체류 외국인 성분은 양방향이 섞이며 같은 결과를 보장하지 않는다.',
'2. 강수일의 이상이 9개 지역에서 동일하다고 결론낼 수 없다. 제한된 명시적 수치 표본에서는 E 평균차의 부호가 갈리고, 평균과 중앙값 또는 E와 I의 방향도 달라진다. Main 계획 평일 160일 중 양수 45일, 명시적 0 15일, 수치 부재 100일이다. 수치 부재를 dry_day로 바꾸지 않았으므로 이 결과는 일반적인 강수일 대 모든 건조일의 비교가 아니다.',
'3. 기온은 월별로 같은 방향이 일관되게 반복되지 않는다. pooled ρ는 E −0.065~0.074, I −0.055~0.119이며 월별 계수의 방향이 지역과 지표에 따라 바뀐다. 소공동처럼 pooled E가 음수지만 8개월 중 6개월의 월별 계수가 양수인 경우도 있어 pooled 값만으로 계절효과를 해석하지 않는다.',
'4. 관측된 동반관계의 구성이 사례별로 다르다는 기술적 설명은 가능하다. 다만 상관의 지역 간 차이가 통계적으로 검증됐거나, 서로 다른 발생 원인을 식별했다는 주장은 하지 않는다. “같은 반복 불안정이라도 관측되는 외부조건의 동반 양상은 같지 않았다”가 허용 표현이다.',
'5. 외부자료는 일부 사례의 활동 맥락을 보탰지만 기존 버스 분석의 설명력이 실질적으로 증가했다고 입증하지 않았다. 설명력 지표나 예측모형을 추가하지 않았다. 반복 불안정이 생활인구, 기상으로 설명됐다는 결론은 허용하지 않는다.',
'6. 결과를 약하다는 이유로 삭제하지 않는다. 최종 보고서 핵심 결론에서는 단기체류 외국인 및 pooled 기온을 공통 설명변수로 강조하지 않는다. 세 생활인구 성분과 기온의 전체 결과는 부록에 남긴다. 일반적인 강수 효과 주장은 자료 범위 제약 때문에 제외하며 조건부 숫자는 감사표에 보존한다.',
'7. 추가 외부자료 없이 기존 버스 결과와 M3 근거를 중심으로 대표 사례 및 정책진단 단계로 진행할 수 있다. 이번 결과로 원인을 확정하거나 정책효과를 약속하지 않는다. 강수 비교를 최종 핵심 증거로 사용하려면 공식 0, 무강수 상태 및 결측을 구분할 수 있는 ASOS 108 일자료와 필드 정의가 추가로 필요하다.',
'## 2. 범위와 집계',
'Main은 2025-09, 2025-10, 2026-01~06의 8개월이다. 2025-11, 2025-12, 2026-07은 복구하지 않았고 2026-08도 넣지 않았다. 1월 포함 Main과 1월 전체 제외 QA를 함께 저장했다. 1월 13~14일만 삭제하지 않았다.',
'기존 M2의 저장 E_sec 및 P90_reached를 사용했다. E는 같은 월, 노선, NODE 쌍, 순서, 시간의 P50 대비 일평균 운행시간 편차이며 단위는 초다. I는 해당 세부키 저장 P90 도달 표시다. 같은 표본에서 추정한 기준에 대한 도달 표시이며 개별 버스 지연 확률, 정시성 위반률 또는 승객 비율이 아니다.',
'복수 순서키가 같은 A-날짜-시간에 있으면 M2와 동일하게 E 중앙값, I 평균으로 접었다. 이어 A-날짜에서 시간별 E 중앙값과 I 평균, 동-날짜에서 구간별 E 중앙값과 I 평균을 차례로 계산했다. 따라서 두 수준에서 시간과 구간을 각각 동일 가중하며, 관측시간 수가 많은 구간에 직접 더 큰 가중치를 주지 않는다. 결측 구간은 0으로 만들지 않고 가용 구간 및 셀 수를 공개했다.',
'I의 동일가중 평균은 내부적으로 정확한 유리수로 연산한 뒤 최종 실수로 저장했다. 이는 순위 동률이 부동소수점 합산 순서에 의해 달라지는 것을 방지하는 수치적 QA이며 새 반올림 cutoff가 아니다. CSV는 round-trip 정밀도로 저장했다.',
'해석 단위는 동 × 날짜다. pooled는 각 동의 가용 날짜를 풀링한 Spearman이며 월 동일 가중 계수나 계절, 요일을 통제한 추정치가 아니다. 같은 날짜의 구간과 시간은 독립 사건으로 세지 않았다. 서울 108의 같은 기상값이 9개 동에 공통으로 붙으며 이를 독립적인 9개의 기상 실험으로 해석하지 않는다.',
'생활인구는 공간 승인이 있는 소공동, 필동, 신림동, 잠실본동, 잠실6동, 잠실7동만 사용했다. 강남구 3개는 NA다. C2A의 성분별 relative_activity_deviation을 바꾸지 않고 24개 시간 라벨의 가용값 중앙값을 일 노출로 만들었다. 세 성분을 합산하거나 특정 시간을 선택하지 않았다. 공식 명칭은 “시간대별 생활인구 기반 도시활동 강도”이며 일별 값은 그 기준 대비 편차의 중앙값이다.',
'## 3. 표본과 결측 QA']
rows=[]
for code in order:
 g=b[b.dong_code.eq(code)];nj=g[g.month.ne('202601')]
 rows.append([g.dong_name.iloc[0],int(g.fixed_diagnostic_segments.iloc[0]),len(g),int(g.daily_dong_E.notna().sum()),int(nj.daily_dong_E.notna().sum()),'승인' if g.living_population_main_approved.iloc[0] else 'NA'])
text += [table(['동','고정 구간 수','계획 평일','Main 버스 유효일','1월 제외 유효일','생활인구'],rows),
f'M2 원 패널 {qa["M2_native_rows"]:,}행에서 유효 양수 관측 {qa["M2_valid_native_rows"]:,}행을 승계했고, 순서키를 접은 유효 시간 셀은 {qa["folded_valid_hour_cells"]:,}개다. 계획 동-날짜 {qa["planned_dong_days"]:,}개 중 {qa["valid_dong_days"]:,}개가 유효하며 {qa["absent_dong_days"]}개는 NA다. 낮은 관측 수를 이유로 새로 제거한 날짜는 없다.',
'전체 9개 동이 동시에 버스 결과 NA인 날은 2025-10-29, 2026-01-05, 2026-01-06, 2026-05-18, 2026-06-15, 2026-06-16이다. 잠실본동은 1월 전체 NA이고 신사동(강남구)은 2026-03-26도 NA다. 기존 공통 분석일 부재 및 고정 Core 셀의 유효성에 따른 결과이며 외부조건 때문에 제외한 것이 아니다.',
'생활인구 일별 성분-동-날짜 2,880개는 모두 계산 가능하다. 이 중 2,868개는 24시간, 10개는 23시간, 2개는 22시간이 기여했다. 6개 동의 동일 시간 결측 14개를 임의 보간하지 않았다. 외부자료만 있는 날짜는 버스 결합 시 완전쌍에서 빠지며 버스 결과를 0으로 채우지 않았다. 월별 및 성분별 분모는 CSV에 있다.',
'## 4. 도시활동 결과',
'아래는 Main 날짜 pooled Spearman과 월별 부호 분포다. 부호 표기는 양/0/음/NA 순서이며 새 판정 cutoff가 아니다. 모든 성분을 같은 형식으로 공개한다.']
rows=[]
for code in order:
 if code not in set(a.dong_code):continue
 for comp,cn in C.items():
  ae=ap(code,comp,'daily_dong_E');ai=ap(code,comp,'daily_dong_I_rate');de=ds(code,'activity','daily_dong_E',comp);di=ds(code,'activity','daily_dong_I_rate',comp)
  rows.append([ae.dong_name,cn,int(ae.n_pairs),f(ae.spearman),signs(de),f(ai.spearman),signs(di),f(ap(code,comp,'daily_dong_E','noJan').spearman),f(ap(code,comp,'daily_dong_I_rate','noJan').spearman)])
text += [table(['동','성분','Main 날짜 n','E ρ','E 월별 부호','I ρ','I 월별 부호','noJan E ρ','noJan I ρ'],rows),
'내국인 성분의 pooled E와 I는 6개 동 모두 양수지만 월별 방향이 모두 양수인 것은 아니다. 소공동과 잠실6동의 장기체류 외국인 성분에서도 양의 동반관계가 보이는 한편, 신림동 단기체류 외국인의 I는 pooled −0.163이며 8개월 중 7개월이 음수다. 이는 실제 관측된 반대 방향을 그대로 보존한 결과이지 어느 성분을 원인으로 채택하거나 배제한 기준이 아니다.',
'월별 각 계수, n, 변수별 고유값 수와 NA 이유는 daily_activity_case_results.csv에 있다. 월별 계수 범위와 중앙값은 monthly_direction_summary.csv에 따로 저장했다. 월별 소표본, 연속 날짜의 의존성, 외부노출과 버스의 서로 다른 관측 선택이 남으므로 유의성 또는 일반화가 입증됐다고 읽지 않는다.',
'## 5. 기상 자료의 범위',
'사용자가 제공한 ASOS 파일은 시간자료여서 일강수량으로 합산하지 않았다. 기상청 날씨누리의 서울(유) 108 일별자료 표에서 Main 8개월의 공식 일평균기온과 일강수량 표시값 242일을 별도로 확보했다. 요청 월과 실제 표 제목, 날짜 개수 및 원문 해시를 확인했다. 원문과 URL을 패키지에 보존했다. 날씨누리는 단순 참고용과 누락값 유의사항을 표시하므로 기상자료개방포털의 정식 일자료 원본을 추가 검증한 것으로 과장하지 않는다.',
'공식 표의 일평균기온은 계획 160일 모두 수치가 있다. 일강수량의 “-”는 수치로 보고되지 않은 상태로 보존했다. 결측/무표시를 0으로 채우지 않았다. 사용자가 지정한 숫자 0 대 양수 규칙만 적용했으며, 숫자 0 표기가 기상학적 완전 무강수를 입증한다는 주장은 하지 않는다. 눈, 미량 강수 등 현상을 따로 분류하거나 새 강수 cutoff를 만들지 않았다.',
'## 6. 기온 결과']
rows=[]
for code in order:
 te=wp(code,'temperature_spearman','daily_dong_E');ti=wp(code,'temperature_spearman','daily_dong_I_rate');de=ds(code,'temperature_spearman','daily_dong_E');di=ds(code,'temperature_spearman','daily_dong_I_rate')
 rows.append([te.dong_name,int(te.n_pairs),f(te.spearman),signs(de),f(de.monthly_min)+'~'+f(de.monthly_max),f(ti.spearman),signs(di),f(wp(code,'temperature_spearman','daily_dong_E','noJan').spearman),f(wp(code,'temperature_spearman','daily_dong_I_rate','noJan').spearman)])
text += [table(['동','Main 날짜 n','E pooled ρ','E 월별 부호','월별 E ρ 범위','I pooled ρ','I 월별 부호','noJan E ρ','noJan I ρ'],rows),
'일부 월에 큰 계수가 있어도 다른 월에서 부호가 뒤집힌다. pooled가 0에 가깝다는 사실만으로 기상 영향 부재를 증명하지 않고, 월별 양수 개수가 많다는 사실만으로 기온의 인과효과를 주장하지 않는다. 높은/낮은 기온의 임의 기준도 만들지 않았다.',
'## 7. 강수 비교: 조건부 참고',
'**일반적인 강수일 대 모든 건조일 비교로 최종 결론을 내리지 않는다. 수치가 없는 100/160일을 NA로 남긴 제한된 표본이므로 누락 선택의 가능성이 크다.** 2025-10과 2026-04는 버스 유효일 중 명시적 0일이 없어 월별 차이가 NA다. 잠실본동 1월도 버스 부재로 NA다. 다음 숫자는 누락된 건조일을 복원한 결과가 아니다.']
rows=[]
for code in order:
 er=wp(code,'rain_minus_dry','daily_dong_E');ir=wp(code,'rain_minus_dry','daily_dong_I_rate')
 rows.append([er.dong_name,int(er.n_rain_dates),int(er.n_dry_dates),int(er.n_precipitation_NA_dates_with_bus),f(er.mean_difference_rain_minus_dry),f(er.median_difference_rain_minus_dry),f(ir.mean_difference_percentage_points),f(ir.median_difference_percentage_points),f(wp(code,'rain_minus_dry','daily_dong_E','noJan').mean_difference_rain_minus_dry)])
text += [table(['동','강수일 n','명시적 0일 n','강수 NA일 n¹','E 평균차(초)','E 중앙값차(초)','I 평균차(%p)','I 중앙값차(%p)','noJan E 평균차(초)'],rows),
'¹ 버스 결과가 유효한 날짜 안에서 수치가 없는 강수 일수다. 차이는 강수−명시적 0이다. I의 원 비율 차이와 %p를 CSV에 모두 보존했다.',
'제한 표본에서도 소공동과 잠실6동은 E 평균차가 음수인 반면 필동, 대치2동 등은 양수다. 개포1동과 잠실7동은 E 평균차와 중앙값차 부호가 다르고, 1월 제외 시 E 평균차의 부호도 바뀐다. 이 불일치를 숨기지 않는다. 다만 적은 명시적 0일 수와 많은 비수치 날짜 때문에 지역별 강수 반응의 차이가 확정됐다는 근거로 사용하지 않는다.',
'## 8. 9개 사례의 네 질문']
for code in order:
 name=names.set_index('dong_code').loc[code,'dong_name'];ans=answers[code]
 text += [f'### {name}',f'1. 도시활동: {ans["activity_case_answer"]}',f'2. 강수: {ans["rain_case_answer"]}',f'3. 기온: {ans["temperature_case_answer"]}',f'4. 설명 범위: {ans["unexplained_case_answer"]}']
text += ['## 9. 1월 제외 QA와 최종 사용',
'Main을 변경하지 않았다. 생활인구 내국인 E의 양수 방향은 1월 제외 후 6개 동 모두 유지되지만 계수 크기는 달라진다. 다른 성분 및 I에서는 부호가 바뀌는 경우도 있다. 잠실본동은 1월 버스 결과가 원래 NA여서 Main과 noJan이 동일하다. 기온 pooled의 0 근처 계수 및 조건부 강수 차이의 부호 전환은 원 결과표에 모두 남겼다.',
'허용 핵심문장: “일부 반복지역에서 도시활동 편차와 운행시간 이상의 양의 동반관계가 관측됐지만, 그 크기와 월별 방향은 지역과 성분에 따라 달랐으며 공통 원인으로 확정되지 않았다.”',
'대표 사례는 기존 고정 명단과 M3 진단을 출발점으로 검토할 수 있다. 이번 상관이 큰 동을 새 대표후보, 정책 우선지역 또는 원인유형으로 선정하지 않았다. 생활인구와 버스 E/I가 같은 날짜에 함께 달라졌다는 기술적 근거만 추가하며, 외부검증지역을 노출조건만으로 먼저 고정하는 C0 원칙도 변경하지 않는다.',
'최종 보고서에서는 생활인구 사례를 제한적 맥락으로, 기온은 방향 불일치를 보이는 보조 결과로, 강수는 자료조건 미충족 주의사항과 조건부 표로 배치하는 것이 타당하다. 약한 결과를 누락하거나 인과표현으로 확대하지 않는다.',
'## 10. 산출물과 재현',
'필수 6개 산출물을 생성했다. 4개 CSV에는 완전쌍 n, 월별 및 pooled, 1월 제외 결과를 보존했다. 패키지에는 원 순서키를 접은 일별 구간 표, 성분별 일별 노출, 월별 방향 요약과 QA, 공식 기상 일별 원문 및 재현 코드를 추가했다. 원본과 기존 결과를 덮어쓰지 않았다.',
'execution_spec_frozen.md는 계산 전에 작성한 운영명세이며 source_manifest.json에는 원본 및 저장 명세 해시가 있다. verification_results.json은 독립적인 집계, 상관, 분모, NA, 제외월 점검을 기록한다. 숫자 CSV는 UTF-8 BOM이며 결측은 빈 셀이다. CSV의 데이터값을 보존하기 위해 표시용 반올림은 보고서에만 적용했다.',
'공식 일자료 출처: https://www.weather.go.kr/w/weather/land/past-obs/obs-by-day.do?stn=108&yy=2025&mm=9&obs=1 . 나머지 7개월의 정확한 URL과 원문 지문은 source_manifest.json의 weather_metadata_manifest에 있다. API 인증이 필요한 경로는 사용하지 않았고, 비공식 기상 재분석이나 시간강수 합산으로 대체하지 않았다.']
(O/'Gate4C2B_daily_case_report.md').write_text('\n\n'.join(text)+'\n')
(O/'units_and_fields.md').write_text('''# 필드와 해석

- daily_dong_E, daily_segment_E: 초. 저장 M2 P50 대비 일평균 운행시간 편차의 명세상 중앙값 집계. 음수와 0 보존.
- daily_dong_I_rate, daily_segment_I_rate: 0~1 비율. 저장 M2 P90 도달 표시의 명세상 평균 집계. 개별 버스 확률 또는 승객 비율이 아님.
- valid_hour_cells: 원 순서키를 접은 구간-날짜-시간 유효 셀 수. native_positive_observations와 구분.
- fixed_diagnostic_segments: 기존 고정 43개 중 해당 동의 구간 수. valid_segments는 해당 날짜 실제 기여 구간 수.
- daily_activity_deviation_ratio: 성분별 C2A relative_activity_deviation의 24시간 가용값 중앙값. 비율 1은 100%. 활동량 총합이나 실제 방문객 수가 아님.
- LOCAL_PEOPLE_DONG / LONG_FOREIGNER_DONG / TEMP_FOREIGNER_DONG: 내국인 / 장기체류 외국인 / 단기체류 외국인. 합산 없음.
- Main/monthly: 해당 월. Main/pooled: 가용 Main 날짜를 풀링. noJan/pooled: 1월 전체 제외. 새로운 시간대, 요일 선택 없음.
- Spearman: 완전쌍의 평균동률 순위 Pearson. 상관 외 유의성 검정, p값, 회귀, 신뢰구간 없음.
- rain_minus_dry: 공식 일강수량 수치가 양수인 날 − 수치가 정확히 0인 날. '-' 표기는 NA. 일반적인 모든 무강수일과의 비교로 확정하지 않음.
- outcome_unit이 비율인 차이에 100을 곱한 *_percentage_points는 %p. 새로운 지표 또는 점수가 아니라 단위 변환.
- n_pairs는 동 내 날짜 수. 여러 구간과 시간 관측을 독립 표본으로 늘리지 않음.
- NA는 자료 부재, 상관 분모 또는 변이 부족, 미승인 공간, 비교집단 부재를 status로 구분. NA를 0으로 대체하지 않음.
''')
print('Report created:',len('\n\n'.join(text)), 'characters')
