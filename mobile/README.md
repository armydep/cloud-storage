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
