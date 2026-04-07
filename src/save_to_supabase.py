"""
save_to_supabase.py — Push scored jobs into the job-tracker Supabase database

Inserts pipeline-scored jobs into the existing 'jobs' table so they appear
on jobs.chunxuhan.com alongside manually-added jobs.

Deduplication: checks by LinkedIn URL (job.link) to avoid inserting the same
job twice across pipeline runs or if you already added it manually.

Usage:
    from src.save_to_supabase import save_to_supabase
    saved, skipped = save_to_supabase(scored_jobs)
"""

import json
import logging
import os
import re
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

logger = logging.getLogger(__name__)


def _extract_linkedin_job_id(url: str) -> str:
    """
    Extract the numeric LinkedIn job ID from a URL.

    LinkedIn job URLs look like:
        https://dk.linkedin.com/jobs/view/data-engineer-at-genmab-4361031466?refId=...
    The job ID is the number at the end of the path: 4361031466
    """
    match = re.search(r"/jobs/view/[^/]*?(\d{8,})", url or "")
    return match.group(1) if match else ""


def _map_sector(title: str, company: str, description: str) -> str:
    """
    Guess the sector from job content to match the job-tracker's sector enum.

    The job-tracker uses: pharma, biotech, tech, finance, public, other
    """
    text = f"{title} {company} {description}".lower()

    # Check keywords for each sector
    if any(w in text for w in ["pharma", "novo nordisk", "lundbeck", "leo pharma",
                                "ferring", "alk", "zealand", "ascendis"]):
        return "pharma"
    if any(w in text for w in ["biotech", "genmab", "novonesis", "bioinformatics",
                                "genomics", "life science"]):
        return "biotech"
    if any(w in text for w in ["finance", "bank", "trading", "quant", "fintech"]):
        return "finance"
    if any(w in text for w in ["public", "government", "university", "hospital",
                                "region", "kommune"]):
        return "public"
    # Default to tech for data/ML/engineering roles
    if any(w in text for w in ["data", "engineer", "ml", "machine learning",
                                "software", "developer", "ai"]):
        return "tech"
    return "other"


def save_to_supabase(scored_jobs: list[dict]) -> tuple[int, int]:
    """
    Insert scored jobs into the Supabase jobs table.

    Args:
        scored_jobs: List of scored job dicts from score_jobs.py

    Returns:
        Tuple of (inserted_count, skipped_count)
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    user_id = os.environ.get("USER_ID")

    if not all([supabase_url, supabase_key, user_id]):
        raise ValueError(
            "Supabase credentials not set. Check SUPABASE_URL, "
            "SUPABASE_SERVICE_ROLE_KEY, and USER_ID in .env"
        )

    sb = create_client(supabase_url, supabase_key)

    # Step 1: Fetch existing jobs for deduplication
    # We grab url + title + company once, then build fast lookup structures
    existing = sb.from_("jobs").select("url, title, company").execute()

    existing_linkedin_ids: set[str] = set()
    existing_title_company: set[tuple[str, str]] = set()
    for row in existing.data:
        url = row.get("url") or ""
        lid = _extract_linkedin_job_id(url)
        if lid:
            existing_linkedin_ids.add(lid)
        title = (row.get("title") or "").strip().lower()
        company = (row.get("company") or "").strip().lower()
        if title and company:
            existing_title_company.add((title, company))

    logger.info(
        "Found %d existing jobs (%d LinkedIn IDs, %d title+company pairs)",
        len(existing.data), len(existing_linkedin_ids), len(existing_title_company),
    )

    today = date.today().isoformat()
    inserted = 0
    skipped = 0

    for job in scored_jobs:
        link = job.get("link", "")

        # Deduplicate: LinkedIn job ID first (handles query-param variations)
        job_id = _extract_linkedin_job_id(link)
        if job_id and job_id in existing_linkedin_ids:
            logger.debug("Skipped (duplicate LinkedIn ID): %s", job.get("title", "?"))
            skipped += 1
            continue

        # Fallback: title + company match (catches non-LinkedIn or ID-less URLs)
        title_lower = (job.get("title") or "").strip().lower()
        company_lower = (job.get("company") or "").strip().lower()
        if title_lower and company_lower and (title_lower, company_lower) in existing_title_company:
            logger.debug("Skipped (duplicate title+company): %s", job.get("title", "?"))
            skipped += 1
            continue

        # Map the pipeline score (0-100) to the job-tracker's 1-10 scale
        overall_score = job.get("scores", {}).get("overall", 0)
        match_score_1_10 = max(1, round(overall_score / 10))

        # Build the summary for match_reasons and gaps (pipe-separated for
        # compatibility with the existing dashboard display)
        summary = job.get("summary", {})
        match_reasons = summary.get("why_you_match", "")
        gaps_text = summary.get("gaps", "")

        desc_plain = job.get("description_plain", "")
        sector = _map_sector(
            job.get("title", ""),
            job.get("company", ""),
            desc_plain,
        )

        # Build the row to insert
        row = {
            "title": job.get("title", "Unknown"),
            "company": job.get("company", ""),
            "sector": sector,
            "location": job.get("location", ""),
            "url": link,
            "platform": "linkedin",
            "source_type": "job_ad",
            "description": desc_plain[:5000],  # truncate to avoid huge rows
            "match_score": match_score_1_10,
            "match_reasons": match_reasons,
            "gaps": gaps_text,
            "added_by": user_id,
            # Pipeline-specific columns
            "source": "pipeline",
            "pipeline_date": today,
            "pipeline_scores": job.get("scores", {}),
            "apply_recommendation": job.get("apply_recommendation", ""),
            "matched_cv": job.get("matched_cv", ""),
            "summary": summary,
        }

        try:
            sb.from_("jobs").insert(row).execute()
            inserted += 1
            # Track so we don't insert twice in the same run
            if job_id:
                existing_linkedin_ids.add(job_id)
            if title_lower and company_lower:
                existing_title_company.add((title_lower, company_lower))
            logger.debug("Inserted: %s @ %s", row["title"], row["company"])
        except Exception as e:
            logger.error(
                "Failed to insert '%s @ %s': %s",
                row["title"], row["company"], e,
            )

    logger.info(
        "Supabase save complete: %d inserted, %d skipped (duplicates)",
        inserted, skipped,
    )

    return inserted, skipped


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    scored_path = Path("data/jobs_scored.json")
    if not scored_path.exists():
        print("No scored jobs found. Run score_jobs.py first.")
        raise SystemExit(1)

    with open(scored_path) as f:
        scored_jobs = json.load(f)

    inserted, skipped = save_to_supabase(scored_jobs)
    print(f"\n✅ Done! {inserted} inserted, {skipped} skipped (duplicates)")
