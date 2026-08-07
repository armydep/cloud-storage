# Phase 5, Slice 6: Upload one file from the Android client

## Overview

A signed-in user can select a single file from their Android device and upload it to the current folder using the presigned URL flow. Upload progress is displayed with visual feedback and cancellation support.

## Acceptance criteria

- [ ] User can tap an "upload" action in the folder list to select a file from device storage
- [ ] File picker shows all files on device; user selects one file to upload
- [ ] Selected file name and size are displayed before upload begins
- [ ] Upload progress displays as a percentage in the file list (0-100%)
- [ ] User can cancel an in-flight upload; file is removed from object storage on cancellation
- [ ] On successful upload, file appears in the current folder's list immediately
- [ ] On failure, an inline error message is shown with retry option
- [ ] Backend prevents duplicate file names in same folder (returns 409)
- [ ] Backend validates file size does not exceed maximum (returns 422)
- [ ] Network errors show user-facing message: "Connection lost. Please check your network and try again."
- [ ] Tests cover success, duplicate name, size validation, network failure, and cancellation

## API contract

**Presign upload**
```
POST /api/v1/files/presign-upload
Authorization: Bearer <token>
Content-Type: application/json

{
  "parent_path": "root",
  "file_name": "document.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 102400
}

Response (200):
{
  "upload_url": "https://minio:9000/bucket/...",
  "method": "PUT",
  "expires_in": 3600
}
```

**Complete upload**
```
POST /api/v1/files/{file_id}/complete-upload
Authorization: Bearer <token>

Response (201):
{
  "id": "uuid",
  "name": "document.pdf",
  "type": "file",
  "size_bytes": 102400,
  "mime_type": "application/pdf",
  "path": "/document.pdf"
}
```

Errors:
- 404: File not found or you do not have permission
- 409: Duplicate file name
- 422: File size exceeds maximum or invalid file name
- 500: Server error

## Architecture decisions

### File selection
- Use `file_picker` package to allow user to select any file type
- Display selected file name and size for confirmation before upload
- Support only single-file upload (not bulk)

### Upload state tracking
- Per-file upload state in `FilesState`: `uploadProgress: Map<String, double>`
- Track upload errors per file: `uploadError: Map<String, String?>`
- Completion state: `completedUploads: Set<String>` (like downloads)

### Progress tracking
- Use dio's `onSendProgress` callback during PUT to presigned URL
- Update UI with real-time percentage (0-100%)
- Display cancel button while uploading (0% < progress < 100%)
- Display retry button on error

### File picker integration
- Use `file_picker` package (already supports Android)
- Request `READ_EXTERNAL_STORAGE` permission at runtime
- Show system file picker UI (native behavior)

### Error handling
- Duplicate file name: show inline error, offer retry (may rename)
- Size validation failure: show file too large message
- Network error during presign: show connection error
- Network error during PUT: show connection error, cancel automatically
- Network error during complete: show completion failed, file may be orphaned (cleanup handled by SCALE 5.2)

## Out of scope

- Bulk file upload
- Upload queue or background upload service
- File deduplication (same content as existing file)
- Resume interrupted uploads
- Custom file naming/path selection during upload (always current folder)
- Progress animation or transition effects
- Upload history or activity log

## Open questions

**Q1: Should we allow cancellation after presign but before PUT?**
A: No. Once the presigned URL is issued, cancellation means the user changed their mind. We don't presign and then cancel without uploading — that's wasted presigned URL generation. Cancel only applies to in-flight PUT and after complete-upload fails.

**Q2: What happens if complete-upload fails but the PUT succeeded?**
A: The object exists in S3 but has no metadata row. This is covered by SCALE 5.3 (cleanup for orphaned metadata). Retry complete-upload; if it still fails, show error and let user retry later.

**Q3: Should file name validation happen before or after presign?**
A: Before presign. Call `validateFileName()` locally (255 char limit, alphanumeric+space/dash/underscore), then presign. The backend validates again, but local validation prevents unnecessary presign calls.

**Q4: Should we show file preview or thumbnail?**
A: No. File picker already shows the file's icon. Preview is out of scope for this slice.

**Q5: How do we handle permission requests at runtime?**
A: Use `permission_handler` package to request `READ_EXTERNAL_STORAGE`. Show permission denial message if user denies.

## Implementation checklist

- [ ] Add file_picker and permission_handler to pubspec.yaml
- [ ] Add READ_EXTERNAL_STORAGE to AndroidManifest
- [ ] Update FilesState to track upload progress, errors, completed uploads
- [ ] Add methods to FilesState: updateUploadProgress, setUploadError, clearUploadState
- [ ] Extend FilesRepository: presignUpload(), completeUpload()
- [ ] Extend FilesController: selectAndUploadFile(), _uploadFile(), cancelUpload()
- [ ] Update FileListItem to show upload button and progress/error states
- [ ] Update FilesBrowserScreen to pass onUpload callback
- [ ] Add file name validation (local side)
- [ ] Add upload progress indicator similar to download (LinearProgressIndicator overlay)
- [ ] Add storage permission request and handling
- [ ] Widget tests: upload button, progress display, cancel button, error message, retry
- [ ] Repository tests: presign endpoint, complete endpoint, error cases
- [ ] Update phase-5-mobile-client.md to mark Slice 6 complete

## Files to create/modify

**New files:**
- None (reuse existing patterns)

**Modified files:**
- `mobile/pubspec.yaml` — add file_picker, permission_handler
- `mobile/android/app/src/main/AndroidManifest.xml` — add READ_EXTERNAL_STORAGE permission
- `mobile/lib/features/files/application/files_state.dart` — add upload state
- `mobile/lib/features/files/application/files_providers.dart` — add upload logic
- `mobile/lib/features/files/data/files_repository.dart` — add presign/complete upload endpoints
- `mobile/lib/features/files/presentation/files_browser_screen.dart` — pass onUpload callback
- `mobile/lib/features/files/presentation/widgets/file_list_item.dart` — show upload progress/error
- `mobile/test/features/files/data/files_repository_upload_test.dart` — new repository tests
- `mobile/test/features/files/presentation/files_upload_test.dart` — new widget tests
- `docs/phases/phase-5-mobile-client.md` — update completion status
