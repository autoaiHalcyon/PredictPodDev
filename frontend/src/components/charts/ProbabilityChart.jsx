import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

const DEFAULT_COLORS = [
  '#EF4444', // Red
  '#F97316', // Orange
  '#EAB308', // Yellow
  '#22C55E', // Green
  '#06B6D4', // Cyan
  '#3B82F6', // Blue
  '#8B5CF6', // Purple
  '#EC4899', // Pink
];

// Abbreviate a team name to ≤4 chars
const abbrev = (name) => {
  if (!name) return '';
  const words = name.trim().split(/\s+/);
  if (words.length === 1) return words[0].slice(0, 4).toUpperCase();
  // Last word usually = city/nickname abbreviation in Kalshi names
  return words[words.length - 1].slice(0, 4).toUpperCase();
};

/** Custom dot: only renders a filled circle + label at the LAST data point */
const EndLabelDot = (props) => {
  const { cx, cy, index, dataLength, stroke, value, teamLabel } = props;
  if (index !== dataLength - 1 || cx == null || cy == null) return null;
  return (
    <g>
      <circle cx={cx} cy={cy} r={4} fill={stroke} stroke="none" />
      <text
        x={cx + 8}
        y={cy - 6}
        fill={stroke}
        fontSize={11}
        fontWeight="700"
        fontFamily="'Inter', sans-serif"
      >
        {teamLabel}
      </text>
      <text
        x={cx + 8}
        y={cy + 7}
        fill={stroke}
        fontSize={12}
        fontWeight="700"
        fontFamily="monospace"
      >
        {value != null ? `${Math.round(value)}%` : ''}
      </text>
    </g>
  );
};

const ProbabilityChart = ({ data, timeframe = 'full' }) => {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-96 bg-gray-800/50 rounded-lg border border-gray-700">
        <p className="text-gray-500">No probability data available</p>
      </div>
    );
  }

  // Extract all unique team names from market_prices
  const teamNames = new Set();
  data.forEach((point) => {
    if (point.market_prices) {
      Object.keys(point.market_prices).forEach((name) => teamNames.add(name));
    }
  });
  const uniqueTeams = Array.from(teamNames).sort();

  // Flatten data structure: move market_prices to top level
  const flattenedData = data.map((point) => {
    const flattened = { timestamp: point.timestamp, time: point.time };
    if (point.market_prices) {
      Object.entries(point.market_prices).forEach(([team, price]) => {
        flattened[`team_${team.replace(/\s+/g, '_')}`] = price;
      });
    }
    return flattened;
  });

  // Assign colors to teams
  const teamColorMap = {};
  uniqueTeams.forEach((team, index) => {
    teamColorMap[team] = DEFAULT_COLORS[index % DEFAULT_COLORS.length];
  });

  // ── Dynamic Y-axis range ──────────────────────────────────────────────────
  // Collect all non-null values across all teams and all data points
  const allValues = flattenedData.flatMap((pt) =>
    uniqueTeams
      .map((t) => pt[`team_${t.replace(/\s+/g, '_')}`])
      .filter((v) => v != null && !isNaN(v))
  );
  const rawMin = allValues.length ? Math.min(...allValues) : 0;
  const rawMax = allValues.length ? Math.max(...allValues) : 100;
  const pad = Math.max(5, (rawMax - rawMin) * 0.15); // at least 5% padding each side
  const domainMin = Math.max(0,   Math.floor((rawMin - pad) / 2.5) * 2.5);
  const domainMax = Math.min(100, Math.ceil ((rawMax + pad) / 2.5) * 2.5);
  const range = domainMax - domainMin || 1;

  // Tick step: aim for ~6 ticks in the visible range
  const rawStep = range / 6;
  const tickStep = rawStep <= 2.5 ? 2.5 : rawStep <= 5 ? 5 : 10;
  const yTicks = [];
  for (let v = domainMin; v <= domainMax + 0.001; v = Math.round((v + tickStep) * 100) / 100) {
    yTicks.push(Math.round(v * 10) / 10);
  }

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-lg">
          <p className="text-gray-400 text-xs mb-2">{label}</p>
          {payload.map((entry, i) => (
            <p key={i} style={{ color: entry.color }} className="text-sm font-mono">
              {entry.name}: {entry.value != null ? `${Math.round(entry.value)}%` : '—'}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  const dataLength = flattenedData.length;

  return (
    <div style={{ minWidth: 0 }}>
      <ResponsiveContainer width="100%" height={420} minWidth={100} minHeight={180}>
        <LineChart data={flattenedData} margin={{ top: 12, right: 72, left: 4, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" verticalPoints={[]} />
          <XAxis
            dataKey="time"
            stroke="#9CA3AF"
            tick={{ fontSize: 10, fill: '#6B7280' }}
            interval={Math.max(1, Math.floor(flattenedData.length / 8))}
            angle={-30}
            textAnchor="end"
            height={45}
            tickFormatter={(v) => {
              const match = String(v).match(/,\s*(.+)$/);
              return match ? match[1] : v;
            }}
          />
          <YAxis
            stroke="#374151"
            domain={[domainMin, domainMax]}
            ticks={yTicks}
            tickFormatter={(v) => `${v}%`}
            tick={{ fontSize: 10, fill: '#6B7280' }}
            width={38}
          />
          <Tooltip content={<CustomTooltip />} />
          {/* 50% reference line only if in view */}
          {domainMin < 50 && domainMax > 50 && (
            <ReferenceLine y={50} stroke="#4B5563" strokeDasharray="5 5" />
          )}

          {uniqueTeams.map((team) => {
            const dataKey = `team_${team.replace(/\s+/g, '_')}`;
            const color = teamColorMap[team];
            const label = abbrev(team);

            return (
              <Line
                key={team}
                type="monotone"
                dataKey={dataKey}
                stroke={color}
                strokeWidth={2}
                dot={(props) => (
                  <EndLabelDot
                    key={`dot-${team}-${props.index}`}
                    {...props}
                    dataLength={dataLength}
                    stroke={color}
                    teamLabel={label}
                  />
                )}
                activeDot={{ r: 5 }}
                name={team}
                isAnimationActive={false}
              />
            );
          })}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default ProbabilityChart;
