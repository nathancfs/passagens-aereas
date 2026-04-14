"""Kiwi (Tequila) API — cheapest flights for a route within a date range."""

import os
from datetime import date, timedelta

import httpx

from ..models import Flight, Route

BASE_URL = "https://api.tequila.kiwi.com/v2/search"


def fetch(route: Route) -> list[Flight]:
    """Fetches cheapest flights per day for the given route and date window."""
    api_key = os.environ.get("KIWI_API_KEY", "")
    if not api_key:
        print("[kiwi] KIWI_API_KEY not set — skipping")
        return []

    results: list[Flight] = []

    params = {
        "fly_from": route.origin,
        "fly_to": route.destination,
        "date_from": route.date_from.strftime("%d/%m/%Y"),
        "date_to": route.date_to.strftime("%d/%m/%Y"),
        "curr": route.currency,
        "max_stopovers": route.max_stops,
        "sort": "price",
        "limit": 50,
        "one_for_city": 1,  # one cheapest result per date
    }
    headers = {"apikey": api_key} if api_key else {}

    try:
        response = httpx.get(BASE_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        print(f"[kiwi] fetch error: {exc}")
        return results

    for item in data.get("data", []):
        try:
            results.append(
                Flight(
                    origin=item["flyFrom"],
                    destination=item["flyTo"],
                    departure_date=date.fromtimestamp(item["dTime"]),
                    price=float(item["price"]),
                    currency=route.currency,
                    airline=item.get("airlines", ["?"])[0],
                    stops=len(item.get("route", [])) - 1,
                    duration_minutes=item.get("fly_duration", "0h").replace("h", "").replace("m", "") and _parse_duration(item.get("fly_duration", "0h 0m")),
                    deep_link=item.get("deep_link", ""),
                    source="kiwi",
                )
            )
        except Exception:
            continue

    return results


def _parse_duration(duration_str: str) -> int:
    """Converts '10h 30m' to total minutes."""
    total = 0
    parts = duration_str.split()
    for part in parts:
        if part.endswith("h"):
            total += int(part[:-1]) * 60
        elif part.endswith("m"):
            total += int(part[:-1])
    return total
