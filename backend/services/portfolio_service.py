"""
Portfolio Service
Manages portfolio tracking and performance metrics.
"""
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging

from models.position import Position
from models.trade import Trade
from adapters.kalshi import KalshiAdapter
from repositories import PositionRepository, TradeRepository

logger = logging.getLogger(__name__)

class PortfolioService:
    """
    Provides portfolio overview and performance metrics.
    """
    
    def __init__(
        self,
        kalshi_adapter: KalshiAdapter,
        position_repo: PositionRepository,
        trade_repo: TradeRepository
    ):
        self.kalshi = kalshi_adapter
        self.position_repo = position_repo
        self.trade_repo = trade_repo
    
    async def get_portfolio_summary(self) -> Dict:
        """
        Get a summary of the current portfolio.
        """
        positions = await self.kalshi.get_positions()
        balance = await self.kalshi.get_balance()
        portfolio_value = await self.kalshi.get_portfolio_value()
        
        # Calculate totals
        total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)
        total_realized_pnl = sum(p.realized_pnl for p in positions)
        total_exposure = sum(p.cost_basis for p in positions if p.is_open)
        
        # Get today's trades
        trades_today = await self.trade_repo.get_trades_today()
        
        return {
            "balance": round(balance, 2),
            "portfolio_value": round(portfolio_value, 2),
            "total_exposure": round(total_exposure, 2),
            "unrealized_pnl": round(total_unrealized_pnl, 2),
            "realized_pnl": round(total_realized_pnl, 2),
            "total_pnl": round(total_unrealized_pnl + total_realized_pnl, 2),
            "open_positions": len([p for p in positions if p.is_open]),
            "trades_today": len(trades_today),
            "is_paper_mode": self.kalshi.is_paper_mode(),
            "updated_at": datetime.utcnow().isoformat()
        }
    
    async def get_positions(self) -> List[Dict]:
        """
        Get all current positions with enriched data.
        """
        positions = await self.kalshi.get_positions()
        return [p.to_dict() for p in positions]
    
    async def get_position_by_game(self, game_id: str) -> List[Dict]:
        """
        Get positions for a specific game.
        """
        positions = await self.kalshi.get_positions()
        game_positions = [p for p in positions if p.game_id == game_id]
        return [p.to_dict() for p in game_positions]
    
    async def get_trades_history(
        self,
        limit: int = 50,
        game_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Get trade history.
        """
        if game_id:
            trades = await self.trade_repo.get_by_game_id(game_id)
        else:
            trades = await self.trade_repo.get_all(limit=limit)
        
        return [t.to_dict() for t in trades]
    
    async def get_performance_metrics(self, days: int = 30) -> Dict:
        """
        Calculate performance metrics over a time period.
        """
        # Get all trades in the period
        trades = await self.trade_repo.get_all(limit=1000)
        
        if not trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "avg_edge_captured": 0
            }
        
        # Calculate metrics
        # Note: In paper trading, we track PnL differently
        winning_trades = [t for t in trades if getattr(t, 'realized_pnl', 0) > 0]
        losing_trades = [t for t in trades if getattr(t, 'realized_pnl', 0) < 0]
        
        total_wins = sum(getattr(t, 'realized_pnl', 0) for t in winning_trades)
        total_losses = abs(sum(getattr(t, 'realized_pnl', 0) for t in losing_trades))
        
        avg_edge = sum(getattr(t, 'edge_at_entry', 0) or 0 for t in trades) / len(trades) if trades else 0
        
        return {
            "total_trades": len(trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": round(len(winning_trades) / len(trades) * 100, 1) if trades else 0,
            "total_pnl": round(total_wins - total_losses, 2),
            "avg_win": round(total_wins / len(winning_trades), 2) if winning_trades else 0,
            "avg_loss": round(total_losses / len(losing_trades), 2) if losing_trades else 0,
            "profit_factor": round(total_wins / total_losses, 2) if total_losses > 0 else 0,
            "avg_edge_captured": round(avg_edge * 100, 2)
        }
    
    async def get_exposure_by_game(self) -> Dict[str, float]:
        """
        Get exposure breakdown by game.
        """
        positions = await self.kalshi.get_positions()
        exposure = {}
        
        for p in positions:
            if p.is_open:
                if p.game_id not in exposure:
                    exposure[p.game_id] = 0
                exposure[p.game_id] += p.cost_basis
        
        return exposure
