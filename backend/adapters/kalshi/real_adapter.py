"""
Real Kalshi Adapter
Live trading implementation for Kalshi prediction market API.
"""
import httpx
import hashlib
import base64
import time
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from .interface import KalshiAdapter
from models.market import Market, OrderBook
from models.position import Position
from models.trade import Trade

logger = logging.getLogger(__name__)


class RealKalshiAdapter(KalshiAdapter):
    """
    Real Kalshi API adapter for live trading.
    Uses Kalshi's REST API for market data and trading.
    """
    
    def __init__(
        self,
        api_key: str,
        private_key: str,
        base_url: str = "https://api.elections.kalshi.com/trade-api/v2",
        demo_mode: bool = False
    ):
        self.api_key = api_key
        self.private_key = private_key
        self.base_url = base_url
        if demo_mode:
            self.base_url = "https://demo-api.kalshi.co/trade-api/v2"
        
        self.client = httpx.AsyncClient(timeout=30.0)
        self._token = None
        self._token_expiry = 0
        
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Generate authentication headers for Kalshi API"""
        # For API key auth (simpler method)
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict:
        """Make authenticated request to Kalshi API"""
        url = f"{self.base_url}{endpoint}"
        headers = await self._get_auth_headers()
        
        try:
            if method == "GET":
                response = await self.client.get(url, headers=headers, params=params)
            elif method == "POST":
                response = await self.client.post(url, headers=headers, json=data)
            elif method == "DELETE":
                response = await self.client.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Kalshi API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Kalshi request failed: {e}")
            raise
    
    # Market Data
    async def get_markets_for_game(self, game_id: str) -> List[Market]:
        """Get all Kalshi markets for a specific game"""
        try:
            # Search for NBA-related markets
            # Kalshi uses event tickers like "NBA-*" for basketball
            params = {
                "status": "open",
                "series_ticker": "NBA"  # Adjust based on actual Kalshi API
            }
            result = await self._request("GET", "/markets", params=params)
            
            markets = []
            for m in result.get("markets", []):
                # Filter for this specific game if possible
                if game_id.replace("nba_", "") in m.get("ticker", "").lower():
                    market = Market(
                        id=m["ticker"],
                        game_id=game_id,
                        event_name=m.get("title", ""),
                        outcome="home",  # Determine from market title
                        yes_price=m.get("yes_ask", 0.5),
                        no_price=m.get("no_ask", 0.5),
                        volume=m.get("volume", 0),
                        open_interest=m.get("open_interest", 0),
                        implied_probability=m.get("yes_ask", 0.5),
                        last_updated=datetime.utcnow()
                    )
                    markets.append(market)
            
            return markets
        except Exception as e:
            logger.error(f"Failed to get markets for game {game_id}: {e}")
            return []
    
    async def get_market(self, market_id: str) -> Optional[Market]:
        """Get a specific market by ID"""
        try:
            result = await self._request("GET", f"/markets/{market_id}")
            m = result.get("market", {})
            
            return Market(
                id=m["ticker"],
                game_id=m.get("event_ticker", ""),
                event_name=m.get("title", ""),
                outcome="home",
                yes_price=m.get("yes_ask", 0.5),
                no_price=m.get("no_ask", 0.5),
                volume=m.get("volume", 0),
                open_interest=m.get("open_interest", 0),
                implied_probability=m.get("yes_ask", 0.5),
                last_updated=datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Failed to get market {market_id}: {e}")
            return None
    
    async def get_orderbook(self, market_id: str) -> Optional[OrderBook]:
        """Get the orderbook for a market"""
        try:
            result = await self._request("GET", f"/markets/{market_id}/orderbook")
            
            return OrderBook(
                market_id=market_id,
                yes_bids=[(b["price"], b["quantity"]) for b in result.get("yes", {}).get("bids", [])],
                yes_asks=[(a["price"], a["quantity"]) for a in result.get("yes", {}).get("asks", [])],
                no_bids=[(b["price"], b["quantity"]) for b in result.get("no", {}).get("bids", [])],
                no_asks=[(a["price"], a["quantity"]) for a in result.get("no", {}).get("asks", [])],
                last_updated=datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Failed to get orderbook for {market_id}: {e}")
            return None
    
    async def get_market_price(self, market_id: str) -> Optional[float]:
        """Get current YES price for a market"""
        market = await self.get_market(market_id)
        return market.yes_price if market else None
    
    # Positions
    async def get_positions(self) -> List[Position]:
        """Get all open positions"""
        try:
            result = await self._request("GET", "/portfolio/positions")
            
            positions = []
            for p in result.get("market_positions", []):
                if p.get("position", 0) != 0:
                    position = Position(
                        id=f"pos_{p['ticker']}",
                        market_id=p["ticker"],
                        side="yes" if p["position"] > 0 else "no",
                        quantity=abs(p["position"]),
                        avg_entry_price=p.get("average_price", 0) / 100,  # Kalshi uses cents
                        current_price=p.get("market_exposure", 0) / abs(p["position"]) / 100 if p["position"] != 0 else 0,
                        unrealized_pnl=p.get("total_traded", 0) / 100,
                        realized_pnl=p.get("realized_pnl", 0) / 100,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    positions.append(position)
            
            return positions
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    async def get_position(self, market_id: str) -> Optional[Position]:
        """Get position for a specific market"""
        positions = await self.get_positions()
        for p in positions:
            if p.market_id == market_id:
                return p
        return None
    
    # Trading
    async def place_order(
        self,
        market_id: str,
        side: str,
        direction: str,
        quantity: int,
        price: Optional[float] = None
    ) -> Trade:
        """Place a trade order"""
        try:
            # Kalshi uses cents for prices
            order_data = {
                "ticker": market_id,
                "action": direction,  # "buy" or "sell"
                "side": side,  # "yes" or "no"
                "count": quantity,
                "type": "market" if price is None else "limit"
            }
            
            if price is not None:
                order_data["price"] = int(price * 100)  # Convert to cents
            
            result = await self._request("POST", "/portfolio/orders", data=order_data)
            order = result.get("order", {})
            
            return Trade(
                id=order.get("order_id", f"trade_{int(time.time())}"),
                market_id=market_id,
                game_id="",  # Would need to look up
                side=side,
                direction=direction,
                quantity=quantity,
                price=order.get("price", 0) / 100,
                total_cost=order.get("price", 0) * quantity / 100,
                status="filled" if order.get("status") == "executed" else order.get("status", "pending"),
                order_type="market" if price is None else "limit",
                created_at=datetime.utcnow(),
                filled_at=datetime.utcnow() if order.get("status") == "executed" else None
            )
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            raise
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order"""
        try:
            await self._request("DELETE", f"/portfolio/orders/{order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    async def flatten_position(self, market_id: str) -> List[Trade]:
        """Close all positions in a market"""
        trades = []
        position = await self.get_position(market_id)
        
        if position and position.quantity > 0:
            # Sell to close
            opposite_direction = "sell" if position.side == "yes" else "buy"
            trade = await self.place_order(
                market_id=market_id,
                side=position.side,
                direction=opposite_direction,
                quantity=position.quantity
            )
            trades.append(trade)
        
        return trades
    
    # Account
    async def get_balance(self) -> float:
        """Get account balance"""
        try:
            result = await self._request("GET", "/portfolio/balance")
            return result.get("balance", 0) / 100  # Convert from cents
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return 0.0
    
    async def get_portfolio_value(self) -> float:
        """Get total portfolio value"""
        try:
            result = await self._request("GET", "/portfolio/balance")
            balance = result.get("balance", 0) / 100
            
            # Add position values
            positions = await self.get_positions()
            position_value = sum(p.quantity * p.current_price for p in positions)
            
            return balance + position_value
        except Exception as e:
            logger.error(f"Failed to get portfolio value: {e}")
            return await self.get_balance()
    
    def is_paper_mode(self) -> bool:
        """This is NOT paper mode - real money"""
        return False
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def validate_credentials(self) -> Dict[str, Any]:
        """Validate API credentials by making a test request"""
        try:
            result = await self._request("GET", "/portfolio/balance")
            return {
                "valid": True,
                "balance": result.get("balance", 0) / 100,
                "message": "API credentials validated successfully"
            }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return {
                    "valid": False,
                    "message": "Invalid API credentials"
                }
            return {
                "valid": False,
                "message": f"API error: {e.response.status_code}"
            }
        except Exception as e:
            return {
                "valid": False,
                "message": f"Connection failed: {str(e)}"
            }
