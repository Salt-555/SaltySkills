---
name: skill-gauntlet
description: Design and run test gauntlets to improve any skill.
version: 2.0.0
author: Hermes
metadata:
  hermes:
    tags: [Skills, Testing, Refinement, Subagents]
---

# Skill Gauntlet

## Overview

Take any skill (skill X) and any improvement goal ("make it better at Y")
and run a test gauntlet that proves whether the skill actually delivers Y —
then integrates what the tests prove. The gauntlet is designed from the
goal, not from a template: improving an editor skill means renders graded
on picture and pacing; improving a data skill means outputs graded on
correctness and edge cases. This skill does NOT author skills from scratch
— it hardens ones that exist.

## When to Use

- "improve skill X at Y" / "make skill X better at Y" — any improvement goal
- "test/sharpen/stress-test skill X" — even without a specific Y
- a skill passed its first real task but hasn't been adversarially exercised
- repeated silent-failure bugs suggest untested paths
- a skill has grown patches and needs consolidation (a clean pass)

Don't use for: authoring a new skill from scratch.

## Prerequisites

- The target skill exists and loads via `skill_view`.
- `delegate_task` available for parallel subagents.

## Step 0 — Frame the goal, set the human gate

Restate the improvement goal as a testable claim: "the skill reliably
produces [outcome Y]". Everything downstream — test design, grading,
verdicts — checks that claim.

**Ask the user one question before dispatching anything:** should the
subagents' work get a human check gate?

- **Yes, every round** — artifacts go to the user with specific review
  prompts after each test round. Use when the skill produces perceptual
  output (video, audio, documents, UI) or when quality is subjective.
  This is how rhythm, pacing, tone, and "looks wrong" bugs get caught —
  automated checks pass them.
- **Yes, final round only** — machine-grading throughout, human review at
  the end. Faster; use when the goal is mechanically verifiable.
- **No gate** — fully autonomous. Only when correctness is objectively
  testable and the user opts out.

Default to asking; never silently skip the gate for perceptual output.

## The Loop

1. **Design tests from the goal.** If Y is broad ("better overall"), one
   brief per distinct capability the skill claims; if Y is narrow ("better
   at audio ducking"), briefs that stress exactly that path plus its
   neighbors. Each brief is a REAL task that forces the skill's
   load-bearing claims to execute. Save briefs to a shared test dir with
   the sources testers need. Every brief ends with the same reporting
   contract (below).
2. **Dispatch parallel testers.** One `delegate_task` call, one task entry
   per tester, each with: the brief path, the skill name, their assigned
   angle, and a private work dir. Testers get `output_schema` with
   `rendered_ok`, `findings_file`, `critical/major/minor_defects`,
   `verdict` so results come back structured. Testers load the CURRENT
   skill from disk via `skill_view` — never a synopsis in the brief (a
   synopsis tests the orchestrator's memory, not the skill).
3. **Human check gate** (as decided in Step 0). Deliver the testers'
   artifacts to the user with specific review prompts — what to look at,
   per artifact, tied to goal Y. Integrate those reads as first-class
   findings. Skip only if the gate was declined.
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
  rate CRITICAL/MAJOR/MINOR), **What worked** (load-bearing and correct —
  so integration doesn't break it), **Editorial notes**.
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
- **Human gate findings outrank machine findings.** A user's "this feels
  wrong" is a defect even when every automated check passes — it proved
  the skill's grading blind spot, not the user's taste.

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
version and archive the findings. With a human gate: also have the user
review the final artifacts; a satisfied user is the exit criterion.
