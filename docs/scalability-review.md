# Scalability Review

Assessment of where Cloud File Storage would hit limits as usage grows, and how
those limits line up with the plans already recorded in [ROADMAP.md](../ROADMAP.md).

- **Commit reviewed:** `b860f41`
- **Scope:** backend (`app/files`, `app/core`, `app/api`), frontend upload and
  download flow, database schema and migrations, container and compose config.
- **Status:** analysis only. No code changes are proposed by this document.

Findings are grouped into sections and numbered so individual items can be
referenced, scheduled, and turned into issues independently. Every item cites
the code it came from.

## How to read this

Each item carries a roadmap status:

| Mark | Meaning |
| --- | --- |
| Tracked | ROADMAP.md already describes this outcome |
| Partial | ROADMAP.md implies it, or covers part of it |
| Gap | Not currently represented in ROADMAP.md |

Tiering is by *when the problem starts to hurt*, not by severity:

- **Tier 1** — degrades under ordinary usage, independent of data volume.
- **Tier 2** — surfaces as the number of files, folders, or users grows.

## Summary

| | Count |
| --- | --- |
| Total items | 32 |
| Tier 1 (Sections 1–3) | 11 |
| Tier 2 (Sections 4–7) | 12 |
| Correctness and security (Section 8) | 3 |
| Missing at scale (Section 9) | 6 |
| Tracked in ROADMAP.md | 7 |
| Partial in ROADMAP.md | 3 |
| Gap | 22 |

## What the current design gets right

Worth stating before the findings, because it is the decision that matters most
for a file service: **file bytes never pass through the API**. The backend issues
a presigned URL and the browser transfers directly to and from object storage
(`app/files/service.py`, `frontend/src/features/files/fileTransfer.ts`). API
servers therefore do not become a bandwidth bottleneck, which is the most common
way file-storage services fail to scale.

Content-addressed object keys (`sha256/<hash>`, `app/core/storage.py:22`) give
natural deduplication, and the index set added in `b4c7d8e9f012` and
`b5e2a91c7f34` matches the query shapes the application actually issues.

The findings below concern the layers built on top of that foundation.

## Sequencing conflicts with current focus

Update 2026-08-09: the delete-file and delete-folder blockers identified here
were resolved by Phase 6 and Phase 7 through blob ref counts, per-user blob
claims, and safe recursive folder deletion. The rename-folder warning remains
open.

At the time of this review, two roadmap items in **Current focus** depended on
groundwork that did not exist yet:

| Roadmap item | Depends on | Consequence if shipped first |
| --- | --- | --- |
| [#40 Delete files](https://github.com/armydep/cloud-storage/issues/40), [#41 Delete folders](https://github.com/armydep/cloud-storage/issues/41) | Items 8.2, 8.3 | Deleting one user's file destroys bytes still referenced by other users |
| [#38 Rename folders](https://github.com/armydep/cloud-storage/issues/38) | Item 6.1 | Renaming a folder near the root rewrites every descendant row under lock |

---

# Tier 1 — degrades under ordinary usage

## Section 1 — Folder listing has no bounds

| # | Finding | Evidence | Roadmap |
| --- | --- | --- | --- |
| 1.1 | Child-folder query has no `LIMIT`/`OFFSET` | `app/files/repository.py:50` | Gap |
| 1.2 | File query has no `LIMIT`/`OFFSET` | `app/files/repository.py:61` | Gap |
| 1.3 | Entire folder is materialized into a single JSON response: every row becomes a Pydantic object in one payload | `app/files/service.py:58-91` | Gap |
| 1.4 | Frontend renders every row with no virtualization | `frontend/src/components/Common/DataTable.tsx` | Gap |

A folder holding tens of thousands of files produces a multi-megabyte response
and a matching allocation spike on every request.

The user-list endpoint already accepts `skip` and `limit`, so the files module
is inconsistent with the convention already established elsewhere in the
codebase.

**Design constraint before implementing:** contents are currently two separately
sorted lists concatenated — folders by name, then files by name
(`app/files/service.py:68-87`). Stable pagination requires choosing a single
ordering across both types first.

The roadmap entry *"Sorting, filtering, and search"* is adjacent but does not
cover pagination.

## Section 2 — Database connections and concurrency

| # | Finding | Evidence | Roadmap |
| --- | --- | --- | --- |
| 2.1 | `create_engine` passes explicit pool arguments from settings instead of SQLAlchemy defaults | `app/core/db.py` | Resolved by #94 |
| 2.2 | Worker count and pool size are configurable; default worst-case is 20 connections per container instead of 60 | `backend/Dockerfile`, `app/core/config.py` | Resolved by #94 |
| 2.3 | Route handlers are synchronous `def`, so FastAPI runs them in a 40-thread pool that contends for 15 connections | one `async def` in all of `app/api/routes/` | Gap |
| 2.4 | No connection proxy (for example PgBouncer in transaction mode) | — | Gap |

The practical effect of 2.1 and 2.2 together: the second API container roughly
saturates PostgreSQL and the third begins failing to acquire connections — well
before CPU becomes the limiting factor. Horizontal scaling is capped by
connection math, not by compute.

Update 2026-08-10: #94 sets explicit defaults:
`BACKEND_WORKERS=4`, `DB_POOL_SIZE=3`, and `DB_MAX_OVERFLOW=2`. Worst-case
connection usage is now
`replicas * BACKEND_WORKERS * (DB_POOL_SIZE + DB_MAX_OVERFLOW)`, or 20
connections per backend container with the defaults. Keep that total below
PostgreSQL `max_connections` with headroom for migrations, prestart, admin
sessions, monitoring, and reserved superuser connections.

## Section 3 — Storage client overhead

| # | Finding | Evidence | Roadmap |
| --- | --- | --- | --- |
| 3.1 | A boto3 S3 client is cached and reused per backend worker process | `app/core/storage.py` | Resolved by #94 |
| 3.2 | `stat_object` performs a network round trip to object storage on every upload completion, serialized with the database work | `app/files/service.py:140` | Resolved by #92 |
| 3.3 | Botocore connect/read timeouts and retry attempts are explicit settings | `app/core/storage.py`, `app/core/config.py` | Resolved by #94 |

`get_s3_client()` is called from every presign and every stat, so 3.1 sits on the
hot path of every upload and download.

Presigned URL *generation* is local HMAC work and requires no network call, so
that part is already efficient; 3.2 concerns the separate existence check.

Update 2026-08-09: #91 removes the larger upload-completion asymmetry that was
found after this review. `complete_upload` no longer streams the object back
through the API to recompute SHA-256; object storage enforces the checksum on
PUT and completion reads checksum metadata with a constant-time HEAD request.

Update 2026-08-10: #92 narrows the remaining upload-completion lock scope.
`complete_upload` now performs S3 metadata verification and canonical object
copy before taking the `file_blobs` row lock, then re-reads the blob under
`FOR UPDATE` only for the claim/ref-count/file mutation block.

Update 2026-08-10: #94 caches the boto3 S3 client per worker process and sets
explicit botocore `connect_timeout`, `read_timeout`, and retry attempts.

---

# Tier 2 — surfaces as data volume grows

## Section 4 — Data model gaps

| # | Finding | Evidence | Roadmap |
| --- | --- | --- | --- |
| 4.1 | No `created_at` on `files` or `folders` | `app/files/models.py` | Tracked — *"Add creation timestamps to files"* |
| 4.2 | No `updated_at`, which blocks incremental synchronization | `app/files/models.py` | Partial — implied by *"Synchronize files between the Android client and cloud storage"* |
| 4.3 | Without a timestamp column only offset pagination is possible, and offset pagination degrades deep into large tables | — | Gap |

The `user` and `item` tables already carry timestamps via `get_datetime_utc`
(`app/models.py`), so the file tables are the exception.

**Schedule 4.1 together with Section 1** — keyset pagination depends on it, and
adding a timestamp column to a large table later is a substantially more
expensive migration.

## Section 5 — Object lifecycle and orphans

| # | Finding | Evidence | Roadmap |
| --- | --- | --- | --- |
| 5.1 | Duplicate filenames are rejected at `complete_upload` but not at `presign_upload`, so a large file can be fully uploaded and only then refused | `app/files/service.py:130-136` vs `94-116` | Gap |
| 5.2 | Objects from rejected or abandoned uploads have no metadata row and nothing removes them | — | Tracked — *"asynchronous cleanup process for S3 objects that have no metadata reference"* |
| 5.3 | The reverse case: metadata rows whose object is missing | — | Tracked — *"asynchronous cleanup process for metadata records whose S3 objects are missing"* |

5.1 is the cheapest fix in this document and directly reduces the orphan volume
that 5.2 has to clean up.

## Section 6 — Tree operations

| # | Finding | Evidence | Roadmap |
| --- | --- | --- | --- |
| 6.1 | Folder rename or move must rewrite `path` on every descendant, plus each descendant's entry in `uq_folders_owner_path` — a write burst proportional to subtree size | ltree materialized path, `app/files/models.py` | Partial — [#38 Rename folders](https://github.com/armydep/cloud-storage/issues/38) will encounter this |
| 6.2 | The GiST index accelerates subtree reads; there is no corresponding strategy for the write side | `b4c7d8e9f012` | Gap |

Materialized paths trade write cost for read speed. The read side is indexed;
the write side has not been designed yet, and `#38` is the feature that will
exercise it.

## Section 7 — Large files and client-side transfer

| # | Finding | Evidence | Roadmap |
| --- | --- | --- | --- |
| 7.1 | `await file.arrayBuffer()` loads the entire file into browser memory before hashing | `frontend/src/features/files/fileHash.ts:2` | Resolved by #90 |
| 7.2 | Hashing is fully serial: it must complete before the upload begins | `frontend/src/features/files/fileTransfer.ts:26` and `:34` | Gap |
| 7.3 | A single `PUT` means no resumability, no parallel parts, and a hard single-request size ceiling | `frontend/src/features/files/fileTransfer.ts:34` | Tracked — *"Support resumable uploads"*, *"Support resumable downloads"* |
| 7.4 | No server-side maximum file size; the schema only requires `size_bytes > 0` | `app/files/schemas.py:30` | Tracked — *"Enforce a maximum file size"* |

7.1 was resolved by chunked browser hashing in #90. 7.2 remains: hashing still
completes before upload begins, and that is not covered by the resumable-upload
entries.

---

# Section 8 — Correctness and security

Found while reading for scalability. Not performance problems, but they
constrain the order in which roadmap items can safely ship.

| # | Finding | Evidence | Roadmap |
| --- | --- | --- | --- |
| 8.1 | `complete_upload` never verifies that the requesting user uploaded the object. Because keys are derived purely from content hash, knowing a file's SHA-256 is sufficient to register it and then download it | `app/files/service.py:138-159` | Gap |
| 8.2 | Content-addressed keys with no reference counting; there is no `blobs` table | `app/core/storage.py:22` | Gap |
| 8.3 | No ownership or claim record linking a user to a blob | — | Gap |

On 8.1 concretely: the upload flow is presign, client `PUT`, then
`complete_upload`, which calls `stat_object` and writes a metadata row if the
object exists. Nothing ties that object to the caller. A user who knows another
user's file hash can skip the `PUT` entirely, submit a matching hash, size and
MIME type, receive a metadata row, and then request a presigned download of
content they never possessed.

Update 2026-08-09: Phase 6 and Phase 7 added `file_blobs.ref_count` and
per-user blob claims before file and folder delete shipped. The historical risk
described below is retained as context for why those pieces exist.

On 8.2 at the time of this review: nothing broke because no delete endpoint
existed. Once [#40](https://github.com/armydep/cloud-storage/issues/40)
and [#41](https://github.com/armydep/cloud-storage/issues/41) shipped,
deleting one user's file would have removed bytes that other users' metadata
still pointed to.

All three share one remedy: a `blobs` table keyed by hash, holding size and a
reference count or explicit per-user claims, with `complete_upload` linking a
user only to a blob that user demonstrably uploaded.

---

# Section 9 — Missing at scale

| # | Finding | Evidence | Roadmap |
| --- | --- | --- | --- |
| 9.1 | No rate limiting; presign endpoints issue object-storage write credentials on demand | — | Gap |
| 9.2 | No storage quota enforcement | — | Tracked — *"Set per-user storage quotas"* |
| 9.3 | One additional database query on every authenticated request (`session.get(User, ...)`) | `app/api/deps.py` | Gap |
| 9.4 | No metrics or tracing; Sentry covers errors only, with no Prometheus or OpenTelemetry | — | Resolved by #93 for metrics; tracing remains future work |
| 9.5 | A single PostgreSQL instance serves both browse reads and upload writes; no read replica | `compose.yml` | Partial — *"Split the application into independently deployable services"* |
| 9.6 | No resource limits or replica counts defined for services | `compose.yml` | Gap |

9.4 is a force multiplier on everything above: without instrumentation, each of
these limits is diagnosed only after it has already caused an outage.

Update 2026-08-10: #93 adds Prometheus metrics for HTTP request rate/latency,
database pool utilisation and checkout wait, and object-storage operation
duration. Check `db_pool_checked_out_connections`,
`db_pool_overflow_connections`, and `db_pool_checkout_wait_seconds` before
acting on SCALE 2.1 / 2.2 connection-pool limits.

---

# Roadmap cross-reference

## ROADMAP.md items that already cover a finding

| ROADMAP.md item | Phase | Covers |
| --- | --- | --- |
| Add creation timestamps to files | File experience | 4.1 |
| Enforce a maximum file size | File experience | 7.4 |
| Support resumable uploads | File experience | 7.3 |
| Support resumable downloads | File experience | 7.3 |
| Set per-user storage quotas | User experience and notifications | 9.2 |
| Asynchronous cleanup for S3 objects with no metadata reference | Storage and reliability | 5.2 |
| Asynchronous cleanup for metadata records whose objects are missing | Storage and reliability | 5.3 |

## ROADMAP.md items that partially relate

| ROADMAP.md item | Phase | Relates to | Note |
| --- | --- | --- | --- |
| Synchronize files between the Android client and cloud storage | Mobile and synchronization | 4.2 | Requires `updated_at`, which does not exist yet |
| Split into independently deployable services | Architecture and scale | 9.5 | Addresses topology, not the single-database read/write contention |
| Sorting, filtering, and search | File experience | Section 1 | Adjacent to pagination but does not replace it |

## ROADMAP.md items that this review flags as blocked

| ROADMAP.md item | Blocked by | Reason |
| --- | --- | --- |
| [#38 Rename folders](https://github.com/armydep/cloud-storage/issues/38) | 6.1 | Subtree path rewrite is unbounded |

Resolved 2026-08-09:

- [#40 Delete files](https://github.com/armydep/cloud-storage/issues/40)
  was unblocked by Phase 6.
- [#41 Delete folders](https://github.com/armydep/cloud-storage/issues/41)
  was unblocked by Phase 7.

## Findings with no roadmap representation

Sections 1 (pagination), 2 (connection pooling and concurrency), 3 (storage
client overhead), 8 (blob ownership and reference counting), and items 4.3, 5.1,
6.2, 7.1, 7.2, 9.1, 9.3, 9.4, 9.6 — **22 items in total** — are not currently
represented in ROADMAP.md.

Sections 2, 3 and item 5.1 are each small and self-contained. Section 8 is the
one group that should be scheduled ahead of work already in Current focus.

---

# Suggested sequencing

1. **Section 1 plus 4.1** — pagination and timestamps belong in the same change.
2. **Section 2 and item 3.1** — small, high leverage, removes the horizontal scaling cap.
3. **Item 6.1** — before `#38 Rename folders`.
4. **Item 5.1** — cheap, and reduces the orphan volume 5.2 must handle.
5. **Item 9.4** — early enough that the remaining items can be measured rather than guessed at.
6. Everything else as the existing roadmap phases reach it.
