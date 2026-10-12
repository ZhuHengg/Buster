# Build Roadmap: Proactive CCTV Alert System

Design: [`docs/SOLUTION_PLAN.md`](../../SOLUTION_PLAN.md) · Problem: [`docs/PROBLEM_STATEMENT.md`](../../PROBLEM_STATEMENT.md)

| Phase | Plan | Delivers | Can start when | Done when |
|---|---|---|---|---|
| 1. Minimum complete demo | [phase1](2026-10-11-cctv-alert-phase1.md) | Live CMS, YOLO tracking, Rule B trigger, Claude verification, guard approve/reject, call/SMS escalation, incident log, replay mode | Now | Snatch clip → alert card ≤ 10 s; normal clip 10 min → 0 alerts; full flow works with zero credentials |
| 2A. Gemini Step 1 | [phase2 Part A](2026-10-11-cctv-alert-phase2-action-model.md) | Gemini Flash screener as a second Step 1 trigger next to Rule B, dataset used as a benchmark (event recall, false triggers per hour) | Phase 1 done; benchmark needs ≥ 15 labelled snatch events from ≥ 10 sources and ≥ 30 min normal (indicative only) | Benchmark report with intervals; case-1/case-2 checked once after the threshold is frozen; snatch → card ≤ 10 s |
| 2B. Action model (deferred) | [phase2 Part B](2026-10-11-cctv-alert-phase2-action-model.md) | Leak-safe dataset build, VideoMAE fine-tune, event-level evaluation, model trigger added to `AnyTrigger` | Part A done **and** 60 snatch segments from ≥ 40 sources, ≥ 2 h normal | Test event recall ≥ 0.90 on the same split Gemini was benchmarked on; Step 1 ≤ 2 s |
| 3. Evidence, scale, feedback | [phase3](2026-10-11-cctv-alert-phase3-evidence-scale.md) | Benchmark report, cameras-per-GPU scale test, Results page, guard feedback → training data, frozen demo build | Phase 1 done (Phase 2 optional) | Reports generated with the real verifier; 3 clean rehearsals; tag `v1.0-demo` |

## Order and parallel work

```
Week-by-week order (solo):

 Build (agent)    ── Phase 1 ──────────────►── Phase 2 Tasks 1–5 ──►── Phase 3 ──► v1.0-demo
 Human work       ── film staged clips ─► download + label online/UCF clips ─► guard/resident interviews
                     (FILMING_GUIDE.md        (label_tool.py, from Phase 2          (fills baseline.json)
                      lands in Phase 2 T1;    Task 1 onward)
                      the shot list is
                      already in spec §12)
```

- **Start filming and collecting clips while Phase 1 is being built.** Data collection is the long pole for Phase 2.
- **If time runs short, skip Phase 2B (training).** Phase 3 works with `TRIGGERS=rule|llm|both`. Spec §12: the action model is the first thing cut.
- Phase 3 Task 4 (feedback loop) feeds back into Phase 2 Tasks 2–4 for a retraining round.

## Things only you can provide

| Item | Needed by | Where it goes |
|---|---|---|
| Which demo clip is the snatch, which is normal; escape direction → gate | Phase 1 Task 1 | `backend/data/cameras.json` |
| More normal clips to fill the 3×3 grid (optional) | Phase 1 Task 11 | `backend/data/` + `cameras.json` |
| Anthropic API key (optional; mock used without it) | Phase 1 Task 6 | `backend/.env` |
| Twilio account + 2 verified phone numbers (optional; dry run without it) | Phase 1 Task 8 | `backend/.env` |
| Staged clips, online clips, UCF-Crime subset, labels | Phase 2 Task 1 | `backend/data/datasets/` |
| Guard interview result: time-to-notice baseline | Phase 3 Task 3 | `backend/reports/baseline.json` |

## Kickoff message for each new chat

> Implement `docs/superpowers/plans/<plan file>` using superpowers:executing-plans. The design is in `docs/SOLUTION_PLAN.md`; the roadmap is in `docs/superpowers/plans/README.md`. Work task by task, test first, and commit after each task on branch `phase-<n>` (not `main`). Stop and ask me at any "Human step" or when a task says to ask the user.

## Outside these plans

Not development work, but needed for judging:
- User interviews (problem statement "Assumptions to validate")
- The pitch deck
- The staged-clip shoot itself
