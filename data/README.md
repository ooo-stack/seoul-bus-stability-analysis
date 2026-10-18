# 실제 입력자료와 비공개 배치

원자료, ZIP, XLS/XLSX, 원시 관측 CSV, 공간파일 및 대형 중간배열은 저장소에 없다. 아래 상대경로는 사용자가 본인 컴퓨터에 준비할 위치다. 같은 이름의 최신 파일로 과거 스냅샷을 바꾸지 않는다. 기존 코드의 원본 해시 검증이 실패하면 새로운 값으로 분석을 계속하지 않는다.

## 실제 사용한 원자료

| 자료명 | 제공기관과 공식 URL | 사용 기간/필요 파일 | 역할 |
| --- | --- | --- | --- |
| 서울시 노선별 정류장 구간별 평균 운행시간 정보 | 서울특별시, [OA-21217](https://data.seoul.go.kr/dataList/OA-21217/S/1/datasetView.do) | 2025-09~2026-08의 `tpss_route_section_speedh_*.zip`, 경계 주차 자료 포함 | 실제 날짜/키 감사, 양수 시간 Core, P50/P90/U, 일별 E/I |
| 서울시 노선별 정류장별 총 버스 운행횟수 정보 | 서울특별시, [OA-21220](https://data.seoul.go.kr/dataList/OA-21220/S/1/datasetView.do) | 같은 기간 `tpss_sta_route_hturn_*.zip` 및 기존 8월 주차 파일 | 날짜 가용성, 빈칸 구조 감사와 C2 |
| 서울시 버스운행노선 정보 및 노선기본정보 | 서울특별시, [OA-15066](https://data.seoul.go.kr/dataList/OA-15066/F/1/datasetView.do), [버스정보 안내](https://topis.seoul.go.kr/) | 아래 10개 스냅샷의 `서울시버스노선기본정보(YYYYMMDD).xlsx`, 원 보관 `서울시버스 정보.zip` | 역사 노선유형과 정확 노선명/ROUTE_ID 연결 |
| 서울시 버스정류소 위치정보 | 서울특별시, [OA-15067](https://data.seoul.go.kr/dataList/OA-15067/S/1/datasetView.do) | `서울시버스정류소위치정보(YYYYMMDD).xlsx` | 역사 NODE_ID, 정류장명과 좌표 |
| 서울시 버스노선별정류소정보 | 서울특별시, [버스 노선정보 제공 창구](https://data.seoul.go.kr/dataList/OA-1091/F/1/datasetView.do), 위 역사 마스터 보관본 | `서울시버스노선별정류소정보(YYYYMMDD).xlsx` | 노선/NODE/순번 정확키, 위치 및 명칭의 동시점 보완 |
| 기존 427개 행정동 경계 | 기존 프로젝트의 공식 검증 공간자산, [브이월드](https://www.vworld.kr/) | `구역의도형_전체분_서울특별시.zip`, 실행 배치명 `02-_-_-.zip`, 내부 `11000/TL_SCCO_GEMD.*` | 공통 서울 내부 판정 및 도착동 배정 |
| 전국 행정동 코드정보 | 서울특별시 생활인구 공식 자료실, [생활인구 아카이브](https://data.seoul.go.kr/dataVisual/seoul/seoulLivingArchive.do) | `전국_행정동_코드정보.zip`, 실행 배치명 `04-_-_-.zip`, 월별 `SEOUL_ADMI/ADMI_YYYYMM.csv` | 8자리 연구코드와 10자리 경계코드 대조 |
| 내국인 생활인구 | 서울특별시, [OA-14991](https://data.seoul.go.kr/dataList/OA-14991/S/1/datasetView.do) | Main 8개월 `LOCAL_PEOPLE_DONG_YYYYMM.zip` | 승인 6개 동의 성분별 도시활동 상대편차 |
| 장기체류 외국인 생활인구 | 서울특별시, [OA-14992](https://data.seoul.go.kr/dataList/OA-14992/S/1/datasetView.do) | Main 8개월 `LONG_FOREIGNER_DONG_YYYYMM.zip` | 별도 성분 분석, 합산 없음 |
| 단기체류 외국인 생활인구 | 서울특별시, [OA-14993](https://data.seoul.go.kr/dataList/OA-14993/S/1/datasetView.do) | Main 8개월 `TEMP_FOREIGNER_DONG_YYYYMM.zip` | 별도 성분 분석, 합산 없음 |
| ASOS 서울 108 공식 일자료 | 기상청, [ASOS 자료](https://data.kma.go.kr/data/grnd/selectAsosRltmList.do?pgmNo=36), [실제 사용한 공식 일별 표 예시](https://www.weather.go.kr/w/weather/land/past-obs/obs-by-day.do?stn=108&yy=2025&mm=9&obs=1) | Main 8개월의 공식 일평균기온/일강수량 표, 기존 `official_asos108_daily.csv`와 원문 해시 manifest | 서울 공통 일별 기상조건. 시간강수 합산 없음 |
| AWS/ASOS 시간자료 | 기상청, [AWS 자료](https://data.kma.go.kr/data/grnd/selectAwsRltmList.do), 위 ASOS 창구 | 2025-09~2026-06의 아래 기존 다운로드명 | C2A 자료구조 감사에만 필요. C2B 일별 Main에는 AWS 사용 안 함 |
| 버스노선별 정류장별 시간대별 승하차 | 서울특별시, [열린데이터광장 공식 검색](https://data.seoul.go.kr/dataList/datasetList.do)에서 같은 자료명 | `2026년_버스노선별_정류장별_시간대별_승하차_인원_정보(06월).csv` | M3A 정확결합 감사, M3B A35의 6월 이벤트 맥락 |

행정동 경계의 과거 개별 다운로드 URL은 기존 인증문서에 보존돼 있지 않다. 위 공식 창구에서 같은 제목만 검색해 임의 파일을 대체하지 말고 `reference/spatial_asset_verification.json`의 기존 해시를 대조한다. SGIS `국가데이터처_SGIS 행정구역 통계 및 경계_20250630.zip`은 보조 보유자료이며 이 Main 427개 경계 대신 사용하지 않았다. [SGIS 자료제공 창구](https://sgis.kostat.go.kr/view/pss/downloadMore)도 참고할 수 있다.

노선별정류소정보는 실제 역사 XLSX 보관본이 입력이다. 실시간 API의 현재 경로로 동일하게 복원된다고 주장하지 않는다. 정확한 과거 파일이 없으면 기존 Gate 보관 중간자료를 사용하거나 재현 범위를 제한해야 한다.

## 마스터 스냅샷

필요 기준일은 20250901, 20251002, 20251103, 20251209, 20260108, 20260226, 20260305, 20260402, 20260506, 20260701 중 F0M에서 사용한 날짜다. 실제 월 매핑은 `outputs/F0M/monthly_master_assignment.csv`가 원장이다. 같은 스냅샷의 노선기본정보, 정류소위치정보, 노선별정류소정보를 사용한다. 20251002 등 월초 이후 파일은 그 달 Main에 소급하지 않는다.

`서울시버스 정보.zip` 원 보관 패키지와 그 안의 정확한 이름의 XLSX를 `data/raw/masters/`에 함께 둔다. 필요한 XLSX는 같은 폴더 또는 하위 폴더에 직접 풀어 둔다. 패키지 파일은 M1의 역사 명칭 해시 검증에도 사용된다. 원본 압축파일을 재압축하면 원 패키지 해시가 달라질 수 있다.

## 로컬 배치

| 경로 | 배치할 내용 |
| --- | --- |
| `data/raw/bus/` | 12개월 구조감사용 시간/횟수 ZIP 전체, 원본 그대로 |
| `data/raw/masters/` | 공식 역사 XLSX와 기존 `서울시버스 정보.zip` |
| `data/raw/spatial/` | 기존 경계 `02-_-_-.zip`, 코드 `04-_-_-.zip`, 환경감사 때만 전용차로 `03-A058_L_20260213.zip` |
| `data/raw/auxiliary/` | 아래 시간 기상 파일, 6월 승하차 및 M3A 감사용 공간/속도 표본 |
| `data/raw/external/c2a_metadata/` | 24개 생활인구 ZIP, 기존 정의서와 다운로드 해시 manifest, 공식 현행 지점 metadata |
| `data/raw/external/official_daily_weather/` | 기존 `official_asos108_daily.csv`, `source_manifest.json`, 원문 일별 HTML 보관본 |
| `data/private/` | 필요 시 기존 Gate 저장 중간자료, 공개 금지 |

별도 위치에 보관했다면 `config.local.json`의 상대경로를 지정한다. 로컬 경로와 파일을 GitHub에 함께 올리지 않는다. 실행 중 필요한 옛 파일명 별칭과 Gate 간 상대경로는 `src/run_gate.py`가 `data/work/` 안에서 만든다. 파일 해시, 날짜, 키를 고치는 기능은 없다.

기존 8월 운행횟수 주차 별칭은 `counts_week.zip`, `counts_w2.zip`, `counts_w3.zip`, `counts_w4.zip`이다. `reference/weekly_archive_aliases.json`의 원본 해시가 맞는 실제 ZIP을 찾아 작업폴더 안에만 별칭을 만든다. 파일명이 비슷하다는 이유로 대체하지 않는다.

## C2A 준비와 C2B의 구분

C2A의 실제 원본 감사코드는 생활인구와 당시 기상 업로드를 함께 감사한다. 아래 파일명이 필요하다.

- `OBS_AWS_TIM_20261017002148.xls`: 기온
- `OBS_AWS_TIM_20261017002756.xls`: 강수
- `OBS_AWS_TIM_20261017002354.xls`: 바람
- `OBS_AWS_TIM_20261017002854.xls`: 습도
- `OBS_ASOS_TIM_20261016132020.xls`: 서울 108 시간자료

확장자와 실제 저장형식이 다를 수 있으므로 원래 CP949 탭 구분 읽기 규칙을 유지한다. C2B 일별 기상은 이 시간자료를 합산하지 않고 별도 공식 일자료를 읽는다. `living_population_exposure_panel.csv`와 `analysis_calendar_metadata_only.csv`가 이미 있으면 `saved_gate_dirs.C2A`로 그 폴더를 지정할 수 있다. `.xls` 업로드 파일명은 데이터 제공기관의 공식 표준명이라는 뜻이 아니다.

생활인구 원자료는 2016년 코드 체계다. C2A-R에서 승인된 소공동, 필동, 신림동, 잠실본동, 잠실6동, 잠실7동만 일별 Main에 들어간다. 신사동(강남구), 대치2동, 개포1동의 공간대응을 이번 패키징에서 추정하지 않는다.

## M3A 환경감사 입력

환경감사를 원자료부터 재현할 때만 `2026년 6월 서울시 차량통행속도.xlsx`, `서울특별시 교통소통 표준링크 매핑정보_20250306.xlsx`, `A008_P_20250814.zip`, `A058_L_20260213.zip` 및 6월 승하차 표본이 필요하다. 제공기관은 서울특별시이며 [TOPIS](https://topis.seoul.go.kr/), [서울교통 빅데이터플랫폼](https://t-data.seoul.go.kr/), [서울 열린데이터광장](https://data.seoul.go.kr/)의 해당 자료명과 당시 보관본을 확인한다. 당시 개별 파일의 다운로드 주소가 보관되지 않은 항목은 현재 링크만으로 원본 동일성을 인증하지 않는다.

이 자료는 구조와 결합 가능성을 감사한 입력이다. 도로속도, 교차로, 전용차로 노출의 원인효과를 계산한 것이 아니다. Main M3B/C는 기존 M3A 감사 결과를 받아 비공간 변수와 정류장쌍 진단을 재현한다. `saved_gate_dirs.M3A`를 지정할 수 있으며 필요한 원자료까지 제출 ZIP에 포함하는 방식은 사용하지 않는다.

## 원자료가 아닌 저장 결과

`outputs/`는 기존 Gate의 행정동, 구간, 집단 요약이다. 개인 이동궤적, 승객 식별자, 차량별 운행기록, 시간대 원시 관측 패널은 포함하지 않는다. 코드/결과 출처 해시는 docs/에 있고 원자료 행 및 원본 키 충돌의 실제 값은 공개 파일에 넣지 않았다.
