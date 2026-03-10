"""
Config Version Service

Manages strategy configuration versions and provides:
- Human-readable rule summaries (auto-generated from JSON)
- Version history and diffs
- Rollback functionality
- Rule chip data for dashboard
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import logging

from models.config_version import (
    ConfigVersion, ConfigDiff, ConfigChangeSource, LeagueType
)
from repositories.config_version_repository import ConfigVersionRepository

logger = logging.getLogger(__name__)


class ConfigVersionService:
    """
    Service for managing strategy configuration versions.
    """
    
    def __init__(self, config_repo: ConfigVersionRepository):
        self.config_repo = config_repo
    
    # ==========================================
    # RULE CHIPS (Dashboard Display)
    # ==========================================
    
    def get_rule_chips(self, config: Dict, league: str = "NBA") -> List[Dict]:
        """
        Extract top 7-9 rule chips for dashboard display.
        Returns key parameters in display-friendly format.
        """
        entry = config.get("entry_rules", {})
        exit_rules = config.get("exit_rules", {})
        filters = config.get("filters", {})
        risk = config.get("risk_limits", {})
        
        chips = []
        
        # Edge min
        edge = entry.get("min_edge_threshold", 0.05)
        chips.append({
            "label": "Edge min",
            "value": f"{edge*100:.1f}%",
            "raw": edge,
            "param": "entry_rules.min_edge_threshold"
        })
        
        # Signal score min
        score = entry.get("min_signal_score", 60)
        chips.append({
            "label": "Score min",
            "value": str(int(score)),
            "raw": score,
            "param": "entry_rules.min_signal_score"
        })
        
        # Persistence ticks
        persist = entry.get("min_persistence_ticks", 3)
        chips.append({
            "label": "Persist",
            "value": f"{persist} ticks",
            "raw": persist,
            "param": "entry_rules.min_persistence_ticks"
        })
        
        # Cooldown
        cooldown = entry.get("cooldown_seconds", 180)
        chips.append({
            "label": "Cooldown",
            "value": f"{cooldown}s",
            "raw": cooldown,
            "param": "entry_rules.cooldown_seconds"
        })
        
        # Max spread
        spread = filters.get("max_spread_pct", 0.05)
        chips.append({
            "label": "Max spread",
            "value": f"{spread*100:.0f}%",
            "raw": spread,
            "param": "filters.max_spread_pct"
        })
        
        # Min liquidity
        liquidity = filters.get("min_liquidity_contracts", 50)
        chips.append({
            "label": "Min depth",
            "value": f"{liquidity}",
            "raw": liquidity,
            "param": "filters.min_liquidity_contracts"
        })
        
        # Max trades/game
        max_trades = risk.get("max_trades_per_game", entry.get("max_entries_per_game", 3))
        chips.append({
            "label": "Max/game",
            "value": str(int(max_trades)),
            "raw": max_trades,
            "param": "risk_limits.max_trades_per_game"
        })
        
        # Edge exit
        exit_edge = exit_rules.get("edge_compression_exit_threshold", 0.02)
        chips.append({
            "label": "Exit edge",
            "value": f"{exit_edge*100:.1f}%",
            "raw": exit_edge,
            "param": "exit_rules.edge_compression_exit_threshold"
        })
        
        # Stop loss
        stop = exit_rules.get("stop_loss_pct", 0.10)
        chips.append({
            "label": "Stop loss",
            "value": f"{stop*100:.0f}%",
            "raw": stop,
            "param": "exit_rules.stop_loss_pct"
        })
        
        return chips[:9]  # Max 9 chips
    
    # ==========================================
    # HUMAN-READABLE SUMMARY
    # ==========================================
    
    def generate_rules_summary(self, config: Dict, model_name: str = "Strategy") -> str:
        """
        Generate a 1-page plain English summary from config JSON.
        Auto-generated to always match the actual config.
        """
        entry = config.get("entry_rules", {})
        exit_rules = config.get("exit_rules", {})
        filters = config.get("filters", {})
        sizing = config.get("position_sizing", {})
        risk = config.get("risk_limits", {})
        trim = config.get("trim_rules", {})
        breakers = config.get("circuit_breakers", {})
        
        sections = []
        
        # Header
        sections.append(f"# {model_name} Rules Summary")
        sections.append(f"*Auto-generated from config at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*\n")
        
        # Market Eligibility
        sections.append("## Market Eligibility Filters")
        sections.append(f"- **Allowed leagues**: {', '.join(filters.get('allowed_leagues', ['NBA', 'NCAA_M', 'NCAA_W']))}")
        sections.append(f"- **Game progress**: {filters.get('min_game_progress', 0)*100:.0f}% to {filters.get('max_game_progress', 1)*100:.0f}%")
        sections.append(f"- **Maximum spread**: {filters.get('max_spread_pct', 0.05)*100:.0f}%")
        sections.append(f"- **Minimum liquidity**: {filters.get('min_liquidity_contracts', 0)} contracts")
        vol_allowed = filters.get('volatility_regime_allowed', ['low', 'medium', 'high'])
        sections.append(f"- **Volatility regimes**: {', '.join(vol_allowed)}")
        sections.append("")
        
        # Entry Rules
        sections.append("## Entry Rules")
        sections.append(f"- **Minimum edge threshold**: {entry.get('min_edge_threshold', 0.05)*100:.1f}%")
        sections.append(f"- **Minimum signal score**: {entry.get('min_signal_score', 60)}")
        sections.append(f"- **Persistence required**: {entry.get('min_persistence_ticks', 3)} consecutive ticks")
        sections.append(f"- **Cooldown between entries**: {entry.get('cooldown_seconds', 180)} seconds")
        sections.append(f"- **Max entries per game**: {entry.get('max_entries_per_game', 3)}")
        if entry.get('require_positive_momentum', False):
            sections.append("- **Momentum alignment required**: Yes")
        sections.append("")
        
        # Exit/Trim Rules
        sections.append("## Exit & Trim Rules")
        sections.append(f"- **Profit target**: {exit_rules.get('profit_target_pct', 0.15)*100:.0f}%")
        sections.append(f"- **Stop loss**: {exit_rules.get('stop_loss_pct', 0.10)*100:.0f}%")
        sections.append(f"- **Edge compression exit**: Below {exit_rules.get('edge_compression_exit_threshold', 0.02)*100:.1f}%")
        sections.append(f"- **Time-based exit**: After {exit_rules.get('time_based_exit_seconds', 600)} seconds")
        sections.append(f"- **Trailing stop**: {exit_rules.get('trailing_stop_pct', 0.05)*100:.0f}%")
        if trim.get('enable_trim', False):
            sections.append(f"- **Trim enabled**: At {trim.get('trim_at_profit_pct', 0.10)*100:.0f}% profit, trim {trim.get('trim_size_pct', 0.50)*100:.0f}%")
        sections.append("")
        
        # Sizing Rules
        sections.append("## Position Sizing")
        sections.append(f"- **Base size**: {sizing.get('base_size_pct', 0.02)*100:.1f}% of capital")
        sections.append(f"- **Maximum position**: {sizing.get('max_position_pct', 0.05)*100:.0f}% of capital")
        sections.append(f"- **Kelly fraction**: {sizing.get('kelly_fraction', 0.25)*100:.0f}%")
        if sizing.get('scale_with_edge', False):
            sections.append(f"- **Edge scaling**: {sizing.get('edge_scale_factor', 1.0)}x")
        sections.append("")
        
        # Risk Limits
        sections.append("## Risk Limits")
        sections.append(f"- **Daily loss cap**: {risk.get('max_daily_loss_pct', 0.05)*100:.0f}%")
        sections.append(f"- **Maximum exposure**: {risk.get('max_exposure_pct', 0.15)*100:.0f}%")
        sections.append(f"- **Max trades per hour**: {risk.get('max_trades_per_hour', 10)}")
        sections.append(f"- **Max trades per day**: {risk.get('max_trades_per_day', 50)}")
        sections.append(f"- **Max drawdown**: {risk.get('max_drawdown_pct', 0.10)*100:.0f}%")
        sections.append("")
        
        # Circuit Breakers
        sections.append("## Circuit Breakers")
        sections.append(f"- **Pause after consecutive losses**: {breakers.get('pause_on_consecutive_losses', 5)}")
        sections.append(f"- **Pause duration**: {breakers.get('pause_duration_seconds', 600)} seconds")
        sections.append(f"- **Pause on drawdown**: {breakers.get('pause_on_drawdown_pct', 0.05)*100:.0f}%")
        if breakers.get('auto_resume', True):
            sections.append("- **Auto-resume**: Yes")
        else:
            sections.append("- **Manual reset required**: Yes")
        
        return "\n".join(sections)
    
    # ==========================================
    # VERSION MANAGEMENT
    # ==========================================
    
    async def get_active_config_with_metadata(
        self, 
        model_id: str, 
        league: str = "BASE"
    ) -> Dict:
        """Get active config with all metadata for dashboard."""
        config_version = await self.config_repo.get_active_config(model_id, league)
        
        if not config_version:
            # Fallback to BASE
            config_version = await self.config_repo.get_active_config(model_id, "BASE")
        
        if not config_version:
            return None
        
        # Get model display name
        model_names = {
            "model_a_disciplined": "Model A - Disciplined Edge Trader",
            "model_b_high_frequency": "Model B - High Frequency Hunter",
            "model_c_institutional": "Model C - Institutional Risk-First"
        }
        
        return {
            "version_id": config_version.version_id,
            "version_number": config_version.version_number,
            "league": config_version.league,
            "config": config_version.config,
            "rule_chips": self.get_rule_chips(config_version.config, league),
            "rules_summary": self.generate_rules_summary(
                config_version.config, 
                model_names.get(model_id, model_id)
            ),
            "applied_at": config_version.applied_at.isoformat() if config_version.applied_at else None,
            "applied_by": config_version.applied_by.value,
            "change_summary": config_version.change_summary
        }
    
    async def get_version_history_with_diffs(
        self,
        model_id: str,
        league: str,
        limit: int = 10
    ) -> List[Dict]:
        """Get version history with diff summaries."""
        versions = await self.config_repo.get_version_history(model_id, league, limit)
        
        history = []
        for v in versions:
            history.append({
                "version_id": v.version_id,
                "version_number": v.version_number,
                "created_at": v.created_at.isoformat(),
                "applied_at": v.applied_at.isoformat() if v.applied_at else None,
                "applied_by": v.applied_by.value,
                "change_summary": v.change_summary,
                "is_active": v.is_active,
                "diff": [
                    {
                        "parameter": d.parameter,
                        "old": d.old_value,
                        "new": d.new_value
                    }
                    for d in v.diff_from_previous
                ]
            })
        
        return history
    
    async def rollback_to_version(
        self,
        model_id: str,
        league: str,
        target_version_id: str
    ) -> Optional[Dict]:
        """Rollback to a previous version."""
        new_version = await self.config_repo.rollback_to_version(
            model_id, league, target_version_id
        )
        
        if new_version:
            return {
                "success": True,
                "new_version_id": new_version.version_id,
                "rolled_back_to": target_version_id
            }
        
        return {"success": False, "error": "Version not found"}
    
    # ==========================================
    # TRADE EXPLAINABILITY
    # ==========================================
    
    def format_trade_explanation(self, trade_data: Dict) -> Dict:
        """
        Format trade data with human-readable explanations.
        """
        entry_reasons = trade_data.get("entry_reason_codes", [])
        exit_reasons = trade_data.get("exit_reason_codes", [])
        
        # Decision-time values
        values = {
            "fair_prob": trade_data.get("fair_prob", 0),
            "market_prob": trade_data.get("market_prob", 0),
            "edge": trade_data.get("edge", 0),
            "signal_score": trade_data.get("signal_score", 0),
            "spread": trade_data.get("spread", 0),
            "depth": trade_data.get("depth", 0),
            "volatility": trade_data.get("volatility", 0),
            "momentum": trade_data.get("momentum", "neutral")
        }
        
        # Generate one-liner
        direction = trade_data.get("direction", "unknown")
        
        if direction == "buy":
            one_liner = self._generate_entry_explanation(values, entry_reasons)
        else:
            one_liner = self._generate_exit_explanation(values, exit_reasons)
        
        return {
            "direction": direction,
            "entry_reasons": entry_reasons,
            "exit_reasons": exit_reasons,
            "values": values,
            "explanation": one_liner
        }
    
    def _generate_entry_explanation(self, values: Dict, reasons: List[str]) -> str:
        """Generate entry explanation one-liner."""
        edge_pct = values["edge"] * 100
        score = values["signal_score"]
        
        parts = [f"ENTER: edge {edge_pct:+.1f}%"]
        
        if "persistence" in str(reasons).lower():
            parts.append("persisted")
        
        if values["spread"] < 0.05:
            parts.append("spread OK")
        
        if values["depth"] > 50:
            parts.append("depth OK")
        
        return ", ".join(parts)
    
    def _generate_exit_explanation(self, values: Dict, reasons: List[str]) -> str:
        """Generate exit explanation one-liner."""
        edge_pct = values["edge"] * 100
        
        # Find main exit reason
        reason_str = str(reasons).lower()
        
        if "stop" in reason_str:
            return f"EXIT: Stop loss triggered"
        elif "profit" in reason_str:
            return f"EXIT: Profit target reached"
        elif "compression" in reason_str:
            return f"EXIT: edge compressed to {edge_pct:+.1f}%"
        elif "time" in reason_str:
            return f"EXIT: Time-based exit"
        else:
            return f"EXIT: edge {edge_pct:+.1f}%"
