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
