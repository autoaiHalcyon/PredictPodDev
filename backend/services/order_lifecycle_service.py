"""
Order Lifecycle Service
Manages complete order lifecycle with reconciliation, idempotency, and guardrails.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import uuid

from models.order_lifecycle import (
    LiveOrder, OrderState, OrderFill, PositionReconciliation,
    OrderType, OrderSide, OrderAction
)
from models.capital_deployment import (
    CapitalDeploymentMode, CapitalDeploymentSettings, TradeConfirmation
)
from repositories.order_repository import OrderRepository
from repositories.settings_repository import SettingsRepository
from adapters.kalshi.interface import KalshiAdapter

logger = logging.getLogger(__name__)


class OrderLifecycleService:
    """
    Institutional-grade order lifecycle management.
    
    Features:
    - 7-state order tracking
    - Idempotency (no duplicate orders)
    - Position reconciliation
    - Slippage/liquidity protection
    - Capital deployment modes
    - Pre-trade confirmation
    """
    
    def __init__(
        self,
        order_repo: OrderRepository,
        settings_repo: SettingsRepository,
        adapter: KalshiAdapter
    ):
        self.order_repo = order_repo
        self.settings_repo = settings_repo
        self.adapter = adapter
        
        # Capital deployment settings
        self._capital_settings: Optional[CapitalDeploymentSettings] = None
        
        # Rate limiting state
        self._order_times: List[datetime] = []
        
        # Reconciliation task
        self._reconciliation_task: Optional[asyncio.Task] = None
        self._order_sync_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def initialize(self):
        """Initialize service and start background tasks."""
        await self.order_repo.create_indexes()
        await self._load_capital_settings()
        self._running = True
        self._reconciliation_task = asyncio.create_task(self._reconciliation_loop())
        self._order_sync_task = asyncio.create_task(self._order_state_sync_loop())
        logger.info("Order Lifecycle Service initialized")
    
    async def shutdown(self):
        """Stop background tasks."""
        self._running = False
        if self._reconciliation_task:
            self._reconciliation_task.cancel()
            try:
                await self._reconciliation_task
            except asyncio.CancelledError:
                pass
        if self._order_sync_task:
            self._order_sync_task.cancel()
            try:
                await self._order_sync_task
            except asyncio.CancelledError:
                pass
    
    async def _load_capital_settings(self):
        """Load capital deployment settings from database."""
        # Default to CONSERVATIVE
        self._capital_settings = CapitalDeploymentSettings.conservative()
        
        # Try to load from database
        try:
            doc = await self.settings_repo.db["capital_deployment"].find_one({"_id": "default"})
            if doc:
                mode = CapitalDeploymentMode(doc.get("mode", "conservative"))
                if mode == CapitalDeploymentMode.CONSERVATIVE:
                    self._capital_settings = CapitalDeploymentSettings.conservative()
                elif mode == CapitalDeploymentMode.NORMAL:
                    self._capital_settings = CapitalDeploymentSettings.normal()
                elif mode == CapitalDeploymentMode.AGGRESSIVE:
                    self._capital_settings = CapitalDeploymentSettings.aggressive()
        except Exception as e:
            logger.warning(f"Failed to load capital settings, using CONSERVATIVE: {e}")
    
    # ============================================
    # CAPITAL DEPLOYMENT
    # ============================================
    
    async def get_capital_settings(self) -> CapitalDeploymentSettings:
        """Get current capital deployment settings."""
        return self._capital_settings
    
    async def set_capital_deployment_mode(
        self,
        mode: CapitalDeploymentMode,
        confirmed: bool = False
    ) -> Dict[str, Any]:
        """
        Set capital deployment mode.
        AGGRESSIVE requires explicit confirmation.
        """
        if mode == CapitalDeploymentMode.AGGRESSIVE and not confirmed:
            return {
                "success": False,
                "message": "AGGRESSIVE mode requires explicit confirmation. Set confirmed=true and acknowledge the risks.",
                "requires_confirmation": True
            }
        
        if mode == CapitalDeploymentMode.CONSERVATIVE:
            self._capital_settings = CapitalDeploymentSettings.conservative()
        elif mode == CapitalDeploymentMode.NORMAL:
            self._capital_settings = CapitalDeploymentSettings.normal()
        elif mode == CapitalDeploymentMode.AGGRESSIVE:
            self._capital_settings = CapitalDeploymentSettings.aggressive()
        
        # Persist to database
        await self.settings_repo.db["capital_deployment"].update_one(
            {"_id": "default"},
            {"$set": {"mode": mode.value, "updated_at": datetime.utcnow()}},
            upsert=True
        )
        
        logger.info(f"Capital deployment mode set to: {mode.value}")
        
        return {
            "success": True,
            "message": f"Capital deployment mode set to {mode.value}",
            "settings": self._capital_settings.to_dict()
        }
    
    # ============================================
    # PRE-TRADE CHECKS
    # ============================================
    
    async def get_trade_confirmation(
        self,
        market_id: str,
        side: str,
        action: str,
        quantity: int,
        price_cents: int
    ) -> TradeConfirmation:
        """
        Generate pre-trade confirmation with all risk checks.
        MUST be displayed before every live order.
        """
        settings = self._capital_settings
        
        # Get current account state
        balance = await self.adapter.get_balance()
        balance_cents = int(balance * 100)
        
        # Get positions for exposure calculation
        positions = await self.adapter.get_positions()
        current_exposure_cents = sum(
            int(p.quantity * p.current_price * 100) for p in positions
        )
        
        # Get today's PnL
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        recent_orders = await self.order_repo.get_recent_orders(limit=100, since=today_start)
        today_pnl_cents = sum(
            o.total_cost_cents * (-1 if o.action == OrderAction.BUY else 1)
            for o in recent_orders if o.is_terminal
        )
        
        # Calculate order impact
        order_total_cents = quantity * price_cents
        max_loss_cents = order_total_cents  # Full loss if goes to 0
        worst_case_cents = order_total_cents + int(order_total_cents * 0.1)  # +10% slippage
        exposure_after = current_exposure_cents + order_total_cents
        
        # Get orderbook for liquidity check
        orderbook = await self.adapter.get_orderbook(market_id)
        
        orderbook_depth = 0
        spread_cents = 0
        order_pct_of_book = 0.0
        
        if orderbook:
            # Calculate depth - handle both dict and Pydantic objects
            if action == "buy" and orderbook.asks:
                orderbook_depth = sum(
                    a.quantity if hasattr(a, 'quantity') else a.get("quantity", 0) 
                    for a in orderbook.asks[:3]
                )
            elif action == "sell" and orderbook.bids:
                orderbook_depth = sum(
                    b.quantity if hasattr(b, 'quantity') else b.get("quantity", 0) 
                    for b in orderbook.bids[:3]
                )
            
            # Calculate spread
            if orderbook.bids and orderbook.asks:
                best_bid = orderbook.bids[0]
                best_ask = orderbook.asks[0]
                bid_price = best_bid.price if hasattr(best_bid, 'price') else best_bid.get("price", 0)
                ask_price = best_ask.price if hasattr(best_ask, 'price') else best_ask.get("price", 0)
                spread_cents = int((ask_price - bid_price) * 100)
            
            # Order as % of top-of-book
            if orderbook_depth > 0:
                order_pct_of_book = (quantity / orderbook_depth) * 100
        
        # Check rate limits
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        
        orders_per_minute = sum(1 for t in self._order_times if t > minute_ago)
        orders_per_hour = sum(1 for t in self._order_times if t > hour_ago)
        
        # Perform all checks
        within_trade_limit = order_total_cents <= settings.max_trade_size_cents
        within_daily_loss = today_pnl_cents > -settings.max_daily_loss_cents
        within_exposure = exposure_after <= settings.max_total_exposure_cents
        within_rate_minute = orders_per_minute < settings.max_orders_per_minute
        within_rate_hour = orders_per_hour < settings.max_orders_per_hour
        within_rate = within_rate_minute and within_rate_hour
        
        liquidity_warning = order_pct_of_book > settings.max_order_pct_of_book * 0.5
        liquidity_blocked = order_pct_of_book > settings.max_order_pct_of_book
        spread_warning = spread_cents > settings.max_spread_cents
        
        all_checks_passed = (
            within_trade_limit and
            within_daily_loss and
            within_exposure and
            within_rate and
            not liquidity_blocked
        )
        
        # Collect blocking reasons
        blocking_reasons = []
        warning_reasons = []
        
        if not within_trade_limit:
            blocking_reasons.append(
                f"Order ${order_total_cents/100:.2f} exceeds max trade size ${settings.max_trade_size_cents/100:.2f}"
            )
        if not within_daily_loss:
            blocking_reasons.append(
                f"Daily loss limit ${settings.max_daily_loss_cents/100:.2f} reached"
            )
        if not within_exposure:
            blocking_reasons.append(
                f"Would exceed max exposure ${settings.max_total_exposure_cents/100:.2f}"
            )
        if not within_rate:
            blocking_reasons.append("Rate limit exceeded")
        if liquidity_blocked:
            blocking_reasons.append(
                f"Order is {order_pct_of_book:.1f}% of orderbook (max {settings.max_order_pct_of_book}%)"
            )
        
        if liquidity_warning and not liquidity_blocked:
            warning_reasons.append(
                f"Order is {order_pct_of_book:.1f}% of orderbook - may cause slippage"
            )
        if spread_warning:
            warning_reasons.append(
                f"Spread is {spread_cents}¢ (threshold: {settings.max_spread_cents}¢)"
            )
        
        return TradeConfirmation(
            # Account state
            account_balance_cents=balance_cents,
            buying_power_cents=balance_cents - current_exposure_cents,
            today_realized_pnl_cents=today_pnl_cents,
            today_open_risk_cents=current_exposure_cents,
            
            # Order details
            order_side=side,
            order_action=action,
            order_quantity=quantity,
            order_price_cents=price_cents,
            order_total_cents=order_total_cents,
            
            # Risk analysis
            max_loss_cents=max_loss_cents,
            worst_case_loss_cents=worst_case_cents,
            daily_risk_utilization_pct=(abs(today_pnl_cents) / settings.max_daily_loss_cents) * 100 if settings.max_daily_loss_cents > 0 else 0,
            exposure_after_trade_cents=exposure_after,
            exposure_utilization_pct=(exposure_after / settings.max_total_exposure_cents) * 100 if settings.max_total_exposure_cents > 0 else 0,
            
            # Liquidity
            orderbook_depth=orderbook_depth,
            spread_cents=spread_cents,
            order_pct_of_book=order_pct_of_book,
            liquidity_warning=liquidity_warning,
            liquidity_blocked=liquidity_blocked,
            
            # Checks
            within_trade_limit=within_trade_limit,
            within_daily_loss_limit=within_daily_loss,
            within_exposure_limit=within_exposure,
            within_rate_limit=within_rate,
            all_checks_passed=all_checks_passed,
            
            # Reasons
            blocking_reasons=blocking_reasons,
            warning_reasons=warning_reasons,
            
            # Confirmation requirements
            requires_double_confirmation=settings.requires_double_confirmation,
            requires_explicit_acknowledgment=settings.requires_explicit_acknowledgment
        )
    
    # ============================================
    # ORDER SUBMISSION
    # ============================================
    
    async def submit_order(
        self,
        market_id: str,
        market_ticker: str,
        side: str,
        action: str,
        quantity: int,
        price_cents: int,
        idempotency_key: str,
        game_id: Optional[str] = None,
        confirmed_double: bool = False,
        acknowledged_risk: bool = False
    ) -> Tuple[Optional[LiveOrder], Optional[str]]:
        """
        Submit order with full lifecycle tracking.
        
        Returns:
            (order, error_message) - order is None if blocked
        """
        # 1. Check idempotency - prevent duplicates
        existing = await self.order_repo.check_idempotency_key(idempotency_key)
        if existing:
            logger.warning(f"Duplicate order blocked: {idempotency_key}")
            return existing, "Duplicate order - original order returned"
        
        # 2. Get pre-trade confirmation
        confirmation = await self.get_trade_confirmation(
            market_id, side, action, quantity, price_cents
        )
        
        # 3. Check if blocked
        if not confirmation.all_checks_passed:
            reasons = "; ".join(confirmation.blocking_reasons)
            logger.warning(f"Order blocked: {reasons}")
            return None, f"Order blocked: {reasons}"
        
        # 4. Check confirmation requirements
        if confirmation.requires_double_confirmation and not confirmed_double:
            return None, "AGGRESSIVE mode requires double confirmation"
        
        if confirmation.requires_explicit_acknowledgment and not acknowledged_risk:
            return None, "AGGRESSIVE mode requires explicit risk acknowledgment"
        
        # 5. Create order record
        order = LiveOrder(
            idempotency_key=idempotency_key,
            market_id=market_id,
            market_ticker=market_ticker,
            game_id=game_id,
            side=OrderSide.YES if side == "yes" else OrderSide.NO,
            action=OrderAction.BUY if action == "buy" else OrderAction.SELL,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price_cents=price_cents,
            expected_fill_price_cents=price_cents,
            state=OrderState.SUBMITTED,
            pre_order_balance_cents=confirmation.account_balance_cents,
            pre_order_exposure_cents=confirmation.today_open_risk_cents,
            pre_order_daily_pnl_cents=confirmation.today_realized_pnl_cents,
            orderbook_depth_at_submission=confirmation.orderbook_depth,
            spread_at_submission_cents=confirmation.spread_cents,
            capital_deployment_mode=self._capital_settings.mode.value,
            adapter_mode="sandbox" if self.adapter.is_paper_mode() else "real"
        )
        
        # 7. Save order to database BEFORE submission (crash safety)
        await self.order_repo.save_order(order)
        await self.order_repo.register_idempotency_key(idempotency_key, order.id)
        
        # 8. Record order time for rate limiting
        self._order_times.append(datetime.utcnow())
        self._order_times = [t for t in self._order_times if t > datetime.utcnow() - timedelta(hours=1)]
        
        # 9. Submit to adapter
        try:
            trade = await self.adapter.place_order(
                market_id=market_id,
                side=side,
                direction=action,
                quantity=quantity,
                price=price_cents / 100,
                idempotency_key=idempotency_key
            )
            
            # Update with exchange order ID
            if trade and trade.id:
                order.exchange_order_id = trade.id
                order.transition_to(OrderState.ACKNOWLEDGED, "Order acknowledged by exchange")
                await self.order_repo.save_order(order)
        
        except Exception as e:
            order.transition_to(OrderState.REJECTED, f"Submission failed: {str(e)}")
            await self.order_repo.save_order(order)
            return order, f"Order submission failed: {str(e)}"
        
        logger.info(f"Order submitted: {order.id} market={market_id} {action} {quantity}@{price_cents}¢")
        
        return order, None
    
    async def cancel_order(self, order_id: str) -> Tuple[bool, str]:
        """Cancel a working order."""
        order = await self.order_repo.get_order(order_id)
        
        if not order:
            return False, "Order not found"
        
        if not order.is_working:
            return False, f"Order is not cancellable (state: {order.state.value})"
        
        try:
            success = await self.adapter.cancel_order(order.exchange_order_id or order.id)
            if success:
                order.transition_to(OrderState.CANCELLED, "User cancelled")
                await self.order_repo.save_order(order)
                return True, "Order cancelled"
            else:
                return False, "Cancel request failed"
        except Exception as e:
            return False, f"Cancel error: {str(e)}"
    
    # ============================================
    # ORDER QUERIES
    # ============================================
    
    async def get_order(self, order_id: str) -> Optional[LiveOrder]:
        """Get order by ID."""
        return await self.order_repo.get_order(order_id)
    
    async def get_order_by_idempotency_key(self, key: str) -> Optional[LiveOrder]:
        """Get order by idempotency key."""
        return await self.order_repo.get_order_by_idempotency_key(key)
    
    async def get_working_orders(self) -> List[LiveOrder]:
        """Get all working orders."""
        return await self.order_repo.get_working_orders()
    
    async def get_recent_orders(self, limit: int = 50) -> List[LiveOrder]:
        """Get recent orders."""
        return await self.order_repo.get_recent_orders(limit)
    
    # ============================================
    # ORDER STATE SYNC
    # ============================================
    
    async def _order_state_sync_loop(self):
        """
        Background task to sync order states from adapter to database.
        Handles the case where async fills in the adapter update the
        in-memory order but not the database.
        """
        while self._running:
            try:
                await self._sync_order_states()
                await asyncio.sleep(5)  # Check every 5 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Order sync error: {e}")
                await asyncio.sleep(5)
    
    async def _sync_order_states(self):
        """
        Sync order states from adapter to database.
        This ensures that async fills in the sandbox adapter
        are reflected in the persisted order state.
        
        Also handles orphaned orders (orders in DB but not in adapter).
        """
        # Get working orders from database
        working_orders = await self.order_repo.get_working_orders()
        
        if not working_orders:
            return
        
        now = datetime.utcnow()
        
        for db_order in working_orders:
            try:
                # Get order from adapter by exchange_order_id or id
                adapter_order = await self.adapter.get_order(
                    db_order.exchange_order_id or db_order.id
                )
                
                if adapter_order:
                    # Check if adapter order has progressed further
                    if adapter_order.state != db_order.state:
                        # Sync state from adapter to database
                        if adapter_order.state == OrderState.FILLED:
                            db_order.filled_quantity = adapter_order.filled_quantity
                            db_order.avg_fill_price_cents = adapter_order.avg_fill_price_cents
                            db_order.fills = adapter_order.fills
                            db_order.transition_to(OrderState.FILLED, "Fill synced from adapter")
                            await self.order_repo.save_order(db_order)
                            logger.info(f"Order {db_order.id} synced to FILLED")
                        
                        elif adapter_order.state == OrderState.PARTIAL:
                            db_order.filled_quantity = adapter_order.filled_quantity
                            db_order.avg_fill_price_cents = adapter_order.avg_fill_price_cents
                            db_order.fills = adapter_order.fills
                            db_order.transition_to(OrderState.PARTIAL, f"Partial fill synced: {adapter_order.filled_quantity}/{adapter_order.quantity}")
                            await self.order_repo.save_order(db_order)
                            logger.info(f"Order {db_order.id} synced to PARTIAL ({adapter_order.filled_quantity}/{adapter_order.quantity})")
                        
                        elif adapter_order.is_terminal:
                            db_order.transition_to(adapter_order.state, f"State synced from adapter: {adapter_order.state.value}")
                            await self.order_repo.save_order(db_order)
                            logger.info(f"Order {db_order.id} synced to {adapter_order.state.value}")
                else:
                    # Order not found in adapter - check if it's orphaned
                    # An order is considered orphaned if it's been in a working state
                    # for more than 60 seconds without adapter tracking
                    order_age = (now - db_order.created_at).total_seconds()
                    
                    if order_age > 60:
                        # Mark as expired - adapter lost track of it
                        db_order.transition_to(
                            OrderState.EXPIRED,
                            f"Order orphaned: not found in adapter after {int(order_age)}s"
                        )
                        await self.order_repo.save_order(db_order)
                        logger.warning(f"Order {db_order.id} marked EXPIRED (orphaned after {int(order_age)}s)")
            
            except Exception as e:
                logger.error(f"Error syncing order {db_order.id}: {e}")
    
    # ============================================
    # RECONCILIATION
    # ============================================
    
    async def _reconciliation_loop(self):
        """Background reconciliation task."""
        while self._running:
            try:
                await self._reconcile_positions()
                await asyncio.sleep(60)  # Check every 60 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Reconciliation error: {e}")
                await asyncio.sleep(60)
    
    async def _reconcile_positions(self):
        """
        Reconcile local position state with adapter-reported state.
        Flags mismatches within 60 seconds.
        """
        # Get adapter positions
        adapter_positions = await self.adapter.get_positions()
        adapter_by_market = {p.market_id: p for p in adapter_positions}
        
        # Get local position state (from filled orders)
        local_positions = await self._calculate_local_positions()
        
        # Compare
        all_markets = set(adapter_by_market.keys()) | set(local_positions.keys())
        
        for market_id in all_markets:
            adapter_pos = adapter_by_market.get(market_id)
            local_pos = local_positions.get(market_id)
            
            recon = PositionReconciliation(
                market_id=market_id,
                local_quantity=local_pos["quantity"] if local_pos else 0,
                local_side=local_pos["side"] if local_pos else "",
                local_avg_price_cents=local_pos["avg_price_cents"] if local_pos else 0,
                adapter_quantity=adapter_pos.quantity if adapter_pos else 0,
                adapter_side=adapter_pos.side if adapter_pos else "",
                adapter_avg_price_cents=int(adapter_pos.avg_entry_price * 100) if adapter_pos else 0,
                quantity_match=True,
                side_match=True,
                price_match=True,
                fully_reconciled=True
            )
            
            # Check for mismatches
            if local_pos and adapter_pos:
                recon.quantity_match = local_pos["quantity"] == adapter_pos.quantity
                recon.side_match = local_pos["side"] == adapter_pos.side
                recon.price_match = abs(local_pos["avg_price_cents"] - int(adapter_pos.avg_entry_price * 100)) < 5
            elif local_pos and not adapter_pos:
                recon.mismatch_type = "missing_remote"
                recon.quantity_match = False
            elif adapter_pos and not local_pos:
                recon.mismatch_type = "missing_local"
                recon.quantity_match = False
            
            recon.fully_reconciled = recon.quantity_match and recon.side_match
            
            if not recon.fully_reconciled:
                recon.mismatch_severity = "critical" if abs(recon.local_quantity - recon.adapter_quantity) > 10 else "warning"
                logger.warning(
                    f"RECONCILIATION MISMATCH: {market_id} "
                    f"local={recon.local_quantity} adapter={recon.adapter_quantity} "
                    f"type={recon.mismatch_type}"
                )
            
            await self.order_repo.save_reconciliation(recon)
    
    async def _calculate_local_positions(self) -> Dict[str, Dict]:
        """Calculate positions from filled orders."""
        positions = {}
        
        orders = await self.order_repo.get_recent_orders(limit=500)
        
        for order in orders:
            if order.state != OrderState.FILLED:
                continue
            
            market_id = order.market_id
            side = order.side.value
            action = order.action.value
            qty = order.filled_quantity
            price = order.avg_fill_price_cents
            
            if market_id not in positions:
                positions[market_id] = {
                    "quantity": 0,
                    "side": side,
                    "avg_price_cents": 0,
                    "total_cost": 0
                }
            
            pos = positions[market_id]
            
            if action == "buy":
                new_qty = pos["quantity"] + qty
                if new_qty > 0:
                    pos["avg_price_cents"] = (pos["total_cost"] + qty * price) // new_qty
                pos["quantity"] = new_qty
                pos["total_cost"] += qty * price
            elif action == "sell":
                pos["quantity"] -= qty
                if pos["quantity"] <= 0:
                    del positions[market_id]
        
        return positions
    
    async def get_reconciliation_status(self) -> Dict[str, Any]:
        """Get current reconciliation status."""
        unreconciled = await self.order_repo.get_unreconciled_positions()
        
        return {
            "total_unreconciled": len(unreconciled),
            "critical_mismatches": len([r for r in unreconciled if r.mismatch_severity == "critical"]),
            "warning_mismatches": len([r for r in unreconciled if r.mismatch_severity == "warning"]),
            "mismatches": [r.to_dict() for r in unreconciled[:10]]
        }
    
    async def force_reconciliation(self) -> Dict[str, Any]:
        """Force immediate reconciliation."""
        await self._reconcile_positions()
        return await self.get_reconciliation_status()
