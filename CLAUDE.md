@AGENTS.md

# Claude Code notes

- Slash commands (`.claude/commands/`), skills (`.claude/skills/`) and the `application-reviewer` agent (`.claude/agents/`) are the unchanged upstream sources. Use them through the routing table in AGENTS.md; `docs/CODEX.md`, `docs/FACT_MEMORY.md` and `docs/REVIEW_CYCLE.md` override conflicting upstream rules.
- Independent review: dispatch a fresh `application-reviewer` subagent via the `Task`/`Agent` tool for each round and record its ID as `reviewer_id`.
