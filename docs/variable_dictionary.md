# 주요 변수 사전

| 변수 | 단위/수준 | 정의와 주의 |
| --- | --- | --- |
| month | YYYYMM | 달력월. held 월과 8월의 역할을 구분 |
| dong_code | 8자리 문자열 | 기존 427개 연구 행정동 코드. 10자리 경계코드와 정확 대응 |
| route_id | 문자열 | 역사 마스터의 ROUTE_ID. 노선번호와 구분 |
| departure_node, arrival_node | 문자열 | 방향성 정류장 NODE_ID. ARS-ID로 대체하지 않음 |
| departure_sequence, arrival_sequence | 순번 | 같은 노선의 반복 정류장을 구분하는 원 세부키 |
| C2_count | 회, 동-월 | 전형적인 정류장의 관측 서비스량. 완전한 총운행량 아님 |
| U_sec | 초 | 날짜별 구간 평균 운행시간의 P90−P50. 정시성 아님 |
| C2_percentile, U_percentile | 0~100 | 기존 round(8)과 평균동률 순위, 각 비결측 분모 |
| candidate | True/False/NA | 월별 두 백분위 >=75. 미평가를 False로 바꾸지 않음 |
| V_rep, K_rep, R_rep | 월 수, 월 수, 0~1 | 기준 8개월의 평가가능 월, 후보 월, 비율 |
| *_noJan | 해당 단위 | 1월 전체 제외 QA. Main 대체 아님 |
| *_all | 해당 단위 | 8월 포함 적격 9개월 보조 요약 |
| segment_id | 문자열 | 기존 758개 배경의 식별자. 정책 순위 아님 |
| diagnostic_no | 정수 | 고정 43개의 표시번호. Top 순위 아님 |
| U_hour_sec | 초 | 같은 월/A/시간의 원 순서키 U 중앙값 |
| V_h, K_h, R_h | 월 수, 월 수, 비율 | 해당 시간의 기존 평가가능/고불안정 월과 비율 |
| E_sec | 초 | 일평균 운행시간 − 같은 월/세부키/시간의 저장 P50 |
| P90_reached | 0/1/NA | 같은 세부키 저장 P90 도달 표시. 개별 버스 지연확률 아님 |
| daily_segment_E | 초 | 날짜의 유효 시간 E 중앙값 |
| daily_segment_I_rate | 0~1 | 날짜의 시간 I 평균, 복수 순서키를 먼저 동일가중 접음 |
| daily_dong_E | 초 | 고정 구간 daily_segment_E 중앙값 |
| daily_dong_I_rate | 0~1 | 고정 구간 daily_segment_I_rate 평균 |
| valid_segments, valid_hour_cells | 수 | 날짜 결과에 기여한 구간과 접힌 시간 셀 수 |
| shared_route_count | 고유 노선 수 | 같은 월 방향성 정류장쌍 공유노선 수. 교통량 아님 |
| pair_support_rate | 0~1 | 복수노선 비교의 both_high/(both_high+A_only_high). 공통 원인확률 아님 |
| relative_activity_deviation | 비율, 성분/동/날짜/시간 | 기존 생활인구 기준 중앙값 대비 편차. 1은 100% |
| daily_activity_deviation_ratio | 비율 | 성분별 24시간 가용 상대편차 중앙값 |
| LOCAL_PEOPLE_DONG | 추정 인구 성분 | 내국인. 실제 방문객 전수 아님 |
| LONG_FOREIGNER_DONG | 추정 인구 성분 | 장기체류 외국인. 별도 보존 |
| TEMP_FOREIGNER_DONG | 추정 인구 성분 | 단기체류 외국인. 별도 보존 |
| daily_mean_temperature_c | ℃ | ASOS 서울 108 공식 일평균기온, 서울 공통 맥락 |
| daily_precipitation_mm | mm/day | 공식 일강수 수치. 비수치 표기는 NA |
| rain_day_status | 범주 | 수치 >0 rain_day, =0 dry_day, 비수치 NA. 일반 무강수와 자동 동일시하지 않음 |
| ridership_quality_group | A/B/C | 기존 정확결합 35개, 반복정류장 4개, 순번불일치 4개 |
| June boarding/alighting events | 이벤트 건수 | 6월 전체 날짜의 승하차 맥락. 고유승객이나 불안정 노출 승객 수 아님 |
| held_geometry | 상태 | 역사적 실제 경로 부재로 정밀 공간노출 미확정 |

CSV마다 원래 Gate의 열 이름을 보존했다. 같은 개념의 열이 U_sec, E_sec 등으로 표시될 수 있다. 원본 재현 코드와 소스 Gate를 docs/result_provenance.json에서 확인한다. 비율과 %p를 구분하며 새 합성점수는 없다.
