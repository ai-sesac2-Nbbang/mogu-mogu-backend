from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.api_router import api_router, auth_router
from app.core.config import get_settings
from app.core.logging_middleware import LoggingMiddleware

app = FastAPI(
    title="Mogu Mogu Backend",
    version="6.1.0",
    description="모두의 구매, '모구모구' - 이웃과 함께하는 AI 기반 공동구매 매칭 플랫폼",
    openapi_url="/openapi.json",
    docs_url="/",
)

app.include_router(auth_router)
app.include_router(api_router)


# 헬스 체크
@app.get("/health")
async def health() -> dict[str, str]:
    return {"message": "OK"}


app.add_middleware(LoggingMiddleware)

# Sets all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        str(origin).rstrip("/")
        for origin in get_settings().security.backend_cors_origins
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Guards against HTTP Host Header attacks
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=get_settings().security.allowed_hosts,
)
