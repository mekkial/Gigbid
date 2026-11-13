# How to label the 30 proposals (judge calibration)  — takes ~40 minutes

File: `evals/results/judge_calibration_sheet.csv` (open in Excel/Numbers/Google Sheets). **Do not open `judge_calibration_hidden.json`** until you are done: it contains the judge's scores and would bias you.

For each row read the job (title + description) and the proposal, then fill the last two columns **yourself** (the brief requires your own labels):

* `human_acceptable (1/0)`: would a careful freelancer send this with at most trivial edits? Say **0** if it makes a claim you cannot support from the evidence, is generic ("I am the best candidate"), pushes contact details or guarantees, or is clearly too short/long (aim 120-220 words).
* `human_overall (1-5)`: 5 = excellent and specific to this job, 3 = fine but generic, 1 = unusable.

Be strict about **invented experience**: that is the thing GigBid exists to prevent. When unsure, label 0.

Then run: `python -m evals.runners.judge_calibration --score` (prints Cohen's kappa and the disagreements; commit `judge_calibration.json`).
Also useful for the viva (question 8): note two items where you and the judge disagree and who was right.

## Blind pairwise panel (classmates, optional but asked for in the brief)
Send 3-5 classmates 10 pairs of anonymised proposals for the same job (one from `v0_naive`, one from `v3_rerank`, random order; use `evals/results/proposals_*.jsonl`) and ask "which would you rather send?". Count wins for each variant and run `binom_two_sided(wins, n)` from `evals/runners/judge_calibration.py` for a sign-test p-value.
