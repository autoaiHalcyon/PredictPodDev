"""
User Model
Defines the User schema and data structure with password management
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """User roles in the system"""
    USER = "user"
    ADMIN = "admin"


class UserBase(BaseModel):
    """Base user schema with common fields"""
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=20)


class UserCreate(UserBase):
    """Schema for user registration"""
    password: str = Field(..., min_length=8, max_length=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "+1234567890",
                "password": "SecurePass123!",
            }
        }


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "john@example.com",
                "password": "SecurePass123!",
            }
        }


class PasswordChange(BaseModel):
    """Schema for changing password"""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "current_password": "OldPass123!",
                "new_password": "NewPass456!",
            }
        }


class ForgotPasswordRequest(BaseModel):
    """Schema for forgot password request"""
    email: EmailStr
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "john@example.com",
            }
        }


class PasswordReset(BaseModel):
    """Schema for password reset"""
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "token": "reset_token_here",
                "new_password": "NewPass456!",
            }
        }


class UserInDB(UserBase):
    """User schema as stored in database"""
    id: str = Field(..., alias="_id")
    hashed_password: str
    role: UserRole = UserRole.USER
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "+1234567890",
                "hashed_password": "$2b$12$...",
                "role": "user",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
                "is_active": True,
            }
        }


class UserResponse(UserBase):
    """User schema for API responses (no password fields)"""
    id: str = Field(..., alias="_id")
    role: UserRole
    created_at: datetime
    is_active: bool
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "+1234567890",
                "role": "user",
                "created_at": "2024-01-01T00:00:00",
                "is_active": True,
            }
        }


class TokenResponse(BaseModel):
    """Schema for token response"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIs...",
                "token_type": "bearer",
                "user": {
                    "_id": "507f1f77bcf86cd799439011",
                    "name": "John Doe",
                    "email": "john@example.com",
                    "phone": "+1234567890",
                    "role": "user",
                    "created_at": "2024-01-01T00:00:00",
                    "is_active": True,
                }
            }
        }


class PasswordResetToken(BaseModel):
    """Schema for password reset tokens stored in database"""
    token_hash: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    used: bool = False
