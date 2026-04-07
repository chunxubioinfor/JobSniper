"""
score_jobs.py — Score each filtered job against CV using an LLM proxy

For each job, sends the job description + CV context to an OpenAI-compatible
LLM API and receives a structured JSON score across 6 dimensions.

The LLM acts as a recruiter: it reads your CV, reads the job posting, and
gives a detailed assessment of how well you fit.

Usage:
    from src.score_jobs import score_jobs
    scored = score_jobs(filtered_jobs)   # returns list of scored job dicts
"""

import json
import logging
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

load_dotenv()

logger = logging.getLogger(__name__)

# --- Configuration ---

# Where to save scored results
OUTPUT_FILE = Path("data/jobs_scored.json")

# CV files to load as context for the LLM
CV_DIR = Path("CVs")
CV_FILES = [
    "master_cv_bio.tex",
    "master_cv_data.tex",
    "relevant_experience_bank.md",
]

# Max characters of job description to send (avoid token limits)
MAX_DESC_LENGTH = 4000

# Delay between API calls to be polite to the proxy
API_DELAY_SECONDS = 0.5

# --- LLM Client Setup ---

# The OpenAI SDK works with any OpenAI-compatible API by changing the base_url.
# This means we can use proxies like GlobalAI instead of paying OpenAI directly.
client = OpenAI(
    api_key=os.environ.get("LLM_API_KEY", ""),
    base_url=os.environ.get("LLM_BASE_URL", "https://globalai.vip/v1"),
)
MODEL = os.environ.get("LLM_MODEL", "gpt-4o")

# --- Scoring Prompt ---

# This is the system prompt — it tells the LLM how to behave.
# "system" messages set the LLM's role and rules.
# "user" messages contain the actual job + CV data to evaluate.
SYSTEM_PROMPT = """You are an expert recruiter and career advisor evaluating job fit for a candidate.

You will receive:
1. The candidate's CV content (two versions: bioinformatics focus and data/analytics focus)
2. The candidate's detailed experience bank
3. A job posting to evaluate

Score the job across 6 dimensions. Return ONLY valid JSON — no markdown fences, no explanation outside the JSON.

{
  "scores": {
    "background_match": <0-10>,
    "skills_overlap": <0-30>,
    "experience_relevance": <0-30>,
    "seniority": <0-10>,
    "language_requirement": <0-10>,
    "company_score": <0-10>
  },
  "summary": {
    "what_they_want": "<1 sentence: what the job is actually asking for>",
    "why_you_match": "<1 sentence: strongest reasons the candidate fits>",
    "gaps": "<1 sentence: key missing skills or experience>"
  },
  "matched_cv": "bio | data | both",
  "apply_recommendation": "strong yes | yes | maybe | no"
}

SCORING GUIDE:

background_match (0-10): Domain fit.
  10 = bioinformatics + pharma/biotech, or data science + life sciences
  7-9 = data/analytics/ML role in relevant industry
  4-6 = general tech/data role, partially relevant domain
  0-3 = completely different domain (finance, sales, legal)

skills_overlap (0-30): How many required/preferred skills the candidate actually has.
  25-30 = nearly all skills match (Python, R, SQL, ML, bioinformatics tools)
  15-24 = core skills match, some gaps in specific tools
  8-14 = some transferable skills but significant gaps
  0-7 = very few matching skills

experience_relevance (0-30): How well the candidate's past work matches job responsibilities.
  25-30 = direct experience doing similar work (pipelines, data analysis, package dev)
  15-24 = related experience with transferable skills
  8-14 = some overlap but different context
  0-7 = minimal relevance

seniority (0-10): Seniority level fit.
  10 = entry-level, junior, or mid-level (perfect for the candidate)
  8 = internship or graduate program
  6 = senior (stretch but possible)
  3 = lead or staff level
  0-2 = director, VP, head of, principal

language_requirement (0-10): Language accessibility.
  10 = English only, or no language requirement mentioned
  7-8 = English primary, Danish "nice to have"
  5 = bilingual (English + Danish)
  2-3 = Danish preferred
  0 = Danish required / fluent Danish mandatory

company_score (0-10): Company/industry bonus.
  9-10 = top-tier biotech/pharma (Novo Nordisk, Genmab, LEO Pharma, etc.)
  7-8 = strong biotech/pharma/AI company
  5-6 = good tech company or consultancy
  3-4 = generic company, unknown industry fit
  0-2 = company not relevant to candidate's goals

matched_cv: Which CV template is the better fit — "bio" (bioinformatics focus),
"data" (analytics/ML focus), or "both" (equally relevant).

apply_recommendation: Based on the overall score (sum of all dimensions, max 100):
  "strong yes" = 70+
  "yes" = 50-69
  "maybe" = 30-49
  "no" = below 30
"""


def load_cv_context() -> str:
    """
    Load all CV files and combine them into a single context string.

    The LLM needs to "read" your CV to evaluate job fit, just like a human
    recruiter would. We send the full text of both CV versions plus the
    experience bank so it has maximum context.
    """
    parts = []
    for filename in CV_FILES:
        filepath = CV_DIR / filename
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8")
            # Strip LaTeX boilerplate — keep only the meaningful content
            # (The LLM can read LaTeX, but cleaner input = better scoring)
            parts.append(f"=== {filename} ===\n{content}")
        else:
            logger.warning("CV file not found: %s", filepath)

    if not parts:
        raise FileNotFoundError(
            f"No CV files found in {CV_DIR}/. "
            "Make sure master_cv_bio.tex, master_cv_data.tex, "
            "and relevant_experience_bank.md are in the CVs/ folder."
        )

    return "\n\n".join(parts)


def strip_html(html: str) -> str:
    """Convert HTML job description to plain text."""
    # Replace common HTML elements with readable formatting
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"<li>", "• ", text)
    text = re.sub(r"</?(ul|ol|p|div|strong|em|b|i|span|h[1-6])[^>]*>", " ", text)
    text = re.sub(r"<[^>]+>", "", text)  # remove any remaining tags
    text = re.sub(r"\s+", " ", text).strip()
    return text


def score_single_job(cv_context: str, job: dict) -> dict:
    """
    Call the LLM to score a single job against the candidate's CV.

    Args:
        cv_context: Combined text of all CV files
        job: Raw job dict from Apify

    Returns:
        Parsed JSON score dict from the LLM
    """
    title = job.get("title", "Unknown")
    company = job.get("companyName", "Unknown")
    location = job.get("location", "Unknown")
    desc_html = job.get("descriptionHtml", "") or ""
    desc_plain = strip_html(desc_html)[:MAX_DESC_LENGTH]

    # Build the user message — this is what the LLM evaluates
    user_message = (
        f"CANDIDATE CV AND EXPERIENCE:\n{cv_context}\n\n"
        f"---\n\n"
        f"JOB POSTING TO EVALUATE:\n"
        f"Title: {title}\n"
        f"Company: {company}\n"
        f"Location: {location}\n"
        f"Description:\n{desc_plain}"
    )

    # Call the LLM API
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0,  # deterministic output for consistent scoring
        response_format={"type": "json_object"},  # force valid JSON
    )

    # Parse the response
    raw_content = response.choices[0].message.content.strip()

    # Some models wrap JSON in markdown code fences — strip them
    if raw_content.startswith("```"):
        raw_content = raw_content.split("```")[1]
        if raw_content.startswith("json"):
            raw_content = raw_content[4:]

    result = json.loads(raw_content)

    # Calculate overall score (sum of all 6 dimensions)
    scores = result.get("scores", {})
    overall = sum(scores.values())
    result["scores"]["overall"] = overall

    return result


def score_jobs(filtered_jobs: list[dict]) -> list[dict]:
    """
    Score all filtered jobs against the candidate's CV.

    Args:
        filtered_jobs: List of job dicts from filter_jobs

    Returns:
        List of job dicts enriched with scoring data
    """
    cv_context = load_cv_context()
    logger.info("Loaded CV context (%d chars)", len(cv_context))
    logger.info("Scoring %d jobs with model '%s'", len(filtered_jobs), MODEL)

    scored_jobs = []
    errors = 0

    for job in tqdm(filtered_jobs, desc="Scoring jobs"):
        title = job.get("title", "Unknown")
        company = job.get("companyName", "Unknown")

        try:
            score_data = score_single_job(cv_context, job)

            # Merge score data into the job dict
            scored_job = {
                # Keep essential fields from the raw job
                "id": job.get("id", ""),
                "title": title,
                "company": company,
                "location": job.get("location", ""),
                "link": job.get("link", ""),
                "posted_at": job.get("postedAt", ""),
                "description_plain": strip_html(
                    job.get("descriptionHtml", "") or ""
                ),
                # Add all scoring data
                **score_data,
            }
            scored_jobs.append(scored_job)
            logger.debug(
                "Scored: %s @ %s → %d/100",
                title, company, score_data["scores"]["overall"],
            )

        except json.JSONDecodeError as e:
            errors += 1
            logger.error("JSON parse error for '%s @ %s': %s", title, company, e)
            continue
        except Exception as e:
            errors += 1
            logger.error("Error scoring '%s @ %s': %s", title, company, e)
            continue

        # Small delay between API calls to avoid rate limiting
        time.sleep(API_DELAY_SECONDS)

    logger.info(
        "Scoring complete: %d scored, %d errors out of %d total",
        len(scored_jobs), errors, len(filtered_jobs),
    )

    # Save scored results to disk
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(scored_jobs, f, indent=2, ensure_ascii=False)
    logger.info("Saved scored jobs to %s", OUTPUT_FILE)

    return scored_jobs


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # Load filtered jobs from the previous step
    filtered_path = Path("data/jobs_filtered.json")
    if not filtered_path.exists():
        print("No filtered jobs found. Run filter_jobs.py first.")
        raise SystemExit(1)

    with open(filtered_path) as f:
        filtered_jobs = json.load(f)

    scored = score_jobs(filtered_jobs)

    print(f"\n{'='*60}")
    print(f"Scored {len(scored)} jobs:")
    print(f"{'='*60}")
    for job in sorted(scored, key=lambda j: j["scores"]["overall"], reverse=True):
        overall = job["scores"]["overall"]
        rec = job.get("apply_recommendation", "?")
        print(f"  {overall:3d}/100  {rec:12s}  {job['title'][:40]:40s} @ {job['company']}")
