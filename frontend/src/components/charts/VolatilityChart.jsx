import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell
} from 'recharts';

const VolatilityChart = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 bg-gray-800/50 rounded-lg border border-gray-700">
        <p className="text-gray-500">No volatility data available</p>
      </div>
    );
  }

  const getBarColor = (volatility) => {
    if (volatility >= 8) return '#EF4444'; // Spike
    if (volatility >= 4) return '#F59E0B'; // High
    if (volatility >= 2) return '#3B82F6'; // Medium
    return '#6B7280'; // Low
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const vol = payload[0].value;
      let regime = 'Low';
      let color = '#6B7280';
      if (vol >= 8) { regime = 'SPIKE'; color = '#EF4444'; }
      else if (vol >= 4) { regime = 'High'; color = '#F59E0B'; }
      else if (vol >= 2) { regime = 'Medium'; color = '#3B82F6'; }
      
      return (
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-lg">
          <p className="text-gray-400 text-xs mb-1">{label}</p>
          <p style={{ color }} className="font-bold">
            {vol.toFixed(1)}% ({regime})
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="h-40" style={{ minWidth: 0 }}>
      <ResponsiveContainer width="100%" height="100%" minWidth={100} minHeight={100}>
        <BarChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis 
            dataKey="time" 
            stroke="#9CA3AF"
            tick={{ fontSize: 9 }}
            interval="preserveStartEnd"
            tickFormatter={(v) => {
              const match = String(v).match(/^([A-Za-z]+ \d+)/);
              return match ? match[1] : v;
            }}
          />
          <YAxis 
            stroke="#9CA3AF"
            tick={{ fontSize: 10 }}
            tickFormatter={(value) => `${value}%`}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={8} stroke="#EF4444" strokeDasharray="3 3" />
          <ReferenceLine y={4} stroke="#F59E0B" strokeDasharray="3 3" />
          <Bar dataKey="volatility" radius={[2, 2, 0, 0]}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={getBarColor(entry.volatility)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default VolatilityChart;
