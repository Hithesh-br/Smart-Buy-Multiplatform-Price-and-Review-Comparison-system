"""
services/price_monitor_service.py
=================================
Automated Background Price Monitoring & Real-Time Alert Dispatch Service:
- Regularly checks active price alerts against current product prices.
- Detects price drops, price reductions, and target reached events.
- Dispatches instant email notifications via verified SMTP to user accounts.
- Synchronizes real-time dashboard status and in-app notifications.
"""

import time
import logging
import threading
import re
from datetime import datetime, timezone

logger = logging.getLogger("smartbuy.price_monitor")

_monitor_thread = None
_stop_event = threading.Event()


def check_all_active_price_alerts() -> dict:
    """
    Inspect all active alerts in the database and trigger notifications
    whenever a product's price drops or changes.
    Evaluates every alert against current product prices across GEC ECom,
    Amazon, Flipkart, and Meesho.
    """
    from database import get_db, process_single_alert, to_object_id
    db = get_db()

    if db is None:
        return {"checked": 0, "triggered": 0, "notifications_sent": 0, "error": "Database unavailable"}

    try:
        query = {
            "status": {"$in": ["monitoring", "active", "email_sent", "target_reached", "email_failed"]}
        }
        alerts = list(db.price_alerts.find(query))
        total_checked = len(alerts)
        total_triggered = 0
        total_sent = 0
        details = []

        # Cache store product prices to avoid repeated database lookups
        store_cache = {}

        for alert in alerts:
            aid = alert.get("_id")
            aid_str = str(aid)
            pid = alert.get("product_id")
            p_name = alert.get("product_name") or ""
            target_p = int(alert.get("target_price") or 0)
            recorded_latest = alert.get("latest_price")
            recorded_prev = alert.get("previous_price") or alert.get("current_price") or target_p
            platform = str(alert.get("platform") or "gececom").lower()
            product_url = alert.get("product_url") or ""

            live_price = None

            # 1. GEC ECom product: fetch live price directly from gececom_products collection
            if platform in ("gececom", "gec", "store", "") or pid:
                if pid:
                    pid_clean = str(pid).strip()
                    raw_pid = pid_clean[4:] if pid_clean.startswith("gec_") else pid_clean
                    if pid_clean not in store_cache:
                        oid = to_object_id(raw_pid) or to_object_id(pid_clean)
                        prod = db.gececom_products.find_one({"$or": [{"_id": oid}, {"id": pid_clean}, {"id": raw_pid}]} if oid else {"$or": [{"id": pid_clean}, {"id": raw_pid}]})
                        store_cache[pid_clean] = prod
                    else:
                        prod = store_cache[pid_clean]

                    if prod:
                        live_price = prod.get("current_price")
                        if not p_name and prod.get("product_name"):
                            p_name = prod.get("product_name")

                # If not found by ID, try matching store product by title
                if live_price is None and p_name:
                    cached_key = f"name_{p_name.lower()}"
                    if cached_key not in store_cache:
                        esc_name = re.escape(p_name.strip())
                        prod_by_name = db.gececom_products.find_one({
                            "product_name": {"$regex": f"^{esc_name}$", "$options": "i"}
                        })
                        if not prod_by_name:
                            search_kw = p_name.strip().lower()
                            for gp in db.gececom_products.find():
                                gp_name = (gp.get("product_name") or "").lower()
                                if search_kw in gp_name or gp_name in search_kw:
                                    prod_by_name = gp
                                    break
                        store_cache[cached_key] = prod_by_name
                    else:
                        prod_by_name = store_cache[cached_key]

                    if prod_by_name:
                        live_price = prod_by_name.get("current_price")

            # 2. External platform (Amazon, Flipkart, Meesho): if live product URL is present, attempt live scrape if configured
            if live_price is None and product_url and platform in ("amazon", "flipkart", "meesho"):
                try:
                    if platform == "amazon":
                        from scrapers.amazon_scraper import AmazonScraper
                        sc = AmazonScraper()
                        res_p, st, _ = sc.scrape_product_url(product_url)
                        if res_p and res_p.get("current_price"):
                            live_price = res_p.get("current_price")
                    elif platform == "flipkart":
                        from scrapers.flipkart_scraper import FlipkartScraper
                        sc = FlipkartScraper()
                        res_p, st, _ = sc.scrape_product_url(product_url)
                        if res_p and res_p.get("current_price"):
                            live_price = res_p.get("current_price")
                except Exception as sc_err:
                    logger.debug(f"[Price Monitor] Online scrape skipped/failed for {platform} alert {aid_str}: {sc_err}")

            # 3. Fallback to latest recorded price or previous price
            if live_price is None:
                live_price = recorded_latest if recorded_latest is not None else recorded_prev

            if live_price is None:
                continue

            try:
                current_p = int(round(float(str(live_price).replace(',', '').replace('₹', '').strip())))
            except (ValueError, TypeError):
                continue

            if current_p <= 0:
                continue

            prev_p = int(recorded_prev or current_p)

            # Delegate atomic evaluation, recipient verification, and dispatch to process_single_alert
            res = process_single_alert(
                alert=alert,
                current_price=current_p,
                previous_price=prev_p,
                force_notify=False
            )

            if res.get("condition_met"):
                total_triggered += 1
            if res.get("email_sent"):
                total_sent += 1
            details.append(res)

        return {
            "checked": total_checked,
            "triggered": total_triggered,
            "notifications_sent": total_sent,
            "details": details
        }
    except Exception as e:
        logger.error(f"[Price Monitor] Error checking active alerts: {e}", exc_info=True)
        return {"checked": 0, "triggered": 0, "notifications_sent": 0, "error": str(e)}


def _monitor_loop(interval_seconds: int = 15):
    """Periodic worker loop running in daemon thread."""
    logger.info(f"[Price Monitor] Background price monitoring worker started (interval: {interval_seconds}s).")
    # Initial pause to let server finish bootstrapping
    time.sleep(2)
    while not _stop_event.is_set():
        try:
            res = check_all_active_price_alerts()
            if res.get("notifications_sent", 0) > 0:
                logger.info(f"[Price Monitor] Cycle complete: {res['notifications_sent']} emails sent out of {res['checked']} checked.")
        except Exception as e:
            logger.warning(f"[Price Monitor] Exception during monitoring cycle: {e}")

        # Sleep in small slices to allow quick thread termination
        for _ in range(int(interval_seconds)):
            if _stop_event.is_set():
                break
            time.sleep(1)


def start_price_monitor(interval_seconds: int = 15):
    """Start the background price monitoring daemon thread."""
    global _monitor_thread
    if _monitor_thread is not None and _monitor_thread.is_alive():
        logger.info("[Price Monitor] Background monitor already running.")
        return _monitor_thread

    _stop_event.clear()
    _monitor_thread = threading.Thread(
        target=_monitor_loop,
        args=(interval_seconds,),
        daemon=True,
        name="SmartBuyPriceMonitor"
    )
    _monitor_thread.start()
    logger.info("[Price Monitor] Launched SmartBuyPriceMonitor background thread.")
    return _monitor_thread


def stop_price_monitor():
    """Stop the background price monitor gracefully."""
    _stop_event.set()
