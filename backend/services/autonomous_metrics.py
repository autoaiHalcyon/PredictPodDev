"""
Autonomous Trading Metrics Service

Tracks system-level metrics for 24-hour autonomous trading:
- Markets evaluated per minute
- Signals generated per minute
- Trades executed per minute
- Capital/Risk utilization
- System health (uptime, memory, CPU)
"""
import asyncio
import logging
import psutil
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque
import json

logger = logging.getLogger(__name__)


@dataclass
class MinuteMetrics:
    """Metrics for a single minute window"""
    timestamp: datetime
    markets_evaluated: int = 0
    signals_generated: int = 0
    trades_executed: int = 0
    capital_utilization_pct: float = 0.0
    risk_utilization_pct: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "markets_evaluated": self.markets_evaluated,
            "signals_generated": self.signals_generated,
            "trades_executed": self.trades_executed,
            "capital_utilization_pct": round(self.capital_utilization_pct, 2),
            "risk_utilization_pct": round(self.risk_utilization_pct, 2)
        }


@dataclass
class SystemHealth:
    """System health metrics"""
    uptime_seconds: float = 0.0
    memory_used_mb: float = 0.0
    memory_percent: float = 0.0
    cpu_percent: float = 0.0
    disk_used_percent: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "uptime_seconds": round(self.uptime_seconds, 0),
            "uptime_formatted": str(timedelta(seconds=int(self.uptime_seconds))),
            "memory_used_mb": round(self.memory_used_mb, 1),
            "memory_percent": round(self.memory_percent, 1),
            "cpu_percent": round(self.cpu_percent, 1),
            "disk_used_percent": round(self.disk_used_percent, 1)
        }


@dataclass
class TradingPerformance:
    """24-hour trading performance summary"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_like_score: float = 0.0
    avg_trade_pnl: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "total_pnl": round(self.total_pnl, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "sharpe_like_score": round(self.sharpe_like_score, 2),
            "avg_trade_pnl": round(self.avg_trade_pnl, 2),
            "best_trade": round(self.best_trade, 2),
            "worst_trade": round(self.worst_trade, 2)
        }


class AutonomousMetricsService:
    """
    Service for tracking 24-hour autonomous trading metrics.
    
    Features:
    - Per-minute metrics tracking
    - Rolling 24-hour window
    - System health monitoring
    - Performance aggregation
    - Audit log persistence
    """
    
    METRICS_RETENTION_HOURS = 24
    AUDIT_LOG_PATH = "/app/logs/autonomous_trading"
    
    def __init__(self, db=None):
        self.db = db
        self.start_time = datetime.now(timezone.utc)
        
        # Per-minute metrics (rolling 24-hour window = 1440 minutes)
        self._minute_metrics: deque = deque(maxlen=1440)
        self._current_minute: Optional[MinuteMetrics] = None
        self._current_minute_start: Optional[datetime] = None
        
        # Aggregate counters
        self._total_markets_evaluated = 0
        self._total_signals_generated = 0
        self._total_trades_executed = 0
        
        # Trade history for performance calc
        self._trade_pnls: List[float] = []
        self._peak_equity: float = 30000.0  # 3 models * $10,000
        self._current_equity: float = 30000.0
        
        # Per-model tracking
        self._model_metrics: Dict[str, Dict] = {
            "model_1": {"trades": 0, "pnl": 0.0, "signals": 0},
            "model_2": {"trades": 0, "pnl": 0.0, "signals": 0}
        }
        
        # Ensure log directory exists
        os.makedirs(self.AUDIT_LOG_PATH, exist_ok=True)
        
        logger.info("AutonomousMetricsService initialized")
    
    def _get_current_minute(self) -> MinuteMetrics:
        """Get or create current minute metrics bucket"""
        now = datetime.now(timezone.utc)
        minute_start = now.replace(second=0, microsecond=0)
        
        if self._current_minute_start != minute_start:
            # Save previous minute if exists
            if self._current_minute:
                self._minute_metrics.append(self._current_minute)
            
            # Start new minute
            self._current_minute = MinuteMetrics(timestamp=minute_start)
            self._current_minute_start = minute_start
        
        return self._current_minute
    
    def record_market_evaluation(self, count: int = 1):
        """Record markets evaluated"""
        metrics = self._get_current_minute()
        metrics.markets_evaluated += count
        self._total_markets_evaluated += count
    
    def record_signal_generated(self, model_id: str, count: int = 1):
        """Record signal generated"""
        metrics = self._get_current_minute()
        metrics.signals_generated += count
        self._total_signals_generated += count
        
        if model_id in self._model_metrics:
            self._model_metrics[model_id]["signals"] += count
    
    def record_trade_executed(self, model_id: str, pnl: float = 0.0):
        """Record trade executed"""
        metrics = self._get_current_minute()
        metrics.trades_executed += 1
        self._total_trades_executed += 1
        self._trade_pnls.append(pnl)
        
        if model_id in self._model_metrics:
            self._model_metrics[model_id]["trades"] += 1
            self._model_metrics[model_id]["pnl"] += pnl
    
    def update_utilization(self, capital_util: float, risk_util: float):
        """Update utilization percentages"""
        metrics = self._get_current_minute()
        metrics.capital_utilization_pct = capital_util
        metrics.risk_utilization_pct = risk_util
    
    def update_equity(self, total_equity: float):
        """Update equity for drawdown calculation"""
        self._current_equity = total_equity
        if total_equity > self._peak_equity:
            self._peak_equity = total_equity
    
    def get_system_health(self) -> SystemHealth:
        """Get current system health metrics"""
        process = psutil.Process()
        
        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        memory_info = process.memory_info()
        
        return SystemHealth(
            uptime_seconds=uptime,
            memory_used_mb=memory_info.rss / (1024 * 1024),
            memory_percent=process.memory_percent(),
            cpu_percent=process.cpu_percent(interval=0.1),
            disk_used_percent=psutil.disk_usage('/').percent
        )
    
    def get_performance_summary(self, strategies: Dict = None) -> TradingPerformance:
        """Calculate 24-hour performance summary"""
        perf = TradingPerformance()
        
        # Get totals from strategies if provided
        if strategies:
            for sid, data in strategies.items():
                portfolio = data.get("portfolio", {})
                perf.realized_pnl += portfolio.get("realized_pnl", 0)
                perf.unrealized_pnl += portfolio.get("unrealized_pnl", 0)
                perf.total_trades += portfolio.get("total_trades", 0)
                perf.winning_trades += portfolio.get("winning_trades", 0)
                perf.losing_trades += portfolio.get("losing_trades", 0)
        
        perf.total_pnl = perf.realized_pnl + perf.unrealized_pnl
        
        # Win rate
        if perf.total_trades > 0:
            perf.win_rate = (perf.winning_trades / perf.total_trades) * 100
            perf.avg_trade_pnl = perf.realized_pnl / perf.total_trades
        
        # Max drawdown
        if self._peak_equity > 0:
            drawdown = self._peak_equity - self._current_equity
            perf.max_drawdown = max(0, drawdown)
            perf.max_drawdown_pct = (drawdown / self._peak_equity) * 100
        
        # Sharpe-like score (simplified)
        if len(self._trade_pnls) >= 10:
            import statistics
            avg_return = statistics.mean(self._trade_pnls)
            std_return = statistics.stdev(self._trade_pnls) if len(self._trade_pnls) > 1 else 1
            perf.sharpe_like_score = (avg_return / std_return * 16) if std_return > 0 else 0
        
        # Best/worst trade
        if self._trade_pnls:
            perf.best_trade = max(self._trade_pnls)
            perf.worst_trade = min(self._trade_pnls)
        
        return perf
    
    def get_minute_metrics(self, last_n_minutes: int = 60) -> List[Dict]:
        """Get last N minutes of metrics"""
        metrics = list(self._minute_metrics)
        if self._current_minute:
            metrics.append(self._current_minute)
        
        return [m.to_dict() for m in metrics[-last_n_minutes:]]
    
    def get_hourly_summary(self) -> List[Dict]:
        """Get hourly aggregated metrics"""
        all_metrics = list(self._minute_metrics)
        if self._current_minute:
            all_metrics.append(self._current_minute)
        
        hourly = {}
        for m in all_metrics:
            hour_key = m.timestamp.replace(minute=0, second=0, microsecond=0)
            if hour_key not in hourly:
                hourly[hour_key] = {
                    "hour": hour_key.isoformat(),
                    "markets_evaluated": 0,
                    "signals_generated": 0,
                    "trades_executed": 0,
                    "avg_capital_util": [],
                    "avg_risk_util": []
                }
            
            hourly[hour_key]["markets_evaluated"] += m.markets_evaluated
            hourly[hour_key]["signals_generated"] += m.signals_generated
            hourly[hour_key]["trades_executed"] += m.trades_executed
            hourly[hour_key]["avg_capital_util"].append(m.capital_utilization_pct)
            hourly[hour_key]["avg_risk_util"].append(m.risk_utilization_pct)
        
        # Calculate averages
        result = []
        for h in sorted(hourly.values(), key=lambda x: x["hour"]):
            h["avg_capital_util"] = sum(h["avg_capital_util"]) / len(h["avg_capital_util"]) if h["avg_capital_util"] else 0
            h["avg_risk_util"] = sum(h["avg_risk_util"]) / len(h["avg_risk_util"]) if h["avg_risk_util"] else 0
            result.append(h)
        
        return result
    
    def get_model_breakdown(self) -> Dict:
        """Get per-model metrics breakdown"""
        return self._model_metrics
    
    def get_full_dashboard(self, strategies: Dict = None) -> Dict:
        """Get complete 24-hour dashboard data"""
        return {
            "system_health": self.get_system_health().to_dict(),
            "performance": self.get_performance_summary(strategies).to_dict(),
            "totals": {
                "markets_evaluated": self._total_markets_evaluated,
                "signals_generated": self._total_signals_generated,
                "trades_executed": self._total_trades_executed
            },
            "per_model": self.get_model_breakdown(),
            "recent_minutes": self.get_minute_metrics(last_n_minutes=10),
            "hourly_summary": self.get_hourly_summary()
        }
    
    async def persist_audit_log(self, entry: Dict):
        """Persist audit log entry to file and DB"""
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        # Write to file
        log_file = os.path.join(
            self.AUDIT_LOG_PATH,
            f"audit_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
        )
        
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
        
        # Write to DB if available
        if self.db is not None:
            try:
                await self.db.autonomous_audit_log.insert_one(entry)
            except Exception as e:
                logger.error(f"Failed to persist audit to DB: {e}")
    
    async def log_market_evaluation(self, game_id: str, markets_count: int, details: Dict = None):
        """Log market evaluation event"""
        self.record_market_evaluation(markets_count)
        
        await self.persist_audit_log({
            "event_type": "MARKET_EVALUATION",
            "game_id": game_id,
            "markets_count": markets_count,
            "details": details or {}
        })
    
    async def log_signal_generated(self, model_id: str, game_id: str, signal_type: str, details: Dict = None):
        """Log signal generation event"""
        self.record_signal_generated(model_id)
        
        await self.persist_audit_log({
            "event_type": "SIGNAL_GENERATED",
            "model_id": model_id,
            "game_id": game_id,
            "signal_type": signal_type,
            "details": details or {}
        })
    
    async def log_trade_executed(self, model_id: str, game_id: str, market_id: str, 
                                  side: str, quantity: int, price: float, pnl: float = 0.0):
        """Log trade execution event"""
        self.record_trade_executed(model_id, pnl)
        
        await self.persist_audit_log({
            "event_type": "TRADE_EXECUTED",
            "model_id": model_id,
            "game_id": game_id,
            "market_id": market_id,
            "side": side,
            "quantity": quantity,
            "price": price,
            "pnl": pnl
        })
    
    async def log_risk_event(self, model_id: str, event_type: str, details: Dict):
        """Log risk-related event"""
        await self.persist_audit_log({
            "event_type": f"RISK_{event_type}",
            "model_id": model_id,
            "details": details
        })


# Global instance
autonomous_metrics: Optional[AutonomousMetricsService] = None
