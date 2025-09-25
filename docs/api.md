# API 문서

모구모구 백엔드 API의 엔드포인트와 사용법을 안내합니다.

## 📋 목차

-   [API 개요](#api-개요)
-   [인증 관련 API](#인증-관련-api)
-   [사용자 관련 API](#사용자-관련-api)
-   [API 사용 예시](#api-사용-예시)
-   [응답 코드](#응답-코드)
-   [에러 처리](#에러-처리)

## API 개요

모구모구 API는 RESTful 설계 원칙을 따르며, JSON 형태로 데이터를 주고받습니다.

### 기본 정보

-   **Base URL**: `http://localhost:8000`
-   **Content-Type**: `application/json`
-   **인증 방식**: JWT Bearer Token

### API 문서 확인

서버가 실행 중일 때 다음 URL에서 인터랙티브 API 문서를 확인할 수 있습니다:

-   **Swagger UI**: http://localhost:8000/
-   **ReDoc**: http://localhost:8000/redoc

## 인증 관련 API

### 사용자 등록

새로운 사용자를 등록합니다.

**엔드포인트**: `POST /auth/register`

**요청 본문**:

```json
{
    "email": "user@example.com",
    "password": "your_password"
}
```

**응답** (201 Created):

```json
{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "create_time": "2024-01-01T00:00:00Z",
    "update_time": "2024-01-01T00:00:00Z"
}
```

### 로그인 (액세스 토큰 발급)

사용자 인증 후 액세스 토큰을 발급받습니다.

**엔드포인트**: `POST /auth/access-token`

**요청 본문** (form-data):

```
username: user@example.com
password: your_password
```

**응답** (200 OK):

```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_at": 1704067200,
    "refresh_token": "abc123def456...",
    "refresh_token_expires_at": 1706659200
}
```

### 토큰 갱신

리프레시 토큰을 사용하여 새로운 액세스 토큰을 발급받습니다.

**엔드포인트**: `POST /auth/refresh-token`

**요청 본문**:

```json
{
    "refresh_token": "abc123def456..."
}
```

**응답** (200 OK):

```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_at": 1704067200,
    "refresh_token": "xyz789uvw012...",
    "refresh_token_expires_at": 1706659200
}
```

## 사용자 관련 API

### 현재 사용자 정보 조회

현재 로그인한 사용자의 정보를 조회합니다.

**엔드포인트**: `GET /users/me`

**헤더**:

```
Authorization: Bearer <access_token>
```

**응답** (200 OK):

```json
{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "create_time": "2024-01-01T00:00:00Z",
    "update_time": "2024-01-01T00:00:00Z"
}
```

### 현재 사용자 삭제

현재 로그인한 사용자 계정을 삭제합니다.

**엔드포인트**: `DELETE /users/me`

**헤더**:

```
Authorization: Bearer <access_token>
```

**응답** (204 No Content)

### 비밀번호 재설정

현재 사용자의 비밀번호를 변경합니다.

**엔드포인트**: `POST /users/reset-password`

**헤더**:

```
Authorization: Bearer <access_token>
```

**요청 본문**:

```json
{
    "password": "new_password"
}
```

**응답** (204 No Content)

## API 사용 예시

### cURL을 사용한 예시

#### 1. 사용자 등록

```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "your_password"
  }'
```

#### 2. 로그인

```bash
curl -X POST "http://localhost:8000/auth/access-token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=your_password"
```

#### 3. 인증이 필요한 API 호출

```bash
curl -X GET "http://localhost:8000/users/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

#### 4. 토큰 갱신

```bash
curl -X POST "http://localhost:8000/auth/refresh-token" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "YOUR_REFRESH_TOKEN"
  }'
```

### JavaScript (fetch) 예시

```javascript
// 로그인
const loginResponse = await fetch("http://localhost:8000/auth/access-token", {
    method: "POST",
    headers: {
        "Content-Type": "application/x-www-form-urlencoded",
    },
    body: "username=user@example.com&password=your_password",
});

const loginData = await loginResponse.json();
const accessToken = loginData.access_token;

// 인증이 필요한 API 호출
const userResponse = await fetch("http://localhost:8000/users/me", {
    headers: {
        Authorization: `Bearer ${accessToken}`,
    },
});

const userData = await userResponse.json();
console.log(userData);
```

### Python (requests) 예시

```python
import requests

# 로그인
login_response = requests.post(
    'http://localhost:8000/auth/access-token',
    data={
        'username': 'user@example.com',
        'password': 'your_password'
    }
)

access_token = login_response.json()['access_token']

# 인증이 필요한 API 호출
user_response = requests.get(
    'http://localhost:8000/users/me',
    headers={'Authorization': f'Bearer {access_token}'}
)

user_data = user_response.json()
print(user_data)
```

## 응답 코드

### 성공 응답

-   **200 OK**: 요청 성공
-   **201 Created**: 리소스 생성 성공
-   **204 No Content**: 요청 성공, 응답 본문 없음

### 클라이언트 오류

-   **400 Bad Request**: 잘못된 요청
-   **401 Unauthorized**: 인증 실패
-   **404 Not Found**: 리소스를 찾을 수 없음

### 서버 오류

-   **500 Internal Server Error**: 서버 내부 오류

## 에러 처리

### 일반적인 에러 응답 형식

```json
{
    "detail": "에러 메시지"
}
```

### 인증 관련 에러

#### 401 Unauthorized

```json
{
    "detail": "Not authenticated"
}
```

#### 400 Bad Request (잘못된 비밀번호)

```json
{
    "detail": "Invalid email or password"
}
```

#### 400 Bad Request (이미 사용 중인 이메일)

```json
{
    "detail": "Email address already used"
}
```

### 토큰 관련 에러

#### 404 Not Found (리프레시 토큰 없음)

```json
{
    "detail": "Refresh token not found"
}
```

#### 400 Bad Request (토큰 만료)

```json
{
    "detail": "Refresh token expired"
}
```

#### 400 Bad Request (토큰 이미 사용됨)

```json
{
    "detail": "Refresh token already used"
}
```

### 에러 처리 모범 사례

1. **상태 코드 확인**: HTTP 상태 코드를 먼저 확인
2. **에러 메시지 파싱**: `detail` 필드에서 구체적인 에러 메시지 확인
3. **재시도 로직**: 네트워크 오류나 일시적 오류에 대한 재시도 구현
4. **토큰 갱신**: 401 에러 시 자동으로 토큰 갱신 시도

### 클라이언트 측 에러 처리 예시

```javascript
async function apiCall(url, options = {}) {
    try {
        const response = await fetch(url, options);

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "API 호출 실패");
        }

        return await response.json();
    } catch (error) {
        console.error("API 호출 오류:", error.message);
        throw error;
    }
}

// 사용 예시
try {
    const userData = await apiCall("http://localhost:8000/users/me", {
        headers: {
            Authorization: `Bearer ${accessToken}`,
        },
    });
    console.log("사용자 정보:", userData);
} catch (error) {
    console.error("사용자 정보 조회 실패:", error.message);
}
```

## 추가 정보

-   **토큰 만료 시간**: 액세스 토큰은 기본적으로 24시간, 리프레시 토큰은 28일
-   **비밀번호 정책**: 최소 8자 이상 권장
-   **CORS**: 개발 환경에서는 `http://localhost:3000` 허용
-   **Rate Limiting**: 현재 구현되지 않음 (필요시 추가 가능)

더 자세한 정보는 [개발 가이드](development.md)를 참조하세요.
