/**
 * Trading Store - Global state management for trading
 * Centralized store for games, trades, and trading modes
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

// Trading Store
export const useTradingStore = create(
  persist(
    (set, get) => ({
      // Games state
      games: [],
      kalshiGames: [],
      activeGames: [],
      
      // Trades state
      allTrades: [],
      paperTrades: [],
      liveTrades: [],
      
      // Mode state
      evaluationMode: true,
      autoMode: false,
      
      // Loading states
      gamesLoading: false,
      tradesLoading: false,
      
      // Last update timestamps
      lastGamesUpdate: null,
      lastTradesUpdate: null,
      
      // Error states
      gamesError: null,
      tradesError: null,
      
      // Actions - Games
      setGames: (gamesOrUpdater) => set((state) => {
        const games = typeof gamesOrUpdater === 'function'
          ? gamesOrUpdater(Array.isArray(state.games) ? state.games : [])
          : gamesOrUpdater;
        return { games: Array.isArray(games) ? games : [], lastGamesUpdate: new Date() };
      }),
      setKalshiGames: (kalshiGames) => set({ kalshiGames }),
      setActiveGames: (activeGames) => set({ activeGames }),
      setGamesLoading: (loading) => set({ gamesLoading: loading }),
      setGamesError: (error) => set({ gamesError: error }),
      
      // Actions - Trades
      setAllTrades: (allTrades) => set({ allTrades, lastTradesUpdate: new Date() }),
      setPaperTrades: (paperTrades) => set({ paperTrades }),
      setLiveTrades: (liveTrades) => set({ liveTrades }),
      setTradesLoading: (loading) => set({ tradesLoading: loading }),
      setTradesError: (error) => set({ tradesError: error }),
      
      // Add a trade instantly (optimistic update)
      addTrade: (trade) => set((state) => {
        const trades = [trade, ...state.allTrades];
        const paperTrades = trade.type === 'paper' 
          ? [trade, ...state.paperTrades] 
          : state.paperTrades;
        const liveTrades = trade.type === 'live' 
          ? [trade, ...state.liveTrades] 
          : state.liveTrades;
        return { allTrades: trades, paperTrades, liveTrades };
      }),
      
      // Update trade status
      updateTradeStatus: (tradeId, status, pnl = null) => set((state) => {
        const updateTrade = (trades) => trades.map(t => 
          t.id === tradeId ? { ...t, status, pnl: pnl ?? t.pnl } : t
        );
        return {
          allTrades: updateTrade(state.allTrades),
          paperTrades: updateTrade(state.paperTrades),
          liveTrades: updateTrade(state.liveTrades)
        };
      }),
      
      // Actions - Modes
      setEvaluationMode: (enabled) => set({ evaluationMode: enabled }),
      setAutoMode: (enabled) => set({ autoMode: enabled }),
      
      // Fetch games from API
      fetchGames: async (statusFilter = null) => {
        const { setGames, setGamesLoading, setGamesError, setActiveGames } = get();
        setGamesLoading(true);
        setGamesError(null);
        
        try {
          const params = statusFilter ? `?status=${statusFilter}` : '';
          const res = await fetch(`${API_BASE}/api/games${params}`);
          if (res.ok) {
            const data = await res.json();
            setGames(data.games || []);
            
            // Filter active/open games
            const active = (data.games || []).filter(g => 
              ['live', 'active', 'open', 'scheduled'].includes(g.game?.status?.toLowerCase())
            );
            setActiveGames(active);
          } else {
            throw new Error('Failed to fetch games');
          }
        } catch (err) {
          setGamesError(err.message);
        } finally {
          setGamesLoading(false);
        }
      },
      
      // Fetch Kalshi basketball games
      fetchKalshiGames: async (sport = 'basketball', status = null) => {
        const { setKalshiGames, setGamesLoading, setGamesError } = get();
        setGamesLoading(true);
        setGamesError(null);
        
        try {
          const params = new URLSearchParams();
          if (status) params.append('status', status);
          params.append('limit', '100');
          
          const res = await fetch(`${API_BASE}/api/kalshi/markets?${params}`);
          if (res.ok) {
            const data = await res.json();
            setKalshiGames(data.markets || []);
          } else {
            throw new Error('Failed to fetch Kalshi games');
          }
        } catch (err) {
          setGamesError(err.message);
        } finally {
          setGamesLoading(false);
        }
      },
      
      // Fetch all trades
      fetchTrades: async (limit = 100) => {
        const { setAllTrades, setPaperTrades, setLiveTrades, setTradesLoading, setTradesError } = get();
        setTradesLoading(true);
        setTradesError(null);
        
        try {
          // Fetch from multiple endpoints
          const [tradesRes, ordersRes] = await Promise.all([
            fetch(`${API_BASE}/api/trades?limit=${limit}`),
            fetch(`${API_BASE}/api/orders?limit=${limit}`)
          ]);
          
          let allTrades = [];
          
          if (tradesRes.ok) {
            const data = await tradesRes.json();
            console.log('Raw trades response:', data);
            // Handle both array and object responses
            const trades = Array.isArray(data) ? data : (data.trades || []);
            allTrades = [...allTrades, ...trades.map(t => ({
              ...t,
              type: t.is_live ? 'live' : 'paper'
            }))];
          }
          
          if (ordersRes.ok) {
            const data = await ordersRes.json();
            console.log('Raw orders response:', data);
            // Handle both array and object responses
            const orders = Array.isArray(data) ? data : (data.orders || []);
            allTrades = [...allTrades, ...orders.map(o => ({
              ...o,
              type: o.is_live ? 'live' : 'paper'
            }))];
          }
          
          // Sort by timestamp
          allTrades.sort((a, b) => new Date(b.timestamp || b.created_at) - new Date(a.timestamp || a.created_at));
          
          // Separate paper and live trades
          const paper = allTrades.filter(t => t.type === 'paper');
          const live = allTrades.filter(t => t.type === 'live');
          
          console.log('Trades set in store:', {
            total: allTrades.length,
            paper: paper.length,
            live: live.length
          });
          
          setAllTrades(allTrades);
          setPaperTrades(paper);
          setLiveTrades(live);
        } catch (err) {
          console.error('Error fetching trades:', err);
          setTradesError(err.message);
        } finally {
          setTradesLoading(false);
        }
      },
      
      // Clear all state
      clearAll: () => set({
        games: [],
        kalshiGames: [],
        activeGames: [],
        allTrades: [],
        paperTrades: [],
        liveTrades: [],
        gamesError: null,
        tradesError: null
      })
    }),
    {
      name: 'predictpod-trading-store',
      partialize: (state) => ({
        evaluationMode: state.evaluationMode,
        autoMode: state.autoMode
      })
    }
  )
);

// Selectors
export const useGames = () => useTradingStore(state => state.games);
export const useActiveGames = () => useTradingStore(state => state.activeGames);
export const useKalshiGames = () => useTradingStore(state => state.kalshiGames);
export const useAllTrades = () => useTradingStore(state => state.allTrades);
export const usePaperTrades = () => useTradingStore(state => state.paperTrades);
export const useLiveTrades = () => useTradingStore(state => state.liveTrades);
export const useEvaluationMode = () => useTradingStore(state => state.evaluationMode);
export const useAutoMode = () => useTradingStore(state => state.autoMode);

export default useTradingStore;
