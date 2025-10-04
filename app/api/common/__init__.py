"""
공통 유틸리티 함수들을 제공하는 모듈입니다.

이 모듈은 API 엔드포인트들 간에 중복되는 기능들을
공통 함수로 추출하여 코드 재사용성과 유지보수성을 향상시킵니다.
"""

from .post_utils import (
    _check_post_permissions,
    _get_mogu_post,
    _get_mogu_post_with_relations,
    _validate_post_status_for_deletion,
)
from .response_utils import (
    _build_mogu_post_response,
    _build_participation_response,
    _build_question_response,
    _build_user_response,
    _convert_questions_answers_to_dict,
)
from .validation_utils import _check_qa_activity_allowed

__all__ = [
    # Post utilities
    "_check_post_permissions",
    "_get_mogu_post",
    "_get_mogu_post_with_relations",
    "_validate_post_status_for_deletion",
    # Response utilities
    "_build_mogu_post_response",
    "_build_participation_response",
    "_build_question_response",
    "_build_user_response",
    "_convert_questions_answers_to_dict",
    # Validation utilities
    "_check_qa_activity_allowed",
]
