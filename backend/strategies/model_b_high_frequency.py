"""
Model B - High Frequency Edge Hunter

Characteristics:
- Lower edge threshold (3%+)
- 1-2 tick persistence
- Short cooldown (60s)
- More entries allowed
- Faster exit compression
- Aggressive trim
- Higher churn tolerance
"""
from typing import Dict, Optional
import logging

from models.game import Game
from models.market import Market
from models.signal import Signal, SignalType
from strategies.base_strategy import BaseStrategy, StrategyConfig, StrategyDecision, DecisionType
from strategies.virtual_portfolio import VirtualPosition

logger = logging.getLogger(__name__)


class ModelBHighFrequency(BaseStrategy):
    """
    High Frequency Edge Hunter - More trades, faster exits.
    
    Entry Rules:
    - Min edge: 3%
    - Min signal score: 45
    - Persistence: 2 ticks
    - Cooldown: 60s
    - No momentum requirement
    
    Exit Rules:
    - Edge compression below 1%
    - Profit target: 8%
    - Stop loss: 6%
    - Time-based exit: 5 min
    - Aggressive trailing stop
    """
    
    def evaluate_entry(
        self,
        game: Game,
        market: Market,
        signal: Signal,
        orderbook: Optional[Dict] = None
    ) -> Optional[StrategyDecision]:
        """Evaluate entry with high-frequency criteria."""
        
        entry_rules = self.config.entry_rules
        
        # 1. Check filters (more permissive)
        passes_filters, filter_reason = self.check_filters(game, market, orderbook)
        if not passes_filters:
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason=f"Filter: {filter_reason}",
                market_id=market.id,
                game_id=game.id
            )
        
        # 2. Check cooldown (shorter)
        if not self.check_cooldown(game.id):
            return None  # Silent skip - high frequency expects some blocks
        
        # 3. Check max entries (higher limit)
        if not self.check_max_entries(game.id):
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason="Max entries per game reached",
                market_id=market.id,
                game_id=game.id
            )
        
        # 4. Check edge threshold (lower)
        min_edge = entry_rules.get("min_edge_threshold", 0.03)
        if abs(signal.edge) < min_edge:
            return None  # Not actionable
        
        # 5. Check signal score (lower threshold)
        min_score = entry_rules.get("min_signal_score", 45)
        signal_score = getattr(signal, '_signal_score', signal.confidence * 100)
        if signal_score < min_score:
            return None  # Silent skip
        
        # 6. Check edge persistence (shorter)
        min_ticks = entry_rules.get("min_persistence_ticks", 2)
        if not self.check_edge_persistence(market.id, min_ticks, min_edge):
            return None  # Silent skip
        
        # 7. No momentum check for high frequency
        # (We trade both directions regardless of momentum)
        
        # All checks passed - enter
        side = "yes" if signal.edge > 0 else "no"
        size = self.calculate_size(signal, self.portfolio.available_capital)
        
        if size <= 0:
            return None
        
        return StrategyDecision(
            decision_type=DecisionType.ENTER,
            reason=f"HF entry: edge {signal.edge:.2%}, score {signal_score:.0f}",
            market_id=market.id,
            game_id=game.id,
            side=side,
            quantity=size,
            price=market.implied_probability,
            edge=signal.edge,
            signal_score=signal_score
        )
    
    def evaluate_exit(
        self,
        game: Game,
        market: Market,
        signal: Signal,
        position: VirtualPosition,
        orderbook: Optional[Dict] = None
    ) -> Optional[StrategyDecision]:
        """Evaluate exit - faster exits for high frequency."""
        
        exit_rules = self.config.exit_rules
        
        # 1. Stop loss (tighter)
        stop_loss_pct = exit_rules.get("stop_loss_pct", 0.06)
        if position.unrealized_pnl_pct <= -stop_loss_pct:
            return StrategyDecision(
                decision_type=DecisionType.EXIT,
                reason=f"Stop loss ({position.unrealized_pnl_pct:.1%})",
                market_id=market.id,
                game_id=game.id,
                side=position.side,
                quantity=position.quantity,
                price=market.implied_probability,
                edge=signal.edge
            )
        
        # 2. Profit target (smaller targets, more frequent wins)
        profit_target_pct = exit_rules.get("profit_target_pct", 0.08)
        if position.unrealized_pnl_pct >= profit_target_pct:
            return StrategyDecision(
                decision_type=DecisionType.EXIT,
                reason=f"Profit target ({position.unrealized_pnl_pct:.1%})",
                market_id=market.id,
                game_id=game.id,
                side=position.side,
                quantity=position.quantity,
                price=market.implied_probability,
                edge=signal.edge
            )
        
        # 3. Edge compression exit (very tight)
        exit_threshold = exit_rules.get("edge_compression_exit_threshold", 0.01)
        if signal.edge < exit_threshold and position.side == "yes":
            return StrategyDecision(
                decision_type=DecisionType.EXIT,
                reason=f"Edge compressed (HF exit)",
                market_id=market.id,
                game_id=game.id,
                side=position.side,
                quantity=position.quantity,
                price=market.implied_probability,
                edge=signal.edge
            )
        
        if signal.edge > -exit_threshold and position.side == "no":
            return StrategyDecision(
                decision_type=DecisionType.EXIT,
                reason=f"Edge compressed short (HF exit)",
                market_id=market.id,
                game_id=game.id,
                side=position.side,
                quantity=position.quantity,
                price=market.implied_probability,
                edge=signal.edge
            )
        
        # 4. Time-based exit (shorter hold time)
        max_hold_time = exit_rules.get("time_based_exit_seconds", 300)
        if position.hold_time_seconds > max_hold_time:
            return StrategyDecision(
                decision_type=DecisionType.EXIT,
                reason=f"Time exit ({max_hold_time}s max)",
                market_id=market.id,
                game_id=game.id,
                side=position.side,
                quantity=position.quantity,
                price=market.implied_probability,
                edge=signal.edge
            )
        
        # 5. Quick trailing stop
        trailing_stop = exit_rules.get("trailing_stop_pct", 0.03)
        if position.unrealized_pnl_pct > trailing_stop * 1.5:
            # In profit - trail aggressively
            if position.unrealized_pnl_pct < trailing_stop * 0.5:
                return StrategyDecision(
                    decision_type=DecisionType.EXIT,
                    reason=f"Trailing stop (HF)",
                    market_id=market.id,
                    game_id=game.id,
                    side=position.side,
                    quantity=position.quantity,
                    price=market.implied_probability,
                    edge=signal.edge
                )
        
        # 6. Edge reversal - exit if edge flips direction
        if position.side == "yes" and signal.edge < 0:
            return StrategyDecision(
                decision_type=DecisionType.EXIT,
                reason=f"Edge reversal (was +, now {signal.edge:.2%})",
                market_id=market.id,
                game_id=game.id,
                side=position.side,
                quantity=position.quantity,
                price=market.implied_probability,
                edge=signal.edge
            )
        
        if position.side == "no" and signal.edge > 0:
            return StrategyDecision(
                decision_type=DecisionType.EXIT,
                reason=f"Edge reversal (was -, now {signal.edge:.2%})",
                market_id=market.id,
                game_id=game.id,
                side=position.side,
                quantity=position.quantity,
                price=market.implied_probability,
                edge=signal.edge
            )
        
        return None
    
    def calculate_size(self, signal: Signal, available_capital: float) -> int:
        """
        Calculate position size - smaller sizes for high frequency.
        Base: 1.5% of capital, quick scaling.
        """
        sizing = self.config.position_sizing
        
        # Base size (smaller for HF)
        base_pct = sizing.get("base_size_pct", 0.015)
        base_amount = available_capital * base_pct
        
        # Scale with edge (less aggressive)
        if sizing.get("scale_with_edge", True):
            edge_scale = sizing.get("edge_scale_factor", 1.5)
            edge_mult = 1 + (abs(signal.edge) * edge_scale)
            base_amount *= min(edge_mult, 1.5)  # Cap at 1.5x
        
        # Apply Kelly fraction
        kelly = sizing.get("kelly_fraction", 0.20)
        base_amount *= kelly
        
        # Max position check
        max_pct = sizing.get("max_position_pct", 0.04)
        max_amount = self.portfolio.starting_capital * max_pct
        final_amount = min(base_amount, max_amount)
        
        # Convert to contracts
        avg_price = signal.market_prob if signal.market_prob > 0.1 else 0.50
        contracts = int(final_amount / avg_price)
        
        return max(1, min(contracts, 50))  # 1-50 contracts (smaller max)
