import asyncio
import json
from datetime import datetime
from repositories.user_repository import UserRepository
from services.auth_utils import PasswordUtils
from motor.motor_asyncio import AsyncIOMotorClient

async def create_test_user():
    try:
        print("[*] Connecting to MongoDB...")
        client = AsyncIOMotorClient("mongodb://localhost:27017", serverSelectionTimeoutMS=5000)
        
        # Test connection
        db = client["predictpod"]
        await db.command("ping")
        print("[✓] Connected to MongoDB")
        
        # Check if user exists
        existing = await db.users.find_one({"email": "predictpod@example.com"})
        if existing:
            print("[!] User already exists")
            client.close()
            return
        
        # Hash the password
        print("[*] Hashing password...")
        hashed_pwd = PasswordUtils.hash_password("Halcyon12$")
        
        # Create user
        print("[*] Creating user...")
        user = {
            "name": "PredictPod User",
            "email": "predictpod@example.com",
            "phone": "+1-555-0123",
            "hashed_password": hashed_pwd,
            "created_at": datetime.utcnow(),
            "is_active": True
        }
        
        result = await db.users.insert_one(user)
        print(f"[✓] User created successfully!")
        print(f"    ID: {result.inserted_id}")
        print(f"    Email: predictpod@example.com")
        print(f"    Password: Halcyon12$")
        
    except Exception as e:
        print(f"[✗] Error: {str(e)}")
        print(f"    Type: {type(e).__name__}")
    finally:
        try:
            client.close()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(create_test_user())

