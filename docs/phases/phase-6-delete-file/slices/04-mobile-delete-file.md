# Slice 4: Android mobile delete file

## Outcome

An authenticated owner can delete a file from the Android Flutter client after
an explicit confirmation step.

## Dependencies

- Slice 2: Backend delete owned file with blob ref-count decrement.

## Implementation notes

- Add `FilesRepository.deleteFile({required String fileId})`.
- The existing mobile upload flow continues to send `blob_hash`; it does not
  need to know about `file_blobs.ref_count`.
- Update mobile upload flow for the new presign response:
  - if `upload_required=true`, upload the file bytes to `upload_url`, then call
    complete-upload;
  - if `upload_required=false`, skip the direct S3 upload and call
    complete-upload immediately.
- Map `404` to `FileNotFoundError`, `5xx` to `ServerError`, and network
  failures to `NetworkError`, matching existing repository conventions.
- Add controller support such as `FilesController.deleteFile(fileId, fileName)`.
- Clear any local per-file download state for the deleted file after success.
- Refresh the current folder after success.
- Expose the action from the existing file row UI or file detail screen. Prefer
  the smallest change that keeps download/open behavior intact.
- Show a Material confirmation dialog before calling the controller.
- Disable duplicate submissions while delete is pending.

## UX contract

- Delete is available only for files, not folders.
- Confirmation copy names the file.
- Cancel does not call the API.
- Success returns to or remains on the folder list and refreshes the contents.
- Failure shows a `SnackBar` or inline error consistent with the current mobile
  file actions.

## Acceptance criteria

- [ ] `FilesRepository.deleteFile` calls
      `DELETE /api/v1/files/{file_id}` with authentication.
- [ ] Mobile upload skips direct S3 upload when presign returns
      `upload_required=false`.
- [ ] Mobile upload still performs direct S3 upload when presign returns
      `upload_required=true`.
- [ ] Repository tests cover `204`, `404`, server error, and network error.
- [ ] File UI exposes Delete for files only.
- [ ] Confirmation dialog includes the target file name.
- [ ] Cancel closes the dialog without calling the API.
- [ ] Confirm calls the delete controller method.
- [ ] Pending state prevents duplicate delete submissions.
- [ ] Success refreshes the current folder.
- [ ] Deleted file disappears from the list after success.
- [ ] Delete clears stale local download/open state for that file.
- [ ] Failure shows a user-visible error and does not remove the file from the
      current state until refresh proves it is gone.

## Suggested tests

- Upload skips Dio PUT for existing blobs.
- Upload still calls complete-upload after skipping direct S3 upload.
- `FilesRepository.deleteFile` calls the expected endpoint.
- `FilesRepository.deleteFile` handles `204`.
- `FilesRepository.deleteFile` maps `404` to `FileNotFoundError`.
- File row or detail UI shows Delete for files only.
- Canceling confirmation does not call delete.
- Confirming delete calls controller and refreshes list on success.
- Failed delete shows an error message.

## Verification

```bash
cd mobile
dart format --output=none --set-exit-if-changed .
flutter analyze
flutter test
flutter build apk --debug
```

## Out of scope

- Backend ref-count/delete implementation.
- Web frontend delete UI.
- Folder deletion.
- Bulk delete.
- Trash, restore, or undo.
- Shared-with-me recipient delete.

## Open questions

None. The mobile slice uses owner file actions, a confirmation dialog, current
folder refresh, and no undo.
