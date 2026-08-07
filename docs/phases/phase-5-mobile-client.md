# Phase 5: Android mobile client

This design implements [ROADMAP 5.1](../../ROADMAP.md) through six delivery slices. The
mobile client is a standalone Flutter application that provides authenticated file and
folder management on Android devices. File bytes are transferred directly between the
device and object storage using presigned URLs, just like the web frontend.

## Completed slices

### Slice 1: Scaffold Android Flutter application infrastructure

The Flutter application is initialized and buildable at `mobile/`, with:

- Android platform support only, application ID `com.armydep.cloudestorage`
- Environment-aware backend API URL configuration via `--dart-define=API_BASE_URL=...`
- Base HTTP client infrastructure (`app/core/network/api_client.dart`) for authenticated requests
- Placeholder launchable screen
- CI coverage for format, analysis, and tests

**Status:** Completed in #47

### Slice 2: Sign in and persist an Android session

Authenticated routing and session management:

- Users sign in with email and password via `POST /api/v1/login/access-token`
- Bearer token stored securely using Android Keystore via `flutter_secure_storage`
- Session restored on app startup via `POST /api/v1/login/test-token`
- Token refresh or validation failures clear session and return user to login
- Sign out removes stored token and returns to login
- Auth state manages splash, login, authenticated, and error screens
- Tests cover sign in, session restore, token expiration, and sign out

**Status:** Completed in #50 (PRs #55, #56 with auth fixes)

### Slice 3: Browse owned files and folders on Android

A signed-in user can navigate their folder hierarchy and view folder contents (files and
child folders). The current folder's files and child folders appear in a list. Folders are
selectable to navigate into them; back navigation returns to the parent folder.

**Status:** Completed in #51

### Slice 4: Create folders from the Android client

A signed-in user can create a child folder in the folder they are currently viewing via a "Create folder" dialog. Folder name validation is performed locally and by the backend. On success, the current folder is refreshed and the new folder appears in the list. On failure, an inline error message is shown without closing the dialog.

**Status:** Completed in #52 (merged PR #57)

### Slice 5: Download and open a file on Android

A signed-in user can tap a file in the folder list and download it to the device's Downloads folder. The download progress is shown with a dismiss button to cancel. On completion, the file can be opened with the system default application.

**Status:** Completed (merged PR #58)

---

## Next slices

### Slice 6: Upload one file from the Android client (issue #54)

Users can select one file from their device and upload it to the current folder using
the presigned URL flow. Progress is shown during upload.

### Slice 7: File details and metadata (issue #55)

Users can view file metadata: size, download date, MIME type, owner.

---

## Acceptance flow

A signed-in user sees their root folder and can:
1. Navigate into child folders and back to parent (Slice 3)
2. Create new folders using a "Create folder" action (Slice 4)
3. Download files to their device and open them (Slice 5)
4. Upload files from their device (Slice 6)
5. View detailed file metadata in a detail screen (Slice 7)

Folder navigation, creation, downloads, and uploads remain independent, vertical slices.
Shared-with-me files are future work under ROADMAP 6 (sharing phase).
