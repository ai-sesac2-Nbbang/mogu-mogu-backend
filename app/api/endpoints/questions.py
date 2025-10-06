from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import api_messages, deps
from app.api.common import _check_qa_activity_allowed, _get_mogu_post
from app.core.database_session import get_async_session
from app.models import MoguPost, QuestionAnswer, User
from app.schemas.requests import (
    AnswerCreateRequest,
    AnswerUpdateRequest,
    QuestionCreateRequest,
    QuestionUpdateRequest,
)
from app.schemas.responses import (
    QuestionAnswerConverter,
    QuestionListResponse,
    QuestionResponse,
    QuestionWithAnswerResponse,
)

router = APIRouter()


async def _get_question(
    post_id: str,
    question_id: str,
    session: AsyncSession,
) -> QuestionAnswer:
    """질문을 조회합니다."""
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="질문을 찾을 수 없습니다.",
        )

    return question


@router.post(
    "/{post_id}/questions",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
    description="질문 작성",
)
async def create_question(
    post_id: str,
    data: QuestionCreateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> QuestionResponse:
    """모구 게시물에 질문을 작성합니다."""

    # 게시물 조회 및 상태 확인
    mogu_post = await _get_mogu_post(post_id, session)
    await _check_qa_activity_allowed(mogu_post, session)

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

    return QuestionResponse(
        id=question.id,
        mogu_post_id=question.mogu_post_id,
        questioner_id=question.questioner_id,
        question=question.question,
        is_private=question.is_private,
        question_created_at=question.question_created_at,
        questioner={
            "id": question.questioner.id,
            "nickname": question.questioner.nickname,
            "profile_image_path": question.questioner.profile_image_path,
        },
    )


@router.patch(
    "/{post_id}/questions/{question_id}",
    response_model=QuestionResponse,
    description="질문 수정",
)
async def update_question(
    post_id: str,
    question_id: str,
    data: QuestionUpdateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> QuestionResponse:
    """질문을 수정합니다 (답변이 달리기 전까지만 가능)."""

    # 질문 조회
    question = await _get_question(post_id, question_id, session)

    # 질문 작성자 권한 확인
    if question.questioner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="질문 작성자만 수정할 수 있습니다.",
        )

    # 게시물 상태 확인
    mogu_post = await _get_mogu_post(post_id, session)
    await _check_qa_activity_allowed(mogu_post, session)

    # 답변이 이미 달렸는지 확인
    if question.answer is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="답변이 달린 질문은 수정할 수 없습니다.",
        )

    # 질문 업데이트
    question.question = data.question
    if data.is_private is not None:
        question.is_private = data.is_private

    await session.commit()
    await session.refresh(question)

    # 질문자 정보 로드
    await session.refresh(question, ["questioner"])

    return QuestionResponse(
        id=question.id,
        mogu_post_id=question.mogu_post_id,
        questioner_id=question.questioner_id,
        question=question.question,
        is_private=question.is_private,
        question_created_at=question.question_created_at,
        questioner={
            "id": question.questioner.id,
            "nickname": question.questioner.nickname,
            "profile_image_path": question.questioner.profile_image_path,
        },
    )


@router.delete(
    "/{post_id}/questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    description="질문 삭제",
)
async def delete_question(
    post_id: str,
    question_id: str,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """질문을 삭제합니다 (답변이 달리기 전까지만 가능)."""

    # 질문 조회
    question = await _get_question(post_id, question_id, session)

    # 질문 작성자 권한 확인
    if question.questioner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="질문 작성자만 삭제할 수 있습니다.",
        )

    # 게시물 상태 확인
    mogu_post = await _get_mogu_post(post_id, session)
    await _check_qa_activity_allowed(mogu_post, session)

    # 답변이 이미 달렸는지 확인
    if question.answer is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="답변이 달린 질문은 삭제할 수 없습니다.",
        )

    # 질문 삭제
    await session.delete(question)
    await session.commit()


@router.post(
    "/{post_id}/questions/{question_id}/answer",
    response_model=QuestionWithAnswerResponse,
    status_code=status.HTTP_201_CREATED,
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

    # 게시물 조회 및 상태 확인
    mogu_post = await _get_mogu_post(post_id, session)
    await _check_qa_activity_allowed(mogu_post, session)

    # 모구장 권한 확인
    if mogu_post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="모구장만 답변을 작성할 수 있습니다.",
        )

    # 질문 조회
    question = await _get_question(post_id, question_id, session)

    # 이미 답변이 있는지 확인
    if question.answer is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
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

    return QuestionWithAnswerResponse.from_question(
        question, QuestionAnswerConverter.build_answerer_data(question)
    )


@router.patch(
    "/{post_id}/questions/{question_id}/answer",
    response_model=QuestionWithAnswerResponse,
    description="답변 수정 (모구장용)",
)
async def update_answer(
    post_id: str,
    question_id: str,
    data: AnswerUpdateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> QuestionWithAnswerResponse:
    """답변을 수정합니다 (모구장만, 모구 완료/취소 전까지)."""

    # 게시물 조회 및 상태 확인
    mogu_post = await _get_mogu_post(post_id, session)
    await _check_qa_activity_allowed(mogu_post, session)

    # 모구장 권한 확인
    if mogu_post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="모구장만 답변을 수정할 수 있습니다.",
        )

    # 질문 조회
    question = await _get_question(post_id, question_id, session)

    # 답변이 있는지 확인
    if question.answer is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="답변이 없는 질문입니다.",
        )

    # 답변 수정
    question.answer = data.answer

    await session.commit()
    await session.refresh(question)

    # 관련 데이터 로드
    await session.refresh(question, ["questioner", "answerer"])

    return QuestionWithAnswerResponse.from_question(
        question, QuestionAnswerConverter.build_answerer_data(question)
    )


@router.delete(
    "/{post_id}/questions/{question_id}/answer",
    status_code=status.HTTP_204_NO_CONTENT,
    description="답변 삭제 (모구장용)",
)
async def delete_answer(
    post_id: str,
    question_id: str,
    current_user: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """답변을 삭제합니다 (모구장만, 모구 완료/취소 전까지)."""

    # 게시물 조회 및 상태 확인
    mogu_post = await _get_mogu_post(post_id, session)
    await _check_qa_activity_allowed(mogu_post, session)

    # 모구장 권한 확인
    if mogu_post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="모구장만 답변을 삭제할 수 있습니다.",
        )

    # 질문 조회
    question = await _get_question(post_id, question_id, session)

    # 답변이 있는지 확인
    if question.answer is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="답변이 없는 질문입니다.",
        )

    # 답변 삭제 (답변 관련 필드만 초기화)
    question.answer = None
    question.answerer_id = None
    question.answer_created_at = None

    await session.commit()


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

    # 게시물 존재 확인
    query = select(MoguPost).where(MoguPost.id == post_id)
    result = await session.execute(query)
    mogu_post = result.scalar_one_or_none()

    if not mogu_post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
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
        questions_data.append(
            QuestionWithAnswerResponse.from_question(
                question, QuestionAnswerConverter.build_answerer_data(question)
            )
        )

    return QuestionListResponse(items=questions_data)
