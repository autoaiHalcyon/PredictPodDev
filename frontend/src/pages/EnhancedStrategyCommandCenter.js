import React, { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Switch } from "../components/ui/switch";
import { ScrollArea } from "../components/ui/scroll-area";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../components/ui/tabs";
import {
  ArrowLeft,
  Play,
  Pause,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Activity,
  DollarSign,
  Target,
  Shield,
  Zap,
  BarChart3,
  RefreshCw,
  Download,
  Crown,
  Medal,
  Settings,
  ChevronRight,
  Eye,
  Percent,
  Scale,
  LineChart,
  AlertCircle,
  CheckCircle2,
  Rocket,
  FileArchive,
  XCircle,
  LogIn,
  LogOut,
  TrendingDown as TrendDown,
  List,
} from "lucide-react";
import { RulesDrawer, RuleChips } from "../components/RulesDrawer";
import AutonomousDashboard from "../components/AutonomousDashboard";

const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

// Model display config
const MODEL_CONFIG = {
  model_a_disciplined: {
    name: "Model A",
    subtitle: "Disciplined Edge Trader",
    color: "emerald",
    icon: Target,
    bgClass: "bg-emerald-500/10 border-emerald-500/30",
    textClass: "text-emerald-400",
    accentClass: "from-emerald-500/20 to-emerald-600/10",
  },
  model_b_high_frequency: {
    name: "Model B",
    subtitle: "High Frequency Hunter",
    color: "blue",
    icon: Zap,
    bgClass: "bg-blue-500/10 border-blue-500/30",
    textClass: "text-blue-400",
    accentClass: "from-blue-500/20 to-blue-600/10",
  },
  model_c_institutional: {
    name: "Model C",
    subtitle: "Institutional Risk-First",
    color: "purple",
    icon: Shield,
    bgClass: "bg-purple-500/10 border-purple-500/30",
    textClass: "text-purple-400",
    accentClass: "from-purple-500/20 to-purple-600/10",
  },
  model_d_growth_focused: {
    name: "Model D",
    subtitle: "Growth Focused Trader",
    color: "rose",
    icon: Rocket,
    bgClass: "bg-rose-500/10 border-rose-500/30",
    textClass: "text-rose-400",
    accentClass: "from-rose-500/20 to-rose-600/10",
  },
  model_e_balanced_hunter: {
    name: "Model E",
    subtitle: "Balanced Edge Hunter",
    color: "amber",
    icon: TrendingUp,
    bgClass: "bg-amber-500/10 border-amber-500/30",
    textClass: "text-amber-400",
    accentClass: "from-amber-500/20 to-amber-600/10",
  },
};

// Format currency
const formatCurrency = (value) => {
  const num = Number(value) || 0;
  const sign = num >= 0 ? "+" : "";
  return `${sign}$${Math.abs(num).toFixed(2)}`;
};

// Format percentage
const formatPct = (value) => {
  const num = Number(value) || 0;
  return `${num.toFixed(1)}%`;
};

// Enhanced Strategy Summary Card with more metrics
const EnhancedStrategySummaryCard = ({
  strategyId,
  data,
  isWinning,
  isBestRiskAdjusted,
  ruleChips,
  performanceMetrics,
}) => {
  const config = MODEL_CONFIG[strategyId] || {
    name: strategyId,
    color: "gray",
    icon: Activity,
  };
  const Icon = config.icon;
  const portfolio = data?.portfolio || {};

  const totalPnl = portfolio.total_pnl || 0;
  const isProfitable = totalPnl >= 0;

  // Get expected PnL from performance metrics
  const expectedPnl = performanceMetrics?.total_expected_profit || 0;
  const actualPnl = performanceMetrics?.total_actual_profit || totalPnl;
  const slippage = performanceMetrics?.total_slippage || 0;

  return (
    <Card
      data-testid={`strategy-card-${strategyId}`}
      className={`${config.bgClass} border-2 ${isWinning ? "ring-2 ring-yellow-400" : ""} transition-all duration-300 hover:shadow-lg`}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div
              className={`p-2 rounded-lg bg-gradient-to-br ${config.accentClass}`}
            >
              <Icon className={`w-5 h-5 ${config.textClass}`} />
            </div>
            <div>
              <CardTitle className="text-lg font-bold flex items-center gap-2">
                {config.name}
                {isWinning && <Crown className="w-4 h-4 text-yellow-400" />}
                {isBestRiskAdjusted && !isWinning && (
                  <Medal className="w-4 h-4 text-amber-400" />
                )}
              </CardTitle>
              <p className="text-xs text-muted-foreground">{config.subtitle}</p>
            </div>
          </div>
          <Badge
            variant={data?.enabled ? "default" : "secondary"}
            className={data?.enabled ? "bg-green-500" : ""}
          >
            {data?.enabled ? "Active" : "Inactive"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {/* Total PnL Display */}
        <div className="mb-4 text-center py-3 rounded-lg bg-background/50">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">
            Total P&L
          </p>
          <p
            className={`text-3xl font-bold ${isProfitable ? "text-green-400" : "text-red-400"}`}
          >
            {formatCurrency(totalPnl)}
          </p>
        </div>

        {/* Capital & Exposure */}
        <div className="grid grid-cols-2 gap-3 text-sm mb-4">
          <div className="p-2 rounded bg-background/30">
            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <DollarSign className="w-3 h-3" /> Capital
            </p>
            <p className="font-semibold">
              ${(portfolio.available_capital || 10000).toFixed(0)}
            </p>
          </div>
          <div className="p-2 rounded bg-background/30">
            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <Scale className="w-3 h-3" /> Exposure
            </p>
            <p className="font-semibold">
              {formatPct(portfolio.risk_utilization || 0)}
            </p>
          </div>
        </div>

        {/* PnL Breakdown */}
        <div className="grid grid-cols-3 gap-2 text-sm mb-4">
          <div>
            <p className="text-xs text-muted-foreground">Realized</p>
            <p
              className={
                portfolio.realized_pnl >= 0
                  ? "text-green-400 font-medium"
                  : "text-red-400 font-medium"
              }
            >
              {formatCurrency(portfolio.realized_pnl)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Unrealized</p>
            <p
              className={
                portfolio.unrealized_pnl >= 0
                  ? "text-green-400 font-medium"
                  : "text-red-400 font-medium"
              }
            >
              {formatCurrency(portfolio.unrealized_pnl)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Expected</p>
            <p
              className={
                expectedPnl >= 0
                  ? "text-blue-400 font-medium"
                  : "text-orange-400 font-medium"
              }
            >
              {formatCurrency(expectedPnl)}
            </p>
          </div>
        </div>

        {/* Performance Metrics */}
        <div className="grid grid-cols-4 gap-2 text-xs mb-4 p-2 rounded bg-background/30">
          <div className="text-center">
            <p className="text-muted-foreground">Win Rate</p>
            <p className="font-bold text-foreground">
              {formatPct(portfolio.win_rate)}
            </p>
          </div>
          <div className="text-center">
            <p className="text-muted-foreground">Avg Edge</p>
            <p className="font-bold text-foreground">
              {formatPct((portfolio.avg_edge_entry || 0) * 100)}
            </p>
          </div>
          <div className="text-center">
            <p className="text-muted-foreground">Max DD</p>
            <p className="font-bold text-orange-400">
              {formatPct(portfolio.max_drawdown_pct)}
            </p>
          </div>
          <div className="text-center">
            <p className="text-muted-foreground">Trades</p>
            <p className="font-bold text-foreground">
              {portfolio.total_trades || 0}
            </p>
          </div>
        </div>

        {/* Sharpe-like Score */}
        <div className="flex items-center justify-between mb-3 p-2 rounded bg-background/30">
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <LineChart className="w-3 h-3" /> Sharpe-like Score
          </span>
          <span
            className={`font-bold ${(performanceMetrics?.sharpe_like_score || 0) > 1 ? "text-green-400" : "text-yellow-400"}`}
          >
            {(performanceMetrics?.sharpe_like_score || 0).toFixed(2)}
          </span>
        </div>

        {/* Rule Chips */}
        {ruleChips && ruleChips.length > 0 && (
          <RuleChips chips={ruleChips} maxDisplay={5} />
        )}

        {/* Action Buttons */}
        <div className="mt-3 flex items-center justify-between">
          <RulesDrawer
            strategyId={strategyId}
            displayName={`${config.name} - ${config.subtitle}`}
            league="BASE"
          />
          <Link to="/optimization">
            <Button variant="ghost" size="sm" className="text-xs">
              <Settings className="w-3 h-3 mr-1" />
              Tune
            </Button>
          </Link>
        </div>

        {/* Circuit Breaker Warning */}
        {portfolio.circuit_breaker_active && (
          <div className="mt-3 p-2 bg-red-500/20 border border-red-500/50 rounded text-xs text-red-400 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Circuit Breaker Active
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Enhanced Comparison Table with Expected vs Actual
const EnhancedComparisonTable = ({
  comparison,
  strategies,
  performanceData,
}) => {
  const metrics = [
    {
      key: "total_pnl",
      label: "Total P&L",
      format: formatCurrency,
      type: "pnl",
    },
    {
      key: "realized_pnl",
      label: "Realized",
      format: formatCurrency,
      type: "pnl",
    },
    {
      key: "unrealized_pnl",
      label: "Unrealized",
      format: formatCurrency,
      type: "pnl",
    },
    {
      key: "expected_pnl",
      label: "Expected P&L",
      format: formatCurrency,
      type: "expected",
      source: "performance",
    },
    {
      key: "slippage",
      label: "Slippage",
      format: formatCurrency,
      type: "slippage",
      source: "performance",
    },
    {
      key: "total_trades",
      label: "Trades",
      format: (v) => v?.toString() || "0",
    },
    { key: "win_rate", label: "Win Rate", format: (v) => formatPct(v) },
    {
      key: "avg_edge_entry",
      label: "Avg Edge",
      format: (v) => `${(v || 0).toFixed(2)}%`,
    },
    {
      key: "max_drawdown_pct",
      label: "Max DD %",
      format: (v) => formatPct(v),
      type: "negative",
    },
    {
      key: "risk_utilization",
      label: "Risk Used",
      format: (v) => formatPct(v),
    },
    {
      key: "sharpe_like_score",
      label: "Sharpe Score",
      format: (v) => (v || 0).toFixed(2),
      source: "performance",
    },
    {
      key: "target_hit_rate",
      label: "Target Hit %",
      format: (v) => formatPct(v),
      source: "performance",
    },
    {
      key: "stop_hit_rate",
      label: "Stop Hit %",
      format: (v) => formatPct(v),
      source: "performance",
      type: "negative",
    },
  ];

  const strategyIds = Object.keys(strategies || {});

  return (
    <Card data-testid="comparison-table">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5" />
          Performance Comparison (Expected vs Actual)
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 px-3 text-muted-foreground">
                  Metric
                </th>
                {strategyIds.map((sid) => {
                  const config = MODEL_CONFIG[sid] || { name: sid };
                  return (
                    <th
                      key={sid}
                      className={`text-center py-2 px-3 ${MODEL_CONFIG[sid]?.textClass || ""}`}
                    >
                      {config.name}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {metrics.map((metric) => (
                <tr
                  key={metric.key}
                  className="border-b border-border/50 hover:bg-muted/30"
                >
                  <td className="py-2 px-3 text-muted-foreground">
                    {metric.label}
                  </td>
                  {strategyIds.map((sid) => {
                    let value;
                    if (metric.source === "performance") {
                      value = performanceData?.[sid]?.[metric.key];
                    } else {
                      value = comparison?.[metric.key]?.[sid];
                    }

                    let colorClass = "";
                    if (metric.type === "pnl") {
                      colorClass =
                        value >= 0 ? "text-green-400" : "text-red-400";
                    } else if (metric.type === "expected") {
                      colorClass = "text-blue-400";
                    } else if (metric.type === "slippage") {
                      colorClass =
                        value > 0 ? "text-orange-400" : "text-green-400";
                    } else if (metric.type === "negative") {
                      colorClass = "text-orange-400";
                    }

                    return (
                      <td
                        key={sid}
                        className={`text-center py-2 px-3 ${colorClass}`}
                      >
                        {metric.format(value)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
};

// League Performance Breakdown Component
const LeaguePerformanceTable = ({ performanceData }) => {
  const leagues = ["NBA", "NCAA_M", "NCAA_W", "EUROLEAGUE", "ABA", "OTHER"];
  const models = Object.keys(MODEL_CONFIG);

  return (
    <Card data-testid="league-performance-table">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Target className="w-5 h-5" />
          Performance by League
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 px-3 text-muted-foreground">
                  League
                </th>
                {models.map((mid) => (
                  <th
                    key={mid}
                    colSpan={2}
                    className={`text-center py-2 px-3 ${MODEL_CONFIG[mid]?.textClass}`}
                  >
                    {MODEL_CONFIG[mid]?.name}
                  </th>
                ))}
              </tr>
              <tr className="border-b border-border/50 text-xs">
                <th></th>
                {models.map((mid) => (
                  <React.Fragment key={mid}>
                    <th className="text-center py-1 px-2 text-muted-foreground">
                      Win%
                    </th>
                    <th className="text-center py-1 px-2 text-muted-foreground">
                      P&L
                    </th>
                  </React.Fragment>
                ))}
              </tr>
            </thead>
            <tbody>
              {leagues.map((league) => (
                <tr
                  key={league}
                  className="border-b border-border/50 hover:bg-muted/30"
                >
                  <td className="py-2 px-3 font-medium">{league}</td>
                  {models.map((mid) => {
                    const leagueData =
                      performanceData?.[mid]?.by_league?.[league] || {};
                    return (
                      <React.Fragment key={mid}>
                        <td className="text-center py-2 px-2 text-muted-foreground">
                          {formatPct(leagueData.win_rate || 0)}
                        </td>
                        <td
                          className={`text-center py-2 px-2 ${(leagueData.total_pnl || 0) >= 0 ? "text-green-400" : "text-red-400"}`}
                        >
                          {formatCurrency(leagueData.total_pnl || 0)}
                        </td>
                      </React.Fragment>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
};

// Game Positions Table (unchanged but with enhancements)
const GamePositionsTable = ({ gamePositions }) => {
  const games = Object.entries(gamePositions || {});

  if (games.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="w-5 h-5" />
            Active Game Positions
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-center py-8">
            No active positions
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card data-testid="game-positions-table">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="w-5 h-5" />
          Active Game Positions
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 px-3 text-muted-foreground">
                  Game
                </th>
                {Object.keys(MODEL_CONFIG).map((sid) => {
                  const config = MODEL_CONFIG[sid];
                  return (
                    <th
                      key={sid}
                      className={`text-center py-2 px-3 ${config.textClass}`}
                    >
                      {config.name}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {games.map(([gameId, positions]) => (
                <tr
                  key={gameId}
                  className="border-b border-border/50 hover:bg-muted/30"
                >
                  <td className="py-2 px-3 font-mono text-xs">
                    {gameId.substring(0, 20)}...
                  </td>
                  {Object.keys(MODEL_CONFIG).map((sid) => {
                    const pos = positions[sid];
                    if (!pos?.has_position) {
                      return (
                        <td
                          key={sid}
                          className="text-center py-2 px-3 text-muted-foreground"
                        >
                          -
                        </td>
                      );
                    }
                    return (
                      <td key={sid} className="text-center py-2 px-3">
                        <div>
                          <Badge
                            variant={
                              pos.side === "yes" ? "default" : "secondary"
                            }
                            className="text-xs"
                          >
                            {pos.side?.toUpperCase()} {pos.quantity}
                          </Badge>
                          <p
                            className={`text-xs mt-1 ${pos.unrealized_pnl >= 0 ? "text-green-400" : "text-red-400"}`}
                          >
                            {formatCurrency(pos.unrealized_pnl)}
                          </p>
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
};

// ─── Recent Trades Panel ──────────────────────────────────────────────────
const ACTION_STYLE = {
  ENTER: {
    bg: "bg-emerald-500/10 border-emerald-500/40",
    text: "text-emerald-400",
    icon: LogIn,
  },
  EXIT: {
    bg: "bg-red-500/10 border-red-500/40",
    text: "text-red-400",
    icon: LogOut,
  },
};

const EXIT_REASON_COLOR = (reason = "") => {
  const r = reason.toLowerCase();
  if (r.includes("profit") || r.includes("target"))
    return "text-emerald-400 bg-emerald-500/10";
  if (r.includes("stop") || r.includes("loss"))
    return "text-red-400 bg-red-500/10";
  if (r.includes("compress") || r.includes("edge"))
    return "text-yellow-400 bg-yellow-500/10";
  if (r.includes("time") || r.includes("max hold"))
    return "text-orange-400 bg-orange-500/10";
  return "text-muted-foreground bg-muted";
};

const ReasonChip = ({ text, color }) => (
  <span
    className={`inline-block px-2 py-0.5 rounded text-xs font-medium border border-white/10 ${color}`}
  >
    {text}
  </span>
);

const RecentTradesPanel = ({ decisions }) => {
  const trades = (decisions || [])
    .filter((r) => r.action === "ENTER" || r.action === "EXIT")
    .slice(0, 20);

  if (!trades.length) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <List className="w-8 h-8 mx-auto mb-2 opacity-40" />
        <p className="text-sm">No trade decisions recorded today.</p>
        <p className="text-xs mt-1 opacity-60">
          Decisions appear once the strategy loop runs live.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {trades.map((rec, i) => {
        const style = ACTION_STYLE[rec.action] || ACTION_STYLE.ENTER;
        const Icon = style.icon;
        const ticker = (rec.market_ticker || rec.event_id || "—").slice(0, 30);
        const modelShort = (rec.model_id || "")
          .replace("model_", "")
          .replace("_disciplined", "A")
          .replace("_high_frequency", "B")
          .replace("_institutional", "C")
          .toUpperCase()
          .slice(0, 1);
        const edgePct = ((rec.edge || 0) * 100).toFixed(1);
        const ts = rec.ts
          ? new Date(rec.ts).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })
          : "";

        // Chips
        const entryReasonChips = (rec.reason_codes || [])
          .filter((c) => c.endsWith("_OK"))
          .map((c) => c.replace("_OK", "").replace(/_/g, " ").toLowerCase())
          .slice(0, 4);

        const exitText = rec.exit_reason || "";

        return (
          <div
            key={i}
            className={`flex flex-wrap items-start gap-3 p-3 rounded-lg border ${style.bg}`}
          >
            {/* Action + time */}
            <div className="flex items-center gap-2 min-w-[90px]">
              <Icon className={`w-4 h-4 ${style.text}`} />
              <div>
                <span className={`text-xs font-bold ${style.text}`}>
                  {rec.action}
                </span>
                <p className="text-xs text-muted-foreground">{ts}</p>
              </div>
            </div>

            {/* Ticker + model */}
            <div className="flex-1 min-w-[140px]">
              <p
                className="text-xs font-mono font-medium truncate"
                title={rec.market_ticker}
              >
                {ticker}
              </p>
              <div className="flex items-center gap-1 mt-0.5">
                <Badge variant="outline" className="text-[10px] h-4 px-1">
                  Model {modelShort}
                </Badge>
                {rec.edge != null && (
                  <span
                    className={`text-[10px] font-medium ${parseFloat(edgePct) >= 0 ? "text-emerald-400" : "text-red-400"}`}
                  >
                    edge {edgePct}%
                  </span>
                )}
              </div>
            </div>

            {/* Reason chips */}
            <div className="flex flex-wrap gap-1 items-center flex-1">
              {rec.action === "ENTER" &&
                entryReasonChips.map((chip, ci) => (
                  <ReasonChip
                    key={ci}
                    text={chip}
                    color="text-emerald-300 bg-emerald-500/10"
                  />
                ))}
              {rec.action === "EXIT" && exitText && (
                <ReasonChip
                  text={exitText.split(":")[0].trim().slice(0, 40)}
                  color={EXIT_REASON_COLOR(exitText)}
                />
              )}
              {rec.human_summary && (
                <span
                  className="text-[10px] text-muted-foreground block w-full mt-0.5 truncate"
                  title={rec.human_summary}
                >
                  {rec.human_summary.slice(0, 80)}
                  {rec.human_summary.length > 80 ? "…" : ""}
                </span>
              )}
            </div>

            {/* PnL for EXIT */}
            {rec.action === "EXIT" && rec.pnl_realized_usd != null && (
              <div
                className={`text-xs font-bold ${rec.pnl_realized_usd >= 0 ? "text-emerald-400" : "text-red-400"}`}
              >
                {rec.pnl_realized_usd >= 0 ? "+" : ""}
                {rec.pnl_realized_usd.toFixed(2)}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

// ─── Rejected Reasons Chart ──────────────────────────────────────────────────
const REJECT_LABEL_MAP = {
  SPREAD_FILTER: "Spread too wide",
  MIN_EDGE: "EV / Edge too low",
  MIN_SIGNAL_SCORE: "Signal score too low",
  EDGE_PERSISTENCE: "Edge not persistent",
  LEAGUE_FILTER: "League filter",
  CIRCUIT_BREAKER: "Circuit breaker",
  DAILY_LOSS_CAP: "Daily loss cap",
  MAX_POSITIONS: "Max positions",
  COOLDOWN: "Cooldown active",
  MAX_ENTRIES: "Max entries/game",
};

const prettyRejectLabel = (code = "") => {
  const base = code.replace(/_FAIL$/, "").replace(/_OK$/, "");
  return REJECT_LABEL_MAP[base] || base.replace(/_/g, " ").toLowerCase();
};

const RejectedReasonsChart = ({ decisions }) => {
  // Aggregate reason_code FAIL counts from BLOCK / NO_TRADE records
  const counts = {};
  (decisions || []).forEach((rec) => {
    if (
      rec.action === "ENTER" ||
      rec.action === "EXIT" ||
      rec.action === "HOLD"
    )
      return;
    (rec.reason_codes || [])
      .filter((c) => c.endsWith("_FAIL"))
      .forEach((code) => {
        counts[code] = (counts[code] || 0) + 1;
      });
    // Also count plain decision reasons from BLOCK records
    if (rec.exit_reason) {
      const key = rec.exit_reason.slice(0, 40);
      counts[key] = (counts[key] || 0) + 1;
    }
  });

  const sorted = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  if (!sorted.length) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <BarChart3 className="w-8 h-8 mx-auto mb-2 opacity-40" />
        <p className="text-sm">No rejection data yet.</p>
      </div>
    );
  }

  const maxVal = sorted[0][1];

  return (
    <div className="space-y-2.5">
      {sorted.map(([code, count], i) => {
        const pct = maxVal > 0 ? (count / maxVal) * 100 : 0;
        const isTop = i === 0;
        return (
          <div key={code} className="flex items-center gap-3">
            <div
              className="text-xs text-muted-foreground w-44 text-right truncate flex-shrink-0"
              title={prettyRejectLabel(code)}
            >
              {prettyRejectLabel(code)}
            </div>
            <div className="flex-1 h-5 bg-muted/30 rounded overflow-hidden">
              <div
                className={`h-full rounded transition-all duration-500 ${
                  isTop ? "bg-orange-500/70" : "bg-orange-500/30"
                }`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <div
              className={`text-xs font-bold w-8 text-right ${isTop ? "text-orange-400" : "text-muted-foreground"}`}
            >
              {count}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// Main Component
export default function EnhancedStrategyCommandCenter() {
  const [summary, setSummary] = useState(null);
  const [gamePositions, setGamePositions] = useState({});
  const [rulesData, setRulesData] = useState({});
  const [performanceData, setPerformanceData] = useState({});
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [isStale, setIsStale] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [editingModel, setEditingModel] = useState(null);
  const [editingRules, setEditingRules] = useState({});
  const [editingErrors, setEditingErrors] = useState({});
  const [recentDecisions, setRecentDecisions] = useState([]);
  const [debugBundleLoading, setDebugBundleLoading] = useState(false);

  // Fetch data
  const fetchData = useCallback(async () => {
    try {
      const [summaryRes, positionsRes, performanceRes, decisionsRes] =
        await Promise.all([
          fetch(`${API_BASE}/api/strategies/summary`),
          fetch(`${API_BASE}/api/strategies/positions/by_game`),
          fetch(`${API_BASE}/api/performance/models`),
          fetch(`${API_BASE}/api/decisions/latest?limit=200`),
        ]);

      if (summaryRes.ok) {
        const summaryData = await summaryRes.json();
        setSummary(summaryData);

        // Fetch rules for each strategy
        const rulesPromises = Object.keys(summaryData.strategies || {}).map(
          async (sid) => {
            try {
              const rulesRes = await fetch(
                `${API_BASE}/api/rules/${sid}?league=BASE`,
              );
              if (rulesRes.ok) {
                return { id: sid, data: await rulesRes.json() };
              }
            } catch (e) {
              console.error(`Failed to fetch rules for ${sid}:`, e);
            }
            return { id: sid, data: null };
          },
        );

        const rulesResults = await Promise.all(rulesPromises);
        const rulesMap = {};
        rulesResults.forEach((r) => {
          if (r.data) rulesMap[r.id] = r.data;
        });
        setRulesData(rulesMap);
      }

      if (positionsRes.ok) {
        const posData = await positionsRes.json();
        setGamePositions(posData);
      }

      if (performanceRes.ok) {
        const perfData = await performanceRes.json();
        setPerformanceData(perfData);
      }

      if (decisionsRes.ok) {
        const decisionsData = await decisionsRes.json();
        setRecentDecisions(decisionsData.records || []);
      }

      setLastUpdate(new Date());
      setIsStale(false);
      setError(null);
    } catch (err) {
      console.error("Failed to fetch strategy data:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch and polling
  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000); // Update every 3 seconds
    return () => clearInterval(interval);
  }, [fetchData]);

  // Stale detection
  useEffect(() => {
    const staleCheck = setInterval(() => {
      if (lastUpdate && new Date() - lastUpdate > 10000) {
        setIsStale(true);
      }
    }, 1000);
    return () => clearInterval(staleCheck);
  }, [lastUpdate]);

  // Control functions
  const toggleStrategies = async (enable) => {
    try {
      await fetch(
        `${API_BASE}/api/strategies/${enable ? "enable" : "disable"}`,
        { method: "POST" },
      );
      fetchData();
    } catch (err) {
      console.error("Failed to toggle strategies:", err);
    }
  };

  const activateKillSwitch = async () => {
    if (
      window.confirm(
        "EMERGENCY: This will stop ALL strategies immediately. Continue?",
      )
    ) {
      try {
        await fetch(`${API_BASE}/api/strategies/kill_switch`, {
          method: "POST",
        });
        fetchData();
      } catch (err) {
        console.error("Failed to activate kill switch:", err);
      }
    }
  };

  const deactivateKillSwitch = async () => {
    try {
      await fetch(`${API_BASE}/api/strategies/kill_switch`, {
        method: "DELETE",
      });
      fetchData();
    } catch (err) {
      console.error("Failed to deactivate kill switch:", err);
    }
  };

  const toggleEvaluationMode = async (enabled) => {
    try {
      await fetch(
        `${API_BASE}/api/strategies/evaluation_mode?enabled=${enabled}`,
        { method: "POST" },
      );
      fetchData();
    } catch (err) {
      console.error("Failed to toggle evaluation mode:", err);
    }
  };

  const toggleAutoMode = async (enabled) => {
    try {
      const endpoint = enabled
        ? "/api/autonomous/enable"
        : "/api/autonomous/disable";
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        credentials: "include",
      });

      // Safely read the response body once regardless of content-type
      let data = {};
      try {
        const text = await res.text();
        if (text) data = JSON.parse(text);
      } catch {
        // body was empty or non-JSON — treat as success if status is ok
      }

      if (!res.ok) {
        throw new Error(
          `Server error: ${res.status} - ${data.detail || data.message || "Unknown error"}`,
        );
      }

      console.log("Auto mode toggled:", data);
      fetchData();
    } catch (err) {
      console.error("Failed to toggle auto mode:", err);
      alert(`Failed to toggle auto mode: ${err.message}`);
    }
  };

  const resetStrategy = async (strategyId) => {
    if (
      window.confirm(
        `Reset portfolio for ${strategyId}? This cannot be undone.`,
      )
    ) {
      try {
        await fetch(`${API_BASE}/api/strategies/${strategyId}/reset`, {
          method: "POST",
        });
        fetchData();
      } catch (err) {
        console.error("Failed to reset strategy:", err);
      }
    }
  };

  const handleEditModel = (modelId) => {
    const model = rulesData[modelId];
    if (model) {
      setEditingModel(modelId);
      setEditingRules(JSON.parse(JSON.stringify(model)));
      setEditingErrors({});
    }
  };

  const replaceWithModel = (newModelId) => {
    // Save current editing model's rules (locally) before switching
    setRulesData((prev) => ({
      ...prev,
      [editingModel]: editingRules,
    }));
    // Switch to new model
    const newModel = rulesData[newModelId];
    if (newModel) {
      setEditingModel(newModelId);
      setEditingRules(JSON.parse(JSON.stringify(newModel)));
      setEditingErrors({});
    }
  };

  const handleSaveRules = async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/rules/${editingModel}/update?league=BASE`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          credentials: "include",
          body: JSON.stringify({
            config: editingRules,
            change_summary: "Manual adjustment via UI",
          }),
        },
      );

      if (!res.ok) {
        // Try to parse error response
        let errorMessage = `Server error: ${res.status}`;
        try {
          const errorData = await res.json();
          errorMessage =
            errorData.errors?.general || errorData.detail || errorMessage;
        } catch {
          // Could not parse error response
        }

        setEditingErrors({ general: errorMessage });
        return;
      }

      // Successfully saved - now fetch fresh rules from backend
      console.log(
        "Rules saved successfully, fetching fresh data from backend...",
      );

      try {
        const freshRes = await fetch(
          `${API_BASE}/api/rules/${editingModel}?league=BASE`,
          {
            headers: { Accept: "application/json" },
            credentials: "include",
          },
        );

        if (freshRes.ok) {
          const freshData = await freshRes.json();
          console.log("Fresh rules loaded from backend:", freshData);

          // Update with fresh data from backend
          // The GET endpoint returns full object with config, rule_chips, etc.
          setRulesData((prev) => ({
            ...prev,
            [editingModel]: freshData,
          }));
        } else {
          console.warn(
            "Failed to fetch fresh rules, using local data:",
            freshRes.status,
          );
          // If fetch fails, at least use the local data we just saved
          setRulesData((prev) => ({
            ...prev,
            [editingModel]: editingRules,
          }));
        }
      } catch (fetchErr) {
        console.warn(
          "Could not fetch fresh rules, using local data:",
          fetchErr,
        );
        // Fallback to local data
        setRulesData((prev) => ({
          ...prev,
          [editingModel]: editingRules,
        }));
      }

      setEditingModel(null);
      setEditingRules({});
      setEditingErrors({});
      alert("Rules updated successfully!");
    } catch (err) {
      console.error("Failed to save rules:", err);
      setEditingErrors({ general: err.message });
    }
  };

  const updateEditingRule = (field, value) => {
    setEditingRules((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const downloadDebugBundle = async () => {
    setDebugBundleLoading(true);
    try {
      const today = new Date().toISOString().split("T")[0];
      const res = await fetch(`${API_BASE}/api/debug/bundle?date=${today}`);
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `debug_bundle_${today.replace(/-/g, "")}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Debug bundle download failed:", err);
      alert(`Download failed: ${err.message}`);
    } finally {
      setDebugBundleLoading(false);
    }
  };

  const exportDailyReport = async (format) => {
    try {
      const res = await fetch(
        `${API_BASE}/api/strategies/report/daily/export?format=${format}`,
      );
      const data = await res.json();

      const blob = new Blob(
        [format === "csv" ? data.data : JSON.stringify(data, null, 2)],
        { type: format === "csv" ? "text/csv" : "application/json" },
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `strategy_report.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to export report:", err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
      </div>
    );
  }

  const strategies = summary?.strategies || {};
  const winningModel = summary?.winning_model;
  const bestRiskAdjusted = summary?.best_risk_adjusted;

  return (
    <div className="min-h-screen bg-background">
      {/* Page Header */}
      <header className="border-b border-border bg-card/50">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <Activity className="w-6 h-6 text-primary" />
                Strategy Command Center
              </h1>
              <p className="text-sm text-muted-foreground">
                Multi-Model Capital Intelligence • Paper Trading
              </p>
              {/* Active config version badges */}
              <div className="flex items-center gap-1.5 mt-1.5">
                {Object.entries(strategies).map(([sid]) => {
                  const cfg = MODEL_CONFIG[sid];
                  if (!cfg) return null;
                  return (
                    <span
                      key={sid}
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border ${cfg.bgClass} ${cfg.textClass}`}
                      title={`${cfg.name} — ${sid}`}
                    >
                      {cfg.name}
                    </span>
                  );
                })}
                {Object.keys(strategies).length > 0 && (
                  <span className="text-[10px] text-muted-foreground ml-1">
                    running
                  </span>
                )}
              </div>
            </div>

            {/* Engine Status Indicators */}
            <div className="flex items-center gap-4">
              {/* Paper Engine Status */}
              <div
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${
                  summary?.evaluation_mode
                    ? "bg-blue-500/10 border-blue-500/50"
                    : "bg-gray-500/10 border-gray-500/50"
                }`}
                data-testid="paper-engine-status"
              >
                <div
                  className={`w-2 h-2 rounded-full ${summary?.evaluation_mode ? "bg-blue-500 animate-pulse" : "bg-gray-500"}`}
                />
                <span
                  className={`text-xs font-medium ${summary?.evaluation_mode ? "text-blue-400" : "text-gray-400"}`}
                >
                  Paper Engine:{" "}
                  {summary?.evaluation_mode ? "RUNNING" : "STOPPED"}
                </span>
              </div>

              {/* Live Engine Status */}
              <div
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${
                  summary?.auto_mode
                    ? "bg-purple-500/10 border-purple-500/50"
                    : "bg-gray-500/10 border-gray-500/50"
                }`}
                data-testid="live-engine-status"
              >
                <div
                  className={`w-2 h-2 rounded-full ${summary?.auto_mode ? "bg-purple-500 animate-pulse" : "bg-gray-500"}`}
                />
                <span
                  className={`text-xs font-medium ${summary?.auto_mode ? "text-purple-400" : "text-gray-400"}`}
                >
                  Live Engine: {summary?.auto_mode ? "RUNNING" : "STOPPED"}
                </span>
              </div>

              <div
                className={`flex items-center gap-2 text-xs ${isStale ? "text-red-400" : "text-muted-foreground"}`}
              >
                {isStale ? (
                  <AlertCircle className="w-4 h-4" />
                ) : (
                  <CheckCircle2 className="w-4 h-4 text-green-400" />
                )}
                {lastUpdate
                  ? `Updated ${Math.round((new Date() - lastUpdate) / 1000)}s ago`
                  : "-"}
              </div>

              <Button variant="outline" size="sm" onClick={fetchData}>
                <RefreshCw className="w-4 h-4 mr-1" />
                Refresh
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Control Panel */}
        <Card
          data-testid="control-panel"
          className="border-2 border-primary/30"
        >
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Shield className="w-5 h-5" />
              Control Panel
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center gap-6">
              <div className="flex items-center gap-3">
                <span className="text-sm">Strategies:</span>
                <Switch
                  checked={summary?.enabled}
                  onCheckedChange={toggleStrategies}
                  data-testid="strategies-toggle"
                />
                <Badge variant={summary?.enabled ? "default" : "secondary"}>
                  {summary?.enabled ? "Enabled" : "Disabled"}
                </Badge>
              </div>

              {/* Evaluation Mode Radio Buttons */}
              <div className="flex items-center gap-3 p-2 rounded-lg bg-muted/30">
                <span className="text-sm font-medium">Evaluation Mode:</span>
                <div className="flex items-center gap-4">
                  <label
                    className="flex items-center gap-2 cursor-pointer"
                    data-testid="evaluation-on-radio"
                  >
                    <input
                      type="radio"
                      name="evaluationMode"
                      checked={summary?.evaluation_mode === true}
                      onChange={() => toggleEvaluationMode(true)}
                      className="w-4 h-4 text-green-500 bg-background border-border focus:ring-green-500"
                    />
                    <span
                      className={`text-sm ${summary?.evaluation_mode ? "text-green-400 font-medium" : "text-muted-foreground"}`}
                    >
                      ON
                    </span>
                  </label>
                  <label
                    className="flex items-center gap-2 cursor-pointer"
                    data-testid="evaluation-off-radio"
                  >
                    <input
                      type="radio"
                      name="evaluationMode"
                      checked={summary?.evaluation_mode === false}
                      onChange={() => toggleEvaluationMode(false)}
                      className="w-4 h-4 text-red-500 bg-background border-border focus:ring-red-500"
                    />
                    <span
                      className={`text-sm ${!summary?.evaluation_mode ? "text-red-400 font-medium" : "text-muted-foreground"}`}
                    >
                      OFF
                    </span>
                  </label>
                </div>
                {summary?.evaluation_mode && (
                  <Badge className="bg-green-500/20 text-green-400 border-green-500/50">
                    Paper Trading Active
                  </Badge>
                )}
              </div>

              {/* Auto Mode Radio Buttons */}
              <div className="flex items-center gap-3 p-2 rounded-lg bg-muted/30">
                <span className="text-sm font-medium">Auto Mode:</span>
                <div className="flex items-center gap-4">
                  <label
                    className="flex items-center gap-2 cursor-pointer"
                    data-testid="auto-mode-on-radio"
                  >
                    <input
                      type="radio"
                      name="autoMode"
                      checked={summary?.auto_mode === true}
                      onChange={() => toggleAutoMode(true)}
                      className="w-4 h-4 text-green-500 bg-background border-border focus:ring-green-500"
                    />
                    <span
                      className={`text-sm ${summary?.auto_mode ? "text-green-400 font-medium" : "text-muted-foreground"}`}
                    >
                      ON
                    </span>
                  </label>
                  <label
                    className="flex items-center gap-2 cursor-pointer"
                    data-testid="auto-mode-off-radio"
                  >
                    <input
                      type="radio"
                      name="autoMode"
                      checked={summary?.auto_mode !== true}
                      onChange={() => toggleAutoMode(false)}
                      className="w-4 h-4 text-red-500 bg-background border-border focus:ring-red-500"
                    />
                    <span
                      className={`text-sm ${!summary?.auto_mode ? "text-red-400 font-medium" : "text-muted-foreground"}`}
                    >
                      OFF
                    </span>
                  </label>
                </div>
                {summary?.auto_mode && (
                  <Badge className="bg-purple-500/20 text-purple-400 border-purple-500/50 animate-pulse">
                    Live Trading Enabled
                  </Badge>
                )}
              </div>

              {summary?.kill_switch_active ? (
                <Button
                  variant="outline"
                  className="border-green-500 text-green-500"
                  onClick={deactivateKillSwitch}
                  data-testid="deactivate-kill-switch"
                >
                  Deactivate Kill Switch
                </Button>
              ) : (
                <Button
                  variant="destructive"
                  onClick={activateKillSwitch}
                  data-testid="kill-switch-btn"
                >
                  <AlertTriangle className="w-4 h-4 mr-2" />
                  KILL SWITCH
                </Button>
              )}

              <div className="flex gap-2 ml-auto">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => exportDailyReport("json")}
                >
                  <Download className="w-4 h-4 mr-1" />
                  JSON
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => exportDailyReport("csv")}
                >
                  <Download className="w-4 h-4 mr-1" />
                  CSV
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={downloadDebugBundle}
                  disabled={debugBundleLoading}
                  className="border-violet-500/50 text-violet-400 hover:bg-violet-500/10"
                  title="Download a ZIP with decision traces, configs and metrics for today"
                >
                  {debugBundleLoading ? (
                    <RefreshCw className="w-4 h-4 mr-1 animate-spin" />
                  ) : (
                    <FileArchive className="w-4 h-4 mr-1" />
                  )}
                  Debug Bundle
                </Button>
              </div>
            </div>

            {summary?.kill_switch_active && (
              <div className="mt-4 p-3 bg-red-500/20 border border-red-500 rounded-lg flex items-center gap-3">
                <AlertTriangle className="w-6 h-6 text-red-500" />
                <div>
                  <p className="font-bold text-red-400">KILL SWITCH ACTIVE</p>
                  <p className="text-sm text-red-300">
                    All strategies stopped. Deactivate to resume.
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid grid-cols-6 w-full max-w-3xl">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="dashboard">24hr Dashboard</TabsTrigger>
            <TabsTrigger value="comparison">Comparison</TabsTrigger>
            <TabsTrigger value="league">By League</TabsTrigger>
            <TabsTrigger value="positions">Positions</TabsTrigger>
            <TabsTrigger value="activity">Activity</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-4 space-y-4">
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(strategies).map(([sid, data]) => (
                <div key={sid} className="relative">
                  <EnhancedStrategySummaryCard
                    strategyId={sid}
                    data={data}
                    isWinning={sid === winningModel}
                    isBestRiskAdjusted={sid === bestRiskAdjusted}
                    ruleChips={rulesData[sid]?.rule_chips}
                    performanceMetrics={performanceData[sid]}
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleEditModel(sid)}
                    className="absolute top-2 right-2 h-8 w-8 p-0"
                    title="Edit Rules"
                  >
                    <Settings className="w-4 h-4" />
                  </Button>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="dashboard" className="mt-4">
            <AutonomousDashboard />
          </TabsContent>

          <TabsContent value="comparison" className="mt-4">
            <EnhancedComparisonTable
              comparison={summary?.comparison}
              strategies={strategies}
              performanceData={performanceData}
            />
          </TabsContent>

          <TabsContent value="league" className="mt-4">
            <LeaguePerformanceTable performanceData={performanceData} />
          </TabsContent>

          <TabsContent value="positions" className="mt-4">
            <GamePositionsTable gamePositions={gamePositions} />
          </TabsContent>

          <TabsContent value="activity" className="mt-4 space-y-4">
            {/* Last 20 Trades */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <List className="w-5 h-5" />
                    Last 20 Trade Decisions
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant="outline"
                      className="text-emerald-400 border-emerald-500/40"
                    >
                      {
                        recentDecisions.filter((r) => r.action === "ENTER")
                          .length
                      }{" "}
                      ENTER
                    </Badge>
                    <Badge
                      variant="outline"
                      className="text-red-400 border-red-500/40"
                    >
                      {
                        recentDecisions.filter((r) => r.action === "EXIT")
                          .length
                      }{" "}
                      EXIT
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <RecentTradesPanel decisions={recentDecisions} />
              </CardContent>
            </Card>

            {/* Rejected Reasons Chart */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <XCircle className="w-5 h-5 text-orange-400" />
                    Top Rejection Reasons
                  </CardTitle>
                  <Badge
                    variant="outline"
                    className="text-orange-400 border-orange-500/40"
                  >
                    {
                      recentDecisions.filter(
                        (r) =>
                          r.action !== "ENTER" &&
                          r.action !== "EXIT" &&
                          r.action !== "HOLD",
                      ).length
                    }{" "}
                    blocked
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <RejectedReasonsChart decisions={recentDecisions} />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Reset Controls */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">
              Admin Controls
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {Object.keys(strategies).map((sid) => {
                const config = MODEL_CONFIG[sid] || { name: sid };
                return (
                  <Button
                    key={sid}
                    variant="outline"
                    size="sm"
                    onClick={() => resetStrategy(sid)}
                    className="text-xs"
                  >
                    Reset {config.name}
                  </Button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Edit Rules Modal */}
        {editingModel && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <Card className="w-full max-w-2xl max-h-[80vh] overflow-auto">
              <CardHeader>
                <div className="flex items-center justify-between gap-4">
                  <CardTitle>
                    Edit Model Rules - {MODEL_CONFIG[editingModel]?.name}
                  </CardTitle>
                  <select
                    value={editingModel}
                    onChange={(e) => replaceWithModel(e.target.value)}
                    className="px-3 py-2 bg-background border border-border rounded text-sm text-foreground cursor-pointer"
                  >
                    <option value="model_a_disciplined">
                      Model A - Disciplined
                    </option>
                    <option value="model_b_high_frequency">
                      Model B - High Frequency
                    </option>
                    <option value="model_c_institutional">
                      Model C - Institutional
                    </option>
                    <option value="model_d_growth_focused">
                      Model D - Growth Focused
                    </option>
                    <option value="model_e_balanced_hunter">
                      Model E - Balanced Hunter
                    </option>
                  </select>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                {editingErrors.general && (
                  <div className="p-3 bg-red-500/20 border border-red-500 rounded text-red-400 text-sm">
                    {editingErrors.general}
                  </div>
                )}

                <div className="max-h-[50vh] overflow-y-auto space-y-4 pr-4">
                  {Object.entries(editingRules).map(([key, value]) => (
                    <div
                      key={key}
                      className="space-y-2 border-l-2 border-blue-500/30 pl-4"
                    >
                      <label className="text-sm font-semibold text-gray-300 capitalize">
                        {key.replace(/_/g, " ")}
                      </label>
                      {typeof value === "string" ? (
                        <input
                          type="text"
                          value={value}
                          onChange={(e) =>
                            updateEditingRule(key, e.target.value)
                          }
                          className="w-full px-3 py-2 bg-background border border-border rounded text-sm text-foreground"
                        />
                      ) : typeof value === "number" ? (
                        <input
                          type="number"
                          value={value}
                          onChange={(e) =>
                            updateEditingRule(key, Number(e.target.value))
                          }
                          className="w-full px-3 py-2 bg-background border border-border rounded text-sm text-foreground"
                        />
                      ) : (
                        <textarea
                          value={JSON.stringify(value, null, 2)}
                          onChange={(e) => {
                            try {
                              updateEditingRule(
                                key,
                                JSON.parse(e.target.value),
                              );
                            } catch {
                              // Invalid JSON, keep as is
                            }
                          }}
                          className="w-full px-3 py-2 bg-background border border-border rounded text-sm text-foreground font-mono"
                          rows="4"
                        />
                      )}
                    </div>
                  ))}
                </div>

                <div className="flex gap-3 justify-end pt-4 border-t border-border">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setEditingModel(null);
                      setEditingRules({});
                      setEditingErrors({});
                    }}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleSaveRules}
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    Save Rules
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="p-4 bg-red-500/20 border border-red-500 rounded-lg">
            <p className="text-red-400">Error: {error}</p>
          </div>
        )}
      </main>
    </div>
  );
}
