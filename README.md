# 🧬 LinkedIn Daily Job Matcher

> An AI-powered pipeline that scrapes LinkedIn every morning, scores job listings against my CV using Claude, and delivers a ranked digest to my inbox — with a personal web dashboard to track everything over time.

---

## 💡 Why I Built This

Job hunting in a specialised field (data + bioinformatics) is noisy. Most job boards surface the same generic listings, and manually scanning LinkedIn every day is slow and inconsistent.

I built this tool to automate the search entirely and replace manual scrolling with a personalised, AI-scored daily briefing — so I spend my time applying to the right jobs, not finding them.

This project also gave me hands-on experience with things I wanted to learn: working with APIs, deploying Python apps on a Linux server, automating tasks with cron, building a web dashboard, and using Git properly on a real project.

---

## ✨ Features

- 🔍 **Daily LinkedIn scraping** via [Apify](https://apify.com/) — no manual searching
- 🤖 **AI-powered scoring** using the Claude API — each job is evaluated against my actual CV and experience bank
- 📊 **Structured scoring rubric** across 6 dimensions (skills overlap, experience relevance, seniority fit, and more)
- 📧 **Daily email digest** — top 10+ jobs ranked by fit score, with per-category breakdowns and plain-English explanations
- 🌐 **Personal web dashboard** — browse, filter, and search all scored jobs over time at my domain
- 🗃️ **SQLite job history** — every scored job is stored; no duplicate entries across days
- 🔒 **Secure by design** — all secrets in `.env`, CVs excluded from Git, server hardened with firewall and fail2ban

---

## 🏗️ Architecture

```
Apify LinkedIn Scraper
        │
        ▼
  fetch_jobs.py        ← Pull raw job listings via Apify API
        │
        ▼
  filter_jobs.py       ← Remove student jobs, Danish-required roles, duplicates
        │
        ▼
  score_jobs.py        ← Send job + CV context to Claude API → structured JSON scores
        │
        ▼
  rank_jobs.py         ← Sort by overall score, select top 10+
        │
   ┌────┴────┐
   ▼         ▼
send_email  save_to_db
(Gmail SMTP) (SQLite)
                │
                ▼
        Flask Dashboard
        (jobs.yourdomain.com)

All triggered by cron at 07:00 daily on a Hetzner VPS
```

---

## 🧠 Scoring Rubric

Each job is scored across six categories by Claude, grounded in my CV content:

| Category | Max | What it measures |
|----------|-----|-----------------|
| `background_match` | 10 | Domain fit — bioinformatics, pharma, biotech, data |
| `skills_overlap` | 30 | Required skills vs. my actual technical stack |
| `experience_relevance` | 30 | Job responsibilities vs. my past projects and roles |
| `seniority` | 10 | Entry/mid preference — penalises lead and director roles |
| `language_requirement` | 10 | English-friendly — penalises Danish-required listings |
| `company_score` | 10 | Bonus for biotech, pharma, and AI companies |
| **overall** | **100** | Sum of all categories |

Claude also returns a per-category reasoning string and a recommendation label: **Strong Yes / Yes / Maybe / No**.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11 |
| Job scraping | [Apify](https://apify.com/) — LinkedIn Jobs Scraper actor |
| AI scoring | [Anthropic Claude API](https://www.anthropic.com/) (`claude-sonnet-4-20250514`) |
| Email | Gmail SMTP via Python `smtplib` |
| Database | SQLite (built into Python) |
| Web dashboard | Flask |
| Server | Hetzner VPS — CAX11, Ubuntu 24.04 |
| Web serving | nginx + systemd |
| Scheduling | cron (`0 7 * * *`) |
| Version control | Git + GitHub |
| Config | python-dotenv |

---

## 📁 Project Structure

```
linkedin-job-matcher/
├── src/
│   ├── main.py             # Orchestrator — runs full pipeline
│   ├── fetch_jobs.py       # Apify API integration
│   ├── filter_jobs.py      # Job cleaning and filtering
│   ├── score_jobs.py       # Claude API scoring loop
│   ├── rank_jobs.py        # Sorting and selection
│   ├── send_email.py       # Gmail SMTP digest
│   └── save_to_db.py       # SQLite persistence
├── dashboard/
│   ├── app.py              # Flask web app
│   ├── templates/          # Jinja2 HTML templates
│   └── static/             # CSS
├── data/                   # Runtime data (gitignored)
├── logs/                   # Pipeline logs (gitignored)
├── .env.example            # Environment variable template
├── requirements.txt
├── PLAN.md                 # Full technical spec and build plan
└── README.md               # This file
```

> ⚠️ CV files and `.env` are excluded from this repository for privacy.

---

## 🚀 Setup & Local Development

### Prerequisites
- Python 3.11+
- An [Apify](https://apify.com/) account (free tier works)
- An [Anthropic API](https://console.anthropic.com/) key
- A Gmail account with an [App Password](https://support.google.com/accounts/answer/185833) set up

### 1. Clone and set up environment

```bash
git clone https://github.com/yourusername/linkedin-job-matcher.git
cd linkedin-job-matcher

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure secrets

```bash
cp .env.example .env
# Open .env and fill in your API keys and email credentials
```

### 3. Add your CV files

```bash
mkdir cvs
# Place these files inside:
#   cvs/master_cv_bio.tex
#   cvs/master_cv_data.tex
#   cvs/relevant_experience_bank.md
```

### 4. Run the pipeline

```bash
python src/main.py
```

### 5. Run the dashboard locally

```bash
python dashboard/app.py
# Open http://localhost:5000
```

---

## ☁️ Deployment (Hetzner VPS)

The pipeline runs on a Hetzner CAX11 instance (Ubuntu 24.04) with:

- **nginx** as a reverse proxy serving the Flask dashboard on a custom domain
- **systemd** managing the Flask app as a persistent service
- **cron** triggering the pipeline at 07:00 daily: `0 7 * * * /path/to/venv/bin/python /path/to/src/main.py`
- **ufw firewall** and **fail2ban** for basic server hardening

---

## 📬 Email Digest Example

```
🧬 Your Daily Job Matches — 6 Apr 2026 | 23 jobs scored

──────────────────────────────────────────────
Rank #1  ·  Overall: 87/100  ·  ✅ Strong Yes
Bioinformatics Data Scientist @ Novo Nordisk
📍 Copenhagen  ·  🗓 Posted: today

  Background Match       9 / 10
  Skills Overlap        26 / 30
  Experience Relevance  25 / 30
  Seniority Fit         10 / 10
  Language               9 / 10
  Company Bonus          8 / 10

Why it fits: Strong alignment with your NGS analysis and Python background.
The role explicitly lists tools from your CV. Company is a top-tier pharma target.

Best CV: bio
🔗 Apply → linkedin.com/jobs/view/...
──────────────────────────────────────────────
```

---

## 🗺️ Roadmap

- [x] Core scraping + scoring pipeline
- [x] Daily email digest
- [x] Web dashboard with job history
- [ ] Cross-day deduplication (skip already-seen jobs)
- [ ] Recency bonus in scoring (boost jobs posted today)
- [ ] Dashboard search bar and date range filter
- [ ] Weekly summary email: "Best job of the week"

---

## 🤝 What I Learned

Building this project gave me practical experience with:

- **Python project structure** — organising a real multi-file project with modules
- **REST APIs** — calling and polling Apify and the Anthropic Claude API
- **Prompt engineering** — writing structured prompts that return consistent, parseable JSON
- **SQLite** — storing and querying data without a full database server
- **Flask** — building and deploying a lightweight web app in Python
- **Linux server administration** — SSH, ufw, fail2ban, nginx, systemd
- **Cron scheduling** — automating tasks on a server
- **Git workflow** — branching, committing with conventional messages, pushing to GitHub
- **Security basics** — environment variables, `.gitignore`, App Passwords, server hardening

---

## 📄 License

This project is for personal use. Not affiliated with LinkedIn, Apify, or Anthropic.

---

*Built in Copenhagen 🇩🇰 · Powered by Claude + Apify*
