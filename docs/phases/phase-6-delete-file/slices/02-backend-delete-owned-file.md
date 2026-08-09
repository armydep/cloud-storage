# Slice 2: Backend delete owned file with blob ref-count decrement

## Outcome

An authenticated file owner can permanently delete one owned logical file
through the backend API. The referenced blob's `ref_count` is decremented, and
the physical S3/MinIO object is deleted only when the deleted file was the final
reference.

## Dependencies

- Slice 1: Backend blob ref-count schema migration, completed in PR
  [#66](https://github.com/armydep/cloude-file-storage/pull/66).

## API contract

```text
DELETE /api/v1/files/{file_id}
```

Responses:

```text
204 No Content
401 Unauthorized
404 File not found
422 Validation error for malformed UUID
```

Authorization behavior:

- Owner of the file receives `204`.
- Another user receives `404`.
- A user who only has the file through `file_shares` receives `404`.
- An unauthenticated caller receives `401`.
- Repeating delete after success receives `404`.

## Implementation notes

Target files:

```text
backend/app/core/storage.py
backend/app/api/routes/files.py
backend/app/files/repository.py
backend/app/files/service.py
backend/tests/core/test_storage.py
backend/tests/api/routes/test_files.py
backend/tests/files/test_repository.py
```

- Add `storage.delete_object(object_key=...)`.
- Add route before more-specific subroutes only if route matching requires it;
  confirm it does not conflict with:
  - `POST /api/v1/files/{file_id}/presign-download`
  - `POST /api/v1/files/{file_id}/shares`
  - `GET /api/v1/files/{file_id}/shares`
  - `DELETE /api/v1/files/{file_id}/shares/{share_id}`
- Add repository function to fetch an owned file by `owner_id` and `file_id`, or
  reuse the existing `get_file_by_id`.
- Add repository function to delete a `StoredFile` without committing
  independently, so file deletion and blob ref-count changes share one
  transaction.
- Add repository function to delete a `FileBlob` without committing
  independently.
- Lock the referenced blob row for update before changing `ref_count`. This
  prevents concurrent deletes for the same blob from both making decisions from
  stale counts.
- Delete the logical file row and decrement blob `ref_count` in the same DB
  transaction.
- Treat `file_blobs.ref_count` as the source of truth for physical-object
  lifecycle. Do not count rows in `files` during delete.
- Raise `StoredFileNotFoundError` when the file does not exist or is not owned
  by the current user.
- Rely on existing database cascade to remove `file_shares` for the deleted
  file.
- If post-commit S3 deletion fails, log it and leave orphan cleanup to a future
  maintenance task. Do not recreate the logical file row.

## Backend delete algorithm

```python
def delete_file(session, owner_id, file_id) -> None:
    file = repository.get_file_by_id(
        session=session,
        owner_id=owner_id,
        file_id=file_id,
    )
    if file is None:
        raise StoredFileNotFoundError

    blob = repository.get_blob_for_update(
        session=session,
        blob_hash=file.blob_hash,
    )
    if blob is None:
        # Database invariant violation. Let this fail loudly; this should not
        # happen after Slice 1 migration.
        raise RuntimeError("File blob metadata is missing")

    object_key = blob.object_key
    repository.delete_file(session=session, file=file)
    repository.decrement_blob_ref_count(blob=blob)

    should_delete_object = blob.ref_count == 0
    if should_delete_object:
        repository.delete_blob(session=session, blob=blob)

    session.commit()

    if should_delete_object:
        try:
            storage.delete_object(object_key=object_key)
        except Exception:
            logger.exception("Failed to delete unreferenced file blob object")
```

Ordering is deliberate:

1. The DB transaction commits the logical delete and ref-count update first.
2. S3 deletion runs after commit only for the final blob reference.
3. S3 deletion failure is logged but does not restore the file row.

## Route behavior

Add:

```python
@router.delete("/{file_id}", status_code=204)
def delete_owned_file(
    session: SessionDep,
    current_user: CurrentUser,
    file_id: uuid.UUID,
) -> None:
    ...
```

Error mapping:

```text
StoredFileNotFoundError -> 404 File not found
```

No response body on success.

## Acceptance criteria

- [ ] `DELETE /api/v1/files/{file_id}` returns `204` for the owner.
- [ ] Deleted file is removed from the `files` table.
- [ ] Deleted file no longer appears in `GET /api/v1/files?path=<folder>`.
- [ ] Deleted file can no longer receive a presigned download URL.
- [ ] Shares for the deleted file are removed by cascade.
- [ ] A prior recipient no longer sees the deleted file in
      `GET /api/v1/files/shared-with-me`.
- [ ] Deleting another user's file returns `404 File not found`.
- [ ] Deleting a shared-with-me file as recipient returns `404 File not found`.
- [ ] Repeating the same delete returns `404 File not found`.
- [ ] Unauthenticated delete returns `401`.
- [ ] Malformed UUID returns `422`.
- [ ] Deleting one of multiple files with the same `blob_hash` decrements
      `ref_count` and does not delete the S3 object.
- [ ] Deleting the final file for a `blob_hash` removes the blob row and calls
      S3 delete for `sha256/{blob_hash}`.
- [ ] S3 delete failure after DB commit is logged and does not recreate the file
      row or blob row.
- [ ] Concurrent delete behavior for the same blob is safe through blob row
      locking.
- [ ] Ref-count decrement and logical file deletion are covered by backend
      tests.

## Suggested tests

- `test_delete_file_succeeds_for_owner`
- `test_delete_file_removes_file_from_folder_listing`
- `test_delete_file_removes_shares`
- `test_delete_file_prevents_later_download`
- `test_delete_file_rejects_another_users_file`
- `test_delete_file_rejects_shared_recipient`
- `test_delete_file_repeated_delete_returns_404`
- `test_delete_file_requires_authentication`
- `test_delete_file_invalid_uuid_returns_422`
- `test_delete_file_shared_blob_decrements_ref_count_without_s3_delete`
- `test_delete_file_final_blob_reference_deletes_blob_and_s3_object`
- `test_delete_file_s3_delete_failure_does_not_restore_file`
- `test_delete_file_locks_blob_before_decrementing_ref_count`

## Non-goals for this slice

Do not change the upload API again in this slice. Slice 1 already introduced
`upload_required` and existing-blob upload skipping. Slice 2 should only add
backend deletion behavior.

## Verification

```bash
docker compose exec backend bash scripts/test.sh
```

For CI coverage, the existing Docker Compose workflow should still pass:

```bash
docker compose build
docker compose up -d --wait backend frontend adminer
curl http://localhost:8000/api/v1/utils/health-check
curl http://localhost:5173
```

## Out of scope

- Frontend or mobile UI.
- OpenAPI client regeneration.
- Folder deletion.
- Bulk delete.
- Trash, restore, undo, or audit trail.
- Unique per-file S3 object keys.
- Background S3 garbage collection.
- Admin deletion.

## Open questions

None. Resolved decisions:

1. Delete is owner-only.
2. Delete is hard-delete, not trash/restore.
3. Folder deletion is out of scope.
4. `file_blobs.ref_count` is the source of truth; do not count `files` rows.
5. S3 object deletion happens only after a successful DB commit.
6. S3 deletion failure is logged and does not rollback logical deletion.
7. Successful API response is `204 No Content`.
