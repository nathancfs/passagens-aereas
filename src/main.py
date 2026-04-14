"""Entry point: runs the monitor on a schedule."""

import os
from dotenv import load_dotenv

load_dotenv()

import yaml
from pathlib import Path
from apscheduler.schedulers.blocking import BlockingScheduler

from .db import init_db
from .monitor import run_once
from .alerts import telegram, email

CONFIG_PATH = Path(__file__).parent.parent / "config" / "routes.yaml"


def alert_fn(alert):
    """Dispatches an alert to all configured channels."""
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        telegram.send(alert)
    if os.environ.get("SMTP_USER"):
        email.send(alert)


def main():
    init_db()

    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    interval_hours = config.get("monitor", {}).get("interval_hours", 6)

    print(f"[main] starting monitor — interval: {interval_hours}h")

    # Run immediately on start
    run_once(alert_fn=alert_fn)

    scheduler = BlockingScheduler()
    scheduler.add_job(run_once, "interval", hours=interval_hours, kwargs={"alert_fn": alert_fn})
    scheduler.start()


if __name__ == "__main__":
    main()
