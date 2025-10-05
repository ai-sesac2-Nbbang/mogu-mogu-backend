"""
공통 유틸리티 함수들을 제공하는 모듈입니다.

이 모듈은 API 엔드포인트들 간에 중복되는 기능들을
공통 함수로 추출하여 코드 재사용성과 유지보수성을 향상시킵니다.
"""

from .post_utils import (
    MoguPostBasicData,
    _build_mogu_post_basic_data,
    _calculate_pagination_info,
    _check_favorite_status,
    _check_post_permissions,
    _execute_paginated_query,
    _extract_thumbnail_image,
    _get_favorite_count,
    _get_mogu_post,
    _get_mogu_post_with_relations,
    _get_user_participation_status,
    _validate_post_status_for_deletion,
)
from .validation_utils import (
    _check_qa_activity_allowed,
    _check_user_participation_status,
    _validate_rating_permissions,
)

__all__ = [
    # Post utilities
    "_build_mogu_post_basic_data",
    "_calculate_pagination_info",
    "_check_post_permissions",
    "_execute_paginated_query",
    "_get_mogu_post",
    "_get_mogu_post_with_relations",
    "_validate_post_status_for_deletion",
    "_get_user_participation_status",
    "_check_favorite_status",
    "_get_favorite_count",
    "_extract_thumbnail_image",
    # Types
    "MoguPostBasicData",
    # Validation utilities
    "_check_qa_activity_allowed",
    "_check_user_participation_status",
    "_validate_rating_permissions",
]
