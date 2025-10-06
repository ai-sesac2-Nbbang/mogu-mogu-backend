# 설치 및 설정 가이드

모구모구 백엔드 프로젝트의 설치 및 개발 환경 설정 방법을 안내합니다.

## 📋 목차

-   [시스템 요구사항](#시스템-요구사항)
-   [Poetry 설치](#poetry-설치)
-   [프로젝트 설정](#프로젝트-설정)
-   [환경 변수 설정](#환경-변수-설정)
-   [개발 환경 실행](#개발-환경-실행)
-   [pre-commit 설정](#pre-commit-설정)
-   [문제 해결](#문제-해결)

## 시스템 요구사항

-   **Python**: 3.13 이상
-   **Docker**: 20.10 이상 (데이터베이스용)
-   **Git**: 2.0 이상

## Poetry 설치

Poetry는 Python 의존성 관리 도구입니다. 먼저 Poetry를 설치해야 합니다.

### Windows

```powershell
# PowerShell에서 실행
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

### macOS/Linux

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### 환경 변수 등록 (Windows)

Poetry 설치 후 환경 변수에 등록해야 합니다:

#### 방법 1: 자동 등록 (권장)

```powershell
# PowerShell을 관리자 권한으로 실행 후
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";$env:APPDATA\Python\Scripts", [EnvironmentVariableTarget]::User)
```

#### 방법 2: 수동 등록

1. **시작 메뉴**에서 "환경 변수" 검색
2. **"시스템 환경 변수 편집"** 클릭
3. **"환경 변수(N)..."** 버튼 클릭
4. **사용자 변수** 섹션에서 **"Path"** 선택 후 **"편집(I)..."** 클릭
5. **"새로 만들기(N)"** 클릭
6. 다음 경로 추가: `%APPDATA%\Python\Scripts`
7. **"확인"** 클릭하여 모든 창 닫기

### 설치 확인

새 터미널을 열고 다음 명령어로 확인:

```bash
poetry --version
```

## 프로젝트 설정

### 1. 저장소 클론

```bash
git clone https://github.com/ai-sesac2-Nbbang/mogu-mogu-backend.git
cd mogu-mogu/backend
```

### 2. 의존성 설치

```bash
# 의존성 설치
poetry install

# 가상환경 활성화 (Windows)
poetry shell

# 가상환경 활성화 (macOS/Linux)
source $(poetry env info --path)/bin/activate
```

### 3. 프로젝트 구조 확인

```
backend/
├── app/                          # 메인 애플리케이션 코드
│   ├── __init__.py
│   ├── main.py                   # FastAPI 애플리케이션 진입점
│   ├── models.py                 # SQLAlchemy 데이터베이스 모델
│   ├── api/                      # API 관련 코드
│   │   ├── __init__.py
│   │   ├── api_router.py         # API 라우터 설정
│   │   ├── deps.py               # 의존성 주입 함수들
│   │   ├── api_messages.py       # API 메시지 상수
│   │   └── endpoints/            # API 엔드포인트들
│   │       ├── auth.py           # 인증 관련 엔드포인트
│   │       └── users.py          # 사용자 관련 엔드포인트
│   ├── core/                     # 핵심 설정 및 유틸리티
│   │   ├── __init__.py
│   │   ├── config.py             # 애플리케이션 설정
│   │   ├── database_session.py  # 데이터베이스 세션 관리
│   │   └── security/             # 보안 관련 모듈
│   │       ├── jwt.py            # JWT 토큰 처리
│   │       └── password.py       # 비밀번호 해싱
│   ├── schemas/                  # Pydantic 스키마
│   │   ├── requests.py           # 요청 스키마
│   │   └── responses.py          # 응답 스키마
│   └── tests/                    # 테스트 코드
│       ├── conftest.py           # 테스트 설정
│       ├── test_auth/            # 인증 테스트
│       ├── test_core/            # 핵심 기능 테스트
│       └── test_users/           # 사용자 테스트
├── alembic/                      # 데이터베이스 마이그레이션
│   ├── env.py                    # Alembic 환경 설정
│   └── versions/                 # 마이그레이션 파일들
├── docs/                         # 프로젝트 문서
├── pyproject.toml                # Poetry 의존성 설정
├── docker-compose.yml            # Docker Compose 설정
├── Dockerfile                    # Docker 이미지 설정
├── alembic.ini                   # Alembic 설정
└── init.sh                       # 초기화 스크립트
```

## 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 [`.env.example`](https://github.com/ai-sesac2-Nbbang/mogu-mogu-backend/blob/main/.env.example)을 참고하여 내용을 추가하세요.

[프로젝트 환경 별 .env 파일 확인하기 (members only)](https://www.notion.so/do0ori/env-file-26d8ad3586848178b583f7a3faaaba57)

### 환경 변수 설명

-   **DATABASE\_\_\***: PostgreSQL 데이터베이스 연결 설정
-   **SECURITY\_\_JWT_SECRET_KEY**: JWT 토큰 서명용 비밀키 (반드시 변경하세요)
-   **SECURITY\_\_JWT_ACCESS_TOKEN_EXPIRE_SECS**: 액세스 토큰 만료 시간 (초)
-   **SECURITY\_\_REFRESH_TOKEN_EXPIRE_SECS**: 리프레시 토큰 만료 시간 (초)
-   **SECURITY\_\_PASSWORD_BCRYPT_ROUNDS**: 비밀번호 해싱 라운드 수
-   **SECURITY\_\_ALLOWED_HOSTS**: 허용된 호스트 목록
-   **SECURITY\_\_BACKEND_CORS_ORIGINS**: CORS 허용 오리진 목록

## 개발 환경 실행

### 1. PostgreSQL 데이터베이스 실행

Docker Compose를 사용하여 PostgreSQL을 실행합니다:

```bash
# 데이터베이스만 실행
docker compose up -d

# 로그 확인
docker compose logs -f postgres_db
```

### 2. 데이터베이스 마이그레이션 실행

```bash
# 마이그레이션 실행
poetry run alembic upgrade head
```

### 3. FastAPI 서버 실행

```bash
# 개발 서버 실행 (자동 재시작 포함)
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 서버 확인

서버가 실행되면 다음 URL에서 API 문서를 확인할 수 있습니다:

-   **Swagger UI**: http://localhost:8000/
-   **ReDoc**: http://localhost:8000/redoc

## pre-commit 설정

코드 품질 관리를 위한 pre-commit hooks를 설정합니다:

```bash
# pre-commit 설치
poetry run pre-commit install --install-hooks

# 모든 파일에 대해 실행
poetry run pre-commit run --all-files
```

### pre-commit이 수행하는 작업들

-   **ruff**: 코드 포맷팅 및 린팅
-   **mypy**: 타입 체킹
-   **기타**: import 정렬, 코드 품질 검사

## 문제 해결

### 자주 발생하는 문제들

#### 1. Poetry 설치 오류

**문제**: Poetry 설치가 실패하거나 명령어를 찾을 수 없음

**해결방법**:

```bash
# Python 3.13이 설치되어 있는지 확인
python --version

# PATH에 Poetry가 추가되었는지 확인
echo $PATH

# 수동으로 PATH 추가 (Windows)
# 환경 변수에서 PATH에 %APPDATA%\Python\Scripts 추가
```

#### 2. 데이터베이스 연결 오류

**문제**: 데이터베이스에 연결할 수 없음

**해결방법**:

```bash
# Docker 컨테이너 상태 확인
docker compose ps

# 데이터베이스 로그 확인
docker compose logs postgres_db

# .env 파일의 데이터베이스 설정 확인
cat .env | grep DATABASE
```

#### 3. 마이그레이션 오류

**문제**: Alembic 마이그레이션이 실패함

**해결방법**:

```bash
# 데이터베이스가 실행 중인지 확인
docker compose ps

# 마이그레이션 상태 확인
poetry run alembic current

# 마이그레이션 히스토리 확인
poetry run alembic history
```

#### 4. 포트 충돌

**문제**: 8000번 포트가 이미 사용 중

**해결방법**:

```bash
# 다른 포트로 실행
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# 또는 사용 중인 프로세스 종료
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:8000 | xargs kill -9
```

### 로그 확인

```bash
# 애플리케이션 로그 확인
poetry run uvicorn app.main:app --reload --log-level debug

# Docker 컨테이너 로그 확인
docker compose logs -f

# 특정 서비스 로그만 확인
docker compose logs -f postgres_db
```

### 추가 도움말

문제가 지속되면 다음을 확인하세요:

1. **Python 버전**: Python 3.13 이상인지 확인
2. **Docker 상태**: Docker가 실행 중인지 확인
3. **포트 사용**: 필요한 포트들이 사용 가능한지 확인
4. **권한 문제**: 파일 권한이나 관리자 권한이 필요한지 확인

더 자세한 도움이 필요하면 [개발 가이드](development.md)를 참조하세요.
