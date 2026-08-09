# Phase 7: Delete folder

## Goal

Let an authenticated owner delete one owned folder from the backend, web
frontend, and Android mobile client.

Folder deletion is recursive: deleting a folder deletes all descendant folders,
all files in that subtree, and all shares attached to those files. Blob storage
continues to use the Phase 6 deduplicated model. Physical S3/MinIO objects are
deleted only when folder deletion removes the final logical reference to the
blob.

Root folder deletion is not supported.

## Product and technical decisions

1. **Folder delete is recursive hard delete.** Trash, restore, undo, retention,
   and soft-delete remain out of scope.

2. **Only folder owners can delete.** A folder belongs to exactly one owner.
   Missing folders, folders owned by another user, and root folder delete
   attempts return `404 Folder not found`.

3. **Root folder is protected.** The `root` folder is the user's stable
   namespace anchor and cannot be deleted.

4. **Deleting a folder removes its subtree.** The backend deletes all descendant
   folders and every file contained anywhere under the target folder.

5. **Shares are removed through existing cascade.** File shares disappear when
   the referenced file rows are deleted.

6. **Blob ref counts remain authoritative.** The backend decrements each
   affected `file_blobs.ref_count` by the number of deleted logical files
   referencing that blob. A physical object is deleted only if its resulting
   ref count reaches zero.

7. **Database changes commit before S3 deletion.** The database remains the
   source of truth. If post-commit S3 deletion fails, the folder delete is not
   rolled back; orphan cleanup is still out of scope.

8. **Successful API response is `204 No Content`.** The clients refresh the
   parent folder after success.

9. **Clients must confirm destructive action.** Confirmation copy must make
   clear that folder contents are also deleted.

## Slice breakdown

### Slice 1: Backend recursive owned-folder delete

Detailed spec:
[01-backend-delete-owned-folder.md](phase-7-delete-folder/slices/01-backend-delete-owned-folder.md)

GitHub issue: [#70](https://github.com/armydep/cloude-file-storage/issues/70)

Status: In progress on branch `feature/phase-7-backend-delete-folder`.

- Add `DELETE /api/v1/files/folders/{folder_id}`.
- Reject root folder deletion.
- Authorize by owner.
- Resolve the target folder subtree.
- Delete all files in the subtree.
- Decrement blob ref counts safely.
- Delete now-unreferenced S3 objects after DB commit.
- Delete descendant folders and target folder.
- Cover recursive delete, authorization, root protection, shares, and blob
  lifecycle behavior.

### Slice 2: Web frontend folder delete

Detailed spec:
[02-frontend-delete-folder.md](phase-7-delete-folder/slices/02-frontend-delete-folder.md)

GitHub issue: [#71](https://github.com/armydep/cloude-file-storage/issues/71)

Depends on Slice 1.

Status: In progress on branch `feature/phase-7-frontend-delete-folder`.

- Regenerate the generated OpenAPI frontend client.
- Add a Delete action for folder rows.
- Show a confirmation dialog that names the folder and warns that contents are
  deleted.
- Call the backend folder delete endpoint.
- Refresh the current folder after success.
- Cover cancel, success, pending, and error states.

### Slice 3: Android mobile folder delete

Detailed spec:
[03-mobile-delete-folder.md](phase-7-delete-folder/slices/03-mobile-delete-folder.md)

GitHub issue: [#72](https://github.com/armydep/cloude-file-storage/issues/72)

Depends on Slice 1.

Status: In progress on branch `feature/phase-7-mobile-delete-folder`.

- Add repository/controller delete support.
- Expose Delete for folder rows.
- Show Android confirmation UI that names the folder and warns that contents
  are deleted.
- Refresh the current folder after success.
- Cover cancel, success, pending, and error states.

## Acceptance flow

An owner has a folder containing direct files, nested folders, and nested files.
Some files may share a blob with files outside the deleted subtree.

The owner selects Delete for the folder, confirms the destructive action, and
the folder disappears from its parent listing. A later refresh still does not
show the folder or any deleted descendants. Any share recipients no longer see
files that were inside the deleted folder, and they cannot request presigned
download URLs for those files.

Blobs still referenced by files outside the deleted subtree remain in S3/MinIO.
Blobs whose final references were removed are deleted from S3/MinIO after the
database transaction commits.

## Out of scope

- Root folder deletion.
- Bulk delete across multiple selected rows.
- Trash, restore, undo, retention periods, or audit log.
- Moving deleted contents elsewhere.
- Background orphaned-object garbage collection.
- Admin deletion of another user's folders.
- Folder sharing or permission inheritance.

## Open questions

None for implementation planning. The phase uses recursive hard-delete,
owner-only authorization, root protection, client confirmation, and the existing
deduplicated blob lifecycle.
