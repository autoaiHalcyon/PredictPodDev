"""
Kalshi Basketball Market Ingestor

Production-grade data ingestion pipeline for all Kalshi basketball markets.
Supports:
- Full category tree mirroring (NBA, NCAA M/W, EuroLeague, etc.)
- Active, upcoming, and historical data (30-60 days)
- Pagination for large datasets (500+ markets)
- Order book data retrieval
- Periodic refresh with caching
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MarketStatus(str, Enum):
    """Kalshi market status enumeration"""
    INITIALIZED = "initialized"
    OPEN = "open"
    ACTIVE = "active"
    CLOSED = "closed"
    SETTLED = "settled"
    DETERMINED = "determined"


class KalshiCategory(BaseModel):
    """Basketball category in the Kalshi tree"""
    id: str
    name: str
    slug: str
    parent_id: Optional[str] = None
    children: List["KalshiCategory"] = Field(default_factory=list)
    market_count: int = 0
    event_count: int = 0


class KalshiEvent(BaseModel):
    """Kalshi event (e.g., Lakers vs Warriors Feb 15)"""
    ticker: str
    title: str
    subtitle: Optional[str] = None
    category: str
    series_ticker: str
    status: str
    open_time: Optional[datetime] = None
    close_time: Optional[datetime] = None
    settlement_timer_seconds: Optional[int] = None
    mutually_exclusive: bool = True
    markets: List[str] = Field(default_factory=list)  # Market tickers
    volume: int = 0


class KalshiMarket(BaseModel):
    """Kalshi market (e.g., Lakers to score > 110)"""
    ticker: str
    event_ticker: str
    series_ticker: str
    category: str
    title: str
    subtitle: Optional[str] = None
    status: str
    yes_bid: Optional[int] = None  # In cents
    yes_ask: Optional[int] = None
    no_bid: Optional[int] = None
    no_ask: Optional[int] = None
    last_price: Optional[int] = None
    volume: int = 0
    open_interest: int = 0
    open_time: Optional[datetime] = None
    close_time: Optional[datetime] = None
    settlement_value: Optional[str] = None
    result: Optional[str] = None
    # Extracted metadata
    team_home: Optional[str] = None
    team_away: Optional[str] = None
    league: Optional[str] = None


class OrderBookSnapshot(BaseModel):
    """Orderbook snapshot for a market"""
    market_ticker: str
    yes_bids: List[Tuple[int, int]] = Field(default_factory=list)  # (price_cents, quantity)
    no_bids: List[Tuple[int, int]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    best_yes_bid: Optional[int] = None
    best_no_bid: Optional[int] = None
    best_yes_ask: Optional[int] = None  # Implied from no_bids
    best_no_ask: Optional[int] = None   # Implied from yes_bids
    spread_cents: Optional[int] = None
    total_liquidity: int = 0


class KalshiBasketballIngestor:
    """
    Kalshi Basketball Market Data Ingestor
    
    Pulls all basketball markets from Kalshi API (demo environment first)
    and stores them for the strategy engine.
    
    Features:
    - Category tree discovery
    - Full pagination support
    - Order book retrieval
    - Caching with TTL
    - Rate limiting compliance
    """
    
    # Base URL for Kalshi API (demo first, then production)
    DEMO_API_URL = "https://demo-api.kalshi.co/trade-api/v2"
    PROD_API_URL = "https://api.elections.kalshi.com/trade-api/v2"
    
    # Basketball category identifiers
    BASKETBALL_CATEGORY = "basketball"
    BASKETBALL_SUBCATEGORIES = [
        "nba",
        "ncaa-mens-basketball",
        "ncaa-womens-basketball", 
        "euroleague",
        "aba-league",
        "germany-bbl",
        "pro-basketball"
    ]
    
    # Rate limiting
    REQUESTS_PER_SECOND = 10  # Conservative for demo
    REQUEST_DELAY = 0.1  # 100ms between requests
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        private_key_path: Optional[str] = None,
        use_demo: bool = True,
        db=None
    ):
        """
        Initialize the ingestor.
        
        Args:
            api_key: Kalshi API key (optional for public endpoints)
            private_key_path: Path to private key file
            use_demo: Use demo API (default True)
            db: MongoDB database instance
        """
        self.api_key = api_key
        self.private_key_path = private_key_path
        self.use_demo = use_demo
        self.db = db
        
        self.base_url = self.DEMO_API_URL if use_demo else self.PROD_API_URL
        self._client: Optional[httpx.AsyncClient] = None
        
        # Cache storage
        self._categories_cache: Optional[List[KalshiCategory]] = None
        self._categories_cache_time: Optional[datetime] = None
        self._events_cache: Dict[str, List[KalshiEvent]] = {}
        self._markets_cache: Dict[str, KalshiMarket] = {}
        
        # Stats
        self.last_sync_time: Optional[datetime] = None
        self.total_events: int = 0
        self.total_markets: int = 0
        self.sync_errors: List[str] = []
        
        logger.info(f"KalshiBasketballIngestor initialized (use_demo={use_demo})")
    
    async def connect(self):
        """Initialize HTTP client"""
        if not self._client:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )
            logger.info("Kalshi HTTP client connected")
    
    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Kalshi HTTP client closed")
    
    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make API request with rate limiting.
        
        Public endpoints don't require authentication.
        """
        if not self._client:
            await self.connect()
        
        url = f"{self.base_url}{path}"
        
        try:
            await asyncio.sleep(self.REQUEST_DELAY)  # Rate limiting
            
            response = await self._client.request(
                method=method,
                url=url,
                params=params
            )
            
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
            self.sync_errors.append(str(e))
            return {}
    
    # ==========================================
    # CATEGORY DISCOVERY
    # ==========================================
    
    async def discover_basketball_categories(self) -> List[KalshiCategory]:
        """
        Discover all basketball categories from Kalshi.
        
        Returns the full tree structure:
        Basketball
        ├── Adriatic ABA League
        ├── College Basketball (M)
        ├── College Basketball (W)
        ├── EuroLeague
        ├── Germany BBL
        ├── Pro Basketball (M) / NBA
        └── etc.
        """
        # Check cache (5 min TTL)
        if (self._categories_cache and self._categories_cache_time and
            (datetime.now(timezone.utc) - self._categories_cache_time).seconds < 300):
            return self._categories_cache
        
        logger.info("Discovering basketball categories...")
        
        # Get sports filters to find basketball categories
        await self._request("GET", "/events", params={
            "status": "open",
            "limit": 1,
            "with_nested_markets": False
        })
        
        # Build category tree from series data
        series_response = await self._request("GET", "/series", params={
            "limit": 200
        })
        
        series_list = series_response.get("series", [])
        
        # Filter basketball series
        basketball_keywords = [
            "basketball", "nba", "ncaa", "euroleague", "aba", "bbl",
            "lakers", "celtics", "warriors", "heat", "bucks", "nuggets",
            "march madness", "college hoops"
        ]
        
        categories: Dict[str, KalshiCategory] = {}
        
        # Root basketball category
        root = KalshiCategory(
            id="basketball",
            name="Basketball",
            slug="basketball"
        )
        categories["basketball"] = root
        
        for series in series_list:
            title_lower = series.get("title", "").lower()
            category = series.get("category", "").lower()
            
            # Check if basketball related
            is_basketball = any(kw in title_lower or kw in category for kw in basketball_keywords)
            
            if is_basketball:
                series_ticker = series.get("ticker", "")
                
                # Determine subcategory
                subcategory_id = self._categorize_series(title_lower, series_ticker)
                
                if subcategory_id not in categories:
                    categories[subcategory_id] = KalshiCategory(
                        id=subcategory_id,
                        name=self._format_category_name(subcategory_id),
                        slug=subcategory_id,
                        parent_id="basketball"
                    )
                
                categories[subcategory_id].market_count += series.get("volume", 0)
        
        # Build tree
        for cat_id, cat in categories.items():
            if cat.parent_id == "basketball" and cat_id != "basketball":
                root.children.append(cat)
        
        self._categories_cache = [root]
        self._categories_cache_time = datetime.now(timezone.utc)
        
        logger.info(f"Discovered {len(root.children)} basketball subcategories")
        
        return self._categories_cache
    
    def _categorize_series(self, title: str, ticker: str) -> str:
        """Categorize a series into a subcategory"""
        title = title.lower()
        ticker = ticker.lower()
        
        if "ncaa" in title or "college" in title or "march madness" in title:
            if "women" in title or "womens" in title or "ncaaw" in ticker:
                return "ncaa-womens-basketball"
            return "ncaa-mens-basketball"
        elif "euroleague" in title or "europe" in title:
            return "euroleague"
        elif "aba" in title or "adriatic" in title:
            return "aba-league"
        elif "bbl" in title or "germany" in title:
            return "germany-bbl"
        elif "nba" in title or "lakers" in title or "celtics" in title:
            return "nba"
        else:
            return "other-basketball"
    
    def _format_category_name(self, slug: str) -> str:
        """Format slug to display name"""
        names = {
            "nba": "Pro Basketball (M) / NBA",
            "ncaa-mens-basketball": "College Basketball (M)",
            "ncaa-womens-basketball": "College Basketball (W)",
            "euroleague": "EuroLeague",
            "aba-league": "Adriatic ABA League",
            "germany-bbl": "Germany BBL",
            "other-basketball": "Other Basketball"
        }
        return names.get(slug, slug.replace("-", " ").title())
    
    # ==========================================
    # EVENT DISCOVERY
    # ==========================================
    
    async def fetch_all_basketball_events(
        self,
        status: Optional[str] = None,
        include_historical: bool = True,
        days_back: int = 60
    ) -> List[KalshiEvent]:
        """
        Fetch all basketball events with pagination.
        
        Args:
            status: Filter by status (open, closed, settled)
            include_historical: Include historical data for backtesting
            days_back: How many days of historical data to fetch
            
        Returns:
            List of all basketball events
        """
        logger.info(f"Fetching basketball events (status={status}, historical={include_historical})...")
        
        all_events: List[KalshiEvent] = []
        cursor = None
        page = 0
        
        while True:
            params = {
                "limit": 200,
                "with_nested_markets": True
            }
            
            if cursor:
                params["cursor"] = cursor
            if status:
                params["status"] = status
            
            response = await self._request("GET", "/events", params=params)
            
            events_data = response.get("events", [])
            cursor = response.get("cursor")
            
            if not events_data:
                break
            
            # Filter basketball events
            for event_data in events_data:
                if self._is_basketball_event(event_data):
                    event = self._parse_event(event_data)
                    if event:
                        all_events.append(event)
            
            page += 1
            logger.info(f"Fetched page {page}, {len(all_events)} basketball events so far")
            
            if not cursor:
                break
            
            # Safety limit
            if page > 50:
                logger.warning("Hit page limit, stopping pagination")
                break
        
        logger.info(f"Total basketball events fetched: {len(all_events)}")
        
        return all_events
    
    def _is_basketball_event(self, event_data: Dict) -> bool:
        """Check if event is basketball related"""
        title = event_data.get("title", "").lower()
        category = event_data.get("category", "").lower()
        series = event_data.get("series_ticker", "").lower()
        
        basketball_keywords = [
            "basketball", "nba", "ncaa", "euroleague", "aba", "bbl",
            "lakers", "celtics", "warriors", "heat", "bucks", "nuggets",
            "76ers", "knicks", "nets", "bulls", "hawks", "hornets",
            "march madness", "college hoops", "points scored"
        ]
        
        return any(kw in title or kw in category or kw in series for kw in basketball_keywords)
    
    def _parse_event(self, data: Dict) -> Optional[KalshiEvent]:
        """Parse event data into KalshiEvent model"""
        try:
            markets = data.get("markets", [])
            market_tickers = [m.get("ticker", "") for m in markets if m.get("ticker")]
            
            return KalshiEvent(
                ticker=data.get("ticker", ""),
                title=data.get("title", ""),
                subtitle=data.get("subtitle"),
                category=data.get("category", ""),
                series_ticker=data.get("series_ticker", ""),
                status=data.get("status", "unknown"),
                mutually_exclusive=data.get("mutually_exclusive", True),
                markets=market_tickers,
                volume=sum(m.get("volume", 0) for m in markets)
            )
        except Exception as e:
            logger.error(f"Error parsing event: {e}")
            return None
    
    # ==========================================
    # MARKET DISCOVERY
    # ==========================================
    
    async def fetch_all_basketball_markets(
        self,
        status: Optional[str] = None
    ) -> List[KalshiMarket]:
        """
        Fetch all basketball markets with pagination.
        
        Returns:
            List of all basketball markets
        """
        logger.info(f"Fetching basketball markets (status={status})...")
        
        all_markets: List[KalshiMarket] = []
        cursor = None
        page = 0
        
        while True:
            params = {"limit": 200}
            
            if cursor:
                params["cursor"] = cursor
            if status:
                params["status"] = status
            
            response = await self._request("GET", "/markets", params=params)
            
            markets_data = response.get("markets", [])
            cursor = response.get("cursor")
            
            if not markets_data:
                break
            
            # Filter basketball markets
            for market_data in markets_data:
                if self._is_basketball_market(market_data):
                    market = self._parse_market(market_data)
                    if market:
                        all_markets.append(market)
                        self._markets_cache[market.ticker] = market
            
            page += 1
            logger.info(f"Fetched page {page}, {len(all_markets)} basketball markets so far")
            
            if not cursor:
                break
            
            # Safety limit
            if page > 100:
                logger.warning("Hit page limit, stopping pagination")
                break
        
        logger.info(f"Total basketball markets fetched: {len(all_markets)}")
        
        return all_markets
    
    def _is_basketball_market(self, market_data: Dict) -> bool:
        """Check if market is basketball related"""
        title = market_data.get("title", "").lower()
        category = market_data.get("category", "").lower()
        ticker = market_data.get("ticker", "").lower()
        
        basketball_keywords = [
            "basketball", "nba", "ncaa", "euroleague", "aba", "bbl",
            "points", "score", "win", "spread", "total",
            "lakers", "celtics", "warriors", "heat"
        ]
        
        return any(kw in title or kw in category or kw in ticker for kw in basketball_keywords)
    
    def _parse_market(self, data: Dict) -> Optional[KalshiMarket]:
        """Parse market data into KalshiMarket model"""
        try:
            return KalshiMarket(
                ticker=data.get("ticker", ""),
                event_ticker=data.get("event_ticker", ""),
                series_ticker=data.get("series_ticker", ""),
                category=data.get("category", ""),
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
                settlement_value=data.get("settlement_value"),
                result=data.get("result"),
                league=self._extract_league(data)
            )
        except Exception as e:
            logger.error(f"Error parsing market: {e}")
            return None
    
    def _extract_league(self, data: Dict) -> str:
        """Extract league from market data"""
        title = data.get("title", "").lower()
        ticker = data.get("ticker", "").lower()
        
        if "ncaa" in title or "college" in title:
            if "women" in title:
                return "NCAA_W"
            return "NCAA_M"
        elif "nba" in title or "nba" in ticker:
            return "NBA"
        elif "euroleague" in title:
            return "EUROLEAGUE"
        elif "aba" in title:
            return "ABA"
        else:
            return "OTHER"
    
    # ==========================================
    # ORDER BOOK
    # ==========================================
    
    async def get_orderbook(self, market_ticker: str) -> Optional[OrderBookSnapshot]:
        """
        Get order book for a specific market.
        
        Args:
            market_ticker: Market ticker
            
        Returns:
            OrderBookSnapshot with bid/ask data
        """
        response = await self._request("GET", f"/markets/{market_ticker}/orderbook")
        
        if not response:
            return None
        
        orderbook = response.get("orderbook", {})
        
        yes_bids = [(b[0], b[1]) for b in orderbook.get("yes", [])]
        no_bids = [(b[0], b[1]) for b in orderbook.get("no", [])]
        
        # Calculate best prices
        best_yes_bid = yes_bids[-1][0] if yes_bids else None
        best_no_bid = no_bids[-1][0] if no_bids else None
        best_yes_ask = (100 - best_no_bid) if best_no_bid else None
        best_no_ask = (100 - best_yes_bid) if best_yes_bid else None
        
        # Calculate spread
        spread = None
        if best_yes_bid and best_yes_ask:
            spread = best_yes_ask - best_yes_bid
        
        # Total liquidity
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
    
    async def full_sync(self) -> Dict[str, Any]:
        """
        Perform full synchronization of all basketball data.
        
        Returns sync status report.
        """
        logger.info("Starting full basketball data sync...")
        
        start_time = datetime.now(timezone.utc)
        self.sync_errors = []
        
        # Discover categories
        categories = await self.discover_basketball_categories()
        
        # Fetch events
        events = await self.fetch_all_basketball_events(status="open")
        historical_events = await self.fetch_all_basketball_events(status="closed")
        
        all_events = events + historical_events
        
        # Fetch markets
        markets = await self.fetch_all_basketball_markets()
        
        # Store to MongoDB if available
        if self.db is not None:
            await self._store_to_db(categories, all_events, markets)
        
        self.last_sync_time = datetime.now(timezone.utc)
        self.total_events = len(all_events)
        self.total_markets = len(markets)
        
        sync_duration = (self.last_sync_time - start_time).total_seconds()
        
        report = {
            "success": len(self.sync_errors) == 0,
            "sync_time": self.last_sync_time.isoformat(),
            "duration_seconds": sync_duration,
            "categories_count": len(categories[0].children) if categories else 0,
            "events_count": len(all_events),
            "open_events": len(events),
            "closed_events": len(historical_events),
            "markets_count": len(markets),
            "errors": self.sync_errors[:10]  # First 10 errors
        }
        
        logger.info(f"Full sync complete: {report}")
        
        return report
    
    async def _store_to_db(
        self,
        categories: List[KalshiCategory],
        events: List[KalshiEvent],
        markets: List[KalshiMarket]
    ):
        """Store synced data to MongoDB"""
        if self.db is None:
            logger.warning("No database configured, skipping storage")
            return
            
        try:
            # Categories
            if categories:
                cat_docs = []
                for root in categories:
                    cat_docs.append(self._category_to_doc(root))
                    for child in root.children:
                        cat_docs.append(self._category_to_doc(child))
                
                await self.db.kalshi_categories.delete_many({})
                if cat_docs:
                    await self.db.kalshi_categories.insert_many(cat_docs)
            
            # Events - upsert
            for event in events:
                await self.db.kalshi_events.update_one(
                    {"ticker": event.ticker},
                    {"$set": event.dict()},
                    upsert=True
                )
            
            # Markets - upsert
            for market in markets:
                await self.db.kalshi_markets.update_one(
                    {"ticker": market.ticker},
                    {"$set": market.dict()},
                    upsert=True
                )
            
            logger.info(f"Stored to DB: {len(events)} events, {len(markets)} markets")
            
        except Exception as e:
            logger.error(f"DB storage error: {e}")
            self.sync_errors.append(f"DB storage: {str(e)}")
    
    def _category_to_doc(self, cat: KalshiCategory) -> Dict:
        """Convert category to MongoDB document"""
        return {
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "parent_id": cat.parent_id,
            "market_count": cat.market_count,
            "event_count": cat.event_count,
            "updated_at": datetime.now(timezone.utc)
        }
    
    # ==========================================
    # GETTERS (From Cache or DB)
    # ==========================================
    
    async def get_categories(self) -> List[Dict]:
        """Get all basketball categories"""
        if self.db is not None:
            cursor = self.db.kalshi_categories.find({}, {"_id": 0})
            return await cursor.to_list(length=100)
        
        if self._categories_cache:
            result = []
            for root in self._categories_cache:
                result.append(root.dict())
                for child in root.children:
                    result.append(child.dict())
            return result
        
        return []
    
    async def get_events(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict]:
        """Get events with filtering"""
        if self.db is not None:
            query = {}
            if category:
                query["category"] = {"$regex": category, "$options": "i"}
            if status:
                query["status"] = status
            
            cursor = self.db.kalshi_events.find(query, {"_id": 0}).skip(skip).limit(limit)
            return await cursor.to_list(length=limit)
        
        return []
    
    async def get_markets(
        self,
        event_ticker: Optional[str] = None,
        league: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict]:
        """Get markets with filtering"""
        if self.db is not None:
            query = {}
            if event_ticker:
                query["event_ticker"] = event_ticker
            if league:
                query["league"] = league
            if status:
                query["status"] = status
            
            cursor = self.db.kalshi_markets.find(query, {"_id": 0}).skip(skip).limit(limit)
            return await cursor.to_list(length=limit)
        
        return []
    
    async def get_market_by_ticker(self, ticker: str) -> Optional[Dict]:
        """Get single market by ticker"""
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
            "total_events": self.total_events,
            "total_markets": self.total_markets,
            "cached_markets": len(self._markets_cache),
            "recent_errors": self.sync_errors[-5:]
        }


# Global instance
kalshi_ingestor: Optional[KalshiBasketballIngestor] = None
