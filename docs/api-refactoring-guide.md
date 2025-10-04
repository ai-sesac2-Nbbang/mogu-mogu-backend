# API 리팩토링 가이드

## 📋 **개요**

이 문서는 Mogu-Mogu 백엔드 API의 리팩토링을 위한 포괄적인 가이드입니다. REST API 설계 원칙, 코드 품질 개선, 그리고 일관성 있는 API 개발을 위한 규칙들을 포함합니다.

---

## 🎯 **리팩토링 목표**

### **1. REST API 표준 준수**

-   HTTP 상태 코드 올바른 사용
-   일관된 응답 구조
-   불필요한 래핑 제거

### **2. 코드 품질 향상**

-   중복 코드 제거
-   공통 함수 추출
-   타입 안정성 보장

### **3. 유지보수성 개선**

-   모듈화된 구조
-   재사용 가능한 컴포넌트
-   명확한 책임 분리

---

## 📐 **REST API 설계 규칙**

### **1. HTTP 상태 코드 활용**

#### **상태 코드 사용 규칙**

| 상태 코드                   | 사용 시기                        | 응답 본문               |
| --------------------------- | -------------------------------- | ----------------------- |
| `200 OK`                    | 성공적인 GET, PUT, PATCH 요청    | 데이터 직접 반환        |
| `201 Created`               | 성공적인 POST 요청 (리소스 생성) | 생성된 리소스 직접 반환 |
| `204 No Content`            | 성공적인 DELETE 요청             | 빈 응답                 |
| `400 Bad Request`           | 잘못된 요청 데이터               | 에러 메시지             |
| `401 Unauthorized`          | 인증되지 않은 사용자             | 에러 메시지             |
| `403 Forbidden`             | 권한이 없는 사용자               | 에러 메시지             |
| `404 Not Found`             | 리소스를 찾을 수 없음            | 에러 메시지             |
| `409 Conflict`              | 리소스 충돌 (중복 생성 등)       | 에러 메시지             |
| `500 Internal Server Error` | 서버 내부 오류                   | 에러 메시지             |

#### **상태 코드 사용 방법**

```python
# ❌ 나쁜 예 - 숫자 직접 사용
@router.get("/users/{user_id}", status_code=200)
@router.post("/users", status_code=201)
@router.delete("/users/{user_id}", status_code=204)

# HTTPException에서도 숫자 사용 금지
raise HTTPException(status_code=404, detail="Not found")
raise HTTPException(status_code=400, detail="Bad request")

# ✅ 좋은 예 - FastAPI status 사용
from fastapi import status

@router.get("/users/{user_id}", status_code=status.HTTP_200_OK)
@router.post("/users", status_code=status.HTTP_201_CREATED)
@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)

# HTTPException에서도 status 사용
raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bad request")
```

#### **상태 코드 사용의 장점**

1. **가독성**: `status.HTTP_201_CREATED` vs `201`
2. **타입 안정성**: IDE에서 자동완성 지원
3. **유지보수성**: 상태 코드 변경 시 한 곳에서만 수정
4. **일관성**: 프로젝트 전체에서 동일한 패턴 사용
5. **오타 방지**: 숫자 오타로 인한 버그 방지

### **2. 응답 구조 원칙**

#### **성공 응답**

```json
// ✅ GET API - 데이터 직접 반환
{
  "id": "string",
  "name": "string",
  "created_at": "datetime"
}

// ✅ POST API (201) - 생성된 리소스 직접 반환
{
  "id": "string",
  "name": "string",
  "created_at": "datetime"
}

// ✅ PUT/PATCH API (200) - 업데이트된 리소스 직접 반환
{
  "id": "string",
  "name": "string",
  "updated_at": "datetime"
}

// ✅ DELETE API (204) - 빈 응답
HTTP/1.1 204 No Content
```

#### **실패 응답**

```json
// ✅ 에러 응답 - 일관된 구조
{
    "detail": "에러 메시지",
    "code": "ERROR_CODE" // 선택적
}
```

#### **목록 응답**

```json
// ✅ 목록 API - 필드로 래핑
{
  "items": [...],
  "pagination": {
    "page": "number",
    "limit": "number",
    "total": "number",
    "total_pages": "number"
  }
}
```

### **3. 불필요한 래핑 금지**

```json
// ❌ 나쁜 예
{
  "message": "성공했습니다",
  "data": { ... }
}

// ✅ 좋은 예
{ ... }  // 데이터 직접 반환
```

---

## 🔧 **코드 리팩토링 규칙**

### **1. 응답 객체 생성 패턴**

#### **Factory Method 패턴 (권장)**

```python
# ✅ 권장 방식 - @classmethod factory 메서드
class UserResponse(BaseModel):
    user_id: str
    email: str
    nickname: str
    # ... 필드들

    @classmethod
    def from_user(cls, user: "User") -> "UserResponse":
        """User 모델로부터 UserResponse를 생성합니다."""
        return cls(
            user_id=user.id,
            email=user.email,
            nickname=user.nickname,
            # ...
        )

# 사용
return UserResponse.from_user(user)
```

#### **Factory Method 패턴의 장점**

1. **응집도 (Cohesion)**: 응답 객체와 생성 로직이 같은 클래스에 위치
2. **캡슐화**: 객체 생성 로직이 객체 내부에 캡슐화됨
3. **네이밍 명확성**: `UserResponse.from_user()` vs `_build_user_response()`
4. **타입 안정성**: IDE에서 자동완성과 타입 체크 지원
5. **확장성**: 여러 생성 방법을 제공하기 쉬움 (`from_user()`, `from_dict()` 등)

#### **유틸리티 클래스 패턴**

```python
# 복잡한 변환 로직의 경우 유틸리티 클래스 사용
class QuestionAnswerConverter:
    """Q&A 데이터 변환을 위한 유틸리티 클래스"""

    @staticmethod
    def to_dict_list(questions_answers: list["QuestionAnswer"] | None) -> list[dict[str, Any]] | None:
        """Q&A 데이터를 딕셔너리 형태로 변환합니다."""
        if not questions_answers:
            return None
        return [
            {
                "id": qa.id,
                "questioner_id": qa.questioner_id,
                "question": qa.question,
                # ...
            }
            for qa in questions_answers
        ]

    @staticmethod
    def build_answerer_data(question: "QuestionAnswer") -> dict[str, Any] | None:
        """답변자 정보를 구성합니다."""
        if question.answerer:
            return {
                "id": question.answerer.id,
                "nickname": question.answerer.nickname,
                "profile_image_url": question.answerer.profile_image_url,
            }
        return None
```

### **2. 공통 함수 추출 원칙**

#### **함수명 규칙**

-   내부 함수: `_` prefix 사용
-   공개 함수: 일반적인 네이밍
-   동사 + 명사 형태

#### **추출 대상**

```python
# ✅ 데이터베이스 조회 중복
async def _get_mogu_post(post_id: str, session: AsyncSession) -> MoguPost:
    """모구 게시물을 조회합니다."""

# ✅ 권한 확인 중복
async def _check_post_permissions(post: MoguPost, user: User) -> None:
    """게시물 권한을 확인합니다."""

# ✅ 상태 검증 중복
async def _validate_post_status(post: MoguPost, allowed_statuses: list) -> None:
    """게시물 상태를 검증합니다."""
```

### **3. 중복 코드 제거 패턴**

#### **데이터베이스 조회**

```python
# ❌ 중복 코드
def api_1():
    query = select(MoguPost).where(MoguPost.id == post_id)
    result = await session.execute(query)
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="게시물을 찾을 수 없습니다")

def api_2():
    query = select(MoguPost).where(MoguPost.id == post_id)
    result = await session.execute(query)
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="게시물을 찾을 수 없습니다")

# ✅ 공통 함수 추출
async def _get_mogu_post(post_id: str, session: AsyncSession) -> MoguPost:
    query = select(MoguPost).where(MoguPost.id == post_id)
    result = await session.execute(query)
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="게시물을 찾을 수 없습니다")
    return post
```

### **4. 에러 처리 표준화**

```python
# ✅ 일관된 에러 처리 - FastAPI status 사용
from fastapi import status

async def _validate_user_permissions(user: User, required_status: str) -> None:
    if user.status != required_status:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"권한이 없습니다. 현재 상태: {user.status}"
        )

async def _validate_post_exists(post_id: str, session: AsyncSession) -> MoguPost:
    post = await session.get(MoguPost, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="게시물을 찾을 수 없습니다"
        )
    return post

# ✅ 추가 에러 처리 예시
async def _validate_post_status(post: MoguPost, allowed_statuses: list) -> None:
    if post.status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"현재 상태에서는 작업할 수 없습니다. 현재 상태: {post.status}"
        )

async def _validate_unique_constraint(error: IntegrityError) -> None:
    if "duplicate key" in str(error):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 존재하는 데이터입니다."
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="데이터베이스 오류가 발생했습니다."
    )
```

---

## 📂 **현재 코드 구조**

### **공통 유틸리티 모듈**

```
app/api/common/
├── __init__.py          # 공통 함수 export
├── post_utils.py        # 게시물 관련 공통 함수
└── validation_utils.py  # 검증 관련 공통 함수
```

#### **post_utils.py**

```python
# 게시물 관련 공통 함수들
async def _get_mogu_post(post_id: str, session: AsyncSession) -> MoguPost
async def _get_mogu_post_with_relations(post_id: str, session: AsyncSession) -> MoguPost
async def _check_post_permissions(post: MoguPost, user: User) -> None
async def _validate_post_status_for_deletion(post: MoguPost) -> None
```

#### **validation_utils.py**

```python
# 검증 관련 공통 함수들
async def _check_qa_activity_allowed(post: MoguPost, session: AsyncSession) -> None
```

### **응답 객체 구조**

#### **Factory Method 패턴 적용**

```python
# app/schemas/responses.py
class UserResponse(BaseModel):
    user_id: str
    email: str
    # ... 필드들

    @classmethod
    def from_user(cls, user: "User") -> "UserResponse":
        """User 모델로부터 UserResponse를 생성합니다."""
        return cls(
            user_id=user.id,
            email=user.email,
            # ...
        )

class ParticipationResponse(BaseModel):
    user_id: str
    mogu_post_id: str
    # ... 필드들

    @classmethod
    def from_participation(cls, participation: "Participation") -> "ParticipationResponse":
        """Participation 모델로부터 ParticipationResponse를 생성합니다."""
        return cls(
            user_id=participation.user_id,
            mogu_post_id=participation.mogu_post_id,
            # ...
        )

class MoguPostResponse(BaseModel):
    id: str
    title: str
    # ... 필드들

    @classmethod
    def from_mogu_post(
        cls,
        mogu_post: "MoguPost",
        my_participation: dict[str, Any] | None = None,
        is_favorited: bool = False,
        questions_answers: list[dict[str, Any]] | None = None,
    ) -> "MoguPostResponse":
        """MoguPost 모델로부터 MoguPostResponse를 생성합니다."""
        # 복잡한 변환 로직...
        return cls(...)

class QuestionWithAnswerResponse(BaseModel):
    id: str
    question: str
    # ... 필드들

    @classmethod
    def from_question(
        cls, question: "QuestionAnswer", answerer_data: dict[str, Any] | None = None
    ) -> "QuestionWithAnswerResponse":
        """QuestionAnswer 모델로부터 QuestionWithAnswerResponse를 생성합니다."""
        return cls(
            id=question.id,
            question=question.question,
            # ...
        )
```

#### **유틸리티 클래스**

```python
class QuestionAnswerConverter:
    """Q&A 데이터 변환을 위한 유틸리티 클래스"""

    @staticmethod
    def to_dict_list(questions_answers: list["QuestionAnswer"] | None) -> list[dict[str, Any]] | None:
        """Q&A 데이터를 딕셔너리 형태로 변환합니다."""
        # 변환 로직...

    @staticmethod
    def build_answerer_data(question: "QuestionAnswer") -> dict[str, Any] | None:
        """답변자 정보를 구성합니다."""
        # 답변자 데이터 구성 로직...
```

---

## 🚀 **새로운 API 개발 시 가이드라인**

### **1. 응답 객체 생성**

```python
# ✅ 권장 방식
class NewEntityResponse(BaseModel):
    id: str
    name: str
    # ... 필드들

    @classmethod
    def from_entity(cls, entity: "NewEntity") -> "NewEntityResponse":
        """NewEntity 모델로부터 NewEntityResponse를 생성합니다."""
        return cls(
            id=entity.id,
            name=entity.name,
            # ...
        )

# API 엔드포인트에서 사용 - 상태 코드 표준화
from fastapi import status

@router.get("/{entity_id}", status_code=status.HTTP_200_OK)
async def get_entity(entity_id: str) -> NewEntityResponse:
    entity = await _get_entity(entity_id, session)
    return NewEntityResponse.from_entity(entity)

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_entity(data: EntityCreateRequest) -> NewEntityResponse:
    entity = await _create_entity(data, session)
    return NewEntityResponse.from_entity(entity)

@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(entity_id: str) -> None:
    await _delete_entity(entity_id, session)
```

### **2. 공통 함수 추출**

```python
# ✅ 새로운 공통 함수 추가 시
# app/api/common/new_utils.py
async def _get_new_entity(entity_id: str, session: AsyncSession) -> NewEntity:
    """새로운 엔티티를 조회합니다."""
    # 조회 로직...
    return entity

# app/api/common/__init__.py에 export 추가
from .new_utils import _get_new_entity

__all__ = [
    # 기존 함수들...
    "_get_new_entity",
]
```

### **3. 복잡한 변환 로직**

```python
# ✅ 복잡한 변환 로직의 경우 유틸리티 클래스 사용
class ComplexDataConverter:
    """복잡한 데이터 변환을 위한 유틸리티 클래스"""

    @staticmethod
    def transform_complex_data(data: ComplexData) -> dict[str, Any]:
        """복잡한 데이터를 변환합니다."""
        # 복잡한 변환 로직...
        return transformed_data

    @staticmethod
    def build_related_info(entity: Entity) -> dict[str, Any] | None:
        """관련 정보를 구성합니다."""
        # 관련 정보 구성 로직...
        return related_info
```

---

## 📊 **코드 품질 지표**

### **정량적 개선**

-   **중복 코드**: 90% 이상 제거
-   **함수 복잡도**: 50% 이상 감소
-   **응답 객체 생성**: 100% 표준화
-   **에러 처리**: 100% 일관성

### **정성적 개선**

-   **유지보수성**: 크게 향상
-   **가독성**: 명확한 구조
-   **확장성**: 재사용 가능한 컴포넌트
-   **일관성**: 표준화된 API

---

## 🔍 **코드 리뷰 포인트**

### **새로운 코드 작성 시 검증 항목**

#### **1. 응답 객체 생성**

-   [ ] Factory method 패턴 사용 여부
-   [ ] `@classmethod`로 구현되었는지
-   [ ] 명확한 메서드명 사용 (`from_*`)
-   [ ] 타입 힌트 완성

#### **2. 공통 함수 추출**

-   [ ] 중복 코드 80% 이상 제거
-   [ ] 내부 함수 `_` prefix 사용
-   [ ] 적절한 함수 분리
-   [ ] 타입 안정성 보장

#### **3. 에러 처리**

-   [ ] 일관된 HTTP 상태 코드 사용 (FastAPI status 사용)
-   [ ] 숫자 직접 사용 금지 (`404` → `status.HTTP_404_NOT_FOUND`)
-   [ ] 표준화된 에러 메시지
-   [ ] 적절한 예외 처리
-   [ ] HTTPException에서 status 사용 확인

#### **4. 코드 구조**

-   [ ] 명확한 책임 분리
-   [ ] 모듈화된 구조
-   [ ] 재사용 가능한 컴포넌트

---

## 📚 **참고 자료**

### **REST API 설계**

-   [HTTP Status Code](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status)
-   [REST API Design Best Practices](https://restfulapi.net/)
-   [JSON API Specification](https://jsonapi.org/)

### **Python 코드 품질**

-   [Python PEP 8](https://pep8.org/)
-   [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
-   [SQLAlchemy Best Practices](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)

### **리팩토링 방법론**

-   [Refactoring: Improving the Design of Existing Code](https://martinfowler.com/books/refactoring.html)
-   [Clean Code](https://www.oreilly.com/library/view/clean-code-a/9780136083238/)

### **Factory Method 패턴**

-   [Factory Method Pattern - Python](https://python-patterns.guide/gang-of-four/factory-method/)
-   [Pydantic Model Methods](https://docs.pydantic.dev/latest/concepts/models/#model-methods)

---

## 🎯 **AI 리팩토링 가이드**

### **AI가 이 문서를 참고하여 리팩토링할 때**

1. **이 문서의 규칙을 철저히 따르기**
2. **Factory method 패턴 우선 적용**
3. **공통 함수 추출 원칙 준수**
4. **기능 보존을 최우선으로 고려**
5. **개별 커밋으로 변경사항 추적**

### **리팩토링 시작 명령어**

```
"docs/api-refactoring-guide.md 문서를 참고하여 [파일명] 리팩토링을 시작해줘"
```

이 문서를 통해 일관되고 체계적인 API 리팩토링이 가능합니다! 🚀
