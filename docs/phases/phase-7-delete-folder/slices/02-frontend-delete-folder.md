# Slice 2: Web frontend folder delete

## Outcome

An authenticated owner can delete a folder from the web Files screen after an
explicit confirmation step.

## Dependencies

- Slice 1: Backend recursive owned-folder delete.

## Tracking

- GitHub issue: [#71](https://github.com/armydep/cloude-file-storage/issues/71)
- Status: Planned.

## Implementation notes

- Regenerate the OpenAPI client after Slice 1 exposes
  `DELETE /api/v1/files/folders/{folder_id}`.
- Do not manually edit generated files in `frontend/src/client/`.
- Add a Delete action for folder rows in the Files table.
- Do not show delete for the root folder. The root folder is not currently a row
  in its own listing, but keep this invariant explicit.
- Confirmation copy must name the folder and state that all contents are
  permanently deleted.
- On success:
  - close the actions menu/dialog;
  - show success feedback;
  - invalidate/refetch the current folder listing;
  - invalidate shared-file queries if present, because deleted subtree files may
    have had shares.
- On error, keep the folder visible and show a clear failure toast.
- Keep existing file delete behavior intact.

## UX contract

- Delete is available for folder rows.
- Selecting Delete opens a confirmation dialog.
- Confirmation copy names the folder.
- Cancel does not call the API.
- Pending state prevents duplicate submissions.
- Success removes the folder row from the current listing after refresh.
- Failure leaves the user on the current screen and keeps the folder visible
  until a later refresh proves otherwise.

## Acceptance criteria

- [ ] Generated frontend client includes the delete folder operation.
- [ ] Folder actions include `Delete`.
- [ ] File delete behavior remains unchanged.
- [ ] Selecting Delete opens a confirmation dialog.
- [ ] Confirmation dialog includes the folder name.
- [ ] Confirmation dialog warns that folder contents are deleted.
- [ ] Cancel closes the dialog without calling the delete endpoint.
- [ ] Confirm calls `DELETE /api/v1/files/folders/{folder_id}`.
- [ ] Pending state prevents duplicate delete submissions.
- [ ] Success invalidates/refetches the current folder listing.
- [ ] Deleted folder disappears from the table after success.
- [ ] Shared-file query cache is invalidated after success.
- [ ] API errors show an error toast and keep the folder visible until refetch.
- [ ] Playwright or component-level tests cover success, cancel, and error
      paths.

## Suggested tests

- Folder row exposes Delete.
- Selecting Delete opens confirmation with the folder name.
- Confirmation warns that folder contents are deleted.
- Canceling confirmation does not issue a network request.
- Confirming delete issues the expected `DELETE` request.
- Successful delete removes the folder row after query refresh.
- Failed delete shows an error toast and keeps the folder visible.
- File delete tests still pass.

## Verification

```bash
docker compose up -d backend
curl -fsS http://localhost:8000/api/v1/openapi.json -o frontend/openapi.json
cd frontend
npm run generate-client
npm run lint
npm run build
npx playwright test tests/files.spec.ts
```

## Out of scope

- Backend folder delete implementation.
- Android mobile folder delete UI.
- Root folder deletion.
- Bulk delete.
- Trash, restore, or undo.
- Folder sharing or inherited permissions.

## Open questions

None. The frontend slice uses row-level folder actions, destructive
confirmation, current-folder refresh, shared-file cache invalidation, and no
undo.
