import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../components/ui/tooltip';
import {
  RefreshCw,
  Activity,
  TrendingUp,
  TrendingDown,
  Minus,
  Wifi,
  Zap,
  Flame,
  AlertTriangle,
  DollarSign,
  Play,
  Pause,
  Loader2
} from 'lucide-react';
import { formatPercent, formatCurrency, getSettings } from '../services/api';
import useRealtimeGames from '../hooks/useRealtimeGames';
import ThemeToggle from '../components/ThemeToggle';
import { placeTrade, closeTrade } from '../services/tradeService';

// ─── Inline Page Transition Loader ───────────────────────────────────────────
const usePageLoader = () => {
  const [show, setShow] = useState(true);   // true on every mount
  const [fadeOut, setFadeOut] = useState(false);
  const timerRef = useRef(null);

  // Show loader on back/forward button
  useEffect(() => {
    const handlePop = () => {
      setFadeOut(false);
      setShow(true);
    };
    window.addEventListener('popstate', handlePop);
    return () => window.removeEventListener('popstate', handlePop);
  }, []);

  // Auto-hide after mount
  useEffect(() => {
    if (show) {
      timerRef.current = setTimeout(() => {
        setFadeOut(true);
        timerRef.current = setTimeout(() => setShow(false), 400);
      }, 600); // minimum visible time
    }
    return () => clearTimeout(timerRef.current);
  }, [show]);

  return { show, fadeOut };
};

const PageLoader = () => {
  const { show, fadeOut } = usePageLoader();
  if (!show) return null;

  return (
    <>
      <style>{`
        .ptl-overlay {
          position: fixed; inset: 0; z-index: 9999;
          background: rgba(9,9,11,0.85);
          backdrop-filter: blur(6px);
          -webkit-backdrop-filter: blur(6px);
          display: flex; flex-direction: column;
          align-items: center; justify-content: center;
          transition: opacity 0.4s ease;
        }
        .ptl-overlay.out { opacity: 0; pointer-events: none; }
        .ptl-overlay.in  { opacity: 1; }

        .ptl-bar {
          position: absolute; top: 0; left: 0;
          height: 2px; width: 100%;
          background: linear-gradient(90deg, transparent 0%, #3b82f6 30%, #8b5cf6 60%, transparent 100%);
          background-size: 200% 100%;
          animation: ptl-slide 1.1s linear infinite;
        }
        @keyframes ptl-slide {
          0%   { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }

        .ptl-body {
          display: flex; flex-direction: column;
          align-items: center; gap: 18px;
          animation: ptl-up 0.3s ease both;
        }
        @keyframes ptl-up {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0); }
        }

        .ptl-ring { position: relative; width: 48px; height: 48px; }
        .ptl-ring div {
          box-sizing: border-box;
          position: absolute; width: 40px; height: 40px;
          margin: 4px; border: 3px solid transparent;
          border-radius: 50%;
          animation: ptl-spin 1.1s cubic-bezier(0.5,0,0.5,1) infinite;
        }
        .ptl-ring div:nth-child(1){ border-top-color:#3b82f6; animation-delay:-0.45s; }
        .ptl-ring div:nth-child(2){ border-top-color:#6366f1; animation-delay:-0.3s;  }
        .ptl-ring div:nth-child(3){ border-top-color:#8b5cf6; animation-delay:-0.15s; }
        .ptl-ring div:nth-child(4){ border-top-color:#a78bfa; }
        @keyframes ptl-spin {
          0%   { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }

        .ptl-label {
          font-family: ui-monospace, 'Fira Code', monospace;
          font-size: 11px; letter-spacing: 0.14em;
          text-transform: uppercase;
          color: rgba(148,163,184,0.7);
          animation: ptl-blink 1.4s ease-in-out infinite;
        }
        @keyframes ptl-blink {
          0%,100% { opacity: 0.4; }
          50%      { opacity: 1;   }
        }
      `}</style>

      <div className={`ptl-overlay ${fadeOut ? 'out' : 'in'}`} aria-hidden="true">
        <div className="ptl-bar" />
        <div className="ptl-body">
          <div className="ptl-ring">
            <div /><div /><div /><div />
          </div>
          <span className="ptl-label">Loading Dashboard</span>
        </div>
      </div>
    </>
  );
};


// ─────────────────────────────────────────────────────────────────────────────
// STRATEGY DEFINITIONS (NEW MODELS)
// ─────────────────────────────────────────────────────────────────────────────
const STRATEGIES = [
  {
    model_id: "model_a_disciplined",
    display_name: "Model A - Disciplined Edge Trader",
    description: "Higher edge threshold, moderate sizing, controlled churn",
    enabled: true,
    starting_capital: 20000,
    currency: "USD",
    entry_rules: {
      min_edge_threshold: 0.05,
      min_signal_score: 65,
      min_persistence_ticks: 3,
      max_entries_per_game: 3,
      cooldown_seconds: 180,
      require_positive_momentum: true
    },
    exit_rules: {
      edge_compression_exit_threshold: 0.02,
      profit_target_pct: 0.15,
      stop_loss_pct: 0.1,
      time_based_exit_seconds: 600,
      trailing_stop_pct: 0.05
    },
    position_sizing: {
      base_size_pct: 0.02,
      max_position_pct: 0.05,
      kelly_fraction: 0.25,
      scale_with_edge: true,
      edge_scale_factor: 2
    },
    risk_limits: {
      max_daily_loss_pct: 0.05,
      max_exposure_pct: 0.15,
      max_trades_per_hour: 10,
      max_trades_per_day: 10,
      max_open_trades: 10,
      max_trades_per_game: 3,
      max_drawdown_pct: 0.1
    },
    filters: {
      min_liquidity_contracts: 50,
      max_spread_pct: 0.05,
      volatility_regime_allowed: ["low", "medium"],
      min_game_progress: 0.1,
      max_game_progress: 0.95,
      allowed_leagues: ["NBA", "NCAA_M", "NCAA_W"]
    },
    trim_rules: {
      enable_trim: true,
      trim_at_profit_pct: 0.1,
      trim_size_pct: 0.5,
      trim_on_edge_decay: true,
      edge_decay_threshold: 0.03
    },
    circuit_breakers: {
      pause_on_consecutive_losses: 3,
      pause_duration_seconds: 600,
      pause_on_drawdown_pct: 0.05,
      auto_resume: true
    }
  },
  {
    model_id: "model_b_high_frequency",
    display_name: "Model B - High Frequency Edge Hunter",
    description: "Lower threshold, aggressive entries, faster exits, higher churn",
    enabled: true,
    starting_capital: 10000,
    currency: "USD",
    entry_rules: {
      min_edge_threshold: 0.03,
      min_signal_score: 45,
      min_persistence_ticks: 2,
      max_entries_per_game: 8,
      cooldown_seconds: 60,
      require_positive_momentum: false
    },
    exit_rules: {
      edge_compression_exit_threshold: 0.01,
      profit_target_pct: 0.08,
      stop_loss_pct: 0.06,
      time_based_exit_seconds: 300,
      trailing_stop_pct: 0.03
    },
    position_sizing: {
      base_size_pct: 0.015,
      max_position_pct: 0.04,
      kelly_fraction: 0.2,
      scale_with_edge: true,
      edge_scale_factor: 1.5
    },
    risk_limits: {
      max_daily_loss_pct: 0.08,
      max_exposure_pct: 0.25,
      max_trades_per_hour: 10,
      max_trades_per_day: 10,
      max_open_trades: 10,
      max_trades_per_game: 8,
      max_drawdown_pct: 0.15
    },
    filters: {
      min_liquidity_contracts: 30,
      max_spread_pct: 0.08,
      volatility_regime_allowed: ["low", "medium", "high"],
      min_game_progress: 0.05,
      max_game_progress: 0.98,
      allowed_leagues: ["NBA", "NCAA_M", "NCAA_W"]
    },
    trim_rules: {
      enable_trim: true,
      trim_at_profit_pct: 0.05,
      trim_size_pct: 0.6,
      trim_on_edge_decay: true,
      edge_decay_threshold: 0.02
    },
    circuit_breakers: {
      pause_on_consecutive_losses: 5,
      pause_duration_seconds: 300,
      pause_on_drawdown_pct: 0.08,
      auto_resume: true
    }
  },
  {
    model_id: "model_c_institutional",
    display_name: "Model C - Institutional Risk-First",
    description: "Highest requirements, strong filters, most conservative sizing",
    enabled: false, // DISABLED: Validation mode — Model A only
    starting_capital: 10000,
    currency: "USD",
    entry_rules: {
      min_edge_threshold: 0.07,
      min_signal_score: 75,
      min_persistence_ticks: 4,
      max_entries_per_game: 2,
      cooldown_seconds: 300,
      require_positive_momentum: true
    },
    exit_rules: {
      edge_compression_exit_threshold: 0.03,
      profit_target_pct: 0.2,
      stop_loss_pct: 0.08,
      time_based_exit_seconds: 900,
      trailing_stop_pct: 0.04
    },
    position_sizing: {
      base_size_pct: 0.01,
      max_position_pct: 0.03,
      kelly_fraction: 0.15,
      scale_with_edge: true,
      edge_scale_factor: 1.5
    },
    risk_limits: {
      max_daily_loss_pct: 0.03,
      max_exposure_pct: 0.1,
      max_trades_per_hour: 2,
      max_trades_per_day: 10,
      max_trades_per_game: 2,
      max_drawdown_pct: 0.06
    },
    filters: {
      min_liquidity_contracts: 100,
      max_spread_pct: 0.03,
      volatility_regime_allowed: ["low"],
      min_game_progress: 0.2,
      max_game_progress: 0.9,
      allowed_leagues: ["NBA", "NCAA_M", "NCAA_W"],
      require_strong_liquidity: true,
      min_volume_24h: 1000
    },
    trim_rules: {
      enable_trim: false,
      trim_at_profit_pct: 0.15,
      trim_size_pct: 0.4,
      trim_on_edge_decay: false,
      edge_decay_threshold: 0.04
    },
    circuit_breakers: {
      pause_on_consecutive_losses: 2,
      pause_duration_seconds: 900,
      pause_on_drawdown_pct: 0.03,
      auto_resume: false,
      require_manual_reset: true
    },
    adverse_move_protection: {
      enable_hard_stop: true,
      hard_stop_pct: 0.05,
      enable_time_stop: true,
      max_adverse_time_seconds: 120
    }
  }
];

/**
 * Evaluate which models match the current signal based on entry rules
 * Professional implementation with comprehensive rule checking
 */
const evaluateStrategies = (signal, isClutch, momentum) => {
  const edge = signal?.edge ?? 0;
  const signalScore = signal?.signal_score ?? 0;

  return STRATEGIES.map((model) => {
    if (!model.enabled) {
      return { model, ruleResults: [], matched: false, reason: 'Model disabled' };
    }

    const entryRules = model.entry_rules;
    const ruleResults = [];

    // Rule 1: Minimum Edge Threshold
    const edgeCheck = Math.abs(edge) >= entryRules.min_edge_threshold;
    ruleResults.push({
      label: `Edge ≥ ${(entryRules.min_edge_threshold * 100).toFixed(1)}%`,
      passed: edgeCheck,
      value: `${(edge * 100).toFixed(2)}% ${!edgeCheck ? `(required ≥ ${(entryRules.min_edge_threshold * 100).toFixed(1)}%)` : ''}`
    });

    // Rule 2: Minimum Signal Score
    const scoreCheck = signalScore >= entryRules.min_signal_score;
    ruleResults.push({
      label: `Signal Score ≥ ${entryRules.min_signal_score}`,
      passed: scoreCheck,
      value: `${Math.round(signalScore)} ${!scoreCheck ? `(required ≥ ${entryRules.min_signal_score})` : ''}`
    });

    // Rule 3: Positive Momentum (if required)
    const momentumCheck = !entryRules.require_positive_momentum || momentum === 'up';
    ruleResults.push({
      label: `Momentum ${entryRules.require_positive_momentum ? 'UP (Required)' : '(Optional)'}`,
      passed: momentumCheck,
      value: `${momentum || 'neutral'} ${!momentumCheck ? `(required: up)` : ''}`
    });

    // Rule 4: Signal Actionability
    const actionableCheck = signal?.is_actionable !== false;
    ruleResults.push({
      label: 'Signal Actionable',
      passed: actionableCheck,
      value: signal?.is_actionable ? 'Yes' : 'No'
    });

    const matched = ruleResults.every((r) => r.passed);

    return { model, ruleResults, matched };
  });
};

// ─────────────────────────────────────────────────────────────────────────────

const Dashboard = () => {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState('all');
  const [volatilitySpikes, setVolatilitySpikes] = useState([]);
  const [tradingMode, setTradingMode] = useState('paper');
  const [autoStrategyEnabled, setAutoStrategyEnabled] = useState(true);
  const [autoStrategyLoading, setAutoStrategyLoading] = useState(false);
  const [autoTradePositions, setAutoTradePositions] = useState({});
  // Mirror of autoTradePositions as a ref so closures always read the latest value
  // without causing the auto-trade useEffect to restart on every position update.
  const autoTradePositionsRef = useRef({});
  const [autoStrategyStats, setAutoStrategyStats] = useState({
    totalExecuted: 0,
    totalExited: 0,
    activePositions: 0,
    lastExecutionTime: null,
    lastExitTime: null,
    executionStatus: 'idle', // idle, executing, exiting
    recentActivity: [],
    evaluatedGames: [], // Track all evaluations for debugging
    showDebug: false, // Toggle debug view
    startTime: null, // When auto-strategy was enabled
    elapsedSeconds: 0, // How long it's been running
    executionCycles: [], // Track every execution cycle with timestamp
  });

  // Track elapsed time while auto-strategy is active
  useEffect(() => {
    if (!autoStrategyEnabled) return;

    // Set start time on first enable
    if (!autoStrategyStats.startTime) {
      setAutoStrategyStats(prev => ({
        ...prev,
        startTime: Date.now()
      }));
    }

    // Update elapsed time every second
    const timer = setInterval(() => {
      setAutoStrategyStats(prev => {
        if (!prev.startTime) return prev;
        const elapsed = Math.floor((Date.now() - prev.startTime) / 1000);
        return { ...prev, elapsedSeconds: elapsed };
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [autoStrategyEnabled, autoStrategyStats.startTime]);

  const { games: rawGames, loading, lastUpdate, refresh } = useRealtimeGames({ autoFetch: true, pollInterval: 30000 });
  const games = useMemo(() => Array.isArray(rawGames) ? rawGames : [], [rawGames]);

  // Keep refs in sync with latest games/loading so the auto-trade effect
  // can always read fresh data without restarting on every poll.
  const gamesRef   = useRef(games);
  const loadingRef = useRef(loading);
  useEffect(() => { gamesRef.current   = games;   }, [games]);
  useEffect(() => { loadingRef.current = loading; }, [loading]);

  useEffect(() => {
    const loadTradingMode = async () => {
      try {
        const settings = await getSettings();
        setTradingMode(settings.kalshi?.trading_mode || 'paper');
      } catch (e) {
        console.error('Failed to load trading mode:', e);
      }
    };
    loadTradingMode();
  }, []);

  // ⚠️ CRITICAL: Load open trades from backend on mount to recover from page refresh
  // This ensures time-based exits work correctly even after page refresh
  useEffect(() => {
    const loadOpenTrades = async () => {
      try {
        console.log('[DASHBOARD] 🔄 Loading open trades from backend...');
        const { fetchTrades } = await import('../services/tradeService');
        const allTrades = await fetchTrades({ status: 'open' });
        
        if (allTrades && allTrades.length > 0) {
          console.log(`[DASHBOARD] ✅ Loaded ${allTrades.length} trades from backend`);
          
          // Rebuild autoTradePositions from DB - ONLY include truly open trades
          const recoveredPositions = {};
          for (const trade of allTrades) {
            // ⚠️ CRITICAL: Only include trades that are TRULY OPEN (no closed_at, no close_date)
            const hasClosed_at = trade.closed_at !== null && trade.closed_at !== undefined && trade.closed_at !== '';
            const hasClose_date = trade.close_date !== null && trade.close_date !== undefined && trade.close_date !== '';
            
            if (hasClosed_at || hasClose_date) {
              console.log(`[DASHBOARD] ⏭️ SKIPPING closed trade: ${trade.id} (closed_at: ${trade.closed_at}, close_date: ${trade.close_date})`);
              continue; // Skip closed trades!
            }
            
            if (trade.game_id) {
              const serverTimestamp = trade.timestamp ? new Date(trade.timestamp).getTime() : Date.now();
              
              // ✅ FIX: Resolve model_id and exitRules from the strategy name stored in DB.
              // Previously both were null, causing checkExits to skip recovered trades entirely
              // (both `if (!exitRules) continue` and `if (!model) continue` fired → stop-loss dead).
              const strategyName = trade.strategy || '';
              const resolvedModel = STRATEGIES.find(s =>
                s.display_name === strategyName ||
                s.model_id === strategyName ||
                strategyName.toLowerCase().includes(s.display_name.toLowerCase().split(' ')[2] || s.model_id)
              ) || STRATEGIES.find(s => s.enabled !== false); // fallback: first enabled model (Model A)

              recoveredPositions[trade.game_id] = {
                tradeId: trade.id,
                tradeId_db: trade.id,
                model_id: resolvedModel?.model_id || 'model_a_disciplined',
                model_name: strategyName || resolvedModel?.display_name || 'Model A - Disciplined Edge Trader',
                side: trade.side || 'yes',
                entryPrice: trade.entry_price,
                fairPrice: trade.entry_price,
                createdAt: serverTimestamp,
                createdAt_server: trade.timestamp,
                exitRules: resolvedModel?.exit_rules || {
                  // Hard-coded safe defaults if model lookup fails
                  stop_loss_pct: 0.10,
                  profit_target_pct: 0.15,
                  time_based_exit_seconds: 600,
                  edge_compression_exit_threshold: 0.02,
                },
              };
              console.log(`[DASHBOARD] 📍 Recovered OPEN position: ${trade.game_id} opened ${new Date(serverTimestamp).toLocaleTimeString()}`);
            }
          }
          
          if (Object.keys(recoveredPositions).length > 0) {
            autoTradePositionsRef.current = recoveredPositions;
            setAutoTradePositions(recoveredPositions);
            
            // ⚠️ Mark these as recovered so we skip their first exit check
            Object.keys(recoveredPositions).forEach(gameId => {
              recoveredTradesRef.current.add(gameId);
            });
            
            console.log(`[DASHBOARD] ✅ Recovered ${Object.keys(recoveredPositions).length} OPEN positions from database`);
          } else {
            console.log(`[DASHBOARD] ℹ️ No truly open trades found (all ${allTrades.length} trades were closed)`);
          }
        }
      } catch (e) {
        console.error('[DASHBOARD] ⚠️ Failed to load open trades:', e);
      }
    };
    
    loadOpenTrades();
  }, []);

  // Execution cycle tracking to prevent duplicate trades in same cycle
  const executionCycleRef = useRef({ cycle: 0, executedGames: new Set() });
  // Track recently closed games to prevent rapid re-entry (cooldown: 2 minutes)
  const recentlyClosedRef = useRef(new Map()); // gameId -> timestamp of close
  const RE_ENTRY_COOLDOWN_MS = 120000; // 2 minutes
  // Guards: prevent concurrent runs of executeTrades / checkExits
  const isExecutingRef = useRef(false);
  const isExitingRef   = useRef(false);
  // ⚠️ Track trades recovered from DB so we can skip their first exit check
  const recoveredTradesRef = useRef(new Set());
  // ✅ FIX: Track the worst (most negative) pnlPercent seen during the 60s grace window
  // per game. If stop-loss was breached during the grace period, we exit at exactly 60s
  // even if the price has since recovered — preventing a breach from going undetected.
  // Map: gameId -> { worstPnl: number, breachedDuringGrace: boolean }
  const newlyPlacedRef = useRef(new Set()); // trades placed in last 20s — non-stop-loss exits skip them

  // Diagnostic: Log games structure on first load
  useEffect(() => {
    if (games.length > 0 && autoStrategyEnabled) {
      console.log('📊 GAMES DATA LOADED:');
      console.log(`  Total Games: ${games.length}`);
      const sampleGame = games[0];
      console.log('  Sample Game Structure:', sampleGame);
      console.log('  Game ID:', sampleGame.game?.id);
      console.log('  Edge:', sampleGame.edge_decimal || sampleGame.edge / 100 || 0);
      console.log('  Signal:', sampleGame.signal);
      console.log('  Intelligence:', sampleGame.intelligence);
      console.log('\n  *** ALL Available Properties ***');
      console.log(Object.keys(sampleGame).sort());
    }
  }, [games, autoStrategyEnabled]);

  // Auto-strategy execution loop
  useEffect(() => {
    if (!autoStrategyEnabled) return;
    // Wait until we have games before starting intervals
    const waitForGames = setInterval(() => {
      if (!loadingRef.current && gamesRef.current.length > 0) {
        clearInterval(waitForGames);
        startIntervals();
      }
    }, 500);

    let executionInterval;
    let exitInterval;

    const executeTrades = async () => {
      // Prevent concurrent runs — if already executing, skip this call entirely
      if (isExecutingRef.current) {
        console.log('[AUTO-TRADE] ⚠️ Skipping: previous execution still in progress');
        return;
      }
      isExecutingRef.current = true;
      try {
        // Refresh game data before execution
        console.log('[AUTO-TRADE] 🔄 Refreshing game data...');
        await refresh();

        // Update status
        setAutoStrategyStats(prev => ({ ...prev, executionStatus: 'executing' }));

        // Start new execution cycle
        const currentCycle = Date.now();
        executionCycleRef.current.cycle = currentCycle;
        executionCycleRef.current.executedGames.clear();

        // Track this cycle execution
        const cycleTimestamp = new Date().toLocaleTimeString();
        setAutoStrategyStats(prev => ({
          ...prev,
          executionCycles: [
            {
              time: cycleTimestamp,
              timestamp: Date.now(),
              status: 'running'
            },
            ...prev.executionCycles.slice(0, 59) // Keep last 60 cycles (1 hour)
          ]
        }));

        // Filter: Only process games that haven't been traded yet (persistent positions)
        // ✅ FIX: Check both game.id and raw event_ticker to avoid duplicate trades
        const untradedGames = gamesRef.current.filter((item) => {
          const id = item.game.id;
          const eventTicker = item.raw?.event_ticker;
          return !autoTradePositionsRef.current[id] &&
                 !(eventTicker && autoTradePositionsRef.current[eventTicker]);
        });
        const cycleId = currentCycle.toString().slice(-5);
        console.log(`[CYCLE-${cycleId}] CYCLE START | Total Games: ${gamesRef.current.length} | Untraded: ${untradedGames.length} | Active Positions: ${Object.keys(autoTradePositionsRef.current).length}`);

        let cycle_stats = { evaluated: 0, matched: 0, executed: 0, failed: 0 };

        for (const item of untradedGames) {
          const gameId = item.game.id;
          const cycleId = currentCycle.toString().slice(-5);

          try {
            // === DUPLICATE PREVENTION: Check if already executed in this cycle ===
            if (executionCycleRef.current.executedGames.has(gameId)) {
              console.log(`[CYCLE-${cycleId}] SKIPPED ${gameId}: Already executed in this cycle`);
              continue;
            }

            // === DUPLICATE PREVENTION: Check if persistent position exists (use ref for latest value) ===
            if (autoTradePositionsRef.current[gameId]) {
              console.log(`[CYCLE-${cycleId}] SKIPPED ${gameId}: Active position already exists`);
              continue;
            }

            // Evaluate strategy rules against this game's signal
            let signal = item.signal;
            
            // Fallback: If signal is missing, compute it from edge
            if (!signal || !signal.signal_type) {
              const edge = item.edge_decimal ?? (item.edge / 100) ?? 0;
              signal = {
                signal_type: edge >= 0.05 ? 'STRONG_BUY' : edge >= 0.03 ? 'BUY' : edge <= -0.05 ? 'STRONG_SELL' : edge <= -0.03 ? 'SELL' : 'HOLD',
                signal_score: Math.abs(edge) * 100,
                risk_tier: 'low',
                is_actionable: Math.abs(edge) >= 0.03,
                edge: edge,
              };
            }
            
            const isClutch = item.is_clutch || false;
            const edge = signal.edge ?? item.edge_decimal ?? (item.edge / 100) ?? 0;
            const intelligence = item.intelligence || {};
            
            cycle_stats.evaluated++;
            console.log(`[CYCLE-${cycleId}] Evaluating Game: ${gameId}`);
            console.log(`  Edge: ${(edge * 100).toFixed(2)}% | Signal Score: ${Math.round(signal?.signal_score || 0)} | Clutch: ${isClutch}`);
            
            const evaluations = evaluateStrategies(signal, isClutch, intelligence.momentum);
            
            // Show detailed rule results
            evaluations.forEach((evaluation) => {
              const results = evaluation.ruleResults.map(r => `${r.label}: ${r.passed ? '✓' : '✗'} (${r.value})`).join(' | ');
              const status = evaluation.matched ? '✅ MATCHED' : '❌ FAILED';
              console.log(`  ${evaluation.model.display_name}: ${status} | ${results}`);
            });
            
            // Track this game's evaluation for debugging
            setAutoStrategyStats(prev => ({
              ...prev,
              evaluatedGames: [
                {
                  gameId,
                  gameName: `${teamName(item.game.awayTeam || item.game.away_team)} @ ${teamName(item.game.homeTeam || item.game.home_team)}`,

                  timestamp: new Date().toLocaleTimeString(),
                  signal: {
                    edge: (edge * 100).toFixed(2),
                    score: Math.round(signal?.signal_score || 0),
                    type: signal?.signal_type,
                    momentum: intelligence.momentum || 'neutral',
                  },
                  evaluations: evaluations.map(e => ({
                    modelName: e.model.display_name,
                    matched: e.matched,
                    rules: e.ruleResults.map(r => ({
                      label: r.label,
                      passed: r.passed,
                      value: r.value,
                    }))
                  }))
                },
                ...prev.evaluatedGames.slice(0, 9)
              ]
            }));
            
            // Find the first matched model (Model A or Model B)
            const matchedEval = evaluations.find((e) => e.matched &&
              (e.model.model_id === 'model_a_disciplined' || e.model.model_id === 'model_b_high_frequency'));
            if (!matchedEval) {
              console.log(`[CYCLE-${cycleId}] ❌ No Model A/B match for ${gameId}`);
              continue;
            }
            
            // ── VALIDATION: Max 10 open trades PER MODEL ──────────────────
            const MAX_OPEN_TRADES = 10;
            const matchedModelId = matchedEval.model.model_id;
            const currentOpenForModel = Object.values(autoTradePositionsRef.current)
              .filter(p => p.model_id === matchedModelId).length;
            if (currentOpenForModel >= MAX_OPEN_TRADES) {
              console.warn(`[CYCLE-${cycleId}] 🛑 MAX OPEN TRADES (${MAX_OPEN_TRADES}) for ${matchedModelId} REACHED — skipping ${gameId}`);
              continue; // Skip this game but keep checking others
            }
            
            cycle_stats.matched++;

            const matchedModel = matchedEval.model;
            const game = item.game;
            const marketProb = item.market ?? item.market_price / 100 ?? 0.5;
            const fairProb = item.fair ?? item.fair_price / 100 ?? 0.5;
            
            const tradeId = `auto-${currentCycle}-${Math.random().toString(36).substr(2, 9)}`;
            
            // Determine long/short based on edge
            const isLong = edge > 0;
            const tradeSide = isLong ? 'yes' : 'no';
            const tradeDirection = 'buy';
            // Always store the raw YES market price as entry_price (consistent convention).
            // Display/P&L code flips both entry and current prices for NO-side trades.
            
            console.log(`[CYCLE-${cycleId}] ✅ EXECUTING: ${matchedModel.display_name} for ${gameId}`);
            console.log(`  Position: ${isLong ? 'LONG' : 'SHORT'} | Entry: ${(marketProb * 100).toFixed(2)}¢ YES / ${((1 - marketProb) * 100).toFixed(2)}¢ NO | Fair: ${(fairProb * 100).toFixed(2)}%`);
            
            try {
              // Use same format as GameDetail.jsx - this is the proven working format
              const tradePayload = {
                id: tradeId,
                game_id: gameId,
                game_title: `${teamName(game.awayTeam || game.away_team)} @ ${teamName(game.homeTeam || game.home_team)}`,

                league: item.league || 'Basketball',
                market_id: game.market_id || gameId,
                market_name: game.market_name || 'Home Team',
                side: tradeSide,
                direction: tradeDirection,
                quantity: 10,
                entry_price: marketProb,   // raw YES market price (consistent convention)
                current_price: marketProb,
                order_type: 'market',
                limit_price: null,
                type: 'auto-edge',
                strategy: matchedModel.display_name,
                signal_type: signal?.signal_type,
                edge: edge,
                status: 'open',
                timestamp: new Date().toISOString(),
                pnl: 0,
              };
              
              console.log(`[CYCLE-${cycleId}] 🚀 Calling placeTrade with:`, tradePayload);
              
              // Use the placeTrade service like GameDetail.jsx does
              const trade = await placeTrade(tradePayload);
              
              if (!trade) {
                console.warn(`[CYCLE-${cycleId}] ⚠️ Trade returned null/undefined:`, trade);
              }
              
              console.log(`[CYCLE-${cycleId}] ✅ Trade response:`, trade);
              
              // === Mark as executed in this cycle to prevent duplicate ===
              executionCycleRef.current.executedGames.add(gameId);
              
              // Track position with model info — update ref immediately (synchronous)
              // so subsequent iterations in this same cycle see the position right away.
              // ⚠️ CRITICAL: Use server timestamp (trade.timestamp) not browser Date.now()
              // This ensures time-based exits work correctly even after page refresh
              const serverTimestamp = trade.timestamp ? new Date(trade.timestamp).getTime() : Date.now();
              const newPosition = {
                tradeId,
                tradeId_db: trade.id,
                model_id: matchedModel.model_id,
                model_name: matchedModel.display_name,
                side: tradeSide,              // needed for side-adjusted P&L checks
                entryPrice: marketProb,        // raw YES price (flip in calculations for NO)
                fairPrice: fairProb,
                createdAt: serverTimestamp,
                createdAt_server: trade.timestamp,
                exitRules: matchedModel.exit_rules,
              };
              autoTradePositionsRef.current = { ...autoTradePositionsRef.current, [gameId]: newPosition };
              setAutoTradePositions({ ...autoTradePositionsRef.current });
              // ✅ FIX: Mark newly placed trade for 20s full-skip, then track worst pnl
              // for the remainder of the 60s grace window.
              newlyPlacedRef.current.add(gameId);
              setTimeout(() => newlyPlacedRef.current.delete(gameId), 20000); // 20s skip for non-stop-loss exits
              console.log(`[CYCLE-${cycleId}] 📍 Position tracked with server timestamp: ${new Date(serverTimestamp).toLocaleTimeString()}`);
              
              // Update stats
              setAutoStrategyStats(prev => ({
                ...prev,
                totalExecuted: prev.totalExecuted + 1,
                activePositions: prev.activePositions + 1,
                lastExecutionTime: new Date(),
                recentActivity: [
                  {
                    type: 'entry',
                    model: matchedModel.display_name,
                    game: `${teamName(game.awayTeam || game.away_team)} @ ${teamName(game.homeTeam || game.home_team)}`,
                    edge: `${(edge * 100).toFixed(2)}%`,
                    time: new Date().toLocaleTimeString(),
                  },
                  ...prev.recentActivity.slice(0, 4)
                ]
              }));
              
              console.log(`[CYCLE-${cycleId}] Position tracked for ${gameId}`);
              cycle_stats.executed++;
            } catch (err) {
              console.error(`[CYCLE-${cycleId}] ❌ Trade execution FAILED for ${gameId}`);
              console.error(`  Error Message: ${err.message}`);
              console.error(`  Full Error:`, err);
              console.error(`  Stack:`, err.stack);
              cycle_stats.failed++;
              
              // Show error in activity feed
              setAutoStrategyStats(prev => ({
                ...prev,
                recentActivity: [
                  {
                    type: 'error',
                    model: matchedModel?.display_name || 'Unknown',
                    game: `${teamName(item.game?.awayTeam || item.game?.away_team)} @ ${teamName(item.game?.homeTeam || item.game?.home_team)}`,

                    error: err.message.substring(0, 60),
                    time: new Date().toLocaleTimeString(),
                  },
                  ...prev.recentActivity.slice(0, 4)
                ]
              }));
            }
          } catch (err) {
            console.error(`Error evaluating strategies for game:`, err);
          }
        }
        
        console.log(`[CYCLE-${cycleId}] CYCLE SUMMARY:`);
        console.log(`  ✓ Evaluated: ${cycle_stats.evaluated} | ✓ Matched: ${cycle_stats.matched} | ✓ Executed: ${cycle_stats.executed} | ✗ Failed: ${cycle_stats.failed}`);
        
        setAutoStrategyStats(prev => ({ ...prev, executionStatus: 'idle' }));
      } catch (err) {
        console.error('Auto-strategy execution error:', err);
        setAutoStrategyStats(prev => ({ ...prev, executionStatus: 'idle' }));
      } finally {
        isExecutingRef.current = false;
      }
    };

    // Check for exits - Exit rule evaluation for all open positions (HIGHEST PRIORITY)
    const checkExits = async () => {
      // Prevent concurrent runs — if already exiting, skip this call
      if (isExitingRef.current) {
        console.log('[AUTO-EXIT] ⚠️ Skipping: previous exit check still in progress');
        return;
      }
      isExitingRef.current = true;
      try {
        setAutoStrategyStats(prev => ({ ...prev, executionStatus: 'exiting' }));

        const openPositions = Object.entries(autoTradePositionsRef.current);
        if (openPositions.length === 0) {
          console.log('[AUTO-EXIT] ℹ️ No open positions to check');
          return;
        }

        console.log(`[AUTO-EXIT] 🔍 Checking ${openPositions.length} open position(s) for exit conditions...`);

        for (const [gameId, position] of openPositions) {
          // newlyPlacedRef marks trades placed in the last 20s.
          // Stop-loss ALWAYS fires immediately regardless of this flag — no grace for stop-loss.
          // Only non-stop-loss conditions (edge compression, time-based) respect this skip.
          const isNewlyPlaced = newlyPlacedRef.current.has(gameId);

          // ✅ FIX: Grace period only skips if we have no live game price yet.
          // If gamesRef has fresh data for this game, evaluate immediately so trades
          // that were already past stop-loss before the page loaded are closed promptly.
          if (recoveredTradesRef.current.has(gameId)) {
            const freshGameItem = gamesRef.current.find(g =>
              g.game.id === gameId ||
              g.game.event_ticker === gameId ||
              g.raw?.event_ticker === gameId ||
              gameId.startsWith(g.game.id + '-') ||
              (g.raw?.event_ticker && gameId.startsWith(g.raw.event_ticker))
            );
            const hasFreshPrice = freshGameItem &&
              (freshGameItem.yes_bid != null || freshGameItem.yes_ask != null || freshGameItem.last_price != null);
            if (!hasFreshPrice) {
              console.log(`[AUTO-EXIT] ⏭️ SKIP (just recovered, no live price yet): ${gameId}`);
              recoveredTradesRef.current.delete(gameId);
              continue;
            }
            // Live price available — evaluate immediately, remove from skip set
            console.log(`[AUTO-EXIT] ✅ Recovered trade has live price, evaluating immediately: ${gameId}`);
            recoveredTradesRef.current.delete(gameId);
          }
          
          // Find current game data
          // ✅ FIX: Fuzzy match — trades store event_ticker (e.g. KXNBAGAME-26MAR03OKCCHI)
          // but the games list is keyed by series_ticker (e.g. KXNBAGAME) or event_ticker.
          // Try all possible ID shapes so we never miss a match.
          const gameItem = gamesRef.current.find(g =>
            g.game.id === gameId ||
            g.game.event_ticker === gameId ||
            g.game.series_ticker === gameId ||
            g.raw?.event_ticker === gameId ||
            g.raw?.series_ticker === gameId ||
            gameId.startsWith(g.game.id + '-') ||
            (g.raw?.event_ticker && gameId.startsWith(g.raw.event_ticker)) ||
            (g.raw?.series_ticker && gameId.startsWith(g.raw.series_ticker))
          );
          if (!gameItem) {
            console.log(`[AUTO-EXIT] ⚠️ Game data not found for ${gameId}`);
            continue;
          }

          // === Find the model for this position (must come BEFORE exitRules) ===
          // ✅ FIX: Fall back to first enabled model if model_id is null (recovered trades).
          const model = STRATEGIES.find(s => s.model_id === position.model_id)
            || STRATEGIES.find(s => s.enabled !== false);
          // Never skip due to missing model — we always have a fallback

          // ✅ FIX: Never skip — fall back through position.exitRules → model.exit_rules → hard defaults.
          // Previously exitRules was null on recovery → 'if (!exitRules) continue' silently killed stop-loss.
          const exitRules = position.exitRules ||
            model?.exit_rules || {
              stop_loss_pct: 0.10,
              profit_target_pct: 0.15,
              time_based_exit_seconds: 600,
              edge_compression_exit_threshold: 0.02,
            };
          // exitRules and model are now always defined

          const yesPrice  = gameItem.market ?? gameItem.market_price / 100 ?? 0.5;
          // For P&L use side-adjusted effective prices: flip both entry+current for NO trades
          const effEntry   = position.side === 'no' ? 1 - position.entryPrice : position.entryPrice;
          const currentPrice = position.side === 'no' ? 1 - yesPrice : yesPrice;
          const fairPrice = gameItem.fair ?? gameItem.fair_price / 100 ?? 0.5;
          
          // ⚠️ CRITICAL: Use server timestamp, not browser time!
          // createdAt is set to server's trade.timestamp (as milliseconds)
          const heldTime = Date.now() - position.createdAt;
          const heldTimeSeconds = heldTime / 1000;
          const heldTimeMinutes = heldTimeSeconds / 60;
          
          console.log(`[EXIT-CHECK] ${gameId}: Held ${heldTimeMinutes.toFixed(1)}min, Server TS: ${new Date(position.createdAt).toLocaleTimeString()}, Now: ${new Date(Date.now()).toLocaleTimeString()}`);
          
          // Calculate P&L using side-adjusted effective prices
          const pnl = currentPrice - effEntry;
          const pnlPercent = effEntry > 0 ? pnl / effEntry : 0;
          
          // Current edge dynamics
          const currentEdge = gameItem.edge_decimal ?? (gameItem.edge / 100) ?? 0;
          const edgeDeviation = Math.abs(currentEdge) - Math.abs(position.edge || 0);
          
          // Professional exit reason tracking with priority system
          let exitReason = null;
          let exitPriority = 0;
          let exitType = 'normal';
          
          // ========== PRIORITY 5: HARD STOPS (NO TIME GATE - Adverse Move Protection) ==========
          if (model.adverse_move_protection?.enable_hard_stop) {
            if (pnlPercent <= -model.adverse_move_protection.hard_stop_pct) {
              exitReason = `🛑 HARD STOP: Adverse move ${(pnlPercent * 100).toFixed(2)}% > ${(model.adverse_move_protection.hard_stop_pct * 100).toFixed(1)}%`;
              exitPriority = 5;
              exitType = 'hard_stop';
            }
          }
          
          // ========== PRIORITY 4: STOP LOSS — FIRES IMMEDIATELY, NO GRACE, NO EXCEPTIONS ==========
          // Stop-loss is a hard capital protection rule. It fires the instant pnlPercent
          // reaches -stop_loss_pct regardless of how old the trade is. No time gate,
          // no grace window, no delay. This is the only way to guarantee the loss never
          // exceeds the threshold in any scenario.
          if (pnlPercent <= -exitRules.stop_loss_pct && exitPriority < 4) {
            exitReason = `❌ STOP LOSS: P&L ${(pnlPercent * 100).toFixed(2)}% ≤ -${(exitRules.stop_loss_pct * 100).toFixed(1)}%`;
            exitPriority = 4;
            exitType = 'stop_loss';
          }
          
          // ========== PRIORITY 3: PROFIT TARGET HIT (NO TIME GATE - Lock in Gains IMMEDIATELY) ==========
          if (pnlPercent >= exitRules.profit_target_pct && exitPriority < 3) {
            exitReason = `✅ PROFIT TARGET: P&L ${(pnlPercent * 100).toFixed(2)}% ≥ +${(exitRules.profit_target_pct * 100).toFixed(1)}%`;
            exitPriority = 3;
            exitType = 'profit_target';
          }
          
          // ⚠️ FOR OTHER CONDITIONS (edge compression, time-based): Apply minimum time gate.
          // Also skip for newly placed trades (<20s) — these non-stop-loss exits need settled prices.
          if (exitPriority < 3) {
            if (isNewlyPlaced) {
              console.log(`[EXIT-GATE] ⏭️ ${gameId}: Non-stop-loss exit skipped (newly placed <20s)`);
              continue;
            }
            const minTimeSeconds = exitRules.time_based_exit_seconds || 600;
            if (heldTimeSeconds < minTimeSeconds) {
              console.log(`[EXIT-GATE] ⏱️ ${gameId}: BLOCKED - Held ${heldTimeMinutes.toFixed(1)}min / ${(minTimeSeconds / 60).toFixed(0)}min required. P&L: ${(pnlPercent * 100).toFixed(2)}% (will retry in ${(minTimeSeconds - heldTimeSeconds).toFixed(0)}s)`);
              continue;
            }
          }
          
          // ========== PRIORITY 2: EDGE COMPRESSION (MEDIUM) - Only if P&L not hit ==========
          if (Math.abs(currentEdge) <= exitRules.edge_compression_exit_threshold && exitPriority < 2) {
            exitReason = `📉 EDGE COMPRESSED: ${(Math.abs(currentEdge) * 100).toFixed(2)}% ≤ ${(exitRules.edge_compression_exit_threshold * 100).toFixed(2)}%`;
            exitPriority = 2;
            exitType = 'edge_compression';
          }
          
          // ========== PRIORITY 0.5: TRAILING STOP (VERY LOW - Momentum Protection) ==========
          if (exitRules.trailing_stop_pct && pnlPercent > 0 && exitPriority < 0.5) {
            if (pnlPercent < exitRules.trailing_stop_pct) {
              exitReason = `🔔 TRAILING STOP: Retraced from peak by ${((exitRules.trailing_stop_pct - pnlPercent) * 100).toFixed(2)}%`;
              exitPriority = 0.5;
              exitType = 'trailing_stop';
            }
          }
          
          // ========== CRITICAL SAFETY CHECK: Verify exit reason is VALID ==========
          // Never exit without a legitimate reason!
          const exitConditionsMet = {
            hardStop: exitReason && exitReason.includes('HARD STOP'),
            stopLoss: exitReason && exitReason.includes('STOP LOSS'),
            profitTarget: exitReason && exitReason.includes('PROFIT TARGET'),
            edgeCompression: exitReason && exitReason.includes('EDGE COMPRESSED'),
            trailingStop: exitReason && exitReason.includes('TRAILING STOP'),
          };
          
          const hasValidReason = Object.values(exitConditionsMet).some(x => x === true);
          
          // ========== Execute exit if condition met ==========
          if (exitReason && exitPriority > 0 && hasValidReason) {
            try {
              console.log(`[EXIT-${exitType.toUpperCase()}] ⏳ Processing: ${position.model_name} | ${gameId}`);
              console.log(`  └─ Reason: ${exitReason}`);
              console.log(`  └─ Model Exit Rule: ${model.display_name}`);
              
              await closeTrade(position.tradeId, currentPrice, exitReason);
              
              // Remove from ref immediately so re-entry logic sees it gone at once.
              const updatedPositions = { ...autoTradePositionsRef.current };
              delete updatedPositions[gameId];
              autoTradePositionsRef.current = updatedPositions;
              setAutoTradePositions({ ...updatedPositions });
              
              console.log(`[EXIT-${exitType.toUpperCase()}] ✅ Game ${gameId} closed successfully`);
              
              // Update stats
              setAutoStrategyStats(prev => ({
                ...prev,
                totalExited: prev.totalExited + 1,
                activePositions: Math.max(0, prev.activePositions - 1),
                lastExitTime: new Date(),
                recentActivity: [
                  {
                    type: 'exit',
                    model: position.model_name,
                    game: gameId.substring(0, 20),
                    pnl: `${(pnlPercent * 100).toFixed(2)}%`,
                    exitType: exitType,
                    time: new Date().toLocaleTimeString(),
                  },
                  ...prev.recentActivity.slice(0, 4)
                ]
              }));
              
              console.log(`[EXIT-${exitType.toUpperCase()}] ✅ SUCCESS: Trade closed | P&L: ${(pnlPercent * 100).toFixed(2)}% | Type: ${exitType}`);
            } catch (err) {
              console.error(`[EXIT-ERROR] ❌ Failed to close ${position.tradeId}: ${err.message}`);
            }
          }
        }
        
        setAutoStrategyStats(prev => ({ ...prev, executionStatus: 'idle' }));
      } catch (err) {
        console.error('[EXIT-CYCLE] Critical error during exit evaluation:', err);
        setAutoStrategyStats(prev => ({ ...prev, executionStatus: 'idle' }));
      } finally {
        isExitingRef.current = false;
      }
    };

    const startIntervals = () => {
      // === Execute trades every 60 seconds ===
      (async () => { await executeTrades(); })(); // Execute immediately on enable
      executionInterval = setInterval(async () => {
        await executeTrades();
      }, 60000);

      // === Check exits every 10 seconds ===
      (async () => { await checkExits(); })();
      exitInterval = setInterval(async () => {
        await checkExits();
      }, 10000);
    }; // end startIntervals

    return () => {
      clearInterval(waitForGames);
      clearInterval(executionInterval);
      clearInterval(exitInterval);
    };
  // games and loading are intentionally excluded — they are read via refs to
  // prevent the effect from restarting (and re-firing executeTrades) on every
  // 30-second poll update.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStrategyEnabled]);

  const getSignalColor = (signalType) => {
    if (!signalType) return 'bg-gray-700 text-gray-300';
    switch (signalType) {
      case 'STRONG_BUY':        return 'bg-green-500 text-white';
      case 'BUY':               return 'bg-green-600/30 text-green-400 border border-green-600';
      case 'SELL':              return 'bg-red-600/30 text-red-400 border border-red-600';
      case 'STRONG_SELL':       return 'bg-red-500 text-white';
      case 'SELL_INTO_STRENGTH':return 'bg-yellow-500/30 text-yellow-400 border border-yellow-500';
      case 'HOLD':              return 'bg-gray-700/50 text-gray-400';
      default:                  return 'bg-gray-700 text-gray-300';
    }
  };

  // Safely extract display name from either a string or a Team object {id, name, abbreviation, logo_url}
  const teamName = (t) => {
    if (!t) return '';
    if (typeof t === 'string') return t;
    return t.abbreviation || t.name || '';
  };

  // Format elapsed time (seconds → HH:MM:SS)
  const formatElapsedTime = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  const getEdgeColor = (edge) => {
    if (edge >= 0.05)  return 'text-green-400';
    if (edge >= 0.03)  return 'text-green-500';
    if (edge <= -0.05) return 'text-red-400';
    if (edge <= 0)     return 'text-red-500';
    return 'text-gray-400';
  };

  const getRiskTierColor = (tier) => {
    switch (tier) {
      case 'low':    return 'text-green-400';
      case 'medium': return 'text-yellow-400';
      case 'high':   return 'text-red-400';
      default:       return 'text-gray-400';
    }
  };

  const getMomentumIcon = (momentum) => {
    switch (momentum) {
      case 'up':   return <TrendingUp   className="w-3 h-3 text-green-500" />;
      case 'down': return <TrendingDown className="w-3 h-3 text-red-500"   />;
      default:     return <Minus        className="w-3 h-3 text-gray-500"  />;
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'live':      return <Badge className="bg-green-500 text-white text-xs animate-pulse">LIVE</Badge>;
      case 'scheduled': return <Badge variant="outline" className="text-xs">Scheduled</Badge>;
      case 'final':     return <Badge variant="secondary" className="text-xs">Final</Badge>;
      case 'halftime':  return <Badge className="bg-yellow-600 text-white text-xs">HT</Badge>;
      default:          return <Badge variant="outline" className="text-xs">{status}</Badge>;
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground transition-colors duration-300">
      {/* Page transition loader — shows on mount & back/forward navigation */}
      <PageLoader />

      {/* Quick Status Bar */}
      <div className="border-b border-border bg-card/30">
        <div className="max-w-[1800px] mx-auto px-4 py-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[140px] h-8 text-xs bg-transparent border-border">
                  <SelectValue placeholder="All Games" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Games</SelectItem>
                  <SelectItem value="live">Live</SelectItem>
                  <SelectItem value="scheduled">Scheduled</SelectItem>
                  <SelectItem value="final">Final</SelectItem>
                </SelectContent>
              </Select>
              <Badge variant="outline" className="text-xs">
                {games.filter((item) => {
                  const status = item.game?.status;
                  if (status === 'final' || status === 'closed') return false;
                  const today = new Date(); today.setHours(0, 0, 0, 0);
                  const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1);
                  if (item.game_date) { const gd = new Date(item.game_date); return gd >= today && gd < tomorrow; }
                  return true;
                }).length} today
              </Badge>
              <Badge variant={tradingMode === 'live' ? 'default' : 'secondary'} className="text-xs">
                {tradingMode === 'live' ? 'Live Mode' : 'Paper Mode'}
              </Badge>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-sm">
                <Wifi className="w-4 h-4 text-green-500" />
                <span className="text-green-500 text-xs">Live API</span>
              </div>
              
              {/* Auto-Strategy Button */}
              <Button
                size="sm"
                variant={autoStrategyEnabled ? "default" : "outline"}
                onClick={() => {
                  if (autoStrategyEnabled) {
                    // Disable: clear start time and execution cycles
                    setAutoStrategyStats(prev => ({
                      ...prev,
                      startTime: null,
                      elapsedSeconds: 0,
                      executionCycles: []
                    }));
                  }
                  setAutoStrategyEnabled(!autoStrategyEnabled);
                }}
                disabled={autoStrategyLoading}
                className={`gap-2 text-xs ${
                  autoStrategyEnabled ? 'bg-emerald-600 hover:bg-emerald-700' : ''
                }`}
              >
                {autoStrategyLoading ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : autoStrategyEnabled ? (
                  <Pause className="w-3 h-3" />
                ) : (
                  <Play className="w-3 h-3" />
                )}
                {autoStrategyEnabled ? 'Auto Strategy' : 'Start Auto'}
                <div className="flex items-center gap-1">
                  {Object.keys(autoTradePositions).length > 0 && (
                    <Badge className="bg-yellow-600 text-xs mr-1">
                      {Object.keys(autoTradePositions).length} Live
                    </Badge>
                  )}
                  {autoStrategyStats.totalExecuted > 0 && (
                    <Badge variant="secondary" className="text-xs">
                      {autoStrategyStats.totalExecuted}/{autoStrategyStats.totalExited}
                    </Badge>
                  )}
                </div>
              </Button>
              
              {lastUpdate && (
                <span className="text-xs text-muted-foreground">
                  {lastUpdate.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'America/New_York', timeZoneName: 'short' })}
                </span>
              )}
              <Button variant="ghost" size="sm" onClick={refresh} disabled={loading}>
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Auto-Strategy Status Dashboard */}
      {autoStrategyEnabled && (
        <div className="max-w-[1800px] mx-auto px-4 pt-3 pb-3">
          <div className="bg-gradient-to-r from-slate-900/50 to-slate-800/50 border border-emerald-900/30 rounded-lg p-4 space-y-3">
            {/* Status Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-emerald-500 animate-pulse" />
                  <span className="text-xs font-semibold text-emerald-400">AUTO-STRATEGY ACTIVE</span>
                </div>
                
                {/* Execution Status Indicator */}
                <div className="flex items-center gap-1 px-2 py-1 bg-slate-700/50 rounded text-xs">
                  <div className={`w-2 h-2 rounded-full ${
                    autoStrategyStats.executionStatus === 'executing' ? 'bg-blue-400 animate-pulse' :
                    autoStrategyStats.executionStatus === 'exiting' ? 'bg-orange-400 animate-pulse' :
                    'bg-green-400'
                  }`} />
                  <span className="text-gray-300 capitalize">
                    {autoStrategyStats.executionStatus === 'executing' ? 'Entering...' :
                     autoStrategyStats.executionStatus === 'exiting' ? 'Exiting...' :
                     'Monitoring'}
                  </span>
                </div>
              </div>
              
              <div className="flex items-center gap-4 text-xs text-gray-400">
                {autoStrategyStats.startTime && (
                  <>
                    <div>
                      <span className="text-gray-500">Started:</span> {new Date(autoStrategyStats.startTime).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'America/New_York', timeZoneName: 'short' })}
                    </div>
                    <div className="flex items-center gap-1 px-2 py-1 bg-slate-700/30 rounded font-mono text-cyan-400">
                      <span>⏱️</span>
                      <span>{formatElapsedTime(autoStrategyStats.elapsedSeconds)}</span>
                    </div>
                  </>
                )}
                {autoStrategyStats.lastExecutionTime && (
                  <span>Last Entry: {autoStrategyStats.lastExecutionTime.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'America/New_York', timeZoneName: 'short' })}</span>
                )}
              </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-5 gap-3">
              {/* Session Start Time */}
              <div className="bg-slate-800/50 rounded p-2 border border-purple-900/20">
                <div className="text-xs text-gray-400 uppercase tracking-wider">Session Started</div>
                <div className="text-sm font-bold text-purple-400 mt-1 font-mono">
                  {autoStrategyStats.startTime 
                    ? new Date(autoStrategyStats.startTime).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'America/New_York', timeZoneName: 'short' })
                    : '—'}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {autoStrategyStats.startTime 
                    ? new Date(autoStrategyStats.startTime).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'America/New_York' })
                    : ''}
                </div>
              </div>

              {/* Active Positions */}
              <div className="bg-slate-800/50 rounded p-2 border border-emerald-900/20">
                <div className="text-xs text-gray-400 uppercase tracking-wider">Active Positions</div>
                <div className="text-lg font-bold text-emerald-400 mt-1">
                  {Object.keys(autoTradePositions).length}
                </div>
              </div>

              {/* Total Executed */}
              <div className="bg-slate-800/50 rounded p-2 border border-blue-900/20">
                <div className="text-xs text-gray-400 uppercase tracking-wider">Total Executed</div>
                <div className="text-lg font-bold text-blue-400 mt-1">
                  {autoStrategyStats.totalExecuted}
                </div>
              </div>

              {/* Total Exited */}
              <div className="bg-slate-800/50 rounded p-2 border border-orange-900/20">
                <div className="text-xs text-gray-400 uppercase tracking-wider">Total Exited</div>
                <div className="text-lg font-bold text-orange-400 mt-1">
                  {autoStrategyStats.totalExited}
                </div>
              </div>

              {/* Win Rate */}
              <div className="bg-slate-800/50 rounded p-2 border border-cyan-900/20">
                <div className="text-xs text-gray-400 uppercase tracking-wider">Session Duration</div>
                <div className="text-lg font-bold text-cyan-400 mt-1 font-mono">
                  {formatElapsedTime(autoStrategyStats.elapsedSeconds)}
                </div>
              </div>
            </div>

            {/* Recent Activity Feed */}
            {autoStrategyStats.recentActivity.length > 0 && (
              <div className="bg-slate-900/30 rounded border border-slate-700/30 p-2">
                <div className="text-xs font-mono uppercase tracking-wider text-gray-500 mb-2">Recent Activity</div>
                <div className="space-y-1 max-h-[120px] overflow-y-auto">
                  {autoStrategyStats.recentActivity.map((activity, idx) => (
                    <div key={idx} className="text-xs font-mono text-gray-300 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {activity.type === 'entry' ? (
                          <>
                            <span className="text-emerald-400">↓ ENTRY</span>
                            <span className="text-gray-500">{activity.model}</span>
                          </>
                        ) : (
                          <>
                            <span className="text-orange-400">↑ EXIT</span>
                            <span className="text-gray-500">{activity.model}</span>
                            <span className={(activity.pnl && String(activity.pnl).includes('-')) ? 'text-red-400' : 'text-green-400'}>
                              {activity.pnl}
                            </span>
                          </>
                        )}
                      </div>
                      <span className="text-gray-600">{activity.time}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Execution Cycles Timeline */}
            {autoStrategyStats.executionCycles.length > 0 && (
              <div className="bg-slate-900/30 rounded border border-slate-700/30 p-2">
                <div className="text-xs font-mono uppercase tracking-wider text-gray-500 mb-2">
                  ⏱️ Execution Cycles (Every 60 seconds)
                </div>
                <div className="flex flex-wrap gap-1 max-h-[80px] overflow-y-auto">
                  {autoStrategyStats.executionCycles.map((cycle, idx) => (
                    <div 
                      key={idx}
                      className="px-2 py-1 rounded text-xs font-mono bg-slate-700/50 border border-slate-600/30 text-gray-300 hover:bg-slate-700 transition-colors"
                      title={`Execution #${autoStrategyStats.executionCycles.length - idx}`}
                    >
                      {cycle.time}
                    </div>
                  ))}
                </div>
                <div className="text-xs text-gray-500 mt-2">
                  Total Cycles: <span className="text-cyan-400 font-mono">{autoStrategyStats.executionCycles.length}</span>
                </div>
              </div>
            )}

            {/* Debug Toggle Button */}
            <div className="flex justify-end">
              <Button
                size="sm"
                variant="outline"
                onClick={() => setAutoStrategyStats(prev => ({ ...prev, showDebug: !prev.showDebug }))}
                className="text-xs"
              >
                {autoStrategyStats.showDebug ? '▼ Hide Debug' : '▶ Show Debug'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Detailed Strategy Evaluation Debug View */}
      {autoStrategyEnabled && autoStrategyStats.showDebug && (
        <div className="max-w-[1800px] mx-auto px-4 pt-3 pb-3">
          <div className="bg-slate-900/80 border border-red-900/50 rounded-lg p-4 space-y-3">
            <div className="text-xs font-mono uppercase tracking-wider text-red-400 mb-2">
              🔍 Strategy Evaluation Debug ({autoStrategyStats.evaluatedGames.length} games evaluated)
            </div>

            <div className="space-y-2 max-h-[500px] overflow-y-auto">
              {autoStrategyStats.evaluatedGames.map((game, gameIdx) => (
                <div
                  key={gameIdx}
                  className="bg-slate-800/50 rounded border border-slate-700/30 p-2"
                >
                  {/* Game Header */}
                  <div className="flex items-center justify-between mb-2 pb-1 border-b border-slate-700/30">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-gray-300">{game.gameName}</span>
                    </div>
                    <span className="text-xs text-gray-500">{game.timestamp}</span>
                  </div>

                  {/* Signal Data */}
                  <div className="grid grid-cols-4 gap-2 mb-2 text-xs">
                    <div className="bg-slate-900/50 rounded p-1 border border-blue-900/30">
                      <div className="text-gray-500">Edge</div>
                      <div className={(game.signal?.edge && String(game.signal.edge).includes('-')) ? 'text-red-400 font-mono' : 'text-green-400 font-mono'}>
                        {game.signal?.edge}%
                      </div>
                    </div>
                    <div className="bg-slate-900/50 rounded p-1 border border-blue-900/30">
                      <div className="text-gray-500">Signal Score</div>
                      <div className="text-yellow-400 font-mono">{game.signal.score}</div>
                    </div>
                    <div className="bg-slate-900/50 rounded p-1 border border-blue-900/30">
                      <div className="text-gray-500">Signal Type</div>
                      <div className="text-purple-400 font-mono capitalize">{game.signal.type}</div>
                    </div>
                    <div className="bg-slate-900/50 rounded p-1 border border-blue-900/30">
                      <div className="text-gray-500">Momentum</div>
                      <div className="text-orange-400 font-mono capitalize">{game.signal.momentum}</div>
                    </div>
                  </div>

                  {/* Model Evaluations */}
                  <div className="space-y-1">
                    {game.evaluations.map((evalResult, idx) => (
                      <div key={idx} className={`rounded p-1 text-xs border ${
                        evalResult.matched 
                          ? 'bg-green-900/20 border-green-800/30' 
                          : 'bg-red-900/20 border-red-800/30'
                      }`}>
                        {/* Model Name and Status */}
                        <div className="flex items-center gap-2 mb-1">
                          <span className={evalResult.matched ? 'text-green-400' : 'text-red-400'}>
                            {evalResult.matched ? '✅' : '❌'}
                          </span>
                          <span className="font-mono text-gray-300">{evalResult.modelName}</span>
                        </div>

                        {/* Rules Grid */}
                        <div className="grid grid-cols-2 gap-1 ml-4">
                          {evalResult.rules.map((rule, rIdx) => (
                            <div
                              key={rIdx}
                              className={`text-xs p-1 rounded border ${
                                rule.passed
                                  ? 'border-green-800/30 bg-green-950/30'
                                  : 'border-red-800/30 bg-red-950/30'
                              }`}
                            >
                              <div className="flex items-center gap-1">
                                <span className={rule.passed ? 'text-green-400' : 'text-red-400'}>
                                  {rule.passed ? '✓' : '✗'}
                                </span>
                                <span className="text-gray-400 text-xs">{rule.label}</span>
                              </div>
                              <div className="text-gray-500 text-xs ml-4">{rule.value}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {autoStrategyStats.evaluatedGames.length === 0 && (
              <div className="text-xs text-gray-500 text-center py-4">
                No evaluations yet. Waiting for next execution cycle...
              </div>
            )}
          </div>
        </div>
      )}

      {/* Volatility Spike Alert */}
      {volatilitySpikes.length > 0 && (
        <div className="max-w-[1800px] mx-auto px-4 pt-4">
          <div className="bg-red-900/30 border border-red-800 rounded-lg p-3 flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-red-500 animate-pulse" />
            <div>
              <span className="text-red-400 font-medium">Volatility Spike Detected: </span>
              {volatilitySpikes.map((spike, idx) => (
                <span key={idx} className="text-red-300">
                  {spike.game} ({(spike.volatility * 100).toFixed(1)}%)
                  {idx < volatilitySpikes.length - 1 && ', '}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Terminal Table */}
      <div className="max-w-[1800px] mx-auto px-4 py-4">
        <div className="bg-card/50 rounded-lg border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-xs text-muted-foreground uppercase tracking-wider border-b border-border">
                  <th className="px-3 py-3 text-left">Game</th>
                  <th className="px-3 py-3 text-center">Game Starts</th>
                  {/* <th className="px-3 py-3 text-center">Opens At</th>
                  <th className="px-3 py-3 text-center">Closes At</th> */}
                  <th className="px-3 py-3 text-center">Status</th>
                  <th className="px-3 py-3 text-center">Score</th>
                  <th className="px-3 py-3 text-center">Market</th>
                  <th className="px-3 py-3 text-center">Fair</th>
                  <th className="px-3 py-3 text-center">Edge</th>
                  <th className="px-3 py-3 text-center">Signal</th>
                  <th className="px-3 py-3 text-center">Score</th>
                  <th className="px-3 py-3 text-center">Risk</th>
                  <th className="px-3 py-3 text-center">Momentum</th>
                  <th className="px-3 py-3 text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {loading && games.length === 0 ? (
                  <tr>
                    <td colSpan={11} className="px-4 py-8 text-center text-muted-foreground">
                      <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
                      Loading...
                    </td>
                  </tr>
                ) : games.length === 0 ? (
                  <tr>
                    <td colSpan={11} className="px-4 py-8 text-center text-muted-foreground">
                      No games found
                    </td>
                  </tr>
                ) : (
                  games
                    .filter((item) => {
                      const status = item.game?.status;
                      if (status === 'final' || status === 'closed') return false;
                      if (statusFilter !== 'all' && status !== statusFilter) return false;

                      // Strict today-only filter using game_date (ISO from Kalshi expected_expiration_date)
                      const today = new Date();
                      today.setHours(0, 0, 0, 0);
                      const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1);

                      if (item.game_date) {
                        const gd = new Date(item.game_date);
                        return gd >= today && gd < tomorrow;
                      }
                      // Fallback: parse date from subtitle e.g. "(Feb 24)"
                      const subtitle = item.raw?.sub_title || item.raw?.event_subtitle || '';
                      const monthDay = subtitle.match(/([A-Za-z]+ \d+)/);
                      if (monthDay) {
                        const gd = new Date(`${monthDay[1]}, ${today.getFullYear()}`);
                        gd.setHours(0,0,0,0);
                        return gd.getTime() === today.getTime();
                      }
                      return true;
                    })
                    .sort((a, b) => {
                      // Sort by expected_expiration_date (actual game end time, NOT close_date which is far-future max-settlement)
                      const dateA = a.markets?.[0]?.expected_expiration_date ? new Date(a.markets[0].expected_expiration_date) : new Date(0);
                      const dateB = b.markets?.[0]?.expected_expiration_date ? new Date(b.markets[0].expected_expiration_date) : new Date(0);
                      return dateA.getTime() - dateB.getTime();
                    }).map((item, idx) => {
                    const game         = item.game;
                    const signal       = item.signal;
                    const marketProb   = item.market ?? item.market_price / 100 ?? 0.5;
                    const fairProb     = item.fair   ?? item.fair_price   / 100 ?? 0.5;
                    const edge         = item.edge_decimal ?? (item.edge / 100)  ?? 0;
                    const intelligence = item.intelligence || {};

                    // Extract dates from Kalshi raw market fields (ISO strings)
                    const firstMarket = item.markets?.[0] || {};
                    const openTs       = firstMarket.open_date  ? new Date(firstMarket.open_date)  : null;
                    // start time ≈ expiration - 3h for NBA
                    const isNBASeries  = /NBA/i.test(item.raw?.series_ticker || '');
                    const nbaOffset    = isNBASeries ? 3 * 60 * 60 * 1000 : 0;
                    const expirationTs = firstMarket.expected_expiration_date ? new Date(firstMarket.expected_expiration_date) : null;
                    const closeTs      = expirationTs ? new Date(expirationTs.getTime() - nbaOffset) : null;

                    // Format dates for display (always EST)
                    const formatDate = (date) => {
                      if (!date) return '—';
                      return date.toLocaleString('en-US', { 
                        month: 'short', 
                        day: 'numeric',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        timeZone: 'America/New_York',
                        timeZoneName: 'short',
                      });
                    };

                    // Get date color based on today vs past/future
                    const getDateColor = (dateObj) => {
                      if (!dateObj) return 'text-gray-400';
                      const today = new Date();
                      today.setHours(0, 0, 0, 0);
                      const compareDate = new Date(dateObj);
                      compareDate.setHours(0, 0, 0, 0);
                      
                      if (compareDate.getTime() === today.getTime()) {
                        return 'text-green-400'; // Today - light green
                      } else if (compareDate < today) {
                        return 'text-red-400'; // Past - red
                      } else {
                        return 'text-yellow-400'; // Future - yellow
                      }
                    };

                    // Extract game date + time from sub_title (e.g. "ORL at LAL (Feb 24)") + expected_expiration_date
                    const gameDateBase = item.raw?.sub_title || item.raw?.event_subtitle || item.event_subtitle || (expirationTs ? expirationTs.toLocaleDateString('en-US', { 
                      month: 'short', 
                      day: 'numeric',
                      year: 'numeric',
                      timeZone: 'America/New_York',
                    }) : '—');
                    const gameTime = closeTs ? closeTs.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'America/New_York', timeZoneName: 'short' }) : null;
                    const gameDate = gameTime ? `${gameDateBase} · ${gameTime}` : gameDateBase;

                    // Build Kalshi market URL
                    const kalshiSeriesTicker = (item.raw?.series_ticker || '').toLowerCase();
                    const kalshiSubtitleSlug = (item.raw?.sub_title || item.raw?.event_subtitle || item.raw?.event_title || '')
                      .toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
                    const kalshiEventTicker = item.raw?.event_ticker || item.ticker || game.id || '';
                    const kalshiUrl = kalshiSeriesTicker
                      ? `https://kalshi.com/markets/${kalshiSeriesTicker}/${kalshiSubtitleSlug}/${kalshiEventTicker}`
                      : null;

                    return (
                      <tr
                        key={`${game.id}-${idx}`}
                        className="hover:bg-muted/50 transition-colors cursor-pointer"
                        onClick={() => navigate(`/game/${game.id}`)}
                      >
                        {/* Game */}
                        <td className="px-3 py-2">
                          <Link to={`/game/${game.id}`} className="hover:text-blue-400" onClick={(e) => e.stopPropagation()}>
                            <div className="flex items-center gap-2">
                              <div className="font-medium text-sm">
                                {teamName(game.awayTeam || game.away_team)} @ {teamName(game.homeTeam || game.home_team)}
                              </div>
                              {item.is_clutch && <Flame className="w-3 h-3 text-orange-500" />}
                            </div>
                          </Link>
                        </td>

                        {/* Game Date */}
                        <td className="px-3 py-2 text-center">
                          <div className={`text-xs font-mono font-semibold ${getDateColor(expirationTs)}`}>
                            {gameDate}
                          </div>
                        </td>

                        {/* Opens At */}
                        {/* <td className="px-3 py-2 text-center">
                          <div className={`text-xs font-mono font-semibold ${getDateColor(openTs)}`}>
                            {formatDate(openTs)}
                          </div>
                        </td> */}

                        {/* Closes At */}
                        {/* <td className="px-3 py-2 text-center">
                          <div className={`text-xs font-mono font-semibold ${getDateColor(closeTs)}`}>
                            {formatDate(closeTs)}
                          </div>
                        </td> */}

                        {/* Status */}
                        <td className="px-3 py-2 text-center">
                          {getStatusBadge(game.status)}
                          {game.status === 'live' && (
                            <div className="text-xs text-gray-500 mt-0.5">
                              Q{game.quarter} {game.time_remaining}
                            </div>
                          )}
                        </td>

                        {/* Score */}
                        <td className="px-3 py-2 text-center">
                          <div className="font-mono">
                            <span className={game.score_differential < 0 ? 'text-green-400' : ''}>
                              {game.away_score}
                            </span>
                            <span className="text-gray-500 mx-1">-</span>
                            <span className={game.score_differential > 0 ? 'text-green-400' : ''}>
                              {game.home_score}
                            </span>
                          </div>
                        </td>

                        {/* Market Prob */}
                        <td className="px-3 py-2 text-center">
                          <div className="font-mono text-blue-400 text-sm">
                            {formatPercent(marketProb)}
                          </div>
                        </td>

                        {/* Fair Prob */}
                        <td className="px-3 py-2 text-center">
                          <div className="font-mono text-purple-400 text-sm">
                            {formatPercent(fairProb)}
                          </div>
                        </td>

                        {/* Edge */}
                        <td className="px-3 py-2 text-center">
                          <div className={`font-mono font-bold text-sm ${getEdgeColor(edge)}`}>
                            {edge >= 0 ? '+' : ''}{formatPercent(edge)}
                          </div>
                        </td>

                        {/* Signal */}
                        <td className="px-3 py-2 text-center">
                          <Badge className={`${getSignalColor(signal?.signal_type)} text-xs`}>
                            {signal?.signal_type?.replace('_', ' ') || 'N/A'}
                          </Badge>
                        </td>

                        {/* Signal Score */}
                        <td className="px-3 py-2 text-center">
                          <TooltipProvider>
                            <Tooltip>
                              <TooltipTrigger>
                                <div className="font-mono text-sm">
                                  {Math.round(signal?.signal_score || 0)}
                                </div>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p>Composite Signal Score (0-100)</p>
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        </td>

                        {/* Risk Tier */}
                        <td className="px-3 py-2 text-center">
                          <span className={`text-xs font-medium capitalize ${getRiskTierColor(signal?.risk_tier)}`}>
                            {signal?.risk_tier || 'N/A'}
                          </span>
                        </td>

                        {/* Momentum */}
                        <td className="px-3 py-2 text-center">
                          {getMomentumIcon(intelligence.momentum)}
                        </td>

                        {/* Action */}
                        <td className="px-3 py-2 text-center" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center justify-center gap-1">
                            <Link to={`/game/${game.id}`}>
                              <Button size="sm" variant="ghost" className="h-7 text-xs">
                                <Zap className="w-3 h-3 mr-1" />
                                Trade
                              </Button>
                            </Link>
                            {kalshiUrl && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 text-xs border-blue-600 text-blue-400 hover:bg-blue-600 hover:text-white px-2"
                                onClick={(e) => { e.stopPropagation(); window.open(kalshiUrl, '_new', 'noopener,noreferrer'); }}
                                title="View on Kalshi"
                              >
                                K
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;