/**
 * useTrades Hook
 * Hook for managing trades (paper + live)
 */
import { useEffect, useCallback, useRef } from 'react';
import { useTradingStore } from '../stores/tradingStore';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';
const POLL_INTERVAL = 3000; // 3 seconds for trades

export default function useTrades(options = {}) {
  const { 
    autoFetch = true, 
    pollInterval = POLL_INTERVAL,
    tradeType = 'all', // 'all', 'paper', 'live'
    status = null // 'active', 'closed', null for all
  } = options;
  
  const {
    allTrades,
    paperTrades,
    liveTrades,
    tradesLoading,
    tradesError,
    lastTradesUpdate,
    setAllTrades,
    setPaperTrades,
    setLiveTrades,
    setTradesLoading,
    setTradesError,
    addTrade,
    updateTradeStatus
  } = useTradingStore();
  
  const pollRef = useRef(null);
  
  // Fetch trades from API
  const loadTrades = useCallback(async () => {
    setTradesLoading(true);
    setTradesError(null);
    
    try {
      // Fetch from multiple endpoints
      const [tradesRes, ordersRes] = await Promise.all([
        fetch(`${API_BASE}/api/trades?limit=100`),
        fetch(`${API_BASE}/api/orders?limit=100`)
      ]);
      
      let allTradesList = [];
      
      if (tradesRes.ok) {
        const data = await tradesRes.json();
        allTradesList = [...allTradesList, ...(data.trades || []).map(t => ({
          ...t,
          type: t.is_live ? 'live' : 'paper',
          status: t.status || 'closed'
        }))];
      }
      
      if (ordersRes.ok) {
        const data = await ordersRes.json();
        allTradesList = [...allTradesList, ...(data.orders || []).map(o => ({
          ...o,
          type: o.is_live ? 'live' : 'paper',
          status: o.status || o.state || 'active'
        }))];
      }
      
      // Remove duplicates based on ID
      const uniqueTrades = allTradesList.reduce((acc, trade) => {
        const key = trade.id || trade.order_id || `${trade.game_id}-${trade.timestamp}`;
        if (!acc.has(key)) {
          acc.set(key, trade);
        }
        return acc;
      }, new Map());
      
      allTradesList = Array.from(uniqueTrades.values());
      
      // Sort by timestamp (newest first)
      allTradesList.sort((a, b) => 
        new Date(b.timestamp || b.created_at) - new Date(a.timestamp || a.created_at)
      );
      
      // Separate paper and live trades
      const paper = allTradesList.filter(t => t.type === 'paper');
      const live = allTradesList.filter(t => t.type === 'live');
      
      setAllTrades(allTradesList);
      setPaperTrades(paper);
      setLiveTrades(live);
    } catch (err) {
      setTradesError(err.message);
    } finally {
      setTradesLoading(false);
    }
  }, [setAllTrades, setPaperTrades, setLiveTrades, setTradesLoading, setTradesError]);
  
  // Start polling
  useEffect(() => {
    if (autoFetch) {
      loadTrades();
      
      pollRef.current = setInterval(() => {
        loadTrades();
      }, pollInterval);
      
      return () => {
        if (pollRef.current) {
          clearInterval(pollRef.current);
        }
      };
    }
  }, [autoFetch, pollInterval, loadTrades]);
  
  // Get filtered trades
  const getFilteredTrades = useCallback(() => {
    let trades = [];
    
    switch (tradeType) {
      case 'paper':
        trades = paperTrades;
        break;
      case 'live':
        trades = liveTrades;
        break;
      default:
        trades = allTrades;
    }
    
    if (status) {
      const activeStatuses = ['active', 'pending', 'working', 'open'];
      const closedStatuses = ['closed', 'filled', 'cancelled', 'expired', 'settled'];
      
      if (status === 'active') {
        trades = trades.filter(t => activeStatuses.includes(t.status?.toLowerCase()));
      } else if (status === 'closed') {
        trades = trades.filter(t => closedStatuses.includes(t.status?.toLowerCase()));
      }
    }
    
    return trades;
  }, [tradeType, status, allTrades, paperTrades, liveTrades]);
  
  // Calculate P&L summary
  const getPnLSummary = useCallback(() => {
    const paper = paperTrades.reduce((sum, t) => sum + (t.pnl || t.realized_pnl || 0), 0);
    const live = liveTrades.reduce((sum, t) => sum + (t.pnl || t.realized_pnl || 0), 0);
    
    const openPaper = paperTrades.filter(t => 
      ['active', 'pending', 'working', 'open'].includes(t.status?.toLowerCase())
    ).length;
    
    const openLive = liveTrades.filter(t => 
      ['active', 'pending', 'working', 'open'].includes(t.status?.toLowerCase())
    ).length;
    
    return {
      totalPaperPnL: paper,
      totalLivePnL: live,
      totalPnL: paper + live,
      openPaperCount: openPaper,
      openLiveCount: openLive,
      totalTrades: allTrades.length
    };
  }, [allTrades, paperTrades, liveTrades]);
  
  return {
    trades: getFilteredTrades(),
    allTrades,
    paperTrades,
    liveTrades,
    loading: tradesLoading,
    error: tradesError,
    lastUpdate: lastTradesUpdate,
    pnlSummary: getPnLSummary(),
    refresh: loadTrades,
    addTrade,
    updateTradeStatus
  };
}
