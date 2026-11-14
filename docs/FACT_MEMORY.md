# Shared candidate fact memory

This protocol applies to every career workflow in Codex, Claude Code, Antigravity and other agents. It supplements `docs/CODEX.md`; preserve all candidate pauses and submission authorization rules. The fact base is the existing editable Markdown workspace, not a separate database or an agent's private memory. Do not migrate or rewrite historical personal data automatically.

## Shared storage

| Location | Purpose |
|---|---|
| `profile/profile.md` | Current candidate profile and entry point; link detailed facts and limitations here. |
| `profile/intake.md` | Dated answers, corrections, decisions, preferences, conflicts, questions, skips and next steps. |
| `profile/sources.md` | Source IDs, original paths and extraction coverage. |
| `story-bank/*.md` | Detailed project/employer evidence with provenance and limits; link from the profile. |

All candidate-specific entries belong in ignored files. `output/applications/YYYY-MM-DD/<identity>/candidate-answers.md` and `facts.md` can preserve verbatim answers and review bundles, but are not the shared base. An answer stored only there or only in chat has not been synchronized. The shared entry must contain the reusable factual substance and limitations, not merely a link to an application. Keep the original answer/source link as provenance.

## Read before retrieving or asking

Before each fact retrieval, question group, fit evaluation, drafting or revision step, read the current on-disk `profile/profile.md` and `profile/intake.md`, then the relevant linked stories and source catalog entries. Do this again on resume, after candidate replies, after edits by another agent or the candidate, and before reusing an earlier fact bundle. Do not rely on an earlier chat read, remembered summary, master resume or previous application. If a file is too large, inventory its headings and read it in complete sequenced chunks; do not treat truncated output as full coverage. Targeted searches locate evidence but do not replace reading the relevant entries and their limits.

Before posing a question, check existing answers, negative answers, skips, pending questions and unresolved conflicts across the shared base. Reuse a clear existing answer. Do not repeat a skipped question or a pending question from another application. Ask again only for a material unresolved distinction, an actual contradiction or a potentially changed fact, explaining what is already known and the specific update needed. Unknown is not absent; a skip is not a negative answer.

If a required file is unavailable, report the gap and do not silently substitute memory or ask the candidate to repeat information without explaining the access problem.

## Persist every new item

After each candidate reply or selected-source intake, before using the new information or ending the turn:

1. Extract every distinct new fact, correction, boundary, negative answer, uncertainty, preference and decision. Split compound replies so that small details are not lost. Preserve actual versus planned work, personal versus commercial use, ownership, dates, units and absent measurements. A statement that changes nothing can point to its existing entry without duplicating it.
2. Record the answer in `profile/intake.md` with date, stable question/item ID, verbatim wording (or an exact source location), factual interpretation, provenance, status and unresolved limits. Use `in source`, `candidate confirmed`, `conflict` or `unknown`; track skipped/pending as question states, not factual confirmation. Candidate statements are not independently verified. Assistant wording, reviewer suggestions and job requirements do not establish candidate facts.
3. Update `profile/profile.md` with each reusable fact or a concise linked summary. Put project detail in the relevant story and link it from the profile; update `profile/sources.md` for new sources. Keep absence of experience and limitations discoverable across applications too. Workflow decisions/preferences belong in the intake journal; do not turn them into CV claims.
4. Preserve prior versions and provenance when correcting a fact. Mark superseded interpretations and the scope of the correction; never silently erase a contradiction or choose whichever version improves a CV. Explicit candidate edits to the fact files are candidate input: preserve their wording and record the change when observed; ask only if the factual meaning or conflict is ambiguous. Do not overwrite those edits from stale application copies.
5. Refresh affected application bundles and derived materials when they are next used. Recheck master freshness and invalidate stale reviews as required by `docs/REVIEW_CYCLE.md`. Do not bulk-rewrite unrelated historical applications or immutable snapshots.

## Saved completeness self-check

Before each handoff, final response, mandatory candidate pause, review-package handoff or readiness/status decision, reconcile every candidate reply and selected-source fact processed since the last audit against the saved shared base. Reread the actual saved entries, rather than assuming a successful write means their content is complete. Preserve mandatory pauses: save what is known, then wait; never invent missing answers to finish an audit.

For applications, append a dated check to `output/applications/YYYY-MM-DD/<identity>/fact-sync-audit.md`. For work without an application, append it to `profile/intake.md`. Include:

- Scope: which replies/question IDs or sources were processed and whether coverage was complete or partial.
- One row per distinct new item: source/answer ID, shared destination and heading/item ID, status/limits, and whether it was newly saved, updated or already present.
- Files freshly read, and unresolved extraction, storage or conflict items. Distinguish missing persistence from a properly recorded unknown/conflict.
- Result: `PASS` only if every processed item is accounted for in shared storage; otherwise `INCOMPLETE` with the missing items and next step. If there were no new facts, state that explicitly and identify what was checked; never fabricate rows.

Fix missing persistence before claiming synchronization, handing off a complete review package or marking READY_TO_APPLY. If saving is unavailable, keep the result INCOMPLETE and report it. A recorded conflict can pass storage completeness but remains unusable as an established claim. This audit checks persistence, not factual truth, independent review or submission. Include the audit reference in the application evidence/review index. In the user-facing reply briefly state where new facts were saved or identify any unsaved items; do not claim a historical audit of applications that were not checked.
