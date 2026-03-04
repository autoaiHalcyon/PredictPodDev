import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Progress } from '../components/ui/progress';
import {
  ArrowLeft,
  RefreshCw,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Activity,
  AlertTriangle,
  Wallet,
  PieChart,
  BarChart3,
  FileText
} from 'lucide-react';
import { getPortfolio, getPositions, getRiskStatus, flattenAll, formatCurrency, formatPercent } from '../services/api';
import ThemeToggle from '../components/ThemeToggle';
import { useTradingStore } from '../stores/tradingStore';

const Portfolio = () => {
  const [portfolio, setPortfolio] = useState(null);
  const [positions, setPositions] = useState([]);
  const [riskStatus, setRiskStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [flattenLoading, setFlattenLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(20);
  
  // Get trades from Zustand store for Paper + Live summary
  const { paperTrades: storePaperTrades, liveTrades: storeLiveTrades, fetchTrades } = useTradingStore();
  
  // Use mock data if no real data is available (for testing)
  const mockOpenTrade = {
    id: 'mock-1',
    game_id: 'KXNBA-SAMPLE',
    market_id: 'market-1',
    side: 'yes',
    direction: 'buy',
    quantity: 5,
    price: 0.65,
    current_price: 0.72,
    status: 'filled',
    pnl: 35,
    unrealized_pnl: 35,
    created_at: new Date().toISOString()
  };
  
  const paperTrades = useMemo(() => storePaperTrades.length > 0 ? storePaperTrades : [], [storePaperTrades]);
  const liveTrades = useMemo(() => storeLiveTrades.length > 0 ? storeLiveTrades : [], [storeLiveTrades]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [portfolioData, positionsData, riskData] = await Promise.all([
        getPortfolio(),
        getPositions(),
        getRiskStatus()
      ]);
      setPortfolio(portfolioData);
      setPositions(positionsData.positions || []);
      setRiskStatus(riskData);
    } catch (error) {
      console.error('Failed to load portfolio:', error);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadData();
    fetchTrades(1000); // Load trades for Paper/Live summary
    // Update portfolio in real-time (every 2 seconds)
    const interval = setInterval(() => {
      loadData();
      fetchTrades(1000);
    }, 2000);
    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchTrades]);

  // Log trades data when it changes
  useEffect(() => {
    console.log('Portfolio - Trades updated:', {
      paperTradesLength: paperTrades.length,
      liveTradesLength: liveTrades.length,
      totalTrades: (paperTrades.length + liveTrades.length),
      paperTrades: paperTrades.map(t => ({ 
        id: t.id, 
        closed_at: t.closed_at, 
        close_date: t.close_date,
        status: t.status
      })),
      liveTrades: liveTrades.map(t => ({ 
        id: t.id, 
        closed_at: t.closed_at, 
        close_date: t.close_date,
        status: t.status
      }))
    });
  }, [paperTrades, liveTrades]);
  
  // Calculate dynamic portfolio values based on actual trades
  const calculatePortfolioMetrics = () => {
    const INITIAL_BALANCE = 10000;
    
    // Closed = HAS closed_at or close_date
    // Open = NO closed_at or close_date
    const isClosed = (t) => {
      const hasClosed_at = t.closed_at !== null && t.closed_at !== undefined && t.closed_at !== '';
      const hasClose_date = t.close_date !== null && t.close_date !== undefined && t.close_date !== '';
      return hasClosed_at || hasClose_date;
    };
    const isOpen = (t) => !isClosed(t);
    
    // Calculate total realized P&L from all closed trades
    const realizedPnL = [...paperTrades, ...liveTrades]
      .filter(isClosed)
      .reduce((sum, t) => sum + (t.pnl || t.realized_pnl || 0), 0);
    
    // Calculate total unrealized P&L from all open trades
    const unrealizedPnL = [...paperTrades, ...liveTrades]
      .filter(isOpen)
      .reduce((sum, t) => sum + (t.unrealized_pnl || t.pnl || 0), 0);
    
    // Current balance = Initial + Realized P&L
    const currentBalance = INITIAL_BALANCE + realizedPnL;
    
    // Portfolio value = Balance + Unrealized P&L
    const portfolioValue = currentBalance + unrealizedPnL;
    
    // Total P&L = Realized + Unrealized
    const totalPnL = realizedPnL + unrealizedPnL;
    
    // Total exposure from open positions (those without close_date or closed_at)
    const totalExposure = [...paperTrades, ...liveTrades]
      .filter(isOpen)
      .reduce((sum, t) => {
        const quantity = t.quantity || t.qty || 0;
        const price = t.price || t.avg_entry_price || 0.5;
        return sum + (quantity * price);
      }, 0);
    
    return {
      balance: currentBalance,
      portfolioValue: portfolioValue,
      totalExposure: totalExposure,
      totalPnL: totalPnL,
      realizedPnL: realizedPnL,
      unrealizedPnL: unrealizedPnL
    };
  };
  
  const portfolioMetrics = calculatePortfolioMetrics();
  
  // Calculate Paper and Live summaries
  const getPaperSummary = () => {
    const INITIAL_BALANCE = 10000;
    
    // Helper: check if trade is open/closed
    const isClosed = (t) => {
      const hasClosed_at = t.closed_at !== null && t.closed_at !== undefined && t.closed_at !== '';
      const hasClose_date = t.close_date !== null && t.close_date !== undefined && t.close_date !== '';
      return hasClosed_at || hasClose_date;
    };
    
    const openPaper = paperTrades.filter(t => !isClosed(t));
    const closedPaper = paperTrades.filter(isClosed);
    
    const realizedPnL = closedPaper.reduce((sum, t) => sum + (t.pnl || t.realized_pnl || 0), 0);
    const unrealizedPnL = openPaper.reduce((sum, t) => sum + (t.unrealized_pnl || t.pnl || 0), 0);
    const totalPnL = realizedPnL + unrealizedPnL;
    
    const exposure = openPaper.reduce((sum, t) => {
      const quantity = t.quantity || t.qty || 0;
      const price = t.price || t.avg_entry_price || 0.5;
      return sum + (quantity * price);
    }, 0);
    
    const balance = INITIAL_BALANCE + realizedPnL;
    const value = balance + unrealizedPnL;
    
    return {
      balance: balance,
      value: value,
      exposure: exposure,
      pnl: totalPnL,
      openCount: openPaper.length,
      totalCount: paperTrades.length
    };
  };
  
  const getLiveSummary = () => {
    // Helper: check if trade is open/closed  
    const isClosed = (t) => {
      const hasClosed_at = t.closed_at !== null && t.closed_at !== undefined && t.closed_at !== '';
      const hasClose_date = t.close_date !== null && t.close_date !== undefined && t.close_date !== '';
      return hasClosed_at || hasClose_date;
    };
    
    const openLive = liveTrades.filter(t => !isClosed(t));
    const closedLive = liveTrades.filter(isClosed);
    
    const realizedPnL = closedLive.reduce((sum, t) => sum + (t.pnl || t.realized_pnl || 0), 0);
    const unrealizedPnL = openLive.reduce((sum, t) => sum + (t.unrealized_pnl || t.pnl || 0), 0);
    const totalPnL = realizedPnL + unrealizedPnL;
    
    const exposure = openLive.reduce((sum, t) => {
      const quantity = t.quantity || t.qty || 0;
      const price = t.price || t.avg_entry_price || 0.5;
      return sum + (quantity * price);
    }, 0);
    
    return {
      balance: 0, // Live balance would come from actual exchange
      value: totalPnL,
      exposure: exposure,
      pnl: totalPnL,
      openCount: openLive.length,
      totalCount: liveTrades.length
    };
  };
  
  const paperSummary = getPaperSummary();
  const liveSummary = getLiveSummary();
  
  // Combine open positions from both paper and live
  const getAllOpenPositions = () => {
    // Open = NO closed_at AND NO close_date (checking for null, undefined, or empty string)
    const isOpen = (t) => {
      const hasClosed_at = t.closed_at !== null && t.closed_at !== undefined && t.closed_at !== '';
      const hasClose_date = t.close_date !== null && t.close_date !== undefined && t.close_date !== '';
      return !hasClosed_at && !hasClose_date;
    };
    
    const paperOpen = paperTrades.filter(isOpen).map(t => ({...t, tradeType: 'PAPER'}));
    const liveOpen = liveTrades.filter(isOpen).map(t => ({...t, tradeType: 'LIVE'}));
    const result = [...paperOpen, ...liveOpen];
    
    console.log('getAllOpenPositions - Filtering result:', {
      paperTradesInput: paperTrades.length,
      liveTradesInput: liveTrades.length,
      paperOpenOutput: paperOpen.length,
      liveOpenOutput: liveOpen.length,
      totalOpenPositions: result.length,
      details: result.map(t => ({
        id: t.id,
        game_id: t.game_id,
        closed_at: t.closed_at,
        close_date: t.close_date,
        status: t.status
      }))
    });
    
    return result;
  };
  
  const allOpenPositions = getAllOpenPositions();
  
  // Pagination for open positions
  const totalPages = Math.ceil(allOpenPositions.length / pageSize);
  const startIdx = (currentPage - 1) * pageSize;
  const endIdx = startIdx + pageSize;
  const paginatedPositions = allOpenPositions.slice(startIdx, endIdx);

  // Calculate risk metrics dynamically
  const calculateRiskMetrics = () => {
    const MAX_OPEN_EXPOSURE = 1000;
    const MAX_DAILY_LOSS = 500;
    
    const currentExposure = portfolioMetrics.totalExposure;
    const exposureUtilization = Math.min(100, (currentExposure / MAX_OPEN_EXPOSURE) * 100);
    
    // Calculate today's P&L (you may need to filter by date)
    const today = new Date().toDateString();
    const todayPnL = [...paperTrades, ...liveTrades]
      .filter(t => {
        const tradeDate = new Date(t.created_at || t.timestamp).toDateString();
        return tradeDate === today;
      })
      .reduce((sum, t) => sum + (t.pnl || t.realized_pnl || 0), 0);
    
    const dailyLoss = Math.abs(Math.min(0, todayPnL));
    const dailyLossUtilization = Math.min(100, (dailyLoss / MAX_DAILY_LOSS) * 100);
    
    return {
      current_exposure: currentExposure,
      max_open_exposure: MAX_OPEN_EXPOSURE,
      exposure_utilization: exposureUtilization,
      daily_pnl: todayPnL,
      max_daily_loss: MAX_DAILY_LOSS,
      daily_loss_utilization: dailyLossUtilization,
      is_locked_out: dailyLoss >= MAX_DAILY_LOSS,
      lockout_reason: dailyLoss >= MAX_DAILY_LOSS ? 'Daily loss limit reached' : null
    };
  };
  
  const dynamicRiskStatus = calculateRiskMetrics();

  const handleFlattenAll = async () => {
    if (!window.confirm('Are you sure you want to close ALL positions? This cannot be undone.')) {
      return;
    }
    setFlattenLoading(true);
    try {
      await flattenAll();
      loadData();
      fetchTrades(100);
    } catch (error) {
      console.error('Failed to flatten positions:', error);
    }
    setFlattenLoading(false);
  };

  return (
    <div className="min-h-screen bg-background text-foreground transition-colors duration-300">
      {/* Page Header */}
      <header className="border-b border-border bg-card/50">
        <div className="max-w-[1400px] mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Wallet className="w-6 h-6 text-blue-500" />
              <h1 className="text-xl font-bold">Portfolio</h1>
            </div>
            <div className="flex items-center gap-4">
              <Badge className="bg-yellow-900/50 text-yellow-400 border border-yellow-700">
                Paper Trading
              </Badge>
              <Button variant="ghost" size="sm" onClick={loadData}>
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-[1400px] mx-auto px-4 py-6">
        {loading && !portfolio ? (
          <div className="flex items-center justify-center py-20">
            <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
          </div>
        ) : (
          <div className="space-y-6">

            {/* Summary Cards - NOW DYNAMIC */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-card rounded-xl border border-border p-6">
                <div className="flex items-center gap-2 text-muted-foreground mb-2">
                  <Wallet className="w-4 h-4" />
                  <span className="text-sm">Balance</span>
                </div>
                <div className="text-3xl font-bold">
                  {formatCurrency(portfolioMetrics.balance)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Realized P&L: {formatCurrency(portfolioMetrics.realizedPnL)}
                </div>
              </div>

              <div className="bg-card rounded-xl border border-border p-6">
                <div className="flex items-center gap-2 text-muted-foreground mb-2">
                  <PieChart className="w-4 h-4" />
                  <span className="text-sm">Portfolio Value</span>
                </div>
                <div className="text-3xl font-bold">
                  {formatCurrency(portfolioMetrics.portfolioValue)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Unrealized P&L: {formatCurrency(portfolioMetrics.unrealizedPnL)}
                </div>
              </div>

              <div className="bg-card rounded-xl border border-border p-6">
                <div className="flex items-center gap-2 text-muted-foreground mb-2">
                  <BarChart3 className="w-4 h-4" />
                  <span className="text-sm">Total Exposure</span>
                </div>
                <div className="text-3xl font-bold">
                  {formatCurrency(portfolioMetrics.totalExposure)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {allOpenPositions.length} open position{allOpenPositions.length !== 1 ? 's' : ''}
                </div>
              </div>

              <div className="bg-card rounded-xl border border-border p-6">
                <div className="flex items-center gap-2 text-muted-foreground mb-2">
                  {portfolioMetrics.totalPnL >= 0 ? (
                    <TrendingUp className="w-4 h-4 text-green-500" />
                  ) : (
                    <TrendingDown className="w-4 h-4 text-red-500" />
                  )}
                  <span className="text-sm">Total P&L</span>
                </div>
                <div className={`text-3xl font-bold ${
                  portfolioMetrics.totalPnL >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  {portfolioMetrics.totalPnL >= 0 ? '+' : ''}{formatCurrency(portfolioMetrics.totalPnL)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  ROI: {formatPercent((portfolioMetrics.totalPnL / 10000))}
                </div>
              </div>
            </div>

            {/* Paper + Live Summary Table */}
            <div className="bg-card rounded-xl border border-border overflow-hidden" data-testid="paper-live-summary">
              <div className="p-4 border-b border-border">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                  <FileText className="w-5 h-5 text-primary" />
                  Trading Summary (Paper + Live)
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-muted/30">
                      <th className="text-left py-3 px-4 font-medium">Mode</th>
                      <th className="text-right py-3 px-4 font-medium">Balance</th>
                      <th className="text-right py-3 px-4 font-medium">Portfolio Value</th>
                      <th className="text-right py-3 px-4 font-medium">Exposure</th>
                      <th className="text-right py-3 px-4 font-medium">Total P/L</th>
                      <th className="text-center py-3 px-4 font-medium">Open Positions</th>
                      <th className="text-center py-3 px-4 font-medium">Total Trades</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-border/50 hover:bg-muted/20">
                      <td className="py-3 px-4">
                        <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/50">PAPER</Badge>
                      </td>
                      <td className="text-right py-3 px-4 font-mono">{formatCurrency(paperSummary.balance)}</td>
                      <td className="text-right py-3 px-4 font-mono">{formatCurrency(paperSummary.value)}</td>
                      <td className="text-right py-3 px-4 font-mono">{formatCurrency(paperSummary.exposure)}</td>
                      <td className={`text-right py-3 px-4 font-mono font-bold ${paperSummary.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {paperSummary.pnl >= 0 ? '+' : ''}{formatCurrency(paperSummary.pnl)}
                      </td>
                      <td className="text-center py-3 px-4 font-mono">{paperSummary.openCount}</td>
                      <td className="text-center py-3 px-4 font-mono">{paperSummary.totalCount}</td>
                    </tr>
                    <tr className="hover:bg-muted/20">
                      <td className="py-3 px-4">
                        <Badge className="bg-purple-500/20 text-purple-400 border-purple-500/50">LIVE</Badge>
                      </td>
                      <td className="text-right py-3 px-4 font-mono">{formatCurrency(liveSummary.balance)}</td>
                      <td className="text-right py-3 px-4 font-mono">{formatCurrency(liveSummary.value)}</td>
                      <td className="text-right py-3 px-4 font-mono">{formatCurrency(liveSummary.exposure)}</td>
                      <td className={`text-right py-3 px-4 font-mono font-bold ${liveSummary.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {liveSummary.pnl >= 0 ? '+' : ''}{formatCurrency(liveSummary.pnl)}
                      </td>
                      <td className="text-center py-3 px-4 font-mono">{liveSummary.openCount}</td>
                      <td className="text-center py-3 px-4 font-mono">{liveSummary.totalCount}</td>
                    </tr>
                  </tbody>
                  <tfoot>
                    <tr className="bg-muted/30 font-medium">
                      <td className="py-3 px-4">COMBINED</td>
                      <td className="text-right py-3 px-4 font-mono">{formatCurrency(paperSummary.balance + liveSummary.balance)}</td>
                      <td className="text-right py-3 px-4 font-mono">{formatCurrency(paperSummary.value + liveSummary.value)}</td>
                      <td className="text-right py-3 px-4 font-mono">{formatCurrency(paperSummary.exposure + liveSummary.exposure)}</td>
                      <td className={`text-right py-3 px-4 font-mono font-bold ${(paperSummary.pnl + liveSummary.pnl) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {(paperSummary.pnl + liveSummary.pnl) >= 0 ? '+' : ''}{formatCurrency(paperSummary.pnl + liveSummary.pnl)}
                      </td>
                      <td className="text-center py-3 px-4 font-mono">{paperSummary.openCount + liveSummary.openCount}</td>
                      <td className="text-center py-3 px-4 font-mono">{paperSummary.totalCount + liveSummary.totalCount}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
            
            

            {/* Risk Status - REMOVED TRADE LIMIT */}
            <div className="bg-card rounded-xl border border-border p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Activity className="w-5 h-5 text-blue-500" />
                Risk Status
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-muted-foreground">Exposure</span>
                    <span>{formatPercent(dynamicRiskStatus.exposure_utilization / 100)}</span>
                  </div>
                  <Progress value={dynamicRiskStatus.exposure_utilization} className="h-2" />
                  <div className="text-xs text-muted-foreground mt-1">
                    {formatCurrency(dynamicRiskStatus.current_exposure)} / {formatCurrency(dynamicRiskStatus.max_open_exposure)}
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-muted-foreground">Daily Loss</span>
                    <span>{formatPercent(dynamicRiskStatus.daily_loss_utilization / 100)}</span>
                  </div>
                  <Progress 
                    value={dynamicRiskStatus.daily_loss_utilization} 
                    className="h-2"
                    style={{
                      backgroundColor: 'rgb(127 29 29)',
                    }}
                  />
                  <div className="text-xs text-muted-foreground mt-1">
                    {formatCurrency(Math.abs(Math.min(0, dynamicRiskStatus.daily_pnl)))} / {formatCurrency(dynamicRiskStatus.max_daily_loss)}
                  </div>
                </div>
              </div>
              {dynamicRiskStatus.is_locked_out && (
                <div className="mt-4 p-3 bg-red-900/30 rounded-lg flex items-center gap-2 text-red-400">
                  <AlertTriangle className="w-5 h-5" />
                  <span>Trading locked: {dynamicRiskStatus.lockout_reason}</span>
                </div>
              )}
            </div>

            {/* Open Positions (Combined Paper + Live from DB) */}
            <div className="bg-card rounded-xl border border-border" data-testid="open-positions">
              <div className="p-6 border-b border-border flex items-center justify-between flex-wrap gap-3">
                <div>
                  <h3 className="text-lg font-semibold">
                    Open Positions ({allOpenPositions.length})
                  </h3>
                  {allOpenPositions.length > 0 && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Showing {startIdx + 1}-{Math.min(endIdx, allOpenPositions.length)} of {allOpenPositions.length}
                    </p>
                  )}
                </div>
                {/* {allOpenPositions.length > 0 && (
                  // <Button
                  //   variant="destructive"
                  //   size="sm"
                  //   onClick={handleFlattenAll}
                  //   disabled={flattenLoading}
                  // >
                  //   {flattenLoading ? (
                  //     <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                  //   ) : (
                  //     <AlertTriangle className="w-4 h-4 mr-2" />
                  //   )}
                  //   Flatten All
                  // </Button>
                )} */}
              </div>
              
              {allOpenPositions.length === 0 ? (
                <div className="p-8 text-center">
                  <div className="text-muted-foreground mb-2">No open positions</div>
                  {(paperTrades.length === 0 && liveTrades.length === 0) && (
                    <div className="text-xs text-muted-foreground mt-4 p-4 bg-muted rounded">
                      <p>Trades Data Status:</p>
                      <p>Paper: {paperTrades.length} | Live: {liveTrades.length}</p>
                      <p className="mt-2 text-blue-400">Loading trades from backend...</p>
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <div className="divide-y divide-border">
                    {/* Show positions from Zustand store (Paper + Live combined from DB) */}
                    {paginatedPositions.map((pos, idx) => (
                      <div key={`store-${startIdx + idx}`} className="p-4 flex items-center justify-between hover:bg-muted/30">
                        <div>
                          <div className="font-medium">{pos.game_title || pos.market_id || 'Unknown'}</div>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge variant="outline">{pos.side?.toUpperCase() || pos.direction?.toUpperCase() || '-'}</Badge>
                            <Badge className={pos.tradeType === 'PAPER' 
                              ? 'bg-blue-500/20 text-blue-400 border-blue-500/50 text-xs' 
                              : 'bg-purple-500/20 text-purple-400 border-purple-500/50 text-xs'
                            }>
                              {pos.tradeType}
                            </Badge>
                            <span className="text-muted-foreground">{pos.quantity || pos.qty || '-'} contracts</span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm text-muted-foreground">
                            Entry: {pos.price ? `${(pos.price * 100).toFixed(1)}¢` : pos.price_cents ? `${pos.price_cents}¢` : '-'}
                            {pos.current_price && ` → ${(pos.current_price * 100).toFixed(1)}¢`}
                          </div>
                          <div className={`font-bold ${
                            (pos.pnl || pos.unrealized_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                          }`}>
                            {formatCurrency(pos.pnl || pos.unrealized_pnl || 0)}
                            {pos.roi_percent && (
                              <span className="text-sm ml-1">
                                ({formatPercent(pos.roi_percent / 100)})
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                  
                  {/* Pagination Controls */}
                  {totalPages > 1 && (
                    <div className="p-4 border-t border-border flex items-center justify-between">
                      <div className="text-sm text-muted-foreground">
                        Page {currentPage} of {totalPages}
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                          disabled={currentPage === 1}
                        >
                          ← Previous
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                          disabled={currentPage === totalPages}
                        >
                          Next →
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Portfolio;