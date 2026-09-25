"""
scrapers/scraper_logger.py
==========================
Dedicated scraper execution and error logger.
Logs to logs/scraper.log and logs/scrapers.log with the required format:

MEESHO
query="..."
provider=...
status=...
products=...
duration=...
"""

import os
import logging
from datetime import datetime

LOG_DIR = (
    "/tmp/smartbuy-logs"
    if os.getenv("VERCEL")
    else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
)
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "scrapers.log")
SCRAPER_LOG_FILE = os.path.join(LOG_DIR, "scraper.log")

DEBUG_SCRAPERS = os.getenv("DEBUG_SCRAPERS", "true").lower() in ("true", "1", "yes")

_logger = logging.getLogger("smartbuy.scrapers.audit")
_logger.setLevel(logging.INFO)

if not _logger.handlers:
    try:
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(message)s"))
        _logger.addHandler(fh)

        fh2 = logging.FileHandler(SCRAPER_LOG_FILE, encoding="utf-8")
        fh2.setLevel(logging.INFO)
        fh2.setFormatter(logging.Formatter("%(message)s"))
        _logger.addHandler(fh2)
    except Exception as e:
        print(f"Failed to initialize FileHandler for scraper logs: {e}")


def log_scraper_event(
    platform: str,
    query: str,
    status: str,
    retry: int = 0,
    products_count: int = 0,
    parsed_count: int = 0,
    url: str = None,
    http_status: int = None,
    error: str = None,
    duration: float = None,
    provider: str = None
):
    """
    Log an audit entry conforming to Section 19 and Section 23 requirements.
    """
    time_str = datetime.now().strftime("%H:%M:%S")
    p_name = platform.upper()
    prov = provider or f"{platform.lower()}_provider"

    lines = [
        f"[{time_str}] {p_name}",
        f'query="{query}"',
        f"provider={prov}",
        f"status={status}",
        f"retry={retry}",
        f"products={products_count}",
    ]
    if parsed_count != products_count and parsed_count > 0:
        lines.append(f"parsed={parsed_count}")
    if url:
        lines.append(f"url={url}")
    if http_status:
        lines.append(f"http_status={http_status}")
    if duration is not None:
        lines.append(f"duration={duration:.2f}s")
    if error:
        clean_err = str(error).split("\n")[0][:120]
        lines.append(f"error={clean_err}")
    lines.append("")

    log_entry = "\n".join(lines)
    try:
        _logger.info(log_entry)
    except Exception:
        pass

    if DEBUG_SCRAPERS:
        status_disp = status.upper()
        if status in ("success", "live"):
            print(f"[{p_name}] {status_disp} – {products_count} products ({duration or 0:.2f}s)")
        else:
            print(f"[{p_name}] {status_disp} – {error or 'No details'} ({duration or 0:.2f}s)")
