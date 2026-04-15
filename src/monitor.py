"""Core monitor: fetch → score against history → alert."""

import yaml
from datetime import date
from pathlib import Path

from .models import Alert, Flight, PriceRecord, Route
from .db import get_price_stats, save_record, get_subscriptions
from .sources import google_flights, kiwi, secret_flying

CONFIG_PATH = Path(__file__).parent.parent / "config" / "routes.yaml"

# Minimum number of historical records before scoring is meaningful
_MIN_HISTORY = 3

# Alert thresholds: price must be cheaper than this % of history
_THRESHOLDS = {
    "Mínima histórica 🔥": 90,
    "Ótimo 🟢": 75,
    "Bom 🟡": 60,
}


def _score_price(price: float, stats: dict) -> tuple[str, float] | None:
    """
    Returns (label, pct_above) if price qualifies for an alert, else None.
    pct_above = % of historical prices strictly above current price.
    """
    if stats["count"] < _MIN_HISTORY:
        return None
    prices = stats["prices"]
    pct_above = sum(1 for p in prices if p > price) / len(prices) * 100
    for label, threshold in _THRESHOLDS.items():
        if pct_above >= threshold:
            return label, round(pct_above, 1)
    return None


def load_routes() -> list[Route]:
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    return [Route(**r) for r in config.get("routes", [])]


def _subscription_routes() -> list[Route]:
    """Load active non-expired subscriptions as Route objects (one or two legs each)."""
    today = date.today()
    routes: list[Route] = []
    for sub in get_subscriptions():
        if sub.date_to < today:
            continue
        routes.append(Route(
            origin=sub.origin,
            destination=sub.destination,
            date_from=max(sub.date_from, today),
            date_to=sub.date_to,
            max_stops=sub.max_stops,
            currency=sub.currency,
            chat_id=sub.chat_id,
        ))
        # Return leg for round-trip subscriptions
        if (
            sub.trip_type == "round-trip"
            and sub.return_date_from
            and sub.return_date_to
            and sub.return_date_to >= today
        ):
            routes.append(Route(
                origin=sub.destination,
                destination=sub.origin,
                date_from=max(sub.return_date_from, today),
                date_to=sub.return_date_to,
                max_stops=sub.max_stops,
                currency=sub.currency,
                chat_id=sub.chat_id,
            ))
    return routes


def run_once(alert_fn=None, lookback_days: int = 60) -> list[Alert]:
    """
    Runs one full monitoring cycle across static routes and bot subscriptions.
    alert_fn: optional callable(Alert) for sending notifications.
    """
    routes = load_routes() + _subscription_routes()
    triggered: list[Alert] = []

    for route in routes:
        route_key = f"{route.origin}-{route.destination}"
        print(f"[monitor] checking {route_key} ({route.date_from} → {route.date_to})")

        flights = _fetch_all(route)
        if not flights:
            print(f"[monitor] no results for {route_key}")
            continue

        for flight in flights:
            if flight.price <= 0:
                continue

            # Save record first, then fetch stats (includes current price)
            record = PriceRecord(
                route_key=route_key,
                departure_date=flight.departure_date,
                price=flight.price,
                currency=flight.currency,
                source=flight.source,
                deep_link=flight.deep_link,
            )
            save_record(record)

            stats = get_price_stats(route_key, flight.departure_date, lookback_days)
            if stats is None or stats["count"] < _MIN_HISTORY:
                print(f"[monitor] {route_key} {flight.departure_date}: building history ({stats['count'] if stats else 1} records)")
                continue

            scored = _score_price(flight.price, stats)
            if scored is None:
                continue

            label, pct_above = scored
            alert = Alert(
                route_key=route_key,
                departure_date=flight.departure_date,
                new_price=flight.price,
                previous_min=stats["min"],
                drop_pct=round((1 - flight.price / stats["mean"]) * 100, 1),
                deep_link=flight.deep_link,
                source=flight.source,
                chat_id=route.chat_id,
                score_label=label,
                score_pct=pct_above,
                hist_mean=round(stats["mean"], 0),
                hist_min=stats["min"],
                hist_count=stats["count"],
            )
            print(f"[monitor] ALERT {route_key} {flight.departure_date}: R${flight.price:.0f} | {label} ({pct_above}% acima)")
                triggered.append(alert)
                if alert_fn:
                    alert_fn(alert)

    return triggered


def _fetch_all(route: Route) -> list[Flight]:
    """Fetches from all sources and keeps lowest price per departure date."""
    flights: list[Flight] = []
    flights.extend(google_flights.fetch(route))
    flights.extend(kiwi.fetch(route))
    flights.extend(secret_flying.fetch(route))

    best: dict[date, Flight] = {}
    for f in flights:
        if f.price <= 0:
            continue
        if f.departure_date not in best or f.price < best[f.departure_date].price:
            best[f.departure_date] = f

    return list(best.values())
