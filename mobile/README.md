# Cloude Storage mobile

Android-only Flutter application for Cloud File Storage. This directory is a
standalone client application; it does not belong to the React workspace in
`frontend/`.

The current scope is infrastructure only. Authentication, file management, and
synchronization will be added in later issues.

## Prerequisites

- Flutter stable, including the Android toolchain
- Android Studio with an Android SDK and emulator, or a physical Android device
- Java version supported by the generated Gradle wrapper
- A running Cloud File Storage backend

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
├── app/             Application widget and top-level composition
├── core/
│   ├── config/      Compile-time application configuration
│   └── network/     Reusable backend HTTP client foundation
└── main.dart        Application bootstrap
```
