# Monitor de Passagens Aéreas

Ferramenta pessoal para monitorar preços de voos e alertar quando aparecer oportunidade abaixo do mínimo histórico.

## Stack
- Python 3.12+
- `httpx` — HTTP requests
- `python-telegram-bot` — alertas Telegram
- `APScheduler` — scheduler
- `SQLite` — histórico de preços em `data/prices.db`
- `Pydantic` — modelos (Flight, Route, PriceRecord, Alert)
- `feedparser` — RSS do Secret Flying
- `pyyaml` — config de rotas
- `python-dotenv` — variáveis de ambiente

## Fontes de dados
- **Kiwi API** (`src/sources/kiwi.py`) — principal, free tier, rota + data
- **Secret Flying RSS** (`src/sources/secret_flying.py`) — error fares de GRU

## Lógica de alerta
1. Busca preços de todas as fontes para cada rota configurada
2. Salva cada resultado no histórico SQLite
3. Compara com mínimo histórico da rota+data
4. Se novo preço ≤ mínimo → dispara alerta (Telegram + email)

## Como rodar
```bash
pip install -r requirements.txt
cp .env.example .env   # preencher credenciais
python -m src.main
```

## Configurar rotas
Editar `config/routes.yaml`:
```yaml
routes:
  - origin: GRU
    destination: LIS
    date_from: 2026-06-01
    date_to: 2026-06-30
    max_stops: 1
    currency: BRL
```

## Env vars necessárias
- `KIWI_API_KEY` — chave da Kiwi/Tequila API
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL_TO`

## Pendências
- Google Flights scraper (`src/sources/google_flights.py`)
- Obter chave Kiwi API (cadastro em tequila.kiwi.com)
- Criar Telegram bot via @BotFather
- Definir destinos e datas reais em routes.yaml
