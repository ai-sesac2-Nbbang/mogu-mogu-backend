"""enable_postgis_for_wish_spots

Revision ID: 2cf693fb8e85
Revises: d1984a6691f7
Create Date: 2025-10-01 14:50:12.645403

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "2cf693fb8e85"
down_revision = "d1984a6691f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostGIS 확장 활성화
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def downgrade() -> None:
    # PostGIS 확장 제거 (주의: 다른 테이블에서 사용 중이면 실패할 수 있음)
    op.execute("DROP EXTENSION IF EXISTS postgis CASCADE")
