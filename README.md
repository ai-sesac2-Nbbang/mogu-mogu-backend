# 모구모구 백엔드 프로젝트

모구모구 백엔드는 FastAPI와 PostgreSQL을 사용한 현대적인 백엔드 API 서비스입니다.

## 🚀 빠른 시작

```bash
# 1. 의존성 설치
poetry install

# 2. 환경 변수 설정
cp .env.example .env
# .env 파일에서 카카오 로그인 설정을 수정하세요

# 3. 데이터베이스 실행
docker compose up -d

# 4. 마이그레이션 실행
poetry run alembic upgrade head

# 5. 서버 실행
poetry run uvicorn app.main:app --reload
```

서버가 실행되면:

-   **API 문서**: http://localhost:8000
-   **카카오 로그인 테스트**: http://localhost:8000/login

## 📚 문서

-   **[설치 및 설정 가이드](docs/setup.md)** - 프로젝트 설정 및 개발 환경 구성
-   **[개발 가이드](docs/development.md)** - 새로운 기능 추가 및 개발 방법
-   **[배포 가이드](docs/deployment.md)** - 프로덕션 배포 방법

## 🛠 기술 스택

-   **FastAPI**: 현대적이고 빠른 Python 웹 프레임워크
-   **PostgreSQL**: 강력한 오픈소스 관계형 데이터베이스
-   **SQLAlchemy 2.0**: 비동기 쿼리, 최고의 자동완성 지원
-   **Alembic**: 데이터베이스 마이그레이션 도구
-   **Poetry**: Python 의존성 관리 도구
-   **Docker**: 컨테이너화

## 📁 프로젝트 구조

```
backend/
├── app/                    # 메인 애플리케이션 코드
│   ├── api/               # API 관련 코드
│   ├── core/              # 핵심 설정 및 유틸리티
│   ├── schemas/           # Pydantic 스키마
│   └── tests/             # 테스트 코드
├── alembic/               # 데이터베이스 마이그레이션
├── docs/                  # 프로젝트 문서
└── docker-compose.yml     # Docker Compose 설정
```

## 🆘 문제 해결

자주 발생하는 문제들과 해결 방법은 [설치 및 설정 가이드](docs/setup.md#문제-해결)를 참조하세요.
