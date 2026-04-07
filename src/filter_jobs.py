"""
filter_jobs.py — Clean and filter raw LinkedIn job listings

Removes jobs that don't match the target profile:
  1. Student jobs (praktikant, student assistant, etc.) — but keeps internships
  2. Irrelevant roles (sales, marketing, legal, HR, facilities, etc.)
  3. Senior leadership roles (Head of, Director, VP, Principal, etc.)
  4. Duplicate listings (same LinkedIn job ID appearing twice)

Note: Danish-speaking jobs are kept — the LLM scorer will penalize them
via the language_requirement score, but they're still worth reviewing.

Usage:
    from src.filter_jobs import filter_jobs
    filtered = filter_jobs(raw_jobs)   # returns cleaned list
"""

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Where to save filtered results
OUTPUT_FILE = Path("data/jobs_filtered.json")

# --- Filter keywords (all matched case-insensitively) ---

# Student/intern job keywords — these roles are not suitable
STUDENT_KEYWORDS = [
    "student",
    "praktikant",
    "praktik",
    "studentermedhjælper",
    "studiejob",
    "werkstudent",
    "working student",
    "forskningspraktikant",
]

# Senior leadership titles — too senior for entry/mid-level target
SENIOR_LEADERSHIP_KEYWORDS = [
    "head of",
    "director",
    "vice president",
    "vp ",                # trailing space to avoid matching "vps"
    "chief ",
    "principal",
    "global head",
    "partner",
    "c-suite",
    "cto",
    "cfo",
    "ceo",
    "coo",
    "founder",
    "co-founder",
]

# Irrelevant role types — completely outside target profile
IRRELEVANT_ROLE_KEYWORDS = [
    "sales advisor",
    "sales representative",
    "account executive",
    "account manager",
    "crm manager",
    "marketing manager",
    "marketing specialist",
    "marketing execution",
    "ehs manager",
    "facilities manager",
    "financial crime",
    "regulatory expert",
    "business manager",
    "commercial asset manager",
    "growth hacker",
    "sro-specialist",
    "client & consulting executive",
]



def _text_lower(job: dict) -> str:
    """Get lowercase searchable text from a job's title."""
    return job.get("title", "").lower()


def _desc_lower(job: dict) -> str:
    """Get lowercase plain text from a job's HTML description."""
    html = job.get("descriptionHtml", "") or ""
    # Strip HTML tags to get plain text for keyword matching
    plain = re.sub(r"<[^>]+>", " ", html).lower()
    return plain


def is_student_job(job: dict) -> bool:
    """Check if this is a student/intern position."""
    title = _text_lower(job)
    desc = _desc_lower(job)
    for keyword in STUDENT_KEYWORDS:
        # Check title — strongest signal
        if keyword in title:
            return True
    # Also check if description starts with student-job framing
    # (some jobs have generic titles but are actually student positions)
    desc_start = desc[:500]
    student_desc_phrases = ["student position", "student job", "studiejob",
                            "praktikstilling", "we are looking for a student"]
    for phrase in student_desc_phrases:
        if phrase in desc_start:
            return True
    return False


def is_senior_leadership(job: dict) -> bool:
    """Check if this is a senior leadership / executive role."""
    title = _text_lower(job)
    for keyword in SENIOR_LEADERSHIP_KEYWORDS:
        if keyword in title:
            return True
    return False


def is_irrelevant_role(job: dict) -> bool:
    """Check if this role is completely outside the target profile."""
    title = _text_lower(job)
    for keyword in IRRELEVANT_ROLE_KEYWORDS:
        if keyword in title:
            return True
    return False



def filter_jobs(raw_jobs: list[dict]) -> list[dict]:
    """
    Apply all filters to raw job listings and return clean results.

    Args:
        raw_jobs: List of job dicts from Apify

    Returns:
        Filtered list with unsuitable jobs removed
    """
    # Track removal reasons for logging
    removed = {
        "duplicate": 0,
        "student": 0,
        "senior_leadership": 0,
        "irrelevant_role": 0,
    }

    # Step 1: Remove duplicates by LinkedIn job ID
    seen_ids = set()
    unique_jobs = []
    for job in raw_jobs:
        job_id = job.get("id", "")
        if job_id in seen_ids:
            removed["duplicate"] += 1
            continue
        seen_ids.add(job_id)
        unique_jobs.append(job)

    # Step 2: Apply content filters
    filtered = []
    for job in unique_jobs:
        title = job.get("title", "Unknown")

        if is_student_job(job):
            removed["student"] += 1
            logger.debug("Filtered (student): %s", title)
            continue

        if is_senior_leadership(job):
            removed["senior_leadership"] += 1
            logger.debug("Filtered (senior): %s", title)
            continue

        if is_irrelevant_role(job):
            removed["irrelevant_role"] += 1
            logger.debug("Filtered (irrelevant): %s", title)
            continue

        filtered.append(job)

    # Log summary
    total_removed = sum(removed.values())
    logger.info(
        "Filtered %d → %d jobs (removed %d: %d duplicates, %d student, "
        "%d senior, %d irrelevant)",
        len(raw_jobs), len(filtered), total_removed,
        removed["duplicate"], removed["student"],
        removed["senior_leadership"], removed["irrelevant_role"],
    )

    # Save filtered results to disk
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)
    logger.info("Saved filtered jobs to %s", OUTPUT_FILE)

    return filtered


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # Load raw jobs from the previous step
    raw_path = Path("data/jobs_raw.json")
    if not raw_path.exists():
        print("No raw jobs found. Run fetch_jobs.py first.")
        raise SystemExit(1)

    with open(raw_path) as f:
        raw_jobs = json.load(f)

    filtered = filter_jobs(raw_jobs)

    print(f"\n{'='*60}")
    print(f"Kept {len(filtered)} jobs out of {len(raw_jobs)} raw listings:")
    print(f"{'='*60}")
    for i, job in enumerate(filtered, 1):
        print(f"  {i:2d}. {job['title'][:55]:55s} @ {job.get('companyName','?')}")
