# Slice 1: Backend recursive owned-folder delete

## Outcome

An authenticated owner can permanently delete one owned non-root folder through
the backend API. The backend deletes the complete folder subtree, removes all
logical file rows in that subtree, decrements affected blob ref counts, and
deletes physical S3/MinIO objects only when those blobs are no longer referenced
by any remaining logical file.

## Dependencies

- Phase 6 completed: file delete and blob ref-count lifecycle are implemented.

## Tracking

- GitHub issue: [#70](https://github.com/armydep/cloude-file-storage/issues/70)
- Status: In progress on branch `feature/phase-7-backend-delete-folder`.

## API contract

```text
DELETE /api/v1/files/folders/{folder_id}
```

Responses:

```text
204 No Content
401 Unauthorized
404 Folder not found
422 Validation error for malformed UUID
```

Authorization behavior:

- Owner of a non-root folder receives `204`.
- Another user receives `404`.
- Root folder delete receives `404`.
- Repeating delete after success receives `404`.
- Unauthenticated caller receives `401`.

## Implementation notes

Target areas:

```text
backend/app/api/routes/files.py
backend/app/files/repository.py
backend/app/files/service.py
backend/tests/api/routes/test_files.py
backend/tests/files/test_repository.py
```

- Add a route that does not conflict with existing file routes:
  `DELETE /api/v1/files/folders/{folder_id}`.
- Add a service function such as `delete_folder(...)`.
- Add repository helpers to:
  - get a folder by owner and id;
  - list descendant folders by owner and `ltree` path prefix with row locks for
    delete operations;
  - list all files in a set of folder ids;
  - aggregate deleted file counts by `blob_hash`;
  - lock affected `file_blobs` rows before decrementing counts;
  - delete files and folders without committing independently.
- Protect root folder deletion. Root can be identified by path `root` and/or
  `parent_id is null`.
- Use one database transaction for:
  - resolving the subtree;
  - locking the subtree folder rows before listing files, so concurrent file or
    child-folder inserts into the subtree block on the folder FK until the
    delete commits;
  - locking affected blob rows;
  - deleting file rows;
  - decrementing/deleting blob rows;
  - deleting descendant folder rows and target folder.
- Delete the selected folder after files and blob metadata have been handled.
  The existing folder self-reference uses database cascade for descendant
  folders, so the service only needs to explicitly delete the selected folder
  row.
- Keep `files.blob_hash -> file_blobs.blob_hash` configured with
  `ON DELETE CASCADE` as a database safety net. The service still deletes file
  rows before deleting blob rows so ref-count changes remain explicit and
  auditable.
- Continue relying on `file_shares.file_id ON DELETE CASCADE` for share cleanup.
- Commit database changes before deleting S3 objects.
- If S3 deletion fails after commit, log it and leave orphan cleanup to a later
  maintenance phase.

## Backend delete algorithm

```python
def delete_folder(session, owner_id, folder_id) -> None:
    folder = repository.get_folder_by_id(
        session=session,
        owner_id=owner_id,
        folder_id=folder_id,
    )
    if folder is None or folder.path == "root":
        raise FolderNotFoundError

    subtree_folders = repository.list_folder_subtree(
        session=session,
        owner_id=owner_id,
        path=folder.path,
        for_update=True,
    )
    folder_ids = [item.id for item in subtree_folders]

    files = repository.list_files_in_folders(
        session=session,
        owner_id=owner_id,
        folder_ids=folder_ids,
    )
    delete_counts = Counter(file.blob_hash for file in files)

    blobs = repository.list_blobs_for_update(
        session=session,
        blob_hashes=list(delete_counts),
    )

    object_keys_to_delete = []
    repository.delete_files(session=session, files=files)
    session.flush()

    for blob in blobs:
        blob.ref_count -= delete_counts[blob.blob_hash]
        if blob.ref_count < 0:
            raise RuntimeError("Blob ref_count would become negative")
        if blob.ref_count == 0:
            object_keys_to_delete.append(blob.object_key)
            repository.delete_blob(session=session, blob=blob)

    session.flush()
    repository.delete_folder(session=session, folder=folder)
    session.commit()

    for object_key in object_keys_to_delete:
        try:
            storage.delete_object(object_key=object_key)
        except Exception:
            logger.exception("Failed to delete unreferenced folder blob object")
```

## Acceptance criteria

- [ ] `DELETE /api/v1/files/folders/{folder_id}` returns `204` for the owner of
      a non-root folder.
- [ ] The target folder no longer appears in its parent folder listing.
- [ ] All descendant folders are deleted.
- [ ] All files in the subtree are deleted.
- [ ] Shares for deleted files are removed by cascade.
- [ ] Prior share recipients no longer see deleted files in Shared with me.
- [ ] Prior share recipients cannot download deleted files.
- [ ] Deleting another user's folder returns `404 Folder not found`.
- [ ] Deleting root returns `404 Folder not found`.
- [ ] Repeating the same folder delete returns `404 Folder not found`.
- [ ] Malformed UUID returns `422`.
- [ ] Deleting an empty folder succeeds.
- [ ] Deleting a folder with direct files succeeds.
- [ ] Deleting a folder with nested folders and nested files succeeds.
- [ ] Blob ref counts are decremented by the number of deleted files per blob.
- [ ] Shared blobs still referenced outside the deleted subtree are not removed
      from S3/MinIO.
- [ ] Final-reference blobs are removed from `file_blobs` and deleted from
      S3/MinIO after DB commit.
- [ ] S3 delete failure after DB commit is logged and does not restore folder or
      file rows.

## Suggested tests

- `test_delete_folder_succeeds_for_owner`
- `test_delete_folder_removes_folder_from_parent_listing`
- `test_delete_folder_deletes_nested_subtree`
- `test_delete_folder_deletes_files_in_subtree`
- `test_delete_folder_removes_shares_for_deleted_files`
- `test_delete_folder_prevents_later_download_for_deleted_file`
- `test_delete_folder_rejects_other_users_folder`
- `test_delete_folder_rejects_root`
- `test_delete_folder_repeated_delete_returns_404`
- `test_delete_folder_invalid_uuid_returns_422`
- `test_delete_empty_folder_succeeds`
- `test_delete_folder_shared_blob_decrements_ref_count_without_s3_delete`
- `test_delete_folder_final_blob_references_delete_blobs_and_s3_objects`
- `test_delete_folder_s3_delete_failure_does_not_restore_db_rows`

## Verification

```bash
cd backend
../.venv/bin/ruff format app tests
../.venv/bin/ruff check app tests
../.venv/bin/pytest tests/api/routes/test_files.py tests/files/test_repository.py
```

For Docker Compose CI compatibility:

```bash
docker compose build
docker compose up -d --wait backend frontend adminer
curl http://localhost:8000/api/v1/utils/health-check
```

## Out of scope

- Web or Android UI.
- Root folder deletion.
- Trash, restore, undo, retention periods, or audit log.
- Folder sharing or inherited permissions.
- Background orphaned-object garbage collection.

## Open questions

None. This slice uses recursive hard-delete, owner-only authorization, root
protection, `204 No Content`, and Phase 6 blob ref-count semantics.
