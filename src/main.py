"""
main.py — JobSniper Pipeline Orchestrator

Runs all pipeline steps in order:
  1. fetch_jobs    — Scrape LinkedIn via Apify
  2. filter_jobs   — Remove student jobs, Danish-required, duplicates
  3. score_jobs    — Score each job against CV using LLM proxy
  4. rank_jobs     — Sort by overall score, select top N
  5. send_email    — Email HTML digest of top matches
  6. save_to_supabase — Push all scored jobs to job-tracker database

Usage:
  python src/main.py          (run full pipeline)
"""

# Each step will be implemented in Phase 2.
# This file will import and call them in sequence.

if __name__ == "__main__":
    print("JobSniper pipeline — not yet implemented. See PLAN.md for roadmap.")
