# 011 Propose-strategy skill for local agents
Status: done
Problem: the judge exists, but an agent dropped into the repo doesn't know how to run the research loop well: what a good hypothesis looks like, when to ask validation, what's off-limits, and how to avoid re-proposing dead ideas.
Outcome: `.claude/skills/propose-strategy/` (plain Markdown, usable by Claude Code, Codex or anyone) with the loop, a strategy template, and a notebook convention (`strategies/candidates/NOTEBOOK.md`) that carries lessons between sessions. Human docs: README and `docs/running-an-experiment.md`.
Done when: a fresh agent session can follow the skill against a synthetic season and produce judged candidates and notebook entries without touching anything off-limits.
Notes: 2026-10-16 dry run by a fresh agent: 3 strategies judged, notebook written, nothing off-limits touched (checked git status and the ledger). It reported ten points of friction, fixed in the skill, template and reports. It also surfaced a fake effect in the synthetic market (see LEARNINGS).
