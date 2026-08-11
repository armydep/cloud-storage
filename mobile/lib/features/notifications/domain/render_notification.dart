import 'package:cloudestorage/features/notifications/domain/notification_models.dart';

/// Notifications carry `event_type` and a structured `payload`, never
/// rendered text (phase-9-in-app-notifications.md decision 6). This mirrors
/// `frontend/src/features/notifications/renderNotification.ts` by design --
/// keep wording in step across both clients, or the same event reads
/// differently on each platform.
String renderNotificationText(AppNotification notification) {
  if (notification.eventType == 'file_shared') {
    final sharerEmail = notification.payload['sharer_email'];
    final fileName = notification.payload['file_name'];
    if (sharerEmail is String && fileName is String) {
      return '$sharerEmail shared "$fileName" with you';
    }
  }

  return 'New notification';
}
