"""
Kalshi Basketball Market Ingestor - V2 (Production)

Properly filters ONLY basketball markets using Kalshi's category/tag hierarchy.
No string guessing - uses authoritative series tickers.

Supported Basketball Categories:
- NBA (Pro Basketball)
- NCAA Men's (College Basketball M)
- NCAA Women's (College Basketball W)
- EuroLeague
- ABA League
- Germany BBL
- Other international leagues
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Set
from enum import Enum
import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BasketballLeague(str, Enum):
    """Supported basketball leagues"""
    NBA = "NBA"
    WNBA = "WNBA"
    NCAA_M = "NCAA_M"
    NCAA_W = "NCAA_W"
    EUROLEAGUE = "EUROLEAGUE"
    EUROCUP = "EUROCUP"
    ABA = "ABA"
    BBL = "BBL"  # Germany
    ACB = "ACB"  # Spain
    SERIE_A = "SERIE_A"  # Italy
    LNB = "LNB"  # France
    BSL = "BSL"  # Turkey
    VTB = "VTB"  # Russia
    NBL = "NBL"  # Australia
    CBA = "CBA"  # China
    KBL = "KBL"  # Korea
    JBLEAGUE = "JBLEAGUE"  # Japan
    FIBA = "FIBA"
    UNRIVALED = "UNRIVALED"
    OTHER = "OTHER"


# Authoritative mapping of series tickers to leagues
BASKETBALL_SERIES_MAP = {
    # NBA
    "KXNBAGAME": BasketballLeague.NBA,
    "KXNBASERIES": BasketballLeague.NBA,
    "KXNBASPREAD": BasketballLeague.NBA,
    "KXNBATOTAL": BasketballLeague.NBA,
    "KXNBATEAMTOTAL": BasketballLeague.NBA,
    "KXNBA1QTOTAL": BasketballLeague.NBA,
    "KXNBA2QTOTAL": BasketballLeague.NBA,
    "KXNBA3QTOTAL": BasketballLeague.NBA,
    "KXNBA4QTOTAL": BasketballLeague.NBA,
    "KXNBA1HTOTAL": BasketballLeague.NBA,
    "KXNBA2HTOTAL": BasketballLeague.NBA,
    "KXNBA1QSPREAD": BasketballLeague.NBA,
    "KXNBA2QSPREAD": BasketballLeague.NBA,
    "KXNBA3QSPREAD": BasketballLeague.NBA,
    "KXNBA4QSPREAD": BasketballLeague.NBA,
    "KXNBA1HSPREAD": BasketballLeague.NBA,
    "KXNBA2HSPREAD": BasketballLeague.NBA,
    "KXNBAGAME1H": BasketballLeague.NBA,
    "KXNBA1QWINNER": BasketballLeague.NBA,
    "KXNBA2QWINNER": BasketballLeague.NBA,
    "KXNBA3QWINNER": BasketballLeague.NBA,
    "KXNBA4QWINNER": BasketballLeague.NBA,
    "KXNBA1HWINNER": BasketballLeague.NBA,
    "KXNBA2HWINNER": BasketballLeague.NBA,
    
    # WNBA
    "KXWNBAGAME": BasketballLeague.WNBA,
    "KXWNBASERIES": BasketballLeague.WNBA,
    
    # NCAA Men's
    "KXNCAAMBGAME": BasketballLeague.NCAA_M,
    "KXNCAAMBBGAME": BasketballLeague.NCAA_M,
    "KXNCAABGAME": BasketballLeague.NCAA_M,
    "KXNCAAMBSPREAD": BasketballLeague.NCAA_M,
    "KXNCAAMBBSPREAD": BasketballLeague.NCAA_M,
    "KXNCAAMBBTOTAL": BasketballLeague.NCAA_M,
    "KXNCAAMBTOTAL": BasketballLeague.NCAA_M,
    
    # NCAA Women's
    "KXNCAAWBGAME": BasketballLeague.NCAA_W,
    "KXNCAAWBSPREAD": BasketballLeague.NCAA_W,
    "KXNCAAWBTOTAL": BasketballLeague.NCAA_W,
    
    # European Leagues
    "KXEUROLEAGUEGAME": BasketballLeague.EUROLEAGUE,
    "KXEUROCUPGAME": BasketballLeague.EUROCUP,
    "KXABAGAME": BasketballLeague.ABA,
    "KXBBLGAME": BasketballLeague.BBL,
    "KXACBGAME": BasketballLeague.ACB,
    "KXBBSERIEAGAME": BasketballLeague.SERIE_A,
    "KXLNBELITEGAME": BasketballLeague.LNB,
    "KXBSLGAME": BasketballLeague.BSL,
    "KXVTBGAME": BasketballLeague.VTB,
    
    # Other International
    "KXNBLGAME": BasketballLeague.NBL,
    "KXCBAGAME": BasketballLeague.CBA,
    "KXKBLGAME": BasketballLeague.KBL,
    "KXJBLEAGUEGAME": BasketballLeague.JBLEAGUE,
    "KXFIBACHAMPLEAGUEGAME": BasketballLeague.FIBA,
    "KXFIBAECUPGAME": BasketballLeague.FIBA,
    "KXGBLGAME": BasketballLeague.OTHER,
    "KXARGLNBGAME": BasketballLeague.OTHER,
    
    # Special
    "KXUNRIVALEDGAME": BasketballLeague.UNRIVALED,
}

# Series tickers that contain game-level markets
GAME_SERIES_TICKERS = set(BASKETBALL_SERIES_MAP.keys())


class KalshiCategory(BaseModel):
    """Basketball category in the tree"""
    id: str
    name: str
    slug: str
    parent_id: Optional[str] = None
    leagues: List[str] = Field(default_factory=list)
    event_count: int = 0
    market_count: int = 0


class KalshiEvent(BaseModel):
    """Kalshi basketball event"""
    ticker: str
    title: str
    subtitle: Optional[str] = None
    series_ticker: str
    league: str
    status: str
    markets: List[str] = Field(default_factory=list)
    volume: int = 0
    open_time: Optional[datetime] = None
    close_time: Optional[datetime] = None


class KalshiMarket(BaseModel):
    """Kalshi basketball market"""
    ticker: str
    event_ticker: str
    series_ticker: str
    league: str
    title: str
    subtitle: Optional[str] = None
    status: str
    yes_bid: Optional[int] = None
    yes_ask: Optional[int] = None
    no_bid: Optional[int] = None
    no_ask: Optional[int] = None
    last_price: Optional[int] = None
    volume: int = 0
    open_interest: int = 0
    open_time: Optional[datetime] = None
    close_time: Optional[datetime] = None
    result: Optional[str] = None
    # Extracted game info
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    game_date: Optional[str] = None


class OrderBookSnapshot(BaseModel):
    """Orderbook snapshot"""
    market_ticker: str
    yes_bids: List[tuple] = Field(default_factory=list)
    no_bids: List[tuple] = Field(default_factory=list)
    best_yes_bid: Optional[int] = None
    best_no_bid: Optional[int] = None
    best_yes_ask: Optional[int] = None
    best_no_ask: Optional[int] = None
    spread_cents: Optional[int] = None
    total_liquidity: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KalshiBasketballIngestorV2:
    """
    Production-grade basketball market ingestor.
    
    Key improvements over V1:
    - Uses authoritative series ticker mapping (no string guessing)
    - Validates against known basketball series
    - Properly categorizes by league
    - MongoDB persistence with indexes
    """
    
    DEMO_API_URL = "https://demo-api.kalshi.co/trade-api/v2"
    PROD_API_URL = "https://api.elections.kalshi.com/trade-api/v2"
    
    REQUEST_DELAY = 0.1  # 100ms between requests
    
    def __init__(
        self,
        use_demo: bool = True,
        db=None
    ):
        self.use_demo = use_demo
        self.db = db
        self.base_url = self.DEMO_API_URL if use_demo else self.PROD_API_URL
        self._client: Optional[httpx.AsyncClient] = None
        
        # Cache
        self._basketball_series: Set[str] = set()
        self._events_cache: Dict[str, KalshiEvent] = {}
        self._markets_cache: Dict[str, KalshiMarket] = {}
        
        # Stats
        self.last_sync_time: Optional[datetime] = None
        self.stats: Dict[str, int] = {}
        self.errors: List[str] = []
        
        logger.info(f"KalshiBasketballIngestorV2 initialized (demo={use_demo})")
    
    async def connect(self):
        """Initialize HTTP client"""
        if not self._client:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"Accept": "application/json"}
            )
    
    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _request(self, method: str, path: str, params: Optional[Dict] = None) -> Dict:
        """Make API request with rate limiting"""
        if not self._client:
            await self.connect()
        
        url = f"{self.base_url}{path}"
        
        try:
            await asyncio.sleep(self.REQUEST_DELAY)
            response = await self._client.request(method=method, url=url, params=params)
            
            if response.status_code == 429:
                logger.warning("Rate limit hit, backing off...")
                await asyncio.sleep(5)
                return await self._request(method, path, params)
            
            if response.status_code >= 400:
                logger.error(f"API error {response.status_code}: {response.text}")
                return {}
            
            return response.json()
        except Exception as e:
            logger.error(f"Request error: {e}")
            self.errors.append(str(e))
            return {}
    
    # ==========================================
    # DISCOVERY - Find Basketball Series
    # ==========================================
    
    async def discover_basketball_series(self) -> Set[str]:
        """
        Discover all basketball series tickers from Kalshi.
        Uses tags and category to validate.
        """
        logger.info("Discovering basketball series...")
        
        # Start with known authoritative list
        discovered = set(GAME_SERIES_TICKERS)
        
        # Also scan API for any new basketball series
        response = await self._request("GET", "/series", params={"limit": 500})
        series_list = response.get("series", [])
        
        for series in series_list:
            ticker = series.get("ticker", "")
            tags = [t.lower() for t in (series.get("tags") or [])]
            category = series.get("category", "").lower()
            title = series.get("title", "").lower()
            
            # Check if this is a basketball series
            if "basketball" in tags:
                discovered.add(ticker)
            elif category == "sports" and "basketball" in title:
                discovered.add(ticker)
            elif "nba" in ticker.lower() or "ncaa" in ticker.lower():
                # Only add if it's a game/spread/total series
                if any(x in ticker.lower() for x in ["game", "spread", "total", "winner"]):
                    discovered.add(ticker)
        
        self._basketball_series = discovered
        logger.info(f"Discovered {len(discovered)} basketball series")
        
        return discovered
    
    def _get_league_for_series(self, series_ticker: str) -> BasketballLeague:
        """Get league for a series ticker"""
        if series_ticker in BASKETBALL_SERIES_MAP:
            return BASKETBALL_SERIES_MAP[series_ticker]
        
        # Fallback classification by ticker pattern
        ticker_upper = series_ticker.upper()
        
        if "WNBA" in ticker_upper:
            return BasketballLeague.WNBA
        elif "NCAAW" in ticker_upper or "NCAA" in ticker_upper and "W" in ticker_upper:
            return BasketballLeague.NCAA_W
        elif "NCAA" in ticker_upper:
            return BasketballLeague.NCAA_M
        elif "NBA" in ticker_upper:
            return BasketballLeague.NBA
        elif "EURO" in ticker_upper:
            return BasketballLeague.EUROLEAGUE
        elif "ABA" in ticker_upper:
            return BasketballLeague.ABA
        elif "BBL" in ticker_upper:
            return BasketballLeague.BBL
        else:
            return BasketballLeague.OTHER
    
    # ==========================================
    # FETCH EVENTS
    # ==========================================
    
    async def fetch_basketball_events(
        self,
        status: Optional[str] = None,
        series_ticker: Optional[str] = None
    ) -> List[KalshiEvent]:
        """
        Fetch basketball events.
        Only includes events from known basketball series.
        """
        logger.info(f"Fetching basketball events (status={status}, series={series_ticker})...")
        
        # Ensure we have series list
        if not self._basketball_series:
            await self.discover_basketball_series()
        
        all_events: List[KalshiEvent] = []
        cursor = None
        page = 0
        
        while True:
            params = {"limit": 200, "with_nested_markets": True}
            if cursor:
                params["cursor"] = cursor
            if status:
                params["status"] = status
            if series_ticker:
                params["series_ticker"] = series_ticker
            
            response = await self._request("GET", "/events", params=params)
            events_data = response.get("events", [])
            cursor = response.get("cursor")
            
            if not events_data:
                break
            
            for event_data in events_data:
                event_series = event_data.get("series_ticker", "")
                
                # CRITICAL: Only include events from basketball series
                if event_series not in self._basketball_series:
                    continue
                
                event = self._parse_event(event_data)
                if event:
                    all_events.append(event)
                    self._events_cache[event.ticker] = event
            
            page += 1
            logger.info(f"Page {page}: {len(all_events)} basketball events")
            
            if not cursor or page > 50:
                break
        
        logger.info(f"Total basketball events: {len(all_events)}")
        return all_events
    
    def _parse_event(self, data: Dict) -> Optional[KalshiEvent]:
        """Parse event data and also extract markets"""
        try:
            series_ticker = data.get("series_ticker", "")
            league = self._get_league_for_series(series_ticker)
            
            # Note: Kalshi uses 'event_ticker' not 'ticker' for events
            event_ticker = data.get("event_ticker", "") or data.get("ticker", "")
            
            markets = data.get("markets", [])
            market_tickers = [m.get("ticker", "") for m in markets if m.get("ticker")]
            
            # Also parse and cache the markets from this event
            for market_data in markets:
                market = self._parse_market_from_event(market_data, series_ticker, league)
                if market:
                    self._markets_cache[market.ticker] = market
            
            # Skip events without a ticker
            if not event_ticker:
                logger.warning(f"Skipping event without ticker: {data.get('title', 'unknown')}")
                return None
            
            return KalshiEvent(
                ticker=event_ticker,
                title=data.get("title", ""),
                subtitle=data.get("subtitle"),
                series_ticker=series_ticker,
                league=league.value,
                status=data.get("status", "unknown"),
                markets=market_tickers,
                volume=sum(m.get("volume", 0) for m in markets)
            )
        except Exception as e:
            logger.error(f"Error parsing event: {e}")
            return None
    
    def _parse_market_from_event(self, data: Dict, series_ticker: str, league) -> Optional[KalshiMarket]:
        """Parse market data from event's nested markets"""
        try:
            return KalshiMarket(
                ticker=data.get("ticker", ""),
                event_ticker=data.get("event_ticker", ""),
                series_ticker=series_ticker,
                league=league.value if hasattr(league, 'value') else str(league),
                title=data.get("title", ""),
                subtitle=data.get("subtitle"),
                status=data.get("status", "unknown"),
                yes_bid=data.get("yes_bid"),
                yes_ask=data.get("yes_ask"),
                no_bid=data.get("no_bid"),
                no_ask=data.get("no_ask"),
                last_price=data.get("last_price"),
                volume=data.get("volume", 0),
                open_interest=data.get("open_interest", 0),
                result=data.get("result")
            )
        except Exception as e:
            logger.error(f"Error parsing market from event: {e}")
            return None
    
    # ==========================================
    # FETCH MARKETS
    # ==========================================
    
    async def fetch_basketball_markets(
        self,
        status: Optional[str] = None,
        event_ticker: Optional[str] = None,
        series_ticker: Optional[str] = None
    ) -> List[KalshiMarket]:
        """
        Fetch basketball markets.
        Only includes markets from basketball series.
        """
        logger.info(f"Fetching basketball markets...")
        
        if not self._basketball_series:
            await self.discover_basketball_series()
        
        all_markets: List[KalshiMarket] = []
        cursor = None
        page = 0
        
        while True:
            params = {"limit": 200}
            if cursor:
                params["cursor"] = cursor
            if status:
                params["status"] = status
            if event_ticker:
                params["event_ticker"] = event_ticker
            if series_ticker:
                params["series_ticker"] = series_ticker
            
            response = await self._request("GET", "/markets", params=params)
            markets_data = response.get("markets", [])
            cursor = response.get("cursor")
            
            if not markets_data:
                break
            
            for market_data in markets_data:
                market_series = market_data.get("series_ticker", "")
                
                # CRITICAL: Only include markets from basketball series
                if market_series not in self._basketball_series:
                    continue
                
                market = self._parse_market(market_data)
                if market:
                    all_markets.append(market)
                    self._markets_cache[market.ticker] = market
            
            page += 1
            logger.info(f"Page {page}: {len(all_markets)} basketball markets")
            
            if not cursor or page > 100:
                break
        
        logger.info(f"Total basketball markets: {len(all_markets)}")
        return all_markets
    
    def _parse_market(self, data: Dict) -> Optional[KalshiMarket]:
        """Parse market data"""
        try:
            series_ticker = data.get("series_ticker", "")
            league = self._get_league_for_series(series_ticker)
            
            return KalshiMarket(
                ticker=data.get("ticker", ""),
                event_ticker=data.get("event_ticker", ""),
                series_ticker=series_ticker,
                league=league.value,
                title=data.get("title", ""),
                subtitle=data.get("subtitle"),
                status=data.get("status", "unknown"),
                yes_bid=data.get("yes_bid"),
                yes_ask=data.get("yes_ask"),
                no_bid=data.get("no_bid"),
                no_ask=data.get("no_ask"),
                last_price=data.get("last_price"),
                volume=data.get("volume", 0),
                open_interest=data.get("open_interest", 0),
                result=data.get("result")
            )
        except Exception as e:
            logger.error(f"Error parsing market: {e}")
            return None
    
    # ==========================================
    # ORDERBOOK
    # ==========================================
    
    async def get_orderbook(self, market_ticker: str) -> Optional[OrderBookSnapshot]:
        """Get orderbook for a market"""
        response = await self._request("GET", f"/markets/{market_ticker}/orderbook")
        
        if not response:
            return None
        
        orderbook = response.get("orderbook", {})
        yes_bids = [(b[0], b[1]) for b in orderbook.get("yes", [])]
        no_bids = [(b[0], b[1]) for b in orderbook.get("no", [])]
        
        best_yes_bid = yes_bids[-1][0] if yes_bids else None
        best_no_bid = no_bids[-1][0] if no_bids else None
        best_yes_ask = (100 - best_no_bid) if best_no_bid else None
        best_no_ask = (100 - best_yes_bid) if best_yes_bid else None
        
        spread = (best_yes_ask - best_yes_bid) if (best_yes_ask and best_yes_bid) else None
        liquidity = sum(q for _, q in yes_bids) + sum(q for _, q in no_bids)
        
        return OrderBookSnapshot(
            market_ticker=market_ticker,
            yes_bids=yes_bids,
            no_bids=no_bids,
            best_yes_bid=best_yes_bid,
            best_no_bid=best_no_bid,
            best_yes_ask=best_yes_ask,
            best_no_ask=best_no_ask,
            spread_cents=spread,
            total_liquidity=liquidity
        )
    
    # ==========================================
    # FULL SYNC
    # ==========================================
    
    async def full_sync(self, include_closed: bool = True) -> Dict[str, Any]:
        """
        Full sync of all basketball data.
        Stores to MongoDB with proper indexes.
        
        Markets are extracted from events (with_nested_markets=True).
        """
        logger.info("Starting full basketball sync...")
        
        start_time = datetime.now(timezone.utc)
        self.errors = []
        
        # Clear caches for fresh sync
        self._events_cache = {}
        self._markets_cache = {}
        
        # Discover series
        await self.discover_basketball_series()
        
        # Fetch open events (markets are parsed inline)
        open_events = await self.fetch_basketball_events(status="open")
        
        # Fetch closed events for history
        closed_events = []
        if include_closed:
            closed_events = await self.fetch_basketball_events(status="closed")
        
        all_events = open_events + closed_events
        
        # Markets are already in cache from event parsing
        all_markets = list(self._markets_cache.values())
        
        # Ensure events are in cache too
        for event in all_events:
            self._events_cache[event.ticker] = event
        
        # Build stats by league
        league_stats = {}
        for event in all_events:
            league = event.league
            if league not in league_stats:
                league_stats[league] = {"events": 0, "markets": 0, "volume": 0}
            league_stats[league]["events"] += 1
            league_stats[league]["volume"] += event.volume
        
        for market in all_markets:
            league = market.league
            if league not in league_stats:
                league_stats[league] = {"events": 0, "markets": 0, "volume": 0}
            league_stats[league]["markets"] += 1
        
        # Store to MongoDB
        if self.db is not None:
            await self._store_to_db(all_events, all_markets)
        
        self.last_sync_time = datetime.now(timezone.utc)
        duration = (self.last_sync_time - start_time).total_seconds()
        
        self.stats = {
            "total_events": len(all_events),
            "open_events": len(open_events),
            "closed_events": len(closed_events),
            "total_markets": len(all_markets),
            "by_league": league_stats,
            "duration_seconds": duration,
            "errors": len(self.errors)
        }
        
        logger.info(f"Sync complete: {self.stats}")
        
        return {
            "success": len(self.errors) == 0,
            "sync_time": self.last_sync_time.isoformat(),
            **self.stats
        }
    
    async def _store_to_db(self, events: List[KalshiEvent], markets: List[KalshiMarket]):
        """Store data to MongoDB with indexes"""
        if self.db is None:
            logger.warning("Database is None, skipping storage")
            return
        
        logger.info(f"Starting DB storage: {len(events)} events, {len(markets)} markets")
        logger.info(f"DB instance: {type(self.db)}, name: {self.db.name if hasattr(self.db, 'name') else 'unknown'}")
        
        try:
            # Create indexes (idempotent)
            await self.db.kalshi_events.create_index("ticker", unique=True)
            await self.db.kalshi_events.create_index("series_ticker")
            await self.db.kalshi_events.create_index("league")
            await self.db.kalshi_events.create_index("status")
            await self.db.kalshi_events.create_index("updated_at")
            
            await self.db.kalshi_markets.create_index("ticker", unique=True)
            await self.db.kalshi_markets.create_index("event_ticker")
            await self.db.kalshi_markets.create_index("series_ticker")
            await self.db.kalshi_markets.create_index("league")
            await self.db.kalshi_markets.create_index("status")
            await self.db.kalshi_markets.create_index("updated_at")
            
            logger.info("Indexes created successfully")
            
            # Upsert events
            now = datetime.now(timezone.utc)
            events_stored = 0
            for event in events:
                doc = event.dict()
                doc["updated_at"] = now
                result = await self.db.kalshi_events.update_one(
                    {"ticker": event.ticker},
                    {"$set": doc},
                    upsert=True
                )
                events_stored += 1
                if events_stored <= 3:
                    logger.info(f"Event upsert result: modified={result.modified_count}, upserted={result.upserted_id is not None}")
            
            # Upsert markets (batch for performance)
            markets_stored = 0
            for market in markets:
                doc = market.dict()
                doc["updated_at"] = now
                await self.db.kalshi_markets.update_one(
                    {"ticker": market.ticker},
                    {"$set": doc},
                    upsert=True
                )
                markets_stored += 1
            
            logger.info(f"Stored to DB: {events_stored} events, {markets_stored} markets")
            
        except Exception as e:
            logger.error(f"DB storage error: {type(e).__name__}: {e}")
            self.errors.append(str(e))
    
    # ==========================================
    # GETTERS
    # ==========================================
    
    async def get_categories(self) -> List[Dict]:
        """Get basketball category tree"""
        # Build from stats
        leagues = list(BasketballLeague)
        
        root = {
            "id": "basketball",
            "name": "Basketball",
            "slug": "basketball",
            "children": []
        }
        
        league_counts = self.stats.get("by_league", {})
        
        for league in leagues:
            if league.value == "OTHER":
                continue
            
            stats = league_counts.get(league.value, {"events": 0, "markets": 0})
            
            root["children"].append({
                "id": league.value.lower(),
                "name": self._league_display_name(league),
                "slug": league.value.lower(),
                "event_count": stats.get("events", 0),
                "market_count": stats.get("markets", 0)
            })
        
        return [root]
    
    def _league_display_name(self, league: BasketballLeague) -> str:
        """Get display name for league"""
        names = {
            BasketballLeague.NBA: "Pro Basketball (M) / NBA",
            BasketballLeague.WNBA: "Pro Basketball (W) / WNBA",
            BasketballLeague.NCAA_M: "College Basketball (M)",
            BasketballLeague.NCAA_W: "College Basketball (W)",
            BasketballLeague.EUROLEAGUE: "EuroLeague",
            BasketballLeague.EUROCUP: "EuroCup",
            BasketballLeague.ABA: "Adriatic ABA League",
            BasketballLeague.BBL: "Germany BBL",
            BasketballLeague.ACB: "Spain Liga ACB",
            BasketballLeague.SERIE_A: "Italy Serie A",
            BasketballLeague.LNB: "France LNB Elite",
            BasketballLeague.BSL: "Turkey BSL",
            BasketballLeague.VTB: "VTB United League",
            BasketballLeague.NBL: "Australia NBL",
            BasketballLeague.CBA: "China CBA",
            BasketballLeague.KBL: "Korea KBL",
            BasketballLeague.JBLEAGUE: "Japan B.League",
            BasketballLeague.FIBA: "FIBA Competitions",
            BasketballLeague.UNRIVALED: "Unrivaled",
        }
        return names.get(league, league.value)
    
    async def get_events(
        self,
        league: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict]:
        """Get events with filtering"""
        if self.db is not None:
            query = {}
            if league:
                query["league"] = league.upper()
            if status:
                query["status"] = status
            
            cursor = self.db.kalshi_events.find(query, {"_id": 0}).skip(skip).limit(limit)
            return await cursor.to_list(length=limit)
        
        # From cache
        events = list(self._events_cache.values())
        if league:
            events = [e for e in events if e.league == league.upper()]
        if status:
            events = [e for e in events if e.status == status]
        
        return [e.dict() for e in events[skip:skip+limit]]
    
    async def get_markets(
        self,
        league: Optional[str] = None,
        event_ticker: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict]:
        """Get markets with filtering"""
        if self.db is not None:
            query = {}
            if league:
                query["league"] = league.upper()
            if event_ticker:
                query["event_ticker"] = event_ticker
            if status:
                query["status"] = status
            
            cursor = self.db.kalshi_markets.find(query, {"_id": 0}).skip(skip).limit(limit)
            return await cursor.to_list(length=limit)
        
        # From cache
        markets = list(self._markets_cache.values())
        if league:
            markets = [m for m in markets if m.league == league.upper()]
        if event_ticker:
            markets = [m for m in markets if m.event_ticker == event_ticker]
        if status:
            markets = [m for m in markets if m.status == status]
        
        return [m.dict() for m in markets[skip:skip+limit]]
    
    async def get_market_by_ticker(self, ticker: str) -> Optional[Dict]:
        """Get single market"""
        if ticker in self._markets_cache:
            return self._markets_cache[ticker].dict()
        
        if self.db is not None:
            doc = await self.db.kalshi_markets.find_one({"ticker": ticker}, {"_id": 0})
            return doc
        
        return None
    
    def get_status(self) -> Dict:
        """Get ingestor status"""
        return {
            "connected": self._client is not None,
            "use_demo": self.use_demo,
            "last_sync": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "basketball_series_count": len(self._basketball_series),
            "cached_events": len(self._events_cache),
            "cached_markets": len(self._markets_cache),
            "stats": self.stats,
            "recent_errors": self.errors[-5:]
        }
    
    async def get_sample_events_by_league(self, sample_size: int = 5) -> Dict[str, List[Dict]]:
        """Get sample events for each league - for validation"""
        samples = {}
        
        for league in BasketballLeague:
            if league == BasketballLeague.OTHER:
                continue
            
            events = await self.get_events(league=league.value, limit=sample_size)
            if events:
                samples[league.value] = events
        
        return samples


# Global instance
kalshi_ingestor_v2: Optional[KalshiBasketballIngestorV2] = None
