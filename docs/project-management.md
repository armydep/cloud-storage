# Project Management Guide

How work is planned, sliced, tracked, and finished in this project.

This guide is written for a team of one to three people. Practices that only pay
off at larger team sizes are deliberately left out, and called out as such where
it matters — adopting them early creates overhead without signal.

Read [ROADMAP.md](../ROADMAP.md) first; this document explains how to work from
it day to day.

## Contents

1. [The three layers](#1-the-three-layers)
2. [Referring to work: ID conventions](#2-referring-to-work-id-conventions)
3. [The board](#3-the-board)
4. [Slicing work into issues](#4-slicing-work-into-issues)
5. [Definition of Ready](#5-definition-of-ready)
6. [Definition of Done](#6-definition-of-done)
7. [Work in progress limit](#7-work-in-progress-limit)
8. [Dependencies and blocked work](#8-dependencies-and-blocked-work)
9. [Managing large findings documents](#9-managing-large-findings-documents)
10. [Cadence](#10-cadence)
11. [What to measure](#11-what-to-measure)
12. [Recurring maintenance](#12-recurring-maintenance)
13. [Weekly checklist](#13-weekly-checklist)
14. [Practices deliberately not adopted](#14-practices-deliberately-not-adopted)

---

## 1. The three layers

Every piece of work lives at exactly one of three levels.

| Layer | Answers | Lifespan | Lives in |
| --- | --- | --- | --- |
| **Roadmap** | *Why*, and roughly *when* | Months; changes rarely | `ROADMAP.md` |
| **Issue** | *What* — one discrete outcome | Days to two weeks | GitHub Issues |
| **Pull request** | *How* | Hours to days | GitHub PRs |

The rule that keeps this working:

> **The roadmap describes outcomes. It never describes tasks.**

"Delete files" is an outcome. "Add a DELETE endpoint to the files router" is a
task, and belongs in an issue. A roadmap that accumulates tasks needs constant
editing, goes stale, and then stops being trusted — at which point it is worse
than no roadmap.

`ROADMAP.md` currently gets this right. The process in its
*"Adding roadmap items"* section is the correct one. Follow it.

### Which layer does this belong in?

- Will it still matter in three months? → Roadmap.
- Is it one shippable outcome a user or operator would notice? → Issue.
- Is it a step toward an issue? → It is not a tracked item at all. It is a
  commit, or a checklist line inside the issue.

---

## 2. Referring to work: ID conventions

The roadmap is numbered (`1.4`, `3.7`, `8.2`). So is
[docs/scalability-review.md](scalability-review.md) (`1.1`, `4.1`, `8.2`).
**These two schemes overlap.** `8.2` means *"Split backend file transfers into
dedicated upload and download services"* in one document and *"content-addressed
keys with no reference counting"* in the other.

Always prefix the source when referring to a numbered item:

| Write this | Not this |
| --- | --- |
| `ROADMAP 1.4` | `1.4` |
| `SCALE 8.2` | `8.2` |
| `#40` | `issue 40` |

Use these prefixes in issue titles, PR descriptions, and commit messages. It
costs nothing and removes a whole class of confusion later.

---

## 3. The board

The project board is at `https://github.com/users/armydep/projects/3`, and
`.github/workflows/add-to-project.yml` adds new issues and pull requests to it
automatically using the `PROJECTS_TOKEN` secret.

Configure these columns:

```
Backlog  →  Ready  →  In progress  →  In review  →  Done
```

| Column | Meaning |
| --- | --- |
| **Backlog** | Captured, not yet specified. Unordered. |
| **Ready** | Specified well enough to start right now with no further thinking. |
| **In progress** | Being actively worked on *today*. |
| **In review** | PR open, waiting on CI or a reviewer. |
| **Done** | Merged to `main`. |

Two habits keep a board honest:

- If an item has not moved in a week, it is either blocked or not really being
  worked on. Say which, in a comment.
- If the board does not match reality, fix the board immediately. A board that
  is known to be wrong gets ignored, and then it is pure overhead.

---

## 4. Slicing work into issues

### Slice vertically

An issue should cut through every layer it needs and end with something
demonstrable.

| Good — vertical | Bad — horizontal |
| --- | --- |
| "A user can delete a file they own" — migration, API, UI, tests | "Add delete endpoint" / "Add delete button" / "Add delete tests" |

A vertical slice can be shipped, demoed, and reverted on its own. A horizontal
slice is half a feature that cannot be any of those things.

### Size rule

> **If it cannot be merged within about three days, split it.**

Not for velocity accounting — because long-lived branches drift away from `main`
and turn into merge conflicts.

This project has already paid that cost once. A review branch sat open while
other work landed on `main`; by the time it was revisited it had unresolvable
conflicts in eight files and had to be rebuilt from scratch against a fresh
`main`. The work was fine. The branch had simply lived too long.

### Splitting a large outcome

When a roadmap item is too big for one issue, split it into vertical slices that
each stand alone:

Roadmap outcome: *ROADMAP 3.4 — Sorting, filtering, and search*

- Sort folder contents by name and size
- Paginate folder contents *(needs SCALE 4.1 first)*
- Filter contents by file category
- Full-text search across a user's files

Each is shippable. None is "the backend part of search".

### Research is its own issue

If you cannot write acceptance criteria, the work is not an implementation task
yet. Open a separate issue — *"Investigate X and produce a plan"* — whose
deliverable is a document or a comment, not code. Close it when the decision is
made, then open the implementation issues it produced.

---

## 5. Definition of Ready

Do not move an issue to **Ready** until all of the following are true.

- [ ] A one-sentence outcome, in user or operator terms
- [ ] Acceptance criteria as a checklist, roughly three to six items
- [ ] Linked roadmap item, if it serves one (for example `ROADMAP 1.4`)
- [ ] Known blockers linked, and the `blocked` label applied if any are open
- [ ] Obvious enough that you know which file you would open first

If you cannot fill these in, the issue is not ready. That is useful information,
not a failure — it usually means a decision has not been made yet.

### Issue template

```markdown
## Outcome
A user can permanently delete a file they own.

## Roadmap
ROADMAP 1.4

## Acceptance criteria
- [ ] `DELETE /api/v1/files/{id}` removes the metadata row
- [ ] Only the owner can delete; others receive 404
- [ ] The stored object is released only when no other metadata references it
- [ ] The file disappears from the folder listing without a page reload
- [ ] Backend tests cover owner, non-owner, and shared-blob cases

## Blocked by
#<blob reference counting issue>  (SCALE 8.2, SCALE 8.3)

## Notes
See docs/scalability-review.md section 8.
```

---

## 6. Definition of Done

An issue is Done when **all** of these hold:

- [ ] CI is green — `test-backend`, `test-docker-compose`, `pre-commit`,
      Playwright
- [ ] Merged to `main`
- [ ] Every acceptance criterion is checked
- [ ] `ROADMAP.md` updated if the change completed a roadmap outcome
- [ ] Documentation updated if behaviour or setup changed

### Never merge red

The automated gates only work if a red check means "actually broken". Once red
becomes background noise, CI stops being a safety net.

This project has already seen the failure mode: three unrelated CI defects sat
red across every open pull request at once — a missing environment file, a
Playwright version mismatch, and a formatter upgrade — and because red was
normal, none of them was noticed for a while. They masked each other, and they
masked whether any of the twelve open dependency updates were genuinely safe.

If a check is red and the cause is genuinely unrelated to the change, fix the
cause as its own issue rather than merging past it.

---

## 7. Work in progress limit

> **Cap "In progress" at one item for a solo developer, two for a pair.**

This is the single highest-leverage habit in this guide, and the least intuitive.

Five things at eighty percent complete ship nothing. One thing at one hundred
percent ships. A low WIP limit also keeps branches short-lived, which prevents
the merge-conflict problem described in section 4.

When something blocks, **do not start a third thing**. Either clear the blocker,
or move the item back to Backlog with a comment naming what it is waiting on.

---

## 8. Dependencies and blocked work

Dependencies held only in your head are the ones that cause damage.

There is a live example. `ROADMAP 1.4` (Delete files) and `ROADMAP 1.5`
(Delete folders) are both in Current focus. Neither can safely ship until blob
reference counting exists (`SCALE 8.2`, `SCALE 8.3`) — object keys are derived
purely from content hash with no reference count, so deleting one user's file
removes bytes that another user's metadata still points to.

Make that visible:

1. Open an issue for the prerequisite work.
2. On the blocked issue, add `Blocked by: #<number>`.
3. Apply the `blocked` label.
4. Move it out of **Ready**.

GitHub does not enforce this. The label and the comment exist so that a future
reader — including you in three weeks — does not pick up the blocked item and
quietly ship data loss.

Currently blocked, per the scalability review:

| Roadmap item | Blocked by | Reason |
| --- | --- | --- |
| ROADMAP 1.4, 1.5 — Delete files and folders | SCALE 8.2, 8.3 | Shared blobs have no reference count |
| ROADMAP 1.2 — Rename folders | SCALE 6.1 | Subtree path rewrite is unbounded |

---

## 9. Managing large findings documents

[docs/scalability-review.md](scalability-review.md) contains 32 items. Do not
turn it into 32 issues.

> **An open issue implies intent to do the work.**

A backlog full of things that will not be done is noise, and noise makes the real
work harder to see. It also makes the board unreadable and the project feel
hopeless.

Instead:

- **The document is the backlog** for its topic. Leave it there.
- **Create issues only for what will be scheduled in the next month or two.**
- When a roadmap phase reaches the relevant area, pull the items out of the
  document and write issues then.

Applied to the current scalability review, roughly four issues are worth opening
now, not thirty-two:

| Issue | Covers | Why now |
| --- | --- | --- |
| Verify blob ownership on upload completion | SCALE 8.1 | Live cross-tenant read; not a scale problem |
| Blob reference counting | SCALE 8.2, 8.3 | Blocks ROADMAP 1.4 and 1.5 |
| Paginate folder contents plus creation timestamps | SCALE 1.1–1.4, 4.1 | ROADMAP 3.7 already plans the timestamps |
| Connection pooling and cached storage client | SCALE 2.1, 3.1 | Small, self-contained, removes a scaling cap |

Everything else waits in the document.

The same rule applies to any future audit, security review, or brainstorm.

---

## 10. Cadence

For one to three people:

| Ritual | When | Duration | Purpose |
| --- | --- | --- | --- |
| **Backlog grooming** | Weekly | 20 minutes | Reorder Backlog, promote two or three items to Ready, close what will never be done, adjust the roadmap if a phase shifted |
| **Board update** | On every merge | Seconds | Keep the board matching reality — mostly automated |
| **Roadmap review** | Monthly, once there is more than one contributor | 30 minutes | Confirm phases still reflect intent |

Grooming is the one that matters. Skipping it is how a backlog becomes a
graveyard.

---

## 11. What to measure

Most metrics are vanity at this size. These three carry real signal, because
they measure *flow* rather than output.

| Signal | Why it matters | Investigate when |
| --- | --- | --- |
| **Age of the oldest open PR** | Predicts merge pain | Older than one week |
| **Time `main` stays red** | Predicts whether CI is trusted | More than a few hours |
| **Items in "In progress"** | Predicts throughput | More than two |

Deliberately not measured: issues closed per week. Counting closed issues only
encourages slicing them finer.

---

## 12. Recurring maintenance

Maintenance without a rhythm becomes an emergency.

**Dependency updates.** Dependabot generates pull requests continuously.
`.github/dependabot.yml` groups minor and patch updates per ecosystem, so this is
usually one pull request rather than a dozen.

- Weekly: merge the grouped minor/patch pull request once CI is green.
- Major version bumps: review individually. Green CI proves nothing exploded; it
  does not prove behaviour is unchanged across a major version.

A backlog of twelve dependency pull requests once accumulated here precisely
because there was no routine slot for them.

**Other recurring work** — dependency audits, backup restore drills, checking
for orphaned storage objects — gets the same treatment: a scheduled slot, or it
becomes an incident.

---

## 13. Weekly checklist

Twenty minutes, once a week.

- [ ] Does the board match reality? Fix it if not.
- [ ] Any item stuck in the same column for a week? Comment on why, or move it.
- [ ] Any pull request open longer than a week? Merge, split, or close it.
- [ ] Is `main` green?
- [ ] Merge the grouped dependency pull request if CI is green.
- [ ] Promote two or three Backlog items to Ready, using the Definition of Ready.
- [ ] Close anything that will honestly never be done.
- [ ] Did anything finish that completes a roadmap outcome? Tick it in
      `ROADMAP.md`.

---

## 14. Practices deliberately not adopted

At one to three people, these cost more than they return. Revisit when the team
grows past roughly five people, or when more than one person is regularly
blocked waiting on another.

| Practice | Why it is skipped |
| --- | --- |
| Sprints and fixed iterations | Adds ceremony without improving prioritisation at this size |
| Story points and velocity | Estimation overhead exceeds its planning value |
| Burndown and burnup charts | Nothing to communicate upward yet |
| Daily standups | Meaningless with one person; a message suffices with three |
| Formal retrospectives | The weekly grooming already covers this informally |
| Separate QA sign-off | Definition of Done plus CI already gates it |
| Release trains | Continuous merge to `main` is simpler and already in place |

The rule behind all of these: **adopt a practice when you feel the pain it
solves, not before.**
