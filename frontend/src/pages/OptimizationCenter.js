import React, { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Switch } from "../components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import {
  ArrowLeft,
  Settings,
  Play,
  Check,
  X,
  RefreshCw,
  AlertTriangle,
  Zap,
  TrendingUp,
  TrendingDown,
  Clock,
  Target,
  Shield,
  BarChart3,
  Rocket
} from "lucide-react";

const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

// Tuner mode options
const TUNER_MODES = [
  { value: "off", label: "Off", description: "Tuner disabled" },
  { value: "propose_only", label: "Propose Only", description: "Suggests changes, requires manual approval" },
  { value: "auto_apply_paper", label: "Auto-Apply (Paper)", description: "Automatically applies changes in paper mode" }
];

// Model config
const MODEL_CONFIG = {
  model_a_disciplined: { name: "Model A", color: "emerald", icon: Target },
  model_b_high_frequency: { name: "Model B", color: "blue", icon: Zap },
  model_c_institutional: { name: "Model C", color: "purple", icon: Shield },
  model_d_growth_focused: { name: "Model D", color: "rose", icon: Rocket },
  model_e_balanced_hunter: { name: "Model E", color: "amber", icon: TrendingUp }
};

export default function OptimizationCenter() {
  const [tunerStatus, setTunerStatus] = useState(null);
  const [tunerSettings, setTunerSettings] = useState(null);
  const [proposals, setProposals] = useState([]);
  const [strategySummary, setStrategySummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  
  const fetchData = useCallback(async () => {
    try {
      const [statusRes, settingsRes, proposalsRes, summaryRes] = await Promise.all([
        fetch(`${API_BASE}/api/tuner/status`),
        fetch(`${API_BASE}/api/tuner/settings`),
        fetch(`${API_BASE}/api/tuner/proposals`),
        fetch(`${API_BASE}/api/strategies/summary`)
      ]);
      
      if (statusRes.ok) setTunerStatus(await statusRes.json());
      if (settingsRes.ok) setTunerSettings(await settingsRes.json());
      if (proposalsRes.ok) {
        const data = await proposalsRes.json();
        setProposals(data.proposals || []);
      }
      if (summaryRes.ok) setStrategySummary(await summaryRes.json());
    } catch (err) {
      console.error("Failed to fetch tuner data:", err);
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, [fetchData]);
  
  const runTunerNow = async () => {
    setRunning(true);
    try {
      const res = await fetch(`${API_BASE}/api/tuner/run`, { method: "POST" });
      if (res.ok) {
        const report = await res.json();
        console.log("Tuner report:", report);
        fetchData();
      }
    } catch (err) {
      console.error("Failed to run tuner:", err);
    } finally {
      setRunning(false);
    }
  };
  
  const updateSettings = async (updates) => {
    try {
      const params = new URLSearchParams(updates);
      await fetch(`${API_BASE}/api/tuner/settings?${params}`, { method: "POST" });
      fetchData();
    } catch (err) {
      console.error("Failed to update settings:", err);
    }
  };
  
  const applyProposal = async (proposalId) => {
    try {
      await fetch(`${API_BASE}/api/tuner/proposals/${proposalId}/apply`, { method: "POST" });
      fetchData();
    } catch (err) {
      console.error("Failed to apply proposal:", err);
    }
  };
  
  const rejectProposal = async (proposalId) => {
    try {
      await fetch(`${API_BASE}/api/tuner/proposals/${proposalId}/reject`, { method: "POST" });
      fetchData();
    } catch (err) {
      console.error("Failed to reject proposal:", err);
    }
  };
  
  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur sticky top-10 z-40">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link to="/strategies" className="text-muted-foreground hover:text-foreground">
                <ArrowLeft className="w-5 h-5" />
              </Link>
              <div>
                <h1 className="text-2xl font-bold flex items-center gap-2">
                  <Settings className="w-6 h-6 text-primary" />
                  Optimization Center
                </h1>
                <p className="text-sm text-muted-foreground">
                  Auto-Tuner Configuration • Paper Trading Only
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <Button variant="outline" size="sm" onClick={fetchData}>
                <RefreshCw className="w-4 h-4 mr-1" />
                Refresh
              </Button>
              <Button 
                onClick={runTunerNow} 
                disabled={running}
                className="bg-primary"
              >
                <Play className="w-4 h-4 mr-1" />
                {running ? "Running..." : "Run Tuner Now"}
              </Button>
            </div>
          </div>
        </div>
      </header>
      
      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Tuner Settings Card */}
        <Card data-testid="tuner-settings">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="w-5 h-5" />
              Tuner Settings
            </CardTitle>
            <CardDescription>Configure auto-tuner behavior</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Mode Selection */}
              <div>
                <label className="text-sm font-medium mb-2 block">Tuner Mode</label>
                <Select
                  value={tunerSettings?.mode || "propose_only"}
                  onValueChange={(value) => updateSettings({ mode: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {TUNER_MODES.map(mode => (
                      <SelectItem key={mode.value} value={mode.value}>
                        <div>
                          <div className="font-medium">{mode.label}</div>
                          <div className="text-xs text-muted-foreground">{mode.description}</div>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              {/* Schedule */}
              <div>
                <label className="text-sm font-medium mb-2 block">Daily Run Time (UTC)</label>
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-muted-foreground" />
                  <span className="text-lg font-mono">
                    {String(tunerSettings?.daily_run_hour_utc || 3).padStart(2, "0")}:00
                  </span>
                </div>
              </div>
              
              {/* Midday Runs */}
              <div>
                <label className="text-sm font-medium mb-2 block">Mid-day Runs</label>
                <div className="flex items-center gap-2">
                  <Switch
                    checked={tunerSettings?.enable_midday_runs || false}
                    onCheckedChange={(checked) => updateSettings({ enable_midday_runs: checked })}
                  />
                  <span className="text-sm text-muted-foreground">
                    Every {tunerSettings?.midday_interval_hours || 6} hours
                  </span>
                </div>
              </div>
            </div>
            
            {/* Status Row */}
            <div className="mt-6 pt-4 border-t border-border flex items-center gap-6 text-sm">
              <div>
                <span className="text-muted-foreground">Status:</span>{" "}
                <Badge variant={tunerStatus?.scheduler_running ? "default" : "secondary"}>
                  {tunerStatus?.scheduler_running ? "Running" : "Stopped"}
                </Badge>
              </div>
              <div>
                <span className="text-muted-foreground">Last Run:</span>{" "}
                <span className="font-mono">
                  {tunerStatus?.last_run 
                    ? new Date(tunerStatus.last_run).toLocaleString()
                    : "Never"
                  }
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Min Sample:</span>{" "}
                <span className="font-mono">{tunerSettings?.min_sample_size_overall || 50} trades</span>
              </div>
              <div>
                <span className="text-muted-foreground">Min Improvement:</span>{" "}
                <span className="font-mono">{tunerSettings?.min_improvement_pct || 5}%</span>
              </div>
            </div>
          </CardContent>
        </Card>
        
        {/* Model Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {strategySummary?.strategies && Object.entries(strategySummary.strategies).map(([modelId, data]) => {
            const config = MODEL_CONFIG[modelId] || { name: modelId, color: "gray", icon: BarChart3 };
            const Icon = config.icon;
            const portfolio = data.portfolio || {};
            
            return (
              <Card key={modelId} className="border-border">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Icon className={`w-5 h-5 text-${config.color}-400`} />
                    {config.name}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="text-xs text-muted-foreground">Total P&L</p>
                      <p className={portfolio.total_pnl >= 0 ? 'text-green-400 font-bold' : 'text-red-400 font-bold'}>
                        ${portfolio.total_pnl?.toFixed(2) || "0.00"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Win Rate</p>
                      <p className="font-medium">{portfolio.win_rate?.toFixed(1) || 0}%</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Trades</p>
                      <p className="font-medium">{portfolio.total_trades || 0}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Max DD</p>
                      <p className="text-orange-400">{portfolio.max_drawdown_pct?.toFixed(1) || 0}%</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
        
        {/* Pending Proposals */}
        <Card data-testid="proposals-list">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5" />
              Pending Proposals
              {proposals.length > 0 && (
                <Badge variant="default" className="ml-2">{proposals.length}</Badge>
              )}
            </CardTitle>
            <CardDescription>Review and apply tuner recommendations</CardDescription>
          </CardHeader>
          <CardContent>
            {proposals.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No pending proposals. Run the tuner to generate recommendations.
              </div>
            ) : (
              <div className="space-y-4">
                {proposals.map(proposal => {
                  const modelConfig = MODEL_CONFIG[proposal.model_id] || { name: proposal.model_id };
                  
                  return (
                    <div
                      key={proposal.id}
                      className="p-4 border border-border rounded-lg bg-muted/20"
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold">{modelConfig.name}</span>
                            <Badge variant="outline">{proposal.league}</Badge>
                            <Badge 
                              variant={proposal.expected_pnl_improvement > 0 ? "default" : "secondary"}
                              className={proposal.expected_pnl_improvement > 0 ? "bg-green-500/20 text-green-400" : ""}
                            >
                              {proposal.expected_pnl_improvement > 0 ? "+" : ""}
                              {proposal.expected_pnl_improvement?.toFixed(1)}% PnL
                            </Badge>
                          </div>
                          <p className="text-sm text-muted-foreground mt-1">
                            {proposal.change_summary}
                          </p>
                          <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                            <span>Sample: {proposal.sample_size} trades</span>
                            <span>Confidence: {(proposal.confidence_score * 100).toFixed(0)}%</span>
                            <span>Created: {new Date(proposal.created_at).toLocaleString()}</span>
                          </div>
                        </div>
                        
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => rejectProposal(proposal.id)}
                            className="text-red-400 border-red-400/50"
                          >
                            <X className="w-4 h-4 mr-1" />
                            Reject
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => applyProposal(proposal.id)}
                            className="bg-green-500 hover:bg-green-600"
                          >
                            <Check className="w-4 h-4 mr-1" />
                            Apply
                          </Button>
                        </div>
                      </div>
                      
                      {/* Changes Preview */}
                      {proposal.changes && proposal.changes.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-border">
                          <p className="text-xs font-medium mb-2">Proposed Changes:</p>
                          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs font-mono">
                            {proposal.changes.map((change, idx) => (
                              <div key={idx} className="bg-background/50 p-2 rounded">
                                <span className="text-muted-foreground">{change.parameter}:</span>
                                <br />
                                <span className="text-red-400">{JSON.stringify(change.old_value)}</span>
                                {" → "}
                                <span className="text-green-400">{JSON.stringify(change.new_value)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
        
        {/* Safety Notice */}
        <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 mt-0.5" />
          <div>
            <p className="font-medium text-amber-400">Paper Trading Only</p>
            <p className="text-sm text-muted-foreground">
              Auto-tuner changes only affect paper trading configurations. Live trading settings 
              are never modified automatically. All changes are logged and can be rolled back.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
