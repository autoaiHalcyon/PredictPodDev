"""
Capital Preview Engine

Generates comprehensive capital allocation projections for each game and trading model.
Shows "What To Expect" before any trade execution.

Features:
- Per-game, per-model projections
- Suggested bet sizing based on Kelly criterion
- Entry/exit price targets with stop losses
- Expected profit, max risk, and EV calculations
- Risk/reward ratio analysis
- Confidence scoring
"""
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math

from models.game import Game
from models.market import Market
from models.signal import Signal
from strategies.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    MINIMAL = "minimal"     # < 1% portfolio
    LOW = "low"             # 1-2%
    MODERATE = "moderate"   # 2-5%
    HIGH = "high"           # 5-10%
    AGGRESSIVE = "aggressive"  # > 10%


@dataclass
class CapitalProjection:
    """
    Capital allocation projection for a specific game and model.
    This is the "What To Expect" panel data.
    """
    # Identifiers
    model_id: str
    model_name: str
    game_id: str
    market_ticker: str
    
    # Trade Parameters
    suggested_side: str  # "yes" or "no"
    suggested_quantity: int
    suggested_bet_size_dollars: float
    
    # Entry/Exit
    entry_price_cents: int
    target_exit_cents: int
    stop_loss_cents: int
    
    # Expected Outcomes
    expected_profit_dollars: float
    maximum_risk_dollars: float
    risk_reward_ratio: float
    expected_value_dollars: float
    
    # Confidence & Analysis
    confidence_pct: float
    edge_pct: float
    win_probability_pct: float
    
    # Risk Categorization
    risk_level: RiskLevel
    portfolio_risk_pct: float  # % of portfolio at risk
    
    # Slippage & Spread (Conservative Fill Assumptions) - with defaults
    estimated_slippage_cents: int = 2
    estimated_spread_cents: int = 4
    slippage_cost_dollars: float = 0.0
    
    # Timing
    time_to_close_minutes: Optional[int] = None
    liquidity_score: float = 0.0  # 0-100
    
    # Reasoning
    entry_reason: str = ""
    risk_factors: List[str] = field(default_factory=list)
    
    # Timestamps
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "game_id": self.game_id,
            "market_ticker": self.market_ticker,
            "suggested_side": self.suggested_side,
            "suggested_quantity": self.suggested_quantity,
            "suggested_bet_size_dollars": round(self.suggested_bet_size_dollars, 2),
            "entry_price_cents": self.entry_price_cents,
            "target_exit_cents": self.target_exit_cents,
            "stop_loss_cents": self.stop_loss_cents,
            "expected_profit_dollars": round(self.expected_profit_dollars, 2),
            "maximum_risk_dollars": round(self.maximum_risk_dollars, 2),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "expected_value_dollars": round(self.expected_value_dollars, 2),
            "estimated_slippage_cents": self.estimated_slippage_cents,
            "estimated_spread_cents": self.estimated_spread_cents,
            "slippage_cost_dollars": round(self.slippage_cost_dollars, 2),
            "confidence_pct": round(self.confidence_pct, 1),
            "edge_pct": round(self.edge_pct, 2),
            "win_probability_pct": round(self.win_probability_pct, 1),
            "risk_level": self.risk_level.value,
            "portfolio_risk_pct": round(self.portfolio_risk_pct, 2),
            "time_to_close_minutes": self.time_to_close_minutes,
            "liquidity_score": round(self.liquidity_score, 1),
            "entry_reason": self.entry_reason,
            "risk_factors": self.risk_factors,
            "generated_at": self.generated_at.isoformat()
        }


@dataclass 
class GameCapitalPreview:
    """
    Complete capital preview for a game across all models.
    """
    game_id: str
    game_title: str
    market_ticker: str
    market_status: str
    
    # Current market state
    current_yes_price: int
    current_no_price: int
    fair_probability: float
    market_edge: float
    
    # Model projections
    model_projections: Dict[str, CapitalProjection] = field(default_factory=dict)
    
    # Aggregate recommendation
    consensus_side: Optional[str] = None
    models_agree_count: int = 0
    best_risk_reward_model: Optional[str] = None
    
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        return {
            "game_id": self.game_id,
            "game_title": self.game_title,
            "market_ticker": self.market_ticker,
            "market_status": self.market_status,
            "current_yes_price": self.current_yes_price,
            "current_no_price": self.current_no_price,
            "fair_probability": round(self.fair_probability, 3),
            "market_edge": round(self.market_edge, 3),
            "model_projections": {k: v.to_dict() for k, v in self.model_projections.items()},
            "consensus_side": self.consensus_side,
            "models_agree_count": self.models_agree_count,
            "best_risk_reward_model": self.best_risk_reward_model,
            "generated_at": self.generated_at.isoformat()
        }


class CapitalPreviewEngine:
    """
    Engine for generating capital allocation projections.
    
    For every game and model, calculates:
    - Optimal bet size (Kelly criterion with fractional)
    - Entry/exit targets
    - Expected profit and risk
    - Confidence and EV
    """
    
    # Default parameters
    KELLY_FRACTION = 0.25  # Quarter Kelly for safety
    MIN_EDGE_FOR_BET = 0.02  # 2% minimum edge
    MAX_PORTFOLIO_RISK = 0.05  # 5% max per trade
    DEFAULT_STOP_LOSS_PCT = 0.20  # 20% stop loss
    DEFAULT_PROFIT_TARGET_PCT = 0.15  # 15% profit target
    
    def __init__(self, strategies: Dict[str, BaseStrategy]):
        """
        Initialize with strategy instances.
        
        Args:
            strategies: Dict of strategy_id -> BaseStrategy instance
        """
        self.strategies = strategies
        self._projections_cache: Dict[str, GameCapitalPreview] = {}
        logger.info("CapitalPreviewEngine initialized")
    
    def generate_game_preview(
        self,
        game: Game,
        market: Market,
        signal: Signal,
        orderbook: Optional[Dict] = None
    ) -> GameCapitalPreview:
        """
        Generate complete capital preview for a game.
        
        Args:
            game: Game data
            market: Market data with pricing
            signal: Current signal with edge/probability
            orderbook: Optional orderbook for liquidity analysis
            
        Returns:
            GameCapitalPreview with all model projections
        """
        # Get current prices (in cents)
        yes_price = int(market.yes_price * 100) if market.yes_price else 50
        no_price = 100 - yes_price
        
        # Get fair probability and edge from signal
        fair_prob = getattr(signal, 'fair_prob', market.implied_probability or 0.5)
        edge = getattr(signal, 'edge', 0)
        
        game_title = f"{game.away_team.abbreviation} @ {game.home_team.abbreviation}"
        
        preview = GameCapitalPreview(
            game_id=game.id,
            game_title=game_title,
            market_ticker=market.kalshi_ticker or market.id,
            market_status=market.status if hasattr(market, 'status') else "active",
            current_yes_price=yes_price,
            current_no_price=no_price,
            fair_probability=fair_prob,
            market_edge=edge
        )
        
        # Calculate liquidity score from orderbook
        liquidity_score = self._calculate_liquidity_score(orderbook)
        
        # Generate projection for each model
        for model_id, strategy in self.strategies.items():
            projection = self._generate_model_projection(
                model_id=model_id,
                strategy=strategy,
                game=game,
                market=market,
                signal=signal,
                fair_prob=fair_prob,
                edge=edge,
                liquidity_score=liquidity_score,
                orderbook=orderbook
            )
            preview.model_projections[model_id] = projection
        
        # Calculate consensus
        self._calculate_consensus(preview)
        
        # Cache
        self._projections_cache[game.id] = preview
        
        return preview
    
    def _generate_model_projection(
        self,
        model_id: str,
        strategy: BaseStrategy,
        game: Game,
        market: Market,
        signal: Signal,
        fair_prob: float,
        edge: float,
        liquidity_score: float,
        orderbook: Optional[Dict] = None
    ) -> CapitalProjection:
        """Generate projection for a specific model"""
        
        # Get strategy config
        config = strategy.config._config
        display_name = strategy.display_name
        
        # Get portfolio state
        portfolio = strategy.portfolio
        available_capital = portfolio.available_capital
        total_capital = portfolio.starting_capital
        
        # Determine trade side based on edge
        yes_price = market.yes_price or 0.5
        
        if edge > 0:
            # Fair prob > market prob -> BUY YES
            suggested_side = "yes"
            entry_price = int(yes_price * 100)
            win_prob = fair_prob
        else:
            # Market overpricing YES -> BUY NO
            suggested_side = "no"
            entry_price = int((1 - yes_price) * 100)
            win_prob = 1 - fair_prob
        
        # Calculate optimal bet size using Kelly criterion
        kelly_fraction = self._calculate_kelly_bet(
            win_probability=win_prob,
            edge=abs(edge),
            available_capital=available_capital
        )
        
        # Apply model-specific risk settings
        model_max_risk = config.get("risk", {}).get("max_position_pct", 0.05)
        position_fraction = min(kelly_fraction, model_max_risk)
        
        bet_size_dollars = available_capital * position_fraction
        quantity = int(bet_size_dollars / (entry_price / 100)) if entry_price > 0 else 0
        
        # Calculate targets
        profit_target_pct = config.get("exit", {}).get("profit_target_pct", self.DEFAULT_PROFIT_TARGET_PCT)
        stop_loss_pct = config.get("exit", {}).get("stop_loss_pct", self.DEFAULT_STOP_LOSS_PCT)
        
        target_exit = min(99, int(entry_price * (1 + profit_target_pct)))
        stop_loss = max(1, int(entry_price * (1 - stop_loss_pct)))
        
        # SLIPPAGE & SPREAD PENALTY (Conservative fill assumptions)
        # Estimate 1-2 cents slippage on entry
        slippage_cents = 2
        # Spread cost (half spread on entry, half on exit)
        spread = orderbook.get("spread_cents", 4) if orderbook else 4
        spread_penalty_cents = spread  # Full spread as penalty
        
        # Adjusted entry price (higher for buys due to crossing spread)
        adjusted_entry_price = entry_price + slippage_cents + (spread_penalty_cents // 2)
        
        # Calculate expected outcomes with slippage
        expected_profit = quantity * (target_exit - adjusted_entry_price) / 100 * win_prob
        max_risk = quantity * (adjusted_entry_price - stop_loss) / 100
        
        # Include slippage in profit calculation (conservative)
        slippage_cost = quantity * (slippage_cents + spread_penalty_cents) / 100
        expected_profit -= slippage_cost
        
        risk_reward = expected_profit / max_risk if max_risk > 0 else 0
        
        # Expected value
        ev = (win_prob * (target_exit - entry_price) - (1 - win_prob) * (entry_price - stop_loss)) / 100 * quantity
        
        # Confidence score (combine edge, liquidity, signal strength)
        signal_score = getattr(signal, '_signal_score', 50)
        confidence = min(95, (abs(edge) * 200 + liquidity_score * 0.3 + signal_score * 0.3))
        
        # Risk level categorization
        portfolio_risk = bet_size_dollars / total_capital if total_capital > 0 else 0
        risk_level = self._categorize_risk(portfolio_risk)
        
        # Entry reasoning
        entry_reason = self._generate_entry_reason(
            edge=edge,
            signal=signal,
            model_id=model_id
        )
        
        # Risk factors
        risk_factors = self._identify_risk_factors(
            game=game,
            market=market,
            liquidity_score=liquidity_score,
            edge=edge
        )
        
        return CapitalProjection(
            model_id=model_id,
            model_name=display_name,
            game_id=game.id,
            market_ticker=market.kalshi_ticker or market.id,
            suggested_side=suggested_side,
            suggested_quantity=quantity,
            suggested_bet_size_dollars=bet_size_dollars,
            entry_price_cents=entry_price,
            target_exit_cents=target_exit,
            stop_loss_cents=stop_loss,
            expected_profit_dollars=expected_profit,
            maximum_risk_dollars=max_risk,
            risk_reward_ratio=risk_reward,
            expected_value_dollars=ev,
            estimated_slippage_cents=slippage_cents,
            estimated_spread_cents=spread,
            slippage_cost_dollars=slippage_cost,
            confidence_pct=confidence,
            edge_pct=abs(edge) * 100,
            win_probability_pct=win_prob * 100,
            risk_level=risk_level,
            portfolio_risk_pct=portfolio_risk * 100,
            liquidity_score=liquidity_score,
            entry_reason=entry_reason,
            risk_factors=risk_factors
        )
    
    def _calculate_kelly_bet(
        self,
        win_probability: float,
        edge: float,
        available_capital: float
    ) -> float:
        """
        Calculate Kelly criterion bet size.
        
        Kelly formula: f = (bp - q) / b
        where:
        - b = odds received (payout ratio)
        - p = probability of win
        - q = probability of loss (1 - p)
        
        Returns fraction of bankroll to bet (capped and fractional Kelly applied)
        """
        if edge < self.MIN_EDGE_FOR_BET:
            return 0.0
        
        # For binary markets, assume roughly 1:1 odds
        b = 1.0
        p = win_probability
        q = 1 - p
        
        kelly = (b * p - q) / b if b > 0 else 0
        
        # Apply fractional Kelly and cap
        fractional_kelly = kelly * self.KELLY_FRACTION
        capped = min(fractional_kelly, self.MAX_PORTFOLIO_RISK)
        
        return max(0, capped)
    
    def _calculate_liquidity_score(self, orderbook: Optional[Dict]) -> float:
        """Calculate liquidity score from orderbook (0-100)"""
        if not orderbook:
            return 50.0  # Default medium liquidity
        
        total_liquidity = orderbook.get("total_liquidity", 0)
        spread = orderbook.get("spread_cents", 10)
        
        # Scoring factors
        liquidity_points = min(50, total_liquidity / 100)  # Max 50 points for volume
        spread_points = max(0, 50 - spread * 5)  # Lower spread = more points
        
        return liquidity_points + spread_points
    
    def _categorize_risk(self, portfolio_risk: float) -> RiskLevel:
        """Categorize risk level based on portfolio percentage"""
        if portfolio_risk < 0.01:
            return RiskLevel.MINIMAL
        elif portfolio_risk < 0.02:
            return RiskLevel.LOW
        elif portfolio_risk < 0.05:
            return RiskLevel.MODERATE
        elif portfolio_risk < 0.10:
            return RiskLevel.HIGH
        else:
            return RiskLevel.AGGRESSIVE
    
    def _generate_entry_reason(
        self,
        edge: float,
        signal: Signal,
        model_id: str
    ) -> str:
        """Generate human-readable entry reason"""
        signal_type = signal.signal_type.value if hasattr(signal, 'signal_type') else "neutral"
        edge_pct = abs(edge) * 100
        
        if edge_pct < 2:
            return "No significant edge detected"
        
        direction = "BUY YES" if edge > 0 else "BUY NO"
        
        reasons = []
        reasons.append(f"{direction} - {edge_pct:.1f}% edge detected")
        
        if signal_type != "neutral":
            reasons.append(f"Signal: {signal_type.upper()}")
        
        if "disciplined" in model_id:
            reasons.append("Meets strict entry criteria")
        elif "high_frequency" in model_id:
            reasons.append("Quick momentum opportunity")
        elif "institutional" in model_id:
            reasons.append("Risk-adjusted opportunity")
        
        return " | ".join(reasons)
    
    def _identify_risk_factors(
        self,
        game: Game,
        market: Market,
        liquidity_score: float,
        edge: float
    ) -> List[str]:
        """Identify risk factors for the trade"""
        factors = []
        
        if liquidity_score < 30:
            factors.append("LOW LIQUIDITY - May experience slippage")
        
        if abs(edge) < 0.03:
            factors.append("THIN EDGE - Small margin for error")
        
        if game.status.value == "live":
            factors.append("LIVE GAME - High volatility expected")
        
        if hasattr(game, 'quarter') and game.quarter >= 4:
            factors.append("LATE GAME - Increased uncertainty")
        
        return factors
    
    def _calculate_consensus(self, preview: GameCapitalPreview):
        """Calculate consensus across models"""
        if not preview.model_projections:
            return
        
        # Count sides
        yes_count = 0
        no_count = 0
        best_rr = 0
        best_rr_model = None
        
        for model_id, proj in preview.model_projections.items():
            if proj.suggested_side == "yes":
                yes_count += 1
            else:
                no_count += 1
            
            if proj.risk_reward_ratio > best_rr:
                best_rr = proj.risk_reward_ratio
                best_rr_model = model_id
        
        if yes_count > no_count:
            preview.consensus_side = "yes"
            preview.models_agree_count = yes_count
        elif no_count > yes_count:
            preview.consensus_side = "no"
            preview.models_agree_count = no_count
        else:
            preview.consensus_side = None
            preview.models_agree_count = 0
        
        preview.best_risk_reward_model = best_rr_model
    
    def get_all_previews(self) -> Dict[str, Dict]:
        """Get all cached previews"""
        return {k: v.to_dict() for k, v in self._projections_cache.items()}
    
    def get_preview(self, game_id: str) -> Optional[Dict]:
        """Get preview for a specific game"""
        if game_id in self._projections_cache:
            return self._projections_cache[game_id].to_dict()
        return None


# Global instance (initialized with strategies)
capital_preview_engine: Optional[CapitalPreviewEngine] = None
