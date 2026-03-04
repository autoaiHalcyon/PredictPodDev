import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';

const EdgeChart = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 bg-gray-800/50 rounded-lg border border-gray-700">
        <p className="text-gray-500">No edge data available</p>
      </div>
    );
  }

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const edge = payload[0].value;
      const color = edge >= 5 ? '#22C55E' : edge >= 3 ? '#86EFAC' : edge <= -5 ? '#EF4444' : edge < 0 ? '#FCA5A5' : '#9CA3AF';
      return (
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-lg">
          <p className="text-gray-400 text-xs mb-1">{label}</p>
          <p style={{ color }} className="text-lg font-bold">
            {edge >= 0 ? '+' : ''}{edge}%
          </p>
        </div>
      );
    }
    return null;
  };

  // Create gradient stops based on data
  const gradientOffset = () => {
    const dataMax = Math.max(...data.map((d) => d.edge));
    const dataMin = Math.min(...data.map((d) => d.edge));
    if (dataMax <= 0) return 0;
    if (dataMin >= 0) return 1;
    return dataMax / (dataMax - dataMin);
  };

  const off = gradientOffset();

  return (
    <div className="h-48" style={{ minWidth: 0 }}>
      <ResponsiveContainer width="100%" height="100%" minWidth={100} minHeight={100}>
        <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="edgeGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset={0} stopColor="#22C55E" stopOpacity={0.8} />
              <stop offset={off} stopColor="#22C55E" stopOpacity={0.3} />
              <stop offset={off} stopColor="#EF4444" stopOpacity={0.3} />
              <stop offset={1} stopColor="#EF4444" stopOpacity={0.8} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis 
            dataKey="time" 
            stroke="#9CA3AF"
            tick={{ fontSize: 10 }}
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
          <ReferenceLine y={5} stroke="#22C55E" strokeDasharray="3 3" label={{ value: '+5%', fill: '#22C55E', fontSize: 10 }} />
          <ReferenceLine y={0} stroke="#6B7280" />
          <ReferenceLine y={-5} stroke="#EF4444" strokeDasharray="3 3" label={{ value: '-5%', fill: '#EF4444', fontSize: 10 }} />
          <Area
            type="monotone"
            dataKey="edge"
            stroke="#8B5CF6"
            fill="url(#edgeGradient)"
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

export default EdgeChart;
