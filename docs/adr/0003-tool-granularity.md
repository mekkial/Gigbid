# ADR 0003 — Tool granularity hypothesis (written before running `tool_granularity.py`)

* **H-A1** Many fine-grained tools (~35) lower tool-selection accuracy vs. our tuned set (15 tools), especially on the small model,
  because near-duplicate tools ("get_job_skills" vs "get_job_budget" vs "get_job_title") compete for attention.
* **H-A2** Few coarse tools (4, action+params) keep tool selection high but lower *argument* accuracy, since the model must pick an
  action string and nest arguments.
* **H-A3** The tuned set (clear, rewritten descriptions) wins on argument accuracy and costs fewer prompt tokens than the fine-grained set.
* Metrics: tool-selection accuracy, argument accuracy (value-matched), prompt tokens per task; 40 tasks; strong and small model.
