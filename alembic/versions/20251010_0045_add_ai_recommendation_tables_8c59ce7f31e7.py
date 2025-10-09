"""add_ai_recommendation_tables

Revision ID: 8c59ce7f31e7
Revises: 0833c664cbb3
Create Date: 2025-10-10 00:45:48.381721

AI 추천 시스템을 위한 테이블 및 뷰 생성:
- mv_host_reputation: 모구장 평판 머티리얼라이즈드 뷰
- item_item_sim: 아이템-아이템 유사도 캐시 테이블
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "8c59ce7f31e7"
down_revision = "0833c664cbb3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) 모구장 평판 머티리얼라이즈드 뷰
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_host_reputation AS
        SELECT
            reviewee_id,
            AVG(stars)::double precision AS avg_stars,
            COUNT(*) AS review_count
        FROM rating
        GROUP BY reviewee_id
        """
    )

    # 유니크 인덱스 (CONCURRENTLY 갱신을 위한 행 식별 보장)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_host_reputation_reviewee
        ON mv_host_reputation (reviewee_id)
        """
    )

    # 보조 인덱스 (조인 최적화)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_mv_host_reputation_reviewee
        ON mv_host_reputation (reviewee_id)
        """
    )

    # 최초 1회 갱신
    op.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_host_reputation")

    # 2) 아이템-아이템 유사도 캐시 테이블
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS item_item_sim (
            src_post_id        uuid NOT NULL,
            neigh_post_id      uuid NOT NULL,
            sim                double precision NOT NULL,
            common_user_count  int NOT NULL,
            updated_at         timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (src_post_id, neigh_post_id)
        )
        """
    )

    # 인덱스
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_item_item_sim_src
        ON item_item_sim (src_post_id)
        """
    )


def downgrade() -> None:
    # 역순으로 제거
    op.execute("DROP INDEX IF EXISTS idx_item_item_sim_src")
    op.execute("DROP TABLE IF EXISTS item_item_sim")

    op.execute("DROP INDEX IF EXISTS idx_mv_host_reputation_reviewee")
    op.execute("DROP INDEX IF EXISTS ux_mv_host_reputation_reviewee")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_host_reputation")
