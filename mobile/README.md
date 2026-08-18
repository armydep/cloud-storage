# Cloude Storage mobile

Android-only Flutter application for Cloud File Storage. This directory is a
standalone client application; it does not belong to the React workspace in
`frontend/`.

The application supports secure sign-in, session restoration, and sign-out.
File management and synchronization will be added in later issues.

## Prerequisites

- Flutter stable, including the Android toolchain
- Android Studio with an Android SDK and emulator, or a physical Android device
- Java version supported by the generated Gradle wrapper
- A running Cloud File Storage backend
- Android 7.0 (API 24) or newer

Verify the local toolchain:

```bash
flutter doctor
```

## API configuration

The application reads `API_BASE_URL` at compile time. Its default is
`http://10.0.2.2:8000`, which lets an Android emulator reach a backend running
on the development host.

Override it without editing source files:

```bash
flutter run --dart-define=API_BASE_URL=https://api.example.com
```

For a physical device, use a backend URL reachable from that device. Do not put
tokens, passwords, or other secrets in `--dart-define` values.

### Reaching search from the emulator

In production the app points at the public API origin, which *is* Traefik, so
`/api/v1/search/*` routes to `search-svc` transparently -- the app needs no
special handling. The Android emulator is the one exception, and it is a
development-environment detail rather than an architectural one.

The default `API_BASE_URL` (`http://10.0.2.2:8000`) reaches `backend`'s
directly published port, bypassing Traefik entirely -- `backend` does not serve
`/api/v1/search/*`, so search calls 404 against that default. Traefik routes by
`Host(api.${DOMAIN})` (typically `api.localhost`), and that hostname resolves
to the emulator itself when the emulator's own resolver looks it up, not to the
host machine -- the same RFC 6761 loopback behavior documented for Playwright's
Chromium in issue #140.

`adb reverse` sidesteps this without editing app code, by forwarding a
connection the emulator makes to its own loopback straight to the host's
matching port:

```bash
adb reverse tcp:80 tcp:80
flutter run --dart-define=API_BASE_URL=http://api.localhost
```

The app's HTTP client sends `http://api.localhost/...` requests exactly as
configured. `api.localhost` resolves to loopback *on the emulator*, so the
connection attempt targets the emulator's own port 80 -- which `adb reverse`
tunnels to the host's port 80, where Traefik (published by
`compose.override.yml`) is listening. Traefik still sees the original
`Host: api.localhost` header, because `adb reverse` forwards the raw
connection rather than rewriting anything, so its `Host(api.localhost) &&
PathPrefix(/api/v1/search)` rule matches and routes to `search-svc` exactly as
it would for a browser on the host.

Re-run `adb reverse` after every emulator restart -- the forwarding rule does
not persist across reboots. `DOMAIN` must match whatever the running compose
stack uses (`api.localhost` for the default `.env.example`); adjust the
`--dart-define` value if the stack overrides `DOMAIN`.

## Run and build

From `mobile/`:

```bash
flutter pub get
flutter run
flutter build apk --dart-define=API_BASE_URL=https://api.example.com
```

The Android application ID is `com.armydep.cloudestorage`.

## Authentication

Sign in with an existing Cloud File Storage email and password. The access
token is stored in Android secure storage and validated whenever the app starts.
Invalid or expired sessions return to sign-in; temporary network or server
failures retain the token and offer a retry. Signing out deletes the token.

Registration, password recovery, and biometric authentication are not part of
the current mobile scope.

## Search

The search icon in the files browser opens a results screen scoped to the
folder currently being viewed -- results come from that folder and everything
beneath it, matching `search-svc`'s folder-scoped query contract. Typing is
debounced, and a category filter can be applied on its own or alongside text.
Results page via the opaque `next_cursor` search-svc returns; the app passes it
back unmodified and never constructs or parses one.

A search failure (search-svc or Elasticsearch unavailable) renders as a
distinct error state with a retry action -- it never looks like "no matches".
A newly uploaded file may briefly not appear in results, since the index is
eventually consistent; this is expected and is not surfaced as an error.

Opening a result reuses the same download/open handling as the files browser,
including shared download progress and error state, since a search result is
just a file.

## Quality checks

```bash
dart format --output=none --set-exit-if-changed .
flutter analyze
flutter test
```

Apply Dart formatting with `dart format .`.

## Source layout

```text
lib/
├── app/             Application widget and auth-aware routing
├── core/
│   ├── config/      Compile-time application configuration
│   └── network/     Reusable backend HTTP client foundation
├── features/
│   └── auth/        Session state, secure storage, API, and screens
└── main.dart        Application bootstrap
```
