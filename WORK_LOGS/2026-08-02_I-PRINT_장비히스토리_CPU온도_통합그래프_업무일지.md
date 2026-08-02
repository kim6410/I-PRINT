# I-PRINT 장비 히스토리 CPU·온도 통합 그래프 업무일지

- 작업일: 2026-08-02
- 대상: `/home/bourne/I-print`

## 요청 내용

장비별 히스토리 화면 하단에 실제 누적 데이터를 사용하여 CPU 사용량과 온도 추이를 한 그래프에서 함께 표시합니다.

## 구현 내용

- 특정 장비가 선택된 경우에만 그래프를 표시합니다.
- 전체 장비 보기 상태에서는 서로 다른 장비 수치가 섞이지 않도록 그래프를 숨깁니다.
- `device_status_history`에서 선택 장비의 최근 이력 최대 120개를 시간순으로 반환합니다.
- CPU 사용량은 왼쪽 축 0~100% 기준으로 표시합니다.
- 온도는 오른쪽 축에서 실제 저장값 범위에 맞춰 표시합니다.
- 두 추이를 하나의 Canvas 선 그래프에 함께 출력합니다.
- 브라우저 크기 변경 시 그래프를 다시 그립니다.
- 온도 값이 없는 장비는 CPU 선만 표시하고 온도 선은 비워 둡니다.

## API 변경

`GET /api/device-history`

추가 응답:

- `chart_points`
  - `collected_at`
  - `cpu_percent`
  - `temperature_c`

## 검증

- Python 문법 검사 PASS
- `device_history.html` HTML 파싱 PASS
- JavaScript 문법 검사 PASS
- 로그인 후 `/history?device_id=1` HTTP 200
- 그래프 Canvas 및 제목 노출 확인
- 5800X 실제 CPU·온도 이력 2건 API 반환 확인
- 전체 장비 조회 시 그래프 데이터 0건 확인
- 서비스 active
- `/health` 정상
- `git diff --check` PASS

## 보호 사항

- 기존 검색, 전체 장비 보기, 15건 페이지네이션, 히스토리 표는 유지했습니다.
- SQLite 운영 DB는 Git에 포함하지 않았습니다.
- 텔레그램 및 프린터 제어 로직은 수정하지 않았습니다.
