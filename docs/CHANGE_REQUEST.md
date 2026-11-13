# Change request: platform policy update (simulated)

The instructor's real policy update was not available to me, so I **simulated** one with the two ingredients the brief describes ("a new rule or cost affecting bidding"):

1. **New rule:** every proposal must disclose AI assistance ("This proposal was drafted with AI assistance and reviewed by me.").
2. **New cost:** jobs paying under $500 cost +2 Connects.

The simulated instructor edit to GigSim (`gigsim/rules.yaml`, `gigsim/app.py`, commit `ff32a4c`) is **not** counted; I counted only what I had to change in GigBid. Because I wrote GigSim myself, I also cannot claim I did not know where the seams were; treat this as a measurement of the architecture, not of surprise.

## What I had to edit in GigBid
| Change | Files | Lines |
|---|---|---|
| Required disclosure phrase | `data/policy_pack/policy_rules.yaml` (+2: a `required_phrases` list) | +2 |
| Compliance Guard appends missing required phrases (generic: any phrase in the list, idempotent, survives human edits because edits are re-checked) | `agent/nodes/compliance.py` | +3 |
| Surcharge | **nothing**: GigSim now returns the effective `connects_cost`; pricing, the dry-run preview and the approval screen all read that field | 0 |
| Tests | `tests/unit/test_change_request.py` (new) | +20 |

Total production change: **5 lines in 2 files** (`git diff --numstat` after commit `ff32a4c`). No prompt changed, no graph changed, no UI change, no API change.

## What this says about the design (and what it does not)
* It worked cheaply because compliance rules are **data** (`policy_rules.yaml`) and the Compliance Guard is the last step before the approval screen **and** re-runs on human edits, so one change covers generated and edited text.
* The cost change was free because the marketplace port returns the platform's effective cost instead of GigBid recomputing it. Had GigSim applied the surcharge only at submission, the dry-run preview would have under-reported it and GigBid would have needed an extra call; the exercise would then have cost more.
* **Not covered:** the Writer was not told about the disclosure (it is appended after the Critic), so the Critic's length check sees text 12 words shorter than what is sent; the 3,000-character platform limit is checked after appending, which is correct, but I did not test a draft within 60 characters of the limit.
* A rule that needs *reasoning* (for example "no claims about a client's industry unless the client named it") would not be absorbed this cheaply: it needs a prompt and an LLM check, not a regex list.
