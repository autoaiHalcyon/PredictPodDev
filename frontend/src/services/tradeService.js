/**
 * tradeService.js
 * ─────────────────────────────────────────────────────────────────────────────
 * All database interactions for paper + live trades.
 * Talks to your REST API; maps component trade objects ↔ DB schema.
 *
 * DB Schema (Trades collection):
 *   id, game_id, market_id, side, direction, quantity, price,
 *   order_type, limit_price, status, filled_quantity, avg_fill_price,
 *   fees, is_paper, created_at, executed_at, signal_type, edge_at_entry
 *
 * Extended fields stored via API (not in original schema but added):
 *   market_name, game_title, league, strategy, type, current_price,
 *   exit_price, closed_at, pnl
 */

// ── Config ────────────────────────────────────────────────────────────────────
const API_BASE = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000/api';

// ── HTTP helpers ──────────────────────────────────────────────────────────────
async function http(method, path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body != null ? JSON.stringify(body) : undefined,
  });

  // 204 No Content
  if (res.status === 204) return null;

  if (!res.ok) {
    let errorDetail = '';
    try {
      const cloned = res.clone();
      const text = await cloned.text();
      try {
        const json = JSON.parse(text);
        errorDetail = json.detail || JSON.stringify(json);
      } catch {
        errorDetail = text || res.statusText;
      }
    } catch {
      errorDetail = res.statusText;
    }
    console.error(`[API ERROR] ${method} ${path} → ${res.status}`, errorDetail);
    throw new Error(`API ${method} ${path} → ${res.status}: ${errorDetail}`);
  }

  return res.json();
}

const api = {
  get:    (path)          => http('GET',    path),
  post:   (path, body)    => http('POST',   path, body),
  patch:  (path, body)    => http('PATCH',  path, body),
  delete: (path)          => http('DELETE', path),
};

// ── ID generator (fallback if crypto.randomUUID unavailable) ─────────────────
function generateId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older browsers
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

// ── Schema mapping: component → DB ───────────────────────────────────────────
/**
 * Convert a component-side trade object into the DB document shape.
 * Entry price is stored as `price` + `avg_fill_price` in the DB.
 */
export function toDbDoc(trade) {
  return {
    // Core identity
    // ✅ FIX: FastAPI requires `id` and `market_id` as non-null fields.
    // Always generate an id if missing, and fall back to game_id for market_id.
    id:              trade.id || generateId(),
    game_id:         trade.game_id,
    market_id:       trade.market_id || trade.market_name || trade.game_id || '',

    // Order params
    side:            trade.side,                          // 'yes' | 'no'
    direction:       trade.direction,                     // 'buy' | 'sell'
    quantity:        trade.quantity,
    price:           trade.entry_price,                   // entry / limit price
    order_type:      trade.order_type || 'market',
    limit_price:     trade.limit_price || null,

    // Fill details
    status:          mapStatus(trade.status),
    filled_quantity: trade.quantity,
    avg_fill_price:  trade.entry_price,
    fees:            calcFees(trade.quantity, trade.entry_price),

    // Flags
    is_paper:        trade.type !== 'live',

    // Timestamps
    created_at:      trade.timestamp || new Date().toISOString(),
    executed_at:     trade.timestamp || new Date().toISOString(),

    // Signal metadata
    signal_type:     trade.signal_type  || null,
    edge_at_entry:   trade.edge         || null,

    // ── Extended fields ──
    type:            trade.type        || 'manual',
    strategy:        trade.strategy    || null,
    market_name:     trade.market_name || null,
    game_title:      trade.game_title  || null,
    league:          trade.league      || null,
    current_price:   trade.current_price ?? trade.entry_price,
    exit_price:      trade.exit_price  || null,
    closed_at:       trade.closed_at   || null,
    pnl:             trade.pnl         || 0,
  };
}

/**
 * Convert a DB document back to the component-side trade shape.
 */
export function fromDbDoc(doc) {
  const entryPrice   = doc.avg_fill_price ?? doc.price ?? 0;
  const currentPrice = doc.current_price  ?? entryPrice;
  const exitPrice    = doc.exit_price     ?? null;
  const curOrExit    = doc.status === 'closed' ? (exitPrice ?? currentPrice) : currentPrice;
  const pnl          = doc.status === 'open'
    ? computePnl(doc.side, entryPrice, currentPrice, doc.quantity)
    : (doc.pnl != null ? doc.pnl : computePnl(doc.side, entryPrice, curOrExit, doc.quantity));

  return {
    id:            doc.id,
    game_id:       doc.game_id,
    market_id:     doc.market_id,
    market_name:   doc.market_name || doc.market_id,
    game_title:    doc.game_title  || doc.game_id,
    league:        doc.league      || '',
    side:          doc.side,
    direction:     doc.direction,
    quantity:      doc.quantity,
    entry_price:   entryPrice,
    current_price: currentPrice,
    exit_price:    exitPrice,
    exit_reason:   doc.exit_reason || null,
    status:        normaliseStatus(doc.status),
    type:          doc.type        || (doc.is_paper ? 'manual' : 'live'),
    strategy:      doc.strategy    || null,
    signal_type:   doc.signal_type || null,
    edge:          doc.edge_at_entry || null,
    timestamp:     doc.created_at,
    closed_at:     doc.closed_at   || null,
    pnl,
    fees:          doc.fees        || 0,
  };
}

// ── Status normalisation ──────────────────────────────────────────────────────
function mapStatus(s) {
  const map = { open: 'filled', closed: 'closed', expired: 'expired' };
  return map[s] || s || 'filled';
}

function normaliseStatus(s) {
  // DB uses 'filled' for an open position; UI uses 'open'
  if (s === 'filled') return 'open';
  return s || 'open';
}

// ── P&L helpers ───────────────────────────────────────────────────────────────
export function computePnl(side, entryPrice, currentPrice, quantity) {
  const eff = (p) => side === 'yes' ? p : 1 - p;
  return Math.round((eff(currentPrice) - eff(entryPrice)) * quantity * 100) / 100;
}

function calcFees(quantity, price) {
  // Kalshi-style: $0.01 per contract, capped at 7% of max profit
  const fee = quantity * 0.01;
  const cap  = quantity * Math.min(price, 1 - price) * 0.07;
  return Math.round(Math.min(fee, cap) * 100) / 100;
}

// ═════════════════════════════════════════════════════════════════════════════
// PUBLIC API
// ═════════════════════════════════════════════════════════════════════════════

/**
 * Place a new paper trade.
 * Returns the saved trade in component shape.
 */
export async function placeTrade(trade) {
  const dbDoc = toDbDoc(trade);
  console.log('[placeTrade] Component payload:', trade);
  console.log('[placeTrade] DB payload (transformed):', dbDoc);
  const doc = await api.post('/api/trades', dbDoc);
  return fromDbDoc(doc);
}

/**
 * Fetch all trades, optionally filtered by game_id.
 */
export async function fetchTrades({ gameId, status, type } = {}) {
  const params = new URLSearchParams();
  if (gameId) params.set('game_id', gameId);
  if (status) params.set('status',  status);
  if (type)   params.set('type',    type);
  const qs   = params.toString();
  const docs = await api.get(`/api/trades${qs ? `?${qs}` : ''}`);
  return (docs || []).map(fromDbDoc);
}

/**
 * Refresh current_price + recompute pnl for all open trades of a game.
 * Called on every poll tick in GameDetail.
 */
export async function refreshPrices(gameId, currentPrice) {
  // Optimistic: update locally displayed values immediately, then persist.
  await api.patch('/api/trades/refresh-prices', { game_id: gameId, current_price: currentPrice });
}

/**
 * Close a trade at the given exit price (market or limit).
 */
export async function closeTrade(tradeId, exitPrice, exitReason = null) {
  const doc = await api.patch(`/api/trades/${tradeId}/close`, {
    exit_price: exitPrice,
    closed_at:  new Date().toISOString(),
    status:     'closed',
    exit_reason: exitReason,
  });
  return fromDbDoc(doc);
}

/**
 * Delete a trade permanently.
 */
export async function deleteTrade(tradeId) {
  await api.delete(`/api/trades/${tradeId}`);
}

/**
 * Compute portfolio-level stats from a trades array (component shape).
 */
export function calcPortfolioStats(trades) {
  const open   = trades.filter(t => t.status === 'open');
  const closed  = trades.filter(t => t.status === 'closed');
  const wins    = closed.filter(t => t.pnl  > 0);
  const losses  = closed.filter(t => t.pnl  < 0);
  const sum     = (arr) => arr.reduce((a, t) => a + (t.pnl || 0), 0);
  const avg     = (arr) => arr.length ? sum(arr) / arr.length : 0;

  return {
    totalPnl:      +sum(trades).toFixed(2),
    realisedPnl:   +sum(closed).toFixed(2),
    unrealisedPnl: +sum(open).toFixed(2),
    winCount:      wins.length,
    lossCount:     losses.length,
    winRate:       closed.length ? Math.round((wins.length / closed.length) * 100) : 0,
    avgWin:        +avg(wins).toFixed(2),
    avgLoss:       +avg(losses).toFixed(2),
    bestTrade:     closed.length ? +Math.max(...closed.map(t => t.pnl)).toFixed(2) : 0,
    worstTrade:    closed.length ? +Math.min(...closed.map(t => t.pnl)).toFixed(2) : 0,
    openCount:     open.length,
    closedCount:   closed.length,
    totalTrades:   trades.length,
    totalVolume:   trades.reduce((a, t) => a + (t.quantity || 0), 0),
  };
}