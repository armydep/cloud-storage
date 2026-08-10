# Phase 3: Frontend Upload and Download Integration

## Goal

Implement the frontend user experience for uploading and downloading files using the Phase 2 backend presigned URL APIs.

Phase 2 completed the backend/storage side:

- MinIO local object storage;
- `POST /api/v1/files/presign-upload`;
- direct browser upload to MinIO using presigned PUT URL;
- `POST /api/v1/files/complete-upload`;
- `POST /api/v1/files/{file_id}/presign-download`;
- direct browser download from MinIO using presigned GET URL;
- DB constraints for folder/file uniqueness.

Phase 3 makes those capabilities usable from the existing Files screen.

## Current frontend state

The frontend already has:

- `Files` sidebar item;
- `/files` route;
- current folder path stored in route search params:
  ```text
  /files?path=root.documents
  ```
- current path breadcrumbs;
- folder navigation by clicking folder rows;
- folder listing powered by:
  ```text
  GET /api/v1/files?path=<current-path>
  ```

Main files:

```text
frontend/src/routes/_layout/files.tsx
frontend/src/components/Files/columns.tsx
frontend/src/client/sdk.gen.ts
frontend/src/client/types.gen.ts
```

## Frontend organization approach

Do not do a broad frontend refactor before implementing upload/download. The current structure is acceptable for the current app size.

Apply a small feature-level organization as Phase 3 work touches the Files area:

```text
frontend/src/features/files/
  fileHash.ts
  fileCategory.ts
  fileTransfer.ts

frontend/src/components/Files/
  columns.tsx
  UploadFileButton.tsx
  FileActionsMenu.tsx
```

Rules:

- keep generated backend client code in `frontend/src/client/`;
- do not manually edit generated client files;
- keep route files responsible for routing, path state, and page composition;
- move reusable file-transfer logic into `frontend/src/features/files/`;
- move reusable Files UI into `frontend/src/components/Files/`;
- only extract UI from `routes/_layout/files.tsx` when that UI is being touched by the slice.

This keeps the frontend aligned with the backend refactor direction without spending time on low-value reorganization.

## Backend API contract to align with

### List folder contents

```text
GET /api/v1/files?path=<ltree-path>
```

Already used by frontend.

### Presign upload

```text
POST /api/v1/files/presign-upload
```

Request:

```json
{
  "folder_path": "root.documents",
  "name": "report.pdf",
  "mime_type": "application/pdf",
  "category": "document",
  "blob_hash": "<64-char-sha256>",
  "size_bytes": 248320
}
```

Response:

```json
{
  "upload_url": "http://localhost:9000/cloud-storage/sha256/...",
  "method": "PUT",
  "headers": {
    "Content-Type": "application/pdf"
  },
  "object_key": "sha256/<hash>",
  "expires_in": 900
}
```

### Complete upload

```text
POST /api/v1/files/complete-upload
```

Request uses the same metadata as presign-upload.

Response is stored file metadata.

### Presign download

```text
POST /api/v1/files/{file_id}/presign-download
```

Response:

```json
{
  "download_url": "http://localhost:9000/cloud-storage/sha256/...",
  "method": "GET",
  "expires_in": 900
}
```

## 1. Regenerate frontend API client

Goal: make the generated frontend client aware of the new backend endpoints and schemas.

Current generator config:

```text
frontend/openapi-ts.config.ts
```

The generator input is:

```text
frontend/openapi.json
```

Important: `frontend/openapi.json` is ignored by git, but the generator expects it locally. Phase 3.1 must recreate `frontend/openapi.json` from the running backend before generation, or update the generator config to point directly at the backend OpenAPI URL.

Work:

- start/rebuild backend with latest Phase 2 code;
- confirm backend exposes OpenAPI schema:
  ```text
  http://localhost:8000/api/v1/openapi.json
  ```
  or:
  ```text
  http://localhost:8000/openapi.json
  ```
  depending on app configuration;
- save the OpenAPI schema to:
  ```text
  frontend/openapi.json
  ```
- regenerate OpenAPI client from `frontend/openapi.json`;
- confirm generated client includes:
  ```text
  FilesService.presignUpload
  FilesService.completeFileUpload
  FilesService.presignDownload
  PresignUploadRequest
  PresignUploadResponse
  CompleteUploadRequest
  PresignDownloadResponse
  ```
- if generated method names differ, use the generated names consistently.

Expected tracked changed files:

```text
frontend/src/client/sdk.gen.ts
frontend/src/client/types.gen.ts
frontend/src/client/schemas.gen.ts
```

Local ignored generator input:

```text
frontend/openapi.json
```

Verification:

```text
docker compose up -d backend
curl -s http://localhost:8000/openapi.json -o frontend/openapi.json
cd frontend
npm run generate-client
npm run lint
```

If the backend serves OpenAPI under `/api/v1/openapi.json`, use:

```text
curl -s http://localhost:8000/api/v1/openapi.json -o frontend/openapi.json
```

Detailed implementation plan:

1. Check backend OpenAPI URL:
   ```bash
   curl -fsS http://localhost:8000/openapi.json > /tmp/openapi.json
   ```
2. If that fails, check:
   ```bash
   curl -fsS http://localhost:8000/api/v1/openapi.json > /tmp/openapi.json
   ```
3. Copy the working schema:
   ```bash
   cp /tmp/openapi.json frontend/openapi.json
   ```
4. Regenerate:
   ```bash
   cd frontend
   npm run generate-client
   ```
5. Inspect generated file methods:
   ```bash
   rg "presign|completeFileUpload|download" src/client
   ```
6. Run frontend checks:
   ```bash
   npm run lint
   npm run build
   ```

Expected generated names:

The backend route function names currently drive operation IDs. Likely generated names:

```text
FilesService.readFiles
FilesService.presignUpload
FilesService.completeFileUpload
FilesService.presignDownload
```

If generated names differ, do not hand-edit generated files. Use the generated names in later Phase 3 slices.

Acceptance criteria:

- generated client contains request/response types for all three Phase 2 file actions;
- generated `FilesService` contains methods for list, presign upload, complete upload, and presign download;
- no manual edits are made inside generated client files;
- frontend lint/build pass;
- `frontend/openapi.json` is present locally as an ignored generator input or generator config is intentionally updated to use a backend URL.

## 2. Add browser file hashing utility

Goal: compute SHA-256 in the browser before requesting an upload URL.

Add:

```text
frontend/src/features/files/fileHash.ts
```

Suggested API:

```ts
export async function calculateSha256(file: File): Promise<string>
```

Implementation:

- use `file.arrayBuffer()`;
- use `crypto.subtle.digest("SHA-256", buffer)`;
- return lowercase hex string.

Acceptance criteria:

- returns 64-character lowercase SHA-256 hex string;
- handles empty files consistently;
- does not send bytes to backend.

## 3. Add MIME category helper

Goal: map browser MIME types to backend `category` enum.

Suggested API:

```ts
export function getFileCategory(mimeType: string): FileCategory
```

Mapping:

```text
image/* -> image
video/* -> video
audio/* -> audio
application/pdf -> document
text/* -> document
spreadsheet MIME types -> spreadsheet
zip/tar/gzip/rar/7z -> archive
fallback -> other
```

Backend-supported categories:

```text
image
video
audio
document
spreadsheet
archive
other
```

Recommended file:

```text
frontend/src/features/files/fileCategory.ts
```

## 4. Add upload UI on Files screen

Goal: let the user upload a file into the currently viewed folder.

Current path source:

```ts
const { path } = Route.useSearch()
const currentPath = path || "root"
```

Work:

- add an Upload button near the `Files` page header;
- add hidden `<input type="file">` or a small upload dialog;
- support selecting one file initially;
- show upload progress/status;
- disable upload button while upload is in progress;
- show success/error toast;
- refresh current folder query after completion.

Recommended component:

```text
frontend/src/components/Files/UploadFileButton.tsx
```

Props:

```ts
type UploadFileButtonProps = {
  currentPath: string
}
```

Upload sequence:

```text
1. User selects file.
2. Frontend computes SHA-256.
3. Frontend derives category from MIME type.
4. Frontend calls presign-upload.
5. Frontend PUTs bytes directly to upload_url.
6. Frontend calls complete-upload.
7. Frontend invalidates/refetches ["files", currentPath].
```

## 5. Implement direct MinIO upload

Goal: upload bytes directly to MinIO using the presigned URL.

Implementation details:

```ts
await fetch(uploadUrl, {
  method: "PUT",
  headers: presignResponse.headers,
  body: file,
})
```

Rules:

- do not attach backend auth token to MinIO request;
- use exactly the headers returned by backend;
- if PUT fails, do not call complete-upload;
- if complete-upload fails, show error and refresh listing.

Known local requirement:

```text
upload_url should use localhost:9000
```

If the browser sees `http://minio:9000`, backend URL rewriting is broken.

## 6. Add download action for file rows

Goal: allow downloading stored files from the Files table.

Current table:

```text
frontend/src/components/Files/columns.tsx
```

Work:

- add row action for `type === "file"`;
- call presign-download with file id;
- download using returned URL;
- do not show download action for folders.

Basic implementation:

```ts
const response = await FilesService.presignDownload({ fileId: row.id })
window.location.href = response.download_url
```

Alternative:

```ts
const a = document.createElement("a")
a.href = response.download_url
a.download = row.name
a.click()
```

Acceptance criteria:

- file row has visible Download action;
- folder row does not;
- clicking Download downloads from MinIO, not backend;
- another user's file remains inaccessible because backend presign returns 404.

## 7. Error handling UX

Handle these backend responses:

```text
401 -> auth/session handling
404 Folder not found -> refresh or navigate to root
400 Uploaded object not found -> upload failed or expired
400 Uploaded object size mismatch -> metadata mismatch
409 File name already exists -> show duplicate filename message
422 validation error -> show invalid file metadata message
```

User-facing messages:

- `Upload failed. Try again.`
- `A file with this name already exists in this folder.`
- `The selected file could not be validated.`
- `Download link could not be created.`

## 8. Frontend tests

Recommended Playwright coverage:

```text
frontend/tests/files.spec.ts
```

Test cases:

- Files page shows current path;
- folder row click navigates to child folder;
- upload button is visible;
- upload success refreshes current folder listing;
- duplicate filename shows error;
- file row download calls presign-download;
- folder rows do not show download action.

Mocking strategy:

- for UI-level tests, mock backend endpoints where practical;
- for one local E2E test, use real backend + MinIO stack.

## 9. Phase 3 implementation slices

### Phase 3.1: Regenerate frontend client

- regenerate API client;
- verify new file endpoint methods/types exist;
- no UI changes yet.

### Phase 3.2: File hash/category utilities

- add SHA-256 utility;
- add MIME category mapper;
- keep both under `frontend/src/features/files/`;
- add a feature barrel export if it makes imports cleaner:
  ```text
  frontend/src/features/files/index.ts
  ```
- add unit tests if frontend test setup supports it.

Detailed implementation plan:

1. Create:
   ```text
   frontend/src/features/files/fileHash.ts
   frontend/src/features/files/fileCategory.ts
   frontend/src/features/files/index.ts
   ```
2. Implement:
   ```ts
   export async function calculateSha256(file: File): Promise<string>
   ```
3. Implement:
   ```ts
   export function getFileCategory(mimeType: string): FileCategory
   ```
4. Import `FileCategory` from the generated client types:
   ```ts
   import type { FileCategory } from "@/client"
   ```
5. Keep functions pure and browser-safe:
   - no backend calls;
   - no MinIO calls;
   - no React state;
   - no route dependency.
6. Verification:
   ```text
   cd frontend
   npm run build
   ```
7. If a frontend unit test framework is already configured, add tests. If not, do not introduce a new test framework in this slice; cover behavior in later Playwright/E2E work.

Acceptance criteria:

- `calculateSha256` returns lowercase 64-character SHA-256 hex;
- empty file hashing works;
- `getFileCategory` returns only backend-supported category values;
- unknown/empty MIME type maps to `other`;
- no route/component files are changed unless needed for exports;
- frontend build passes.

### Phase 3.3: Upload button and upload flow

- add `UploadFileButton`;
- wire it into `/files`;
- implement presign-upload, MinIO PUT, complete-upload;
- refresh current folder.

Detailed implementation plan:

1. Add upload flow helper:
   ```text
   frontend/src/features/files/fileTransfer.ts
   ```
2. Export a single upload API:
   ```ts
   export async function uploadFileToCurrentFolder({
     file,
     currentPath,
   }: {
     file: File
     currentPath: string
   }): Promise<void>
   ```
3. Inside `uploadFileToCurrentFolder`:
   - calculate `blob_hash` with `calculateSha256(file)`;
   - derive `category` with `getFileCategory(file.type)`;
   - build metadata:
     ```ts
     {
       folder_path: currentPath,
       name: file.name,
       mime_type: file.type || "application/octet-stream",
       category,
       blob_hash,
       size_bytes: file.size,
     }
     ```
   - call `FilesService.presignUpload({ requestBody: metadata })`;
   - upload bytes directly to MinIO:
     ```ts
     await fetch(presign.upload_url, {
       method: presign.method || "PUT",
       headers: presign.headers,
       body: file,
     })
     ```
   - if MinIO upload fails, throw and do not call complete-upload;
   - call `FilesService.completeFileUpload({ requestBody: metadata })`.
4. Add upload UI:
   ```text
   frontend/src/components/Files/UploadFileButton.tsx
   ```
5. `UploadFileButton` props:
   ```ts
   type UploadFileButtonProps = {
     currentPath: string
   }
   ```
6. `UploadFileButton` behavior:
   - render visible Upload button;
   - use hidden `<input type="file">`;
   - support one file per upload in this slice;
   - disable button while upload is running;
   - show basic uploading state;
   - show success/error toast;
   - reset file input after each attempt.
7. Refresh current folder after successful upload:
   ```ts
   queryClient.invalidateQueries({ queryKey: ["files", currentPath] })
   ```
8. Wire the button into:
   ```text
   frontend/src/routes/_layout/files.tsx
   ```
   Place it in the page header next to the Files title.
9. Error handling in this slice:
   - duplicate filename `409`: show `A file with this name already exists in this folder.`;
   - validation/object errors: show `Upload failed. Try again.`;
   - keep detailed error mapping polish for Phase 3.5.
10. Verification:
    ```text
    cd frontend
    npm run build
    ```

Acceptance criteria:

- Files page shows an Upload button;
- selecting a file starts the presigned upload flow;
- browser sends file bytes to MinIO URL, not backend;
- backend receives only presign/complete metadata requests;
- complete-upload is not called when MinIO PUT fails;
- successful upload refreshes the current folder listing;
- current path is passed as `folder_path`;
- upload button is disabled while upload is running;
- frontend build passes.

### Phase 3.4: Download action

- add file-row Download action;
- implement presign-download call;
- start browser download.

Detailed implementation plan:

1. Extend the file transfer helper:
   ```text
   frontend/src/features/files/fileTransfer.ts
   ```
2. Add:
   ```ts
   export async function downloadFile(file: {
     id: string
     name: string
   }): Promise<void>
   ```
3. Inside `downloadFile`:
   - call:
     ```ts
     FilesService.presignDownload({ fileId: file.id })
     ```
   - create a temporary anchor:
     ```ts
     const link = document.createElement("a")
     link.href = response.download_url
     link.download = file.name
     link.click()
     ```
   - do not call backend to fetch bytes;
   - do not attach auth headers to the MinIO URL.
4. Add row action UI:
   ```text
   frontend/src/components/Files/FileActionsMenu.tsx
   ```
5. `FileActionsMenu` props:
   ```ts
   type FileActionsMenuProps = {
     file: FolderContentPublic
   }
   ```
6. Behavior:
   - render only for rows where `type === "file"`;
   - call `downloadFile` on click;
   - show loading/disabled state while presigned URL is being created;
   - show error toast: `Download link could not be created.`;
   - keep folder rows without a download action.
7. Update:
   ```text
   frontend/src/components/Files/columns.tsx
   ```
   Add an `actions` column at the end and render `FileActionsMenu` only for file rows.
8. Verification:
   ```text
   cd frontend
   npm run build
   ```

Acceptance criteria:

- file rows show a Download action;
- folder rows do not show a Download action;
- clicking Download calls backend presign-download;
- browser downloads directly from MinIO presigned URL;
- backend does not proxy downloaded bytes;
- download action handles errors with a toast;
- folder navigation still works;
- frontend build passes.

### Phase 3.5: UX polish and tests

- loading states;
- progress/error handling;
- Playwright coverage;
- update frontend README if needed.

Detailed implementation plan:

1. Review current Files UI behavior manually:
   - `/files` loads root folder;
   - current path is visible;
   - folder rows navigate into child folders;
   - empty folder state still renders correctly;
   - Upload button is visible on every folder path;
   - file rows show Download action;
   - folder rows do not show Download action.
2. Improve upload UX only where needed:
   - make upload-in-progress state clear;
   - keep duplicate filename message visible and specific;
   - keep generic upload failure message for non-409 errors;
   - ensure file input resets after success/failure;
   - ensure folder listing refreshes after upload success.
3. Improve download UX only where needed:
   - keep download action disabled while presigned URL is being created;
   - keep error toast for presign failures;
   - keep folder rows action-free.
4. Add Playwright coverage:
   ```text
   frontend/tests/files.spec.ts
   ```
5. Recommended test cases:
   - Files page shows current path;
   - clicking a folder row navigates to that folder path;
   - empty seeded folder shows empty state;
   - Upload button exists;
   - file rows show Download action;
   - folder rows do not show Download action.
6. Optional local E2E test if stable with Docker stack:
   - login;
   - navigate to `/files`;
   - upload a small text file into `root.documents`;
   - verify the uploaded file appears without manual reload.
7. Do not introduce broad mocking or a new unit test framework in this slice.
8. Run checks:
   ```text
   cd frontend
   npm run build
   npm run test -- files.spec.ts
   ```
9. If repo-wide lint is run, note the existing SVG accessibility failures unless they are fixed in this slice.

Acceptance criteria:

- existing folder browsing remains working;
- Upload and Download controls are visible in the correct places;
- duplicate upload error remains user-readable;
- failed download presign shows an error toast;
- Playwright coverage exists for Files navigation and row actions;
- frontend build passes;
- targeted Files Playwright test passes or any remaining blocker is documented.

### Phase 3.6: Real stack upload/download verification

Goal: verify the implemented frontend upload/download flow against the real local Docker stack, not only mocked Playwright responses.

Why this slice exists:

- Phase 3.3 and 3.4 implemented the frontend flows;
- Phase 3.5 added deterministic UI tests with mocked file API responses;
- the remaining risk is integration-specific:
  - browser-to-MinIO CORS;
  - presigned URL host rewriting;
  - upload metadata matching actual MinIO object state;
  - download behavior for files that exist in DB but not in MinIO.

Work:

1. Start/rebuild the real stack:
   ```text
   docker compose up -d --build
   ```
2. Confirm required services are healthy/running:
   ```text
   docker compose ps
   ```
   Required:
   - backend;
   - frontend;
   - db;
   - minio;
   - minio-create-bucket completed successfully.
3. Verify frontend URL:
   ```text
   http://localhost:5173/files
   ```
4. Verify backend returns browser-accessible presigned URLs:
   - upload/download URLs must use:
     ```text
     http://localhost:9000
     ```
   - they must not use:
     ```text
     http://minio:9000
     ```
5. Test real upload manually or with Playwright:
   - log in as seeded user;
   - browse to `root.documents`;
   - upload a small `.txt` file with a unique name;
   - confirm success toast;
   - confirm the uploaded file appears without manual reload.
6. Test real download:
   - use the uploaded file from step 5, not old mock DB rows;
   - click Download;
   - confirm the file downloads from MinIO.
7. If upload fails in browser:
   - inspect browser network console;
   - check whether the failed request is backend API or MinIO PUT;
   - if MinIO PUT fails with CORS, add MinIO CORS configuration to setup;
   - if URL host is `minio`, fix backend public URL rewriting/config.
8. If download fails for seeded mock files:
   - expected for DB-only seed rows unless matching MinIO objects exist;
   - verify download using a newly uploaded file first.

Acceptance criteria:

- real browser upload works through presigned PUT;
- uploaded file metadata is completed in backend;
- current folder refreshes after upload;
- real browser download works through presigned GET;
- MinIO URLs are browser-accessible;
- any required MinIO CORS/setup fix is documented and committed;
- no backend byte proxying is introduced.

Implementation result:

- real browser upload was verified against Docker stack;
- frontend uploaded bytes directly to MinIO with presigned PUT;
- uploaded file appeared in `root.documents` without manual reload;
- presigned URLs used browser-accessible `http://localhost:9000`;
- MinIO PUT returned success;
- initial download behavior opened/navigated to the MinIO object for text files instead of producing a browser download;
- backend presigned download generation was updated to include `ResponseContentDisposition: attachment`;
- real browser download then produced a download event with the uploaded filename;
- MinIO GET returned success;
- no backend byte proxying was added.

## Acceptance criteria for Phase 3

- user can upload a file into the current folder from `/files`;
- uploaded file appears after completion without manual page reload;
- user can download an uploaded file;
- folder navigation still works;
- current path remains visible and stable during upload/download;
- browser uploads/downloads directly to/from MinIO;
- backend does not proxy file bytes;
- duplicate filename errors are visible to user;
- frontend checks pass.
