# 2026-08-01 I-PRINT 1차 운영 배포 및 Phase 2 다음 작업 인수인계

## 1. 인수인계 기준

I-PRINT는 2026-08-01 기준으로 1차 운영 배포가 완료됐습니다.

다음 작업자는 기능 수정 전에 반드시 아래 문서를 순서대로 확인합니다.

1. `/home/bourne/I-print/00_READ_FIRST.md`
2. `/home/bourne/I-print/WORK_LOGS/2026-08-01_I-PRINT_도메인_SSL_로그인_모바일_최종인수인계.md`
3. 이 인수인계 문서

## 2. 프로젝트 정보

```text
프로젝트 루트: /home/bourne/I-print
내부 서비스: http://127.0.0.1:8897
외부 서비스: https://iprint.mystorymaker.net
GitHub: https://github.com/kim6410/I-PRINT.git
브랜치: main
```

StoryMaker와는 별도 경로, 별도 저장소, 별도 서비스로 운영합니다.

## 3. 완료된 기능

- GitHub 저장소 생성 및 origin 연결
- StoryMaker 관련 흔적 제거
- `00_READ_FIRST.md`와 `README.md` 정비
- Git 미추적 파일 금지 및 운영 파일 제외 규칙 적용
- 관리자 로그인 적용
- 관리자 아이디 `i-print`
- 초기 비밀번호 `ssu`
- 비로그인 전체 접근 제어
- PC·모바일 자동 분기
- `/mobile` 모바일 전용 화면
- `?view=pc` PC 화면 강제 표시
- 카드보기·리스트보기·테마보기
- 카드 입체감과 상태 효과
- 외부 도메인 연결
- Nginx Proxy Manager Proxy Host 연결
- Let's Encrypt SSL 발급
- 504 Gateway Timeout 원인 분석 및 방화벽 보완

## 4. 네트워크 및 SSL 기준

```text
DNS
iprint.mystorymaker.net → 183.100.34.61

Nginx Proxy Manager 내부 연결
호스트 8897/tcp

방화벽 허용
172.19.0.0/16 → 8897/tcp
```

504 Gateway Timeout이 다시 발생하면 애플리케이션 코드보다 아래 순서로 먼저 확인합니다.

1. `8897` 서비스 응답
2. Nginx Proxy Manager 컨테이너 상태
3. Docker 네트워크 대역
4. `8897/tcp` 방화벽 허용 규칙
5. Proxy Host의 Forward Host와 Forward Port
6. SSL 인증서 상태

## 5. 타임머신 백업

도메인 연결 전 정상 기준 백업은 아래 경로에 있습니다.

```text
/home/bourne/I_PRINT_TIME_MACHINE/I_PRINT_WORKING_20260801_0526_iprint_domain_연결전
```

Git bundle과 주요 소스, 문서, Nginx Proxy Manager 스냅샷이 포함되어 있습니다.

## 6. Git 기준점

최종 업무일지 작성 커밋은 아래와 같습니다.

```text
커밋: 4f0e63e5d734d7fa36aad34faeae0d29922cb70a
메시지: I-PRINT 1차 운영 배포 최종 업무일지
```

이 인수인계 문서 자체는 위 커밋 다음에 별도 커밋되므로, 다음 작업 시작 시 `git log -1 --oneline`과 `origin/main`을 다시 확인합니다.

## 7. 최종 검증 상태

```text
로컬 /health: PASS
SQLite 응답: printer_jobs.db 정상
외부 HTTPS: PASS
비로그인 접근: HTTP 302 로그인 이동
관리자 로그인: PASS
모바일 자동 분기: PASS
타임머신 백업: 존재 확인 PASS
Git 미추적 파일: 0개
업무일지 작성 전 로컬·origin/main·원격 main 동기화: PASS
```

## 8. 다음 작업 Phase 2

다음 단계는 디자인 추가보다 실제 출력 작업과 프린터 오류 데이터를 수집하는 기능입니다.

1. 출력 중 문서 실시간 표시
2. 사용자명 표시
3. 문서명 표시
4. 페이지 수 표시
5. 출력 시작 시간과 종료 시간
6. 실시간 진행 상태
7. 프린터 오류 감지
   - 용지 부족
   - 토너 부족
   - 용지 걸림
   - 오프라인
   - 통신 오류
8. 관리자 알림 기능

## 9. Phase 2 권장 작업 순서

### 1단계. Windows 수집 가능 항목 조사

5800X와 원격 Windows PC에서 PowerShell로 실제 취득 가능한 값을 먼저 확인합니다.

- `Get-PrintJob`
- `Get-Printer`
- WMI 또는 CIM 프린터 상태
- Windows 이벤트 로그
- 인쇄 대기열 작업 ID
- 문서명
- 사용자명
- 총 페이지 수
- 제출 시간
- 작업 상태

### 2단계. 에이전트 전송 구조 확정

각 Windows PC에 상주하는 PowerShell 에이전트가 Tailscale을 통해 I-PRINT API로 상태를 전달하는 구조를 우선 검토합니다.

브라우저가 각 PC를 직접 조회하는 구조보다 서버가 상태를 모으고 대시보드가 서버 API만 조회하는 구조가 관리와 보안에 유리합니다.

### 3단계. DB 스키마 설계

기존 운영 DB를 바로 변경하지 말고 아래 항목의 추가 필요성을 먼저 정리합니다.

- 프린터 식별자
- 장비 식별자
- 작업 ID
- 사용자명
- 문서명
- 총 페이지 수
- 출력 완료 페이지 수
- 제출 시각
- 시작 시각
- 종료 시각
- 오류 코드
- 오류 메시지
- 마지막 수신 시각

SQLite 스키마 변경 전에는 반드시 별도 백업을 생성합니다.

### 4단계. 실시간 표시 방식

초기에는 2~5초 간격 폴링으로 안정성을 확인하고, 동시 장비 수와 트래픽이 늘어날 때 Server-Sent Events 또는 WebSocket을 검토합니다.

### 5단계. 관리자 알림

오류가 발생할 때마다 반복 알림을 보내지 않도록 상태 전환 기준으로 설계합니다.

```text
정상 → 오류: 알림 1회
오류 유지: 중복 알림 억제
오류 → 정상: 복구 알림 1회
```

## 10. 다음 채팅 첫 작업

다음 채팅에서는 수정부터 시작하지 않습니다.

아래 순서로 현재 기준을 다시 확인합니다.

```text
1. 00_READ_FIRST.md 읽기
2. 최종 업무일지 읽기
3. 이 인수인계 문서 읽기
4. git status --short
5. git ls-files --others --exclude-standard
6. git log -1 --oneline
7. 로컬 HEAD와 origin/main 비교
8. 8897 /health 확인
9. 외부 HTTPS와 로그인 확인
10. Windows 프린터 상태 수집 가능 항목 조사
```

현재 정상 운영 화면과 인증, 도메인, SSL, 방화벽 기준을 보존하면서 Phase 2를 별도 단위로 진행합니다.
