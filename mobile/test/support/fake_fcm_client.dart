import 'package:cloudestorage/features/push/data/fcm_client.dart';

/// A no-op double for tests that render screens watching
/// `pushDeviceRegistrationProvider` (currently `FilesBrowserScreen`) but
/// aren't testing push themselves. The real `FirebaseFcmClient` talks to a
/// platform channel that has no handler registered under `flutter test`,
/// which hangs rather than throwing -- this avoids that entirely by never
/// returning a token, so registration is always a no-op.
class NoOpFcmClient implements FcmClient {
  const NoOpFcmClient();

  @override
  Future<String?> getToken() async => null;

  @override
  Stream<String> get onTokenRefresh => const Stream.empty();

  @override
  Future<bool> requestPermission() async => false;
}
