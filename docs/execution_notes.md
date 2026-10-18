# 실제 실행순서와 경로 어댑터

## 원본 보존

src/gates/에는 실제 사용한 51개 Python 파일을 두었다. 경로가 필요한 파일에만 seoul_bus_paths의 바인딩을 삽입했다. C2B 분석 파일의 ROOT 할당 한 곳은 출력폴더 생성 전에 상대 작업경로를 사용하도록 바꿨다. 원본 AST에서 이 경로 노드와 어댑터 삽입만 제외하면 계산구문이 동일하다. 원본/정리본 SHA256과 변경 유형은 code_provenance.json에 있다.

이 어댑터는 raw값, 월 적격성, 지표 또는 후보를 계산하지 않는다. Gate가 서로의 디렉터리를 읽던 기존 구조를 data/work/ 안에서 재현한다. 심볼릭 링크를 지원하지 않는 Windows에서는 파일/폴더 복사로 대체한다. 캐시 입력은 처음에 없는 파일만 가져오며 재실행 결과 위에 옛 캐시를 덮어쓰지 않는다.

## 순서

1. F0SX 원본 inventory → scan → duplicates → sequence audit → assemble → verify.
2. F0M prepare_masters → audit_master_matches → finalize_readiness.
3. F1A prepare_inputs → run_all → route_population_QA → assemble_results → 기존 package_results(후속 단계가 요구하는 해시 manifest 생성).
4. F1B reproduce_gate2f1b. 입력과 출력은 CLI로 지정.
5. F1C 원 일별/4주창 복원 prepare → restore → compute_variants → assemble_robustness → verify.
6. M1 restore_core_inputs → analyze_segments → verify_outputs.
7. M2 analyze_hours → restore_daily → analyze_weekdays → summarize_results → verify_results.
8. 기존 M3A 결합가능성 감사 또는 보관된 감사 결과 준비. M3B build_nonspatial/verify → M3C analyze_evidence/verify.
9. 기존 C2A 노출 감사 결과 준비. C2B analyze → report → verify.

번호 1과 2는 01_data_audit.py 진입점으로 묶었다. 이후 02~08 진입점은 README와 대응한다. 데이터가 없는 현재 공개 저장소에서 `--run`이 즉시 전체 분석을 끝내는 구조가 아니다. `--check-inputs`의 존재 확인 후 실제 원본 해시와 키 검증은 원래 스크립트가 수행한다.

## 주 실행순서에서 제외한 코드

옛 임시 코드, 다운로드/업로드 도우미, 이미지 렌더러, 발표자료 제작 코드, 원시자료 복사본은 넣지 않았다. Gate별 본문 보고서와 기존 대형 ZIP을 다시 포장하는 코드도 후속 해시 계약에 필요한 F1A 예외를 제외하면 넣지 않았다. C2A의 기존 공개자료 다운로드 코드는 실제 노출 준비의 출처 확인용으로만 보존하고 Main 실행에서 자동 다운로드하지 않는다.

이 저장소의 분석단계를 실행하면 그 단계의 기존 계산을 재현한다. 이번 제출 정리 과정에서는 원시 버스 전체를 새로 분석하지 않았다. 저장결과 기반 QA와 원자료부터 재실행하는 절차를 혼동하지 않는다.
