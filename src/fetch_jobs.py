"""
fetch_jobs.py — Scrape LinkedIn jobs via Apify

Triggers the 'curious_coder/linkedin-jobs-scraper' actor with pre-configured
LinkedIn search URLs, waits for results, and saves raw job listings to JSON.

The search URLs use LinkedIn's f_TPR=r86400 filter (last 24 hours) so we only
get fresh postings each day.

Usage:
    from src.fetch_jobs import fetch_jobs
    jobs = fetch_jobs()          # returns list of job dicts
"""

import json
import logging
import os
from pathlib import Path

from apify_client import ApifyClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging — writes to both console and log file
logger = logging.getLogger(__name__)

# --- Configuration ---

# The Apify actor that scrapes LinkedIn's public job search pages
ACTOR_ID = "curious_coder/linkedin-jobs-scraper"

# LinkedIn search URLs — each targets a different keyword in Copenhagen
# f_TPR=r86400 = posted in last 24 hours (daily freshness)
# geoId=102194656 = Copenhagen metro area
# distance=10 = within 10 miles
SEARCH_URLS = [
    # "Data" jobs in Copenhagen (covers analyst, scientist, engineer)
    "https://www.linkedin.com/jobs/search?keywords=Data&location=Copenhagen&geoId=102194656&distance=10&f_TPR=r86400&position=1&pageNum=0",
    # "Bioinformatics" jobs in Copenhagen
    "https://www.linkedin.com/jobs/search?keywords=Bioinformatics&location=Copenhagen&geoId=102194656&distance=10&f_TPR=r86400&position=1&pageNum=0",
]

# Max jobs to scrape per search URL (stay within Apify free tier)
JOBS_PER_SEARCH = 100

# How long to wait for the actor to finish (seconds)
# LinkedIn scraping with company details takes ~2-3 min per 100 jobs
TIMEOUT_SECS = 300

# Where to save raw results
OUTPUT_FILE = Path("data/jobs_raw.json")


def fetch_jobs() -> list[dict]:
    """
    Trigger the Apify LinkedIn scraper and return raw job listings.

    Returns:
        List of job dicts, each containing fields like:
        - id, title, companyName, location, link, postedAt, descriptionHtml, etc.
    """
    # Get the API token from environment variables
    api_token = os.environ.get("APIFY_API_TOKEN")
    if not api_token:
        raise ValueError("APIFY_API_TOKEN not set in .env file")

    # Create an Apify client — this is our connection to the Apify platform
    client = ApifyClient(api_token)

    # Configure the actor input — tells it what to scrape
    run_input = {
        "urls": SEARCH_URLS,
        "scrapeCompany": False,     # Skip company details to save time and credits
        "count": JOBS_PER_SEARCH,   # Max jobs per search URL
    }

    logger.info(
        "Starting Apify actor '%s' with %d search URLs, max %d jobs each",
        ACTOR_ID, len(SEARCH_URLS), JOBS_PER_SEARCH,
    )

    # .call() starts the actor and waits for it to finish (polling internally)
    # This blocks until the run completes or times out
    try:
        run = client.actor(ACTOR_ID).call(
            run_input=run_input,
            timeout_secs=TIMEOUT_SECS,
        )
    except Exception as e:
        logger.error("Apify actor run failed: %s", e)
        raise

    # Check if the run succeeded
    status = run.get("status")
    if status != "SUCCEEDED":
        logger.warning("Actor run finished with status: %s", status)

    # Download all results from the actor's dataset
    dataset_id = run["defaultDatasetId"]
    items = client.dataset(dataset_id).list_items().items
    logger.info("Fetched %d raw job listings from Apify", len(items))

    # Save raw results to disk (overwritten daily)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    logger.info("Saved raw jobs to %s", OUTPUT_FILE)

    return items


# This block runs only when you execute this file directly:
#   python src/fetch_jobs.py
# It won't run when another file imports fetch_jobs as a function.
if __name__ == "__main__":
    # Set up basic logging so we can see what's happening
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    jobs = fetch_jobs()
    print(f"\nDone! Fetched {len(jobs)} jobs. Saved to {OUTPUT_FILE}")

    # Show a quick preview of the first 3 jobs
    for i, job in enumerate(jobs[:3]):
        print(f"\n--- Job {i+1} ---")
        print(f"  Title:   {job.get('title', 'N/A')}")
        print(f"  Company: {job.get('companyName', 'N/A')}")
        print(f"  Location:{job.get('location', 'N/A')}")
        print(f"  Posted:  {job.get('postedAt', 'N/A')}")
        print(f"  Link:    {job.get('link', 'N/A')}")
