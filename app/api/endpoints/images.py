"""이미지 관리 API"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.core.supabase import get_supabase_storage
from app.models import User
from app.schemas.requests import ImageDeleteRequest, PresignedUrlRequest
from app.schemas.responses import PresignedUrlResponse

router = APIRouter()


@router.post("/presigned-url", response_model=PresignedUrlResponse)
async def create_presigned_upload_url(
    request: PresignedUrlRequest,
    current_user: User = Depends(deps.get_current_user),
) -> PresignedUrlResponse:
    """
    업로드용 사전 서명 URL 생성

    클라이언트에서 직접 Supabase Storage에 업로드할 수 있는 URL을 생성합니다.
    """
    # 단순한 경로 생성: 사용자 ID 하위에 UUID 파일명
    file_extension = (
        request.file_name.split(".")[-1] if "." in request.file_name else "jpg"
    )
    file_uuid = str(uuid.uuid4())
    file_path = f"{current_user.id}/{file_uuid}.{file_extension}"

    try:
        # 사전 서명 URL 생성 (1시간 유효)
        supabase_storage = get_supabase_storage()
        upload_url = await supabase_storage.create_presigned_url(
            bucket_name=request.bucket_name, file_path=file_path, expires_in=3600
        )

        return PresignedUrlResponse(
            upload_url=upload_url,
            file_path=file_path,
            expires_in=3600,
            bucket_name=request.bucket_name,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"사전 서명 URL 생성 실패: {str(e)}",
        )


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    description="이미지 삭제 (단일 또는 다중)",
)
async def delete_images(
    data: ImageDeleteRequest,
    current_user: User = Depends(deps.get_current_user),
) -> None:
    """
    이미지 삭제 (단일 또는 다중)

    - **file_paths**: 삭제할 이미지 파일 경로 목록 (1개 이상)
    - **bucket_name**: Supabase Storage 버킷명
    """
    try:
        # 각 파일 경로에 대해 권한 확인
        for file_path in data.file_paths:
            # 경로 형식: {user_id}/{uuid}.{extension}
            path_parts = file_path.split("/")
            PATH_PARTS_LENGTH = 2
            if len(path_parts) != PATH_PARTS_LENGTH or path_parts[0] != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"이미지를 삭제할 권한이 없습니다: {file_path}",
                )

        # Supabase Storage에서 파일들 삭제
        supabase_storage = get_supabase_storage()
        await supabase_storage.delete_files_batch(data.bucket_name, data.file_paths)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"이미지 삭제 실패: {str(e)}",
        )
