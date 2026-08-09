# Slice 3: Web frontend delete file

## Outcome

An authenticated owner can delete a file from the web Files screen after an
explicit confirmation step.

## Dependencies

- Slice 2: Backend delete owned file with blob ref-count decrement.

## Implementation notes

- Regenerate the OpenAPI client after Slice 2 exposes
  `DELETE /api/v1/files/{file_id}`.
- Do not manually edit generated files in `frontend/src/client/`.
- The existing web upload flow continues to send `blob_hash`; it does not need
  to know about `file_blobs.ref_count`.
- Update web upload flow for the new presign response:
  - if `upload_required=true`, upload the file bytes to `upload_url`, then call
    complete-upload;
  - if `upload_required=false`, skip the direct S3 upload and call
    complete-upload immediately.
- Add a Delete item to `FileActionsMenu` for file rows only.
- Use destructive styling and a confirmation dialog before mutation.
- On success:
  - close the actions menu/dialog;
  - show success feedback;
  - invalidate the current `["files", currentPath]` query;
  - invalidate shared-file queries if present in the query cache.
- On error, keep the user on the current screen and show a clear failure toast.

## UX contract

- The delete action is available only for owned files in the Files screen.
- The confirmation copy names the file.
- Cancel does not call the API.
- While delete is pending, the delete control is disabled or shows pending
  state to prevent double-submit.
- After success, the file disappears without requiring a full page reload.

## Acceptance criteria

- [ ] Generated frontend client includes the delete file operation.
- [ ] Web upload skips direct S3 upload when presign returns
      `upload_required=false`.
- [ ] Web upload still performs direct S3 upload when presign returns
      `upload_required=true`.
- [ ] File actions menu includes `Delete` for files.
- [ ] Folders do not show the delete-file action.
- [ ] Selecting Delete opens a confirmation dialog.
- [ ] Confirmation dialog includes the target file name.
- [ ] Cancel closes the dialog without calling the delete endpoint.
- [ ] Confirm calls `DELETE /api/v1/files/{file_id}`.
- [ ] Pending state prevents duplicate delete submissions.
- [ ] Success invalidates/refetches the current folder listing.
- [ ] Deleted file disappears from the table after success.
- [ ] API errors show an error toast and keep the file visible until refetch.
- [ ] Playwright or component-level tests cover success, cancel, and error
      paths.

## Suggested tests

- Upload skips `fetch(upload_url, { method: "PUT" })` for existing blobs.
- Upload still calls complete-upload after skipping direct S3 upload.
- Delete action is visible for file rows and absent for folder rows.
- Canceling the confirmation dialog does not issue a network request.
- Confirming delete issues the expected `DELETE` request.
- Successful delete removes the row after query refresh.
- Failed delete shows an error toast.

## Verification

```bash
docker compose up -d backend
curl -fsS http://localhost:8000/api/v1/openapi.json -o frontend/openapi.json
cd frontend
npm run generate-client
npm run lint
npm run build
```

Run Playwright if the slice adds or updates end-to-end coverage:

```bash
npx playwright test
```

## Out of scope

- Backend ref-count/delete implementation.
- Android mobile delete UI.
- Folder deletion.
- Bulk delete.
- Trash, restore, or undo.
- Shared-with-me recipient delete.

## Open questions

None. The frontend slice uses owner file actions, a confirmation dialog, query
invalidation, and no undo.
