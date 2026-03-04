import React, { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import {
  Activity,
  Clock,
  Cpu,
  HardDrive,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Zap,
  Target,
  DollarSign,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Server,
  Power,
  XCircle,
  Eye,
  Filter
} from "lucide-react";

const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

// Format duration
const formatDuration = (seconds) => {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  return `${hours}h ${minutes}m ${secs}s`;
};

// Format relative time
const formatRelativeTime = (isoString) => {
  if (!isoString) return "Never";
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  return `${Math.floor(diffSec / 3600)}h ago`;
};

// Format currency
const formatCurrency = (value, showSign = true) => {
  const num = Number(value) || 0;
  const sign = showSign ? (num >= 0 ? "+" : "") : "";
  return `${sign}$${Math.abs(num).toFixed(2)}`;
};

// Engine Status Banner - TOP PRIORITY COMPONENT
const EngineStatusBanner = ({ health, metrics }) => {
  const isRunning = health?.autonomous_enabled === true;
  
  // Calculate time since last tick
  const getTimeSinceLastTick = () => {
    if (!health?.strategy_loop_last_tick_at) return null;
    const lastTick = new Date(health.strategy_loop_last_tick_at);
    const now = new Date();
    const diffSec = Math.floor((now - lastTick) / 1000);
    return diffSec;
  };
  
  const lastTickSec = getTimeSinceLastTick();
  const isStale = lastTickSec !== null && lastTickSec > 30; // Stale if no tick in 30s
  
  return (
    <div 
      data-testid="engine-status-banner"
      className={`p-4 rounded-lg border-2 mb-4 ${
        isRunning 
          ? isStale 
            ? 'bg-yellow-500/10 border-yellow-500/50' 
            : 'bg-green-500/10 border-green-500/50' 
          : 'bg-red-500/10 border-red-500/50'
      }`}
    >
      {/* Main Status Row */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        {/* Engine Status */}
        <div className="flex items-center gap-3">
          {isRunning ? (
            <>
              <div className={`w-3 h-3 rounded-full ${isStale ? 'bg-yellow-500 animate-pulse' : 'bg-green-500 animate-pulse'}`} />
              <div className="flex items-center gap-2">
                <Power className={`w-5 h-5 ${isStale ? 'text-yellow-400' : 'text-green-400'}`} />
                <span className={`text-lg font-bold ${isStale ? 'text-yellow-400' : 'text-green-400'}`}>
                  ENGINE: RUNNING
                </span>
                <CheckCircle2 className={`w-5 h-5 ${isStale ? 'text-yellow-400' : 'text-green-400'}`} />
              </div>
            </>
          ) : (
            <>
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <div className="flex items-center gap-2">
                <Power className="w-5 h-5 text-red-400" />
                <span className="text-lg font-bold text-red-400">ENGINE: STOPPED</span>
                <XCircle className="w-5 h-5 text-red-400" />
              </div>
            </>
          )}
        </div>
        
        {/* Key Metrics */}
        <div className="flex items-center gap-6 text-sm">
          {/* Last Tick */}
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-muted-foreground" />
            <span className="text-muted-foreground">Last tick:</span>
            <span className={`font-mono font-bold ${lastTickSec !== null && lastTickSec <= 10 ? 'text-green-400' : lastTickSec !== null && lastTickSec <= 30 ? 'text-yellow-400' : 'text-red-400'}`}>
              {lastTickSec !== null ? `${lastTickSec}s ago` : 'Never'}
            </span>
          </div>
          
          {/* Markets Scanned */}
          <div className="flex items-center gap-2">
            <Eye className="w-4 h-4 text-muted-foreground" />
            <span className="text-muted-foreground">Markets scanned:</span>
            <span className="font-mono font-bold text-blue-400">
              {metrics?.markets_scanned_last_min || 0}
            </span>
          </div>
          
          {/* Open Markets */}
          <div className="flex items-center gap-2">
            <Target className="w-4 h-4 text-muted-foreground" />
            <span className="text-muted-foreground">Open markets:</span>
            <Badge className={metrics?.open_markets_found_last_min > 0 ? 'bg-green-500' : 'bg-yellow-500/50'}>
              {metrics?.open_markets_found_last_min || 0}
            </Badge>
          </div>
          
          {/* Next Open ETA */}
          {metrics?.open_markets_found_last_min === 0 && metrics?.next_open_market_eta && (
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-muted-foreground" />
              <span className="text-xs text-yellow-400">
                {metrics.next_open_market_eta}
              </span>
            </div>
          )}
        </div>
      </div>
      
      {/* Secondary Row - Ticks & Uptime */}
      <div className="mt-3 pt-3 border-t border-border/50 flex items-center gap-6 text-xs text-muted-foreground">
        <div>
          <span>Strategy Loop Ticks: </span>
          <span className="font-mono text-foreground">{health?.strategy_loop_ticks_total || 0}</span>
        </div>
        <div>
          <span>Discovery Loop Ticks: </span>
          <span className="font-mono text-foreground">{health?.discovery_loop_ticks_total || 0}</span>
        </div>
        <div>
          <span>Uptime: </span>
          <span className="font-mono text-foreground">{formatDuration(health?.uptime_sec || 0)}</span>
        </div>
        <div>
          <span>DB: </span>
          <Badge variant="outline" className={health?.db_ping ? 'border-green-500 text-green-400' : 'border-red-500 text-red-400'}>
            {health?.db_ping ? 'OK' : 'ERR'}
          </Badge>
        </div>
        <div>
          <span>WS Connections: </span>
          <span className="font-mono text-foreground">{health?.ws_connections || 0}</span>
        </div>
      </div>
    </div>
  );
};

// Why Not Trading Section
const WhyNotTradingCard = ({ metrics }) => {
  const filterReasons = metrics?.filtered_out_reason_counts || {};
  const hasFilters = Object.keys(filterReasons).length > 0;
  const openMarkets = metrics?.open_markets_found_last_min || 0;
  
  // If markets are open and being traded, show success
  if (openMarkets > 0 && metrics?.passed_filter_count > 0) {
    return (
      <Card className="border-border border-green-500/30" data-testid="why-not-trading-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-green-400" />
            Trading Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-green-400">
            <Activity className="w-4 h-4 animate-pulse" />
            <span className="font-medium">Actively evaluating {openMarkets} open markets</span>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            {metrics?.passed_filter_count || 0} markets passed filters, {metrics?.total_evaluated - metrics?.passed_filter_count || 0} filtered out
          </p>
        </CardContent>
      </Card>
    );
  }
  
  return (
    <Card className="border-border border-yellow-500/30" data-testid="why-not-trading-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Filter className="w-4 h-4 text-yellow-400" />
          Why Not Trading?
        </CardTitle>
      </CardHeader>
      <CardContent>
        {openMarkets === 0 ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-yellow-400">
              <Clock className="w-4 h-4" />
              <span className="font-medium">No open markets right now</span>
            </div>
            {metrics?.next_open_market_eta && (
              <p className="text-xs text-muted-foreground">
                {metrics.next_open_market_eta}
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              {metrics?.markets_next_24h_count || 0} markets expected in next 24h
            </p>
          </div>
        ) : hasFilters ? (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground mb-2">
              Markets filtered out for the following reasons:
            </p>
            <div className="space-y-1">
              {Object.entries(filterReasons).map(([reason, count]) => (
                <div key={reason} className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground capitalize">
                    {reason.replace(/_/g, " ")}
                  </span>
                  <Badge variant="secondary" className="text-xs">
                    {count}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No filter data available yet. Enable autonomous mode to start scanning.
          </p>
        )}
      </CardContent>
    </Card>
  );
};

// Scheduler Heartbeat Card
const SchedulerHeartbeatCard = ({ scheduler }) => {
  if (!scheduler || scheduler.scheduler_status === "not_started") {
    return (
      <Card className="border-border border-yellow-500/30" data-testid="scheduler-heartbeat-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Scheduler Status
            <Badge className="bg-yellow-500/20 text-yellow-400">NOT STARTED</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Click "ENABLE AUTO MODE" to start the 2-loop scheduler
          </p>
        </CardContent>
      </Card>
    );
  }
  
  const discoveryAlive = scheduler.discovery_last_tick && 
    (new Date() - new Date(scheduler.discovery_last_tick)) < 120000; // 2 min
  const tradingAlive = scheduler.trading_last_tick && 
    (new Date() - new Date(scheduler.trading_last_tick)) < 10000; // 10 sec
  
  return (
    <Card className="border-border border-green-500/30" data-testid="scheduler-heartbeat-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Activity className="w-4 h-4 text-green-400" />
          Scheduler Heartbeat
          <Badge className="bg-green-500/20 text-green-400">
            {scheduler.scheduler_status?.toUpperCase()}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {/* Discovery Loop */}
          <div className="p-2 rounded bg-blue-500/10">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-blue-400 font-medium">Discovery Loop (30s)</span>
              <Badge variant="outline" className={discoveryAlive ? "border-green-500 text-green-400" : "border-red-500 text-red-400"}>
                {discoveryAlive ? "ALIVE" : "STALE"}
              </Badge>
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div>
                <span className="text-muted-foreground">Last Tick:</span>
                <span className="ml-1 font-mono">{formatRelativeTime(scheduler.discovery_last_tick)}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Total:</span>
                <span className="ml-1 font-mono">{scheduler.discovery_ticks}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Rate:</span>
                <span className="ml-1 font-mono">{scheduler.discovery_rate}/min</span>
              </div>
            </div>
          </div>
          
          {/* Trading Loop */}
          <div className="p-2 rounded bg-purple-500/10">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-purple-400 font-medium">Trading Loop (3s)</span>
              <Badge variant="outline" className={
                scheduler.trading_status === "active" || scheduler.trading_status === "evaluating" 
                  ? "border-green-500 text-green-400" 
                  : "border-yellow-500 text-yellow-400"
              }>
                {scheduler.trading_status?.toUpperCase().replace(/_/g, " ")}
              </Badge>
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div>
                <span className="text-muted-foreground">Last Tick:</span>
                <span className="ml-1 font-mono">{formatRelativeTime(scheduler.trading_last_tick)}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Total:</span>
                <span className="ml-1 font-mono">{scheduler.trading_ticks}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Rate:</span>
                <span className="ml-1 font-mono">{scheduler.trading_rate}/min</span>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// Scanning Metrics Card
const ScanningMetricsCard = ({ scheduler }) => {
  if (!scheduler || scheduler.scheduler_status === "not_started") {
    return null;
  }
  
  return (
    <Card className="border-border" data-testid="scanning-metrics-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Target className="w-4 h-4" />
          Market Scanning
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Scanned counts */}
          <div className="grid grid-cols-2 gap-3">
            <div className="p-2 rounded bg-muted/30 text-center">
              <p className="text-2xl font-bold text-foreground">{scheduler.events_scanned || 0}</p>
              <p className="text-xs text-muted-foreground">Events Scanned</p>
            </div>
            <div className="p-2 rounded bg-muted/30 text-center">
              <p className="text-2xl font-bold text-foreground">{scheduler.markets_scanned || 0}</p>
              <p className="text-xs text-muted-foreground">Markets Scanned</p>
            </div>
          </div>
          
          {/* Open markets indicator */}
          <div className={`p-3 rounded ${scheduler.open_markets > 0 ? 'bg-green-500/20' : 'bg-yellow-500/10'}`}>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Open Markets Now</span>
              <Badge className={scheduler.open_markets > 0 ? 'bg-green-500' : 'bg-yellow-500/50'}>
                {scheduler.open_markets || 0}
              </Badge>
            </div>
            {scheduler.open_markets === 0 && scheduler.next_open_eta && (
              <p className="text-xs text-yellow-400 mt-1">
                {scheduler.next_open_eta}
              </p>
            )}
          </div>
          
          {/* Next 24h counts */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-2 rounded bg-muted/30">
              <p className="text-muted-foreground">Events (24h)</p>
              <p className="font-bold text-lg">{scheduler.next_24h_events || 0}</p>
            </div>
            <div className="p-2 rounded bg-muted/30">
              <p className="text-muted-foreground">Markets (24h)</p>
              <p className="font-bold text-lg">{scheduler.next_24h_markets || 0}</p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// Filter Transparency Card
const FilterTransparencyCard = ({ filters }) => {
  if (!filters || filters.total_evaluated === 0) {
    return (
      <Card className="border-border" data-testid="filter-transparency-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Filter Transparency
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground text-center py-4">
            No markets evaluated yet
          </p>
        </CardContent>
      </Card>
    );
  }
  
  const filterReasons = filters.filtered_out_reason_counts || {};
  
  return (
    <Card className="border-border" data-testid="filter-transparency-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          Filter Transparency
          <Badge variant="outline">{filters.pass_rate_pct}% pass rate</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {/* Summary */}
          <div className="flex justify-between text-xs mb-3">
            <span className="text-green-400">Passed: {filters.passed_filter_count}</span>
            <span className="text-red-400">Filtered: {filters.total_evaluated - filters.passed_filter_count}</span>
            <span className="text-muted-foreground">Total: {filters.total_evaluated}</span>
          </div>
          
          {/* Reason breakdown */}
          <div className="space-y-1">
            {Object.entries(filterReasons).map(([reason, count]) => (
              <div key={reason} className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">
                  {reason.replace(/_/g, " ").toLowerCase()}
                </span>
                <Badge variant="secondary" className="text-xs">
                  {count}
                </Badge>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// System Health Card
const SystemHealthCard = ({ health }) => {
  const getHealthStatus = () => {
    if (health.cpu_percent > 80 || health.memory_percent > 80) return "warning";
    if (health.cpu_percent > 95 || health.memory_percent > 95) return "critical";
    return "healthy";
  };
  
  const status = getHealthStatus();
  const statusColors = {
    healthy: "text-green-400 bg-green-500/10",
    warning: "text-yellow-400 bg-yellow-500/10",
    critical: "text-red-400 bg-red-500/10"
  };
  
  return (
    <Card className="border-border" data-testid="system-health-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Server className="w-4 h-4" />
          System Health
          <Badge className={statusColors[status]}>
            {status.toUpperCase()}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">Uptime</p>
              <p className="font-mono font-medium">{health.uptime_formatted || formatDuration(health.uptime_seconds)}</p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">CPU</p>
              <p className={`font-mono font-medium ${health.cpu_percent > 80 ? 'text-yellow-400' : ''}`}>
                {health.cpu_percent?.toFixed(1)}%
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <HardDrive className="w-4 h-4 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">Memory</p>
              <p className={`font-mono font-medium ${health.memory_percent > 80 ? 'text-yellow-400' : ''}`}>
                {health.memory_used_mb?.toFixed(0)} MB ({health.memory_percent?.toFixed(1)}%)
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">Disk</p>
              <p className="font-mono font-medium">{health.disk_used_percent?.toFixed(1)}%</p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// Performance Summary Card
const PerformanceSummaryCard = ({ performance }) => {
  const isProfitable = performance.total_pnl >= 0;
  
  return (
    <Card className="border-border" data-testid="performance-summary-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <BarChart3 className="w-4 h-4" />
          24-Hour Performance
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* Total PnL */}
        <div className="text-center py-3 mb-4 rounded-lg bg-background/50">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">Total P&L</p>
          <p className={`text-3xl font-bold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
            {formatCurrency(performance.total_pnl)}
          </p>
        </div>
        
        <div className="grid grid-cols-3 gap-3 text-center text-sm mb-4">
          <div>
            <p className="text-xs text-muted-foreground">Realized</p>
            <p className={performance.realized_pnl >= 0 ? 'text-green-400 font-medium' : 'text-red-400 font-medium'}>
              {formatCurrency(performance.realized_pnl)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Unrealized</p>
            <p className={performance.unrealized_pnl >= 0 ? 'text-green-400 font-medium' : 'text-red-400 font-medium'}>
              {formatCurrency(performance.unrealized_pnl)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Max DD</p>
            <p className="text-orange-400 font-medium">
              {formatCurrency(performance.max_drawdown, false)}
            </p>
          </div>
        </div>
        
        <div className="grid grid-cols-4 gap-2 text-xs text-center">
          <div className="p-2 rounded bg-background/30">
            <p className="text-muted-foreground">Trades</p>
            <p className="font-bold text-lg">{performance.total_trades}</p>
          </div>
          <div className="p-2 rounded bg-background/30">
            <p className="text-muted-foreground">Win Rate</p>
            <p className={`font-bold text-lg ${performance.win_rate >= 50 ? 'text-green-400' : 'text-yellow-400'}`}>
              {performance.win_rate?.toFixed(1)}%
            </p>
          </div>
          <div className="p-2 rounded bg-background/30">
            <p className="text-muted-foreground">Sharpe</p>
            <p className={`font-bold text-lg ${performance.sharpe_like_score >= 1 ? 'text-green-400' : 'text-yellow-400'}`}>
              {performance.sharpe_like_score?.toFixed(2)}
            </p>
          </div>
          <div className="p-2 rounded bg-background/30">
            <p className="text-muted-foreground">Avg Trade</p>
            <p className={`font-bold text-lg ${performance.avg_trade_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {formatCurrency(performance.avg_trade_pnl)}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// Activity Metrics Card
const ActivityMetricsCard = ({ totals, recentMinutes }) => {
  // Calculate rates from recent minutes
  const avgMarketsPerMin = recentMinutes.length > 0 
    ? recentMinutes.reduce((sum, m) => sum + m.markets_evaluated, 0) / recentMinutes.length 
    : 0;
  const avgSignalsPerMin = recentMinutes.length > 0 
    ? recentMinutes.reduce((sum, m) => sum + m.signals_generated, 0) / recentMinutes.length 
    : 0;
  const avgTradesPerMin = recentMinutes.length > 0 
    ? recentMinutes.reduce((sum, m) => sum + m.trades_executed, 0) / recentMinutes.length 
    : 0;
  
  return (
    <Card className="border-border" data-testid="activity-metrics-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Zap className="w-4 h-4" />
          Activity Metrics
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Totals */}
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="p-2 rounded bg-blue-500/10">
              <p className="text-xs text-blue-400">Markets Evaluated</p>
              <p className="font-bold text-lg text-blue-400">{totals.markets_evaluated.toLocaleString()}</p>
            </div>
            <div className="p-2 rounded bg-purple-500/10">
              <p className="text-xs text-purple-400">Signals Generated</p>
              <p className="font-bold text-lg text-purple-400">{totals.signals_generated.toLocaleString()}</p>
            </div>
            <div className="p-2 rounded bg-green-500/10">
              <p className="text-xs text-green-400">Trades Executed</p>
              <p className="font-bold text-lg text-green-400">{totals.trades_executed.toLocaleString()}</p>
            </div>
          </div>
          
          {/* Per-minute rates */}
          <div className="text-xs text-muted-foreground">
            <p className="mb-2 font-medium">Per-Minute Rates (10 min avg):</p>
            <div className="grid grid-cols-3 gap-2">
              <div className="flex items-center gap-1">
                <Target className="w-3 h-3" />
                <span>{avgMarketsPerMin.toFixed(1)} mkts/min</span>
              </div>
              <div className="flex items-center gap-1">
                <Activity className="w-3 h-3" />
                <span>{avgSignalsPerMin.toFixed(1)} sigs/min</span>
              </div>
              <div className="flex items-center gap-1">
                <TrendingUp className="w-3 h-3" />
                <span>{avgTradesPerMin.toFixed(2)} trades/min</span>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// Utilization Card
const UtilizationCard = ({ recentMinutes }) => {
  const latest = recentMinutes.length > 0 ? recentMinutes[recentMinutes.length - 1] : null;
  
  const capitalUtil = latest?.capital_utilization_pct || 0;
  const riskUtil = latest?.risk_utilization_pct || 0;
  
  const getUtilColor = (pct) => {
    if (pct > 80) return "text-red-400";
    if (pct > 50) return "text-yellow-400";
    return "text-green-400";
  };
  
  return (
    <Card className="border-border" data-testid="utilization-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <DollarSign className="w-4 h-4" />
          Utilization
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground">Capital Utilization</span>
              <span className={getUtilColor(capitalUtil)}>{capitalUtil.toFixed(1)}%</span>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div 
                className={`h-full transition-all ${capitalUtil > 80 ? 'bg-red-500' : capitalUtil > 50 ? 'bg-yellow-500' : 'bg-green-500'}`}
                style={{ width: `${Math.min(100, capitalUtil)}%` }}
              />
            </div>
          </div>
          
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground">Risk Utilization</span>
              <span className={getUtilColor(riskUtil)}>{riskUtil.toFixed(1)}%</span>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div 
                className={`h-full transition-all ${riskUtil > 80 ? 'bg-red-500' : riskUtil > 50 ? 'bg-yellow-500' : 'bg-green-500'}`}
                style={{ width: `${Math.min(100, riskUtil)}%` }}
              />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// Main Dashboard Component
export default function AutonomousDashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [health, setHealth] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [error, setError] = useState(null);
  
  const fetchData = useCallback(async () => {
    try {
      // Fetch all three endpoints in parallel with proper CORS headers
      const fetchOptions = {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        credentials: 'include'
      };
      
      const [dashboardRes, healthRes, metricsRes] = await Promise.all([
        fetch(`${API_BASE}/api/autonomous/dashboard`, fetchOptions).catch(err => {
          console.error('Dashboard fetch error:', err);
          return { ok: false, status: 0, statusText: err.message };
        }),
        fetch(`${API_BASE}/api/health`, fetchOptions).catch(err => {
          console.error('Health fetch error:', err);
          return { ok: false, status: 0, statusText: err.message };
        }),
        fetch(`${API_BASE}/api/autonomous/metrics`, fetchOptions).catch(err => {
          console.error('Metrics fetch error:', err);
          return { ok: false, status: 0, statusText: err.message };
        })
      ]);
      
      if (dashboardRes.ok) {
        try {
          const data = await dashboardRes.json();
          setDashboard(data);
        } catch (parseErr) {
          console.warn('Failed to parse dashboard:', parseErr);
        }
      } else {
        console.warn(`Dashboard endpoint returned ${dashboardRes.status}: ${dashboardRes.statusText}`);
      }
      
      if (healthRes.ok) {
        try {
          const data = await healthRes.json();
          setHealth(data);
        } catch (parseErr) {
          console.warn('Failed to parse health:', parseErr);
        }
      }
      
      if (metricsRes.ok) {
        try {
          const data = await metricsRes.json();
          setMetrics(data);
        } catch (parseErr) {
          console.warn('Failed to parse metrics:', parseErr);
        }
      }
      
      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      console.error('Fetch error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000); // Update every 3 seconds for real-time feel
    return () => clearInterval(interval);
  }, [fetchData]);
  
  if (loading && !dashboard) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <RefreshCw className="w-8 h-8 mx-auto animate-spin text-primary" />
          <p className="mt-2 text-muted-foreground">Loading dashboard...</p>
        </CardContent>
      </Card>
    );
  }
  
  if (!dashboard && !health) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          <AlertTriangle className="w-8 h-8 mx-auto text-yellow-400 mb-2" />
          <p>Dashboard data unavailable</p>
          {error && <p className="text-xs text-red-400 mt-1">{error}</p>}
        </CardContent>
      </Card>
    );
  }
  
  return (
    <div className="space-y-4" data-testid="autonomous-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-bold">24-Hour Autonomous Trading Dashboard</h2>
        </div>
        <div className="text-xs text-muted-foreground">
          Last update: {lastUpdate?.toLocaleTimeString()}
        </div>
      </div>
      
      {/* Engine Status Banner - MOST IMPORTANT */}
      <EngineStatusBanner health={health} metrics={metrics} />
      
      {/* Why Not Trading Section */}
      <WhyNotTradingCard metrics={metrics} />
      
      {/* Main Grid */}
      {dashboard && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <SystemHealthCard health={dashboard.system_health} />
            <PerformanceSummaryCard performance={dashboard.performance} />
            <ActivityMetricsCard 
              totals={dashboard.totals} 
              recentMinutes={dashboard.recent_minutes || []} 
            />
            <UtilizationCard recentMinutes={dashboard.recent_minutes || []} />
          </div>
          
          {/* Scheduler Heartbeat and Scanning */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <SchedulerHeartbeatCard scheduler={dashboard.scheduler} />
            <ScanningMetricsCard scheduler={dashboard.scheduler} />
            <FilterTransparencyCard filters={dashboard.scheduler?.filters} />
          </div>
          
          {/* Per-Model Breakdown */}
          {dashboard.per_model && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Per-Model Breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-4">
                  {Object.entries(dashboard.per_model).map(([modelId, modelMetrics]) => (
                    <div key={modelId} className="p-3 rounded-lg bg-muted/30">
                      <p className="text-xs text-muted-foreground mb-2">
                        {modelId.replace(/_/g, " ").toUpperCase()}
                      </p>
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        <div>
                          <p className="text-muted-foreground">Signals</p>
                          <p className="font-bold">{modelMetrics.signals}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Trades</p>
                          <p className="font-bold">{modelMetrics.trades}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">PnL</p>
                          <p className={`font-bold ${modelMetrics.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {formatCurrency(modelMetrics.pnl)}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
