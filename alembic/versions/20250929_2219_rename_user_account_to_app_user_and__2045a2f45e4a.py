"""rename user_account to app_user and user_id to id

Revision ID: 2045a2f45e4a
Revises: abc123def456
Create Date: 2025-09-29 22:19:29.997051

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "2045a2f45e4a"
down_revision = "abc123def456"
branch_labels = None
depends_on = None


def upgrade():
    # 테이블명 변경: user_account -> app_user
    op.rename_table("user_account", "app_user")

    # 컬럼명 변경: user_id -> id
    op.alter_column("app_user", "user_id", new_column_name="id")

    # 외래키 참조 업데이트
    op.drop_constraint(
        "refresh_token_user_id_fkey", "refresh_token", type_="foreignkey"
    )
    op.create_foreign_key(
        "refresh_token_user_id_fkey",
        "refresh_token",
        "app_user",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    # 외래키 제거
    op.drop_constraint(
        "refresh_token_user_id_fkey", "refresh_token", type_="foreignkey"
    )
    op.create_foreign_key(
        "refresh_token_user_id_fkey",
        "refresh_token",
        "user_account",
        ["user_id"],
        ["user_id"],
        ondelete="CASCADE",
    )

    # 컬럼명 되돌리기: id -> user_id
    op.alter_column("app_user", "id", new_column_name="user_id")

    # 테이블명 되돌리기: app_user -> user_account
    op.rename_table("app_user", "user_account")
