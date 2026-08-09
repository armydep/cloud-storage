# Slice 3: Android mobile folder delete

## Outcome

An authenticated owner can delete a folder from the Android Flutter client after
an explicit confirmation step.

## Dependencies

- Slice 1: Backend recursive owned-folder delete.

## Tracking

- GitHub issue: [#72](https://github.com/armydep/cloude-file-storage/issues/72)
- Status: Completed in PR [#75](https://github.com/armydep/cloude-file-storage/pull/75).

## Implementation notes

- Add `FilesRepository.deleteFolder({required String folderId})`.
- Map `404` to `FolderNotFoundError`, `5xx` to `ServerError`, and network
  failures to `NetworkError`, matching existing repository conventions.
- Add controller support such as `FilesController.deleteFolder(folderId)`.
- Track per-folder pending delete state to prevent duplicate submissions.
- Expose Delete for folder rows.
- Do not expose Delete for root.
- Confirmation copy must name the folder and state that all contents are
  permanently deleted.
- Refresh the current folder after success.
- If the user deletes a folder they are currently viewing through a detail or
  nested context in the future, navigate back to the nearest surviving parent.
  Current implementation can keep the action on parent folder rows only.
- Keep existing file delete behavior intact.

## UX contract

- Delete is available for folder rows.
- Confirmation copy names the folder.
- Confirmation warns that folder contents are deleted.
- Cancel does not call the API.
- Confirm calls the delete controller method.
- Pending state prevents duplicate submissions.
- Success remains on the parent folder list and refreshes contents.
- Failure shows a `SnackBar` or inline error and does not remove the folder from
  current state until refresh proves it is gone.

## Acceptance criteria

- [ ] `FilesRepository.deleteFolder` calls
      `DELETE /api/v1/files/folders/{folder_id}` with authentication.
- [ ] Repository tests cover `204`, `404`, server error, and network error.
- [ ] Folder UI exposes Delete for folders.
- [ ] File delete behavior remains unchanged.
- [ ] Root folder delete is not exposed.
- [ ] Confirmation dialog includes the target folder name.
- [ ] Confirmation dialog warns that folder contents are deleted.
- [ ] Cancel closes the dialog without calling the API.
- [ ] Confirm calls the delete controller method.
- [ ] Pending state prevents duplicate delete submissions.
- [ ] Success refreshes the current folder.
- [ ] Deleted folder disappears from the list after success.
- [ ] Failure shows a user-visible error and keeps the folder visible until
      refresh proves it is gone.

## Suggested tests

- `FilesRepository.deleteFolder` calls the expected endpoint.
- `FilesRepository.deleteFolder` handles `204`.
- `FilesRepository.deleteFolder` maps `404` to `FolderNotFoundError`.
- `FilesRepository.deleteFolder` maps `5xx` to `ServerError`.
- `FilesRepository.deleteFolder` maps network failure to `NetworkError`.
- Folder row shows Delete.
- Confirmation includes folder name and recursive-delete warning.
- Canceling confirmation does not call delete.
- Confirming delete calls controller and refreshes list on success.
- Failed delete shows an error message and keeps the folder visible.

## Verification

```bash
cd mobile
dart format --output=none --set-exit-if-changed .
flutter analyze
flutter test
flutter build apk --debug
```

## Out of scope

- Backend folder delete implementation.
- Web folder delete UI.
- Root folder deletion.
- Bulk delete.
- Trash, restore, or undo.
- Folder sharing or inherited permissions.

## Open questions

None. The mobile slice uses row-level folder actions, destructive confirmation,
current-folder refresh, and no undo.
