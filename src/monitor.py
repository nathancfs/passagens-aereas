"""Core monitor: fetch → compare with historical min → alert."""

import yaml
from datetime import date
from pathlib import Path

from .models import Alert, Flight, PriceRecord, Route
from .db import get_historical_min, save_record
from .sources import kiwi, secret_flying

CONFIG_PATH = Path(__file__).parent.parent / "config" / "routes.yaml"


def load_routes() -> list[Route]:
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    return [Route(**r) for r in config.get("routes", [])]


def run_once(alert_fn=None) -> list[Alert]:
    """
    Runs one full monitoring cycle.
    alert_fn: optional callable(Alert) for sending notifications.
    Returns list of alerts triggered.
    """
    routes = load_routes()
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

            record = PriceRecord(
                route_key=route_key,
                departure_date=flight.departure_date,
                price=flight.price,
                currency=flight.currency,
                source=flight.source,
                deep_link=flight.deep_link,
            )
            save_record(record)

            prev_min = get_historical_min(route_key, flight.departure_date)

            # First record for this route+date — save but don't alert yet
            if prev_min is None:
                print(f"[monitor] {route_key} {flight.departure_date}: first record R${flight.price:.0f}")
                continue

            if flight.price <= prev_min:
                drop_pct = round((1 - flight.price / prev_min) * 100, 1) if prev_min > 0 else 0
                alert = Alert(
                    route_key=route_key,
                    departure_date=flight.departure_date,
                    new_price=flight.price,
                    previous_min=prev_min,
                    drop_pct=drop_pct,
                    deep_link=flight.deep_link,
                    source=flight.source,
                )
                print(f"[monitor] ALERT {route_key} {flight.departure_date}: R${flight.price:.0f} (was R${prev_min:.0f}, -{drop_pct}%)")
                triggered.append(alert)
                if alert_fn:
                    alert_fn(alert)

    return triggered


def _fetch_all(route: Route) -> list[Flight]:
    """Fetches from all sources and deduplicates by (date, price)."""
    flights: list[Flight] = []
    flights.extend(kiwi.fetch(route))
    flights.extend(secret_flying.fetch(route))

    # Deduplicate: keep lowest price per departure date
    best: dict[date, Flight] = {}
    for f in flights:
        if f.price <= 0:
            continue
        if f.departure_date not in best or f.price < best[f.departure_date].price:
            best[f.departure_date] = f

    return list(best.values())
