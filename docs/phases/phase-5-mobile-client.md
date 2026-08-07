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

## Next slice

### Slice 3: Browse owned files and folders on Android

**Blocked by:** None (depends only on completed Slice 2)

A signed-in user can navigate their folder hierarchy and view folder contents (files and
child folders). The current folder's files and child folders appear in a list. Folders are
selectable to navigate into them; back navigation returns to the parent folder.

#### API contract

```
GET /api/v1/files?path=<ltree_path>
  Returns: FolderWithContentsPublic
  Fields: id, name, path, created_at, contents[]
  Contents item: id, name, type(string), path(string|null), size_bytes(int|null), category(string|null), mime_type(string|null)
    - type="folder" when path is set (path is child folder path)
    - type="file" when mime_type is set
```

#### Acceptance criteria

- [ ] The authenticated home screen displays the root folder's direct files and child folders.
- [ ] Tapping a child folder loads that folder and displays its contents; navigation history is maintained.
- [ ] Tapping the back button or platform back gesture returns to the parent folder.
- [ ] File rows display: name, category icon, size (formatted as KB/MB/GB).
- [ ] Folder rows display: name, folder icon.
- [ ] Loading state shows a progress indicator while the API request is in flight.
- [ ] Empty-folder state shows an appropriate message with an icon when the folder contains no items.
- [ ] Network and server errors (404, 500, timeout, etc.) are shown with a dismissible message and a retry action.
- [ ] Pull-to-refresh (swipe down) reloads the current folder without changing the navigation path.
- [ ] Repository and widget tests cover root loading, folder navigation, empty contents, refresh, and error states.

#### Architecture decisions

**State management:** Use `FutureProvider.family` for folder contents at each path. Current
path is stored in a simple `StateProvider<String>`. No `FolderController` needed for initial
version; folder loading is request-driven, not state-driven.

**Navigation:** Single `/files` route with current path managed by provider state. Deep
linking to specific paths deferred; back navigation uses provider state, not route stack.

**API client:** Generate typed Dart models and API client from backend OpenAPI schema using
`openapi-generator`. (Implementation detail for Slice 3.)

**File categories and icons:** Backend provides a `category` field (based on MIME type);
mobile displays category-specific icons using `flutter_svg` or Material icons.

**Error handling:** Show user-friendly error messages without exposing raw API responses.
Differentiate between "Folder not found" (404), "Permission denied" (403 implied as 404),
network timeout, and generic server errors (5xx). All errors include a retry button.

**Empty state:** Show a single "This folder is empty" message for zero-item folders, with
an icon (e.g., folder outline with a "no items" badge). Do not differentiate between
truly empty and permission-denied at this stage (permission denied is a 404 to the client).

#### Out of scope

- Deep linking to specific folders via URL or notification tap.
- Folder creation, rename, or deletion.
- File upload, download, rename, or deletion.
- Search or sorting.
- File previews or inline media playback.
- Offline caching or synchronization.
- Shared-with-me files.
- Shared-with-me tab or sidebar (ROADMAP 6.2 on mobile).

#### Next slice: Slice 4

Once folder browsing is stable, the next slice is **Create folders from the Android
client** (#52), which adds a "Create folder" button to each folder screen and calls
`POST /api/v1/files/folders`.

---

## Remaining slices (planned order)

### Slice 4: Create folders from the Android client (issue #52)

**Blocked by:** Slice 3 (requires folder browsing UI and navigation)

Users can create a child folder in the current folder via a "Create folder" dialog. Validation,
duplicate-name errors, and network failures are handled.

### Slice 5: Download and open a file on Android (issue #53)

**Blocked by:** Slice 3 (requires file listing and file row actions)

Users can download files they own and hand them to Android's file open/share chooser.

### Slice 6: Upload one file from the Android client (issue #54)

**Blocked by:** Slice 3 (requires folder UI and file actions)

Users can select one file from their device and upload it to the current folder using
the presigned URL flow (no bearer token on object storage).

---

## Acceptance flow

A signed-in user sees their root folder. They tap a child folder to navigate into it.
The child folder's files and nested folders appear. They tap back (or the platform back
gesture) to return to the root. A network error briefly shows a message with a retry
button. Pulling down the folder refreshes its contents. An empty folder shows
"This folder is empty" with no error.

Folder creation, file upload, and file download remain separate, dependent slices.
Shared-with-me files are future work under ROADMAP 6 (sharing phase).
