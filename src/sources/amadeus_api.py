"""Amadeus Flight Cheapest Date Search — cheapest fares per date for a route."""

import os
from datetime import date, datetime

from amadeus import Client, ResponseError

from ..models import Flight, Route


def _client() -> Client:
    return Client(
        client_id=os.environ["AMADEUS_CLIENT_ID"],
        client_secret=os.environ["AMADEUS_CLIENT_SECRET"],
    )


def fetch(route: Route) -> list[Flight]:
    """Returns cheapest available fares per departure date for the route window."""
    if not os.environ.get("AMADEUS_CLIENT_ID"):
        print("[amadeus] AMADEUS_CLIENT_ID not set — skipping")
        return []

    results: list[Flight] = []

    try:
        amadeus = _client()
        response = amadeus.shopping.flight_dates.get(
            origin=route.origin,
            destination=route.destination,
            departureDate=f"{route.date_from},{route.date_to}",
            currency=route.currency,
            oneWay=False,
            nonStop=route.max_stops == 0,
        )
    except ResponseError as exc:
        print(f"[amadeus] API error: {exc}")
        return results
    except Exception as exc:
        print(f"[amadeus] unexpected error: {exc}")
        return results

    for offer in response.data:
        try:
            dep_date = date.fromisoformat(offer["departureDate"])
            price = float(offer["price"]["total"])
            deep_link = offer.get("links", {}).get("flightDates", "")

            results.append(
                Flight(
                    origin=route.origin,
                    destination=route.destination,
                    departure_date=dep_date,
                    price=price,
                    currency=route.currency,
                    airline="?",
                    stops=-1,
                    duration_minutes=0,
                    deep_link=deep_link,
                    source="amadeus",
                )
            )
        except Exception:
            continue

    return results
