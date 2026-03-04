"""
User Repository
Handles all database operations for users
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional, List
from models.user import UserCreate, UserInDB, UserResponse, PasswordResetToken
from services.auth_utils import PasswordUtils, TokenUtils
import logging

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for User model database operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize with database instance"""
        self.db = db
        self.collection = db.users
    
    async def ensure_indexes(self):
        """Create necessary indexes"""
        try:
            await self.collection.create_index("email", unique=True)
            await self.collection.create_index("created_at")
            logger.info("User collection indexes created")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
    
    async def create_user(self, user_create: UserCreate) -> UserInDB:
        """Create a new user"""
        # Check if user already exists
        existing = await self.collection.find_one({"email": user_create.email})
        if existing:
            raise ValueError(f"Email {user_create.email} already registered")
        
        # Hash password
        hashed_password = PasswordUtils.hash_password(user_create.password)
        
        # Prepare user document
        user_doc = {
            "name": user_create.name,
            "email": user_create.email,
            "phone": user_create.phone,
            "hashed_password": hashed_password,
            "role": "user",
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        # Insert into database
        result = await self.collection.insert_one(user_doc)
        user_doc["_id"] = str(result.inserted_id)
        
        logger.info(f"User created: {user_create.email}")
        return UserInDB(**user_doc)
    
    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """Get user by email"""
        user_doc = await self.collection.find_one(
            {"email": email},
            {"email": 1, "name": 1, "phone": 1, "hashed_password": 1, 
             "role": 1, "is_active": 1, "created_at": 1, "updated_at": 1}
        )
        
        if not user_doc:
            return None
        
        # Convert ObjectId to string
        user_doc["_id"] = str(user_doc["_id"])
        return UserInDB(**user_doc)
    
    async def get_user_by_id(self, user_id: str) -> Optional[UserInDB]:
        """Get user by ID"""
        try:
            obj_id = ObjectId(user_id)
        except Exception:
            return None
        
        user_doc = await self.collection.find_one(
            {"_id": obj_id},
            {"email": 1, "name": 1, "phone": 1, "hashed_password": 1,
             "role": 1, "is_active": 1, "created_at": 1, "updated_at": 1}
        )
        
        if not user_doc:
            return None
        
        # Convert ObjectId to string
        user_doc["_id"] = str(user_doc["_id"])
        return UserInDB(**user_doc)
    
    async def update_password(self, user_id: str, new_password: str) -> bool:
        """Update user password"""
        try:
            obj_id = ObjectId(user_id)
        except Exception:
            return False
        
        hashed_password = PasswordUtils.hash_password(new_password)
        
        result = await self.collection.update_one(
            {"_id": obj_id},
            {
                "$set": {
                    "hashed_password": hashed_password,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return result.modified_count > 0
    
    async def get_user_response(self, user_id: str) -> Optional[UserResponse]:
        """Get user as response object (without password)"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None
        
        return UserResponse(
            _id=str(user.id),
            name=user.name,
            email=user.email,
            phone=user.phone,
            role=user.role,
            created_at=user.created_at,
            is_active=user.is_active
        )
    
    async def user_exists(self, email: str) -> bool:
        """Check if user exists by email"""
        count = await self.collection.count_documents({"email": email})
        return count > 0
    
    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user account"""
        try:
            obj_id = ObjectId(user_id)
        except Exception:
            return False
        
        result = await self.collection.update_one(
            {"_id": obj_id},
            {
                "$set": {
                    "is_active": False,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return result.modified_count > 0


class PasswordResetTokenRepository:
    """Repository for password reset tokens"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize with database instance"""
        self.db = db
        self.collection = db.password_reset_tokens
    
    async def ensure_indexes(self):
        """Create necessary indexes"""
        try:
            await self.collection.create_index("user_id")
            await self.collection.create_index("expires_at", expireAfterSeconds=0)
            logger.info("Password reset token collection indexes created")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
    
    async def create_reset_token(self, user_id: str, expires_in_hours: int = 24) -> str:
        """Create a password reset token"""
        token = TokenUtils.generate_reset_token()
        token_hash = TokenUtils.hash_reset_token(token)
        
        reset_token_doc = {
            "user_id": user_id,
            "token_hash": token_hash,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=expires_in_hours),
            "used": False
        }
        
        await self.collection.insert_one(reset_token_doc)
        return token
    
    async def verify_reset_token(self, user_id: str, token: str) -> bool:
        """Verify a password reset token"""
        token_hash = TokenUtils.hash_reset_token(token)
        
        token_doc = await self.collection.find_one({
            "user_id": user_id,
            "token_hash": token_hash,
            "used": False,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        return token_doc is not None
    
    async def mark_token_as_used(self, user_id: str, token: str) -> bool:
        """Mark a reset token as used"""
        token_hash = TokenUtils.hash_reset_token(token)
        
        result = await self.collection.update_one(
            {"user_id": user_id, "token_hash": token_hash},
            {"$set": {"used": True}}
        )
        
        return result.modified_count > 0
    
    async def delete_user_tokens(self, user_id: str) -> int:
        """Delete all reset tokens for a user"""
        result = await self.collection.delete_many({"user_id": user_id})
        return result.deleted_count


from datetime import timedelta
