from pydantic import BaseModel

from agent.handoffs import MessageIntent, ReplyDraft
from agent.llm import chat_json
from agent.prompts import load_prompt, untrusted


class _Out(BaseModel):
    intent: MessageIntent
    text: str


async def respond(tools, proposal_id: str, message: str, requirement_hint: str = "") -> ReplyDraft:
    evidence = await tools.call("client_liaison", "search_evidence", requirement=message[:200] or requirement_hint, k=2)
    slots = await tools.call("client_liaison", "free_slots")
    ev = "\n".join(f"[{e['id']}] {e['text'][:300]}" for e in evidence)
    o = chat_json("client_liaison", load_prompt("liaison"),
                  f"{untrusted('client_message', message)}\n\nEVIDENCE:\n{ev}\nAVAILABLE SLOTS: {slots}", _Out)
    return ReplyDraft(proposal_id=proposal_id, intent=o.intent, text=o.text,
                      proposed_slots=slots if o.intent.intent == "interview_request" else [])
