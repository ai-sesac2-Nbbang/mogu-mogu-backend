# 개발 가이드

모구모구 백엔드 프로젝트의 개발 방법과 새로운 기능 추가 방법을 안내합니다.

## 📋 목차

-   [프로젝트 소개](#프로젝트-소개)
-   [개발 환경 설정](#개발-환경-설정)
-   [데이터베이스 마이그레이션](#데이터베이스-마이그레이션)
-   [테스트](#테스트)
-   [새로운 기능 추가하기](#새로운-기능-추가하기)
-   [코드 품질 관리](#코드-품질-관리)

## 프로젝트 소개

모구모구는 [rafsaf/minimal-fastapi-postgres-template](https://github.com/rafsaf/minimal-fastapi-postgres-template)을 기반으로 하되, 더욱 현대적이고 실용적인 접근 방식을 채택했습니다. 이 템플릿은 [공식 FastAPI 템플릿](https://github.com/tiangolo/full-stack-fastapi-postgresql)을 기반으로 하되 최신 기술 스택과 개선된 구조를 제공합니다.

### 주요 개선사항

-   **SQLAlchemy 2.0 스타일**: `crud` 폴더 없이도 충분히 강력한 ORM 활용
-   **간소화된 구조**: `core` 폴더 재구성, `schemas` 파일 통합
-   **최신 기술 스택**: Python 3.13, 최신 라이브러리 버전 사용
-   **향상된 테스트**: 병렬 실행, 트랜잭션 롤백, 테스트 데이터베이스 자동 생성
-   **최소한의 User 모델**: 프로젝트에 맞게 확장 가능한 기본 구조

### 2024년 업데이트

템플릿이 현재 스타일과 지식에 맞게 업데이트되었으며, 다음 세 가지 핵심 원칙을 적용했습니다:

-   **병렬 테스트 실행**: CPU 코어 수에 따른 자동 병렬화로 속도 향상
-   **트랜잭션 롤백**: 각 테스트 후 자동 롤백으로 데이터 격리
-   **테스트 데이터베이스**: docker-compose.yml 대신 자동 생성된 테스트 DB 사용

## 개발 환경 설정

### 필수 도구

-   **Python 3.13+**: 최신 Python 버전
-   **Poetry**: 의존성 관리
-   **Docker**: 데이터베이스 실행용
-   **Git**: 버전 관리

### 개발 도구

-   **pre-commit**: 코드 품질 관리
-   **ruff**: 코드 포맷팅 및 린팅
-   **mypy**: 타입 체킹
-   **pytest**: 테스트 프레임워크

자세한 설치 방법은 [설치 및 설정 가이드](setup.md)를 참조하세요.

## 데이터베이스 마이그레이션

### 새 마이그레이션 생성

모델을 수정한 후 새로운 마이그레이션을 생성합니다:

```bash
# 자동 마이그레이션 생성
poetry run alembic revision --autogenerate -m "설명"

# 수동 마이그레이션 생성
poetry run alembic revision -m "설명"
```

### 마이그레이션 실행

```bash
# 최신 마이그레이션 적용
poetry run alembic upgrade head

# 특정 버전으로 마이그레이션
poetry run alembic upgrade <revision_id>

# 마이그레이션 되돌리기
poetry run alembic downgrade -1
```

### 마이그레이션 상태 확인

```bash
# 현재 마이그레이션 상태 확인
poetry run alembic current

# 마이그레이션 히스토리 확인
poetry run alembic history
```

## 테스트

### 테스트 실행

```bash
# 모든 테스트 실행
poetry run pytest

# 특정 테스트 파일 실행
poetry run pytest app/tests/test_auth/

# 커버리지와 함께 실행
poetry run pytest --cov=app --cov-report=html

# 병렬 실행
poetry run pytest -n auto
```

### 테스트 구조

-   `test_auth/`: 인증 관련 테스트
-   `test_core/`: 핵심 기능 테스트 (JWT, 비밀번호 해싱)
-   `test_users/`: 사용자 관련 테스트

### 테스트 작성 가이드

```python
# app/tests/test_example.py

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import User


async def test_example_endpoint(
    client: AsyncClient,
    default_user_headers: dict[str, str],
    default_user: User,
) -> None:
    """예시 테스트 함수"""
    response = await client.get(
        app.url_path_for("example_endpoint"),
        headers=default_user_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    result = response.json()
    assert result["user_id"] == default_user.user_id
```

## 새로운 기능 추가하기

### 단계별 예시: Pet 모델 구현

실제 예시로 Pet 모델을 추가하는 과정을 단계별로 설명합니다.

#### 1. SQLAlchemy 모델 추가

`app/models.py`에 Pet 모델을 추가합니다:

```python
# app/models.py

class Pet(Base):
    __tablename__ = "pet"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_account.user_id", ondelete="CASCADE"),
    )
    pet_name: Mapped[str] = mapped_column(String(50), nullable=False)
    user: Mapped["User"] = relationship()
```

**SQLAlchemy 2.0의 강력한 기능**:

-   `Mapped`와 `mapped_column`은 SQLAlchemy 2.0의 핵심 기능
-   최고의 자동완성 지원과 타입 안정성 제공
-   자세한 내용: [SQLAlchemy 2.0 문서](https://docs.sqlalchemy.org/en/20/changelog/whatsnew_20.html)

#### 2. Alembic 마이그레이션 생성 및 적용

```bash
# 마이그레이션 생성
poetry run alembic revision --autogenerate -m "create_pet_model"

# 마이그레이션 적용
poetry run alembic upgrade head
```

**Alembic의 장점**:

-   비동기 설정과 완벽 호환
-   `--autogenerate` 플래그로 자동 변경 감지
-   특정 컬럼 변경도 정확히 감지

#### 3. Pydantic 스키마 추가

`app/schemas/requests.py`와 `app/schemas/responses.py`에 스키마를 추가합니다:

```python
# app/schemas/requests.py

class PetCreateRequest(BaseRequest):
    pet_name: str
```

```python
# app/schemas/responses.py

class PetResponse(BaseResponse):
    id: int
    pet_name: str
    user_id: str
```

**스키마 구조**:

-   `requests.py`: 요청 데이터 검증
-   `responses.py`: 응답 데이터 형식 정의
-   `BaseRequest`, `BaseResponse`: 공통 필드 상속

#### 4. API 엔드포인트 구현

`app/api/endpoints/pets.py` 파일을 생성합니다:

```python
# app/api/endpoints/pets.py

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models import Pet, User
from app.schemas.requests import PetCreateRequest
from app.schemas.responses import PetResponse

router = APIRouter()


@router.post(
    "/create",
    response_model=PetResponse,
    status_code=status.HTTP_201_CREATED,
    description="새로운 펫을 생성합니다. 로그인한 사용자만 가능합니다.",
)
async def create_new_pet(
    data: PetCreateRequest,
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Pet:
    new_pet = Pet(user_id=current_user.user_id, pet_name=data.pet_name)

    session.add(new_pet)
    await session.commit()

    return new_pet


@router.get(
    "/me",
    response_model=list[PetResponse],
    status_code=status.HTTP_200_OK,
    description="현재 로그인한 사용자의 모든 펫을 조회합니다.",
)
async def get_all_my_pets(
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_user),
) -> list[Pet]:
    pets = await session.scalars(
        select(Pet).where(Pet.user_id == current_user.user_id).order_by(Pet.pet_name)
    )

    return list(pets.all())
```

#### 5. 라우터 등록

`app/api/api_router.py`에 새로운 라우터를 등록합니다:

```python
# app/api/api_router.py

from app.api.endpoints import auth, users, pets

api_router.include_router(pets.router, prefix="/pets", tags=["pets"])
```

#### 6. 테스트 작성

`app/tests/test_pets/test_pets.py` 파일을 생성합니다:

```python
# app/tests/test_pets/test_pets.py

from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import Pet, User


async def test_create_new_pet(
    client: AsyncClient, default_user_headers: dict[str, str], default_user: User
) -> None:
    response = await client.post(
        app.url_path_for("create_new_pet"),
        headers=default_user_headers,
        json={"pet_name": "멍멍이"},
    )
    assert response.status_code == status.HTTP_201_CREATED

    result = response.json()
    assert result["user_id"] == default_user.user_id
    assert result["pet_name"] == "멍멍이"


async def test_get_all_my_pets(
    client: AsyncClient,
    default_user_headers: dict[str, str],
    default_user: User,
    session: AsyncSession,
) -> None:
    pet1 = Pet(user_id=default_user.user_id, pet_name="펫_1")
    pet2 = Pet(user_id=default_user.user_id, pet_name="펫_2")

    session.add(pet1)
    session.add(pet2)
    await session.commit()

    response = await client.get(
        app.url_path_for("get_all_my_pets"),
        headers=default_user_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    assert response.json() == [
        {
            "user_id": pet1.user_id,
            "pet_name": pet1.pet_name,
            "id": pet1.id,
        },
        {
            "user_id": pet2.user_id,
            "pet_name": pet2.pet_name,
            "id": pet2.id,
        },
    ]
```

### 일반적인 기능 추가 가이드

#### 1. 새로운 모델 추가

`app/models.py`에 새로운 SQLAlchemy 모델을 추가합니다:

```python
class Post(Base):
    __tablename__ = "post"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    author_id: Mapped[str] = mapped_column(
        ForeignKey("user_account.user_id", ondelete="CASCADE")
    )
    author: Mapped["User"] = relationship()
```

#### 2. Pydantic 스키마 추가

`app/schemas/requests.py`와 `app/schemas/responses.py`에 스키마를 추가합니다:

```python
# requests.py
class PostCreateRequest(BaseModel):
    title: str
    content: str | None = None

# responses.py
class PostResponse(BaseModel):
    id: int
    title: str
    content: str | None
    author_id: str
    create_time: datetime
    update_time: datetime
```

#### 3. API 엔드포인트 추가

`app/api/endpoints/`에 새로운 라우터를 생성합니다:

```python
# app/api/endpoints/posts.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models import Post
from app.schemas.requests import PostCreateRequest
from app.schemas.responses import PostResponse

router = APIRouter()

@router.post("/", response_model=PostResponse)
async def create_post(
    post_data: PostCreateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(deps.get_session),
) -> Post:
    # 포스트 생성 로직
    pass
```

#### 4. 라우터 등록

`app/api/api_router.py`에 새로운 라우터를 등록합니다:

```python
from app.api.endpoints import auth, users, posts

api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
```

#### 5. 마이그레이션 생성 및 적용

```bash
# 마이그레이션 생성
poetry run alembic revision --autogenerate -m "Add posts table"

# 마이그레이션 적용
poetry run alembic upgrade head
```

## 코드 품질 관리

### pre-commit 설정

코드 품질 관리를 위한 pre-commit hooks를 설정합니다:

```bash
# pre-commit 설치
poetry run pre-commit install --install-hooks

# 모든 파일에 대해 실행
poetry run pre-commit run --all-files
```

### 코드 스타일 가이드

#### 1. Python 코드 스타일

-   **PEP 8**: Python 공식 스타일 가이드 준수
-   **ruff**: 자동 포맷팅 및 린팅
-   **mypy**: 타입 힌트 강제

#### 2. 함수 및 클래스 명명

```python
# 함수명: snake_case
async def create_new_user():
    pass

# 클래스명: PascalCase
class UserService:
    pass

# 상수: UPPER_SNAKE_CASE
MAX_RETRY_COUNT = 3
```

#### 3. 타입 힌트

```python
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

async def get_user_by_id(
    session: AsyncSession,
    user_id: str
) -> Optional[User]:
    """사용자 ID로 사용자 조회"""
    pass
```

#### 4. 문서화

```python
async def create_user(
    session: AsyncSession,
    email: str,
    password: str
) -> User:
    """
    새로운 사용자를 생성합니다.

    Args:
        session: 데이터베이스 세션
        email: 사용자 이메일
        password: 사용자 비밀번호

    Returns:
        생성된 사용자 객체

    Raises:
        HTTPException: 이메일이 이미 사용 중인 경우
    """
    pass
```

### 테스트 작성 가이드

#### 1. 테스트 함수 명명

```python
# test_<기능>_<시나리오>_<예상결과>
async def test_create_user_with_valid_data_returns_user():
    pass

async def test_create_user_with_existing_email_raises_exception():
    pass
```

#### 2. 테스트 구조

```python
async def test_example():
    # Arrange: 테스트 데이터 준비
    user_data = {"email": "test@example.com", "password": "password"}

    # Act: 테스트 실행
    response = await client.post("/auth/register", json=user_data)

    # Assert: 결과 검증
    assert response.status_code == 201
    assert response.json()["email"] == user_data["email"]
```

#### 3. 테스트 격리

-   각 테스트는 독립적으로 실행되어야 함
-   데이터베이스 트랜잭션 롤백으로 데이터 격리
-   테스트 간 의존성 없음

### 성능 최적화

#### 1. 데이터베이스 쿼리 최적화

```python
# N+1 문제 방지
users = await session.scalars(
    select(User).options(selectinload(User.posts))
)

# 인덱스 활용
posts = await session.scalars(
    select(Post).where(Post.author_id == user_id).order_by(Post.created_at.desc())
)
```

#### 2. 비동기 처리

```python
# 병렬 처리
async def process_multiple_users(user_ids: List[str]):
    tasks = [get_user_by_id(session, user_id) for user_id in user_ids]
    users = await asyncio.gather(*tasks)
    return users
```

### 디버깅 팁

#### 1. 로깅 활용

```python
import logging

logger = logging.getLogger(__name__)

async def create_user(session: AsyncSession, email: str):
    logger.info(f"Creating user with email: {email}")
    try:
        user = User(email=email)
        session.add(user)
        await session.commit()
        logger.info(f"User created successfully: {user.user_id}")
        return user
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        raise
```

#### 2. 개발 서버 디버깅

```bash
# 디버그 모드로 실행
poetry run uvicorn app.main:app --reload --log-level debug

# 특정 모듈 로그만 확인
poetry run uvicorn app.main:app --reload --log-level debug --log-config logging.conf
```

## 추가 학습 자료

-   [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
-   [SQLAlchemy 공식 문서](https://docs.sqlalchemy.org/)
-   [Alembic 공식 문서](https://alembic.sqlalchemy.org/)
-   [Poetry 공식 문서](https://python-poetry.org/docs/)
-   [Pydantic 공식 문서](https://pydantic-docs.helpmanual.io/)

더 자세한 정보는 [API 문서](api.md)와 [배포 가이드](deployment.md)를 참조하세요.
