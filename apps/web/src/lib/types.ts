export interface Evidence { id: string; type: string; source: string; date: string; outcome: string | null; skills: string[]; text: string }
export interface Claim { text: string; evidence_ids: string[]; verdict: "supported" | "partly_supported" | "unsupported" }
export interface Critique { approved: boolean; grounding: number; personalisation: number; length_ok: boolean; issues: string[] }
export interface Risk { score: number; flags: string[]; client_quality: number; is_scam: boolean; injection_detected: boolean; explanation: string }
export interface Fit { score: number; matches: { requirement: string; evidence_ids: string[]; supported: boolean }[]; matched_skills: string[]; missing_skills: string[]; reasons: string }
export interface Price { amount: number; budget_type: string; floor: number; market_p50: number | null; connects_cost: number; connects_worth_it: boolean; rationale: string }
export interface DryRun { dry_run: boolean; would_send?: { job_id: string; cover_letter: string; bid_amount: number }; connects_cost?: number; balance_after?: number }
export interface ProposalPayload {
  kind?: string; pending: boolean; job_id?: string; draft: string; send_text: string; claims: Claim[]; evidence: Evidence[];
  risk_report: Risk; price_quote: Price; critiques: Critique[]; compliance?: { allowed: boolean; violations: string[] }; dry_run?: DryRun;
}
export interface MessagePayload { kind: "message_approval"; proposal_id: string; client_message: string; intent: { intent: string }; draft: string; proposed_slots: string[] }
export interface JobDetail {
  run: { thread_id: string; job_id: string; status: string; title: string | null; fit: number | null; risk: number | null; decision: string | null; price: number | null; summary: Record<string, any> };
  job: { title: string; description: string; required_skills: string[]; budget: { min: number; max: number; type?: string }; connects_cost: number } | null;
  job_spec: { deliverables: string[]; required_skills: string[]; budget_min: number | null; budget_max: number | null; budget_type: string; hidden_needs: string[]; screening_questions: string[] } | null;
  risk_report: Risk | null; fit_report: Fit | null; evidence: Evidence[] | null; decision: { action: string; reason: string } | null; price_quote: Price | null;
}
export interface TraceItem { node: string; latency_s: number; tokens_in?: number; tokens_out?: number; cost_usd?: number; models?: string[]; replay?: boolean }
export interface RunDetail { run: { thread_id: string; job_id: string; status: string; title: string | null }; trace: TraceItem[]; trace_url: string | null; totals: { steps?: number; tokens?: number; cost_usd?: number } }
export interface ThreadItem { thread_id: string; job_id: string; title: string | null; proposal_id: string; messages: { from: string; text: string }[]; conversation: { thread_id: string; status: string } | null }
export interface Health { marketplace: "up" | "down"; detail?: string }
