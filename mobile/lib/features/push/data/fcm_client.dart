import 'package:firebase_messaging/firebase_messaging.dart';

/// Thin wrapper around [FirebaseMessaging], so the push feature's own logic
/// can be unit-tested with a fake -- `flutter test` has no Firebase plugin
/// bindings available, the same reason `SearchIndex` and `ApiClient` are
/// abstracted behind interfaces elsewhere in this app.
abstract interface class FcmClient {
  /// The device's current registration token, or `null` if one could not be
  /// obtained (no Play Services, no network, Firebase not initialized).
  Future<String?> getToken();

  /// Fires whenever FCM rotates the token -- on its own schedule, for
  /// reasons that have nothing to do with app usage.
  Stream<String> get onTokenRefresh;

  /// Requests the OS notification permission (`POST_NOTIFICATIONS` on
  /// Android 13+). Returns whether the app may show notifications
  /// afterward. A device token can still be obtained regardless of this
  /// permission -- it only gates whether a notification is actually shown.
  Future<bool> requestPermission();
}

class FirebaseFcmClient implements FcmClient {
  const FirebaseFcmClient();

  @override
  Future<String?> getToken() => FirebaseMessaging.instance.getToken();

  @override
  Stream<String> get onTokenRefresh =>
      FirebaseMessaging.instance.onTokenRefresh;

  @override
  Future<bool> requestPermission() async {
    final settings = await FirebaseMessaging.instance.requestPermission();
    return settings.authorizationStatus == AuthorizationStatus.authorized ||
        settings.authorizationStatus == AuthorizationStatus.provisional;
  }
}
