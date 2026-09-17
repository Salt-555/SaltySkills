---
name: skill-gauntlet
description: Run skills through subagent test gauntlets to refine them.
version: 1.2.0
author: Hermes
metadata:
  hermes:
    tags: [Skills, Testing, Refinement, Subagents]
---

# Skill Accelerator

Turns a working-but-green skill into a refined one through an orchestration
loop: design real tasks, subagents execute them using the skill, you vet
and integrate their defect reports, then a cleaning subagent consolidates
into the next generation. It does NOT replace authoring a skill from
scratch — load it once a skill exists and has survived one real use.

## When to Use

- "sharpen/tighten/stress-test this skill"
- a skill passed its first real task but hasn't been adversarially exercised
- repeated silent-failure bugs suggest untested paths
- a skill has grown patches and needs consolidation (gen2)

## Prerequisites

- The target skill exists and loads via `skill_view`.
- `delegate_task` available for parallel subagents.

## The Loop

1. **Design tests.** Write one brief per editorial-style/angle the skill
   claims to cover, each a REAL task that forces the skill's load-bearing
   claims to execute. Save briefs to a shared test dir with the sources the
   testers need. Every brief ends with the same reporting contract (below).
2. **Dispatch parallel testers.** One `delegate_task` call, one task entry
   per tester, each with: the brief path, the skill name, their assigned
   angle, and a private work dir. Testers get `output_schema` with
   `rendered_ok`, `findings_file`, `critical/major/minor_defects`, `verdict`
   so results come back structured. Testers load the CURRENT skill from
   disk via `skill_view` — never a synopsis in the brief (a synopsis tests
   the orchestrator's memory, not the skill).
3. **Human check gate (optional but recommended).** Between test rounds,
   deliver the testers' rendered outputs to the user with specific review
   prompts — what to watch for, per artifact. Human review catches quality
   failures that automated checks pass (rhythm, pacing, audio levels,
   incoherence); integrate those reads as first-class findings. Use this
   gate whenever the skill produces perceptual output (video, audio,
   documents) or before calling a generation "done".
4. **Vet.** For each finding: is it reproducible, is it consistent with
   other testers' reports, does it contradict something already in the
   skill? Verify claims you doubt yourself (a quick probe beats a wrong
   patch). Rejected findings get a reason — noise is how skills bloat.
5. **Integrate.** `skill_manage` patches: SKILL.md for the load-bearing
   rules, `references/` via `file_path` for depth. Fix the false sentence,
   not just the symptom. Check the index promises against the files that
   exist. Integrate ONLY what changes behavior.
6. **Clean (next gen) — only when warranted.** Cleaning is not a default
   step every generation; run it on evidence: SKILL.md drifting past
   ~200-220 lines, the same fact documented in two places, or a test round
   flagging wording (not missing facts) as the problem. A gen that only
   adds new pitfalls needs the next test round, not a clean — cleaning a
   moving target wastes the pass and invites over-trimming to justify the
   subagent's existence. When you do run it: spawn one cleaning subagent
   to drop bloat, consolidate duplicates, cut narration, tighten to the
   house style (~100 lines simple, ~200 complex; ≤60-char description; no
   router sections). You accept/reject its suggestions at your own
   discretion, then bump the version. Expect to reject 1-2 proposals per
   pass (route-phrase cuts and reference-file merges are the usual
   over-reaches).

## Tester Reporting Contract (in every brief)

- Do NOT edit the skill or course files — you are a tester; report back.
- `findings.md` with: **Skill defects** (quote the exact misleading text,
  rate CRITICAL/MAXOR-worth/MINOR), **What worked** (load-bearing and
  correct — so integration doesn't break it), **Editorial notes**.
- "Honest over flattering. A clean run with zero findings is suspicious."
- Verify deliverables by inspecting actual output (frame content, file
  structure, rendered results) — exit codes and counts lie.

## Orchestrator Discipline

- **Do not do the testing yourself.** The moment you fall into
  hand-debugging the task, you are a tester with a conflict of interest:
  you wrote the skill, so you avoid its rough edges a fresh user hits.
  Dispatch, steer, integrate — hands off the work itself.
- **Steer stragglers.** When one tester runs long, `delegate_task
  action='steer'` with "wrap up now: write findings with what you have, a
  partial honest report beats a complete late one."
- **Test briefs are load-bearing.** A bad brief (arithmetic that doesn't
  sum, cut points that don't exist) burns the tester's time and poisons
  findings. Sanity-check the brief's numbers before dispatch.
- **Provenance matters.** Track which findings came from which tester and
  which you verified yourself — the cleaning subagent should know what is
  battle-tested vs. speculative.

## Pitfalls

- Integration without vetting imports the tester's misunderstandings into
  the skill. Verify before you patch.
- Fixing the symptom sentence leaves the wrong mental model that produced
  it — hunt the paragraph that taught the mistake.
- A cleaning pass that only deletes is safe; one that also rewrites risks
  breaking load-bearing claims. When cleaning touches a pitfall that came
  from a verified failure, re-verify it still reads true.
- Patches to `references/` files need `file_path` in the `skill_manage`
  op — a wrong-path patch aborts the whole batch (atomic), so batch
  same-file edits together and different-file edits separately.

## Verification

After a full loop: run the test suite once more with one fresh subagent on
the hardest brief. If the new tester's findings.md reports zero CRITICAL
defects on paths that previously failed, the generation is done — bump the
version and archive the findings.
