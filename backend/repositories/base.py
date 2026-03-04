"""
Base Repository - Abstract interface for database operations.
Designed for easy MongoDB -> PostgreSQL migration.
"""
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional, Dict, Any
from datetime import datetime

T = TypeVar('T')

class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository defining the interface for all data operations.
    Implementations can use MongoDB, PostgreSQL, or any other database.
    """
    
    @abstractmethod
    async def create(self, entity: T) -> T:
        """Create a new entity"""
        pass
    
    @abstractmethod
    async def get_by_id(self, id: str) -> Optional[T]:
        """Get entity by ID"""
        pass
    
    @abstractmethod
    async def get_all(self, limit: int = 100, skip: int = 0) -> List[T]:
        """Get all entities with pagination"""
        pass
    
    @abstractmethod
    async def update(self, id: str, data: Dict[str, Any]) -> Optional[T]:
        """Update entity by ID"""
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Delete entity by ID"""
        pass
    
    @abstractmethod
    async def find(self, filters: Dict[str, Any], limit: int = 100) -> List[T]:
        """Find entities matching filters"""
        pass
    
    @abstractmethod
    async def count(self, filters: Dict[str, Any] = None) -> int:
        """Count entities matching filters"""
        pass
