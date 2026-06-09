"""CoinGecko API client — fetch live market data for the top coins.

Public API, no key required. We use the /coins/markets endpoint which returns
price + market cap + 24h change for many coins in one call.
Docs: https://docs.coingecko.com/reference/coins-markets
"""

from __future__ import annotations

from datetime import datetime, timezone

import requests

API_URL = "https://api.coingecko.com/api/v3/coins/markets"
DEFAULT_PER_PAGE = 50  # top-50 by market cap — plenty for demo questions


class CoinGeckoError(RuntimeError):
    """Raised when the CoinGecko API call fails."""


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # API returns e.g. '2026-06-09T10:08:57.332Z'
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_markets(per_page: int = DEFAULT_PER_PAGE) -> list[dict]:
    """Return a normalized list of market rows + a shared captured_at timestamp.

    Each item carries the fields we persist (coin metadata + a price tick).
    """
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": per_page,
        "page": 1,
        "price_change_percentage": "24h",
    }
    try:
        resp = requests.get(API_URL, params=params, timeout=30,
                            headers={"accept": "application/json"})
        resp.raise_for_status()
        raw = resp.json()
    except requests.RequestException as exc:
        raise CoinGeckoError(f"CoinGecko request failed: {exc}") from exc
    except ValueError as exc:
        raise CoinGeckoError(f"CoinGecko returned non-JSON: {exc}") from exc

    if not isinstance(raw, list):
        raise CoinGeckoError(f"Unexpected CoinGecko response: {str(raw)[:120]}")

    # One crawl = one timestamp for every tick, so a "latest snapshot" is a
    # clean MAX(captured_at) filter downstream.
    captured_at = datetime.now(timezone.utc).replace(tzinfo=None)

    rows: list[dict] = []
    for c in raw:
        rows.append({
            # coin metadata
            "coin_id": c["id"],
            "symbol": (c.get("symbol") or "").lower(),
            "name": c.get("name") or c["id"],
            "market_cap_rank": c.get("market_cap_rank"),
            "circulating_supply": c.get("circulating_supply"),
            "total_supply": c.get("total_supply"),
            "max_supply": c.get("max_supply"),
            "ath": c.get("ath"),
            "ath_date": _parse_dt(c.get("ath_date")),
            # price tick
            "price_usd": c.get("current_price"),
            "market_cap": c.get("market_cap"),
            "total_volume": c.get("total_volume"),
            "high_24h": c.get("high_24h"),
            "low_24h": c.get("low_24h"),
            "price_change_24h": c.get("price_change_24h"),
            "price_change_pct_24h": c.get("price_change_percentage_24h"),
            "market_cap_change_pct_24h": c.get("market_cap_change_percentage_24h"),
            "captured_at": captured_at,
        })

    # Skip coins with no price (can't form a valid tick).
    return [r for r in rows if r["price_usd"] is not None]


def to_json_safe(row: dict) -> dict:
    """Convert a market row to a JSON-serializable dict (datetimes → ISO strings).

    Used by the Kafka producer so messages can be json.dumps'd; the consumer
    parses the strings back to datetimes before writing to Postgres.
    """
    out = dict(row)
    for key in ("ath_date", "captured_at"):
        val = out.get(key)
        out[key] = val.isoformat() if isinstance(val, datetime) else val
    return out


def from_json_safe(row: dict) -> dict:
    """Inverse of to_json_safe — restore datetime fields from ISO strings."""
    out = dict(row)
    for key in ("ath_date", "captured_at"):
        val = out.get(key)
        out[key] = _parse_dt(val) if isinstance(val, str) else val
    return out
