# Phase 5, Slice 5: Download and open a file on Android

**Issue:** #53  
**Blocks:** Slice 6 (File details and metadata)  
**Blocked by:** #51 (Slice 3: Browse files and folders), #52 (Slice 4: Create folders)

A signed-in user can tap a file in the folder list and download it to the device's Downloads folder. The download progress is shown with a dismiss button to cancel. On completion, the file can be opened with the system default application. Download errors show a user-friendly message inline in the file list item without blocking other interactions.

## Outcome

A user can download any file they own from the file list to their device's Downloads folder and open it with the default system application.

## Acceptance criteria

- [ ] Files in the folder list have a download action (icon or long-press menu).
- [ ] Tapping the download action initiates a `GET` request with a presigned URL from `GET /api/v1/files/{id}/download`.
- [ ] Download progress appears as a progress indicator on the file item (0–100%).
- [ ] A cancel button is shown during download; tapping it aborts the download.
- [ ] On completion, the file is saved to `Downloads/<original_filename>`.
- [ ] User can tap the completed download to open it with the system default application (via `android.intent.action.VIEW`).
- [ ] On HTTP error (4xx, 5xx) or network error, an inline error message appears; retry is available without re-opening.
- [ ] Download state is per-file (multiple files can download in parallel).
- [ ] The file list remains interactive during download.
- [ ] Repository tests cover success, HTTP errors (404, 500), network failure, and cancel.
- [ ] Widget tests cover download action, progress display, completion, error display, and cancel.

## API contract

```
GET /api/v1/files/{id}/download
  Headers: Authorization: Bearer <token>
  Returns: JSON (200 OK)
    {
      "url": "https://minio:9000/bucket/sha256/abc123...",
      "expires_in_seconds": 3600
    }
  Errors:
    404: File not found or not owned
    500: Server error

GET {url}  (to minio, using presigned URL)
  Returns: file content (binary)
  No auth required (URL is presigned)
  Errors:
    404: Object not found in storage
    500: Storage backend error
```

## Architecture decisions

**Download strategy:**
- Fetch presigned URL from backend (short-lived, ~1 hour)
- Stream download directly to device storage (never load entire file into memory)
- Use `dio` package for streaming downloads with progress callbacks

**Storage location:**
- Save to `Downloads/` directory (device standard, visible to user)
- Use original filename from file metadata
- No deduplication or uniqueness check; overwrite if file exists

**Progress and cancellation:**
- Per-file progress state in `FilesState` (keyed by file id)
- Cancellation via `CancelToken` from `dio`
- UI shows progress bar overlay on file item
- Cancel button visible while downloading

**File opening:**
- Use `open_file` or `android_intent` package to trigger system intent
- Intent: `android.intent.action.VIEW` with `file://` URI
- Graceful fallback if no handler available (show "No app to open" message)

**Error handling:**
- Network errors: "Connection lost. Please check your network and try again."
- File not found (404): "File not found or you don't have permission."
- Storage backend error (500): "File download failed. Please try again later."
- No disk space: "Not enough storage on device." (handle `IOException`)
- File open failure: "No application found to open this file type."
- Errors shown inline without blocking list; retry available

**Download state lifecycle:**
- Idle → Downloading (progress 0–100%) → Complete or Error
- Completed state persists; user can re-open without re-downloading
- Error state can be retried; retry clears previous error

## State management

**State to add:**
- `downloadProgress: Map<String, double>` — per-file progress (0.0–1.0), null if not downloading
- `downloadError: Map<String, String?>` — per-file error message, null if no error
- `completedDownloads: Set<String>` — file ids that have been successfully downloaded

**FilesController additions:**
- `downloadFile(String fileId, String fileName) async` — initiates download
- `cancelDownload(String fileId) async` — cancels in-flight download
- `openFile(String filePath)` — opens file with system intent

**FilesRepository additions:**
- `getDownloadUrl(String fileId) async` — fetches presigned URL
- `downloadFileToDevice(String url, String filePath, {required void Function(double) onProgress, required CancelToken cancelToken})` — streams download

## Out of scope

- Batch downloads (select multiple files, download all)
- Download history or download management UI
- Resume partial downloads
- In-app file preview/viewer
- File sharing (already planned separately)
- Automatic re-opening after download
- Background download service
- Download queue with prioritization
- Compression (download as-is)

## Open questions (to resolve before implementation)

1. **Progress UI placement:** Overlay progress bar on file item, or show in a separate download notification?
   - → Overlay progress bar on file item (like folder creation error state)

2. **Multiple downloads:** Allow parallel downloads, or queue them?
   - → Allow parallel downloads (each file has independent state)

3. **Re-download:** If file is already downloaded locally, re-download or skip?
   - → Always re-download (fresh copy, no caching)

4. **File type handling:** Block certain file types, or allow all?
   - → Allow all types (no restrictions, system app handles filtering)

5. **Disk space check:** Pre-check available space before download?
   - → No pre-check; catch `IOException` during write, show "no space" error

## Testing strategy

**Repository/API:**
- Mock API success (200, presigned URL)
- Mock 404 (file not found)
- Mock 500 (server error)
- Mock network error (timeout/exception)
- Mock Minio presigned download success and failure
- Mock `dio` download with progress callbacks

**Widget:**
- Download action appears on file item
- Tapping action initiates download
- Progress bar displays and updates (0, 50, 100%)
- Cancel button visible during download
- Cancelling stops download and clears state
- Completion shows success state
- Error displays inline
- Retry clears error and re-downloads
- Multiple files download independently

**Integration:**
- User downloads single file from root
- User navigates to subfolder and downloads from there
- User cancels download mid-stream
- User sees error and retries successfully
- User opens downloaded file with system app

## Next slice: Slice 6

Once file downloads are stable, the next slice is **File details and metadata** (#54), which shows file size, download date, and MIME type in a detail view.

## Implementation notes

- `dio` package already included in `pubspec.yaml` for HTTP client; use `Dio.download()` for streaming
- `path_provider` package for `getDownloadsDirectory()`
- `open_file` or `android_intent` for opening files (evaluate both)
- `android:requestLegacyExternalStoragePermission` if targeting older Android
- Test files: `files_repository_download_test.dart`, `files_browser_screen_download_test.dart`
