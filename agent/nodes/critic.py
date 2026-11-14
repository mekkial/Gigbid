from agent.handoffs import Critique, ProposalDraft
from agent.llm import chat_json, load_config
from agent.prompts import load_prompt, untrusted


def review(job: dict, draft: ProposalDraft, unsupported: int) -> Critique:
    words = len(draft.cover_letter.split())
    user = (f"{untrusted('job_post', job['title'] + chr(10) + job['description'])}\n\nPROPOSAL:\n{draft.cover_letter}\n"
            f"Unsupported claims remaining after verification: {unsupported}. Word count: {words}.")
    c = chat_json("critic", load_prompt("critic"), user, Critique)
    cfg = load_config()["critic"]
    c.length_ok = cfg["min_words"] <= words <= cfg["max_words"]
    if not c.length_ok:
        c.approved = False; c.issues.append(f"cover letter is {words} words; target 120-220")
    if unsupported:
        c.approved = False; c.issues.append("unsupported claims remain")
    return c
