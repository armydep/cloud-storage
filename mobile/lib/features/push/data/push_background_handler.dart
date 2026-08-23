import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/widgets.dart';

import 'package:cloudestorage/features/push/data/local_notifications_client.dart';
import 'package:cloudestorage/features/push/domain/push_message.dart';

/// The FCM background/terminated message entry point.
///
/// This runs in its own isolate -- there is no `ProviderContainer`, no
/// widget tree, and no Firebase initialization carried over from the main
/// isolate, which is why this stays a free function rather than a class
/// method (the `firebase_messaging` plugin requires exactly that shape) and
/// why it repeats `Firebase.initializeApp()`.
///
/// A data-only FCM message (design doc decision 12) is never shown by the
/// OS automatically in any app state, unlike a "notification" message --
/// this is the code that makes "a notification appears with the app
/// closed" true at all.
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    await Firebase.initializeApp();
  } on Object catch (e) {
    debugPrint('Firebase initialization failed in background handler: $e');
  }

  await handleBackgroundMessageData(
    message.data,
    client: FlutterLocalNotificationsClient(),
  );
}

/// The testable half of the handler: given the data map and a
/// [LocalNotificationsClient], decides whether to show a notification and
/// with what content. Split out because the entry point above cannot be
/// exercised directly under `flutter test` -- it talks to real Firebase and
/// plugin initialization that has no test binding.
Future<void> handleBackgroundMessageData(
  Map<String, dynamic> data, {
  required LocalNotificationsClient client,
}) async {
  final content = parsePushMessageData(data);
  if (content == null) return;

  try {
    await client.show(id: content.notificationId, title: content.title);
  } on Object catch (e) {
    debugPrint('Failed to show local notification: $e');
  }
}
