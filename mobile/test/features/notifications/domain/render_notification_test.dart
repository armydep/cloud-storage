import 'package:cloudestorage/features/notifications/domain/notification_models.dart';
import 'package:cloudestorage/features/notifications/domain/render_notification.dart';
import 'package:flutter_test/flutter_test.dart';

AppNotification _notification({
  required String eventType,
  required Map<String, dynamic> payload,
}) {
  return AppNotification(
    id: 'notif-1',
    eventType: eventType,
    payload: payload,
    createdAt: DateTime.utc(2026, 8, 10, 12),
  );
}

void main() {
  group('renderNotificationText', () {
    // Wording must match frontend/src/features/notifications/renderNotification.ts
    // exactly (phase-9-in-app-notifications.md decision 6) -- the same event
    // reads differently on each platform if the two drift.
    test('renders file_shared with the sharer email and file name', () {
      final notification = _notification(
        eventType: 'file_shared',
        payload: {
          'sharer_email': 'alice@example.com',
          'file_name': 'report.pdf',
        },
      );

      expect(
        renderNotificationText(notification),
        'alice@example.com shared "report.pdf" with you',
      );
    });

    test('falls back to a generic message when payload fields are missing', () {
      final notification = _notification(
        eventType: 'file_shared',
        payload: {'sharer_email': 'alice@example.com'},
      );

      expect(renderNotificationText(notification), 'New notification');
    });

    test(
      'falls back to a generic message when payload fields are the wrong type',
      () {
        final notification = _notification(
          eventType: 'file_shared',
          payload: {'sharer_email': 42, 'file_name': 'report.pdf'},
        );

        expect(renderNotificationText(notification), 'New notification');
      },
    );

    test('falls back to a generic message for an unknown event type', () {
      final notification = _notification(
        eventType: 'some_future_event',
        payload: {'sharer_email': 'alice@example.com', 'file_name': 'x.pdf'},
      );

      expect(renderNotificationText(notification), 'New notification');
    });
  });
}
