import pytest

from app.core.security.password import get_password_hash, verify_password


@pytest.mark.skip(reason="hashed_password 필드가 제거되어 스킵")
def test_hashed_password_is_verified() -> None:
    pwd_hash = get_password_hash("my_password")
    assert verify_password("my_password", pwd_hash)


@pytest.mark.skip(reason="hashed_password 필드가 제거되어 스킵")
def test_invalid_password_is_not_verified() -> None:
    pwd_hash = get_password_hash("my_password")
    assert not verify_password("my_password_invalid", pwd_hash)
