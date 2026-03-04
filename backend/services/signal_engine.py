"""
Signal Engine v2
Advanced trading signal generation with composite scoring.

Features:
- Composite SignalScore (0-100)
- Portfolio-aware recommendations
- Volatility regime detection
- Momentum tracking
- Clutch time adjustments
"""
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timedelta
from enum import Enum
import math
import logging

from models.game import Game, GameStatus
from models.market import Market
from models.signal import Signal, SignalType
from models.tick import ProbabilityTick
from models.position import Position
from config import settings

logger = logging.getLogger(__name__)

class VolatilityRegime(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    SPIKE = "spike"

class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class PositionState(str, Enum):
    FLAT = "flat"
    LONG = "long"
    SHORT = "short"

class SignalEngine:
    """
    Advanced signal generation with composite scoring.
    
    SignalScore = weighted combination of:
    - Edge magnitude (40%)
    - Time remaining factor (20%)
    - Volatility regime (15%)
    - Score differential (15%)
    - Momentum direction (10%)
    """
    
    # Weights for composite score
    WEIGHT_EDGE = 0.40
    WEIGHT_TIME = 0.20
    WEIGHT_VOLATILITY = 0.15
    WEIGHT_SCORE_DIFF = 0.15
    WEIGHT_MOMENTUM = 0.10
    
    # Signal thresholds
    EDGE_STRONG_BUY = 0.05
    EDGE_BUY = 0.03
    EDGE_SELL = 0.0
    EDGE_STRONG_SELL = -0.05
    
    # Volatility spike detection
    VOLATILITY_SPIKE_THRESHOLD = 0.08  # 8% change in 60 seconds
    VOLATILITY_HIGH_THRESHOLD = 0.04
    VOLATILITY_MEDIUM_THRESHOLD = 0.02
    
    # Clutch time settings
    CLUTCH_TIME_SECONDS = 300  # 5 minutes
    
    def __init__(self):
        # Recent probability history for momentum/volatility
        self._prob_history: Dict[str, List[Tuple[datetime, float]]] = {}
        self._last_volatility_spike: Dict[str, datetime] = {}
    
    def generate_signal(
        self,
        game: Game,
        market: Market,
        fair_prob: float,
        confidence: float = 0.5,
        position: Optional[Position] = None
    ) -> Signal:
        """
        Generate a comprehensive trading signal.
        
        Args:
            game: Current game state
            market: Kalshi market
            fair_prob: Our calculated fair probability
            confidence: Model confidence
            position: User's current position (for portfolio-aware signals)
            
        Returns:
            Signal with composite score and portfolio-aware recommendation
        """
        market_prob = market.implied_probability
        edge = fair_prob - market_prob
        
        # Track probability history for momentum/volatility
        self._update_prob_history(game.id, market_prob)
        
        # Calculate component scores
        edge_score = self._calculate_edge_score(edge)
        time_score = self._calculate_time_score(game)
        volatility_score, volatility_regime = self._calculate_volatility_score(game.id)
        score_diff_score = self._calculate_score_diff_score(game)
        momentum_score, momentum_direction = self._calculate_momentum_score(game.id)
        
        # Composite signal score (0-100)
        signal_score = (
            edge_score * self.WEIGHT_EDGE +
            time_score * self.WEIGHT_TIME +
            volatility_score * self.WEIGHT_VOLATILITY +
            score_diff_score * self.WEIGHT_SCORE_DIFF +
            momentum_score * self.WEIGHT_MOMENTUM
        )
        
        # Clutch time adjustment
        is_clutch = self._is_clutch_time(game)
        if is_clutch:
            # Boost score impact in clutch
            signal_score = min(100, signal_score * 1.15)
        
        # Determine signal type based on edge and score
        signal_type = self._determine_signal_type(edge, game, signal_score)
        
        # Risk tier
        risk_tier = self._determine_risk_tier(volatility_regime, is_clutch, edge)
        
        # Portfolio-aware recommendation
        position_state = self._get_position_state(position)
        recommended_action, recommended_side = self._get_portfolio_aware_recommendation(
            signal_type, edge, position_state, position
        )
        
        # Calculate position sizing
        recommended_size = self._calculate_position_size(
            signal_score=signal_score,
            edge=edge,
            confidence=confidence,
            risk_tier=risk_tier,
            is_clutch=is_clutch
        )
        
        # Trade analytics
        analytics = self._calculate_trade_analytics(
            edge=edge,
            fair_prob=fair_prob,
            market_prob=market_prob,
            recommended_size=recommended_size
        )
        
        # Detect volatility spike
        volatility_spike_detected = self._detect_volatility_spike(game.id)
        
        signal = Signal(
            game_id=game.id,
            market_id=market.id,
            signal_type=signal_type,
            edge=round(edge, 4),
            fair_prob=round(fair_prob, 4),
            market_prob=round(market_prob, 4),
            confidence=round(signal_score / 100, 2),  # Use signal score as confidence
            volatility=round(self._get_recent_volatility(game.id), 4),
            recommended_side=recommended_side,
            recommended_size=round(recommended_size, 2),
            max_loss=round(analytics['max_risk'], 2),
            expected_value=round(analytics['expected_value'], 2),
            score_diff=game.score_differential,
            time_remaining_seconds=game.total_seconds_remaining,
            quarter=game.quarter,
            generated_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=30)
        )
        
        # Add extended attributes
        signal._signal_score = signal_score
        signal._risk_tier = risk_tier
        signal._volatility_regime = volatility_regime
        signal._momentum_direction = momentum_direction
        signal._is_clutch = is_clutch
        signal._position_state = position_state
        signal._recommended_action = recommended_action
        signal._volatility_spike = volatility_spike_detected
        signal._analytics = analytics
        
        return signal
    
    def _calculate_edge_score(self, edge: float) -> float:
        """Convert edge to 0-100 score. Higher edge = higher score."""
        # Normalize edge: 0% = 50, +10% = 100, -10% = 0
        normalized = (edge + 0.10) / 0.20 * 100
        return max(0, min(100, normalized))
    
    def _calculate_time_score(self, game: Game) -> float:
        """
        Time remaining factor.
        Late game = higher score (more certain outcomes).
        """
        if game.status != GameStatus.LIVE:
            return 50
        
        progress = game.game_progress  # 0-1
        # Exponential increase in late game
        return min(100, 30 + (progress ** 2) * 70)
    
    def _calculate_volatility_score(self, game_id: str) -> Tuple[float, VolatilityRegime]:
        """
        Calculate volatility score.
        High volatility = lower score (more uncertain).
        """
        volatility = self._get_recent_volatility(game_id)
        
        if volatility >= self.VOLATILITY_SPIKE_THRESHOLD:
            regime = VolatilityRegime.SPIKE
            score = 20
        elif volatility >= self.VOLATILITY_HIGH_THRESHOLD:
            regime = VolatilityRegime.HIGH
            score = 40
        elif volatility >= self.VOLATILITY_MEDIUM_THRESHOLD:
            regime = VolatilityRegime.MEDIUM
            score = 60
        else:
            regime = VolatilityRegime.LOW
            score = 80
        
        return score, regime
    
    def _calculate_score_diff_score(self, game: Game) -> float:
        """
        Score differential factor.
        Larger leads = higher certainty = higher score.
        """
        if game.status != GameStatus.LIVE:
            return 50
        
        abs_diff = abs(game.score_differential)
        # Normalize: 0 points = 50, 20+ points = 100
        score = min(100, 50 + (abs_diff / 20) * 50)
        return score
    
    def _calculate_momentum_score(self, game_id: str) -> Tuple[float, str]:
        """
        Calculate momentum based on recent probability changes.
        Returns score and direction.
        """
        history = self._prob_history.get(game_id, [])
        if len(history) < 3:
            return 50, "neutral"
        
        # Get trend over last 5 readings
        recent = [h[1] for h in history[-5:]]
        
        if len(recent) < 2:
            return 50, "neutral"
        
        # Calculate average change
        changes = [recent[i+1] - recent[i] for i in range(len(recent)-1)]
        avg_change = sum(changes) / len(changes)
        
        if avg_change > 0.01:
            direction = "up"
            score = min(100, 60 + abs(avg_change) * 500)
        elif avg_change < -0.01:
            direction = "down"
            score = min(100, 60 + abs(avg_change) * 500)
        else:
            direction = "neutral"
            score = 50
        
        return score, direction
    
    def _determine_signal_type(self, edge: float, game: Game, signal_score: float) -> SignalType:
        """Determine signal type based on edge and context."""
        # Late game sell-into-strength rule
        if self._should_sell_into_strength(game, edge):
            return SignalType.SELL_INTO_STRENGTH
        
        # Edge-based signals
        if edge >= self.EDGE_STRONG_BUY:
            return SignalType.STRONG_BUY
        elif edge >= self.EDGE_BUY:
            return SignalType.BUY
        elif edge <= self.EDGE_STRONG_SELL:
            return SignalType.STRONG_SELL
        elif edge <= self.EDGE_SELL:
            return SignalType.SELL
        else:
            return SignalType.HOLD
    
    def _should_sell_into_strength(self, game: Game, edge: float) -> bool:
        """Check for late-game sell-into-strength condition."""
        if game.status != GameStatus.LIVE:
            return False
        
        if game.quarter < 4 or game.total_seconds_remaining > 360:
            return False
        
        # Large lead with positive edge (we're winning big)
        if abs(game.score_differential) >= 6 and edge > 0.03:
            return True
        
        return False
    
    def _determine_risk_tier(
        self, 
        volatility_regime: VolatilityRegime,
        is_clutch: bool,
        edge: float
    ) -> RiskTier:
        """Determine risk tier for the signal."""
        if volatility_regime == VolatilityRegime.SPIKE:
            return RiskTier.HIGH
        
        if is_clutch and abs(edge) < 0.03:
            return RiskTier.HIGH
        
        if volatility_regime == VolatilityRegime.HIGH:
            return RiskTier.MEDIUM
        
        if abs(edge) >= 0.05:
            return RiskTier.LOW
        elif abs(edge) >= 0.03:
            return RiskTier.MEDIUM
        else:
            return RiskTier.HIGH
    
    def _get_position_state(self, position: Optional[Position]) -> PositionState:
        """Get user's current position state."""
        if not position or not position.is_open:
            return PositionState.FLAT
        
        if position.side == "yes":
            return PositionState.LONG
        else:
            return PositionState.SHORT
    
    def _get_portfolio_aware_recommendation(
        self,
        signal_type: SignalType,
        edge: float,
        position_state: PositionState,
        position: Optional[Position]
    ) -> Tuple[str, str]:
        """
        Generate portfolio-aware recommendation.
        Returns (action, side).
        """
        if position_state == PositionState.FLAT:
            # No position - recommend ENTER if signal is actionable
            if signal_type in [SignalType.STRONG_BUY, SignalType.BUY]:
                return "ENTER_LONG", "yes"
            elif signal_type in [SignalType.STRONG_SELL, SignalType.SELL]:
                return "ENTER_SHORT", "no"
            return "WAIT", "none"
        
        elif position_state == PositionState.LONG:
            # Already long on YES
            if signal_type == SignalType.SELL_INTO_STRENGTH:
                return "EXIT", "no"  # Close position
            elif signal_type in [SignalType.STRONG_SELL, SignalType.SELL]:
                return "EXIT", "no"
            elif edge > 0.05:
                return "HOLD", "none"
            elif edge > 0.02:
                return "HOLD", "none"
            elif edge < 0:
                return "TRIM", "no"  # Reduce position
            return "HOLD", "none"
        
        else:  # SHORT
            # Already short on NO
            if signal_type in [SignalType.STRONG_BUY, SignalType.BUY]:
                return "COVER", "yes"  # Close short
            elif edge < -0.03:
                return "HOLD", "none"
            elif edge > 0:
                return "COVER", "yes"
            return "HOLD", "none"
    
    def _calculate_position_size(
        self,
        signal_score: float,
        edge: float,
        confidence: float,
        risk_tier: RiskTier,
        is_clutch: bool
    ) -> float:
        """Calculate recommended position size based on Kelly-inspired formula."""
        base_size = 25.0  # Base position
        
        # Signal score multiplier (50=1x, 100=2x, 0=0.5x)
        score_mult = 0.5 + (signal_score / 100)
        
        # Edge multiplier
        edge_mult = min(2.0, 1 + abs(edge) * 10)
        
        # Risk tier adjustment
        risk_mult = {
            RiskTier.LOW: 1.2,
            RiskTier.MEDIUM: 1.0,
            RiskTier.HIGH: 0.6
        }[risk_tier]
        
        # Clutch time: reduce sizing
        clutch_mult = 0.8 if is_clutch else 1.0
        
        size = base_size * score_mult * edge_mult * risk_mult * clutch_mult
        
        return min(size, settings.max_position_size)
    
    def _calculate_trade_analytics(
        self,
        edge: float,
        fair_prob: float,
        market_prob: float,
        recommended_size: float
    ) -> Dict:
        """Calculate comprehensive trade analytics."""
        # Expected value
        ev = edge * recommended_size
        
        # Max risk (lose entire stake)
        max_risk = recommended_size
        
        # Break-even probability
        break_even_prob = market_prob
        
        # Suggested exit (lock in profit at 80% of fair prob edge)
        suggested_exit_prob = market_prob + (edge * 0.8)
        
        # Suggested stop (cut loss at 50% of edge against)
        suggested_stop_prob = market_prob - (abs(edge) * 0.5)
        
        # Risk-reward ratio
        potential_profit = recommended_size * abs(edge)
        risk_reward = potential_profit / max_risk if max_risk > 0 else 0
        
        return {
            'expected_value': ev,
            'max_risk': max_risk,
            'break_even_prob': round(break_even_prob, 4),
            'suggested_exit_prob': round(min(0.95, max(0.05, suggested_exit_prob)), 4),
            'suggested_stop_prob': round(min(0.95, max(0.05, suggested_stop_prob)), 4),
            'risk_reward_ratio': round(risk_reward, 2)
        }
    
    def _update_prob_history(self, game_id: str, prob: float):
        """Update probability history for momentum/volatility tracking."""
        now = datetime.utcnow()
        if game_id not in self._prob_history:
            self._prob_history[game_id] = []
        
        self._prob_history[game_id].append((now, prob))
        
        # Keep only last 2 minutes of data
        cutoff = now - timedelta(minutes=2)
        self._prob_history[game_id] = [
            (t, p) for t, p in self._prob_history[game_id] if t > cutoff
        ]
    
    def _get_recent_volatility(self, game_id: str) -> float:
        """Calculate recent volatility (60-second rolling)."""
        history = self._prob_history.get(game_id, [])
        if len(history) < 2:
            return 0.0
        
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=60)
        recent = [p for t, p in history if t > cutoff]
        
        if len(recent) < 2:
            return 0.0
        
        # Calculate max swing in last 60 seconds
        return max(recent) - min(recent)
    
    def _detect_volatility_spike(self, game_id: str) -> bool:
        """Detect if a volatility spike occurred."""
        volatility = self._get_recent_volatility(game_id)
        
        if volatility >= self.VOLATILITY_SPIKE_THRESHOLD:
            now = datetime.utcnow()
            last_spike = self._last_volatility_spike.get(game_id)
            
            # Only report spike once per minute
            if not last_spike or (now - last_spike).seconds > 60:
                self._last_volatility_spike[game_id] = now
                logger.warning(f"VOLATILITY SPIKE detected for {game_id}: {volatility:.1%}")
                return True
        
        return False
    
    def _is_clutch_time(self, game: Game) -> bool:
        """Check if game is in clutch time."""
        return (
            game.status == GameStatus.LIVE and
            game.quarter >= 4 and
            game.total_seconds_remaining <= self.CLUTCH_TIME_SECONDS
        )
    
    def create_probability_tick(
        self,
        game: Game,
        market_prob: float,
        fair_prob: float,
        signal_type: SignalType
    ) -> ProbabilityTick:
        """Create a probability tick for time-series storage."""
        return ProbabilityTick(
            game_id=game.id,
            timestamp=datetime.utcnow(),
            market_prob=round(market_prob, 4),
            fair_prob=round(fair_prob, 4),
            edge=round(fair_prob - market_prob, 4),
            home_score=game.home_score,
            away_score=game.away_score,
            score_diff=game.score_differential,
            quarter=game.quarter,
            time_remaining_seconds=game.total_seconds_remaining,
            signal=signal_type.value
        )
    
    def get_market_intelligence(self, game_id: str) -> Dict:
        """Get market intelligence metrics."""
        history = self._prob_history.get(game_id, [])
        
        if len(history) < 2:
            return {
                'trend_5min': 'neutral',
                'trend_30min': 'neutral',
                'volatility_regime': 'low',
                'momentum': 'neutral',
                'volatility_value': 0.0
            }
        
        now = datetime.utcnow()
        
        # 5-minute trend
        cutoff_5m = now - timedelta(minutes=5)
        recent_5m = [p for t, p in history if t > cutoff_5m]
        trend_5m = self._calculate_trend(recent_5m)
        
        # Use all available data for longer trend
        trend_30m = self._calculate_trend([p for _, p in history])
        
        # Volatility regime
        vol = self._get_recent_volatility(game_id)
        if vol >= self.VOLATILITY_SPIKE_THRESHOLD:
            vol_regime = 'spike'
        elif vol >= self.VOLATILITY_HIGH_THRESHOLD:
            vol_regime = 'high'
        elif vol >= self.VOLATILITY_MEDIUM_THRESHOLD:
            vol_regime = 'medium'
        else:
            vol_regime = 'low'
        
        # Momentum
        _, momentum = self._calculate_momentum_score(game_id)
        
        return {
            'trend_5min': trend_5m,
            'trend_30min': trend_30m,
            'volatility_regime': vol_regime,
            'momentum': momentum,
            'volatility_value': round(vol, 4)
        }
    
    def _calculate_trend(self, probs: List[float]) -> str:
        """Calculate trend direction from probability list."""
        if len(probs) < 2:
            return 'neutral'
        
        change = probs[-1] - probs[0]
        if change > 0.02:
            return 'up'
        elif change < -0.02:
            return 'down'
        return 'neutral'
