"""
One-time backfill: create trading_audit_log entries for all trades in db.trades
that don't already have one.  Run with: python scripts/backfill_audit.py
"""
import asyncio, sys, uuid
from datetime import datetime

async def main():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["predictpod"]

    trades = await db.trades.find({}, {"_id": 0}).to_list(length=10_000)
    print(f"Found {len(trades)} trades in db.trades", flush=True)

    inserted = 0
    skipped  = 0
    for t in trades:
        order_id = t.get("id") or str(uuid.uuid4())
        if await db.trading_audit_log.find_one({"order_id": order_id}):
            skipped += 1
            continue
        price_f = float(t.get("avg_fill_price") or t.get("price") or 0)
        qty     = int(t.get("quantity") or 0)
        created = t.get("created_at") or datetime.utcnow()
        if isinstance(created, str):
            try:    created = datetime.fromisoformat(created)
            except: created = datetime.utcnow()
        await db.trading_audit_log.insert_one({
            "id":               str(uuid.uuid4()),
            "order_id":         order_id,
            "market_id":        t.get("market_id") or "",
            "market_ticker":    t.get("market_id") or "",
            "game_id":          t.get("game_id"),
            "side":             t.get("side") or "",
            "action":           t.get("direction") or "buy",
            "order_type":       t.get("order_type") or "market",
            "quantity":         qty,
            "price_cents":      round(price_f * 100),
            "edge":             float(t.get("edge_at_entry") or 0),
            "status":           t.get("status") or "filled",
            "fill_price_cents": round(price_f * 100),
            "filled_quantity":  int(t.get("filled_quantity") or qty),
            "cost_basis_cents": round(price_f * 100 * qty),
            "fees_cents":       round(float(t.get("fees") or 0) * 100),
            "strategy":         t.get("strategy"),
            "signal_type":      t.get("signal_type"),
            "game_title":       t.get("game_title"),
            "market_name":      t.get("market_name"),
            "league":           t.get("league"),
            "is_paper":         t.get("is_paper", True),
            "timestamp":        created,
            "created_at":       created,
        })
        inserted += 1

    total = await db.trading_audit_log.count_documents({})
    print(f"Done. Inserted={inserted}  Skipped(already existed)={skipped}  Total audit docs={total}", flush=True)
    client.close()

asyncio.run(main())
