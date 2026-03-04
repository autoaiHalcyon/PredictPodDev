"""
NBA Data Provider Interface
Abstract interface for NBA live data - allows swapping providers.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from models.game import Game

class NBADataProvider(ABC):
    """
    Abstract interface for NBA live data providers.
    Implement this to add new data sources (ESPN, NBA Stats, etc.)
    """
    
    @abstractmethod
    async def get_live_games(self) -> List[Game]:
        """
        Get all currently live NBA games.
        Returns list of Game objects with live scores.
        """
        pass
    
    @abstractmethod
    async def get_game_by_id(self, game_id: str) -> Optional[Game]:
        """
        Get a specific game by ID.
        """
        pass
    
    @abstractmethod
    async def get_todays_games(self) -> List[Game]:
        """
        Get all NBA games scheduled for today.
        """
        pass
    
    @abstractmethod
    async def get_upcoming_games(self, days: int = 7) -> List[Game]:
        """
        Get upcoming NBA games for the next N days.
        """
        pass
    
    @abstractmethod
    async def refresh_game(self, game_id: str) -> Optional[Game]:
        """
        Refresh live data for a specific game.
        """
        pass
