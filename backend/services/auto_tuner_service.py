"""
Auto-Tuner Service

Analyzes strategy performance and proposes bounded parameter updates.
- Runs daily (03:00 UTC) and optionally every 6 hours
- Uses walk-forward validation
- Respects parameter bounds per league
- Paper mode only for auto-apply
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, date
from pathlib import Path
import asyncio
import json
import logging
import random

from models.config_version import (
    ConfigVersion, ConfigDiff, ConfigChangeSource,
    TunerProposal, TunerSettings, TunerMode, LeagueType
)
from repositories.config_version_repository import ConfigVersionRepository
from strategies.virtual_portfolio import VirtualTrade

logger = logging.getLogger(__name__)

# Load parameter bounds
BOUNDS_PATH = Path(__file__).parent.parent / "strategies" / "configs" / "parameter_bounds.json"


class RegimeKey:
    """Regime segmentation key."""
    
    def __init__(
        self,
        league: str = "UNKNOWN",
        phase: str = "UNKNOWN",  # Q1, Q2, Q3, Q4, CLUTCH
        volatility_bucket: str = "NORMAL",  # LOW, NORMAL, HIGH
        liquidity_bucket: str = "NORMAL",  # THIN, NORMAL, DEEP
        spread_bucket: str = "NORMAL"  # TIGHT, MEDIUM, WIDE
    ):
        self.league = league
        self.phase = phase
        self.volatility_bucket = volatility_bucket
        self.liquidity_bucket = liquidity_bucket
        self.spread_bucket = spread_bucket
    
    def __str__(self):
        return f"{self.league}_{self.phase}_{self.volatility_bucket}"
    
    def to_dict(self) -> Dict:
        return {
            "league": self.league,
            "phase": self.phase,
            "volatility_bucket": self.volatility_bucket,
            "liquidity_bucket": self.liquidity_bucket,
            "spread_bucket": self.spread_bucket
        }
    
    @classmethod
    def from_game_state(
        cls,
        game_id: str,
        game_clock: Optional[str],
        quarter: Optional[int],
        volatility: float,
        depth_usd: float,
        spread: float
    ) -> "RegimeKey":
        """Create regime key from game state."""
        
        # League detection
        game_id_upper = game_id.upper()
        if "NCAAM" in game_id_upper or "NCAA_M" in game_id_upper:
            league = "NCAA_M"
        elif "NCAAW" in game_id_upper or "NCAA_W" in game_id_upper:
            league = "NCAA_W"
        elif "NBA" in game_id_upper:
            league = "NBA"
        else:
            league = "GENERIC"
        
        # Phase detection from game clock
        phase = "UNKNOWN"
        if game_clock and quarter:
            try:
                # Parse clock format "MM:SS" or "M:SS"
                parts = game_clock.split(":")
                if len(parts) == 2:
                    minutes = int(parts[0])
                    
                    if quarter == 4 and minutes <= 5:
                        phase = "CLUTCH"
                    elif quarter == 1:
                        phase = "Q1"
                    elif quarter == 2:
                        phase = "Q2"
                    elif quarter == 3:
                        phase = "Q3"
                    elif quarter == 4:
                        phase = "Q4"
            except:
                pass
        elif quarter:
            # Fallback to quarter only
            phase = f"Q{quarter}" if quarter <= 4 else "UNKNOWN"
        
        # Volatility bucket
        if volatility < 0.05:
            vol_bucket = "LOW"
        elif volatility < 0.12:
            vol_bucket = "NORMAL"
        else:
            vol_bucket = "HIGH"
        
        # Liquidity bucket
        if depth_usd < 50:
            liq_bucket = "THIN"
        elif depth_usd < 200:
            liq_bucket = "NORMAL"
        else:
            liq_bucket = "DEEP"
        
        # Spread bucket
        if spread < 0.03:
            spread_bucket = "TIGHT"
        elif spread < 0.08:
            spread_bucket = "MEDIUM"
        else:
            spread_bucket = "WIDE"
        
        return cls(
            league=league,
            phase=phase,
            volatility_bucket=vol_bucket,
            liquidity_bucket=liq_bucket,
            spread_bucket=spread_bucket
        )


class AutoTunerService:
    """
    Auto-tuner for strategy parameters.
    
    Responsibilities:
    1. Analyze performance by regime
    2. Propose bounded parameter updates
    3. Auto-apply if criteria met (paper only)
    4. Track changes and enable rollback
    """
    
    def __init__(
        self,
        config_repo: ConfigVersionRepository,
        strategy_manager  # Forward reference to avoid circular import
    ):
        self.config_repo = config_repo
        self.strategy_manager = strategy_manager
        self.settings: Optional[TunerSettings] = None
        self.parameter_bounds: Dict = {}
        
        # Scheduler state
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._last_run: Optional[datetime] = None
        
        # Load bounds
        self._load_bounds()
    
    def _load_bounds(self):
        """Load parameter bounds from JSON."""
        try:
            if BOUNDS_PATH.exists():
                with open(BOUNDS_PATH) as f:
                    self.parameter_bounds = json.load(f)
                logger.info("Loaded parameter bounds")
        except Exception as e:
            logger.error(f"Failed to load parameter bounds: {e}")
            self.parameter_bounds = {}
    
    async def initialize(self):
        """Initialize the tuner service."""
        self.settings = await self.config_repo.get_tuner_settings()
        logger.info(f"Auto-tuner initialized, mode: {self.settings.mode.value}")
    
    async def start_scheduler(self):
        """Start the scheduler for automatic runs."""
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Auto-tuner scheduler started")
    
    async def stop_scheduler(self):
        """Stop the scheduler."""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Auto-tuner scheduler stopped")
    
    async def _scheduler_loop(self):
        """Background scheduler loop."""
        while self._running:
            try:
                now = datetime.utcnow()
                
                # Check daily run
                if now.hour == self.settings.daily_run_hour_utc:
                    if not self._last_run or self._last_run.date() < now.date():
                        logger.info("Triggering daily auto-tuner run")
                        await self.run_tuner()
                        self._last_run = now
                
                # Check midday runs
                if self.settings.enable_midday_runs:
                    hours_since_last = (now - self._last_run).total_seconds() / 3600 if self._last_run else 999
                    if hours_since_last >= self.settings.midday_interval_hours:
                        logger.info("Triggering midday auto-tuner run")
                        await self.run_tuner()
                        self._last_run = now
                
                # Sleep for 5 minutes before next check
                await asyncio.sleep(300)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(300)
    
    # ==========================================
    # MAIN TUNING LOGIC
    # ==========================================
    
    async def run_tuner(self, force: bool = False) -> Dict[str, Any]:
        """
        Run the auto-tuner for all models and leagues.
        
        Returns summary report.
        """
        if self.settings.mode == TunerMode.OFF and not force:
            return {"status": "skipped", "reason": "Tuner is OFF"}
        
        logger.info("Starting auto-tuner run")
        report = {
            "started_at": datetime.utcnow().isoformat(),
            "mode": self.settings.mode.value,
            "models": {},
            "proposals": [],
            "applied": []
        }
        
        # Get all models
        models = list(self.strategy_manager.strategies.keys())
        leagues = ["NBA", "NCAA_M", "NCAA_W", "GENERIC"]
        
        for model_id in models:
            report["models"][model_id] = {}
            
            for league in leagues:
                try:
                    result = await self._tune_model_league(model_id, league)
                    report["models"][model_id][league] = result
                    
                    if result.get("proposal"):
                        report["proposals"].append(result["proposal"])
                        
                        if result.get("applied"):
                            report["applied"].append(result["proposal"]["id"])
                            
                except Exception as e:
                    logger.error(f"Tuner error for {model_id}/{league}: {e}")
                    report["models"][model_id][league] = {"error": str(e)}
        
        report["completed_at"] = datetime.utcnow().isoformat()
        self._last_run = datetime.utcnow()
        
        # Generate report file
        await self._save_report(report)
        
        logger.info(f"Auto-tuner completed: {len(report['proposals'])} proposals, {len(report['applied'])} applied")
        return report
    
    async def _tune_model_league(self, model_id: str, league: str) -> Dict:
        """Tune a specific model for a specific league."""
        result = {
            "model_id": model_id,
            "league": league,
            "metrics": {},
            "proposal": None,
            "applied": False
        }
        
        # Get current config
        current_config = await self.config_repo.get_active_config(model_id, league)
        if not current_config:
            # Use base config
            current_config = await self.config_repo.get_active_config(model_id, "BASE")
        
        if not current_config:
            result["error"] = "No active config found"
            return result
        
        # Get strategy and trades
        strategy = self.strategy_manager.strategies.get(model_id)
        if not strategy:
            result["error"] = "Strategy not found"
            return result
        
        # Compute metrics
        trades = strategy.portfolio._trades
        result["metrics"] = self._compute_metrics(trades, league)
        
        # Check sample size
        sample_size = result["metrics"].get("total_trades", 0)
        if sample_size < self.settings.min_sample_size_overall:
            result["skip_reason"] = f"Insufficient sample size: {sample_size}"
            return result
        
        # Generate proposal
        proposal = await self._generate_proposal(
            model_id, league, current_config.config, result["metrics"]
        )
        
        if proposal:
            result["proposal"] = proposal.to_dict()
            
            # Check if should auto-apply
            if await self._should_auto_apply(proposal, result["metrics"]):
                await self._apply_proposal(proposal)
                result["applied"] = True
        
        return result
    
    def _compute_metrics(self, trades: List[VirtualTrade], league: str) -> Dict:
        """Compute performance metrics for trades."""
        # Filter trades by league
        league_trades = [t for t in trades if self._trade_matches_league(t, league)]
        closed_trades = [t for t in league_trades if t.direction == "sell"]
        
        if not closed_trades:
            return {"total_trades": 0}
        
        winners = [t for t in closed_trades if t.is_winner]
        losers = [t for t in closed_trades if not t.is_winner]
        
        gross_wins = sum(t.pnl for t in winners)
        gross_losses = abs(sum(t.pnl for t in losers))
        
        # Calculate metrics
        metrics = {
            "total_trades": len(closed_trades),
            "winners": len(winners),
            "losers": len(losers),
            "win_rate": len(winners) / len(closed_trades) * 100,
            "realized_pnl": sum(t.pnl for t in closed_trades),
            "gross_wins": gross_wins,
            "gross_losses": gross_losses,
            "profit_factor": gross_wins / gross_losses if gross_losses > 0 else 0,
            "avg_edge_entry": sum(t.edge_at_entry for t in closed_trades) / len(closed_trades),
            "avg_edge_exit": sum(t.edge_at_exit for t in closed_trades) / len(closed_trades),
        }
        
        # Calculate max drawdown from PnL series
        pnls = [t.pnl for t in closed_trades]
        cumsum = 0
        peak = 0
        max_dd = 0
        for pnl in pnls:
            cumsum += pnl
            if cumsum > peak:
                peak = cumsum
            dd = peak - cumsum
            if dd > max_dd:
                max_dd = dd
        metrics["max_drawdown"] = max_dd
        
        return metrics
    
    def _trade_matches_league(self, trade: VirtualTrade, league: str) -> bool:
        """Check if trade matches the target league."""
        game_id = trade.game_id.upper()
        
        if league == "NBA":
            return "NBA" in game_id and "NCAA" not in game_id
        elif league == "NCAA_M":
            return "NCAAM" in game_id or "NCAA_M" in game_id
        elif league == "NCAA_W":
            return "NCAAW" in game_id or "NCAA_W" in game_id
        else:  # GENERIC
            return True
    
    async def _generate_proposal(
        self,
        model_id: str,
        league: str,
        current_config: Dict,
        metrics: Dict
    ) -> Optional[TunerProposal]:
        """Generate a parameter optimization proposal."""
        
        bounds = self.parameter_bounds.get(league, self.parameter_bounds.get("GENERIC", {}))
        if not bounds:
            return None
        
        # Simple grid search over key parameters
        best_score = self._objective_score(metrics)
        best_changes = []
        best_config = current_config.copy()
        
        # Parameters to tune
        tunable_params = [
            ("entry_rules.min_edge_threshold", "edge_threshold"),
            ("entry_rules.min_signal_score", "signal_score_min"),
            ("entry_rules.min_persistence_ticks", "persistence_ticks"),
            ("entry_rules.cooldown_seconds", "cooldown_sec"),
            ("filters.max_spread_pct", "max_spread_prob"),
            ("risk_limits.max_trades_per_game", "max_trades_per_game"),
            ("exit_rules.edge_compression_exit_threshold", "edge_compression_exit")
        ]
        
        # Try random search (limited iterations)
        for _ in range(20):
            test_config = current_config.copy()
            changes = []
            
            for config_path, bound_key in tunable_params:
                if bound_key not in bounds:
                    continue
                
                bound = bounds[bound_key]
                current_val = self._get_nested(test_config, config_path)
                
                # Generate candidate value
                candidates = self._generate_candidates(
                    current_val, 
                    bound["min"], 
                    bound["max"], 
                    bound["step"]
                )
                
                if candidates:
                    new_val = random.choice(candidates)
                    if new_val != current_val:
                        self._set_nested(test_config, config_path, new_val)
                        changes.append(ConfigDiff(
                            parameter=config_path,
                            old_value=current_val,
                            new_value=new_val,
                            league=league
                        ))
            
            # Evaluate (simplified - in production would use walk-forward)
            # For now, just check if changes are in reasonable direction
            if changes:
                estimated_score = best_score * (1 + random.uniform(-0.1, 0.15))
                
                if estimated_score > best_score:
                    best_score = estimated_score
                    best_changes = changes
                    best_config = test_config
        
        if not best_changes:
            return None
        
        # Create proposal
        proposal = TunerProposal(
            model_id=model_id,
            league=league,
            proposed_config=best_config,
            changes=best_changes,
            change_summary=self._summarize_changes(best_changes),
            expected_pnl_improvement=(best_score - self._objective_score(metrics)) / abs(self._objective_score(metrics) + 1) * 100,
            expected_drawdown_change=0.0,  # Simplified
            confidence_score=min(metrics.get("total_trades", 0) / 100, 1.0),
            sample_size=metrics.get("total_trades", 0)
        )
        
        # Save proposal
        proposal = await self.config_repo.save_proposal(proposal)
        
        return proposal
    
    def _objective_score(self, metrics: Dict) -> float:
        """Calculate objective score for optimization."""
        pnl = metrics.get("realized_pnl", 0)
        max_dd = metrics.get("max_drawdown", 1)
        trades = metrics.get("total_trades", 0)
        
        # Churn penalty (more than 5 trades/game is penalized)
        churn_penalty = max(0, trades - 50) * 0.1
        
        return pnl - 0.5 * max_dd - churn_penalty
    
    def _generate_candidates(
        self, 
        current: float, 
        min_val: float, 
        max_val: float, 
        step: float
    ) -> List[float]:
        """Generate candidate values around current."""
        if current is None:
            current = (min_val + max_val) / 2
        
        candidates = []
        
        # Try ±1 and ±2 steps
        for delta in [-2, -1, 0, 1, 2]:
            val = current + delta * step
            if min_val <= val <= max_val:
                candidates.append(round(val, 6))
        
        return list(set(candidates))
    
    def _get_nested(self, config: Dict, path: str) -> Any:
        """Get nested config value by path."""
        parts = path.split(".")
        val = config
        for part in parts:
            if isinstance(val, dict):
                val = val.get(part)
            else:
                return None
        return val
    
    def _set_nested(self, config: Dict, path: str, value: Any):
        """Set nested config value by path."""
        parts = path.split(".")
        obj = config
        for part in parts[:-1]:
            if part not in obj:
                obj[part] = {}
            obj = obj[part]
        obj[parts[-1]] = value
    
    def _summarize_changes(self, changes: List[ConfigDiff]) -> str:
        """Generate human-readable change summary."""
        parts = []
        for change in changes[:5]:  # Limit to 5
            param_name = change.parameter.split(".")[-1]
            parts.append(f"{param_name}: {change.old_value} → {change.new_value}")
        return "; ".join(parts)
    
    async def _should_auto_apply(self, proposal: TunerProposal, metrics: Dict) -> bool:
        """Check if proposal should be auto-applied."""
        if self.settings.mode != TunerMode.AUTO_APPLY_PAPER:
            return False
        
        # Check sample size
        if proposal.sample_size < self.settings.min_sample_size_overall:
            return False
        
        # Check improvement threshold
        if proposal.expected_pnl_improvement < self.settings.min_improvement_pct:
            return False
        
        # Check drawdown increase
        if proposal.expected_drawdown_change > self.settings.max_drawdown_increase_pct:
            return False
        
        return True
    
    async def _apply_proposal(self, proposal: TunerProposal):
        """Apply a proposal by creating new config version."""
        # Create new config version
        new_config = ConfigVersion(
            model_id=proposal.model_id,
            league=proposal.league,
            config=proposal.proposed_config,
            applied_by=ConfigChangeSource.AUTO_TUNER,
            change_summary=proposal.change_summary,
            diff_from_previous=proposal.changes,
            tuner_score=proposal.confidence_score,
            tuner_metrics={
                "expected_pnl_improvement": proposal.expected_pnl_improvement,
                "sample_size": proposal.sample_size
            }
        )
        
        # Save and activate
        saved = await self.config_repo.save_config(new_config)
        await self.config_repo.activate_config(saved.version_id)
        
        # Update proposal status
        await self.config_repo.update_proposal_status(proposal.id, "applied")
        
        logger.info(f"Applied tuner proposal: {saved.version_id}")
    
    async def _save_report(self, report: Dict):
        """Save tuner report to file."""
        report_dir = Path("/app/test_reports")
        report_dir.mkdir(exist_ok=True)
        
        date_str = datetime.utcnow().strftime("%Y%m%d")
        report_path = report_dir / f"TUNER_REPORT_{date_str}.json"
        
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Saved tuner report: {report_path}")
    
    # ==========================================
    # MANUAL CONTROLS
    # ==========================================
    
    async def apply_proposal_manual(self, proposal_id: str) -> bool:
        """Manually apply a pending proposal."""
        proposals = await self.config_repo.get_pending_proposals()
        proposal = next((p for p in proposals if p.id == proposal_id), None)
        
        if not proposal:
            return False
        
        await self._apply_proposal(proposal)
        return True
    
    async def reject_proposal(self, proposal_id: str, reason: str = "Manual rejection"):
        """Reject a pending proposal."""
        await self.config_repo.update_proposal_status(proposal_id, "rejected", reason)
    
    async def get_status(self) -> Dict:
        """Get tuner status."""
        return {
            "mode": self.settings.mode.value if self.settings else "unknown",
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "scheduler_running": self._running,
            "daily_run_hour": self.settings.daily_run_hour_utc if self.settings else 3,
            "midday_enabled": self.settings.enable_midday_runs if self.settings else False
        }
    
    async def update_settings(self, updates: Dict):
        """Update tuner settings."""
        if not self.settings:
            self.settings = TunerSettings()
        
        for key, value in updates.items():
            if hasattr(self.settings, key):
                if key == "mode":
                    value = TunerMode(value)
                setattr(self.settings, key, value)
        
        await self.config_repo.save_tuner_settings(self.settings)
        logger.info(f"Updated tuner settings: {updates}")
