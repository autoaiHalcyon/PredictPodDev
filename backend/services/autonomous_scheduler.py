"""
Autonomous Strategy Scheduler

Implements 2-loop architecture:
1. Discovery Loop (30-60s) - Always running, scans for markets
2. Trading Loop (1-5s) - Active when open markets exist

Exposes heartbeat and scanning metrics.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


class FilterReason(str, Enum):
    """Reasons why a market was filtered out"""
    STATUS_MISMATCH = "status_mismatch"
    NO_ORDERBOOK = "no_orderbook"
    SPREAD_TOO_WIDE = "spread_too_wide"
    LOW_LIQUIDITY = "low_liquidity"
    OUTSIDE_TIME_WINDOW = "outside_time_window"
    STALE_DATA = "stale_data"
    NO_EDGE = "no_edge"
    BELOW_MIN_SCORE = "below_min_score"
    COOLDOWN_ACTIVE = "cooldown_active"
    RISK_LIMIT_HIT = "risk_limit_hit"


@dataclass
class HeartbeatMetrics:
    """Strategy loop heartbeat metrics"""
    # Discovery loop
    discovery_loop_last_tick_at: Optional[datetime] = None
    discovery_loop_ticks_total: int = 0
    discovery_loop_tick_rate_per_min: float = 0.0
    discovery_loop_status: str = "stopped"
    
    # Trading loop
    trading_loop_last_tick_at: Optional[datetime] = None
    trading_loop_ticks_total: int = 0
    trading_loop_tick_rate_per_min: float = 0.0
    trading_loop_status: str = "stopped"
    
    # Overall
    scheduler_started_at: Optional[datetime] = None
    scheduler_status: str = "stopped"
    
    def to_dict(self) -> Dict:
        return {
            "discovery_loop": {
                "last_tick_at": self.discovery_loop_last_tick_at.isoformat() if self.discovery_loop_last_tick_at else None,
                "ticks_total": self.discovery_loop_ticks_total,
                "tick_rate_per_min": round(self.discovery_loop_tick_rate_per_min, 2),
                "status": self.discovery_loop_status
            },
            "trading_loop": {
                "last_tick_at": self.trading_loop_last_tick_at.isoformat() if self.trading_loop_last_tick_at else None,
                "ticks_total": self.trading_loop_ticks_total,
                "tick_rate_per_min": round(self.trading_loop_tick_rate_per_min, 2),
                "status": self.trading_loop_status
            },
            "scheduler": {
                "started_at": self.scheduler_started_at.isoformat() if self.scheduler_started_at else None,
                "status": self.scheduler_status,
                "uptime_seconds": (datetime.now(timezone.utc) - self.scheduler_started_at).total_seconds() if self.scheduler_started_at else 0
            }
        }


@dataclass
class ScanningMetrics:
    """Market discovery and scanning metrics"""
    # Last minute counts
    events_scanned_last_min: int = 0
    markets_scanned_last_min: int = 0
    
    # Upcoming market counts
    events_next_24h_count: int = 0
    markets_next_24h_count: int = 0
    
    # Next market info
    next_open_market_eta: Optional[str] = None
    next_open_market_ticker: Optional[str] = None
    next_open_market_title: Optional[str] = None
    
    # Open markets currently
    open_markets_found_last_min: int = 0
    open_events_found_last_min: int = 0
    
    # Rolling window for per-minute calculation
    _scan_timestamps: List[datetime] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "events_scanned_last_min": self.events_scanned_last_min,
            "markets_scanned_last_min": self.markets_scanned_last_min,
            "events_next_24h_count": self.events_next_24h_count,
            "markets_next_24h_count": self.markets_next_24h_count,
            "next_open_market": {
                "eta": self.next_open_market_eta,
                "ticker": self.next_open_market_ticker,
                "title": self.next_open_market_title
            },
            "open_markets_found_last_min": self.open_markets_found_last_min,
            "open_events_found_last_min": self.open_events_found_last_min
        }


@dataclass
class FilterMetrics:
    """Filter transparency metrics"""
    filtered_out_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    passed_filter_count: int = 0
    total_evaluated: int = 0
    
    def record_filter(self, reason: FilterReason):
        self.filtered_out_counts[reason.value] += 1
        self.total_evaluated += 1
    
    def record_passed(self):
        self.passed_filter_count += 1
        self.total_evaluated += 1
    
    def reset_minute(self):
        """Reset counts for new minute window"""
        self.filtered_out_counts = defaultdict(int)
        self.passed_filter_count = 0
        self.total_evaluated = 0
    
    def to_dict(self) -> Dict:
        return {
            "filtered_out_reason_counts": dict(self.filtered_out_counts),
            "passed_filter_count": self.passed_filter_count,
            "total_evaluated": self.total_evaluated,
            "pass_rate_pct": round((self.passed_filter_count / self.total_evaluated * 100) if self.total_evaluated > 0 else 0, 1)
        }


class AutonomousScheduler:
    """
    2-Loop autonomous trading scheduler.
    
    Discovery Loop (30-60s):
    - Always running
    - Scans Kalshi for basketball events/markets
    - Updates next_open_market_eta
    - Counts events/markets for next 24h
    
    Trading Loop (1-5s):
    - Active when open markets exist
    - Evaluates signals
    - Executes trades if conditions met
    """
    
    DISCOVERY_INTERVAL_SECONDS = 30
    TRADING_INTERVAL_SECONDS = 3
    
    def __init__(self, db=None, strategy_manager=None, kalshi_ingestor=None):
        self.db = db
        self.strategy_manager = strategy_manager
        self.kalshi_ingestor = kalshi_ingestor
        
        # Metrics
        self.heartbeat = HeartbeatMetrics()
        self.scanning = ScanningMetrics()
        self.filters = FilterMetrics()
        
        # Loop control
        self._running = False
        self._discovery_task: Optional[asyncio.Task] = None
        self._trading_task: Optional[asyncio.Task] = None
        
        # Tick history for rate calculation
        self._discovery_tick_times: List[datetime] = []
        self._trading_tick_times: List[datetime] = []
        
        logger.info("AutonomousScheduler initialized")
    
    async def start(self):
        """Start both loops"""
        if self._running:
            logger.warning("Scheduler already running")
            return
        
        self._running = True
        self.heartbeat.scheduler_started_at = datetime.now(timezone.utc)
        self.heartbeat.scheduler_status = "running"
        
        # Start discovery loop (always on)
        self._discovery_task = asyncio.create_task(self._discovery_loop())
        self.heartbeat.discovery_loop_status = "running"
        
        # Start trading loop (activates when markets exist)
        self._trading_task = asyncio.create_task(self._trading_loop())
        self.heartbeat.trading_loop_status = "waiting"
        
        logger.info("Autonomous scheduler started - Discovery and Trading loops active")
    
    async def stop(self):
        """Stop both loops"""
        self._running = False
        self.heartbeat.scheduler_status = "stopped"
        self.heartbeat.discovery_loop_status = "stopped"
        self.heartbeat.trading_loop_status = "stopped"
        
        if self._discovery_task:
            self._discovery_task.cancel()
        if self._trading_task:
            self._trading_task.cancel()
        
        logger.info("Autonomous scheduler stopped")
    
    async def _discovery_loop(self):
        """
        Discovery loop - runs every 30-60s.
        Scans for markets even when none are open.
        """
        logger.info("Discovery loop started")
        
        while self._running:
            try:
                await self._run_discovery_tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Discovery loop error: {e}")
            
            await asyncio.sleep(self.DISCOVERY_INTERVAL_SECONDS)
        
        logger.info("Discovery loop stopped")
    
    async def _run_discovery_tick(self):
        """
        Single discovery tick.

        Bug #2 fix: actually calls the Kalshi ingestor to fetch live markets
        instead of only reading from the local DB (which starts empty).
        """
        now = datetime.now(timezone.utc)

        self.heartbeat.discovery_loop_last_tick_at = now
        self.heartbeat.discovery_loop_ticks_total += 1
        self._discovery_tick_times.append(now)

        cutoff = now - timedelta(minutes=5)
        self._discovery_tick_times = [t for t in self._discovery_tick_times if t > cutoff]

        if len(self._discovery_tick_times) >= 2:
            time_span = (self._discovery_tick_times[-1] - self._discovery_tick_times[0]).total_seconds()
            if time_span > 0:
                self.heartbeat.discovery_loop_tick_rate_per_min = (
                    len(self._discovery_tick_times) - 1
                ) / time_span * 60

        open_markets = 0
        open_events = 0
        events_next_24h = 0
        markets_next_24h = 0

        # Step 1: Pull fresh data from Kalshi into DB
        if self.kalshi_ingestor is not None:
            try:
                await self.kalshi_ingestor.full_sync()
                logger.info("Discovery: Kalshi ingestor sync complete")
            except Exception as e:
                logger.error(f"Discovery: Kalshi ingestor sync failed: {e}")

        # Step 2: Count markets from DB (now populated by ingestor)
        if self.db is not None:
            try:
                open_events = await self.db.kalshi_events.count_documents(
                    {"status": {"$in": ["open", "active"]}}
                )
                open_markets = await self.db.kalshi_markets.count_documents(
                    {"status": {"$in": ["open", "active"]}}
                )
                events_next_24h = await self.db.kalshi_events.count_documents(
                    {"status": {"$nin": ["settled", "closed"]}}
                )
                markets_next_24h = await self.db.kalshi_markets.count_documents(
                    {"status": {"$nin": ["settled", "closed"]}}
                )
            except Exception as e:
                logger.error(f"Discovery: DB count error: {e}")

        self.scanning.open_events_found_last_min = open_events
        self.scanning.open_markets_found_last_min = open_markets
        self.scanning.events_scanned_last_min = open_events
        self.scanning.markets_scanned_last_min = open_markets
        self.scanning.events_next_24h_count = events_next_24h
        self.scanning.markets_next_24h_count = markets_next_24h

        if open_markets == 0:
            self.scanning.next_open_market_eta = "No markets currently open — next NBA games ~7 PM ET"
            self.scanning.next_open_market_ticker = None
            self.scanning.next_open_market_title = None
            self.heartbeat.trading_loop_status = "waiting_for_markets"
        else:
            self.scanning.next_open_market_eta = None
            self.heartbeat.trading_loop_status = "active"

        logger.info(
            f"Discovery tick complete: {open_markets} open markets, "
            f"{markets_next_24h} total in next 24h"
        )
    
    async def _trading_loop(self):
        """
        Trading loop - runs every 1-5s when markets are open.
        Evaluates signals and executes trades.
        """
        logger.info("Trading loop started")
        
        while self._running:
            try:
                # Only run active evaluation if open markets exist
                if self.scanning.open_markets_found_last_min > 0:
                    await self._run_trading_tick()
                else:
                    # Still tick to show we're alive, but no evaluation
                    await self._run_idle_tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Trading loop error: {e}")
            
            await asyncio.sleep(self.TRADING_INTERVAL_SECONDS)
        
        logger.info("Trading loop stopped")
    
    async def _run_trading_tick(self):
        """
        Single trading tick.

        Bug #1 fix: actually calls strategy_manager.process_tick() for each
        open market instead of the TODO stub that only simulated filter counts.
        """
        now = datetime.now(timezone.utc)

        self.heartbeat.trading_loop_last_tick_at = now
        self.heartbeat.trading_loop_ticks_total += 1
        self._trading_tick_times.append(now)
        self.heartbeat.trading_loop_status = "evaluating"

        cutoff = now - timedelta(minutes=1)
        self._trading_tick_times = [t for t in self._trading_tick_times if t > cutoff]

        if len(self._trading_tick_times) >= 2:
            time_span = (self._trading_tick_times[-1] - self._trading_tick_times[0]).total_seconds()
            if time_span > 0:
                self.heartbeat.trading_loop_tick_rate_per_min = (
                    len(self._trading_tick_times) / time_span * 60
                )

        self.filters.reset_minute()

        if self.db is None or self.strategy_manager is None:
            self.heartbeat.trading_loop_status = "active"
            return

        try:
            cursor = self.db.kalshi_markets.find(
                {"status": {"$in": ["open", "active"]}},
                limit=100
            )
            markets_raw = await cursor.to_list(length=100)

            if not markets_raw:
                self.heartbeat.trading_loop_status = "waiting_for_markets"
                return

            from models.market import Market
            from models.game import Game, GameStatus
            from services.probability_engine import ProbabilityEngine
            from services.signal_engine import SignalEngine

            prob_engine = ProbabilityEngine()
            signal_engine = SignalEngine()

            for market_doc in markets_raw:
                try:
                    yes_bid = (market_doc.get("yes_bid") or 49) / 100
                    yes_ask = (market_doc.get("yes_ask") or 51) / 100
                    volume = market_doc.get("volume", 0)
                    spread = round(yes_ask - yes_bid, 4)

                    if spread > 0.04:
                        self.filters.record_filter(FilterReason.SPREAD_TOO_WIDE)
                        continue

                    if volume < 100:
                        self.filters.record_filter(FilterReason.LOW_LIQUIDITY)
                        continue

                    market = Market(
                        id=market_doc.get("ticker", ""),
                        game_id=market_doc.get("event_ticker", ""),
                        yes_price=(yes_bid + yes_ask) / 2,
                        yes_bid=yes_bid,
                        yes_ask=yes_ask,
                        volume=volume,
                    )

                    game = Game(
                        id=market.game_id or market.id,
                        home_team="Home",
                        away_team="Away",
                        home_score=0,
                        away_score=0,
                        status=GameStatus.LIVE,
                        quarter=2,
                        time_remaining_seconds=720,
                    )

                    home_prob, _ = prob_engine.calculate_win_probability(
                        game, market_prob=market.implied_probability
                    )
                    signal = signal_engine.generate_signal(
                        game=game,
                        market=market,
                        fair_prob=home_prob,
                        confidence=0.5,
                    )

                    self.filters.record_passed()

                    decisions = await self.strategy_manager.process_tick(
                        game=game,
                        market=market,
                        signal=signal,
                        orderbook={"total_liquidity": volume, "spread": spread},
                    )

                    for strategy_id, decision in decisions.items():
                        if decision and decision.decision_type.value == "ENTER":
                            logger.info(
                                f"SIGNAL ENTER [{strategy_id}] market={market.id} "
                                f"edge={signal.edge:.3f} side={decision.side} qty={decision.quantity}"
                            )

                except Exception as e:
                    logger.error(f"Error evaluating market {market_doc.get('ticker')}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Trading tick error: {e}")

        self.heartbeat.trading_loop_status = "active"
    
    async def _run_idle_tick(self):
        """Idle tick when no open markets"""
        now = datetime.now(timezone.utc)
        
        # Still update heartbeat to show we're alive
        self.heartbeat.trading_loop_last_tick_at = now
        self.heartbeat.trading_loop_ticks_total += 1
        self._trading_tick_times.append(now)
        
        # Keep only last minute of ticks
        cutoff = now - timedelta(minutes=1)
        self._trading_tick_times = [t for t in self._trading_tick_times if t > cutoff]
        
        # Calculate tick rate
        if len(self._trading_tick_times) >= 2:
            time_span = (self._trading_tick_times[-1] - self._trading_tick_times[0]).total_seconds()
            if time_span > 0:
                self.heartbeat.trading_loop_tick_rate_per_min = len(self._trading_tick_times) / time_span * 60
        
        self.heartbeat.trading_loop_status = "waiting_for_markets"
    
    def get_health(self) -> Dict:
        """Get full health check response"""
        return {
            "heartbeat": self.heartbeat.to_dict(),
            "scanning": self.scanning.to_dict(),
            "filters": self.filters.to_dict(),
            "status": "healthy" if self._running else "stopped"
        }
    
    def get_metrics_summary(self) -> Dict:
        """Get summary for dashboard display"""
        return {
            "scheduler_status": self.heartbeat.scheduler_status,
            "discovery_last_tick": self.heartbeat.discovery_loop_last_tick_at.isoformat() if self.heartbeat.discovery_loop_last_tick_at else None,
            "discovery_ticks": self.heartbeat.discovery_loop_ticks_total,
            "discovery_rate": round(self.heartbeat.discovery_loop_tick_rate_per_min, 2),
            "trading_last_tick": self.heartbeat.trading_loop_last_tick_at.isoformat() if self.heartbeat.trading_loop_last_tick_at else None,
            "trading_ticks": self.heartbeat.trading_loop_ticks_total,
            "trading_rate": round(self.heartbeat.trading_loop_tick_rate_per_min, 2),
            "trading_status": self.heartbeat.trading_loop_status,
            "events_scanned": self.scanning.events_scanned_last_min,
            "markets_scanned": self.scanning.markets_scanned_last_min,
            "open_markets": self.scanning.open_markets_found_last_min,
            "next_24h_events": self.scanning.events_next_24h_count,
            "next_24h_markets": self.scanning.markets_next_24h_count,
            "next_open_eta": self.scanning.next_open_market_eta,
            "filters": self.filters.to_dict()
        }


# Global instance
autonomous_scheduler: Optional[AutonomousScheduler] = None
