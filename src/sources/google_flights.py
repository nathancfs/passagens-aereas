"""Google Flights via fast-flights — no API key required."""

import time
from datetime import date, timedelta

from fast_flights import FlightData, Passengers, get_flights

from ..models import Flight, Route

# Sample every N days within the date window — reduces requests per run.
# At 6h interval: 5-day step = ~6 requests/run instead of 30.
DATE_STEP_DAYS = 5
REQUEST_DELAY_SECONDS = 3


def fetch(route: Route) -> list[Flight]:
    """Samples cheapest flights across the route's date window."""
    results: list[Flight] = []

    current = route.date_from
    while current <= route.date_to:
        flights = _fetch_date(route, current)
        results.extend(flights)
        current += timedelta(days=DATE_STEP_DAYS)
        if current <= route.date_to:
            time.sleep(REQUEST_DELAY_SECONDS)

    return results


def _fetch_date(route: Route, dep_date: date) -> list[Flight]:
    try:
        result = get_flights(
            flight_data=[
                FlightData(
                    date=dep_date.strftime("%Y-%m-%d"),
                    from_airport=route.origin,
                    to_airport=route.destination,
                )
            ],
            trip="one-way",
            seat="economy",
            passengers=Passengers(adults=1),
            fetch_mode="common",
        )
    except Exception as exc:
        print(f"[google_flights] error on {dep_date}: {exc}")
        return []

    flights = []
    # Sort by price ascending, take top 3
    sorted_flights = sorted(
        result.flights,
        key=lambda f: _parse_price(str(getattr(f, "price", "0")))
    )
    for f in sorted_flights[:3]:
        try:
            price = _parse_price(str(getattr(f, "price", "0")))
            if price <= 0:
                continue

            flights.append(
                Flight(
                    origin=route.origin,
                    destination=route.destination,
                    departure_date=dep_date,
                    price=price,
                    currency=route.currency,
                    airline=getattr(f, "name", "?"),
                    stops=getattr(f, "stops", -1),
                    duration_minutes=_parse_duration(getattr(f, "duration", "")),
                    deep_link="https://www.google.com/travel/flights",
                    source="google_flights",
                )
            )
        except Exception:
            continue

    return flights


def _parse_price(raw: str) -> float:
    import re
    match = re.search(r"[\d.,]+", raw.replace(",", ""))
    if match:
        try:
            return float(match.group().replace(",", ""))
        except ValueError:
            pass
    return 0.0


def _parse_duration(raw: str) -> int:
    """Converts '10 hr 30 min' or '10h30m' to total minutes."""
    import re
    hours = re.search(r"(\d+)\s*h", raw)
    mins = re.search(r"(\d+)\s*m", raw)
    total = 0
    if hours:
        total += int(hours.group(1)) * 60
    if mins:
        total += int(mins.group(1))
    return total
