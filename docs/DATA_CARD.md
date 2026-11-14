# Data card

GigBid uses **real** public job postings for market realism and **synthetic** data wherever real data does not exist
(freelancer portfolios, past proposals with outcomes, client histories and preferences, scams, prompt injections, gold labels).
Every synthetic record carries `"synthetic": true`; real records carry `"synthetic": false` and a `source`.

## Sources

| Source | Used for | Size | Real? |
|---|---|---|---|
| Kaggle `ahmedmyalo/upwork-freelance-jobs-60k` (`Final_Upwork_Dataset.csv`) | jobs (title, description, skills = `Category_1..9`), Connects cost, client spend/rating/payment verification/country, fixed or hourly budget | 63,950 rows -> 3,000 kept after cleaning | **real** |
| Kaggle `asaniczka/upwork-job-postings-dataset-2024-50k-records` (`upwork-jobs.csv`) | overall hourly/fixed price statistics (market p50) | 53,058 rows (2023-12-02 to 2024-02-23) | **real** |
| `data/build/gen_data.py` (seeded, `SEED=4016`) | 3 freelancer personas, 16 case studies each (some describing the same project twice), repo READMEs and code stubs, reviews, 150 labelled past proposals each, 80 clients with hidden preferences, 630 labelled jobs | see below | **synthetic** |

Not used: the other four datasets listed in the brief (no fields we needed that the two above lack).

**Licences** (read from the Kaggle API metadata on 2026-11-14):
* `ahmedmyalo/upwork-freelance-jobs-60k`: **Apache 2.0**. Redistribution of derived data is allowed with attribution and a statement of changes; the changes are the cleaning steps in `data/build/`.
* `asaniczka/upwork-job-postings-dataset-2024-50k-records`: **ODC Attribution License (ODC-By)**. Use is allowed with attribution. Only aggregate price statistics are derived from it.

Attribution: "Upwork freelance jobs (+60k)" by ahmedmyalo and "Upwork Job Postings Dataset 2024 (50K Records)" by asaniczka, both on Kaggle.
The repository does not redistribute the raw CSVs (`data/raw/` is git-ignored). It ships only the cleaning code, the cleaned 3,000-job sample, and derived statistics (`market_stats.json`).
The jobs are public postings; no personal data about freelancers is included, and client rows contain only aggregate stats.

## Preprocessing (`data/build/prepare_jobs.py`)
1. Drop rows with missing title/description or descriptions < 80 characters; drop exact duplicates of (title, description).
2. Skills = non-null `Category_1..9`. Budgets parsed from `Job_Cost` (fixed) or `Start_rate`/`End_rate` (hourly) into USD numbers.
3. Route each job to a persona bucket by keyword (`DOMAINS`), keep a seeded random 3,000 (2,225 full-stack, 411 data-analyst, 364 AI/ML). The routing is only a convenience for statistics; it is **not** a gold label.
4. Market statistics (`data/processed/market_stats.json`): p25/p50/p75 per bucket and kind (fixed, hourly).
5. Client records from the real rows keep spend, rating, verification, country. **Hidden preferences (budget ceiling, dislike of generic openings) are synthetic** even though the client row is real.

## Synthetic corpus design (what makes retrieval non-trivial, and its limits)
* Personas: AI/ML engineer, full-stack developer, data analyst. Each has 8 base projects x 2 (the second is a "phase 2" of the same project, so evidence is described twice).
* Some skills are only *implied* ("packaged the service so it ran identically on any machine" for Docker).
* Past proposals: 35% generic openings (win/reply rates 5% / 15%), 65% specific (22% / 38%) so outcome-aware ranking has signal.
* Dev sets (`evals/datasets/dev_<persona>.jsonl`): per persona 200 jobs + 10 duplicates = 210 rows: 90 good (gold bid), 40 out-of-scope (skip), 20 low-ball budget (skip), 30 scams (unpaid work, off-platform contact/payment), 20 with planted prompt-injection text (gold: still bid, and ignore the instruction).
  Gold fields: `decision`, `scam`, `injected`, `evidence_ids` (case-study ids whose skills match), `fair_price_band`.

## Limitations (read before trusting any number)
* **Templated text.** Case studies and proposals come from templates; vocabulary overlap between jobs and evidence is high. Absolute retrieval scores are optimistic; the *ordering* of variants is the finding.
* **Gold evidence = skills overlap**, not a human judgement of relevance. It cannot reward evidence that is relevant for other reasons.
* **Fair price band = the posted budget** for synthetic jobs, so "price inside the band" is close to trivial there; it is only informative for hourly jobs.
* **Real jobs have no gold labels**; they feed the live stream, pricing statistics and demos, not the metrics.
* **Simulated clients** decide replies from skill overlap, budget ceiling, generic-opening penalty and a specificity bonus (`gigsim/app.py::_simulate_client`) plus seeded noise. Reply rate therefore measures "does the proposal look good to this simulator", which is correlated with, but not the same as, real client behaviour. Weights live in `gigsim/rules.yaml`.
* The hidden test set mentioned in the brief is not available to me; the dev sets are split by `load_jobs` (stratified, seeded) and no result is tuned on a held-out set except the V8 threshold (calibrated on one persona, tested on the other two).
* Free-tier LLM limits (8,000 tokens/min and 1,000 requests/day per model) cap evaluation sizes; every results file records its `n`. Small `n` means wide confidence intervals.
* Personal data: none; emails/phone numbers in logs are masked (`mcp_servers/common.py::mask_pii`, `apps/api/logging_config.py`).
