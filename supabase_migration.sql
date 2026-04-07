-- JobSniper Pipeline Migration
-- Run this in your Supabase dashboard: SQL Editor → New Query → Paste → Run
--
-- Adds pipeline-specific columns to the existing jobs table.
-- All columns use IF NOT EXISTS so it's safe to run multiple times.

-- 'pipeline' or 'manual' — how the job entered the system
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS source text DEFAULT 'manual';

-- Which daily pipeline run found this job (for filtering by date)
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS pipeline_date date;

-- Full score breakdown as JSON: {background_match, skills_overlap, ...}
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS pipeline_scores jsonb;

-- "strong yes", "yes", "maybe", "no"
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS apply_recommendation text;

-- "bio", "data", or "both" — which CV template fits best
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS matched_cv text;

-- {what_they_want, why_you_match, gaps} — quick summary for the email/dashboard
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS summary jsonb;
