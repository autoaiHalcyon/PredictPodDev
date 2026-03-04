"""
Authentication Service
Handles all authentication business logic
"""
from typing import Optional, Dict, Any
from datetime import timedelta
from fastapi import HTTPException, status
from models.user import UserCreate, UserLogin, UserInDB, UserResponse, TokenResponse, PasswordChange, PasswordReset
from repositories.user_repository import UserRepository, PasswordResetTokenRepository
from services.auth_utils import PasswordUtils, JWTUtils
import logging

logger = logging.getLogger(__name__)


class AuthService:
    """Service for authentication operations"""
    
    def __init__(
        self,
        user_repo: UserRepository,
        reset_token_repo: PasswordResetTokenRepository
    ):
        """Initialize with required repositories"""
        self.user_repo = user_repo
        self.reset_token_repo = reset_token_repo
    
    async def signup(self, user_create: UserCreate) -> TokenResponse:
        """
        Register a new user
        
        Args:
            user_create: User registration data
            
        Returns:
            TokenResponse with access token and user info
            
        Raises:
            HTTPException: If email already registered
        """
        try:
            # Create user in database
            user_in_db = await self.user_repo.create_user(user_create)
            
            # Generate access token
            access_token = JWTUtils.create_access_token(
                data={"sub": str(user_in_db.id)},
                expires_delta=timedelta(hours=24)
            )
            
            # Prepare response
            user_response = UserResponse(
                _id=str(user_in_db.id),
                name=user_in_db.name,
                email=user_in_db.email,
                phone=user_in_db.phone,
                role=user_in_db.role,
                created_at=user_in_db.created_at,
                is_active=user_in_db.is_active
            )
            
            logger.info(f"User signed up successfully: {user_create.email}")
            
            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
                user=user_response
            )
        
        except ValueError as e:
            logger.warning(f"Signup failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Signup error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred during signup"
            )
    
    async def login(self, user_login: UserLogin) -> TokenResponse:
        """
        Authenticate user with email and password
        
        Args:
            user_login: Login credentials
            
        Returns:
            TokenResponse with access token and user info
            
        Raises:
            HTTPException: If credentials are invalid
        """
        try:
            # Get user by email
            user = await self.user_repo.get_user_by_email(user_login.email)
            
            # Verify user exists and password matches
            if not user or not PasswordUtils.verify_password(
                user_login.password, user.hashed_password
            ):
                logger.warning(f"Failed login attempt for: {user_login.email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            # Check if user is active
            if not user.is_active:
                logger.warning(f"Login attempt on inactive account: {user_login.email}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is inactive"
                )
            
            # Generate access token
            access_token = JWTUtils.create_access_token(
                data={"sub": str(user.id)},
                expires_delta=timedelta(hours=24)
            )
            
            # Prepare response
            user_response = UserResponse(
                _id=str(user.id),
                name=user.name,
                email=user.email,
                phone=user.phone,
                role=user.role,
                created_at=user.created_at,
                is_active=user.is_active
            )
            
            logger.info(f"User logged in: {user_login.email}")
            
            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
                user=user_response
            )
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred during login"
            )
    
    async def change_password(
        self,
        user_id: str,
        password_change: PasswordChange
    ) -> Dict[str, str]:
        """
        Change user password
        
        Args:
            user_id: User ID
            password_change: Current and new password
            
        Returns:
            Success message
            
        Raises:
            HTTPException: If current password is incorrect
        """
        try:
            # Get user
            user = await self.user_repo.get_user_by_id(user_id)
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Verify current password
            if not PasswordUtils.verify_password(
                password_change.current_password,
                user.hashed_password
            ):
                logger.warning(f"Failed password change attempt for: {user.email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Current password is incorrect"
                )
            
            # Update password
            success = await self.user_repo.update_password(
                user_id,
                password_change.new_password
            )
            
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update password"
                )
            
            logger.info(f"Password changed for: {user.email}")
            
            return {"message": "Password changed successfully"}
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Password change error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while changing password"
            )
    
    async def request_password_reset(self, email: str) -> Dict[str, str]:
        """
        Request password reset for email
        
        Args:
            email: User email
            
        Returns:
            Dictionary with reset token (for demo purposes)
            
        Raises:
            HTTPException: If user not found
        """
        try:
            # Get user by email
            user = await self.user_repo.get_user_by_email(email)
            
            if not user:
                # For security, don't reveal if email exists
                logger.warning(f"Password reset requested for non-existent email: {email}")
                return {
                    "message": "If an account exists with that email, a reset link will be sent"
                }
            
            # Generate reset token
            reset_token = await self.reset_token_repo.create_reset_token(
                str(user.id),
                expires_in_hours=24
            )
            
            logger.info(f"Password reset token generated for: {email}")
            
            # In production, this should be sent via email
            # For now, return token for frontend to use (in production, send via email)
            return {
                "message": "Password reset link sent to your email",
                "reset_token": reset_token  # Remove in production, use email instead
            }
        
        except Exception as e:
            logger.error(f"Password reset request error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while processing password reset"
            )
    
    async def reset_password(
        self,
        user_id: str,
        reset_data: PasswordReset
    ) -> Dict[str, str]:
        """
        Reset password using reset token
        
        Args:
            user_id: User ID
            reset_data: Reset token and new password
            
        Returns:
            Success message
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            # Verify reset token
            token_valid = await self.reset_token_repo.verify_reset_token(
                user_id,
                reset_data.token
            )
            
            if not token_valid:
                logger.warning(f"Invalid password reset token for user: {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired reset token"
                )
            
            # Update password
            success = await self.user_repo.update_password(
                user_id,
                reset_data.new_password
            )
            
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to reset password"
                )
            
            # Mark token as used
            await self.reset_token_repo.mark_token_as_used(user_id, reset_data.token)
            
            logger.info(f"Password reset successful for user: {user_id}")
            
            return {"message": "Password reset successfully"}
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while resetting password"
            )
    
    async def get_user(self, user_id: str) -> UserResponse:
        """
        Get user profile
        
        Args:
            user_id: User ID
            
        Returns:
            User response
            
        Raises:
            HTTPException: If user not found
        """
        try:
            user_response = await self.user_repo.get_user_response(user_id)
            
            if not user_response:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            return user_response
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Get user error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while fetching user"
            )
