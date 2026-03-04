import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from '../components/ui/dialog';
import {
  ArrowLeft, RefreshCw, Activity, TrendingUp, DollarSign,
  AlertTriangle, Zap, Clock, Flame, Bot, CheckCircle2, XCircle,
  ShieldAlert, Info, FileText, Loader2, Calendar,
} from 'lucide-react';
import { formatPercent, formatCurrency } from '../services/api';
import ProbabilityChart from '../components/charts/ProbabilityChart';
import EdgeChart from '../components/charts/EdgeChart';
import VolatilityChart from '../components/charts/VolatilityChart';
import IntelligencePanel from '../components/panels/IntelligencePanel';
import TradeAnalyticsPanel from '../components/panels/TradeAnalyticsPanel';
import { useTradingStore } from '../stores/tradingStore';
import {
  placeTrade, fetchTrades, refreshPrices, closeTrade,
  calcPortfolioStats, computePnl,
} from '../services/tradeService';

// ─────────────────────────────────────────────────────────────────────────────
// KALSHI DIRECT API
// ─────────────────────────────────────────────────────────────────────────────
const KALSHI_BASE = 'https://api.elections.kalshi.com/v1';
const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || '';

function buildKalshiUrl(eventTicker) {
  const datePattern = /^([A-Z]+)-(\d{2}[A-Z]{3}.+)$/;
  const match = eventTicker.match(datePattern);
  if (!match) throw new Error(`Cannot parse series from event ticker: ${eventTicker}`);

  if (!eventTicker) return null;
  // ✅ Route through your backend proxy instead of Kalshi directly
  return `${API_BASE_URL}/api/kalshi/event/${eventTicker}`;
}

// All basketball games last ~3h: start ≈ target_datetime (expiration) - 3h
const BASKETBALL_OFFSET_MS = 3 * 60 * 60 * 1000;
function approxStartTime(targetDatetime, seriesTicker) {
  if (!targetDatetime) return null;
  const exp = new Date(targetDatetime);
  if (isNaN(exp)) return null;
  return new Date(exp.getTime() - BASKETBALL_OFFSET_MS).toISOString();
}

// ── Mock chart seeder ───────────────────────────────────────────────────
function generateMockChartData(startTimeIso, markets) {
  const fmtTime = (date) =>
    date.toLocaleString('en-US', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
      timeZone: 'America/New_York',
    });

  const now      = new Date();
  const team0    = markets[0]?.team_name || markets[0]?.name || 'Home';
  const team1    = markets[1]?.team_name || markets[1]?.name || 'Away';

  const rawPrice = markets[0]?.last_price ?? markets[0]?.yes_price ?? 0.5;
  const endP0    = Math.round(rawPrice * 100 * 100) / 100;

  let start = new Date(startTimeIso);
  if (isNaN(start) || now.getTime() - start.getTime() < 5 * 60 * 1000) {
    start = new Date(now.getTime() - 3 * 60 * 60 * 1000);
  }

  const totalMs  = now.getTime() - start.getTime();
  const INTERVAL = 60 * 1000;
  const n        = Math.max(10, Math.min(300, Math.ceil(totalMs / INTERVAL)));
  const stepMs   = totalMs / n;

  const points = [];
  let val = 50 + (Math.random() - 0.5) * 8;

  for (let i = 0; i <= n; i++) {
    const t        = new Date(start.getTime() + i * stepMs);
    const progress = i / n;

    if (i > 0) {
      const noise  = ((Math.random() + Math.random() + Math.random()) / 3 - 0.5) * 10;
      const drift  = (endP0 - val) * (0.04 + 0.12 * Math.pow(progress, 1.5));
      val = Math.max(1, Math.min(99, val + noise + drift));
    }

    const v0 = Math.round(val * 100) / 100;
    const v1 = Math.round((100 - val) * 100) / 100;

    points.push({
      timestamp:     t.toISOString(),
      time:          fmtTime(t),
      market_prob:   v0,
      fair_prob:     v0,
      edge:          0,
      market_prices: { [team0]: v0, [team1]: v1 },
    });
  }
  return points;
}

// ─────────────────────────────────────────────────────────────────────────────
// FIX: Robust Kalshi event transformer that handles multiple API response shapes
// ─────────────────────────────────────────────────────────────────────────────
function extractMarketsFromResponse(responseData) {
  // Shape 1: { event: { markets: [...] } }  — standard Kalshi v2 event endpoint
  if (responseData?.event?.markets?.length) {
    return { event: responseData.event, markets: responseData.event.markets };
  }

  // Shape 2: { markets: [...] }  — some proxy wrappers return markets at top level
  if (responseData?.markets?.length) {
    return { event: responseData, markets: responseData.markets };
  }

  // Shape 3: { series: { markets: [...] } }  — series endpoint used for some tickers
  if (responseData?.series?.markets?.length) {
    return { event: responseData.series, markets: responseData.series.markets };
  }

  // Shape 4: Direct array  — rare but possible from some proxy implementations
  if (Array.isArray(responseData) && responseData.length) {
    return { event: { markets: responseData }, markets: responseData };
  }

  // Shape 5: Single event object with nested event key variations
  const eventObj = responseData?.event || responseData?.data?.event || responseData?.result || responseData;
  if (eventObj?.markets?.length) {
    return { event: eventObj, markets: eventObj.markets };
  }

  return { event: responseData, markets: [] };
}

function transformKalshiEvent(eventData) {
  // ✅ FIX: Use robust extractor instead of the single-shape assumption
  const { event, markets } = extractMarketsFromResponse(eventData);

  if (markets.length < 1) {
    // Provide detailed debug info to help diagnose the backend response shape
    console.error('[GameDetail] No markets found. Response shape:', JSON.stringify(eventData).slice(0, 500));
    throw new Error('No markets found in Kalshi event');
  }

  const [market0, market1] = markets;

  // ✅ FIX: Guard against missing market1 (some games may only have 1 market initially)
  // FIX: Do NOT spread market0 — that copies the home team's name onto the away fallback.
  const safeMarket1 = market1 || {
    id: null,
    name: null,   // resolved to 'Away' by resolveMarketName inside makeTeam
    yes_bid:  100 - (market0.yes_ask ?? 50),
    yes_ask:  100 - (market0.yes_bid ?? 50),
    last_price: market0.last_price != null ? 100 - market0.last_price : null,
    status: market0.status,
    volume: 0, open_interest: 0,
    dollar_volume: 0, recent_volume: 0, dollar_recent_volume: 0, dollar_open_interest: 0,
  };

  const midPrice = (m) => {
    const bid = m.yes_bid ?? 0;
    const ask = m.yes_ask ?? 100;
    if (bid === 0 && ask <= 1)   return (m.last_price ?? 0) / 100;
    if (bid >= 99 && ask >= 99)  return (m.last_price ?? 99) / 100;
    return (bid + ask) / 2 / 100;
  };

  const prob0 = midPrice(market0);
  const prob1 = midPrice(safeMarket1);
  const total = prob0 + prob1 || 1;
  const normProb0 = prob0 / total;
  const normProb1 = prob1 / total;

  const marketStatus = market0.status || 'active';
  let gameStatus = 'scheduled';
  if (marketStatus === 'active') {
    const hasTraded = market0.volume > 0 || safeMarket1.volume > 0;
    const isSettling = market0.yes_bid >= 99 || market0.yes_bid === 0;
    gameStatus = isSettling ? 'final' : hasTraded ? 'live' : 'scheduled';
  }

  const league = event.product_metadata?.league
    || event.product_metadata?.competition
    || event.series_ticker
      ?.replace(/KXNCAAM/, 'NCAA M ')
      .replace(/KXNCAAW/, 'NCAA W ')
      .replace(/KXNBL/, 'NBL')
      .replace(/KNBA/, 'NBA')
    || 'Sports';

  // ✅ FIX: Guard m.name — Kalshi NCAAW/NCAAB events sometimes return
  // markets where `name` is undefined, causing `.split()` to crash.
  const resolveMarketName = (m, fallback) =>
    m.name || m.yes_sub_title || m.yes_subtitle || m.subtitle || m.short_name || fallback;

  const makeTeam = (m) => {
    const teamName = resolveMarketName(m, 'TBD');
    return {
      name: teamName,
      abbreviation:
        m.rulebook_variables?.['Color Palette']?.split('-')[1] ||
        teamName.split(' ').filter(Boolean).map(w => w[0]).join('').slice(0, 4) || '?',
      logo_url: null,
    };
  };

  const homeTeam  = makeTeam(market0);
  const awayTeam  = makeTeam(safeMarket1);
  const homeMarket = market0;
  const awayMarket = safeMarket1;
  const homeProb   = normProb0;
  const awayProb   = normProb1;

  const homeMidCents  = ((homeMarket.yes_bid ?? 0) + (homeMarket.yes_ask ?? 100)) / 2;
  const edgeRaw       = (homeMarket.last_price ?? homeMidCents - homeMidCents) / 100;
  const prevHome      = homeMarket.prev_period_price ?? homeMidCents;
  const priceChange   = homeMidCents - prevHome;
  const volatility    = Math.abs(priceChange) / 100;
  const trend         = priceChange > 3 ? 'up' : priceChange < -3 ? 'down' : 'neutral';

  return {
    game: {
      id:           event.ticker || event.event_ticker,
      league,
      title:        event.title || event.event_title || `${homeTeam.name} vs ${awayTeam.name}`,
      subtitle:     event.sub_title || event.event_subtitle || '',
      status:       gameStatus,
      start_time:   approxStartTime(event.target_datetime, event.series_ticker),
      expiration:   event.target_datetime,
      away_team:    awayTeam,
      home_team:    homeTeam,
      away_score:   0,
      home_score:   0,
      quarter:      0,
      time_remaining: '',
    },
    markets: [
      {
        id:                 homeMarket.id,
        ticker:             homeMarket.ticker_name || homeMarket.ticker,
        name:               homeMarket.name,
        team_name:          homeTeam.name,
        outcome:            'home',
        yes_bid:            (homeMarket.yes_bid ?? 0) / 100,
        yes_ask:            (homeMarket.yes_ask ?? 100) / 100,
        yes_price:          homeMidCents / 100,
        last_price:         (homeMarket.last_price ?? homeMidCents) / 100,
        prev_price:         ((homeMarket.prev_period_price ?? homeMarket.yes_bid) ?? 0) / 100,
        implied_probability: homeProb,
        volume:             homeMarket.volume ?? 0,
        open_interest:      homeMarket.open_interest ?? 0,
        dollar_volume:      homeMarket.dollar_volume ?? 0,
        recent_volume:      homeMarket.recent_volume ?? 0,
        dollar_recent_volume: homeMarket.dollar_recent_volume ?? 0,
        dollar_open_interest: homeMarket.dollar_open_interest ?? 0,
        open_date:          homeMarket.open_date,
        expected_expiration_date: homeMarket.expected_expiration_date,
        is_active:          homeMarket.status === 'active',
      },
      {
        id:                 awayMarket.id,
        ticker:             awayMarket.ticker_name || awayMarket.ticker,
        name:               awayMarket.name,
        team_name:          awayTeam.name,
        outcome:            'away',
        yes_bid:            (awayMarket.yes_bid ?? 0) / 100,
        yes_ask:            (awayMarket.yes_ask ?? 100) / 100,
        yes_price:          ((awayMarket.yes_bid ?? 0) + (awayMarket.yes_ask ?? 100)) / 2 / 100,
        last_price:         (awayMarket.last_price ?? ((awayMarket.yes_bid ?? 0) + (awayMarket.yes_ask ?? 100)) / 2) / 100,
        prev_price:         ((awayMarket.prev_period_price ?? awayMarket.yes_bid) ?? 0) / 100,
        implied_probability: awayProb,
        volume:             awayMarket.volume ?? 0,
        open_interest:      awayMarket.open_interest ?? 0,
        dollar_volume:      awayMarket.dollar_volume ?? 0,
        recent_volume:      awayMarket.recent_volume ?? 0,
        dollar_recent_volume: awayMarket.dollar_recent_volume ?? 0,
        dollar_open_interest: awayMarket.dollar_open_interest ?? 0,
        open_date:          awayMarket.open_date,
        expected_expiration_date: awayMarket.expected_expiration_date,
        is_active:          awayMarket.status === 'active',
      },
    ],
    fair_prob_home: homeProb,
    fair_prob_away: awayProb,
    confidence: 0.7,
    signal: {
      signal_type:        edgeRaw > 0.03 ? 'BUY' : edgeRaw < -0.03 ? 'SELL' : 'HOLD',
      signal_score:       Math.round(50 + edgeRaw * 200),
      edge:               edgeRaw,
      fair_prob:          homeProb,
      market_prob:        homeMidCents / 100,
      risk_tier:          volatility > 0.1 ? 'high' : volatility > 0.05 ? 'medium' : 'low',
      recommended_action: edgeRaw > 0.03 ? 'ENTER_LONG' : edgeRaw < -0.03 ? 'ENTER_SHORT' : 'WAIT',
      recommended_size:   Math.round(Math.abs(edgeRaw) * 100 * 10) / 10,
      is_actionable:      Math.abs(edgeRaw) > 0.03,
      momentum_direction: trend,
      volatility,
      analytics: {
        expected_value:      edgeRaw * 100,
        break_even_prob:     homeMidCents / 100,
        max_risk:            Math.abs(edgeRaw) * 100,
        suggested_exit_prob: homeProb + edgeRaw * 0.5,
        suggested_stop_prob: homeProb - edgeRaw * 0.5,
        risk_reward_ratio:   edgeRaw > 0 ? edgeRaw / (1 - homeProb) : 0,
      },
    },
    intelligence: {
      trend_5min:       trend,
      trend_30min:      trend,
      volatility_regime: volatility > 0.1 ? 'spike' : 'normal',
      volatility_value: volatility,
      momentum:         trend === 'neutral' ? 'neutral' : trend === 'up' ? 'positive' : 'negative',
    },
    is_clutch:          volatility > 0.12 && gameStatus === 'live',
    probability_history: [],
    positions:          [],
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// STRATEGY DEFINITIONS
// ─────────────────────────────────────────────────────────────────────────────
const STRATEGIES = [
  {
    id: 'model_a', name: 'Model A', color: 'emerald',
    description: 'Disciplined Edge Trader - 5% min edge, momentum required, 15% profit target, 3-loss circuit breaker.',
    side: 'yes', direction: 'buy',
    model: 'Model A',
    rules: [
      { label: 'Edge ≥ 5%',          check: (s) => (s?.edge || 0) >= 0.05 },
      { label: 'Signal Score ≥ 60',  check: (s) => (s?.signal_score || 0) >= 60 },
      { label: 'Momentum required',  check: (s) => !!s?.momentum_aligned },
      { label: 'Risk tier LOW',      check: (s) => s?.risk_tier === 'low' },
    ],
  },
  {
    id: 'model_b', name: 'Model B', color: 'blue',
    description: 'High Frequency Hunter - 3% min edge, 8% profit target, 5-loss circuit breaker, fast entries.',
    side: 'yes', direction: 'buy',
    model: 'Model B',
    rules: [
      { label: 'Edge ≥ 3%',          check: (s) => (s?.edge || 0) >= 0.03 },
      { label: 'Signal Score ≥ 45',  check: (s) => (s?.signal_score || 0) >= 45 },
      { label: 'Risk tier LOW/MED',  check: (s) => ['low', 'medium'].includes(s?.risk_tier) },
    ],
  },
  {
    id: 'model_c', name: 'Model C', color: 'purple',
    description: 'Institutional Risk-First - 7% min edge, 20% profit target, premium signal quality, manual reset.',
    side: 'yes', direction: 'buy',
    model: 'Model C',
    rules: [
      { label: 'Edge ≥ 7%',           check: (s) => (s?.edge || 0) >= 0.07 },
      { label: 'Signal Score ≥ 75',   check: (s) => (s?.signal_score || 0) >= 75 },
      { label: 'Momentum required',   check: (s) => !!s?.momentum_aligned },
      { label: 'Risk tier LOW',       check: (s) => s?.risk_tier === 'low' },
    ],
  },
];

const evaluateStrategies = (signal, isClutch) =>
  STRATEGIES.map((strat) => {
    const ruleResults = strat.rules.map((rule) => ({
      label:  rule.label,
      passed: rule.check(signal, isClutch),
    }));
    return { strategy: strat, ruleResults, matched: ruleResults.every((r) => r.passed) };
  });

const AUTO_TRADE_COOLDOWN_MS = 60_000;

// ─────────────────────────────────────────────────────────────────────────────
// COLOR HELPERS
// ─────────────────────────────────────────────────────────────────────────────
const colorMap = {
  green:   { badge: 'bg-green-600',   border: 'border-green-700',   text: 'text-green-400',   bg: 'bg-green-900/30'   },
  blue:    { badge: 'bg-blue-600',    border: 'border-blue-700',    text: 'text-blue-400',    bg: 'bg-blue-900/30'    },
  red:     { badge: 'bg-red-600',     border: 'border-red-700',     text: 'text-red-400',     bg: 'bg-red-900/30'     },
  orange:  { badge: 'bg-orange-600',  border: 'border-orange-700',  text: 'text-orange-400',  bg: 'bg-orange-900/30'  },
  yellow:  { badge: 'bg-yellow-600',  border: 'border-yellow-700',  text: 'text-yellow-400',  bg: 'bg-yellow-900/30'  },
  emerald: { badge: 'bg-emerald-600', border: 'border-emerald-700', text: 'text-emerald-400', bg: 'bg-emerald-900/30' },
  purple:  { badge: 'bg-purple-600',  border: 'border-purple-700',  text: 'text-purple-400',  bg: 'bg-purple-900/30'  },
};

const getSignalColor = (t) => ({
  BUY: 'bg-green-500', STRONG_BUY: 'bg-green-600',
  SELL: 'bg-red-500',  STRONG_SELL: 'bg-red-600', HOLD: 'bg-gray-600',
}[t] || 'bg-gray-700');

// ─────────────────────────────────────────────────────────────────────────────
// STRATEGY MATCH PANEL
// ─────────────────────────────────────────────────────────────────────────────
const StrategyMatchPanel = ({ evaluations }) => {
  const matched = evaluations.filter((e) => e.matched);
  if (matched.length === 0) {
    return (
      <div className="rounded-lg border border-red-700 bg-red-900/20 p-4 space-y-3">
        <div className="flex items-center gap-2 text-red-400 font-semibold text-sm">
          <ShieldAlert className="w-4 h-4" /> No Strategy Matched
        </div>
        <p className="text-xs text-gray-400">
          Current conditions do not satisfy any strategy rules. Proceeding will execute
          a paper trade <span className="text-red-400 font-medium">at your own risk</span>.
        </p>
        <div className="space-y-3 pt-1">
          {evaluations.map(({ strategy, ruleResults }) => {
            const c = colorMap[strategy.color];
            return (
              <div key={strategy.id}>
                <p className={`text-xs font-semibold mb-1 ${c.text}`}>{strategy.name}</p>
                {ruleResults.map((r) => (
                  <div key={r.label} className="flex items-center gap-2 text-xs text-gray-500">
                    <XCircle className="w-3 h-3 text-red-600 flex-shrink-0" /> {r.label}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {matched.map(({ strategy, ruleResults }) => {
        const c = colorMap[strategy.color];
        return (
          <div key={strategy.id} className={`rounded-lg border ${c.border} ${c.bg} p-4 space-y-2`}>
            <div className={`flex items-center gap-2 font-semibold text-sm ${c.text}`}>
              <CheckCircle2 className="w-4 h-4" /> Strategy Matched: {strategy.name}
            </div>
            <p className="text-xs text-gray-400">{strategy.description}</p>
            <div className="space-y-1 pt-1">
              {ruleResults.map((r) => (
                <div key={r.label} className="flex items-center gap-2 text-xs text-gray-300">
                  <CheckCircle2 className="w-3 h-3 text-green-400 flex-shrink-0" /> {r.label}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// PLACED TRADES LIST
// ─────────────────────────────────────────────────────────────────────────────
const TradesList = ({ gameId, refreshKey, onCloseRequest }) => {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchTrades({ gameId })
      .then((t) => { if (!cancelled) setTrades(t); })
      .catch(console.error)
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [gameId, refreshKey]);

  if (loading && trades.length === 0) {
    return (
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 flex items-center justify-center gap-2 text-xs text-gray-500">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading positions…
      </div>
    );
  }

  if (trades.length === 0) {
    return (
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 text-center text-xs text-gray-500">
        No positions for this game yet.
      </div>
    );
  }

  const stats    = calcPortfolioStats(trades);
  const totalPnl = stats.totalPnl;

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-yellow-400" />
          Positions
          <Badge variant="outline" className="text-xs">{trades.length}</Badge>
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Game P&amp;L:</span>
          <span className={`text-sm font-bold font-mono ${totalPnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}
          </span>
          <Link to="/trades">
            <Button size="sm" variant="ghost" className="h-7 text-xs gap-1 text-blue-400 hover:text-blue-300">
              <FileText className="w-3 h-3" />All Trades
            </Button>
          </Link>
        </div>
      </div>

      <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
        {trades.map((t) => {
          const pnl       = t.pnl || 0;
          const isNoTrade = (t.side || 'yes') === 'no';
          const effEntry  = isNoTrade ? 1 - (t.entry_price || 0) : (t.entry_price || 0);
          const curYes    = t.current_price ?? t.entry_price ?? 0;
          const effCur    = isNoTrade ? 1 - curYes : curYes;
          const returnPct = effEntry > 0 ? ((effCur - effEntry) / effEntry) * 100 : 0;

          return (
            <div key={t.id}
              className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg text-xs gap-2">
              {/* Left */}
              <div className="flex items-center gap-2 flex-wrap min-w-0">
                <Badge className={
                  t.type === 'auto-edge' ? 'bg-purple-700 text-white text-[10px]' :
                  t.type === 'signal'    ? 'bg-blue-700 text-white text-[10px]'   :
                                           'bg-gray-700 text-white text-[10px]'
                }>
                  {t.type === 'auto-edge' ? 'AUTO' : t.type === 'signal' ? 'SIG' : 'MAN'}
                </Badge>
                <span className="font-semibold text-white truncate max-w-[120px]">
                  {t.market_name || t.team_name || '—'}
                </span>
                <span className={`font-bold ${t.side === 'yes' ? 'text-emerald-400' : 'text-red-400'}`}>
                  {t.direction?.toUpperCase()} {t.side?.toUpperCase()}
                </span>
                <span className="text-gray-400">{t.quantity}×</span>
                <span className="text-gray-500 font-mono hidden sm:inline">
                  {(effEntry * 100).toFixed(0)}¢
                  {' → '}
                  {(effCur * 100).toFixed(0)}¢
                </span>
                <Badge className={`text-[10px] px-1.5 py-0 ${
                  t.status === 'open'
                    ? 'bg-blue-900/50 text-blue-300 border border-blue-700'
                    : 'bg-gray-800 text-gray-500 border border-gray-700'
                }`}>{t.status}</Badge>
              </div>

              {/* Right */}
              <div className="flex items-center gap-3 flex-shrink-0 text-right">
                {t.status === 'open' && (
                  <Button
                    size="sm" variant="ghost"
                    className="h-6 px-2 text-[10px] text-yellow-400 hover:text-yellow-300 hover:bg-yellow-900/20"
                    onClick={() => onCloseRequest(t)}
                  >
                    Exit
                  </Button>
                )}
                {t.strategy && (
                  <span className="text-purple-400 italic hidden md:inline text-[10px]">{t.strategy}</span>
                )}
                <span className="text-gray-500">
                  {t.timestamp ? new Date(t.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'America/New_York', timeZoneName: 'short' }) : '—'}
                </span>
                <div className="flex flex-col items-end">
                  <span className={`font-bold font-mono ${pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
                  </span>
                  <span className={`text-[10px] font-mono ${returnPct >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                    {returnPct >= 0 ? '+' : ''}{returnPct.toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// MAIN COMPONENT
// ─────────────────────────────────────────────────────────────────────────────
const GameDetail = () => {
  const { gameId } = useParams();

  const [data, setData]                         = useState(null);
  const [chartData, setChartData]               = useState({ probability_data: [], volatility_data: [] });
  const [loading, setLoading]                   = useState(true);
  const [error, setError]                       = useState(null);
  const [chartTimeframe, setChartTimeframe]     = useState('full');
  const [lastFetched, setLastFetched]           = useState(null);

  const localHistoryRef = useRef([]);
  const historyLoadedRef = useRef(false);

  // ── Helpers ──────────────────────────────────────────────────────────────
  const fmtChartTime = (date) =>
    date.toLocaleString('en-US', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
      timeZone: 'America/New_York',
    });

  // ── Seed chart with Kalshi candlestick history ────
  const loadHistory = useCallback(async (markets) => {
    if (historyLoadedRef.current || !markets?.length) return;
    historyLoadedRef.current = true;
    try {
      const endTs   = Math.floor(Date.now() / 1000);
      const startTs = endTs - 30 * 24 * 60 * 60;
      const results = await Promise.all(
        markets.slice(0, 2).map((m) => {
          if (!m.ticker) return Promise.resolve({ candlesticks: [] });
          const params = new URLSearchParams({
            period_interval: '60',
            start_ts: String(startTs),
            end_ts:   String(endTs),
          });
          return fetch(
            `${API_BASE_URL}/api/markets/${encodeURIComponent(m.ticker)}/candlesticks?${params}`,
            { headers: { Accept: 'application/json' } }
          ).then((r) => r.ok ? r.json() : { candlesticks: [] }).catch(() => ({ candlesticks: [] }));
        })
      );
      const candles0 = results[0]?.candlesticks || [];
      const candles1 = results[1]?.candlesticks || [];
      if (!candles0.length && !candles1.length) return;

      const len = Math.max(candles0.length, candles1.length);
      const histPoints = [];
      for (let i = 0; i < len; i++) {
        const c0 = candles0[i] || {};
        const c1 = candles1[i] || {};
        const ts  = c0.end_ts || c1.end_ts;
        if (!ts) continue;
        const dt  = new Date(ts * 1000);
        const price0 = c0.close_price ?? c0.last_price ?? 50;
        const price1 = c1.close_price ?? c1.last_price ?? 50;
        const point = {
          timestamp: dt.toISOString(),
          time: fmtChartTime(dt),
          market_prob: price0,
          fair_prob: price0,
          edge: 0,
          market_prices: {},
        };
        if (markets[0]) point.market_prices[markets[0].team_name || markets[0].name] = Math.round(price0 * 10) / 10;
        if (markets[1]) point.market_prices[markets[1].team_name || markets[1].name] = Math.round(price1 * 10) / 10;
        histPoints.push(point);
      }
      if (histPoints.length) localHistoryRef.current = histPoints;
    } catch (e) {
      console.warn('History load failed (non-critical):', e);
    }
  }, []);


  const [tradeDialogOpen, setTradeDialogOpen]       = useState(false);
  const [tradeSide, setTradeSide]                   = useState('yes');
  const [tradeDirection, setTradeDirection]         = useState('buy');
  const [tradeMarketOutcome, setTradeMarketOutcome] = useState('home');
  const [tradeQuantity, setTradeQuantity]           = useState(10);
  const [tradeDollarAmount, setTradeDollarAmount]   = useState('');
  const [tradeLoading, setTradeLoading]             = useState(false);
  const [tradeResult, setTradeResult]               = useState(null);

  const [exitTarget, setExitTarget]   = useState(null);
  const [exitLoading, setExitLoading] = useState(false);

  const [strategyEvaluations, setStrategyEvaluations] = useState([]);
  const [tradesKey, setTradesKey] = useState(0);
  const bumpTrades = () => setTradesKey((k) => k + 1);

  const [autoTradeEnabled, setAutoTradeEnabled] = useState(false);
  const [edgeThreshold, setEdgeThreshold]       = useState(5);
  const [autoTradeQty, setAutoTradeQty]         = useState(5);
  const [autoTradeLog, setAutoTradeLog]         = useState([]);
  const lastAutoTradeRef = useRef(0);

  const addTrade = useTradingStore((state) => state.addTrade);

  // ── Fetch from Kalshi ─────────────────────────────────────────────────────
  const loadGame = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const url = buildKalshiUrl(gameId);
      const res = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!res.ok) throw new Error(`Kalshi API error: ${res.status} ${res.statusText}`);

      const json     = await res.json();
      const gameData = transformKalshiEvent(json);
      const now      = new Date();
      const hm       = gameData.markets.find((m) => m.outcome === 'home');

      if (hm) {
        await loadHistory(gameData.markets);

        const isFlat = localHistoryRef.current.length < 10 || (
          localHistoryRef.current.length > 0 &&
          localHistoryRef.current.every(
            (p) => p.market_prob === localHistoryRef.current[0].market_prob
          )
        );
        if (isFlat && gameData.game.start_time) {
          localHistoryRef.current = generateMockChartData(
            gameData.game.start_time,
            gameData.markets,
          );
        }

        const point = {
          timestamp: now.toISOString(),
          time:      fmtChartTime(now),
          market_prob: Math.round(hm.yes_price * 100 * 10) / 10,
          fair_prob:   Math.round(gameData.fair_prob_home * 100 * 10) / 10,
          edge:        Math.round((gameData.signal?.edge || 0) * 100 * 10) / 10,
        };

        point.market_prices = {};
        gameData.markets.forEach((market) => {
          const teamName = market.team_name || market.name;
          point.market_prices[teamName] = Math.round(market.yes_price * 100 * 10) / 10;
        });

        localHistoryRef.current = [...localHistoryRef.current.slice(-299), point];
        refreshPrices(gameId, hm.yes_price).then(() => bumpTrades()).catch(console.error);
      }

      const probData = localHistoryRef.current;
      const volData  = probData.map((p, i) => {
        const ref = probData[Math.max(0, i - 12)];
        return {
          time:       p.time,
          volatility: Math.round(Math.abs(p.market_prob - ref.market_prob) * 10) / 10,
        };
      });

      setData(gameData);
      setChartData({ probability_data: probData, volatility_data: volData });
      setLastFetched(now);
      if (!silent) {
        const hm = gameData.markets.find((m) => m.outcome === 'home');
        const am = gameData.markets.find((m) => m.outcome === 'away');
        if (am && hm && (am.yes_price ?? 0) > (hm.yes_price ?? 0)) {
          setTradeMarketOutcome('away');
        } else {
          setTradeMarketOutcome('home');
        }
      }
    } catch (err) {
      setError(err.message);
    }
    if (!silent) setLoading(false);
  }, [gameId, loadHistory]);

  useEffect(() => {
    loadGame(false);
    const interval = setInterval(() => loadGame(true), 60_000);
    return () => clearInterval(interval);
  }, [loadGame]);

  useEffect(() => {
    if (data) setStrategyEvaluations(evaluateStrategies(data.signal, data.is_clutch));
  }, [data]);

  // ── Manual Trade ──────────────────────────────────────────────────────────
  const handleTrade = async () => {
    setTradeLoading(true);
    setTradeResult(null);
    try {
      const market = data?.markets?.find((m) => m.outcome === tradeMarketOutcome);
      if (!market) throw new Error('Market not found');

      const entryPrice = tradeSide === 'yes'
        ? (tradeDirection === 'buy' ? market.yes_ask  : market.yes_bid)
        : (tradeDirection === 'buy' ? (1 - market.yes_bid) : (1 - market.yes_ask));

      const dollarAmt   = parseFloat(tradeDollarAmount) || 0;
      const derivedQty  = dollarAmt > 0 && entryPrice > 0
        ? Math.max(1, Math.round(dollarAmt / entryPrice))
        : tradeQuantity;

      const matchedStrategy = strategyEvaluations.find((e) => e.matched)?.strategy;
      const teamDisplayName = market.team_name || market.name;

      const newTrade = {
        id:            `paper-${Date.now()}-${Math.random().toString(36).slice(2, 5)}`,
        game_id:       gameId,
        game_title:    data?.game?.title || gameId,
        league:        data?.game?.league || '',
        market_id:     market.id,
        market_name:   teamDisplayName,
        team_name:     teamDisplayName,
        side:          tradeSide,
        direction:     tradeDirection,
        quantity:      derivedQty,
        entry_price:   entryPrice,
        current_price: market.yes_price,
        dollar_amount: dollarAmt || derivedQty * entryPrice,
        type:          'manual',
        strategy:      matchedStrategy?.name || null,
        signal_type:   data?.signal?.signal_type || null,
        edge:          data?.signal?.edge || 0,
        status:        'open',
        timestamp:     new Date().toISOString(),
        pnl:           0,
      };

      const saved = await placeTrade(newTrade);
      addTrade(saved);
      bumpTrades();

      const costAmt = dollarAmt > 0 ? `$${dollarAmt.toFixed(2)}` : `${derivedQty}×`;
      setTradeResult({
        success: true,
        message: `Order filled: ${tradeDirection.toUpperCase()} ${tradeSide.toUpperCase()} ${teamDisplayName} · ${costAmt} @ ${(entryPrice * 100).toFixed(0)}¢`,
      });
      setTradeDollarAmount('');
      await loadGame(true);
    } catch (err) {
      setTradeResult({ success: false, message: err.message });
    }
    setTradeLoading(false);
  };

  // ── Exit / Close trade ────────────────────────────────────────────────────
  const handleExitConfirm = async () => {
    if (!exitTarget) return;
    setExitLoading(true);
    try {
      await closeTrade(exitTarget.id, exitTarget.current_price);
      bumpTrades();
      setExitTarget(null);
    } catch (err) {
      console.error('Close trade failed:', err);
    }
    setExitLoading(false);
  };

  // ── Auto-Edge watcher ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!autoTradeEnabled || !data) return;

    const edgeRaw = data?.signal?.edge || 0;
    const edgePct = Math.abs(edgeRaw * 100);
    if (edgePct < edgeThreshold) return;

    const now = Date.now();
    if (now - lastAutoTradeRef.current < AUTO_TRADE_COOLDOWN_MS) return;

    const market = data?.markets?.find((m) => m.outcome === 'home');
    if (!market) return;

    const autoSide       = edgeRaw >= 0 ? 'yes' : 'no';
    const entryPrice     = autoSide === 'yes' ? market.yes_ask : (1 - market.yes_bid);
    const teamDisplayName = market.team_name || market.name;

    const executeAutoTrade = async () => {
      lastAutoTradeRef.current = now;
      try {
        const newTrade = {
          id:            `auto-${Date.now()}-${Math.random().toString(36).slice(2, 5)}`,
          game_id:       gameId,
          game_title:    data?.game?.title || gameId,
          league:        data?.game?.league || '',
          market_id:     market.id,
          market_name:   teamDisplayName,
          team_name:     teamDisplayName,
          side:          autoSide,
          direction:     'buy',
          quantity:      autoTradeQty,
          entry_price:   entryPrice,
          current_price: market.yes_price,
          type:          'auto-edge',
          strategy:      `Auto-Edge (${edgePct.toFixed(1)}% edge)`,
          signal_type:   data?.signal?.signal_type || null,
          edge:          edgeRaw,
          status:        'open',
          timestamp:     new Date().toISOString(),
          pnl:           0,
        };

        const saved = await placeTrade(newTrade);
        addTrade(saved);
        bumpTrades();

        setAutoTradeLog((prev) => [{
          id:        saved.id,
          timestamp: saved.timestamp,
          edge:      edgePct.toFixed(1),
          side:      autoSide.toUpperCase(),
          qty:       autoTradeQty,
          success:   true,
          message:   `${teamDisplayName} · ${autoSide.toUpperCase()} ${autoTradeQty}c @ ${(entryPrice * 100).toFixed(0)}¢`,
        }, ...prev].slice(0, 10));
      } catch (err) {
        setAutoTradeLog((prev) => [{
          id:        `auto-err-${Date.now()}`,
          timestamp: new Date().toISOString(),
          edge:      edgePct.toFixed(1),
          success:   false,
          message:   err.message,
        }, ...prev].slice(0, 10));
      }
    };

    executeAutoTrade();
  }, [data, autoTradeEnabled, edgeThreshold, autoTradeQty, gameId, addTrade]);

  // ── Early returns ─────────────────────────────────────────────────────────
  if (loading && !data) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
        <div className="text-center space-y-3">
          <RefreshCw className="w-8 h-8 animate-spin text-blue-500 mx-auto" />
          <p className="text-sm text-muted-foreground">Fetching live Kalshi data…</p>
          <p className="text-xs text-muted-foreground font-mono">{gameId}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
        <div className="text-center space-y-4 max-w-sm">
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto" />
          <p className="text-red-400 font-medium">Failed to load game</p>
          <p className="text-xs text-muted-foreground font-mono break-all">{error}</p>
          <Button onClick={() => loadGame(false)} className="mt-2">Retry</Button>
        </div>
      </div>
    );
  }

  // ── Derived values ────────────────────────────────────────────────────────
  const game        = data?.game;
  const signal      = data?.signal;
  const homeMarket  = data?.markets?.find((m) => m.outcome === 'home');
  const awayMarket  = data?.markets?.find((m) => m.outcome === 'away');
  const intelligence = data?.intelligence;
  const isClutch    = data?.is_clutch;

  const matchedStrategies       = strategyEvaluations.filter((e) => e.matched);
  const currentEdgePct          = Math.abs((signal?.edge || 0) * 100);
  const autoTradeReady          = autoTradeEnabled && currentEdgePct >= edgeThreshold;
  const selectedMarket          = data?.markets?.find((m) => m.outcome === tradeMarketOutcome);
  const estimatedEntryPrice     = selectedMarket
    ? (tradeSide === 'yes'
        ? (tradeDirection === 'buy' ? selectedMarket.yes_ask  : selectedMarket.yes_bid)
        : (tradeDirection === 'buy' ? (1 - selectedMarket.yes_bid) : (1 - selectedMarket.yes_ask)))
    : 0;

  const getRiskTierColor = (tier) =>
    ({ low: 'text-green-400', medium: 'text-yellow-400', high: 'text-red-400' }[tier] || 'text-gray-400');

  const chanceColor = (pct) =>
    pct >= 70 ? 'text-green-400' : pct >= 50 ? 'text-blue-400' : pct >= 30 ? 'text-yellow-400' : 'text-red-400';

  const getActionColor = (action) => {
    if (!action) return 'text-gray-400';
    if (action.includes('LONG') || action === 'COVER') return 'text-green-400';
    if (action.includes('SHORT') || action.includes('EXIT')) return 'text-red-400';
    return 'text-gray-400';
  };

  const statusBadge = () => ({
    live:      <Badge className="bg-green-500 text-white text-xs animate-pulse">LIVE</Badge>,
    final:     <Badge className="bg-gray-500 text-white text-xs">FINAL</Badge>,
    scheduled: <Badge variant="outline" className="text-muted-foreground text-xs">SCHEDULED</Badge>,
  }[game?.status] || <Badge variant="outline" className="text-xs">{game?.status}</Badge>);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-background text-foreground transition-colors duration-300">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="border-b border-border bg-card/50">
        <div className="max-w-[1600px] mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Link to="/"><Button variant="ghost" size="sm" className="p-1">
                  <ArrowLeft className="w-4 h-4" />
                </Button></Link>
                <h1 className="text-lg font-bold">
                  {game?.away_team?.name} vs {game?.home_team?.name}
                </h1>
              </div>
              <div className="flex items-center gap-2 mt-1 ml-8 flex-wrap">
                <Badge variant="outline" className="text-muted-foreground text-xs">{game?.league}</Badge>
                {statusBadge()}
                {isClutch && (
                  <Badge className="bg-orange-500/20 text-orange-400 border border-orange-500/50 text-xs">
                    <Flame className="w-3 h-3 mr-1" />CLUTCH
                  </Badge>
                )}
                {matchedStrategies.length > 0 && (
                  <Badge className="bg-green-900/50 text-green-400 border border-green-700 text-xs">
                    <CheckCircle2 className="w-3 h-3 mr-1" />
                    {matchedStrategies[0].strategy.name} Active
                  </Badge>
                )}
                {autoTradeEnabled && (
                  <Badge className={`text-xs flex items-center gap-1 ${
                    autoTradeReady
                      ? 'bg-purple-600 text-white animate-pulse'
                      : 'bg-purple-900/40 text-purple-400 border border-purple-700'
                  }`}>
                    <Bot className="w-3 h-3" />
                    AUTO {autoTradeReady ? 'ACTIVE' : 'WATCHING'}
                  </Badge>
                )}
                {lastFetched && (
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <Clock className="w-3 h-3" />{lastFetched.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'America/New_York', timeZoneName: 'short' })}
                  </span>
                )}
                {data?.game?.start_time && (
                  <span className="text-xs text-cyan-400 flex items-center gap-1 font-medium">
                    <Calendar className="w-3 h-3" />
                    {new Date(data.game.start_time).toLocaleString('en-US', {
                      weekday: 'short', month: 'short', day: 'numeric',
                      hour: '2-digit', minute: '2-digit',
                      timeZone: 'America/New_York', timeZoneName: 'short',
                    })}
                  </span>
                )}
                <Link to="/trades">
                  <Badge className="bg-yellow-900/40 text-yellow-400 border border-yellow-700/60 text-xs cursor-pointer hover:bg-yellow-900/60">
                    <FileText className="w-3 h-3 mr-1" />Trades
                  </Badge>
                </Link>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground font-mono hidden md:block truncate max-w-[200px]">
                {gameId}
              </span>
              {(() => {
                const seriesTicker = (gameId.match(/^([A-Z]+)/)?.[1] || '').toLowerCase();
                const subtitleSlug = (data?.game?.subtitle || '')
                  .toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
                const kalshiUrl = `https://kalshi.com/markets/${seriesTicker}${subtitleSlug ? '/' + subtitleSlug : ''}/${gameId}`;
                return (
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs font-bold px-2 h-7 border-blue-700 text-blue-400 hover:bg-blue-900/30 hover:text-blue-300"
                    onClick={() => window.open(kalshiUrl, '_new', 'noopener,noreferrer')}
                    title="Open on Kalshi"
                  >
                    K
                  </Button>
                );
              })()}
              <Button variant="ghost" size="sm" onClick={() => loadGame(false)}>
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-[1600px] mx-auto px-4 py-4">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">

          {/* ── Main 3-col ────────────────────────────────────────────────── */}
          <div className="lg:col-span-3 space-y-4">

            {/* Game Header + Market Cards */}
            <div className="bg-card rounded-xl border border-border p-4 space-y-4">
              {/* Game title row */}
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-base font-bold leading-tight truncate">{game?.title}</h2>
                  {game?.subtitle && (
                    <p className="text-xs text-muted-foreground mt-0.5">{game.subtitle}</p>
                  )}
                  <div className="flex items-center gap-2 flex-wrap mt-2">
                    <Badge variant="outline" className="text-muted-foreground text-xs">{game?.league}</Badge>
                    {statusBadge()}
                    {isClutch && (
                      <Badge className="bg-orange-500/20 text-orange-400 border border-orange-500/50 text-xs">
                        <Flame className="w-3 h-3 mr-1" />CLUTCH
                      </Badge>
                    )}
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  {game?.start_time && (
                    <div className="text-xs text-muted-foreground flex items-center gap-1 justify-end">
                      <Clock className="w-3 h-3" />
                      {new Date(game.start_time).toLocaleString('en-US', {
                        month: 'short', day: 'numeric',
                        hour: '2-digit', minute: '2-digit',
                        timeZone: 'America/New_York', timeZoneName: 'short',
                      })}
                    </div>
                  )}
                  <div className="text-xs text-gray-600 mt-1 font-mono">{game?.id}</div>
                </div>
              </div>

              {/* Two team market cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[homeMarket, awayMarket].map((market) => {
                  if (!market) return null;
                  const chancePct   = Math.round((market.last_price ?? market.yes_price ?? 0) * 100);
                  const yesBidCents = Math.round((market.yes_bid  ?? 0) * 100);
                  const yesAskCents = Math.round((market.yes_ask  ?? 0) * 100);
                  const noBidCents  = 100 - yesAskCents;
                  const noAskCents  = 100 - yesBidCents;
                  const prevPct     = Math.round((market.prev_price ?? market.yes_price ?? 0) * 100);
                  const delta       = chancePct - prevPct;
                  const isHome      = market.outcome === 'home';
                  return (
                    <div
                      key={market.ticker}
                      className={`rounded-lg border p-3 ${
                        isHome
                          ? 'border-blue-700 bg-blue-900/10'
                          : 'border-purple-700 bg-purple-900/10'
                      }`}
                    >
                      {/* Team name + chance */}
                      <div className="flex items-center justify-between mb-3">
                        <div className="font-semibold text-sm truncate flex-1 pr-2">{market.name}</div>
                        <div className="flex items-end gap-1">
                          <span className={`text-2xl font-bold ${chanceColor(chancePct)}`}>{chancePct}%</span>
                          {delta !== 0 && (
                            <span className={`text-xs font-mono mb-0.5 ${
                              delta > 0 ? 'text-green-500' : 'text-red-500'
                            }`}>
                              {delta > 0 ? '+' : ''}{delta}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* YES / NO bid-ask grid */}
                      <div className="grid grid-cols-2 gap-2 text-xs mb-3">
                        <div className="bg-gray-800/70 rounded p-2">
                          <div className="text-gray-400 font-semibold mb-1.5">YES</div>
                          <div className="flex justify-between mb-1">
                            <span className="text-gray-500">Bid</span>
                            <span className="text-green-400 font-mono">{yesBidCents}¢</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-500">Ask</span>
                            <span className="text-red-400 font-mono">{yesAskCents}¢</span>
                          </div>
                        </div>
                        <div className="bg-gray-800/70 rounded p-2">
                          <div className="text-gray-400 font-semibold mb-1.5">NO</div>
                          <div className="flex justify-between mb-1">
                            <span className="text-gray-500">Bid</span>
                            <span className="text-green-400 font-mono">{noBidCents}¢</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-500">Ask</span>
                            <span className="text-red-400 font-mono">{noAskCents}¢</span>
                          </div>
                        </div>
                      </div>

                      {/* Volume stats */}
                      <div className="grid grid-cols-3 gap-1 text-xs text-center pt-2 border-t border-gray-700/60">
                        <div>
                          <div className="text-gray-500">Volume</div>
                          <div className="text-gray-300">{(market.volume ?? 0).toLocaleString()}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">$ Vol</div>
                          <div className="text-gray-300">${(market.dollar_volume ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Rec. Vol</div>
                          <div className="text-gray-300">{(market.recent_volume ?? 0).toLocaleString()}</div>
                        </div>
                        <div className="col-span-3 mt-1">
                          <div className="text-gray-500">Open Interest</div>
                          <div className="text-gray-300">{(market.open_interest ?? 0).toLocaleString()}</div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Probability bar */}
              <div className="space-y-1">
                <div className="flex rounded-full overflow-hidden h-2">
                  <div className="bg-blue-500 transition-all duration-500"
                    style={{ width: `${Math.round((homeMarket?.last_price ?? homeMarket?.yes_price ?? 0.5) * 100)}%` }} />
                  <div className="bg-purple-500 transition-all duration-500"
                    style={{ width: `${Math.round((awayMarket?.last_price ?? awayMarket?.yes_price ?? 0.5) * 100)}%` }} />
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span className="text-blue-400 font-medium">
                    {homeMarket?.name} &nbsp;{formatPercent(homeMarket?.last_price ?? homeMarket?.yes_price ?? 0.5)}
                  </span>
                  <span className="text-gray-600 text-[10px]">implied win prob</span>
                  <span className="text-purple-400 font-medium">
                    {formatPercent(awayMarket?.last_price ?? awayMarket?.yes_price ?? 0.5)}&nbsp; {awayMarket?.name}
                  </span>
                </div>
              </div>

              {/* Edge summary row */}
              <div className="grid grid-cols-3 gap-2 text-xs text-center pt-2 border-t border-gray-800">
                <div>
                  <div className="text-gray-500">Market Mid</div>
                  <div className="text-blue-400 font-mono font-semibold">
                    {formatPercent(homeMarket?.yes_price ?? 0.5)}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">Edge</div>
                  <div className={`font-mono font-bold ${
                    (signal?.edge ?? 0) >= 0.03  ? 'text-green-400' :
                    (signal?.edge ?? 0) <= -0.03 ? 'text-red-400'   : 'text-gray-400'
                  }`}>
                    {(signal?.edge ?? 0) >= 0 ? '+' : ''}{formatPercent(signal?.edge ?? 0)}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">Signal</div>
                  <Badge className={`text-[10px] ${getSignalColor(signal?.signal_type)}`}>
                    {signal?.signal_type || 'N/A'}
                  </Badge>
                </div>
              </div>
            </div>

            {/* Charts */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <h3 className="text-sm font-semibold">Probability Charts</h3>
                  {lastFetched && (
                    <div className="flex items-center gap-1.5 text-xs text-gray-500">
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
                      </span>
                      <span>Live &middot; updated {lastFetched.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone: 'America/New_York' })} EST &middot; every 1 min</span>
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  {['5m', '15m', 'full'].map((tf) => (
                    <Button key={tf} variant={chartTimeframe === tf ? 'default' : 'ghost'}
                      size="sm" onClick={() => setChartTimeframe(tf)} className="text-xs">
                      {tf === 'full' ? 'Full' : tf}
                    </Button>
                  ))}
                </div>
              </div>
              {chartData.probability_data.length < 2 ? (
                <div className="h-40 flex items-center justify-center text-muted-foreground text-sm">
                  <div className="text-center">
                    <Clock className="w-6 h-6 mx-auto mb-2 opacity-50" />
                    <p>Accumulating live data points…</p>
                    <p className="text-xs mt-1">Polling every 10 seconds</p>
                  </div>
                </div>
              ) : (
                <Tabs defaultValue="probability" className="space-y-4">
                  <TabsList className="bg-gray-800">
                    <TabsTrigger value="probability">Market vs Fair</TabsTrigger>
                    <TabsTrigger value="edge">Edge</TabsTrigger>
                    <TabsTrigger value="volatility">Volatility</TabsTrigger>
                  </TabsList>
                  <TabsContent value="probability">
                    <ProbabilityChart data={chartData.probability_data} timeframe={chartTimeframe} />
                  </TabsContent>
                  <TabsContent value="edge">
                    <EdgeChart data={chartData.probability_data} />
                  </TabsContent>
                  <TabsContent value="volatility">
                    <VolatilityChart data={chartData.volatility_data} />
                  </TabsContent>
                </Tabs>
              )}
            </div>

            {/* Signal + Intelligence */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className={`rounded-xl border p-4 ${getSignalColor(signal?.signal_type)} bg-opacity-10 border-opacity-30`}>
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="text-sm font-semibold">Trading Signal</h3>
                    <Badge className={`mt-1 ${getSignalColor(signal?.signal_type)}`}>
                      {signal?.signal_type || 'N/A'}
                    </Badge>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-gray-400">Signal Score</div>
                    <div className="text-2xl font-bold">{Math.round(signal?.signal_score ?? 50)}</div>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <span className="text-gray-500 text-xs">Risk Tier</span>
                    <div className={`font-medium capitalize ${getRiskTierColor(signal?.risk_tier)}`}>
                      {signal?.risk_tier || 'N/A'}
                    </div>
                  </div>
                  <div>
                    <span className="text-gray-500 text-xs">Action</span>
                    <div className={`font-medium text-xs ${getActionColor(signal?.recommended_action)}`}>
                      {signal?.recommended_action || 'WAIT'}
                    </div>
                  </div>
                  <div>
                    <span className="text-gray-500 text-xs">Size</span>
                    <div className="font-medium">{formatCurrency(signal?.recommended_size ?? 0)}</div>
                  </div>
                </div>
              </div>
              <IntelligencePanel intelligence={intelligence} isClutch={isClutch} />
            </div>

            {/* Live Strategy Status Grid */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Info className="w-4 h-4 text-blue-400" />Live Strategy Status
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {STRATEGIES.map((strat) => {
                  const ev      = strategyEvaluations.find((e) => e.strategy.id === strat.id);
                  const matched = ev?.matched || false;
                  const c       = colorMap[strat.color];
                  return (
                    <div key={strat.id} className={`rounded-lg border p-3 ${
                      matched ? `${c.border} ${c.bg}` : 'border-gray-700 bg-gray-800/30'
                    }`}>
                      <div className={`flex items-center gap-2 text-xs font-semibold mb-2 ${matched ? c.text : 'text-gray-500'}`}>
                        {matched ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                        {strat.name}
                      </div>
                      <div className="space-y-1">
                        {ev?.ruleResults.map((r) => (
                          <div key={r.label} className={`flex items-center gap-1 text-xs ${r.passed ? 'text-gray-300' : 'text-gray-600'}`}>
                            {r.passed
                              ? <CheckCircle2 className="w-3 h-3 text-green-500 flex-shrink-0" />
                              : <XCircle      className="w-3 h-3 text-red-800  flex-shrink-0" />}
                            {r.label}
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Positions */}
            <TradesList
              gameId={gameId}
              refreshKey={tradesKey}
              onCloseRequest={(trade) => setExitTarget(trade)}
            />
          </div>

          {/* ── Sidebar ───────────────────────────────────────────────────── */}
          <div className="space-y-4">
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 sticky top-20 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <Zap className="w-4 h-4 text-yellow-500" />Trade Panel
                </h3>
                <Badge className="bg-yellow-900/50 text-yellow-400 border border-yellow-700 text-xs">Paper</Badge>
              </div>

              {/* Context line */}
              {selectedMarket && (
                <div className="text-xs text-gray-400">
                  <span className="text-gray-500">{game?.title}</span>
                  <div className={`font-semibold mt-0.5 ${
                    tradeDirection === 'buy' ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {tradeDirection === 'buy' ? 'Buy' : 'Sell'} {tradeSide.toUpperCase()} · {selectedMarket.team_name || selectedMarket.name}
                  </div>
                </div>
              )}

              <div className="space-y-3">
                {/* Team Selection Cards */}
                <div className="grid grid-cols-2 gap-2">
                  {[{ market: homeMarket, outcome: 'home' }, { market: awayMarket, outcome: 'away' }].map(({ market: m, outcome }) => (
                    <div
                      key={outcome}
                      onClick={() => setTradeMarketOutcome(outcome)}
                      className={`p-3 rounded-lg border cursor-pointer transition-all ${
                        tradeMarketOutcome === outcome
                          ? 'border-blue-500 bg-blue-900/30 ring-1 ring-blue-500'
                          : 'border-gray-700 bg-gray-800/50 hover:border-gray-600'
                      }`}
                    >
                      <div className="font-semibold text-sm mb-2 truncate">
                        {m?.team_name || m?.name || outcome}
                      </div>
                      <div className="grid grid-cols-3 gap-1 text-xs text-center">
                        <div>
                          <div className="text-gray-500 text-[10px]">Bid</div>
                          <div className="text-green-400 font-mono">{((m?.yes_bid ?? 0) * 100).toFixed(0)}¢</div>
                        </div>
                        <div>
                          <div className="text-gray-500 text-[10px]">Mid</div>
                          <div className="text-white font-mono">{((m?.yes_price ?? 0) * 100).toFixed(0)}¢</div>
                        </div>
                        <div>
                          <div className="text-gray-500 text-[10px]">Ask</div>
                          <div className="text-red-400 font-mono">{((m?.yes_ask ?? 0) * 100).toFixed(0)}¢</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Buy / Sell pill toggle */}
                <div className="flex rounded-lg bg-gray-800 p-0.5 gap-0.5">
                  {['buy', 'sell'].map((dir) => (
                    <button
                      key={dir}
                      onClick={() => setTradeDirection(dir)}
                      className={`flex-1 py-1.5 rounded-md text-sm font-semibold transition-all capitalize ${
                        tradeDirection === dir
                          ? dir === 'buy'
                            ? 'bg-green-600 text-white shadow'
                            : 'bg-red-600 text-white shadow'
                          : 'text-gray-400 hover:text-gray-200'
                      }`}
                    >
                      {dir.charAt(0).toUpperCase() + dir.slice(1)}
                    </button>
                  ))}
                </div>

                {/* YES / NO price buttons */}
                {selectedMarket && (() => {
                  const yesPriceCents = Math.round((selectedMarket.yes_ask ?? 0) * 100);
                  const noPriceCents  = 100 - Math.round((selectedMarket.yes_bid ?? 0) * 100);
                  return (
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        onClick={() => setTradeSide('yes')}
                        className={`py-2.5 rounded-full text-sm font-bold border transition-all ${
                          tradeSide === 'yes'
                            ? 'border-green-400 text-green-400 bg-green-400/20 ring-1 ring-green-400/50'
                            : 'border-green-700 text-green-600 bg-transparent hover:border-green-500 hover:text-green-400'
                        }`}
                      >
                        Yes &nbsp;<span className="font-mono">{yesPriceCents}¢</span>
                      </button>
                      <button
                        onClick={() => setTradeSide('no')}
                        className={`py-2.5 rounded-full text-sm font-bold border transition-all ${
                          tradeSide === 'no'
                            ? 'border-red-400 text-red-400 bg-red-400/20 ring-1 ring-red-400/50'
                            : 'border-red-700 text-red-600 bg-transparent hover:border-red-500 hover:text-red-400'
                        }`}
                      >
                        No &nbsp;<span className="font-mono">{noPriceCents}¢</span>
                      </button>
                    </div>
                  );
                })()}

                {/* Dollar amount input */}
                <div className="rounded-lg border border-gray-700 bg-gray-800/60 p-3">
                  <div className="flex items-center justify-between mb-1">
                    <Label className="text-xs text-gray-400">Amount</Label>
                    <div className="flex items-center gap-1">
                      <span className="text-gray-400 text-sm">$</span>
                      <input
                        type="number"
                        min="1"
                        step="1"
                        placeholder="0"
                        value={tradeDollarAmount}
                        onChange={(e) => setTradeDollarAmount(e.target.value)}
                        className="bg-transparent text-white text-right text-lg font-semibold w-24 outline-none placeholder-gray-600"
                      />
                    </div>
                  </div>
                  {signal?.analytics && (
                    <div className="text-[11px] text-green-400">
                      Edge: {((signal?.edge ?? 0) >= 0 ? '+' : '')}{((signal?.edge ?? 0) * 100).toFixed(1)}%
                    </div>
                  )}
                </div>

                {/* Odds + Payout */}
                {(() => {
                  const dollarAmt = parseFloat(tradeDollarAmount) || 0;
                  if (!dollarAmt || !selectedMarket) return null;
                  const entryP = estimatedEntryPrice;
                  const odds   = Math.round(entryP * 100);
                  const payout = entryP > 0 ? dollarAmt / entryP : 0;
                  const profit = payout - dollarAmt;
                  return (
                    <div className="rounded-lg border border-gray-700 bg-gray-800/40 divide-y divide-gray-700/60">
                      <div className="flex items-center justify-between px-3 py-2 text-sm">
                        <span className="text-gray-400">Odds</span>
                        <span className="text-white font-medium">{odds}% chance</span>
                      </div>
                      <div className="flex items-center justify-between px-3 py-2 text-sm">
                        <span className="text-gray-400">Payout if {tradeSide.toUpperCase()}</span>
                        <span className="text-green-400 font-bold">${payout.toFixed(2)}</span>
                      </div>
                      <div className="flex items-center justify-between px-3 py-2 text-sm">
                        <span className="text-gray-400">Profit if {tradeSide.toUpperCase()}</span>
                        <span className="text-emerald-400 font-bold">+${profit.toFixed(2)}</span>
                      </div>
                    </div>
                  );
                })()}

                {/* Place Order button */}
                <Button
                  className="w-full bg-green-600 hover:bg-green-500 text-white font-bold h-11 text-sm rounded-lg"
                  onClick={() => setTradeDialogOpen(true)}
                  disabled={tradeLoading || (!tradeDollarAmount && tradeQuantity < 1)}
                >
                  {tradeLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Place Order'}
                </Button>
              </div>

              {tradeResult && (
                <div className={`p-2 rounded-lg text-xs ${
                  tradeResult.success ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
                }`}>
                  {tradeResult.message}
                </div>
              )}

              {/* Auto-Edge Panel */}
              <div className="border-t border-gray-700 pt-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold flex items-center gap-2">
                    <Bot className="w-4 h-4 text-purple-400" />Auto-Edge
                  </span>
                  <button
                    onClick={() => setAutoTradeEnabled((v) => !v)}
                    className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors ${
                      autoTradeEnabled ? 'bg-purple-600' : 'bg-gray-600'
                    }`}
                  >
                    <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${
                      autoTradeEnabled ? 'translate-x-6' : 'translate-x-1'
                    }`} />
                  </button>
                </div>
                <p className="text-xs text-gray-500">
                  Automatically places a paper order on the home market when edge exceeds the threshold.
                </p>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <Label className="text-xs text-gray-400">Min Edge (%)</Label>
                    <Input type="number" value={edgeThreshold}
                      onChange={(e) => setEdgeThreshold(parseFloat(e.target.value) || 1)}
                      className="bg-gray-800 border-gray-700 h-8 text-sm" min={0.5} max={50} step={0.5}
                      disabled={!autoTradeEnabled} />
                  </div>
                  <div>
                    <Label className="text-xs text-gray-400">Auto Qty</Label>
                    <Input type="number" value={autoTradeQty}
                      onChange={(e) => setAutoTradeQty(parseInt(e.target.value) || 1)}
                      className="bg-gray-800 border-gray-700 h-8 text-sm" min={1} max={50}
                      disabled={!autoTradeEnabled} />
                  </div>
                </div>
                <div className={`p-2 rounded-lg text-xs flex items-center justify-between ${
                  !autoTradeEnabled ? 'bg-gray-800/50 text-gray-500'
                  : autoTradeReady  ? 'bg-purple-900/40 text-purple-300 border border-purple-700 animate-pulse'
                  : 'bg-gray-800/50 text-gray-400'
                }`}>
                  <span>Current edge:</span>
                  <span className="font-bold">
                    {currentEdgePct.toFixed(1)}%
                    {autoTradeEnabled ? ` / ${edgeThreshold}% needed` : ' (paused)'}
                  </span>
                </div>

                {autoTradeLog.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-xs text-gray-500 font-medium">Execution log</p>
                    <div className="max-h-32 overflow-y-auto space-y-1">
                      {autoTradeLog.map((entry) => (
                        <div key={entry.id} className={`flex items-center justify-between px-2 py-1 rounded text-xs ${
                          entry.success ? 'bg-green-900/20 text-green-400' : 'bg-red-900/20 text-red-400'
                        }`}>
                          <span className="flex items-center gap-1">
                            {entry.success
                              ? <CheckCircle2 className="w-3 h-3" />
                              : <XCircle className="w-3 h-3" />}
                            {new Date(entry.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'America/New_York', timeZoneName: 'short' })}
                          </span>
                          <span>{entry.message || `${entry.side} ${entry.qty}c @ ${entry.edge}% edge`}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Trade Confirmation Dialog ─────────────────────────────────────── */}
      <Dialog open={tradeDialogOpen} onOpenChange={setTradeDialogOpen}>
        <DialogContent className="bg-gray-900 border-gray-800 max-w-md max-h-[90vh] flex flex-col overflow-hidden">
          <DialogHeader>
            <DialogTitle>Confirm Paper Order</DialogTitle>
            <DialogDescription>Review strategy match before submitting.</DialogDescription>
          </DialogHeader>
          <div className="py-3 space-y-4 text-sm overflow-y-auto flex-1 pr-1">
            <div className="space-y-2 p-3 bg-gray-800/50 rounded-lg text-xs">
              <div className="flex justify-between">
                <span className="text-gray-400">Team:</span>
                <span className="font-semibold text-white">
                  {selectedMarket?.team_name || selectedMarket?.name}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Side:</span>
                <span className={`font-bold ${tradeSide === 'yes' ? 'text-emerald-400' : 'text-red-400'}`}>
                  {tradeSide.toUpperCase()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Direction:</span>
                <span className="font-medium">{tradeDirection.toUpperCase()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Order Type:</span>
                <span className="font-medium text-blue-400">MARKET</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Quantity:</span>
                <span className="font-medium">{tradeQuantity} contracts</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Est. Fill Price:</span>
                <span className="font-medium">{(estimatedEntryPrice * 100).toFixed(0)}¢</span>
              </div>
              <div className="flex justify-between border-t border-gray-700 pt-2">
                <span className="text-gray-400">Total Cost:</span>
                <span className="font-bold text-white">
                  ${(estimatedEntryPrice * tradeQuantity).toFixed(2)}
                </span>
              </div>
            </div>
            <div>
              <p className="text-xs text-gray-400 font-medium mb-2 flex items-center gap-1">
                <Info className="w-3 h-3" />Strategy Analysis
              </p>
              <StrategyMatchPanel evaluations={strategyEvaluations} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTradeDialogOpen(false)}>Cancel</Button>
            <Button
              onClick={() => { handleTrade(); setTradeDialogOpen(false); }}
              disabled={tradeLoading}
            >
              {tradeLoading
                ? <><Loader2 className="w-4 h-4 animate-spin mr-1" />Submitting…</>
                : matchedStrategies.length > 0 ? 'Submit Order' : 'Submit Anyway'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Exit Position Dialog ──────────────────────────────────────────── */}
      <Dialog open={!!exitTarget} onOpenChange={() => setExitTarget(null)}>
        <DialogContent className="bg-gray-900 border-gray-800 max-w-sm">
          <DialogHeader>
            <DialogTitle>Exit Position</DialogTitle>
            <DialogDescription>Close this position at the current market price.</DialogDescription>
          </DialogHeader>
          {exitTarget && (
            <div className="py-3 space-y-2 text-sm">
              <div className="space-y-2 p-3 bg-gray-800/50 rounded-lg text-xs">
                <div className="flex justify-between">
                  <span className="text-gray-400">Team:</span>
                  <span className="font-semibold text-white">{exitTarget.market_name || exitTarget.team_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Position:</span>
                  <span className={`font-bold ${exitTarget.side === 'yes' ? 'text-emerald-400' : 'text-red-400'}`}>
                    {exitTarget.direction?.toUpperCase()} {exitTarget.side?.toUpperCase()} × {exitTarget.quantity}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Entry Price:</span>
                  <span className="font-mono">{((exitTarget.entry_price || 0) * 100).toFixed(0)}¢</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Exit Price (market):</span>
                  <span className="font-mono text-blue-400">{((exitTarget.current_price || 0) * 100).toFixed(0)}¢</span>
                </div>
                <div className={`flex justify-between font-bold border-t border-gray-700 pt-2 ${
                  (exitTarget.pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                }`}>
                  <span>Realised P&L:</span>
                  <span className="font-mono">
                    {(exitTarget.pnl || 0) >= 0 ? '+' : ''}${(exitTarget.pnl || 0).toFixed(2)}
                  </span>
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setExitTarget(null)}>Cancel</Button>
            <Button
              className="bg-red-700 hover:bg-red-600"
              onClick={handleExitConfirm}
              disabled={exitLoading}
            >
              {exitLoading
                ? <><Loader2 className="w-4 h-4 animate-spin mr-1" />Closing…</>
                : 'Close Position'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default GameDetail;
