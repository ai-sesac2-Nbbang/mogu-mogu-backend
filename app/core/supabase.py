"""Supabase Storage 클라이언트 설정"""

from supabase import Client, create_client

from app.core.config import get_settings


class SupabaseStorage:
    """Supabase Storage 클라이언트 래퍼"""

    def __init__(self) -> None:
        self.client: Client = self._create_client()
        self.default_bucket = "images"

    def _create_client(self) -> Client:
        """Supabase 클라이언트 생성"""
        settings = get_settings()

        return create_client(
            settings.supabase.url, settings.supabase.anon_key.get_secret_value()
        )

    async def delete_file(self, bucket_name: str, file_path: str) -> bool:
        """파일 삭제"""
        try:
            result = self.client.storage.from_(bucket_name).remove([file_path])

            if result.get("error"):
                raise Exception(f"삭제 실패: {result['error']}")

            return True
        except Exception as e:
            raise Exception(f"파일 삭제 중 오류: {str(e)}")

    async def create_presigned_url(
        self, bucket_name: str, file_path: str, expires_in: int = 3600
    ) -> str:
        """업로드용 사전 서명 URL 생성"""
        try:
            result = self.client.storage.from_(bucket_name).create_signed_upload_url(
                file_path, expires_in
            )

            if result.get("error"):
                raise Exception(f"사전 서명 URL 생성 실패: {result['error']}")

            return str(result.get("signedURL", ""))
        except Exception as e:
            raise Exception(f"사전 서명 URL 생성 중 오류: {str(e)}")

    def get_public_url(self, bucket_name: str, file_path: str) -> str:
        """공개 URL 생성"""
        return str(self.client.storage.from_(bucket_name).get_public_url(file_path))


# 전역 인스턴스 (lazy initialization)
_supabase_storage: SupabaseStorage | None = None


def get_supabase_storage() -> SupabaseStorage:
    """Supabase Storage 인스턴스 반환 (lazy initialization)"""
    global _supabase_storage  # noqa: PLW0603
    if _supabase_storage is None:
        _supabase_storage = SupabaseStorage()
    return _supabase_storage


# 하위 호환성을 위한 alias
supabase_storage = get_supabase_storage()
