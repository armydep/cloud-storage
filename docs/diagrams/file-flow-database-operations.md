# Upload and Download — Database Operations, Step by Step

A textual breakdown of every database operation performed during file upload and download, in
execution order. For each step: which table, which operation, and on which columns.

Companion to [`file-upload-flow.md`](file-upload-flow.md) and
[`file-download-flow.md`](file-download-flow.md), which show the same flows as sequence diagrams.
This document is the table-level reference.

Verified against `backend/app/files/service.py` and `backend/app/files/repository.py`.

## Notation

- **`SELECT`** — read, no lock
- **`SELECT … FOR UPDATE`** — read that takes a row-level write lock held until the transaction ends
- **`INSERT` / `UPDATE` / `DELETE`** — writes
- **`COMMIT`** — transaction boundary; everything since the previous boundary becomes durable together
- **`—`** — the step touches no database at all

Steps marked *conditional* only run on some paths; the condition is stated.

## Tables involved

| Table | Purpose | Written during upload? | Written during download? |
| --- | --- | --- | --- |
| `user` | Authentication — read once per request to resolve the JWT subject | No | No |
| `folders` | Folder tree (ltree `path`), scoped by `owner_id` | Only to auto-create the root folder | No |
| `files` | File metadata rows a listing reads | Yes — one `INSERT` per upload | No |
| `file_blobs` | One row per distinct content hash; holds `ref_count` | Yes — `INSERT` and/or `UPDATE` | No |
| `file_blob_claims` | Records that a given user legitimately possesses a blob's content | Yes — `INSERT` (idempotent) | No |
| `pending_uploads` | Tracks an in-flight upload between presign and completion | Yes — `INSERT` then `DELETE` | No |
| `file_shares` | Grants a non-owner access to a file | No | Read only |

**Download performs no writes at all.** It is two `SELECT`s (auth + the file) plus local URL
signing.

## Step 0 — on every authenticated request

Every one of the requests below is preceded by the same lookup, performed by the `CurrentUser`
dependency in `app/api/deps.py` before the route body runs:

| Step | Table | Operation | Columns / predicate |
| --- | --- | --- | --- |
| Resolve the JWT subject to a user | `user` | `SELECT` by primary key | `WHERE id = :jwt_sub`, then checks `is_active` |

It is omitted from the per-request tables below to avoid repeating it four times, but it is a real
query on every call — one extra round trip per authenticated request, recorded as SCALE 9.3.

---

# UPLOAD

Upload is **two separate HTTP requests in two separate transactions**, with a direct browser→MinIO
transfer in between, then usually a third request to refresh the listing.

## Request 1 — `POST /api/v1/files/presign-upload`

Service: `create_presigned_upload` (`app/files/service.py`).

| # | Step | Table | Operation | Columns / predicate |
| --- | --- | --- | --- | --- |
| 1 | Resolve the target folder | `folders` | `SELECT` | `WHERE owner_id = :user AND path = :folder_path` |
| 2 | Look for existing content with this hash | `file_blobs` | `SELECT` by primary key | `WHERE blob_hash = :blob_hash` |
| 3 | Check whether *this user* already possesses that content | `file_blob_claims` | `SELECT` | `WHERE owner_id = :user AND blob_hash = :blob_hash` |
| 4 | Sign the presigned `PUT` URL | — | — | Local HMAC signing. **No network call to MinIO**, no database access |
| 5 | Record the in-flight upload | `pending_uploads` | `INSERT` | `id`, `owner_id`, `blob_hash`, `object_key`, `size_bytes`, `mime_type`, `expires_at` (`created_at` defaults to now) |
| 6 | Make it durable | — | **`COMMIT`** | Commits step 5 only |

**Step 1 fails** → `404 Folder not found`, nothing written.

**Branch after step 3.** If steps 2 and 3 *both* returned a row — the content already exists **and**
this user already has a claim on it — the request returns `upload_required=false` immediately.
**Steps 4–6 do not run: no `INSERT`, no `COMMIT`, and the browser skips the upload to MinIO
entirely.** This is the deduplication fast path.

`expires_at` is set to now + `S3_PRESIGNED_URL_EXPIRES_SECONDS` (default 900s). This is what step 4
of the next request filters on.

## Between the requests — direct transfer

| # | Step | Table | Operation | Notes |
| --- | --- | --- | --- | --- |
| — | Browser `PUT`s the bytes to MinIO with `x-amz-checksum-sha256` | — | — | **No backend involvement, no database access.** MinIO verifies the checksum server-side and rejects a mismatch |

## Request 2 — `POST /api/v1/files/complete-upload`

Service: `complete_upload` (`app/files/service.py`). **Everything from step 1 to the `COMMIT` at step
13 runs in one transaction.**

| # | Step | Table | Operation | Columns / predicate |
| --- | --- | --- | --- | --- |
| 1 | Re-resolve the target folder | `folders` | `SELECT` | `WHERE owner_id = :user AND path = :folder_path` |
| 2 | Reject a duplicate filename | `files` | `SELECT` | `WHERE folder_id = :folder AND name = :name` |
| 3 | Look up the blob (still unlocked) | `file_blobs` | `SELECT` by primary key | `WHERE blob_hash = :blob_hash` |
| 4 | Look up this user's claim | `file_blob_claims` | `SELECT` | `WHERE owner_id = :user AND blob_hash = :blob_hash` |
| 5 | *Conditional* — find the in-flight upload | `pending_uploads` | `SELECT` | `WHERE owner_id = :user AND blob_hash = :blob_hash AND expires_at > now()` `ORDER BY created_at DESC` `LIMIT 1` |
| 6 | *Conditional* — verify the uploaded object | — | — | `HEAD` to MinIO with `ChecksumMode=ENABLED`; compares size, content type and SHA-256. No database access |
| 7 | *Conditional* — promote the object to its canonical key | — | — | `COPY` in MinIO from `uploads/…` to `sha256/{hash}`. No database access |
| 8 | *Conditional* — create the blob row | `file_blobs` | `INSERT` | `blob_hash`, `object_key`, `size_bytes`, `ref_count = 0` |
| 9 | Take the write lock | `file_blobs` | **`SELECT … FOR UPDATE`** | `WHERE blob_hash = :blob_hash` |
| 10 | Claim the blob for this user | `file_blob_claims` | `SELECT`, then `INSERT` if absent | `owner_id`, `blob_hash` |
| 11 | Count the new reference | `file_blobs` | `UPDATE` | `SET ref_count = ref_count + 1` |
| 12 | Create the file metadata row | `files` | `INSERT` | `id`, `owner_id`, `folder_id`, `name`, `mime_type`, `category`, `blob_hash`, `size_bytes`, `created_at` |
| 13 | *Conditional* — consume the in-flight record | `pending_uploads` | `DELETE` | `WHERE id = :pending_upload_id` |
| 14 | Make it all durable | — | **`COMMIT`** | Commits steps 8, 10, 11, 12 and 13 **together** |
| 15 | *Conditional* — remove the staging object | — | — | `DELETE` in MinIO of the `uploads/…` object. **After the commit, best-effort** — a failure is logged and swallowed, leaving an orphaned object (see #100) |

### Which conditional steps run

**Steps 5–8 depend on what steps 3 and 4 found:**

- **Blob exists AND this user has a claim** → steps 5–8 are all skipped. The claim alone is proof
  the user possesses the content, so there is no `pending_uploads` lookup and no MinIO verification.
- **Blob exists but this user has no claim** → steps 5 and 6 run (the user must prove they uploaded
  it); steps 7 and 8 are skipped because the blob row already exists.
- **Blob does not exist** → steps 5, 6, 7 and 8 all run. This is a genuinely new piece of content.

If step 5 finds no unexpired row, the request fails with `400` and nothing is written. An expired
`pending_uploads` row is invisible to this query and is never cleaned up — the row and its object
are stranded (#100).

**Steps 13 and 15** run only if step 5 actually found a `pending_uploads` row.

### Two details worth knowing

**The lock at step 9 is deliberately late.** Steps 6 and 7 are network round trips to MinIO. Taking
the `file_blobs` lock before them would hold a row lock across that latency for every concurrent
uploader of the same content. Delaying it to step 9 keeps the lock window to steps 9–14, which are
all local database work. This was the change in ROADMAP 2.7 / #92.

**Step 11 is not an atomic SQL increment.** `ref_count` is incremented on the ORM object in Python,
so the emitted statement sets an absolute value rather than `ref_count = ref_count + 1` computed by
Postgres. It is still correct — but only because step 9 holds a `FOR UPDATE` lock on that row for
the whole read-modify-write. Remove or weaken the lock and concurrent uploads of the same content
will lose increments.

## Request 3 — `GET /api/v1/files` (refresh the listing)

Service: `get_folder_contents` (`app/files/service.py`). Not part of upload proper, but it is what
makes the new file appear.

| # | Step | Table | Operation | Columns / predicate |
| --- | --- | --- | --- | --- |
| 1 | Resolve the folder | `folders` | `SELECT` | `WHERE owner_id = :user AND path = :path` |
| 2 | *Conditional* — auto-create the root folder | `folders` | `INSERT` + `COMMIT` | Only when the path is the root and no row exists (first-ever request for a new user) |
| 3 | List subfolders | `folders` | `SELECT` | `WHERE owner_id = :user AND parent_id = :folder` `ORDER BY name` |
| 4 | List files | `files` `JOIN` `user` | `SELECT` | `WHERE files.owner_id = :user AND files.folder_id = :folder` `ORDER BY files.name` — joins `user` to expose `owner_email` |

Neither list is paginated (SCALE 1.1 / 1.2).

---

# DOWNLOAD

One HTTP request, then a direct browser→MinIO transfer. **No table is written at any point.**

## Request — `POST /api/v1/files/{file_id}/presign-download`

Service: `create_presigned_download` (`app/files/service.py`).

| # | Step | Table | Operation | Columns / predicate |
| --- | --- | --- | --- | --- |
| 1 | Authorize and load the file | `files` `LEFT JOIN` `file_shares` | `SELECT` | `WHERE files.id = :file_id AND (files.owner_id = :user OR file_shares.recipient_id = :user)` |
| 2 | Derive the object key | — | — | `sha256/{files.blob_hash}` — string construction only |
| 3 | Sign the presigned `GET` URL | — | — | Local HMAC signing. **No network call to MinIO**, no database access |

That is the entire database interaction: **one `SELECT`, no writes, no `COMMIT`.**

**Step 1 returns no row** → `404 File not found`. This covers three distinct cases — the file does
not exist, the caller is neither owner nor share recipient, or the id is not a file at all — and all
three return `404`, never `403`, so the API never reveals that a file exists to someone without
access.

The `LEFT JOIN` means both access paths are answered by one query: the caller matches either on
`files.owner_id` (they own it) or on `file_shares.recipient_id` (it was shared with them). Owner and
recipient get byte-identical responses.

## After the request — direct transfer

| # | Step | Table | Operation | Notes |
| --- | --- | --- | --- | --- |
| — | Browser `GET`s the presigned URL from MinIO | — | — | **No backend involvement, no database access.** File bytes never pass through the API |

---

# Summary

## Writes per request

| Request | `user` | `folders` | `files` | `file_blobs` | `file_blob_claims` | `pending_uploads` | `file_shares` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `presign-upload` | — | — | — | — | — | `INSERT` | — |
| `complete-upload` | — | — | `INSERT` | `INSERT` and/or `UPDATE` | `INSERT` | `DELETE` | — |
| `GET /files` | — | `INSERT` (root only) | — | — | — | — | — |
| `presign-download` | — | — | — | — | — | — | — |

`user` is read on every request (step 0) but never written by any of these flows.

## Transaction boundaries

Four separate transactions are involved in a single upload:

1. `presign-upload` — commits the `pending_uploads` row on its own. If the user abandons the upload
   here, that row and its MinIO object persist indefinitely.
2. `complete-upload` — commits `file_blobs`, `file_blob_claims`, `files` and the `pending_uploads`
   delete **as one unit**. Either the file is fully registered or none of it is.
3. `GET /files` — read-only, unless it creates a root folder.
4. The MinIO staging-object delete happens **outside all of them**, after the commit, best-effort.

Download runs a single read-only transaction.

## Where each guarantee comes from

| Guarantee | Enforced by |
| --- | --- |
| No two files with the same name in a folder | `uq_files_folder_name`, checked at step 2 and enforced at `INSERT` |
| One `file_blobs` row per distinct content | `blob_hash` primary key; a concurrent duplicate `INSERT` is caught and ignored |
| A user cannot register content they never uploaded | `file_blob_claims` + the `pending_uploads` proof path (SCALE 8.1) |
| `ref_count` stays accurate under concurrency | The `SELECT … FOR UPDATE` at step 9 |
| `ref_count` never goes negative | `ck_file_blobs_ref_count_non_negative` |
| Cross-user access returns 404, not 403 | Every query filters on `owner_id`; download's join adds `file_shares.recipient_id` |
