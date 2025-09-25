# 배포 가이드

모구모구 백엔드 프로젝트의 프로덕션 배포 방법을 안내합니다.

## 📋 목차

-   [배포 전략](#배포-전략)
-   [Docker 배포](#docker-배포)
-   [보안 설정](#보안-설정)
-   [환경 변수 설정](#환경-변수-설정)
-   [모니터링](#모니터링)
-   [백업 및 복구](#백업-및-복구)

## 배포 전략

모구모구 백엔드는 **Docker 컨테이너**를 통한 배포를 기본으로 합니다. Uvicorn 웹서버가 포함된 Dockerfile을 제공하여 간단하고 효율적인 배포가 가능합니다.

### 배포 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │────│   FastAPI App   │────│   PostgreSQL    │
│   (Nginx)       │    │   (Docker)      │    │   (Docker)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 권장 배포 환경

-   **로드 밸런서**: Nginx, HAProxy
-   **웹서버**: Uvicorn (기본), Nginx Unit, Daphne, Hypercorn
-   **데이터베이스**: PostgreSQL 16+
-   **컨테이너**: Docker, Docker Compose
-   **오케스트레이션**: Kubernetes (선택사항)

## Docker 배포

### 1. Docker 이미지 빌드

```bash
# 프로덕션용 이미지 빌드
docker build -t mogu-mogu-backend:latest .

# 특정 태그로 빌드
docker build -t mogu-mogu-backend:v1.0.0 .
```

### 2. Docker Compose를 사용한 배포

#### 개발 환경

```yaml
# docker-compose.yml
version: "3.8"

services:
    postgres_db:
        restart: unless-stopped
        image: postgres:17
        volumes:
            - postgres_db:/var/lib/postgresql/data
        environment:
            - POSTGRES_DB=${DATABASE__DB}
            - POSTGRES_USER=${DATABASE__USERNAME}
            - POSTGRES_PASSWORD=${DATABASE__PASSWORD}
        env_file:
            - .env
        ports:
            - "${DATABASE__PORT}:5432"

    app:
        build: .
        restart: unless-stopped
        ports:
            - "8000:8000"
        environment:
            - DATABASE__HOSTNAME=postgres_db
        env_file:
            - .env
        depends_on:
            - postgres_db

volumes:
    postgres_db:
```

#### 프로덕션 환경

```yaml
# docker-compose.prod.yml
version: "3.8"

services:
    postgres_db:
        restart: unless-stopped
        image: postgres:17
        volumes:
            - postgres_db:/var/lib/postgresql/data
        environment:
            - POSTGRES_DB=${DATABASE__DB}
            - POSTGRES_USER=${DATABASE__USERNAME}
            - POSTGRES_PASSWORD=${DATABASE__PASSWORD}
        env_file:
            - .env.prod
        networks:
            - app-network

    app:
        image: mogu-mogu-backend:latest
        restart: unless-stopped
        ports:
            - "8000:8000"
        environment:
            - DATABASE__HOSTNAME=postgres_db
        env_file:
            - .env.prod
        depends_on:
            - postgres_db
        networks:
            - app-network

    nginx:
        image: nginx:alpine
        restart: unless-stopped
        ports:
            - "80:80"
            - "443:443"
        volumes:
            - ./nginx.conf:/etc/nginx/nginx.conf
            - ./ssl:/etc/nginx/ssl
        depends_on:
            - app
        networks:
            - app-network

volumes:
    postgres_db:

networks:
    app-network:
        driver: bridge
```

### 3. 배포 실행

```bash
# 프로덕션 환경 배포
docker compose -f docker-compose.prod.yml up -d

# 로그 확인
docker compose -f docker-compose.prod.yml logs -f

# 서비스 상태 확인
docker compose -f docker-compose.prod.yml ps
```

## 보안 설정

### 1. CORS (Cross-Origin Resource Sharing)

프로덕션 환경에서는 CORS 설정을 엄격하게 관리해야 합니다.

```python
# app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://yourdomain.com",
        "https://www.yourdomain.com",
        "https://api.yourdomain.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

**환경별 CORS 설정**:

-   **개발**: `http://localhost:3000`
-   **스테이징**: `https://staging.yourdomain.com`
-   **프로덕션**: `https://yourdomain.com`

### 2. Allowed Hosts

HTTP Host Header 공격을 방지하기 위해 허용된 호스트를 설정합니다.

```python
# app/main.py
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "yourdomain.com",
        "www.yourdomain.com",
        "api.yourdomain.com"
    ],
)
```

### 3. HTTPS 설정

Nginx를 통한 HTTPS 설정:

```nginx
# nginx.conf
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location / {
        proxy_pass http://app:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 4. 보안 헤더

```python
# app/main.py
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

# HTTPS 리다이렉트 (프로덕션에서만)
if get_settings().environment == "production":
    app.add_middleware(HTTPSRedirectMiddleware)

# 보안 헤더 추가
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response
```

## 환경 변수 설정

### 프로덕션 환경 변수

`.env.prod` 파일을 생성하고 다음 내용을 추가하세요:

```env
# 환경 설정
ENVIRONMENT=production
LOG_LEVEL=WARNING

# 데이터베이스 설정
DATABASE__HOSTNAME=postgres_db
DATABASE__USERNAME=postgres
DATABASE__PASSWORD=your_strong_password_here
DATABASE__PORT=5432
DATABASE__DB=mogu_mogu_prod

# 보안 설정
SECURITY__JWT_SECRET_KEY=your_very_strong_secret_key_here
SECURITY__JWT_ACCESS_TOKEN_EXPIRE_SECS=3600
SECURITY__REFRESH_TOKEN_EXPIRE_SECS=604800
SECURITY__PASSWORD_BCRYPT_ROUNDS=14
SECURITY__ALLOWED_HOSTS=["yourdomain.com", "www.yourdomain.com"]
SECURITY__BACKEND_CORS_ORIGINS=["https://yourdomain.com"]

# Redis 설정 (선택사항)
REDIS__HOST=redis
REDIS__PORT=6379
REDIS__DB=0
```

### 환경 변수 보안

```bash
# 환경 변수 파일 권한 설정
chmod 600 .env.prod

# Docker 시크릿 사용 (Docker Swarm)
echo "your_strong_password" | docker secret create db_password -
```

## 모니터링

### 1. 로깅 설정

```python
# app/core/config.py
import logging
from pythonjsonlogger import jsonlogger

def setup_logging():
    logHandler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter()
    logHandler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(logHandler)
    logger.setLevel(logging.INFO)
```

### 2. 헬스 체크

```python
# app/api/endpoints/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps

router = APIRouter()

@router.get("/health")
async def health_check(session: AsyncSession = Depends(deps.get_session)):
    """헬스 체크 엔드포인트"""
    try:
        # 데이터베이스 연결 확인
        await session.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

### 3. 메트릭 수집

```python
# app/middleware/metrics.py
import time
from fastapi import Request

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    # 메트릭 수집 (Prometheus, DataDog 등)
    logger.info({
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "process_time": process_time
    })

    return response
```

### 4. 모니터링 도구

#### Prometheus + Grafana

```yaml
# docker-compose.monitoring.yml
version: "3.8"

services:
    prometheus:
        image: prom/prometheus
        ports:
            - "9090:9090"
        volumes:
            - ./prometheus.yml:/etc/prometheus/prometheus.yml

    grafana:
        image: grafana/grafana
        ports:
            - "3000:3000"
        environment:
            - GF_SECURITY_ADMIN_PASSWORD=admin
```

#### ELK Stack

```yaml
# docker-compose.logging.yml
version: "3.8"

services:
    elasticsearch:
        image: elasticsearch:8.0.0
        environment:
            - discovery.type=single-node

    logstash:
        image: logstash:8.0.0
        volumes:
            - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf

    kibana:
        image: kibana:8.0.0
        ports:
            - "5601:5601"
```

## 백업 및 복구

### 1. 데이터베이스 백업

```bash
# PostgreSQL 백업
docker exec postgres_db pg_dump -U postgres mogu_mogu_prod > backup_$(date +%Y%m%d_%H%M%S).sql

# 압축 백업
docker exec postgres_db pg_dump -U postgres mogu_mogu_prod | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

### 2. 자동 백업 스크립트

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups"
DB_NAME="mogu_mogu_prod"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$DATE.sql.gz"

# 백업 디렉토리 생성
mkdir -p $BACKUP_DIR

# 데이터베이스 백업
docker exec postgres_db pg_dump -U postgres $DB_NAME | gzip > $BACKUP_FILE

# 7일 이상 된 백업 파일 삭제
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE"
```

### 3. 복구

```bash
# 백업에서 복구
gunzip -c backup_20240101_120000.sql.gz | docker exec -i postgres_db psql -U postgres mogu_mogu_prod

# 특정 시점 복구 (WAL 아카이빙 사용)
docker exec postgres_db pg_basebackup -D /var/lib/postgresql/data -Ft -z -P
```

## 성능 최적화

### 1. 데이터베이스 최적화

```sql
-- 인덱스 생성
CREATE INDEX idx_user_email ON user_account(email);
CREATE INDEX idx_refresh_token_token ON refresh_token(refresh_token);
CREATE INDEX idx_refresh_token_exp ON refresh_token(exp);

-- 쿼리 최적화
EXPLAIN ANALYZE SELECT * FROM user_account WHERE email = 'user@example.com';
```

### 2. 애플리케이션 최적화

```python
# 연결 풀 설정
from sqlalchemy.pool import QueuePool

engine = create_async_engine(
    database_url,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True
)
```

### 3. 캐싱

```python
# Redis 캐싱
import redis
import json

redis_client = redis.Redis(host='redis', port=6379, db=0)

async def get_cached_user(user_id: str):
    cached = redis_client.get(f"user:{user_id}")
    if cached:
        return json.loads(cached)
    return None

async def cache_user(user_id: str, user_data: dict):
    redis_client.setex(f"user:{user_id}", 3600, json.dumps(user_data))
```

## 배포 자동화

### 1. GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
    push:
        branches: [main]

jobs:
    deploy:
        runs-on: ubuntu-latest
        steps:
            - uses: actions/checkout@v2

            - name: Build Docker image
              run: docker build -t mogu-mogu-backend:${{ github.sha }} .

            - name: Deploy to server
              run: |
                  docker tag mogu-mogu-backend:${{ github.sha }} your-registry/mogu-mogu-backend:latest
                  docker push your-registry/mogu-mogu-backend:latest

                  # 서버에서 배포 실행
                  ssh user@your-server "docker pull your-registry/mogu-mogu-backend:latest && docker compose -f docker-compose.prod.yml up -d"
```

### 2. Blue-Green 배포

```bash
# Blue-Green 배포 스크립트
#!/bin/bash

# Blue 환경에서 Green으로 전환
docker compose -f docker-compose.prod.yml up -d --scale app=2
docker compose -f docker-compose.prod.yml stop app_old
docker compose -f docker-compose.prod.yml rm -f app_old
```

## 문제 해결

### 1. 일반적인 배포 문제

#### 포트 충돌

```bash
# 사용 중인 포트 확인
netstat -tulpn | grep :8000

# 프로세스 종료
kill -9 $(lsof -ti:8000)
```

#### 메모리 부족

```bash
# Docker 메모리 제한 설정
docker run -m 512m mogu-mogu-backend:latest
```

#### 디스크 공간 부족

```bash
# Docker 정리
docker system prune -a
docker volume prune
```

### 2. 로그 분석

```bash
# 애플리케이션 로그
docker logs -f mogu-mogu-backend

# 데이터베이스 로그
docker logs -f postgres_db

# Nginx 로그
docker logs -f nginx
```

### 3. 성능 모니터링

```bash
# 컨테이너 리소스 사용량
docker stats

# 데이터베이스 연결 수
docker exec postgres_db psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"
```

## 추가 정보

-   **로드 밸런싱**: Nginx, HAProxy 설정
-   **SSL 인증서**: Let's Encrypt, Cloudflare
-   **CDN**: CloudFront, Cloudflare
-   **데이터베이스**: PostgreSQL 클러스터링
-   **캐싱**: Redis, Memcached

더 자세한 정보는 [개발 가이드](development.md)를 참조하세요.
