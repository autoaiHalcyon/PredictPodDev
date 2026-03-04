/**
 * PredictPod API Service
 * Handles all API calls to the backend
 */

import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Axios instance with default config
const api = axios.create({
  baseURL: API,
  timeout: 10000,
});

// ============================================
// GAMES
// ============================================

export const getGames = async (status = null) => {
  const params = status ? { status } : {};
  const response = await api.get('/games', { params });
  return response.data;
};

export const getGame = async (gameId) => {
  const response = await api.get(`/games/${gameId}`);
  return response.data;
};

// ============================================
// MARKETS
// ============================================

export const getMarket = async (marketId) => {
  const response = await api.get(`/markets/${marketId}`);
  return response.data;
};

// ============================================
// TRADING
// ============================================

export const placeTrade = async (gameId, marketId, side, direction, quantity, price = null) => {
  const response = await api.post('/trades', null, {
    params: { game_id: gameId, market_id: marketId, side, direction, quantity, price }
  });
  return response.data;
};

export const executeSignal = async (marketId, gameId) => {
  const response = await api.post('/trades/execute-signal', null, {
    params: { market_id: marketId, game_id: gameId }
  });
  return response.data;
};

export const flattenAll = async () => {
  const response = await api.post('/trades/flatten-all');
  return response.data;
};

export const getTrades = async (limit = 50, gameId = null) => {
  const params = { limit };
  if (gameId) params.game_id = gameId;
  const response = await api.get('/trades', { params });
  return response.data;
};

// ============================================
// PORTFOLIO
// ============================================

export const getPortfolio = async () => {
  const response = await api.get('/portfolio');
  return response.data;
};

export const getPositions = async () => {
  const response = await api.get('/portfolio/positions');
  return response.data;
};

export const getPerformance = async (days = 30) => {
  const response = await api.get('/portfolio/performance', { params: { days } });
  return response.data;
};

// ============================================
// RISK
// ============================================

export const getRiskStatus = async () => {
  const response = await api.get('/risk/status');
  return response.data;
};

export const getRiskLimits = async () => {
  const response = await api.get('/risk/limits');
  return response.data;
};

export const updateRiskLimits = async (limits) => {
  const response = await api.put('/risk/limits', null, { params: limits });
  return response.data;
};

// ============================================
// SETTINGS
// ============================================

export const getSettings = async () => {
  const response = await api.get('/settings');
  return response.data;
};

export const healthCheck = async () => {
  const response = await api.get('/health');
  return response.data;
};

// ============================================
// KALSHI API CREDENTIALS
// ============================================

export const saveKalshiKeys = async (apiKey, privateKey) => {
  const response = await api.post('/settings/kalshi_keys', null, {
    params: { api_key: apiKey, private_key: privateKey }
  });
  return response.data;
};

export const getKalshiKeys = async () => {
  const response = await api.get('/settings/kalshi_keys');
  return response.data;
};

export const deleteKalshiKeys = async () => {
  const response = await api.delete('/settings/kalshi_keys');
  return response.data;
};

export const validateKalshiKeys = async () => {
  const response = await api.post('/settings/kalshi_keys/validate');
  return response.data;
};

// ============================================
// LIVE TRADING CONTROL
// ============================================

export const enableLiveTrading = async (confirmedRisk) => {
  const response = await api.post('/settings/live_trading/enable', null, {
    params: { confirmed_risk: confirmedRisk }
  });
  return response.data;
};

export const disableLiveTrading = async () => {
  const response = await api.post('/settings/live_trading/disable');
  return response.data;
};

// ============================================
// KILL SWITCH
// ============================================

export const activateKillSwitch = async () => {
  const response = await api.post('/admin/kill_switch');
  return response.data;
};

export const deactivateKillSwitch = async () => {
  const response = await api.delete('/admin/kill_switch');
  return response.data;
};

// ============================================
// GUARDRAILS
// ============================================

export const getGuardrails = async () => {
  const response = await api.get('/settings/guardrails');
  return response.data;
};

export const updateGuardrails = async (guardrails) => {
  const response = await api.put('/settings/guardrails', null, { params: guardrails });
  return response.data;
};

// ============================================
// SANDBOX / ORDER LIFECYCLE
// ============================================

export const getSandboxStatus = async () => {
  const response = await api.get('/sandbox/status');
  return response.data;
};

export const getCapitalDeployment = async () => {
  const response = await api.get('/settings/capital_deployment');
  return response.data;
};

export const setCapitalDeployment = async (mode, confirmed = false, acknowledged = false) => {
  const response = await api.post('/settings/capital_deployment', null, {
    params: { mode, confirmed, acknowledged }
  });
  return response.data;
};

export const previewOrder = async (marketId, side, action, quantity, priceCents) => {
  const response = await api.post('/orders/preview', null, {
    params: {
      market_id: marketId,
      side,
      action,
      quantity,
      price_cents: priceCents
    }
  });
  return response.data;
};

export const submitOrder = async (params) => {
  const response = await api.post('/orders/submit', null, { params });
  return response.data;
};

export const getOrders = async (limit = 50, workingOnly = false) => {
  const response = await api.get('/orders', {
    params: { limit, working_only: workingOnly }
  });
  return response.data;
};

export const getOrder = async (orderId) => {
  const response = await api.get(`/orders/${orderId}`);
  return response.data;
};

export const cancelOrder = async (orderId) => {
  const response = await api.delete(`/orders/${orderId}`);
  return response.data;
};

export const getReconciliationStatus = async () => {
  const response = await api.get('/reconciliation/status');
  return response.data;
};

export const forceReconciliation = async () => {
  const response = await api.post('/reconciliation/force');
  return response.data;
};

// ============================================
// UTILITIES
// ============================================

export const formatOdds = (probability) => {
  if (probability >= 0.5) {
    const american = Math.round(-100 / (1 - probability) * (1 - probability));
    return american >= 0 ? `+${american}` : american;
  } else {
    const american = Math.round(100 / probability - 100);
    return `+${american}`;
  }
};

export const formatPercent = (value, decimals = 1) => {
  return `${(value * 100).toFixed(decimals)}%`;
};

export const formatCurrency = (value) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value);
};

export const formatTime = (seconds) => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};
