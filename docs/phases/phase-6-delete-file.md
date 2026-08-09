# Phase 6: Delete file with deduplicated blob storage

This design implements GitHub issue
[#40](https://github.com/armydep/cloude-file-storage/issues/40): support file
deletion.

## Goal

Let an authenticated file owner delete one owned file from the backend, web
frontend, and Android mobile client while preserving the current
content-addressed storage model:

```text
object_key = sha256/{blob_hash}
```

Identical file bytes are stored once in S3/MinIO and referenced by multiple
logical `files` rows through a new `file_blobs` table. The backend deletes the
physical S3 object only when the last logical file reference is deleted.

## Product and technical decisions resolved before implementation

1. **Deduplicated blob storage is intentional.** Identical file bytes continue
   to map to one physical S3 object.

2. **Add an explicit blob lifecycle model.** A new `file_blobs` table stores
   one row per physical object with `blob_hash`, `object_key`, `size_bytes`,
   `ref_count`, and `created_at`.

3. **`files` remains the logical file model.** A `files` row represents one
   user-visible file in one folder. Multiple `files` rows can reference the same
   `file_blobs.blob_hash`.

4. **Delete means hard-delete logical file metadata.** The deleted file row is
   removed immediately. Trash, undo, restore, and soft-delete are out of scope.

5. **Only file owners can delete.** A share recipient can download a shared file
   but cannot delete it.

6. **Folders are out of scope.** Folder deletion is not part of this phase.

7. **Shares are removed through database cascade.** Existing
   `file_shares.file_id` uses `ON DELETE CASCADE`, so deleting a file row removes
   that file's share grants.

8. **Blob ref counts gate physical deletion.** On file delete, the backend
   decrements `file_blobs.ref_count`. If it reaches zero, the blob row is
   removed and the S3 object is deleted.

9. **Existing blobs are not overwritten.** If a client requests upload for a
   `blob_hash` already present in `file_blobs`, the backend must not issue a new
   presigned PUT URL for that object key. The client can skip the direct S3
   upload and call complete-upload to create another logical file reference.

10. **S3 delete happens after the DB commit.** The database remains the source of
   truth. If the DB delete succeeds but S3 delete fails, the object may be
   orphaned and should be cleaned by a later maintenance job. The user's logical
   delete should not be rolled back after DB commit.

11. **API response is `204 No Content`.** A successful delete returns no body.
    Missing files, files owned by another user, and shared-only files all return
    `404 File not found` to avoid leaking existence.

12. **Clients confirm destructive action.** Web and mobile must show a
    confirmation step before calling the delete API.

## Slice breakdown

### Slice 1: Backend blob ref-count schema migration

Detailed spec:
[01-backend-blob-ref-count-migration.md](phase-6-delete-file/slices/01-backend-blob-ref-count-migration.md)

GitHub issue: [#65](https://github.com/armydep/cloude-file-storage/issues/65)

- Add `file_blobs` table.
- Backfill one blob row per existing `files.blob_hash`.
- Set `ref_count` from current `files` references.
- Add a foreign key from `files.blob_hash` to `file_blobs.blob_hash`.
- Update models/repository code to understand blob rows.
- Keep existing upload/download behavior working.
- Update presign upload so existing blobs return "upload not required" instead
  of a presigned PUT URL.

### Slice 2: Backend delete owned file with blob ref-count decrement

Detailed spec:
[02-backend-delete-owned-file.md](phase-6-delete-file/slices/02-backend-delete-owned-file.md)

GitHub issue: [#62](https://github.com/armydep/cloude-file-storage/issues/62)

Depends on Slice 1.

- Add `DELETE /api/v1/files/{file_id}`.
- Authorize by owner only.
- Delete the logical file row.
- Decrement the referenced blob's `ref_count`.
- Delete the S3 object only when the deleted file was the final reference.
- Rely on share cascade.

### Slice 3: Web frontend delete file

Detailed spec:
[03-frontend-delete-file.md](phase-6-delete-file/slices/03-frontend-delete-file.md)

GitHub issue: [#63](https://github.com/armydep/cloude-file-storage/issues/63)

Depends on Slice 2.

- Regenerate the generated OpenAPI frontend client.
- Update upload handling so it skips direct S3 upload when the backend says the
  blob already exists.
- Add a Delete action to owned file actions.
- Show a confirmation dialog.
- Invalidate/refetch the current folder and shared file queries after success.
- Cover success, cancel, pending, and error states.

### Slice 4: Android mobile delete file

Detailed spec:
[04-mobile-delete-file.md](phase-6-delete-file/slices/04-mobile-delete-file.md)

GitHub issue: [#64](https://github.com/armydep/cloude-file-storage/issues/64)

Depends on Slice 2.

- Add repository/controller delete support.
- Update upload handling so it skips direct S3 upload when the backend says the
  blob already exists.
- Expose delete from file rows or file detail screen.
- Show Android confirmation UI.
- Refresh current folder after success.
- Cover success, cancel, pending, and error states.

## Acceptance flow

An owner uploads or already has a file in a folder. The file row references a
`file_blobs` row. If another logical file has identical bytes, both file rows
reference the same blob row and the blob `ref_count` is greater than one.

From either web or Android, the owner selects Delete, confirms the action, and
the file disappears from the current folder. A later folder refresh still does
not show the deleted file. Any previous share recipient no longer sees that file
under Shared with me and cannot request a presigned download URL for it.

If the deleted file was not the final reference to its blob, the S3 object
remains. If it was the final reference, the backend deletes the S3 object after
the database transaction commits.

## Out of scope

- Folder deletion.
- Bulk delete.
- Trash, restore, undo, retention periods, or audit log.
- Unique per-file S3 object keys.
- Background orphaned-object garbage collection.
- Deleting shared-with-me files as a recipient.
- Admin delete of another user's files.

## Open questions

None. The implementation decisions above are resolved for this phase.
