from agent.handoffs import JobSpec
from agent.llm import chat_json
from agent.prompts import load_prompt, untrusted


def deterministic_spec(job: dict) -> JobSpec:
    b = job.get("budget", {})
    return JobSpec(job_id=job["job_id"], title=job["title"], required_skills=job.get("required_skills", []),
                   budget_min=b.get("min"), budget_max=b.get("max"),
                   budget_type=b.get("type", "fixed" if (b.get("max") or 0) > 50 else "unknown"),
                   screening_questions=job.get("screening_questions", []))


def analyse(job: dict) -> JobSpec:
    base = deterministic_spec(job)
    try:
        spec = chat_json("analyst", load_prompt("analyst"),
                         untrusted("job_post", f"Title: {job['title']}\n{job['description']}\nSkills: {job.get('required_skills')}"), JobSpec)
    except Exception:  # noqa: BLE001 - degrade to structured fields on the post
        return base
    # structured marketplace fields beat LLM guesses
    spec.job_id, spec.title = base.job_id, base.title
    spec.required_skills = base.required_skills or spec.required_skills
    spec.budget_min, spec.budget_max, spec.budget_type = base.budget_min, base.budget_max, base.budget_type
    spec.screening_questions = base.screening_questions or spec.screening_questions
    return spec
