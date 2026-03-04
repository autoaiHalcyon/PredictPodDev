"""
Kalshi Sandbox Adapter
Connects to Kalshi Demo API for safe testing with mock funds.
Falls back to Full Lifecycle Simulation if demo API unavailable.
"""
import os
import time
import hmac
import base64
import hashlib
import asyncio
import logging
import random
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
import httpx
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding

from adapters.kalshi.interface import KalshiAdapter
from models.market import Market, MarketType, OrderBook
from models.position import Position
from models.trade import Trade, TradeStatus, TradeSide, TradeDirection
from models.order_lifecycle import (
    LiveOrder, OrderState, OrderFill, OrderType, OrderSide, OrderAction
)

logger = logging.getLogger(__name__)


class KalshiAdapterSandbox(KalshiAdapter):
    """
    Sandbox adapter for Kalshi Demo API.
    Uses demo-api.kalshi.co with mock funds.
    
    If demo API is unavailable, provides Full Lifecycle Simulation Mode.
    """
    
    DEMO_BASE_URL = "https://demo-api.kalshi.co/trade-api/v2"
    
    def __init__(
        self,
        api_key: str = "",
        private_key: str = "",
        simulation_mode: bool = True  # Default to simulation if no credentials
    ):
        self.api_key = api_key
        self.private_key_pem = private_key
        self.private_key = None
        self.simulation_mode = simulation_mode
        self.demo_connected = False
        
        # Simulation state (used when demo API unavailable)
        self._sim_balance = 10000.0  # $100 in demo funds
        self._sim_positions: Dict[str, Position] = {}
        self._sim_orders: Dict[str, LiveOrder] = {}
        self._sim_order_queue: List[Tuple[str, float, OrderFill]] = []  # (order_id, fill_time, fill)
        
        # HTTP client
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Parse private key if provided
        if private_key:
            try:
                self.private_key = serialization.load_pem_private_key(
                    private_key.encode() if isinstance(private_key, str) else private_key,
                    password=None
                )
                self.simulation_mode = False
            except Exception as e:
                logger.warning(f"Failed to parse private key, using simulation: {e}")
                self.simulation_mode = True
    
    async def connect(self) -> bool:
        """
        Try to connect to demo API.
        Returns True if connected, False if falling back to simulation.
        """
        if self.simulation_mode or not self.api_key:
            logger.info("Sandbox running in SIMULATION mode (no API credentials)")
            return False
        
        try:
            result = await self._request("GET", "/portfolio/balance")
            if result and "balance" in result:
                self._sim_balance = result["balance"] / 100  # Cents to dollars
                self.demo_connected = True
                logger.info(f"Connected to Kalshi Demo API. Balance: ${self._sim_balance:.2f}")
                return True
        except Exception as e:
            logger.warning(f"Could not connect to Demo API, using simulation: {e}")
        
        self.simulation_mode = True
        return False
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    def _sign_request(self, method: str, path: str, timestamp: str) -> str:
        """Sign request using RSA-PSS-SHA256."""
        if not self.private_key:
            return ""
        
        message = f"{timestamp}{method}{path}".encode()
        
        signature = self.private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return base64.b64encode(signature).decode()
    
    async def _request(
        self,
        method: str,
        path: str,
        data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Make authenticated request to Demo API."""
        url = f"{self.DEMO_BASE_URL}{path}"
        timestamp = str(int(time.time() * 1000))
        signature = self._sign_request(method, path, timestamp)
        
        headers = {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }
        
        try:
            if method == "GET":
                response = await self.client.get(url, headers=headers)
            elif method == "POST":
                response = await self.client.post(url, headers=headers, json=data)
            elif method == "DELETE":
                response = await self.client.delete(url, headers=headers)
            else:
                return None
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Demo API request failed: {e}")
            return None
    
    # ============================================
    # MARKET DATA
    # ============================================
    
    async def get_markets_for_game(self, game_id: str) -> List[Market]:
        """Get markets for a game (simulation mode returns mock markets)."""
        if self.simulation_mode:
            return self._sim_get_markets(game_id)
        
        # Try demo API
        try:
            result = await self._request("GET", f"/events/{game_id}")
            if result and "markets" in result:
                markets = []
                for m in result["markets"]:
                    markets.append(Market(
                        id=m["ticker"],
                        game_id=game_id,
                        type=MarketType.MONEYLINE,
                        ticker=m["ticker"],
                        title=m.get("title", ""),
                        yes_price=m.get("yes_bid", 50) / 100,
                        no_price=m.get("no_bid", 50) / 100,
                        volume=m.get("volume", 0)
                    ))
                return markets
        except Exception as e:
            logger.error(f"Failed to get markets: {e}")
        
        return self._sim_get_markets(game_id)
    
    def _sim_get_markets(self, game_id: str) -> List[Market]:
        """Simulated markets."""
        return [
            Market(
                id=f"SANDBOX-{game_id}-ML",
                game_id=game_id,
                type=MarketType.MONEYLINE,
                ticker=f"SANDBOX-{game_id}-ML",
                title="Moneyline Market",
                yes_price=0.50 + random.uniform(-0.1, 0.1),
                no_price=0.50 + random.uniform(-0.1, 0.1),
                volume=random.randint(1000, 10000)
            )
        ]
    
    async def get_market(self, market_id: str) -> Optional[Market]:
        """Get specific market."""
        if self.simulation_mode:
            return Market(
                id=market_id,
                game_id="sandbox",
                type=MarketType.MONEYLINE,
                ticker=market_id,
                title="Sandbox Market",
                yes_price=0.50 + random.uniform(-0.05, 0.05),
                no_price=0.50 + random.uniform(-0.05, 0.05),
                volume=random.randint(1000, 10000)
            )
        
        try:
            result = await self._request("GET", f"/markets/{market_id}")
            if result:
                return Market(
                    id=result["ticker"],
                    game_id=result.get("event_ticker", ""),
                    type=MarketType.MONEYLINE,
                    ticker=result["ticker"],
                    title=result.get("title", ""),
                    yes_price=result.get("yes_bid", 50) / 100,
                    no_price=result.get("no_bid", 50) / 100,
                    volume=result.get("volume", 0)
                )
        except Exception:
            pass
        
        return None
    
    async def get_orderbook(self, market_id: str) -> Optional[OrderBook]:
        """Get orderbook for slippage/liquidity checks."""
        if self.simulation_mode:
            return self._sim_get_orderbook(market_id)
        
        try:
            result = await self._request("GET", f"/markets/{market_id}/orderbook")
            if result:
                from models.market import OrderBookLevel
                return OrderBook(
                    bids=[OrderBookLevel(price=b[0]/100, quantity=b[1]) for b in result.get("yes", [])[:5]],
                    asks=[OrderBookLevel(price=a[0]/100, quantity=a[1]) for a in result.get("no", [])[:5]]
                )
        except Exception:
            pass
        
        return self._sim_get_orderbook(market_id)
    
    def _sim_get_orderbook(self, market_id: str) -> OrderBook:
        """Simulated orderbook with realistic depth."""
        from models.market import OrderBookLevel
        mid_price = 0.50
        bids = [
            OrderBookLevel(price=mid_price - i * 0.02, quantity=random.randint(50, 200))
            for i in range(5)
        ]
        asks = [
            OrderBookLevel(price=mid_price + i * 0.02 + 0.02, quantity=random.randint(50, 200))
            for i in range(5)
        ]
        return OrderBook(
            bids=bids,
            asks=asks
        )
    
    async def get_market_price(self, market_id: str) -> Optional[float]:
        """Get current YES price."""
        market = await self.get_market(market_id)
        return market.yes_price if market else None
    
    # ============================================
    # POSITIONS
    # ============================================
    
    async def get_positions(self) -> List[Position]:
        """Get all positions."""
        if self.simulation_mode:
            return list(self._sim_positions.values())
        
        try:
            result = await self._request("GET", "/portfolio/positions")
            if result and "market_positions" in result:
                positions = []
                for p in result["market_positions"]:
                    positions.append(Position(
                        market_id=p["ticker"],
                        side=TradeSide.YES if p.get("position", 0) > 0 else TradeSide.NO,
                        quantity=abs(p.get("position", 0)),
                        avg_price=p.get("market_exposure", 0) / max(abs(p.get("position", 0)), 1) / 100,
                        current_price=p.get("market_exposure", 0) / 100
                    ))
                return positions
        except Exception:
            pass
        
        return list(self._sim_positions.values())
    
    async def get_position(self, market_id: str) -> Optional[Position]:
        """Get position for specific market."""
        if self.simulation_mode:
            return self._sim_positions.get(market_id)
        
        positions = await self.get_positions()
        return next((p for p in positions if p.market_id == market_id), None)
    
    # ============================================
    # TRADING - Full Lifecycle
    # ============================================
    
    async def place_order(
        self,
        market_id: str,
        side: str,
        direction: str,
        quantity: int,
        price: Optional[float] = None,
        idempotency_key: Optional[str] = None
    ) -> Trade:
        """
        Place order with full lifecycle simulation.
        Returns immediately with SUBMITTED status.
        Order progresses through states asynchronously.
        """
        if self.simulation_mode:
            return await self._sim_place_order(
                market_id, side, direction, quantity, price, idempotency_key
            )
        
        # Try demo API
        try:
            order_data = {
                "ticker": market_id,
                "action": direction,
                "type": "limit" if price else "market",
                "count": quantity
            }
            
            if price:
                if side == "yes":
                    order_data["yes_price"] = int(price * 100)
                else:
                    order_data["no_price"] = int(price * 100)
            
            result = await self._request("POST", "/portfolio/orders", order_data)
            
            if result and "order" in result:
                o = result["order"]
                return Trade(
                    id=o.get("order_id", ""),
                    game_id="sandbox",
                    market_id=market_id,
                    side=TradeSide.YES if side == "yes" else TradeSide.NO,
                    direction=TradeDirection.BUY if direction == "buy" else TradeDirection.SELL,
                    quantity=quantity,
                    price=price or 0.50,
                    status=TradeStatus.FILLED if o.get("status") == "filled" else TradeStatus.PENDING,
                    is_paper=True
                )
        except Exception as e:
            logger.error(f"Demo API order failed: {e}")
        
        # Fall back to simulation
        return await self._sim_place_order(
            market_id, side, direction, quantity, price, idempotency_key
        )
    
    async def _sim_place_order(
        self,
        market_id: str,
        side: str,
        direction: str,
        quantity: int,
        price: Optional[float],
        idempotency_key: Optional[str]
    ) -> Trade:
        """
        Simulated order placement with realistic lifecycle.
        Simulates: delays, partial fills, rejections, rate limits.
        """
        import uuid
        order_id = str(uuid.uuid4())
        price = price or (0.50 + random.uniform(-0.05, 0.05))
        
        # Simulate rate limit (5% chance)
        if random.random() < 0.05:
            logger.warning(f"SIMULATION: Rate limit hit for order {order_id}")
            return Trade(
                id=order_id,
                game_id="sandbox",
                market_id=market_id,
                side=TradeSide.YES if side == "yes" else TradeSide.NO,
                direction=TradeDirection.BUY if direction == "buy" else TradeDirection.SELL,
                quantity=quantity,
                price=price,
                status=TradeStatus.REJECTED,
                is_paper=True
            )
        
        # Simulate rejection (3% chance)
        if random.random() < 0.03:
            logger.warning(f"SIMULATION: Order rejected {order_id}")
            return Trade(
                id=order_id,
                game_id="sandbox",
                market_id=market_id,
                side=TradeSide.YES if side == "yes" else TradeSide.NO,
                direction=TradeDirection.BUY if direction == "buy" else TradeDirection.SELL,
                quantity=quantity,
                price=price,
                status=TradeStatus.REJECTED,
                is_paper=True
            )
        
        # Create simulated order with lifecycle
        order = LiveOrder(
            id=order_id,
            idempotency_key=idempotency_key or order_id,
            market_id=market_id,
            market_ticker=market_id,
            side=OrderSide.YES if side == "yes" else OrderSide.NO,
            action=OrderAction.BUY if direction == "buy" else OrderAction.SELL,
            order_type=OrderType.LIMIT if price else OrderType.MARKET,
            quantity=quantity,
            price_cents=int(price * 100),
            state=OrderState.SUBMITTED,
            adapter_mode="sandbox"
        )
        
        self._sim_orders[order_id] = order
        
        # Schedule fill simulation (10% partial, 85% full, 5% never fills)
        fill_type = random.choices(
            ["full", "partial", "none"],
            weights=[0.85, 0.10, 0.05]
        )[0]
        
        if fill_type == "full":
            # Full fill after 0.5-2 seconds
            delay = random.uniform(0.5, 2.0)
            asyncio.create_task(self._simulate_fill(order_id, quantity, price, delay))
        elif fill_type == "partial":
            # Partial fill, then complete
            partial_qty = random.randint(1, quantity - 1)
            asyncio.create_task(self._simulate_fill(order_id, partial_qty, price, 0.5))
            asyncio.create_task(self._simulate_fill(order_id, quantity - partial_qty, price, 2.0))
        
        # Update balance immediately (pessimistic)
        cost = quantity * price
        if direction == "buy":
            self._sim_balance -= cost
        
        logger.info(f"SIMULATION: Order submitted {order_id}, type={fill_type}")
        
        return Trade(
            id=order_id,
            game_id="sandbox",
            market_id=market_id,
            side=TradeSide.YES if side == "yes" else TradeSide.NO,
            direction=TradeDirection.BUY if direction == "buy" else TradeDirection.SELL,
            quantity=quantity,
            price=price,
            status=TradeStatus.PENDING,
            is_paper=True
        )
    
    async def _simulate_fill(
        self,
        order_id: str,
        quantity: int,
        price: float,
        delay: float
    ):
        """Simulate fill after delay."""
        await asyncio.sleep(delay)
        
        order = self._sim_orders.get(order_id)
        if not order or order.is_terminal:
            return
        
        # Add slippage (±2%)
        fill_price = price * (1 + random.uniform(-0.02, 0.02))
        
        fill = OrderFill(
            quantity=quantity,
            price_cents=int(fill_price * 100),
            fee_cents=int(quantity * fill_price * 0.01)  # 1% fee
        )
        
        order.add_fill(fill)
        
        # Update position
        if order.state == OrderState.FILLED:
            self._update_sim_position(order)
        
        logger.info(f"SIMULATION: Fill {order_id}: {quantity} @ {fill_price:.2f}¢")
    
    def _update_sim_position(self, order: LiveOrder):
        """Update simulated position after fill."""
        market_id = order.market_id
        side = order.side.value
        action = order.action.value
        qty = order.filled_quantity
        price = order.avg_fill_price_cents / 100
        
        existing = self._sim_positions.get(market_id)
        
        if action == "buy":
            if existing:
                # Add to position
                new_qty = existing.quantity + qty
                new_avg = (existing.quantity * existing.avg_entry_price + qty * price) / new_qty
                existing.quantity = new_qty
                existing.avg_entry_price = new_avg
            else:
                # Generate a fake game_id for sandbox positions
                game_id = f"SANDBOX-{market_id}"
                self._sim_positions[market_id] = Position(
                    game_id=game_id,
                    market_id=market_id,
                    side="yes" if side == "yes" else "no",
                    quantity=qty,
                    avg_entry_price=price,
                    current_price=price
                )
        elif action == "sell" and existing:
            existing.quantity -= qty
            if existing.quantity <= 0:
                del self._sim_positions[market_id]
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel pending order."""
        if self.simulation_mode:
            order = self._sim_orders.get(order_id)
            if order and order.is_working:
                order.transition_to(OrderState.CANCELLED, "User cancelled")
                logger.info(f"SIMULATION: Order cancelled {order_id}")
                return True
            return False
        
        try:
            result = await self._request("DELETE", f"/portfolio/orders/{order_id}")
            return result is not None
        except Exception:
            return False
    
    async def flatten_position(self, market_id: str) -> List[Trade]:
        """Close all positions in market."""
        position = await self.get_position(market_id)
        if not position or position.quantity <= 0:
            return []
        
        # Sell entire position
        trade = await self.place_order(
            market_id=market_id,
            side=position.side.value,
            direction="sell",
            quantity=position.quantity
        )
        
        return [trade]
    
    # ============================================
    # ACCOUNT
    # ============================================
    
    async def get_balance(self) -> float:
        """Get account balance."""
        if self.simulation_mode:
            return self._sim_balance
        
        try:
            result = await self._request("GET", "/portfolio/balance")
            if result and "balance" in result:
                return result["balance"] / 100
        except Exception:
            pass
        
        return self._sim_balance
    
    async def get_portfolio_value(self) -> float:
        """Get total portfolio value."""
        balance = await self.get_balance()
        positions = await self.get_positions()
        
        position_value = sum(
            p.quantity * p.current_price for p in positions
        )
        
        return balance + position_value
    
    def is_paper_mode(self) -> bool:
        """Sandbox is always paper mode (no real money)."""
        return True
    
    def is_simulation_mode(self) -> bool:
        """Whether running in full simulation without demo API."""
        return self.simulation_mode
    
    # ============================================
    # ORDER LIFECYCLE QUERIES
    # ============================================
    
    async def get_order(self, order_id: str) -> Optional[LiveOrder]:
        """Get order status for lifecycle tracking."""
        if self.simulation_mode:
            return self._sim_orders.get(order_id)
        
        try:
            result = await self._request("GET", f"/portfolio/orders/{order_id}")
            if result:
                # Convert to LiveOrder
                return LiveOrder(
                    id=result.get("order_id"),
                    idempotency_key=result.get("client_order_id", ""),
                    market_id=result.get("ticker", ""),
                    market_ticker=result.get("ticker", ""),
                    side=OrderSide.YES if result.get("side") == "yes" else OrderSide.NO,
                    action=OrderAction.BUY if result.get("action") == "buy" else OrderAction.SELL,
                    quantity=result.get("count", 0),
                    filled_quantity=result.get("filled_count", 0),
                    price_cents=result.get("yes_price", 0) or result.get("no_price", 0),
                    state=self._map_kalshi_status(result.get("status")),
                    adapter_mode="sandbox"
                )
        except Exception:
            pass
        
        return None
    
    def _map_kalshi_status(self, status: str) -> OrderState:
        """Map Kalshi status to OrderState."""
        mapping = {
            "resting": OrderState.ACKNOWLEDGED,
            "pending": OrderState.SUBMITTED,
            "filled": OrderState.FILLED,
            "canceled": OrderState.CANCELLED,
            "expired": OrderState.EXPIRED
        }
        return mapping.get(status, OrderState.SUBMITTED)
    
    async def get_working_orders(self) -> List[LiveOrder]:
        """Get all working orders."""
        if self.simulation_mode:
            return [o for o in self._sim_orders.values() if o.is_working]
        
        try:
            result = await self._request("GET", "/portfolio/orders")
            if result and "orders" in result:
                return [
                    await self.get_order(o["order_id"])
                    for o in result["orders"]
                    if o.get("status") in ["resting", "pending"]
                ]
        except Exception:
            pass
        
        return []
    
    async def validate_credentials(self) -> Dict[str, Any]:
        """Validate sandbox credentials."""
        await self.connect()
        balance = await self.get_balance()
        
        return {
            "valid": True,  # Sandbox always valid
            "message": "Sandbox mode active" if self.simulation_mode else "Demo API connected",
            "balance": balance,
            "simulation_mode": self.simulation_mode,
            "demo_connected": self.demo_connected
        }
