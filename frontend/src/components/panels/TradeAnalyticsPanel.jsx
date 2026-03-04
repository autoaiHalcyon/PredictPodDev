import React from 'react';
import { formatCurrency } from '../../services/api';
import {
  Calculator,
  TrendingUp,
  TrendingDown,
  Target,
  Shield,
  DollarSign
} from 'lucide-react';

const TradeAnalyticsPanel = ({ analytics, signal }) => {
  if (!analytics) return null;

  const formatPercent = (val) => `${(val * 100).toFixed(1)}%`;

  return (
    <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
      <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Calculator className="w-4 h-4 text-blue-500" />
        Trade Analytics
      </h4>

      <div className="space-y-3">
        {/* Expected Value */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400 flex items-center gap-1">
            <TrendingUp className="w-3 h-3" /> Expected Value
          </span>
          <span className={`font-mono font-medium ${
            (analytics.expected_value || 0) >= 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {formatCurrency(analytics.expected_value || 0)}
          </span>
        </div>

        {/* Break-even Probability */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400 flex items-center gap-1">
            <Target className="w-3 h-3" /> Break-even Prob
          </span>
          <span className="font-mono">
            {formatPercent(analytics.break_even_prob || 0)}
          </span>
        </div>

        {/* Max Risk */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400 flex items-center gap-1">
            <Shield className="w-3 h-3" /> Max Risk
          </span>
          <span className="font-mono text-red-400">
            {formatCurrency(analytics.max_risk || 0)}
          </span>
        </div>

        {/* Suggested Exit */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400 flex items-center gap-1">
            <TrendingUp className="w-3 h-3 text-green-500" /> Exit Target
          </span>
          <span className="font-mono text-green-400">
            {formatPercent(analytics.suggested_exit_prob || 0)}
          </span>
        </div>

        {/* Suggested Stop */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400 flex items-center gap-1">
            <TrendingDown className="w-3 h-3 text-red-500" /> Stop Loss
          </span>
          <span className="font-mono text-red-400">
            {formatPercent(analytics.suggested_stop_prob || 0)}
          </span>
        </div>

        {/* Risk-Reward */}
        <div className="pt-2 border-t border-gray-700 flex items-center justify-between">
          <span className="text-xs text-gray-400 flex items-center gap-1">
            <DollarSign className="w-3 h-3" /> Risk/Reward
          </span>
          <span className={`font-mono font-bold ${
            (analytics.risk_reward_ratio || 0) >= 1 ? 'text-green-400' : 'text-yellow-400'
          }`}>
            {(analytics.risk_reward_ratio || 0).toFixed(2)}x
          </span>
        </div>
      </div>
    </div>
  );
};

export default TradeAnalyticsPanel;
