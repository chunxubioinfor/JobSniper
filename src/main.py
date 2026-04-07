"""
main.py — JobSniper Pipeline Orchestrator

Runs the full pipeline in order:
  1. fetch_jobs      → scrape LinkedIn via Apify
  2. filter_jobs     → remove student jobs, irrelevant roles, duplicates
  3. score_jobs      → score each job against CV using LLM proxy
  4. rank_jobs       → sort by overall score, select top N
  5. send_email      → email HTML digest of top matches
  6. save_to_supabase → push all scored jobs to job-tracker database

This is the single entry point for the daily cron job:
    python src/main.py

Each step saves its output to data/ so you can also run steps individually
for debugging:
    python src/fetch_jobs.py
    python src/filter_jobs.py
    etc.
"""

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Set up logging FIRST — before importing other modules
# This configures both console output and a log file
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        # Print to console so you can watch it run
        logging.StreamHandler(sys.stdout),
        # Also save to a log file (one per day, overwritten daily)
        logging.FileHandler(
            LOG_DIR / f"pipeline_{datetime.now().strftime('%Y-%m-%d')}.log",
            mode="w",
        ),
    ],
)

logger = logging.getLogger("jobsniper")

# Now import the pipeline steps
from src.fetch_jobs import fetch_jobs
from src.filter_jobs import filter_jobs
from src.score_jobs import score_jobs
from src.rank_jobs import rank_jobs
from src.send_email import send_email
from src.save_to_supabase import save_to_supabase


def run_pipeline():
    """Run the full JobSniper pipeline end-to-end."""
    start_time = time.time()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info("=" * 60)
    logger.info("JobSniper pipeline starting — %s", today)
    logger.info("=" * 60)

    # Step 1: Fetch raw jobs from LinkedIn
    logger.info("Step 1/6: Fetching jobs from LinkedIn...")
    raw_jobs = fetch_jobs()
    logger.info("→ Fetched %d raw jobs", len(raw_jobs))

    if not raw_jobs:
        logger.warning("No jobs fetched. Exiting pipeline.")
        return

    # Step 2: Filter out noise
    logger.info("Step 2/6: Filtering jobs...")
    filtered = filter_jobs(raw_jobs)
    logger.info("→ %d jobs after filtering", len(filtered))

    if not filtered:
        logger.warning("All jobs filtered out. Exiting pipeline.")
        return

    # Step 3: Score against CV
    logger.info("Step 3/6: Scoring jobs against CV...")
    scored = score_jobs(filtered)
    logger.info("→ %d jobs scored", len(scored))

    if not scored:
        logger.warning("No jobs scored successfully. Exiting pipeline.")
        return

    # Step 4: Rank and select top N
    logger.info("Step 4/6: Ranking jobs...")
    ranked = rank_jobs(scored)
    logger.info("→ Top %d jobs selected", len(ranked))

    # Step 5: Send email digest
    logger.info("Step 5/6: Sending email digest...")
    try:
        send_email(ranked, total_scanned=len(raw_jobs), total_scored=len(scored))
        logger.info("→ Email sent successfully")
    except Exception as e:
        # Email failure shouldn't kill the pipeline — jobs are still saved
        logger.error("→ Email failed: %s", e)

    # Step 6: Save to Supabase
    logger.info("Step 6/6: Saving to Supabase...")
    try:
        inserted, skipped = save_to_supabase(scored)
        logger.info("→ %d inserted, %d skipped (duplicates)", inserted, skipped)
    except Exception as e:
        logger.error("→ Supabase save failed: %s", e)

    # Summary
    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info(
        "Pipeline complete in %.0fs — %d fetched → %d filtered → "
        "%d scored → top %d emailed",
        elapsed, len(raw_jobs), len(filtered), len(scored), len(ranked),
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    run_pipeline()
