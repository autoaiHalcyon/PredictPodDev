"""
Mock Kalshi Adapter
Simulates Kalshi market data and paper trading.
"""
import random
import asyncio
from typing import List, Optional, Dict
from datetime import datetime
import uuid
import logging

from .interface import KalshiAdapter
from models.market import Market, MarketType, OrderBook, OrderBookLevel
from models.position import Position
from models.trade import Trade, TradeStatus, TradeSide, TradeDirection

logger = logging.getLogger(__name__)

class MockKalshiAdapter(KalshiAdapter):
    """
    Mock Kalshi Adapter for paper trading.
    Simulates realistic market behavior.
    """
    
    def __init__(self, initial_balance: float = 10000.0):
        self.balance = initial_balance
        self.positions: Dict[str, Position] = {}  # market_id -> Position
        self.trades: List[Trade] = []
        self.markets: Dict[str, Market] = {}  # market_id -> Market
        self._game_markets: Dict[str, List[str]] = {}  # game_id -> [market_ids]
    
    # Market Data
    async def get_markets_for_game(self, game_id: str) -> List[Market]:
        """Get or create mock markets for a game"""
        if game_id not in self._game_markets:
            # Create home and away winner markets
            home_market = self._create_mock_market(game_id, "home")
            away_market = self._create_mock_market(game_id, "away")
            
            self.markets[home_market.id] = home_market
            self.markets[away_market.id] = away_market
            self._game_markets[game_id] = [home_market.id, away_market.id]
        
        market_ids = self._game_markets[game_id]
        return [self.markets[mid] for mid in market_ids]
    
    async def get_market(self, market_id: str) -> Optional[Market]:
        """Get a specific market"""
        return self.markets.get(market_id)
    
    async def get_orderbook(self, market_id: str) -> Optional[OrderBook]:
        """Generate a mock orderbook"""
        market = self.markets.get(market_id)
        if not market:
            return None
        
        mid_price = market.yes_price
        spread = 0.02  # 2 cent spread
        
        # Generate realistic orderbook
        bids = [
            OrderBookLevel(price=round(mid_price - spread/2 - i*0.01, 2), 
                          quantity=random.randint(10, 100))
            for i in range(5)
        ]
        asks = [
            OrderBookLevel(price=round(mid_price + spread/2 + i*0.01, 2),
                          quantity=random.randint(10, 100))
            for i in range(5)
        ]
        
        return OrderBook(bids=bids, asks=asks)
    
    async def get_market_price(self, market_id: str) -> Optional[float]:
        """Get current YES price"""
        market = self.markets.get(market_id)
        return market.yes_price if market else None
    
    # Positions
    async def get_positions(self) -> List[Position]:
        """Get all open positions"""
        return [p for p in self.positions.values() if p.is_open]
    
    async def get_position(self, market_id: str) -> Optional[Position]:
        """Get position for a specific market"""
        return self.positions.get(market_id)
    
    # Trading
    async def place_order(
        self,
        market_id: str,
        side: str,
        direction: str,
        quantity: int,
        price: Optional[float] = None
    ) -> Trade:
        """Execute a paper trade"""
        market = self.markets.get(market_id)
        if not market:
            raise ValueError(f"Market {market_id} not found")
        
        # Determine execution price
        if price is None:  # Market order
            if direction == "buy":
                exec_price = market.yes_ask if side == "yes" else (1 - market.yes_bid)
            else:  # sell
                exec_price = market.yes_bid if side == "yes" else (1 - market.yes_ask)
        else:
            exec_price = price
        
        # Calculate cost
        notional = quantity * exec_price
        fees = quantity * 0.01  # $0.01 per contract
        total_cost = notional + fees if direction == "buy" else -notional + fees
        
        # Check balance for buys
        if direction == "buy" and total_cost > self.balance:
            raise ValueError(f"Insufficient balance. Required: ${total_cost:.2f}, Available: ${self.balance:.2f}")
        
        # Create trade
        trade = Trade(
            id=str(uuid.uuid4()),
            game_id=market.game_id,
            market_id=market_id,
            side=TradeSide(side),
            direction=TradeDirection(direction),
            quantity=quantity,
            price=exec_price,
            status=TradeStatus.FILLED,
            filled_quantity=quantity,
            avg_fill_price=exec_price,
            fees=fees,
            is_paper=True,
            executed_at=datetime.utcnow()
        )
        
        # Update balance
        if direction == "buy":
            self.balance -= total_cost
        else:
            self.balance += notional - fees
        
        # Update position
        self._update_position(market, trade)
        
        # Store trade
        self.trades.append(trade)
        
        logger.info(f"Paper trade executed: {direction} {quantity} {side} @ ${exec_price:.2f}")
        
        return trade
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order - in paper mode, all orders fill instantly"""
        return False
    
    async def flatten_position(self, market_id: str) -> List[Trade]:
        """Close all positions in a market"""
        position = self.positions.get(market_id)
        if not position or not position.is_open:
            return []
        
        # Create closing trade
        trade = await self.place_order(
            market_id=market_id,
            side=position.side,
            direction="sell",
            quantity=position.quantity
        )
        
        return [trade]
    
    # Account
    async def get_balance(self) -> float:
        """Get current balance"""
        return self.balance
    
    async def get_portfolio_value(self) -> float:
        """Get total portfolio value"""
        positions_value = sum(
            p.quantity * p.current_price 
            for p in self.positions.values() 
            if p.is_open
        )
        return self.balance + positions_value
    
    def is_paper_mode(self) -> bool:
        return True
    
    # Helper methods
    def _create_mock_market(self, game_id: str, outcome: str) -> Market:
        """Create a mock market with realistic pricing"""
        # Start with ~50/50 odds
        base_price = 0.50 + random.uniform(-0.10, 0.10)
        spread = 0.02
        
        return Market(
            id=f"mock_{game_id}_{outcome}",
            game_id=game_id,
            kalshi_ticker=f"NBA-{game_id.upper()}-{outcome.upper()}",
            market_type=MarketType.WINNER,
            outcome=outcome,
            yes_price=round(base_price, 2),
            no_price=round(1 - base_price, 2),
            yes_bid=round(base_price - spread/2, 2),
            yes_ask=round(base_price + spread/2, 2),
            volume=random.randint(1000, 50000),
            is_active=True
        )
    
    def _update_position(self, market: Market, trade: Trade):
        """Update position after a trade"""
        position = self.positions.get(market.id)
        
        if trade.direction == TradeDirection.BUY:
            if position and position.side == trade.side:
                # Adding to existing position
                total_cost = (position.avg_entry_price * position.quantity + 
                             trade.avg_fill_price * trade.quantity)
                new_quantity = position.quantity + trade.quantity
                position.avg_entry_price = total_cost / new_quantity
                position.quantity = new_quantity
                position.cost_basis += trade.avg_fill_price * trade.quantity
            else:
                # New position
                position = Position(
                    id=str(uuid.uuid4()),
                    game_id=market.game_id,
                    market_id=market.id,
                    side=trade.side,
                    quantity=trade.quantity,
                    avg_entry_price=trade.avg_fill_price,
                    cost_basis=trade.avg_fill_price * trade.quantity,
                    is_paper=True
                )
                self.positions[market.id] = position
        else:  # SELL
            if position:
                if trade.quantity >= position.quantity:
                    # Closing entire position
                    pnl = (trade.avg_fill_price - position.avg_entry_price) * position.quantity
                    if position.side == "no":
                        pnl = -pnl
                    position.realized_pnl += pnl
                    position.quantity = 0
                    position.closed_at = datetime.utcnow()
                else:
                    # Partial close
                    pnl = (trade.avg_fill_price - position.avg_entry_price) * trade.quantity
                    if position.side == "no":
                        pnl = -pnl
                    position.realized_pnl += pnl
                    position.quantity -= trade.quantity
    
    def update_market_prices(self, game_id: str, fair_prob_home: float):
        """
        Update mock market prices based on fair probability.
        Called by the signal engine to simulate market movements.
        """
        if game_id not in self._game_markets:
            return
        
        for market_id in self._game_markets[game_id]:
            market = self.markets[market_id]
            
            # Add some noise to simulate market inefficiency
            noise = random.uniform(-0.05, 0.05)
            
            if market.outcome == "home":
                new_price = max(0.05, min(0.95, fair_prob_home + noise))
            else:
                new_price = max(0.05, min(0.95, (1 - fair_prob_home) + noise))
            
            spread = 0.02
            market.yes_price = round(new_price, 2)
            market.no_price = round(1 - new_price, 2)
            market.yes_bid = round(new_price - spread/2, 2)
            market.yes_ask = round(new_price + spread/2, 2)
            market.volume += random.randint(10, 100)
            market.last_updated = datetime.utcnow()
            
            # Update position PnL
            if market_id in self.positions:
                self.positions[market_id].update_pnl(new_price)
