# Phase 4: File sharing with specific users

This design implements [ROADMAP 6.1](../../ROADMAP.md) through four small,
dependent delivery slices. Email is the application's username. Sharing grants
download-only access to an existing active user and never copies file bytes.

## Slice 1: Backend grant, discovery, and download

- Store one share per file and recipient, with cascade cleanup.
- Let an owner share a file by recipient email.
- List files shared with the authenticated user.
- Let owners and current recipients request the existing presigned download.
- Regenerate the frontend API client and cover authorization and validation.

Public API:

```text
POST /api/v1/files/{file_id}/shares
GET  /api/v1/files/shared-with-me
POST /api/v1/files/{file_id}/presign-download
```

## Slice 2: Frontend sharing and Shared with me

Depends on Slice 1.

- Add a Share action and recipient-email dialog to owned files.
- Add a Shared with me sidebar route and table.
- Show file metadata and owner email, with download as the only file action.
- Cover success, validation errors, navigation, empty state, and download in
  Playwright.

## Slice 3: Backend share management and revocation

Depends on Slice 1.

- Let an owner list the recipients for one owned file.
- Let an owner revoke a specific share.
- Remove revoked files from recipient listings and download authorization.
- Regenerate the client and cover owner scoping and repeated revocation.

Planned API:

```text
GET    /api/v1/files/{file_id}/shares
DELETE /api/v1/files/{file_id}/shares/{share_id}
```

## Slice 4: Frontend share management and revocation

Depends on Slices 2 and 3.

- Show current recipients in the Share dialog.
- Add per-recipient revoke controls with pending and error states.
- Refresh the owner view immediately after revocation.
- Complete Playwright coverage and mark ROADMAP 6.1 delivered.

## Acceptance flow

An owner shares a file with another registered user's email. The recipient sees
the file under Shared with me and can download it, but cannot modify or reshare
it. The owner can later see and revoke that recipient, after which the file is
absent from the recipient's listing and download requests return not found.

Folder sharing, public links, invitations, notifications, editable permissions,
and recipient resharing are outside this phase.
