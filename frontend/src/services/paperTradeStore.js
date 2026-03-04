import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from '../components/ui/dialog';
import {
  ArrowLeft, TrendingUp, TrendingDown, DollarSign, Activity,
  BarChart3, Target, Trash2, X, RefreshCw, ChevronDown, ChevronUp,
  FileText, Filter, Download, AlertTriangle,
} from 'lucide-react';
import {
  getTrades, getPortfolioStats, closeTrade, deleteTrade,
  clearAllTrades, calcPnl,
} from '../services/paperTradeStore';

// ── tiny helpers ──────────────────────────────────────────────────────────────
const fmt = (n, decimals = 2) =>
  (n >= 0 ? '+' : '') + Number(n).toFixed(decimals);

const fmtUsd = (n) => {
  const abs = Math.abs(n).toFixed(2);
  return (n >= 0 ? '+$' : '-$') + abs;
};

const fmtPct = (n) => (n >= 0 ? '+' : '') + Number(n).toFixed(1) + '%';

const pnlColor = (n) =>
  n > 0 ? 'text-emerald-400' : n < 0 ? 'text-red-400' : 'text-gray-400';

const pnlBg = (n) =>
  n > 0 ? 'bg-emerald-900/20 border-emerald-800/50'
         : n < 0 ? 'bg-red-900/20 border-red-800/50'
         : 'bg-gray-800/30 border-gray-700/50';

const statusColor = {
  open:    'bg-blue-900/40 text-blue-300 border border-blue-700/60',
  closed:  'bg-gray-800/60 text-gray-400 border border-gray-700/60',
  expired: 'bg-yellow-900/40 text-yellow-400 border border-yellow-700/60',
};

const typeColor = {
  manual:      'bg-gray-700 text-gray-200',
  signal:      'bg-blue-700 text-white',
  'auto-edge': 'bg-purple-700 text-white',
};

// ── Stat Card ─────────────────────────────────────────────────────────────────
const StatCard = ({ label, value, sub, icon: Icon, valueClass = 'text-white' }) => (
  <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-col gap-1">
    <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
      <span>{label}</span>
      {Icon && <Icon className="w-3.5 h-3.5" />}
    </div>
    <div className={`text-2xl font-bold font-mono ${valueClass}`}>{value}</div>
    {sub && <div className="text-xs text-gray-500">{sub}</div>}
  </div>
);

// ── Mini sparkline (SVG, no lib) ──────────────────────────────────────────────
const MiniBar = ({ value, max }) => {
  const pct = max > 0 ? Math.abs(value) / max : 0;
  const color = value >= 0 ? '#34d399' : '#f87171';
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct * 100}%`, background: color }}
        />
      </div>
    </div>
  );
};

// ── Trade Row ─────────────────────────────────────────────────────────────────
const TradeRow = ({ trade, maxAbsPnl, onClose, onDelete, expanded, onToggle }) => {
  const pnl = trade.pnl || 0;
  const entryPct  = (trade.entry_price  * 100).toFixed(0);
  const currentPct = (trade.current_price * 100).toFixed(0);
  const exitPct   = trade.exit_price != null ? (trade.exit_price * 100).toFixed(0) : null;
  const returnPct = trade.entry_price > 0
    ? ((trade.current_price - trade.entry_price) / trade.entry_price) * 100
    : 0;

  return (
    <>
      <tr
        className="border-b border-gray-800/60 hover:bg-gray-800/30 transition-colors cursor-pointer"
        onClick={onToggle}
      >
        {/* Game */}
        <td className="px-4 py-3">
          <div className="flex flex-col gap-0.5">
            <Link
              to={`/game/${trade.game_id}`}
              className="text-xs font-mono text-blue-400 hover:text-blue-300 truncate max-w-[140px]"
              onClick={e => e.stopPropagation()}
            >
              {trade.game_id}
            </Link>
            <span className="text-xs text-gray-500 truncate max-w-[140px]">
              {trade.market_name || trade.game_title || '—'}
            </span>
          </div>
        </td>

        {/* Type */}
        <td className="px-3 py-3">
          <Badge className={`${typeColor[trade.type] || typeColor.manual} text-[10px] px-1.5 py-0`}>
            {trade.type === 'auto-edge' ? 'AUTO' : trade.type?.toUpperCase()}
          </Badge>
        </td>

        {/* Side / Dir */}
        <td className="px-3 py-3 text-center">
          <div className="flex flex-col items-center gap-0.5">
            <span className={`text-xs font-bold ${trade.side === 'yes' ? 'text-emerald-400' : 'text-red-400'}`}>
              {trade.side?.toUpperCase()}
            </span>
            <span className="text-[10px] text-gray-500">{trade.direction?.toUpperCase()}</span>
          </div>
        </td>

        {/* Qty */}
        <td className="px-3 py-3 text-center font-mono text-sm text-gray-200">
          {trade.quantity}
        </td>

        {/* Entry */}
        <td className="px-3 py-3 text-center font-mono text-sm text-gray-400">
          {entryPct}¢
        </td>

        {/* Current / Exit */}
        <td className="px-3 py-3 text-center font-mono text-sm">
          {trade.status === 'closed'
            ? <span className="text-gray-400">{exitPct}¢</span>
            : <span className="text-white">{currentPct}¢</span>}
        </td>

        {/* P&L bar + number */}
        <td className="px-3 py-3">
          <div className="flex flex-col gap-1 items-end">
            <span className={`font-mono font-bold text-sm ${pnlColor(pnl)}`}>
              {fmtUsd(pnl)}
            </span>
            <MiniBar value={pnl} max={maxAbsPnl} />
          </div>
        </td>

        {/* Return % */}
        <td className="px-3 py-3 text-center">
          <span className={`text-xs font-mono ${pnlColor(returnPct)}`}>
            {fmtPct(returnPct)}
          </span>
        </td>

        {/* Status */}
        <td className="px-3 py-3 text-center">
          <Badge className={`${statusColor[trade.status]} text-[10px] px-1.5 py-0`}>
            {trade.status}
          </Badge>
        </td>

        {/* Time */}
        <td className="px-3 py-3 text-right text-[10px] text-gray-500 whitespace-nowrap">
          {new Date(trade.timestamp).toLocaleString('en-US', {
            month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit',
          })}
        </td>

        {/* Expand chevron */}
        <td className="px-3 py-3 text-center text-gray-600">
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </td>
      </tr>

      {/* ── Expanded detail row ── */}
      {expanded && (
        <tr className="bg-gray-900/60 border-b border-gray-800/60">
          <td colSpan={11} className="px-6 py-4">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-4">
              <div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Strategy</div>
                <div className="text-xs text-purple-300">{trade.strategy || '—'}</div>
              </div>
              <div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">League</div>
                <div className="text-xs text-gray-200">{trade.league || '—'}</div>
              </div>
              <div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Entry Price</div>
                <div className="text-xs font-mono text-gray-200">{entryPct}¢ / contract</div>
              </div>
              <div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                  {trade.status === 'closed' ? 'Exit Price' : 'Current Price'}
                </div>
                <div className="text-xs font-mono text-gray-200">
                  {trade.status === 'closed' ? exitPct : currentPct}¢ / contract
                </div>
              </div>
              <div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Cost Basis</div>
                <div className="text-xs font-mono text-gray-200">
                  ${(trade.entry_price * trade.quantity).toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                  {trade.status === 'closed' ? 'Closed At' : 'Age'}
                </div>
                <div className="text-xs text-gray-200">
                  {trade.status === 'closed' && trade.closed_at
                    ? new Date(trade.closed_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
                    : formatAge(trade.timestamp)}
                </div>
              </div>
            </div>

            {/* P&L breakdown */}
            <div className={`rounded-lg border p-3 flex items-center justify-between ${pnlBg(pnl)}`}>
              <div className="flex items-center gap-3">
                {pnl >= 0
                  ? <TrendingUp className="w-4 h-4 text-emerald-400" />
                  : <TrendingDown className="w-4 h-4 text-red-400" />}
                <span className="text-xs text-gray-400">
                  {trade.status === 'open' ? 'Unrealised P&L' : 'Realised P&L'}
                </span>
                <span className={`font-mono font-bold ${pnlColor(pnl)}`}>
                  {fmtUsd(pnl)}
                </span>
                <span className={`text-xs font-mono ${pnlColor(returnPct)}`}>
                  ({fmtPct(returnPct)})
                </span>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2">
                {trade.status === 'open' && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs border-gray-600 text-gray-300 hover:border-red-600 hover:text-red-400"
                    onClick={(e) => { e.stopPropagation(); onClose(trade); }}
                  >
                    <X className="w-3 h-3 mr-1" />Close at Market
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs text-gray-500 hover:text-red-400"
                  onClick={(e) => { e.stopPropagation(); onDelete(trade.id); }}
                >
                  <Trash2 className="w-3 h-3" />
                </Button>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
};

function formatAge(ts) {
  const ms = Date.now() - new Date(ts).getTime();
  const m  = Math.floor(ms / 60000);
  if (m < 60)   return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24)   return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

// ── Main Portfolio Page ───────────────────────────────────────────────────────
const PaperTradePortfolio = () => {
  const [trades, setTrades]           = useState([]);
  const [stats, setStats]             = useState({});
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter]   = useState('all');
  const [search, setSearch]           = useState('');
  const [sortKey, setSortKey]         = useState('timestamp');
  const [sortDir, setSortDir]         = useState('desc');
  const [expandedId, setExpandedId]   = useState(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [closeTarget, setCloseTarget] = useState(null);

  const reload = useCallback(() => {
    setTrades(getTrades());
    setStats(getPortfolioStats());
  }, []);

  useEffect(() => {
    reload();
    const id = setInterval(reload, 5000);
    return () => clearInterval(id);
  }, [reload]);

  // ── filtering + sorting ───────────────────────────────────────────────────
  const visible = trades
    .filter(t => statusFilter === 'all' || t.status  === statusFilter)
    .filter(t => typeFilter   === 'all' || t.type    === typeFilter)
    .filter(t => {
      if (!search) return true;
      const q = search.toLowerCase();
      return (
        t.game_id?.toLowerCase().includes(q) ||
        t.market_name?.toLowerCase().includes(q) ||
        t.strategy?.toLowerCase().includes(q)
      );
    })
    .sort((a, b) => {
      let av = a[sortKey], bv = b[sortKey];
      if (typeof av === 'string') av = av.toLowerCase();
      if (typeof bv === 'string') bv = bv.toLowerCase();
      return sortDir === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
    });

  const maxAbsPnl = visible.reduce((m, t) => Math.max(m, Math.abs(t.pnl || 0)), 0.01);

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const SortTh = ({ label, k, className = '' }) => (
    <th
      className={`px-3 py-3 text-[10px] uppercase tracking-wider text-gray-500 cursor-pointer hover:text-gray-300 select-none ${className}`}
      onClick={() => toggleSort(k)}
    >
      <span className="flex items-center gap-1 justify-center">
        {label}
        {sortKey === k && (sortDir === 'asc'
          ? <ChevronUp className="w-3 h-3" />
          : <ChevronDown className="w-3 h-3" />)}
      </span>
    </th>
  );

  // ── close at market ───────────────────────────────────────────────────────
  const handleClose = (trade) => setCloseTarget(trade);
  const confirmClose = () => {
    if (!closeTarget) return;
    closeTrade(closeTarget.id, closeTarget.current_price);
    setCloseTarget(null);
    reload();
  };

  // ── delete ────────────────────────────────────────────────────────────────
  const handleDelete = (id) => {
    deleteTrade(id);
    reload();
  };

  // ── CSV export ────────────────────────────────────────────────────────────
  const exportCsv = () => {
    const headers = ['ID', 'Game', 'Market', 'Type', 'Strategy', 'Side', 'Dir', 'Qty',
                     'Entry¢', 'Current¢', 'Exit¢', 'P&L $', 'Return%', 'Status', 'Opened', 'Closed'];
    const rows = trades.map(t => [
      t.id, t.game_id, t.market_name, t.type, t.strategy,
      t.side, t.direction, t.quantity,
      (t.entry_price  * 100).toFixed(1),
      (t.current_price* 100).toFixed(1),
      t.exit_price != null ? (t.exit_price * 100).toFixed(1) : '',
      t.pnl?.toFixed(2),
      t.entry_price > 0 ? (((t.current_price - t.entry_price) / t.entry_price) * 100).toFixed(2) : '0',
      t.status,
      t.timestamp ? new Date(t.timestamp).toLocaleString() : '',
      t.closed_at  ? new Date(t.closed_at ).toLocaleString() : '',
    ]);
    const csv = [headers, ...rows].map(r => r.map(v => `"${v ?? ''}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = `paper_trades_${new Date().toISOString().slice(0, 10)}.csv`; a.click();
  };

  // ── render ────────────────────────────────────────────────────────────────
  const totalPnlPos = stats.totalPnl > 0;

  return (
    <div className="min-h-screen bg-background text-foreground">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="border-b border-border bg-card/50 sticky top-0 z-10">
        <div className="max-w-[1600px] mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/"><Button variant="ghost" size="sm" className="p-1"><ArrowLeft className="w-4 h-4" /></Button></Link>
            <div>
              <h1 className="text-base font-bold flex items-center gap-2">
                <FileText className="w-4 h-4 text-yellow-400" />
                Paper Trade Portfolio
              </h1>
              <p className="text-xs text-muted-foreground">Simulated trading log — no real money</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={exportCsv} className="text-xs gap-1">
              <Download className="w-3 h-3" />Export CSV
            </Button>
            <Button
              variant="ghost" size="sm"
              onClick={() => setConfirmClear(true)}
              className="text-xs gap-1 text-red-400 hover:text-red-300"
            >
              <Trash2 className="w-3 h-3" />Clear All
            </Button>
            <Button variant="ghost" size="sm" onClick={reload}>
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-[1600px] mx-auto px-4 py-6 space-y-6">

        {/* ── Stats Grid ─────────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <StatCard
            label="Total P&L"
            value={fmtUsd(stats.totalPnl || 0)}
            sub={`Realised ${fmtUsd(stats.realisedPnl || 0)}`}
            icon={DollarSign}
            valueClass={pnlColor(stats.totalPnl || 0)}
          />
          <StatCard
            label="Unrealised"
            value={fmtUsd(stats.unrealisedPnl || 0)}
            sub={`${stats.openCount || 0} open positions`}
            icon={Activity}
            valueClass={pnlColor(stats.unrealisedPnl || 0)}
          />
          <StatCard
            label="Win Rate"
            value={`${stats.winRate || 0}%`}
            sub={`${stats.winCount || 0}W / ${stats.lossCount || 0}L`}
            icon={Target}
            valueClass={stats.winRate >= 50 ? 'text-emerald-400' : 'text-red-400'}
          />
          <StatCard
            label="Avg Win"
            value={fmtUsd(stats.avgWin || 0)}
            sub={`Avg loss ${fmtUsd(stats.avgLoss || 0)}`}
            icon={TrendingUp}
            valueClass="text-emerald-400"
          />
          <StatCard
            label="Best Trade"
            value={fmtUsd(stats.bestTrade || 0)}
            sub={`Worst ${fmtUsd(stats.worstTrade || 0)}`}
            icon={BarChart3}
            valueClass="text-emerald-400"
          />
          <StatCard
            label="Total Trades"
            value={stats.totalTrades || 0}
            sub={`${stats.totalVolume || 0} contracts`}
            icon={FileText}
            valueClass="text-white"
          />
        </div>

        {/* ── P&L Summary Bar ────────────────────────────────────────────── */}
        {stats.totalTrades > 0 && (
          <div className={`rounded-xl border p-4 flex items-center justify-between ${
            totalPnlPos
              ? 'bg-emerald-900/10 border-emerald-800/40'
              : 'bg-red-900/10 border-red-800/40'
          }`}>
            <div className="flex items-center gap-3">
              {totalPnlPos
                ? <TrendingUp className="w-5 h-5 text-emerald-400" />
                : <TrendingDown className="w-5 h-5 text-red-400" />}
              <div>
                <div className="text-xs text-gray-400">Portfolio P&L</div>
                <div className={`text-xl font-bold font-mono ${pnlColor(stats.totalPnl)}`}>
                  {fmtUsd(stats.totalPnl || 0)}
                </div>
              </div>
            </div>
            <div className="hidden sm:flex gap-6 text-center text-xs">
              <div>
                <div className="text-gray-500 mb-0.5">Realised</div>
                <div className={`font-mono font-semibold ${pnlColor(stats.realisedPnl)}`}>
                  {fmtUsd(stats.realisedPnl || 0)}
                </div>
              </div>
              <div>
                <div className="text-gray-500 mb-0.5">Unrealised</div>
                <div className={`font-mono font-semibold ${pnlColor(stats.unrealisedPnl)}`}>
                  {fmtUsd(stats.unrealisedPnl || 0)}
                </div>
              </div>
              <div>
                <div className="text-gray-500 mb-0.5">Win Rate</div>
                <div className={`font-mono font-semibold ${stats.winRate >= 50 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {stats.winRate || 0}%
                </div>
              </div>
              <div>
                <div className="text-gray-500 mb-0.5">Open</div>
                <div className="font-mono font-semibold text-blue-400">{stats.openCount || 0}</div>
              </div>
            </div>
          </div>
        )}

        {/* ── Filters ────────────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Filter className="w-3.5 h-3.5" />Filters:
          </div>
          <Input
            placeholder="Search game / market / strategy…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="h-8 text-xs bg-gray-900 border-gray-700 w-48"
          />
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-28 h-8 text-xs bg-gray-900 border-gray-700">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-gray-900 border-gray-700">
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="open">Open</SelectItem>
              <SelectItem value="closed">Closed</SelectItem>
              <SelectItem value="expired">Expired</SelectItem>
            </SelectContent>
          </Select>
          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="w-28 h-8 text-xs bg-gray-900 border-gray-700">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-gray-900 border-gray-700">
              <SelectItem value="all">All Types</SelectItem>
              <SelectItem value="manual">Manual</SelectItem>
              <SelectItem value="signal">Signal</SelectItem>
              <SelectItem value="auto-edge">Auto-Edge</SelectItem>
            </SelectContent>
          </Select>
          <span className="text-xs text-gray-500 ml-auto">
            {visible.length} of {trades.length} trades
          </span>
        </div>

        {/* ── Table ──────────────────────────────────────────────────────── */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          {visible.length === 0 ? (
            <div className="py-16 text-center space-y-3">
              <FileText className="w-8 h-8 mx-auto text-gray-700" />
              <p className="text-sm text-gray-500">
                {trades.length === 0
                  ? 'No paper trades yet — place your first trade from a game detail page.'
                  : 'No trades match the current filters.'}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-gray-800 bg-gray-950/60">
                  <tr>
                    <th className="px-4 py-3 text-left text-[10px] uppercase tracking-wider text-gray-500">Game / Market</th>
                    <th className="px-3 py-3 text-left text-[10px] uppercase tracking-wider text-gray-500">Type</th>
                    <SortTh label="Side"   k="side"       className="text-center" />
                    <SortTh label="Qty"    k="quantity"   className="text-center" />
                    <SortTh label="Entry"  k="entry_price"  className="text-center" />
                    <th className="px-3 py-3 text-center text-[10px] uppercase tracking-wider text-gray-500">Cur / Exit</th>
                    <SortTh label="P&L"    k="pnl"        className="text-right" />
                    <th className="px-3 py-3 text-center text-[10px] uppercase tracking-wider text-gray-500">Return</th>
                    <SortTh label="Status" k="status"     className="text-center" />
                    <SortTh label="Opened" k="timestamp"  className="text-right" />
                    <th className="px-3 py-3 w-6" />
                  </tr>
                </thead>
                <tbody>
                  {visible.map(trade => (
                    <TradeRow
                      key={trade.id}
                      trade={trade}
                      maxAbsPnl={maxAbsPnl}
                      onClose={handleClose}
                      onDelete={handleDelete}
                      expanded={expandedId === trade.id}
                      onToggle={() => setExpandedId(id => id === trade.id ? null : trade.id)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ── Footer note ────────────────────────────────────────────────── */}
        <p className="text-xs text-gray-600 text-center">
          Paper trades are stored locally in your browser. No real money is involved.
        </p>
      </div>

      {/* ── Confirm Close Dialog ─────────────────────────────────────────── */}
      <Dialog open={!!closeTarget} onOpenChange={() => setCloseTarget(null)}>
        <DialogContent className="bg-gray-900 border-gray-800 max-w-sm">
          <DialogHeader>
            <DialogTitle>Close Trade at Market</DialogTitle>
            <DialogDescription>
              This will lock in your P&L at the current price.
            </DialogDescription>
          </DialogHeader>
          {closeTarget && (
            <div className="py-2 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-400">Market:</span>
                <span className="font-medium">{closeTarget.market_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Exit Price:</span>
                <span className="font-mono">{(closeTarget.current_price * 100).toFixed(0)}¢</span>
              </div>
              <div className={`flex justify-between font-bold ${pnlColor(closeTarget.pnl)}`}>
                <span>Realised P&L:</span>
                <span className="font-mono">{fmtUsd(closeTarget.pnl || 0)}</span>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setCloseTarget(null)}>Cancel</Button>
            <Button onClick={confirmClose}>Confirm Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Confirm Clear Dialog ─────────────────────────────────────────── */}
      <Dialog open={confirmClear} onOpenChange={setConfirmClear}>
        <DialogContent className="bg-gray-900 border-gray-800 max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="w-4 h-4" />Clear All Trades
            </DialogTitle>
            <DialogDescription>
              This will permanently delete all {trades.length} paper trades from local storage.
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmClear(false)}>Cancel</Button>
            <Button
              className="bg-red-700 hover:bg-red-600"
              onClick={() => { clearAllTrades(); reload(); setConfirmClear(false); }}
            >
              Delete All
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PaperTradePortfolio;