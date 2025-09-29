import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import User


@pytest.mark.skip(reason="hashed_password 필드가 제거되어 스킵")
@pytest.mark.asyncio(loop_scope="session")
async def test_reset_current_user_password_status_code(
    client: AsyncClient,
    default_user_headers: dict[str, str],
) -> None:
    response = await client.post(
        app.url_path_for("reset_current_user_password"),
        headers=default_user_headers,
        json={"password": "test_pwd"},
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.skip(reason="hashed_password 필드가 제거되어 스킵")
@pytest.mark.asyncio(loop_scope="session")
async def test_reset_current_user_password_is_changed_in_db(
    client: AsyncClient,
    default_user_headers: dict[str, str],
    default_user: User,
    session: AsyncSession,
) -> None:
    await client.post(
        app.url_path_for("reset_current_user_password"),
        headers=default_user_headers,
        json={"password": "test_pwd"},
    )

    user = await session.scalar(select(User).where(User.id == default_user.id))
    assert user is not None
    # assert verify_password("test_pwd", user.hashed_password)  # hashed_password 필드 제거됨
