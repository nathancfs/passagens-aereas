from datetime import date, datetime
from pydantic import BaseModel


class Route(BaseModel):
    origin: str
    destination: str
    date_from: date
    date_to: date
    max_stops: int = 1
    currency: str = "BRL"
    chat_id: str | None = None  # set for subscription-based routes


class Flight(BaseModel):
    origin: str
    destination: str
    departure_date: date
    price: float
    currency: str
    airline: str
    stops: int
    duration_minutes: int
    deep_link: str
    source: str  # "kiwi", "google_flights", "secret_flying"
    fetched_at: datetime = None

    def model_post_init(self, __context):
        if self.fetched_at is None:
            self.fetched_at = datetime.utcnow()


class PriceRecord(BaseModel):
    route_key: str          # "GRU-LIS"
    departure_date: date
    price: float
    currency: str
    source: str
    deep_link: str
    recorded_at: datetime = None

    def model_post_init(self, __context):
        if self.recorded_at is None:
            self.recorded_at = datetime.utcnow()


class Alert(BaseModel):
    route_key: str
    departure_date: date
    new_price: float
    previous_min: float
    drop_pct: float
    deep_link: str
    source: str
    chat_id: str | None = None  # if set, send to this chat instead of env default
    # Score fields (percentile-based)
    score_label: str = ""       # "Mínima histórica 🔥", "Ótimo 🟢", "Bom 🟡"
    score_pct: float = 0.0      # % of history records with higher price
    hist_mean: float = 0.0
    hist_min: float = 0.0
    hist_count: int = 0


class Subscription(BaseModel):
    id: int | None = None
    chat_id: str
    origin: str
    destination: str
    date_from: date
    date_to: date
    max_stops: int = 1
    currency: str = "BRL"
    trip_type: str = "one-way"        # "one-way" or "round-trip"
    return_date_from: date | None = None
    return_date_to: date | None = None
    active: bool = True
    created_at: datetime = None

    def model_post_init(self, __context):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    @property
    def route_key(self) -> str:
        return f"{self.origin}-{self.destination}"


# Mapping of country codes to main airports (IATA codes)
# Google Flights supports city codes (e.g., MIL = all Milan airports)
AIRPORTS_BY_COUNTRY: dict[str, list[str]] = {
    # South America
    "BR": ["GRU", "GIG", "VCP", "CNF", "BSB", "POA", "CWB"],
    "AR": ["EZE", "AEP", "COR"],
    "UY": ["MVD"],
    "CL": ["SCL"],
    "CO": ["BOG", "MDE"],
    "PE": ["LIM"],
    # Europe
    "IT": ["FCO", "MIL", "VCE", "NAP", "FLR", "BLQ"],
    "ES": ["MAD", "BCN", "AGP", "SVQ", "VLC"],
    "PT": ["LIS", "OPO", "FAO"],
    "FR": ["CDG", "ORY", "NCE", "LYS", "MRS"],
    "DE": ["FRA", "MUC", "BER", "DUS", "HAM"],
    "UK": ["LHR", "LGW", "MAN", "EDI"],
    "NL": ["AMS"],
    "CH": ["ZRH", "GVA"],
    "AT": ["VIE"],
    "BE": ["BRU"],
    "GR": ["ATH"],
    # North America
    "US": ["JFK", "LAX", "MIA", "ORD", "ATL", "SFO", "BOS"],
    "CA": ["YYZ", "YVR", "YUL"],
    "MX": ["MEX", "CUN"],
    # Asia
    "JP": ["NRT", "HND", "KIX"],
    "CN": ["PEK", "PVG", "CAN", "HKG"],
    "TH": ["BKK"],
    "SG": ["SIN"],
    "AE": ["DXB"],
    # Oceania
    "AU": ["SYD", "MEL", "BNE"],
    "NZ": ["AKL"],
}


def is_country_code(code: str) -> bool:
    """Check if a code is a country code (2 letters, uppercase)."""
    return len(code) == 2 and code.isupper() and code in AIRPORTS_BY_COUNTRY


def expand_country_to_airports(code: str) -> list[str]:
    """Expand a country code to its main airports. Returns [code] if not a country."""
    if is_country_code(code):
        return AIRPORTS_BY_COUNTRY.get(code, [code])
    return [code]  # Already an airport code
