/**
 * useAutoTrader Hook
 * Handles live trade execution (when autoMode is ON)
 * Runs independently from paper trader
 */
import { useEffect, useCallback, useRef } from 'react';
import { useTradingStore } from '../stores/tradingStore';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';
const MAX_RETRIES = 2;

export default function useAutoTrader(options = {}) {
  const { 
    enabled = true,
    onTradeAttempt = () => {},
    onTradeSuccess = () => {},
    onTradeFailed = () => {}
  } = options;
  
  const {
    autoMode,
    addTrade
  } = useTradingStore();
  
  const pendingTradesRef = useRef(new Set());
  
  // Execute a live trade with retries
  const executeLiveTrade = useCallback(async (tradeParams) => {
    const { game_id, market_id, side, quantity, price } = tradeParams;
    
    // Generate unique trade key to prevent duplicates
    const tradeKey = `${game_id}-${market_id}-${side}-${Date.now()}`;
    
    // Check if same trade is already pending
    if (pendingTradesRef.current.has(tradeKey)) {
      console.log(`[AUTO_TRADER] Duplicate trade blocked: ${tradeKey}`);
      return { success: false, reason: 'duplicate' };
    }
    
    // Verify auto mode before each trade
    const currentStore = useTradingStore.getState();
    if (!currentStore.autoMode) {
      console.log('[AUTO_TRADER] Trade blocked - Auto Mode OFF');
      return { success: false, reason: 'auto_mode_off' };
    }
    
    pendingTradesRef.current.add(tradeKey);
    console.log(`[AUTO_TRADER] live_trade_attempt: ${JSON.stringify(tradeParams)}`);
    onTradeAttempt(tradeParams);
    
    let lastError = null;
    
    for (let attempt = 1; attempt <= MAX_RETRIES + 1; attempt++) {
      try {
        const response = await fetch(`${API_BASE}/api/trades`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...tradeParams,
            is_paper: false,
            is_live: true
          })
        });
        
        if (response.ok) {
          const data = await response.json();
          console.log(`[AUTO_TRADER] live_trade_success: ${JSON.stringify(data)}`);
          
          // Add trade optimistically to store
          addTrade({
            id: data.trade_id || data.order_id || tradeKey,
            game_id,
            market_id,
            side,
            quantity,
            price,
            type: 'live',
            status: 'active',
            timestamp: new Date().toISOString(),
            pnl: 0
          });
          
          onTradeSuccess(data);
          pendingTradesRef.current.delete(tradeKey);
          return { success: true, data };
        } else {
          const errorData = await response.json().catch(() => ({}));
          lastError = errorData.detail || response.statusText;
          console.log(`[AUTO_TRADER] Attempt ${attempt} failed: ${lastError}`);
        }
      } catch (error) {
        lastError = error.message;
        console.log(`[AUTO_TRADER] Attempt ${attempt} error: ${error.message}`);
      }
      
      // Wait before retry
      if (attempt < MAX_RETRIES + 1) {
        await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
      }
    }
    
    // All retries failed
    console.log(`[AUTO_TRADER] live_trade_failed: ${lastError}`);
    onTradeFailed({ ...tradeParams, error: lastError });
    pendingTradesRef.current.delete(tradeKey);
    
    return { success: false, error: lastError };
  }, [addTrade, onTradeAttempt, onTradeSuccess, onTradeFailed]);
  
  // Check if live trading is available
  const isAvailable = autoMode && enabled;
  
  return {
    executeLiveTrade,
    isAvailable,
    autoMode
  };
}
