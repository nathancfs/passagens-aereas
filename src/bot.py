"""Conversational Telegram bot for managing flight price alert subscriptions."""

import re
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .db import delete_subscription, get_subscriptions, save_subscription
from .models import Route, Subscription, AIRPORTS_BY_COUNTRY, is_country_code, expand_country_to_airports
from .sources import google_flights

# ── States ─────────────────────────────────────────────────────────────────────

(
    MENU,
    ASK_ORIGIN, CHOOSE_ORIGIN,
    ASK_DEST, CHOOSE_DEST,
    ASK_TRIP_TYPE,
    ASK_DATE_MODE_DEP,
    ASK_DATE_FROM, ASK_DATE_TO,
    ASK_DATE_MODE_RET,
    ASK_RETURN_FROM, ASK_RETURN_TO,
    ASK_STOPS,
    CONFIRM_SUB,
) = range(14)

# ── Airport map ────────────────────────────────────────────────────────────────

AIRPORT_MAP: dict[str, list[tuple[str, str]]] = {
    # Countries (expand to all airports)
    "br":             [("BR", "🇧🇷 Brasil (todos os aeroportos)")],
    "brasil":         [("BR", "🇧🇷 Brasil (todos os aeroportos)")],
    "argentina":      [("AR", "🇦🇷 Argentina (todos os aeroportos)")],
    "uruguai":        [("UY", "🇺🇾 Uruguai (todos os aeroportos)")],
    "chile":          [("CL", "🇨🇱 Chile (todos os aeroportos)")],
    "colombia":       [("CO", "🇨🇴 Colômbia (todos os aeroportos)")],
    "peru":           [("PE", "🇵🇪 Peru (todos os aeroportos)")],
    "italia":         [("IT", "🇮🇹 Itália (todos os aeroportos)")],
    "italy":          [("IT", "🇮🇹 Itália (todos os aeroportos)")],
    "espanha":        [("ES", "🇪🇸 Espanha (todos os aeroportos)")],
    "spain":          [("ES", "🇪🇸 Espanha (todos os aeroportos)")],
    "portugal":       [("PT", "🇵🇹 Portugal (todos os aeroportos)")],
    "franca":         [("FR", "🇫🇷 França (todos os aeroportos)")],
    "france":         [("FR", "🇫🇷 França (todos os aeroportos)")],
    "alemanha":       [("DE", "🇩🇪 Alemanha (todos os aeroportos)")],
    "germany":        [("DE", "🇩🇪 Alemanha (todos os aeroportos)")],
    "uk":             [("UK", "🇬🇧 Reino Unido (todos os aeroportos)")],
    "reino unido":    [("UK", "🇬🇧 Reino Unido (todos os aeroportos)")],
    "holanda":        [("NL", "🇳🇱 Holanda (todos os aeroportos)")],
    "netherlands":     [("NL", "🇳🇱 Holanda (todos os aeroportos)")],
    "suica":           [("CH", "🇨🇭 Suíça (todos os aeroportos)")],
    "switzerland":    [("CH", "🇨🇭 Suíça (todos os aeroportos)")],
    "austria":        [("AT", "🇦🇹 Áustria (todos os aeroportos)")],
    "belgica":        [("BE", "🇧🇪 Bélgica (todos os aeroportos)")],
    "belgium":        [("BE", "🇧🇪 Bélgica (todos os aeroportos)")],
    "grecia":         [("GR", "🇬🇷 Grécia (todos os aeroportos)")],
    "greece":         [("GR", "🇬🇷 Grécia (todos os aeroportos)")],
    "eua":             [("US", "🇺🇸 EUA (todos os aeroportos)")],
    "usa":            [("US", "🇺🇸 EUA (todos os aeroportos)")],
    "estados unidos": [("US", "🇺🇸 EUA (todos os aeroportos)")],
    "canada":         [("CA", "🇨🇦 Canadá (todos os aeroportos)")],
    "mexico":         [("MX", "🇲🇽 México (todos os aeroportos)")],
    "japao":          [("JP", "🇯🇵 Japão (todos os aeroportos)")],
    "japan":          [("JP", "🇯🇵 Japão (todos os aeroportos)")],
    "australia":      [("AU", "🇦🇺 Austrália (todos os aeroportos)")],
    "nova zelandia":  [("NZ", "🇳🇿 Nova Zelândia (todos os aeroportos)")],
    "new zealand":    [("NZ", "🇳🇿 Nova Zelândia (todos os aeroportos)")],
    # Brazil cities
    "sao paulo":      [("GRU", "São Paulo/Guarulhos"), ("CGH", "São Paulo/Congonhas")],
    "sp":             [("GRU", "São Paulo/Guarulhos")],
    "guarulhos":      [("GRU", "São Paulo/Guarulhos")],
    "gru":            [("GRU", "São Paulo/Guarulhos")],
    "congonhas":      [("CGH", "São Paulo/Congonhas")],
    "cgh":            [("CGH", "São Paulo/Congonhas")],
    "viracopos":      [("VCP", "Campinas/Viracopos")],
    "vcp":            [("VCP", "Campinas/Viracopos")],
    "campinas":       [("VCP", "Campinas/Viracopos")],
    "rio de janeiro": [("GIG", "Rio/Galeão"), ("SDU", "Rio/Santos Dumont")],
    "rio":            [("GIG", "Rio/Galeão"), ("SDU", "Rio/Santos Dumont")],
    "rj":             [("GIG", "Rio/Galeão"), ("SDU", "Rio/Santos Dumont")],
    "galeao":         [("GIG", "Rio/Galeão")],
    "gig":            [("GIG", "Rio/Galeão")],
    "santos dumont":  [("SDU", "Rio/Santos Dumont")],
    "sdu":            [("SDU", "Rio/Santos Dumont")],
    "brasilia":       [("BSB", "Brasília")],
    "bsb":            [("BSB", "Brasília")],
    "belo horizonte": [("CNF", "BH/Confins"), ("PLU", "BH/Pampulha")],
    "bh":             [("CNF", "BH/Confins")],
    "cnf":            [("CNF", "BH/Confins")],
    "confins":        [("CNF", "BH/Confins")],
    "porto alegre":   [("POA", "Porto Alegre")],
    "poa":            [("POA", "Porto Alegre")],
    "recife":         [("REC", "Recife")],
    "rec":            [("REC", "Recife")],
    "salvador":       [("SSA", "Salvador")],
    "ssa":            [("SSA", "Salvador")],
    "fortaleza":      [("FOR", "Fortaleza")],
    "for":            [("FOR", "Fortaleza")],
    "curitiba":       [("CWB", "Curitiba")],
    "cwb":            [("CWB", "Curitiba")],
    "florianopolis":  [("FLN", "Florianópolis")],
    "floripa":        [("FLN", "Florianópolis")],
    "fln":            [("FLN", "Florianópolis")],
    "manaus":         [("MAO", "Manaus")],
    "mao":            [("MAO", "Manaus")],
    "belem":          [("BEL", "Belém")],
    "bel":            [("BEL", "Belém")],
    "natal":          [("NAT", "Natal")],
    "nat":            [("NAT", "Natal")],
    "maceio":         [("MCZ", "Maceió")],
    "mcz":            [("MCZ", "Maceió")],
    # Europe
    "lisboa":         [("LIS", "Lisboa")],
    "lisbon":         [("LIS", "Lisboa")],
    "lis":            [("LIS", "Lisboa")],
    "paris":          [("CDG", "Paris/CDG"), ("ORY", "Paris/Orly")],
    "cdg":            [("CDG", "Paris/CDG")],
    "ory":            [("ORY", "Paris/Orly")],
    "london":         [("LHR", "Londres/Heathrow"), ("LGW", "Londres/Gatwick"), ("STN", "Londres/Stansted")],
    "londres":        [("LHR", "Londres/Heathrow"), ("LGW", "Londres/Gatwick")],
    "lhr":            [("LHR", "Londres/Heathrow")],
    "lgw":            [("LGW", "Londres/Gatwick")],
    "stn":            [("STN", "Londres/Stansted")],
    "roma":           [("FCO", "Roma/Fiumicino")],
    "rome":           [("FCO", "Roma/Fiumicino")],
    "fco":            [("FCO", "Roma/Fiumicino")],
    "milao":          [("MXP", "Milão/Malpensa"), ("LIN", "Milão/Linate")],
    "milan":          [("MXP", "Milão/Malpensa"), ("LIN", "Milão/Linate")],
    "mxp":            [("MXP", "Milão/Malpensa")],
    "lin":            [("LIN", "Milão/Linate")],
    "madrid":         [("MAD", "Madri")],
    "mad":            [("MAD", "Madri")],
    "barcelona":      [("BCN", "Barcelona")],
    "bcn":            [("BCN", "Barcelona")],
    "amsterdam":      [("AMS", "Amsterdam")],
    "amsterda":       [("AMS", "Amsterdam")],
    "ams":            [("AMS", "Amsterdam")],
    "frankfurt":      [("FRA", "Frankfurt")],
    "fra":            [("FRA", "Frankfurt")],
    "munique":        [("MUC", "Munique")],
    "munich":         [("MUC", "Munique")],
    "muc":            [("MUC", "Munique")],
    "zurique":        [("ZRH", "Zurique")],
    "zurich":         [("ZRH", "Zurique")],
    "zrh":            [("ZRH", "Zurique")],
    "genebra":        [("GVA", "Genebra")],
    "geneva":         [("GVA", "Genebra")],
    "gva":            [("GVA", "Genebra")],
    "dublin":         [("DUB", "Dublin")],
    "irlanda":        [("DUB", "Dublin")],
    "dub":            [("DUB", "Dublin")],
    "atenas":         [("ATH", "Atenas")],
    "ath":            [("ATH", "Atenas")],
    "viena":          [("VIE", "Viena")],
    "vie":            [("VIE", "Viena")],
    "praga":          [("PRG", "Praga")],
    "republica tcheca":[("PRG", "Praga")],
    "prg":            [("PRG", "Praga")],
    "varsovia":       [("WAW", "Varsóvia")],
    "polonia":        [("WAW", "Varsóvia")],
    "waw":            [("WAW", "Varsóvia")],
    "estocolmo":      [("ARN", "Estocolmo")],
    "suecia":         [("ARN", "Estocolmo")],
    "arn":            [("ARN", "Estocolmo")],
    "oslo":           [("OSL", "Oslo")],
    "noruega":        [("OSL", "Oslo")],
    "osl":            [("OSL", "Oslo")],
    "copenhague":     [("CPH", "Copenhague")],
    "dinamarca":      [("CPH", "Copenhague")],
    "cph":            [("CPH", "Copenhague")],
    "helsinki":       [("HEL", "Helsinki")],
    "finlandia":      [("HEL", "Helsinki")],
    "hel":            [("HEL", "Helsinki")],
    "bruxelas":       [("BRU", "Bruxelas")],
    "bru":            [("BRU", "Bruxelas")],
    # Americas
    "miami":          [("MIA", "Miami")],
    "mia":            [("MIA", "Miami")],
    "new york":       [("JFK", "Nova York/JFK"), ("EWR", "Newark")],
    "nova york":      [("JFK", "Nova York/JFK"), ("EWR", "Newark")],
    "jfk":            [("JFK", "Nova York/JFK")],
    "ewr":            [("EWR", "Newark")],
    "orlando":        [("MCO", "Orlando")],
    "mco":            [("MCO", "Orlando")],
    "los angeles":    [("LAX", "Los Angeles")],
    "lax":            [("LAX", "Los Angeles")],
    "san francisco":  [("SFO", "San Francisco")],
    "sfo":            [("SFO", "San Francisco")],
    "chicago":        [("ORD", "Chicago/O'Hare")],
    "ord":            [("ORD", "Chicago/O'Hare")],
    "toronto":        [("YYZ", "Toronto")],
    "yyz":            [("YYZ", "Toronto")],
    "cancun":         [("CUN", "Cancún")],
    "cun":            [("CUN", "Cancún")],
    "mex":            [("MEX", "Cidade do México")],
    "buenos aires":   [("EZE", "Buenos Aires/Ezeiza"), ("AEP", "Buenos Aires/Aeroparque")],
    "eze":            [("EZE", "Buenos Aires/Ezeiza")],
    "santiago":       [("SCL", "Santiago")],
    "scl":            [("SCL", "Santiago")],
    "lima":           [("LIM", "Lima")],
    "lim":            [("LIM", "Lima")],
    "bogota":         [("BOG", "Bogotá")],
    "bog":            [("BOG", "Bogotá")],
    # Asia / Middle East / Africa / Oceania
    "dubai":          [("DXB", "Dubai")],
    "dxb":            [("DXB", "Dubai")],
    "abu dhabi":      [("AUH", "Abu Dhabi")],
    "auh":            [("AUH", "Abu Dhabi")],
    "doha":           [("DOH", "Doha")],
    "qatar":          [("DOH", "Doha")],
    "doh":            [("DOH", "Doha")],
    "tokyo":          [("NRT", "Tóquio/Narita"), ("HND", "Tóquio/Haneda")],
    "toquio":         [("NRT", "Tóquio/Narita"), ("HND", "Tóquio/Haneda")],
    "nrt":            [("NRT", "Tóquio/Narita")],
    "hnd":            [("HND", "Tóquio/Haneda")],
    "osaka":          [("KIX", "Osaka/Kansai")],
    "kix":            [("KIX", "Osaka/Kansai")],
    "bangkok":        [("BKK", "Bangkok")],
    "tailandia":      [("BKK", "Bangkok")],
    "bkk":            [("BKK", "Bangkok")],
    "singapura":      [("SIN", "Singapura")],
    "singapore":      [("SIN", "Singapura")],
    "sin":            [("SIN", "Singapura")],
    "hong kong":      [("HKG", "Hong Kong")],
    "hkg":            [("HKG", "Hong Kong")],
    "seul":           [("ICN", "Seul/Incheon")],
    "coreia":         [("ICN", "Seul/Incheon")],
    "icn":            [("ICN", "Seul/Incheon")],
    "xangai":         [("PVG", "Xangai/Pudong")],
    "shanghai":       [("PVG", "Xangai/Pudong")],
    "china":          [("PVG", "Xangai/Pudong"), ("PEK", "Pequim/Capital")],
    "pvg":            [("PVG", "Xangai/Pudong")],
    "pequim":         [("PEK", "Pequim/Capital")],
    "pek":            [("PEK", "Pequim/Capital")],
    "mumbai":         [("BOM", "Mumbai")],
    "india":          [("BOM", "Mumbai"), ("DEL", "Nova Delhi")],
    "bom":            [("BOM", "Mumbai")],
    "nova delhi":     [("DEL", "Nova Delhi")],
    "delhi":          [("DEL", "Nova Delhi")],
    "del":            [("DEL", "Nova Delhi")],
    "bali":           [("DPS", "Bali/Denpasar")],
    "dps":            [("DPS", "Bali/Denpasar")],
    "joanesburgo":    [("JNB", "Joanesburgo")],
    "africa do sul":  [("JNB", "Joanesburgo")],
    "jnb":            [("JNB", "Joanesburgo")],
    "cairo":          [("CAI", "Cairo")],
    "egito":          [("CAI", "Cairo")],
    "cai":            [("CAI", "Cairo")],
    "sydney":         [("SYD", "Sydney")],
    "syd":            [("SYD", "Sydney")],
    "melbourne":      [("MEL", "Melbourne")],
    "mel":            [("MEL", "Melbourne")],
    "auckland":       [("AKL", "Auckland")],
    "akl":            [("AKL", "Auckland")],
}

_STOPS_LABEL = {0: "Direto", 1: "1 parada", 2: "2+ paradas"}


def _normalize(text: str) -> str:
    s = text.lower().strip()
    for pat, rep in [
        (r"[àáâãä]", "a"), (r"[éêë]", "e"), (r"[íî]", "i"),
        (r"[óôõö]", "o"), (r"[úû]", "u"), (r"ç", "c"),
    ]:
        s = re.sub(pat, rep, s)
    return s


def infer_airports(text: str) -> list[tuple[str, str]]:
    n = _normalize(text)

    # IATA code (3 letters)
    if re.match(r"^[a-z]{3}$", n):
        iata = n.upper()
        for opts in AIRPORT_MAP.values():
            for code, name in opts:
                if code == iata:
                    return [(code, name)]
        # Not found as IATA — could be a city name (e.g. "rio" → GIG+SDU)
        if n in AIRPORT_MAP:
            return AIRPORT_MAP[n]
        return [(iata, iata)]

    # City/country name in map (includes "brasil" → BR, "italia" → IT, "br" → BR)
    if n in AIRPORT_MAP:
        return AIRPORT_MAP[n]

    # Country code typed directly (e.g. "IT") — fallback, expands to individual airports
    if is_country_code(n.upper()):
        country = n.upper()
        return [(code, f"{code} ({country})") for code in AIRPORTS_BY_COUNTRY[country]]

    # Fuzzy match
    seen: set[str] = set()
    matches: list[tuple[str, str]] = []
    for key, opts in AIRPORT_MAP.items():
        if n in key or key in n:
            for code, name in opts:
                if code not in seen:
                    matches.append((code, name))
                    seen.add(code)
    return matches


_FALLBACK_AIRPORT_NAMES: dict[str, str] = {
    # City aggregate codes (Google Flights)
    "MIL": "Milão (todos)",
    "LON": "Londres (todos)",
    "NYC": "Nova York (todos)",
    "PAR": "Paris (todos)",
    "TYO": "Tóquio (todos)",
    "OSA": "Osaka (todos)",
    "BUE": "Buenos Aires (todos)",
    "CHI": "Chicago (todos)",
    # South America
    "COR": "Córdoba",
    "MVD": "Montevidéu/Carrasco",
    "MDE": "Medellín",
    # Italy
    "VCE": "Veneza/Marco Polo",
    "NAP": "Nápoles/Capodichino",
    "FLR": "Florença/Peretola",
    "BLQ": "Bolonha",
    # Spain
    "AGP": "Málaga/Costa del Sol",
    "SVQ": "Sevilha",
    "VLC": "Valência",
    # Portugal
    "OPO": "Porto",
    "FAO": "Faro",
    # France
    "NCE": "Nice/Côte d'Azur",
    "LYS": "Lyon",
    "MRS": "Marselha",
    # Germany
    "BER": "Berlim",
    "DUS": "Düsseldorf",
    "HAM": "Hamburgo",
    # UK
    "MAN": "Manchester",
    "EDI": "Edimburgo",
    # USA
    "ATL": "Atlanta",
    "BOS": "Boston",
    # Canada
    "YVR": "Vancouver",
    "YUL": "Montreal",
    # Asia
    "CAN": "Guangzhou",
    # Australia
    "BNE": "Brisbane",
}


def _airport_name(iata: str) -> str:
    """Look up display name for an IATA code in AIRPORT_MAP."""
    for opts in AIRPORT_MAP.values():
        for code, name in opts:
            if code == iata:
                return name
    return _FALLBACK_AIRPORT_NAMES.get(iata, iata)


def _airport_kb(airports: list[tuple[str, str]], todos_code: str | None = None) -> InlineKeyboardMarkup:
    """
    todos_code: if set, overrides the 'Todos' button callback code.
                Use a country code (e.g. 'IT') so the monitor handles expansion,
                instead of creating one subscription per airport.
    """
    buttons = [
        [InlineKeyboardButton(f"{code} — {name}", callback_data=f"ap:{code}:{name[:28]}")]
        for code, name in airports[:5]
    ]
    if todos_code or len(airports) > 1:
        if todos_code:
            all_codes = todos_code
            btn_text = "✈️ Todos os aeroportos"
        else:
            all_codes = "|".join(code for code, _ in airports[:5])
            btn_text = "Todos — " + " + ".join(code for code, _ in airports[:5])
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"ap:all:{all_codes}")])
    buttons.append([InlineKeyboardButton("✏️ Digitar outro", callback_data="ap:other")])
    return InlineKeyboardMarkup(buttons)


def _parse_date(text: str) -> date | None:
    t = _normalize(text)
    months = {
        "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4,
        "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
        "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
        "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
        "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
    }
    # "novembro 2026" or "nov 2026"
    m = re.match(r"(\w+)\s+(\d{4})", t)
    if m and m.group(1) in months:
        return date(int(m.group(2)), months[m.group(1)], 1)
    # "nov/26" or "jun/2026"
    m = re.match(r"^([a-z]+)[/\-](\d{2,4})$", t)
    if m and m.group(1) in months:
        year = int(m.group(2))
        if year < 100:
            year += 2000
        return date(year, months[m.group(1)], 1)
    m = re.match(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", t)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            pass
    m = re.match(r"(\d{1,2})[/\-.](\d{1,2})$", t)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        today = date.today()
        for year in (today.year, today.year + 1):
            try:
                d = date(year, month, day)
                if d >= today:
                    return d
            except ValueError:
                continue
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sub_summary_line(sub: Subscription) -> str:
    trip = "↔ Ida e volta" if sub.trip_type == "round-trip" else "→ Só ida"
    stops = _STOPS_LABEL.get(sub.max_stops, f"{sub.max_stops}+ paradas")
    base = (
        f"<b>{sub.origin} → {sub.destination}</b> | {trip}\n"
        f"   Ida: {sub.date_from.strftime('%d/%m')}–{sub.date_to.strftime('%d/%m/%Y')} | {stops}"
    )
    if sub.trip_type == "round-trip" and sub.return_date_from:
        base += (
            f"\n   Volta: {sub.return_date_from.strftime('%d/%m')}–"
            f"{sub.return_date_to.strftime('%d/%m/%Y')}"
        )
    return base


def _main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔔 Novo alerta", callback_data="menu:new")],
        [InlineKeyboardButton("📋 Meus alertas", callback_data="menu:list"),
         InlineKeyboardButton("✏️ Editar", callback_data="menu:edit")],
        [InlineKeyboardButton("🗑️ Remover alerta", callback_data="menu:del")],
    ])


async def _send_menu(update_or_query, text="O que deseja fazer?") -> None:
    kb = _main_menu_kb()
    if hasattr(update_or_query, "edit_message_text"):
        await update_or_query.edit_message_text(
            f"✈️ <b>Nate's Flights</b>\n\n{text}", parse_mode="HTML", reply_markup=kb
        )
    else:
        await update_or_query.message.reply_text(
            f"✈️ <b>Nate's Flights</b>\n\n{text}", parse_mode="HTML", reply_markup=kb
        )


# ── /start → MENU ──────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await _send_menu(update)
    return MENU


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]

    if action == "new":
        context.user_data.pop("editing_id", None)
        await query.edit_message_text(
            "De onde você vai sair?\n<i>(ex: São Paulo, GRU, Rio, Brasília)</i>",
            parse_mode="HTML",
        )
        return ASK_ORIGIN

    if action == "list":
        chat_id = str(query.from_user.id)
        subs = get_subscriptions(chat_id)
        if not subs:
            await query.answer("Nenhum alerta ativo.", show_alert=True)
            return MENU
        lines = ["<b>Seus alertas ativos:</b>\n"]
        for sub in subs:
            lines.append(_sub_summary_line(sub))
        await query.edit_message_text(
            "\n\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Voltar", callback_data="menu:back")
            ]]),
        )
        return MENU

    if action == "edit":
        chat_id = str(query.from_user.id)
        subs = get_subscriptions(chat_id)
        if not subs:
            await query.answer("Nenhum alerta para editar.", show_alert=True)
            return MENU
        buttons = [
            [InlineKeyboardButton(
                f"✏️ {sub.origin}→{sub.destination} {sub.date_from.strftime('%d/%m')}-{sub.date_to.strftime('%d/%m')}",
                callback_data=f"edit:{sub.id}",
            )]
            for sub in subs
        ]
        buttons.append([InlineKeyboardButton("« Voltar", callback_data="menu:back")])
        await query.edit_message_text(
            "Qual alerta deseja editar?",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return MENU

    if action == "del":
        chat_id = str(query.from_user.id)
        subs = get_subscriptions(chat_id)
        if not subs:
            await query.answer("Nenhum alerta para remover.", show_alert=True)
            return MENU
        buttons = [
            [InlineKeyboardButton(
                f"🗑️ {sub.origin}→{sub.destination} {sub.date_from.strftime('%d/%m')}-{sub.date_to.strftime('%d/%m')}",
                callback_data=f"del:{sub.id}",
            )]
            for sub in subs
        ]
        buttons.append([InlineKeyboardButton("🗑️ Remover todos", callback_data="del:all")])
        buttons.append([InlineKeyboardButton("« Voltar", callback_data="menu:back")])
        await query.edit_message_text(
            "Qual alerta deseja remover?",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return MENU

    if action == "back":
        await _send_menu(query)
        return MENU

    return MENU


async def handle_manage_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles edit:{id} and del:{id} callbacks from the management views."""
    query = update.callback_query
    await query.answer()

    kind, value = query.data.split(":", 1)

    if kind == "edit":
        sub_id = int(value)
        context.user_data["editing_id"] = sub_id
        await query.edit_message_text(
            "Reconfigurando o alerta.\n\n"
            "De onde você vai sair?\n<i>(ex: São Paulo, GRU, Rio)</i>",
            parse_mode="HTML",
        )
        return ASK_ORIGIN

    if kind == "del":
        chat_id = str(query.from_user.id)
        if value == "all":
            for sub in get_subscriptions(chat_id):
                delete_subscription(sub.id)
            await _send_menu(query, "Todos os alertas removidos.")
        else:
            delete_subscription(int(value))
            await _send_menu(query, "Alerta removido.")
        return MENU

    return MENU


# ── Questionnaire ──────────────────────────────────────────────────────────────

async def ask_origin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    airports = infer_airports(update.message.text)
    if not airports:
        await update.message.reply_text(
            "Não reconheci. Tente o nome da cidade ou código IATA (ex: GRU, SDU, BSB)."
        )
        return ASK_ORIGIN
    if len(airports) == 1:
        code, name = airports[0]
        if is_country_code(code):
            airport_options = [(c, _airport_name(c)) for c in AIRPORTS_BY_COUNTRY[code]]
            await update.message.reply_text(
                f"Aeroportos de {name}. Qual deseja monitorar?",
                reply_markup=_airport_kb(airport_options, todos_code=code),
            )
            return CHOOSE_ORIGIN
        context.user_data["origin"] = code
        context.user_data.pop("origin_all", None)
        await update.message.reply_text(
            f"Saindo de <b>{name} ({code})</b>.\n\nPara onde vai?\n"
            "<i>(ex: Lisboa, Itália, Paris, Miami)</i>",
            parse_mode="HTML",
        )
        return ASK_DEST
    await update.message.reply_text(
        f"Encontrei {len(airports)} opções. Qual aeroporto de origem?",
        reply_markup=_airport_kb(airports),
    )
    return CHOOSE_ORIGIN


async def choose_origin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "ap:other":
        await query.edit_message_text("Tente outro nome ou código IATA:")
        return ASK_ORIGIN
    if query.data.startswith("ap:all:"):
        raw = query.data[len("ap:all:"):]
        if is_country_code(raw):
            # Country code — single subscription, monitor expands to airports
            context.user_data["origin"] = raw
            context.user_data.pop("origin_all", None)
            label = raw
        else:
            codes = raw.split("|")
            context.user_data["origin"] = codes[0]
            context.user_data["origin_all"] = codes
            label = " + ".join(codes)
        await query.edit_message_text(
            f"Saindo de <b>{label}</b>.\n\nPara onde vai?\n"
            "<i>(ex: Lisboa, Itália, Paris, Miami)</i>",
            parse_mode="HTML",
        )
        return ASK_DEST
    _, code, name = query.data.split(":", 2)
    context.user_data["origin"] = code
    context.user_data.pop("origin_all", None)
    await query.edit_message_text(
        f"Saindo de <b>{name} ({code})</b>.\n\nPara onde vai?\n"
        "<i>(ex: Lisboa, Itália, Paris, Miami)</i>",
        parse_mode="HTML",
    )
    return ASK_DEST


async def ask_dest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    airports = infer_airports(update.message.text)
    if not airports:
        await update.message.reply_text(
            "Não reconheci. Tente o nome da cidade ou código IATA (ex: LIS, CDG, MXP)."
        )
        return ASK_DEST
    if len(airports) == 1:
        code, name = airports[0]
        if is_country_code(code):
            airport_options = [(c, _airport_name(c)) for c in AIRPORTS_BY_COUNTRY[code]]
            await update.message.reply_text(
                f"Aeroportos de {name}. Qual deseja monitorar?",
                reply_markup=_airport_kb(airport_options, todos_code=code),
            )
            return CHOOSE_DEST
        context.user_data["destination"] = code
        context.user_data.pop("dest_all", None)
        await _ask_trip_type(update.message, name, code)
        return ASK_TRIP_TYPE
    await update.message.reply_text(
        f"Encontrei {len(airports)} opções. Qual aeroporto de destino?",
        reply_markup=_airport_kb(airports),
    )
    return CHOOSE_DEST


async def choose_dest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "ap:other":
        await query.edit_message_text("Tente outro destino:")
        return ASK_DEST
    if query.data.startswith("ap:all:"):
        raw = query.data[len("ap:all:"):]
        if is_country_code(raw):
            # Country code — single subscription, monitor expands to airports
            context.user_data["destination"] = raw
            context.user_data.pop("dest_all", None)
            label = raw
        else:
            codes = raw.split("|")
            context.user_data["destination"] = codes[0]
            context.user_data["dest_all"] = codes
            label = " + ".join(codes)
        await _ask_trip_type(query, label, "")
        return ASK_TRIP_TYPE
    _, code, name = query.data.split(":", 2)
    context.user_data["destination"] = code
    context.user_data.pop("dest_all", None)
    await _ask_trip_type(query, name, code)
    return ASK_TRIP_TYPE


async def _ask_trip_type(msg_or_query, dest_name: str, dest_code: str) -> None:
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✈️ Só ida", callback_data="trip:one-way"),
        InlineKeyboardButton("🔄 Ida e volta", callback_data="trip:round-trip"),
    ]])
    dest_label = f"{dest_name} ({dest_code})" if dest_code else dest_name
    text = (
        f"Destino: <b>{dest_label}</b>.\n\n"
        "Tipo de viagem?"
    )
    if hasattr(msg_or_query, "edit_message_text"):
        await msg_or_query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await msg_or_query.reply_text(text, parse_mode="HTML", reply_markup=kb)


def _parse_date_range(text: str) -> tuple[date, date] | None:
    """Parses 'X a Y' or 'X - Y' (spaces required around dash) into (date_from, date_to)."""
    sep = re.split(r"\s+a\s+|\s+-\s+|\s+–\s+", text.strip(), maxsplit=1)
    if len(sep) == 2:
        d1 = _parse_date(sep[0].strip())
        d2 = _parse_date(sep[1].strip())
        if d1 and d2 and d2 >= d1:
            return d1, d2
    return None


_DATE_HINT_EXACT = "<i>(ex: 12/12/26 ou 12/12/2026)</i>"
_DATE_HINT_RANGE = "<i>(ex: 12/12/26 a 15/01/27)</i>"
_DATE_HINT_RANGE_END = "<i>(ex: 15/01/27)</i>"


async def _ask_date_mode(msg_or_query, label: str) -> None:
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📅 Data específica", callback_data=f"datemode:{label}:exact"),
        InlineKeyboardButton("📆 Período flexível", callback_data=f"datemode:{label}:range"),
    ]])
    text = f"Datas de <b>{label}</b> — data fixa ou período?"
    if hasattr(msg_or_query, "edit_message_text"):
        await msg_or_query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await msg_or_query.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def ask_trip_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["trip_type"] = query.data.split(":")[1]
    await _ask_date_mode(query, "partida")
    return ASK_DATE_MODE_DEP


async def ask_trip_type_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles text input when user types instead of clicking trip type buttons."""
    t = _normalize(update.message.text)
    if any(k in t for k in ("volta", "round", "ida e volta", "roundtrip")):
        context.user_data["trip_type"] = "round-trip"
    else:
        context.user_data["trip_type"] = "one-way"
    await _ask_date_mode(update.message, "partida")
    return ASK_DATE_MODE_DEP


async def handle_date_mode_dep(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    mode = query.data.split(":")[-1]  # "exact" or "range"
    context.user_data["date_mode"] = mode
    if mode == "exact":
        await query.edit_message_text(
            f"Qual a data de <b>partida</b>?\n{_DATE_HINT_EXACT}", parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            f"Período de <b>partida</b>?\n{_DATE_HINT_RANGE}", parse_mode="HTML"
        )
    return ASK_DATE_FROM


async def ask_date_from(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    mode = context.user_data.get("date_mode", "range")

    if mode == "exact":
        d = _parse_date(text)
        if d is None:
            await update.message.reply_text(
                f"Não entendi. Tente: {_DATE_HINT_EXACT}", parse_mode="HTML"
            )
            return ASK_DATE_FROM
        if d < date.today():
            await update.message.reply_text("Essa data já passou. Tente uma data futura.")
            return ASK_DATE_FROM
        context.user_data["date_from"] = d
        context.user_data["date_to"] = d
        if context.user_data.get("trip_type") == "round-trip":
            await _ask_date_mode(update.message, "retorno")
            return ASK_DATE_MODE_RET
        await _ask_stops(update.message)
        return ASK_STOPS

    # range mode
    rng = _parse_date_range(text)
    if rng:
        d_from, d_to = rng
        if d_from < date.today():
            await update.message.reply_text("A data inicial já passou. Tente datas futuras.")
            return ASK_DATE_FROM
        context.user_data["date_from"] = d_from
        context.user_data["date_to"] = d_to
        if context.user_data.get("trip_type") == "round-trip":
            await _ask_date_mode(update.message, "retorno")
            return ASK_DATE_MODE_RET
        await _ask_stops(update.message)
        return ASK_STOPS

    d = _parse_date(text)
    if d is None:
        await update.message.reply_text(
            f"Não entendi. Tente: {_DATE_HINT_RANGE}", parse_mode="HTML"
        )
        return ASK_DATE_FROM
    if d < date.today():
        await update.message.reply_text("Essa data já passou. Tente uma data futura.")
        return ASK_DATE_FROM
    context.user_data["date_from"] = d
    await update.message.reply_text(
        f"Partida a partir de <b>{d.strftime('%d/%m/%Y')}</b>.\n\n"
        f"Até qual data?\n{_DATE_HINT_RANGE_END}",
        parse_mode="HTML",
    )
    return ASK_DATE_TO


async def ask_date_to(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    d = _parse_date(update.message.text)
    if d is None:
        await update.message.reply_text(
            f"Não entendi. Tente: {_DATE_HINT_RANGE_END}", parse_mode="HTML"
        )
        return ASK_DATE_TO
    if d < context.user_data["date_from"]:
        await update.message.reply_text("A data final deve ser depois da inicial.")
        return ASK_DATE_TO
    context.user_data["date_to"] = d

    if context.user_data.get("trip_type") == "round-trip":
        await _ask_date_mode(update.message, "retorno")
        return ASK_DATE_MODE_RET

    await _ask_stops(update.message)
    return ASK_STOPS


async def handle_date_mode_ret(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    mode = query.data.split(":")[-1]
    context.user_data["return_date_mode"] = mode
    if mode == "exact":
        await query.edit_message_text(
            f"Qual a data de <b>retorno</b>?\n{_DATE_HINT_EXACT}", parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            f"Período de <b>retorno</b>?\n{_DATE_HINT_RANGE}", parse_mode="HTML"
        )
    return ASK_RETURN_FROM


async def ask_return_from(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    mode = context.user_data.get("return_date_mode", "range")
    min_date = context.user_data["date_to"]

    if mode == "exact":
        d = _parse_date(text)
        if d is None:
            await update.message.reply_text(
                f"Não entendi. Tente: {_DATE_HINT_EXACT}", parse_mode="HTML"
            )
            return ASK_RETURN_FROM
        if d < min_date:
            await update.message.reply_text("O retorno deve ser depois da partida.")
            return ASK_RETURN_FROM
        context.user_data["return_date_from"] = d
        context.user_data["return_date_to"] = d
        await _ask_stops(update.message)
        return ASK_STOPS

    # range mode
    rng = _parse_date_range(text)
    if rng:
        d_from, d_to = rng
        if d_from < min_date:
            await update.message.reply_text("O retorno deve ser depois da partida.")
            return ASK_RETURN_FROM
        context.user_data["return_date_from"] = d_from
        context.user_data["return_date_to"] = d_to
        await _ask_stops(update.message)
        return ASK_STOPS

    # Single date — ask for end date
    d = _parse_date(text)
    if d is None:
        await update.message.reply_text(
            f"Não entendi. Tente: {_DATE_HINT_RANGE}", parse_mode="HTML"
        )
        return ASK_RETURN_FROM
    if d < min_date:
        await update.message.reply_text("O retorno deve ser depois da partida.")
        return ASK_RETURN_FROM
    context.user_data["return_date_from"] = d
    await update.message.reply_text(
        f"Retorno a partir de <b>{d.strftime('%d/%m/%Y')}</b>.\n\n"
        f"Até qual data?\n{_DATE_HINT_RANGE_END}",
        parse_mode="HTML",
    )
    return ASK_RETURN_TO


async def ask_return_to(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    d = _parse_date(update.message.text)
    if d is None:
        await update.message.reply_text(
            f"Não entendi. Tente: {_DATE_HINT_RANGE_END}", parse_mode="HTML"
        )
        return ASK_RETURN_TO
    if d < context.user_data["return_date_from"]:
        await update.message.reply_text("A data final deve ser depois da inicial.")
        return ASK_RETURN_TO
    context.user_data["return_date_to"] = d
    await _ask_stops(update.message)
    return ASK_STOPS


async def _ask_stops(msg) -> None:
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("Direto", callback_data="stops:0"),
        InlineKeyboardButton("1 parada", callback_data="stops:1"),
        InlineKeyboardButton("2+ paradas", callback_data="stops:2"),
    ]])
    await msg.reply_text(
        "Máximo de <b>paradas/conexões</b> aceitas?",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def ask_stops(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    stops = int(query.data.split(":")[1])
    context.user_data["max_stops"] = stops

    origin = context.user_data["origin"]
    dest = context.user_data["destination"]
    origin_all = context.user_data.get("origin_all", [origin])
    dest_all = context.user_data.get("dest_all", [dest])
    date_from: date = context.user_data["date_from"]
    date_to: date = context.user_data["date_to"]
    trip_type = context.user_data.get("trip_type", "one-way")
    stops_label = _STOPS_LABEL[stops]

    origin_label = " + ".join(origin_all)
    dest_label = " + ".join(dest_all)
    trip_label = "Ida e volta" if trip_type == "round-trip" else "Só ida"
    summary_lines = [
        f"Buscando <b>{origin_label} → {dest_label}</b> | {trip_label}",
        f"Partida: {date_from.strftime('%d/%m')}–{date_to.strftime('%d/%m/%Y')} | {stops_label}",
    ]
    if trip_type == "round-trip":
        rf = context.user_data.get("return_date_from")
        rt = context.user_data.get("return_date_to")
        if rf and rt:
            summary_lines.append(f"Retorno: {rf.strftime('%d/%m')}–{rt.strftime('%d/%m/%Y')}")
    summary_lines.append("\n⏳ Aguarde...")

    await query.edit_message_text("\n".join(summary_lines), parse_mode="HTML")

    preview_origin = expand_country_to_airports(origin)[0]
    preview_dest = expand_country_to_airports(dest)[0]
    route = Route(
        origin=preview_origin,
        destination=preview_dest,
        date_from=date_from,
        date_to=date_to,
        max_stops=stops,
    )
    try:
        flights = google_flights.fetch(route)
    except Exception:
        flights = []

    prices = [f.price for f in flights if f.price > 0]
    preview_label = (
        f"<i>({preview_origin}→{preview_dest})</i> "
        if (preview_origin != origin or preview_dest != dest) else ""
    )
    if prices:
        avg = sum(prices) / len(prices)
        low = min(prices)
        best = min(flights, key=lambda f: f.price)
        context.user_data["current_min"] = low
        price_info = (
            f"💰 Preço médio ida {preview_label}: R$ {avg:,.0f}\n"
            f"📉 Mínimo encontrado: R$ {low:,.0f} ({best.departure_date.strftime('%d/%m')})\n\n"
            "Vou te avisar quando aparecer algo <b>abaixo do mínimo histórico</b>."
        )
    else:
        context.user_data["current_min"] = None
        price_info = "⚠️ Não achei preços agora, mas vou monitorar e te avisar quando encontrar."

    confirm_text = "\n".join(summary_lines[:-1]).replace("⏳ Aguarde...", "").strip()
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirmar alerta", callback_data="confirm:yes"),
        InlineKeyboardButton("❌ Cancelar", callback_data="confirm:no"),
    ]])
    await query.edit_message_text(
        f"{confirm_text}\n\n{price_info}",
        parse_mode="HTML",
        reply_markup=kb,
    )
    return CONFIRM_SUB


async def confirm_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "confirm:no":
        await _send_menu(query, "Cancelado.")
        return MENU

    editing_id = context.user_data.pop("editing_id", None)
    if editing_id is not None:
        delete_subscription(editing_id)

    origin_all = context.user_data.get("origin_all", [context.user_data["origin"]])
    dest_all = context.user_data.get("dest_all", [context.user_data["destination"]])

    count = 0
    for orig in origin_all:
        for dst in dest_all:
            sub = Subscription(
                chat_id=str(query.from_user.id),
                origin=orig,
                destination=dst,
                date_from=context.user_data["date_from"],
                date_to=context.user_data["date_to"],
                max_stops=context.user_data["max_stops"],
                trip_type=context.user_data.get("trip_type", "one-way"),
                return_date_from=context.user_data.get("return_date_from"),
                return_date_to=context.user_data.get("return_date_to"),
            )
            save_subscription(sub)
            count += 1

    origin_label = " + ".join(origin_all)
    dest_label = " + ".join(dest_all)
    action = "atualizado" if editing_id else "criado"
    rotas = f" ({count} rotas)" if count > 1 else ""
    await _send_menu(
        query,
        f"✅ Alerta {action}{rotas}! Vou monitorar <b>{origin_label} → {dest_label}</b> "
        f"e te avisar quando o preço estiver abaixo do mínimo histórico.",
    )
    return MENU


async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _send_menu(update, "Configuração cancelada.")
    return MENU


# ── Application builder ────────────────────────────────────────────────────────

def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MENU: [
                CallbackQueryHandler(handle_menu, pattern=r"^menu:"),
                CallbackQueryHandler(handle_manage_action, pattern=r"^(edit|del):"),
            ],
            ASK_ORIGIN:    [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_origin)],
            CHOOSE_ORIGIN: [
                CallbackQueryHandler(choose_origin, pattern=r"^ap:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_origin),  # re-busca se digitar
            ],
            ASK_DEST:      [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_dest)],
            CHOOSE_DEST:   [
                CallbackQueryHandler(choose_dest, pattern=r"^ap:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_dest),  # re-busca se digitar
            ],
            ASK_TRIP_TYPE: [
                CallbackQueryHandler(ask_trip_type, pattern=r"^trip:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_trip_type_text),
            ],
            ASK_DATE_MODE_DEP: [CallbackQueryHandler(handle_date_mode_dep, pattern=r"^datemode:partida:")],
            ASK_DATE_FROM:     [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_date_from)],
            ASK_DATE_TO:       [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_date_to)],
            ASK_DATE_MODE_RET: [CallbackQueryHandler(handle_date_mode_ret, pattern=r"^datemode:retorno:")],
            ASK_RETURN_FROM:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_return_from)],
            ASK_RETURN_TO:     [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_return_to)],
            ASK_STOPS:     [CallbackQueryHandler(ask_stops, pattern=r"^stops:")],
            CONFIRM_SUB:   [CallbackQueryHandler(confirm_subscription, pattern=r"^confirm:")],
        },
        fallbacks=[CommandHandler("cancelar", cancel_conv)],
        allow_reentry=True,
        per_message=False,
    )

    app.add_handler(conv)
    return app
