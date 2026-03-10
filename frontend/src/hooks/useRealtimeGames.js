/**
 * useRealtimeGames Hook
 * Centralized polling/websocket logic for real-time game updates
 */

import { useEffect, useCallback, useRef } from "react";
import { useTradingStore } from "../stores/tradingStore";
import useWebSocket from "./useWebSocket";

const POLL_INTERVAL = 5000; // 5 seconds

// ✅ FIX: Route through your FastAPI backend to avoid CORS + 403 from Kalshi
// Your backend proxies the request server-side with proper auth headers.
const API_BASE_URL =
  import.meta.env?.VITE_API_URL ||        // Vite env var (preferred)
  process.env?.REACT_APP_API_URL ||        // CRA env var
  "https://alpha.predictpod.co";           // production fallback

export default function useRealtimeGames(options = {}) {
  const {
    autoFetch = true,
    pollInterval = POLL_INTERVAL,
    statusFilter = null,
    includeKalshi = false,
  } = options;

  const {
    games,
    activeGames,
    kalshiGames,
    gamesLoading,
    gamesError,
    lastGamesUpdate,
    setGames,
    setActiveGames,
    setKalshiGames,
    setGamesLoading,
    setGamesError,
  } = useTradingStore();

  const pollRef = useRef(null);

  /**
   * WebSocket handler (optional realtime updates)
   */
  const handleWsMessage = useCallback(
    (data) => {
      if (data.type === "bulk_update" && data.updates) {
        setGames((prevGames) => {
          const updatedGames = [...prevGames];

          data.updates.forEach((update) => {
            const idx = updatedGames.findIndex(
              (g) => g.game?.id === update.game?.id,
            );

            if (idx >= 0) {
              updatedGames[idx] = update;
            } else {
              updatedGames.push(update);
            }
          });

          return updatedGames;
        });

        const active = games.filter((g) =>
          ["live", "active", "open", "scheduled"].includes(
            g.game?.status?.toLowerCase(),
          ),
        );

        setActiveGames(active);
      }
    },
    [games, setGames, setActiveGames],
  );

  const { isConnected } = useWebSocket(handleWsMessage);

  /**
   * Fetch games via your FastAPI proxy (avoids CORS + handles Kalshi auth server-side)
   */
  const loadGames = useCallback(async () => {
    setGamesLoading(true);
    setGamesError(null);

    try {
      // ✅ FIX: Call YOUR backend proxy, not Kalshi directly.
      // The FastAPI /api/kalshi/series endpoint handles auth + CORS server-side.
      const params = new URLSearchParams({
        order_by: "trending",
        status: statusFilter || "open,unopened",
        category: "Sports",
        tag: "Basketball",
        scope: "Games",
        page_size: "100",
      });

      const res = await fetch(
        `${API_BASE_URL}/api/kalshi/series?${params.toString()}`,
      );

      if (!res.ok) {
        const errText = await res.text().catch(() => res.statusText);
        throw new Error(`Failed to fetch games (${res.status}): ${errText}`);
      }

      const data = await res.json();

      // ✅ FIX: Kalshi v2 API returns `series` not `current_page`
      // Support both shapes for safety
      const rows = data.series || data.current_page || [];

      if (rows.length === 0) {
        console.warn("[useRealtimeGames] No rows returned from API. Full response:", data);
      }

      // Map Kalshi series -> your existing store shape
      const gamesList = rows.map((s) => {
        const m0 = s.markets?.[0] || {};
        const m1 = s.markets?.[1] || {};

        // Teams from Kalshi JSON
        const away = m0.name || m0.yes_sub_title || m0.yes_subtitle || "";
        const home = m1.name || m1.yes_sub_title || m1.yes_subtitle || "";

        // Choose primary market for pricing
        const primary = m0?.yes_bid != null ? m0 : m1 || m0;

        // cents (0-100)
        const yesBid = primary.yes_bid ?? null;
        const yesAsk = primary.yes_ask ?? null;
        const last   = primary.last_price ?? null;

        // MARKET cents: live mid(bid+ask) > bid > ask > last_price > 50
        // ✅ FIX: Prefer live bid/ask mid over last_price.
        // last_price is the most recent TRADED price and can be hours old for
        // low-volume markets. Entering at a stale last_price means the very first
        // live poll shows a different price → trade opens with an instant P&L offset.
        // bid/ask always reflects the live order book.
        const marketCents =
          yesBid != null && yesAsk != null
            ? Math.round((yesBid + yesAsk) / 2)  // live mid — always preferred
            : yesBid != null
              ? yesBid
              : yesAsk != null
                ? yesAsk
                : last != null
                  ? last                          // stale last_price — last resort only
                  : 50;

        const marketDec = marketCents / 100;

        // ✅ FIX: Use real model probability from backend as fair value.
        // Previously fairCents was hardcoded to 50, making edge = market - 50.
        // That is NOT a tradeable edge — it just means "the market is not 50-50".
        // The backend probability_engine.py calculates real win probabilities;
        // the /api/kalshi/series endpoint should include fair_prob per market.
        // We check s.fair_prob (series level) and m0/m1.fair_prob (market level).
        // If the backend does not yet supply it, we fall back to marketDec (edge=0),
        // which correctly prevents trading until a real signal exists.
        const serverFairDec =
          (s.fair_prob  != null ? s.fair_prob  :
           m0.fair_prob != null ? m0.fair_prob :
           m1.fair_prob != null ? m1.fair_prob : null);

        const fairDec    = serverFairDec ?? marketDec;   // fallback → edge = 0, no phantom signal
        const fairCents  = Math.round(fairDec * 100);
        const edgeDec    = marketDec - fairDec;           // real edge: model says X, market says Y
        const edgeCents  = edgeDec * 100;

        const status = s.is_closing ? "closed" : "open";

        return {
          // ---------- TOP LEVEL ALIASES (strings) ----------
          away_team: away,
          home_team: home,
          awayTeam: away,
          homeTeam: home,
          team1: away,
          team2: home,

          // ---------- TOP LEVEL ALIASES (objects) ----------
          away_team_obj: { name: away },
          home_team_obj: { name: home },
          awayObj: { name: away },
          homeObj: { name: home },
          away: { name: away },
          home: { name: home },

          // ---------- PRICING (cents + decimals) ----------
          market_price: marketCents,
          fair_price:   fairCents,
          edge:         edgeCents,

          market:       marketDec,
          fair:         fairDec,
          edge_decimal: edgeDec,

          market_prob:  marketDec,
          fair_prob:    fairDec,
          edge_prob:    edgeDec,

          yes_bid:  yesBid,
          yes_ask:  yesAsk,
          last_price: last,

          // ---------- SIGNAL ----------
          signal: {
            signal_type:
              edgeDec >  0.05 ? "STRONG_BUY"  :
              edgeDec >  0.03 ? "BUY"          :
              edgeDec < -0.05 ? "STRONG_SELL"  :
              edgeDec < -0.03 ? "SELL"         : "HOLD",
            // ✅ FIX: signal_score scaled to [0,100] over a ±20% edge range.
            // Old formula (abs(edge)*1000) gave score=100 for any edge > 0.1,
            // making EVERY game with a price away from 50¢ score 100/100.
            // New formula: 0% edge → score 0, 5% edge → score 25, 10% → 50, 20%+ → 100.
            signal_score: Math.min(100, Math.abs(edgeDec) * 500),
            is_actionable: Math.abs(edgeDec) >= 0.03,
            risk_tier:
              Math.abs(edgeDec) > 0.07 ? "low" :
              Math.abs(edgeDec) > 0.04 ? "medium" : "high",
            edge: edgeDec,
          },

          // ---------- INTELLIGENCE ----------
          intelligence: {
            momentum:
              (primary.price_delta ?? 0) > 0 ? "up" :
              (primary.price_delta ?? 0) < 0 ? "down" : "neutral",
            volume:               s.total_volume ?? primary.volume ?? 0,
            dollar_volume:        primary.dollar_volume ?? 0,
            recent_volume:        primary.recent_volume ?? 0,
            dollar_recent_volume: primary.dollar_recent_volume ?? 0,
            volatility:           Math.abs(primary.price_delta ?? 0),
          },

          score:    0,
          risk:     "N/A",
          ticker:   s.event_ticker || s.series_ticker,
          league:   s.league || s.product_metadata?.competition || "Basketball",
          volume:   s.total_volume ?? primary.volume ?? 0,
          is_clutch: false,

          // Game start ≈ expected_expiration_date - 3h for NBA
          game_date: (() => {
            const exp = m0.expected_expiration_date || m1.expected_expiration_date || null;
            if (!exp) return null;
            const isNBA   = /NBA/i.test(s.series_ticker || "");
            const offset  = isNBA ? 3 * 60 * 60 * 1000 : 0;
            return new Date(new Date(exp).getTime() - offset).toISOString();
          })(),

          raw:     s,
          markets: s.markets || [],

          // ---------- NESTED GAME OBJECT ----------
          game: {
            id:     s.event_ticker || s.series_ticker,
            ticker: s.event_ticker || s.series_ticker,
            // ✅ Store both so Dashboard lookups never miss a match
            event_ticker:  s.event_ticker  || null,
            series_ticker: s.series_ticker || null,
            series_id:     s.series_ticker || null,
            status,

            away_team: away,
            home_team: home,
            awayTeam:  away,
            homeTeam:  home,

            away:  { name: away },
            home:  { name: home },
            teams: { away: { name: away }, home: { name: home } },

            matchup: `${away} @ ${home}`,
            title:
              s.event_title ||
              s.product_metadata?.["1v1_title"] ||
              `${away} @ ${home}`,

            subtitle: s.sub_title || s.event_subtitle || "",
            league:   s.league || s.product_metadata?.competition || "Basketball",
          },
        };
      });

      setGames(gamesList);
      console.log(`[useRealtimeGames] ✅ Loaded ${gamesList.length} games`);
      if (gamesList.length > 0) {
        console.log("[useRealtimeGames] Sample game:", gamesList[0]);
      }

      const active = gamesList.filter((g) =>
        ["open", "active", "live", "scheduled", "unopened"].includes(
          g.game?.status,
        ),
      );

      setActiveGames(active);
    } catch (err) {
      console.error("[useRealtimeGames] Fetch error:", err);
      setGamesError(err.message);
    } finally {
      setGamesLoading(false);
    }
  }, [statusFilter, setGames, setActiveGames, setGamesLoading, setGamesError]);

  /**
   * Polling
   */
  useEffect(() => {
    if (!autoFetch) return;

    loadGames();

    pollRef.current = setInterval(() => {
      loadGames();
    }, pollInterval);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
      }
    };
  }, [autoFetch, pollInterval, loadGames]);

  /**
   * Manual refresh
   */
  const refresh = useCallback(() => {
    loadGames();
  }, [loadGames]);

  return {
    games,
    activeGames,
    kalshiGames,
    loading: gamesLoading,
    error: gamesError,
    lastUpdate: lastGamesUpdate,
    isConnected,
    refresh,
  };
}
