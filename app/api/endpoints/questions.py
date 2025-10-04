from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import api_messages, deps
from app.core.database_session import get_async_session
from app.enums import PostStatusEnum
from app.models import MoguPost, QuestionAnswer, User
from app.schemas.requests import AnswerCreateRequest, QuestionCreateRequest
from app.schemas.responses import (
    QuestionListResponse,
    QuestionMessageResponse,
    QuestionResponse,
    QuestionWithAnswerResponse,
)

router = APIRouter()


@router.post(
    "/{post_id}/questions",
    response_model=QuestionMessageResponse,
    description="질문 작성",
)
async def create_question(
    post_id: str,
    data: QuestionCreateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> QuestionMessageResponse:
    """모구 게시물에 질문을 작성합니다."""

    # 게시물 조회
    query = select(MoguPost).where(MoguPost.id == post_id)
    result = await session.execute(query)
    mogu_post = result.scalar_one_or_none()

    if not mogu_post:
        raise HTTPException(
            status_code=404,
            detail=api_messages.MOGU_POST_NOT_FOUND,
        )

    # 질문 작성 가능한 상태인지 확인
    if mogu_post.status == PostStatusEnum.CANCELED.value:
        raise HTTPException(
            status_code=400,
            detail="취소된 모구에는 질문할 수 없습니다.",
        )

    # 질문 생성
    question = QuestionAnswer(
        mogu_post_id=post_id,
        questioner_id=current_user.id,
        question=data.question,
        is_private=data.is_private,
        question_created_at=datetime.utcnow(),
    )

    session.add(question)
    await session.commit()
    await session.refresh(question)

    # 질문자 정보 로드
    await session.refresh(question, ["questioner"])

    return QuestionMessageResponse(
        message="질문이 작성되었습니다.",
        question=QuestionResponse(
            id=question.id,
            mogu_post_id=question.mogu_post_id,
            questioner_id=question.questioner_id,
            question=question.question,
            is_private=question.is_private,
            question_created_at=question.question_created_at,
            questioner={
                "id": question.questioner.id,
                "nickname": question.questioner.nickname,
                "profile_image_url": question.questioner.profile_image_url,
            },
        ),
    )


@router.post(
    "/{post_id}/questions/{question_id}/answer",
    response_model=QuestionWithAnswerResponse,
    description="답변 작성 (모구장용)",
)
async def create_answer(
    post_id: str,
    question_id: str,
    data: AnswerCreateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> QuestionWithAnswerResponse:
    """질문에 답변을 작성합니다 (모구장만)."""

    # 게시물 조회
    mogu_post_query = select(MoguPost).where(MoguPost.id == post_id)
    mogu_post_result = await session.execute(mogu_post_query)
    mogu_post = mogu_post_result.scalar_one_or_none()

    if not mogu_post:
        raise HTTPException(
            status_code=404,
            detail=api_messages.MOGU_POST_NOT_FOUND,
        )

    # 모구장 권한 확인
    if mogu_post.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="모구장만 답변을 작성할 수 있습니다.",
        )

    # 질문 조회
    question_query = select(QuestionAnswer).where(
        and_(
            QuestionAnswer.id == question_id,
            QuestionAnswer.mogu_post_id == post_id,
        )
    )
    question_result = await session.execute(question_query)
    question = question_result.scalar_one_or_none()

    if not question:
        raise HTTPException(
            status_code=404,
            detail="질문을 찾을 수 없습니다.",
        )

    # 이미 답변이 있는지 확인
    if question.answer is not None:
        raise HTTPException(
            status_code=400,
            detail="이미 답변이 작성된 질문입니다.",
        )

    # 답변 업데이트
    question.answer = data.answer
    question.answerer_id = current_user.id
    question.answer_created_at = datetime.utcnow()

    await session.commit()
    await session.refresh(question)

    # 관련 데이터 로드
    await session.refresh(question, ["questioner", "answerer"])

    # 답변자 정보 구성
    answerer_data = None
    if question.answerer:
        answerer_data = {
            "id": question.answerer.id,
            "nickname": question.answerer.nickname,
            "profile_image_url": question.answerer.profile_image_url,
        }

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


@router.get(
    "/{post_id}/questions",
    response_model=QuestionListResponse,
    description="Q&A 목록 조회",
)
async def get_questions(
    post_id: str,
    current_user: User | None = Depends(deps.get_current_user_optional),
    session: AsyncSession = Depends(get_async_session),
) -> QuestionListResponse:
    """모구 게시물의 Q&A 목록을 조회합니다."""

    # 게시물 조회
    query = select(MoguPost).where(MoguPost.id == post_id)
    result = await session.execute(query)
    mogu_post = result.scalar_one_or_none()

    if not mogu_post:
        raise HTTPException(
            status_code=404,
            detail=api_messages.MOGU_POST_NOT_FOUND,
        )

    # Q&A 목록 조회
    questions_query = (
        select(QuestionAnswer)
        .options(
            selectinload(QuestionAnswer.questioner),
            selectinload(QuestionAnswer.answerer),
        )
        .where(QuestionAnswer.mogu_post_id == post_id)
        .order_by(QuestionAnswer.question_created_at.desc())
    )

    questions_result = await session.execute(questions_query)
    questions = questions_result.scalars().all()

    questions_data = []
    for question in questions:
        # 답변자 정보 구성
        answerer_data = None
        if question.answerer:
            answerer_data = {
                "id": question.answerer.id,
                "nickname": question.answerer.nickname,
                "profile_image_url": question.answerer.profile_image_url,
            }

        questions_data.append(
            QuestionWithAnswerResponse(
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
        )

    return QuestionListResponse(questions=questions_data)
