"""
Market Model - Represents a Kalshi prediction market.
"""
from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field
import uuid

class MarketType(str, Enum):
    WINNER = "winner"  # Who wins the game
    SPREAD = "spread"  # Point spread (future)
    TOTAL = "total"  # Over/under (future)

class OrderBookLevel(BaseModel):
    price: float  # 0.00 - 1.00
    quantity: int  # Number of contracts

class OrderBook(BaseModel):
    bids: List[OrderBookLevel] = []  # Buy orders (highest first)
    asks: List[OrderBookLevel] = []  # Sell orders (lowest first)
    
    @property
    def best_bid(self) -> Optional[float]:
        return self.bids[0].price if self.bids else None
    
    @property
    def best_ask(self) -> Optional[float]:
        return self.asks[0].price if self.asks else None
    
    @property
    def spread(self) -> Optional[float]:
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None

class Market(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    game_id: str
    kalshi_ticker: Optional[str] = None  # e.g., "NBA-LAL-LAC-WIN"
    
    market_type: MarketType = MarketType.WINNER
    outcome: str  # "home" or "away" for winner markets
    
    # Current prices (0.00 - 1.00, representing probability)
    yes_price: float = 0.50  # Price to buy YES
    no_price: float = 0.50   # Price to buy NO (typically 1 - yes_price)
    
    # Order book
    yes_bid: float = 0.49    # Best bid for YES
    yes_ask: float = 0.51    # Best ask for YES
    orderbook: Optional[OrderBook] = None
    
    # Volume and liquidity
    volume: int = 0  # Total contracts traded
    open_interest: int = 0  # Outstanding contracts
    
    # Status
    is_active: bool = True
    settled: bool = False
    settlement_value: Optional[float] = None  # 1.0 if YES wins, 0.0 if NO wins
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def implied_probability(self) -> float:
        """Market implied probability from YES price"""
        return self.yes_price
    
    @property
    def mid_price(self) -> float:
        """Mid price between bid and ask"""
        return (self.yes_bid + self.yes_ask) / 2

    @property
    def spread(self) -> float:
        """Bid-ask spread (yes_ask - yes_bid)"""
        return round(self.yes_ask - self.yes_bid, 6)

    def to_dict(self) -> dict:
        return {
            **self.dict(),
            'implied_probability': self.implied_probability,
            'mid_price': self.mid_price
        }
