"""Entry point: runs the Telegram bot + background price monitor."""

import os
import threading

from dotenv import load_dotenv

load_dotenv()

import yaml
from pathlib import Path
from apscheduler.schedulers.blocking import BlockingScheduler

from .db import init_db
from .monitor import run_once
from .alerts import telegram as telegram_alerts, email
from .bot import build_application

CONFIG_PATH = Path(__file__).parent.parent / "config" / "routes.yaml"


def _alert_fn(alert):
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        telegram_alerts.send(alert)
    if os.environ.get("SMTP_USER"):
        email.send(alert)


def _scheduler_thread(interval_hours: int) -> None:
    """Runs the price monitor on a schedule in a background thread."""
    run_once(alert_fn=_alert_fn)

    scheduler = BlockingScheduler()
    scheduler.add_job(run_once, "interval", hours=interval_hours, kwargs={"alert_fn": _alert_fn})
    print(f"[scheduler] running every {interval_hours}h")
    scheduler.start()


def main():
    init_db()

    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    interval_hours = config.get("monitor", {}).get("interval_hours", 6)

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = build_application(token)

    t = threading.Thread(target=_scheduler_thread, args=(interval_hours,), daemon=True)
    t.start()

    print("[main] bot starting — send /start on Telegram")
    # run_polling() is synchronous and manages its own event loop internally
    app.run_polling()


if __name__ == "__main__":
    main()
