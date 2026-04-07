"""
send_email.py — Send a daily HTML digest of top-ranked job matches

Connects to Gmail's SMTP server using an App Password and sends a styled
HTML email with score breakdowns, reasoning, and direct apply links.

Usage:
    from src.send_email import send_email
    send_email(ranked_jobs, total_scanned=27, total_scored=11)
"""

import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _recommendation_badge(rec: str) -> str:
    """Return an emoji badge for the apply recommendation."""
    badges = {
        "strong yes": "✅ Strong Yes",
        "yes": "👍 Yes",
        "maybe": "🟡 Maybe",
        "no": "❌ No",
    }
    return badges.get(rec, rec)


def _score_bar(score: int, max_score: int) -> str:
    """Generate a simple text-based progress bar for a score."""
    filled = round(score / max_score * 10)
    return "█" * filled + "░" * (10 - filled)


def _build_html(ranked_jobs: list[dict], total_scanned: int, total_scored: int) -> str:
    """
    Build the full HTML email body.

    This is a big function, but it's just string formatting — no logic.
    The HTML uses inline styles because most email clients ignore <style> tags.
    """
    today = datetime.now(timezone.utc).strftime("%d %b %Y")

    # --- Header ---
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 700px; margin: 0 auto; color: #1a1a1a;">

    <div style="background: linear-gradient(135deg, #004f90 0%, #0073c6 100%); padding: 24px 28px; border-radius: 12px 12px 0 0;">
        <h1 style="color: #ffffff; margin: 0; font-size: 22px;">🧬 Your Daily Job Matches</h1>
        <p style="color: #b8d9f2; margin: 6px 0 0; font-size: 14px;">
            {today} &nbsp;·&nbsp; {total_scanned} scanned &nbsp;·&nbsp;
            {total_scored} scored &nbsp;·&nbsp; Top {len(ranked_jobs)} shown
        </p>
    </div>

    <div style="background: #f8f9fa; padding: 8px 28px; border-bottom: 1px solid #e0e0e0;">
        <p style="margin: 8px 0; font-size: 13px; color: #666;">
            <a href="https://jobs.chunxuhan.com" style="color: #004f90; text-decoration: none;">
                📊 Open Dashboard →
            </a>
        </p>
    </div>
    """

    # Score dimension labels and max values
    dimensions = [
        ("background_match", "Background Match", 10),
        ("skills_overlap", "Skills Overlap", 30),
        ("experience_relevance", "Experience Relevance", 30),
        ("seniority", "Seniority Fit", 10),
        ("language_requirement", "Language", 10),
        ("company_score", "Company Bonus", 10),
    ]

    # --- Job cards ---
    for job in ranked_jobs:
        rank = job.get("rank", "?")
        overall = job["scores"]["overall"]
        rec = job.get("apply_recommendation", "?")
        badge = _recommendation_badge(rec)
        cv = job.get("matched_cv", "?")
        link = job.get("link", "#")
        posted = job.get("posted_at", "")

        # Format posted date
        posted_label = ""
        if posted:
            try:
                posted_dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
                delta = datetime.now(timezone.utc) - posted_dt
                if delta.days == 0:
                    posted_label = "today"
                elif delta.days == 1:
                    posted_label = "yesterday"
                else:
                    posted_label = f"{delta.days}d ago"
            except (ValueError, TypeError):
                posted_label = posted[:10]

        # Card background colour based on recommendation
        bg_colors = {
            "strong yes": "#f0faf0",
            "yes": "#f5f9f0",
            "maybe": "#fefef5",
            "no": "#fafafa",
        }
        bg = bg_colors.get(rec, "#ffffff")

        html += f"""
        <div style="background: {bg}; padding: 20px 28px; border-bottom: 1px solid #e8e8e8;">

            <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px;">
                <span style="font-size: 13px; color: #888; font-weight: 600;">
                    #{rank}
                </span>
                <span style="font-size: 13px; font-weight: 600;">
                    {badge}
                </span>
            </div>

            <h2 style="margin: 0 0 4px; font-size: 17px; color: #1a1a1a;">
                {job['title']}
            </h2>
            <p style="margin: 0 0 12px; font-size: 14px; color: #555;">
                {job['company']} &nbsp;·&nbsp; 📍 {job.get('location', 'N/A')[:40]}
                {f' &nbsp;·&nbsp; 🗓 {posted_label}' if posted_label else ''}
            </p>

            <div style="font-size: 28px; font-weight: 700; color: #004f90; margin-bottom: 12px;">
                {overall}<span style="font-size: 16px; color: #999; font-weight: 400;">/100</span>
            </div>

            <table style="width: 100%; font-size: 13px; border-collapse: collapse;">
        """

        # Score breakdown rows
        for key, label, max_val in dimensions:
            score_val = job["scores"].get(key, 0)
            reason = job.get("reasoning", {}).get(key, "")
            bar = _score_bar(score_val, max_val)

            html += f"""
                <tr>
                    <td style="padding: 3px 0; color: #555; width: 160px;">{label}</td>
                    <td style="padding: 3px 8px; font-family: monospace; font-size: 12px; color: #004f90;">{bar}</td>
                    <td style="padding: 3px 0; text-align: right; font-weight: 600; width: 55px;">{score_val}/{max_val}</td>
                </tr>
            """

        html += """
            </table>
        """

        # Summary block — what they want, why you match, gaps
        summary = job.get("summary", {})
        what = summary.get("what_they_want", "")
        why = summary.get("why_you_match", "")
        gaps = summary.get("gaps", "")

        if any([what, why, gaps]):
            html += """
            <div style="margin: 12px 0 8px; font-size: 13px; line-height: 1.6; background: #ffffff; border-left: 3px solid #004f90; padding: 8px 12px; border-radius: 0 4px 4px 0;">
            """
            if what:
                html += f"""<div style="color: #555;"><strong>What they want:</strong> {what}</div>"""
            if why:
                html += f"""<div style="color: #2e7d32;"><strong>Why you match:</strong> {why}</div>"""
            if gaps:
                html += f"""<div style="color: #c62828;"><strong>Gaps:</strong> {gaps}</div>"""
            html += "</div>"

        html += f"""
            <div style="margin-top: 10px; font-size: 13px;">
                <span style="background: #e8f0fe; padding: 3px 8px; border-radius: 4px; color: #004f90;">
                    CV: {cv}
                </span>
                &nbsp;&nbsp;
                <a href="{link}" style="color: #004f90; text-decoration: none; font-weight: 600;">
                    🔗 Apply →
                </a>
            </div>
        </div>
        """

    # --- Footer ---
    html += f"""
    <div style="padding: 20px 28px; text-align: center; font-size: 12px; color: #999; background: #f8f9fa; border-radius: 0 0 12px 12px;">
        <a href="https://jobs.chunxuhan.com" style="color: #004f90; text-decoration: none;">
            View all jobs on dashboard →
        </a>
        <br><br>
        Powered by JobSniper · GPT-4o + Apify
    </div>
    </div>
    """

    return html


def send_email(
    ranked_jobs: list[dict],
    total_scanned: int = 0,
    total_scored: int = 0,
) -> None:
    """
    Send the daily digest email via Gmail SMTP.

    Args:
        ranked_jobs: Sorted list of top jobs with scores and reasoning
        total_scanned: Number of raw jobs fetched from Apify
        total_scored: Number of jobs that passed filtering and were scored
    """
    sender = os.environ.get("GMAIL_SENDER")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("GMAIL_RECIPIENT")

    if not all([sender, password, recipient]):
        raise ValueError(
            "Gmail credentials not set. Check GMAIL_SENDER, "
            "GMAIL_APP_PASSWORD, and GMAIL_RECIPIENT in .env"
        )

    today = datetime.now(timezone.utc).strftime("%d %b %Y")
    top_score = ranked_jobs[0]["scores"]["overall"] if ranked_jobs else 0

    # Build the email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"🧬 Daily Job Matches — {today} | "
        f"{len(ranked_jobs)} jobs | Top: {top_score}/100"
    )
    msg["From"] = sender
    msg["To"] = recipient

    # Build HTML body
    html_body = _build_html(ranked_jobs, total_scanned, total_scored)
    msg.attach(MIMEText(html_body, "html"))

    # Connect to Gmail's SMTP server and send
    # Port 587 uses STARTTLS — starts unencrypted, then upgrades to TLS
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()                   # upgrade connection to secure
            server.login(sender, password)      # authenticate with App Password
            server.sendmail(sender, recipient, msg.as_string())

        logger.info("Email sent to %s (%d jobs)", recipient, len(ranked_jobs))

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Gmail authentication failed. Check your App Password. "
            "Make sure 2FA is enabled and you're using an App Password, "
            "not your regular Gmail password."
        )
        raise
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        raise


if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    ranked_path = Path("data/jobs_ranked.json")
    if not ranked_path.exists():
        print("No ranked jobs found. Run rank_jobs.py first.")
        raise SystemExit(1)

    with open(ranked_path) as f:
        ranked_jobs = json.load(f)

    # Get totals from previous step files
    raw_path = Path("data/jobs_raw.json")
    scored_path = Path("data/jobs_scored.json")
    total_scanned = len(json.load(open(raw_path))) if raw_path.exists() else 0
    total_scored = len(json.load(open(scored_path))) if scored_path.exists() else 0

    send_email(ranked_jobs, total_scanned, total_scored)
    print(f"✅ Email sent with {len(ranked_jobs)} jobs!")
