/**
 * useRealtimeGames Hook
 * Centralized polling/websocket logic for real-time game updates
 */

import { useEffect, useCallback, useRef } from "react";
import { useTradingStore } from "../stores/tradingStore";
import useWebSocket from "./useWebSocket";

const POLL_INTERVAL = 5000; // 5 seconds

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
   * Fetch games from Kalshi Series API
   */
  const loadGames = useCallback(async () => {
    setGamesLoading(true);
    setGamesError(null);

    try {
      const params = new URLSearchParams({
        order_by: "trending",
        status: statusFilter || "open,unopened",
        category: "Sports",
        tag: "Basketball",
        scope: "Games",
        hydrate: "milestones,structured_targets",
        page_size: "100",
        include_sports_derivatives: "false",
        with_milestones: "true",
      });

      const res = await fetch(
        `https://api.elections.kalshi.com/v1/search/series?${params.toString()}`,
      );

      if (!res.ok) {
        throw new Error("Failed to fetch Kalshi series");
      }

      const data = await res.json();
      const rows = data.current_page || [];

      // Map Kalshi series -> your existing store shape
      const gamesList = rows.map((s) => {
        const m0 = s.markets?.[0] || {};
        const m1 = s.markets?.[1] || {};

        // Teams from Kalshi JSON
        // JSON field is `name` (cleanest) with `yes_sub_title` fallback
        const away = m0.name || m0.yes_sub_title || m0.yes_subtitle || "";
        const home = m1.name || m1.yes_sub_title || m1.yes_subtitle || "";

        // Choose a primary market to display pricing (use first market by default)
        const primary = m0?.yes_bid != null ? m0 : m1 || m0;

        // cents (0-100)
        const yesBid = primary.yes_bid ?? null;
        const yesAsk = primary.yes_ask ?? null;
        const last = primary.last_price ?? null;

        // MARKET cents: last_price > mid > bid > ask > 50
        const marketCents =
          last != null
            ? last
            : yesBid != null && yesAsk != null
              ? Math.round((yesBid + yesAsk) / 2)
              : yesBid != null
                ? yesBid
                : yesAsk != null
                  ? yesAsk
                  : 50;

        // FAIR cents (until you have a model)
        const fairCents = 50;

        const edgeCents = marketCents - fairCents;

        const status = s.is_closing ? "closed" : "open";

        // Convert to decimals too (0-1) because some UIs use that
        const marketDec = marketCents / 100;
        const fairDec = fairCents / 100;
        const edgeDec = marketDec - fairDec;

      return {
  // ---------- TOP LEVEL ALIASES (strings) ----------
  away_team: away,
  home_team: home,
  awayTeam: away,
  homeTeam: home,
  away: away,
  home: home,
  team1: away,
  team2: home,

  // ---------- TOP LEVEL ALIASES (objects) ----------
  away_team_obj: { name: away },
  home_team_obj: { name: home },

  awayObj: { name: away },
  homeObj: { name: home },

  // common pattern: row.away.name / row.home.name
  away: { name: away },
  home: { name: home },

  // ---------- PRICING (provide BOTH cents + decimals) ----------
  // cents (0-100)
  market_price: marketCents,
  fair_price: fairCents,
  edge: edgeCents,

  // decimals (0-1)
  market: marketDec,
  fair: fairDec,
  edge_decimal: edgeDec,

  // also common keys
  market_prob: marketDec,
  fair_prob: fairDec,
  edge_prob: edgeDec,

  yes_bid: yesBid,
  yes_ask: yesAsk,
  last_price: last,

  // ---------- OTHER COLUMNS ----------
  // Create proper signal object for strategy evaluation
  signal: {
    signal_type: edgeDec > 0.05 ? 'STRONG_BUY' : edgeDec > 0.03 ? 'BUY' : edgeDec < -0.05 ? 'STRONG_SELL' : edgeDec < -0.03 ? 'SELL' : 'HOLD',
    signal_score: Math.min(100, Math.abs(edgeDec) * 100 * 10), // Convert edge to 0-100 score
    is_actionable: Math.abs(edgeDec) >= 0.03,
    risk_tier: Math.abs(edgeDec) > 0.07 ? 'low' : Math.abs(edgeDec) > 0.04 ? 'medium' : 'high',
    edge: edgeDec,
  },
  
  // Create intelligence object with momentum data
  intelligence: {
    momentum: (primary.price_delta ?? 0) > 0 ? 'up' : (primary.price_delta ?? 0) < 0 ? 'down' : 'neutral',
    volume: s.total_volume ?? primary.volume ?? 0,
    dollar_volume: primary.dollar_volume ?? 0,
    recent_volume: primary.recent_volume ?? 0,
    dollar_recent_volume: primary.dollar_recent_volume ?? 0,
    volatility: Math.abs(primary.price_delta ?? 0),
  },

  score: 0,
  risk: "N/A",

  ticker: s.event_ticker || s.series_ticker,
  league: s.league || s.product_metadata?.competition || "Basketball",
  volume: s.total_volume ?? primary.volume ?? 0,
  is_clutch: false,

  // Game start ≈ expected_expiration_date - 3h for NBA (expiration is game end)
  // This ensures the date falls on the correct calendar day for today-only filtering
  game_date: (() => {
    const exp = m0.expected_expiration_date || m1.expected_expiration_date || null;
    if (!exp) return null;
    const isNBA = /NBA/i.test(s.series_ticker || '');
    const offset = isNBA ? 3 * 60 * 60 * 1000 : 0;
    return new Date(new Date(exp).getTime() - offset).toISOString();
  })(),

  raw: s,
  markets: s.markets || [],

  // ---------- NESTED GAME OBJECT (provide MANY shapes) ----------
  game: {
    id: s.event_ticker || s.series_ticker,
    ticker: s.event_ticker || s.series_ticker,
    status,

    // strings
    away_team: away,
    home_team: home,
    awayTeam: away,
    homeTeam: home,

    // objects (VERY common)
    away: { name: away },
    home: { name: home },

    teams: {
      away: { name: away },
      home: { name: home }
    },

    matchup: `${away} @ ${home}`,

    title:
      s.event_title ||
      s.product_metadata?.["1v1_title"] ||
      `${away} @ ${home}`,

    subtitle: s.sub_title || s.event_subtitle || "",
    league: s.league || s.product_metadata?.competition || "Basketball",
  }
};

      });

      setGames(gamesList);
      console.log("FIRST GAME ROW:", gamesList[0]);

      const active = gamesList.filter((g) =>
        ["open", "active", "live", "scheduled", "unopened"].includes(
          g.game?.status,
        ),
      );

      setActiveGames(active);
    } catch (err) {
      console.error("Realtime games fetch error:", err);
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
