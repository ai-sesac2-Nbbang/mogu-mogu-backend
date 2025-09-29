import pytest
from fastapi import status
from httpx import AsyncClient

from app.main import app
from app.tests.conftest import default_user_email, default_user_id


@pytest.mark.asyncio(loop_scope="session")
async def test_read_current_user_status_code(
    client: AsyncClient, default_user_headers: dict[str, str]
) -> None:
    response = await client.get(
        app.url_path_for("read_current_user"),
        headers=default_user_headers,
    )

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio(loop_scope="session")
async def test_read_current_user_response(
    client: AsyncClient, default_user_headers: dict[str, str]
) -> None:
    response = await client.get(
        app.url_path_for("read_current_user"),
        headers=default_user_headers,
    )

    response_data = response.json()
    assert response_data["user_id"] == default_user_id
    assert response_data["email"] == default_user_email
    assert "provider" in response_data
    assert "kakao_id" in response_data
    assert "kakao_connected_at" in response_data
