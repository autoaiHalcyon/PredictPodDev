import React, { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import {
  TrendingUp,
  TrendingDown,
  Target,
  Zap,
  Shield,
  AlertTriangle,
  RefreshCw,
  Edit,
  Save,
  X,
  Clock,
  DollarSign,
} from "lucide-react";

const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

// Format utilities
const formatCurrency = (value) => {
  const num = Number(value) || 0;
  const sign = num >= 0 ? "+" : "";
  return `${sign}$${Math.abs(num).toFixed(2)}`;
};

const formatPct = (value) => {
  const num = Number(value) || 0;
  return `${num.toFixed(1)}%`;
};

// Strategy configs
const MODEL_CONFIG = {
  model_a_disciplined: {
    name: "Model A",
    subtitle: "Disciplined Edge Trader",
    color: "emerald",
    icon: Target,
  },
  model_b_high_frequency: {
    name: "Model B",
    subtitle: "High Frequency Hunter",
    color: "blue",
    icon: Zap,
  },
  model_c_institutional: {
    name: "Model C",
    subtitle: "Institutional Risk-First",
    color: "purple",
    icon: Shield,
  },
};

// Rules Editor Component
const RulesEditor = ({ strategyId, rulesData, onSave, onCancel }) => {
  const [editedConfig, setEditedConfig] = useState(rulesData?.config || {});
  const [saving, setSaving] = useState(false);
  const [changeSummary, setChangeSummary] = useState("");

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/rules/${strategyId}/update?league=BASE`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          config: editedConfig,
          change_summary: changeSummary || "Manual adjustment",
        }),
      });

      if (res.ok) {
        const data = await res.json();
        alert("Rules saved successfully!");
        onSave();
      } else {
        alert("Failed to save rules");
      }
    } catch (err) {
      console.error("Failed to save rules:", err);
      alert("Error saving rules");
    } finally {
      setSaving(false);
    }
  };

  const updateNestedValue = (path, value) => {
    const keys = path.split(".");
    const newConfig = JSON.parse(JSON.stringify(editedConfig));
    let current = newConfig;

    for (let i = 0; i < keys.length - 1; i++) {
      if (!current[keys[i]]) current[keys[i]] = {};
      current = current[keys[i]];
    }

    current[keys[keys.length - 1]] = value;
    setEditedConfig(newConfig);
  };

  return (
    <div className="space-y-4 bg-gray-900/50 p-6 rounded-lg border border-gray-800">
      <h3 className="text-lg font-bold flex items-center gap-2">
        <Edit className="w-5 h-5" />
        Edit Rules
      </h3>

      {/* Key Rule Parameters */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Entry Rules */}
        <div>
          <label className="block text-xs text-muted-foreground mb-2">Min Edge (%)</label>
          <input
            type="number"
            step="0.01"
            value={(editedConfig.entry_rules?.min_edge_threshold || 0.05) * 100}
            onChange={(e) =>
              updateNestedValue("entry_rules.min_edge_threshold", e.target.value / 100)
            }
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white"
          />
        </div>

        <div>
          <label className="block text-xs text-muted-foreground mb-2">Min Signal Score</label>
          <input
            type="number"
            value={editedConfig.entry_rules?.min_signal_score || 60}
            onChange={(e) =>
              updateNestedValue("entry_rules.min_signal_score", parseInt(e.target.value))
            }
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white"
          />
        </div>

        <div>
          <label className="block text-xs text-muted-foreground mb-2">Min Persistence (ticks)</label>
          <input
            type="number"
            value={editedConfig.entry_rules?.min_persistence_ticks || 3}
            onChange={(e) =>
              updateNestedValue("entry_rules.min_persistence_ticks", parseInt(e.target.value))
            }
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white"
          />
        </div>

        {/* Exit Rules */}
        <div>
          <label className="block text-xs text-muted-foreground mb-2">Profit Target (%)</label>
          <input
            type="number"
            step="0.01"
            value={(editedConfig.exit_rules?.profit_target_pct || 0.15) * 100}
            onChange={(e) =>
              updateNestedValue("exit_rules.profit_target_pct", e.target.value / 100)
            }
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white"
          />
        </div>

        <div>
          <label className="block text-xs text-muted-foreground mb-2">Stop Loss (%)</label>
          <input
            type="number"
            step="0.01"
            value={(editedConfig.exit_rules?.stop_loss_pct || 0.10) * 100}
            onChange={(e) =>
              updateNestedValue("exit_rules.stop_loss_pct", e.target.value / 100)
            }
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white"
          />
        </div>

        <div>
          <label className="block text-xs text-muted-foreground mb-2">Max Spread (%)</label>
          <input
            type="number"
            step="0.01"
            value={(editedConfig.filters?.max_spread_pct || 0.05) * 100}
            onChange={(e) =>
              updateNestedValue("filters.max_spread_pct", e.target.value / 100)
            }
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white"
          />
        </div>
      </div>

      {/* Change Summary */}
      <div>
        <label className="block text-xs text-muted-foreground mb-2">Change Summary</label>
        <textarea
          value={changeSummary}
          onChange={(e) => setChangeSummary(e.target.value)}
          placeholder="e.g., 'Loosened edge threshold to increase trade frequency'"
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white h-20"
        />
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <Button
          onClick={handleSave}
          disabled={saving}
          className="gap-2 bg-green-700 hover:bg-green-600"
        >
          <Save className="w-4 h-4" />
          {saving ? "Saving..." : "Save Rules"}
        </Button>
        <Button onClick={onCancel} variant="outline" className="gap-2">
          <X className="w-4 h-4" />
          Cancel
        </Button>
      </div>
    </div>
  );
};

// Daily Stats Card
const DailyStatsCard = ({ strategyId, data, rules, onEditRules }) => {
  const config = MODEL_CONFIG[strategyId];
  const Icon = config.icon;
  const [showEditor, setShowEditor] = useState(false);

  const dailyStats = data?.daily_stats || {};
  const totalPnl = data?.total_pnl || 0;
  const isProfitable = totalPnl >= 0;

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
        {/* Main PnL */}
        <div className="text-center pb-4 border-b border-border">
          <p className="text-xs text-muted-foreground uppercase">Daily P&L</p>
          <p
            className={`text-3xl font-bold mt-2 ${
              isProfitable ? "text-green-400" : "text-red-400"
            }`}
          >
            {formatCurrency(totalPnl)}
          </p>
        </div>

        {/* Key Metrics Grid */}
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-xs text-muted-foreground">Trades Today</p>
            <p className="text-lg font-bold">{data?.trades_today || 0}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Win Rate</p>
            <p className="text-lg font-bold">{formatPct(data?.win_rate)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Max Drawdown</p>
            <p className="text-orange-400 font-bold">
              {formatPct(data?.max_drawdown_pct)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Profit Factor</p>
            <p className="text-blue-400 font-bold">{(data?.profit_factor || 0).toFixed(2)}x</p>
          </div>
        </div>

        {/* Rules Section */}
        <div className="pt-4 border-t border-border">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-bold text-sm">Current Rules</h4>
            <Button
              onClick={() => setShowEditor(!showEditor)}
              variant="ghost"
              size="sm"
              className="gap-2"
            >
              <Edit className="w-3 h-3" />
              {showEditor ? "Cancel" : "Edit"}
            </Button>
          </div>

          {showEditor ? (
            <RulesEditor
              strategyId={strategyId}
              rulesData={rules}
              onSave={() => {
                setShowEditor(false);
                onEditRules();
              }}
              onCancel={() => setShowEditor(false)}
            />
          ) : (
            <div className="space-y-2 text-xs">
              {rules?.rule_chips && rules.rule_chips.map((chip) => (
                <div key={chip.param} className="flex justify-between bg-gray-900/50 p-2 rounded">
                  <span className="text-muted-foreground">{chip.label}</span>
                  <span className="font-mono font-bold text-foreground">{chip.value}</span>
                </div>
              ))}
              {rules?.applied_at && (
                <p className="text-xs text-muted-foreground mt-2 italic">
                  Last updated: {new Date(rules.applied_at).toLocaleString()}
                </p>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

// Trade Execution Summary
const TradeExecutionSummary = ({ trades }) => {
  if (!trades || trades.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="w-5 h-5" />
            Today's Trade Executions
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-center py-8">No trades executed today</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="w-5 h-5" />
          Today's Trade Executions
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 px-3 text-muted-foreground">Time</th>
                <th className="text-left py-2 px-3 text-muted-foreground">Game / Market</th>
                <th className="text-center py-2 px-3 text-muted-foreground">Strategy</th>
                <th className="text-center py-2 px-3 text-muted-foreground">Side</th>
                <th className="text-right py-2 px-3 text-muted-foreground">Entry</th>
                <th className="text-right py-2 px-3 text-muted-foreground">Current</th>
                <th className="text-right py-2 px-3 text-muted-foreground">P&L</th>
                <th className="text-center py-2 px-3 text-muted-foreground">Status</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade, idx) => {
                const isProfitable = (trade.pnl || 0) >= 0;
                return (
                  <tr key={idx} className="border-b border-border/50 hover:bg-muted/20">
                    <td className="py-2 px-3 text-muted-foreground">
                      {new Date(trade.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="py-2 px-3 text-foreground">{trade.market_name || "—"}</td>
                    <td className="py-2 px-3 text-center text-blue-400 text-[10px]">
                      {trade.strategy?.split("_")[1]?.toUpperCase() || "—"}
                    </td>
                    <td className="py-2 px-3 text-center">
                      <Badge
                        className={`text-[10px] ${
                          trade.side === "yes"
                            ? "bg-green-900/50 text-green-400"
                            : "bg-red-900/50 text-red-400"
                        }`}
                      >
                        {trade.side?.toUpperCase()}
                      </Badge>
                    </td>
                    <td className="py-2 px-3 text-right font-mono">
                      {((trade.entry_price || 0) * 100).toFixed(0)}¢
                    </td>
                    <td className="py-2 px-3 text-right font-mono">
                      {((trade.current_price || 0) * 100).toFixed(0)}¢
                    </td>
                    <td className={`py-2 px-3 text-right font-bold ${
                      isProfitable ? "text-green-400" : "text-red-400"
                    }`}>
                      {formatCurrency(trade.pnl || 0)}
                    </td>
                    <td className="py-2 px-3 text-center">
                      <Badge
                        className={`text-[10px] ${
                          (trade.status || "").toLowerCase() === "closed"
                            ? "bg-gray-700 text-gray-300"
                            : "bg-blue-900/50 text-blue-300"
                        }`}
                      >
                        {(trade.status || "open").toUpperCase()}
                      </Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
};

// Main Component
export default function DailyResults() {
  const [dailyReport, setDailyReport] = useState(null);
  const [rulesData, setRulesData] = useState({});
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [date, setDate] = useState(new Date().toISOString().split("T")[0]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch daily report
      const reportRes = await fetch(`${API_BASE}/api/strategies/report/daily?date=${date}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (!reportRes.ok) {
        if (reportRes.status === 429) {
          throw new Error('Server rate limit exceeded. Please wait a moment.');
        } else if (reportRes.status === 403 || reportRes.status === 0) {
          throw new Error('CORS error: Backend is blocking requests. Ensure CORS_ORIGINS includes http://localhost:3000');
        } else {
          throw new Error(`Backend error: ${reportRes.status}`);
        }
      }
      
      const reportData = await reportRes.json();
      setDailyReport(reportData);

      // Fetch rules for each strategy
      const rulesMap = {};
      const strategyIds = Object.keys(reportData?.strategies || {});

      for (const sid of strategyIds) {
        try {
          const rulesRes = await fetch(`${API_BASE}/api/rules/${sid}?league=BASE`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
          });
          if (rulesRes.ok) {
            rulesMap[sid] = await rulesRes.json();
          }
        } catch (err) {
          console.error(`Failed to fetch rules for ${sid}:`, err);
        }
      }
      setRulesData(rulesMap);

      // Fetch today's trades
      const tradesRes = await fetch(`${API_BASE}/api/trades?limit=100`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });
      if (tradesRes.ok) {
        const tradesData = await tradesRes.json();
        // Filter to today
        const today = new Date().toDateString();
        const todaysTrades = (tradesData.trades || []).filter(
          (t) => new Date(t.timestamp).toDateString() === today
        );
        setTrades(todaysTrades);
      }

      setError(null);
    } catch (err) {
      console.error("Failed to load data:", err);
      if (err instanceof TypeError && err.message === 'Failed to fetch') {
        setError('Network error: Cannot reach backend. Check if server is running on port 8000.');
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
      </div>
    );
  }

  const strategies = dailyReport?.strategies || {};

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <TrendingUp className="w-6 h-6 text-primary" />
                Daily Results & Rules Management
              </h1>
              <p className="text-sm text-muted-foreground">
                Daily performance summary, rules review, and optimization
              </p>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white"
              />
              <Button variant="outline" size="sm" onClick={loadData}>
                <RefreshCw className="w-4 h-4 mr-1" />
                Refresh
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Strategy Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(strategies).map(([sid, data]) => (
            <DailyStatsCard
              key={sid}
              strategyId={sid}
              data={data}
              rules={rulesData[sid]}
              onEditRules={loadData}
            />
          ))}
        </div>

        {/* Trade Executions */}
        <TradeExecutionSummary trades={trades} />

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
