"""
응답 객체 생성 관련 공통 유틸리티 함수들입니다.
"""

from collections.abc import Sequence
from typing import Any

from geoalchemy2.shape import to_shape

from app.models import MoguPost, Participation, QuestionAnswer, User
from app.schemas.responses import (
    MoguPostResponse,
    ParticipationResponse,
    QuestionWithAnswerResponse,
    UserResponse,
)


def _build_user_response(user: User) -> UserResponse:
    """사용자 응답 객체를 생성합니다."""
    return UserResponse(
        user_id=user.id,
        email=user.email,
        nickname=user.nickname,
        profile_image_url=user.profile_image_url,
        phone_number=user.phone_number,
        birth_date=user.birth_date,
        gender=user.gender,
        created_at=user.created_at,
        updated_at=user.updated_at,
        reported_count=user.reported_count,
        status=user.status,
    )


def _build_participation_response(
    participation: Participation,
) -> ParticipationResponse:
    """참여 응답 객체를 생성합니다."""
    return ParticipationResponse(
        mogu_post_id=participation.mogu_post_id,
        user_id=participation.user_id,
        status=participation.status,
        applied_at=participation.applied_at,
        decided_at=participation.decided_at,
    )


def _build_question_response(
    question: QuestionAnswer, answerer_data: dict[str, Any] | None = None
) -> QuestionWithAnswerResponse:
    """Q&A 응답 객체를 생성합니다."""
    return QuestionWithAnswerResponse(
        id=question.id,
        question=question.question,
        answer=question.answer,
        is_private=question.is_private,
        question_created_at=question.question_created_at,
        answer_created_at=question.answer_created_at,
        questioner={
            "id": question.questioner.id,
            "nickname": question.questioner.nickname,
            "profile_image_url": question.questioner.profile_image_url,
        },
        answerer=answerer_data,
    )


def _build_mogu_post_response(
    mogu_post: MoguPost,
    my_participation: dict[str, Any] | None = None,
    is_favorited: bool = False,
    questions_answers: list[dict[str, Any]] | None = None,
) -> MoguPostResponse:
    """모구 게시물 응답 객체를 생성합니다."""
    # Shapely를 사용한 위도/경도 추출
    point = to_shape(mogu_post.mogu_spot)
    latitude = point.y
    longitude = point.x

    return MoguPostResponse(
        id=mogu_post.id,
        user_id=mogu_post.user_id,
        title=mogu_post.title,
        description=mogu_post.description,
        price=mogu_post.price,
        category=mogu_post.category,
        mogu_market=mogu_post.mogu_market,
        mogu_spot={
            "latitude": latitude,
            "longitude": longitude,
        },
        mogu_datetime=mogu_post.mogu_datetime,
        status=mogu_post.status,
        target_count=mogu_post.target_count,
        joined_count=mogu_post.joined_count,
        created_at=mogu_post.created_at,
        images=[
            {
                "id": img.id,
                "image_url": img.image_url,
                "order": img.sort_order,
            }
            for img in mogu_post.images
        ],
        user={
            "id": mogu_post.user.id,
            "nickname": mogu_post.user.nickname,
            "profile_image_url": mogu_post.user.profile_image_url,
        },
        my_participation=my_participation,
        is_favorited=is_favorited,
        questions_answers=questions_answers,
    )


def _convert_questions_answers_to_dict(
    questions_answers: Sequence[Any] | None,
) -> list[dict[str, Any]] | None:
    """Q&A 데이터를 딕셔너리 형태로 변환합니다."""
    if not questions_answers:
        return None

    return [
        {
            "id": qa.id,
            "questioner_id": qa.questioner_id,
            "question": qa.question,
            "answerer_id": qa.answerer_id,
            "answer": qa.answer,
            "is_private": qa.is_private,
            "question_created_at": qa.question_created_at,
            "answer_created_at": qa.answer_created_at,
        }
        for qa in questions_answers
    ]
