import React, { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Switch } from "../components/ui/switch";
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
  Settings
} from "lucide-react";
import { RulesDrawer, RuleChips } from "../components/RulesDrawer";

const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

// Model display config
const MODEL_CONFIG = {
  model_a_disciplined: {
    name: "Model A",
    subtitle: "Disciplined Edge Trader",
    color: "emerald",
    icon: Target,
    bgClass: "bg-emerald-500/10 border-emerald-500/30",
    textClass: "text-emerald-400"
  },
  model_b_high_frequency: {
    name: "Model B",
    subtitle: "High Frequency Hunter",
    color: "blue",
    icon: Zap,
    bgClass: "bg-blue-500/10 border-blue-500/30",
    textClass: "text-blue-400"
  },
  model_c_institutional: {
    name: "Model C",
    subtitle: "Institutional Risk-First",
    color: "purple",
    icon: Shield,
    bgClass: "bg-purple-500/10 border-purple-500/30",
    textClass: "text-purple-400"
  }
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

// Strategy Summary Card
const StrategySummaryCard = ({ strategyId, data, isWinning, isBestRiskAdjusted, ruleChips }) => {
  const config = MODEL_CONFIG[strategyId] || { name: strategyId, color: "gray", icon: Activity };
  const Icon = config.icon;
  const portfolio = data?.portfolio || {};
  
  const totalPnl = portfolio.total_pnl || 0;
  const isProfitable = totalPnl >= 0;
  
  return (
    <Card 
      data-testid={`strategy-card-${strategyId}`}
      className={`${config.bgClass} border-2 ${isWinning ? 'ring-2 ring-yellow-400' : ''} transition-all duration-300`}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className={`w-5 h-5 ${config.textClass}`} />
            <CardTitle className="text-lg font-bold">
              {config.name}
              {isWinning && <Crown className="inline w-4 h-4 ml-2 text-yellow-400" />}
              {isBestRiskAdjusted && !isWinning && <Medal className="inline w-4 h-4 ml-2 text-amber-400" />}
            </CardTitle>
          </div>
          <Badge 
            variant={data?.enabled ? "default" : "secondary"}
            className={data?.enabled ? "bg-green-500" : ""}
          >
            {data?.enabled ? "Active" : "Inactive"}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">{config.subtitle}</p>
      </CardHeader>
      <CardContent>
        {/* Big Total PnL */}
        <div className="mb-4 text-center">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">Total P&L</p>
          <p className={`text-3xl font-bold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
            {formatCurrency(totalPnl)}
          </p>
        </div>
        
        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-xs text-muted-foreground">Realized</p>
            <p className={portfolio.realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
              {formatCurrency(portfolio.realized_pnl)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Unrealized</p>
            <p className={portfolio.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
              {formatCurrency(portfolio.unrealized_pnl)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Win Rate</p>
            <p className="text-foreground">{formatPct(portfolio.win_rate)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Trades Today</p>
            <p className="text-foreground">{portfolio.trades_today || 0}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Max Drawdown</p>
            <p className="text-orange-400">{formatPct(portfolio.max_drawdown_pct)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Risk Used</p>
            <p className="text-foreground">{formatPct(portfolio.risk_utilization)}</p>
          </div>
        </div>
        
        {/* Rule Chips */}
        {ruleChips && ruleChips.length > 0 && (
          <RuleChips chips={ruleChips} maxDisplay={7} />
        )}
        
        {/* View Rules Button */}
        <div className="mt-3 flex items-center justify-between">
          <RulesDrawer 
            strategyId={strategyId} 
            displayName={`${config.name} - ${config.subtitle}`}
            league="BASE"
          />
          <Link to="/optimization">
            <Button variant="ghost" size="sm" className="text-xs">
              <Settings className="w-3 h-3 mr-1" />
              Optimize
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

// Comparison Table
const ComparisonTable = ({ comparison, strategies }) => {
  const metrics = [
    { key: "total_pnl", label: "Total P&L", format: formatCurrency },
    { key: "realized_pnl", label: "Realized", format: formatCurrency },
    { key: "unrealized_pnl", label: "Unrealized", format: formatCurrency },
    { key: "total_trades", label: "Trades", format: (v) => v?.toString() || "0" },
    { key: "win_rate", label: "Win Rate", format: (v) => formatPct(v) },
    { key: "avg_edge_entry", label: "Avg Edge Entry", format: (v) => `${(v || 0).toFixed(2)}%` },
    { key: "max_drawdown_pct", label: "Max DD %", format: (v) => formatPct(v) },
    { key: "risk_utilization", label: "Risk Used %", format: (v) => formatPct(v) }
  ];
  
  const strategyIds = Object.keys(strategies || {});
  
  return (
    <Card data-testid="comparison-table">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5" />
          Side-by-Side Comparison
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 px-3 text-muted-foreground">Metric</th>
                {strategyIds.map(sid => {
                  const config = MODEL_CONFIG[sid] || { name: sid };
                  return (
                    <th key={sid} className={`text-center py-2 px-3 ${MODEL_CONFIG[sid]?.textClass || ''}`}>
                      {config.name}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {metrics.map(metric => (
                <tr key={metric.key} className="border-b border-border/50 hover:bg-muted/30">
                  <td className="py-2 px-3 text-muted-foreground">{metric.label}</td>
                  {strategyIds.map(sid => {
                    const value = comparison?.[metric.key]?.[sid];
                    return (
                      <td key={sid} className="text-center py-2 px-3">
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

// Game Positions Table
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
          <p className="text-muted-foreground text-center py-8">No active positions</p>
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
                <th className="text-left py-2 px-3 text-muted-foreground">Game</th>
                {Object.keys(MODEL_CONFIG).map(sid => {
                  const config = MODEL_CONFIG[sid];
                  return (
                    <th key={sid} className={`text-center py-2 px-3 ${config.textClass}`}>
                      {config.name}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {games.map(([gameId, positions]) => (
                <tr key={gameId} className="border-b border-border/50 hover:bg-muted/30">
                  <td className="py-2 px-3 font-mono text-xs">{gameId.substring(0, 20)}...</td>
                  {Object.keys(MODEL_CONFIG).map(sid => {
                    const pos = positions[sid];
                    if (!pos?.has_position) {
                      return <td key={sid} className="text-center py-2 px-3 text-muted-foreground">-</td>;
                    }
                    return (
                      <td key={sid} className="text-center py-2 px-3">
                        <div>
                          <Badge variant={pos.side === "yes" ? "default" : "secondary"} className="text-xs">
                            {pos.side?.toUpperCase()} {pos.quantity}
                          </Badge>
                          <p className={`text-xs mt-1 ${pos.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
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

// Main Component
export default function StrategyCommandCenter() {
  const [summary, setSummary] = useState(null);
  const [gamePositions, setGamePositions] = useState({});
  const [rulesData, setRulesData] = useState({});
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [isStale, setIsStale] = useState(false);
  const [error, setError] = useState(null);
  
  // Fetch data
  const fetchData = useCallback(async () => {
    try {
      const [summaryRes, positionsRes] = await Promise.all([
        fetch(`${API_BASE}/api/strategies/summary`, { 
          method: 'GET',
          headers: { 'Content-Type': 'application/json' }
        }),
        fetch(`${API_BASE}/api/strategies/positions/by_game`, {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' }
        })
      ]);
      
      if (!summaryRes.ok) {
        const status = summaryRes.status;
        if (status === 429) {
          setError('Server rate limit exceeded. Please wait a moment.');
        } else if (status === 403 || status === 0) {
          setError('CORS error: Backend is blocking requests. Ensure CORS_ORIGINS includes http://localhost:3000');
        } else {
          setError(`Backend error: ${status}`);
        }
        setLoading(false);
        return;
      }
      
      const summaryData = await summaryRes.json();
      setSummary(summaryData);
      
      // Fetch rules for each strategy
      const rulesPromises = Object.keys(summaryData.strategies || {}).map(async (sid) => {
        try {
          const rulesRes = await fetch(`${API_BASE}/api/rules/${sid}?league=BASE`);
          if (rulesRes.ok) {
            return { id: sid, data: await rulesRes.json() };
          }
        } catch (e) {
          console.error(`Failed to fetch rules for ${sid}:`, e);
        }
        return { id: sid, data: null };
      });
      
      const rulesResults = await Promise.all(rulesPromises);
      const rulesMap = {};
      rulesResults.forEach(r => {
        if (r.data) rulesMap[r.id] = r.data;
      });
      setRulesData(rulesMap);
      
      if (positionsRes.ok) {
        const posData = await positionsRes.json();
        setGamePositions(posData);
      }
      
      setLastUpdate(new Date());
      setIsStale(false);
      setError(null);
    } catch (err) {
      console.error("Failed to fetch strategy data:", err);
      if (err instanceof TypeError && err.message === 'Failed to fetch') {
        setError('Network error: Cannot reach backend. Check if server is running on port 8000.');
      } else {
        setError(err.message || 'Unknown error fetching data');
      }
    } finally {
      setLoading(false);
    }
  }, []);
  
  // Initial fetch and polling
  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); // Update every 5 seconds (reduced from 2)
    return () => clearInterval(interval);
  }, [fetchData]);
  
  // Stale detection
  useEffect(() => {
    const staleCheck = setInterval(() => {
      if (lastUpdate && (new Date() - lastUpdate) > 10000) {
        setIsStale(true);
      }
    }, 1000);
    return () => clearInterval(staleCheck);
  }, [lastUpdate]);
  
  // Control functions
  const toggleStrategies = async (enable) => {
    try {
      await fetch(`${API_BASE}/api/strategies/${enable ? 'enable' : 'disable'}`, { method: 'POST' });
      fetchData();
    } catch (err) {
      console.error("Failed to toggle strategies:", err);
    }
  };
  
  const activateKillSwitch = async () => {
    if (window.confirm("EMERGENCY: This will stop ALL strategies immediately. Continue?")) {
      try {
        await fetch(`${API_BASE}/api/strategies/kill_switch`, { method: 'POST' });
        fetchData();
      } catch (err) {
        console.error("Failed to activate kill switch:", err);
      }
    }
  };
  
  const deactivateKillSwitch = async () => {
    try {
      await fetch(`${API_BASE}/api/strategies/kill_switch`, { method: 'DELETE' });
      fetchData();
    } catch (err) {
      console.error("Failed to deactivate kill switch:", err);
    }
  };
  
  const toggleEvaluationMode = async (enabled) => {
    try {
      await fetch(`${API_BASE}/api/strategies/evaluation_mode?enabled=${enabled}`, { method: 'POST' });
      fetchData();
    } catch (err) {
      console.error("Failed to toggle evaluation mode:", err);
    }
  };
  
  const resetStrategy = async (strategyId) => {
    if (window.confirm(`Reset portfolio for ${strategyId}? This cannot be undone.`)) {
      try {
        await fetch(`${API_BASE}/api/strategies/${strategyId}/reset`, { method: 'POST' });
        fetchData();
      } catch (err) {
        console.error("Failed to reset strategy:", err);
      }
    }
  };
  
  const exportDailyReport = async (format) => {
    try {
      const res = await fetch(`${API_BASE}/api/strategies/report/daily/export?format=${format}`);
      const data = await res.json();
      
      // Create download
      const blob = new Blob([format === 'csv' ? data.data : JSON.stringify(data, null, 2)], 
        { type: format === 'csv' ? 'text/csv' : 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
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
                Basketball Strategy Command Center
              </h1>
              <p className="text-sm text-muted-foreground">
                Multi-Model Parallel Execution • Paper Trading Only
              </p>
            </div>
            
            {/* Status Indicators */}
            <div className="flex items-center gap-4">
              {/* Last Updated */}
              <div className={`text-xs ${isStale ? 'text-red-400' : 'text-muted-foreground'}`}>
                Last updated: {lastUpdate ? `${Math.round((new Date() - lastUpdate) / 1000)}s ago` : '-'}
                {isStale && <span className="ml-2 text-red-400">(STALE)</span>}
              </div>
              
              {/* Refresh */}
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
        <Card data-testid="control-panel" className="border-2 border-primary/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="w-5 h-5" />
              Control Panel
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center gap-6">
              {/* Main Enable/Disable */}
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
              
              {/* Evaluation Mode */}
              <div className="flex items-center gap-3">
                <span className="text-sm">Evaluation Mode:</span>
                <Switch
                  checked={summary?.evaluation_mode}
                  onCheckedChange={toggleEvaluationMode}
                  data-testid="evaluation-toggle"
                />
              </div>
              
              {/* Kill Switch */}
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
              
              {/* Export */}
              <div className="flex gap-2 ml-auto">
                <Button variant="outline" size="sm" onClick={() => exportDailyReport('json')}>
                  <Download className="w-4 h-4 mr-1" />
                  Export JSON
                </Button>
                <Button variant="outline" size="sm" onClick={() => exportDailyReport('csv')}>
                  <Download className="w-4 h-4 mr-1" />
                  Export CSV
                </Button>
              </div>
            </div>
            
            {/* Kill Switch Active Warning */}
            {summary?.kill_switch_active && (
              <div className="mt-4 p-3 bg-red-500/20 border border-red-500 rounded-lg flex items-center gap-3">
                <AlertTriangle className="w-6 h-6 text-red-500" />
                <div>
                  <p className="font-bold text-red-400">KILL SWITCH ACTIVE</p>
                  <p className="text-sm text-red-300">All strategies have been stopped. Deactivate to resume.</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
        
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(strategies).map(([sid, data]) => (
            <StrategySummaryCard
              key={sid}
              strategyId={sid}
              data={data}
              isWinning={sid === winningModel}
              isBestRiskAdjusted={sid === bestRiskAdjusted}
              ruleChips={rulesData[sid]?.rule_chips}
            />
          ))}
        </div>
        
        {/* Comparison Table */}
        <ComparisonTable comparison={summary?.comparison} strategies={strategies} />
        
        {/* Game Positions */}
        <GamePositionsTable gamePositions={gamePositions} />
        
        {/* Detailed Model Rules & Configuration */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="w-5 h-5" />
              Model Rules & Configuration
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-2">
              Detailed specifications and constraints for each trading model
            </p>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {/* Model A */}
              <div className="border border-emerald-500/30 bg-emerald-500/5 rounded-lg p-4">
                <h3 className="font-bold text-emerald-400 mb-3">Model A — Disciplined Edge Trader</h3>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-xs">
                  <div>
                    <p className="text-muted-foreground font-semibold">Entry Rules</p>
                    <ul className="space-y-1 mt-1 text-foreground text-[11px]">
                      <li>Edge ≥ 5%</li>
                      <li>Signal Score ≥ 60</li>
                      <li>Persistence: 3 ticks</li>
                      <li>Cooldown: 180s</li>
                      <li>Max 3 entries/game</li>
                      <li>Momentum required</li>
                    </ul>
                  </div>
                  <div>
                    <p className="text-muted-foreground font-semibold">Exit & Risk</p>
                    <ul className="space-y-1 mt-1 text-foreground text-[11px]">
                      <li>Profit Target: 15%</li>
                      <li>Stop Loss: 10%</li>
                      <li>Trailing Stop: 5%</li>
                      <li>Time Exit: 600s</li>
                      <li>Trim 50% @ 10%</li>
                      <li>Daily Cap: 5%</li>
                    </ul>
                  </div>
                  <div>
                    <p className="text-muted-foreground font-semibold">Position Sizing</p>
                    <ul className="space-y-1 mt-1 text-foreground text-[11px]">
                      <li>Base: 2% capital</li>
                      <li>Max: 5% capital</li>
                      <li>Kelly: 25%</li>
                      <li>Max 20 trades/day</li>
                      <li>Max 4 trades/hour</li>
                      <li>Max DD: 10%</li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Model B */}
              <div className="border border-blue-500/30 bg-blue-500/5 rounded-lg p-4">
                <h3 className="font-bold text-blue-400 mb-3">Model B — High Frequency Hunter</h3>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-xs">
                  <div>
                    <p className="text-muted-foreground font-semibold">Entry Rules</p>
                    <ul className="space-y-1 mt-1 text-foreground text-[11px]">
                      <li>Edge ≥ 3%</li>
                      <li>Signal Score ≥ 45</li>
                      <li>Persistence: 2 ticks</li>
                      <li>Cooldown: 60s</li>
                      <li>Max 8 entries/game</li>
                      <li>Momentum optional</li>
                    </ul>
                  </div>
                  <div>
                    <p className="text-muted-foreground font-semibold">Exit & Risk</p>
                    <ul className="space-y-1 mt-1 text-foreground text-[11px]">
                      <li>Profit Target: 8%</li>
                      <li>Stop Loss: 6%</li>
                      <li>Trailing Stop: 3%</li>
                      <li>Time Exit: 300s</li>
                      <li>Trim 60% @ 5%</li>
                      <li>Daily Cap: 8%</li>
                    </ul>
                  </div>
                  <div>
                    <p className="text-muted-foreground font-semibold">Position Sizing</p>
                    <ul className="space-y-1 mt-1 text-foreground text-[11px]">
                      <li>Base: 1.5% capital</li>
                      <li>Max: 4% capital</li>
                      <li>Kelly: 20%</li>
                      <li>Max 60 trades/day</li>
                      <li>Max 12 trades/hour</li>
                      <li>Max DD: 15%</li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Model C */}
              <div className="border border-purple-500/30 bg-purple-500/5 rounded-lg p-4">
                <h3 className="font-bold text-purple-400 mb-3">Model C — Institutional Risk-First</h3>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-xs">
                  <div>
                    <p className="text-muted-foreground font-semibold">Entry Rules</p>
                    <ul className="space-y-1 mt-1 text-foreground text-[11px]">
                      <li>Edge ≥ 7%</li>
                      <li>Signal Score ≥ 75</li>
                      <li>Persistence: 4 ticks</li>
                      <li>Cooldown: 300s</li>
                      <li>Max 2 entries/game</li>
                      <li>Momentum required</li>
                    </ul>
                  </div>
                  <div>
                    <p className="text-muted-foreground font-semibold">Exit & Risk</p>
                    <ul className="space-y-1 mt-1 text-foreground text-[11px]">
                      <li>Profit Target: 20%</li>
                      <li>Stop Loss: 8%</li>
                      <li>Trailing Stop: 4%</li>
                      <li>Time Exit: 900s</li>
                      <li>Premium signal quality</li>
                      <li>Daily Cap: 3%</li>
                    </ul>
                  </div>
                  <div>
                    <p className="text-muted-foreground font-semibold">Position Sizing</p>
                    <ul className="space-y-1 mt-1 text-foreground text-[11px]">
                      <li>Base: 1% capital</li>
                      <li>Max: 3% capital</li>
                      <li>Kelly: 15%</li>
                      <li>Max 10 trades/day</li>
                      <li>Max 2 trades/hour</li>
                      <li>Max DD: 6%</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
        
        {/* Reset Controls */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Admin Controls</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {Object.keys(strategies).map(sid => {
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
        
        {/* Error Display */}
        {error && (
          <div className="p-4 bg-red-500/20 border border-red-500 rounded-lg">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-red-400 font-semibold mb-1">Backend Connection Error</p>
                <p className="text-red-300 text-sm mb-2">{error}</p>
                <p className="text-red-300 text-xs">
                  Troubleshooting: Ensure backend is running on port 8000 with <code className="bg-red-900/30 px-1 rounded">python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload</code>
                </p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
