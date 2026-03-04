import React, { useState, useEffect, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { ScrollArea } from "../components/ui/scroll-area";
import { seriesToMarket } from "../services/kalshiSeriesAdapter";
import {
  ArrowLeft,
  Search,
  RefreshCw,
  Database,
  Activity,
  Filter,
  LayoutGrid,
  List,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Folder
} from "lucide-react";

const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

// League icons/colors - matching backend league IDs
const LEAGUE_CONFIG = {
  "basketball": { name: "All Basketball", color: "text-primary", bg: "bg-primary/10" },
  "nba": { name: "Pro Basketball (M) / NBA", color: "text-blue-400", bg: "bg-blue-500/10" },
  "wnba": { name: "Pro Basketball (W) / WNBA", color: "text-pink-400", bg: "bg-pink-500/10" },
  "ncaa_m": { name: "College Basketball (M)", color: "text-orange-400", bg: "bg-orange-500/10" },
  "ncaa_w": { name: "College Basketball (W)", color: "text-purple-400", bg: "bg-purple-500/10" },
  "euroleague": { name: "EuroLeague", color: "text-green-400", bg: "bg-green-500/10" },
  "eurocup": { name: "EuroCup", color: "text-green-300", bg: "bg-green-500/10" },
  "aba": { name: "Adriatic ABA League", color: "text-purple-400", bg: "bg-purple-500/10" },
  "bbl": { name: "Germany BBL", color: "text-yellow-400", bg: "bg-yellow-500/10" },
  "acb": { name: "Spain Liga ACB", color: "text-red-400", bg: "bg-red-500/10" },
  "fiba": { name: "FIBA Competitions", color: "text-cyan-400", bg: "bg-cyan-500/10" },
  "other": { name: "Other Basketball", color: "text-gray-400", bg: "bg-gray-500/10" }
};

// Simplified Category List Item (non-recursive)
const CategoryListItem = ({ category, isSelected, onClick, level = 0 }) => {
  const config = LEAGUE_CONFIG[category.slug] || LEAGUE_CONFIG[category.id] || { 
    name: category.name, 
    color: "text-muted-foreground", 
    bg: "bg-muted/30" 
  };
  
  const indent = level * 16;
  
  return (
    <div
      className={`flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer transition-colors hover:bg-muted/50 ${isSelected ? 'bg-primary/20 border-l-2 border-primary' : ''}`}
      style={{ paddingLeft: `${12 + indent}px` }}
      onClick={onClick}
      data-testid={`category-${category.id}`}
    >
      <Activity className={`w-4 h-4 ${config.color}`} />
      
      <span className={`flex-1 text-sm font-medium ${config.color}`}>
        {config.name}
      </span>
      
      {category.market_count > 0 && (
        <Badge variant="secondary" className="text-xs">
          {category.market_count}
        </Badge>
      )}
    </div>
  );
};

// Market Card Component
const MarketCard = ({ market, onSelect }) => {
  const statusColor = {
    "open": "bg-green-500",
    "active": "bg-blue-500",
    "closed": "bg-gray-500",
    "settled": "bg-purple-500"
  }[market.status] || "bg-gray-500";
  
  const yesBid = market.yes_bid ? `${market.yes_bid}¢` : "-";
  const yesAsk = market.yes_ask ? `${market.yes_ask}¢` : "-";
  const spread = market.yes_bid && market.yes_ask ? `${market.yes_ask - market.yes_bid}¢` : "-";
  
  return (
    <Card 
      className="hover:border-primary/50 cursor-pointer transition-all"
      onClick={() => onSelect(market)}
      data-testid={`market-card-${market.ticker}`}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-2">
          <div className="flex-1">
            <h3 className="font-medium text-sm line-clamp-2">{market.title}</h3>
            {market.subtitle && (
              <p className="text-xs text-muted-foreground mt-1">{market.subtitle}</p>
            )}
          </div>
          <Badge variant="secondary" className={`${statusColor} text-white text-xs`}>
            {market.status?.toUpperCase()}
          </Badge>
        </div>
        
        <div className="grid grid-cols-4 gap-2 text-xs mt-3">
          <div>
            <p className="text-muted-foreground">Yes Bid</p>
            <p className="font-mono text-green-400">{yesBid}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Yes Ask</p>
            <p className="font-mono text-red-400">{yesAsk}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Spread</p>
            <p className="font-mono text-foreground">{spread}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Volume</p>
            <p className="font-mono text-foreground">{market.volume?.toLocaleString() || 0}</p>
          </div>
        </div>
        
        <div className="flex items-center justify-between mt-3 pt-2 border-t border-border">
          <span className="text-xs text-muted-foreground font-mono">
            {market.ticker}
          </span>
          <Badge variant="outline" className="text-xs">
            {market.league || market.category}
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
};

// Event Card Component
const EventCard = ({ event, onSelect }) => {
  const marketCount = event.markets?.length || 0;
  
  return (
    <Card 
      className="hover:border-primary/50 cursor-pointer transition-all"
      onClick={() => onSelect(event)}
      data-testid={`event-card-${event.ticker}`}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-2">
          <h3 className="font-medium text-sm">{event.title}</h3>
          <Badge variant="secondary" className="text-xs">
            {event.status}
          </Badge>
        </div>
        
        {event.subtitle && (
          <p className="text-xs text-muted-foreground mb-2">{event.subtitle}</p>
        )}
        
        <div className="flex items-center justify-between text-xs mt-3 pt-2 border-t border-border">
          <span className="text-muted-foreground">
            {marketCount} market{marketCount !== 1 ? 's' : ''}
          </span>
          <span className="text-muted-foreground font-mono">{event.ticker}</span>
        </div>
      </CardContent>
    </Card>
  );
};

// Main Component
export default function AllGamesPage() {
  const navigate = useNavigate();
  
  // State
  const [categories, setCategories] = useState([]);
  const [markets, setMarkets] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState("grid"); // grid or list
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState(null);
  const [error, setError] = useState(null);
  
  // Pagination
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const PAGE_SIZE = 50;
  
  // Fetch categories
  const fetchCategories = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/kalshi/categories`);
      if (res.ok) {
        const data = await res.json();
        setCategories(data.categories || []);
      }
    } catch (err) {
      console.error("Failed to fetch categories:", err);
    }
  }, []);
  
  // Fetch markets with filtering
  // const fetchMarkets = useCallback(async (reset = false) => {
  //   try {
  //     setLoading(true);
      
  //     const skip = reset ? 0 : page * PAGE_SIZE;
  //     const params = new URLSearchParams({
  //       limit: PAGE_SIZE.toString(),
  //       skip: skip.toString()
  //     });
      
  //     if (statusFilter) params.append("status", statusFilter);
  //     if (selectedCategory && selectedCategory !== "basketball") {
  //       params.append("league", selectedCategory.toUpperCase().replace(/-/g, "_"));
  //     }
      
  //     const res = await fetch(`${API_BASE}/api/kalshi/markets?${params}`);
  //     if (res.ok) {
  //       const data = await res.json();
      
        
  //       if (reset) {
  //         setMarkets(data.markets || []);
  //       } else {
  //         setMarkets(prev => [...prev, ...(data.markets || [])]);
  //       }
        
  //       setHasMore((data.markets || []).length >= PAGE_SIZE);
  //       if (reset) setPage(0);
  //     }
  //   } catch (err) {
  //     console.error("Failed to fetch markets:", err);
  //     setError(err.message);
  //   } finally {
  //     setLoading(false);
  //   }
  // }, [selectedCategory, statusFilter, page]);

  // Fetch markets with filtering (Kalshi Series API)
// Fetch markets with filtering (Kalshi Series API)
const fetchMarkets = useCallback(async (reset = false) => {
  try {
    setLoading(true);

    const skip = reset ? 0 : page * PAGE_SIZE;

    // Build Kalshi series params
    const params = new URLSearchParams({
      order_by: "trending",
      status: statusFilter || "open,unopened",
      category: "Sports",
      tag: "Basketball",
      scope: "Games",
      hydrate: "milestones,structured_targets",
      page_size: PAGE_SIZE.toString(),
      include_sports_derivatives: "false",
      with_milestones: "true"
    });

    // Optional league filter
    if (selectedCategory && selectedCategory !== "basketball") {
      params.append(
        "tag",
        selectedCategory.toUpperCase().replace(/-/g, "_")
      );
    }

    const res = await fetch(
      // `https://api.elections.kalshi.com/v1/search/series?${params.toString()}`
      `${API_BASE}/api/kalshi/series?${params.toString()}`
    );

    if (!res.ok) {
      throw new Error("Failed to fetch Kalshi series");
    }

    const data = await res.json();

    // 🔴 IMPORTANT: Kalshi uses current_page
    const series = data.current_page || [];

    // Map Kalshi -> UI market shape
    const adaptedMarkets = series.slice(skip, skip + PAGE_SIZE).map((s) => {
      const m0 = s.markets?.[0];
      const m1 = s.markets?.[1];

      const primary = m0?.yes_bid != null ? m0 : (m1 || m0);

      return {
        ticker: s.event_ticker || s.series_ticker,

        title:
          s.event_title ||
          s.product_metadata?.["1v1_title"] ||
          `${m0?.yes_subtitle || ""} vs ${m1?.yes_subtitle || ""}`.trim(),

        subtitle: s.event_subtitle || "",

        status: s.is_closing ? "closed" : "open",

        yes_bid: primary?.yes_bid ?? null,
        yes_ask: primary?.yes_ask ?? null,

        volume: primary?.volume ?? s.total_volume ?? 0,

        league: s.league || s.product_metadata?.competition || "Basketball",
        category: "Basketball",

        raw: s
      };
    });

    if (reset) {
      setMarkets(adaptedMarkets);
      setPage(0);
    } else {
      setMarkets((prev) => [...prev, ...adaptedMarkets]);
    }

    setHasMore(adaptedMarkets.length >= PAGE_SIZE);

  } catch (err) {
    console.error("Failed to fetch markets:", err);
    setError(err.message);
  } finally {
    setLoading(false);
  }
}, [selectedCategory, statusFilter, page]);

  
  // Fetch status
  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/kalshi/status`);
      if (res.ok) {
        const data = await res.json();
        setSyncStatus(data);
      }
    } catch (err) {
      console.error("Failed to fetch status:", err);
    }
  }, []);
  
  // Sync data
  const syncData = async () => {
    setSyncing(true);
    setError(null);
    
    try {
      const res = await fetch(`${API_BASE}/api/kalshi/sync`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setSyncStatus(data);
        
        // Refresh data
        await fetchCategories();
        await fetchMarkets(true);
      } else {
        setError("Sync failed");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSyncing(false);
    }
  };
  
  // Select category
  const selectCategory = (category) => {
    setSelectedCategory(category.id);
    setPage(0);
    fetchMarkets(true);
  };
  
  // Load more
  const loadMore = () => {
    if (!loading && hasMore) {
      setPage(prev => prev + 1);
    }
  };
  
  // Initial load
  useEffect(() => {
    fetchCategories();
    fetchStatus();
    fetchMarkets(true);
  }, [fetchCategories, fetchStatus, fetchMarkets]);
  
  // Fetch markets when filter changes
  useEffect(() => {
    fetchMarkets(true);
  }, [selectedCategory, statusFilter, fetchMarkets]);
  
  // Fetch more when page changes
  useEffect(() => {
    if (page > 0) {
      fetchMarkets(false);
    }
  }, [page, fetchMarkets]);
  
  // Filter markets by search
  const filteredMarkets = markets.filter(m => 
    !searchQuery || 
    m.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    m.ticker?.toLowerCase().includes(searchQuery.toLowerCase())
  );
  
  return (
    <div className="min-h-screen bg-background">
      {/* Page Header */}
      <header className="border-b border-border bg-card/50">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <Database className="w-6 h-6 text-primary" />
                All Basketball Games
              </h1>
              <p className="text-sm text-muted-foreground">
                Kalshi Markets • {syncStatus?.total_markets || 0} Markets
              </p>
            </div>
            
            <div className="flex items-center gap-3">
              {/* Sync Status */}
              <div className="text-xs text-muted-foreground flex items-center gap-2">
                {syncStatus?.last_sync ? (
                  <>
                    <CheckCircle2 className="w-4 h-4 text-green-400" />
                    Last sync: {new Date(syncStatus.last_sync).toLocaleTimeString()}
                  </>
                ) : (
                  <>
                    <AlertCircle className="w-4 h-4 text-yellow-400" />
                    Not synced
                  </>
                )}
              </div>
              
              {/* Sync Button */}
              <Button 
                variant="outline" 
                size="sm" 
                onClick={syncData}
                disabled={syncing}
                data-testid="sync-btn"
              >
                {syncing ? (
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                ) : (
                  <RefreshCw className="w-4 h-4 mr-1" />
                )}
                {syncing ? "Syncing..." : "Sync Data"}
              </Button>
            </div>
          </div>
        </div>
      </header>
      
      <div className="container mx-auto px-4 py-6">
        <div className="flex gap-6">
          {/* Sidebar - Category Tree */}
          <aside className="w-64 shrink-0">
            <Card className="sticky top-28">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Folder className="w-4 h-4" />
                  Categories
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <ScrollArea className="h-[60vh]">
                  <div className="p-2">
                    {/* Flatten categories for simple list */}
                    {categories.map(cat => (
                      <div key={cat.id}>
                        <CategoryListItem
                          category={cat}
                          isSelected={selectedCategory === cat.id}
                          onClick={() => selectCategory(cat)}
                          level={0}
                        />
                        {/* Show children */}
                        {cat.children && cat.children.map(child => (
                          <CategoryListItem
                            key={child.id}
                            category={child}
                            isSelected={selectedCategory === child.id}
                            onClick={() => selectCategory(child)}
                            level={1}
                          />
                        ))}
                      </div>
                    ))}
                    
                    {categories.length === 0 && (
                      <div className="text-center py-8 text-muted-foreground text-sm">
                        <p>No categories loaded</p>
                        <p className="text-xs mt-1">Click "Sync Data" to fetch</p>
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </aside>
          
          {/* Main Content */}
          <main className="flex-1 space-y-4">
            {/* Filters Bar */}
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-4">
                  {/* Search */}
                  <div className="relative flex-1 max-w-md">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                      placeholder="Search markets..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-9"
                      data-testid="search-input"
                    />
                  </div>
                  
                  {/* Status Filter */}
                  <div className="flex items-center gap-2">
                    <Filter className="w-4 h-4 text-muted-foreground" />
                    <select
                      value={statusFilter}
                      onChange={(e) => setStatusFilter(e.target.value)}
                      className="bg-background border border-border rounded-md px-3 py-2 text-sm"
                      data-testid="status-filter"
                    >
                      <option value="">All Status</option>
                      <option value="open">Open</option>
                      <option value="active">Active</option>
                      <option value="closed">Closed</option>
                      <option value="settled">Settled</option>
                    </select>
                  </div>
                  
                  {/* View Mode */}
                  <div className="flex items-center gap-1 border border-border rounded-md p-1">
                    <Button
                      variant={viewMode === "grid" ? "secondary" : "ghost"}
                      size="sm"
                      onClick={() => setViewMode("grid")}
                    >
                      <LayoutGrid className="w-4 h-4" />
                    </Button>
                    <Button
                      variant={viewMode === "list" ? "secondary" : "ghost"}
                      size="sm"
                      onClick={() => setViewMode("list")}
                    >
                      <List className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            {/* Markets Grid/List */}
            {loading && markets.length === 0 ? (
              <div className="flex items-center justify-center py-20">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
              </div>
            ) : filteredMarkets.length === 0 ? (
              <Card>
                <CardContent className="py-20 text-center">
                  <Database className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-medium mb-2">No Markets Found</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    {syncStatus?.total_markets === 0 
                      ? "Click 'Sync Data' to fetch basketball markets from Kalshi"
                      : "Try adjusting your filters or search query"
                    }
                  </p>
                  {syncStatus?.total_markets === 0 && (
                    <Button onClick={syncData} disabled={syncing}>
                      {syncing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
                      Sync Data
                    </Button>
                  )}
                </CardContent>
              </Card>
            ) : (
              <>
                {/* Results Count */}
                <div className="flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">
                    Showing {filteredMarkets.length} of {syncStatus?.total_markets || markets.length} markets
                  </p>
                </div>
                
                {/* Grid View */}
                {viewMode === "grid" ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredMarkets.map(market => (
                      <MarketCard
                        key={market.ticker}
                        market={market}
                        onSelect={(m) => navigate(`/game/${m.ticker}`)}
                      />
                    ))}
                  </div>
                ) : (
                  // List View
                  <Card>
                    <CardContent className="p-0">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-border">
                            <th className="text-left py-3 px-4 text-muted-foreground">Market</th>
                            <th className="text-center py-3 px-2 text-muted-foreground">Status</th>
                            <th className="text-right py-3 px-2 text-muted-foreground">Yes Bid</th>
                            <th className="text-right py-3 px-2 text-muted-foreground">Yes Ask</th>
                            <th className="text-right py-3 px-2 text-muted-foreground">Volume</th>
                            <th className="text-center py-3 px-4 text-muted-foreground">League</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredMarkets.map(market => (
                            <tr 
                              key={market.ticker} 
                              className="border-b border-border/50 hover:bg-muted/30 cursor-pointer"
                              onClick={() => navigate(`/game/${market.ticker}`)}
                            >
                              <td className="py-3 px-4">
                                <div>
                                  <p className="font-medium">{market.title}</p>
                                  <p className="text-xs text-muted-foreground font-mono">{market.ticker}</p>
                                </div>
                              </td>
                              <td className="text-center py-3 px-2">
                                <Badge variant="secondary" className="text-xs">
                                  {market.status}
                                </Badge>
                              </td>
                              <td className="text-right py-3 px-2 font-mono text-green-400">
                                {market.yes_bid ? `${market.yes_bid}¢` : "-"}
                              </td>
                              <td className="text-right py-3 px-2 font-mono text-red-400">
                                {market.yes_ask ? `${market.yes_ask}¢` : "-"}
                              </td>
                              <td className="text-right py-3 px-2 font-mono">
                                {market.volume?.toLocaleString() || 0}
                              </td>
                              <td className="text-center py-3 px-4">
                                <Badge variant="outline" className="text-xs">
                                  {market.league || "-"}
                                </Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </CardContent>
                  </Card>
                )}
                
                {/* Load More */}
                {hasMore && (
                  <div className="flex justify-center py-4">
                    <Button 
                      variant="outline" 
                      onClick={loadMore}
                      disabled={loading}
                    >
                      {loading ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : null}
                      Load More
                    </Button>
                  </div>
                )}
              </>
            )}
            
            {/* Error Display */}
            {error && (
              <div className="p-4 bg-red-500/20 border border-red-500 rounded-lg flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-red-400" />
                <p className="text-red-400">{error}</p>
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
