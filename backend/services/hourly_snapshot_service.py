"""
Automated Hourly Metrics Snapshot Service

Captures and persists system metrics every hour during 24-hour unattended runs:
- Timestamp
- CPU, Memory, Uptime
- Scheduler ticks (strategy + discovery)
- Scanned counts (events, markets)
- Open market counts
- Trades executed
- P&L (realized, unrealized, total)
- Safe mode state (kill switch, autonomous enabled)
"""
import asyncio
import json
import logging
import os
import psutil
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

SNAPSHOTS_DIR = "/app/logs/metrics_snapshots"


@dataclass
class MetricSnapshot:
    """Hourly metric snapshot data structure"""
    # Timestamp
    timestamp: str
    hour_number: int  # 1-24 during 24h run
    
    # System Health
    cpu_percent: float
    memory_used_mb: float
    memory_percent: float
    disk_percent: float
    uptime_sec: int
    
    # Scheduler Heartbeat
    autonomous_enabled: bool
    strategy_loop_ticks_total: int
    strategy_loop_last_tick_at: Optional[str]
    discovery_loop_ticks_total: int
    discovery_loop_last_tick_at: Optional[str]
    scheduler_status: str
    
    # Scanning Metrics
    events_scanned_last_min: int
    markets_scanned_last_min: int
    events_next_24h_count: int
    markets_next_24h_count: int
    open_markets_found_last_min: int
    open_events_found_last_min: int
    
    # Filter Metrics
    filter_pass_rate_pct: float
    filtered_out_reason_counts: Dict[str, int]
    
    # Trading Activity
    total_trades_executed: int
    trades_this_hour: int
    signals_generated: int
    markets_evaluated: int
    
    # P&L
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    max_drawdown: float
    max_drawdown_pct: float
    
    # Per-Model Breakdown
    model_1_pnl: float
    model_1_trades: int
    model_2_pnl: float
    model_2_trades: int
    
    # Safe Mode State
    kill_switch_active: bool
    paper_trading_mode: bool
    
    # WebSocket
    ws_connections: int
    db_ping: bool
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class HourlyMetricsSnapshotService:
    """
    Service to capture hourly metric snapshots during 24-hour unattended runs.
    
    Features:
    - Hourly snapshots saved to JSON files
    - Rolling 24-hour summary
    - CSV export for analysis
    - Memory-efficient (only stores current + summary)
    """
    
    SNAPSHOT_INTERVAL_SECONDS = 3600  # 1 hour
    
    def __init__(self, db=None, scheduler=None, metrics_service=None, strategy_manager=None):
        self.db = db
        self.scheduler = scheduler
        self.metrics_service = metrics_service
        self.strategy_manager = strategy_manager
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._start_time: Optional[datetime] = None
        self._hour_number = 0
        self._last_trades_count = 0
        
        # Ensure directory exists
        os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
        
        logger.info(f"HourlyMetricsSnapshotService initialized. Saving to: {SNAPSHOTS_DIR}")
    
    async def start(self):
        """Start the hourly snapshot service"""
        if self._running:
            logger.warning("Snapshot service already running")
            return
        
        self._running = True
        self._start_time = datetime.now(timezone.utc)
        self._hour_number = 0
        
        # Take initial snapshot asynchronously so it doesn't block the HTTP response
        async def _initial_snapshot():
            try:
                await self._take_snapshot()
            except Exception as e:
                logger.error(f"Initial snapshot failed: {e}")
        
        asyncio.create_task(_initial_snapshot())
        
        # Start hourly loop
        self._task = asyncio.create_task(self._snapshot_loop())
        
        logger.info("Hourly metrics snapshot service started")
    
    async def stop(self):
        """Stop the snapshot service"""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        # Take final snapshot
        await self._take_snapshot(is_final=True)
        
        # Generate summary report
        await self._generate_summary_report()
        
        logger.info("Hourly metrics snapshot service stopped")
    
    async def _snapshot_loop(self):
        """Main loop that takes snapshots every hour"""
        while self._running:
            try:
                await asyncio.sleep(self.SNAPSHOT_INTERVAL_SECONDS)
                await self._take_snapshot()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Snapshot loop error: {e}")
    
    async def _take_snapshot(self, is_final: bool = False):
        """Take a single metric snapshot"""
        self._hour_number += 1
        now = datetime.now(timezone.utc)
        
        # Get system metrics
        process = psutil.Process()
        
        # Calculate uptime
        uptime_sec = 0
        if self._start_time:
            uptime_sec = int((now - self._start_time).total_seconds())
        
        # Get scheduler metrics
        autonomous_enabled = False
        strategy_loop_ticks = 0
        strategy_loop_last_tick = None
        discovery_loop_ticks = 0
        discovery_loop_last_tick = None
        scheduler_status = "not_running"
        
        if self.scheduler:
            autonomous_enabled = self.scheduler._running
            hb = self.scheduler.heartbeat
            strategy_loop_ticks = hb.trading_loop_ticks_total
            strategy_loop_last_tick = hb.trading_loop_last_tick_at.isoformat() if hb.trading_loop_last_tick_at else None
            discovery_loop_ticks = hb.discovery_loop_ticks_total
            discovery_loop_last_tick = hb.discovery_loop_last_tick_at.isoformat() if hb.discovery_loop_last_tick_at else None
            scheduler_status = hb.scheduler_status
        
        # Get scanning metrics
        events_scanned = 0
        markets_scanned = 0
        events_next_24h = 0
        markets_next_24h = 0
        open_markets = 0
        open_events = 0
        filter_pass_rate = 0.0
        filtered_counts = {}
        
        if self.scheduler:
            scanning = self.scheduler.scanning
            events_scanned = scanning.events_scanned_last_min
            markets_scanned = scanning.markets_scanned_last_min
            events_next_24h = scanning.events_next_24h_count
            markets_next_24h = scanning.markets_next_24h_count
            open_markets = scanning.open_markets_found_last_min
            open_events = scanning.open_events_found_last_min
            
            filters = self.scheduler.filters
            filter_pass_rate = round((filters.passed_filter_count / filters.total_evaluated * 100) if filters.total_evaluated > 0 else 0, 1)
            filtered_counts = dict(filters.filtered_out_counts)
        
        # Get trading activity
        total_trades = 0
        signals_generated = 0
        markets_evaluated = 0
        
        if self.metrics_service:
            total_trades = self.metrics_service._total_trades_executed
            signals_generated = self.metrics_service._total_signals_generated
            markets_evaluated = self.metrics_service._total_markets_evaluated
        
        trades_this_hour = total_trades - self._last_trades_count
        self._last_trades_count = total_trades
        
        # Get P&L from strategies
        realized_pnl = 0.0
        unrealized_pnl = 0.0
        total_pnl = 0.0
        max_drawdown = 0.0
        max_drawdown_pct = 0.0
        
        model_1_pnl = 0.0
        model_1_trades = 0
        model_2_pnl = 0.0
        model_2_trades = 0
        
        kill_switch_active = False
        
        if self.strategy_manager:
            summary = self.strategy_manager.get_summary()
            kill_switch_active = summary.get("kill_switch_active", False)
            
            for sid, data in summary.get("strategies", {}).items():
                portfolio = data.get("portfolio", {})
                realized_pnl += portfolio.get("realized_pnl", 0)
                unrealized_pnl += portfolio.get("unrealized_pnl", 0)
                
                if "model_1" in sid.lower():
                    model_1_pnl = portfolio.get("total_pnl", 0)
                    model_1_trades = portfolio.get("total_trades", 0)
                elif "model_2" in sid.lower():
                    model_2_pnl = portfolio.get("total_pnl", 0)
                    model_2_trades = portfolio.get("total_trades", 0)
        
        total_pnl = realized_pnl + unrealized_pnl
        
        # Get performance metrics for drawdown
        if self.metrics_service:
            perf = self.metrics_service.get_performance_summary(
                self.strategy_manager.get_summary().get("strategies", {}) if self.strategy_manager else {}
            )
            max_drawdown = perf.max_drawdown
            max_drawdown_pct = perf.max_drawdown_pct
        
        # DB ping
        db_ping = False
        try:
            if self.db is not None:
                await self.db.command("ping")
                db_ping = True
        except Exception:
            pass
        
        # Create snapshot
        snapshot = MetricSnapshot(
            timestamp=now.isoformat(),
            hour_number=self._hour_number if not is_final else -1,
            
            cpu_percent=process.cpu_percent(interval=0.1),
            memory_used_mb=process.memory_info().rss / (1024 * 1024),
            memory_percent=process.memory_percent(),
            disk_percent=psutil.disk_usage('/').percent,
            uptime_sec=uptime_sec,
            
            autonomous_enabled=autonomous_enabled,
            strategy_loop_ticks_total=strategy_loop_ticks,
            strategy_loop_last_tick_at=strategy_loop_last_tick,
            discovery_loop_ticks_total=discovery_loop_ticks,
            discovery_loop_last_tick_at=discovery_loop_last_tick,
            scheduler_status=scheduler_status,
            
            events_scanned_last_min=events_scanned,
            markets_scanned_last_min=markets_scanned,
            events_next_24h_count=events_next_24h,
            markets_next_24h_count=markets_next_24h,
            open_markets_found_last_min=open_markets,
            open_events_found_last_min=open_events,
            
            filter_pass_rate_pct=filter_pass_rate,
            filtered_out_reason_counts=filtered_counts,
            
            total_trades_executed=total_trades,
            trades_this_hour=trades_this_hour,
            signals_generated=signals_generated,
            markets_evaluated=markets_evaluated,
            
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_pnl=total_pnl,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            
            model_1_pnl=model_1_pnl,
            model_1_trades=model_1_trades,
            model_2_pnl=model_2_pnl,
            model_2_trades=model_2_trades,
            
            kill_switch_active=kill_switch_active,
            paper_trading_mode=True,  # Always paper in current deployment
            
            ws_connections=0,  # Would need ws_manager reference
            db_ping=db_ping
        )
        
        # Save to file
        filename = f"snapshot_hour_{self._hour_number:02d}_{now.strftime('%Y%m%d_%H%M%S')}.json"
        if is_final:
            filename = f"snapshot_final_{now.strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = os.path.join(SNAPSHOTS_DIR, filename)
        
        try:
            with open(filepath, 'w') as f:
                f.write(snapshot.to_json())
            logger.info(f"Snapshot saved: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
        
        # Also save to DB if available
        if self.db is not None:
            try:
                await self.db.metrics_snapshots.insert_one(snapshot.to_dict())
            except Exception as e:
                logger.error(f"Failed to persist snapshot to DB: {e}")
        
        return snapshot
    
    async def _generate_summary_report(self):
        """Generate a summary report of all snapshots"""
        try:
            # Read all snapshot files
            snapshots = []
            for filename in sorted(os.listdir(SNAPSHOTS_DIR)):
                if filename.startswith("snapshot_") and filename.endswith(".json"):
                    filepath = os.path.join(SNAPSHOTS_DIR, filename)
                    with open(filepath, 'r') as f:
                        snapshots.append(json.load(f))
            
            if not snapshots:
                return
            
            # Calculate summary stats
            cpu_values = [s["cpu_percent"] for s in snapshots]
            memory_values = [s["memory_percent"] for s in snapshots]
            
            summary = {
                "report_generated": datetime.now(timezone.utc).isoformat(),
                "total_snapshots": len(snapshots),
                "total_hours": snapshots[-1].get("hour_number", len(snapshots)),
                "start_time": snapshots[0]["timestamp"],
                "end_time": snapshots[-1]["timestamp"],
                
                "system_health": {
                    "cpu_avg": round(sum(cpu_values) / len(cpu_values), 2),
                    "cpu_max": round(max(cpu_values), 2),
                    "cpu_min": round(min(cpu_values), 2),
                    "memory_avg": round(sum(memory_values) / len(memory_values), 2),
                    "memory_max": round(max(memory_values), 2),
                    "uptime_final": snapshots[-1]["uptime_sec"]
                },
                
                "trading_activity": {
                    "total_trades": snapshots[-1]["total_trades_executed"],
                    "total_signals": snapshots[-1]["signals_generated"],
                    "total_markets_evaluated": snapshots[-1]["markets_evaluated"]
                },
                
                "performance": {
                    "final_realized_pnl": snapshots[-1]["realized_pnl"],
                    "final_unrealized_pnl": snapshots[-1]["unrealized_pnl"],
                    "final_total_pnl": snapshots[-1]["total_pnl"],
                    "max_drawdown": max(s["max_drawdown"] for s in snapshots),
                    "max_drawdown_pct": max(s["max_drawdown_pct"] for s in snapshots)
                },
                
                "per_model": {
                    "model_a": {
                        "final_pnl": snapshots[-1]["model_a_pnl"],
                        "final_trades": snapshots[-1]["model_a_trades"]
                    },
                    "model_b": {
                        "final_pnl": snapshots[-1]["model_b_pnl"],
                        "final_trades": snapshots[-1]["model_b_trades"]
                    },
                    "model_c": {
                        "final_pnl": snapshots[-1]["model_c_pnl"],
                        "final_trades": snapshots[-1]["model_c_trades"]
                    }
                },
                
                "scheduler": {
                    "final_strategy_ticks": snapshots[-1]["strategy_loop_ticks_total"],
                    "final_discovery_ticks": snapshots[-1]["discovery_loop_ticks_total"]
                },
                
                "stability": {
                    "db_failures": sum(1 for s in snapshots if not s["db_ping"]),
                    "scheduler_interruptions": sum(1 for s in snapshots if not s["autonomous_enabled"]),
                    "kill_switch_activations": sum(1 for s in snapshots if s["kill_switch_active"])
                }
            }
            
            # Save summary
            summary_path = os.path.join(SNAPSHOTS_DIR, "24h_summary_report.json")
            with open(summary_path, 'w') as f:
                json.dump(summary, f, indent=2)
            
            logger.info(f"Summary report saved: {summary_path}")
            
        except Exception as e:
            logger.error(f"Failed to generate summary report: {e}")
    
    async def take_manual_snapshot(self) -> Dict:
        """Take an immediate snapshot (for debugging/verification)"""
        snapshot = await self._take_snapshot()
        return snapshot.to_dict()
    
    def get_status(self) -> Dict:
        """Get current service status"""
        return {
            "running": self._running,
            "hour_number": self._hour_number,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "snapshots_dir": SNAPSHOTS_DIR,
            "interval_seconds": self.SNAPSHOT_INTERVAL_SECONDS
        }


# Global instance
hourly_snapshot_service: Optional[HourlyMetricsSnapshotService] = None
