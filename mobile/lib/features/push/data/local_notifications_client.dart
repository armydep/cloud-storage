import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// Thin wrapper around [FlutterLocalNotificationsPlugin], mirroring
/// [FcmClient]'s reason for existing: `flutter test` has no platform-channel
/// handler for it, so the push feature's own logic is unit-tested against a
/// fake instead.
///
/// Only used to show the notification a data-only FCM message never gets
/// shown automatically -- Android auto-displays a system notification for a
/// "notification" message when the app is backgrounded, but a pure "data"
/// message (design doc decision 12) always reaches app code instead, in
/// every app state, so the app must build the notification itself.
abstract interface class LocalNotificationsClient {
  Future<void> show({required int id, required String title, String? body});
}

const _channelId = 'push_default';
const _channelName = 'Notifications';
const _channelDescription = 'File sharing and account notifications.';

class FlutterLocalNotificationsClient implements LocalNotificationsClient {
  FlutterLocalNotificationsClient()
    : _plugin = FlutterLocalNotificationsPlugin();

  final FlutterLocalNotificationsPlugin _plugin;
  bool _initialized = false;

  Future<void> _ensureInitialized() async {
    if (_initialized) return;
    const androidSettings = AndroidInitializationSettings(
      '@mipmap/ic_launcher',
    );
    await _plugin.initialize(
      const InitializationSettings(android: androidSettings),
    );
    _initialized = true;
  }

  @override
  Future<void> show({
    required int id,
    required String title,
    String? body,
  }) async {
    await _ensureInitialized();
    await _plugin.show(
      id,
      title,
      body,
      const NotificationDetails(
        android: AndroidNotificationDetails(
          _channelId,
          _channelName,
          channelDescription: _channelDescription,
          importance: Importance.high,
          priority: Priority.high,
        ),
      ),
    );
  }
}
