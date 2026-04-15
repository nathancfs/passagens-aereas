"""Core monitor: fetch → compare with historical min → alert."""

import yaml
from datetime import date
from pathlib import Path

from .models import Alert, Flight, PriceRecord, Route
from .db import get_historical_min, save_record, get_subscriptions
from .sources import google_flights, kiwi, secret_flying

CONFIG_PATH = Path(__file__).parent.parent / "config" / "routes.yaml"


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


def run_once(alert_fn=None) -> list[Alert]:
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

            prev_min = get_historical_min(route_key, flight.departure_date)

            record = PriceRecord(
                route_key=route_key,
                departure_date=flight.departure_date,
                price=flight.price,
                currency=flight.currency,
                source=flight.source,
                deep_link=flight.deep_link,
            )
            save_record(record)

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
                    chat_id=route.chat_id,
                )
                print(f"[monitor] ALERT {route_key} {flight.departure_date}: R${flight.price:.0f} (was R${prev_min:.0f}, -{drop_pct}%)")
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
