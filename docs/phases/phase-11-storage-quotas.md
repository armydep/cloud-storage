# Phase 11: Storage quotas

## Goal

Give every user a storage allowance, enforce it on upload, and notify them as
they approach it.

Completes ROADMAP 4.2 (per-user storage quotas) and ROADMAP 4.3 (notify users
when they reach or approach their quota). Adjacent to ROADMAP 7.3 (storage usage
reporting), which the usage endpoint added here largely serves.

## Product and technical decisions

1. **Usage is logical, not physical.** A user's usage is
   `SUM(files.size_bytes)` over the files they own. Because object keys are
   content-addressed, one stored object can back several `files` rows — three
   copies of a 1 GB file count as 3 GB against the owner even though only 1 GB
   is stored.

   This matches what users expect and what comparable products do; the
   deduplication saving is the operator's margin, not the user's. It also avoids
   the question physical accounting cannot answer cleanly: when two users hold
   the same blob, whose gigabyte is it?

   Accepted consequence: a user can reach their quota with files that cost
   nothing extra to store.

2. **Files shared *with* a user do not count against that user.** They are owned
   by someone else, who is already paying for them. Consequence: a user can read
   an unbounded amount of storage through shares while holding almost none.

3. **The default quota is 100 MB, configured in `.env`.** A nullable
   `user.quota_bytes` overrides it per user, which is what ROADMAP 4.2 asks for.
   `NULL` means "use the default", so changing the default moves every
   unconfigured user at once.

4. **Exceeding the quota is a hard block on upload, and nothing else.**
   Downloads, deletes, shares and browsing keep working. Nothing is ever deleted
   automatically. Lowering a quota below a user's current usage leaves their
   files intact and simply blocks new uploads until they are under it again.

5. **Enforcement happens at both `presign_upload` and `complete_upload`, and
   only the second one is authoritative.** The size supplied at presign is
   client-controlled and untrusted; the size at completion is verified against
   object storage. Presigned `PUT` carries no size cap, so a client can reserve
   30 MB and upload 80 MB.

   The presign check exists for fast feedback and to avoid wasted transfer. The
   completion check is the actual gate. Presigned `POST` with a
   `content-length-range` policy could cap the transfer itself, but that changes
   the client flow and is out of scope.

6. **Rejecting at completion must delete the pending object.** The bytes are
   already in object storage under `uploads/<owner_id>/<upload_id>`. Leaving them
   creates exactly the orphan class the cleanup work exists to remove.

7. **Concurrency is resolved with a row lock on `user`, taken late and held
   briefly.** Two devices uploading at once is a plain read-then-write race:
   both read the same usage, both see room, both commit. The check and the
   reservation must happen inside one transaction holding
   `SELECT ... FROM user WHERE id = :id FOR UPDATE`.

   This mirrors `get_blob_for_update` (`app/files/repository.py:271`), already
   the house idiom. The lesson from the blob lock-ordering work applies: the
   object-storage `HEAD` in `complete_upload` happens *before* the lock is taken,
   never inside it. The critical section is an aggregate and an insert.

8. **In-flight uploads are reserved through `pending_uploads`.** Usage counts
   committed files plus unexpired pending uploads, so a reservation exists from
   presign until completion or expiry. `pending_uploads.size_bytes` already
   exists for this.

9. **The usage query filters reservations on `expires_at > now()`.** An expired
   pending upload stops counting immediately, whether or not anything has reaped
   the row yet. This makes quota self-healing and downgrades the reaper from a
   correctness dependency to a cleanliness one — without it, an abandoned upload
   would consume allowance permanently.

10. **Usage is computed on demand, not maintained as a counter.** A `SUM` over
    `files` for one owner uses `ix_files_owner_id` and is correct by
    construction. A maintained counter on `user` would be O(1) to read but adds
    an invariant to keep accurate across single deletes, folder deletes and
    backfills. Revisit when measurement says to — the metrics work makes that
    observable.

11. **Quota threshold notification is edge-triggered from the upload path.**
    Phase 8 left open who detects a condition that nothing emits. Quota answers
    it cleanly: usage only ever grows on upload, so the upload that crosses the
    threshold emits the event. No scheduled scan is needed.

12. **Crossing back down resets the notification, which requires state.**
    `user.quota_notified_threshold` records the highest threshold already
    notified. Crossing upward past an un-notified threshold emits and records it;
    dropping below clears it, so a later re-crossing notifies again. Without this
    column, deleting and re-uploading would either spam or go silent forever.

13. **The notification threshold is configurable in `.env`, defaulting to 80%.**

## Enforcement points

```
  presign_upload                 client PUT                complete_upload
  ──────────────                 ──────────                ───────────────
  size: CLIENT-SUPPLIED          bytes land in             size: VERIFIED
  untrusted                      object storage            via HEAD
                                 regardless
  reserve + reject early         no enforcement            THE ACTUAL GATE
  (avoids wasted transfer)       possible with             reject → delete
                                 presigned PUT             pending object
```

Both checks run under the user row lock. Only the second one can be trusted.

## Data model

```sql
user
  quota_bytes                bigint  NULL   -- NULL = use the configured default
  quota_notified_threshold   int     NULL   -- highest percent already notified

-- settings, from .env
QUOTA_DEFAULT_BYTES              = 104857600   -- 100 MB
QUOTA_NOTIFY_THRESHOLD_PERCENT   = 80
```

Usage for one user:

```sql
  SELECT COALESCE(SUM(size_bytes), 0) FROM files
   WHERE owner_id = :user_id
+ SELECT COALESCE(SUM(size_bytes), 0) FROM pending_uploads
   WHERE owner_id = :user_id AND expires_at > now()
```

Both aggregates are index-backed: `ix_files_owner_id` and the `owner_id` prefix
of `ix_pending_uploads_owner_blob`.

Per repository convention, any new index or constraint is mirrored in the model's
`__table_args__` so autogenerate reports no drift.

## Concurrency

```
  quota 100 MB, using 60 MB

  Device A                        Device B
     │ presign 30 MB                 │ presign 30 MB
     ├─ BEGIN                        │
     ├─ SELECT user FOR UPDATE ◄─────┼── B blocks here
     ├─ usage = 60, 60+30 = 90 ✓     │
     ├─ INSERT pending_upload        │
     └─ COMMIT ──────────────────────┼─► B proceeds
                                     ├─ usage = 90 (includes A's reservation)
                                     ├─ 90+30 = 120 > 100 ✗ rejected
                                     └─ COMMIT
```

The same lock guards `complete_upload`, where the verified size is checked
against the quota one final time.

## Slice breakdown

### Slice 1 — backend: quota configuration, usage, and enforcement

`quota_bytes` and `quota_notified_threshold` columns; settings; the usage query;
enforcement at `presign_upload` and `complete_upload` under the user row lock;
pending-object deletion on rejection; a usage endpoint.

**Depends on the pending-upload reaper.** Decision 9 keeps quota correct without
it, but abandoned uploads would otherwise leave rows accumulating forever.

### Slice 2 — quota threshold notifications

`quota_threshold_reached` emitted from the upload path when the configured
threshold is crossed; `quota_notified_threshold` maintained for reset semantics;
bound to `q.email` and `q.inapp` through the existing exchange.

Completes ROADMAP 4.3.

### Slice 3 — web: usage display

Usage against quota in the React SPA, and a clear message when an upload is
rejected for quota.

### Slice 4 — mobile: usage display

The same in the Flutter client.

### Slice 5 — admin: set a per-user quota

Superuser-only endpoint and UI to set `quota_bytes` for a user.

## Acceptance flow

1. A new user's quota is the configured default; usage is zero.
2. Uploading brings usage up; the files view shows used against total.
3. An upload that would exceed the quota is rejected at presign, before any bytes
   move.
4. A client that under-reports its size at presign is rejected at completion, and
   the uploaded object is deleted.
5. Two devices uploading concurrently cannot jointly exceed the quota; the second
   is rejected.
6. Abandoning an upload frees the reservation once it expires, with or without
   the reaper having run.
7. Crossing 80% emits a notification once; deleting files and crossing again
   emits it again.
8. Deleting files frees allowance immediately.
9. A superuser can raise one user's quota without affecting anyone else.

## Out of scope

- Physical or deduplicated accounting. Decision 1.
- Soft limits, grace margins, or overage allowances. Decision 4 is a hard block.
- Billing, plans, or paid tiers.
- Quotas on anything other than storage bytes — no file-count or bandwidth caps.
- Automatic deletion or archival of anything when a quota is exceeded.
- Presigned `POST` with `content-length-range`. Decision 5.
- Per-folder or per-share quotas.

## Open questions

None open. The questions raised while drafting — logical versus physical usage,
whether shared files count, the default and its location, hard block versus
grace, the notification threshold and its reset semantics, and whether the
reaper is a prerequisite — are settled as decisions 1 to 13.
