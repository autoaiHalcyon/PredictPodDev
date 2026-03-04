"""
PredictPod API Server v2
Probability Intelligence Terminal for Prediction Markets

Enhanced with:
- Real-time chart data endpoints
- Portfolio-aware signals
- Market intelligence
- Trade analytics
- Volatility spike detection
- Rate limiting
- Production-ready health checks
"""
from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager
from routes.trades import router as trades_router
from routes.auth import router as auth_router, set_auth_service
from routes.decisions import router as decisions_router
from routes.debug import router as debug_router
from services.log_sanitizer import install_log_sanitizer
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
import logging
import json
import os
import time

from config import settings
from models import *
from repositories import *
from repositories.user_repository import UserRepository, PasswordResetTokenRepository
from services import *
from services.auth_service import AuthService
from services.signal_engine import SignalEngine
from adapters import ESPNAdapter, MockKalshiAdapter
from services import decision_tracer as _decision_tracer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Install PII/secrets scrubber immediately so no sensitive data leaks
install_log_sanitizer()
logger = logging.getLogger(__name__)

# Rate limiting storage
rate_limit_storage: Dict[str, List[float]] = defaultdict(list)

# Global instances
db = None
game_repo: GameRepository = None
market_repo: MarketRepository = None
position_repo: PositionRepository = None
trade_repo: TradeRepository = None
tick_repo: TickRepository = None
settings_repo = None
order_repo = None

espn_adapter: ESPNAdapter = None
kalshi_adapter: MockKalshiAdapter = None
sandbox_adapter = None

prob_engine: ProbabilityEngine = None
signal_engine: SignalEngine = None
trade_engine: TradeEngine = None
risk_engine: RiskEngine = None
portfolio_service: PortfolioService = None
kalshi_settings_service = None
order_lifecycle_service = None

# Authentication related globals
user_repo: UserRepository = None
reset_token_repo: PasswordResetTokenRepository = None
auth_service: AuthService = None

# Application start time for uptime tracking
app_start_time: datetime = None

# JSON serializer that handles datetime/date objects
def _json_serial(obj):
    """JSON serializer for objects not serializable by default json encoder."""
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        try:
            text = json.dumps(message, default=_json_serial)
        except Exception as e:
            logger.error(f"Broadcast serialization error: {e}")
            return
        for connection in self.active_connections:
            try:
                await connection.send_text(text)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")

ws_manager = ConnectionManager()

# Background update task
async def update_loop():
    """Background task for real-time updates every 3-5 seconds"""
    while True:
        try:
            if espn_adapter and kalshi_adapter:
                await update_all_data()
        except Exception as e:
            logger.error(f"Update loop error: {e}")
        await asyncio.sleep(settings.market_refresh_interval)

async def update_all_data():
    """Fetch latest data and broadcast updates"""
    games = await espn_adapter.get_todays_games()
    
    updates = []
    volatility_spikes = []
    
    for game in games:
        await game_repo.upsert_by_espn_id(game)
        
        # Get/create mock markets
        markets = await kalshi_adapter.get_markets_for_game(game.id)
        home_market = next((m for m in markets if m.outcome == "home"), None)
        
        if not home_market:
            continue
        
        # Get user position for portfolio-aware signals
        position = await kalshi_adapter.get_position(home_market.id)
        
        # Calculate probability using market as anchor for pre-game
        home_prob, away_prob = prob_engine.calculate_win_probability(
            game, 
            market_prob=home_market.implied_probability
        )
        confidence = prob_engine.get_probability_confidence(game)
        
        # Update mock market prices
        kalshi_adapter.update_market_prices(game.id, home_prob)
        markets = await kalshi_adapter.get_markets_for_game(game.id)
        home_market = next((m for m in markets if m.outcome == "home"), None)
        
        # Generate signal with position awareness
        signal = signal_engine.generate_signal(
            game, home_market, home_prob, confidence, position
        )
        
        # Store probability tick
        tick = signal_engine.create_probability_tick(
            game, home_market.implied_probability, home_prob, signal.signal_type
        )
        await tick_repo.create_prob_tick(tick)
        
        # Check for volatility spike
        if hasattr(signal, '_volatility_spike') and signal._volatility_spike:
            volatility_spikes.append({
                'game_id': game.id,
                'game': f"{game.away_team.abbreviation} @ {game.home_team.abbreviation}",
                'volatility': signal.volatility,
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Get market intelligence
        intelligence = signal_engine.get_market_intelligence(game.id)
        
        # Build update payload
        update = {
            "type": "game_update",
            "game": game.to_dict(),
            "markets": [m.to_dict() for m in markets],
            "fair_prob_home": home_prob,
            "fair_prob_away": away_prob,
            "confidence": confidence,
            "signal": {
                **signal.to_dict(),
                "signal_score": getattr(signal, '_signal_score', 0),
                "risk_tier": getattr(signal, '_risk_tier', 'medium'),
                "volatility_regime": getattr(signal, '_volatility_regime', 'low'),
                "momentum_direction": getattr(signal, '_momentum_direction', 'neutral'),
                "is_clutch": getattr(signal, '_is_clutch', False),
                "position_state": getattr(signal, '_position_state', 'flat'),
                "recommended_action": getattr(signal, '_recommended_action', 'WAIT'),
                "analytics": getattr(signal, '_analytics', {})
            },
            "intelligence": intelligence,
            "is_clutch": prob_engine.is_clutch_time(game),
            "timestamp": datetime.utcnow().isoformat()
        }
        updates.append(update)
        
        # Process through strategy engine if enabled
        if strategy_manager.is_enabled:
            try:
                # Get orderbook data for the market
                orderbook = await kalshi_adapter.get_orderbook(home_market.id) if hasattr(kalshi_adapter, 'get_orderbook') else None
                orderbook_dict = None
                if orderbook:
                    # Use pydantic serialization so bids/asks become plain dicts,
                    # not OrderBookLevel objects (which don't have .get()).
                    try:
                        orderbook_dict = orderbook.model_dump()
                    except AttributeError:
                        orderbook_dict = orderbook.dict()
                
                # Process tick through all strategies
                decisions = await strategy_manager.process_tick(
                    game=game,
                    market=home_market,
                    signal=signal,
                    orderbook=orderbook_dict
                )
                
                # Log significant decisions
                for sid, decision in decisions.items():
                    if decision and decision.decision_type.value in ["ENTER", "EXIT", "TRIM"]:
                        logger.info(f"[STRATEGY] {sid}: {decision.decision_type.value} on {game.id} - {decision.reason}")
            except Exception as e:
                logger.error(f"Strategy engine error for game {game.id}: {e}")
    
    # Broadcast updates
    if updates and ws_manager.active_connections:
        message = {
            "type": "bulk_update",
            "updates": updates,
            "volatility_spikes": volatility_spikes,
            "timestamp": datetime.utcnow().isoformat()
        }
        await ws_manager.broadcast(message)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global db, game_repo, market_repo, position_repo, trade_repo, tick_repo, settings_repo, order_repo
    global espn_adapter, kalshi_adapter, sandbox_adapter
    global prob_engine, signal_engine, trade_engine, risk_engine, portfolio_service
    global kalshi_settings_service, order_lifecycle_service
    global user_repo, reset_token_repo, auth_service
    global app_start_time
    global db  # Add db to global scope
    
    app_start_time = datetime.utcnow()
    
    # Initialize MongoDB
    mongo_url = os.environ.get('MONGO_URL', settings.mongo_url)
    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ.get('DB_NAME', settings.db_name)]
    
    # Create indexes for time-series data
    await db.probability_ticks.create_index([("game_id", 1), ("timestamp", -1)])
    await db.probability_ticks.create_index([("timestamp", -1)])
    await db.trades.create_index([("created_at", -1)])
    await db.trades.create_index([("game_id", 1), ("created_at", -1)])
    # Create index for audit log
    await db.trading_audit_log.create_index([("timestamp", -1)])
    logger.info("MongoDB indexes created for time-series data")
    
    # Initialize repositories
    game_repo = GameRepository(db)
    market_repo = MarketRepository(db)
    position_repo = PositionRepository(db)
    trade_repo = TradeRepository(db)
    tick_repo = TickRepository(db)
    settings_repo = SettingsRepository(db)
    
    # Import and initialize order repository
    from repositories import OrderRepository
    order_repo = OrderRepository(db)
    await order_repo.create_indexes()
    
    # Initialize authentication repositories and service
    user_repo = UserRepository(db)
    reset_token_repo = PasswordResetTokenRepository(db)
    await user_repo.ensure_indexes()
    await reset_token_repo.ensure_indexes()
    
    auth_service = AuthService(user_repo, reset_token_repo)
    set_auth_service(auth_service)
    logger.info("Authentication service initialized")
    
    # Initialize Kalshi settings service
    kalshi_settings_service = KalshiSettingsService(settings_repo)
    
    # Check server-level live trading flag from env
    server_live_enabled = os.environ.get("LIVE_TRADING_ENABLED", "false").lower() == "true"
    if server_live_enabled:
        await settings_repo.set_server_live_trading(True)
        logger.info("Server-level live trading is ENABLED")
    else:
        logger.info("Server-level live trading is DISABLED (set LIVE_TRADING_ENABLED=true to enable)")
    
    # Initialize adapters
    espn_adapter = ESPNAdapter()
    kalshi_adapter = MockKalshiAdapter(initial_balance=10000.0)
    
    # Initialize Sandbox adapter for testing
    from adapters.kalshi import KalshiAdapterSandbox
    sandbox_adapter = KalshiAdapterSandbox(simulation_mode=True)
    await sandbox_adapter.connect()
    logger.info(f"Sandbox adapter initialized (simulation_mode={sandbox_adapter.simulation_mode})")
    
    # Initialize services
    prob_engine = ProbabilityEngine()
    signal_engine = SignalEngine()
    trade_engine = TradeEngine(kalshi_adapter, position_repo, trade_repo)
    risk_engine = RiskEngine(trade_repo, position_repo)
    portfolio_service = PortfolioService(kalshi_adapter, position_repo, trade_repo)
    
    # Initialize Order Lifecycle Service with sandbox adapter
    from services import OrderLifecycleService
    order_lifecycle_service = OrderLifecycleService(order_repo, settings_repo, sandbox_adapter)
    await order_lifecycle_service.initialize()
    logger.info("Order Lifecycle Service initialized with reconciliation")
    
    # Initialize Config Versioning and Auto-Tuner
    global config_version_repo, config_version_service, auto_tuner_service
    from repositories.config_version_repository import ConfigVersionRepository
    from services.config_version_service import ConfigVersionService
    from services.auto_tuner_service import AutoTunerService
    
    config_version_repo = ConfigVersionRepository(db)
    await config_version_repo.create_indexes()
    
    # Initialize base configs from strategy JSON files
    strategy_configs = {
        model_id: strategy.config._config 
        for model_id, strategy in strategy_manager.strategies.items()
    }
    await config_version_repo.initialize_base_configs(strategy_configs)
    
    config_version_service = ConfigVersionService(config_version_repo)
    auto_tuner_service = AutoTunerService(config_version_repo, strategy_manager)
    await auto_tuner_service.initialize()
    
    # Start auto-tuner scheduler (runs at 03:00 UTC by default)
    await auto_tuner_service.start_scheduler()
    logger.info("Config versioning and Auto-tuner initialized")
    
    # Start background update task
    update_task = asyncio.create_task(update_loop())

    # ── Auto-start autonomous scheduler on every server boot ─────────────────
    # Trades should be placed regardless of which frontend page is open.
    # The scheduler is always started here; /api/autonomous/enable can also
    # start or restart it at any time from the UI.
    global autonomous_scheduler_instance, autonomous_metrics_service, hourly_snapshot_service
    try:
        from services.autonomous_scheduler import AutonomousScheduler
        from services.autonomous_metrics import AutonomousMetricsService
        from services.kalshi_ingestor_v2 import KalshiBasketballIngestorV2
        autonomous_metrics_service = AutonomousMetricsService(db)
        # Bug #2 fix: pass live ingestor so discovery loop fetches real Kalshi markets
        _kalshi_ingestor = KalshiBasketballIngestorV2(db=db)
        try:
            await _kalshi_ingestor.connect()
        except Exception as _ie:
            logger.warning(f'Kalshi ingestor connect warning (will retry): {_ie}')
        autonomous_scheduler_instance = AutonomousScheduler(
            db=db,
            strategy_manager=strategy_manager,
            kalshi_ingestor=_kalshi_ingestor,
        )
        await autonomous_scheduler_instance.start()
        strategy_manager.enable()
        try:
            from services.hourly_snapshot_service import HourlyMetricsSnapshotService
            hourly_snapshot_service = HourlyMetricsSnapshotService(
                db=db,
                scheduler=autonomous_scheduler_instance,
                metrics_service=autonomous_metrics_service,
                strategy_manager=strategy_manager
            )
            await hourly_snapshot_service.start()
        except Exception as _hse:
            logger.warning(f"Hourly snapshot service skipped: {_hse}")
        logger.info("Autonomous scheduler auto-started on boot")
    except Exception as _ase:
        logger.error(f"Failed to auto-start autonomous scheduler: {_ase}", exc_info=True)
    # ─────────────────────────────────────────────────────────────────────────

    # Determine trading mode log message
    kalshi_settings = await kalshi_settings_service.get_settings()
    if kalshi_settings.is_live_trading_active:
        logger.warning("PredictPod API v2 started - LIVE TRADING MODE")
    else:
        logger.info("PredictPod API v2 started - PAPER TRADING MODE (Sandbox ready)")
    
    yield
    
    # Shutdown
    if auto_tuner_service:
        await auto_tuner_service.stop_scheduler()
    if autonomous_scheduler_instance:
        await autonomous_scheduler_instance.stop()
    if hourly_snapshot_service:
        try:
            await hourly_snapshot_service.stop()
        except Exception:
            pass
    if order_lifecycle_service:
        await order_lifecycle_service.shutdown()
    if sandbox_adapter:
        await sandbox_adapter.close()
    
    update_task.cancel()
    await espn_adapter.close()
    client.close()
    _decision_tracer.flush_all()
    logger.info("PredictPod API v2 shutdown")

# Rate limiting middleware
async def check_rate_limit(request: Request) -> bool:
    """Check if request should be rate limited"""
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()
    window_start = current_time - settings.rate_limit_window
    
    # Clean old entries
    rate_limit_storage[client_ip] = [
        t for t in rate_limit_storage[client_ip] if t > window_start
    ]
    
    # Check limit
    if len(rate_limit_storage[client_ip]) >= settings.rate_limit_requests:
        return False
    
    # Add current request
    rate_limit_storage[client_ip].append(current_time)
    return True

# Create FastAPI app
app = FastAPI(
    title="PredictPod API",
    description="Probability Intelligence Terminal for Prediction Markets",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware with env-based allowlist
cors_origins = settings.cors_origins_list
logger.info(f"CORS origins configured: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight for 1 hour
)

# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Skip rate limiting for:
    # - Health checks
    # - CORS preflight requests
    # - Static files
    if request.method == "OPTIONS":  # Skip CORS preflight
        return await call_next(request)
    
    if request.url.path in ["/api/health", "/api/health/ws", "/api/", "/"]:
        return await call_next(request)
    
    if not await check_rate_limit(request):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded (500 requests/60s). Try again later."}
        )
    return await call_next(request)

api_router = APIRouter(prefix="/api")

# ============================================
# HEALTH & STATUS
# ============================================

@api_router.get("/")
async def root():
    # Get current trading mode from settings
    trading_mode = "MOCKED"
    is_live = False
    is_paper = True
    
    if kalshi_settings_service:
        try:
            ks = await kalshi_settings_service.get_settings()
            is_live = ks.is_live_trading_active
            is_paper = not is_live
            trading_mode = "LIVE" if is_live else "MOCKED"
        except:
            pass
    
    return {
        "name": "PredictPod API",
        "version": "2.0.0",
        "status": "running",
        "paper_mode": is_paper,
        "live_trading_enabled": is_live,
        "kalshi_mode": trading_mode,
        "timestamp": datetime.utcnow().isoformat()
    }

@api_router.get("/health")
async def health_check():
    """
    Comprehensive health check with scheduler heartbeat metrics.
    
    Returns:
    - autonomous_enabled: bool
    - strategy_loop_last_tick_at: ISO timestamp
    - strategy_loop_ticks_total: int
    - discovery_loop_last_tick_at: ISO timestamp
    - discovery_loop_ticks_total: int
    - uptime_sec: int
    - db_ping: bool
    - ws_connections: int
    """
    global autonomous_scheduler_instance, app_start_time
    
    db_healthy = False
    db_error = None
    
    # Test MongoDB connectivity
    try:
        if db is not None:
            await db.command("ping")
            db_healthy = True
    except Exception as e:
        db_error = str(e)
        logger.error(f"Health check - DB error: {e}")
    
    # Calculate uptime
    uptime_seconds = 0
    if app_start_time:
        uptime_seconds = (datetime.utcnow() - app_start_time).total_seconds()
    
    # Get tick count for monitoring
    tick_count = 0
    try:
        if tick_repo:
            tick_count = await db.probability_ticks.count_documents({})
    except:
        pass
    
    # Scheduler heartbeat metrics
    autonomous_enabled = False
    strategy_loop_last_tick_at = None
    strategy_loop_ticks_total = 0
    discovery_loop_last_tick_at = None
    discovery_loop_ticks_total = 0
    
    if autonomous_scheduler_instance:
        autonomous_enabled = autonomous_scheduler_instance._running
        hb = autonomous_scheduler_instance.heartbeat
        
        strategy_loop_last_tick_at = hb.trading_loop_last_tick_at.isoformat() if hb.trading_loop_last_tick_at else None
        strategy_loop_ticks_total = hb.trading_loop_ticks_total
        discovery_loop_last_tick_at = hb.discovery_loop_last_tick_at.isoformat() if hb.discovery_loop_last_tick_at else None
        discovery_loop_ticks_total = hb.discovery_loop_ticks_total
    
    health_status = {
        "status": "healthy" if db_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        # P0 Required fields
        "autonomous_enabled": autonomous_enabled,
        "strategy_loop_last_tick_at": strategy_loop_last_tick_at,
        "strategy_loop_ticks_total": strategy_loop_ticks_total,
        "discovery_loop_last_tick_at": discovery_loop_last_tick_at,
        "discovery_loop_ticks_total": discovery_loop_ticks_total,
        "uptime_sec": int(uptime_seconds),
        "db_ping": db_healthy,
        "ws_connections": len(ws_manager.active_connections),
        # Additional details
        "components": {
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
                "connected": db is not None,
                "error": db_error
            },
            "espn_adapter": {
                "status": "healthy" if espn_adapter else "unavailable",
                "connected": espn_adapter is not None
            },
            "kalshi_adapter": {
                "status": "healthy" if kalshi_adapter else "unavailable",
                "connected": kalshi_adapter is not None,
                "mode": "MOCKED (Paper Trading)"
            },
            "websocket": {
                "active_connections": len(ws_manager.active_connections)
            }
        },
        "metrics": {
            "total_ticks_stored": tick_count,
            "paper_trading_mode": True,
            "live_trading_enabled": False
        }
    }
    
    # Add Kalshi integration status
    if kalshi_settings_service:
        try:
            ks = await kalshi_settings_service.get_settings()
            health_status["metrics"]["paper_trading_mode"] = not ks.is_live_trading_active
            health_status["metrics"]["live_trading_enabled"] = ks.is_live_trading_active
            health_status["components"]["kalshi_adapter"]["mode"] = (
                "LIVE" if ks.is_live_trading_active else "MOCKED (Paper Trading)"
            )
            health_status["components"]["kalshi_integration"] = {
                "has_credentials": ks.credentials is not None,
                "credentials_validated": ks.credentials.validation_status.value if ks.credentials else "none",
                "kill_switch_active": ks.kill_switch_active
            }
        except Exception as e:
            logger.error(f"Error getting Kalshi status: {e}")
    
    return health_status

@api_router.get("/health/ws")
async def websocket_health():
    """
    WebSocket-specific health check.
    Returns WebSocket connection status and statistics.
    """
    return {
        "status": "healthy",
        "websocket": {
            "active_connections": len(ws_manager.active_connections),
            "max_connections": 100,
            "broadcast_interval_seconds": settings.market_refresh_interval
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# ============================================
# GAMES
# ============================================

@api_router.get("/games")
async def get_games(status: Optional[str] = None):
    """Get all NBA games with probabilities and signals"""
    games = await espn_adapter.get_todays_games()
    
    if status:
        games = [g for g in games if g.status.value == status]
    
    result = []
    for game in games:
        markets = await kalshi_adapter.get_markets_for_game(game.id)
        home_market = next((m for m in markets if m.outcome == "home"), None)
        
        home_prob, away_prob = prob_engine.calculate_win_probability(
            game,
            market_prob=home_market.implied_probability if home_market else None
        )
        confidence = prob_engine.get_probability_confidence(game)
        
        position = await kalshi_adapter.get_position(home_market.id) if home_market else None
        
        signal = None
        intelligence = {}
        if home_market:
            signal = signal_engine.generate_signal(game, home_market, home_prob, confidence, position)
            intelligence = signal_engine.get_market_intelligence(game.id)
        
        result.append({
            "game": game.to_dict(),
            "fair_prob_home": home_prob,
            "fair_prob_away": away_prob,
            "confidence": confidence,
            "markets": [m.to_dict() for m in markets],
            "signal": {
                **signal.to_dict(),
                "signal_score": getattr(signal, '_signal_score', 0),
                "risk_tier": getattr(signal, '_risk_tier', 'medium'),
                "volatility_regime": getattr(signal, '_volatility_regime', 'low'),
                "is_clutch": getattr(signal, '_is_clutch', False),
                "recommended_action": getattr(signal, '_recommended_action', 'WAIT'),
            } if signal else None,
            "intelligence": intelligence,
            "is_clutch": prob_engine.is_clutch_time(game)
        })
    
    return {"games": result, "count": len(result)}

@api_router.get("/games/{game_id}")
async def get_game(game_id: str):
    """Get detailed game data with full analysis"""
    game = await game_repo.get_by_id(game_id)
    if not game:
        games = await espn_adapter.get_todays_games()
        game = next((g for g in games if g.id == game_id), None)
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    markets = await kalshi_adapter.get_markets_for_game(game.id)
    home_market = next((m for m in markets if m.outcome == "home"), None)
    
    home_prob, away_prob = prob_engine.calculate_win_probability(
        game,
        market_prob=home_market.implied_probability if home_market else None
    )
    confidence = prob_engine.get_probability_confidence(game)
    
    position = await kalshi_adapter.get_position(home_market.id) if home_market else None
    
    signal = None
    intelligence = {}
    if home_market:
        signal = signal_engine.generate_signal(game, home_market, home_prob, confidence, position)
        intelligence = signal_engine.get_market_intelligence(game.id)
    
    prob_history = await tick_repo.get_prob_ticks_for_game(game_id, limit=500)
    positions = await portfolio_service.get_position_by_game(game_id)
    
    return {
        "game": game.to_dict(),
        "fair_prob_home": home_prob,
        "fair_prob_away": away_prob,
        "confidence": confidence,
        "markets": [m.to_dict() for m in markets],
        "signal": {
            **signal.to_dict(),
            "signal_score": getattr(signal, '_signal_score', 0),
            "risk_tier": getattr(signal, '_risk_tier', 'medium'),
            "volatility_regime": getattr(signal, '_volatility_regime', 'low'),
            "momentum_direction": getattr(signal, '_momentum_direction', 'neutral'),
            "is_clutch": getattr(signal, '_is_clutch', False),
            "position_state": getattr(signal, '_position_state', 'flat'),
            "recommended_action": getattr(signal, '_recommended_action', 'WAIT'),
            "analytics": getattr(signal, '_analytics', {})
        } if signal else None,
        "intelligence": intelligence,
        "is_clutch": prob_engine.is_clutch_time(game),
        "probability_history": [t.dict() for t in prob_history],
        "positions": positions
    }

# ============================================
# CHART DATA
# ============================================

@api_router.get("/games/{game_id}/chart-data")
async def get_chart_data(
    game_id: str,
    timeframe: str = "full",  # 5m, 15m, full
    limit: int = 500
):
    """Get probability chart data for a game"""
    now = datetime.utcnow()
    
    if timeframe == "5m":
        start_time = now - timedelta(minutes=5)
    elif timeframe == "15m":
        start_time = now - timedelta(minutes=15)
    else:
        start_time = None
    
    ticks = await tick_repo.get_prob_ticks_for_game(
        game_id, 
        start_time=start_time,
        limit=limit
    )
    
    # Format for charts
    chart_data = []
    for tick in ticks:
        chart_data.append({
            "timestamp": tick.timestamp.isoformat(),
            "time": tick.timestamp.strftime("%H:%M:%S"),
            "market_prob": round(tick.market_prob * 100, 1),
            "fair_prob": round(tick.fair_prob * 100, 1),
            "edge": round(tick.edge * 100, 1),
            "score_diff": tick.score_diff,
            "quarter": tick.quarter,
            "time_remaining": tick.time_remaining_seconds,
            "signal": tick.signal
        })
    
    # Calculate volatility data (rolling 60-second changes)
    volatility_data = []
    for i, tick in enumerate(ticks):
        # Find tick from ~60 seconds ago
        target_time = tick.timestamp - timedelta(seconds=60)
        prev_tick = None
        for j in range(i-1, -1, -1):
            if ticks[j].timestamp <= target_time:
                prev_tick = ticks[j]
                break
        
        if prev_tick:
            change = abs(tick.market_prob - prev_tick.market_prob)
            volatility_data.append({
                "timestamp": tick.timestamp.isoformat(),
                "time": tick.timestamp.strftime("%H:%M:%S"),
                "volatility": round(change * 100, 2)
            })
    
    return {
        "game_id": game_id,
        "timeframe": timeframe,
        "probability_data": chart_data,
        "volatility_data": volatility_data,
        "tick_count": len(chart_data)
    }

# ============================================
# MARKET INTELLIGENCE
# ============================================

@api_router.get("/games/{game_id}/intelligence")
async def get_market_intelligence(game_id: str):
    """Get market intelligence for a game"""
    intelligence = signal_engine.get_market_intelligence(game_id)
    
    # Get additional stats
    ticks = await tick_repo.get_prob_ticks_for_game(game_id, limit=100)
    
    edge_stats = {}
    if ticks:
        edges = [t.edge for t in ticks]
        edge_stats = {
            "avg_edge": round(sum(edges) / len(edges) * 100, 2),
            "max_edge": round(max(edges) * 100, 2),
            "min_edge": round(min(edges) * 100, 2),
            "current_edge": round(edges[-1] * 100, 2) if edges else 0
        }
    
    return {
        **intelligence,
        "edge_stats": edge_stats,
        "data_points": len(ticks)
    }

# ============================================
# MARKETS
# ============================================

@api_router.get("/markets/{market_id}")
async def get_market(market_id: str):
    """Get market details with orderbook"""
    market = await kalshi_adapter.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    orderbook = await kalshi_adapter.get_orderbook(market_id)
    
    return {
        "market": market.to_dict(),
        "orderbook": orderbook.dict() if orderbook else None
    }

@api_router.get("/markets/{ticker}/candlesticks")
async def get_market_candlesticks(
    ticker: str,
    series_ticker: Optional[str] = None,
    period_interval: int = 60,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
):
    """
    Proxy Kalshi candlestick data.
    Tries trade-api/v2 (authenticated) first; synthesises from DB trades if unavailable.
    """
    import httpx
    from datetime import datetime as _dt, timezone as _tz

    now_ts   = int(_dt.now(_tz.utc).timestamp())
    end_ts   = end_ts   or now_ts
    start_ts = start_ts or (end_ts - 30 * 24 * 3600)  # default 30 days

    # ── 1. Try authenticated Kalshi trade-api/v2 ─────────────────────────
    api_key = None
    if kalshi_settings_service:
        try:
            ks = await kalshi_settings_service.get_settings()
            api_key = getattr(ks, 'api_key', None) or getattr(ks, 'kalshi_api_key', None)
        except Exception:
            pass

    if api_key:
        try:
            kalshi_url = (
                f"https://api.elections.kalshi.com/trade-api/v2"
                f"/markets/{ticker}/candlesticks"
                f"?period_interval={period_interval}&start_ts={start_ts}&end_ts={end_ts}"
            )
            if series_ticker:
                kalshi_url += f"&series_ticker={series_ticker}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    kalshi_url,
                    headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass  # fall through to synthetic data

    # ── 2. Synthesise candlesticks from DB trades ─────────────────────────
    # Group closed trades for this ticker into hourly buckets and emit a
    # synthetic OHLC that the frontend chart understands.
    from collections import defaultdict

    day_start = _dt.utcfromtimestamp(start_ts)
    day_end   = _dt.utcfromtimestamp(end_ts)

    pipeline = [
        {"$match": {
            "$or": [{"market_id": ticker}, {"game_id": {"$regex": ticker.rsplit('-', 1)[0] if '-' in ticker else ticker}}],
            "created_at": {"$gte": day_start, "$lte": day_end},
        }}
    ]
    docs = await trade_repo.collection.aggregate(pipeline).to_list(length=5000)

    if not docs:
        return {"candlesticks": []}

    # bucket_key → list of prices seen in that interval
    interval_secs = period_interval * 60
    buckets: dict = defaultdict(list)
    for doc in docs:
        ts_field = doc.get("created_at") or doc.get("executed_at")
        if not ts_field:
            continue
        ts = ts_field.timestamp() if hasattr(ts_field, 'timestamp') else float(ts_field)
        bucket = int(ts / interval_secs) * interval_secs
        price = doc.get("entry_price") or doc.get("price") or 0.5
        buckets[bucket].append(price * 100)  # convert to centi-cents (0-100)

    candlesticks = []
    for bucket_ts in sorted(buckets.keys()):
        prices = buckets[bucket_ts]
        candlesticks.append({
            "end_ts":      bucket_ts + interval_secs,
            "open_price":  round(prices[0], 2),
            "close_price": round(prices[-1], 2),
            "high_price":  round(max(prices), 2),
            "low_price":   round(min(prices), 2),
            "last_price":  round(prices[-1], 2),
            "volume":      len(prices),
        })

    return {"candlesticks": candlesticks}

# ============================================
# TRADING
# ============================================

@api_router.post("/trades")
async def place_trade(
    game_id: str,
    market_id: str,
    side: str,
    direction: str,
    quantity: int,
    price: Optional[float] = None
):
    """Place a paper trade"""
    trade, error = await trade_engine.execute_trade(
        game_id=game_id,
        market_id=market_id,
        side=side,
        direction=direction,
        quantity=quantity,
        price=price
    )
    
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    return {"trade": trade.to_dict(), "message": "Trade executed"}

@api_router.post("/trades/execute-signal")
async def execute_signal(market_id: str, game_id: str):
    """Execute trade based on current signal"""
    game = await game_repo.get_by_id(game_id)
    if not game:
        games = await espn_adapter.get_todays_games()
        game = next((g for g in games if g.id == game_id), None)
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    market = await kalshi_adapter.get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    position = await kalshi_adapter.get_position(market_id)
    home_prob, _ = prob_engine.calculate_win_probability(game, market.implied_probability)
    confidence = prob_engine.get_probability_confidence(game)
    signal = signal_engine.generate_signal(game, market, home_prob, confidence, position)
    
    if not signal.is_actionable:
        raise HTTPException(status_code=400, detail="No actionable signal")
    
    trade, error = await trade_engine.execute_signal(signal)
    
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    return {"trade": trade.to_dict(), "signal": signal.to_dict()}

@api_router.post("/trades/flatten-all")
async def flatten_all():
    """Emergency: Close all positions"""
    closed, errors = await trade_engine.flatten_all_positions()
    return {
        "message": f"Closed {closed} positions with {errors} errors",
        "positions_closed": closed,
        "errors": errors
    }

@api_router.get("/trades")
async def get_trades(limit: int = 50, game_id: Optional[str] = None):
    """Get trade history"""
    trades = await portfolio_service.get_trades_history(limit=limit, game_id=game_id)
    return {"trades": trades, "count": len(trades)}

# ============================================
# PORTFOLIO
# ============================================

@api_router.get("/portfolio")
async def get_portfolio():
    """Get portfolio summary with enhanced metrics"""
    summary = await portfolio_service.get_portfolio_summary()
    performance = await portfolio_service.get_performance_metrics()
    
    return {
        **summary,
        "performance": performance
    }

@api_router.get("/portfolio/positions")
async def get_positions():
    """Get all open positions with enhanced data"""
    positions = await portfolio_service.get_positions()
    
    # Enrich positions with entry probability and edge captured
    enriched = []
    for pos in positions:
        game = await game_repo.get_by_id(pos.get('game_id', ''))
        market = await kalshi_adapter.get_market(pos.get('market_id', ''))
        
        if game and market:
            current_prob = market.implied_probability
            entry_prob = pos.get('avg_entry_price', 0.5)
            edge_captured = current_prob - entry_prob
            
            enriched.append({
                **pos,
                'entry_prob': round(entry_prob * 100, 1),
                'current_prob': round(current_prob * 100, 1),
                'edge_captured': round(edge_captured * 100, 2),
                'game_status': game.status.value if game else 'unknown'
            })
        else:
            enriched.append(pos)
    
    return {"positions": enriched, "count": len(enriched)}

@api_router.get("/portfolio/performance")
async def get_performance(days: int = 30):
    """Get performance metrics"""
    metrics = await portfolio_service.get_performance_metrics(days=days)
    return metrics

# ============================================
# RISK
# ============================================

@api_router.get("/risk/status")
async def get_risk_status():
    """Get current risk status"""
    status = await risk_engine.get_current_status()
    return status.to_dict()

@api_router.get("/risk/limits")
async def get_risk_limits():
    """Get current risk limits"""
    limits = risk_engine.get_limits()
    return limits.dict()

@api_router.put("/risk/limits")
async def update_risk_limits(
    max_position_size: Optional[float] = None,
    max_trade_size: Optional[float] = None,
    max_open_exposure: Optional[float] = None,
    max_daily_loss: Optional[float] = None,
    max_trades_per_day: Optional[int] = None
):
    """Update risk limits"""
    current = risk_engine.get_limits()
    
    if max_position_size is not None:
        current.max_position_size = max_position_size
    if max_trade_size is not None:
        current.max_trade_size = max_trade_size
    if max_open_exposure is not None:
        current.max_open_exposure = max_open_exposure
    if max_daily_loss is not None:
        current.max_daily_loss = max_daily_loss
    if max_trades_per_day is not None:
        current.max_trades_per_day = max_trades_per_day
    
    risk_engine.update_limits(current)
    
    return {"message": "Risk limits updated", "limits": current.dict()}

# ============================================
# SETTINGS
# ============================================

@api_router.get("/settings")
async def get_settings():
    """Get current system settings including Kalshi integration status"""
    kalshi_settings = {}
    if kalshi_settings_service:
        kalshi_settings = await kalshi_settings_service.get_settings_for_frontend()
    
    return {
        "paper_trading_enabled": settings.paper_trading_enabled,
        "live_trading_enabled": settings.live_trading_enabled,
        "score_refresh_interval": settings.score_refresh_interval,
        "market_refresh_interval": settings.market_refresh_interval,
        "edge_threshold_buy": settings.edge_threshold_buy,
        "edge_threshold_strong_buy": settings.edge_threshold_strong_buy,
        "clutch_time_seconds": 300,
        "volatility_spike_threshold": 0.08,
        "model_info": prob_engine.get_model_info() if prob_engine else None,
        "kalshi": kalshi_settings
    }

# ============================================
# KALSHI API CREDENTIALS MANAGEMENT
# ============================================

@api_router.post("/settings/kalshi_keys")
async def save_kalshi_keys(api_key: str, private_key: str):
    """
    Save Kalshi API credentials securely.
    Credentials are encrypted before storage.
    """
    if not kalshi_settings_service:
        raise HTTPException(status_code=503, detail="Settings service not available")
    
    try:
        result = await kalshi_settings_service.save_credentials(api_key, private_key)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error saving credentials: {e}")
        raise HTTPException(status_code=500, detail="Failed to save credentials")

@api_router.get("/settings/kalshi_keys")
async def get_kalshi_keys():
    """
    Get Kalshi credential status (NEVER exposes actual keys).
    Returns masked key info and validation status.
    """
    if not kalshi_settings_service:
        raise HTTPException(status_code=503, detail="Settings service not available")
    
    settings_data = await kalshi_settings_service.get_settings_for_frontend()
    return {
        "has_credentials": settings_data.get("has_credentials", False),
        "credentials_info": settings_data.get("credentials_info"),
        "trading_mode": settings_data.get("trading_mode"),
        "is_live_trading_active": settings_data.get("is_live_trading_active")
    }

@api_router.delete("/settings/kalshi_keys")
async def delete_kalshi_keys():
    """Delete stored Kalshi credentials and disable live trading."""
    if not kalshi_settings_service:
        raise HTTPException(status_code=503, detail="Settings service not available")
    
    return await kalshi_settings_service.delete_credentials()

@api_router.post("/settings/kalshi_keys/validate")
async def validate_kalshi_keys():
    """
    Validate stored Kalshi credentials by making a test API call.
    Returns detailed validation result.
    """
    if not kalshi_settings_service:
        raise HTTPException(status_code=503, detail="Settings service not available")
    
    return await kalshi_settings_service.validate_credentials()

# ============================================
# LIVE TRADING CONTROL
# ============================================

@api_router.post("/settings/live_trading/enable")
async def enable_live_trading(confirmed_risk: bool = False):
    """
    Enable live trading mode.
    Requires explicit risk acknowledgment.
    """
    if not kalshi_settings_service:
        raise HTTPException(status_code=503, detail="Settings service not available")
    
    return await kalshi_settings_service.enable_live_trading(confirmed_risk)

@api_router.post("/settings/live_trading/disable")
async def disable_live_trading():
    """Disable live trading and return to paper mode."""
    if not kalshi_settings_service:
        raise HTTPException(status_code=503, detail="Settings service not available")
    
    return await kalshi_settings_service.disable_live_trading()

# ============================================
# KILL SWITCH (EMERGENCY)
# ============================================

@api_router.post("/admin/kill_switch")
async def activate_kill_switch():
    """
    EMERGENCY: Immediately disable all live trading.
    Forces adapter to MOCK mode.
    Does NOT close open positions automatically.
    """
    if not kalshi_settings_service:
        raise HTTPException(status_code=503, detail="Settings service not available")
    
    return await kalshi_settings_service.activate_kill_switch()

@api_router.delete("/admin/kill_switch")
async def deactivate_kill_switch():
    """Deactivate kill switch (requires manual re-enable of live trading)."""
    if not kalshi_settings_service:
        raise HTTPException(status_code=503, detail="Settings service not available")
    
    return await kalshi_settings_service.deactivate_kill_switch()

# ============================================
# TRADING GUARDRAILS
# ============================================

@api_router.get("/settings/guardrails")
async def get_guardrails():
    """Get current trading guardrails."""
    if not kalshi_settings_service:
        raise HTTPException(status_code=503, detail="Settings service not available")
    
    guardrails = await kalshi_settings_service.get_guardrails()
    return guardrails.dict()

@api_router.put("/settings/guardrails")
async def update_guardrails(
    max_dollars_per_trade: Optional[float] = None,
    max_open_exposure: Optional[float] = None,
    max_daily_loss: Optional[float] = None,
    max_trades_per_hour: Optional[int] = None,
    max_trades_per_day: Optional[int] = None
):
    """Update trading guardrails."""
    if not kalshi_settings_service:
        raise HTTPException(status_code=503, detail="Settings service not available")
    
    from models import LiveTradingGuardrails
    
    current = await kalshi_settings_service.get_guardrails()
    
    if max_dollars_per_trade is not None:
        current.max_dollars_per_trade = max_dollars_per_trade
    if max_open_exposure is not None:
        current.max_open_exposure = max_open_exposure
    if max_daily_loss is not None:
        current.max_daily_loss = max_daily_loss
    if max_trades_per_hour is not None:
        current.max_trades_per_hour = max_trades_per_hour
    if max_trades_per_day is not None:
        current.max_trades_per_day = max_trades_per_day
    
    return await kalshi_settings_service.update_guardrails(current)

# ============================================
# AUDIT LOG
# ============================================

@api_router.get("/admin/audit_log")
async def get_audit_log(limit: int = 100):
    """Get recent audit log entries."""
    if not kalshi_settings_service:
        raise HTTPException(status_code=503, detail="Settings service not available")
    
    return await kalshi_settings_service.get_audit_log(limit)

# ============================================
# SANDBOX / ORDER LIFECYCLE
# ============================================

@api_router.get("/sandbox/status")
async def get_sandbox_status():
    """Get sandbox adapter status."""
    if not sandbox_adapter:
        raise HTTPException(status_code=503, detail="Sandbox adapter not available")
    
    balance = await sandbox_adapter.get_balance()
    positions = await sandbox_adapter.get_positions()
    working_orders = await sandbox_adapter.get_working_orders()
    
    return {
        "mode": "simulation" if sandbox_adapter.is_simulation_mode() else "demo_api",
        "demo_connected": sandbox_adapter.demo_connected,
        "balance": balance,
        "positions_count": len(positions),
        "working_orders_count": len(working_orders),
        "is_paper_mode": sandbox_adapter.is_paper_mode()
    }

@api_router.post("/sandbox/connect")
async def connect_sandbox(api_key: str = "", private_key: str = ""):
    """
    Connect sandbox adapter to Kalshi Demo API.
    If no credentials provided, stays in simulation mode.
    """
    global sandbox_adapter
    
    from adapters.kalshi import KalshiAdapterSandbox
    
    if sandbox_adapter:
        await sandbox_adapter.close()
    
    sandbox_adapter = KalshiAdapterSandbox(
        api_key=api_key,
        private_key=private_key,
        simulation_mode=not (api_key and private_key)
    )
    
    connected = await sandbox_adapter.connect()
    
    return {
        "success": True,
        "connected_to_demo_api": connected,
        "simulation_mode": sandbox_adapter.simulation_mode,
        "balance": await sandbox_adapter.get_balance()
    }

# ============================================
# CAPITAL DEPLOYMENT MODE
# ============================================

@api_router.get("/settings/capital_deployment")
async def get_capital_deployment():
    """Get current capital deployment mode and settings."""
    if not order_lifecycle_service:
        raise HTTPException(status_code=503, detail="Order lifecycle service not available")
    
    settings = await order_lifecycle_service.get_capital_settings()
    return settings.to_dict()

@api_router.post("/settings/capital_deployment")
async def set_capital_deployment(
    mode: str,
    confirmed: bool = False,
    acknowledged: bool = False
):
    """
    Set capital deployment mode.
    AGGRESSIVE mode requires confirmed=true and acknowledged=true.
    """
    if not order_lifecycle_service:
        raise HTTPException(status_code=503, detail="Order lifecycle service not available")
    
    from models import CapitalDeploymentMode
    
    try:
        mode_enum = CapitalDeploymentMode(mode.lower())
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid mode. Must be: conservative, normal, or aggressive"
        )
    
    # AGGRESSIVE requires both confirmations
    if mode_enum == CapitalDeploymentMode.AGGRESSIVE:
        if not confirmed or not acknowledged:
            return {
                "success": False,
                "message": "AGGRESSIVE mode requires both confirmed=true AND acknowledged=true. You are acknowledging increased risk.",
                "requires_confirmation": True,
                "requires_acknowledgment": True
            }
    
    return await order_lifecycle_service.set_capital_deployment_mode(mode_enum, confirmed)

# ============================================
# ORDER LIFECYCLE MANAGEMENT
# ============================================

@api_router.get("/orders")
async def get_orders(limit: int = 50, working_only: bool = False):
    """Get recent orders."""
    if not order_lifecycle_service:
        raise HTTPException(status_code=503, detail="Order lifecycle service not available")
    
    if working_only:
        orders = await order_lifecycle_service.get_working_orders()
    else:
        orders = await order_lifecycle_service.get_recent_orders(limit)
    
    return {
        "orders": [o.to_dict() for o in orders],
        "total": len(orders)
    }

@api_router.get("/orders/{order_id}")
async def get_order(order_id: str):
    """Get order by ID."""
    if not order_lifecycle_service:
        raise HTTPException(status_code=503, detail="Order lifecycle service not available")
    
    order = await order_lifecycle_service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return order.to_dict()

@api_router.post("/orders/preview")
async def preview_order(
    market_id: str,
    side: str,
    action: str,
    quantity: int,
    price_cents: int
):
    """
    Preview order with all risk checks BEFORE submission.
    Returns trade confirmation with all warnings and blocks.
    """
    if not order_lifecycle_service:
        raise HTTPException(status_code=503, detail="Order lifecycle service not available")
    
    confirmation = await order_lifecycle_service.get_trade_confirmation(
        market_id, side, action, quantity, price_cents
    )
    
    return confirmation.to_dict()

@api_router.post("/orders/submit")
async def submit_order(
    market_id: str,
    market_ticker: str,
    side: str,
    action: str,
    quantity: int,
    price_cents: int,
    idempotency_key: str,
    game_id: Optional[str] = None,
    confirmed_double: bool = False,
    acknowledged_risk: bool = False
):
    """
    Submit order with full lifecycle tracking.
    
    REQUIRED: idempotency_key - unique key to prevent duplicates
    """
    if not order_lifecycle_service:
        raise HTTPException(status_code=503, detail="Order lifecycle service not available")
    
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="idempotency_key is required")
    
    order, error = await order_lifecycle_service.submit_order(
        market_id=market_id,
        market_ticker=market_ticker,
        side=side,
        action=action,
        quantity=quantity,
        price_cents=price_cents,
        idempotency_key=idempotency_key,
        game_id=game_id,
        confirmed_double=confirmed_double,
        acknowledged_risk=acknowledged_risk
    )
    
    if error and not order:
        raise HTTPException(status_code=400, detail=error)
    
    return {
        "success": True,
        "order": order.to_dict() if order else None,
        "message": error or "Order submitted successfully"
    }

@api_router.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    """Cancel a working order."""
    if not order_lifecycle_service:
        raise HTTPException(status_code=503, detail="Order lifecycle service not available")
    
    success, message = await order_lifecycle_service.cancel_order(order_id)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}

# ============================================
# RECONCILIATION
# ============================================

@api_router.get("/reconciliation/status")
async def get_reconciliation_status():
    """Get current position reconciliation status."""
    if not order_lifecycle_service:
        raise HTTPException(status_code=503, detail="Order lifecycle service not available")
    
    return await order_lifecycle_service.get_reconciliation_status()

@api_router.post("/reconciliation/force")
async def force_reconciliation():
    """Force immediate position reconciliation."""
    if not order_lifecycle_service:
        raise HTTPException(status_code=503, detail="Order lifecycle service not available")
    
    return await order_lifecycle_service.force_reconciliation()

# ============================================
# MULTI-MODEL STRATEGY ENGINE
# ============================================

# Import strategy manager
from strategies import strategy_manager

@api_router.get("/strategies/summary")
async def get_strategy_summary():
    """
    Get aggregated summary of all strategies.
    Shows which model is winning, comparison table, and individual stats.
    """
    summary = strategy_manager.get_summary()
    # Inject autonomous / auto-mode status so the UI can reflect it
    auto_mode_on = (
        autonomous_scheduler_instance is not None
        and getattr(autonomous_scheduler_instance, '_running', False)
    )
    summary["auto_mode"] = auto_mode_on
    summary["autonomous_enabled"] = auto_mode_on
    return summary

@api_router.get("/strategies/{strategy_id}")
async def get_strategy_detail(strategy_id: str):
    """Get detailed info for a specific strategy."""
    if strategy_id not in strategy_manager.strategies:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
    
    strategy = strategy_manager.strategies[strategy_id]
    return {
        "summary": strategy.get_summary(),
        "positions": strategy.get_positions_summary(),
        "recent_decisions": strategy.get_decision_log(50)
    }

@api_router.post("/strategies/enable")
async def enable_strategies():
    """Enable all strategies (evaluation mode)."""
    strategy_manager.enable()
    return {"message": "Strategies enabled", "enabled": True}

@api_router.post("/strategies/disable")
async def disable_strategies():
    """Disable all strategies."""
    strategy_manager.disable()
    return {"message": "Strategies disabled", "enabled": False}

@api_router.post("/strategies/kill_switch")
async def activate_strategy_kill_switch():
    """EMERGENCY: Activate kill switch to stop all strategies immediately."""
    strategy_manager.activate_kill_switch()
    return {"message": "KILL SWITCH ACTIVATED - All strategies stopped", "kill_switch_active": True}

@api_router.delete("/strategies/kill_switch")
async def deactivate_strategy_kill_switch():
    """Deactivate strategy kill switch."""
    strategy_manager.deactivate_kill_switch()
    return {"message": "Kill switch deactivated", "kill_switch_active": False}

@api_router.post("/strategies/evaluation_mode")
async def set_evaluation_mode(enabled: bool = True):
    """Enable/disable evaluation mode (runs all strategies on all basketball games)."""
    strategy_manager.set_evaluation_mode(enabled)
    return {"message": f"Evaluation mode {'enabled' if enabled else 'disabled'}", "evaluation_mode": enabled}

@api_router.post("/strategies/{strategy_id}/reset")
async def reset_strategy_portfolio(strategy_id: str, starting_capital: Optional[float] = None):
    """Reset a strategy's portfolio (admin only)."""
    if strategy_id not in strategy_manager.strategies:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
    
    strategy_manager.reset_strategy(strategy_id, starting_capital)
    return {"message": f"Strategy {strategy_id} portfolio reset", "starting_capital": starting_capital or 10000.0}

@api_router.post("/strategies/reset_all")
async def reset_all_strategy_portfolios():
    """Reset all strategy portfolios (admin only)."""
    strategy_manager.reset_all_strategies()
    return {"message": "All strategy portfolios reset"}

@api_router.get("/strategies/positions/by_game")
async def get_strategy_positions_by_game():
    """Get all positions organized by game for dashboard display."""
    return strategy_manager.get_all_positions_by_game()

@api_router.get("/strategies/positions/game/{game_id}")
async def get_strategy_positions_for_game(game_id: str):
    """Get positions for a specific game across all strategies."""
    return strategy_manager.get_game_positions(game_id)

@api_router.get("/strategies/decisions")
async def get_strategy_decisions(limit: int = 100):
    """Get recent decision logs for all strategies."""
    return strategy_manager.get_decision_logs(limit)

@api_router.get("/strategies/{strategy_id}/export/trades")
async def export_strategy_trades(strategy_id: str, format: str = "json"):
    """Export trade history for a strategy."""
    if strategy_id not in strategy_manager.strategies:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
    
    if format == "csv":
        csv_data = strategy_manager.export_trades_csv(strategy_id)
        return JSONResponse(
            content={"format": "csv", "data": csv_data},
            headers={"Content-Disposition": f"attachment; filename={strategy_id}_trades.csv"}
        )
    else:
        json_data = strategy_manager.export_trades_json(strategy_id)
        return JSONResponse(
            content={"format": "json", "data": json.loads(json_data)},
            headers={"Content-Disposition": f"attachment; filename={strategy_id}_trades.json"}
        )

@api_router.get("/strategies/report/daily")
async def get_daily_evaluation_report(date: Optional[str] = None):
    """Get daily evaluation report for all strategies — computed from DB trades."""
    from datetime import date as _date, datetime as _dt
    target_date = date or _date.today().isoformat()

    # Parse the requested date into UTC day boundaries
    day_start = _dt.strptime(target_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0)
    day_end   = day_start.replace(hour=23, minute=59, second=59, microsecond=999999)

    # ── Strategy name → canonical ID mapping ────────────────────────────────
    STRATEGY_MAP = {
        "model a":                                 "model_a_disciplined",
        "model_a":                                 "model_a_disciplined",
        "model_a_disciplined":                     "model_a_disciplined",
        "model a - disciplined edge trader":       "model_a_disciplined",
        "disciplined edge trader":                 "model_a_disciplined",
        "model b":                                 "model_b_high_frequency",
        "model_b":                                 "model_b_high_frequency",
        "model_b_high_frequency":                  "model_b_high_frequency",
        "model b - high frequency edge hunter":    "model_b_high_frequency",
        "high frequency edge hunter":              "model_b_high_frequency",
        "high frequency hunter":                   "model_b_high_frequency",
    }
    DISPLAY_NAMES = {
        "model_a_disciplined":    "Model A - Disciplined Edge Trader",
        "model_b_high_frequency": "Model B - High Frequency Edge Hunter",
    }

    def _strategy_id(raw: str) -> str:
        return STRATEGY_MAP.get((raw or "").strip().lower(), "model_a_disciplined")

    # ── Pull today's closed trades from MongoDB ──────────────────────────────
    pipeline = [
        {"$match": {
            "status": "closed",
            "$or": [
                {"closed_at": {"$gte": day_start, "$lte": day_end}},
                {"created_at": {"$gte": day_start, "$lte": day_end}},
            ]
        }}
    ]
    raw_docs = await trade_repo.collection.aggregate(pipeline).to_list(length=10000)

    # ── Aggregate per strategy ───────────────────────────────────────────────
    from collections import defaultdict
    buckets: dict = defaultdict(lambda: {"pnl": 0.0, "winners": 0, "losers": 0, "pnls": []})

    for doc in raw_docs:
        sid = _strategy_id(doc.get("strategy") or "")
        pnl_val = float(doc.get("pnl") or doc.get("realized_pnl") or 0)
        buckets[sid]["pnl"]  += pnl_val
        buckets[sid]["pnls"].append(pnl_val)
        if pnl_val >= 0:
            buckets[sid]["winners"] += 1
        else:
            buckets[sid]["losers"]  += 1

    # ── Build response in the same shape the frontend expects ───────────────
    strategies_out = {}
    for sid in ["model_a_disciplined", "model_b_high_frequency"]:
        b          = buckets[sid]
        total      = b["winners"] + b["losers"]
        win_rate   = round((b["winners"] / total) * 100, 1) if total else 0.0
        avg_pnl    = round(b["pnl"] / total, 4) if total else 0.0
        strategies_out[sid] = {
            "display_name": DISPLAY_NAMES[sid],
            "daily_stats": {
                "date":         target_date,
                "trades":       total,
                "realized_pnl": round(b["pnl"], 2),
                "winners":      b["winners"],
                "losers":       b["losers"],
                "win_rate":     win_rate,
                "avg_pnl":      avg_pnl,
                "trade_count":  total,
                "avg_win_loss": avg_pnl,
            },
            "total_pnl":        round(b["pnl"], 2),
            "max_drawdown":     0.0,
            "max_drawdown_pct": 0.0,
            "win_rate":         win_rate,
            "profit_factor":    0.0,
            "avg_edge_entry":   0.0,
            "avg_edge_exit":    0.0,
            "by_league":        {},
            "trades_today":     total,
        }

    return {
        "date":         target_date,
        "generated_at": _dt.utcnow().isoformat(),
        "strategies":   strategies_out,
    }

@api_router.get("/strategies/report/daily/export")
async def export_daily_report(date: Optional[str] = None, format: str = "json"):
    """Export daily report."""
    if format == "csv":
        csv_data = strategy_manager.export_daily_report_csv(date)
        return JSONResponse(
            content={"format": "csv", "data": csv_data},
            headers={"Content-Disposition": f"attachment; filename=daily_report.csv"}
        )
    else:
        return JSONResponse(
            content=json.loads(strategy_manager.export_daily_report_json(date)),
            headers={"Content-Disposition": f"attachment; filename=daily_report.json"}
        )

@api_router.get("/strategies/{strategy_id}/config")
async def get_strategy_config(strategy_id: str):
    """Get current configuration for a strategy."""
    config = strategy_manager.get_strategy_config(strategy_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
    return config

@api_router.post("/strategies/reload_configs")
async def reload_strategy_configs():
    """Reload all strategy configurations from files."""
    strategy_manager.reload_configs()
    return {"message": "All strategy configurations reloaded"}

# ============================================
# RULES TRANSPARENCY & CONFIG VERSIONING
# ============================================

# Initialize services (will be set up in startup)
config_version_repo = None
config_version_service = None
auto_tuner_service = None

@api_router.get("/rules/{strategy_id}")
async def get_strategy_rules(strategy_id: str, league: str = "BASE"):
    """
    Get rules for a strategy with full transparency.
    Returns rule chips, human-readable summary, and JSON config.
    """
    if not config_version_service:
        # Fallback to direct config
        config = strategy_manager.get_strategy_config(strategy_id)
        if not config:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
        
        from services.config_version_service import ConfigVersionService
        temp_service = ConfigVersionService(None)
        return {
            "version_id": "N/A",
            "league": league,
            "rule_chips": temp_service.get_rule_chips(config, league),
            "rules_summary": temp_service.generate_rules_summary(config, strategy_id),
            "config": config,
            "applied_by": "initial",
            "applied_at": None
        }
    
    result = await config_version_service.get_active_config_with_metadata(strategy_id, league)
    if not result:
        raise HTTPException(status_code=404, detail=f"Config not found for {strategy_id}/{league}")
    
    return result

@api_router.get("/rules/{strategy_id}/history")
async def get_strategy_rules_history(strategy_id: str, league: str = "BASE", limit: int = 10):
    """Get version history with diffs for a strategy."""
    if not config_version_service:
        return {"versions": [], "message": "Config versioning not initialized"}
    
    history = await config_version_service.get_version_history_with_diffs(strategy_id, league, limit)
    return {"versions": history}

@api_router.post("/rules/{strategy_id}/rollback")
async def rollback_strategy_rules(strategy_id: str, league: str, target_version_id: str):
    """Rollback to a previous config version (admin only)."""
    if not config_version_service:
        raise HTTPException(status_code=503, detail="Config versioning not initialized")
    
    result = await config_version_service.rollback_to_version(strategy_id, league, target_version_id)
    return result

@api_router.post("/rules/{strategy_id}/update")
async def update_strategy_rules(strategy_id: str, league: str = "BASE", config: Dict = None, change_summary: str = ""):
    """Update rules for a strategy and save new version."""
    if not config_version_service or not config_version_repo:
        raise HTTPException(status_code=503, detail="Config versioning not initialized")
    
    if not config:
        raise HTTPException(status_code=400, detail="Config is required")
    
    try:
        logger.info(f"Updating rules for {strategy_id} ({league})")
        from models.config_version import ConfigVersion, ConfigChangeSource
        from datetime import datetime
        
        # Get current version
        current = await config_version_repo.get_active_config(strategy_id, league)
        logger.info(f"Current version: {current.version_number if current else 'none'}")
        
        # Create new version
        new_version = ConfigVersion(
            model_id=strategy_id,
            league=league,
            version_number=(current.version_number + 1) if current else 1,
            config=config,
            applied_at=datetime.utcnow(),
            applied_by=ConfigChangeSource.MANUAL,
            change_summary=change_summary or "Manual rules adjustment",
            is_active=True
        )
        logger.info(f"New version number: {new_version.version_number}")
        
        # Calculate diff from previous
        if current:
            try:
                from deepdiff import DeepDiff
                diff = DeepDiff(current.config, config, ignore_order=True)
                
                from models.config_version import ConfigDiff
                for key, value in diff.items():
                    if isinstance(value, dict):
                        for param, changes in value.items():
                            if isinstance(changes, tuple) and len(changes) == 2:
                                new_version.diff_from_previous.append(
                                    ConfigDiff(parameter=param, old_value=changes[0], new_value=changes[1], league=league)
                                )
            except ImportError:
                # Fallback: if deepdiff not available, create simple diff
                logger.warning("deepdiff not available, using simple diff")
                from models.config_version import ConfigDiff
                for key in config:
                    if key not in current.config or current.config[key] != config[key]:
                        old_val = current.config.get(key, "N/A")
                        new_version.diff_from_previous.append(
                            ConfigDiff(parameter=key, old_value=str(old_val), new_value=str(config[key]), league=league)
                        )
        
        # Save new version
        logger.info(f"Saving config version {new_version.version_id}...")
        saved = await config_version_repo.save_config(new_version)
        logger.info(f"Config version saved successfully: {saved.version_id}")
        
        # Reload strategy with new config
        strategy_manager.reload_configs()
        
        return {
            "success": True,
            "new_version_id": saved.version_id,
            "version_number": saved.version_number,
            "message": "Rules updated successfully"
        }
    
    except Exception as e:
        error_msg = str(e)
        logger.exception(f"Failed to update rules for {strategy_id}: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Failed to update rules: {error_msg}")

# ============================================
# AUTO-TUNER
# ============================================

@api_router.get("/tuner/status")
async def get_tuner_status():
    """Get auto-tuner status."""
    if not auto_tuner_service:
        return {
            "mode": "not_initialized",
            "last_run": None,
            "scheduler_running": False
        }
    
    return await auto_tuner_service.get_status()

@api_router.post("/tuner/run")
async def run_tuner_now():
    """Manually trigger auto-tuner run (admin only)."""
    if not auto_tuner_service:
        raise HTTPException(status_code=503, detail="Auto-tuner not initialized")
    
    report = await auto_tuner_service.run_tuner(force=True)
    return report

@api_router.get("/tuner/proposals")
async def get_tuner_proposals(model_id: Optional[str] = None, league: Optional[str] = None):
    """Get pending tuner proposals."""
    if not auto_tuner_service:
        return {"proposals": []}
    
    proposals = await auto_tuner_service.config_repo.get_pending_proposals(model_id, league)
    return {"proposals": [p.to_dict() for p in proposals]}

@api_router.post("/tuner/proposals/{proposal_id}/apply")
async def apply_tuner_proposal(proposal_id: str):
    """Manually apply a pending proposal (admin only)."""
    if not auto_tuner_service:
        raise HTTPException(status_code=503, detail="Auto-tuner not initialized")
    
    success = await auto_tuner_service.apply_proposal_manual(proposal_id)
    if success:
        return {"message": "Proposal applied", "proposal_id": proposal_id}
    else:
        raise HTTPException(status_code=404, detail="Proposal not found or already processed")

@api_router.post("/tuner/proposals/{proposal_id}/reject")
async def reject_tuner_proposal(proposal_id: str, reason: str = "Manual rejection"):
    """Reject a pending proposal (admin only)."""
    if not auto_tuner_service:
        raise HTTPException(status_code=503, detail="Auto-tuner not initialized")
    
    await auto_tuner_service.reject_proposal(proposal_id, reason)
    return {"message": "Proposal rejected", "proposal_id": proposal_id, "reason": reason}

@api_router.get("/tuner/settings")
async def get_tuner_settings():
    """Get auto-tuner settings."""
    if not auto_tuner_service or not auto_tuner_service.settings:
        from models.config_version import TunerSettings
        return TunerSettings().to_dict()
    
    return auto_tuner_service.settings.to_dict()

@api_router.post("/tuner/settings")
async def update_tuner_settings(
    mode: Optional[str] = None,
    daily_run_hour_utc: Optional[int] = None,
    enable_midday_runs: Optional[bool] = None,
    min_sample_size_overall: Optional[int] = None,
    min_improvement_pct: Optional[float] = None
):
    """Update auto-tuner settings (admin only)."""
    if not auto_tuner_service:
        raise HTTPException(status_code=503, detail="Auto-tuner not initialized")
    
    updates = {}
    if mode is not None:
        updates["mode"] = mode
    if daily_run_hour_utc is not None:
        updates["daily_run_hour_utc"] = daily_run_hour_utc
    if enable_midday_runs is not None:
        updates["enable_midday_runs"] = enable_midday_runs
    if min_sample_size_overall is not None:
        updates["min_sample_size_overall"] = min_sample_size_overall
    if min_improvement_pct is not None:
        updates["min_improvement_pct"] = min_improvement_pct
    
    await auto_tuner_service.update_settings(updates)
    return {"message": "Tuner settings updated", "updates": updates}


# ============================================
# KALSHI DIRECT PROXY ENDPOINTS
# (Used by frontend — no ingestor required)
# ============================================

@api_router.get("/kalshi/series")
async def proxy_kalshi_series(
    order_by: str = "trending",
    status: str = "open,unopened",
    category: str = "Sports",
    tag: str = "Basketball",
    scope: str = "Games",
    page_size: int = 100,
):
    """Proxy for Kalshi Series API — used by Dashboard to list games."""
    import httpx
    api_key = os.environ.get("KALSHI_API_KEY")
    if kalshi_settings_service:
        try:
            ks = await kalshi_settings_service.get_settings()
            api_key = getattr(ks, 'api_key', None) or getattr(ks, 'kalshi_api_key', None) or api_key
        except Exception:
            pass
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.elections.kalshi.com/v1/search/series",  # ✅ v1
                params={"order_by": order_by, "status": status, "category": category,
                        "tag": tag, "scope": scope, "page_size": page_size},
                headers=headers,
            )
        if resp.status_code == 403:
            raise HTTPException(status_code=502, detail="Kalshi 403 — set KALSHI_API_KEY env var")
        if not resp.is_success:
            raise HTTPException(status_code=resp.status_code, detail=f"Kalshi API error: {resp.status_code}")
        return resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Kalshi unreachable: {exc}")


@api_router.get("/kalshi/event/{event_ticker}")
async def proxy_kalshi_event(event_ticker: str):
    """Proxy for Kalshi event detail — used by TradesCenter for live price lookups."""
    import httpx
    api_key = os.environ.get("KALSHI_API_KEY")
    if kalshi_settings_service:
        try:
            ks = await kalshi_settings_service.get_settings()
            api_key = getattr(ks, 'api_key', None) or getattr(ks, 'kalshi_api_key', None) or api_key
        except Exception:
            pass
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(
                f"https://api.elections.kalshi.com/trade-api/v2/events/{event_ticker}",
                headers=headers,
            )
        if not resp.is_success:
            raise HTTPException(status_code=resp.status_code, detail=f"Event {event_ticker} not found")
        return resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Kalshi unreachable: {exc}")



# ============================================
# KALSHI BASKETBALL DATA INGESTION (V2)
# ============================================

# Global ingestor instance (V2)
kalshi_basketball_ingestor = None
capital_engine = None
perf_tracker = None

@api_router.get("/kalshi/status")
async def get_kalshi_ingestor_status():
    """Get Kalshi data ingestor status"""
    if not kalshi_basketball_ingestor:
        return {
            "initialized": False,
            "message": "Kalshi ingestor not initialized. Run /api/kalshi/sync first."
        }
    
    return {
        "initialized": True,
        **kalshi_basketball_ingestor.get_status()
    }

@api_router.post("/kalshi/sync")
async def sync_kalshi_data():
    """
    Trigger full synchronization of Kalshi basketball data.
    Uses V2 ingestor with proper basketball filtering.
    """
    global kalshi_basketball_ingestor
    
    # Use V2 ingestor with proper filtering
    from services.kalshi_ingestor_v2 import KalshiBasketballIngestorV2
    
    if not kalshi_basketball_ingestor:
        kalshi_basketball_ingestor = KalshiBasketballIngestorV2(
            use_demo=True,
            db=db
        )
        await kalshi_basketball_ingestor.connect()
    
    report = await kalshi_basketball_ingestor.full_sync()
    return report

@api_router.get("/kalshi/validate")
async def validate_basketball_data():
    """
    Validate basketball data integrity.
    Returns counts by league and sample events for verification.
    """
    if not kalshi_basketball_ingestor:
        raise HTTPException(status_code=503, detail="Run /api/kalshi/sync first")
    
    # Get stats
    stats = kalshi_basketball_ingestor.stats
    
    # Get sample events per league
    samples = await kalshi_basketball_ingestor.get_sample_events_by_league(sample_size=5)
    
    return {
        "validation": "PASSED" if stats.get("total_events", 0) > 0 else "NO_DATA",
        "total_events": stats.get("total_events", 0),
        "total_markets": stats.get("total_markets", 0),
        "by_league": stats.get("by_league", {}),
        "sample_events_per_league": samples,
        "basketball_series_count": len(kalshi_basketball_ingestor._basketball_series),
        "errors": kalshi_basketball_ingestor.errors[:5]
    }

@api_router.get("/kalshi/categories")
async def get_kalshi_categories():
    """
    Get basketball category tree.
    
    Returns:
    Basketball
    ├── Pro Basketball (M) / NBA
    ├── Pro Basketball (W) / WNBA
    ├── College Basketball (M)
    ├── College Basketball (W)
    ├── EuroLeague
    ├── Adriatic ABA League
    ├── Germany BBL
    └── etc.
    """
    if not kalshi_basketball_ingestor:
        # Return static structure if not synced
        return {
            "categories": [
                {
                    "id": "basketball",
                    "name": "Basketball",
                    "slug": "basketball",
                    "children": [
                        {"id": "nba", "name": "Pro Basketball (M) / NBA", "slug": "nba", "event_count": 0, "market_count": 0},
                        {"id": "wnba", "name": "Pro Basketball (W) / WNBA", "slug": "wnba", "event_count": 0, "market_count": 0},
                        {"id": "ncaa_m", "name": "College Basketball (M)", "slug": "ncaa_m", "event_count": 0, "market_count": 0},
                        {"id": "ncaa_w", "name": "College Basketball (W)", "slug": "ncaa_w", "event_count": 0, "market_count": 0},
                        {"id": "euroleague", "name": "EuroLeague", "slug": "euroleague", "event_count": 0, "market_count": 0},
                        {"id": "aba", "name": "Adriatic ABA League", "slug": "aba", "event_count": 0, "market_count": 0},
                        {"id": "bbl", "name": "Germany BBL", "slug": "bbl", "event_count": 0, "market_count": 0}
                    ]
                }
            ]
        }
    
    categories = await kalshi_basketball_ingestor.get_categories()
    return {"categories": categories}


@api_router.get("/kalshi/events")
async def get_kalshi_events(
    league: Optional[str] = Query(None, description="Filter by league (NBA, NCAA_M, NCAA_W, etc.)"),
    status: Optional[str] = Query(None, description="Filter by status (open, closed, settled)"),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0)
):
    """
    Get basketball events with filtering.
    Supports pagination for large datasets.
    """
    if not kalshi_basketball_ingestor:
        return {"events": [], "total": 0, "message": "Run /api/kalshi/sync first"}
    
    events = await kalshi_basketball_ingestor.get_events(
        league=league,
        status=status,
        limit=limit,
        skip=skip
    )
    
    return {
        "events": events,
        "count": len(events),
        "limit": limit,
        "skip": skip
    }

@api_router.get("/kalshi/markets")
async def get_kalshi_markets(
    event_ticker: Optional[str] = Query(None, description="Filter by event ticker"),
    league: Optional[str] = Query(None, description="Filter by league (NBA, NCAA_M, NCAA_W, etc.)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0)
):
    """
    Get basketball markets with filtering.
    Supports pagination for 500+ markets.
    """
    if not kalshi_basketball_ingestor:
        return {"markets": [], "total": 0, "message": "Run /api/kalshi/sync first"}
    
    markets = await kalshi_basketball_ingestor.get_markets(
        event_ticker=event_ticker,
        league=league,
        status=status,
        limit=limit,
        skip=skip
    )
    
    return {
        "markets": markets,
        "count": len(markets),
        "limit": limit,
        "skip": skip
    }

@api_router.get("/kalshi/markets/{ticker}")
async def get_kalshi_market_detail(ticker: str):
    """Get detailed market information including orderbook"""
    if not kalshi_basketball_ingestor:
        raise HTTPException(status_code=503, detail="Kalshi ingestor not initialized")
    
    market = await kalshi_basketball_ingestor.get_market_by_ticker(ticker)
    if not market:
        raise HTTPException(status_code=404, detail=f"Market {ticker} not found")
    
    orderbook = await kalshi_basketball_ingestor.get_orderbook(ticker)
    
    return {
        "market": market,
        "orderbook": orderbook.dict() if orderbook else None
    }

@api_router.get("/kalshi/orderbook/{ticker}")
async def get_kalshi_orderbook(ticker: str):
    """Get orderbook for a specific market"""
    if not kalshi_basketball_ingestor:
        raise HTTPException(status_code=503, detail="Kalshi ingestor not initialized")
    
    orderbook = await kalshi_basketball_ingestor.get_orderbook(ticker)
    if not orderbook:
        raise HTTPException(status_code=404, detail=f"Orderbook not found for {ticker}")
    
    return orderbook.dict()

# ============================================
# CAPITAL PREVIEW ENGINE
# ============================================

@api_router.get("/capital/preview/{game_id}")
async def get_capital_preview(game_id: str):
    """
    Get capital allocation preview for a specific game.
    Shows "What To Expect" panel with projections for all models.
    """
    global capital_engine
    
    if not capital_engine:
        from services.capital_preview_engine import CapitalPreviewEngine
        capital_engine = CapitalPreviewEngine(strategy_manager.strategies)
    
    preview = capital_engine.get_preview(game_id)
    if not preview:
        raise HTTPException(status_code=404, detail=f"No preview available for game {game_id}")
    
    return preview

@api_router.get("/capital/previews")
async def get_all_capital_previews():
    """Get all cached capital previews"""
    global capital_engine
    
    if not capital_engine:
        from services.capital_preview_engine import CapitalPreviewEngine
        capital_engine = CapitalPreviewEngine(strategy_manager.strategies)
    
    return capital_engine.get_all_previews()

@api_router.post("/capital/generate/{game_id}")
async def generate_capital_preview(game_id: str):
    """
    Generate fresh capital preview for a game.
    Requires game data to be available.
    """
    global capital_engine
    
    if not capital_engine:
        from services.capital_preview_engine import CapitalPreviewEngine
        capital_engine = CapitalPreviewEngine(strategy_manager.strategies)
    
    # Get game data
    game = await game_repo.get_by_id(game_id)
    if not game:
        games = await espn_adapter.get_todays_games()
        game = next((g for g in games if g.id == game_id), None)
    
    if not game:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    # Get market
    markets = await kalshi_adapter.get_markets_for_game(game_id)
    home_market = next((m for m in markets if m.outcome == "home"), None)
    
    if not home_market:
        raise HTTPException(status_code=404, detail="No market found for game")
    
    # Get signal
    home_prob, _ = prob_engine.calculate_win_probability(game, home_market.implied_probability)
    confidence = prob_engine.get_probability_confidence(game)
    position = await kalshi_adapter.get_position(home_market.id)
    signal = signal_engine.generate_signal(game, home_market, home_prob, confidence, position)
    
    # Get orderbook
    orderbook = await kalshi_adapter.get_orderbook(home_market.id)
    orderbook_dict = None
    if orderbook:
        orderbook_dict = {
            "total_liquidity": getattr(orderbook, 'total_liquidity', 0),
            "spread_cents": 2
        }
    
    # Generate preview
    preview = capital_engine.generate_game_preview(
        game=game,
        market=home_market,
        signal=signal,
        orderbook=orderbook_dict
    )
    
    return preview.to_dict()

# ============================================
# PERFORMANCE TRACKING
# ============================================

@api_router.get("/performance/models")
async def get_all_model_performance():
    """Get performance metrics for all models"""
    global perf_tracker
    
    if not perf_tracker:
        from services.performance_tracker import PerformanceTracker
        perf_tracker = PerformanceTracker(db)
    
    return perf_tracker.get_all_model_metrics()

@api_router.get("/performance/models/{model_id}")
async def get_model_performance(model_id: str):
    """Get performance metrics for a specific model"""
    global perf_tracker
    
    if not perf_tracker:
        from services.performance_tracker import PerformanceTracker
        perf_tracker = PerformanceTracker(db)
    
    metrics = perf_tracker.get_model_metrics(model_id)
    if not metrics:
        raise HTTPException(status_code=404, detail=f"No metrics for model {model_id}")
    
    return metrics

@api_router.get("/performance/comparison")
async def get_performance_comparison():
    """
    Get side-by-side performance comparison table.
    
    Tracks per model:
    - Expected vs Actual Profit
    - Slippage
    - Stop Hits / Missed Targets
    - Performance by League, Game Phase, Volatility, Liquidity
    """
    global perf_tracker
    
    if not perf_tracker:
        from services.performance_tracker import PerformanceTracker
        perf_tracker = PerformanceTracker(db)
    
    return perf_tracker.get_comparison_table()

@api_router.get("/performance/league/{model_id}")
async def get_league_performance(model_id: str):
    """Get performance breakdown by league for a model"""
    global perf_tracker
    
    if not perf_tracker:
        from services.performance_tracker import PerformanceTracker
        perf_tracker = PerformanceTracker(db)
    
    return perf_tracker.get_league_breakdown(model_id)

@api_router.get("/performance/trades")
async def get_performance_trades(
    model_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200)
):
    """Get recent trade records with performance data"""
    global perf_tracker
    
    if not perf_tracker:
        from services.performance_tracker import PerformanceTracker
        perf_tracker = PerformanceTracker(db)
    
    return {"trades": perf_tracker.get_recent_trades(model_id, limit)}

# ============================================
# AUTONOMOUS TRADING METRICS (24-HOUR DASHBOARD)
# ============================================

# Global autonomous metrics instance
autonomous_metrics_service = None

@api_router.get("/autonomous/dashboard")
async def get_autonomous_dashboard():
    """
    Get full 24-hour autonomous trading dashboard.
    
    Includes:
    - System health (uptime, memory, CPU)
    - Performance summary (trades, PnL, win rate, Sharpe, max DD)
    - Per-minute metrics (markets/signals/trades per minute)
    - Hourly summary
    - Per-model breakdown
    - Scheduler heartbeat and scanning metrics
    """
    global autonomous_metrics_service, autonomous_scheduler_instance
    
    if not autonomous_metrics_service:
        from services.autonomous_metrics import AutonomousMetricsService
        autonomous_metrics_service = AutonomousMetricsService(db)
    
    # Get strategy data for performance calc
    strategies = {}
    if strategy_manager:
        summary = strategy_manager.get_summary()  # Not async
        strategies = summary.get("strategies", {})
    
    # Get base dashboard
    dashboard = autonomous_metrics_service.get_full_dashboard(strategies)
    
    # Add scheduler metrics if available
    if autonomous_scheduler_instance:
        dashboard["scheduler"] = autonomous_scheduler_instance.get_metrics_summary()
    else:
        dashboard["scheduler"] = {
            "scheduler_status": "not_started",
            "message": "Enable autonomous mode to start scheduler"
        }
    
    return dashboard

@api_router.get("/autonomous/metrics/minute")
async def get_minute_metrics(
    last_n: int = Query(60, ge=1, le=1440)
):
    """Get per-minute metrics for last N minutes"""
    global autonomous_metrics_service
    
    if not autonomous_metrics_service:
        from services.autonomous_metrics import AutonomousMetricsService
        autonomous_metrics_service = AutonomousMetricsService(db)
    
    return {"metrics": autonomous_metrics_service.get_minute_metrics(last_n)}

@api_router.get("/autonomous/metrics/hourly")
async def get_hourly_metrics():
    """Get hourly aggregated metrics"""
    global autonomous_metrics_service
    
    if not autonomous_metrics_service:
        from services.autonomous_metrics import AutonomousMetricsService
        autonomous_metrics_service = AutonomousMetricsService(db)
    
    return {"hourly": autonomous_metrics_service.get_hourly_summary()}

@api_router.get("/autonomous/health")
async def get_system_health():
    """Get current system health metrics"""
    global autonomous_metrics_service
    
    if not autonomous_metrics_service:
        from services.autonomous_metrics import AutonomousMetricsService
        autonomous_metrics_service = AutonomousMetricsService(db)
    
    return autonomous_metrics_service.get_system_health().to_dict()

# Global scheduler instance
autonomous_scheduler_instance = None

# Global hourly snapshot service
hourly_snapshot_service = None

@api_router.get("/health/full")
async def get_full_health():
    """
    Full system health check including scheduler heartbeat.
    
    Returns:
    - autonomous_enabled (bool)
    - strategy_loop_last_tick_at
    - strategy_loop_ticks_total
    - discovery_loop_last_tick_at
    - discovery_loop_ticks_total
    - uptime_sec
    - db_ping
    - ws_connections
    """
    global autonomous_scheduler_instance, autonomous_metrics_service, app_start_time
    
    # Calculate uptime
    uptime_sec = 0
    if app_start_time:
        uptime_sec = (datetime.utcnow() - app_start_time).total_seconds()
    
    # Test DB connectivity
    db_ping = False
    try:
        if db is not None:
            await db.command("ping")
            db_ping = True
    except Exception as e:
        logger.error(f"DB ping failed: {e}")
    
    # Check if autonomous mode is enabled
    autonomous_enabled = False
    strategy_loop_last_tick_at = None
    strategy_loop_ticks_total = 0
    discovery_loop_last_tick_at = None
    discovery_loop_ticks_total = 0
    
    if autonomous_scheduler_instance:
        autonomous_enabled = autonomous_scheduler_instance._running
        hb = autonomous_scheduler_instance.heartbeat
        
        strategy_loop_last_tick_at = hb.trading_loop_last_tick_at.isoformat() if hb.trading_loop_last_tick_at else None
        strategy_loop_ticks_total = hb.trading_loop_ticks_total
        discovery_loop_last_tick_at = hb.discovery_loop_last_tick_at.isoformat() if hb.discovery_loop_last_tick_at else None
        discovery_loop_ticks_total = hb.discovery_loop_ticks_total
    
    return {
        "autonomous_enabled": autonomous_enabled,
        "strategy_loop_last_tick_at": strategy_loop_last_tick_at,
        "strategy_loop_ticks_total": strategy_loop_ticks_total,
        "discovery_loop_last_tick_at": discovery_loop_last_tick_at,
        "discovery_loop_ticks_total": discovery_loop_ticks_total,
        "uptime_sec": int(uptime_sec),
        "db_ping": db_ping,
        "ws_connections": len(ws_manager.active_connections),
        "timestamp": datetime.utcnow().isoformat()
    }

@api_router.get("/autonomous/scheduler/status")
async def get_scheduler_status():
    """Get detailed scheduler status with heartbeat and scanning metrics"""
    global autonomous_scheduler_instance
    
    if autonomous_scheduler_instance:
        return autonomous_scheduler_instance.get_metrics_summary()
    
    return {
        "scheduler_status": "not_started",
        "discovery_ticks": 0,
        "trading_ticks": 0,
        "open_markets": 0
    }

@api_router.get("/autonomous/metrics")
async def get_autonomous_metrics():
    """
    Get autonomous trading metrics for dashboard display.
    
    Returns:
    - events_scanned_last_min
    - markets_scanned_last_min
    - events_next_24h_count
    - markets_next_24h_count
    - open_markets_found_last_min
    - next_open_market_eta
    - filtered_out_reason_counts
    """
    global autonomous_scheduler_instance
    
    if not autonomous_scheduler_instance:
        return {
            "events_scanned_last_min": 0,
            "markets_scanned_last_min": 0,
            "events_next_24h_count": 0,
            "markets_next_24h_count": 0,
            "open_markets_found_last_min": 0,
            "next_open_market_eta": None,
            "filtered_out_reason_counts": {},
            "status": "scheduler_not_started"
        }
    
    scanning = autonomous_scheduler_instance.scanning
    filters = autonomous_scheduler_instance.filters
    
    return {
        "events_scanned_last_min": scanning.events_scanned_last_min,
        "markets_scanned_last_min": scanning.markets_scanned_last_min,
        "events_next_24h_count": scanning.events_next_24h_count,
        "markets_next_24h_count": scanning.markets_next_24h_count,
        "open_markets_found_last_min": scanning.open_markets_found_last_min,
        "open_events_found_last_min": scanning.open_events_found_last_min,
        "next_open_market_eta": scanning.next_open_market_eta,
        "next_open_market_ticker": scanning.next_open_market_ticker,
        "next_open_market_title": scanning.next_open_market_title,
        "filtered_out_reason_counts": dict(filters.filtered_out_counts),
        "passed_filter_count": filters.passed_filter_count,
        "total_evaluated": filters.total_evaluated,
        "pass_rate_pct": round((filters.passed_filter_count / filters.total_evaluated * 100) if filters.total_evaluated > 0 else 0, 1),
        "status": "running" if autonomous_scheduler_instance._running else "stopped"
    }

@api_router.post("/autonomous/enable")
async def enable_autonomous_mode():
    """
    Enable full autonomous trading mode for all 3 models.
    
    This will:
    - Enable all strategies
    - Set to AUTO mode
    - Start Discovery Loop (30s interval) - always running
    - Start Trading Loop (3s interval) - active when markets open
    - Start Hourly Snapshot Service for 24h monitoring
    - Begin logging all metrics
    """
    global autonomous_metrics_service, autonomous_scheduler_instance, hourly_snapshot_service
    
    try:
        # Validate dependencies
        if db is None:
            raise RuntimeError("Database not initialized")
        
        if strategy_manager is None:
            raise RuntimeError("Strategy manager not initialized")
        
        # Initialize metrics service
        if not autonomous_metrics_service:
            try:
                from services.autonomous_metrics import AutonomousMetricsService
                logger.info("Creating AutonomousMetricsService...")
                autonomous_metrics_service = AutonomousMetricsService(db)
                logger.info("AutonomousMetricsService created successfully")
            except Exception as e:
                error_msg = f"Failed to initialize metrics service: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise HTTPException(status_code=500, detail=error_msg)
        
        # Create and start scheduler
        if not autonomous_scheduler_instance:
            try:
                from services.autonomous_scheduler import AutonomousScheduler
                logger.info("Creating AutonomousScheduler...")
                autonomous_scheduler_instance = AutonomousScheduler(
                    db=db,
                    strategy_manager=strategy_manager
                )
                logger.info("AutonomousScheduler created successfully")
            except Exception as e:
                error_msg = f"Scheduler creation failed: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise HTTPException(status_code=500, detail=error_msg)
        
        # Start the scheduler loops
        try:
            logger.info("Starting scheduler loops...")
            await autonomous_scheduler_instance.start()
            logger.info("Scheduler loops started successfully")
        except Exception as e:
            error_msg = f"Failed to start scheduler: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise HTTPException(status_code=500, detail=error_msg)
        
        # Start hourly snapshot service for 24h monitoring
        try:
            from services.hourly_snapshot_service import HourlyMetricsSnapshotService
            if not hourly_snapshot_service:
                logger.info("Creating HourlyMetricsSnapshotService...")
                hourly_snapshot_service = HourlyMetricsSnapshotService(
                    db=db,
                    scheduler=autonomous_scheduler_instance,
                    metrics_service=autonomous_metrics_service,
                    strategy_manager=strategy_manager
                )
                logger.info("HourlyMetricsSnapshotService created successfully")
            logger.info("Starting hourly snapshot service...")
            await hourly_snapshot_service.start()
            logger.info("Hourly snapshot service started successfully")
        except Exception as e:
            error_msg = f"Failed to start hourly snapshot service: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # Don't fail the entire enable if this fails - it's not critical
            logger.warning("Continuing without hourly snapshot service")
        
        # Enable all strategies
        try:
            logger.info("Enabling strategies...")
            strategy_manager.enable()
            logger.info("Strategies enabled successfully")
            
            # Log the activation
            if autonomous_metrics_service:
                logger.info("Logging autonomous mode activation...")
                await autonomous_metrics_service.persist_audit_log({
                    "event_type": "AUTONOMOUS_MODE_ENABLED",
                    "models": ["model_a_disciplined", "model_b_high_frequency", "model_c_institutional"],
                    "mode": "AUTO",
                    "scheduler": "2-loop (discovery + trading)",
                    "hourly_snapshots": "enabled if available"
                })
                logger.info("Audit log created successfully")
        except Exception as e:
            error_msg = f"Strategy enable failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise HTTPException(status_code=500, detail=error_msg)
        
        return {
            "status": "AUTONOMOUS_MODE_ENABLED",
            "models_enabled": 3,
            "mode": "AUTO",
            "scheduler": {
                "discovery_loop": "running (30s interval)",
                "trading_loop": "running (3s interval, active when markets open)"
            },
            "hourly_snapshots": {
                "enabled": True,
                "directory": "/app/logs/metrics_snapshots",
                "interval": "1 hour"
            },
            "timestamp": datetime.utcnow().isoformat(),
            "message": "All 3 models now running in full autonomous paper trading mode with 2-loop scheduler and hourly snapshots"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.exception(f"Unexpected error in enable_autonomous_mode: {error_msg}")
        logger.error(f"Full traceback: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Failed to enable autonomous mode: {error_msg}")

@api_router.post("/autonomous/disable")
async def disable_autonomous_mode():
    """Disable autonomous trading mode and stop scheduler"""
    global autonomous_metrics_service, autonomous_scheduler_instance, hourly_snapshot_service
    
    try:
        # Stop hourly snapshot service
        if hourly_snapshot_service:
            try:
                await hourly_snapshot_service.stop()
            except Exception as e:
                logger.error(f"Error stopping hourly snapshot service: {e}")
        
        # Stop scheduler
        if autonomous_scheduler_instance:
            try:
                await autonomous_scheduler_instance.stop()
            except Exception as e:
                logger.error(f"Error stopping scheduler: {e}")
        
        if strategy_manager:
            try:
                strategy_manager.disable()
            except Exception as e:
                logger.error(f"Error disabling strategies: {e}")
            
            if autonomous_metrics_service:
                try:
                    await autonomous_metrics_service.persist_audit_log({
                        "event_type": "AUTONOMOUS_MODE_DISABLED"
                    })
                except Exception as e:
                    logger.error(f"Error logging disable event: {e}")
        
        return {
            "status": "AUTONOMOUS_MODE_DISABLED",
            "scheduler": "stopped",
            "hourly_snapshots": "stopped (summary report generated)",
            "message": "Autonomous trading mode disabled",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.exception("Unexpected error in disable_autonomous_mode")
        raise HTTPException(status_code=500, detail=f"Failed to disable autonomous mode: {str(e)}")

@api_router.post("/autonomous/run_cycle")
async def run_trading_cycle():
    """
    Immediately run one full auto-trading cycle using the SAME data source as the
    Terminal page (Dashboard.jsx + useRealtimeGames.js):

      Kalshi Series API → edge = marketPrice − 50¢ (fair = 50¢ hardcoded)
      signal_score       = min(100, |edge| × 1000)
      momentum           = price_delta sign (>0 → "up", <0 → "down")

    This ensures trade counts and model matching are identical whether triggered
    from the Terminal or the Trades page.
    """
    import uuid as _uuid
    import httpx

    # ── Model definitions (identical to Dashboard.jsx STRATEGIES) ─────────
    MODELS = [
        {
            "model_id": "model_a_disciplined",
            "display_name": "Model A - Disciplined Edge Trader",
            "min_edge": 0.05,
            "min_signal_score": 65,
            "require_positive_momentum": True,
            "max_open": 10,
        },
        {
            "model_id": "model_b_high_frequency",
            "display_name": "Model B - High Frequency Edge Hunter",
            "min_edge": 0.03,
            "min_signal_score": 45,
            "require_positive_momentum": False,
            "max_open": 10,
        },
    ]

    # ── Step 1: Fetch from Kalshi Series API (same as useRealtimeGames.js) ─
    KALSHI_SERIES_URL = (
        "https://api.elections.kalshi.com/v1/search/series"
        "?order_by=trending&status=open,unopened&category=Sports"
        "&tag=Basketball&scope=Games&page_size=100"
        "&include_sports_derivatives=false&with_milestones=true"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(KALSHI_SERIES_URL, headers={"Accept": "application/json"})
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Kalshi Series API returned {resp.status_code}")
        series_list = resp.json().get("current_page", [])
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Kalshi Series API unreachable: {exc}")

    if not series_list:
        return {"status": "no_games", "trades_placed": 0, "message": "No Basketball series found on Kalshi"}

    # ── Step 2: Load existing open trades to check model caps / duplicates ─
    from models.trade import Trade
    existing_trades = await trade_repo.get_all(limit=1000)
    open_game_model_pairs: set = set()
    model_open_counts: dict = {"model_a": 0, "model_b": 0}

    for t in existing_trades:
        closed = getattr(t, "status", None) in ("closed", "cancelled", "expired")
        has_closed_at = bool(getattr(t, "closed_at", None))
        if not closed and not has_closed_at:
            gid = getattr(t, "game_id", None)
            strat = (getattr(t, "strategy", "") or "").lower().replace(" ", "_")
            mk = "model_b" if "model_b" in strat else "model_a"
            if gid:
                open_game_model_pairs.add((gid, mk))
            if "model_b" in strat:
                model_open_counts["model_b"] += 1
            elif "model_a" in strat:
                model_open_counts["model_a"] += 1

    placed = 0
    skipped = 0

    # ── Step 3: Evaluate each series ──────────────────────────────────────
    for series in series_list:
        try:
            markets = series.get("markets", [])
            if not markets:
                continue

            m0 = markets[0] if len(markets) > 0 else {}
            m1 = markets[1] if len(markets) > 1 else {}

            # Primary market for pricing (same logic as useRealtimeGames.js)
            primary = m0 if m0.get("yes_bid") is not None else (m1 or m0)

            # Market price in cents (same formula as useRealtimeGames.js)
            yes_bid = primary.get("yes_bid")
            yes_ask = primary.get("yes_ask")
            last    = primary.get("last_price")

            if last is not None:
                market_cents = last
            elif yes_bid is not None and yes_ask is not None:
                market_cents = round((yes_bid + yes_ask) / 2)
            elif yes_bid is not None:
                market_cents = yes_bid
            elif yes_ask is not None:
                market_cents = yes_ask
            else:
                market_cents = 50

            # Fair price is always 50¢ (hardcoded in useRealtimeGames.js)
            fair_cents  = 50
            market_dec  = market_cents / 100.0
            edge_dec    = (market_cents - fair_cents) / 100.0   # = marketDec − 0.50

            # Skip non-actionable markets (|edge| < 3¢, same as is_actionable in frontend)
            if abs(edge_dec) < 0.03:
                continue
            if market_dec <= 0:
                continue

            # Signal score: identical to useRealtimeGames.js formula
            signal_score = min(100.0, abs(edge_dec) * 1000.0)

            # Momentum: from price_delta (same as useRealtimeGames.js intelligence.momentum)
            price_delta = primary.get("price_delta") or 0
            if price_delta > 0:
                momentum = "up"
            elif price_delta < 0:
                momentum = "down"
            else:
                # No price_delta available — fall back to edge direction
                momentum = "up" if edge_dec > 0 else "down"

            # Game / market identifiers
            game_id = series.get("event_ticker") or series.get("series_ticker")
            if not game_id:
                continue

            market_id = primary.get("ticker") or primary.get("market_ticker") or game_id

            # Team names (same logic as useRealtimeGames.js)
            away = m0.get("name") or m0.get("yes_sub_title") or m0.get("yes_subtitle") or "AWAY"
            home = m1.get("name") or m1.get("yes_sub_title") or m1.get("yes_subtitle") or "HOME"
            game_title = f"{away} @ {home}"

            league = (
                series.get("league")
                or (series.get("product_metadata") or {}).get("competition")
                or "Basketball"
            )

            # YES side = we think price will go to 100¢ (edge > 0 means market is cheap)
            # NO side  = we think price will go to 0¢   (edge < 0 means market is expensive)
            trade_side = "yes" if edge_dec > 0 else "no"

            # ── Evaluate each model independently ────────────────────────
            for model in MODELS:
                mk = "model_b" if "b" in model["model_id"] else "model_a"

                if (game_id, mk) in open_game_model_pairs:
                    skipped += 1
                    continue
                if model_open_counts[mk] >= model["max_open"]:
                    continue
                if abs(edge_dec) < model["min_edge"]:
                    continue
                if signal_score < model["min_signal_score"]:
                    continue
                if model["require_positive_momentum"] and momentum != "up":
                    continue

                now = datetime.utcnow()
                trade_id = f"auto-be-{int(now.timestamp())}-{_uuid.uuid4().hex[:8]}"
                doc = {
                    "id":              trade_id,
                    "game_id":         game_id,
                    "market_id":       market_id,
                    "side":            trade_side,
                    "direction":       "buy",
                    "quantity":        10,
                    "price":           market_dec,
                    "order_type":      "market",
                    "limit_price":     None,
                    "status":          "filled",
                    "filled_quantity": 10,
                    "avg_fill_price":  market_dec,
                    "entry_price":     market_dec,
                    "fees":            0.0,
                    "is_paper":        True,
                    "created_at":      now,
                    "executed_at":     now,
                    "timestamp":       now,
                    "signal_type":     "STRONG_BUY" if abs(edge_dec) > 0.05 else "BUY",
                    "edge_at_entry":   float(edge_dec),
                    "type":            "auto-edge",
                    "strategy":        model["display_name"],
                    "market_name":     primary.get("subtitle") or primary.get("yes_sub_title") or "Home Team",
                    "game_title":      game_title,
                    "league":          league,
                    "current_price":   market_dec,
                    "exit_price":      None,
                    "closed_at":       None,
                    "pnl":             0.0,
                    "realized_pnl":    0.0,
                }
                trade = Trade(**doc)
                await trade_repo.create(trade)

                model_open_counts[mk] += 1
                open_game_model_pairs.add((game_id, mk))
                placed += 1

                logger.info(
                    f"[run_cycle] ✅ {model['display_name']} → {game_id} "
                    f"| edge={edge_dec*100:.1f}¢ score={signal_score:.0f} "
                    f"momentum={momentum} side={trade_side}"
                )

        except Exception as exc:
            logger.warning(f"[run_cycle] Skipped series {series.get('event_ticker', '?')}: {exc}")
            continue

    return {
        "status": "ok",
        "trades_placed": placed,
        "games_evaluated": len(series_list),
        "games_skipped_existing": skipped,
        "message": f"Trading cycle complete — {placed} new trade(s) placed across {len(series_list)} Kalshi series",
    }


# ============================================
# HOURLY SNAPSHOT SERVICE
# ============================================

@api_router.get("/snapshots/status")
async def get_snapshot_status():
    """Get hourly snapshot service status"""
    global hourly_snapshot_service
    
    if not hourly_snapshot_service:
        return {
            "status": "not_started",
            "message": "Enable autonomous mode to start hourly snapshots"
        }
    
    return hourly_snapshot_service.get_status()

@api_router.post("/snapshots/take")
async def take_manual_snapshot():
    """Take an immediate snapshot (for testing/verification)"""
    global hourly_snapshot_service
    
    if not hourly_snapshot_service:
        # Create temporary instance for manual snapshot
        from services.hourly_snapshot_service import HourlyMetricsSnapshotService
        temp_service = HourlyMetricsSnapshotService(
            db=db,
            scheduler=autonomous_scheduler_instance,
            metrics_service=autonomous_metrics_service,
            strategy_manager=strategy_manager
        )
        snapshot = await temp_service.take_manual_snapshot()
        return {"snapshot": snapshot, "note": "Manual snapshot taken (service not running)"}
    
    snapshot = await hourly_snapshot_service.take_manual_snapshot()
    return {"snapshot": snapshot}

@api_router.get("/snapshots/list")
async def list_snapshots():
    """List all snapshot files"""
    import os
    snapshots_dir = "/app/logs/metrics_snapshots"
    
    if not os.path.exists(snapshots_dir):
        return {"snapshots": [], "count": 0}
    
    files = sorted([f for f in os.listdir(snapshots_dir) if f.endswith('.json')])
    return {
        "snapshots": files,
        "count": len(files),
        "directory": snapshots_dir
    }

@api_router.get("/snapshots/{filename}")
async def get_snapshot(filename: str):
    """Get a specific snapshot file content"""
    import os
    snapshots_dir = "/app/logs/metrics_snapshots"
    filepath = os.path.join(snapshots_dir, filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    with open(filepath, 'r') as f:
        return json.load(f)

# ============================================
# WEBSOCKET
# ============================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)

app.include_router(auth_router)
app.include_router(trades_router)
app.include_router(decisions_router)
app.include_router(debug_router)
app.include_router(api_router)
