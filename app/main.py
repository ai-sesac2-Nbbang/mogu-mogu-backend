import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.api_router import api_router, auth_router
from app.core.config import get_settings

app = FastAPI(
    title="minimal fastapi postgres template",
    version="6.1.0",
    description="https://github.com/rafsaf/minimal-fastapi-postgres-template",
    openapi_url="/openapi.json",
    docs_url="/",
)

app.include_router(auth_router)
app.include_router(api_router)

# 정적 파일 서빙 설정
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# 로그인 페이지
@app.get("/login")
async def read_login() -> HTMLResponse | dict[str, str]:
    static_file_path = os.path.join(static_dir, "index.html")
    if os.path.exists(static_file_path):
        # HTML 파일을 읽어서 환경 변수 주입
        with open(static_file_path, encoding="utf-8") as f:
            html_content = f.read()

        # 카카오 설정 주입
        settings = get_settings()
        rest_api_key = settings.kakao.rest_api_key.get_secret_value()
        redirect_uri = settings.kakao.redirect_uri
        html_content = html_content.replace("{{REST_API_KEY}}", rest_api_key)
        html_content = html_content.replace("{{REDIRECT_URI}}", redirect_uri)

        return HTMLResponse(content=html_content)
    return {"message": "Static files not found"}


# 사용자 정보 페이지
@app.get("/user")
async def read_user() -> FileResponse | dict[str, str]:
    static_file_path = os.path.join(static_dir, "user.html")
    if os.path.exists(static_file_path):
        return FileResponse(static_file_path)
    return {"message": "User page not found"}


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
