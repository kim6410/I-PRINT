# 00_READ_FIRST — I-PRINT 숭실대학교

이 문서는 `/home/bourne/I-print` 프로젝트 작업 전 가장 먼저 확인해야 하는 최상위 기준 문서입니다.

I-PRINT는 원격 PC와 프린터를 안전하게 관제하기 위한 독립 프로젝트입니다.
모든 작업 규칙은 I-PRINT의 운영 안정성, 실데이터 보호, 최소 수정, 검증 가능한 변경 이력을 기준으로 적용합니다.

## 0. I-PRINT 최상위 운영 원칙

1. 작업을 시작하기 전에 반드시 이 문서와 최신 업무일지를 먼저 읽습니다.
2. 현재 정상 작동 상태를 먼저 확인한 뒤 수정합니다.
3. 사용자가 요청하지 않은 기능이나 구조를 임의로 확대하지 않습니다.
4. 수정은 대상 파일·함수·문구만 최소 범위로 진행합니다.
5. 기존 코드를 통째로 덮어쓰거나 전체 파일을 재작성하지 않습니다.
6. 파괴적 명령, 강제 초기화, 무차별 삭제, 와일드카드 삭제를 사용하지 않습니다.
7. 운영 DB·로그·인증정보·에이전트 설정·실데이터를 Git에 포함하지 않습니다.
8. 위험도가 있는 수정 전에는 수정 대상 파일만 날짜·시간이 포함된 이름으로 별도 백업합니다.
9. 실제 장비 데이터와 테스트 슬롯 데이터를 혼동하지 않도록 명확히 구분합니다.
10. 기능을 수정한 뒤 문법·API·HTTP·서비스·브라우저 표시를 실제로 검증합니다.
11. 작업 결과는 업무일지에 남기고 Git 커밋과 원격 Push까지 완료합니다.
12. 작업 종료 시 미추적 파일이 1개라도 남아 있으면 완료로 판단하지 않습니다.
13. 로컬 `HEAD`, `origin/main`, 실제 원격 `main`이 동일한지 확인합니다.
14. 사용자가 명시적으로 승인하지 않은 대규모 리팩터링·폴더 이동·기능 제거는 금지합니다.
15. 문제가 발생하면 임의로 우회하지 말고 원인·영향 범위·복원 기준을 먼저 확인합니다.

이 원칙은 임시 작업 지시, 편의상 만든 스크립트, 자동화 도구의 기본 동작보다 우선합니다.

## 1. 프로젝트 위치

- 작업 루트: `/home/bourne/I-print`
- 대시보드: `http://192.168.0.32:8897`
- GitHub: `https://github.com/kim6410/I-PRINT`
- 기본 브랜치: `main`

## 2. 현재 실제 연결 장비

- 5800X
  - Tailscale: `100.117.206.9`
  - Windows 에이전트 포트: `8898`
  - CPU·온도·메모리·디스크·프린터 상태 실데이터
- Mac mini
  - Tailscale: `100.116.128.62`
  - macOS 에이전트 포트: `8898`
  - CPU·메모리·디스크·프린터 상태 실데이터

나머지 카드는 Tailscale 및 에이전트 설치 전 테스트 슬롯입니다.

## 3. 절대 보호 원칙

1. 기존 파일을 통째로 덮어쓰지 않는다.
2. 변경은 필요한 함수·블록·문구만 최소 범위로 적용한다.
3. 파일 삭제·이동·강제 초기화·와일드카드 삭제 명령을 사용하지 않는다.
4. SQLite 운영 DB와 캐시·임시 파일은 GitHub에 올리지 않는다.
5. 실제 데이터와 테스트 데이터를 화면에서 명확히 구분한다.
6. 모든 원격 장비 통신은 Tailscale IP를 우선 사용한다.
7. 작업 시작 전 현재 Git 상태와 서비스 상태를 먼저 확인한다.

## 4. 미추적 파일 금지 규칙

작업 종료 시 Git 작업 트리에 미추적 파일을 절대 남기지 않는다.

반드시 아래를 확인한다.

```bash
git status --short
```

출력에 `??`가 있으면 다음 중 하나로 처리한다.

- 소스·문서·설정 파일이면 검토 후 Git에 추가한다.
- DB·로그·캐시·백업·임시 파일이면 `.gitignore`에 정확한 경로 또는 패턴을 추가한다.
- 정체가 불분명한 파일은 임의 삭제하지 말고 생성 원인부터 확인한다.

작업 완료 기준은 다음과 같다.

```text
미추적 파일 0개
의도하지 않은 수정 파일 0개
커밋 누락 0개
로컬 main과 origin/main 일치
```

## 5. Git 작업 순서

작업 전:

```bash
cd /home/bourne/I-print
git status --short
git log -1 --oneline
git remote -v
```

작업 후:

```bash
git status --short
git diff --check
git add <검증된 파일만>
git commit -m "작업 내용을 구체적으로 기록"
git push origin main
git status --short
git rev-parse HEAD
git rev-parse origin/main
```

`git add .`는 미추적 파일을 잘못 포함할 수 있으므로 기본적으로 사용하지 않는다.

## 6. Git에 올리지 않는 파일

현재 `.gitignore` 기준으로 아래 파일은 추적하지 않는다.

- `printer_jobs.db`
- `*.db`, `*.sqlite`, `*.sqlite3`
- `__pycache__/`
- `*.pyc`
- `*.log`
- `*.bak*`
- 로컬 환경 파일과 임시 파일

새로운 운영 데이터 파일이 생기면 먼저 `.gitignore`에 추가한 뒤 작업을 계속한다.

## 7. 주요 파일

- `app.py` — FastAPI 서버, SQLite 조회 API, 장비 상태 프록시
- `index.html` — 대시보드 UI와 카드 렌더링, 5초 자동 갱신
- `README.md` — 프로젝트 소개
- `00_READ_FIRST.md` — 작업 안전 기준과 인수인계 기준
- `.gitignore` — 운영 데이터와 임시 파일 추적 방지

## 7-1. I-PRINT 작업 전 확인 순서

모든 작업은 아래 순서로 시작합니다.

```bash
cd /home/bourne/I-print
cat 00_READ_FIRST.md
find WORK_LOGS -maxdepth 1 -type f -name '*.md' -printf '%T@ %TY-%Tm-%Td %TH:%TM:%TS %f\n' 2>/dev/null | sort -nr | head -n 5
git status --short
git branch --show-current
git log -1 --oneline
git remote -v
systemctl status i-print-dashboard --no-pager 2>/dev/null || true
curl -fsS http://127.0.0.1:8897/health
```

최신 업무일지가 있으면 이 문서 다음으로 읽고, 현재 서비스·Git·API 상태가 정상인지 확인한 뒤 작업합니다.

## 7-2. 백업 원칙

I-PRINT에서는 Git과 작업 백업의 역할을 명확히 구분합니다.

- Git: 소스·문서·설정 변경 이력 관리
- `Backup/`: 위험 수정 전 대상 파일의 즉시 복원본
- 운영 DB: 별도 비공개 백업 대상
- 에이전트 설치 파일: 각 장비 또는 별도 비공개 보관 위치에서 관리

백업이 필요한 작업:

- 파일 삭제·이동·이름 변경
- 핵심 API 또는 데이터 구조 수정
- SQLite 스키마 변경
- 서비스 실행 설정 변경
- Tailscale 주소·에이전트 포트 변경
- 여러 파일을 동시에 수정하는 작업
- 실제 프린터 제어 명령 연결

권장 백업 이름:

```text
I_PRINT_WORKING_YYYYMMDD_HHMMSS_작업명_수정전
```

백업 파일은 프로젝트 루트에 흩어 놓지 않고 `Backup/` 하위에 보관하며 Git에는 포함하지 않습니다.

## 7-3. WORK_LOGS 운영 원칙

업무일지 위치:

```text
/home/bourne/I-print/WORK_LOGS
```

기능 수정·장비 연결·오류 해결·배포·DB 변경 작업이 끝나면 반드시 업무일지를 남깁니다.

업무일지에는 아래 내용을 포함합니다.

- 작업 일시와 목표
- 작업 전 상태
- 수정 파일과 수정 범위
- 새로 생성하거나 비활성화한 파일
- 백업 위치
- 실제 검증 결과
- Tailscale·에이전트·API·HTTP 상태
- SQLite 무결성 또는 조회 결과
- 남은 문제와 다음 작업 순서
- Git 커밋 해시
- 로컬·원격 커밋 일치 여부
- 미추적 파일 0개 확인 결과

진단용 임시 파일·출력 로그·테스트 JSON은 `WORK_LOGS/` 루트에 남기지 않고, 필요한 경우 `_TOOLS`, `_DIAGNOSTICS`, `_ARCHIVE` 하위에서만 관리하며 기본적으로 Git에서 제외합니다.

## 7-4. 파일 수정 원칙

1. 수정 전 원본 파일의 관련 블록을 먼저 읽습니다.
2. 대상 파일 전체를 재작성하지 않습니다.
3. 함수·CSS 블록·문구 단위로 최소 수정합니다.
4. 한 번에 너무 많은 파일을 수정하지 않습니다.
5. 임시 패치 파일과 복사본을 프로젝트 루트에 남기지 않습니다.
6. 운영 파일을 수정한 뒤 같은 이름의 `.bak`, `.old`, `.tmp` 파일을 루트에 방치하지 않습니다.
7. 기존 기능을 제거하거나 동작을 바꿀 때는 사용자 승인과 복원 기준을 먼저 확보합니다.
8. 자동 생성 도구가 만든 파일도 작업자가 직접 검토하고 추적 또는 제외를 결정합니다.

금지 명령과 방식:

```text
rm -rf
find ... -delete
truncate
와일드카드(*)를 사용한 삭제·이동·덮어쓰기
Set-Content를 이용한 기존 파일 전체 덮어쓰기
git clean
git reset --hard
확인 없는 git add .
```

## 7-5. 검증 단계

작업 완료는 화면이 보이는 것만으로 판단하지 않습니다.

최소 검증 항목:

- Python 문법 또는 모듈 로드
- JavaScript 문법
- HTML 응답과 HTTP 200
- `/health` 응답
- 5800X 상태 API
- Mac mini 상태 API
- Tailscale IP 통신
- 대시보드 5초 갱신
- 프린터 작업 게시판 검색·페이지네이션
- SQLite `integrity_check`
- 브라우저 실제 표시
- 서비스 재시작 후 복구
- 재부팅 후 에이전트 자동 실행 여부

실제 검증하지 못한 항목은 `정상`이라고 기록하지 않고 `미검증`으로 남깁니다.

## 7-6. Git 안전 규칙

I-PRINT에서 Git은 소스와 문서의 변경 이력을 관리하는 도구이며, 전체 시스템 백업을 대신하지 않습니다.

작업 시작 시:

```bash
git status --short
git ls-files --others --exclude-standard
git branch --show-current
git log -1 --oneline
```

커밋 전:

```bash
git status --short
git diff --check
git diff --stat -- <수정 경로>
git diff -- <수정 경로>
git add -- <검증된 파일 1> <검증된 파일 2>
git diff --cached --stat
git diff --cached
```

Push 후:

```bash
git fetch origin main
LOCAL=$(git rev-parse HEAD)
TRACKING=$(git rev-parse origin/main)
REMOTE=$(git ls-remote --heads origin main | awk '{print $1}')
printf 'LOCAL=%s\nTRACKING=%s\nREMOTE=%s\n' "$LOCAL" "$TRACKING" "$REMOTE"
git status --short
git ls-files --others --exclude-standard
```

`LOCAL`, `TRACKING`, `REMOTE`가 모두 같고, `git status --short`와 미추적 파일 조회 결과가 비어 있어야 작업이 끝난 것입니다.

## 7-7. 미추적 파일 0개 강제 원칙

새 파일이 생기면 작업이 끝나기 전에 반드시 아래 셋 중 하나로 분류합니다.

1. 실제 소스·문서·설정: 검증 후 명시적으로 `git add -- <경로>`
2. 운영 데이터·로그·캐시·백업: `.gitignore`에 정확한 규칙 추가
3. 불필요한 임시 산출물: 생성 경로와 용도를 확인한 뒤 안전하게 정리

미추적 파일을 단순히 숨기기 위해 광범위한 `.gitignore` 패턴을 추가하면 안 됩니다.

특히 다음 파일을 프로젝트 루트에 남기지 않습니다.

- 임시 Python·PowerShell·JavaScript 패치 파일
- 테스트 응답 JSON
- 화면 캡처
- 다운로드 압축파일
- `.bak`, `.old`, `.tmp`, `.copy`
- DB 복제본
- 로그 덤프
- 인증키 또는 토큰 파일

작업 종료 보고에는 반드시 다음 문장을 포함합니다.

```text
미추적 파일 0개 확인 완료
```

## 8. 현재 화면 기준

- 메인 제목: `I-PRINT 숭실대학교`
- 실제 연결 카드: 5800X, Mac mini
- 학생회관 카드: 학생회관 01~06
- 건물별 프린터 테스트 카드: 19개
- 전체 카드 수: 27개
- PC 화면: 한 줄 3개 카드
- 장비 상태 갱신: 5초
- 프린터 작업 게시판 갱신: 5초

## 9. 다음 개발 우선순위

1. 상단 통계 숫자를 카드 데이터 기준 자동 계산으로 전환
2. 학생회관 01~06에 Tailscale과 Windows 에이전트 설치
3. 건물별 프린터 PC 연결 및 실데이터 수집
4. 실제 `Reset Print Queue` 명령 API 연결
5. 프린터 작업 이력을 SQLite에 자동 기록
6. 실제 물리 프린터와 가상 프린터 구분

## 10. 작업 종료 보고 기준

작업 종료 시 아래 내용을 반드시 남긴다.

- 수정한 파일
- 실제 검증 결과
- 서비스 상태
- Git 커밋 해시
- origin/main 일치 여부
- 미추적 파일 0개 확인 여부

이 문서의 규칙이 다른 임시 지시보다 우선합니다.
