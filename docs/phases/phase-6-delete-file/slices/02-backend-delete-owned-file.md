# Slice 2: Backend delete owned file with blob ref-count decrement

## Outcome

An authenticated file owner can permanently delete one owned logical file
through the backend API. The referenced blob's `ref_count` is decremented, and
the physical S3/MinIO object is deleted only when the deleted file was the final
reference.

## Dependencies

- Slice 1: Backend blob ref-count schema migration.

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

- Add `storage.delete_object(object_key=...)`.
- Add route before more-specific subroutes only if route matching requires it;
  confirm it does not conflict with:
  - `POST /api/v1/files/{file_id}/presign-download`
  - `POST /api/v1/files/{file_id}/shares`
  - `GET /api/v1/files/{file_id}/shares`
  - `DELETE /api/v1/files/{file_id}/shares/{share_id}`
- Add repository function to fetch an owned file by `owner_id` and `file_id`, or
  reuse the existing `get_file_by_id`.
- Lock the referenced blob row for update before changing `ref_count`.
- Delete the logical file row and decrement blob `ref_count` in the same DB
  transaction.
- If `ref_count` becomes zero:
  - delete the blob row in the same transaction;
  - commit the DB transaction;
  - delete the S3 object after commit.
- If `ref_count` remains greater than zero:
  - commit the DB transaction;
  - do not delete the S3 object.
- Raise `StoredFileNotFoundError` when the file does not exist or is not owned
  by the current user.
- Rely on existing database cascade to remove `file_shares` for the deleted
  file.
- If post-commit S3 deletion fails, log it and leave orphan cleanup to a future
  maintenance task. Do not recreate the logical file row.

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

None. The backend delete slice uses hard-delete logical files, owner-only
authorization, `204 No Content`, share cascade, and ref-counted physical blob
deletion.
