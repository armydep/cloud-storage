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

For a physical device, use a backend URL reachable from that device -- and make
sure that URL is **Traefik's** origin (port 80/443, `Host: api.${DOMAIN}`), not
`backend`'s directly-published port 8000. Pointing at port 8000 works for
login and file upload (those routes exist on `backend` itself), which is what
makes the mistake easy to miss, but `backend` does not serve
`/api/v1/search/*` -- only Traefik routes that prefix on to `search-svc` -- so
search silently 404s while everything else appears to work. Do not put tokens,
passwords, or other secrets in `--dart-define` values.

### Reaching search from the emulator

In production the app points at the public API origin, which *is* Traefik, so
`/api/v1/search/*` routes to `search-svc` transparently -- the app needs no
special handling. The Android emulator is the one exception, and it is a
development-environment detail rather than an architectural one.

The default `API_BASE_URL` (`http://10.0.2.2:8000`) reaches `backend`'s
directly published port, bypassing Traefik entirely -- `backend` does not serve
`/api/v1/search/*`, so search calls 404 against that default. Traefik routes by
`Host(api.${DOMAIN})` (typically `api.localhost`), so reaching `search-svc`
from the emulator means getting a request there with that Host header intact.

**Try this first**, and confirm it before relying on it -- the assumption below
was not verified against a real emulator:

```bash
adb reverse tcp:80 tcp:80
flutter run --dart-define=API_BASE_URL=http://api.localhost
```

The idea: `adb reverse` forwards any connection the emulator makes to its own
`localhost:80` straight to the host's port 80, where Traefik listens
(published by `compose.override.yml`), without touching the bytes of the
connection -- so whatever Host header the HTTP client sent survives unchanged,
and Traefik's `Host(api.localhost) && PathPrefix(/api/v1/search)` rule can
still match it. This depends on `api.localhost` resolving to loopback *on the
emulator itself* first, the same RFC 6761 treatment Chromium gives `.localhost`
names (documented for Playwright in issue #140) -- but Chromium's resolver and
Android's system resolver are different implementations, and it is not
confirmed here that Android's also treats an arbitrary `*.localhost` subdomain
as loopback rather than just the literal string `localhost`. Verify with
`adb logcat` while the app attempts a search, or a plain `adb shell ping -c1
api.localhost` -- if it resolves to `127.0.0.1`, the arrangement above works;
if the lookup fails outright, it does not, and `adb reverse` never sees a
connection to intercept.

**If that lookup fails**, a slower but dependable fallback avoids the DNS
question entirely by using a name Android's normal resolver can actually look
up over real DNS: [nip.io](https://nip.io) resolves `<anything>.<ip>.nip.io` to
`<ip>`, so pointing both the compose stack and the app at
`10.0.2.2.nip.io` sidesteps `.localhost` handling altogether (needs emulator
internet access, and reconfiguring the running stack's `DOMAIN`, so it is
better suited to a dedicated local mobile-testing stack than a shared one):

```bash
# In .env for that stack: DOMAIN=10.0.2.2.nip.io
flutter run --dart-define=API_BASE_URL=http://api.10.0.2.2.nip.io
```

Re-run `adb reverse` after every emulator restart -- the forwarding rule does
not persist across reboots. Either way, `DOMAIN` must match whatever the
running compose stack uses; adjust the `--dart-define` value if the stack
overrides it from the `.env.example` default.

## Run and build

From `mobile/`:

```bash
flutter pub get
flutter run
flutter build apk --dart-define=API_BASE_URL=https://api.example.com
```

The Android application ID is `com.armydep.cloudstorage`.

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

## Push notifications

This slice (issue #119) registers the device's FCM token with the backend and
lets the user opt in from Settings. **No notification is ever sent yet** --
that is a separate, later slice (#152). What exists today is purely the
plumbing: a device token reaches the backend, and a per-user `push_enabled`
preference can be turned on and off. Android only; no APNs, no web push.

### Two gates, both must be open

Push delivery (once #152 ships) will require **two independent things** to be
true at once, and "nothing arrives" during manual testing is almost always one
of them being closed by design, not a bug:

1. **The OS notification permission** (`POST_NOTIFICATIONS`, requested from
   the Settings toggle) -- declining it is a normal, supported outcome. The
   app continues to work fully; it just never registers a token or turns the
   preference on.
2. **The `push_enabled` preference** on the user's account -- defaults to
   `false` for every user (opt-in, never opt-out, per the phase 12 design
   doc). Turning the OS permission on does not imply this is on, and vice
   versa: the Settings toggle sets both together, but a user can decline the
   permission and never reach the preference, or (in principle, via the API)
   have the preference set without ever having granted the permission.

If you are testing this slice end-to-end, confirm both explicitly before
concluding something is broken.

### Firebase project setup (required, not included)

`google-services.json` in `android/app/` is currently a **placeholder** --
structurally valid enough for `flutter build apk` and CI to succeed, but it is
not a real Firebase project and `FirebaseMessaging.instance.getToken()` will
fail or return nothing against it. A human with access to the
[Firebase console](https://console.firebase.google.com) needs to:

1. Create **two** separate Firebase projects -- one for development, one for
   production (phase 12 design doc, decision 8). Do not share one project
   across environments.
2. Register an Android app in each with application ID
   `com.armydep.cloudstorage`.
3. Download each project's `google-services.json` and swap it into
   `android/app/google-services.json` for the environment you are building
   against, replacing the placeholder committed here.
4. Enable Cloud Messaging (FCM) on each project.

The placeholder file is safe to leave committed as the checked-in default --
it only stops working when someone tries to actually receive a token, at
which point the fix is step 3 above, done locally and never committed back.

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
│   ├── auth/        Session state, secure storage, API, and screens
│   └── push/        FCM device-token lifecycle and the push opt-in
└── main.dart        Application bootstrap
```
