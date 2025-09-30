from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import api_messages
from app.core import database_session
from app.core.security.jwt import verify_jwt_token
from app.models import User

# JWT Bearer 토큰 인증을 위한 스키마
bearer_scheme = HTTPBearer()


async def get_session() -> AsyncGenerator[AsyncSession]:
    async with database_session.get_async_session() as session:
        yield session


async def get_current_user(
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    session: AsyncSession = Depends(get_session),
) -> User:
    # token은 HTTPAuthorizationCredentials 객체이므로 .credentials로 실제 토큰 값에 접근
    token_payload = verify_jwt_token(token.credentials)

    user = await session.scalar(select(User).where(User.id == token_payload.sub))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=api_messages.JWT_ERROR_USER_REMOVED,
        )
    return user
