"""
Model E - Balanced Edge Hunter

Characteristics:
- Moderate-low edge threshold (4.5%+)
- 2 tick persistence requirement
- Lower cooldown (1.5 min)
- Conservative position sizing
- Consistent performance focus
- Higher trade frequency opportunistic
"""
from typing import Dict, Optional
import logging

from models.game import Game
from models.market import Market
from models.signal import Signal, SignalType
from strategies.base_strategy import BaseStrategy, StrategyConfig, StrategyDecision, DecisionType
from strategies.virtual_portfolio import VirtualPosition

logger = logging.getLogger(__name__)


class ModelEBalancedHunter(BaseStrategy):
    """
    Balanced Edge Hunter - Consistent performance with opportunistic entries.
    
    Entry Rules:
    - Min edge: 4.5%
    - Min signal score: 50
    - Persistence: 2 ticks
    - Cooldown: 90s
    - No momentum requirement
    
    Exit Rules:
    - Edge compression below 1.2%
    - Profit target: 10%
    - Stop loss: 7%
    - Time-based exit: 6 min
    """
    
    def evaluate_entry(
        self,
        game: Game,
        market: Market,
        signal: Signal,
        orderbook: Optional[Dict] = None
    ) -> Optional[StrategyDecision]:
        """Evaluate entry with balanced hunting criteria."""
        
        entry_rules = self.config.entry_rules
        
        # 1. Check filters first
        passes_filters, filter_reason = self.check_filters(game, market, orderbook)
        if not passes_filters:
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason=f"Filter: {filter_reason}",
                market_id=market.id,
                game_id=game.id
            )
        
        # 2. Check cooldown
        if not self.check_cooldown(game.id):
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason="Cooldown active",
                market_id=market.id,
                game_id=game.id
            )
        
        # 3. Check max entries per game
        if not self.check_max_entries(game.id):
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason="Max entries per game reached",
                market_id=market.id,
                game_id=game.id
            )
        
        # 4. Check edge threshold
        min_edge = entry_rules.get("min_edge_threshold", 0.045)
        if abs(signal.edge) < min_edge:
            return None  # Not actionable, silent skip
        
        # 5. Check signal score
        min_score = entry_rules.get("min_signal_score", 50)
        signal_score = getattr(signal, '_signal_score', signal.confidence * 100)
        if signal_score < min_score:
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason=f"Signal score {signal_score:.0f} < {min_score}",
                market_id=market.id,
                game_id=game.id,
                edge=signal.edge,
                signal_score=signal_score
            )
        
        # 6. Check edge persistence
        min_ticks = entry_rules.get("min_persistence_ticks", 2)
        if not self.check_edge_persistence(market.id, min_ticks, min_edge):
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason=f"Edge not persistent ({min_ticks} ticks required)",
                market_id=market.id,
                game_id=game.id,
                edge=signal.edge,
                signal_score=signal_score
            )
        
        # 7. Momentum check is optional - not required for this model
        # Allows entries even without momentum alignment
        
        # All checks passed - calculate size and enter
        side = "yes" if signal.edge > 0 else "no"
        size = self.calculate_size(signal, self.portfolio.available_capital)
        
        if size <= 0:
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason="Calculated size is 0",
                market_id=market.id,
                game_id=game.id
            )
        
        return StrategyDecision(
            decision_type=DecisionType.ENTER,
            reason=f"Balanced hunt: edge {signal.edge:.2%}, score {signal_score:.0f}",
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
        """Evaluate exit conditions."""
        
        exit_rules = self.config.exit_rules
        
        # 1. Stop loss
        stop_loss_pct = exit_rules.get("stop_loss_pct", 0.07)
        if position.unrealized_pnl_pct <= -stop_loss_pct:
            return StrategyDecision(
                decision_type=DecisionType.EXIT,
                reason=f"Stop loss triggered ({position.unrealized_pnl_pct:.1%})",
                market_id=market.id,
                game_id=game.id,
                side=position.side,
                quantity=position.quantity,
                price=market.implied_probability,
                edge=signal.edge
            )
        
        # 2. Profit target
        profit_target_pct = exit_rules.get("profit_target_pct", 0.10)
        if position.unrealized_pnl_pct >= profit_target_pct:
            return StrategyDecision(
                decision_type=DecisionType.EXIT,
                reason=f"Profit target reached ({position.unrealized_pnl_pct:.1%})",
                market_id=market.id,
                game_id=game.id,
                side=position.side,
                quantity=position.quantity,
                price=market.implied_probability,
                edge=signal.edge
            )
        
        # 3. Edge compression exit
        exit_threshold = exit_rules.get("edge_compression_exit_threshold", 0.012)
        if signal.edge < exit_threshold and position.side == "yes":
            return StrategyDecision(
                decision_type=DecisionType.EXIT,
                reason=f"Edge compressed below {exit_threshold:.1%}",
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
                reason=f"Edge compressed (short) above {-exit_threshold:.1%}",
                market_id=market.id,
                game_id=game.id,
                side=position.side,
                quantity=position.quantity,
                price=market.implied_probability,
                edge=signal.edge
            )
        
        # 4. Time-based exit
        max_hold_time = exit_rules.get("time_based_exit_seconds", 360)
        if position.hold_time_seconds > max_hold_time:
            return StrategyDecision(
                decision_type=DecisionType.EXIT,
                reason=f"Max hold time {max_hold_time}s exceeded",
                market_id=market.id,
                game_id=game.id,
                side=position.side,
                quantity=position.quantity,
                price=market.implied_probability,
                edge=signal.edge
            )
        
        # 5. Trailing stop
        trailing_stop = exit_rules.get("trailing_stop_pct", 0.035)
        # Simplified trailing stop logic
        if position.unrealized_pnl_pct > trailing_stop * 2:
            # We're up significantly, start trailing
            if position.unrealized_pnl_pct < trailing_stop:
                return StrategyDecision(
                    decision_type=DecisionType.EXIT,
                    reason=f"Trailing stop triggered",
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
        Calculate position size using balanced hunter sizing.
        Base: 1.8% of capital, scaled with edge.
        """
        sizing = self.config.position_sizing
        
        # Base size
        base_pct = sizing.get("base_size_pct", 0.018)
        base_amount = available_capital * base_pct
        
        # Scale with edge
        if sizing.get("scale_with_edge", True):
            edge_scale = sizing.get("edge_scale_factor", 1.8)
            edge_mult = 1 + (abs(signal.edge) * edge_scale)
            base_amount *= min(edge_mult, 2.0)  # Cap at 2x
        
        # Apply Kelly fraction
        kelly = sizing.get("kelly_fraction", 0.22)
        base_amount *= kelly
        
        # Max position check
        max_pct = sizing.get("max_position_pct", 0.045)
        max_amount = self.portfolio.starting_capital * max_pct
        final_amount = min(base_amount, max_amount)
        
        # Convert to contracts (assuming price is 0.50 average)
        avg_price = signal.market_prob if signal.market_prob > 0.1 else 0.50
        contracts = int(final_amount / avg_price)
        
        return max(1, min(contracts, 100))  # 1-100 contracts
