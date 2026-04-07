# 🧬 LinkedIn Daily Job Matcher — Project Plan

> **For Claude Code:** Read this file fully before writing any code. This is the single source of truth for the project. Always re-read the CV and experience files referenced in Section 3 before any scoring or matching decisions.

---

## 0. How Claude Code Should Work With Me

This project is built to **work and learn at the same time**. Claude Code must follow these teaching principles throughout every phase:

- **Explain before you write.** Before generating any file or function, briefly explain in plain English what it does, why it's needed, and what concept it teaches (e.g. API calls, environment variables, cron jobs).
- **Comment generously.** Every non-trivial line of code should have a comment. Assume I have beginner Python knowledge — I can read code but don't write it independently yet.
- **Introduce concepts when they appear.** When using a new tool or pattern (e.g. `try/except`, `.env` files, virtual environments, Git branches), pause and explain the concept in 2–3 sentences before using it.
- **Suggest Git commits at natural checkpoints.** After each working feature, remind me to commit with a clear, conventional commit message (e.g. `feat: add Apify job fetcher`). Explain what `git add`, `git commit`, and `git push` do each time until it becomes habit.
- **Ask before assuming.** If something is ambiguous, ask rather than guess.
- **Phase by phase.** Do not jump ahead. Complete and test each phase fully before moving to the next.

---

## 1. Project Goal

Build an automated Python pipeline that:
1. Runs **once daily at 07:00** on a cloud server (Hetzner VPS)
2. Scrapes LinkedIn for fresh English-language job postings in Copenhagen matching a target profile
3. Scores each job using a structured rubric calibrated against the owner's CVs and experience
4. Sends a **ranked digest email** of the top 10+ best-fit jobs every morning
5. Saves **all scored jobs to a personal web dashboard** on the owner's domain — so they can browse, filter, and look back over time

---

## 2. Owner Profile

- **Location:** Copenhagen, Denmark
- **Language:** English-only jobs (filter out roles requiring Danish)
- **Target roles:** Data Analyst / BI, Data Scientist / ML, Data Engineer, Bioinformatician
- **Seniority preference:** Entry-level to mid-level. Penalise Lead, Principal, Head-of, and Director roles.
- **Preferred industries:** Biotech, Pharma, Life Sciences, AI/ML companies
- **Exclude:** Student jobs (keywords: praktikant, studentermedhjælper, student assistant, internship, praktik)

---

## 3. Reference Files — ALWAYS READ THESE FIRST

> Claude Code must read and internalise these files at the start of every session and before any job scoring. Load all three as context when calling the Claude API for scoring.

| File | Purpose |
|------|---------|
| `cvs/master_cv_bio.tex` | Master CV — bioinformatics / life sciences focus |
| `cvs/master_cv_data.tex` | Master CV — data / analytics / ML focus |
| `cvs/relevant_experience_bank.md` | Detailed experience bank: projects, tools, responsibilities |

---

## 4. System Architecture

```
[Apify]  LinkedIn Jobs Scraper Actor (triggered via API)
    ↓
[fetch_jobs.py]      Pull raw listings → jobs_raw.json
    ↓
[filter_jobs.py]     Remove student jobs, Danish-required, duplicates → jobs_filtered.json
    ↓
[score_jobs.py]      Claude API scores each job against CV context → jobs_scored.json
    ↓
[rank_jobs.py]       Sort by overall score, select top 10+
    ↓
[send_email.py]      HTML digest → Gmail SMTP → owner's inbox
    ↓
[save_to_db.py]      Append all scored jobs to SQLite (for dashboard)
    ↓
[Web Dashboard]      Flask app on owner's domain — browse, filter, search all past jobs
    ↓
[Cron on Hetzner]    Triggers main.py at 07:00 every day
```

---

## 5. Tech Stack

| Component | Tool | Notes |
|-----------|------|-------|
| Job source | Apify — LinkedIn Jobs Scraper | Apify Python SDK |
| AI scoring | OpenAI-compatible LLM proxy (GlobalAI / others) | CV content passed as context |
| Email | Gmail SMTP via `smtplib` | Gmail App Password |
| Database | Supabase (PostgreSQL) | Shared with job-tracker web app |
| Web dashboard | Existing Next.js app (jobs.chunxuhan.com) | No separate dashboard needed |
| Scheduling | `cron` on Linux VPS | `0 7 * * *` |
| Server | Hetzner VPS — CAX11 (Helsinki or Nuremberg) | Ubuntu 24.04 |
| Language | Python 3.11+ | Beginner-friendly, well-commented |
| Config | `.env` + `python-dotenv` | Never hardcode secrets |
| Logging | Python `logging` module | Logs to file + console |
| Version control | Git + GitHub (private repo) | Commit at every working checkpoint |

---

## 6. Scoring Rubric

Claude API must return a **valid JSON object** for each job — no markdown fences, no preamble, raw JSON only. All scoring must be grounded in the content of the three CV/experience files.

```json
{
  "job_title": "...",
  "company": "...",
  "location": "...",
  "job_url": "...",
  "posted_date": "...",
  "scores": {
    "background_match": 0,
    "skills_overlap": 0,
    "experience_relevance": 0,
    "seniority": 0,
    "language_requirement": 0,
    "company_score": 0,
    "overall": 0
  },
  "reasoning": {
    "background_match": "...",
    "skills_overlap": "...",
    "experience_relevance": "...",
    "seniority": "...",
    "language_requirement": "...",
    "company_score": "..."
  },
  "matched_cv": "bio | data | both",
  "apply_recommendation": "strong yes | yes | maybe | no"
}
```

### Score Definitions

| Category | Range | Logic |
|----------|-------|-------|
| `background_match` | 0–10 | Domain fit: bioinformatics, pharma, biotech **and** data/analytics roles score high |
| `skills_overlap` | 0–30 | Overlap between job's required/preferred skills and owner's actual technical stack |
| `experience_relevance` | 0–30 | How well job responsibilities align with owner's past projects and roles |
| `seniority` | 0–10 | Entry/junior/mid = 10. Senior = 6. Lead/Principal/Head/Director = 0–2 |
| `language_requirement` | 0–10 | English-friendly = 10. Danish preferred = 5. Danish required = 0 |
| `company_score` | 0–10 | Biotech/pharma/AI = 8–10. Generic consultancy = 3–5. Unknown = 5 |
| `overall` | 0–100 | Sum of all above |

### Future improvements (Phase 5)
- `recency_bonus` (0–5 extra): Jobs posted within the last 24 hours get a boost
- `growth_potential`: Detect mentions of learning budget, mentorship, or training

---

## 7. Apify Configuration

- **Actor:** LinkedIn Jobs Scraper (highest-rated on Apify store)
- **Daily search queries:**
  - `"data analyst" Copenhagen`
  - `"data scientist" Copenhagen`
  - `"data engineer" Copenhagen`
  - `"bioinformatics" Denmark`
  - `"machine learning" Copenhagen`
- **Max results per query:** 25–30 (stay within Apify free tier, ~150 total/day)
- **Fetch method:** Trigger actor via API → poll until complete → download dataset as JSON

---

## 8. Email Digest Format

**Subject:** `🧬 Your Daily Job Matches — {date} | {N} jobs scored`

**HTML body structure:**

```
Header: date · jobs scanned · jobs scored · link to web dashboard

For each top job (sorted by overall score, minimum top 10):
──────────────────────────────────────────────────────────
Rank #N  ·  Overall: XX/100  ·  ✅ Strong Yes / 🟡 Maybe
[Job Title] @ [Company]
📍 Location  ·  🗓 Posted: X days ago

Score Breakdown:
  Background Match      X / 10
  Skills Overlap       XX / 30
  Experience Relevance XX / 30
  Seniority Fit         X / 10
  Language              X / 10
  Company Bonus         X / 10

Why it fits: [2–3 sentence Claude explanation]
Best CV to use: [bio / data / both]
🔗 Apply: [LinkedIn URL]
──────────────────────────────────────────────────────────

Footer: "View all jobs → [dashboard URL] · Powered by Claude + Apify"
```

---

## 9. Web Dashboard

A lightweight Flask web app hosted on the owner's existing domain (e.g. `jobs.yourdomain.com`).

### Features
- **Home page:** Table of all scored jobs, newest first, with score badge and recommendation label
- **Filter bar:** Filter by role type, score range, recommendation, date range
- **Job detail page:** Full score breakdown + Claude's reasoning per category
- **Stats strip:** Total jobs tracked · Average score this week · Top company seen

### Data storage
- SQLite database at `data/jobs.db`
- One row per scored job with all score fields, metadata, and date
- Deduplication: check job URL before inserting — never store the same job twice

### Deployment
- Runs as a `systemd` service on the Hetzner VPS
- Served via `nginx` reverse proxy on the owner's existing domain
- No login required (personal use, non-sensitive data)

---

## 10. Git & Version Control

> Claude Code should explain Git concepts as they appear for the first time.

### Setup
- **Remote:** GitHub (private repository)
- **Main branch:** `main` — always stable and deployable
- **Feature branches:** one per phase (e.g. `feat/fetch-jobs`, `feat/scoring`, `feat/dashboard`)

### Commit message convention (Conventional Commits)
```
feat: add Apify job fetcher
fix: handle missing job description field
docs: update README with dashboard setup
chore: add .gitignore and requirements.txt
refactor: extract scoring logic into helper function
```

### `.gitignore` must include
```
.env
data/
logs/
__pycache__/
*.pyc
venv/
cvs/          ← CV files are private, never commit to GitHub
```

---

## 11. Project File Structure

```
linkedin-job-matcher/
├── PLAN.md                        ← this file
├── README.md                      ← public-facing project description
├── .env                           ← secrets (never commit)
├── .env.example                   ← empty template (safe to commit)
├── .gitignore
├── requirements.txt
│
├── cvs/                           ← private, in .gitignore
│   ├── master_cv_bio.tex
│   ├── master_cv_data.tex
│   └── relevant_experience_bank.md
│
├── src/
│   ├── main.py                    ← orchestrator: runs all steps in order
│   ├── fetch_jobs.py              ← trigger Apify, download results
│   ├── filter_jobs.py             ← clean and filter listings
│   ├── score_jobs.py              ← Claude API scoring loop
│   ├── rank_jobs.py               ← sort and select top N
│   ├── send_email.py              ← Gmail SMTP HTML digest
│   └── save_to_db.py              ← write scored jobs to SQLite
│
├── dashboard/
│   ├── app.py                     ← Flask web app
│   ├── templates/
│   │   ├── index.html             ← jobs table with filters
│   │   └── job_detail.html        ← full score breakdown per job
│   └── static/
│       └── style.css
│
├── data/
│   ├── jobs.db                    ← SQLite database (in .gitignore)
│   ├── jobs_raw.json              ← Apify output (overwritten daily)
│   ├── jobs_filtered.json
│   └── jobs_scored.json
│
└── logs/
    └── pipeline.log
```

---

## 12. Environment Variables (`.env`)

```
APIFY_API_TOKEN=your_apify_token_here
ANTHROPIC_API_KEY=your_anthropic_key_here
GMAIL_SENDER=your@gmail.com
GMAIL_APP_PASSWORD=your_gmail_app_password_here
GMAIL_RECIPIENT=your@gmail.com
DASHBOARD_URL=https://jobs.yourdomain.com
```

---

## 13. Build Phases

### Phase 1 — Project Skeleton & Git Setup
- [ ] Explain and set up Python virtual environment (`venv`)
- [ ] Explain and initialise Git repo, connect to GitHub remote
- [ ] Create folder structure, `.gitignore`, `.env.example`, `requirements.txt`
- [ ] First commit: `chore: initialise project structure`

### Phase 2 — Core Pipeline (local, test before deploy)
- [ ] `fetch_jobs.py` — Apify API call, save raw JSON (teach: HTTP APIs, JSON)
- [ ] `filter_jobs.py` — filter and clean listings (teach: list filtering, string matching)
- [ ] `score_jobs.py` — Claude API scoring loop (teach: prompt engineering, API loops)
- [ ] `rank_jobs.py` — sort and slice results (teach: Python sorting, slicing)
- [ ] `send_email.py` — Gmail SMTP HTML email (teach: SMTP, HTML emails, App Passwords)
- [ ] `main.py` — orchestrate all steps (teach: script structure, `if __name__ == "__main__"`)
- [ ] Test full pipeline end-to-end locally
- [ ] Commit: `feat: complete local pipeline`

### Phase 3 — Web Dashboard
- [ ] Explain Flask and how web frameworks work
- [ ] `save_to_db.py` — SQLite storage (teach: databases, SQL basics, `INSERT OR IGNORE`)
- [ ] `dashboard/app.py` — Flask routes (teach: routing, templates, GET requests)
- [ ] Build `index.html` and `job_detail.html` with Jinja2 templating
- [ ] Test dashboard locally at `localhost:5000`
- [ ] Commit: `feat: add job history dashboard`

### Phase 4 — Deploy to Hetzner VPS
- [ ] Explain what a VPS is and why it matters
- [ ] Provision Hetzner CAX11 (Ubuntu 24.04), explain SSH key setup
- [ ] Basic hardening: `ufw` firewall, `fail2ban` (teach: Linux security basics)
- [ ] Install Python, git, clone repo, configure `.env` on server
- [ ] Deploy Flask via `systemd` + `nginx` reverse proxy (teach: services, reverse proxies)
- [ ] Point domain to dashboard (teach: DNS A records)
- [ ] Add cron job `0 7 * * *` (teach: cron syntax)
- [ ] Run pipeline manually → confirm email + dashboard update
- [ ] Commit: `feat: deployed to VPS with cron scheduling`

### Phase 5 — Improvements (post-launch)
- [ ] Deduplication: skip jobs already stored in database
- [ ] Recency bonus scoring
- [ ] Dashboard: search bar + date range filter
- [ ] Optional: weekly "best job of the week" email summary

---

## 14. Notes for Claude Code

- **Always read CV files before scoring.** Load all three `cvs/` files and pass full text as context to the Claude API prompt.
- **Teach as you build.** Explain every new concept before introducing it. This project is a learning journey.
- **Suggest Git commits at every milestone.** Explain `git add`, `git commit -m`, and `git push` every time until it's habitual.
- **Beginner-friendly Python only.** Clear names, comments on every non-obvious line, no magic one-liners.
- **Never hardcode secrets.** All sensitive values come from `.env` via `python-dotenv`.
- **Error handling is required.** Wrap all API calls in `try/except`. Log failures and continue — never crash the whole pipeline over one bad listing.
- **JSON from Claude must be clean.** Prompt explicitly for raw JSON only, validate with `json.loads()` before use.
- **Stay within Apify free tier.** Cap total daily results to ~150 jobs across all queries.
