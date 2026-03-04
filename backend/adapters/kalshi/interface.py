"""
Kalshi Adapter Interface
Abstract interface for Kalshi market data and trading.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from models.market import Market, OrderBook
from models.position import Position
from models.trade import Trade

class KalshiAdapter(ABC):
    """
    Abstract interface for Kalshi API.
    Implement MockKalshiAdapter for paper trading,
    RealKalshiAdapter for live trading.
    """
    
    # Market Data
    @abstractmethod
    async def get_markets_for_game(self, game_id: str) -> List[Market]:
        """Get all Kalshi markets for a specific game"""
        pass
    
    @abstractmethod
    async def get_market(self, market_id: str) -> Optional[Market]:
        """Get a specific market by ID"""
        pass
    
    @abstractmethod
    async def get_orderbook(self, market_id: str) -> Optional[OrderBook]:
        """Get the orderbook for a market"""
        pass
    
    @abstractmethod
    async def get_market_price(self, market_id: str) -> Optional[float]:
        """Get current YES price for a market"""
        pass
    
    # Positions
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """Get all open positions"""
        pass
    
    @abstractmethod
    async def get_position(self, market_id: str) -> Optional[Position]:
        """Get position for a specific market"""
        pass
    
    # Trading
    @abstractmethod
    async def place_order(
        self,
        market_id: str,
        side: str,  # "yes" or "no"
        direction: str,  # "buy" or "sell"
        quantity: int,
        price: Optional[float] = None  # None for market order
    ) -> Trade:
        """Place a trade order"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order"""
        pass
    
    @abstractmethod
    async def flatten_position(self, market_id: str) -> List[Trade]:
        """Close all positions in a market (panic button)"""
        pass
    
    # Account
    @abstractmethod
    async def get_balance(self) -> float:
        """Get account balance"""
        pass
    
    @abstractmethod
    async def get_portfolio_value(self) -> float:
        """Get total portfolio value (balance + positions)"""
        pass
    
    # Utility
    @abstractmethod
    def is_paper_mode(self) -> bool:
        """Whether this adapter is in paper trading mode"""
        pass
