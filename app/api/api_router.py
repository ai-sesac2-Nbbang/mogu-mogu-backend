from fastapi import APIRouter

from app.api import api_messages
from app.api.endpoints import (
    auth,
    comments,
    favorites,
    images,
    mogu_posts,
    participations,
    ratings,
    users,
)

auth_router = APIRouter()
auth_router.include_router(auth.router, prefix="/auth", tags=["auth"])

api_router = APIRouter(
    responses={
        401: {
            "description": "No `Authorization` access token header, token is invalid or user removed",
            "content": {
                "application/json": {
                    "examples": {
                        "not authenticated": {
                            "summary": "No authorization token header",
                            "value": {"detail": "Not authenticated"},
                        },
                        "invalid token": {
                            "summary": "Token validation failed, decode failed, it may be expired or malformed",
                            "value": {"detail": "Token invalid: {detailed error msg}"},
                        },
                        "removed user": {
                            "summary": api_messages.JWT_ERROR_USER_REMOVED,
                            "value": {"detail": api_messages.JWT_ERROR_USER_REMOVED},
                        },
                    }
                }
            },
        },
    }
)
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(favorites.router, prefix="/mogu-posts", tags=["favorites"])
api_router.include_router(mogu_posts.router, prefix="/mogu-posts", tags=["mogu-posts"])
api_router.include_router(
    participations.router, prefix="/mogu-posts", tags=["participations"]
)
api_router.include_router(comments.router, prefix="/mogu-posts", tags=["comments"])
api_router.include_router(ratings.router, prefix="/mogu-posts", tags=["ratings"])
api_router.include_router(ratings.independent_router, prefix="", tags=["ratings"])
api_router.include_router(ratings.keywords_router, prefix="", tags=["rating-keywords"])
api_router.include_router(images.router, prefix="/images", tags=["images"])
