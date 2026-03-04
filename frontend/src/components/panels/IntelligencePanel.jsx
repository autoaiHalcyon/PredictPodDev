import React from 'react';
import { Badge } from '../ui/badge';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Activity,
  Zap,
  AlertTriangle
} from 'lucide-react';

const IntelligencePanel = ({ intelligence, isClutch }) => {
  // Show placeholder if no intelligence data
  if (!intelligence || Object.keys(intelligence).length === 0) {
    return (
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan-500" />
            Market Intelligence
          </h3>
        </div>
        <div className="text-center py-6 text-gray-500">
          <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">Collecting market data...</p>
          <p className="text-xs mt-1">Intelligence will appear once enough data is gathered</p>
        </div>
      </div>
    );
  }

  const getTrendIcon = (trend) => {
    switch (trend) {
      case 'up': return <TrendingUp className="w-4 h-4 text-green-500" />;
      case 'down': return <TrendingDown className="w-4 h-4 text-red-500" />;
      default: return <Minus className="w-4 h-4 text-gray-500" />;
    }
  };

  const getVolatilityColor = (regime) => {
    switch (regime) {
      case 'spike': return 'bg-red-500 text-white';
      case 'high': return 'bg-orange-500 text-white';
      case 'medium': return 'bg-blue-500 text-white';
      default: return 'bg-gray-600 text-gray-300';
    }
  };

  const getMomentumColor = (momentum) => {
    switch (momentum) {
      case 'up': return 'text-green-400';
      case 'down': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <Activity className="w-4 h-4 text-cyan-500" />
          Market Intelligence
        </h3>
        {isClutch && (
          <Badge className="bg-orange-500/20 text-orange-400 border border-orange-500/50 animate-pulse">
            <Zap className="w-3 h-3 mr-1" />
            Clutch Mode
          </Badge>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* 5-min Trend */}
        <div className="bg-gray-800/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">5-min Trend</div>
          <div className="flex items-center gap-2">
            {getTrendIcon(intelligence.trend_5min)}
            <span className="text-sm font-medium capitalize">
              {intelligence.trend_5min || 'neutral'}
            </span>
          </div>
        </div>

        {/* 30-min Trend */}
        <div className="bg-gray-800/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">30-min Trend</div>
          <div className="flex items-center gap-2">
            {getTrendIcon(intelligence.trend_30min)}
            <span className="text-sm font-medium capitalize">
              {intelligence.trend_30min || 'neutral'}
            </span>
          </div>
        </div>

        {/* Volatility Regime */}
        <div className="bg-gray-800/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">Volatility</div>
          <Badge className={getVolatilityColor(intelligence.volatility_regime)}>
            {intelligence.volatility_regime?.toUpperCase() || 'LOW'}
          </Badge>
          {intelligence.volatility_value > 0 && (
            <span className="text-xs text-gray-500 ml-2">
              {(intelligence.volatility_value * 100).toFixed(1)}%
            </span>
          )}
        </div>

        {/* Momentum */}
        <div className="bg-gray-800/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">Momentum</div>
          <span className={`text-sm font-medium capitalize ${getMomentumColor(intelligence.momentum)}`}>
            {intelligence.momentum || 'neutral'}
          </span>
        </div>
      </div>

      {/* Volatility Spike Warning */}
      {intelligence.volatility_regime === 'spike' && (
        <div className="mt-4 p-3 bg-red-900/30 rounded-lg border border-red-800 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-red-500" />
          <div>
            <div className="text-sm font-medium text-red-400">
              ⚡ Rapid Probability Expansion
            </div>
            <div className="text-xs text-red-300">High volatility detected</div>
          </div>
        </div>
      )}
    </div>
  );
};

export default IntelligencePanel;
