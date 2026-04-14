"""Secret Flying RSS — error fares and flash deals mentioning GRU / São Paulo."""

import feedparser

from ..models import Flight, Route

FEED_URL = "https://www.secretflying.com/posts/feed/"
GRU_KEYWORDS = ["GRU", "São Paulo", "Sao Paulo", "Guarulhos", "Congonhas", "CGH"]


def fetch(route: Route) -> list[Flight]:
    """Parses Secret Flying RSS and returns entries relevant to the route."""
    results: list[Flight] = []

    try:
        feed = feedparser.parse(FEED_URL)
    except Exception as exc:
        print(f"[secret_flying] feed error: {exc}")
        return results

    destination_keywords = _destination_keywords(route.destination)

    for entry in feed.entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        text = f"{title} {summary}".upper()

        origin_match = any(kw.upper() in text for kw in GRU_KEYWORDS)
        dest_match = any(kw.upper() in text for kw in destination_keywords)

        if not (origin_match or dest_match):
            continue

        price = _extract_price(text)

        results.append(
            Flight(
                origin=route.origin,
                destination=route.destination,
                departure_date=route.date_from,  # RSS doesn't have exact dates
                price=price or 0.0,
                currency=route.currency,
                airline="?",
                stops=-1,       # unknown
                duration_minutes=0,
                deep_link=entry.get("link", ""),
                source="secret_flying",
            )
        )

    return results


def _destination_keywords(iata: str) -> list[str]:
    """Maps IATA codes to city name keywords for text matching."""
    mapping = {
        "LIS": ["LIS", "Lisboa", "Lisbon", "Portugal"],
        "MAD": ["MAD", "Madrid", "Spain", "Espanha"],
        "CDG": ["CDG", "Paris", "France"],
        "LHR": ["LHR", "London", "Londres"],
        "MIA": ["MIA", "Miami", "Florida"],
        "JFK": ["JFK", "New York", "Nova York"],
        "EZE": ["EZE", "Buenos Aires", "Argentina"],
    }
    return mapping.get(iata, [iata])


def _extract_price(text: str) -> float | None:
    """Tries to extract a numeric price from the text."""
    import re
    match = re.search(r"R\$\s?(\d[\d.,]+)", text)
    if match:
        raw = match.group(1).replace(".", "").replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            pass
    return None
