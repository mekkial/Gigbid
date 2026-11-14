# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Freelancers (first persona: an AI/ML freelancer) who bid on marketplace jobs and want to stop wasting time, paid Connects and generic proposals. Secondary audience for the public landing page: course reviewers and hiring managers who open the link to judge the project.
_Inferred from the repository and the original assignment; not confirmed in an interview (the user asked to proceed quickly)._

## Product Purpose
GigBid finds jobs, judges whether to bid, flags scams and prompt-injection attempts, and drafts proposals in which every claim links to the freelancer's own portfolio evidence. A human approves every proposal and message before anything is sent.

## Positioning
Evidence-linked claims plus a mandatory human approval, shown by live agent progress (the product never leaves the user guessing whether it is still working).

## Constraints
No invented customers, testimonials, pricing or statistics on any page: the marketplace is a simulator (GigSim) and the data is partly synthetic. Numbers shown must come from `evals/results/*.json`.
The existing Playwright tests in `apps/web/tests/e2e` must keep passing. Accessibility: keyboard and reduced-motion support.

## Visual commitments (binding, from the user)
Use the downloaded "Tessel Agent Landing" component (pixel-mosaic, serif headlines, mono labels, hairline frame) on the **cobalt** palette. The landing page is the main attraction; app screens stay calm with light interactivity, not a mosaic everywhere.
