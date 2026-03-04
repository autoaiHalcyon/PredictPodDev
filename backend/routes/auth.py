"""
Authentication Routes
API endpoints for authentication operations
"""
from fastapi import APIRouter, HTTPException, status, Depends, Request
from models.user import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    PasswordChange, ForgotPasswordRequest, PasswordReset
)
from repositories.user_repository import UserRepository, PasswordResetTokenRepository
from services.auth_service import AuthService
from services.auth_utils import get_current_user, JWTUtils
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# Router will be initialized with dependencies in server.py
router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Global references to be set in server.py
_auth_service: AuthService = None


def set_auth_service(auth_service: AuthService):
    """Set the auth service instance (called from server.py)"""
    global _auth_service
    _auth_service = auth_service


@router.post("/signup", response_model=TokenResponse)
async def signup(user_create: UserCreate) -> TokenResponse:
    """
    Register a new user
    
    - **name**: User's full name
    - **email**: User's email address (must be unique)
    - **phone**: User's phone number
    - **password**: Password (minimum 8 characters)
    """
    if not _auth_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth service not initialized"
        )
    
    return await _auth_service.signup(user_create)


@router.post("/login", response_model=TokenResponse)
async def login(user_login: UserLogin) -> TokenResponse:
    """
    Authenticate user with email and password
    
    Returns access token and user information
    """
    if not _auth_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth service not initialized"
        )
    
    return await _auth_service.login(user_login)


@router.post("/change-password", response_model=Dict[str, str])
async def change_password(
    password_change: PasswordChange,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Change current user's password
    
    Requires:
    - **current_password**: Current password for verification
    - **new_password**: New password (minimum 8 characters)
    """
    if not _auth_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth service not initialized"
        )
    
    user_id = current_user["user_id"]
    return await _auth_service.change_password(user_id, password_change)


@router.post("/forgot-password", response_model=Dict[str, str])
async def forgot_password(
    request: ForgotPasswordRequest
) -> Dict[str, str]:
    """
    Request password reset
    
    Sends a password reset token to the user's email
    """
    if not _auth_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth service not initialized"
        )
    
    return await _auth_service.request_password_reset(request.email)


@router.post("/reset-password", response_model=Dict[str, str])
async def reset_password(
    reset_data: PasswordReset,
    request: Request
) -> Dict[str, str]:
    """
    Reset password using reset token
    
    Requires:
    - **token**: Reset token from email
    - **new_password**: New password (minimum 8 characters)
    """
    if not _auth_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth service not initialized"
        )
    
    # Extract user_id from token if provided, or from request header
    auth_header = request.headers.get("Authorization")
    if auth_header:
        try:
            scheme, token = auth_header.split()
            if scheme.lower() == "bearer":
                payload = JWTUtils.verify_token(token)
                if payload and "sub" in payload:
                    user_id = payload["sub"]
                    return await _auth_service.reset_password(user_id, reset_data)
        except (ValueError, AttributeError, HTTPException):
            pass
    
    # If no valid token in header, check if token itself contains user info
    # For now, we'll require the token to be properly authenticated
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required for password reset"
    )


@router.get("/profile", response_model=UserResponse)
async def get_profile(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> UserResponse:
    """
    Get current user's profile
    
    Requires valid authentication token
    """
    if not _auth_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth service not initialized"
        )
    
    user_id = current_user["user_id"]
    return await _auth_service.get_user(user_id)


@router.post("/verify-token", response_model=Dict[str, Any])
async def verify_token(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Verify current authentication token
    
    Returns user information if token is valid
    """
    user_id = current_user["user_id"]
    
    if not _auth_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth service not initialized"
        )
    
    user = await _auth_service.get_user(user_id)
    return {
        "valid": True,
        "user": user,
        "message": "Token is valid"
    }
