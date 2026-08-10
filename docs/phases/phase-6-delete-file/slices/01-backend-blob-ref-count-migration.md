# Slice 1: Backend blob ref-count schema migration

## Outcome

The backend has an explicit `file_blobs` table representing physical S3/MinIO
objects and a reliable reference count for existing and future logical files.
Existing upload and download behavior continues to work.

## Storage model

Physical blob:

```text
file_blobs
- blob_hash   primary key, SHA-256 hex
- object_key  unique, e.g. sha256/{blob_hash}
- size_bytes
- ref_count
- created_at
```

Logical file:

```text
files
- id
- owner_id
- folder_id
- name
- blob_hash -> file_blobs.blob_hash
- mime_type
- category
- size_bytes
- created_at
```

The S3 object key remains content-addressed:

```text
sha256/{blob_hash}
```

## Migration plan

1. Create `file_blobs`.
2. Backfill from existing `files` rows:
   - one row per distinct `files.blob_hash`;
   - `object_key = 'sha256/' || blob_hash`;
   - `size_bytes` from existing file rows;
   - `ref_count = count(files.id)`.
3. Add indexes/constraints:
   - primary key on `file_blobs.blob_hash`;
   - unique constraint/index on `file_blobs.object_key`;
   - check `ref_count >= 0`;
   - index on `file_blobs.object_key` if not covered by unique constraint.
4. Add a foreign key from `files.blob_hash` to `file_blobs.blob_hash`.
5. Keep the existing `ix_files_blob_hash` index for folder listing and joins.

If existing rows with the same `blob_hash` have different `size_bytes`, the
migration should fail instead of choosing an arbitrary size. That would indicate
corrupt metadata because equal SHA-256 hashes should describe identical bytes in
normal operation.

## Code changes

- Add `StoredBlob`/`FileBlob` model in `backend/app/files/models.py`.
- Add repository helpers:
  - `get_blob_by_hash(...)`;
  - `get_blob_for_update(...)`;
  - `create_blob(...)`;
  - `increment_blob_ref_count(...)`;
  - `decrement_blob_ref_count(...)`.
- Update upload completion so creating a file also creates or increments the
  referenced blob inside the same database transaction.
- Keep object keys content-addressed with
  `storage.get_object_key(request.blob_hash)`.
- Change presign upload response to represent both paths:
  - missing blob: return a presigned PUT URL and `upload_required=true`;
  - existing blob: return no PUT URL and `upload_required=false`.
- Do not issue a presigned PUT URL for an existing blob hash. This prevents an
  authenticated user from overwriting a shared content-addressed object.
- Keep presign download using the blob/object key for the file's hash.
- Add tests for migration-backed model/repository behavior.

Suggested response shape:

```json
{
  "upload_required": true,
  "upload_url": "http://localhost:9000/cloud-storage/sha256/...",
  "method": "PUT",
  "headers": {
    "Content-Type": "application/pdf"
  },
  "object_key": "sha256/...",
  "expires_in": 900
}
```

For an existing blob:

```json
{
  "upload_required": false,
  "upload_url": null,
  "method": null,
  "headers": {},
  "object_key": "sha256/...",
  "expires_in": 0
}
```

## Acceptance criteria

- [ ] Alembic migration creates `file_blobs`.
- [ ] Migration backfills one blob row per existing distinct `files.blob_hash`.
- [ ] Backfilled `ref_count` equals the number of file rows for each hash.
- [ ] `file_blobs.object_key` is unique.
- [ ] `files.blob_hash` references `file_blobs.blob_hash`.
- [ ] Existing file downloads still use `sha256/{blob_hash}` and continue to
      work after migration.
- [ ] Completing an upload for a new hash creates a blob row with `ref_count=1`.
- [ ] Completing an upload for an existing hash increments the existing blob's
      `ref_count`.
- [ ] Completing duplicate logical files with the same `blob_hash` does not
      create duplicate blob rows.
- [ ] Presign upload for a missing blob returns `upload_required=true` and a
      presigned PUT URL.
- [ ] Presign upload for an existing blob returns `upload_required=false` and no
      presigned PUT URL.
- [ ] Existing blobs cannot be overwritten through presign upload.
- [ ] Backend tests cover new and existing blob completion paths.

## Suggested tests

- `test_complete_upload_creates_blob_for_new_hash`
- `test_complete_upload_increments_blob_ref_count_for_existing_hash`
- `test_complete_upload_same_hash_creates_one_blob_row`
- `test_presign_upload_missing_blob_requires_upload`
- `test_presign_upload_existing_blob_skips_upload`
- `test_presign_upload_existing_blob_does_not_issue_put_url`
- `test_presign_download_uses_blob_object_key`
- migration test/manual verification that backfilled counts match current files

## Verification

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend bash scripts/test.sh
```

For Docker Compose CI compatibility:

```bash
docker compose build
docker compose up -d --wait backend frontend adminer
curl http://localhost:8000/api/v1/utils/health-check
curl http://localhost:5173
```

## Out of scope

- Delete API.
- Frontend or mobile UI.
- Folder deletion.
- Unique per-file S3 object keys.
- Background S3 garbage collection.

## Open questions

None. This slice keeps content-addressed object keys and introduces explicit
blob reference counting.
