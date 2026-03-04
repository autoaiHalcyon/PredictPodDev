"""
Model C - Institutional Risk-First

Characteristics:
- Highest signal score requirement (75+)
- Strong volatility filter (low only)
- Strong liquidity requirements
- Hard adverse-move stops
- Longer cooldown (5 min)
- Lower max trades per game
- Most conservative sizing
"""
from typing import Dict, Optional
from datetime import datetime
import logging

from models.game import Game
from models.market import Market
from models.signal import Signal, SignalType
from strategies.base_strategy import BaseStrategy, StrategyConfig, StrategyDecision, DecisionType
from strategies.virtual_portfolio import VirtualPosition

logger = logging.getLogger(__name__)


class ModelCInstitutional(BaseStrategy):
    """
    Institutional Risk-First - Maximum conviction trades only.
    
    Entry Rules:
    - Min edge: 7%
    - Min signal score: 75
    - Persistence: 4 ticks
    - Cooldown: 300s
    - Requires positive momentum
    - Low volatility only
    - Strong liquidity required
    
    Exit Rules:
    - Edge compression below 3%
    - Profit target: 20%
    - Stop loss: 8%
    - Hard adverse move stop: 5%
    - Time-based exit: 15 min
    """
    
    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        
        # Track adverse moves for hard stop
        self._entry_prices: Dict[str, float] = {}
        self._peak_prices: Dict[str, float] = {}
    
    def evaluate_entry(
        self,
        game: Game,
        market: Market,
        signal: Signal,
        orderbook: Optional[Dict] = None
    ) -> Optional[StrategyDecision]:
        """Evaluate entry with institutional-grade criteria."""
        
        entry_rules = self.config.entry_rules
        filters = self.config.filters
        
        # 1. Check filters (strict)
        passes_filters, filter_reason = self.check_filters(game, market, orderbook)
        if not passes_filters:
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason=f"Filter: {filter_reason}",
                market_id=market.id,
                game_id=game.id
            )
        
        # 2. Volatility regime check (low only)
        vol_regime = getattr(signal, '_volatility_regime', None)
        if vol_regime:
            allowed_regimes = filters.get("volatility_regime_allowed", ["low"])
            if vol_regime.value not in allowed_regimes:
                return StrategyDecision(
                    decision_type=DecisionType.BLOCK,
                    reason=f"Volatility regime {vol_regime.value} not allowed",
                    market_id=market.id,
                    game_id=game.id
                )
        
        # 3. Strong liquidity requirement
        if filters.get("require_strong_liquidity", True) and orderbook:
            min_liquidity = filters.get("min_liquidity_contracts", 100)
            total_liquidity = orderbook.get("total_liquidity", 0)
            if total_liquidity < min_liquidity:
                return StrategyDecision(
                    decision_type=DecisionType.BLOCK,
                    reason=f"Insufficient liquidity ({total_liquidity} < {min_liquidity})",
                    market_id=market.id,
                    game_id=game.id
                )
        
        # 4. Check cooldown (longer)
        if not self.check_cooldown(game.id):
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason="Cooldown active (institutional)",
                market_id=market.id,
                game_id=game.id
            )
        
        # 5. Check max entries per game (lower limit)
        if not self.check_max_entries(game.id):
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason="Max entries per game reached (institutional)",
                market_id=market.id,
                game_id=game.id
            )
        
        # 6. Check edge threshold (highest)
        min_edge = entry_rules.get("min_edge_threshold", 0.07)
        if abs(signal.edge) < min_edge:
            return None  # Not actionable
        
        # 7. Check signal score (highest requirement)
        min_score = entry_rules.get("min_signal_score", 75)
        signal_score = getattr(signal, '_signal_score', signal.confidence * 100)
        if signal_score < min_score:
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason=f"Signal score {signal_score:.0f} < {min_score} (institutional)",
                market_id=market.id,
                game_id=game.id,
                edge=signal.edge,
                signal_score=signal_score
            )
        
        # 8. Check edge persistence (longest)
        min_ticks = entry_rules.get("min_persistence_ticks", 4)
        if not self.check_edge_persistence(market.id, min_ticks, min_edge):
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason=f"Edge not persistent ({min_ticks} ticks required)",
                market_id=market.id,
                game_id=game.id,
                edge=signal.edge,
                signal_score=signal_score
            )
        
        # 9. Check momentum (required)
        if entry_rules.get("require_positive_momentum", True):
            momentum = getattr(signal, '_momentum_direction', 'neutral')
            if signal.edge > 0 and momentum == 'down':
                return StrategyDecision(
                    decision_type=DecisionType.BLOCK,
                    reason="Negative momentum (institutional requires alignment)",
                    market_id=market.id,
                    game_id=game.id,
                    edge=signal.edge
                )
            if signal.edge < 0 and momentum == 'up':
                return StrategyDecision(
                    decision_type=DecisionType.BLOCK,
                    reason="Positive momentum on short signal",
                    market_id=market.id,
                    game_id=game.id,
                    edge=signal.edge
                )
        
        # All institutional checks passed - this is a high-conviction trade
        side = "yes" if signal.edge > 0 else "no"
        size = self.calculate_size(signal, self.portfolio.available_capital)
        
        if size <= 0:
            return StrategyDecision(
                decision_type=DecisionType.BLOCK,
                reason="Calculated size is 0",
                market_id=market.id,
                game_id=game.id
            )
        
        # Track entry for adverse move calculation
        self._entry_prices[market.id] = market.implied_probability
        self._peak_prices[market.id] = market.implied_probability
        
        logger.info(f"[{self.strategy_id}] INSTITUTIONAL ENTRY: {side} {size}@{market.implied_probability:.2f}")
        
        return StrategyDecision(
            decision_type=DecisionType.ENTER,
            reason=f"Institutional entry: edge {signal.edge:.2%}, score {signal_score:.0f}, vol={vol_regime}",
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
        """Evaluate exit with institutional risk management."""
        
        exit_rules = self.config.exit_rules
        adverse_protection = self.config.get("adverse_move_protection", {})
        
        # Update peak price tracking
        if market.id in self._peak_prices:
            if position.side == "yes":
                self._peak_prices[market.id] = max(
                    self._peak_prices[market.id],
                    market.implied_probability
                )
            else:
                self._peak_prices[market.id] = min(
                    self._peak_prices[market.id],
                    market.implied_probability
                )
        
        # 1. Hard adverse move stop
        if adverse_protection.get("enable_hard_stop", True):
            hard_stop_pct = adverse_protection.get("hard_stop_pct", 0.05)
            entry_price = self._entry_prices.get(market.id, position.avg_entry_price)
            
            if position.side == "yes":
                adverse_move = entry_price - market.implied_probability
            else:
                adverse_move = market.implied_probability - entry_price
            
            if adverse_move > hard_stop_pct:
                return StrategyDecision(
                    decision_type=DecisionType.EXIT,
                    reason=f"HARD STOP: Adverse move {adverse_move:.1%} > {hard_stop_pct:.1%}",
                    market_id=market.id,
                    game_id=game.id,
                    side=position.side,
                    quantity=position.quantity,
                    price=market.implied_probability,
                    edge=signal.edge
                )
        
        # 2. Time-based adverse stop
        if adverse_protection.get("enable_time_stop", True):
            max_adverse_time = adverse_protection.get("max_adverse_time_seconds", 120)
            if position.unrealized_pnl < 0 and position.hold_time_seconds > max_adverse_time:
                return StrategyDecision(
                    decision_type=DecisionType.EXIT,
                    reason=f"Time stop: Adverse for {position.hold_time_seconds:.0f}s > {max_adverse_time}s",
                    market_id=market.id,
                    game_id=game.id,
                    side=position.side,
                    quantity=position.quantity,
                    price=market.implied_probability,
                    edge=signal.edge
                )
        
        # 3. Standard stop loss
        stop_loss_pct = exit_rules.get("stop_loss_pct", 0.08)
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
        
        # 4. Profit target (higher for institutional)
        profit_target_pct = exit_rules.get("profit_target_pct", 0.20)
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
        
        # 5. Edge compression exit
        exit_threshold = exit_rules.get("edge_compression_exit_threshold", 0.03)
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
                reason=f"Edge compressed (short)",
                market_id=market.id,
                game_id=game.id,
                side=position.side,
                quantity=position.quantity,
                price=market.implied_probability,
                edge=signal.edge
            )
        
        # 6. Time-based exit (longest hold time allowed)
        max_hold_time = exit_rules.get("time_based_exit_seconds", 900)
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
        
        # 7. Trailing stop from peak
        trailing_stop = exit_rules.get("trailing_stop_pct", 0.04)
        peak_price = self._peak_prices.get(market.id)
        if peak_price:
            if position.side == "yes":
                drop_from_peak = peak_price - market.implied_probability
            else:
                drop_from_peak = market.implied_probability - peak_price
            
            if drop_from_peak > trailing_stop and position.unrealized_pnl > 0:
                return StrategyDecision(
                    decision_type=DecisionType.EXIT,
                    reason=f"Trailing stop: {drop_from_peak:.1%} drop from peak",
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
        Calculate position size - most conservative sizing.
        Base: 1% of capital, limited scaling.
        """
        sizing = self.config.position_sizing
        
        # Base size (smallest)
        base_pct = sizing.get("base_size_pct", 0.01)
        base_amount = available_capital * base_pct
        
        # Scale with edge (conservative)
        if sizing.get("scale_with_edge", True):
            edge_scale = sizing.get("edge_scale_factor", 1.5)
            edge_mult = 1 + (abs(signal.edge) * edge_scale)
            base_amount *= min(edge_mult, 1.3)  # Cap at 1.3x
        
        # Apply Kelly fraction (smallest)
        kelly = sizing.get("kelly_fraction", 0.15)
        base_amount *= kelly
        
        # Max position check (tightest)
        max_pct = sizing.get("max_position_pct", 0.03)
        max_amount = self.portfolio.starting_capital * max_pct
        final_amount = min(base_amount, max_amount)
        
        # Convert to contracts
        avg_price = signal.market_prob if signal.market_prob > 0.1 else 0.50
        contracts = int(final_amount / avg_price)
        
        return max(1, min(contracts, 30))  # 1-30 contracts (smallest max)
    
    def reset_portfolio(self, starting_capital: Optional[float] = None):
        """Reset portfolio and tracking."""
        super().reset_portfolio(starting_capital)
        self._entry_prices.clear()
        self._peak_prices.clear()
