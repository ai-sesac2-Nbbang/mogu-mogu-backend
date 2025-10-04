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

### **1. 공통 함수 추출 원칙**

#### **함수명 규칙**

-   내부 함수: `_` prefix 사용
-   공개 함수: 일반적인 네이밍
-   동사 + 명사 형태

#### **추출 대상**

```python
# ✅ 데이터베이스 조회 중복
async def _get_mogu_post(post_id: str, session: AsyncSession) -> MoguPost:
    """모구 게시물을 조회합니다."""

# ✅ 응답 객체 생성 중복
def _build_user_response(user: User) -> UserResponse:
    """사용자 응답 객체를 생성합니다."""

# ✅ 권한 확인 중복
async def _check_post_permissions(post: MoguPost, user: User) -> None:
    """게시물 권한을 확인합니다."""

# ✅ 상태 검증 중복
async def _validate_post_status(post: MoguPost, allowed_statuses: list) -> None:
    """게시물 상태를 검증합니다."""
```

### **2. 중복 코드 제거 패턴**

#### **응답 객체 생성**

```python
# ❌ 중복 코드
def create_user_api():
    return UserResponse(
        user_id=user.id,
        email=user.email,
        nickname=user.nickname,
        # ... 20개 필드
    )

def update_user_api():
    return UserResponse(
        user_id=user.id,
        email=user.email,
        nickname=user.nickname,
        # ... 동일한 20개 필드
    )

# ✅ 공통 함수 추출
def _build_user_response(user: User) -> UserResponse:
    return UserResponse(
        user_id=user.id,
        email=user.email,
        nickname=user.nickname,
        # ... 20개 필드
    )

def create_user_api():
    return _build_user_response(user)

def update_user_api():
    return _build_user_response(user)
```

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

### **3. 에러 처리 표준화**

```python
# ✅ 일관된 에러 처리
async def _validate_user_permissions(user: User, required_status: str) -> None:
    if user.status != required_status:
        raise HTTPException(
            status_code=403,
            detail=f"권한이 없습니다. 현재 상태: {user.status}"
        )

async def _validate_post_exists(post_id: str, session: AsyncSession) -> MoguPost:
    post = await session.get(MoguPost, post_id)
    if not post:
        raise HTTPException(
            status_code=404,
            detail="게시물을 찾을 수 없습니다"
        )
    return post
```

---

## 📂 **파일별 리팩토링 계획**

### **Phase 1: 기본 API**

#### **auth.py**

-   **문제점**: 긴 함수, 리다이렉트 URL 생성 중복
-   **개선사항**:
    -   `_get_user_by_kakao_id()` 함수 추출
    -   `_extract_kakao_user_info()` 함수 추출
    -   `_create_new_user()` 함수 추출
    -   `_create_error_redirect()` 함수 추출
    -   `_create_success_redirect()` 함수 추출

#### **users.py**

-   **문제점**: 응답 객체 생성 중복, 온보딩 로직 중복
-   **개선사항**:
    -   `_build_user_response()` 함수 추출
    -   `_check_onboarding_completion()` 함수 추출
    -   DELETE API → 204 응답 적용

### **Phase 2: 핵심 API**

#### **mogu_posts.py**

-   **문제점**: 가장 복잡한 파일, 중복 코드 대량 존재
-   **개선사항**:
    -   `_get_mogu_post()` 함수 추출
    -   `_build_post_response()` 함수 추출
    -   `_validate_post_permissions()` 함수 추출
    -   `_validate_post_status()` 함수 추출
    -   응답 표준화 적용

#### **participations.py**

-   **문제점**: 일부 공통 함수 있으나 개선 필요
-   **개선사항**:
    -   기존 공통 함수 개선
    -   응답 표준화 적용
    -   에러 처리 표준화

### **Phase 3: 고도화**

#### **questions.py**

-   **문제점**: 이미 일부 리팩토링 완료, 추가 최적화 필요
-   **개선사항**:
    -   더 많은 공통 함수 추출
    -   응답 객체 생성 최적화

#### **공통 유틸리티 모듈**

-   **목표**: `app/api/common/` 디렉토리 생성
-   **내용**:
    -   `auth_utils.py`: 인증 관련 공통 함수
    -   `post_utils.py`: 게시물 관련 공통 함수
    -   `user_utils.py`: 사용자 관련 공통 함수
    -   `response_utils.py`: 응답 생성 공통 함수

---

## 📊 **리팩토링 진행 체크리스트**

### **각 파일별 체크리스트**

#### **✅ REST API 표준 준수**

-   [ ] DELETE API → 204 No Content 응답
-   [ ] 불필요한 message 래핑 제거
-   [ ] 데이터 직접 반환 원칙 적용
-   [ ] 일관된 에러 응답 구조

#### **✅ 코드 품질 개선**

-   [ ] 중복 코드 80% 이상 제거
-   [ ] 공통 함수 추출 (내부 함수 `_` prefix)
-   [ ] 타입 힌트 완성
-   [ ] 에러 처리 표준화

#### **✅ 성능 최적화**

-   [ ] N+1 쿼리 문제 해결
-   [ ] 불필요한 데이터베이스 조회 제거
-   [ ] 효율적인 데이터 로딩 (selectinload 등)

#### **✅ 테스트 가능성**

-   [ ] 의존성 주입 개선
-   [ ] 함수 단위 테스트 가능한 구조
-   [ ] 모킹 가능한 인터페이스

---

## 🚀 **실행 순서**

### **1단계: 파일별 개별 리팩토링**

```bash
# 각 파일별로 개별 커밋
git commit -m "refactor(auth): REST API 표준 적용 및 공통 함수 추출"
git commit -m "refactor(users): 응답 객체 생성 중복 제거"
git commit -m "refactor(mogu_posts): 대규모 중복 코드 제거"
git commit -m "refactor(participations): 기존 함수 개선 및 표준화"
git commit -m "refactor(questions): 추가 최적화 및 표준화"
```

### **2단계: 공통 모듈 생성**

```bash
# 공통 유틸리티 모듈 생성
mkdir -p app/api/common
# 각 유틸리티 파일 생성 및 공통 함수 이동
git commit -m "feat(common): 공통 유틸리티 모듈 생성"
```

### **3단계: 전체 테스트 및 검증**

```bash
# 테스트 실행
pytest
# 린트 검사
ruff check
# 타입 검사
mypy
git commit -m "test: 리팩토링 후 전체 테스트 검증"
```

---

## 📈 **예상 효과**

### **정량적 개선**

-   **코드 라인 수**: 30-40% 감소
-   **중복 코드**: 80% 이상 제거
-   **함수 복잡도**: 50% 이상 감소
-   **테스트 커버리지**: 20% 이상 향상

### **정성적 개선**

-   **유지보수성**: 크게 향상
-   **가독성**: 명확한 구조
-   **확장성**: 재사용 가능한 컴포넌트
-   **일관성**: 표준화된 API

---

## 🔍 **코드 리뷰 포인트**

### **리팩토링 후 검증 항목**

#### **1. 기능 보존**

-   [ ] 기존 API 동작 완전 보존
-   [ ] 에러 케이스 동일하게 처리
-   [ ] 성능 저하 없음

#### **2. 코드 품질**

-   [ ] 중복 코드 제거 확인
-   [ ] 공통 함수 적절한 추출
-   [ ] 타입 안정성 보장

#### **3. API 일관성**

-   [ ] REST API 표준 준수
-   [ ] 응답 구조 일관성
-   [ ] 에러 처리 표준화

#### **4. 테스트 가능성**

-   [ ] 단위 테스트 작성 가능
-   [ ] 모킹 가능한 구조
-   [ ] 의존성 주입 적절

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

---

## 🎯 **AI 리팩토링 가이드**

### **AI가 이 문서를 참고하여 리팩토링할 때**

1. **이 문서의 규칙을 철저히 따르기**
2. **각 Phase별 우선순위 준수**
3. **체크리스트를 통해 완성도 검증**
4. **기능 보존을 최우선으로 고려**
5. **개별 커밋으로 변경사항 추적**

### **리팩토링 시작 명령어**

```
"docs/api-refactoring-guide.md 문서를 참고하여 auth.py 리팩토링을 시작해줘"
```

이 문서를 통해 일관되고 체계적인 API 리팩토링이 가능합니다! 🚀
