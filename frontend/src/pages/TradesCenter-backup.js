/**
 * TradesCenter.jsx
 * ─────────────────────────────────────────────────────────────────────────────
 * Full trade blotter — reads from the database via tradeService.
 * Route: <Route path="/trades" element={<TradesCenter />} />
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from '../components/ui/dialog';
import {
  RefreshCw, Activity, DollarSign, Search, Filter, FileText,
  BarChart3, Target, Trash2, X, TrendingUp, TrendingDown,
  Download, AlertTriangle, Loader2, ChevronDown, ChevronUp,
  Shield, Clock, ArrowUpRight, ArrowDownRight, Zap, Info,
} from 'lucide-react';
import {
  fetchTrades, closeTrade, deleteTrade, calcPortfolioStats, computePnl,
} from '../services/tradeService';

// ─────────────────────────────────────────────────────────────────────────────
// KALSHI LIVE PRICE FETCH
// ─────────────────────────────────────────────────────────────────────────────
const KALSHI_BASE = 'https://api.elections.kalshi.com/v1';

function buildKalshiUrl(eventTicker) {
  const datePattern = /^([A-Z]+)-(\d{2}[A-Z]{3}.+)$/;
  const match = eventTicker.match(datePattern);
  if (!match) return null;
  return `${KALSHI_BASE}/series/${match[1]}/events/${eventTicker}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────────────────
// Module-level constant — not a reactive value, never needs to be a hook dependency
const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

const fmtUsd = (n) => {
  const v = Number(n) || 0;
  return (v >= 0 ? '+$' : '-$') + Math.abs(v).toFixed(2);
};
const fmtPct  = (n) => (n >= 0 ? '+' : '') + Number(n).toFixed(1) + '%';
const pnlCls  = (n) => (n > 0 ? 'text-emerald-400' : n < 0 ? 'text-red-400' : 'text-gray-400');
const pnlBg   = (n) =>
  n > 0 ? 'bg-emerald-900/10 border-emerald-800/40'
  : n < 0 ? 'bg-red-900/10 border-red-800/40'
  : 'bg-gray-800/20 border-gray-700/40';

const fmtTime = (ts) =>
  ts
    ? new Date(ts).toLocaleString('en-US', {
        month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit',
      })
    : '—';

const fmtTimeFull = (ts) =>
  ts
    ? new Date(ts).toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      })
    : '—';

const OPEN_STATUSES   = new Set(['open', 'active', 'pending', 'working', 'filled']);
const CLOSED_STATUSES = new Set(['closed', 'cancelled', 'expired', 'settled']);

// Open = no closed_at or close_date (null, undefined, or empty)
// Closed = has closed_at or close_date
const isOpen   = (t) => {
  const hasClosed_at = t.closed_at !== null && t.closed_at !== undefined && t.closed_at !== '';
  const hasClose_date = t.close_date !== null && t.close_date !== undefined && t.close_date !== '';
  return !hasClosed_at && !hasClose_date;
};
const isClosed = (t) => {
  const hasClosed_at = t.closed_at !== null && t.closed_at !== undefined && t.closed_at !== '';
  const hasClose_date = t.close_date !== null && t.close_date !== undefined && t.close_date !== '';
  return hasClosed_at || hasClose_date;
};

// ─────────────────────────────────────────────────────────────────────────────
// MODEL CONFIG
// ─────────────────────────────────────────────────────────────────────────────
const MODEL_CONFIG = {
  model_a_disciplined: {
    name: 'Model A',
    subtitle: 'Disciplined Edge Trader',
    color: 'emerald',
    icon: Target,
  },
  model_b_high_frequency: {
    name: 'Model B',
    subtitle: 'High Frequency Hunter',
    color: 'blue',
    icon: TrendingUp,
  },
  model_c_institutional: {
    name: 'Model C',
    subtitle: 'Institutional Risk-First',
    color: 'purple',
    icon: Shield,
  },
};

const MODEL_RULES = {
  model_a_disciplined: {
    name: 'Model A - Disciplined Edge Trader',
    entry: { minEdge: '≥ 5.0%', minSignal: '≥ 60', profitTarget: '15%', stopLoss: '10%', maxPosition: '5% of capital', dailyLossCap: '5%' },
    exit: {
      profitTarget: 15,
      stopLoss: 10,
      edgeCompressionThreshold: 2.0,
      timeBasedExitSeconds: 600,
      trailingStopPercent: 5,
      trimEnabled: true,
      trimProfitTarget: 10,
      trimPercentage: 50,
    },
  },
  model_b_high_frequency: {
    name: 'Model B - High Frequency Hunter',
    entry: { minEdge: '≥ 3.0%', minSignal: '≥ 45', profitTarget: '8%', stopLoss: '6%', maxPosition: '4% of capital', dailyLossCap: '8%' },
    exit: {
      profitTarget: 8,
      stopLoss: 6,
      edgeCompressionThreshold: 1.0,
      timeBasedExitSeconds: 300,
      trailingStopPercent: 3,
      trimEnabled: true,
      trimProfitTarget: 5,
      trimPercentage: 60,
    },
  },
  model_c_institutional: {
    name: 'Model C - Institutional Risk-First',
    entry: { minEdge: '≥ 7.0%', minSignal: '≥ 75', profitTarget: '20%', stopLoss: '8%', maxPosition: '3% of capital', dailyLossCap: '3%' },
    exit: {
      profitTarget: 20,
      stopLoss: 8,
      edgeCompressionThreshold: 3.0,
      timeBasedExitSeconds: 900,
      trailingStopPercent: 4,
      trimEnabled: false,
    },
  },
};

const getStrategyInfo = (trade) => {
  if (!trade.strategy) return { name: trade.strategy, color: 'gray', rules: null };
  const strategyId = trade.strategy.toLowerCase().replace(/ /g, '_');
  const modelRules = MODEL_RULES[strategyId] || MODEL_RULES.model_a_disciplined;
  const config     = MODEL_CONFIG[strategyId] || { name: trade.strategy, color: 'gray' };
  return { name: config.name, subtitle: config.subtitle, color: config.color, rules: modelRules, strategyId };
};

const getEntryExitExplanation = (trade) => {
  const entryReasons = [];
  if (trade.entry_signal_score) entryReasons.push(`Signal Score: ${trade.entry_signal_score}`);
  if (trade.entry_edge)         entryReasons.push(`Edge at Entry: ${(trade.entry_edge * 100).toFixed(1)}%`);
  if (trade.entry_reason)       entryReasons.push(trade.entry_reason);
  if (entryReasons.length === 0) entryReasons.push('Standard entry criteria met');

  // Convention: entry_price and current_price are raw YES prices. Flip both for NO trades.
  const _isNo2    = (trade.side || 'yes') === 'no';
  const _e2       = _isNo2 ? 1 - (trade.entry_price || 0) : (trade.entry_price || 0);
  const _x2raw    = trade.exit_price ?? trade.current_price ?? 0;
  const _x2       = _isNo2 ? 1 - _x2raw : _x2raw;
  const returnPct = _e2 > 0 ? ((_x2 - _e2) / _e2) * 100 : 0;

  // Get model-specific rules for exit logic
  const strategyId = trade.strategy ? trade.strategy.toLowerCase().replace(/ /g, '_') : 'model_a_disciplined';
  const modelRules = MODEL_RULES[strategyId] || MODEL_RULES.model_a_disciplined;
  const exitRules = modelRules.exit || {};
  const profitTarget = exitRules.profitTarget || 15;
  const stopLoss = exitRules.stopLoss || 10;

  // Get time elapsed in minutes
  const timeElapsedMinutes = trade.timestamp && trade.closed_at
    ? (new Date(trade.closed_at) - new Date(trade.timestamp)) / 60000
    : 0;
  const maxTimeSeconds = exitRules.timeBasedExitSeconds || 600;

  const exitReasons = [];
  if (trade.exit_reason)                               exitReasons.push(trade.exit_reason);
  else if (returnPct >= profitTarget)                  exitReasons.push(`Profit Target Hit (≥ ${profitTarget}%)`);
  else if (returnPct <= -stopLoss)                     exitReasons.push(`Stop Loss Triggered (≤ -${stopLoss}%)`);
  else if (timeElapsedMinutes * 60 >= maxTimeSeconds)  exitReasons.push(`Time-Based Exit (${Math.round(maxTimeSeconds / 60)} min)`);
  else if (exitRules.edgeCompressionThreshold && trade.exit_edge && trade.exit_edge < exitRules.edgeCompressionThreshold)
    exitReasons.push(`Edge Compression Exit (edge < ${exitRules.edgeCompressionThreshold}%)`);
  else if (trade.exit_rule)                            exitReasons.push(trade.exit_rule);
  if (exitReasons.length === 0)                        exitReasons.push(isOpen(trade) ? 'Position still open' : 'Closed at market');

  return { entry: entryReasons, exit: exitReasons };
};

// ─────────────────────────────────────────────────────────────────────────────
// KPI CARD
// ─────────────────────────────────────────────────────────────────────────────
const KPICard = ({ title, value, icon: Icon, variant = 'default', sub }) => {
  const colour = {
    default:  'text-foreground',
    positive: 'text-emerald-400',
    negative: 'text-red-400',
    warning:  'text-yellow-400',
    info:     'text-blue-400',
  }[variant] || 'text-foreground';
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wide">{title}</p>
            <p className={`text-2xl font-bold font-mono mt-1 ${colour}`}>{value}</p>
            {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
          </div>
          <div className={`p-3 rounded-lg bg-muted/50 ${colour}`}>
            <Icon className="w-5 h-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// MINI SPARKLINE BAR
// ─────────────────────────────────────────────────────────────────────────────
const MiniBar = ({ value, max }) => {
  const pct   = max > 0 ? Math.abs(value) / max : 0;
  const color = value >= 0 ? '#34d399' : '#f87171';
  return (
    <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
      <div className="h-full rounded-full transition-all duration-500"
        style={{ width: `${Math.min(pct * 100, 100)}%`, background: color }} />
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// DAILY STATS CARD
// ─────────────────────────────────────────────────────────────────────────────
const DailyStatsCard = ({ strategyId, data }) => {
  const config = MODEL_CONFIG[strategyId] || { name: strategyId, subtitle: '', icon: Activity };
  const Icon = config.icon;
  const totalPnl   = data?.total_pnl || 0;
  const dailyStats = data?.daily_stats || {};
  return (
    <Card className="border-2">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className="w-5 h-5" />
            <div>
              <CardTitle className="text-lg">{config.name}</CardTitle>
              <p className="text-xs text-muted-foreground">{config.subtitle}</p>
            </div>
          </div>
          <Badge variant="default">Daily Report</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="text-center pb-4 border-b border-border">
          <p className="text-xs text-muted-foreground uppercase">Daily P&L</p>
          <p className={`text-3xl font-bold font-mono mt-1 ${totalPnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {fmtUsd(totalPnl)}
          </p>
        </div>
        <div className="grid grid-cols-3 gap-3 text-xs text-center">
          <div>
            <p className="text-muted-foreground">Win Rate</p>
            <p className="font-bold mt-1">{dailyStats.win_rate != null ? fmtPct(dailyStats.win_rate) : '—'}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Trades</p>
            <p className="font-bold mt-1">{dailyStats.trade_count || 0}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Avg Trade</p>
            <p className="font-bold mt-1">{dailyStats.avg_win_loss != null ? fmtUsd(dailyStats.avg_win_loss) : '—'}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// TRADE DETAIL MODAL
// ─────────────────────────────────────────────────────────────────────────────
const TradeDetailModal = ({ trade, onClose }) => {
  if (!trade) return null;

  // Compute P&L live (same formula as the table row) so dollar + % always agree.
  // Only use stale trade.pnl for closed trades where current_price won't update.
  const closed     = isClosed(trade);
  const open       = isOpen(trade);
  const pnl = (() => {
    if (closed) return Number(trade.pnl) || 0;
    // Haven't received a live Kalshi price yet — defer to stored pnl
    if (!trade._hasLivePrice) return trade.pnl != null ? Number(trade.pnl) : null;
    return computePnl(trade.side || 'yes', trade.entry_price || 0, trade.current_price, trade.quantity || 1);
  })();

  // Convention: entry_price and current_price are raw YES market prices.
  // For NO trades, flip BOTH to get the actual contracted side value.
  // For closed trades use exit_price so returnPct reflects the actual exit, not a stale current_price.
  const isNo       = (trade.side || 'yes') === 'no';
  const effEntry   = isNo ? 1 - (trade.entry_price || 0) : (trade.entry_price || 0);
  const effCurRaw  = closed
    ? (trade.exit_price ?? trade.current_price ?? trade.entry_price ?? 0)
    : (trade.current_price ?? trade.entry_price ?? 0);
  const effCur     = isNo ? 1 - effCurRaw : effCurRaw;
  // returnPct is null for open trades until the first live Kalshi price arrives.
  const returnPct  = (() => {
    if (closed) return effEntry > 0 ? ((effCur - effEntry) / effEntry) * 100 : 0;
    if (!trade._hasLivePrice) return null;
    return effEntry > 0 ? ((effCur - effEntry) / effEntry) * 100 : 0;
  })();

  // Display prices: flip BOTH entry and exit/current for NO trades to show actual contract values
  const entryC    = (effEntry * 100).toFixed(1);
  const curC      = (effCur   * 100).toFixed(1);
  const exitEffC  = trade.exit_price != null
    ? ((isNo ? 1 - trade.exit_price : trade.exit_price) * 100).toFixed(1) : null;
  const exitOrCur = exitEffC ?? curC;
  const gameTitle  = trade.game_title ? String(trade.game_title).replace(/\s*@\s*/g, ' vs ') : '—';

  const strategyInfo  = getStrategyInfo(trade);
  const explanation   = getEntryExitExplanation(trade);
  const strategyColor = strategyInfo.color || 'gray';

  // Estimated P&L momentum — simple projection based on return%
  const momentum = returnPct > 0 ? 'positive' : returnPct < 0 ? 'negative' : 'neutral';
  const momentumLabel = momentum === 'positive'
    ? 'Trending toward profit target'
    : momentum === 'negative'
    ? 'Approaching stop-loss threshold'
    : 'Flat — no directional momentum';

  const costBasis = (trade.entry_price || 0) * (trade.quantity || 0);

  return (
    <Dialog open={!!trade} onOpenChange={onClose}>
      <DialogContent
        className="bg-gray-950 border border-gray-800 max-w-2xl w-full p-0 overflow-hidden rounded-xl flex flex-col [&>button]:hidden"
        style={{ maxHeight: '90vh' }}
      >

        {/* ── Modal Header ── */}
        <div className="bg-gray-900 border-b border-gray-800 px-6 py-4 flex-shrink-0">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <Badge className={`text-[10px] px-2 py-0.5 ${open
                  ? 'bg-blue-900/60 text-blue-300 border border-blue-700'
                  : 'bg-gray-800 text-gray-400 border border-gray-700'}`}>
                  {open && <Activity className="w-2.5 h-2.5 mr-1 inline animate-pulse" />}
                  {(trade.status || 'open').toUpperCase()}
                </Badge>
                <Badge className={`text-[10px] px-2 py-0.5 bg-${strategyColor}-900/40 text-${strategyColor}-300 border border-${strategyColor}-700/50`}>
                  {strategyInfo.name}
                </Badge>
                <span className="text-xs text-gray-500 font-mono">#{String(trade.id || '—')}</span>
              </div>
              {/* Game title prominent */}
              <h2 className="text-base font-semibold text-white leading-tight">
                {gameTitle}
              </h2>
              <p className="text-xs text-gray-400 mt-0.5">
                {trade.league || '—'}
                {trade.game_id && (
                  <> · <Link to={`/game/${trade.game_id}`} className="text-blue-500 hover:text-blue-400 underline" onClick={onClose}>{trade.game_id}</Link></>
                )}
              </p>
              {trade.game_id && (() => {
                const series = trade.game_id.split('-')[0].toLowerCase();
                const kalshiUrl = `https://kalshi.com/markets/${series}/${trade.game_id}`;
                return (
                  <button
                    onClick={() => window.open(kalshiUrl, '_new', 'noopener,noreferrer')}
                    className="mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-blue-700 text-blue-400 hover:bg-blue-900/30 hover:text-blue-300 text-xs font-bold transition-colors"
                    title="Open on Kalshi"
                  >
                    K <span className="font-normal opacity-70">Open on Kalshi ↗</span>
                  </button>
                );
              })()}
            </div>
            {/* Single close button */}
            <button onClick={onClose}
              className="text-gray-500 hover:text-white transition-colors p-1 rounded hover:bg-gray-800 flex-shrink-0 mt-0.5">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto">

          {/* ── Section 1: Entry Details ── */}
          <div className="px-6 pt-5 pb-4">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-1 h-4 bg-emerald-500 rounded-full" />
              <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-widest">Entry</h3>
            </div>

            {/* Trade position — which team, which side */}
            {(() => {
              // Parse the actual team name from market_name
              // market_name may look like: "Lakers", "Lakers ML", "Lakers -5.5", "Will Lakers win?"
              const rawMarket = trade.market_name || trade.market_id || '';
              // Strip common suffixes to isolate team name
              const teamName = rawMarket
                .replace(/\s+(ML|moneyline|spread|total|over|under|[-+]\d+(\.\d+)?)\s*$/i, '')
                .replace(/^(Will|Does|Can)\s+/i, '')
                .replace(/\s+(win|cover|score|advance|make).*/i, '')
                .trim() || rawMarket || '—';

              const isYes = trade.side === 'yes';
              const actionLabel = isYes
                ? `Bid YES on ${teamName}`
                : `Bid NO on ${teamName}`;
              const subLabel = isYes
                ? `You bet ${teamName} will win / cover`
                : `You bet ${teamName} will NOT win / cover`;

              return (
                <div className={`rounded-lg border p-4 mb-4 ${isYes ? 'bg-emerald-950/30 border-emerald-800/40' : 'bg-red-950/30 border-red-800/40'}`}>
                  <div className="flex items-start justify-between flex-wrap gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Team Bid On</p>
                      {/* Big team name */}
                      <p className="text-xl font-bold text-white leading-tight mb-2 truncate">{teamName}</p>
                      {/* Action row */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${
                          isYes
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                            : 'bg-red-500/20 text-red-300 border border-red-500/40'
                        }`}>
                          {isYes ? '▲' : '▼'} {trade.side?.toUpperCase()}
                        </span>
                        {trade.direction && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-gray-800 text-gray-300 border border-gray-700">
                            {trade.direction.toUpperCase()}
                          </span>
                        )}
                        {rawMarket !== teamName && (
                          <span className="text-[10px] text-gray-500 font-mono">{rawMarket}</span>
                        )}
                      </div>
                      <p className={`text-xs mt-2 font-medium ${isYes ? 'text-emerald-400' : 'text-red-400'}`}>
                        {subLabel}
                      </p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Qty</p>
                      <p className="text-2xl font-bold font-mono text-white">{trade.quantity ?? '—'}</p>
                      <p className="text-[10px] text-gray-500">contracts</p>
                    </div>
                  </div>
                </div>
              );
            })()}

            {/* Entry price strip */}
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Entry Price</p>
                  <p className="text-lg font-bold font-mono text-white">{entryC}¢</p>
                </div>
                <div>
                  <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Cost Basis</p>
                  <p className="text-sm font-mono text-white">${costBasis.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Entry Time</p>
                  <p className="text-xs font-mono text-gray-300">{fmtTimeFull(trade.timestamp)}</p>
                </div>
              </div>
            </div>

            {/* Strategy + entry reasons */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="bg-gray-900/60 border border-gray-800/60 rounded-lg p-3">
                <div className="flex items-center gap-1.5 mb-2">
                  <Zap className="w-3 h-3 text-gray-500" />
                  <span className="text-[10px] text-gray-500 uppercase tracking-wider">Strategy</span>
                </div>
                <p className="text-xs text-gray-200">{strategyInfo.name}</p>
                {strategyInfo.subtitle && <p className="text-[10px] text-gray-500 mt-0.5">{strategyInfo.subtitle}</p>}
              </div>
              <div className="bg-emerald-950/30 border border-emerald-800/30 rounded-lg p-3">
                <p className="text-[10px] text-emerald-500 uppercase tracking-wider mb-2 font-semibold">This Trade's Entry</p>
                <div className="space-y-1">
                  {explanation.entry.map((reason, idx) => (
                    <div key={idx} className="flex items-start gap-2">
                      <span className="text-emerald-500 text-xs mt-0.5">✓</span>
                      <span className="text-xs text-emerald-300">{reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Model Entry & Exit Rules */}
            {strategyInfo?.rules && (
              <div className="grid grid-cols-1 gap-3 mb-4">
                {/* Entry Rules from Model */}
                <div className="bg-blue-950/25 border border-blue-800/40 rounded-lg p-3">
                  <p className="text-[10px] text-blue-500 uppercase tracking-wider mb-2 font-semibold">Model Entry Rules</p>
                  <div className="space-y-1.5 text-[9px]">
                    <div className="flex items-start gap-2">
                      <span className="text-blue-400 mt-0.5">▸</span>
                      <div>
                        <p className="text-blue-300 font-semibold">Min Edge</p>
                        <p className="text-blue-200">{strategyInfo.rules.entry.minEdge}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-blue-400 mt-0.5">▸</span>
                      <div>
                        <p className="text-blue-300 font-semibold">Signal Score</p>
                        <p className="text-blue-200">{strategyInfo.rules.entry.minSignal}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-blue-400 mt-0.5">▸</span>
                      <div>
                        <p className="text-blue-300 font-semibold">Max Position</p>
                        <p className="text-blue-200">{strategyInfo.rules.entry.maxPosition}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-blue-400 mt-0.5">▸</span>
                      <div>
                        <p className="text-blue-300 font-semibold">Daily Loss Cap</p>
                        <p className="text-blue-200">{strategyInfo.rules.entry.dailyLossCap}</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Exit Rules from Model */}
                <div className="bg-amber-950/25 border border-amber-800/40 rounded-lg p-3">
                  <p className="text-[10px] text-amber-500 uppercase tracking-wider mb-2 font-semibold">Model Exit Rules</p>
                  <div className="space-y-1.5 text-[9px]">
                    <div className="flex items-start gap-2">
                      <span className="text-amber-400 mt-0.5">▸</span>
                      <div>
                        <p className="text-amber-300 font-semibold">Profit Target</p>
                        <p className="text-amber-200">{strategyInfo.rules.exit.profitTarget}%</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-amber-400 mt-0.5">▸</span>
                      <div>
                        <p className="text-amber-300 font-semibold">Stop Loss</p>
                        <p className="text-amber-200">{strategyInfo.rules.exit.stopLoss}%</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-amber-400 mt-0.5">▸</span>
                      <div>
                        <p className="text-amber-300 font-semibold">Time-Based Exit</p>
                        <p className="text-amber-200">{Math.round(strategyInfo.rules.exit.timeBasedExitSeconds / 60)} min</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-amber-400 mt-0.5">▸</span>
                      <div>
                        <p className="text-amber-300 font-semibold">Edge Compression Exit</p>
                        <p className="text-amber-200">{"< " + strategyInfo.rules.exit.edgeCompressionThreshold.toFixed(1)}%</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-amber-400 mt-0.5">▸</span>
                      <div>
                        <p className="text-amber-300 font-semibold">Trailing Stop</p>
                        <p className="text-amber-200">{strategyInfo.rules.exit.trailingStopPercent}%</p>
                      </div>
                    </div>
                    {strategyInfo.rules.exit.trimEnabled && (
                      <div className="flex items-start gap-2">
                        <span className="text-amber-400 mt-0.5">▸</span>
                        <div>
                          <p className="text-amber-300 font-semibold">Trim at {strategyInfo.rules.exit.trimProfitTarget}%</p>
                          <p className="text-amber-200">Sell {strategyInfo.rules.exit.trimPercentage}% of position</p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* ── Divider ── */}
          <div className="mx-6 border-t border-gray-800/80 border-dashed" />

          {/* ── Section 2: Exit / P&L ── */}
          <div className="px-6 py-5">
            <div className="flex items-center gap-2 mb-4">
              <div className={`w-1 h-4 rounded-full ${pnl != null ? (pnl >= 0 ? 'bg-emerald-500' : 'bg-red-500') : 'bg-gray-600'}`} />
              <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-widest">
                {closed ? 'Exit & Result' : 'Live P&L'}
              </h3>
            </div>

            {/* P&L big number */}
            <div className={`rounded-lg border p-4 mb-4 flex items-center justify-between flex-wrap gap-4 ${pnlBg(pnl)}`}>
              <div>
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                  {open ? 'Unrealised P&L' : 'Realised P&L'}
                </p>
                <div className="flex items-baseline gap-3">
                  {pnl === null
                    ? <span className="text-3xl font-bold font-mono text-gray-500">—</span>
                    : <>
                        <span className={`text-3xl font-bold font-mono ${pnlCls(pnl)}`}>{fmtUsd(pnl)}</span>
                        <span className={`text-sm font-mono ${pnlCls(returnPct)}`}>
                          {returnPct === null ? '—' : `(${fmtPct(returnPct)})`}
                        </span>
                      </>
                  }
                </div>
              </div>
              <div className="text-right">
                {(pnl == null || pnl >= 0)
                  ? <ArrowUpRight className="w-10 h-10 text-emerald-500/30 ml-auto" />
                  : <ArrowDownRight className="w-10 h-10 text-red-500/30 ml-auto" />}
              </div>
            </div>

            {/* Exit price + time */}
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                <div>
                  <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                    {closed ? 'Exit Price' : 'Current Price'}
                  </p>
                  <p className="text-lg font-bold font-mono text-white">{exitOrCur}¢</p>
                </div>
                <div>
                  <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Price Move</p>
                  <p className={`text-sm font-mono font-bold ${pnlCls(returnPct)}`}>
                    {returnPct >= 0 ? '+' : ''}{(Number(exitOrCur) - Number(entryC)).toFixed(1)}¢
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                    {closed ? 'Closed At' : 'Time Open'}
                  </p>
                  <p className="text-xs font-mono text-gray-300">
                    {closed ? fmtTimeFull(trade.closed_at) : fmtTimeFull(trade.timestamp)}
                  </p>
                </div>
              </div>
            </div>

            {/* Exit reason */}
            {closed && (
              <div className={`rounded-lg border p-3 mb-4 ${pnl >= 0
                ? 'bg-emerald-950/30 border-emerald-800/30'
                : 'bg-red-950/30 border-red-800/30'}`}>
                <p className={`text-[10px] uppercase tracking-wider mb-2 font-semibold ${pnl >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                  This Trade's Exit
                </p>
                <div className="space-y-1.5">
                  {/* Show stored exit reason if available (from auto-exit) */}
                  {trade.exit_reason ? (
                    <div className="flex items-start gap-2">
                      <span className={`text-xs mt-0.5 ${pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>✓</span>
                      <span className={`text-xs ${pnl >= 0 ? 'text-emerald-300' : 'text-red-300'}`}>{trade.exit_reason}</span>
                    </div>
                  ) : (
                    /* Otherwise show generated explanation */
                    explanation.exit.map((reason, idx) => (
                      <div key={idx} className="flex items-start gap-2">
                        <span className={`text-xs mt-0.5 ${pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>→</span>
                        <span className={`text-xs ${pnl >= 0 ? 'text-emerald-300' : 'text-red-300'}`}>{reason}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* Model Exit Rules */}
            {closed && strategyInfo?.rules && (
              <div className="bg-orange-950/25 border border-orange-800/40 rounded-lg p-3 mb-4">
                <p className="text-[10px] text-orange-500 uppercase tracking-wider mb-2 font-semibold">Model Exit Rules Summary</p>
                <div className="space-y-1.5 text-[9px]">
                  <div className="flex items-start gap-2">
                    <span className="text-orange-400 mt-0.5">▸</span>
                    <div>
                      <p className="text-orange-300 font-semibold">Profit Target</p>
                      <p className="text-orange-200">{strategyInfo.rules.exit.profitTarget}%</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-orange-400 mt-0.5">▸</span>
                    <div>
                      <p className="text-orange-300 font-semibold">Stop Loss</p>
                      <p className="text-orange-200">{strategyInfo.rules.exit.stopLoss}%</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-orange-400 mt-0.5">▸</span>
                    <div>
                      <p className="text-orange-300 font-semibold">Time-Based Exit</p>
                      <p className="text-orange-200">{Math.round(strategyInfo.rules.exit.timeBasedExitSeconds / 60)} min</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-orange-400 mt-0.5">▸</span>
                    <div>
                      <p className="text-orange-300 font-semibold">Trailing Stop</p>
                      <p className="text-orange-200">{strategyInfo.rules.exit.trailingStopPercent}%</p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Exit Condition Evaluation at Close */}
            {closed && (
              <div className="bg-purple-950/20 border border-purple-800/40 rounded-lg p-3 mb-4">
                <p className="text-[10px] text-purple-500 uppercase tracking-wider mb-3 font-semibold">Exit Conditions at Close</p>
                <div className="space-y-2 text-[10px]">
                  {/* Profit Target Status */}
                  <div className="border-l-2 border-purple-600 pl-2 py-1">
                    <div className="flex items-center gap-2">
                      <p className="text-purple-400 font-semibold">Profit Target:</p>
                      <p className="text-purple-300">{strategyInfo?.rules?.exit?.profitTarget || 15}%</p>
                      <span className={`text-[9px] ${returnPct >= (strategyInfo?.rules?.exit?.profitTarget || 15) ? 'text-emerald-400' : 'text-gray-500'}`}>
                        ({returnPct >= (strategyInfo?.rules?.exit?.profitTarget || 15) ? '✓ HIT' : '○ not hit'})
                      </span>
                    </div>
                    {returnPct < (strategyInfo?.rules?.exit?.profitTarget || 15) && (
                      <p className="text-gray-400 text-[9px] mt-1">Actual: {returnPct.toFixed(2)}%</p>
                    )}
                  </div>

                  {/* Stop Loss Status */}
                  <div className="border-l-2 border-red-600 pl-2 py-1">
                    <div className="flex items-center gap-2">
                      <p className="text-red-400 font-semibold">Stop Loss:</p>
                      <p className="text-red-300">{-(strategyInfo?.rules?.exit?.stopLoss || 10)}%</p>
                      <span className={`text-[9px] ${returnPct <= -(strategyInfo?.rules?.exit?.stopLoss || 10) ? 'text-red-400' : 'text-gray-500'}`}>
                        ({returnPct <= -(strategyInfo?.rules?.exit?.stopLoss || 10) ? '✓ HIT' : '○ not hit'})
                      </span>
                    </div>
                    {returnPct > -(strategyInfo?.rules?.exit?.stopLoss || 10) && (
                      <p className="text-gray-400 text-[9px] mt-1">Actual: {returnPct.toFixed(2)}%</p>
                    )}
                  </div>

                  {/* Time-Based Exit Status */}
                  <div className="border-l-2 border-blue-600 pl-2 py-1">
                    <div className="flex items-center gap-2">
                      <p className="text-blue-400 font-semibold">Time Exit ({Math.round((strategyInfo?.rules?.exit?.timeBasedExitSeconds || 600) / 60)} min):</p>
                      <p className="text-blue-300">{trade.timestamp && trade.closed_at 
                        ? `${Math.floor((new Date(trade.closed_at) - new Date(trade.timestamp)) / 60000)}min`
                        : 'N/A'}</p>
                    </div>
                  </div>

                  {/* Edge Compression Exit Status */}
                  {strategyInfo?.rules?.exit?.edgeCompressionThreshold && (
                    <div className="border-l-2 border-cyan-600 pl-2 py-1">
                      <div className="flex items-center gap-2">
                        <p className="text-cyan-400 font-semibold">Edge Compression:</p>
                        <p className="text-cyan-300">{"< " + (strategyInfo.rules.exit.edgeCompressionThreshold).toFixed(1)}%</p>
                        <span className={`text-[9px] ${trade.exit_edge && trade.exit_edge < strategyInfo.rules.exit.edgeCompressionThreshold ? 'text-cyan-400' : 'text-gray-500'}`}>
                          ({trade.exit_edge ? (trade.exit_edge < strategyInfo.rules.exit.edgeCompressionThreshold ? '✓ HIT' : '○ not hit') : 'N/A'})
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* P&L Momentum — for open trades */}
            {open && (
              <div className="bg-gray-900/60 border border-gray-800/60 rounded-lg p-3">
                <div className="flex items-center gap-1.5 mb-2">
                  <Info className="w-3 h-3 text-gray-500" />
                  <span className="text-[10px] text-gray-500 uppercase tracking-wider">Expected P&L Momentum</span>
                </div>
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${
                    momentum === 'positive' ? 'bg-emerald-400' :
                    momentum === 'negative' ? 'bg-red-400' : 'bg-gray-500'
                  }`} />
                  <p className="text-xs text-gray-300">{momentumLabel}</p>
                </div>
                {/* Visual momentum bar */}
                <div className="mt-3 grid grid-cols-3 gap-1 text-[9px] text-gray-600">
                  <span className="text-red-500">Stop Loss ({strategyInfo?.rules?.exit?.stopLoss ?? 'N/A'}%)</span>
                  <span className="text-center text-gray-600">Entry</span>
                  <span className="text-right text-emerald-500">Target ({strategyInfo?.rules?.exit?.profitTarget ?? 'N/A'}%)</span>
                </div>
                <div className="relative mt-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                  {/* Stop zone */}
                  <div className="absolute left-0 top-0 h-full w-1/4 bg-red-900/40" />
                  {/* Target zone */}
                  <div className="absolute right-0 top-0 h-full w-1/4 bg-emerald-900/40" />
                  {/* Current position indicator */}
                  <div
                    className={`absolute top-0 h-full w-1 rounded-full transition-all duration-700 ${pnlCls(returnPct).replace('text-', 'bg-')}`}
                    style={{
                      left: `${Math.min(Math.max(50 + (returnPct ?? 0) * 2, 2), 98)}%`,
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Modal Footer ── */}
        <div className="border-t border-gray-800 bg-gray-900/60 px-6 py-3 flex items-center justify-end flex-shrink-0">
          <Button variant="outline" size="sm" className="text-xs h-7" onClick={onClose}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// TRADE ROW
// ─────────────────────────────────────────────────────────────────────────────
const typeCls = {
  'auto-edge': 'bg-purple-700 text-white',
  signal:      'bg-blue-700 text-white',
  manual:      'bg-gray-700 text-gray-200',
  live:        'bg-orange-700 text-white',
};
const typeLbl = {
  'auto-edge': 'AUTO', signal: 'SIG', manual: 'MAN', live: 'LIVE',
};

const TradeRow = ({ trade, maxAbsPnl, onCloseRequest, onDelete, onSelect }) => {
  const navigate = useNavigate();

  // Build Kalshi market URL from game_id
  const kalshiMarketUrl = (() => {
    if (!trade.game_id) return null;
    const series = trade.game_id.split('-')[0].toLowerCase();
    return `https://kalshi.com/markets/${series}/${trade.game_id}`;
  })();

  // Format game date from trade timestamp
  const gameDateLabel = trade.timestamp
    ? new Date(trade.timestamp).toLocaleString('en-US', {
        month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
        timeZone: 'America/New_York',
      })
    : null;
  // Convention: entry_price and current_price are raw YES prices. Flip both for NO trades.
  const isNoSide  = (trade.side || 'yes') === 'no';
  const tEffEntry = isNoSide ? 1 - (trade.entry_price || 0) : (trade.entry_price || 0);
  const tCurRaw   = trade.current_price ?? trade.entry_price ?? 0;
  const tEffCur   = isNoSide ? 1 - tCurRaw : tCurRaw;
  // returnPct and pnl are null for open trades until the first live Kalshi price arrives,
  // so we can show "—" instead of a misleading +$0.00 / 0.0%.
  const returnPct = (() => {
    if (isClosed(trade)) return tEffEntry > 0 ? ((tEffCur - tEffEntry) / tEffEntry) * 100 : 0;
    if (!trade._hasLivePrice) return null;
    return tEffEntry > 0 ? ((tEffCur - tEffEntry) / tEffEntry) * 100 : 0;
  })();
  const pnl = (() => {
    // For closed trades use the stored final pnl; for open trades compute live
    if (isClosed(trade)) return trade.pnl || 0;
    // Haven't received a live Kalshi price yet — defer to stored pnl
    if (!trade._hasLivePrice) return trade.pnl ?? null;
    return computePnl(trade.side || 'yes', trade.entry_price || 0, trade.current_price, trade.quantity || 1);
  })();
  const entryC    = (tEffEntry * 100).toFixed(0);
  const curC      = (tEffCur   * 100).toFixed(0);
  const exitC     = trade.exit_price != null
    ? ((isNoSide ? 1 - trade.exit_price : trade.exit_price) * 100).toFixed(0) : null;
  const gameTitle = trade.game_title
    ? String(trade.game_title).replace(/\s*@\s*/g, ' vs ')
    : '—';
  const open = isOpen(trade);

  return (
    <tr
      className="border-b border-border/50 hover:bg-muted/30 transition-colors cursor-pointer group"
      onClick={() => onSelect(trade)}
    >
      {/* ID — tiny mono */}
      <td className="py-2.5 px-3 whitespace-nowrap">
        <span className="font-mono text-[10px] text-muted-foreground">
          {String(trade.id || '—').slice(0, 10)}…
        </span>
      </td>

      {/* Game Title — primary, highlighted */}
      <td className="py-2.5 px-3">
        <div className="flex flex-col gap-0.5">
          <span className="text-xs font-semibold text-white group-hover:text-blue-200 transition-colors block max-w-[220px] truncate">
            {gameTitle}
          </span>
          <div className="flex items-center gap-2">
            <Link
              to={`/game/${trade.game_id}`}
              className="text-[10px] text-blue-500 hover:text-blue-400 font-mono"
              onClick={(e) => e.stopPropagation()}
            >
              {trade.game_id || '—'}
            </Link>
            {gameDateLabel && (
              <span className="text-[10px] text-cyan-500 flex items-center gap-0.5">
                <Clock className="w-2.5 h-2.5" />{gameDateLabel}
              </span>
            )}
          </div>
        </div>
      </td>

      {/* Trade Position — team + side */}
      <td className="py-2.5 px-3 whitespace-nowrap">
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-gray-200 block max-w-[140px] truncate font-medium">
            {trade.market_name || trade.market_id || '—'}
          </span>
          <span className={`inline-flex items-center gap-1 text-[10px] font-bold ${
            trade.side === 'yes' ? 'text-emerald-400' : 'text-red-400'
          }`}>
            {trade.side === 'yes' ? '▲' : '▼'} {trade.direction?.toUpperCase()} {trade.side?.toUpperCase()}
          </span>
        </div>
      </td>

      {/* Type */}
      <td className="py-2.5 px-3 text-center whitespace-nowrap">
        <Badge className={`${typeCls[trade.type] || typeCls.manual} text-[10px] px-1.5 py-0`}>
          {typeLbl[trade.type] || 'MAN'}
        </Badge>
      </td>

      {/* Entry */}
      <td className="py-2.5 px-3 text-right font-mono text-xs text-muted-foreground whitespace-nowrap">{entryC}¢</td>

      {/* Cur / Exit */}
      <td className="py-2.5 px-3 text-right font-mono text-xs whitespace-nowrap">
        {isClosed(trade)
          ? <span className="text-gray-400">{exitC ?? '—'}¢</span>
          : <span className="text-white">{curC}¢</span>}
      </td>

      {/* Qty */}
      <td className="py-2.5 px-3 text-right font-mono text-xs whitespace-nowrap">{trade.quantity ?? '—'}</td>

      {/* Status */}
      <td className="py-2.5 px-3 text-center whitespace-nowrap">
        <Badge className={`text-[10px] px-1.5 py-0 ${
          open
            ? 'bg-blue-900/50 text-blue-300 border border-blue-700'
            : 'bg-gray-800 text-gray-500 border border-gray-700'
        }`}>
          {open && <Activity className="w-2.5 h-2.5 mr-0.5 inline animate-pulse" />}
          {(trade.status || 'open').toUpperCase()}
        </Badge>
      </td>

      {/* Strategy */}
      <td className="py-2.5 px-3 whitespace-nowrap">
        <span className="text-[10px] text-purple-400 italic">{trade.strategy || '—'}</span>
      </td>

      {/* P&L */}
      <td className="py-2.5 px-3 text-right whitespace-nowrap">
        <div className="flex flex-col items-end gap-1">
          {pnl === null
            ? <span className="font-mono font-bold text-sm text-gray-500">—</span>
            : <><span className={`font-mono font-bold text-sm ${pnlCls(pnl)}`}>{fmtUsd(pnl)}</span>
               <MiniBar value={pnl} max={maxAbsPnl} /></>
          }
        </div>
      </td>

      {/* Return % */}
      <td className="py-2.5 px-3 text-center whitespace-nowrap">
        {returnPct === null
          ? <span className="text-xs font-mono text-gray-500">—</span>
          : <span className={`text-xs font-mono ${pnlCls(returnPct)}`}>{fmtPct(returnPct)}</span>
        }
      </td>

      {/* Opened */}
      <td className="py-2.5 px-3 text-right text-[10px] text-gray-500 whitespace-nowrap">
        {fmtTime(trade.timestamp)}
      </td>

      {/* Closed */}
      <td className="py-2.5 px-3 text-right text-[10px] text-gray-500 whitespace-nowrap">
        {fmtTime(trade.closed_at)}
      </td>

      {/* Actions */}
      <td className="py-2.5 px-3 text-center whitespace-nowrap">
        <div className="flex items-center justify-center gap-1">
          {/* Kalshi K button */}
          {kalshiMarketUrl && (
            <Button size="sm" variant="ghost"
              className="h-6 px-1.5 text-[10px] font-bold text-blue-400 hover:text-blue-300 hover:bg-blue-900/20 border border-blue-800"
              onClick={(e) => { e.stopPropagation(); window.open(kalshiMarketUrl, '_new', 'noopener,noreferrer'); }}
              title="Open on Kalshi">
              K
            </Button>
          )}
          {open && (
            <Button size="sm" variant="ghost"
              className="h-6 px-1.5 text-[10px] text-yellow-400 hover:text-yellow-300 hover:bg-yellow-900/20"
              onClick={(e) => { e.stopPropagation(); onCloseRequest(trade); }}>
              <X className="w-2.5 h-2.5 mr-0.5" />Exit
            </Button>
          )}
          <Button size="sm" variant="ghost"
            className="h-6 px-1.5 text-[10px] text-red-400 hover:text-red-300 hover:bg-red-900/20"
            onClick={(e) => { e.stopPropagation(); onDelete(trade.id); }}>
            <Trash2 className="w-2.5 h-2.5" />
          </Button>
          <span className="text-[10px] text-gray-600 group-hover:text-gray-400 transition-colors ml-1">
            <Info className="w-3 h-3" />
          </span>
        </div>
      </td>
    </tr>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SORT HEADER
// ─────────────────────────────────────────────────────────────────────────────
const SortTh = ({ label, k, sortKey, sortDir, onSort, className = '' }) => (
  <th
    className={`py-3 px-3 text-[10px] uppercase tracking-wider text-muted-foreground font-medium cursor-pointer hover:text-foreground select-none whitespace-nowrap ${className}`}
    onClick={() => onSort(k)}
  >
    <span className="flex items-center gap-1">
      {label}
      {sortKey === k && (
        sortDir === 'asc'
          ? <ChevronUp className="w-3 h-3" />
          : <ChevronDown className="w-3 h-3" />
      )}
    </span>
  </th>
);

// ─────────────────────────────────────────────────────────────────────────────
// MAIN
// ─────────────────────────────────────────────────────────────────────────────
export default function TradesCenter() {
  const [trades, setTrades]         = useState([]);
  const [stats, setStats]           = useState({});
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [dailyReport, setDailyReport] = useState(null);

  // Filters
  const [typeFilter, setTypeFilter]     = useState('all');
  const [statusFilter, setStatusFilter] = useState('open'); // Default to showing open trades
  const [sideFilter, setSideFilter]     = useState('all');
  const [search, setSearch]             = useState('');
  const [dateRange, setDateRange]       = useState('all');
  const [sortKey, setSortKey]           = useState('timestamp');
  const [sortDir, setSortDir]           = useState('desc');

  // UI
  const [selectedTrade, setSelectedTrade] = useState(null);
  const [exitTarget, setExitTarget]       = useState(null);
  const [exitLoading, setExitLoading]     = useState(false);
  const [deleteTarget, setDeleteTarget]   = useState(null);
  const [closeAllLoading, setCloseAllLoading] = useState(false);
  const [closeAllConfirm, setCloseAllConfirm] = useState(false);
  const [currentPage, setCurrentPage]     = useState(1);
  const [pageSize, setPageSize]           = useState(50);
  const [autoExitStats, setAutoExitStats] = useState({ totalExited: 0, lastExitTime: null });

  // ⚠️ Track trades that were just loaded - skip their first exit check
  const newlyLoadedTradesRef = useRef(new Set());
  
  // Per-game cooldown tracking for Kalshi API (429 errors)
  const perGameCooldownRef = useRef({});
  const fetchChunkIndexRef = useRef(0);
  const CHUNK_SIZE = 6;

  // ── Trigger a backend trading cycle (fire-and-forget) ──────────────────
  // Cooldown ref prevents hammering the endpoint
  const lastCycleTriggerRef = useRef(0);
  const triggerTradingCycle = useCallback((force = false) => {
    const now = Date.now();
    if (!force && now - lastCycleTriggerRef.current < 30_000) return; // 30s cooldown
    lastCycleTriggerRef.current = now;
    fetch(`${API_BASE}/api/autonomous/run_cycle`, { method: 'POST' })
      .then(r => r.json())
      .then(d => console.log('[TradesCenter] Trading cycle triggered:', d.message))
      .catch(e => console.warn('[TradesCenter] Trading cycle trigger failed:', e));
  }, []);

  // ── Load ─────────────────────────────────────────────────────────────────
  const refresh = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const data = await fetchTrades(1000);
      console.log('TradesCenter - Trades loaded:', {
        total: data.length,
        open: data.filter(isOpen).length,
        closed: data.filter(isClosed).length,
        details: data.map(t => ({
          id: t.id,
          game_id: t.game_id,
          closed_at: t.closed_at,
          close_date: t.close_date,
          status: t.status
        }))
      });
      
      // ⚠️ Mark all newly loaded open trades to skip first exit check
      const openTradeIds = data.filter(isOpen).map(t => t.id);
      openTradeIds.forEach(id => newlyLoadedTradesRef.current.add(id));
      
      setTrades(data);
      setStats(calcPortfolioStats(data));
      const today = new Date().toISOString().split('T')[0];
      try {
        const res = await fetch(`${API_BASE}/api/strategies/report/daily?date=${today}`);
        if (res.ok) setDailyReport(await res.json());
      } catch { /* silently ignore */ }
      setLastUpdate(new Date());

      // If no open trades exist after loading, kick off a backend trading cycle
      // so new trades appear automatically without navigating to the Terminal page.
      if (data.filter(isOpen).length === 0) {
        triggerTradingCycle();
      }
    } catch (err) { setError(err.message); }
    if (!silent) setLoading(false);
  }, [triggerTradingCycle]);

  // ── Auto-Exit Logic ──────────────────────────────────────────────────────
  // VALIDATION MODE: Model A & B active. Stop loss fires at -10%.
  // Max concurrent open trades: 10 per model (20 total).
  const checkAutoExits = useCallback(async (tradesToCheck) => {
    if (!tradesToCheck.length) return;
    
    const openTrades = tradesToCheck.filter(isOpen);
    if (!openTrades.length) return;
    
    let autoExited = 0;
    
    for (const trade of openTrades) {
      // ⚠️ CRITICAL: Skip trades that were just loaded - give them one cycle grace period
      if (newlyLoadedTradesRef.current.has(trade.id)) {
        newlyLoadedTradesRef.current.delete(trade.id); // Remove from skip list for next cycle
        continue;
      }
      
      const strategyInfo = getStrategyInfo(trade);
      const exitRules = strategyInfo?.rules?.exit;
      if (!exitRules) continue;
      
      // Convention: entry_price and current_price are raw YES prices. Flip both for NO trades.
      const _isNo      = (trade.side || 'yes') === 'no';
      const _effEntry  = _isNo ? 1 - (trade.entry_price || 0) : (trade.entry_price || 0);
      const _effCur    = _isNo ? 1 - (trade.current_price || 0) : (trade.current_price || 0);
      const returnPct  = _effEntry > 0 ? ((_effCur - _effEntry) / _effEntry) * 100 : 0;
      
      const heldTimeSeconds = trade.timestamp ? (Date.now() - new Date(trade.timestamp).getTime()) / 1000 : 0;
      const heldTimeMinutes = heldTimeSeconds / 60;
      const minTimeSeconds = exitRules.timeBasedExitSeconds || 600; // Default 10 min if not set
      
      let shouldExit = false;
      let exitReason = null;
      // exitPrice: use the rule-target price so P&L always reflects the exact threshold
      // regardless of how much slippage occurred between polling intervals.
      let exitPrice = trade.current_price || trade.entry_price;
      
      // ✅ PRIORITY 1: Profit Target (HIGHEST) - NO TIME GATE - Lock in gains immediately
      if (returnPct >= exitRules.profitTarget) {
        shouldExit = true;
        // Cap recorded exit at the profit-target price, not the (potentially higher) slippage price
        const _effTarget = _effEntry * (1 + exitRules.profitTarget / 100);
        exitPrice = _isNo ? 1 - _effTarget : _effTarget;
        exitReason = `✅ PROFIT TARGET HIT: ${returnPct.toFixed(2)}% >= ${exitRules.profitTarget}% after ${heldTimeMinutes.toFixed(1)}min`;
      }
      
      // ✅ PRIORITY 2: Stop Loss (HIGH) - NO TIME GATE - Limit losses IMMEDIATELY
      // VALIDATION: Model A stop loss fires at -10% (exitRules.stopLoss = 10)
      else if (returnPct <= -exitRules.stopLoss) {
        shouldExit = true;
        // Cap exit price at the guaranteed stop-loss threshold price, NOT the collapsed market
        // price. Binary prediction markets resolve instantly (e.g. 96¢ → 4¢) faster than the
        // polling loop, so using current_price causes massive stop-loss slippage (-95% instead
        // of -10%). We simulate a limit-stop that fills at exactly entry × (1 − stopLoss%),
        // consistent with how profit-target exits cap at entry × (1 + profitTarget%).
        const _effStopPrice = _effEntry * (1 - exitRules.stopLoss / 100);
        exitPrice = _isNo ? 1 - _effStopPrice : _effStopPrice;
        const slippageNote = returnPct < -exitRules.stopLoss
          ? ` (market slipped to ${returnPct.toFixed(1)}%, capped at -${exitRules.stopLoss}%)`
          : '';
        exitReason = `Stop Loss: -${exitRules.stopLoss}% threshold reached after ${heldTimeMinutes.toFixed(1)}min (exit at ${(exitPrice * 100).toFixed(1)}¢${slippageNote})`;
        console.log(`[STOP-LOSS] 🛑 ${trade.id} | Stop-loss -${exitRules.stopLoss}% triggered (market at ${returnPct.toFixed(2)}%) | capped exit at ${(exitPrice * 100).toFixed(1)}¢ (entry ${(_effEntry * 100).toFixed(1)}¢)`);
      }
      
      // ⚠️ FOR OTHER CONDITIONS: Apply minimum time gate
      else {
        // Only check edge compression or other conditions after minimum time
        if (heldTimeSeconds < minTimeSeconds) {
          continue; // Skip to next trade
        }
        
        // Priority 3: Edge Compression (MEDIUM) - Alpha decay, exit if edge disappeared
        if (exitRules.edgeCompressionThreshold && trade.exit_edge && trade.exit_edge < exitRules.edgeCompressionThreshold) {
          shouldExit = true;
          exitReason = `📉 EDGE COMPRESSED: ${(trade.exit_edge * 100).toFixed(2)}% < ${(exitRules.edgeCompressionThreshold * 100).toFixed(2)}% after ${heldTimeMinutes.toFixed(1)}min`;
        }
      }
      
      // ⚠️ VALIDATION: Only exit if we have a valid exit reason
      if (shouldExit && exitReason) {
        try {
          console.log(`[AUTO-EXIT] 🎯 ${trade.id} | ${exitReason}`);
          // Pass exit_reason to closeTrade so it's stored in database
          await closeTrade(trade.id, exitPrice, exitReason);
          autoExited++;
        } catch (err) {
          console.error(`[AUTO-EXIT] ❌ ${trade.id}: ${err.message}`);
        }
      }
    }
    
    if (autoExited > 0) {
      setAutoExitStats(prev => ({
        totalExited: prev.totalExited + autoExited,
        lastExitTime: new Date()
      }));
    }
  }, []);

  // ── Update Live Prices from Game Details ──────────────────────────────────
  const updateLivePrices = useCallback(async () => {
    try {
      // Get current trades from ref (not from closure)
      setTrades(prevTrades => {
        const openTrades = prevTrades.filter(isOpen);
        if (!openTrades.length) return prevTrades;

        // Build unique game IDs
        const gameIds = Array.from(new Set(openTrades.map(t => t.game_id)));
        
        // Filter out games in cooldown
        const now = Date.now();
        const availableGameIds = gameIds.filter(gameId => {
          const cooldown = perGameCooldownRef.current[gameId];
          return !cooldown || now > cooldown;
        });

        if (!availableGameIds.length) return prevTrades;

        // Chunking: rotate through available games
        const chunkStart = fetchChunkIndexRef.current * CHUNK_SIZE;
        const chunk = availableGameIds.slice(chunkStart, chunkStart + CHUNK_SIZE);
        fetchChunkIndexRef.current = (fetchChunkIndexRef.current + 1) % Math.ceil(availableGameIds.length / CHUNK_SIZE || 1);

        const tradesByGame = {};
        openTrades.forEach(trade => {
          if (!tradesByGame[trade.game_id]) tradesByGame[trade.game_id] = [];
          tradesByGame[trade.game_id].push(trade);
        });

        // Perform fetches in parallel and update immediately
        (async () => {
          const updateMap = {};
          const results = await Promise.allSettled(
            chunk.map(async (gameId) => {
              try {
                const kalshiUrl = buildKalshiUrl(gameId);
                if (!kalshiUrl) return { gameId, price: null };
                
                const res = await fetch(kalshiUrl, {
                  headers: { Accept: 'application/json' },
                  signal: AbortSignal.timeout(5000)
                });

                if (res.status === 429) {
                  const retryAfter = res.headers.get('Retry-After');
                  const waitMs = retryAfter ? parseInt(retryAfter) * 1000 : 60000;
                  perGameCooldownRef.current[gameId] = Date.now() + waitMs;
                  return { gameId, price: null };
                }

                if (!res.ok) return { gameId, price: null };

                const json = await res.json();
                const event = json.event || json;
                const markets = event.markets || [];
                
                if (markets.length >= 2) {
                  const homeMarket = markets[1];
                  const livePrice = (homeMarket.yes_bid + homeMarket.yes_ask) / 2 / 100;
                  if (livePrice > 0) {
                    return { gameId, price: livePrice };
                  }
                }
                return { gameId, price: null };
              } catch (err) {
                console.debug(`Failed to fetch price for game ${gameId}:`, err.message);
                return { gameId, price: null };
              }
            })
          );

          // Process results and build update map
          results.forEach(result => {
            if (result.status === 'fulfilled' && result.value?.price) {
              updateMap[result.value.gameId] = result.value.price;
            }
          });

          // Apply updates if any prices changed
          if (Object.keys(updateMap).length > 0) {
            let liveUpdatedTrades = [];
            setTrades(prev => {
              const updated = prev.map(tc =>
                updateMap[tc.game_id]
                  ? { ...tc, current_price: updateMap[tc.game_id], _hasLivePrice: true }
                  : tc
              );
              const withLivePnl = updated.map(t => {
                if (isClosed(t)) return t;
                const cur = updateMap[t.game_id] ?? t.current_price ?? t.entry_price ?? 0;
                return { ...t, pnl: computePnl(t.side || 'yes', t.entry_price || 0, cur, t.quantity || 1) };
              });
              setStats(calcPortfolioStats(withLivePnl));
              liveUpdatedTrades = withLivePnl; // capture for stop-loss check
              return updated;
            });
            // ✅ CRITICAL: Run stop-loss check immediately with LIVE market prices,
            // not the stale DB prices that checkAutoExits would otherwise use.
            setTimeout(() => checkAutoExits(liveUpdatedTrades), 0);
          }
        })();

        return prevTrades;
      });
    } catch (err) {
      console.debug('updateLivePrices error:', err);
    }
  }, [checkAutoExits]);

  useEffect(() => {
    refresh(false);
    const id = setInterval(async () => {
      const data = await fetchTrades(1000);
      // Preserve live current_price / pnl / _hasLivePrice from previous state
      // so the display doesn't flash +$0.00 between refreshes.
      setTrades(prev => {
        const prevMap = {};
        prev.forEach(t => { prevMap[t.id] = t; });
        return data.map(t => {
          const existing = prevMap[t.id];
          if (existing && isOpen(t) && existing._hasLivePrice) {
            return { ...t, current_price: existing.current_price, pnl: existing.pnl ?? t.pnl, _hasLivePrice: true };
          }
          return t;
        });
      });
      setStats(calcPortfolioStats(data));
      setLastUpdate(new Date());
      // Auto-exit check runs with latest data
      checkAutoExits(data);
    }, 15_000);
    return () => clearInterval(id);
  }, [checkAutoExits, refresh, triggerTradingCycle]);

  // ── Execution interval: mirrors the Terminal's 60-second auto-strategy loop ──
  // Keeps calling run_cycle until both Model A (max 10) and Model B (max 10) are full,
  // exactly as the Terminal does when the Dashboard page is mounted.
  useEffect(() => {
    const MAX_PER_MODEL = 10;

    const countOpenByModel = (tradeList) => {
      let modelA = 0, modelB = 0;
      tradeList.filter(isOpen).forEach(t => {
        const s = (t.strategy || '').toLowerCase();
        if (s.includes('model_b') || s.includes('high frequency') || s.includes('model b')) modelB++;
        else modelA++;
      });
      return { modelA, modelB };
    };

    const runExecutionCycle = async () => {
      try {
        const data = await fetchTrades(1000);
        const { modelA, modelB } = countOpenByModel(data);
        // Only trigger if at least one model still has open slots
        if (modelA < MAX_PER_MODEL || modelB < MAX_PER_MODEL) {
          triggerTradingCycle(true); // force = bypass cooldown
          // Schedule two follow-up refreshes so newly placed trades appear promptly
          setTimeout(() => refresh(true), 5_000);
          setTimeout(() => refresh(true), 12_000);
        }
      } catch { /* ignore */ }
    };

    // Run immediately on mount, then every 60 seconds (matching Terminal's execution interval)
    runExecutionCycle();
    const execId = setInterval(runExecutionCycle, 60_000);
    return () => clearInterval(execId);
  }, [refresh, triggerTradingCycle]);

  // ── Update Live Prices Every 2 Minutes (Rate Limit Safe) ──
  useEffect(() => {
    // On mount: immediately fetch ALL open game prices (no chunk limit)
    const fetchAllOnMount = async () => {
      try {
        const data = await fetchTrades(1000);
        const openTrades = data.filter(isOpen);
        const gameIds = Array.from(new Set(openTrades.map(t => t.game_id).filter(Boolean)));
        if (!gameIds.length) return;
        const updateMap = {};
        await Promise.allSettled(
          gameIds.map(async (gameId) => {
            try {
              const kalshiUrl = buildKalshiUrl(gameId);
              if (!kalshiUrl) return;
              const res = await fetch(kalshiUrl, { headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(6000) });
              if (!res.ok) return;
              const json = await res.json();
              const event = json.event || json;
              const markets = event.markets || [];
              if (markets.length >= 2) {
                const homeMarket = markets[1];
                const livePrice = (homeMarket.yes_bid + homeMarket.yes_ask) / 2 / 100;
                if (livePrice > 0) updateMap[gameId] = livePrice;
              }
            } catch { /* ignore */ }
          })
        );
        if (Object.keys(updateMap).length > 0) {
          setTrades(prev => {
            const updated = prev.map(t =>
              updateMap[t.game_id]
                ? { ...t, current_price: updateMap[t.game_id], _hasLivePrice: true }
                : t
            );
            // Also recompute stats with live pnl for open trades
            const withLivePnl = updated.map(t => {
              if (isClosed(t)) return t;
              const cur = updateMap[t.game_id] ?? t.current_price ?? t.entry_price ?? 0;
              return { ...t, pnl: computePnl(t.side || 'yes', t.entry_price || 0, cur, t.quantity || 1) };
            });
            setStats(calcPortfolioStats(withLivePnl));
            return updated;
          });
          // Live prices updated on mount — exit checks run via the 15s polling
          // interval only, after the grace period (newlyLoadedTradesRef) is set.
        }
      } catch { /* ignore */ }
    };
    fetchAllOnMount();
    // Then poll via chunked updater every 10 s
    const priceInterval = setInterval(() => {
      updateLivePrices();
    }, 10_000);
    return () => clearInterval(priceInterval);
  }, [updateLivePrices]);

  // ── Keep selected trade in sync with latest data ───────────────────────────
  useEffect(() => {
    if (selectedTrade && trades.length > 0) {
      const updatedTrade = trades.find(t => t.id === selectedTrade.id);
      if (updatedTrade && JSON.stringify(updatedTrade) !== JSON.stringify(selectedTrade)) {
        setSelectedTrade(updatedTrade);
      }
    }
  }, [trades, selectedTrade]);

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleExitConfirm = async () => {
    if (!exitTarget) return;
    setExitLoading(true);
    try {
      // Determine if remaining open trades will be 0 after this close
      const openBeforeClose = trades.filter(isOpen);
      const willBeEmpty = openBeforeClose.length <= 1;

      await closeTrade(exitTarget.id, exitTarget.current_price);
      setExitTarget(null);
      await refresh(true);

      // If no open positions remain, trigger a new trading cycle immediately
      // and schedule a follow-up refresh to show the newly placed trades.
      if (willBeEmpty) {
        triggerTradingCycle(true); // force = bypass cooldown
        setTimeout(() => refresh(true), 4_000);
        setTimeout(() => refresh(true), 8_000);
      }
    } catch (err) { setError(`Failed to close: ${err.message}`); }
    setExitLoading(false);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      // Decide before deletion whether any open trades remain afterwards
      const openBeforeDelete = trades.filter(isOpen);
      const deletingOpenTrade = openBeforeDelete.some(t => t.id === deleteTarget);
      const remainingOpenCount = deletingOpenTrade
        ? openBeforeDelete.length - 1
        : openBeforeDelete.length;

      await deleteTrade(deleteTarget);
      setDeleteTarget(null);
      await refresh(true);

      // No open trades left after deletion — force a new trading cycle immediately
      // so fresh trades appear on this page without navigating to the Terminal.
      if (remainingOpenCount === 0) {
        triggerTradingCycle(true); // force = bypass cooldown
        setTimeout(() => refresh(true), 4_000);
        setTimeout(() => refresh(true), 8_000);
      }
    } catch (err) { setError(`Failed to delete: ${err.message}`); }
  };

  const handleCloseAllConfirm = async () => {
    const openTrades = trades.filter(isOpen);
    if (!openTrades.length) { setCloseAllConfirm(false); return; }
    setCloseAllLoading(true);
    let ok = 0, fail = 0;
    for (const t of openTrades) {
      try { await closeTrade(t.id, t.current_price || t.entry_price); ok++; }
      catch { fail++; }
    }
    setCloseAllLoading(false);
    setCloseAllConfirm(false);
    if (ok) { setError(null); await refresh(true); }
    if (fail) setError(`Closed ${ok}, ${fail} failed`);

    // All trades were just closed — force a new trading cycle immediately
    // so fresh positions are placed without needing to visit the Terminal page.
    if (ok > 0) {
      triggerTradingCycle(true); // force = bypass cooldown
      setTimeout(() => refresh(true), 4_000);
      setTimeout(() => refresh(true), 8_000);
    }
  };

  const exportCsv = () => {
    const headers = ['ID','Game','Game Title','Market','Type','Strategy','Side','Dir','Qty','Entry¢','Current¢','Exit¢','P&L$','Return%','Status','Opened','Closed'];
    const rows = trades.map((t) => [
      t.id, t.game_id,
      t.game_title ? String(t.game_title).replace(/\s*@\s*/g, ' vs ') : '',
      t.market_name, t.type, t.strategy, t.side, t.direction, t.quantity,
      ((t.entry_price || 0) * 100).toFixed(1),
      ((t.current_price || 0) * 100).toFixed(1),
      t.exit_price != null ? (t.exit_price * 100).toFixed(1) : '',
      (t.pnl || 0).toFixed(2),
      t.entry_price > 0 ? (((t.current_price - t.entry_price) / t.entry_price) * 100).toFixed(2) : '0',
      t.status,
      t.timestamp ? new Date(t.timestamp).toLocaleString() : '',
      t.closed_at ? new Date(t.closed_at).toLocaleString() : '',
    ]);
    const csv = [headers, ...rows].map((r) => r.map((v) => `"${v ?? ''}"`).join(',')).join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    a.download = `trades_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir('desc'); }
  };

  // ── Filter + sort ─────────────────────────────────────────────────────────
  const filtered = trades
    .filter((t) => {
      if (typeFilter === 'paper') return t.type !== 'live';
      if (typeFilter === 'live')  return t.type === 'live';
      if (typeFilter !== 'all')   return t.type === typeFilter;
      return true;
    })
    .filter((t) => {
      if (statusFilter === 'open')   return isOpen(t);
      if (statusFilter === 'closed') return isClosed(t);
      return true;
    })
    .filter((t) => {
      if (sideFilter === 'all') return true;
      return t.side?.toLowerCase() === sideFilter || t.direction?.toLowerCase() === sideFilter;
    })
    .filter((t) => {
      if (!search) return true;
      const q = search.toLowerCase();
      return [t.game_id, t.game_title, t.market_name, t.strategy, t.signal_type, t.id]
        .some((v) => v?.toLowerCase().includes(q));
    })
    .filter((t) => {
      if (dateRange === 'all') return true;
      const ms = { '1h': 3_600_000, '24h': 86_400_000, '7d': 604_800_000, '30d': 2_592_000_000 }[dateRange];
      if (!ms) return true;
      return new Date(t.timestamp || t.created_at || 0).getTime() >= Date.now() - ms;
    })
    .sort((a, b) => {
      let av = a[sortKey], bv = b[sortKey];
      if (typeof av === 'string') av = av.toLowerCase();
      if (typeof bv === 'string') bv = bv.toLowerCase();
      return sortDir === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
    });

  const maxAbsPnl     = filtered.reduce((m, t) => Math.max(m, Math.abs(t.pnl || 0)), 0.01);
  const filteredTotal = filtered.reduce((s, t) => s + (t.pnl || 0), 0);
  const secAgo        = lastUpdate ? Math.round((Date.now() - lastUpdate) / 1000) : null;

  console.log('Trades filtered:', {
    total: trades.length,
    filtered: filtered.length,
    open: trades.filter(isOpen).length,
    closed: trades.filter(isClosed).length,
    statusFilter,
    typeFilter
  });

  const totalPages = Math.ceil(filtered.length / pageSize);
  const startIdx   = (currentPage - 1) * pageSize;
  const endIdx     = startIdx + pageSize;
  const paginated  = filtered.slice(startIdx, endIdx);

  useEffect(() => { setCurrentPage(1); }, [typeFilter, statusFilter, sideFilter, search, dateRange, sortKey, sortDir]);

  const sortProps = { sortKey, sortDir, onSort: toggleSort };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-background text-foreground overflow-x-hidden">

      {/* ── Header ── */}
      <header className="border-b border-border bg-card/50 sticky top-0 z-10">
        <div className="max-w-[1800px] mx-auto px-4 py-4 flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-xl font-bold flex items-center gap-2">
              <FileText className="w-5 h-5 text-yellow-400" />Trades Center
            </h1>
            <p className="text-xs text-muted-foreground">
              Paper &amp; live position blotter · auto-refreshes every 15s · click any row for details
              {autoExitStats.lastExitTime && (
                <span className="ml-2 text-emerald-400">
                  ✅ Auto-exited {autoExitStats.totalExited} trades
                </span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {error && (
              <span className="text-xs text-red-400 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />{error}
              </span>
            )}
            {secAgo !== null && (
              <span className="text-xs text-muted-foreground">Updated {secAgo}s ago</span>
            )}
            <Button variant="ghost" size="sm" onClick={exportCsv} className="text-xs gap-1">
              <Download className="w-3 h-3" />Export CSV
            </Button>
            {(stats.openCount || 0) > 0 && (
              <Button variant="destructive" size="sm" onClick={() => setCloseAllConfirm(true)}
                disabled={closeAllLoading} className="text-xs gap-1">
                {closeAllLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3" />}
                Close All ({stats.openCount})
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={() => refresh(false)} disabled={loading}>
              <RefreshCw className={`w-4 h-4 mr-1 ${loading ? 'animate-spin' : ''}`} />Refresh
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-[1800px] mx-auto px-4 py-6 space-y-5 min-w-0">

        {/* ── Daily Results ── */}
        {dailyReport && Object.keys(dailyReport.strategies || {}).length > 0 && (
          <div className="space-y-3">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-blue-400" />Daily Results
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(dailyReport.strategies).map(([sid, data]) => (
                <DailyStatsCard key={sid} strategyId={sid} data={data} />
              ))}
            </div>
          </div>
        )}

        {/* ── Validation Mode Banner ── */}
        {(() => {
          const openTrades = trades.filter(isOpen);
          const modelACount = openTrades.filter(t => {
            const sid = (t.strategy || '').toLowerCase().replace(/ /g, '_');
            return sid === 'model_a_disciplined' || sid.includes('model_a');
          }).length;
          const modelBCount = openTrades.filter(t => {
            const sid = (t.strategy || '').toLowerCase().replace(/ /g, '_');
            return sid === 'model_b_high_frequency' || sid.includes('model_b');
          }).length;
          const aAtLimit = modelACount >= 10;
          const bAtLimit = modelBCount >= 10;
          const atLimit = aAtLimit || bAtLimit;
          return (
            <div className={`rounded-xl border p-3 flex flex-wrap items-center justify-between gap-3 ${atLimit ? 'border-red-500/60 bg-red-950/30' : 'border-emerald-500/40 bg-emerald-950/20'}`}>
              <div className="flex items-center gap-2">
                <Shield className={`w-4 h-4 ${atLimit ? 'text-red-400' : 'text-emerald-400'}`} />
                <span className={`text-xs font-semibold ${atLimit ? 'text-red-300' : 'text-emerald-300'}`}>
                  🔒 VALIDATION MODE
                </span>
                <span className="text-xs text-muted-foreground">
                  Model A &amp; B &nbsp;·&nbsp; 10% Stop-Loss Auto-Exit &nbsp;·&nbsp; 10 Trades Each
                </span>
              </div>
              <div className="flex items-center gap-3 text-xs">
                <span className={`px-2 py-0.5 rounded font-mono font-bold ${aAtLimit ? 'bg-red-500/30 text-red-300' : 'bg-emerald-500/20 text-emerald-300'}`}>
                  A: {modelACount}/10
                </span>
                <span className={`px-2 py-0.5 rounded font-mono font-bold ${bAtLimit ? 'bg-red-500/30 text-red-300' : 'bg-emerald-500/20 text-emerald-300'}`}>
                  B: {modelBCount}/10
                </span>
                {atLimit && (
                  <span className="text-red-400 font-semibold animate-pulse">⚠ LIMIT REACHED — new trades blocked</span>
                )}
              </div>
            </div>
          );
        })()}

        {/* ── KPI Row ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KPICard title="Total Paper P&L" value={fmtUsd(stats.totalPnl ?? 0)} icon={DollarSign}
            variant={(stats.totalPnl ?? 0) >= 0 ? 'positive' : 'negative'}
            sub={`Realised ${fmtUsd(stats.realisedPnl ?? 0)}`} />
          <KPICard title="Open Positions" value={stats.openCount ?? 0} icon={Activity}
            variant="info" sub={`${stats.closedCount ?? 0} closed`} />
          <KPICard title="Win Rate" value={`${stats.winRate ?? 0}%`} icon={Target}
            variant={(stats.winRate ?? 0) >= 50 ? 'positive' : 'negative'}
            sub={`${stats.winCount ?? 0}W / ${stats.lossCount ?? 0}L`} />
          <KPICard title="Total Volume" value={(stats.totalVolume ?? 0).toLocaleString()} icon={BarChart3}
            variant="default" sub={`${stats.totalTrades ?? 0} trades`} />
        </div>

        {/* ── P&L Summary Bar ── */}
        {(stats.totalTrades ?? 0) > 0 && (
          <div className={`rounded-xl border p-4 flex flex-wrap items-center justify-between gap-4 ${pnlBg(stats.totalPnl)}`}>
            <div className="flex items-center gap-3">
              {(stats.totalPnl ?? 0) >= 0
                ? <TrendingUp  className="w-5 h-5 text-emerald-400" />
                : <TrendingDown className="w-5 h-5 text-red-400" />}
              <div>
                <div className="text-xs text-muted-foreground">Portfolio P&L</div>
                <div className={`text-2xl font-bold font-mono ${pnlCls(stats.totalPnl)}`}>
                  {fmtUsd(stats.totalPnl ?? 0)}
                </div>
              </div>
            </div>
            <div className="hidden sm:flex gap-8 text-center text-xs">
              {[
                ['Unrealised', fmtUsd(stats.unrealisedPnl ?? 0), pnlCls(stats.unrealisedPnl)],
                ['Realised',   fmtUsd(stats.realisedPnl   ?? 0), pnlCls(stats.realisedPnl)],
                ['Avg Win',    fmtUsd(stats.avgWin  ?? 0), 'text-emerald-400'],
                ['Avg Loss',   fmtUsd(stats.avgLoss ?? 0), 'text-red-400'],
                ['Open',       stats.openCount ?? 0, 'text-blue-400'],
              ].map(([label, val, cls]) => (
                <div key={label}>
                  <div className="text-muted-foreground mb-0.5">{label}</div>
                  <div className={`font-mono font-semibold ${cls}`}>{val}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Filters ── */}
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-wrap items-center gap-3">
              <Filter className="w-4 h-4 text-muted-foreground flex-shrink-0" />

              <Select value={pageSize.toString()} onValueChange={(v) => { setPageSize(parseInt(v)); setCurrentPage(1); }}>
                <SelectTrigger className="w-28 h-9 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {[10, 25, 50, 100].map((n) => (
                    <SelectItem key={n} value={String(n)}>{n} / Page</SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className="w-36 h-9 text-xs"><SelectValue placeholder="Type" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="paper">Paper</SelectItem>
                  <SelectItem value="live">Live</SelectItem>
                  <SelectItem value="manual">Manual</SelectItem>
                  <SelectItem value="auto-edge">Auto-Edge</SelectItem>
                  <SelectItem value="signal">Signal</SelectItem>
                </SelectContent>
              </Select>

              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-36 h-9 text-xs"><SelectValue placeholder="Status" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="open">Open / Active</SelectItem>
                  <SelectItem value="closed">Closed</SelectItem>
                </SelectContent>
              </Select>

              <Select value={sideFilter} onValueChange={setSideFilter}>
                <SelectTrigger className="w-28 h-9 text-xs"><SelectValue placeholder="Side" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Sides</SelectItem>
                  <SelectItem value="yes">YES</SelectItem>
                  <SelectItem value="no">NO</SelectItem>
                  <SelectItem value="buy">Buy</SelectItem>
                  <SelectItem value="sell">Sell</SelectItem>
                </SelectContent>
              </Select>

              <Select value={dateRange} onValueChange={setDateRange}>
                <SelectTrigger className="w-32 h-9 text-xs"><SelectValue placeholder="Date" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Time</SelectItem>
                  <SelectItem value="1h">Last Hour</SelectItem>
                  <SelectItem value="24h">Last 24h</SelectItem>
                  <SelectItem value="7d">Last 7 Days</SelectItem>
                  <SelectItem value="30d">Last 30 Days</SelectItem>
                </SelectContent>
              </Select>

              <div className="relative flex-1 min-w-[200px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                <Input placeholder="Search game / market / strategy / signal…"
                  value={search} onChange={(e) => setSearch(e.target.value)}
                  className="pl-8 h-9 text-xs" />
              </div>

              <Badge variant="outline" className="text-muted-foreground text-xs ml-auto whitespace-nowrap">
                {startIdx + 1}–{Math.min(endIdx, filtered.length)} of {filtered.length} trades
              </Badge>
            </div>
          </CardContent>
        </Card>

        {/* ── Trade Table ── */}
        <Card className="overflow-hidden">
          <CardContent className="p-0">
            {loading && trades.length === 0 ? (
              <div className="flex items-center justify-center gap-2 py-20 text-muted-foreground text-sm">
                <Loader2 className="w-6 h-6 animate-spin" />Loading positions from database…
              </div>
            ) : filtered.length === 0 ? (
              <div className="text-center py-20 space-y-3">
                <FileText className="w-10 h-10 mx-auto text-muted-foreground opacity-40" />
                <p className="text-sm font-medium">No trades</p>
              </div>
            ) : (
              <div className="block w-full overflow-x-auto" style={{ WebkitOverflowScrolling: 'touch' }}>
                <table className="w-full text-sm" style={{ minWidth: '1400px' }}>
                  <thead>
                    <tr className="border-b border-border bg-muted/20">
                      <th className="py-3 px-3 text-left text-[10px] uppercase tracking-wider text-muted-foreground font-medium whitespace-nowrap">Order ID</th>
                      <SortTh label="Game"       k="game_title"  {...sortProps} className="text-left" />
                      <th className="py-3 px-3 text-left text-[10px] uppercase tracking-wider text-muted-foreground font-medium whitespace-nowrap">Position</th>
                      <th className="py-3 px-3 text-center text-[10px] uppercase tracking-wider text-muted-foreground font-medium whitespace-nowrap">Type</th>
                      <SortTh label="Entry"      k="entry_price" {...sortProps} className="text-right" />
                      <th className="py-3 px-3 text-right text-[10px] uppercase tracking-wider text-muted-foreground font-medium whitespace-nowrap">Cur / Exit</th>
                      <SortTh label="Qty"        k="quantity"    {...sortProps} className="text-right" />
                      <th className="py-3 px-3 text-center text-[10px] uppercase tracking-wider text-muted-foreground font-medium whitespace-nowrap">Status</th>
                      <th className="py-3 px-3 text-left text-[10px] uppercase tracking-wider text-muted-foreground font-medium whitespace-nowrap">Strategy</th>
                      <SortTh label="P&L"        k="pnl"         {...sortProps} className="text-right" />
                      <th className="py-3 px-3 text-center text-[10px] uppercase tracking-wider text-muted-foreground font-medium whitespace-nowrap">Return</th>
                      <SortTh label="Opened"     k="timestamp"   {...sortProps} className="text-right" />
                      <th className="py-3 px-3 text-right text-[10px] uppercase tracking-wider text-muted-foreground font-medium whitespace-nowrap">Closed</th>
                      <th className="py-3 px-3 text-center text-[10px] uppercase tracking-wider text-muted-foreground font-medium whitespace-nowrap">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginated.map((trade, idx) => (
                      <TradeRow
                        key={trade.id || idx}
                        trade={trade}
                        maxAbsPnl={maxAbsPnl}
                        onCloseRequest={(t) => setExitTarget(t)}
                        onDelete={(id) => setDeleteTarget(id)}
                        onSelect={(t) => setSelectedTrade(t)}
                      />
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 border-border bg-muted/10">
                      <td colSpan={10} className="py-3 px-3 text-xs text-muted-foreground">
                        {filtered.length} positions · {filtered.filter(isOpen).length} open
                      </td>
                      <td className="py-3 px-3 text-right">
                        <span className={`font-mono font-bold text-sm ${pnlCls(filteredTotal)}`}>
                          {fmtUsd(filteredTotal)}
                        </span>
                      </td>
                      <td colSpan={5} />
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* ── Pagination ── */}
        {filtered.length > pageSize && (
          <div className="flex items-center justify-between p-4 border border-border rounded-lg bg-card/50">
            <div className="text-xs text-muted-foreground">
              Showing <span className="font-bold">{startIdx + 1}</span> to{' '}
              <span className="font-bold">{Math.min(endIdx, filtered.length)}</span> of{' '}
              <span className="font-bold">{filtered.length}</span> trades
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm"
                onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                disabled={currentPage === 1}>
                ← Previous
              </Button>
              <div className="flex items-center gap-1">
                {(totalPages <= 6
                  ? Array.from({ length: totalPages }, (_, i) => i + 1)
                  : [1, 2, 3, 4, '...', totalPages - 1, totalPages]
                ).map((page, idx) =>
                  page === '...' ? (
                    <span key={`e${idx}`} className="text-muted-foreground px-1">…</span>
                  ) : (
                    <Button key={page} variant={currentPage === page ? 'default' : 'outline'}
                      size="sm" className="h-8 w-8 p-0 text-xs"
                      onClick={() => setCurrentPage(page)}>
                      {page}
                    </Button>
                  )
                )}
              </div>
              <Button variant="outline" size="sm"
                onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                disabled={currentPage === totalPages}>
                Next →
              </Button>
            </div>
          </div>
        )}

        <p className="text-xs text-gray-600 text-center">
          Paper trades are simulated — no real capital at risk. All positions are stored in the database.
        </p>
      </main>

      {/* ── Trade Detail Modal ── */}
      <TradeDetailModal trade={selectedTrade} onClose={() => setSelectedTrade(null)} />

      {/* ── Exit Confirm ── */}
      <Dialog open={!!exitTarget} onOpenChange={() => setExitTarget(null)}>
        <DialogContent className="bg-gray-900 border-gray-800 max-w-sm">
          <DialogHeader>
            <DialogTitle>Exit Position</DialogTitle>
            <DialogDescription>Close at current market price. P&L will be locked in.</DialogDescription>
          </DialogHeader>
          {exitTarget && (
            <div className="py-3 space-y-2 p-3 bg-gray-800/50 rounded-lg text-xs">
              {[
                ['Market',      exitTarget.market_name],
                ['Position',    `${exitTarget.direction?.toUpperCase()} ${exitTarget.side?.toUpperCase()} × ${exitTarget.quantity}`],
                ['Entry Price', `${((exitTarget.entry_price   || 0) * 100).toFixed(0)}¢`],
                ['Exit Price',  `${((exitTarget.current_price || 0) * 100).toFixed(0)}¢`],
              ].map(([label, val]) => (
                <div key={label} className="flex justify-between">
                  <span className="text-gray-400">{label}:</span>
                  <span className="font-medium">{val}</span>
                </div>
              ))}
              <div className={`flex justify-between font-bold border-t border-gray-700 pt-2 ${pnlCls(exitTarget.pnl)}`}>
                <span>Realised P&L:</span>
                <span className="font-mono">{fmtUsd(exitTarget.pnl || 0)}</span>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setExitTarget(null)}>Cancel</Button>
            <Button className="bg-red-700 hover:bg-red-600" onClick={handleExitConfirm} disabled={exitLoading}>
              {exitLoading ? <><Loader2 className="w-4 h-4 animate-spin mr-1" />Closing…</> : 'Close Position'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Delete Confirm ── */}
      <Dialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent className="bg-gray-900 border-gray-800 max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="w-4 h-4" />Delete Trade Record
            </DialogTitle>
            <DialogDescription>
              Permanently removes this trade from the database. Cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button className="bg-red-700 hover:bg-red-600" onClick={handleDeleteConfirm}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Close All ── */}
      <Dialog open={closeAllConfirm} onOpenChange={() => setCloseAllConfirm(false)}>
        <DialogContent className="bg-gray-900 border-gray-800 max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-yellow-400">
              <AlertTriangle className="w-4 h-4" />Close All Open Positions
            </DialogTitle>
            <DialogDescription>
              This will exit all {trades.filter(isOpen).length} open position{trades.filter(isOpen).length !== 1 ? 's' : ''} at current market price.
            </DialogDescription>
          </DialogHeader>
          <div className="py-3 p-3 bg-gray-800/50 rounded-lg text-xs space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-400">Open Positions:</span>
              <span className="font-medium">{trades.filter(isOpen).length}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Total Unrealised P&L:</span>
              <span className={`font-mono font-bold ${pnlCls(trades.filter(isOpen).reduce((s, t) => s + (t.pnl || 0), 0))}`}>
                {fmtUsd(trades.filter(isOpen).reduce((s, t) => s + (t.pnl || 0), 0))}
              </span>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCloseAllConfirm(false)}>Cancel</Button>
            <Button className="bg-red-700 hover:bg-red-600" onClick={handleCloseAllConfirm} disabled={closeAllLoading}>
              {closeAllLoading ? <><Loader2 className="w-4 h-4 animate-spin mr-1" />Closing All…</> : 'Close All Positions'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}