import React, { useState, useEffect, useCallback } from "react";
import { Link, useParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import {
  ArrowLeft,
  DollarSign,
  Target,
  Shield,
  Zap,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  RefreshCw,
  Eye,
  Calculator,
  Activity,
  Scale,
  BarChart3,
  Percent,
  Clock,
  AlertCircle,
  CheckCircle2,
  Rocket
} from "lucide-react";

const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

// Model config
const MODEL_CONFIG = {
  model_a_disciplined: {
    name: "Model A",
    subtitle: "Disciplined",
    color: "emerald",
    icon: Target,
    bgClass: "bg-emerald-500/10 border-emerald-500/30",
    textClass: "text-emerald-400"
  },
  model_b_high_frequency: {
    name: "Model B",
    subtitle: "High Frequency",
    color: "blue",
    icon: Zap,
    bgClass: "bg-blue-500/10 border-blue-500/30",
    textClass: "text-blue-400"
  },
  model_c_institutional: {
    name: "Model C",
    subtitle: "Institutional",
    color: "purple",
    icon: Shield,
    bgClass: "bg-purple-500/10 border-purple-500/30",
    textClass: "text-purple-400"
  },
  model_d_growth_focused: {
    name: "Model D",
    subtitle: "Growth Focused",
    color: "rose",
    icon: Rocket,
    bgClass: "bg-rose-500/10 border-rose-500/30",
    textClass: "text-rose-400"
  },
  model_e_balanced_hunter: {
    name: "Model E",
    subtitle: "Balanced Hunter",
    color: "amber",
    icon: TrendingUp,
    bgClass: "bg-amber-500/10 border-amber-500/30",
    textClass: "text-amber-400"
  }
};

// Risk level colors
const RISK_COLORS = {
  minimal: "text-green-400 bg-green-500/10",
  low: "text-green-400 bg-green-500/10",
  moderate: "text-yellow-400 bg-yellow-500/10",
  high: "text-orange-400 bg-orange-500/10",
  aggressive: "text-red-400 bg-red-500/10"
};

// Format currency
const formatCurrency = (value, showSign = true) => {
  const num = Number(value) || 0;
  const sign = showSign ? (num >= 0 ? "+" : "") : "";
  return `${sign}$${Math.abs(num).toFixed(2)}`;
};

// Model Projection Card
const ModelProjectionCard = ({ modelId, projection }) => {
  const config = MODEL_CONFIG[modelId] || { name: modelId, icon: Activity };
  const Icon = config.icon;
  
  const riskColorClass = RISK_COLORS[projection?.risk_level] || "text-gray-400";
  const isPositiveEV = (projection?.expected_value_dollars || 0) > 0;
  
  return (
    <Card 
      className={`${config.bgClass} border-2 transition-all hover:shadow-lg`}
      data-testid={`projection-card-${modelId}`}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className={`w-5 h-5 ${config.textClass}`} />
            <div>
              <CardTitle className="text-lg font-bold">{config.name}</CardTitle>
              <p className="text-xs text-muted-foreground">{config.subtitle}</p>
            </div>
          </div>
          <Badge className={riskColorClass}>
            {projection?.risk_level?.toUpperCase() || "N/A"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Trade Recommendation */}
        <div className="p-3 rounded-lg bg-background/50">
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">Recommendation</p>
          <div className="flex items-center justify-between">
            <Badge 
              variant={projection?.suggested_side === "yes" ? "default" : "secondary"}
              className={`text-lg px-4 py-1 ${projection?.suggested_side === "yes" ? 'bg-green-500' : 'bg-red-500'}`}
            >
              {projection?.suggested_side?.toUpperCase() || "-"}
            </Badge>
            <div className="text-right">
              <p className="text-2xl font-bold">{projection?.suggested_quantity || 0}</p>
              <p className="text-xs text-muted-foreground">contracts</p>
            </div>
          </div>
        </div>
        
        {/* Bet Size */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-2 rounded bg-background/30">
            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <DollarSign className="w-3 h-3" /> Bet Size
            </p>
            <p className="text-xl font-bold text-foreground">
              {formatCurrency(projection?.suggested_bet_size_dollars, false)}
            </p>
          </div>
          <div className="p-2 rounded bg-background/30">
            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <Percent className="w-3 h-3" /> Portfolio Risk
            </p>
            <p className="text-xl font-bold text-foreground">
              {(projection?.portfolio_risk_pct || 0).toFixed(1)}%
            </p>
          </div>
        </div>
        
        {/* Entry/Exit Targets */}
        <div className="p-3 rounded-lg border border-border">
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">Price Targets</p>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div>
              <p className="text-xs text-muted-foreground">Entry</p>
              <p className="font-mono font-bold text-foreground">
                {projection?.entry_price_cents || "-"}¢
              </p>
            </div>
            <div>
              <p className="text-xs text-green-400">Target Exit</p>
              <p className="font-mono font-bold text-green-400">
                {projection?.target_exit_cents || "-"}¢
              </p>
            </div>
            <div>
              <p className="text-xs text-red-400">Stop Loss</p>
              <p className="font-mono font-bold text-red-400">
                {projection?.stop_loss_cents || "-"}¢
              </p>
            </div>
          </div>
        </div>
        
        {/* Expected Outcomes */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 rounded bg-green-500/10">
            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <TrendingUp className="w-3 h-3" /> Expected Profit
            </p>
            <p className="text-xl font-bold text-green-400">
              {formatCurrency(projection?.expected_profit_dollars)}
            </p>
          </div>
          <div className="p-3 rounded bg-red-500/10">
            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <TrendingDown className="w-3 h-3" /> Maximum Risk
            </p>
            <p className="text-xl font-bold text-red-400">
              {formatCurrency(projection?.maximum_risk_dollars, false)}
            </p>
          </div>
        </div>
        
        {/* Risk/Reward & EV */}
        <div className="grid grid-cols-3 gap-2 p-2 rounded bg-background/30 text-center">
          <div>
            <p className="text-xs text-muted-foreground">Risk/Reward</p>
            <p className={`font-bold ${(projection?.risk_reward_ratio || 0) >= 1.5 ? 'text-green-400' : 'text-yellow-400'}`}>
              {(projection?.risk_reward_ratio || 0).toFixed(2)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Expected Value</p>
            <p className={`font-bold ${isPositiveEV ? 'text-green-400' : 'text-red-400'}`}>
              {formatCurrency(projection?.expected_value_dollars)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Confidence</p>
            <p className="font-bold text-foreground">
              {(projection?.confidence_pct || 0).toFixed(0)}%
            </p>
          </div>
        </div>
        
        {/* Edge & Win Probability */}
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">Edge:</span>
            <span className={`font-bold ${(projection?.edge_pct || 0) > 3 ? 'text-green-400' : 'text-yellow-400'}`}>
              {(projection?.edge_pct || 0).toFixed(1)}%
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">Win Prob:</span>
            <span className="font-bold text-foreground">
              {(projection?.win_probability_pct || 0).toFixed(0)}%
            </span>
          </div>
        </div>
        
        {/* Entry Reason */}
        <div className="p-2 rounded bg-background/30">
          <p className="text-xs text-muted-foreground mb-1">Entry Reason</p>
          <p className="text-sm">{projection?.entry_reason || "No recommendation"}</p>
        </div>
        
        {/* Risk Factors */}
        {projection?.risk_factors && projection.risk_factors.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Risk Factors</p>
            {projection.risk_factors.map((factor, i) => (
              <div key={i} className="flex items-center gap-2 text-xs text-orange-400">
                <AlertTriangle className="w-3 h-3" />
                {factor}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Main Component
export default function CapitalPreviewPage() {
  const { gameId } = useParams();
  
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  
  // Fetch preview
  const fetchPreview = useCallback(async () => {
    if (!gameId) return;
    
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/capital/preview/${gameId}`);
      
      if (res.ok) {
        const data = await res.json();
        setPreview(data);
        setError(null);
      } else if (res.status === 404) {
        setPreview(null);
      } else {
        setError("Failed to load preview");
      }
    } catch (err) {
      console.error("Failed to fetch preview:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [gameId]);
  
  // Generate preview
  const generatePreview = async () => {
    if (!gameId) return;
    
    try {
      setGenerating(true);
      const res = await fetch(`${API_BASE}/api/capital/generate/${gameId}`, { method: 'POST' });
      
      if (res.ok) {
        const data = await res.json();
        setPreview(data);
        setError(null);
      } else {
        const errData = await res.json();
        setError(errData.detail || "Failed to generate preview");
      }
    } catch (err) {
      console.error("Failed to generate preview:", err);
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  };
  
  // Initial load
  useEffect(() => {
    fetchPreview();
  }, [fetchPreview]);
  
  // Periodically refresh
  useEffect(() => {
    const interval = setInterval(fetchPreview, 10000);
    return () => clearInterval(interval);
  }, [fetchPreview]);
  
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur sticky top-10 z-40">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link to="/" className="text-muted-foreground hover:text-foreground transition-colors">
                <ArrowLeft className="w-5 h-5" />
              </Link>
              <div>
                <h1 className="text-2xl font-bold flex items-center gap-2">
                  <Calculator className="w-6 h-6 text-primary" />
                  Capital Preview
                </h1>
                <p className="text-sm text-muted-foreground">
                  "What To Expect" • Pre-Execution Projections
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <Button variant="outline" size="sm" onClick={fetchPreview}>
                <RefreshCw className="w-4 h-4 mr-1" />
                Refresh
              </Button>
              <Button 
                variant="default" 
                size="sm" 
                onClick={generatePreview}
                disabled={generating}
              >
                {generating ? (
                  <RefreshCw className="w-4 h-4 mr-1 animate-spin" />
                ) : (
                  <Calculator className="w-4 h-4 mr-1" />
                )}
                Generate Preview
              </Button>
            </div>
          </div>
        </div>
      </header>
      
      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Game Info */}
        {preview && (
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold">{preview.game_title}</h2>
                  <p className="text-sm text-muted-foreground font-mono">{preview.market_ticker}</p>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Current YES: </span>
                    <span className="font-mono font-bold">{preview.current_yes_price}¢</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Fair Prob: </span>
                    <span className="font-mono font-bold">{(preview.fair_probability * 100).toFixed(1)}%</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Edge: </span>
                    <span className={`font-mono font-bold ${preview.market_edge > 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {(preview.market_edge * 100).toFixed(2)}%
                    </span>
                  </div>
                </div>
              </div>
              
              {/* Consensus */}
              {preview.consensus_side && (
                <div className="mt-4 p-3 rounded-lg bg-primary/10 border border-primary/30">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-5 h-5 text-primary" />
                      <span className="font-medium">
                        Consensus: {preview.models_agree_count}/3 models agree on{" "}
                        <Badge variant="default" className={preview.consensus_side === "yes" ? "bg-green-500" : "bg-red-500"}>
                          {preview.consensus_side.toUpperCase()}
                        </Badge>
                      </span>
                    </div>
                    {preview.best_risk_reward_model && (
                      <span className="text-sm text-muted-foreground">
                        Best R/R: {MODEL_CONFIG[preview.best_risk_reward_model]?.name || preview.best_risk_reward_model}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}
        
        {/* Loading State */}
        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
          </div>
        )}
        
        {/* No Preview */}
        {!loading && !preview && (
          <Card>
            <CardContent className="py-20 text-center">
              <Calculator className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No Preview Available</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Click "Generate Preview" to calculate capital projections for this game.
              </p>
              <Button onClick={generatePreview} disabled={generating}>
                {generating ? (
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Calculator className="w-4 h-4 mr-2" />
                )}
                Generate Preview
              </Button>
            </CardContent>
          </Card>
        )}
        
        {/* Model Projections Grid */}
        {preview && preview.model_projections && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Object.entries(preview.model_projections).map(([modelId, projection]) => (
              <ModelProjectionCard
                key={modelId}
                modelId={modelId}
                projection={projection}
              />
            ))}
          </div>
        )}
        
        {/* Error Display */}
        {error && (
          <div className="p-4 bg-red-500/20 border border-red-500 rounded-lg flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-red-400" />
            <p className="text-red-400">{error}</p>
          </div>
        )}
        
        {/* Generated At */}
        {preview?.generated_at && (
          <p className="text-xs text-muted-foreground text-center">
            Generated: {new Date(preview.generated_at).toLocaleString()}
          </p>
        )}
      </main>
    </div>
  );
}
