"""Request/Response logging middleware."""

import json
import time
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import get_settings

# 색상 없이 단순한 로깅

# 응답 시간 임계값 (밀리초)
SLOW_RESPONSE_THRESHOLD_MS = 1000  # 1초
MEDIUM_RESPONSE_THRESHOLD_MS = 500  # 0.5초


# 개발 환경 감지
def is_development() -> bool:
    """개발 환경인지 확인"""
    settings = get_settings()
    return settings.environment.lower() in [
        "development",
        "dev",
        "local",
    ]


class LoggingMiddleware(BaseHTTPMiddleware):
    """미들웨어: 모든 요청/응답을 상세히 로깅"""

    # 민감한 정보를 포함할 수 있는 헤더
    SENSITIVE_HEADERS = {
        "authorization",
        "cookie",
        "x-api-key",
        "x-auth-token",
    }

    # 민감한 정보를 포함할 수 있는 요청 필드
    SENSITIVE_BODY_FIELDS = {
        "password",
        "access_token",
        "refresh_token",
        "token",
        "secret",
        "email",
        "phone_number",
        "birth_date",
    }

    # 로깅할 최대 body 크기 (바이트)
    MAX_BODY_SIZE = 10000  # 10KB

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """요청/응답 로깅"""
        start_time = time.time()
        request_id = f"req-{int(time.time() * 1000)}"

        # 요청 정보 수집
        request_info = await self._get_request_info(request, request_id)

        # 요청 로그 출력
        self._log_request(request_info)

        # 응답 처리
        response = await call_next(request)

        # Response body 캡처 및 새로운 Response 생성
        response_body, new_response = await self._capture_response_body(response)

        # 처리 시간 계산
        process_time = time.time() - start_time

        # 응답 정보 수집 및 로그 출력
        response_info = self._get_response_info(
            new_response, process_time, response_body
        )
        self._log_response(request_info, response_info)

        # 처리 시간을 응답 헤더에 추가
        new_response.headers["X-Process-Time"] = f"{process_time:.4f}"
        new_response.headers["X-Request-ID"] = request_id

        return new_response

    async def _capture_response_body(self, response: Response) -> tuple[Any, Response]:
        """Response body 캡처 및 새로운 Response 생성"""
        try:
            # Response body를 바이트로 수집
            body_bytes = b""
            # body_iterator가 있는지 확인 후 사용
            if hasattr(response, "body_iterator"):
                async for chunk in response.body_iterator:
                    body_bytes += chunk
            else:
                # body_iterator가 없는 경우 빈 바이트 반환
                body_bytes = b""

            # 로깅용 body 문자열 생성 (truncation 적용)
            if len(body_bytes) > self.MAX_BODY_SIZE:
                truncated_bytes = body_bytes[: self.MAX_BODY_SIZE]
                body_str = (
                    truncated_bytes.decode("utf-8", errors="ignore") + "...[TRUNCATED]"
                )
            else:
                body_str = body_bytes.decode("utf-8", errors="ignore")

            # JSON 파싱 시도 (로깅용)
            try:
                body_json = json.loads(body_str)
                parsed_body = self._mask_sensitive_body(body_json)
            except json.JSONDecodeError:
                # JSON이 아닌 경우 문자열로 반환
                parsed_body = body_str

            # 새로운 Response 객체 생성 (body를 다시 설정)
            new_response = Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

            return parsed_body, new_response

        except Exception as e:
            # 에러 발생 시 원본 Response 반환
            return f"<Error capturing response body: {str(e)}>", response

    async def _get_request_info(
        self, request: Request, request_id: str
    ) -> dict[str, Any]:
        """요청 정보 수집"""
        # 헤더 수집 (민감한 정보 마스킹)
        headers = {
            key: self._mask_sensitive_header(key, value)
            for key, value in request.headers.items()
        }

        # 요청 본문 수집 (JSON인 경우만)
        body = None
        if request.method in ["POST", "PATCH", "PUT"]:
            try:
                body = await self._get_request_body(request)
            except Exception:
                body = "<Unable to parse body>"

        return {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": headers,
            "body": body,
            "client_host": request.client.host if request.client else None,
        }

    async def _get_request_body(self, request: Request) -> Any:
        """요청 본문 가져오기 및 민감한 정보 마스킹"""
        # Content-Type 확인
        content_type = request.headers.get("content-type", "")

        if "application/json" in content_type:
            try:
                body = await request.json()
                # 민감한 필드 마스킹
                return self._mask_sensitive_body(body)
            except Exception:
                return "<Invalid JSON>"
        elif "application/x-www-form-urlencoded" in content_type:
            try:
                form_data = await request.form()
                return self._mask_sensitive_body(dict(form_data))
            except Exception:
                return "<Unable to parse form data>"
        else:
            return f"<{content_type}>"

    def _get_response_info(
        self, response: Response, process_time: float, body: Any = None
    ) -> dict[str, Any]:
        """응답 정보 수집"""
        return {
            "status_code": response.status_code,
            "process_time": f"{process_time:.4f}s",
            "process_time_ms": int(process_time * 1000),
            "headers": dict(response.headers),
            "body": body,
        }

    def _mask_sensitive_header(self, key: str, value: str) -> str:
        """민감한 헤더 마스킹"""
        # 개발 환경에서는 마스킹하지 않음
        if is_development():
            return value

        if key.lower() in self.SENSITIVE_HEADERS:
            if key.lower() == "authorization" and value.startswith("Bearer "):
                # Bearer 토큰은 앞부분만 표시
                token = value.split(" ")[1]
                return f"Bearer {token[:10]}...{token[-4:]}"
            return "***MASKED***"
        return value

    def _mask_sensitive_body(self, body: Any) -> Any:
        """민감한 본문 필드 마스킹"""
        # 개발 환경에서는 마스킹하지 않음
        if is_development():
            return body

        if isinstance(body, dict):
            return {
                key: (
                    "***MASKED***"
                    if key.lower() in self.SENSITIVE_BODY_FIELDS
                    else self._mask_sensitive_body(value)
                )
                for key, value in body.items()
            }
        elif isinstance(body, list):
            return [self._mask_sensitive_body(item) for item in body]
        else:
            return body

    def _log_request(self, request_info: dict[str, Any]) -> None:
        # Request body가 있으면 출력
        if (
            request_info.get("body")
            and request_info["body"] != "<Unable to parse body>"
        ):
            body_str = json.dumps(request_info["body"], ensure_ascii=False, indent=2)
            print()
            print("INFO:     🟠 Request Body:")
            print(body_str)

    def _log_response(
        self, request_info: dict[str, Any], response_info: dict[str, Any]
    ) -> None:
        """응답 로그 출력 (FastAPI 스타일)"""
        process_time_ms = response_info["process_time_ms"]
        process_time = response_info["process_time"]

        # 응답 시간에 따른 이모지 결정
        if process_time_ms > SLOW_RESPONSE_THRESHOLD_MS:
            time_emoji = "⚠️"
        elif process_time_ms > MEDIUM_RESPONSE_THRESHOLD_MS:
            time_emoji = "⏱️"
        else:
            time_emoji = "✅"

        # OpenAPI 스펙이나 Swagger UI HTML은 로깅 제외
        request_path = request_info.get("path", "")
        if request_path in ["/openapi.json", "/", "/docs", "/redoc"]:
            return

        # Response body가 있으면 출력
        if response_info.get("body"):
            if isinstance(response_info["body"], str):
                body_str = response_info["body"]
            else:
                body_str = json.dumps(
                    response_info["body"], ensure_ascii=False, indent=2
                )

            print(
                f"INFO:     🔵 Response Body {time_emoji} {process_time} ({process_time_ms}ms):"
            )
            print(body_str)
