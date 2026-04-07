"""
rank_jobs.py — Sort scored jobs by overall score and select the top N

This is a short module, but keeping it separate means you can easily change
the ranking logic later (e.g. add a recency bonus, weight certain categories
more heavily, or set a minimum score threshold).

Usage:
    from src.rank_jobs import rank_jobs
    top_jobs = rank_jobs(scored_jobs)        # default top 10
    top_jobs = rank_jobs(scored_jobs, top_n=5)
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Where to save the final ranked output
OUTPUT_FILE = Path("data/jobs_ranked.json")

# Default: include at least this many jobs in the digest
DEFAULT_TOP_N = 10

# Minimum score to include — jobs below this are excluded even if we have
# fewer than top_n results. Set to 0 to include everything.
MIN_SCORE = 0


def rank_jobs(scored_jobs: list[dict], top_n: int = DEFAULT_TOP_N) -> list[dict]:
    """
    Sort jobs by overall score (descending) and return the top N.

    Args:
        scored_jobs: List of job dicts with 'scores' containing 'overall'
        top_n: Maximum number of jobs to return

    Returns:
        Sorted list of the top N jobs, each with a 'rank' field added
    """
    # Filter out jobs below minimum score
    eligible = [
        j for j in scored_jobs
        if j.get("scores", {}).get("overall", 0) >= MIN_SCORE
    ]

    # Sort by overall score, highest first
    ranked = sorted(
        eligible,
        key=lambda j: j["scores"]["overall"],
        reverse=True,
    )

    # Take the top N
    top = ranked[:top_n]

    # Add a rank number to each job (1 = best)
    for i, job in enumerate(top, start=1):
        job["rank"] = i

    logger.info(
        "Ranked %d jobs → top %d (scores: %s)",
        len(scored_jobs),
        len(top),
        ", ".join(str(j["scores"]["overall"]) for j in top),
    )

    # Save ranked results to disk
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(top, f, indent=2, ensure_ascii=False)
    logger.info("Saved ranked jobs to %s", OUTPUT_FILE)

    return top


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

    top = rank_jobs(scored_jobs)

    print(f"\n{'='*60}")
    print(f"Top {len(top)} jobs:")
    print(f"{'='*60}")
    for job in top:
        overall = job["scores"]["overall"]
        rec = job.get("apply_recommendation", "?")
        cv = job.get("matched_cv", "?")
        print(
            f"  #{job['rank']:2d}  {overall:3d}/100  {rec:12s}  "
            f"CV:{cv:5s}  {job['title'][:35]:35s} @ {job['company']}"
        )
