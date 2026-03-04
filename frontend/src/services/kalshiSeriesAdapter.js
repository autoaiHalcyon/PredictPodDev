export function seriesToMarket(series) {
  const tags = Array.isArray(series.tags) ? series.tags : [];

  const league =
    series.league ||
    series.category ||
    tags.find(t =>
      ["NBA", "WNBA", "NCAAM", "NCAAW", "EUROLEAGUE"].includes(
        String(t).toUpperCase()
      )
    ) ||
    "Basketball";

  return {
    ticker: series.ticker,
    title: series.title,
    subtitle: series.subtitle || series.short_description || "",
    status: (series.status || "").toLowerCase(),

    // fields already expected by UI
    yes_bid: null,
    yes_ask: null,
    volume: series.volume ?? 0,

    league,
    category: "Basketball",

    raw: series
  };
}
