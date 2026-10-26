> **Codex, Claude Code & Antigravity:** See the [workspace contract](docs/CODEX.md) and [bounded review-cycle protocol](docs/REVIEW_CYCLE.md) (plus `AGENTS.md` and `CLAUDE.md`) for unified repo skills, privacy, application identity/status, and independent review across all three environments. `.claude/` remains the unchanged upstream reference.

<picture>
  <img src="assets/banner.svg" alt="Open Career Skills: Claude skills for the job hunt that refuse to invent facts about you" width="100%">
</picture>

# Open Career Skills

**The prompt architecture behind [JobMentis](https://jobmentis.com/en/claude-skills-for-job-hunting?ref=oss-readme), open-sourced as installable Claude skills — extended in this fork into a deterministic, multi-agent career workspace for Codex, Claude Code, and Antigravity.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

## How This Fork Works (Codex, Claude Code & Antigravity)

While the upstream repository targets Claude Code with single-pass markdown outputs, this fork layers a **strict provenance, deterministic state, and bounded multi-round review architecture** on top of the untouched `.claude/` upstream prompts. You can switch freely between **Codex**, **Claude Code**, and **Antigravity** on the exact same local career data without path or state drift.

```mermaid
flowchart TD
    subgraph Agents["1. Multi-Agent Entry Layer"]
        Codex["Codex (AGENTS.md + .agents/skills/ocs-*)"]
        AGY["Antigravity (AGENTS.md + .agents/skills/ocs-*)"]
        Claude["Claude Code (CLAUDE.md + /commands & ocs-*)"]
        Contract["Workspace Contract (docs/CODEX.md + docs/REVIEW_CYCLE.md)"]
        Upstream["Unchanged Upstream Prompts (.claude/commands, skills, agents)"]
        Codex --> Contract
        AGY --> Contract
        Claude --> Contract
        Contract -. "overrides paths, states & review" .-> Upstream
    end

    subgraph Intake["2. Source Intake, Provenance & Master Resumes"]
        RawDocs["Original DOCX / XLSX / PDF + Git Repos"]
        IntakePy["scripts/intake.py (SHA-256 copy + cell/paragraph extraction)"]
        Sources["profile/sources.md + profile/intake.md (Epistemic labels)"]
        Profile["profile/profile.md + story-bank/*.md"]
        Masters["output/master-resumes/{backend-fullstack,platform-devops-sre}.md"]
        CheckMaster["scripts/check_master.py (SHA-256 freshness gate)"]
        RawDocs --> IntakePy --> Sources --> Profile --> Masters --> CheckMaster
    end

    subgraph Discovery["3. Job Discovery & Deterministic Application Identity"]
        JobInputs["Manual JD / URL, Portals, or ./scripts/hirify"]
        Inbox["tracker/inbox.md (Dedup by canonical URL / source ID)"]
        AppPy["scripts/application.py init"]
        AppDir["output/applications/<company>-<role>-<hash>/ (identity.json, job.md, status.md)"]
        JobInputs --> Inbox --> AppPy --> AppDir
    end

    subgraph Evaluation["4. Eligibility Gate & Mandatory Interactive Pauses"]
        Elig["Eligibility First (Remote, Serbia, B2B/Contractor, Visa, Language)"]
        Fit["Weighted Fit Evaluation (fit-evaluation.md)"]
        Stop1(["HARD STOP 1: User decides whether to draft"])
        OptP1["Requirement Mapping + Optimizer Phase 1 Questions"]
        Stop2(["HARD STOP 2: User answers or skips questions"])
        AppDir --> Elig --> Fit --> Stop1 --> OptP1 --> Stop2
    end

    subgraph ReviewCycle["5. Bounded 3-Round Text Review Cycle (scripts/review_cycle.py)"]
        Draft["Draft cv.md + facts.md (Transport bundle with source locations)"]
        Snap["review_cycle.py start / snapshot (Immutable SHA-256 manifest)"]
        Subagent["Fresh Independent Reviewer Subagent per Round (Task / Codex Subagent / invoke_subagent)"]
        Record["review_cycle.py record (Validates hashes, fresh reviewer_id & round cap <= 3)"]
        Stop2 --> Draft --> Snap --> Subagent --> Record
        Record -- "outcome: revise (round 1 or 2)" --> Draft
        Record -- "outcome: needs_input (user adds new facts)" --> OptP1
    end

    subgraph FinalGate["6. Handoff, DOCX/PDF Rendering & Final Gate"]
        TextHandoff["User inspects reviewed Markdown (passed / plateau / limit_reached)"]
        Render["Render from documents/templates/*.docx (Unbulleted paragraphs + visual/PDF check)"]
        FinalRev["Fresh Independent Final Review (final-review.md with render hashes)"]
        Ready["State: READY_TO_APPLY (tracker/applications.md + status.md)"]
        Applied["State: APPLIED (Only after explicit user confirmation + submission date)"]
        Record -- "passed / plateau / limit_reached" --> TextHandoff --> Render --> FinalRev --> Ready --> Applied
    end
```

### Key Enhancements Over Upstream

1. **Cross-Agent Compatibility without Upstream Drift**
   - **`.claude/` stays untouched** so upstream updates merge cleanly.
   - **[AGENTS.md](AGENTS.md)** (loaded automatically by Codex and Antigravity) and **[CLAUDE.md](CLAUDE.md)** (loaded automatically by Claude Code) apply the rules in **[docs/CODEX.md](docs/CODEX.md)** and **[docs/REVIEW_CYCLE.md](docs/REVIEW_CYCLE.md)**.
   - Nine `ocs-*` skill adapters (`ocs-workspace`, `ocs-optimizer`, `ocs-stories`, `ocs-evidence`, `ocs-jobs`, `ocs-ats`, `ocs-letter`, `ocs-interview`, `ocs-linkedin`) live in `.agents/skills/` and `codex/skills/` (kept byte-for-byte identical and verified by `tests/test_workspace_compat.py`).

2. **Auditable Source Intake & Master Resumes**
   - **`python3 scripts/intake.py <file>...`** copies selected DOCX/XLSX files into content-addressed `documents/sources/` and extracts text with exact paragraph or sheet/cell coordinates.
   - Every fact in `profile/profile.md` and `story-bank/*.md` carries provenance (`profile/sources.md`, `profile/intake.md`) and an epistemic status (`in source`, `candidate confirmed`, `conflict`, or `unknown`). Disputed facts are excluded until resolved.
   - Two directional master resumes (`output/master-resumes/backend-fullstack.md` and `output/master-resumes/platform-devops-sre.md`) embed SHA-256 hashes of all source files; **`python3 scripts/check_master.py`** flags `STALE` inputs before reuse.

3. **Deterministic Application Identity & 10-State Pipeline**
   - **`python3 scripts/application.py init --company ... --role ... --url ... [--source-id ...]`** normalizes URLs (stripping tracking parameters) and creates a stable folder `output/applications/<company>-<role>-<hash>/` with `identity.json`, `job.md`, and `status.md`.
   - Eligibility precedes fit scoring and explicitly tracks **international remote**, **work from Serbia**, and **B2B/contractor** status (`confirmed`, `unknown`, `not eligible`) alongside work authorization, location, and language.
   - Applications follow a strict 10-state machine in `status.md` and `tracker/applications.md`: `INBOX`, `EVALUATED`, `DRAFTING`, `IN_REVIEW`, `READY_TO_APPLY`, `APPLIED`, `INTERVIEWING`, `OFFER`, `REJECTED`, `DROPPED`. Opening a form or generating files never sets `APPLIED` — only explicit user confirmation with a submission date does.

4. **Bounded 3-Round Independent Review Cycle & Two-Stage Gate**
   - **`python3 scripts/review_cycle.py`** (`start`, `snapshot`, `record`, `status`) manages an immutable, lock-protected audit journal under `output/applications/<app>/review-cycles/<cycle>/rounds/<round>/`.
   - Each round snapshots `cv.md`, `job.md`, `facts.md`, and all underlying source files with SHA-256 manifests, then dispatches a **fresh independent reviewer subagent** (`Task`/`Agent` in Claude Code, a fresh subagent in Codex, or `invoke_subagent` in Antigravity) with defanged `<job_description>` fences.
   - The helper enforces at most **3 review rounds per cycle**, requires a distinct `reviewer_id` per round, and invalidates stale snapshots if live inputs change (`exit code 2`).
   - **Two-stage readiness**: after the Markdown text cycle completes, the user reviews the text first. Only then is the CV rendered from the reference template in `documents/templates/` into DOCX/PDF (using separate unbulleted experience paragraphs) and audited in a separate `final-review.md` before `READY_TO_APPLY`.

5. **Sandboxed Local Tooling & Verification**
   - **Optional Hirify CLI (`./scripts/hirify`)**: pinned to `hirify-cli` in `package.json`, storing config and credentials strictly inside git-ignored `.hirify/config/` with auto-updates disabled.
   - **Automated test suite (`python3 -m unittest discover -s tests`)**: 29 deterministic unit tests covering DOCX/XLSX intake, canonical URL & source-ID deduplication, the 3-round review state machine, skill sync, and `.gitignore` privacy guards.

---

Generic AI career advice gets people rejected: polished emptiness, invented metrics, "results-driven professional" boilerplate that recruiters spot in three seconds. These skills are built the opposite way. Their defining behavior is that they **ask you a question rather than invent a fact about you**, and they enforce the writing craft (plain verbs, real numbers, say-it-out-loud naturalness) that survives both ATS parsers and human readers.

Run them locally in Claude Code or Claude Desktop, on your own subscription, with your data on your machine.

## The eight skills

| Skill | What it does | The rule that makes it different |
|---|---|---|
| **ruthless-cv-optimizer** | Rewrites your CV against a specific job description | Two-phase flow: it diagnoses and ASKS about suspect numbers and empty bullets, waits for your answers, then rewrites. Gaps are reported honestly, never papered over. |
| **star-story-extractor** | Turns a messy braindump into a sharp STAR interview story, filed in your story bank | Missing metric: it asks you ONE question instead of estimating. Also matches your bank against any pasted JD. |
| **linkedin-360brew-planner** | Plans and drafts LinkedIn posts under the 2026 ranking rules | Built on LinkedIn's 360Brew decoder model (the reason hashtags and pods died). Saves over likes, analytical first line, pillar discipline. |
| **cover-letter-writer** | A 300-400 word letter grounded in your real stories | Two or three deep JD connections instead of six shallow ones; banned-cliche list enforced. |
| **mock-interviewer** | A pressure-tested rehearsal, one question at a time | Stays in character, interrupts rambling, drills "what did YOU do?", then debriefs against structure / specificity / ownership / quantification. |
| **job-search** | Finds current postings matching your profile | Zero dependencies; only reports jobs it actually fetched or you pasted. Blocked boards get you ready-made search URLs, never invented listings. |
| **evidence-miner** | Harvests real achievements from your git history into the story bank | Groundedness rule: no citable artifact (commits, PRs, dates), no proposed achievement. Business impact numbers come from you, never inferred from code. |
| **ats-detective** | Works out which Applicant Tracking System a company runs, and the CV rules that follow | Confirms the vendor from the posting URL or a live public board API, never from a guess. A board whose declared name disagrees with the company is rejected, and "could not probe" is never reported as "not present". |

## The /apply pipeline

The skills also compose into one end-to-end flow per job:

<picture>
  <img src="assets/terminal-apply.svg" alt="An /apply run: fit evaluation with an honest verdict, a hard stop for your call, drafting from your facts only, the reviewer restoring a mutated number, tracker entry" width="100%">
</picture>

The reviewer is a separate subagent that audits every claim in the drafts against your actual profile and stories; anything unsourced gets flagged for removal, not "improved". After the pipeline, `/mock-interview` rehearses the evaluation's real gaps and `/upskill` turns gaps recurring across 2+ applications into a learning plan. Full walkthrough: [docs/WORKFLOW.md](docs/WORKFLOW.md). Per-skill contracts: [docs/SKILLS.md](docs/SKILLS.md). Something misbehaving: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Install

### Option A: use this workspace (recommended)

The repo is a ready-to-run Claude Code career workspace with file-based memory: your profile in `profile/`, your STAR stories in `story-bank/`, your content calendar in `content/`.

```bash
# fork on GitHub first (keep your fork private if you plan to push), then:
git clone https://github.com/squerne/open-career-skills.git
cd open-career-skills
claude
# then, inside Claude Code:
/setup
```

`/setup` builds your profile from a pasted CV or a guided interview. From there:

```
/find-jobs        # real postings matching your profile, fit-triaged
/apply <url>      # the full pipeline: evaluate, draft, review, track
/optimize-cv      # paste a JD, get a tailored CV in output/
/extract-story    # braindump a win, get a STAR story in story-bank/
/mine-evidence    # harvest achievements from your git history
/plan-content     # 6 post ideas, or draft one post
/cover-letter     # tailored letter in output/
/mock-interview   # one question at a time, debrief at the end
/upskill          # learning plan from gaps recurring across applications
```

Your personal data (`profile/profile.md`, your stories, your calendar, everything in `output/`) is **git-ignored by design**: even if you push your fork publicly, your CV and metrics stay local.

### Option B: install individual skills

Copy any skill folder into your own project or user skills directory:

```bash
cp -r .claude/skills/ruthless-cv-optimizer ~/.claude/skills/
```

Works in Claude Code and Claude Desktop (any agent that reads `SKILL.md` skills). Without the workspace, skills ask you to paste your CV instead of reading `profile/`.

### Option C: plain chat (ChatGPT, claude.ai, Gemini)

The five writing skills have self-contained paste-able versions in [`prompts/`](prompts/). Paste one as your first message and follow along. You lose the file-based memory; the prompts tell you what to paste each time. (`/apply`, `/find-jobs`, `/upskill`, and `/mine-evidence` need file and web tools, so they are Claude Code only.)

## Why we open-sourced this

Prompts are a commodity; anyone can copy text. What they can't copy from a markdown file is the system around it. We build [JobMentis](https://jobmentis.com/en/claude-skills-for-job-hunting?ref=oss-readme), a career OS where these same engines run against a persistent, structured version of your career: CV analyses, a searchable story bank, a job tracker, and interview intelligence that feed each other automatically. The [full story of why we did this, and where the free skills end and the product begins](https://jobmentis.com/en/claude-skills-for-job-hunting?ref=oss-readme), is on that page.

This repo is the honest free tier. It genuinely works, and we want it to: a job search run on grounded, non-fabricated assets is better for everyone, including the recruiters. What the hosted product adds is scale and statefulness:

| | This repo | JobMentis |
|---|---|---|
| The prompt craft | ✅ identical philosophy | ✅ |
| Your cost | your Claude subscription | free tier + Pro |
| Memory | markdown files in your fork | structured, searchable, cross-device, plus a confirmed-facts memory every check trusts |
| Claim verification | the `/apply` reviewer flags unsourced claims per run | a groundedness reviewer on every rewrite, plus "this is true, remember it" so confirmed facts are never re-flagged |
| CV ↔ story bank ↔ JD matching | manual, per session | automatic, across your whole pipeline |
| Job pipeline tracking | a folder of files | tracker with per-vendor ATS rules |
| Mock interviews | text chat | live voice, company-specific question banks |
| Personality-aware coaching, human coaches | ❌ | ✅ |

If the flat files start feeling like the bottleneck, that's the moment we built the product for: https://jobmentis.com/en/signup?ref=oss-readme

## FAQ

**Do these work with models other than Claude?**
The `prompts/` versions work with any capable chat model. The `SKILL.md` versions target Claude Code / Claude Desktop.

**Why do the skills refuse to add metrics to my CV?**
Because invented numbers are the fastest way to fail an interview. The skills ask you for the real figure; if you don't have one, an unquantified true bullet beats a quantified fake one.

**What is 360Brew?**
LinkedIn's decoder-only ranking foundation model (published on arXiv, January 2025). It reads post text directly, which is why hashtags, pods, and link-in-first-comment tricks stopped working. Longer explanation: https://jobmentis.com/en/guide/linkedin-algorithm-guide

**Is my data sent anywhere?**
Only to the model provider you already use (Anthropic, OpenAI, ...). The workspace stores everything in local files, and the `.gitignore` keeps personal files out of your commits.

**Can I contribute a skill?**
Yes. See [CONTRIBUTING.md](CONTRIBUTING.md). The quality bar: no skill may fabricate user facts, ever.

## Acknowledgments / Credits

This repo stands on ideas from two MIT-licensed projects, reimplemented (not copied) for this workspace:

- **[MadsLorentzen/ai-job-search](https://github.com/MadsLorentzen/ai-job-search)**: the fork-and-run workspace pattern, and the concepts behind our `/apply` drafter-reviewer pipeline, the application tracker, and `/upskill` gap analysis. If you want LaTeX/PDF CV output or Danish job-board CLIs, use his repo; it does both better than we ever will in Markdown.
- **[Play-New/apply-new](https://github.com/Play-New/apply-new)**: the principle that career evidence should come from work artifacts and that every prose claim should trace to underlying data. Our `evidence-miner` skill and the reviewer's groundedness audit are descendants of that idea.

## License

MIT. "JobMentis" is a trademark of JobMentis; the license covers the prompts and code in this repo, not the brand.
