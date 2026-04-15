# Monitor de Passagens Aéreas

Ferramenta pessoal para monitorar preços de voos e alertar quando aparecer oportunidade abaixo do mínimo histórico.

## Stack
- Python 3.12+
- `httpx` — HTTP requests
- `python-telegram-bot` — alertas Telegram
- `APScheduler` — scheduler
- `SQLite` — histórico de preços em `data/prices.db`
- `Pydantic` — modelos (Flight, Route, PriceRecord, Alert, Subscription)
- `fast-flights` — Google Flights scraper (sem API key)
- `feedparser` — RSS do Secret Flying
- `pyyaml` — config de rotas
- `python-dotenv` — variáveis de ambiente

## Fontes de dados
- **Google Flights** (`src/sources/google_flights.py`) — principal, via fast-flights
- **Kiwi API** (`src/sources/kiwi.py`) — secundário, free tier (requer KIWI_API_KEY)
- **Secret Flying RSS** (`src/sources/secret_flying.py`) — error fares de GRU

## Lógica de alerta
1. Busca preços de todas as fontes para cada rota configurada
2. Salva cada resultado no histórico SQLite
3. Compara com histórico via percentil (não mínimo absoluto)
4. Labels: "Mínima histórica 🔥" (top 10%), "Ótimo 🟢" (top 25%), "Bom 🟡" (top 40%)
5. Dispara alerta via Telegram + email

## Bot Telegram — fluxo de subscription
1. `/start` → menu principal
2. "Novo alerta" → pergunta origem → destino → tipo de viagem
3. Origem/destino aceitam: código IATA (GRU), cidade (São Paulo, Roma), ou país (Brasil, Itália)
4. Cidades com múltiplos aeroportos mostram teclado com opção "Todos"
5. Países mostram aeroportos individuais + "✈️ Todos os aeroportos" → armazena código de país (BR, IT), monitor expande em tempo de execução
6. Datas: botões "📅 Data específica" ou "📆 Período flexível" → aceita `12/12/26` ou `12/12/26 a 15/01/27`

## Expansão de países
`models.py` contém `AIRPORTS_BY_COUNTRY` — mapeamento de código de país → aeroportos principais.
`monitor.py/_subscription_routes()` expande automaticamente antes de buscar preços.
Exemplo: subscription BR→IT gera rotas GRU→FCO, GRU→MIL, GRU→VCE, GIG→FCO, etc.

## Como rodar local (dev)
```bash
pip install -r requirements.txt
# criar .env.local com token do bot de dev (ver .env.example)
set DOTENV_PATH=.env.local && python -m src.main
```

## Como rodar produção (Oracle)
```bash
python -m src.main   # usa .env padrão
```

## Env vars necessárias
- `KIWI_API_KEY` — chave da Kiwi/Tequila API (opcional)
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL_TO` (opcional)

## Pendências
- Obter chave Kiwi API (cadastro em tequila.kiwi.com) para segunda fonte de preços
