"""
Strategy Engine Manager

Orchestrates multiple trading strategies running in parallel.
- Single feed, broadcast to all strategies
- Independent execution per strategy
- Aggregated dashboard data
- Kill switch control
"""
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, date, timedelta
from pathlib import Path
import asyncio
import json
import logging

from models.game import Game
from models.market import Market
from models.signal import Signal
from strategies.base_strategy import BaseStrategy, StrategyConfig, StrategyDecision, DecisionType
from strategies.model_1_enhanced_clv import Model1EnhancedCLV
from strategies.model_2_strong_favorite import Model2StrongFavorite

logger = logging.getLogger(__name__)

# Config directory
CONFIG_DIR = Path(__file__).parent / "configs"


class StrategyEngineManager:
    """
    Manages multiple trading strategies running in parallel.
    
    Features:
    - Single market feed, broadcast to all strategies
    - Independent virtual portfolios per strategy
    - Aggregated dashboard metrics
    - Global kill switch
    - Daily evaluation reports
    """
    
    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {}
        self._enabled = False
        self._kill_switch_active = False
        self._evaluation_mode = True
        
        # Decision loop timing
        self._last_tick_time: Optional[datetime] = None
        self._tick_interval_seconds = 3  # Process every 3 seconds
        
        # Daily reports
        self._daily_reports: Dict[str, Dict] = {}
        
        # Load strategies
        self._load_strategies()
        
        logger.info("StrategyEngineManager initialized")
    
    def _load_strategies(self):
        """
        Load the 2-model system per Master Rules v2.0.

        Model 1: Enhanced CLV    — $700 allocation (70%)
        Model 2: Strong Favorite — $300 allocation (30%)

        No other models. No deviations.
        """
        strategy_configs = [
            ("model_1_enhanced_clv",    Model1EnhancedCLV),
            ("model_2_strong_favorite", Model2StrongFavorite),
        ]

        for config_name, strategy_class in strategy_configs:
            config_path = CONFIG_DIR / f"{config_name}.json"

            if config_path.exists():
                try:
                    config = StrategyConfig(str(config_path))
                    if not config.enabled:
                        logger.info(f"Skipping disabled strategy: {config.display_name}")
                        continue
                    strategy = strategy_class(config)
                    self.strategies[config.model_id] = strategy
                    logger.info(f"Loaded strategy: {config.display_name}")
                except Exception as e:
                    logger.error(f"Failed to load strategy {config_name}: {e}")
            else:
                logger.warning(f"Config not found: {config_path}")
    
    # ==========================================
    # CONTROL METHODS
    # ==========================================
    
    def enable(self):
        """Enable the strategy engine."""
        self._enabled = True
        for strategy in self.strategies.values():
            strategy.enable()
        logger.info("Strategy Engine ENABLED")
    
    def disable(self):
        """Disable the strategy engine."""
        self._enabled = False
        for strategy in self.strategies.values():
            strategy.disable()
        logger.info("Strategy Engine DISABLED")
    
    def activate_kill_switch(self):
        """Activate global kill switch - stops all strategies."""
        self._kill_switch_active = True
        self.disable()
        logger.warning("KILL SWITCH ACTIVATED - All strategies stopped")
    
    def deactivate_kill_switch(self):
        """Deactivate kill switch."""
        self._kill_switch_active = False
        logger.info("Kill switch deactivated")
    
    def set_evaluation_mode(self, enabled: bool):
        """Enable/disable evaluation mode."""
        self._evaluation_mode = enabled
        if enabled:
            self.enable()
            logger.info("Evaluation Mode ENABLED - All strategies running")
        else:
            logger.info("Evaluation Mode DISABLED")
    
    @property
    def is_enabled(self) -> bool:
        return self._enabled and not self._kill_switch_active
    
    @property
    def is_kill_switch_active(self) -> bool:
        return self._kill_switch_active
    
    # ==========================================
    # TICK PROCESSING
    # ==========================================
    
    async def process_tick(
        self,
        game: Game,
        market: Market,
        signal: Signal,
        orderbook: Optional[Dict] = None
    ) -> Dict[str, Optional[StrategyDecision]]:
        """
        Process a market tick across all strategies.
        
        This is the main entry point - receives single feed,
        broadcasts to all strategies.
        
        Returns dict of strategy_id -> decision
        """
        if not self.is_enabled:
            return {}
        
        self._last_tick_time = datetime.utcnow()
        
        decisions = {}
        
        # Process each strategy in parallel (but independent)
        for strategy_id, strategy in self.strategies.items():
            try:
                decision = strategy.process_tick(game, market, signal, orderbook)
                decisions[strategy_id] = decision
            except Exception as e:
                logger.error(f"Strategy {strategy_id} error: {e}")
                decisions[strategy_id] = None
        
        return decisions
    
    async def process_batch(
        self,
        ticks: List[Dict]  # List of {game, market, signal, orderbook}
    ) -> Dict[str, List[StrategyDecision]]:
        """
        Process multiple ticks (for multiple games).
        """
        all_decisions = {sid: [] for sid in self.strategies.keys()}
        
        for tick in ticks:
            decisions = await self.process_tick(
                game=tick.get("game"),
                market=tick.get("market"),
                signal=tick.get("signal"),
                orderbook=tick.get("orderbook")
            )
            
            for sid, decision in decisions.items():
                if decision and decision.decision_type != DecisionType.HOLD:
                    all_decisions[sid].append(decision)
        
        return all_decisions
    
    def update_position_prices(self, market_id: str, current_price: float):
        """Update position prices across all strategies."""
        for strategy in self.strategies.values():
            strategy.portfolio.update_position_price(market_id, current_price)
    
    # ==========================================
    # DASHBOARD DATA
    # ==========================================
    
    def get_summary(self) -> Dict:
        """Get aggregated summary for dashboard."""
        summaries = {}
        
        for strategy_id, strategy in self.strategies.items():
            summaries[strategy_id] = strategy.get_summary()
        
        # Find winning model
        pnls = [(sid, s["portfolio"]["total_pnl"]) for sid, s in summaries.items()]
        pnls_sorted = sorted(pnls, key=lambda x: x[1], reverse=True)
        
        winning_model = pnls_sorted[0][0] if pnls_sorted else None
        
        # Risk-adjusted winner (PnL / max_drawdown)
        risk_adjusted = []
        for sid, s in summaries.items():
            pnl = s["portfolio"]["total_pnl"]
            dd = max(s["portfolio"]["max_drawdown"], 1)  # Avoid div by 0
            risk_adjusted.append((sid, pnl / dd))
        risk_adjusted_sorted = sorted(risk_adjusted, key=lambda x: x[1], reverse=True)
        best_risk_adjusted = risk_adjusted_sorted[0][0] if risk_adjusted_sorted else None
        
        return {
            "enabled": self._enabled,
            "kill_switch_active": self._kill_switch_active,
            "evaluation_mode": self._evaluation_mode,
            "last_tick": self._last_tick_time.isoformat() if self._last_tick_time else None,
            "strategies": summaries,
            "winning_model": winning_model,
            "best_risk_adjusted": best_risk_adjusted,
            "comparison": self._build_comparison_table(summaries)
        }
    
    def _build_comparison_table(self, summaries: Dict) -> Dict:
        """Build side-by-side comparison data."""
        metrics = [
            "total_pnl", "realized_pnl", "unrealized_pnl",
            "total_trades", "win_rate", "avg_edge_entry",
            "max_drawdown_pct", "risk_utilization"
        ]
        
        comparison = {}
        for metric in metrics:
            comparison[metric] = {}
            for sid, s in summaries.items():
                value = s["portfolio"].get(metric, 0)
                comparison[metric][sid] = value
        
        return comparison
    
    def get_game_positions(self, game_id: str) -> Dict[str, List[Dict]]:
        """Get positions for a specific game across all strategies."""
        positions = {}
        
        for strategy_id, strategy in self.strategies.items():
            game_positions = strategy.portfolio.get_positions_for_game(game_id)
            positions[strategy_id] = [p.to_dict() for p in game_positions]
        
        return positions
    
    def get_all_positions_by_game(self) -> Dict[str, Dict]:
        """Get all positions organized by game for dashboard."""
        games = {}
        
        for strategy_id, strategy in self.strategies.items():
            for pos in strategy.portfolio.get_all_positions():
                if pos.game_id not in games:
                    games[pos.game_id] = {}
                
                games[pos.game_id][strategy_id] = {
                    "has_position": True,
                    "side": pos.side,
                    "quantity": pos.quantity,
                    "entry_price": pos.avg_entry_price,
                    "current_price": pos.current_price,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "status": "HOLD"
                }
        
        # Fill in strategies without positions
        for game_id in games:
            for strategy_id in self.strategies:
                if strategy_id not in games[game_id]:
                    games[game_id][strategy_id] = {
                        "has_position": False,
                        "side": None,
                        "quantity": 0,
                        "entry_price": 0,
                        "current_price": 0,
                        "unrealized_pnl": 0,
                        "status": "FLAT"
                    }
        
        return games
    
    # ==========================================
    # DECISION LOGS
    # ==========================================
    
    def get_decision_logs(self, limit: int = 100) -> Dict[str, List[Dict]]:
        """Get decision logs for all strategies."""
        logs = {}
        for strategy_id, strategy in self.strategies.items():
            logs[strategy_id] = strategy.get_decision_log(limit)
        return logs
    
    # ==========================================
    # DAILY REPORTS
    # ==========================================
    
    def generate_daily_report(self, date_str: Optional[str] = None) -> Dict:
        """Generate daily evaluation report."""
        if date_str is None:
            date_str = date.today().isoformat()
        
        report = {
            "date": date_str,
            "generated_at": datetime.utcnow().isoformat(),
            "strategies": {}
        }
        
        for strategy_id, strategy in self.strategies.items():
            daily_stats = strategy.portfolio.get_daily_stats(date_str)
            league_stats = strategy.portfolio.get_stats_by_league()
            
            # Calculate profit factor
            winners_pnl = sum(
                t.pnl for t in strategy.portfolio._trades 
                if t.direction == "sell" and t.is_winner
            )
            losers_pnl = abs(sum(
                t.pnl for t in strategy.portfolio._trades 
                if t.direction == "sell" and not t.is_winner
            ))
            profit_factor = winners_pnl / losers_pnl if losers_pnl > 0 else 0.0
            
            report["strategies"][strategy_id] = {
                "display_name": strategy.display_name,
                "daily_stats": daily_stats,
                "total_pnl": strategy.portfolio.total_pnl,
                "max_drawdown": strategy.portfolio.max_drawdown,
                "max_drawdown_pct": strategy.portfolio.max_drawdown_pct,
                "win_rate": strategy.portfolio.win_rate,
                "profit_factor": round(profit_factor, 2),
                "avg_edge_entry": strategy.portfolio.avg_edge_at_entry,
                "avg_edge_exit": strategy.portfolio.avg_edge_at_exit,
                "by_league": league_stats,
                "trades_today": daily_stats.get("trades", 0)
            }
        
        # Store for export
        self._daily_reports[date_str] = report
        
        return report
    
    def export_daily_report_json(self, date_str: Optional[str] = None) -> str:
        """Export daily report as JSON."""
        if date_str is None:
            date_str = date.today().isoformat()
        
        if date_str not in self._daily_reports:
            self.generate_daily_report(date_str)
        
        return json.dumps(self._daily_reports[date_str], indent=2)
    
    def export_daily_report_csv(self, date_str: Optional[str] = None) -> str:
        """Export daily report as CSV."""
        if date_str is None:
            date_str = date.today().isoformat()
        
        if date_str not in self._daily_reports:
            self.generate_daily_report(date_str)
        
        report = self._daily_reports[date_str]
        
        # Build CSV
        headers = [
            "strategy_id", "display_name", "pnl", "max_drawdown",
            "win_rate", "profit_factor", "trades", "avg_edge_entry"
        ]
        lines = [",".join(headers)]
        
        for sid, data in report["strategies"].items():
            row = [
                sid,
                data["display_name"],
                str(round(data["total_pnl"], 2)),
                str(round(data["max_drawdown"], 2)),
                str(round(data["win_rate"], 1)),
                str(data["profit_factor"]),
                str(data["trades_today"]),
                str(round(data["avg_edge_entry"] * 100, 2))
            ]
            lines.append(",".join(row))
        
        return "\n".join(lines)
    
    # ==========================================
    # PORTFOLIO MANAGEMENT
    # ==========================================
    
    def reset_strategy(self, strategy_id: str, starting_capital: Optional[float] = None):
        """Reset a specific strategy's portfolio."""
        if strategy_id in self.strategies:
            self.strategies[strategy_id].reset_portfolio(starting_capital)
            logger.info(f"Strategy {strategy_id} portfolio reset")
    
    def reset_all_strategies(self):
        """Reset all strategy portfolios."""
        for strategy in self.strategies.values():
            strategy.reset_portfolio()
        logger.info("All strategy portfolios reset")
    
    def export_trades_csv(self, strategy_id: str) -> str:
        """Export trades for a specific strategy."""
        if strategy_id in self.strategies:
            return self.strategies[strategy_id].portfolio.export_trades_csv()
        return ""
    
    def export_trades_json(self, strategy_id: str) -> str:
        """Export trades for a specific strategy."""
        if strategy_id in self.strategies:
            return self.strategies[strategy_id].portfolio.export_trades_json()
        return "[]"
    
    # ==========================================
    # CONFIGURATION
    # ==========================================
    
    def reload_configs(self):
        """Reload all strategy configurations."""
        for strategy in self.strategies.values():
            strategy.config.reload()
        logger.info("All strategy configs reloaded")
    
    def get_strategy_config(self, strategy_id: str) -> Optional[Dict]:
        """Get config for a specific strategy."""
        if strategy_id in self.strategies:
            return self.strategies[strategy_id].config._config
        return None
    
    def update_strategy_config(self, strategy_id: str, updates: Dict) -> bool:
        """Update strategy config (runtime only, doesn't persist)."""
        if strategy_id not in self.strategies:
            return False
        
        config = self.strategies[strategy_id].config._config
        
        # Deep merge updates
        def deep_merge(base: Dict, updates: Dict):
            for key, value in updates.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value
        
        deep_merge(config, updates)
        logger.info(f"Strategy {strategy_id} config updated (runtime)")
        
        return True


# Global instance
strategy_manager = StrategyEngineManager()
