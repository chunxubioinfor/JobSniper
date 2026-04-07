"""
health_check.py — Verify daily pipeline ran successfully

Checks today's pipeline log for the "Pipeline complete" marker.
If missing (pipeline failed or never ran), sends an alert email.

Intended to run via cron ~90 min after the pipeline:
    30 8 * * * cd /home/chunxu/JobSniper && /home/chunxu/JobSniper/venv/bin/python -m src.health_check >> /home/chunxu/JobSniper/logs/health.log 2>&1
"""

import logging
import os
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("jobsniper.health")

LOG_DIR = Path("logs")
SUCCESS_MARKER = "Pipeline complete"


def check_pipeline_log() -> tuple[bool, str]:
    """
    Check if today's pipeline log exists and contains the success marker.

    Returns:
        (ok, detail) — True if pipeline succeeded, False otherwise.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"pipeline_{today}.log"

    if not log_file.exists():
        return False, f"Log file not found: {log_file}"

    content = log_file.read_text()

    if SUCCESS_MARKER not in content:
        # Grab last 5 lines for context
        tail = "\n".join(content.strip().splitlines()[-5:])
        return False, f"'{SUCCESS_MARKER}' not found in {log_file}.\nLast lines:\n{tail}"

    return True, f"Pipeline completed successfully ({log_file})"


def send_alert(detail: str) -> None:
    """Send a short alert email via Gmail SMTP."""
    sender = os.environ.get("GMAIL_SENDER")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("GMAIL_RECIPIENT")

    if not all([sender, password, recipient]):
        raise ValueError(
            "Gmail credentials not set. Check GMAIL_SENDER, "
            "GMAIL_APP_PASSWORD, and GMAIL_RECIPIENT in .env"
        )

    today = datetime.now().strftime("%d %b %Y")

    msg = MIMEText(
        f"JobSniper pipeline health check failed on {today}.\n\n{detail}\n\n"
        f"Check the VPS logs for details:\n"
        f"  ssh chunxu@204.168.248.57\n"
        f"  cat /home/chunxu/JobSniper/logs/pipeline_{datetime.now().strftime('%Y-%m-%d')}.log\n"
    )
    msg["Subject"] = f"[JobSniper] Pipeline FAILED — {today}"
    msg["From"] = sender
    msg["To"] = recipient

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        logger.info("Alert email sent to %s", recipient)
    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Gmail authentication failed. Check your App Password."
        )
        raise
    except Exception as e:
        logger.error("Failed to send alert email: %s", e)
        raise


def main() -> None:
    """Run the health check."""
    logger.info("Running pipeline health check...")

    ok, detail = check_pipeline_log()

    if ok:
        logger.info(detail)
    else:
        logger.warning("HEALTH CHECK FAILED: %s", detail)
        send_alert(detail)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
