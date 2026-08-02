# 2026-08-02 I-PRINT 관제 설정 DB 생성 및 UI 기능 연결 업무일지

## 작업 범위

기존 `printer_jobs.db`를 유지한 상태에서 관제 설정용 SQLite 테이블을 추가하고 `/settings` 화면의 조회·ON/OFF·반복주기·시간대 저장 기능을 실제 DB에 연결했다.

## 안전 조치

- 수정 전 운영 DB를 `Backup/printer_jobs_before_alert_settings_YYYYMMDD_HHMMSS.db` 형식으로 백업
- 기존 `printer_jobs`, `managed_devices` 테이블 유지
- 기존 텔레그램 감시 스레드와 프린터 제어 로직은 변경하지 않음
- 모든 스키마는 `CREATE TABLE IF NOT EXISTS` 방식으로 반복 실행 가능하게 구성

## 생성 테이블

- `alert_contacts`: 담당자와 텔레그램 Chat ID, 담당 시간, ON/OFF
- `alert_locations`: 위치, 주소, PC·프린터 수, 상태, ON/OFF
- `alert_types`: 장애 유형, 심각도, 기본 재알림 주기, ON/OFF
- `alert_time_groups`: 시간 그룹, 시작·종료 시각, 요일, 재알림, 우선순위
- `alert_policies`: 정책명, 위치, 대상, 시간 그룹, 반복주기, 최소 지속시간, ON/OFF
- `alert_policy_contacts`: 정책과 담당자 연결
- `alert_policy_types`: 정책과 장애 유형 연결
- `alert_history`: 발생·확인·복구·수신자·발송 횟수 이력

## 초기 데이터

UI 껍데기에 표시하던 담당자 2명, 위치 3곳, 장애 유형 7개, 시간 그룹 4개, 알림 정책 5개를 DB 초기 데이터로 등록했다.

기존 텔레그램 허용 Chat ID 중 첫 번째 값은 담당자 1의 Chat ID로 저장하되 실제 값은 로그와 문서에 출력하지 않았다.

## API 연결

- `GET /api/settings`: 전체 설정과 요약 조회
- `PATCH /api/settings/{entity}/{id}/toggle`: 정책·담당자·위치·장애유형·시간그룹 ON/OFF
- `PATCH /api/settings/types/{id}`: 장애 유형 기본 재알림 주기 저장
- `PATCH /api/settings/time-groups/{id}`: 시작·종료 시각 저장

## 화면 연결

`settings.html`에서 다음 항목을 SQLite DB 기준으로 동적 렌더링한다.

- 상단 요약 카드
- 알림 정책
- 담당자
- 위치 / PC 그룹
- 장애 유형
- 시간대
- 알림 이력

ON/OFF 스위치, 장애 재알림 주기, 시간대 입력은 변경 즉시 API를 통해 DB에 저장된다.

## 검증

- Python 문법검사 PASS
- HTML 파싱 PASS
- SQLite `integrity_check=ok`
- 생성 수량: 담당자 2, 위치 3, 장애유형 7, 시간그룹 4, 정책 5
- 정책 ON/OFF 저장 후 원래 값 복구 테스트 PASS
- 로그인 후 `/settings` 페이지 응답 및 동적 API 참조 확인 PASS
- `i-print-dashboard.service` active
- `/health` 정상

## 다음 단계

현재는 설정 저장과 UI 조회가 연결된 단계다.

다음 작업에서는 실제 텔레그램 감시 엔진이 `alert_policies`, `alert_contacts`, `alert_types`, `alert_time_groups`를 읽어 위치·PC·시간대·담당자별로 발송 대상을 결정하도록 연결한다.
