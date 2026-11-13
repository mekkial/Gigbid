"""Prompt templates a freelancer would actually pick in Claude Desktop / Cursor."""


def answer_screening_question(question: str) -> str:
    return ("Answer this client screening question using ONLY my portfolio. First call search_evidence with the key "
            "requirement from the question, then answer in 60-120 words, citing the project ids you used. If the "
            f"portfolio has no support, say so plainly instead of inventing experience.\n\nQuestion: {question}")


def summarise_fit(job_description: str) -> str:
    return ("Assess how well I fit this job. Break it into requirements, call search_evidence for each, and give a table "
            "of requirement -> evidence ids -> supported/partly/unsupported, then an overall fit score 0-100.\n\n"
            f"Job:\n{job_description}")


def draft_cover_letter(job_description: str, tone: str = "direct and friendly") -> str:
    return (f"Write a cover letter (120-220 words, {tone}) for this job. Open with the client's problem. Every claim about "
            "my experience must come from search_evidence results and cite the project id. No guarantees, no contact "
            f"details.\n\nJob:\n{job_description}")
